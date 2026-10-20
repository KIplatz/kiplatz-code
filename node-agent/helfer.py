# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import getpass
import ipaddress
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
import datenfluss
import geheim
import plattform
import sicher_schreiben
import sprachen

UPDATE_BLICK_S = 300
SCHLUESSEL_PFLEGE_S = 3600
PROTOKOLL = "protokoll.txt"
STAND = "helfer-stand.json"
STAND_S = 60
STAND_ALT_S = 3 * STAND_S
ONLINE_S = 360
LESBAR = "helfer-protokoll.txt"
LESBAR_MAX = 512 * 1024


_MAC_SPRACHE: str | None = None


def _mac_sprache() -> str:
    global _MAC_SPRACHE
    if _MAC_SPRACHE is None:
        _MAC_SPRACHE = ""
        if plattform.system() == "macos":
            import re
            import subprocess
            for schluessel in ("AppleLanguages", "AppleLocale"):
                try:
                    r = subprocess.run(["/usr/bin/defaults", "read", "-g", schluessel], capture_output=True, text=True, timeout=3, check=False)
                except (OSError, subprocess.SubprocessError):
                    continue
                m = re.search(r"[A-Za-z]{2}", r.stdout or "") if r.returncode == 0 else None
                if m:
                    _MAC_SPRACHE = m.group(0).lower()
                    break
    return _MAC_SPRACHE


def englisch() -> bool:
    mac = _mac_sprache()
    if mac:
        return mac != "de"
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


def _zahl_ganz(n: int) -> str:
    return f"{n:,}" if englisch() else f"{n:,}".replace(",", ".")


def _ist_adresse(host: str) -> bool:
    try:
        ipaddress.ip_address(str(host).strip("[]"))
        return True
    except ValueError:
        return False


