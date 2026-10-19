# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import getpass
import json
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

_HIER = Path(__file__).resolve().parent
if str(_HIER) not in sys.path:
    sys.path.insert(0, str(_HIER))

import app_core
import app_install
import app_web
import community
import geheim
import plattform
import sprachen

UPDATE_BLICK_S = 300
SCHLUESSEL_PFLEGE_S = 3600
PROTOKOLL = "protokoll.txt"


def englisch() -> bool:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        wert = os.environ.get(name, "")
        if wert:
            return not wert.lower().startswith("de")
    return False


_KATALOG = False


def _t(text: str) -> str:
    global _KATALOG
    if not englisch():
        return text
    if not _KATALOG:
        try:
            sprachen.laden(json.loads((app_web.webapp_dir() / "sprache-en.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            sprachen.laden({})
        _KATALOG = True
    return sprachen.uebersetzen(text)


def _sag(text: str) -> None:
    print("\n".join(_t(z) for z in str(text).split("\n")), flush=True)


def _zahl(x: float) -> str:
    return f"{x:g}" if englisch() else app_core.zahl_de(x)


def daten_ordner(args) -> Path:
    basis = Path(args.daten) if getattr(args, "daten", None) else plattform.daten_ordner()
    if getattr(args, "spielwiese", False):
        basis = app_web.spielwiese_vorbereiten(basis.with_name(basis.name + "-spielwiese"), ki_von=basis / "ki")
    return basis


def _core(args) -> app_core.AppCore:
    core = app_core.AppCore(app_core.Profile.TEST, base_dir=daten_ordner(args))
    core.ensure_directories()
    return core


def _melden(core: app_core.AppCore, zeile: str, *, auch_zeigen: bool = True) -> None:
    app_web._log(core, "helfer: " + zeile)
    if auch_zeigen:
        _sag(zeile)


def _api(core: app_core.AppCore) -> app_web.Api:
    return app_web.Api(core, geraet_name=app_web._geraet_name(core), install_dir=plattform.programm_ordner())


def _freigabe(core: app_core.AppCore, cpu: int | None, ram: float | None) -> app_core.Freigabe:
    alt = core.load_freigabe()
    if not (core.base_dir / app_core.FREIGABE_FILENAME).exists():
        alt = app_core.recommended_freigabe(core.load_first_start())
    f = app_core.Freigabe(False, int(alt.cpu_prozent if cpu is None else cpu), float(alt.ram_gib if ram is None else ram), alt.speicher_mb, "")
    core.save_freigabe(f)
    return f


def anmeldung(api: app_web.Api) -> tuple[str, object]:
    d = api._community.geraet()
    if d is not None:
        return "da", d
    datei = api._community.dir / community.GERAET_DATEI
    if not datei.is_file():
        return "fehlt", None
    try:
        geheim.lesen(str(json.loads(datei.read_text(encoding="utf-8")).get("schluessel") or ""))
    except geheim.GeheimError as exc:
        return "unlesbar", exc.detail
    except (OSError, ValueError, AttributeError):
        return "unlesbar", "die gespeicherte Anmeldung ist beschädigt"
    return "unlesbar", "die gespeicherte Anmeldung ist unvollständig"


def _grafisch() -> bool:
    return plattform.system() == "macos" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def mit_konto(api: app_web.Api, *, warten_s: float = 1.0) -> dict:
    r = api.community_beitreten_konto(browser=False)
    if not r["ok"]:
        return r
    adresse = r["daten"]["adresse"]
    _sag("Öffne diese Adresse im Browser, gern auch am Handy, melde dich mit deinem KIplatz-Konto an und bestätige „Einen neuen PC … verbinden?“:")
    print(adresse, flush=True)
    if _grafisch():
        try:
            webbrowser.open(adresse)
        except Exception:
            pass
    _sag("Der Helfer wartet auf deine Bestätigung, höchstens 10 Minuten (abbrechen mit Strg+C).")
    try:
        while True:
            st = api.community_beitreten_konto_stand()["daten"] or {}
            if not st.get("laeuft"):
                break
            time.sleep(warten_s)
    except KeyboardInterrupt:
        api.community_beitreten_konto_abbrechen()
        return {"ok": False, "text": "Abgebrochen. Es wurde nichts angemeldet."}
    if st.get("fertig"):
        return {"ok": True, "text": f"Willkommen. Dieses Gerät gehört jetzt mit dem Konto {st.get('konto', '')} zur Community."}
    return {"ok": False, "text": st.get("fehler") or "Abgebrochen. Es wurde nichts angemeldet."}


def einrichten(args) -> int:
    core = _core(args)
    first = core.run_first_start_check()
    api = _api(core)
    try:
        zustand, grund = anmeldung(api)
        if zustand == "unlesbar":
            _sag(f"Dieses Gerät ist schon angemeldet, die Anmeldung ist gerade nicht lesbar: {grund}. Nichts wurde geändert.")
            return 3
        if zustand == "fehlt":
            if args.mit_code:
                r = api.community_beitreten(getpass.getpass(_t("Code vom Admin:") + " "))
            else:
                r = mit_konto(api)
            if not r["ok"]:
                _sag(r["text"])
                return 1
            _sag(r["text"])
            _melden(core, "OK beigetreten", auch_zeigen=False)
        else:
            _melden(core, "Dieses Gerät gehört schon zur Community.")
        f = _freigabe(core, args.cpu, args.ram)
        core.start()
        if first.gpu_names:
            _sag(f"Erkannt: {first.cpu_cores or '?'} Kerne, {_zahl(first.memory_gib)} GB Arbeitsspeicher, Grafik: {', '.join(first.gpu_names)}.")
        else:
            _sag(f"Erkannt: {first.cpu_cores or '?'} Kerne, {_zahl(first.memory_gib)} GB Arbeitsspeicher, keine eigene Grafikkarte (der Prozessor erarbeitet).")
        _sag(f"Der Helfer nimmt höchstens {f.cpu_prozent} % des Prozessors und {_zahl(f.ram_gib)} GB Arbeitsspeicher (ändern: kiplatz-helfer grenzen).")
    finally:
        api.herunterfahren()
    if args.ohne_autostart:
        _sag(f"Starten: {plattform.programm_ordner() / plattform.STARTER} start")
        return 0
    _sag(plattform.autostart_an(protokoll=core.diagnosis_dir / "helfer.log"))
    _sag(f"Protokoll: {core.diagnosis_dir / PROTOKOLL}")
    return 0


_GRUNDLAGE_BAU = ""


def _update_pruefen(api: app_web.Api, core: app_core.AppCore, programm: Path) -> bool:
    global _GRUNDLAGE_BAU
    if api._update_warten():
        return False
    neu = app_install.neuester_bau(api._community.adresse, api._community._oeffner)
    if not neu or neu <= app_core.APP_BUILD or neu == _GRUNDLAGE_BAU:
        return False
    try:
        was, text = app_install.update_quelle_holen(api._community.adresse, programm, eigener_bau=app_core.APP_BUILD, oeffner=api._community._oeffner)
    except app_core.AppError as exc:
        _melden(core, f"ABGELEHNT update: {exc.code}: {exc.detail}")
        return False
    if was == "grundlage":
        _GRUNDLAGE_BAU = neu
        _melden(core, f"HINWEIS update: Bau {neu} braucht Python {text}; der Helfer holt sein ganzes Paket neu (kiplatz.at/helfer)")
        return False
    _melden(core, f"OK update {was}: {text}")
    return was == "aktualisiert"


def starten(args) -> int:
    core = _core(args)
    sperre = plattform.Sperre(core.base_dir)
    if not sperre.holen():
        _sag("Der Helfer läuft schon (für diesen Datenordner).")
        return 0
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass
    programm = plattform.programm_ordner()
    api = _api(core)
    zustand, grund = anmeldung(api)
    if zustand != "da":
        sperre.freigeben()
        if zustand == "fehlt":
            _sag("Noch nicht eingerichtet: kiplatz-helfer einrichten")
            return 0
        (programm / "update-probe.starts").unlink(missing_ok=True)
        _melden(core, f"HINWEIS start: Anmeldung gerade nicht lesbar ({grund}); neuer Versuch durch den Dienst")
        return 3
    core.run_first_start_check()
    app_install.alt_aufraeumen(programm)
    app_install.update_bestaetigen(programm)
    stopp = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_a: stopp.set())
    _melden(core, f"OK start Bau {app_core.APP_BUILD} auf {plattform.system()}, Daten in {core.base_dir}")
    neu_starten = False
    try:
        api.vorbereiten(selbst_einrichten=False, ki_auto=True)
        if api.prep_error:
            _melden(core, f"FEHLER vorbereiten: {api.prep_error}")
        seit_pflege = 0.0
        while not stopp.wait(UPDATE_BLICK_S):
            try:
                if _update_pruefen(api, core, programm):
                    neu_starten = True
                    break
            except Exception as exc:
                _melden(core, f"FEHLER update: {type(exc).__name__}", auch_zeigen=False)
            seit_pflege += UPDATE_BLICK_S
            if seit_pflege >= SCHLUESSEL_PFLEGE_S:
                seit_pflege = 0.0
                api._schluessel_pflegen()
    finally:
        api.herunterfahren()
        sperre.freigeben()
        _melden(core, "OK beendet" + (", Neustart mit der neuen Fassung" if neu_starten else ""))
    if neu_starten:
        starter = programm / plattform.STARTER
        os.execv(str(starter), [str(starter), "start", *(["--daten", args.daten] if args.daten else []), *(["--spielwiese"] if args.spielwiese else [])])
    return 0


def status(args) -> int:
    core = _core(args)
    api = _api(core)
    try:
        zustand, g = anmeldung(api)
        if zustand == "da":
            _sag(f"Angemeldet als „{g['name']}“ bei {api._community.adresse}.")
        elif zustand == "unlesbar":
            _sag(f"Angemeldet, aber gerade nicht lesbar: {g}.")
        else:
            _sag("Noch nicht eingerichtet: kiplatz-helfer einrichten")
        konto = api._konto_dict()
        if konto:
            _sag(f"KIplatz-Konto: {konto['name']}")
        _sag("Arbeit für die Community: an" if core.run_state() is app_core.node_local_state.RunState.ACTIVE else "Arbeit für die Community: aus")
        _sag("Autostart: an" if plattform.autostart_an_ist() else "Autostart: aus")
        sperre = plattform.Sperre(core.base_dir)
        laeuft = not sperre.holen()
        sperre.freigeben()
        _sag("Der Helfer läuft gerade." if laeuft else "Der Helfer läuft gerade nicht.")
        f = core.load_freigabe()
        _sag(f"Grenzen: {f.cpu_prozent} % Prozessor, {_zahl(f.ram_gib)} GB Arbeitsspeicher. Bau {app_core.APP_BUILD}.")
        p = core.diagnosis_dir / PROTOKOLL
        if p.is_file():
            _sag(f"Protokoll ({p}), die letzten Zeilen:")
            for zeile in p.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]:
                print("  " + zeile)
    finally:
        api.herunterfahren()
    return 0


def grenzen(args) -> int:
    core = _core(args)
    try:
        f = _freigabe(core, args.cpu, args.ram)
    except app_core.AppError as exc:
        _sag(exc.detail)
        return 1
    _sag(f"Gespeichert: höchstens {f.cpu_prozent} % des Prozessors und {_zahl(f.ram_gib)} GB Arbeitsspeicher. Gilt beim nächsten Start des Helfers.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if englisch():
        community.SPRACHE = "en"
    p = argparse.ArgumentParser(prog="kiplatz-helfer", description=_t("KIplatz-Helfer: dein PC hilft der Community, ohne Fenster."))
    p.add_argument("--daten", help=argparse.SUPPRESS)
    p.add_argument("--spielwiese", action="store_true", help=argparse.SUPPRESS)
    unter = p.add_subparsers(dest="befehl", required=True)
    e = unter.add_parser("einrichten", help=_t("mit dem KIplatz-Konto beitreten und den Autostart einschalten"))
    e.add_argument("--mit-code", action="store_true", help=_t("mit dem Code vom Admin statt mit dem KIplatz-Konto (wird abgefragt)"))
    e.add_argument("--cpu", type=int, default=None)
    e.add_argument("--ram", type=float, default=None)
    e.add_argument("--ohne-autostart", action="store_true")
    unter.add_parser("start", help=_t("den Helfer im Vordergrund laufen lassen (so startet ihn der Dienst)"))
    unter.add_parser("status", help=_t("zeigen, ob er angemeldet ist und läuft"))
    unter.add_parser("an", help=_t("Autostart und Dienst einschalten"))
    unter.add_parser("aus", help=_t("Autostart und Dienst ausschalten; die Daten bleiben"))
    g = unter.add_parser("grenzen", help=_t("Prozessor- und Arbeitsspeicher-Grenze setzen"))
    g.add_argument("--cpu", type=int, default=None)
    g.add_argument("--ram", type=float, default=None)
    args = p.parse_args(argv)
    if plattform.system() == "windows":
        _sag("Unter Windows gibt es das Programm mit Fenster (kiplatz.at/download).")
        return 1
    plattform.zertifikate_des_systems()
    try:
        if args.befehl == "einrichten":
            return einrichten(args)
        if args.befehl == "start":
            return starten(args)
        if args.befehl == "status":
            return status(args)
        if args.befehl == "grenzen":
            return grenzen(args)
        if args.befehl == "an":
            _sag(plattform.autostart_an(protokoll=_core(args).diagnosis_dir / "helfer.log"))
            return 0
        _sag(plattform.autostart_aus())
        return 0
    except app_core.AppError as exc:
        _sag(app_web.menschlich(exc.code, exc.detail))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