def lesbar(core: app_core.AppCore, satz: str) -> None:
    try:
        core.ensure_directories()
        pfad = core.diagnosis_dir / LESBAR
        if pfad.is_file() and pfad.stat().st_size > LESBAR_MAX:
            rest = pfad.read_bytes()[-(LESBAR_MAX // 2):]
            sicher_schreiben.roh(pfad, rest[rest.find(b"\n") + 1:])
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M") + "  " + _t(satz) + "\n")
    except OSError:
        pass


def stand_erheben(api: app_web.Api) -> dict:
    ki = api._ki.zustand()
    r = api._rechen.zustand()
    s = api._halter.stand()
    c = api._credits_dict()
    eigener = datenfluss.host_von(api._community.adresse)
    verbindungen, andere = [], {"host": "", "anfragen": 0, "raus": 0, "rein": 0}
    kontakt = ""
    for h in datenfluss.stand()["hosts"]:
        if h["host"] == eigener:
            kontakt = h.get("zuletzt") or ""
        if _ist_adresse(h["host"]) and h["host"] != eigener:
            for k in ("anfragen", "raus", "rein"):
                andere[k] += int(h.get(k) or 0)
        else:
            verbindungen.append({k: h.get(k) for k in ("host", "anfragen", "raus", "rein")})
    if andere["anfragen"]:
        verbindungen.append(andere)
    return {"version": 1, "zeit": time.time(), "bau": app_core.APP_BUILD, "server": eigener, "kontakt": kontakt,
            "modell": ki.get("modell") if ki.get("laeuft") else None, "modell_auf": ki.get("geraet"),
            "antwortet": bool(api._kann_fuer_andere_antworten()), "phase": r.get("phase"), "arbeit": str(r.get("text") or "").split("\n")[0],
            "gesamt": {k: int((r.get("gesamt") or {}).get(k) or 0) for k in ("antworten", "abschnitte", "credits")},
            "scheiben": {"anzahl": int(s.get("anzahl") or 0), "mb": float(s.get("mb") or 0), "geliefert": int(s.get("geliefert") or 0)},
            "guthaben": c.get("guthaben"), "verbindungen": verbindungen}


def _kontakt_zeit(stand: dict) -> float | None:
    import calendar
    try:
        return float(calendar.timegm(time.strptime(str(stand.get("kontakt") or ""), "%Y-%m-%dT%H:%M:%SZ")))
    except (ValueError, OverflowError):
        return None


def online(stand: dict, jetzt: float | None = None) -> bool:
    t = _kontakt_zeit(stand)
    return t is not None and (jetzt if jetzt is not None else time.time()) - t <= ONLINE_S


def _mehrzahl(n: int, eins: str, viele: str) -> str:
    return eins if n == 1 else viele.format(_zahl_ganz(n))


def stand_vergleichen(vorher: dict | None, jetzt: dict) -> list[str]:
    saetze = []
    war_online = online(vorher, vorher["zeit"]) if vorher else None
    ist_online = online(jetzt, jetzt["zeit"])
    if ist_online != war_online:
        saetze.append(f"Verbunden mit {jetzt['server']}." if ist_online else f"Keine Verbindung zu {jetzt['server']}. Der Helfer versucht es weiter.")
    if (vorher or {}).get("modell") != jetzt["modell"] and (vorher or jetzt["modell"]):
        saetze.append(f"Modell für Antworten: {jetzt['modell']} auf {_t(str(jetzt['modell_auf']))}." if jetzt["modell"] else "Kein Modell für Antworten geladen.")
    alt = (vorher or {}).get("gesamt") or {}
    neu = jetzt["gesamt"]
    d = neu["antworten"] - int(alt.get("antworten", neu["antworten"]))
    if d > 0:
        saetze.append(_mehrzahl(d, "1 Frage der Community beantwortet.", "{0} Fragen der Community beantwortet."))
    d = neu["abschnitte"] - int(alt.get("abschnitte", neu["abschnitte"]))
    if d > 0:
        saetze.append(_mehrzahl(d, "1 Abschnitt für die Suche aufbereitet.", "{0} Abschnitte für die Suche aufbereitet."))
    d = neu["credits"] - int(alt.get("credits", neu["credits"]))
    if d > 0:
        saetze.append(_mehrzahl(d, "1 Credit verdient.", "{0} Credits verdient."))
    s_alt, s_neu = (vorher or {}).get("scheiben") or {}, jetzt["scheiben"]
    if vorher and s_neu["anzahl"] != s_alt.get("anzahl"):
        saetze.append(f"Scheiben des gemeinsamen Wissens auf diesem Gerät: {s_neu['anzahl']} ({_zahl(s_neu['mb'])} MB).")
    d = s_neu["geliefert"] - int(s_alt.get("geliefert", s_neu["geliefert"]))
    if d > 0:
        saetze.append(_mehrzahl(d, "1 Scheibe für eine Stichprobe geliefert.", "{0} Scheiben für Stichproben geliefert."))
    return saetze


def _stand_schreiben(api: app_web.Api, core: app_core.AppCore, vorher: dict | None) -> dict | None:
    try:
        jetzt = stand_erheben(api)
        sicher_schreiben.json_datei(core.base_dir / STAND, jetzt)
        for satz in stand_vergleichen(vorher, jetzt):
            lesbar(core, satz)
        return jetzt
    except Exception as exc:
        _melden(core, f"FEHLER stand: {type(exc).__name__}", auch_zeigen=False)
        return vorher


def daten_ordner(args) -> Path:
    basis = Path(args.daten) if getattr(args, "daten", None) else plattform.daten_ordner()
    if getattr(args, "spielwiese", False):
        basis = app_web.spielwiese_vorbereiten(basis.with_name(basis.name + "-spielwiese"), ki_von=basis / "ki")
    return basis


def _core(args) -> app_core.AppCore:
    core = app_core.AppCore(base_dir=daten_ordner(args))
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
            if args.mit_code or args.spielwiese:
                if args.spielwiese and not args.mit_code:
                    _sag("Auf der Spielwiese trittst du mit dem Code „spielwiese“ bei.")
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
        lesbar(core, f"Update auf Bau {neu} abgelehnt: {_t(exc.detail)}")
        return False
    if was == "grundlage":
        _GRUNDLAGE_BAU = neu
        _melden(core, f"HINWEIS update: Bau {neu} braucht Python {text}; der Helfer holt sein ganzes Paket neu (kiplatz.at/helfer)")
        lesbar(core, f"Bau {neu} braucht ein neues Helfer-Paket (Python {text}). Bitte das Paket neu holen.")
        return False
    _melden(core, f"OK update {was}: {text}")
    if was == "aktualisiert":
        lesbar(core, f"Update auf Bau {neu} eingesetzt. Der Helfer startet neu.")
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
    lesbar(core, f"Der Helfer ist gestartet (Bau {app_core.APP_BUILD}).")
    neu_starten = False
    try:
        api.vorbereiten(selbst_einrichten=False, ki_auto=True)
        if api.prep_error:
            _melden(core, f"FEHLER vorbereiten: {api.prep_error}")
            lesbar(core, f"Beim Start ging etwas nicht: {_t(str(api.prep_error))}")
        vorher = _stand_schreiben(api, core, None)
        seit_update = seit_pflege = 0.0
        while not stopp.wait(STAND_S):
            vorher = _stand_schreiben(api, core, vorher)
            seit_update += STAND_S
            if seit_update < UPDATE_BLICK_S:
                continue
            seit_update = 0.0
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
        if not neu_starten:
            lesbar(core, "Der Helfer ist beendet.")
    if neu_starten:
        starter = programm / plattform.STARTER
        os.execv(str(starter), [str(starter), "start", *(["--daten", args.daten] if args.daten else []), *(["--spielwiese"] if args.spielwiese else [])])
    return 0


def _stand_lesen(core: app_core.AppCore) -> dict:
    d = sicher_schreiben.json_laden(core.base_dir / STAND, {}, art=dict)
    return d if isinstance(d, dict) and d.get("version") == 1 else {}


def status(args) -> int:
    core = _core(args)
    api = _api(core)
    try:
        zustand, g = anmeldung(api)
        sperre = plattform.Sperre(core.base_dir)
        laeuft = not sperre.holen()
        sperre.freigeben()
        st = _stand_lesen(core)
        frisch = laeuft and st and time.time() - float(st.get("zeit") or 0) <= STAND_ALT_S
        r = api._rechen.zustand()
        heute, gesamt = r.get("heute") or {}, r.get("gesamt") or {}
        s = api._halter.stand()
        c = api._credits_dict()
        f = core.load_freigabe()
        if getattr(args, "json", False):
            print(json.dumps({"angemeldet": zustand == "da", "laeuft": laeuft, "online": bool(frisch and online(st)), "bau": app_core.APP_BUILD,
                              "modell": st.get("modell") if frisch else None, "modell_auf": st.get("modell_auf") if frisch else None,
                              "antwortet": st.get("antwortet") if frisch else None, "phase": st.get("phase") if frisch else None,
                              "fragen": {"heute": int(heute.get("antworten") or 0), "gesamt": int(gesamt.get("antworten") or 0)},
                              "abschnitte": {"heute": int(heute.get("abschnitte") or 0), "gesamt": int(gesamt.get("abschnitte") or 0)},
                              "scheiben": {"anzahl": int(s.get("anzahl") or 0), "mb": float(s.get("mb") or 0),
                                           "geliefert": int((st.get("scheiben") or {}).get("geliefert") or 0) if frisch else None},
                              "credits": {"guthaben": c.get("guthaben"), "heute": int(heute.get("credits") or 0)},
                              "verbindungen": st.get("verbindungen") if frisch else None,
                              "grenzen": {"cpu_prozent": f.cpu_prozent, "ram_gib": f.ram_gib},
                              "autostart": plattform.autostart_an_ist(),
                              "protokoll": str(core.diagnosis_dir / LESBAR)}, ensure_ascii=False, indent=2))
            return 0
        if zustand == "da":
            _sag(f"Angemeldet als „{g['name']}“ bei {api._community.adresse}.")
        elif zustand == "unlesbar":
            _sag(f"Angemeldet, aber gerade nicht lesbar: {g}.")
        else:
            _sag("Noch nicht eingerichtet: kiplatz-helfer einrichten")
        konto = api._konto_dict()
        if konto:
            _sag(f"KIplatz-Konto: {konto['name']}")
        _sag("Der Helfer läuft gerade." if laeuft else "Der Helfer läuft gerade nicht.")
        if frisch:
            server = st.get("server") or ""
            _sag(f"Online: ja, {server} hat zuletzt um {time.strftime('%H:%M', time.localtime(_kontakt_zeit(st)))} geantwortet." if online(st)
                 else f"Online: nein, {server} hat seit {ONLINE_S // 60} Minuten nicht geantwortet. Der Helfer versucht es weiter.")
            if st.get("modell"):
                _sag(f"Modell für Antworten: {st['modell']} auf {_t(str(st.get('modell_auf') or '?'))}.")
            elif st.get("antwortet"):
                _sag("Modell für Antworten: wird gerade geladen.")
            else:
                _sag("Fragen der Community beantworten Geräte mit Grafikkarte (am Mac der Apple-Chip) und 16 GB Arbeitsspeicher. Dieses Gerät erledigt Hintergrundarbeit für das gemeinsame Wissen.")
            if st.get("arbeit"):
                _sag(f"Gerade: {_t(st['arbeit'])}")
        elif laeuft:
            _sag("Der Helfer startet gerade; in einer Minute steht hier mehr.")
        _sag(f"Beantwortete Fragen: {_zahl_ganz(int(heute.get('antworten') or 0))} heute, {_zahl_ganz(int(gesamt.get('antworten') or 0))} insgesamt.")
        _sag(f"Für die Suche aufbereitet: {_zahl_ganz(int(heute.get('abschnitte') or 0))} Abschnitte heute, {_zahl_ganz(int(gesamt.get('abschnitte') or 0))} insgesamt.")
        geliefert = int((st.get("scheiben") or {}).get("geliefert") or 0) if frisch else 0
        anzahl, mb = int(s.get("anzahl") or 0), _zahl(float(s.get("mb") or 0))
        _sag(f"Scheiben des gemeinsamen Wissens: {anzahl} ({mb} MB), seit dem Start {geliefert} für Stichproben geliefert." if geliefert
             else f"Scheiben des gemeinsamen Wissens: {anzahl} ({mb} MB).")
        if c.get("guthaben") is not None:
            _sag(f"Credits: {_zahl_ganz(int(c['guthaben']))}, heute {_zahl_ganz(int(heute.get('credits') or 0))} verdient.")
        _sag("Arbeit für die Community: an" if core.run_state() is app_core.node_local_state.RunState.ACTIVE else "Arbeit für die Community: aus")
        _sag("Autostart: über Docker" if plattform.im_container() else "Autostart: an" if plattform.autostart_an_ist() else "Autostart: aus")
        _sag(f"Grenzen: {f.cpu_prozent} % Prozessor, {_zahl(f.ram_gib)} GB Arbeitsspeicher. Bau {app_core.APP_BUILD}.")
        if frisch and st.get("verbindungen"):
            _sag("Verbindungen seit dem Start (nur Gegenstelle, Anzahl und Menge, nie ein Inhalt):")
            for v in st["verbindungen"]:
                wer = v.get("host") or _t("andere PCs der Community (Modelle von PC zu PC)")
                zeile = (f"{wer}: {_zahl_ganz(int(v.get('anfragen') or 0))} Anfragen, {_zahl(round(int(v.get('raus') or 0) / 1e6, 1))} MB hinaus und "
                         f"{_zahl(round(int(v.get('rein') or 0) / 1e6, 1))} MB herein")
                print("  " + _t(zeile), flush=True)
        p = core.diagnosis_dir / LESBAR
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
    s = unter.add_parser("status", help=_t("zeigen, was der Helfer gerade tut"))
    s.add_argument("--json", action="store_true", help=_t("derselbe Stand als JSON, für eigene Werkzeuge"))
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
