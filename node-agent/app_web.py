# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import platform
import re
import shutil
import webbrowser
import subprocess
import sys
import contextlib
import dataclasses
import itertools
import threading
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import pakete_tausch
pakete_tausch.beim_start()

import abgleich_geraet
import zuhause
import fenster as fragfenster
import dateisuche
import app_core
import app_install
import bedeutung
import bewertung
import credits
import anhaenge
import skills
import meine_ki
import sprechen
import gedaechtnis
import vorwaermen
import warmhalten
import weitergeben
import morgenbericht
import pruefstand
import satzweise
import auswahl
import bildschirm
import datenfluss
import einmal
import gespraeche
import hotkey
import konto_basis

import kalender_dach
import kalender_welt
import region
import antwortspeicher_basis
import belege
import stellen
import wikipedia
import grafik_last
import geheim
import messwerte
import vorlesen
import neuerungen
import gespraeche_import
import hausordnung
import krisenhilfe
import heimnetz
import ki_laufzeit
import modell_katalog
import nachschauen
import ordner_aufgaben
import node_local_state
import vermittlung_basis
import wissen
import absicht
import kurse
import rechnen
import antwortsprache
import community
import gemeinschaft
import wortindex
KONTO_ISSUER = "https://werkstatt.kiplatz.at"
PC_ART = "Windows-PC" if sys.platform == "win32" else "Mac" if sys.platform == "darwin" else "Linux-PC"
BEITRITT_BLICK_S = 3.0
BEITRITT_FRIST_S = 600.0
import pruefung
import selbstauskunft
import woerterbuch_at
import bezug
import schriftstueck
import osm_orte
import quellen_stand
import schnittstelle
import sicher_schreiben
import rechenarbeit
import scheiben_halter
import themen
import verteiler

WEBAPP_DIRNAME = "webapp"
QUELLTEXT_SATZ = "Der Quelltext von Programm und App ist offen (Lizenz GNU AGPL 3): kiplatz.at/quelltext"
INDEX_NAME = "index.html"
GROUND = "#f4f6f5"
KI_WARTEN_S = 180
WARTEN_TAKT_S = 0.7
ABHOLEN_WARTEN_S = 10.0
UPDATE_PRUEFRUNDE_HOECHSTENS_S = 30 * 60
PRUEFRUNDE_NACH_FEHLER_S = 10 * 60
UPDATE_ANTWORT_HOECHSTENS_S = 600
ABHOLEN_FEHLVERSUCHE = 2
KNAPP_TREFFER = 2
KNAPP_ZEICHEN = 500
WIKI_KANDIDATEN = 8
LIVE_STELLEN = 6
LIVE_STELLEN_LISTE = 8
PRUEFER_MODELLE = ("14B", "8B")
PRUEFSTAND_MITGLIEDER = True
TRAINING_TAKT_S = 10.0
KURZTEST_SKRIPT = "kurztest.py"
KURZTEST_ART = ("--ohne-systemtext", "--batch", "8")
KURZTEST_HOECHSTENS_S = 9 * 60
PRUEFSTAND_VERSUCHE = 3
PRUEFSTAND_HOCHLADEN_VERSUCHE = 3
PRUEFSTAND_HOCHLADEN_WARTE_S = 60.0
PRUEFSTAND_ANHALTEN_S = 120.0
PRUEFEN_PAUSIERT_TEXT = "Prüfen und Training sind am Server pausiert, bis die Community genug freie Rechner hat."
MESS_SUCHE_ABSTAND_S = 40.0
MESS_SUCHEN_NACHT_MAX = 400
PRUEFSTAND_AB_B = 8.0
WARTEN_UNGENOMMEN_S = 25
WARTEN_UNGENOMMEN_BESCHAEFTIGT_S = 70
WARTEN_ANTWORT_S = 150


LIZENZEN = ("KIplatz: freie Software unter der GNU AGPL 3.0 oder später (Programm und App). "
            "KI-Laufzeit: llama.cpp und ggml (MIT, © The ggml authors), unverändert aus Ollama (MIT, © Ollama), unterschrieben von Ollama Inc.; "
            "Spracherkennung: whisper.cpp (MIT, © The ggml authors). "
            "Modelle: Ministral 3 von Mistral AI (Apache-2.0); Qwen3-Embedding 0.6B, Qwen3-Reranker 0.6B und Qwen3-ASR 0.6B von Qwen, Alibaba Cloud (Apache-2.0). "
            "Programm: Python (PSF-Lizenz); pywebview, psutil, pypdf, pycparser, segno (BSD); pythonnet, clr-loader, bottle, proxy_tools, cffi, truststore (MIT); "
            "cryptography (Apache-2.0 oder BSD); pywin32, typing-extensions (PSF-Lizenz); WebView2 (Microsoft, Teil von Windows). "
            "Wissen: Wikipedia (Texte unter CC BY-SA 4.0, © die Autorinnen und Autoren der Wikipedia). "
            "Orte: OpenStreetMap (Daten unter ODbL, © OpenStreetMap-Mitwirkende).")


def webapp_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", _HERE))
    return base / WEBAPP_DIRNAME


def sprache_einbauen(html: str) -> str:
    try:
        werk = (webapp_dir() / "oberflaeche-sprache.js").read_text(encoding="utf-8")
        liste = json.loads((webapp_dir() / "sprache-en.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return html
    daten = json.dumps(liste, ensure_ascii=False).replace("<", "\\u003c")
    kopf = f"<script>globalThis.KIPLATZ_TEXTE_EN = {daten};</script>\n<script>{werk}</script>\n"
    return html.replace("</head>", kopf + "</head>", 1)


def build_core(argv: list[str] | None = None) -> tuple[app_core.AppCore, argparse.Namespace]:
    parser = argparse.ArgumentParser(prog="community-ai", description="KIplatz: das Programm")
    parser.add_argument("--basis", type=Path, default=None, help="anderer Datenordner (Tests, Proben)")
    parser.add_argument("--autostart", action="store_true", help="wird von Windows beim Anmelden übergeben; startet minimiert")
    parser.add_argument("--selbsttest", action="store_true", help="alle Aktionen ohne Fenster ausführen und berichten")
    parser.add_argument("--ki-holen", action="store_true", help="KI-Laufzeit und Modell ohne Fenster holen und prüfen")
    parser.add_argument("--anbieten", action="store_true", help="„KIplatz im Heimnetz anbieten“ einschalten und das Fenster öffnen")
    parser.add_argument("--spielwiese", action="store_true", help="Spielwiese für Mitbauende: eigener Datenordner, eigener Server (Wegwerfdaten)")
    parser.add_argument("--entfernen", action="store_true", help="wird von Windows (Einstellungen → Apps) aufgerufen: Programm ohne Fenster entfernen, Daten bleiben")
    args = parser.parse_args(argv)
    umzug = None
    if args.spielwiese:
        args.basis = spielwiese_vorbereiten(args.basis or Path.home() / SPIELWIESE_DIRNAME)
    elif args.basis is None:
        umzug = app_core.daten_umziehen(fenster_offen=einmal.belegt)
        args.basis = umzug.ordner
    core = app_core.AppCore(base_dir=args.basis)
    if umzug is not None and umzug.satz:
        _log(core, umzug.satz)
    return core, args


SPIELWIESE_DIRNAME = "CommunityAI-Spielwiese"
SPIELWIESE_ADRESSE = "https://kiplatz.at:8445"


def spielwiese_vorbereiten(basis: Path, *, ki_von: Path | None = None) -> Path:
    basis = Path(basis)
    app_core.ensure_plain_directory(basis)
    c = app_core.ensure_plain_directory(basis / community.DIRNAME) / "einstellung.json"
    d = sicher_schreiben.json_laden(c, {})
    if not str(d.get("adresse") or "").startswith("https://"):
        d["adresse"] = SPIELWIESE_ADRESSE
        sicher_schreiben.json_datei(c, d)
    verweis = basis / ki_laufzeit.KI_VERWEIS
    if ki_von is None:
        ki_von = app_core.default_base_dir() / ki_laufzeit.KI_DIRNAME
        if not ki_von.is_dir():
            ki_von = app_core.alter_daten_dir() / ki_laufzeit.KI_DIRNAME
    alt = verweis.read_text(encoding="utf-8").strip() if verweis.is_file() else ""
    if (not alt or not Path(alt).is_dir()) and ki_von.is_dir() and not app_core._is_reparse(ki_von):
        sicher_schreiben.text(verweis, str(ki_von))
    return basis


_TECHNIK_RE = re.compile(r"\s*\((HTTP \d+[^)]*|[A-Za-z]*Error[^)]*|Code -?\d+[^)]*)\)")

_MENSCHLICH = {
    "COMMUNITY_KONTO_NOETIG": "Ohne Konto sind es 5 Fragen am Tag, und die sind für heute aufgebraucht. Mit einem kostenlosen KIplatz-Konto fragst du ohne Grenze und bist Teil der Community: unter „Meine Community“, „Dein KIplatz-Konto“. Morgen geht es auch ohne Konto wieder.",
    "KI_ANTWORT": "Das Modell auf diesem Gerät hat nicht geantwortet. Stell die Frage bitte noch einmal. Klappt es wieder nicht, hilft ein Klick unter Hilfe → „Fehler melden“.",
    "KI_START": "Die KI auf diesem Gerät konnte nicht starten. Das Programm hat den Grund notiert; unter Hilfe → „Fehler melden“ geht er an uns.",
    "KI_FEHLER": "Die KI auf diesem Gerät konnte nicht starten. Das Programm hat den Grund notiert; unter Hilfe → „Fehler melden“ geht er an uns.",
    "UPDATE_SERVER": "Der Community-Server ist gerade nicht erreichbar. Das Programm probiert es später von selbst wieder.",
    "UPDATE_DOWNLOAD": "Das Update ist beim Herunterladen abgebrochen. Das Programm probiert es in einer Stunde wieder.",
    "UPDATE_PRUEFSUMME": "Das Update war nicht unversehrt und wurde verworfen. Das Programm probiert es später wieder.",
    "SERVER": "Der Community-Server antwortet gerade nicht. Deine Frage beantwortet dieses Gerät selbst; alles andere holt das Programm später nach.",
    "GERAET": "Dieses Gerät ist bei der Community nicht angemeldet. Dazukommen geht unter „Meine Community“.",
    "HEIMNETZ_PORT": "Der Anschluss fürs Heimnetz ist gerade belegt, meist noch vom Programm davor. Das Programm versucht es gleich von selbst wieder.",
    "COMMUNITY_NOT_AUS": "Der Admin hat die Community gerade angehalten. Deine Frage beantwortet dieses Gerät selbst.",
}


def menschlich(code: str, detail: str) -> str:
    text = _MENSCHLICH.get(str(code))
    if text:
        return text
    sauber = _TECHNIK_RE.sub("", str(detail)).strip()
    return f"Das hat nicht geklappt: {sauber}" if sauber else "Das hat nicht geklappt."


def nacht_satz(n) -> str:
    if not isinstance(n, dict) or not int(n.get("gesamt", 0) or 0):
        return ""
    try:
        tag = datetime.strptime(str(n.get("tag", "")), "%Y-%m-%d").strftime("%d.%m.")
    except ValueError:
        tag = ""
    s = f"Dein PC hat in der Nacht{' auf den ' + tag if tag else ''} {int(n['richtig'])} von {int(n['gesamt'])} Prüffragen der Community richtig beantwortet."
    if n.get("hinten"):
        s += " Bis eine Nacht wieder besser passt, bekommen andere PCs die Fragen der Mitglieder zuerst."
    return s


_SATZ_AM_TAG = ("Dein Rechner hat am Montag, {0} {1} und {2}.", "Dein Rechner hat am Dienstag, {0} {1} und {2}.",
                "Dein Rechner hat am Mittwoch, {0} {1} und {2}.", "Dein Rechner hat am Donnerstag, {0} {1} und {2}.",
                "Dein Rechner hat am Freitag, {0} {1} und {2}.", "Dein Rechner hat am Samstag, {0} {1} und {2}.",
                "Dein Rechner hat am Sonntag, {0} {1} und {2}.")


def vorher_satz(vorher) -> str:
    if not isinstance(vorher, dict) or not vorher.get("tag"):
        return ""
    try:
        d = datetime.strptime(str(vorher["tag"]), "%Y-%m-%d").date()
    except ValueError:
        return ""
    return tagesbilanz_satz(vorher, d)


def _tagesbilanz_teile(heute: dict) -> list[str]:
    teile = []
    n = heute.get("antworten")
    if n:
        teile.append("1 Frage von Mitgliedern beantwortet" if n == 1 else f"{n} Fragen von Mitgliedern beantwortet")
    n = heute.get("vertieft")
    if n:
        teile.append("1 Abschnitt vertieft" if n == 1 else f"{n} Abschnitte vertieft")
    n = heute.get("vertieft_geprueft")
    if n:
        teile.append("1 Vertiefung anderer geprüft" if n == 1 else f"{n} Vertiefungen anderer geprüft")
    n = heute.get("abschnitte")
    if n:
        teile.append("1 Abschnitt für die Suche aufbereitet" if n == 1 else f"{n} Abschnitte für die Suche aufbereitet")
    return teile


def tagesbericht_zahlen(rang, teams, team_name: str = "", nacht=None) -> dict:
    def zahl(x) -> int:
        try:
            return int(x or 0)
        except (TypeError, ValueError):
            return 0
    out: dict = {"platz": None, "team": None, "nacht": None}
    if isinstance(rang, dict) and zahl(rang.get("dein_platz")):
        out["platz"] = {"platz": zahl(rang["dein_platz"]), "von": zahl(rang.get("anzahl"))}
    if isinstance(teams, dict) and zahl(teams.get("dein_platz")):
        out["team"] = {"name": str(team_name or "")[:60], "platz": zahl(teams["dein_platz"]), "von": zahl(teams.get("anzahl"))}
    if isinstance(nacht, dict) and zahl(nacht.get("gesamt")):
        out["nacht"] = {"richtig": zahl(nacht.get("richtig")), "gesamt": zahl(nacht.get("gesamt")), "tag": str(nacht.get("tag") or "")[:10], "hinten": bool(nacht.get("hinten"))}
    return out


def platz_satz(rang, teams, team_name: str = "") -> str:
    ich = rang.get("dein_platz") if isinstance(rang, dict) else None
    von = rang.get("anzahl", "?") if isinstance(rang, dict) else "?"
    tp = teams.get("dein_platz") if isinstance(teams, dict) else None
    tn = teams.get("anzahl", "?") if isinstance(teams, dict) else "?"
    if ich and tp and team_name:
        return f"Du bist in der Bestenliste auf Platz {ich} von {von}, dein Team „{team_name}“ auf Platz {tp} von {tn} Teams."
    if ich and tp:
        return f"Du bist in der Bestenliste auf Platz {ich} von {von}, dein Team auf Platz {tp} von {tn} Teams."
    if ich:
        return f"Du bist in der Bestenliste auf Platz {ich} von {von}."
    if tp and team_name:
        return f"Dein Team „{team_name}“ auf Platz {tp} von {tn} Teams."
    if tp:
        return f"Dein Team auf Platz {tp} von {tn} Teams."
    return ""


def tagesbilanz_satz(heute: dict, tag=None) -> str:
    teile = _tagesbilanz_teile(heute)
    if not teile:
        return ""
    liste = ", ".join(teile)
    c = heute.get("credits", 0)
    verdient = "1 Credit verdient" if c == 1 else f"{c} Credits verdient"
    if tag is None:
        return f"Dein Rechner hat heute {liste} und {verdient}."
    if (datetime.now().date() - tag).days == 1:
        return f"Dein Rechner hat gestern {liste} und {verdient}."
    return _SATZ_AM_TAG[tag.weekday()].format(tag.strftime("%d.%m."), liste, verdient)


class _Zwischenstand:

    def __init__(self, pfad: Path, art: str):
        self.pfad, self.art = Path(pfad), art

    def laden(self) -> tuple[dict, bool]:
        eintraege: dict = {}
        gemeldet = False
        try:
            zeilen = self.pfad.read_text(encoding="utf-8").splitlines()
            kopf = json.loads(zeilen[0]) if zeilen else {}
        except (OSError, ValueError, UnicodeDecodeError):
            return {}, False
        if kopf.get("art") != self.art:
            return {}, False
        for z in zeilen[1:]:
            try:
                d = json.loads(z)
            except ValueError:
                continue
            if d.get("gemeldet"):
                gemeldet = True
            elif isinstance(d.get("eintrag"), dict) and d.get("kennung"):
                eintraege[str(d["kennung"])] = (str(d.get("frage", "")), d["eintrag"])
        return eintraege, gemeldet

    def beginnen(self) -> None:
        self._schreiben(json.dumps({"art": self.art, "begonnen": time.time()}) + "\n", "w")

    def anhaengen(self, kennung: str, frage: str, eintrag: dict) -> None:
        self._schreiben(json.dumps({"kennung": kennung, "frage": frage, "eintrag": eintrag}, ensure_ascii=False) + "\n", "a")

    def gemeldet(self) -> None:
        self._schreiben(json.dumps({"gemeldet": True}) + "\n", "a")

    def loeschen(self) -> None:
        try:
            self.pfad.unlink()
        except OSError:
            pass

    def _schreiben(self, text: str, modus: str) -> None:
        try:
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
            with open(self.pfad, modus, encoding="utf-8", newline="\n") as f:
                f.write(text)
        except OSError:
            pass


def _log(core: app_core.AppCore, line: str) -> None:
    try:
        core.ensure_directories()
        with open(core.diagnosis_dir / "protokoll.txt", "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + app_core._mask(line) + chr(10))
    except Exception:
        pass


def _write_error_report(core: app_core.AppCore, exc: BaseException):
    try:
        core.ensure_directories()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = core.diagnosis_dir / f"fehler-{stamp}.txt"
        sicher_schreiben.text(path, app_core._mask("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))
        return path
    except Exception:
        return None


def modell_stufe(name: str) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*B\b", name or "", re.I)
    return float(m.group(1).replace(",", ".")) if m else 0.0


def ki_anzeigename(modellname: str) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*B\b", modellname or "", re.I)
    b = float(m.group(1).replace(",", ".")) if m else 0.0
    if not b:
        return "KIplatz"
    return "KIplatz (großes Modell)" if b >= 12 else ("KIplatz (mittleres Modell)" if b >= 6 else "KIplatz (kleines Modell)")

class KiSteuerung:

    def __init__(self, core: app_core.AppCore, *, server: ki_laufzeit.KiServer | None = None, herunterladen=ki_laufzeit.herunterladen,
                 geraete_ermitteln=ki_laufzeit.geraete_ermitteln) -> None:
        self._core = core
        self.ordner = ki_laufzeit.KiOrdner(core.base_dir)
        self.server = server or ki_laufzeit.KiServer(self.ordner)
        self._herunterladen = herunterladen
        self._geraete_ermitteln = geraete_ermitteln
        self.pc_quellen = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._nachlauf = False
        self.phase = "aus"
        self.meldung = ""
        self.fortschritt = {"was": "", "done": 0, "gesamt": 0}
        self.wahl: ki_laufzeit.Wahl | None = None
        self.verbindung = heimnetz.Verbindung(core.base_dir)
        self._einstellung_pfad = core.base_dir / heimnetz.DIRNAME / "einstellung.json"
        self.fern: dict | None = None
        self.danach = None
        self.nur_prozessor = False
        self.bilder_gewuenscht = False
        self.probe: tuple[Path, str] | None = None
        self.probe_geladen = False
        self.fassung = ""
        self.gesperrt = ""


    def einstellung(self) -> dict:
        return sicher_schreiben.json_laden(self._einstellung_pfad, {})

    def einstellung_setzen(self, **werte) -> dict:
        d = self.einstellung()
        d.update(werte)
        app_core.ensure_plain_directory(self._einstellung_pfad.parent)
        sicher_schreiben.json_datei(self._einstellung_pfad, d)
        return d

    def quelle(self) -> str:
        q = self.einstellung().get("quelle")
        return "heimnetz" if (q == "heimnetz" and self.verbindung.daten() is not None) else "lokal"

    def fern_name(self) -> str:
        d = self.verbindung.daten()
        return d.name if d else "anderes Gerät"

    def geraet_de(self) -> str:
        if self.quelle() == "heimnetz":
            return f"{self.fern_name()} im Heimnetz"
        return self.wahl.geraet_name_de() if self.wahl else "?"

    def eingerichtet(self) -> bool:
        if self.quelle() != "lokal" or not self.ordner.server_exe.is_file():
            return False
        if self.wahl is not None:
            return self.ordner.modell_da(self.wahl.modell)
        return any(self.ordner.modell_da(m) for m in ki_laufzeit.MODELLE.values())

    def bereit(self) -> bool:
        if self.quelle() == "heimnetz":
            return self.phase == "bereit"
        return self.phase == "bereit" and self.server.laeuft()

    def frage(self, nachrichten: list[dict], *, on_token=None, zusatz: str = "", max_tokens: int | None = None, kurz: bool = False):
        if self.quelle() == "heimnetz":
            a = self.verbindung.frage(nachrichten, on_token=on_token)
            self.fern = {"name": a.geraet, "ki": a.ki}
            return a
        extra = {"max_tokens": int(max_tokens)} if max_tokens else {}
        return self.server.frage(nachrichten, on_token=on_token, zusatz=zusatz, kurz=kurz, **extra)

    def zustand(self) -> dict:
        quelle = self.quelle()
        laeuft = self.bereit()
        if quelle == "lokal" and self.phase == "bereit" and not laeuft:
            self.phase, self.meldung = "fehler", "der KI-Server hat sich beendet; Details in ki/server.log"
        return {
            "phase": self.phase, "laeuft": laeuft, "meldung": self.meldung, "fortschritt": dict(self.fortschritt),
            "laufzeit_da": self.ordner.laufzeit_da(),
            "quelle": quelle, "fern_name": self.fern_name() if self.verbindung.daten() else None, "gekoppelt": self.verbindung.daten() is not None,
            "modell": self.wahl.modell.name if (quelle == "lokal" and self.wahl) else None,
            "fassung": self.fassung if (quelle == "lokal" and laeuft) else None, "probe": bool(self.probe_geladen),
            "geraet": self.geraet_de() if laeuft else None,
            "modelle": [{"kennung": m.kennung, "name": m.name, "gb": round(m.groesse / 2**30, 2), "da": self.ordner.modell_da(m)} for m in ki_laufzeit.MODELLE.values()],
        }

    def einschalten(self) -> bool:
        with self._lock:
            if self.bereit() or (self._thread and self._thread.is_alive() and not self._nachlauf) or self.gesperrt:
                return False
            self._nachlauf = False
            self.phase, self.meldung = "laden", ""
            ziel = self._fern_ablauf if self.quelle() == "heimnetz" else self._einschalten_ablauf
            self._thread = threading.Thread(target=ziel, name="ki-einschalten", daemon=True)
            self._thread.start()
            return True

    def _fern_ablauf(self) -> None:
        try:
            self._melden(f"{self.fern_name()} wird gefragt, ob KIplatz dort läuft", 0, 0)
            self.fern = self.verbindung.hallo()
            self.phase, self.meldung = "bereit", f"KIplatz antwortet auf {self.fern['name']} im Heimnetz" + (f" ({self.fern['ki']})" if self.fern.get("ki") else "")
            _log(self._core, "OK ki_einschalten heimnetz")
        except app_core.AppError as exc:
            self.phase, self.meldung = "fehler", exc.detail
            _log(self._core, f"ABGELEHNT ki_einschalten heimnetz: {exc.code}: {exc.detail}")
        except Exception as exc:
            path = _write_error_report(self._core, exc)
            self.phase, self.meldung = "fehler", f"Unerwarteter Fehler: {type(exc).__name__}" + (f" (Details in {path.name})" if path else "")
            _log(self._core, f"FEHLER ki_einschalten heimnetz: {type(exc).__name__}: {exc}")

    def _melden(self, was: str, done: int, gesamt: int) -> None:
        self.fortschritt = {"was": was, "done": done, "gesamt": gesamt}

    def _einschalten_ablauf(self) -> None:
        try:
            self.ordner.anlegen()
            if not self.ordner.laufzeit_da():
                if self.ordner.server_exe.is_file() and not getattr(self, "_unterschrift_gemeldet", False):
                    self._unterschrift_gemeldet = True
                    _log(self._core, "ABGELEHNT laufzeit: Unterschrift der Laufzeit nicht gültig, wird aus dem geprüften ZIP neu ausgepackt")
                zip_pfad = self.ordner.downloads_dir / ki_laufzeit.LAUFZEIT.datei
                if not ki_laufzeit.pruefsumme_ok(zip_pfad, ki_laufzeit.LAUFZEIT):
                    self._herunterladen(ki_laufzeit.LAUFZEIT, zip_pfad, fortschritt=lambda d, g: self._melden("KI-Laufzeit wird geholt", d, g),
                                        warten=lambda text: self._melden(text, 0, 0))
                self._melden("KI-Laufzeit wird ausgepackt", 0, 0)
                ki_laufzeit.laufzeit_entpacken(zip_pfad, self.ordner.laufzeit_dir, schon_da=self.ordner.laufzeit_da)
            self._melden("Grafikkarte wird gewählt", 0, 0)
            first = self._core.load_first_start()
            geraete = self._geraete_ermitteln(self.ordner.server_exe)
            if self.nur_prozessor:
                wahl = ki_laufzeit.waehlen((), first.memory_gib if first else 0.0)
                wahl = ki_laufzeit.Wahl(None, wahl.modell, "die Grafikkarte hat bei der letzten Antwort versagt, deshalb der Prozessor",
                                        ki_laufzeit.PROZESSOR_KARTE_VERSAGT)
            else:
                wahl = ki_laufzeit.waehlen(geraete, first.memory_gib if first else 0.0)
            self.wahl = wahl
            plan: list[tuple[str, object, Path]] = []
            if not self.ordner.modell_da(wahl.modell):
                plan.append((ki_anzeigename(wahl.modell.name), wahl.modell, self.ordner.modell_pfad(wahl.modell)))
            if wahl.modell.bilder and wahl.geraet is not None and wahl.geraet.eigenstaendig and not self.ordner.bilder_da(wahl.modell):
                plan.append(("Bild-Zusatz", wahl.modell.bilder, self.ordner.bilder_pfad(wahl.modell)))
            gesamt = sum(int(getattr(p, "groesse", 0) or 0) for _, p, _ in plan)
            vor = 0
            for nr, (name, paket, ziel) in enumerate(plan, 1):
                was = f"{name} wird geholt" + (f" ({nr} von {len(plan)})" if len(plan) > 1 else "")
                try:
                    self._herunterladen(paket, ziel, fortschritt=lambda d, g, vor=vor, was=was: self._melden(was, vor + d, gesamt or g),
                                        warten=lambda text: self._melden(text, 0, 0), **({"pc_quellen": self.pc_quellen} if self.pc_quellen else {}))
                except (ki_laufzeit.KiError, app_core.AppError) as exc:
                    if name != "Bild-Zusatz":
                        raise
                    _log(self._core, f"ABGELEHNT bild-zusatz: {getattr(exc, 'code', '')}: {getattr(exc, 'detail', exc)}")
                vor += int(getattr(paket, "groesse", 0) or 0)
            self.phase = "starten"
            self._melden(f"{ki_anzeigename(wahl.modell.name)} wird auf {wahl.geraet_name_de()} gestartet", 0, 0)
            threads = None
            if wahl.geraet is None and first is not None and first.cpu_cores:
                kerne = int(first.cpu_cores)
                if first.role is app_core.Role.CLIENT_ONLY:
                    threads = max(1, kerne - 1)
                else:
                    threads = max(1, kerne * int(self._core.load_freigabe().cpu_prozent) // 100)
            probe = self.probe if self.probe is not None and self.probe[1] == wahl.modell.kennung else None
            self.server.start(wahl, threads=threads, bilder=self.bilder_gewuenscht, **({"modell_pfad": probe[0]} if probe else {}))
            self.probe_geladen = probe is not None
            self.fassung = modell_katalog.fassung(probe[0].name if probe else wahl.modell.datei)
            self._nachlauf = True
            self.phase, self.meldung = "bereit",f"{ki_anzeigename(wahl.modell.name)} läuft auf {wahl.geraet_name_de()} ({wahl.grund})"
            _log(self._core, f"OK ki_einschalten {wahl.modell.kennung} {wahl.geraet.kennung if wahl.geraet else 'cpu'}"
                             + (f" Probemodell {probe[0].name}" if probe else ""))
            if self.danach is not None:
                self.danach()
        except app_core.AppError as exc:
            if threading.current_thread() is self._thread:
                self.phase, self.meldung = "fehler", exc.detail
                self._melden("", 0, 0)
            _log(self._core, f"ABGELEHNT ki_einschalten: {exc.code}: {exc.detail}")
        except Exception as exc:
            path = _write_error_report(self._core, exc)
            if threading.current_thread() is self._thread:
                self.phase, self.meldung = "fehler", f"Unerwarteter Fehler: {type(exc).__name__}" + (f" (Details in {path.name})" if path else "")
            _log(self._core, f"FEHLER ki_einschalten: {type(exc).__name__}: {exc}")

    def ausschalten(self) -> None:
        self.server.stop()
        self.phase, self.meldung = "aus", ""
        self.fortschritt = {"was": "", "done": 0, "gesamt": 0}

    def auf_prozessor_wechseln(self) -> bool:
        if self.quelle() != "lokal" or self.wahl is None or self.wahl.geraet is None or self.nur_prozessor:
            return False
        self.nur_prozessor = True
        self.ausschalten()
        self.einschalten()
        return True

    def mit_bildern_einschalten(self) -> bool:
        if self.quelle() != "lokal" or self.wahl is None or self.wahl.geraet is None or not self.wahl.geraet.eigenstaendig or self.nur_prozessor:
            return False
        if getattr(self.server, "bilder", False) or not self.ordner.bilder_da(self.wahl.modell):
            return False
        self.bilder_gewuenscht = True
        self.ausschalten()
        self.einschalten()
        return True

    def ki_beschreibung(self) -> str:
        return f"KIplatz auf {self.wahl.geraet_name_de()}" if (self.wahl and self.server.laeuft()) else "KIplatz ist dort gerade aus"


def anmelde_sicherung(base_dir: Path) -> Path | None:
    if sys.platform != "win32":
        import plattform
        try:
            helfer = Path(base_dir).resolve() == plattform.daten_ordner().resolve()
        except OSError:
            helfer = False
        return plattform.sicherungs_ordner() if helfer and not os.environ.get("PYTEST_CURRENT_TEST") else None
    lokal = os.environ.get("LOCALAPPDATA")
    try:
        normal = Path(base_dir).resolve() in {app_core.default_base_dir().resolve(), app_core.alter_daten_dir().resolve()}
    except OSError:
        normal = False
    if not lokal or not normal or os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    return app_core.kiplatz_dir() / "sicherung"


def speicher_pfad(ort: str) -> Path | None:
    if not ort:
        return None
    return Path(ort) / app_core.SPEICHER_ORDNER / scheiben_halter.DIRNAME


def osm_pfad(ort: str, base_dir: Path) -> Path:
    return (Path(ort) / app_core.SPEICHER_ORDNER / osm_orte.DIRNAME) if ort else (Path(base_dir) / osm_orte.DIRNAME)


def wiki_pfad(ort: str, base_dir: Path) -> Path:
    return (Path(ort) / app_core.SPEICHER_ORDNER / wikipedia.DIRNAME) if ort else (Path(base_dir) / wikipedia.DIRNAME)


class Api:

    def __init__(self, core: app_core.AppCore, *, registry: app_install.RegistryOps | None = None, ki: KiSteuerung | None = None,
                 window=None, geraet_name: str = "dieses Gerät", install_dir: Path | None = None, rechen: "rechenarbeit.Rechenarbeit | None" = None,
                 bedeutung_: "bedeutung.Bedeutung | None" = None, nachschauer: "nachschauen.Nachschauer | None" = None,
                 bewertung_: "bewertung.Bewertung | None" = None) -> None:
        self._install_dir = install_dir
        self._core = core
        self._registry = registry if registry is not None else (app_install.WinRegistryRunKey() if (app_install.running_exe() or app_install.portable_root()) else app_install.MemoryRegistry())
        self._ki = ki or KiSteuerung(core)
        self._window = window
        self._geraet_name = geraet_name
        self._kontobuch = credits.Kontobuch(core.base_dir)
        self._kiste = skills.Skillkiste(core.base_dir)
        import platzl_programm
        self._platzl_mod = platzl_programm
        self._ablage = gespraeche.Gespraechsablage(core.base_dir)
        self._wissen = wissen.Wissensspeicher(core.base_dir)
        self._community = community.Community(core.base_dir, sicherung=anmelde_sicherung(core.base_dir))
        self._platzl = self._platzl_mod.Platzl(core.base_dir, self._community)
        self._zuhause = zuhause.Haushalt(core.base_dir)
        self._fenster = fragfenster.Fragfenster(core.base_dir, self._wissen)
        self._dateiliste = dateisuche.Dateiliste()
        try:
            if self._zuhause.an() and self._zuhause.liste():
                self._dateiliste.vorbereiten()
        except Exception:
            pass
        self._abgleich = abgleich_geraet.AbgleichGeraet(core.base_dir, self._community, self._ablage)
        try:
            self._community.sicherung_pruefen()
            if self._community.geraet() is not None and self._community.wiederhergestellt:
                _log(core, "OK anmeldung aus der Sicherung wiederhergestellt (neuer Programmordner)")
        except Exception as exc:
            _log(core, f"FEHLER anmeldung sicherung: {type(exc).__name__}")
        self._community_stand: tuple[float, community.Stand] | None = None
        self._staerkste: tuple[float, float] | None = None
        self._ki_von_hand_aus = False
        self._nochmal_vorige: dict[str, str] = {}
        self._beitritt: dict | None = None
        self._konto_anmeldung: konto_basis.Anmeldung | None = None
        self._konto_qr = ""
        self._letzter_stand: dict | None = None
        self._dienst = heimnetz.Dienst(core.base_dir, frage_fn=self._dienst_frage, name=geraet_name if geraet_name != "dieses Gerät" else None,
                                       kontobuch=self._kontobuch, ki_beschreibung=self._ki.ki_beschreibung, wissen_fn=self._wissen_auftrag)
        self._dienst.protokoll = lambda line: _log(core, line)
        self._bedeutung = bedeutung_ or bedeutung.Bedeutung(core, protokoll=lambda line: _log(core, line))
        self._bewertung = bewertung_ or bewertung.Bewertung(core, protokoll=lambda line: _log(core, line))
        self._wiki = wikipedia.WikiKopie(lambda: wiki_pfad(self._core.load_freigabe().speicher_ort, self._core.base_dir),
                                         freigabe_mb=lambda: self._core.load_freigabe().speicher_mb, darf=self._wiki_darf, karte_frei=self._wiki_karte_frei,
                                         vektoren=lambda texte: self._bedeutung.server.vektoren(texte, timeout_s=300),
                                         vektoren_bereit=lambda: self._bedeutung.bereit(), log=lambda line: _log(core, line),
                                         gemeinschaft=lambda: self._community if self._community.geraet() is not None else None,
                                         modell=lambda: ki_laufzeit.EMBEDDING.sha256[:16], ablage=lambda: self._halter.dir)
        self._osm = osm_orte.OrteKopie(lambda: osm_pfad(self._core.load_freigabe().speicher_ort, self._core.base_dir),
                                       freigabe_mb=lambda: self._core.load_freigabe().speicher_mb, darf=self._wiki_darf,
                                       vorgesehen=lambda: self._community.ist_admin(), log=lambda line: _log(core, line))
        self._halter = scheiben_halter.Halter(core.base_dir, lambda: self._community, limit_mb=lambda: max(0, self._core.load_freigabe().speicher_mb - self._wiki.belegt_mb() - self._osm.belegt_mb()), log=lambda line: _log(core, line),
                                              ordner=lambda: speicher_pfad(self._core.load_freigabe().speicher_ort))
        self._spiegel = gemeinschaft.Spiegel(core.base_dir, lambda: self._community, protokoll=lambda line: _log(core, line)) if wortindex.moeglich() else None
        self._themen = themen.Themen(lambda: self._ki.einstellung(), lambda: self._community, self._wissen, log=lambda line: _log(core, line))
        self._rechen = rechen or rechenarbeit.Rechenarbeit(core, lambda: self._community, self._kontobuch, geraet_name=geraet_name, protokoll=lambda line: _log(core, line), halter=self._halter, themen=self._themen, stand=lambda: " ".join(x for x in (self._wiki.text_de(), self._osm.text_de()) if x),
                                                            server=getattr(self._bedeutung, "server", None), server_geteilt=lambda: getattr(self._bedeutung, "phase", "") == "bereit",
                                                            urteil=self._urteil, urteil_bereit=lambda: self._ki.quelle() == "lokal" and self._ki.bereit(),
                                                            antworten=self._antwort_fuer_mitglied, ki_starten=self._ki_starten_blockierend, ki_stoppen=self._ki_entladen,
                                                            antworten_moeglich=self._kann_fuer_andere_antworten, fragen_immer=self.fragen_immer,
                                                            vertiefen=self._vertiefen, vertiefen_pruefen=self._vertiefen_pruefen,
                                                            vorwaermen=self._vorwaermen_lauf,
                                                            pruefstand=self._pruefstand_lauf,
                                                            karte_vergeben=lambda: self._ki.gesperrt if self._kurztest_laeuft() else "",
                                                            modell_name=lambda: self._ki.wahl.modell.name if (self._ki.wahl and self._ki.quelle() == "lokal"
                                                                                                              and self._ki.ordner.modell_da(self._ki.wahl.modell)) else "",
                                                            kopie=lambda: bool(self._spiegel is not None and self._spiegel.bereit()),
                                                            speicher_freigeben=lambda: getattr(self._bedeutung, "schlank_machen", lambda: False)())
        self._pruefstand_thread: threading.Thread | None = None
        self._kurztest_thread: threading.Thread | None = None
        self._karte_lock = threading.Lock()
        self._warmhalter = warmhalten.Warmhalter(
            [("antwort", lambda: self._ki.server if self._ki.bereit() else None, lambda s: warmhalten.antwort_anstossen(s, getattr(self._rechen, "vorrang", None))),
             ("bewertung", lambda: self._bewertung.server if getattr(self._bewertung, "phase", "") == "bereit" else None, warmhalten.bewertung_anstossen),
             ("bedeutung", lambda: self._bedeutung.server if getattr(self._bedeutung, "phase", "") == "bereit" else None, warmhalten.bedeutung_anstossen)],
            darf=self._warm_darf, log=lambda line: _log(core, line))
        self._ki.danach = self._modelle_danach
        self._weitergeber = weitergeben.Weitergeber(core, self._community, self._ki.ordner.modelle_dir, log=lambda z: _log(core, z),
                                                    rechenkraft_laeuft=lambda: self._core.run_state() is node_local_state.RunState.ACTIVE,
                                                    frage_laeuft=lambda: getattr(self._rechen, "phase", "") == "antwortet")
        self._ki.pc_quellen = self._weitergeber.quellen
        self._community.bei_weitergeben = self._weitergeber.halter_auftrag
        self._mess_suche_zuletzt, self._mess_suchen, self._mess_suche_gemeldet = 0.0, 0, False
        self._mess_bremse = False
        self._pruefrunde: dict | None = None
        self._ruht_gemeldet = ""
        self._pruefrunde_pause_bis = 0.0
        self._update_steht_an = ""
        self._runde_ruht_grund = ""
        self._knopf_wartet = False
        self._knopf_meldung = ""
        self._mess_uhr, self._mess_schlafen = time.monotonic, time.sleep
        self._nachschauer = nachschauer or nachschauen.Nachschauer(suche_fn=lambda frage, **kw: self._websuche(frage, **kw))
        self._schnittstelle = schnittstelle.Schnittstelle(self._schnittstelle_antwort, self._schnittstelle_schluessel, log=lambda line: _log(core, line),
                                                          docker=lambda: bool(self._ki.einstellung().get("schnittstelle_docker")))
        self._zwischenablage = auswahl.in_zwischenablage
        self._strg_v = auswahl._strg_v
        if geraet_name != "dieses Gerät":
            self._ki.verbindung.eigen = geraet_name
        self._sprechen = sprechen.Steuerung(sprechen.SprachOrdner(self._ki.ordner), threads=sprechen.threads_wahl(self._kerne()), log=lambda line: _log(core, line))
        self._gedaechtnis = gedaechtnis.Gedaechtnis(core.base_dir)
        self.prep_error: str | None = None
        self.start_meldung = ""
        self._stopp = threading.Event()
        self.schliessen_angefordert = False
        self.versteckt = False
        self.abbruch_gewuenscht = False
        self._community_frage: str | None = None
        self.spielwiese =self._community.adresse.rstrip("/") == SPIELWIESE_ADRESSE

    @property
    def schliessen_angefordert(self) -> bool:
        return self._stopp.is_set()

    @schliessen_angefordert.setter
    def schliessen_angefordert(self, an: bool) -> None:
        if an:
            self._stopp.set()
        else:
            self._stopp.clear()

    def herunterfahren(self) -> None:
        self.schliessen_angefordert = True
        for teil, name in (("_sprechen", "beenden"),
                           ("_schnittstelle", "stop"), ("_dienst", "stop"),
                           ("_warmhalter", "stop"),
                           ("_rechen", "stop"),
                           ("_bedeutung", "ausschalten"), ("_bewertung", "ausschalten"),
                           ("_ki", "ausschalten")):
            schritt = getattr(getattr(self, teil, None), name, None)
            if schritt is None:
                continue
            try:
                schritt()
            except Exception as exc:
                _log(self._core, f"FEHLER herunterfahren {teil}.{name}: {type(exc).__name__}")


    def _guarded(self, name: str, action, ok_text: str = "") -> dict:
        try:
            daten = action()
            _log(self._core, f"OK {name}")
            return {"ok": True, "text": ok_text, "daten": daten}
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT {name}: {exc.code}: {exc.detail}")
            return {"ok": False, "text": menschlich(exc.code, exc.detail), "code": exc.code, "daten": None}
        except Exception as exc:
            _write_error_report(self._core, exc)
            _log(self._core, f"FEHLER {name}: {type(exc).__name__}: {exc}")
            return {"ok": False, "text": "Da ist etwas schiefgegangen. Das Programm hat es notiert; unter Hilfe → „Fehler melden“ geht es mit einem Klick an uns.", "code": "UNERWARTET", "daten": None}

    def _community_status(self) -> community.Stand:
        if self._community_stand and time.time() - self._community_stand[0] < 60:
            return self._community_stand[1]
        st = self._community.stand()
        self._community_stand = (time.time(), st)
        return st

    def _modelle_danach(self) -> None:
        if getattr(self._ki, "gesperrt", ""):
            return
        self._bedeutung.einschalten()

        def dann():
            t = getattr(self._bedeutung, "_thread", None)
            if t is not None:
                t.join(timeout=600)
            if not getattr(self._ki, "gesperrt", ""):
                self._bewertung.einschalten()
        threading.Thread(target=dann, name="bewertung-danach", daemon=True).start()

    def _mit_wissen(self, nachrichten: list[dict], *, privat_erlaubt: bool | str = True, frisch: bool = False, knapp: bool = False) -> tuple[str, list[dict], int, str]:
        zusatz, quellen, n, hinweis = self._mit_wissen_ohne_zeit(nachrichten, privat_erlaubt=privat_erlaubt, frisch=frisch, knapp=knapp)
        sf = suchfrage(nachrichten)
        leit = "\n".join(z for z in (frage_leitzeilen(sf) if zusatz else "", namen_leitzeilen(self._unbekannte_namen(sf))) if z)
        return (wissen.datum_zeile() + ("\n" + leit if leit else "") + ("\n\n" + zusatz if zusatz else "") + "\n\n" + wissen.uhrzeit_zeile(),
                quellen, n, hinweis)

    def _mit_wissen_ohne_zeit(self, nachrichten: list[dict], *, privat_erlaubt: bool | str, frisch: bool, knapp: bool = False) -> tuple[str, list[dict], int, str]:
        self._letzter_stand = None
        _EIGEN.an = bool(privat_erlaubt) and privat_erlaubt != wissen.FENSTER
        frage = suchfrage(nachrichten)
        if privat_erlaubt == wissen.FENSTER:
            self._schritt("sucht in den Unterlagen …")
            try:
                lokal = self._wissen.suchen(frage, privat_erlaubt=wissen.FENSTER)
            except app_core.AppError:
                lokal = []
            zusatz, quellen = wissen.kontext_bauen(lokal)
            return zusatz, quellen, len(lokal), "Frag-Fenster: nur in den Unterlagen des Betriebs gesucht, nicht im Internet und nicht in der Community."
        self._schritt("sucht im Wissen der Community …")
        if _dateifrage(frage):
            try:
                lokal = self._wissen.suchen(frage, privat_erlaubt=privat_erlaubt) if privat_erlaubt else []
            except app_core.AppError:
                lokal = []
            zusatz, quellen = wissen.kontext_bauen(lokal)
            if privat_erlaubt is True:
                hinweis = "Frage nach einer eigenen Datei: nur auf diesem Gerät gesucht, nicht im Internet und nicht in der Community."
            elif privat_erlaubt:
                hinweis = "Frage nach einer eigenen Datei: nur auf deinem PC daheim gesucht, nicht im Internet und nicht in der Community."
            else:
                hinweis = "Frage nach einer eigenen Datei: der PC, der geantwortet hat, sieht deine Dateien nicht; gesucht wurde nichts."
            return zusatz, quellen, len(lokal), hinweis
        server: list[wissen.Treffer] = []
        server_n, hinweis = 0, ""
        vektor = self._bedeutung.frage_vektor(frage)
        fachgebiete = wissen.fachgebiete_pruefen(getattr(_FACH, "wert", None))
        if self._spiegel is not None:
            try:
                if self._spiegel.bereit():
                    server, server_n = self._spiegel.suchen(frage, vektor=vektor, fachgebiete=fachgebiete)
                    bedeutung_wort = self._spiegel.letzte_suche.startswith("bedeutung+wort")
                    if privat_erlaubt is True:
                        hinweis = ("Im Gemeinschaftswissen auf diesem Gerät nach Bedeutung und Wörtern gesucht." if bedeutung_wort
                                   else "Im Gemeinschaftswissen auf diesem Gerät nach Wörtern gesucht.")
                    else:
                        hinweis = ("Im Gemeinschaftswissen auf dem PC, der geantwortet hat, nach Bedeutung und Wörtern gesucht." if bedeutung_wort
                                   else "Im Gemeinschaftswissen auf dem PC, der geantwortet hat, nach Wörtern gesucht.")
            except Exception as exc_spiegel:
                _log(self._core, f"FEHLER gemeinschaftswissen suchen: {type(exc_spiegel).__name__}")
                server, server_n, hinweis = [], 0, ""
        try:
            if not hinweis:
                server, server_n = self._community.suchen(frage, vektor=vektor, fachgebiete=fachgebiete)
                self._community_stand = (time.time(), community.Stand(True, server_n, "Community", f"{server_n} Quellen am Community-Server"))
                hinweis = ("Am Server nach Bedeutung und Wörtern gesucht." if self._community.letzte_suche == "bedeutung+wort"
                           else ("Am Server nur nach Wörtern gesucht (noch keine Vektoren im Index)." if vektor else "Am Server nur nach Wörtern gesucht (Bedeutungs-Modell nicht bereit)."))
        except app_core.AppError as exc:
            hinweis = (f"Community-Server nicht erreichbar ({exc.detail}); nur dieses Gerät durchsucht." if privat_erlaubt is True
                       else f"Community-Server nicht erreichbar ({exc.detail}); nur der PC, der geantwortet hat, wurde durchsucht.")
            self._community_stand = (time.time(), community.Stand(False, 0, "Community", exc.detail))
        try:
            lokal = self._wissen.suchen(frage, privat_erlaubt=privat_erlaubt)
            lokal_n = len(self._wissen.liste(privat=None if privat_erlaubt else False))
        except app_core.AppError:
            lokal, lokal_n = [], 0
        live: list[wissen.Treffer] = []
        ergaenzend: list[wissen.Treffer] = []
        for adresse in wissen.adressen_in_text(frage):
            try:
                q, text, tr = wissen.live_lesen(adresse, frage)
                live += tr
                hinweis = f"{q.adresse} jetzt live gelesen. " + hinweis
                self._live_merken(q, text)
            except app_core.AppError as exc:
                hinweis = f"{adresse} ließ sich nicht lesen ({exc.detail}). " + hinweis
        selbst = selbstauskunft.betrifft(frage)
        if selbst:
            live = selbstauskunft.treffer() + live
            hinweis = "Selbstauskunft von KIplatz als erste Quelle. " + hinweis
        at_woerter = [] if selbst else woerterbuch_at.treffer(frage)
        if at_woerter:
            live = at_woerter + live
            hinweis = "Österreichisches Wörterbuch von KIplatz als erste Quelle. " + hinweis
        anbieter = not selbst and selbstauskunft.anbieter(frage)
        if anbieter:
            ergaenzend = selbstauskunft.steckbrief_treffer() + ergaenzend
            hinweis = "Steckbrief von KIplatz als Quelle (Frage nach KI-Anbietern). " + hinweis
        ziel = zeitziel(frage)
        if ziel != (None, None):
            vorher_n = len(server) + len(lokal)
            def alt(t: wissen.Treffer) -> bool:
                if ziel[0] is None and t.quelle.art != "nachgeschaut":
                    return False
                return nachschauen.veraltet_text(t.quelle.titel + " " + t.quelle.adresse + " " + t.text, *ziel)
            server = [t for t in server if not alt(t)]
            lokal = [t for t in lokal if not alt(t)]
            if len(server) + len(lokal) < vorher_n:
                hinweis = f"{vorher_n - len(server) - len(lokal)} gemerkte Stellen mit einem älteren Stand übergangen. " + hinweis
        richtung = nachschauen.richtung(frage)
        erkannt = nachschauen.erkennen(frage)
        if richtung and not (erkannt is not None and erkannt.art in ("wetter", "schlagzeilen")):
            grenze = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
            heute_ = ki_laufzeit.heute()
            fenster_ = nachschauen.letzt_fenster(frage)

            def vorbei(t: wissen.Treffer) -> bool:
                if t.quelle.art == "nachgeschaut" and t.quelle.datum < grenze:
                    return True
                return nachschauen.zeitlich_vorbei(t.text, heute_, richtung, fenster_)
            vorher_n = len(server) + len(lokal)
            server = [t for t in server if not vorbei(t)]
            lokal = [t for t in lokal if not vorbei(t)]
            if len(server) + len(lokal) < vorher_n:
                hinweis = f"{vorher_n - len(server) - len(lokal)} gemerkte Stellen übergangen, die nicht zu heute passen. " + hinweis
        kalender_teil: list[wissen.Treffer] = []
        kal = kalender_dach.quelle(frage)
        if kal is not None:
            kq = wissen.Quelle("kalender-" + (region.erkennen(frage) or region.Region("at")).land, "berechnet", kal[0], "", wissen._jetzt(), 0)
            if kal[2]:
                live = [wissen.Treffer(kq, kal[1], 9.5)] + live
            else:
                kalender_teil = [wissen.Treffer(kq, kal[1], 9.5)]
            hinweis = "Feiertage vom Programm aus dem Kalender berechnet. " + hinweis
        elif kalender_welt.betrifft(frage):
            abgefragt = []
            for land in kalender_welt.laender_fuer(frage):
                je_jahr: dict[int, list[dict]] = {}
                for j in kalender_welt.jahre(frage)[:3]:
                    try:
                        tage = self._community.feiertage(land, j)
                    except (app_core.AppError, OSError, ValueError):
                        tage = None
                    if tage:
                        je_jahr[j] = tage
                if je_jahr:
                    kq = wissen.Quelle("kalender-" + land.lower(), "abgefragt", f"Feiertage {land} (Nager.Date, vom Server abgefragt)", "", wissen._jetzt(), 0)
                    abgefragt.append(wissen.Treffer(kq, kalender_welt.text(land, je_jahr, frage), 9.5))
            if abgefragt:
                live = abgefragt + live
                hinweis = "Feiertage vom Server bei Nager.Date abgefragt (nur Land und Jahr, ohne Gerät und Person). " + hinweis
        if self.nachschauen_an() and not selbst:
            vorher = next((str(n.get("content", "")) for n in reversed([n for n in (nachrichten or []) if n.get("role") == "user"][:-1])), "")
            if stellen.passend(frage, vorher):
                self._schritt("liest bei der zuständigen Stelle nach …")
                funde, fehler = stellen.lesen_fuer(frage, vorher=vorher)
                jetzt = wissen._jetzt()
                bis = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                lauf_s = getattr(_SUCHLAUF, "stand", None)
                for f in reversed(funde):
                    sq = wissen.Quelle(wissen.kennung_fuer("stelle", f.adresse + "|" + f.stelle), "nachgeschaut", f.titel, f.adresse, jetzt, len(f.text), bis)
                    ergaenzend = [wissen.Treffer(sq, f.text, 9.0)] + ergaenzend
                    if isinstance(lauf_s, dict):
                        lauf_s.setdefault("stellen", set()).add(sq.kennung)
                if funde:
                    namen = ", ".join(sorted({stellen.NAMEN.get(f.stelle, f.stelle) for f in funde}))
                    hinweis = f"Bei der zuständigen Stelle nachgeschaut ({namen}). " + hinweis
                    self._letzter_stand = {"art": "stelle", "titel": funde[0].titel, "nachgeschaut": jetzt, "gilt_bis": "", "aus_gedaechtnis": False}
                for satz in fehler:
                    _log(self._core, f"ABGELEHNT stelle: {satz}")
                    hinweis = f"Zuständige Stelle nicht lesbar ({satz}). " + hinweis
        orte: list[wissen.Treffer] = []
        if not selbst and self._osm.bereit():
            try:
                orte = self._osm.suchen(frage) if not privat_erlaubt else self._osm.suchen(frage, ort_hinweis=morgenbericht.einstellung_lesen(self._ki.einstellung())["ort"])
            except Exception as exc:
                _log(self._core, f"FEHLER openstreetmap suchen: {type(exc).__name__}")
            if orte:
                hinweis = ("In den Orten aus OpenStreetMap auf diesem Gerät nachgeschlagen. " if privat_erlaubt is True
                           else "In den Orten aus OpenStreetMap auf dem PC, der geantwortet hat, nachgeschlagen. ") + hinweis
        vorab = None
        ohne_wiki = not selbst and not frisch and nachschauen.nicht_im_lexikon(frage)
        rechen = not selbst and not frisch and belege.rechenaufgabe(frage)
        listen = (not selbst and not frisch and not ohne_wiki and not rechen and nachschauen.listenfrage(frage) and suche_denkbar(frage)
                  and not _frueher_gefragt(nachrichten))
        namen = [] if (selbst or live or ergaenzend or orte or frisch or ohne_wiki or rechen) else self._unbekannte_namen(frage)
        if (frisch or ohne_wiki or namen or listen) and not live and not selbst and self.nachschauen_an() and frage.strip():
            if namen:
                _log(self._core, f"OK unbekannter name: {len(namen)} Name(n) stehen in keinem Wikipedia-Abschnitt, die Suche läuft gleich mit")
            elif listen:
                _log(self._core, "OK listenfrage: eine Frage nach mehreren Dingen mit Zahlen, die Suche läuft gleich mit")
            vorab = self._nachschauen_vorab(frage, server + lokal, nachrichten, frisch=frisch, modell=bool(listen))
        if (vorab is None and not frisch and not live and not ergaenzend and not orte and not selbst and self.nachschauen_an() and frage.strip()
                and massfrage(frage) and nachschauen.erkennen(frage) is None and not _frueher_gefragt(nachrichten)
                and not nachschauen.richtung(frage)):
            self._suche_nebenher(frage, nachrichten)
        wiki: list[wissen.Treffer] = []
        wiki_titel: list[wissen.Treffer] = []
        zeitgebunden = ziel != (None, None)
        art = nachschauen.erkennen(frage)
        bewerten = self._bewertung.bereit()
        if ohne_wiki and vorab is not None:
            hinweis = "Die Wikipedia wurde übersprungen: so etwas steht in keinem Lexikon, darum gleich im Internet gesucht. " + hinweis
        elif rechen:
            hinweis = "Eine Rechenaufgabe mit den Zahlen der Frage: nicht in der Wikipedia nachgeschlagen und nicht im Internet gesucht. " + hinweis
        elif listen and vorab is not None:
            hinweis = "Eine Frage nach mehreren Dingen mit Zahlen: die Suche im Internet lief gleich mit. " + hinweis
        if (not live and not selbst and not rechen and not (ohne_wiki and vorab is not None) and self._wiki.bereit()
                and not (art is not None and art.art in ("wetter", "schlagzeilen"))):
            self._schritt("schlägt in der Wikipedia nach …")
            t_wiki = time.time()
            try:
                teile = nachschauen.teilfragen(frage)
                if teile:
                    je = max(2, (WIKI_KANDIDATEN if bewerten else 3) // len(teile) + 1)
                    wiki_listen = [self._wiki.suchen(tf, vektor=self._bedeutung.frage_vektor(tf), n=je, abbrechen=lambda: self.abbruch_gewuenscht) for _d, tf in teile]
                    gesehen_w: set[tuple[str, str]] = set()
                    for i in range(max((len(x) for x in wiki_listen), default=0)):
                        for liste in wiki_listen:
                            if i < len(liste) and (liste[i].quelle.kennung, liste[i].text[:80]) not in gesehen_w:
                                gesehen_w.add((liste[i].quelle.kennung, liste[i].text[:80]))
                                wiki.append(liste[i])
                else:
                    wiki = self._wiki.suchen(frage, vektor=vektor, n=WIKI_KANDIDATEN if bewerten else 3, abbrechen=lambda: self.abbruch_gewuenscht)
            except Exception as exc:
                _log(self._core, f"FEHLER wikipedia suchen: {type(exc).__name__}")
            wiki_messen(self._wiki, time.time() - t_wiki)
            if self.abbruch_gewuenscht:
                raise app_core.AppError("ABGEBROCHEN", "auf deinen Wunsch abgebrochen")
            if not zeitgebunden:
                try:
                    wiki_titel = self._wiki.einleitung(frage)
                except Exception as exc:
                    _log(self._core, f"FEHLER wikipedia einleitung: {type(exc).__name__}")
            if wiki_titel and wiki and belege.zahlenfrage(frage):
                namen = [_titel_name(t) for t in wiki_titel]
                vorher_w = len(wiki)
                wiki = [t for t in wiki if not _ortsteil_stelle(t, namen)]
                if len(wiki) < vorher_w:
                    hinweis = f"{vorher_w - len(wiki)} Stellen aus Ortsteil-Artikeln weggelassen. " + hinweis
            if wiki:
                a_ = self._wiki.ausgabe()
                hinweis = (f"In der Wikipedia-Kopie auf diesem Gerät nachgeschlagen (Stand {a_[6:8]}.{a_[4:6]}.{a_[:4]}). " if privat_erlaubt is True
                           else f"In der Wikipedia-Kopie auf dem PC, der geantwortet hat, nachgeschlagen (Stand {a_[6:8]}.{a_[4:6]}.{a_[:4]}). ") + hinweis
        sortiert: bewertung.Sortierung | None = None
        live_sortiert = False
        if bewerten and not selbst:
            kandidaten = ergaenzend + orte + server + lokal + ([] if zeitgebunden else wiki + wiki_titel)
            if kandidaten:
                self._schritt("prüft, welche Fundstellen wirklich passen …")
                sortiert = self._bewertung.sortieren(frage, kandidaten)
        if not live and self.nachschauen_an():
            nach, satz = vorab() if vorab is not None else self._nachschauen(frage, ergaenzend + orte + server + lokal + ([] if zeitgebunden else wiki + wiki_titel), frisch=frisch,
                                                                             nachrichten=nachrichten, abgedeckt=sortiert.deckt_ab if sortiert is not None else None)
            if nach and sortiert is not None and (art is None or art.art == "suche"):
                s2 = self._bewertung.sortieren(frage, nach)
                if s2 is not None:
                    raus = len(nach) - len(s2.treffer)
                    nach = s2.treffer
                    if raus:
                        hinweis = f"{raus} gelesene Stellen passten nicht zur Frage und wurden weggelassen. " + hinweis
                    live_sortiert = True
            live += nach
            if satz:
                hinweis = satz + " " + hinweis
        live = kalender_teil + ergaenzend + live
        schon_live = {t.quelle.kennung for t in live if t.quelle.art != "nachgeschaut"}
        live = orte + live
        n_treffer = KNAPP_TREFFER if knapp else wissen.TREFFER
        n_rest = max(1, n_treffer + 2 - len(live)) if live else n_treffer
        if fachgebiete and sortiert is not None:
            sortiert = _fach_vorziehen(sortiert, fachgebiete)
        if sortiert is not None:
            rest = sortiert.treffer[:n_rest]
            if zeitgebunden and wiki:
                rest = rest + wiki[:1]
            hinweis = ("Die gespeicherten Fundstellen wurden gelesen und nach Passung sortiert. " if sortiert.treffer
                       else "Keine gespeicherte Fundstelle passte wirklich zur Frage. ") + hinweis
        else:
            rest = wissen.treffer_mischen(wissen.fachgebiet_gewichten(server, fachgebiete), wissen.fachgebiet_gewichten(lokal, fachgebiete), n=n_rest)
            if wiki:
                rest = (wiki[:2] + rest[: max(1, n_treffer - 2)]) if not (zeitgebunden or live) else (rest + wiki[:1])
        if wiki_titel:
            da = {(t.quelle.kennung, t.text[:80]) for t in rest}
            vorn = [t for t in wiki_titel if (t.quelle.kennung, t.text[:80]) not in da]
            if vorn:
                rest = vorn + [t for t in rest][: max(1, n_treffer - len(vorn))]
                hinweis = "Der Wikipedia-Artikel zum genannten Namen steht vorn. " + hinweis
        if knapp:
            rest = [wissen.Treffer(t.quelle, t.text[:KNAPP_ZEICHEN], t.punkte) for t in rest]
        if fachgebiete and any(t.quelle.fachgebiet in fachgebiete for t in rest):
            hinweis = "Fundstellen aus den Quellen deiner Fachgebiete stehen vorn. " + hinweis
        land_weg = land_weg_live = 0
        if belege.regelfrage(frage) or belege.preisfrage(frage):
            rest, land_weg = belege.fremdes_land_weg(frage, rest)
            live, land_weg_live = belege.fremdes_land_weg(frage, live)
        if land_weg + land_weg_live:
            hinweis = "Fundstellen über ein anderes Land als das gefragte wurden weggelassen. " + hinweis
        if belege.preisfrage(frage) and ziel[1] is not None:
            vorher_live = len(live)
            live = [t for t in live if t.quelle.art not in ("nachgeschaut", "live")
                    or not nachschauen.veraltet_text(t.quelle.titel + " " + t.quelle.adresse + " " + t.text, *ziel)]
            if len(live) < vorher_live:
                hinweis = f"{vorher_live - len(live)} gelesene Stellen mit Preisen aus einem früheren Jahr wurden weggelassen. " + hinweis
        if art is None or art.art == "suche":
            gesucht = [t for t in live if t.quelle.art == "nachgeschaut"]
            teile = nachschauen.teilfragen(frage)
            grenze = (min(2, len(teile)) * LIVE_STELLEN if teile else LIVE_STELLEN_LISTE if nachschauen.listenfrage(frage) else LIVE_STELLEN)
            if len(gesucht) > grenze:
                weg = {id(t) for t in gesucht[grenze:]}
                live = [t for t in live if id(t) not in weg]
                hinweis = ((f"Von den passenden gelesenen Stellen bekam das Modell die {grenze} besten, {len(weg)} weitere nicht. " if live_sortiert
                            else f"Von den gelesenen Stellen bekam das Modell die ersten {grenze}, {len(weg)} weitere nicht. ") + hinweis)
        schon = {(t.quelle.kennung, t.text[:80]) for t in live}
        zusatz, quellen = wissen.kontext_bauen(live + [t for t in rest if (t.quelle.kennung, t.text[:80]) not in schon], live=schon_live)
        if selbst and zusatz:
            zusatz = selbstauskunft.ANWEISUNG + "\n\n" + zusatz
        elif anbieter and zusatz:
            zusatz = selbstauskunft.ANWEISUNG_ANBIETER + "\n\n" + zusatz
        return zusatz, quellen, server_n + lokal_n, hinweis


    @staticmethod
    def _schritt(text: str) -> None:
        fn = getattr(_SCHRITT, "fn", None)
        if fn is not None:
            try:
                fn(text)
            except Exception:
                pass

    def _suchwoerter(self, nachrichten: list[dict] | None, frage: str, *, entscheiden: bool = False, bisher: list[str] | None = None,
                     ohne_modell: bool = False) -> list[str] | None:
        verlauf = [n for n in (nachrichten or []) if n.get("role") in ("user", "assistant") and isinstance(n.get("content"), str)][-5:]
        if not verlauf:
            verlauf = [{"role": "user", "content": frage}]
        ab = _absicht_von(verlauf)
        ist_auftrag, korrektur = ab.frisch, ab.korrektur
        if ist_auftrag:
            verlauf = verlauf[:-1] + [{"role": "user", "content": frage + (" (die vorige Antwort passte nicht)" if korrektur else "")}]
            verlauf = [n for n in verlauf if n.get("role") == "user"]
        sache = genannte_sache(verlauf, ab, frage)
        if sache:
            verlauf = [n for i, n in enumerate(verlauf) if n.get("role") == "user"
                       and not (i > 0 and verlauf[i - 1].get("role") == "assistant"
                                and str(verlauf[i - 1].get("content", "")).startswith(schriftstueck.VORSPANN))][:-1] + [{"role": "user", "content": sache}]
            entscheiden = False
        frueher = next((str(n["content"]) for n in reversed(verlauf[:-1]) if n.get("role") == "user"), "")
        bisher = [b for b in (bisher or []) if b]
        if not ohne_modell and self._ki.quelle() == "lokal" and self._ki.bereit():
            gespraech = chr(10).join(("Person: " if n["role"] == "user" else "KI: ") + " ".join(str(n["content"]).split())[:400 if n["role"] == "user" else 160]
                                     for n in verlauf)
            leit = frage_leitzeilen(frage)
            auftrag = ((leit + chr(10) + chr(10)) if leit else "") + "Gespräch:" + chr(10) + gespraech + chr(10) + chr(10)
            if bisher:
                auftrag += SUCHWORT_ANDERS.format(bisher="; ".join(f"„{b}“" for b in bisher)) + chr(10) + chr(10)
            if entscheiden:
                auftrag += SUCHWORT_ENTSCHEIDEN + chr(10) + chr(10)
            if such_sprache(frage) == "en":
                auftrag += SUCHWORT_ENGLISCH + chr(10) + chr(10)
            original = ki_laufzeit.original()
            if original:
                auftrag += f"Die Person hat auf Englisch gefragt: „{original}“." + chr(10) + chr(10)
            try:
                a = self._ki.server.frage([{"role": "user", "content": wissen.zeit_zeile() + chr(10) + auftrag + "Suchanfragen für die letzte Frage:"}],
                                         system=SUCHWORT_SYSTEM, max_tokens=48, temperature=0.0)
                if entscheiden and re.match(r"\s*[„\"']?keine\b", a.text or "", re.I):
                    return None
                liste = suchwoerter_liste(a.text)
                if ist_auftrag:
                    liste = [ohne_auftragswoerter(q, frage) for q in liste]
                z = [q for q in suchwoerter_ordnen([q for q in liste if q], frage, frueher) if q.lower() not in {b.lower() for b in bisher}]
                eigen = set(wissen.woerter(sache))
                if (sache and not bisher and 1 <= len(sache.split()) <= 8 and eigen
                        and not any(eigen <= set(wissen.woerter(q)) and len(set(wissen.woerter(q)) - eigen) <= 1 for q in z)):
                    z = [sache] + z[:1]
                if z:
                    return z
            except app_core.AppError as exc:
                _log(self._core, f"INFO suchwoerter vom Modell: {exc.code}")
        if entscheiden:
            return None
        if sache:
            regel = suchwoerter_ordnen([sache if len(sache.split()) <= 8 else (nachschauen.suchbegriffe_regel(sache, "") or sache)], frage, "") or [sache]
        elif such_sprache(frage) == "en":
            original = ki_laufzeit.original()
            regel = suchwoerter_ordnen([nachschauen.suchbegriffe_regel(original, "") or original], frage, frueher) or [original]
        else:
            regel = suchwoerter_ordnen([nachschauen.suchbegriffe_regel(frage, frueher) or frage], frage, frueher) or [frage]
        if bisher:
            r = region.erkennen(frage)
            jetzt_wort = "latest" if such_sprache(frage) == "en" else "aktuell"
            anders = [f"{q} {r.land_name if r else ''} {jetzt_wort}".replace("  ", " ").strip() for q in regel]
            return [q for q in anders if q.lower() not in {b.lower() for b in bisher}] or None
        return regel

    def _nachschauen_vorab(self, frage: str, treffer: list[wissen.Treffer], nachrichten: list[dict] | None, *, frisch: bool = True,
                           modell: bool = False):
        fn, lauf, mess = getattr(_SCHRITT, "fn", None), getattr(_SUCHLAUF, "stand", None), ki_laufzeit.messung_liste()
        eigen = getattr(_EIGEN, "an", True)
        original = ki_laufzeit.original()
        zone = ki_laufzeit.zone()
        erg: dict = {}

        def suchen() -> None:
            _SCHRITT.fn, _SUCHLAUF.stand, _EIGEN.an = fn, lauf, eigen
            ki_laufzeit.original_setzen(original)
            ki_laufzeit.zone_setzen(zone)
            ki_laufzeit.messung_teilen(mess)
            try:
                erg["r"] = self._nachschauen(frage, treffer, frisch=True, nachrichten=nachrichten) if frisch else \
                    self._nachschauen(frage, treffer, suchen=True, nachrichten=nachrichten, modell_woerter=modell)
            except BaseException as exc:
                erg["e"] = exc
            finally:
                ki_laufzeit.messung_teilen(None)

        t = threading.Thread(target=suchen, name="nachschauen-vorab", daemon=True)
        t.start()

        def ergebnis() -> tuple[list[wissen.Treffer], str]:
            t.join()
            if "e" in erg:
                raise erg["e"]
            return erg["r"]
        return ergebnis

    def _suche_nebenher(self, frage: str, nachrichten: list[dict] | None) -> None:
        lauf = getattr(_SUCHLAUF, "stand", None)
        if lauf is None or lauf["runde"] or lauf["gesucht"] or "nebenher" in lauf or not hasattr(self._nachschauer, "suche_runde"):
            return
        anfragen = nachschauen.anfragen_aufteilen(self._suchwoerter(nachrichten, frage, ohne_modell=True) or [frage], frage)
        richtung = nachschauen.richtung(frage)
        erg: dict = {}

        sprache = such_sprache(frage)
        original, zone = ki_laufzeit.original(), ki_laufzeit.zone()

        def suchen() -> None:
            ki_laufzeit.original_setzen(original)
            ki_laufzeit.zone_setzen(zone)
            try:
                erg["r"] = self._nachschauer.suche_runde(anfragen, frage, sprache=sprache, zeit=nachschauen.zeitraum(frage),
                                                          ausser=frozenset(), ziel=zeitziel(frage))
            except BaseException as exc:
                erg["e"] = exc

        t = threading.Thread(target=suchen, name="suche-nebenher", daemon=True)
        t.start()

        def holen():
            t.join()
            if "e" in erg:
                raise erg["e"]
            return erg["r"]
        lauf["nebenher"] = {"anfragen": anfragen, "holen": holen}

    def nachschauen_an(self) -> bool:
        if getattr(_FENSTERFRAGE, "an", False):
            return False
        return bool(self._ki.einstellung().get("nachschauen", True))

    def _waehrung_antwort(self, text: str) -> "kurse.Ergebnis | None":
        if not self.nachschauen_an():
            return None
        try:
            return kurse.frage_beantworten(text)
        except Exception as exc:
            _log(self._core, f"FEHLER kurse: {type(exc).__name__}")
            return None

    def _nachschauen(self, frage: str, treffer: list[wissen.Treffer], *, frisch: bool = False, nachrichten: list[dict] | None = None,
                     abgedeckt: bool | None = None, suchen: bool = False, modell_woerter: bool = False) -> tuple[list[wissen.Treffer], str]:
        if _dateifrage(frage):
            return [], ""
        deckt_ab = (lambda: abgedeckt) if abgedeckt is not None else (lambda: self._deckt_ab(frage, treffer))
        a = nachschauen.erkennen_im_gespraech(nachrichten) if nachrichten else nachschauen.erkennen(frage)
        lauf = getattr(_SUCHLAUF, "stand", None)
        spaeter = bool(lauf and lauf["runde"] > 0)
        if a is None and (frisch or suchen) and frage.strip():
            a = nachschauen.Auftrag("suche", " ".join(frage.split()))
        alle: list[str] | None = None
        if a is None and suche_denkbar(frage) and not deckt_ab():
            self._schritt("überlegt, ob und wonach es suchen soll …")
            alle = self._suchwoerter(nachrichten, frage, entscheiden=True)
            if alle:
                a = nachschauen.Auftrag("suche", " ".join(frage.split()))
        if a is None or a.rueckfrage:
            return [], ""
        if a.art == "suche" and not frisch and not suchen and alle is None and deckt_ab():
            return [], ""
        weitere: list[str] = []
        neben = lauf.get("nebenher") if lauf and not lauf["gesucht"] and a.art == "suche" and alle is None else None
        if neben is not None:
            try:
                brauchbar = bool(neben["holen"]()[0])
            except Exception:
                brauchbar = False
            if brauchbar:
                alle = list(neben["anfragen"])
            else:
                lauf["nebenher_leer"] = lauf.pop("nebenher", None)
        if a.art == "suche":
            if alle is None and not spaeter and not _frueher_gefragt(nachrichten) and not modell_woerter:
                alle = self._suchwoerter(nachrichten, frage, ohne_modell=True)
                if lauf is not None and alle:
                    lauf["nur_regel"] = True
            if alle is None:
                self._schritt("überlegt, wonach es suchen soll …" if not spaeter else "sucht noch einmal mit anderen Wörtern …")
                alle = self._suchwoerter(nachrichten, frage, bisher=lauf["gesucht"] if spaeter else None)
                if lauf is not None:
                    lauf["nur_regel"] = False
            if not alle:
                return [], "Eine weitere Suche mit anderen Wörtern war nicht möglich."
            alle = nachschauen.anfragen_aufteilen(alle, frage)
            if hasattr(self._nachschauer, "suche_runde"):
                return self._suchrunde(frage, alle, lauf, treffer, frisch=frisch or spaeter)
            a, weitere = nachschauen.Auftrag("suche", alle[0]), alle[1:]
        gemerkt = [] if frisch else [t for t in treffer if t.quelle.art == "nachgeschaut" and t.quelle.gueltig() and (not a.titel or t.quelle.titel == a.titel)]
        if a.art == "suche":
            gemerkt = [t for t in gemerkt if nachschauen.frage_kennung(a.frage) in t.text or t.punkte >= 3]
        if gemerkt:
            g = gemerkt[0].quelle
            self._letzter_stand = {"art": a.art, "titel": g.titel, "nachgeschaut": g.datum, "gilt_bis": g.gueltig_bis, "aus_gedaechtnis": True}
            return gemerkt[:4], f"Schon vorhin nachgeschaut (privat auf diesem PC): „{g.titel}“, am {g.datum[:10]} um {g.datum[11:16]} UTC, gilt bis {g.gueltig_bis[:10]} {g.gueltig_bis[11:16]} UTC."
        self._schritt(f"schaut das Wetter für {a.ort} nach …" if a.art == "wetter" and a.ort else ("holt die neuesten Schlagzeilen …" if a.art == "schlagzeilen"
                      else f"sucht im Internet nach „{a.frage}“ und liest die besten Seiten …"))
        try:
            ergebnisse = self._nachschauer.ausfuehren(a)
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT nachschauen {a.art}: {exc.code}: {exc.detail}")
            if not weitere:
                return [], f"Nachschauen ({a.art}) hat nicht geklappt: {exc.detail}."
            ergebnisse = []
        for q in weitere:
            self._schritt(f"sucht noch nach „{q}“ …")
            try:
                gesehen = {e.adresse for e in ergebnisse}
                ergebnisse += [e for e in self._nachschauer.ausfuehren(nachschauen.Auftrag("suche", q)) if e.adresse not in gesehen]
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT nachschauen suche 2: {exc.code}: {exc.detail}")
        if not ergebnisse:
            return [], "Nachschauen (suche) hat nichts gefunden."
        ergebnisse, alt_raus = nachschauen.nur_aktuelle([a.frage] + weitere, ergebnisse) if a.art == "suche" else (ergebnisse, 0)
        ergebnisse.sort(key=lambda e: 0 if e.titel.startswith("Suchergebnisse") else 1)
        je_seite: list[list[wissen.Treffer]] = []
        for e in ergebnisse:
            q, tr = nachschauen.als_quelle(e)
            je_seite.append(tr)
            self._nachgeschaut_merken(e)
        out = [tr[i] for i in range(max((len(x) for x in je_seite), default=0)) for tr in je_seite if i < len(tr)]
        woher = ergebnisse[0].woher if ergebnisse else ""
        wohin = _wohin_gemerkt()
        if ergebnisse:
            self._letzter_stand = {"art": a.art, "titel": ergebnisse[0].titel, "nachgeschaut": wissen._jetzt(), "gilt_bis": ergebnisse[0].gueltig_bis, "aus_gedaechtnis": False}
        return out[:10], f"Jetzt {woher}, {wohin}." + (f" {gesucht_satz(frage, [a.frage] + weitere)}" if a.art == "suche" else "") + (
            (" 1 Seite mit einem älteren Stand (frühere Saison oder früheres Jahr) aussortiert." if alt_raus == 1 else
             f" {alt_raus} Seiten mit einem älteren Stand (frühere Saison oder früheres Jahr) aussortiert." if alt_raus else ""))

    def _suchrunde(self, frage: str, anfragen: list[str], lauf: dict | None, treffer: list[wissen.Treffer], *, frisch: bool) -> tuple[list[wissen.Treffer], str]:
        r = region.erkennen(frage)
        richtung = nachschauen.richtung(frage)
        if not frisch:
            kennung = nachschauen.frage_kennung(frage)
            grenze = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
            gemerkt = [t for t in treffer if t.quelle.art == "nachgeschaut" and t.quelle.gueltig() and kennung in t.text and (not richtung or t.quelle.datum >= grenze)]
            if gemerkt:
                g = gemerkt[0].quelle
                self._letzter_stand = {"art": "suche", "titel": g.titel, "nachgeschaut": g.datum, "gilt_bis": g.gueltig_bis, "aus_gedaechtnis": True}
                return gemerkt[:4], f"Schon vorhin nachgeschaut (privat auf diesem PC): „{g.titel}“, am {g.datum[:10]} um {g.datum[11:16]} UTC, gilt bis {g.gueltig_bis[:10]} {g.gueltig_bis[11:16]} UTC."
        neben = lauf.get("nebenher") if lauf and not lauf["gesucht"] else None
        if neben is not None and neben["anfragen"] == anfragen:
            lauf.pop("nebenher", None)
        else:
            neben = None
        if len(anfragen) > 1:
            vorne, letzte = _aufzaehlung(anfragen)
            self._schritt(f"sucht im Internet nach {vorne} und „{letzte}“ und liest die besten Seiten …")
        else:
            self._schritt(f"sucht im Internet nach „{''.join(anfragen)}“ und liest die besten Seiten …")
        try:
            ergebnisse, gelesen, woher = neben["holen"]() if neben is not None else self._nachschauer.suche_runde(
                anfragen, frage, sprache=such_sprache(frage), zeit=nachschauen.zeitraum(frage),
                ausser=frozenset(lauf["gelesen"]) if lauf else frozenset(), ziel=zeitziel(frage))
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT nachschauen suche: {exc.code}: {exc.detail}")
            if lauf is not None:
                lauf["gesucht"] += anfragen
                if exc.code != nachschauen.SUCHE_NICHTS:
                    lauf["abgelehnt"] = True
            return [], f"Nachschauen (suche) hat nichts gefunden ({exc.detail})."
        if lauf is not None:
            lauf["gesucht"] += anfragen
            lauf["gelesen"] |= set(gelesen)
        je_seite: list[list[wissen.Treffer]] = []
        for e in ergebnisse:
            _q, tr = nachschauen.als_quelle(e)
            je_seite.append(tr)
            self._nachgeschaut_merken(e)
        out = [tr[i] for i in range(max((len(x) for x in je_seite), default=0)) for tr in je_seite if i < len(tr)]
        wohin = _wohin_gemerkt()
        self._letzter_stand = {"art": "suche", "titel": ergebnisse[0].titel, "nachgeschaut": wissen._jetzt(), "gilt_bis": ergebnisse[0].gueltig_bis, "aus_gedaechtnis": False}
        seiten = sum(1 for e in ergebnisse if not e.titel.startswith("Suchergebnisse"))
        anfragen = nachschauen.anfragen_aufteilen([q for q in anfragen if q and q.strip()], frage)[:4] or [frage]
        gelesen = (f"Jetzt im Internet gesucht ({woher}), 1 Seite gelesen, {wohin}." if seiten == 1
                   else f"Jetzt im Internet gesucht ({woher}), {seiten} Seiten gelesen, {wohin}.")
        return out[:12], f"{gelesen} {gesucht_satz(frage, anfragen, r.land if r else '')}"

    @staticmethod
    def _deckt_ab(frage: str, treffer: list[wissen.Treffer]) -> bool:
        fw = set(wissen.woerter(frage))
        if not fw:
            return True
        noetig = max(2, -(-len(fw) * 3 // 5))
        return any(len(fw & set(wissen.woerter(t.quelle.titel + " " + t.text))) >= noetig for t in treffer)

    def _nachgeschaut_merken(self, e: nachschauen.Ergebnis) -> None:
        if not getattr(_EIGEN, "an", True):
            return
        try:
            b = hausordnung.pruefen(e.titel + "\n" + e.text)
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
            self._wissen.aufraeumen()
            self._wissen.hinzufuegen("nachgeschaut", e.titel, e.adresse, e.text, gueltig_bis=e.gueltig_bis)
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT nachgeschaut_merken: {exc.code}: {exc.detail}")


    def _vorwaermen_lauf(self):
        e = self._ki.einstellung()
        jetzt = datetime.now()
        heute = jetzt.strftime("%Y-%m-%d")
        w = e.get("vorwaermen_weiter") if isinstance(e.get("vorwaermen_weiter"), dict) else {}
        offen = int(w.get("ab", 0) or 0) if (w.get("tag") == heute and vorwaermen.einstellung_lesen(e)["an"]
                                              and vorwaermen.VON_STUNDE <= jetzt.hour < vorwaermen.BIS_STUNDE) else 0
        if w:
            self._ki.einstellung_setzen(vorwaermen_weiter=None)
        if not self.nachschauen_an() or (not offen and not vorwaermen.faellig(e, jetzt)):
            return None
        self._ki.einstellung_setzen(vorwaermen_zuletzt=heute)
        _EIGEN.an = True
        frage_wartet = getattr(self._rechen, "frage_wartet", lambda: False)
        stand: dict = {}
        n, fehler = vorwaermen.laufen(self._nachschauer, self._nachgeschaut_merken, ort_eigen=vorwaermen.einstellung_lesen(e)["ort"],
                                      weiter=lambda: self._core.run_state() is node_local_state.RunState.ACTIVE and not frage_wartet(),
                                      ab=offen, stand=stand)
        if "weiter_ab" in stand:
            self._ki.einstellung_setzen(vorwaermen_weiter={"tag": heute, "ab": int(stand["weiter_ab"])})
            _log(self._core, f"OK vorwaermen: für eine Frage unterbrochen, geht danach beim {stand['weiter_ab'] + 1}. Nachschauen weiter")
        for f in fehler[:5]:
            _log(self._core, f"INFO vorwaermen: {f}")
        return n


    PRUEFSTAND_WEGE = ("zustand", "ki_zustand", "skills_liste", "gespraeche_liste", "tagesbilanz")

    def pruefstand_an(self) -> bool:
        return bool(self._ki.einstellung().get("pruefstand_an", False))

    def _pruefrunden_heute(self) -> int:
        e = self._ki.einstellung().get("pruefrunden")
        return int(e.get("n", 0) or 0) if isinstance(e, dict) and e.get("tag") == datetime.now().strftime("%Y-%m-%d") else 0

    def _karte_fremd(self) -> str:
        r = grafik_last.belegt()
        if r is not None:
            return r[1] if r[0] else ""
        try:
            leer = self._rechen._leerlauf_s()
        except Exception:
            leer = None
        return "" if (leer is not None and leer >= rechenarbeit.LEERLAUF_S) else "jemand arbeitet am PC, und die Last auf der Grafikkarte ist nicht messbar"

    def _runde_ruht(self, grund: str) -> None:
        if grund != getattr(self, "_ruht_gemeldet", ""):
            self._ruht_gemeldet = grund
            _log(self._core, f"INFO pruefstand: die Prüfrunde wartet, {grund}")

    def _pruefstand_lauf(self, *, erzwingen: bool = False, probelauf: bool = False) -> dict | None:
        if self._pruefen_pausiert():
            if erzwingen:
                raise app_core.AppError("PRUEFEN_PAUSIERT", PRUEFEN_PAUSIERT_TEXT)
            return None
        admin = self._community.ist_admin()
        e = self._ki.einstellung()
        if admin:
            if not erzwingen and (not self.pruefstand_an() or self._pruefrunden_heute() >= pruefstand.DURCHGANG_RUNDEN):
                return None
        elif (erzwingen or not PRUEFSTAND_MITGLIEDER or modell_stufe(self._ki.wahl.modell.name if self._ki.wahl else "") < PRUEFSTAND_AB_B
              or not pruefstand.faellig(str(e.get("pruefstand_zuletzt", "")), datetime.now())):
            return None
        if not erzwingen:
            if time.monotonic() < self._pruefrunde_pause_bis:
                return None
            steht_an = getattr(self, "_update_steht_an", "")
            if steht_an and steht_an > app_core.APP_BUILD:
                self._runde_ruht(f"ein Update auf Bau {steht_an} steht an")
                return None
            fremd = self._karte_fremd()
            if fremd:
                self._runde_ruht(fremd)
                return None
        try:
            if admin:
                fragen, runde = self._community.pruefrunde_holen(app_core.APP_BUILD, getattr(self._ki, "fassung", "") or "", probelauf=probelauf)
            else:
                self._ki.einstellung_setzen(pruefstand_zuletzt=datetime.now().strftime("%Y-%m-%d"))
                fragen, runde = self._community.pruefstand_holen(), {}
        except BaseException:
            self._pruefrunde_fehlschlag("der Server gab keine Prüfrunde")
            raise
        if not fragen:
            self._pruefrunde_fehlschlag("der Server hat für dieses Gerät gerade keine Prüffragen")
            if erzwingen:
                raise app_core.AppError("KEINE_PRUEFFRAGEN", "Der Server hat gerade keine Prüffragen für diesen PC. Meist kennt er sein Modell "
                                                             "noch nicht, weil KIplatz eben erst gestartet ist; bitte in einer Minute noch einmal.")
            return None
        self._ruht_gemeldet = ""
        self._mess_suche_zuletzt, self._mess_suchen, self._mess_suche_gemeldet = 0.0, 0, False
        self._mess_bremse = True
        self._pruefung_seit = time.monotonic()
        self._pruefrunde = {"n": 0, "von": len(fragen), "nummer": runde.get("nummer"), "runden": runde.get("von"),
                            "rotation_bis": runde.get("pos_bis"), "rotation_von": runde.get("von_gesamt")}
        self._runde_ruht_grund = ""
        try:
            b = self._pruefstand_fragen(fragen, runde=runde, erzwingen=erzwingen)
        except BaseException:
            self._pruefrunde_fehlschlag("die Prüfrunde brach mit einem Fehler ab")
            raise
        finally:
            self._mess_bremse = False
            self._pruefung_seit = 0.0
            self._pruefrunde = None
        if b is None and self._runde_ruht_grund == "die KI ist ausgefallen":
            self._pruefrunde_fehlschlag(self._runde_ruht_grund)
        if b is not None and admin:
            self._ki.einstellung_setzen(pruefrunden={"tag": datetime.now().strftime("%Y-%m-%d"), "n": self._pruefrunden_heute() + 1})
        return b

    def _pruefrunde_fehlschlag(self, grund: str) -> None:
        self._pruefrunde_pause_bis = time.monotonic() + PRUEFRUNDE_NACH_FEHLER_S
        _log(self._core, f"INFO pruefstand: {grund}; die nächste Prüfrunde frühestens in {PRUEFRUNDE_NACH_FEHLER_S // 60} Minuten")

    def _websuche(self, frage: str, **kw) -> list[dict]:
        vorrang = getattr(self._rechen, "vorrang", None)
        pruef = (getattr(self, "_mess_bremse", False) and getattr(self._rechen, "phase", "") == "prueft_selbst"
                 and not (isinstance(vorrang, threading.Event) and vorrang.is_set()))
        if pruef:
            try:
                gemerkt = self._community.websuche(frage, 8, **{**kw, "pruef": True, "nur_gemerkt": True})
            except Exception:
                gemerkt = None
            if gemerkt is not None:
                return gemerkt
            self._mess_suche_budget(vorrang)
            return self._community.websuche(frage, 8, **{**kw, "pruef": True})
        return self._community.websuche(frage, 8, **kw)

    def _mess_suche_budget(self, vorrang) -> None:
        if self._mess_suchen >= MESS_SUCHEN_NACHT_MAX:
            if not self._mess_suche_gemeldet:
                self._mess_suche_gemeldet = True
                _log(self._core, f"INFO pruefstand: {MESS_SUCHEN_NACHT_MAX} Internet-Suchen in dieser Runde erreicht, weitere Prüffragen laufen ohne Suche")
            raise app_core.AppError("SUCHE_GESCHONT", "Die Prüfrunde schont die Suchmaschinen; diese Prüffrage läuft ohne Suche.")
        jetzt = self._mess_uhr()
        ziel = self._mess_suche_zuletzt + MESS_SUCHE_ABSTAND_S if self._mess_suche_zuletzt else jetzt
        beginn = time.monotonic()
        try:
            while jetzt < ziel:
                if isinstance(vorrang, threading.Event) and vorrang.is_set():
                    raise app_core.AppError("SUCHE_GESCHONT", "Jemand fragt gerade selbst; diese Prüffrage läuft ohne Suche.")
                self._mess_schlafen(min(0.5, ziel - jetzt))
                jetzt = self._mess_uhr()
        finally:
            self._mess_gewartet = getattr(self, "_mess_gewartet", 0.0) + (time.monotonic() - beginn)
        self._mess_suche_zuletzt, self._mess_suchen = jetzt, self._mess_suchen + 1


    def _pruefen_pausiert(self, *, frisch: bool = False) -> bool:
        try:
            pausiert = bool(getattr(self._community, "pruefen_pausiert", lambda **_k: False)(**({"frisch": True} if frisch else {})))
        except Exception:
            return False
        if pausiert:
            heute = datetime.now().strftime("%Y-%m-%d")
            if getattr(self, "_pausiert_gemeldet", "") != heute:
                self._pausiert_gemeldet = heute
                _log(self._core, "INFO pruefstand: Prüfen und Training sind am Server pausiert (bis die Community genug freie Rechner hat)")
        return pausiert

    def _training_einstellung(self) -> dict | None:
        t = self._ki.einstellung().get("training")
        if not isinstance(t, dict) or not t.get("an"):
            return None
        try:
            ordner, python = Path(str(t.get("ordner", ""))), Path(str(t.get("python", "")))
        except (TypeError, ValueError):
            return None
        if not (ordner.is_absolute() and python.is_absolute() and python.is_file()):
            return None
        return {"ordner": ordner, "python": python}

    def _mit_freier_karte(self, befehl: list[str], ordner, logdatei: Path, hoechstens_s: float, *, grund: str, meldung: str,
                          gesperrt: str):
        rechen = self._rechen
        getattr(rechen, "fragen_abgeben", lambda grund: None)(grund)
        vorher = rechen.phase
        rechen.phase, rechen.meldung = "trainiert", meldung
        self._ki.gesperrt = gesperrt
        proc = None
        unterbrochen = False
        try:
            self._ki_entladen()
            getattr(rechen, "_server_stoppen", lambda: None)()
            with open(logdatei, "ab") as log:
                proc = subprocess.Popen(befehl, cwd=str(ordner), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            ki_laufzeit.an_programm_binden(proc)
            bis = time.time() + hoechstens_s
            while proc.poll() is None:
                if time.time() > bis:
                    break
                if self._core.run_state() is not node_local_state.RunState.ACTIVE:
                    unterbrochen = True
                    break
                time.sleep(TRAINING_TAKT_S)
        finally:
            try:
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=30)
            except Exception as exc:
                _log(self._core, f"FEHLER training beenden: {type(exc).__name__}")
            finally:
                self._ki.gesperrt = ""
                rechen.phase = vorher
                try:
                    if self.ki_auto() and not self._schwach():
                        self._ki.einschalten()
                except Exception as exc:
                    _log(self._core, f"FEHLER ki nach dem training: {type(exc).__name__}")
        return proc, unterbrochen

    def kurztest_starten(self) -> dict:
        def go():
            if not self._community.ist_admin():
                raise app_core.AppError("NUR_ADMIN", "Den Kurztest startet nur der Admin-PC.")
            t = self._training_einstellung()
            if t is None or not (t["ordner"] / KURZTEST_SKRIPT).is_file():
                raise app_core.AppError("KURZTEST_FEHLT", f"Training oder {KURZTEST_SKRIPT} fehlen im Trainingsordner (Einstellung „training“).")
            pruefstand = (self._pruefstand_thread is not None and self._pruefstand_thread.is_alive()) or bool(getattr(self, "_pruefung_seit", 0.0))
            if pruefstand or not self._karte_lock.acquire(blocking=False):
                raise app_core.AppError("KURZTEST_LAEUFT", "Gerade läuft schon ein Test oder ein Training.")

            def lauf():
                try:
                    self._guarded("kurztest_lauf", lambda: self._kurztest_lauf(t))
                finally:
                    self._karte_lock.release()
            try:
                self._kurztest_thread = threading.Thread(target=lauf, name="kurztest", daemon=True)
                self._kurztest_thread.start()
            except BaseException:
                self._karte_lock.release()
                raise
            return {"gestartet": True}
        return self._guarded("kurztest_starten", go, "Der Kurztest läuft, höchstens 10 Minuten. KIplatz pausiert so lange und startet danach wieder.")

    def _kurztest_lauf(self, t: dict) -> dict:
        aus = t["ordner"] / f"kurztest-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        _log(self._core, f"OK kurztest: beginnt in {aus.name}")
        self._ki.einstellung_setzen(kurztest_ergebnis={"zeit": datetime.now().isoformat(timespec="seconds"), "ende": "läuft", "bericht": ""})
        proc, unterbrochen = self._mit_freier_karte(
            [str(t["python"]), "-I", "-X", "utf8", str(t["ordner"] / KURZTEST_SKRIPT), str(aus), *KURZTEST_ART], t["ordner"],
            t["ordner"] / f"{aus.name}.log", KURZTEST_HOECHSTENS_S, grund="dieser PC testet gerade das Training",
            meldung="Testet das Training. Fragen beantworten so lange andere PCs.",
            gesperrt="Dieser PC testet gerade das Training. Bitte frag in ein paar Minuten noch einmal.")
        try:
            bericht = (aus / "bericht.txt").read_text(encoding="utf-8")
        except OSError:
            bericht = ""
        ende = ("unterbrochen" if unterbrochen else "fertig" if proc is not None and proc.returncode == 0 and bericht
                else f"Fehler (Rückgabe {getattr(proc, 'returncode', None)})")
        ergebnis = {"zeit": datetime.now().isoformat(timespec="seconds"), "ende": ende, "ordner": aus.name, "bericht": bericht[:4000]}
        self._ki.einstellung_setzen(kurztest_ergebnis=ergebnis)
        _log(self._core, f"OK kurztest: {ende}, Bericht {aus / 'bericht.txt'}")
        return ergebnis

    def kurztest_stand(self) -> dict:
        return self._guarded("kurztest_stand", lambda: {"laeuft": self._kurztest_laeuft(),
                                                         "ergebnis": self._ki.einstellung().get("kurztest_ergebnis") or {}})

    def _kurztest_laeuft(self) -> bool:
        t = getattr(self, "_kurztest_thread", None)
        return bool(t is not None and t.is_alive())

    def _pruefstand_fragen(self, fragen: list, *, runde: dict, erzwingen: bool) -> dict | None:
        if erzwingen:
            self._rechen.phase, self._rechen.meldung = "prueft_selbst", ""
        rid = str(runde.get("id") or "")
        art = f"runde:{rid}:{app_core.APP_BUILD}" if rid else f"tag:{datetime.now():%Y-%m-%d}:{app_core.APP_BUILD}"
        zs = _Zwischenstand(Path(self._ki.ordner.ki_dir) / "pruefstand-zwischenstand.ndjson", art)
        fertig, schon = zs.laden()
        if schon or not fertig:
            zs.beginnen()
            fertig = {}
        else:
            _log(self._core, f"OK pruefstand: Zwischenstand gefunden, {len(fertig)} Prüffragen schon beantwortet; es geht dort weiter")
        self._ki_starten_blockierend()
        antworten: list[dict] = []
        ruht = ""
        for f in fragen:
            if self._core.run_state() is not node_local_state.RunState.ACTIVE:
                ruht = "Pause oder Programmende"
                break
            kennung = str(f.get("kennung", ""))
            alt = fertig.get(kennung)
            if alt is not None and alt[0] == str(f.get("frage", "")):
                antworten.append(alt[1])
                self._pruefrunde_zaehlen(len(antworten))
                continue
            fremd = self._karte_fremd()
            if fremd:
                ruht = fremd
                break
            for versuch in range(PRUEFSTAND_VERSUCHE):
                getattr(self._rechen, "mitglied_jetzt", lambda: False)()
                bis = time.time() + rechenarbeit.VORRANG_WARTEN_MAX_S
                while self._rechen.vorrang_aktiv() and time.time() < bis:
                    if getattr(self._rechen, "mitglied_jetzt", lambda: False)():
                        continue
                    time.sleep(0.5)
                t0 = time.time()
                self._mess_gewartet = 0.0
                _SCHATTEN.zeit = 0.0
                schein: dict = {}
                vorrang = getattr(self._rechen, "vorrang", None)
                _VERMISCHT.liste = []
                _GESTRICHEN.liste = []
                _SCHATTEN.liste = []
                _MESSWEG.d = {}
                ablauf: list[tuple[float, str]] = []
                ki_aus = False
                try:
                    with ki_laufzeit.abbruch_bei(vorrang) if isinstance(vorrang, threading.Event) else contextlib.nullcontext():
                        text, schein = self._antwort_fuer_mitglied([{"role": "user", "content": str(f.get("frage", ""))}], [], "Prüfstand",
                                                                   schritt_melden=lambda s, _a=ablauf, _t=t0: _a.append((time.time() - _t, str(s))),
                                                                   messen=True)
                except app_core.AppError as exc:
                    text = f"(keine Antwort: {exc.detail})"
                    ki_aus = exc.code == "KI_AUS"
                finally:
                    vermischt_liste, _VERMISCHT.liste = list(getattr(_VERMISCHT, "liste", None) or []), None
                    gestrichen_liste, _GESTRICHEN.liste = list(getattr(_GESTRICHEN, "liste", None) or []), None
                    schatten_liste, _SCHATTEN.liste = list(getattr(_SCHATTEN, "liste", None) or []), None
                    weg, _MESSWEG.d = getattr(_MESSWEG, "d", None), None
                if ki_aus:
                    _log(self._core, f"INFO pruefstand: die KI war bei Prüffrage {len(antworten) + 1} aus{self._ki_ende_grund()}; sie wird neu gestartet")
                    if versuch == PRUEFSTAND_VERSUCHE - 1:
                        break
                    try:
                        self._ki_starten_blockierend()
                        continue
                    except app_core.AppError as exc:
                        _log(self._core, f"ABGELEHNT pruefstand: die KI startet nicht ({exc.code}); die Runde ruht")
                        break
                if not (isinstance(vorrang, threading.Event) and vorrang.is_set()) or versuch == PRUEFSTAND_VERSUCHE - 1:
                    break
                _log(self._core, "OK pruefstand: Prüffrage für eine echte Frage abgebrochen, sie wird wiederholt")
            if ki_aus:
                ruht = "die KI ist ausgefallen"
                break
            pr = schein.get("pruefung") if isinstance(schein.get("pruefung"), dict) else {}
            gewartet = getattr(self, "_mess_gewartet", 0.0)
            richter_s = float(getattr(_SCHATTEN, "zeit", 0.0) or 0.0)
            if isinstance(weg, dict):
                weg["schritte"] = ohne_suchbremse(ohne_suchbremse(schritte_summe(ablauf, time.time() - t0), gewartet), richter_s,
                                                  name="Probe: Richter", zuerst=())
            eintrag = {"kennung": kennung, "antwort": text, "dauer_s": round(max(0.0, time.time() - t0 - gewartet - richter_s), 1),
                       "pruefung": {k: pr.get(k, 0) for k in ("gruen", "gelb", "rot")}, "belege": list(schein.get("belege") or [])[:5],
                       "quellen": str(schein.get("quellen", ""))[:600],
                       "notiz": notiz_zusammen(vermischt_notiz(vermischt_liste) + schatten_notiz(schatten_liste) + gestrichen_notiz(gestrichen_liste),
                                               pruefstand.notiz_aus(schein.get("quellen", ""))),
                       "weg": mess_weg(schein, weg)}
            zs.anhaengen(kennung, str(f.get("frage", "")), eintrag)
            antworten.append(eintrag)
            self._pruefrunde_zaehlen(len(antworten))
        if ruht:
            self._runde_ruht_grund = ruht
            _log(self._core, f"INFO pruefstand: Runde ruht nach {len(antworten)} von {len(fragen)} Prüffragen ({ruht}); beim nächsten Mal geht es dort weiter")
            return None
        wege = {}
        for name in self.PRUEFSTAND_WEGE:
            try:
                r = getattr(self, name)()
                wege[name] = bool(isinstance(r, dict) and r.get("ok", True))
            except Exception:
                wege[name] = False
        for versuch in range(PRUEFSTAND_HOCHLADEN_VERSUCHE):
            try:
                b = self._community.pruefstand_ergebnis([mess_bericht(a) for a in antworten], wege, runde=rid)
                break
            except app_core.AppError as exc:
                _log(self._core, f"FEHLER pruefstand hochladen (Versuch {versuch + 1}): {exc.code}")
                if versuch == PRUEFSTAND_HOCHLADEN_VERSUCHE - 1:
                    raise
                self._mess_schlafen(PRUEFSTAND_HOCHLADEN_WARTE_S)
        zs.gemeldet()
        r = b.get("runde") if isinstance(b.get("runde"), dict) else None
        _log(self._core, f"OK pruefstand {b.get('richtig')} von {b.get('gesamt')} richtig, Wege {b.get('wege_ok')} von {b.get('wege_gesamt')}"
                         + (f"; Runde {r.get('nummer')} von {runde.get('von')}, Messreihe {r.get('richtig')} von {r.get('gesamt')}" if r else ""))
        try:
            self._ki.einstellung_setzen(pruefstand_nacht={"tag": str(b.get("tag", ""))[:10], "richtig": int(b.get("richtig", 0) or 0),
                                                          "gesamt": int(b.get("gesamt", 0) or 0), "hinten": bool(b.get("hinten"))})
        except (TypeError, ValueError):
            pass
        return b

    def _pruefrunde_zaehlen(self, n: int) -> None:
        p = getattr(self, "_pruefrunde", None)
        if isinstance(p, dict):
            p["n"] = n

    def pruefstand_stand(self) -> dict:
        def go():
            e = self._ki.einstellung()
            laeuft = bool((self._pruefstand_thread and self._pruefstand_thread.is_alive()) or getattr(self, "_pruefung_seit", 0.0))
            p = getattr(self, "_pruefrunde", None)
            d = {"an": self.pruefstand_an(), "zuletzt": str(e.get("pruefstand_zuletzt", "")), "laeuft": laeuft,
                 "runden_heute": self._pruefrunden_heute(), "runden_tag": pruefstand.DURCHGANG_RUNDEN,
                 "wartet": laeuft and bool(getattr(self, "_knopf_wartet", False)), "meldung": "" if laeuft else str(getattr(self, "_knopf_meldung", "")),
                 **({"fortschritt": dict(p)} if isinstance(p, dict) else {})}
            try:
                d.update(self._community.pruefstand_stand())
            except app_core.AppError as exc:
                d["hinweis"] = exc.detail
            try:
                d["training"] = self._community.trainingsliste_zahl()
            except app_core.AppError:
                d["training"] = None
            return d
        return self._guarded("pruefstand_stand", go)

    def pruefstand_setzen(self, daten: dict) -> dict:
        def go():
            daten_ = dict(daten or {})
            if "an" in daten_:
                self._ki.einstellung_setzen(pruefstand_an=bool(daten_.pop("an")))
            if daten_:
                self._community.pruefstand_setzen(daten_)
            return self.pruefstand_stand()["daten"]
        return self._guarded("pruefstand_setzen", go, "Gespeichert.")

    def pruefstand_jetzt(self, probelauf: bool = False) -> dict:
        def go():
            if (self._pruefstand_thread and self._pruefstand_thread.is_alive()) or getattr(self, "_pruefung_seit", 0.0):
                raise app_core.AppError("PRUEFSTAND_LAEUFT", "eine Prüfrunde läuft schon")
            if self._kurztest_laeuft():
                raise app_core.AppError("KURZTEST_LAEUFT", "Gerade läuft schon ein Test oder ein Training.")
            if self._pruefen_pausiert(frisch=True):
                raise app_core.AppError("PRUEFEN_PAUSIERT", PRUEFEN_PAUSIERT_TEXT)
            fremd = self._karte_fremd()
            if fremd:
                _log(self._core, f"ABGELEHNT pruefstand_jetzt: {fremd}")
                raise app_core.AppError("KARTE_BELEGT", "die Grafikkarte wird gerade von einem anderen Programm gebraucht, zum Beispiel von einem Spiel oder Video"
                                        if "nicht messbar" not in fremd else "am PC wird gerade gearbeitet, und die Last auf der Grafikkarte ist nicht messbar")

            def lauf():
                gehalten = False
                try:
                    gehalten = self._rechen.anhalten(hoechstens_s=PRUEFSTAND_ANHALTEN_S)
                    self._knopf_wartet = False
                    if not gehalten:
                        self._knopf_meldung = (f"Die Rechenarbeit war {int(PRUEFSTAND_ANHALTEN_S // 60)} Minuten lang mitten in einem Auftrag; "
                                               "bitte noch einmal drücken.")
                        _log(self._core, "ABGELEHNT pruefstand_lauf: die Rechenarbeit kam nicht zwischen zwei Aufträge")
                        return
                    r = self._guarded("pruefstand_lauf", lambda: self._pruefstand_lauf(erzwingen=True, probelauf=bool(probelauf)))
                    b = r.get("daten") if r.get("ok") else None
                    rd = b.get("runde") if isinstance(b, dict) and isinstance(b.get("runde"), dict) else {}
                    if not r.get("ok"):
                        self._knopf_meldung = str(r.get("text", ""))
                    elif rd:
                        self._knopf_meldung = f"Fertig: {rd.get('richtig', 0)} von {rd.get('gesamt', 0)} Fragen richtig, der Bericht ist beim Server."
                    elif isinstance(b, dict):
                        self._knopf_meldung = f"Fertig: {b.get('richtig', 0)} von {b.get('gesamt', 0)} Prüffragen richtig, der Bericht ist beim Server."
                    else:
                        grund = self._runde_ruht_grund or "sie wurde unterbrochen"
                        self._knopf_meldung = f"Die Runde wartet ({grund}); beim nächsten Mal geht es dort weiter."
                finally:
                    self._knopf_wartet = False
                    if gehalten:
                        self._rechen.weiter()
            self._knopf_wartet, self._knopf_meldung = True, ""
            self._pruefstand_thread = threading.Thread(target=lauf, name="pruefstand", daemon=True)
            self._pruefstand_thread.start()
            return {"gestartet": True}
        return self._guarded("pruefstand_jetzt", go, "Der Probelauf läuft: 24 Fragen, rund 5 Minuten. Ist noch eine Prüfrunde offen, geht zuerst sie zu Ende." if probelauf
                             else "Die Prüfrunde läuft: 100 Fragen, rund 20 Minuten. Du kannst den PC dabei weiter benutzen.")

    def vorwaermen_setzen(self, an: bool) -> dict:
        return self._guarded("vorwaermen_setzen", lambda: self._ki.einstellung_setzen(vorwaermen=bool(an)) or {"vorwaermen": bool(an)},
                             "Dein Rechner holt in der Früh Wetter und Schlagzeilen für alle vor." if an else "Kein Vorwärmen mehr.")


    def tagesbilanz(self, hinweis: bool = False) -> dict:
        def go():
            z = self._rechen.zustand()
            heute, gesamt = z.get("heute") or {}, z.get("gesamt") or {}
            netz = None
            try:
                netz = (self._community.rechenstand().get("bilanz") or {}) if self._community.geraet() is not None else None
            except app_core.AppError:
                netz = None
            satz = tagesbilanz_satz(heute)
            vorher = vorher_satz(z.get("vorher"))
            rang, teams, team_name = None, None, ""
            if self._community.geraet() is not None:
                try:
                    rang = self._community.rangliste()
                    teams = self._community.team_rangliste()
                    team_name = next((str(r.get("name", "")) for r in (teams or {}).get("zeilen", []) if r.get("dein_team")), "")
                except app_core.AppError:
                    pass
            platz = platz_satz(rang, teams, team_name)
            nacht_roh = self._ki.einstellung().get("pruefstand_nacht")
            zahlen = tagesbericht_zahlen(rang, teams, team_name, nacht_roh)
            out = {"geraet": {"heute": heute, "gesamt": gesamt, "satz": satz, "vorher": vorher, "platz": platz,
                              "nacht": nacht_satz(nacht_roh), "zahlen": zahlen},
                   "netz": netz, "hinweis": ""}
            bericht = vorher or satz
            if hinweis and bericht:
                tag = datetime.now().strftime("%Y-%m-%d")
                if self._ki.einstellung().get("bilanz_gezeigt") != tag:
                    self._ki.einstellung_setzen(bilanz_gezeigt=tag)
                    vorne = f"Dein Tagesbericht: {bericht}"
                    out["hinweis"] = f"{vorne} {platz}" if platz else vorne
            return out
        return self._guarded("tagesbilanz", go)

    def nachschauen_setzen(self, an: bool) -> dict:
        def go():
            self._ki.einstellung_setzen(nachschauen=bool(an))
            return {"nachschauen": self.nachschauen_an()}
        return self._guarded("nachschauen_setzen", go, "Nachschauen im Internet ist eingeschaltet: Wetter, Schlagzeilen und, wenn die Community nichts weiß, eine Suche." if an
                             else "Nachschauen im Internet ist ausgeschaltet. KIplatz antwortet nur aus dem Wissensspeicher und aus sich selbst.")

    def _live_merken(self, q: wissen.Quelle, text: str) -> None:
        if not getattr(_EIGEN, "an", True):
            return
        try:
            self._wissen.hinzufuegen("nachgeschaut", q.titel, q.adresse, text, gueltig_bis=nachschauen.gueltig_bis("suche", datetime.now(timezone.utc)))
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT live_merken: {exc.code}: {exc.detail}")

    class _AntwortMitQuellen:
        def __init__(self, a, quellen, im_speicher):
            self.text, self.prompt_tokens, self.completion_tokens, self.dauer_s = a.text, a.prompt_tokens, a.completion_tokens, a.dauer_s
            self.quellen, self.im_speicher = quellen, im_speicher

    def _dienst_frage(self, nachrichten: list[dict], on_token):
        if not self._ki.server.laeuft():
            raise app_core.AppError("KI_AUS", "KIplatz ist auf diesem Gerät gerade ausgeschaltet")
        _EIGEN.an = False
        zusatz, quellen, im_speicher, _hinweis = self._mit_wissen(nachrichten, privat_erlaubt=False)
        a = self._ki.server.frage(nachrichten, on_token=on_token, zusatz=zusatz)
        return Api._AntwortMitQuellen(a, quellen, im_speicher)


    def _antwort_fuer_mitglied(self, nachrichten: list[dict], auszuege: list[dict], fuer: str, *, frisch: bool = False, teil_melden=None, schritt_melden=None,
                               skill: dict | None = None, zuhause: dict | None = None, fenster: dict | None = None,
                               fachgebiete: list | None = None, messen: bool = False, zone: int | None = None) -> tuple[str, dict]:
        ki_laufzeit.zone_setzen(zone)
        vorher = getattr(_SCHRITT, "fn", None)
        lauf_vorher = getattr(_SUCHLAUF, "stand", None)
        _SCHRITT.fn = schritt_melden
        _SUCHLAUF.stand = {"runde": 0, "gesucht": [], "gelesen": set()}
        _FREMD.texte = []
        _FACH.wert = wissen.fachgebiete_pruefen(fachgebiete)
        privat: bool | str = False
        daheim = ""
        if fenster is not None:
            ok, name = self._fenster.gilt(fenster)
            if not ok:
                _SCHRITT.fn, _SUCHLAUF.stand = vorher, lauf_vorher
                _log(self._core, f"ABGELEHNT fenster: {name}")
                raise app_core.AppError("FENSTER_AUS", "das Frag-Fenster ist an diesem PC aus oder nicht dieses")
            _FENSTERFRAGE.an = True
            try:
                self._fenster.aktualisieren()
            except Exception as exc:
                _log(self._core, f"FEHLER fenster aktualisieren: {type(exc).__name__}")
            auszuege, privat, fuer, frisch, zuhause = [], wissen.FENSTER, "Besucher im Frag-Fenster", False, None
            skill = fragfenster.als_skill(name)
        if zuhause is not None:
            ok, grund = self._zuhause.pruefen(zuhause)
            _NETZ.an = zuhause.get("modus") == "netz"
            if ok and zuhause.get("modus") == "holen":
                try:
                    return self._dateien_holen(zuhause)
                finally:
                    _SCHRITT.fn, _SUCHLAUF.stand = vorher, lauf_vorher
            if ok and not zuhause.get("modus") and _dateifrage(suchfrage(zuhause["nachrichten"])):
                _SCHRITT.fn, _SUCHLAUF.stand = vorher, lauf_vorher
                return DATEI_HAKEN, {**self._schein_ohne_modell("nachgefragt"), "zuhause": "mit_unterlagen"}
            if ok and zuhause.get("modus") == "dateien":
                try:
                    return self._dateien_antwort(suchfrage(zuhause["nachrichten"]))
                finally:
                    _SCHRITT.fn, _SUCHLAUF.stand = vorher, lauf_vorher
            if not ok and zuhause.get("modus") in ("dateien", "holen"):
                _SCHRITT.fn, _SUCHLAUF.stand = vorher, lauf_vorher
                _log(self._core, f"ABGELEHNT zuhause dateien: {grund}")
                return DATEI_NICHT_GEKOPPELT, {**self._schein_ohne_modell("nachgesehen"), "zuhause": "ohne_unterlagen"}
            if ok:
                nachrichten = vermittlung_basis._nachrichten_pruefen(zuhause["nachrichten"], maskieren=False)
                skill = zuhause.get("skill") if isinstance(zuhause.get("skill"), dict) else None
                auszuege, privat, fuer, daheim = [], wissen.HAUSHALT, "dein Handy", "mit_unterlagen"
            else:
                daheim = "ohne_unterlagen"
                _log(self._core, f"ABGELEHNT zuhause: {grund}; wie für ein fremdes Gerät beantwortet")
        try:
            englisch = None
            ab0 = absicht.letzte(nachrichten)
            _ABSICHT.wert = ab0
            en_frage = antwortsprache.frage_sprache(antwortsprache.letzte_frage(nachrichten)) == "en"
            laeuft = self._ki.server.laeuft()
            vorab = self._antwort_vorab(nachrichten, ab=ab0, en_frage=en_frage, krisenhilfe_an=fenster is None,
                                        waehrung=not skill and not zuhause and laeuft, bezug_an=not skill and not zuhause and not fenster and not auszuege,
                                        uebersetzen=laeuft)
            if vorab is not None:
                text_v, gemacht_v, woher_v, en_v = vorab
                schein = {**self._schein_ohne_modell(gemacht_v), "quellen": woher_v,
                          "geraet": "ein PC der Community" if gemacht_v == krisenhilfe.GEMACHT else f"{self._geraet_name} (Community) für {fuer}"}
                if en_frage and en_v:
                    return en_v, schein
                if en_frage and laeuft:
                    self._schritt("schreibt die Antwort auf Englisch …")
                    return antwortsprache.antwort_uebersetzen(self._ki.server.frage, text_v, schein, teil_melden, log=lambda z: _log(self._core, z))
                return text_v, schein
            if en_frage and not ab0.antwort and self._ki.server.laeuft():
                self._schritt("liest die Frage …")
                try:
                    englisch = antwortsprache.frage_auf_deutsch(self._ki.server.frage, nachrichten)
                except Exception as exc:
                    _log(self._core, f"FEHLER frage_auf_deutsch: {type(exc).__name__}")
                if englisch:
                    ki_laufzeit.original_setzen(antwortsprache.letzte_frage(nachrichten))
            text, schein = self._antwort_fuer_mitglied_ohne_schritt(englisch or nachrichten, auszuege, fuer, frisch=frisch,
                                                                    teil_melden=None if englisch else teil_melden, skill=skill, privat=privat,
                                                                    messen=messen)
            en_fertig = str(schein.pop("_en", "") or "")
            if en_frage and en_fertig:
                text = en_fertig
            elif englisch:
                self._schritt("schreibt die Antwort auf Englisch …")
                text, schein = antwortsprache.antwort_uebersetzen(self._ki.server.frage, text, schein, teil_melden, log=lambda z: _log(self._core, z),
                                                                  frage=antwortsprache.letzte_frage(nachrichten))
                text, schein = self.eigene_worte_englisch(text, schein)
            if daheim:
                schein = {**schein, "zuhause": daheim}
                if daheim == "mit_unterlagen":
                    schein["geraet"] = "dein PC daheim, mit deinen Unterlagen"
            return text, schein
        finally:
            _SCHRITT.fn = vorher
            ki_laufzeit.original_setzen("")
            ki_laufzeit.zone_setzen(None)
            _SUCHLAUF.stand = lauf_vorher
            _NETZ.an = False
            _FENSTERFRAGE.an = False
            _ABSICHT.wert = None
            _FACH.wert = None

    def _fertig_aus_kopie(self, nachrichten: list[dict], *, fuer_andere: bool = False) -> tuple[str, dict] | None:
        if self._spiegel is None:
            return None
        try:
            e = self._spiegel.antwort(nachrichten)
        except Exception as exc:
            _log(self._core, f"FEHLER antwort aus der Kopie: {type(exc).__name__}")
            return None
        if e is None or not hausordnung.pruefen(e["text"]).ok:
            return None
        if not antwortspeicher_basis.ausliefern_ok(e.get("lieferschein"), e.get("text")):
            return None
        ls = dict(e["lieferschein"])
        ls["aus_speicher"] = {"erarbeitet": time.strftime("%Y-%m-%d", time.localtime(e["angelegt"])) if e["angelegt"] else "", "von": e["von"]}
        ls["speicher_id"] = e["kennung"]
        ls["dauer_s"] = 0.0
        ls["quellen"] = (str(ls.get("quellen") or "").rstrip() + " " + (
            "Diese Antwort hat ein PC der Community schon einmal geprüft erarbeitet; sie kam fertig aus dem Antwort-Speicher, aus der Kopie "
            "auf dem PC, der geantwortet hat." if fuer_andere else
            "Diese Antwort hat ein PC der Community schon einmal geprüft erarbeitet; sie kam fertig aus dem Antwort-Speicher, aus der Kopie "
            "auf diesem PC.")).strip()
        _log(self._core, "OK antwort aus der Kopie des Antwort-Speichers, ohne Modell")
        return e["text"], ls

    def _antwort_fuer_mitglied_ohne_schritt(self, nachrichten: list[dict], auszuege: list[dict], fuer: str, *, frisch: bool = False, teil_melden=None,
                                            skill: dict | None = None, privat: bool | str = False, messen: bool = False) -> tuple[str, dict]:
        if not (self._ki.quelle() == "lokal" and self._ki.server.laeuft()):
            raise app_core.AppError("KI_AUS", "KIplatz ist auf diesem Gerät gerade ausgeschaltet")
        _EIGEN.an = bool(privat)
        ab = _absicht_von(nachrichten)
        frisch = frisch or ab.frisch
        mit_skill = None
        if skill:
            try:
                mit_skill = skills.lesen(str(skill.get("text", "")), quelle="platzl")
            except app_core.AppError as exc:
                raise app_core.AppError("SKILL", f"der mitgebrachte Skill ist nicht lesbar: {exc.detail}") from exc
        if not ab.antwort and _dateifrage(suchfrage(nachrichten)) and privat != wissen.FENSTER:
            gefunden = self._wissen.suchen(suchfrage(nachrichten), privat_erlaubt=privat) if privat else []
            if not gefunden:
                satz = (DATEI_NICHTS_DAHEIM if privat else DATEI_NUR_DAHEIM)
                return satz, {"modell": "ohne Modell", "geraet": f"{self._geraet_name} (Community) für {fuer}", "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
                              "quellen": "Frage nach einer eigenen Datei: nicht im Internet gesucht.", "quellen_liste": [], "gemacht": "nachgesehen",
                              "erfunden": "nichts", "pruefung": pruefung.pruefen("", []).kurz()}
        text, lieferschein, _a = self._antwort_kern(
            nachrichten, ab=ab, fuer=fuer, frisch=frisch, privat=privat, messen=messen,
            kopie=None if (skill or privat) else "andere",
            vorspann=skills.vorspann(mit_skill) if mit_skill is not None else "",
            vorspann_hinweis=f"Skill „{mit_skill.name}“ angewendet." if mit_skill is not None else "",
            strom=_Teilgeber(teil_melden) if teil_melden is not None else None, skill_name=mit_skill.name if mit_skill is not None else None)
        return text, lieferschein


    def _antwort_vorab(self, nachrichten: list[dict], *, ab, en_frage: bool, krisenhilfe_an: bool = True, waehrung: bool = True,
                       bezug_an: bool = True, uebersetzen: bool = True) -> tuple[str, str, str, str] | None:
        frage = antwortsprache.letzte_frage(nachrichten)
        if krisenhilfe_an:
            kh = krisenhilfe.antwort(frage)
            if kh is not None:
                _log(self._core, "OK antwort: Krisenhilfe, ohne Modell")
                return kh, krisenhilfe.GEMACHT, krisenhilfe.WOHER, krisenhilfe.TEXT_EN
        if ab.antwort:
            return None
        vorige = next((str(n.get("content") or "") for n in reversed(nachrichten[:-1]) if n.get("role") == "assistant"), "")
        if uebersetzen and en_frage and ab.art == "sprache" and ab.sprache == "en" and vorige.strip():
            return ohne_auszuege(ohne_markdown(vorige)), "übersetzt", "die vorige Antwort, ins Englische übertragen.", ""
        if waehrung:
            kw = self._waehrung_antwort(frage)
            if kw is not None:
                return kw.de, "gerechnet", "Referenzkurs der Europäischen Zentralbank (EZB), vom Programm selbst gerechnet.", kw.en
        if bezug_an:
            bz = bezug.rueckfrage(nachrichten)
            if bz:
                return bz, "nachgefragt", "keine Quelle nötig, das Programm fragt nach.", bezug.ANTWORT_EN
        return None

    def _antwort_kern(self, nachrichten: list[dict], *, ab, fuer: str, frisch: bool = False, privat: bool | str = True, fern: bool = False,
                      messen: bool = False, kopie: str | None = None, vorspann: str = "", vorspann_hinweis: str = "",
                      modell_nachrichten: list[dict] | None = None, strom=None, melden=None, knapp: bool = False, max_tokens: int | None = None,
                      kurz: bool = False, prozessor_rueckfall: bool = False, knopf: bool = False, nachsuche_erlaubt: bool = True,
                      skill_name: str | None = None, geraet: str | None = None) -> tuple[str, dict, "ki_laufzeit.Antwort | None"]:
        melden = melden or self._schritt
        strom = strom if strom is not None else _Still()
        modell_nachrichten = modell_nachrichten if modell_nachrichten is not None else nachrichten
        geraet = geraet or f"{self._geraet_name} (Community) für {fuer}"
        if ab.antwort:
            return ab.antwort, {"modell": f"{ab.gemacht}, ohne Modell", "geraet": geraet, "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
                                "quellen": "keine Quelle nötig, das Programm antwortet selbst.", "quellen_liste": [],
                                "gemacht": ab.gemacht, "erfunden": "nichts, ohne Modell",
                                "pruefung": pruefung.pruefen("", []).kurz(), "_en": ab.antwort_en or ""}, None
        ohne_suche = absicht.ohne_suche(ab) and not fern
        a4 = nachschauen.erkennen_im_gespraech(nachrichten) if (not fern and self.nachschauen_an()) else None
        if a4 is not None and a4.rueckfrage:
            return a4.rueckfrage, {"modell": "nachgefragt, ohne Modell", "geraet": geraet, "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
                                   "quellen": "keine Quelle nötig, das Programm fragt nach.", "quellen_liste": [], "gemacht": "nachgefragt",
                                   "erfunden": "nichts, es wurde nur nachgefragt", "pruefung": pruefung.pruefen("", []).kurz(), "_en": ""}, None
        if kopie and not (messen or frisch):
            fertig = self._fertig_aus_kopie(nachrichten, fuer_andere=(kopie == "andere"))
            if fertig is not None:
                fertig[1]["geraet"] = (f"{self._geraet_name} (Community) für {fuer}, aus dem Antwort-Speicher" if kopie == "andere"
                                       else "aus dem Antwort-Speicher der Community (Kopie auf diesem PC)")
                return fertig[0], fertig[1], None
        if callable(vorspann):
            vorspann, vorspann_hinweis, mn = vorspann()
            if mn is not None:
                modell_nachrichten = mn
        lauf = getattr(_SUCHLAUF, "stand", None)
        wahl = self._ki.wahl
        schrift = None if (fern or ab.frisch or ohne_suche) else schriftstueck.runde(nachrichten)
        klein = False
        if schrift is not None and not schrift[0].offen:
            aufgabe, runde = schrift
            zusatz = (wissen.datum_zeile() + "\n\n" + (schriftstueck.vorspann_fragen(aufgabe) if runde == "fragen" else schriftstueck.vorspann_schreiben(aufgabe))
                      + "\n\n" + wissen.uhrzeit_zeile())
            quellen, im_speicher, hinweis, quellen_stand = [], 0, f"Schriftstück ({aufgabe.art}), Runde: {'Rückfragen' if runde == 'fragen' else 'Schreiben'}; der Wissensspeicher wurde dafür nicht durchsucht.", None
        elif schrift is not None:
            aufgabe, runde = schrift
            zusatz, quellen, im_speicher, hinweis = self._mit_wissen(nachrichten, privat_erlaubt=privat, frisch=frisch, knapp=knapp)
            quellen_stand = self._letzter_stand
            zusatz = (schriftstueck.vorspann_fragen(aufgabe) if runde == "fragen" else schriftstueck.vorspann_schreiben(aufgabe)) + ("\n\n" + zusatz if zusatz else "")
            hinweis = (hinweis + " " if hinweis else "") + ("Vorhaben: die KI prüft zuerst, ob dir etwas Wichtiges fehlt." if runde == "fragen" else "Vorhaben, zweite Runde nach den Rückfragen.")
        elif ohne_suche:
            zusatz, quellen, im_speicher, hinweis, quellen_stand = wissen.datum_zeile(), [], 0, KEINE_NEUE_SUCHE, None
            _suchrunden_aufbrauchen()
        else:
            klein = not frisch and not fern and self.nachschauen_an() and klein_wissensfrage(wahl.modell.name if wahl else "", suchfrage(nachrichten))
            zusatz, quellen, im_speicher, hinweis = ("", [], 0, "") if fern else self._mit_wissen(nachrichten, privat_erlaubt=privat, frisch=frisch or klein, knapp=knapp)
            quellen_stand = None if fern else self._letzter_stand
            if klein:
                hinweis = (KLEIN_HINWEIS + " " + hinweis).strip()
            if knopf and not fern and quellen_stand is None and "live gelesen" not in hinweis:
                grund = next((s for s in hinweis.split(". ") if "nicht geklappt" in s or "ließ sich nicht" in s), "").strip().rstrip(".")
                raise app_core.AppError("NACHPRUEFEN_LEER", (grund or "im Netz war zu dieser Frage nichts zu finden") + "; die Antwort oben bleibt")
        if vorspann:
            zusatz = vorspann + ("\n\n" + zusatz if zusatz else "")
        if vorspann_hinweis:
            hinweis = (hinweis + " " if hinweis else "") + vorspann_hinweis

        def modell(zusatz_: str, on_token, *, max_tokens_: int | None = None):
            return self._ki.frage(modell_nachrichten, on_token=on_token, zusatz=zusatz_, max_tokens=max_tokens_ or max_tokens, kurz=kurz)

        self._schritt("schreibt die Antwort …")
        zusatz = mit_auftrag(mit_fokus(zusatz, suchfrage(modell_nachrichten)), modell_nachrichten)
        try:
            a = modell(zusatz, strom.token)
        except app_core.AppError as exc:
            if not prozessor_rueckfall or exc.code != "KI_ANTWORT" or fern or self.abbruch_gewuenscht or not self._ki.auf_prozessor_wechseln():
                raise
            _log(self._core, f"INFO prozessor statt grafikkarte: {exc.detail}")
            melden("Das Modell ist auf der Grafikkarte gestolpert; es startet auf dem Prozessor neu …")
            self._ki_bereit_machen(einschalten=True)
            wahl = self._ki.wahl
            kurz, max_tokens = True, 320
            a = modell(zusatz, strom.token)
            hinweis = (hinweis + " " if hinweis else "") + f"Die Grafikkarte hat versagt ({exc.detail}); die Antwort kam vom Prozessor."
        strom.schluss()
        if getattr(a, "gekuerzt", False):
            hinweis = (hinweis + " " if hinweis else "") + GEKUERZT_HINWEIS
        nachgeholt = False

        def nachsuchen(satz: str, grund: str) -> bool:
            nonlocal a, zusatz, quellen, im_speicher, hinweis, quellen_stand, nachgeholt
            lauf["runde"] += 1
            melden(satz)
            try:
                zusatz2, quellen2, im_speicher2, hinweis2 = self._mit_wissen(nachrichten, privat_erlaubt=privat, frisch=True)
                if not any(q.get("art") == "nachgeschaut" for q in quellen2):
                    return False
                if vorspann:
                    zusatz2 = vorspann + ("\n\n" + zusatz2 if zusatz2 else "")
                zusatz2 = (zusatz2 + "\n\n" if zusatz2 else "") + frage_fokus(suchfrage(nachrichten))
                self._schritt("schreibt die Antwort mit dem, was es gefunden hat …")
                r = strom.runde()
                a2 = modell(zusatz2, r.token)
                r.schluss()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT nachgeholt: {exc.code}: {exc.detail}")
                return False
            a, zusatz, quellen, im_speicher, quellen_stand, nachgeholt = a2, zusatz2, quellen2, im_speicher2, self._letzter_stand, True
            hinweis = (grund + " " + hinweis2 + (" " + vorspann_hinweis if vorspann_hinweis else "")
                       + (" " + GEKUERZT_HINWEIS if getattr(a2, "gekuerzt", False) else "")).strip()
            strom.neu()
            return True

        while (schrift is None and not frisch and not fern and self.nachschauen_an() and _WEISS_NICHT.search(ohne_markdown(a.text) or "")
               and lauf and lauf["runde"] < SUCHRUNDEN - 1):
            if not nachsuchen("Das weiß ich noch nicht, ich suche danach …" if lauf["runde"] == 0 else "Noch nicht gefunden, ich suche mit anderen Wörtern …",
                              "Das Modell kannte es nicht, darum wurde im Internet nachgeschaut."):
                break
        if getattr(a, "abgebrochen", False):
            hinweis = (hinweis + " " if hinweis else "") + "Auf deinen Wunsch gestoppt; das ist der Teil der Antwort bis dahin."
        if fern:
            quellen, im_speicher = list(getattr(a, "quellen", ()) or ()), int(getattr(a, "im_speicher", 0) or 0)
        self._schritt("prüft die Antwort gegen die Quellen …")
        pr = pruefung.pruefen(a.text or "", [(int(q["nummer"]), str(q.get("text", ""))) for q in quellen if q.get("text")])
        if klein and not getattr(a, "abgebrochen", False) and pr.gruen == 0 and not _WEISS_NICHT.search(ohne_markdown(a.text or "")):
            a = dataclasses.replace(a, text=_GESUCHT_NICHTS_SATZ)
            pr = pruefung.pruefen(a.text, [])
            strom.neu()
        verworfen = False
        if not fern and erfunden_verdacht(pr, quellen, schrift, suchfrage(nachrichten)):
            melden("Die erste Antwort enthielt Erfundenes; KIplatz antwortet noch einmal, kurz und ehrlich …")
            try:
                a = modell(zusatz + "\n\n" + ERFUNDEN_ZUSATZ, None, max_tokens_=160)
                pr = pruefung.pruefen(a.text or "", [(int(q["nummer"]), str(q.get("text", ""))) for q in quellen if q.get("text")])
                hinweis = (hinweis + " " if hinweis else "") + "Die erste Fassung enthielt Erfundenes und wurde verworfen."
                verworfen = True
                strom.neu()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT erfunden_nachfrage: {exc.code}: {exc.detail}")
        if (verworfen and schrift is None and not frisch and not fern and not nachgeholt and self.nachschauen_an()
                and _WEISS_NICHT.search(ohne_markdown(a.text) or "") and lauf and lauf["runde"] < SUCHRUNDEN - 1):
            if nachsuchen("Die erste Fassung passte nicht zu den Quellen, ich suche im Internet …",
                          "Die erste Fassung passte nicht zu den Quellen, darum wurde im Internet nachgeschaut."):
                self._schritt("prüft die Antwort gegen die Quellen …")
                pr = pruefung.pruefen(a.text or "", [(int(q["nummer"]), str(q.get("text", ""))) for q in quellen if q.get("text")])

        def fertig_machen():
            lieferschein = {
                "modell": "KIplatz" if fern else (wahl.modell.name if wahl else "KIplatz"), "geraet": geraet,
                "bau": app_core.APP_BUILD,
                "fassung": None if fern else self._ki.fassung,
                "dauer_s": a.dauer_s, "wortstuecke": a.completion_tokens, "gelesen": a.prompt_tokens,
                "quellen": wissen.quellen_text_de(a.text or "", quellen, im_speicher, auch_nummern={s.quelle for s in pr.saetze if s.farbe == "gruen" and s.quelle}) + (f" {hinweis}" if hinweis else ""),
                "quellen_liste": wissen.benutzte_quellen(a.text or "", quellen, {s.quelle for s in pr.saetze if s.farbe == "gruen" and s.quelle}),
                "gemacht": "live nachgeprüft" if frisch else ("nachgeschaut und geantwortet" if nachgeholt else "geantwortet"), "erfunden": pr.text, "pruefung": pr.kurz(),
            }
            if verworfen:
                lieferschein["erste_fassung"] = "nachgeschaut" if nachgeholt else "verworfen"
            if quellen_stand:
                lieferschein["stand"] = quellen_stand
            if skill_name:
                lieferschein["skill"] = skill_name
            antwort_text = ohne_auszuege(ohne_markdown(a.text)) or "(keine Antwort erhalten)"
            vorher_text = antwort_text
            antwort_text = self._belege_nachher(antwort_text, suchfrage(nachrichten), "" if fern else zusatz, [] if fern else quellen, lieferschein,
                                                None if fern else (lambda extra: modell(zusatz + "\n\n" + extra, None, max_tokens_=240).text),
                                                schreiben=schrift is not None, ampel=not fern)
            if antwort_text != vorher_text:
                strom.neu()
            return antwort_text, vorher_text, lieferschein

        antwort_text, vorher_text, lieferschein = fertig_machen()
        if (schrift is None and not frisch and not fern and nachsuche_erlaubt and self.nachschauen_an() and lauf and lauf["runde"] < SUCHRUNDEN - 1
                and _WEISS_NICHT.search(antwort_text) and (not im_netz_gesucht(nachgeholt, quellen, lauf) or lauf.get("nur_regel"))):
            if nachsuchen("Das weiß ich noch nicht sicher, ich suche im Internet …",
                          "Die Angabe stand in keiner Fundstelle, darum wurde im Internet nachgeschaut."):
                self._schritt("prüft die Antwort gegen die Quellen …")
                pr = pruefung.pruefen(a.text or "", [(int(q["nummer"]), str(q.get("text", ""))) for q in quellen if q.get("text")])
                antwort_text, vorher_text, lieferschein = fertig_machen()
        if nebenher_satz(lauf):
            lieferschein["quellen"] = (lieferschein.get("quellen", "") + " " + nebenher_satz(lauf)).strip()
        if schrift is not None:
            antwort_text, lieferschein["gemacht"] = _schriftstueck_nachbearbeiten(antwort_text, schrift[1], lieferschein, schrift[0])
        elif not frisch and not fern and self.nachschauen_an() and _WEISS_NICHT.search(antwort_text):
            antwort_text = _weiss_nicht_anwenden(antwort_text, lieferschein, gesucht=im_netz_gesucht(nachgeholt, quellen, lauf), vorher=vorher_text)
        _woertlich_markieren(antwort_text, quellen, lieferschein)
        weg = getattr(_MESSWEG, "d", None)
        if isinstance(weg, dict):
            weg.update(stellen=sum(1 for q in quellen if q.get("text")), arten=sorted({str(q.get("art") or "") for q in quellen if q.get("text")}),
                       suchanfragen=len(lauf["gesucht"]) if lauf else 0, suchrunden=int(lauf["runde"]) if lauf else 0,
                       im_netz=im_netz_gesucht(nachgeholt, quellen, lauf))
        return antwort_text, lieferschein, a

    def _wiki_darf(self) -> bool:
        if self._core.run_state() is not node_local_state.RunState.ACTIVE or not rechenarbeit.am_strom_windows():
            return False
        try:
            leer = rechenarbeit.node_idle_detector.get_idle_seconds()
        except Exception:
            return False
        return leer is not None and leer >= rechenarbeit.LEERLAUF_S

    def _wiki_karte_frei(self) -> bool:
        if getattr(self._rechen, "wiki_ruht", False):
            return False
        return not self._rechen.vorrang_aktiv() and self._rechen.phase not in ("antwortet", "laden", "hitze", "rechnet", "startet", "fehler", "arbeitsspeicher", "am_geraet")

    def _arbeit_text(self) -> str:
        t = self._rechen.text_de()
        try:
            w = self._wiki.text_de()
        except Exception:
            w = ""
        return t + ("\n" + w if w else "")

    def _beleg_pruefer(self):
        wahl = self._ki.wahl
        if self._ki.quelle() != "lokal" or not self._ki.bereit() or wahl is None or wahl.modell.kennung not in PRUEFER_MODELLE:
            return None

        def pruefen(zusatz: str, woerter: list[str]) -> set[int]:
            self._schritt("prüft Zahlen, Daten und Namen gegen die Quellen …")
            a = self._ki.server.frage([{"role": "user", "content": belege.PRUEFER_SYSTEM + "\n\n" + belege.pruefer_auftrag(woerter)}], zusatz=zusatz,
                                      max_tokens=8 * len(woerter) + 16, temperature=0.0, art="pruefer")
            return belege.urteil_lesen(a.text, len(woerter))
        return pruefen

    def _umschreiber(self):
        if self._ki.quelle() != "lokal" or not self._ki.bereit():
            return None

        def umschreiben(saetze: list[str], englisch: bool) -> dict[int, str]:
            self._schritt("schreibt übernommene Sätze in eigenen Worten …")
            auftrag = "\n".join(f"{i + 1}. {' '.join(s.split())}" for i, s in enumerate(saetze))
            a = self._ki.server.frage([{"role": "user", "content": (belege.UMSCHREIBEN_EN if englisch else belege.UMSCHREIBEN_DE) + "\n\n" + auftrag}],
                                      max_tokens=80 * len(saetze) + 32, temperature=0.3, art="eigen")
            return umschreibung_lesen(a.text, len(saetze))
        return umschreiben

    def eigene_worte_englisch(self, text: str, schein: dict) -> tuple[str, dict]:
        neu, notizen, ersetzt = eigene_worte(text, list(getattr(_FREMD, "texte", None) or []), self._umschreiber(), englisch=True)
        if neu == text:
            return text, schein
        schein = dict(schein)
        schein["belege"] = list(schein.get("belege") or []) + notizen
        pr = schein.get("pruefung") if isinstance(schein.get("pruefung"), dict) else None
        if pr and isinstance(pr.get("saetze"), list):
            saetze = []
            for s in pr["saetze"]:
                t = ersetzt.get(str(s.get("text", "")), str(s.get("text", ""))) if isinstance(s, dict) else ""
                if t and t in neu:
                    saetze.append({**s, "text": t})
            schein["pruefung"] = {**pr, "saetze": saetze}
        _log(self._core, "INFO belege englisch: " + " ".join(notizen))
        return neu, schein

    def _belege_nachher(self, text: str, frage: str, zusatz: str, quellen: list[dict], lieferschein: dict, nochmal, *, schreiben: bool = False,
                        ampel: bool = True) -> str:
        def neu(extra: str) -> str:
            self._schritt("prüft Zahlen, Daten und Namen nach und antwortet genauer …")
            return ohne_auszuege(ohne_markdown(nochmal(extra)))
        pruefer = self._beleg_pruefer()

        def pruefer_mit_schritt(z, saetze):
            self._schritt("lässt das Modell zweifelhafte Sätze noch einmal prüfen …")
            return pruefer(z, saetze)
        bekannt = getattr(self._wiki, "namen_bekannt", None)
        bew = getattr(self, "_bewertung", None)

        def richter(satz: str, texte: list[str]) -> float | None:
            vorrang = getattr(getattr(self, "_rechen", None), "vorrang", None)
            if bew is None or not texte or not bew.server.laeuft() or (isinstance(vorrang, threading.Event) and vorrang.is_set()):
                return None
            je_quelle = [richter_stuecke(str(t)) for t in texte]
            stuecke = [s for reihe in itertools.zip_longest(*je_quelle) for s in reihe if s][:bewertung.MAX_KANDIDATEN]
            t0 = time.monotonic()
            try:
                werte = bew.server.bewerten("Stützt der Text diese Aussage? " + " ".join(satz.split())[:600], stuecke,
                                            timeout_s=bewertung.TIMEOUT_S)
            finally:
                _SCHATTEN.zeit = float(getattr(_SCHATTEN, "zeit", 0.0) or 0.0) + time.monotonic() - t0
            return round(max(werte), 2) if werte else None
        _FREMD.texte = belege.fremde_texte(quellen)
        neu_text, notizen = belege_anwenden(text, frage, zusatz, quellen, nochmal=neu if nochmal is not None else None,
                                            pruefer=pruefer_mit_schritt if pruefer is not None else None, schreiben=schreiben, bekannt=bekannt,
                                            umschreiben=self._umschreiber() if nochmal is not None else None,
                                            richter=richter if not schreiben else None)
        if notizen:
            _log(self._core, "INFO belege: " + " ".join(notizen))
            lieferschein["belege"] = notizen
            lieferschein["quellen"] = (lieferschein.get("quellen", "") + " " + " ".join(notizen)).strip()
        if ampel or neu_text != text:
            pr = pruefung.pruefen(neu_text, [(int(q["nummer"]), str(q.get("text", ""))) for q in quellen if q.get("text")])
            lieferschein["pruefung"], lieferschein["erfunden"] = pr.kurz(), pr.text
        return neu_text

    def _unbekannte_namen(self, frage: str) -> list[str]:
        if not frage or _dateifrage(frage) or not suche_denkbar(frage):
            return []
        t = time.time()
        try:
            return list(getattr(self._wiki, "unbekannte_namen", lambda t: [])(frage) or [])
        except Exception as exc:
            _log(self._core, f"FEHLER unbekannte namen: {type(exc).__name__}")
            return []
        finally:
            if time.time() - t > 2.0:
                _log(self._core, f"LANGSAM unbekannte namen: {time.time() - t:.1f} s")

    def _kann_fuer_andere_antworten(self) -> bool:
        return self._ki.quelle() == "lokal" and not self._schwach() and self._ki.eingerichtet()

    def _warm_darf(self) -> bool:
        if self._core.run_state() is not node_local_state.RunState.ACTIVE or not self._kann_fuer_andere_antworten():
            return False
        vorrang = getattr(self._rechen, "vorrang_aktiv", None)
        if vorrang is not None and vorrang():
            return False
        return getattr(self._rechen, "phase", "") not in ("aus", "akku", "hitze", "laden", "startet", "fehler", "nicht_angemeldet", "ruht", "antwortet", "trainiert")

    def _ki_starten_blockierend(self) -> None:
        if self._ki.quelle() != "lokal":
            raise app_core.AppError("KI_QUELLE", "dieses Gerät fragt selbst ein anderes Gerät; es kann nicht für andere antworten")
        self._ki_bereit_machen(einschalten=True)

    def _ki_ende_grund(self) -> str:
        try:
            proc = getattr(self._ki.server, "proc", None)
            code = proc.poll() if proc is not None else None
            zeilen = [z.strip() for z in str(self._ki.server.log_ende() or "").splitlines() if z.strip()]
        except Exception:
            return ""
        wichtig = [z for z in zeilen if re.search(r"(?i)error|fail|abort|out of memory|device lost|exception|vk_|terminat", z)] or zeilen
        teile = ([f"Endcode {code}"] if code is not None else []) + ([" | ".join(z[:160] for z in wichtig[-3:])] if wichtig else [])
        return f" ({'; '.join(teile)})" if teile else ""

    def _ki_entladen(self) -> None:
        self._ki.ausschalten()
        self._bedeutung.ausschalten()
        self._bewertung.ausschalten()

    def _schwach(self) -> bool:
        first = self._core.load_first_start()
        return first is not None and first.role is not app_core.Role.COMPUTE_STRONG

    def fragt_community(self) -> bool:
        if self._ki.quelle() != "lokal" or self._community.geraet() is None:
            return False
        if getattr(self._ki, "probe_geladen", False) or getattr(self._ki, "gesperrt", ""):
            return True
        e = self._ki.einstellung().get("fragt_community")
        if e in (True, False):
            return bool(e)
        return self._schwach() or self._besseres_modell_da()

    def _besseres_modell_da(self) -> bool:
        jetzt = time.time()
        if not self._staerkste or jetzt - self._staerkste[0] > 60:
            try:
                wert = float(((self._community.rechenstand() or {}).get("fragen") or {}).get("staerkste_stufe", 0) or 0)
            except (app_core.AppError, ValueError, TypeError, AttributeError):
                wert = 0.0
            self._staerkste = (jetzt, wert)
        bereit = getattr(self._ki, "bereit", lambda: True)()
        eigen = modell_stufe(self._ki.wahl.modell.name) if (self._ki.wahl and bereit) else 0.0
        return self._staerkste[1] > eigen

    def fragen_immer(self) -> bool:
        e = self._ki.einstellung().get("fragen_immer")
        if e in (True, False):
            return bool(e)
        first = self._core.load_first_start()
        return first is not None and first.role is app_core.Role.COMPUTE_STRONG

    def fragen_immer_setzen(self, an: bool) -> dict:
        def go():
            self._ki.einstellung_setzen(fragen_immer=bool(an))
            return {"fragen_immer": self.fragen_immer()}
        return self._guarded("fragen_immer_setzen", go, "Fragen anderer Mitglieder beantwortet dein Rechner ab jetzt auch, während du daran arbeitest (dauert Sekunden)." if an
                             else "Fragen anderer Mitglieder beantwortet dein Rechner nur noch, wenn du gerade nicht daran bist.")

    def weitergeben_setzen(self, an: bool) -> dict:
        def go():
            self._weitergeber.setzen(bool(an))
            return self._zustand()
        return self._guarded("weitergeben_setzen", go, "Dein PC gibt Modelle an andere Mitglieder weiter, solange er Rechenkraft teilt." if an
                             else "Dein PC gibt keine Modelle mehr an andere Mitglieder weiter.")

    def fragt_community_setzen(self, an) -> dict:
        def go():
            self._ki.einstellung_setzen(fragt_community=None if an is None else bool(an))
            return {"fragt_community": self.fragt_community()}
        return self._guarded("fragt_community_setzen", go, "Deine Fragen beantwortet ab jetzt ein freier Rechner der Community." if an
                             else ("Automatisch: Rechner ohne starke Grafikkarte fragen die Community." if an is None else "Deine Fragen beantwortet ab jetzt dieses Gerät selbst."))

    def _community_antwort(self, nachrichten: list[dict], fuer_seite, *, vorige: str = "", skill: dict | None = None, fachgebiete: list | None = None) -> dict:
        online = None
        try:
            rs = self._community.rechenstand()
            if (rs.get("not_aus") or {}).get("an"):
                grund = str((rs.get("not_aus") or {}).get("grund") or "")
                raise app_core.AppError("COMMUNITY_NOT_AUS", "die Community ist gerade angehalten" + (f" ({grund})" if grund else ""))
            online = int((rs.get("fragen") or {}).get("rechner_online", 0) or 0)
        except (ValueError, TypeError, AttributeError):
            online = None
        except app_core.AppError as exc:
            if exc.code == "COMMUNITY_NOT_AUS":
                raise
            online = None
        if online == 0:
            raise app_core.AppError("COMMUNITY_KEINER", "gerade beantwortet kein Gerät der Community Fragen")
        extra = {**({"vorige": vorige} if vorige else {}), **({"skill": skill} if skill else {}), **({"fachgebiete": list(fachgebiete)} if fachgebiete else {})}
        k = self._community.frage_stellen(nachrichten, **extra)
        t0 = time.time()
        warten_ungenommen = WARTEN_UNGENOMMEN_S if not online else WARTEN_UNGENOMMEN_BESCHAEFTIGT_S
        fuer_seite("Deine Frage ist bei der Community. Ein freier PC übernimmt sie gleich …" if not online
                   else f"Deine Frage ist bei der Community ({online} PCs online). Ein freier PC übernimmt sie gleich …")
        self._schritt("wartet auf einen freien PC der Community …")
        self._community_frage = k
        try:
            d = self._community_warten(k, t0, warten_ungenommen, fuer_seite)
            if isinstance(d, dict):
                d = {**d, "auftrag": k}
            return d
        finally:
            self._community_frage = None

    def _community_warten(self, k: str, t0: float, warten_ungenommen: float, fuer_seite, *, daheim: bool = False,
                          warten_genommen: float = WARTEN_ANTWORT_S) -> dict:
        stand = ""
        fehlversuche = 0
        while True:
            if self.abbruch_gewuenscht:
                self._community.frage_aufgeben(k)
                raise app_core.AppError("ABGEBROCHEN", "auf deinen Wunsch abgebrochen")
            frist = WARTEN_ANTWORT_S if stand.startswith("genommen:") else warten_ungenommen
            try:
                r = self._community.antwort_abholen(k, seit=stand.partition(":")[2], warten_s=max(1.0, min(ABHOLEN_WARTEN_S, frist - (time.time() - t0))))
            except app_core.AppError as exc:
                if exc.code != "COMMUNITY_UNERREICHBAR" or fehlversuche >= ABHOLEN_FEHLVERSUCHE or time.time() - t0 > frist:
                    raise
                fehlversuche += 1
                _log(self._core, f"HINWEIS antwort abholen: {exc.detail}; Versuch {fehlversuche + 1}")
                time.sleep(WARTEN_TAKT_S)
                continue
            fehlversuche = 0
            if self.abbruch_gewuenscht:
                self._community.frage_aufgeben(k)
                raise app_core.AppError("ABGEBROCHEN", "auf deinen Wunsch abgebrochen")
            if not r.get("stand"):
                time.sleep(WARTEN_TAKT_S)
            stand = f"{r.get('status')}:{r.get('stand') or ''}"
            st = r.get("status")
            if st == "fertig":
                if isinstance(r.get("etikett"), dict) and isinstance(r.get("lieferschein"), dict):
                    r["lieferschein"] = {**r["lieferschein"], "etikett": r["etikett"]}
                return r
            if st == "verworfen":
                raise app_core.AppError("COMMUNITY_KEINER", str(r.get("grund", "kein Rechner hat geantwortet")))
            if st == "genommen":
                fuer_seite("Dein PC daheim ist dran …" if daheim else "Ein PC aus der Community erarbeitet gerade deine Antwort …")
                self._schritt(str(r.get("schritt") or ("dein PC daheim ist dran …" if daheim else "ein PC aus der Community erarbeitet deine Antwort …")))
                if r.get("teil") and self._window is not None:
                    self._js(f"app.teil({json.dumps(str(r['teil']), ensure_ascii=False)})")
                if time.time() - t0 > warten_genommen:
                    self._community.frage_aufgeben(k)
                    raise app_core.AppError("COMMUNITY_LANGSAM", "dein PC daheim hat zu lange gebraucht; probier es gleich noch einmal" if daheim
                                            else "der Rechner der Community hat zu lange gebraucht")
            elif time.time() - t0 > warten_ungenommen:
                self._community.frage_aufgeben(k)
                raise app_core.AppError("COMMUNITY_KEINER", vermittlung_basis.ZUHAUSE_AUS_TEXT if daheim else "gerade ist kein Rechner der Community frei")

    def community_einladung(self) -> dict:
        def go():
            d = dict(self._community.einladung_erzeugen())
            basis = "https://kiplatz.at" if self._community.adresse.rstrip("/") == community.STANDARD_ADRESSE else self._community.adresse.rstrip("/")
            adresse = f"{basis}/app/?code={d.get('code', '')}"
            d["adresse"] = adresse
            try:
                import segno
                d["qr"] = segno.make(adresse, error="m").svg_data_uri(scale=5, border=2, dark="#1b1f1e", light="#ffffff")
            except Exception as exc:
                _log(self._core, f"INFO qr nicht möglich: {type(exc).__name__}")
            return d
        return self._guarded("community_einladung", go)

    def community_beitreten(self, code: str) -> dict:
        def go():
            d = self._community.geraet_mit_code(str(code), self._geraet_name)
            return {"geraet": {"kennung": d["kennung"], "name": d["name"], "seit": d["seit"]}, "fragt_community": self.fragt_community()}
        return self._guarded("community_beitreten", go, "Willkommen. Dieses Gerät gehört jetzt zur Community.")


    def community_beitreten_konto(self, browser: bool = True) -> dict:
        def go():
            if self._community.geraet() is not None:
                raise app_core.AppError("KONTO_SCHON", "dieses Gerät gehört schon zur Community")
            if self._community.adresse.rstrip("/") == SPIELWIESE_ADRESSE:
                raise app_core.AppError("KONTO_SPIELWIESE", "Auf der Spielwiese trittst du mit dem Code „spielwiese“ bei; das KIplatz-Konto gilt für die echte Community.")
            lauf = self._beitritt
            if lauf is not None and lauf["laeuft"]:
                return self._beitritt_stand()
            d = self._community.konto_beitritt_start(PC_ART, self._geraet_name)
            if not d["adresse"].startswith(KONTO_ISSUER.rstrip("/") + "/"):
                raise app_core.AppError("KONTO_ISSUER", f"die Anmeldestelle {d['adresse'][:60]} ist nicht die Werkstatt von KIplatz; abgebrochen")
            self._beitritt = {"laeuft": True, "fertig": False, "fehler": "", "adresse": d["adresse"], "konto": ""}
            threading.Thread(target=self._beitritt_abholen, args=(d["ticket"], self._beitritt), name="kiplatz-beitritt-konto", daemon=True).start()
            try:
                if browser:
                    webbrowser.open(d["adresse"])
            except Exception as exc:
                _log(self._core, f"INFO browser nicht geöffnet: {type(exc).__name__}")
            return self._beitritt_stand()
        return self._guarded("community_beitreten_konto", go)

    def _beitritt_stand(self) -> dict:
        lauf = self._beitritt or {"laeuft": False, "fertig": False, "fehler": "", "adresse": "", "konto": ""}
        return {**lauf, "adresse": lauf["adresse"] if lauf["laeuft"] else "", "fragt_community": self.fragt_community()}

    def community_beitreten_konto_stand(self) -> dict:
        return self._guarded("community_beitreten_konto_stand", self._beitritt_stand)

    def community_beitreten_konto_abbrechen(self) -> dict:
        def go():
            if self._beitritt is not None and self._beitritt["laeuft"]:
                self._beitritt.update(laeuft=False, fehler="")
            return self._beitritt_stand()
        return self._guarded("community_beitreten_konto_abbrechen", go)

    def _beitritt_abholen(self, ticket: str, lauf: dict) -> None:
        ende = time.monotonic() + BEITRITT_FRIST_S
        while lauf["laeuft"] and not self._stopp.wait(BEITRITT_BLICK_S):
            if not lauf["laeuft"]:
                return
            if time.monotonic() > ende:
                lauf.update(laeuft=False, fehler="Die Anmeldung hat zu lange gedauert. Bitte noch einmal.")
                return
            try:
                d = self._community.konto_beitritt_abholen(ticket)
            except app_core.AppError as exc:
                if exc.code in ("COMMUNITY_LANGSAM", "COMMUNITY_UNERREICHBAR"):
                    continue
                _log(self._core, f"ABGELEHNT community_beitreten_konto: {exc.code}: {exc.detail}")
                lauf.update(laeuft=False, fehler="Abgebrochen oder abgelaufen. Bitte noch einmal." if exc.code == "COMMUNITY_KONTO_ABGELAUFEN"
                            else menschlich(exc.code, exc.detail))
                return
            except Exception as exc:
                _write_error_report(self._core, exc)
                _log(self._core, f"FEHLER community_beitreten_konto: {type(exc).__name__}")
                lauf.update(laeuft=False, fehler="Da ist etwas schiefgegangen. Das Programm hat es notiert.")
                return
            if d is None:
                continue
            self._ki.einstellung_setzen(konto={"name": d["konto"] or d["name"], "sub": ""})
            self._community_stand = None
            lauf.update(laeuft=False, fertig=True, konto=d["konto"] or d["name"])
            _log(self._core, "OK community_beitreten_konto")
            return

    def community_meine_daten(self) -> dict:
        return self._guarded("community_meine_daten", lambda: self._community.meine_daten())

    def community_schluessel_erneuern(self) -> dict:
        def go():
            self._community.schluessel_erneuern()
            return {"erneuert": True}
        return self._guarded("community_schluessel_erneuern", go, "Dieses Gerät hat einen neuen Schlüssel. Der alte gilt ab sofort nicht mehr; Name und Credits bleiben.")

    def _schluessel_pflegen(self) -> None:
        try:
            if self._community.geraet() is not None and self._community.schluessel_faellig(rueckweg_s=app_install.rueckweg_zeit(self._install_dir)):
                self._community.schluessel_erneuern()
                _log(self._core, "OK schluessel erneuert")
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT schluessel_erneuern: {exc.code}: {exc.detail}")

    def community_austreten(self) -> dict:
        def go():
            a = self._community.austreten()
            self._rechen.stop()
            try:
                self._halter.alles_loeschen()
            except Exception as exc:
                _log(self._core, f"FEHLER scheiben löschen: {type(exc).__name__}")
            return {"antwort": a, "fragt_community": self.fragt_community()}
        return self._guarded("community_austreten", go, "Du hast die Community verlassen. Am Server ist nichts mehr über dieses Gerät gespeichert. Komm gern wieder.")

    def _wissen_auftrag(self, auftrag: dict) -> dict:
        was = str(auftrag.get("was", ""))
        if was == "liste":
            return {"quellen": self._wissen_fuer_gekoppelte()}
        if was == "seite":
            adresse = str(auftrag.get("adresse", "")).strip()
            wissen.nur_oeffentlich(adresse)
            endgueltig, titel, text = wissen.seite_holen(adresse, pruefer=wissen.nur_oeffentlich)
            b = hausordnung.pruefen(titel + "\n" + text)
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
            q = self._wissen.hinzufuegen("privatseite", titel, endgueltig, text)
            return {"quelle": q.kurz(), "quellen": self._wissen_fuer_gekoppelte()}
        if was == "entfernen":
            kennung = str(auftrag.get("kennung", ""))
            if not any(q["kennung"] == kennung for q in self._wissen_fuer_gekoppelte()) or not self._wissen.entfernen(kennung):
                raise app_core.AppError("WISSEN_KENNUNG", "diese Quelle gibt es nicht")
            return {"quellen": self._wissen_fuer_gekoppelte()}
        raise app_core.AppError("WISSEN_AUFTRAG", "unbekannter Auftrag")

    def _wissen_fuer_gekoppelte(self) -> list[dict]:
        return [q for q in self._wissen.liste(privat=None) if q.get("art") not in wissen.GEHEIM_ARTEN]

    def _js(self, code: str) -> None:
        if self._window is not None:
            try:
                self._window.evaluate_js(code)
            except Exception:
                pass

    def vorbereiten(self, *, selbst_einrichten: bool = True, ki_auto: bool | None = None) -> None:
        try:
            self._core.ensure_directories()
            self._core.run_first_start_check()
        except app_core.AppError as exc:
            self.prep_error = f"Vorbereitung unvollständig: {exc.detail}"
            _log(self._core, f"ABGELEHNT vorbereiten: {exc.code}: {exc.detail}")
            return
        try:
            n = self._wissen.seiten_privat_machen()
            if n:
                _log(self._core, f"OK {n} hier gelesene Websites sind jetzt privat")
        except Exception as exc:
            _log(self._core, f"FEHLER seiten privat machen: {type(exc).__name__}")
        if self._ki.einstellung().get("schnittstelle"):
            r = self._guarded("schnittstelle_start", self._schnittstelle.start)
            if not r["ok"]:
                self.start_meldung = r["text"]
        if self._ki.einstellung().get("anbieten") and self._ki.quelle() == "lokal":
            r = self._guarded("heimnetz_anbieten_start", self._anbieten_start)
            if not r["ok"]:
                if r.get("code") == "HEIMNETZ_PORT":
                    self._anbieten_spaeter()
                else:
                    self.start_meldung = r["text"]
        elif (self.ki_auto() if ki_auto is None else ki_auto) and self._ki.quelle() == "lokal":
            if self._schwach() or self._ki.einstellung().get("fragt_community") is True:
                _log(self._core, "OK ki_auto übersprungen (fragt die Community)")
            elif self._ki.einschalten():
                _log(self._core, "OK ki_auto einschalten")
        if self._core.run_state() is node_local_state.RunState.ACTIVE:
            self._rechen.start()
        self._warmhalter.start()
        if self._community.geraet() is not None and not self.spielwiese:
            self._weitergeber.starten()
        if not self.spielwiese:
            self._wiki.start()
            self._osm.start()
        self._quellen_melden_im_hintergrund()
        if not selbst_einrichten:
            return
        app_install.alt_aufraeumen(self._install_dir)
        portable = app_install.portable_root()
        if app_install.running_exe() is not None or portable is not None:
            self._update_im_hintergrund()
            self._gemeinschaft_im_hintergrund()
        if portable is not None:
            r = self._guarded("self_setup", lambda: app_install.ensure_installed_portable(portable, self._install_dir, bau=app_core.APP_BUILD))
        else:
            r = self._guarded("self_setup", lambda: app_install.ensure_installed(app_install.running_exe(), self._install_dir))
        if r["ok"]:
            what, info = r["daten"]
            _log(self._core, f"OK self_setup {what}")
            if what == "eingerichtet":
                self.start_meldung = "Eingerichtet: Das Programm liegt jetzt dauerhaft in deinem Benutzerordner. Unter „Einstellungen“ kannst du den Autostart einschalten."
            elif what == "aktualisiert":
                self.start_meldung = "Die neue Version wurde in deinen Benutzerordner übernommen."
            if info is not None and self._install_dir is None:
                if portable is not None:
                    cmd = app_install.start_command(info.exe_path.parent)
                    s = app_install.ensure_shortcut(Path(cmd[0]), args=f'"{cmd[1]}"', arbeitsordner=info.exe_path.parent)
                else:
                    s = app_install.ensure_shortcut(info.exe_path)
                _log(self._core, f"OK desktop_symbol {s}")
                if portable is not None:
                    neu = lambda d: app_install.ensure_shortcut(Path(cmd[0]), d, args=f'"{cmd[1]}"', arbeitsordner=info.exe_path.parent)
                    _log(self._core, f"OK verknuepfungen {app_install.verknuepfungen_aufraeumen(info.exe_path.parent, anlegen=neu)}")
                if s == "angelegt" and what in ("eingerichtet", "aktualisiert"):
                    self.start_meldung += " Auf dem Desktop liegt jetzt „KIplatz“."
                if portable is not None:
                    sm = app_install.startmenue_dir()
                    if sm is not None:
                        _log(self._core, f"OK startmenue {app_install.ensure_shortcut(Path(cmd[0]), sm, args=f'\"{cmd[1]}\"', arbeitsordner=info.exe_path.parent)}")
                    _log(self._core, f"OK apps_eintrag {app_install.apps_eintrag_setzen(info.exe_path.parent, app_core.APP_VERSION, app_core.APP_BUILD)}")
                    if what == "eingerichtet" and not app_install.autostart_enabled(registry=self._registry):
                        self._registry.set(app_install.RUN_VALUE_NAME, app_install.autostart_command_portable(info.exe_path.parent))
                        _log(self._core, "OK autostart eingerichtet")
                        self.start_meldung += " Es startet ab jetzt mit Windows, still ins Symbol bei der Uhr; unter Einstellungen lässt sich das abschalten."
                    elif app_install.autostart_erneuern(info.exe_path.parent, registry=self._registry):
                        _log(self._core, "OK autostart erneuert (der Eintrag zeigte auf eine Datei, die es nicht mehr gibt)")
        else:
            self.start_meldung = r["text"]
        if pakete_tausch.ERGEBNIS:
            _log(self._core, f"{'OK' if pakete_tausch.ERGEBNIS == 'getauscht' else 'HINWEIS'} pakete_tausch {pakete_tausch.ERGEBNIS}")


    def _freigabe_dict(self, f: app_core.Freigabe) -> dict:
        return {"nur_im_leerlauf": f.nur_im_leerlauf, "cpu_prozent": f.cpu_prozent, "ram_gib": f.ram_gib, "speicher_mb": f.speicher_mb, "speicher_ort": f.speicher_ort, "text": f.text_de()}

    def _freigabe_aus(self, nur_im_leerlauf, cpu_prozent, ram_gib, speicher_mb, speicher_ort=None) -> app_core.Freigabe:
        alt = self._core.load_freigabe()
        if speicher_mb is None:
            speicher_mb = alt.speicher_mb
        if speicher_ort is None:
            speicher_ort = alt.speicher_ort
        try:
            return app_core.Freigabe(bool(nur_im_leerlauf), int(cpu_prozent), round(float(ram_gib) * 2) / 2, int(speicher_mb), str(speicher_ort or ""))
        except (TypeError, ValueError):
            raise app_core.AppError("FREIGABE_UNGUELTIG", "Prozessor-, Arbeitsspeicher- oder Festplattenwert nicht erlaubt") from None

    def _laufwerke(self) -> list[dict]:
        belegt_mb = self._halter.belegt() // 1_000_000 + self._wiki.belegt_mb() + self._osm.belegt_mb()
        jetzt = self._core.load_freigabe().speicher_ort
        out = []
        for lw in app_core.laufwerke():
            frei = int(lw["frei_mb"]) + (belegt_mb if lw["ort"] == jetzt else 0)
            out.append({**lw, "max_mb": max(0, min(app_core.SPEICHER_MAX_MB, frei - scheiben_halter.RESERVE_BYTES // 1_000_000)),
                        "empfehlung_mb": app_core.speicher_empfehlung_mb(frei)})
        return out

    def _speicher_grenzen(self, ort: str) -> dict:
        try:
            wurzel = Path(ort) if ort else self._core.base_dir
            while not wurzel.exists() and wurzel.parent != wurzel:
                wurzel = wurzel.parent
            frei = shutil.disk_usage(wurzel).free // 1_000_000 + ((self._halter.belegt() // 1_000_000 + self._wiki.belegt_mb() + self._osm.belegt_mb()) if ort == self._core.load_freigabe().speicher_ort else 0)
        except OSError:
            frei = 0
        return {"max_mb": max(0, min(app_core.SPEICHER_MAX_MB, frei - scheiben_halter.RESERVE_BYTES // 1_000_000)), "empfehlung_mb": app_core.speicher_empfehlung_mb(frei), "frei_mb": frei}

    def _zustand(self) -> dict:
        state = self._core.run_state().value
        first = self._core.load_first_start()
        current = self._core.load_freigabe()
        empf = app_core.recommended_freigabe(first)
        info = app_install.installed_info(self._install_dir)
        d = {
            "app": {"name": app_core.APP_NAME, "version": app_core.APP_VERSION, "profil": "Spielwiese" if self.spielwiese else "",
                    "spielwiese": self.spielwiese, "spielwiese_code": community_dienst_spielwiese_code() if self.spielwiese else "",
                    "quelle": app_install.running_exe() is None and app_install.portable_root() is None, "start_meldung": self.start_meldung, "prep_error": self.prep_error, "geraet_name": self._geraet_name},
            "lauf": {"zustand": state, "ueberschrift": {"ACTIVE": "Eingeschaltet", "PAUSED": "Pausiert", "STOPPED": "Gestoppt"}[state],
                     "text": self._core.status_text_de(arbeit=self._arbeit_text() if state == "ACTIVE" else None, kurz=True)},
            "rechen": self._rechen.zustand(),
            "geraet": {"rolle": app_core.ROLE_LABELS_DE[first.role] if first else "Erststart-Prüfung steht noch aus",
                       "memory_gib": first.memory_gib if first else None, "cpu_cores": first.cpu_cores if first else None, "gpus": list(first.gpu_names) if first else []},
            "freigabe": self._freigabe_dict(current), "empfehlung": self._freigabe_dict(empf),
            "folgen": app_core.freigabe_folgen_saetze(current, first),
            "grenzen": {"cpu_min": app_core.CPU_MIN, "cpu_max": app_core.CPU_MAX, "ram_min": app_core.RAM_SCHRITT_GIB, "ram_max": app_core.ram_max_gib(first),
                        "ram_schritt": app_core.RAM_SCHRITT_GIB, "speicher_min": app_core.SPEICHER_MIN_MB, **self._speicher_grenzen(current.speicher_ort)},
            "laufwerke": self._laufwerke(),
            "einrichtung": {"installiert": info is not None, "seit": info.installed_at[:10] if info else None, "autostart": app_install.autostart_enabled(registry=self._registry)},
            "credits": self._credits_dict(),
            "ki": {**self._ki.zustand(), "bedeutung": self._bedeutung.zustand(), "bewertung": self._bewertung.zustand()},
            "heimnetz": self._heimnetz_dict(),
            "nachschauen": self.nachschauen_an(),
            "vorwaermen": vorwaermen.einstellung_lesen(self._ki.einstellung())["an"],
            "ki_auto": self.ki_auto(),
            "mitglied": self._community.geraet() is not None,
            "fragt_community": self.fragt_community(),
            "fragt_community_wahl": self._ki.einstellung().get("fragt_community"),
            "weitergeben": {"an": self._weitergeber.an(), "zeile": self._weitergeber.zeile()},
            "fragen_immer": self.fragen_immer(),
            "kann_antworten": self._kann_fuer_andere_antworten(),
            "dunkel": self.dunkel(),
            "schnittstelle": self._schnittstelle_dict(),
            "admin": self._community.ist_admin(),
            "neu": self.neu_liste(),
            "erststart": self.erststart_offen(),
            "kennenlernen": self.einrichtung_stand(),
            "gedaechtnis": self._gedaechtnis.stand(),
            "morgenbericht": self.morgenbericht_stand(),
            "auswahl_uebernehmen": self.auswahl_an(),
        }
        d["reparaturen"] = self._reparaturen_saetze()
        return d


    def _schnittstelle_schluessel(self) -> str | None:
        e = self._ki.einstellung()
        roh = str(e.get("schnittstelle_schluessel") or "")
        if not roh:
            return None
        try:
            s = geheim.lesen(roh)
        except geheim.GeheimError as exc:
            _log(self._core, f"FEHLER schnittstelle schluessel: {exc.code}")
            return None
        if not geheim.geschuetzt(roh):
            self._ki.einstellung_setzen(schnittstelle_schluessel=geheim.schuetzen(s))
        return s or None if e.get("schnittstelle") else None

    def _schnittstelle_dict(self) -> dict:
        return {**self._schnittstelle.zustand(), "schluessel": self._schnittstelle_schluessel() or "", "gewollt": bool(self._ki.einstellung().get("schnittstelle"))}

    def schnittstelle_setzen(self, an: bool) -> dict:
        def go():
            if an:
                if not self._ki.einstellung().get("schnittstelle_schluessel"):
                    self._ki.einstellung_setzen(schnittstelle_schluessel=geheim.schuetzen(schnittstelle.schluessel_neu()))
                self._ki.einstellung_setzen(schnittstelle=True)
                try:
                    self._schnittstelle.start()
                except schnittstelle.SchnittstellenFehler as exc:
                    self._ki.einstellung_setzen(schnittstelle=False)
                    raise app_core.AppError("SCHNITTSTELLE_PORT", exc.text) from None
            else:
                self._schnittstelle.stop()
                self._ki.einstellung_setzen(schnittstelle=False)
            return self._schnittstelle_dict()
        return self._guarded("schnittstelle_setzen", go, "Andere Programme auf diesem Gerät dürfen KIplatz jetzt fragen. Adresse und Schlüssel stehen unten." if an
                             else "Die Tür für andere Programme ist zu.")

    def kopieren(self, text: str) -> dict:
        def go():
            t = str(text or "")
            if not t:
                raise app_core.AppError("NICHTS_ZU_KOPIEREN", "Da ist nichts zum Kopieren.")
            if len(t) > 200_000:
                raise app_core.AppError("ZU_LANG", "Das ist zu lang zum Kopieren; bitte markieren und mit Strg + C kopieren.")
            if not self._zwischenablage(t):
                raise app_core.AppError("KOPIEREN", "Kopieren ging nicht; bitte markieren und mit Strg + C kopieren.")
            return {"zeichen": len(t)}
        return self._guarded("kopieren", go)

    def einfuegen_druecken(self) -> dict:
        def go():
            if not self._window_vorne():
                raise app_core.AppError("NICHT_VORNE", "Bitte zuerst ins Fenster von KIplatz klicken, dann noch einmal.")
            self._strg_v()
            return {}
        return self._guarded("einfuegen_druecken", go)

    def schnittstelle_schluessel_kopieren(self) -> dict:
        def go():
            k = self._schnittstelle_schluessel()
            if not k:
                raise app_core.AppError("KEIN_SCHLUESSEL", "Es gibt noch keinen Schlüssel; schalte zuerst die Tür für andere Programme ein.")
            if not self._zwischenablage(k):
                raise app_core.AppError("KOPIEREN", "Kopieren ging nicht; bitte „Anzeigen“, dann den Schlüssel markieren und mit Strg + C kopieren.")
            return {"zeichen": len(k)}
        return self._guarded("schnittstelle_schluessel_kopieren", go, "Schlüssel in die Zwischenablage kopiert.")

    def schnittstelle_docker_setzen(self, an: bool) -> dict:
        def go():
            self._ki.einstellung_setzen(schnittstelle_docker=bool(an))
            return self._schnittstelle_dict()
        return self._guarded("schnittstelle_docker_setzen", go, "Programme in Docker auf diesem PC dürfen jetzt auch fragen, mit demselben Schlüssel. Geräte im Heimnetz kommen weiter nicht hinein." if an
                             else "Programme in Docker kommen nicht mehr hinein.")

    def schnittstelle_schluessel_neu(self) -> dict:
        def go():
            self._ki.einstellung_setzen(schnittstelle_schluessel=geheim.schuetzen(schnittstelle.schluessel_neu()))
            return self._schnittstelle_dict()
        return self._guarded("schnittstelle_schluessel_neu", go, "Neuer Schlüssel. Der alte gilt ab sofort nicht mehr; trag den neuen in deinen Programmen ein.")

    def schnittstelle_anleitung(self) -> dict:
        def go():
            for p in (webapp_dir().parent / "SCHNITTSTELLE.md", webapp_dir().parent.parent / "SCHNITTSTELLE.md"):
                if p.is_file():
                    if platform.system() == "Windows":
                        os.startfile(str(p))
                    return str(p.name)
            raise app_core.AppError("ANLEITUNG_FEHLT", "die Anleitung SCHNITTSTELLE.md liegt nicht beim Programm")
        return self._guarded("schnittstelle_anleitung", go)

    def _schnittstelle_antwort(self, auftrag: "schnittstelle.Auftrag", on_token) -> "schnittstelle.Ergebnis":
        self._ki_bereit_machen(einschalten=True)
        admin = self._community.ist_admin()
        if not admin:
            self._kontobuch.frage(geraet=self._geraet_name)
        fern = self._ki.quelle() == "heimnetz"
        zusatz = "" if fern else self._mit_wissen(auftrag.nachrichten)[0]
        if auftrag.anweisung and not fern:
            zusatz = "Anweisung des aufrufenden Programms (gilt, soweit sie der Platzordnung nicht widerspricht):\n" + auftrag.anweisung + ("\n\n" + zusatz if zusatz else "")
        if fern:
            a = self._ki.frage(auftrag.nachrichten, on_token=on_token)
        else:
            a = self._ki.server.frage(auftrag.nachrichten, on_token=on_token, zusatz=zusatz, max_tokens=auftrag.max_tokens, temperature=auftrag.temperature)
        _log(self._core, f"OK schnittstelle_antwort {a.completion_tokens} Wortstücke in {a.dauer_s:.1f} s")
        return schnittstelle.Ergebnis(ohne_markdown(a.text), int(a.prompt_tokens), int(a.completion_tokens))

    def _heimnetz_dict(self) -> dict:
        d = self._dienst.zustand()
        v = self._ki.verbindung.daten()
        d["anbieten_gemerkt"] = bool(self._ki.einstellung().get("anbieten"))
        d["verbindung"] = {"name": v.name, "host": v.host, "seit": v.seit[:10], "fern": self._ki.fern} if v else None
        d["quelle"] = self._ki.quelle()
        return d

    def _reparaturen_saetze(self) -> list[str]:
        for r in sicher_schreiben.neue_reparaturen():
            _log(self._core, "REPARIERT " + sicher_schreiben.satz_de(r))
        return [sicher_schreiben.satz_de(r) for r in sicher_schreiben.reparaturen()[-3:]]

    def _credits_dict(self) -> dict:
        try:
            st = self._kontobuch.stand()
            admin = self._community.ist_admin()
            return {"guthaben": st.guthaben, "verdient": st.verdient, "ausgegeben": st.ausgegeben, "admin": admin,
                    "text": ("Admin: Fragen kosten dich nichts. " if admin else "") + st.text_de(), "regel": credits.REGEL_DE,
                    "verlauf": verlauf_buendeln(self._kontobuch.verlauf(200))[-12:]}
        except app_core.AppError as exc:
            if exc.code == "CREDITS_DATEI" and self._kontobuch.beschaedigt():
                verdient = None
                try:
                    g = (self._community.meine_daten() or {}).get("geraet") or {}
                    verdient = int(g.get("credits", 0)) if isinstance(g, dict) and "credits" in g else None
                except (app_core.AppError, ValueError, TypeError):
                    verdient = None
                try:
                    st = self._kontobuch.reparieren(verdient=verdient, geraet=self._geraet_name)
                    _log(self._core, f"OK credits repariert (verdient laut Server: {verdient})")
                    admin = self._community.ist_admin()
                    return {"guthaben": st.guthaben, "verdient": st.verdient, "ausgegeben": st.ausgegeben, "admin": admin,
                            "text": "Die Credits-Datei war beschädigt (zum Beispiel nach einem harten Ausschalten) und wurde neu angelegt"
                                    + ("; der Stand kommt aus der Bestenliste der Community. " if verdient is not None else "; die alte liegt daneben. ") + st.text_de(),
                            "regel": credits.REGEL_DE, "verlauf": self._kontobuch.verlauf(12)}
                except app_core.AppError as exc2:
                    _log(self._core, f"ABGELEHNT credits reparieren: {exc2.code}: {exc2.detail}")
            return {"guthaben": None, "verdient": 0, "ausgegeben": 0, "text": exc.detail, "regel": credits.REGEL_DE, "verlauf": []}

    def zustand(self) -> dict:
        return self._guarded("zustand", self._zustand)


    def start(self) -> dict:
        return self._guarded("start", lambda: (self._core.start(), self._rechen.start(), self._zustand())[2], "Eingeschaltet. Dein Rechner beantwortet Fragen anderer Mitglieder und rechnet Aufträge, sobald er frei ist.")

    def pause(self) -> dict:
        return self._guarded("pause", lambda: (self._core.pause(), self._rechen.stop(), self._reserve_entladen(), self._zustand())[3], "Pausiert.")

    def stopp(self) -> dict:
        return self._guarded("stop", lambda: (self._core.stop(), self._rechen.stop(), self._reserve_entladen(), self._zustand())[3], "Gestoppt.")

    def _reserve_entladen(self) -> None:
        try:
            if self._ki.quelle() == "lokal" and self._ki.server.laeuft() and self.fragt_community():
                self._ki_entladen()
                _log(self._core, "OK modell in der Pause entladen (dieses Gerät fragt die Community)")
        except Exception as exc:
            _log(self._core, f"FEHLER modell entladen: {type(exc).__name__}")

    def rechen_zustand(self) -> dict:
        return self._guarded("rechen_zustand", lambda: {"rechen": self._rechen.zustand(), "lauf": self._zustand()["lauf"]})

    def freigabe_folgen(self, nur_im_leerlauf: bool, cpu_prozent: int, ram_gib: float, speicher_mb: int | None = None, speicher_ort: str | None = None) -> dict:
        def go():
            f = self._freigabe_aus(nur_im_leerlauf, cpu_prozent, ram_gib, speicher_mb, speicher_ort)
            return app_core.freigabe_folgen_saetze(f, self._core.load_first_start())
        return self._guarded("freigabe_folgen", go)

    def speicher_grenzen(self, speicher_ort: str = "") -> dict:
        return self._guarded("speicher_grenzen", lambda: self._speicher_grenzen(self._ort_pruefen(speicher_ort)))

    def _ort_pruefen(self, ort) -> str:
        ort = str(ort or "")
        if ort and ort not in {lw["ort"] for lw in app_core.laufwerke()}:
            raise app_core.AppError("FREIGABE_ORT", "Dieses Laufwerk kann KIplatz nicht verwenden. Bitte ein anderes wählen.")
        return ort

    def freigabe_speichern(self, nur_im_leerlauf: bool, cpu_prozent: int, ram_gib: float, speicher_mb: int | None = None, speicher_ort: str | None = None) -> dict:
        def go():
            f = self._freigabe_aus(nur_im_leerlauf, cpu_prozent, ram_gib, speicher_mb, speicher_ort)
            ort = self._ort_pruefen(f.speicher_ort)
            first = self._core.load_first_start()
            if f.ram_gib > app_core.ram_max_gib(first):
                raise app_core.AppError("FREIGABE_UNGUELTIG", f"Höchstens {app_core.zahl_de(app_core.ram_max_gib(first))} GB Arbeitsspeicher, der Rest bleibt für dich.")
            g = self._speicher_grenzen(ort)
            if f.speicher_mb > max(g["max_mb"], 0):
                raise app_core.AppError("FREIGABE_UNGUELTIG", f"Auf diesem Laufwerk sind höchstens {app_core.groesse_de(g['max_mb'])} frei.")
            neu = speicher_pfad(ort)
            if ort:
                app_core.ensure_plain_directory(Path(ort) / app_core.SPEICHER_ORDNER)
            if ort != self._core.load_freigabe().speicher_ort:
                self._halter.umziehen(neu or (self._core.base_dir / scheiben_halter.DIRNAME))
                self._wiki.umzug_vormerken(self._wiki.ordner, wiki_pfad(ort, self._core.base_dir))
                self._osm.umzug_vormerken(self._osm.ordner, osm_pfad(ort, self._core.base_dir))
            self._core.save_freigabe(f)
            try:
                self._halter.aufraeumen()
            except Exception as exc:
                _log(self._core, f"FEHLER scheiben aufraeumen: {type(exc).__name__}")
            return self._zustand()
        return self._guarded("save_freigabe", go, "Freigabe gespeichert.")

    def speicher_stand(self) -> dict:
        def go():
            d = {"geraet": self._halter.stand(), "netz": None, "landkarte": None, "wikipedia": self._wiki.zustand(), "openstreetmap": self._osm.zustand()}
            try:
                d["netz"] = (self._community.rechenstand().get("scheiben") or None) if self._community.geraet() is not None else None
                if self._community.ist_admin():
                    d["landkarte"] = self._community.scheiben_landkarte()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT speicher_stand: {exc.code}: {exc.detail}")
            return d
        return self._guarded("speicher_stand", go)


    def _quellen_sammeln(self) -> dict:
        suche = None
        if self._community.geraet() is not None:
            try:
                suche = self._community.suche_stand()
            except Exception:
                suche = None
        return quellen_stand.sammeln(wiki=self._wiki, osm=self._osm, ki=self._ki, bedeutung=self._bedeutung, suche=suche)

    def quellen_stand(self) -> dict:
        def go():
            if not self._community.ist_admin():
                raise app_core.AppError("NUR_ADMIN", "nur für den Admin")
            q = self._quellen_sammeln()
            d = {"quellen": q, "zeilen": quellen_stand.zeilen(q), "geraete": None, "still": []}
            try:
                vom_server = self._community._anfrage("/quellen-stand", mit_schluessel=True)
                d["geraete"] = [{"kennung": k, **{x: v.get(x) for x in ("name", "admin", "zeit")}, "kurz": quellen_stand.kurz(v.get("quellen") or {})}
                                for k, v in (vom_server.get("geraete") or {}).items() if isinstance(v, dict)]
                d["still"] = [s for s in vom_server.get("still") or [] if isinstance(s, dict)]
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT quellen_stand: {exc.code}: {exc.detail}")
            return d
        return self._guarded("quellen_stand", go)

    def _quellen_melden_im_hintergrund(self) -> None:
        def lauf():
            gemeldet_fehler = 0.0
            while not self._stopp.wait(quellen_stand.MELDEN_ABSTAND_S):
                if self._community.geraet() is None:
                    continue
                try:
                    self._community.quellen_melden(self._quellen_sammeln())
                except Exception as exc:
                    if time.monotonic() - gemeldet_fehler > 3600:
                        gemeldet_fehler = time.monotonic()
                        _log(self._core, f"ABGELEHNT quellen melden: {getattr(exc, 'detail', None) or type(exc).__name__}")
        threading.Thread(target=lauf, name="quellen-melden", daemon=True).start()


    def ki_zustand(self) -> dict:
        return self._guarded("ki_zustand", lambda: {**self._ki.zustand(), "bedeutung": self._bedeutung.zustand(), "bewertung": self._bewertung.zustand()})

    def ki_einschalten(self) -> dict:
        def go():
            self._ki_von_hand_aus = False
            if not self._ki.einschalten():
                raise app_core.AppError("KI_LAEUFT", "die KI ist schon eingeschaltet oder wird gerade eingeschaltet")
            return self._ki.zustand()
        text = (f"Verbinde mit {self._ki.fern_name()} …" if self._ki.quelle() == "heimnetz"
                else "Die KI wird eingeschaltet. Beim ersten Mal holt sie Laufzeit und Modell, das dauert ein paar Minuten.")
        return self._guarded("ki_einschalten", go, text)

    def ki_ausschalten(self) -> dict:
        self._ki_von_hand_aus = True
        return self._guarded("ki_ausschalten", lambda: (self._ki.ausschalten(), self._bedeutung.ausschalten(), self._bewertung.ausschalten(), self._ki.zustand())[3], "Die KI ist ausgeschaltet.")

    def ki_auto(self) -> bool:
        return bool(self._ki.einstellung().get("ki_auto", True))

    def ki_auto_setzen(self, an: bool) -> dict:
        def go():
            self._ki.einstellung_setzen(ki_auto=bool(an))
            return {"ki_auto": self.ki_auto()}
        return self._guarded("ki_auto_setzen", go, "Die KI startet ab jetzt mit dem Programm." if an
                             else "Die KI startet erst mit der ersten Frage oder wenn du sie einschaltest.")

    def _ki_bereit_machen(self, *, einschalten: bool = True) -> None:
        if getattr(self._ki, "gesperrt", ""):
            raise app_core.AppError("TRAINING", self._ki.gesperrt)
        if self._ki.bereit():
            return
        if self._ki.quelle() != "lokal" or not einschalten:
            raise app_core.AppError("KI_AUS", "die KI ist ausgeschaltet; schalte sie oben ein")
        self._ki.einschalten()
        t0 = time.time()
        letzte = ""
        while time.time() - t0 < KI_WARTEN_S:
            if self._ki.bereit():
                if letzte and self._window is not None:
                    self._js('app.hinweis("")')
                return
            f = self._ki.fortschritt
            text = (f.get("was") or "Die KI startet") + (f" ({f['done'] * 100 // f['gesamt']} %)" if f.get("gesamt") else "")
            text += "" if text.endswith(".") else " …"
            if text != letzte and self._window is not None:
                letzte = text
                self._js(f"app.hinweis({json.dumps(text, ensure_ascii=False)})")
            if self._ki.phase == "fehler":
                if letzte and self._window is not None:
                    self._js('app.hinweis("")')
                raise app_core.AppError("KI_FEHLER", f"die KI konnte nicht starten: {self._ki.meldung}")
            time.sleep(0.5)
        if self._ki.phase == "laden":
            raise app_core.AppError("KI_LAEDT", "die KI holt gerade zum ersten Mal Laufzeit und Modell (ein paar Minuten); stell die Frage danach noch einmal")
        raise app_core.AppError("KI_AUS", "die KI ist noch nicht bereit; versuch es gleich noch einmal")


    def gespraeche_liste(self) -> dict:
        return self._guarded("gespraeche_liste", self._ablage.liste)

    def gespraech_neu(self) -> dict:
        return self._guarded("gespraech_neu", lambda: self._ablage.neu().to_json_dict())

    def gespraech_laden(self, kennung: str) -> dict:
        return self._guarded("gespraech_laden", lambda: self._ablage.laden(str(kennung)).to_json_dict())

    def gespraech_umbenennen(self, kennung: str, titel: str) -> dict:
        return self._guarded("gespraech_umbenennen", lambda: self._ablage.umbenennen(str(kennung), str(titel)).to_json_dict(), "Umbenannt.")

    def gespraech_pruefen_lassen(self, kennung: str, nummer: int) -> dict:
        def go():
            g = self._ablage.laden(str(kennung))
            n = int(nummer)
            if not 0 <= n < len(g.nachrichten) or g.nachrichten[n].get("rolle") != "assistant":
                raise app_core.AppError("GESPRAECH_PRUEFUNG", "diese Antwort gibt es nicht")
            frage = next((m.get("text", "") for m in reversed(g.nachrichten[:n]) if m.get("rolle") == "user"), "")
            ls = g.nachrichten[n].setdefault("lieferschein", {})
            if ls.get("mitglied_pruefung"):
                return {"pruefung": ls["mitglied_pruefung"]}
            quellen = [str(q.get("titel", "")) + (f" ({q['adresse']})" if q.get("adresse") else "") for q in (ls.get("quellen_liste") or []) if isinstance(q, dict)]
            r = self._community.pruefung_anbieten(frage, str(g.nachrichten[n].get("text", "")), quellen)
            eintrag = {"kennung": str(r.get("kennung", "")), "status": "offen", "seit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

            def eintragen(frisch):
                if n < len(frisch.nachrichten) and frisch.nachrichten[n].get("rolle") == "assistant":
                    frisch.nachrichten[n].setdefault("lieferschein", {})["mitglied_pruefung"] = eintrag
            self._ablage.aendern(str(kennung), eintragen)
            return {"pruefung": eintrag}
        return self._guarded("gespraech_pruefen_lassen", go, "Angefragt. Ein Mitglied, das Zeit hat, schaut sich Frage und Antwort an; du siehst das Ergebnis dann unter der Antwort.")

    def gespraech_pruefstand(self, kennung: str) -> dict:
        def go():
            g = self._ablage.laden(str(kennung))
            offen = [m["lieferschein"]["mitglied_pruefung"]["kennung"] for m in g.nachrichten
                     if isinstance(m.get("lieferschein"), dict) and isinstance(m["lieferschein"].get("mitglied_pruefung"), dict)
                     and m["lieferschein"]["mitglied_pruefung"].get("status") == "offen"]
            if not offen:
                return {"gespraech": g.to_json_dict(), "neu": 0}
            stand = self._community.pruefung_stand(offen)
            neu = 0

            def eintragen(frisch):
                nonlocal neu
                for m in frisch.nachrichten:
                    p = (m.get("lieferschein") or {}).get("mitglied_pruefung") if isinstance(m.get("lieferschein"), dict) else None
                    if p and p.get("kennung") in stand and stand[p["kennung"]].get("status") == "geprueft" and p.get("status") != "geprueft":
                        p.update({k: stand[p["kennung"]].get(k, "") for k in ("status", "urteil", "kommentar", "pruefer_name", "geprueft_zeit")})
                        neu += 1
            if any(v.get("status") == "geprueft" for v in stand.values() if isinstance(v, dict)):
                g = self._ablage.aendern(str(kennung), eintragen)
            return {"gespraech": g.to_json_dict(), "neu": neu}
        return self._guarded("gespraech_pruefstand", go)

    def pruefungen_offen(self) -> dict:
        return self._guarded("pruefungen_offen", lambda: {"pruefungen": self._community.pruefungen(), "mitglied": self._community.geraet() is not None})

    def pruefung_abgeben(self, kennung: str, urteil: str, kommentar: str = "") -> dict:
        def go():
            r = self._community.pruefung_abgeben(str(kennung), str(urteil), str(kommentar or ""))
            return {"antwort": r, "pruefungen": self._community.pruefungen()}
        return self._guarded("pruefung_abgeben", go, "Danke fürs Nachschauen. Das Mitglied sieht dein Urteil unter seiner Antwort, und du hast 2 Credits dafür bekommen.")

    def gespraech_bewerten(self, kennung: str, nummer: int, wert: str, grund: str = "", vorschlag: str = "", an: str = "") -> dict:
        def go():
            w = self._ablage.bewerten(str(kennung), int(nummer), str(wert), grund=str(grund or ""), vorschlag=str(vorschlag or ""))
            gemeldet = ""
            berichtigt = False
            if w == "schlecht" and len(str(vorschlag or "").strip()) >= 3:
                g0 = self._ablage.laden(str(kennung))
                n0 = int(nummer)
                frage0 = next((m.get("text", "") for m in reversed(g0.nachrichten[:n0]) if m.get("rolle") == "user"), "")
                titel0, text0 = wissen.berichtigung_text(frage0, str(g0.nachrichten[n0].get("text", "")), str(grund or ""), str(vorschlag or ""))
                self._wissen.hinzufuegen("berichtigung", titel0, f"berichtigung:{kennung}/{n0}", text0)
                berichtigt = True
            if w and self._community.kann_merken():
                try:
                    try:
                        sid = str(((self._ablage.laden(str(kennung)).nachrichten[int(nummer)] or {}).get("lieferschein") or {}).get("speicher_id") or "")
                    except (IndexError, ValueError, TypeError, AttributeError):
                        sid = ""
                    if re.fullmatch(r"[0-9a-f]{20}", sid):
                        (self._community.speicher_schlecht if w == "schlecht" else self._community.speicher_gut)(sid)
                    self._community.zaehlen(w)
                    if w == "schlecht" and an in ("admin", "community") and (grund or vorschlag):
                        g = self._ablage.laden(str(kennung))
                        n = int(nummer)
                        frage = next((m.get("text", "") for m in reversed(g.nachrichten[:n]) if m.get("rolle") == "user"), "")
                        self._community.rueckmeldung(frage, str(g.nachrichten[n].get("text", "")), str(grund or ""), str(vorschlag or ""), str(an))
                        gemeldet = an
                except app_core.AppError as exc:
                    _log(self._core, f"ABGELEHNT rueckmeldung: {exc.code}: {exc.detail}")
            return {"bewertung": w, "gemeldet": gemeldet, "berichtigt": berichtigt}
        r = self._guarded("gespraech_bewerten", go)
        if r["ok"]:
            d = r["daten"]
            if d["bewertung"] == "gut":
                r["text"] = "Danke, dass du die Community unterstützt."
            elif d["bewertung"] == "schlecht":
                if d.get("berichtigt"):
                    r["text"] = {"admin": "Danke. Dein Gerät hält sich ab jetzt an deine Berichtigung; der Admin hat sie auch bekommen.",
                                 "community": "Danke. Dein Gerät hält sich ab jetzt an deine Berichtigung. Ein anderes Gerät prüft sie noch gegen die Platzordnung, dann gilt sie für alle."
                                 }.get(d["gemeldet"], "Danke. Dein Gerät hält sich ab jetzt an deine Berichtigung.")
                    return r
                r["text"] = {"admin": "Danke fürs Hinschauen. Deine Rückmeldung ist beim Admin.", "community": "Danke fürs Hinschauen. Deine Rückmeldung sehen jetzt alle Mitglieder unter „Meine Community“."}.get(d["gemeldet"], "Gemerkt. Danke fürs Hinschauen.")
            else:
                r["text"] = ""
        return r

    def antwort_rueckmelden(self, kennung: str, nummer: int, grund: str = "", vorschlag: str = "", an: str = "admin") -> dict:
        grund, vorschlag = str(grund or "").strip(), str(vorschlag or "").strip()

        def go():
            if len(grund) < 3 and len(vorschlag) < 3:
                raise app_core.AppError("RUECKMELDUNG_LEER", "Wähl einen Grund oder schreib, wie es richtig wäre.")
            if not self._community.kann_merken():
                raise app_core.AppError("GERAET", "nicht in der Community")
            g = self._ablage.laden(str(kennung))
            n = int(nummer)
            if not (0 <= n < len(g.nachrichten)) or g.nachrichten[n].get("rolle") == "user":
                raise app_core.AppError("NACHRICHT", "Diese Antwort gibt es in dem Gespräch nicht mehr.")
            frage = next((m.get("text", "") for m in reversed(g.nachrichten[:n]) if m.get("rolle") == "user"), "")
            ziel = "community" if str(an) == "community" and "anstößig" not in grund.lower() and len(vorschlag) >= 3 else "admin"
            self._community.rueckmeldung(frage, str(g.nachrichten[n].get("text", "")), grund, vorschlag, ziel)
            return {"an": ziel}
        r = self._guarded("antwort_rueckmelden", go)
        if r["ok"]:
            r["text"] = ("Danke. Ein anderes Mitglied prüft deinen Vorschlag, danach gilt er für alle." if r["daten"]["an"] == "community"
                         else "Danke, ist bei uns angekommen. Wir sehen es uns binnen 48 Stunden an.")
        return r

    def gespraech_verschieben(self, kennung: str, projekt: str) -> dict:
        return self._guarded("gespraech_verschieben", lambda: self._ablage.verschieben(str(kennung), str(projekt or "")).to_json_dict(),
                             "Verschoben." if projekt else "Aus dem Projekt genommen.")

    def gespraech_archivieren(self, kennung: str, an: bool = True) -> dict:
        return self._guarded("gespraech_archivieren", lambda: self._ablage.archivieren(str(kennung), bool(an)).to_json_dict(),
                             "Archiviert. Über „Archiv“ unten in der Leiste findest du es wieder." if an else "Wieder in der Liste.")

    def gespraech_farbe(self, kennung: str, farbe: str) -> dict:
        return self._guarded("gespraech_farbe", lambda: self._ablage.farbe_setzen(str(kennung), str(farbe)).to_json_dict())

    def projekt_farben(self) -> dict:
        return self._guarded("projekt_farben", lambda: {"farben": self._ablage.projekt_farben(), "palette": {k: list(v) for k, v in gespraeche.FARBEN.items()}})

    def projekt_farbe(self, projekt: str, farbe: str) -> dict:
        return self._guarded("projekt_farbe", lambda: self._ablage.projekt_farbe_setzen(str(projekt), str(farbe)))

    def projekt_anlegen(self, projekt: str) -> dict:
        return self._guarded("projekt_anlegen", lambda: self._ablage.projekt_anlegen(str(projekt)), "Projekt angelegt.")

    def projekt_umbenennen(self, alt: str, neu: str) -> dict:
        return self._guarded("projekt_umbenennen", lambda: self._ablage.projekt_umbenennen(str(alt), str(neu)), "Projekt umbenannt.")

    def projekt_entfernen(self, projekt: str) -> dict:
        return self._guarded("projekt_entfernen", lambda: self._ablage.projekt_entfernen(str(projekt)))

    def gespraech_anheften(self, kennung: str, an: bool = True) -> dict:
        return self._guarded("gespraech_anheften", lambda: self._ablage.anheften(str(kennung), bool(an)).to_json_dict(), "Angeheftet, ganz oben." if an else "Losgelöst.")

    def gespraech_exportieren(self, kennung: str) -> dict:
        def go():
            ziel = Path.home() / "Downloads"
            if not ziel.is_dir():
                ziel = Path.home()
            p = self._ablage.exportieren(str(kennung), ziel)
            return {"pfad": str(p)}
        r = self._guarded("gespraech_exportieren", go)
        if r["ok"]:
            r["text"] = f"Gespeichert als Textdatei: {r['daten']['pfad']}"
        return r


    def gespraech_anhang(self, kennung: str) -> dict:
        def go():
            p = self._datei_waehlen(("Dokumente (*.pdf;*.docx;*.txt;*.md;*.html;*.htm;*.csv)", "Alle Dateien (*.*)"))
            a = anhaenge.lesen(p)
            b = hausordnung.pruefen(a.text[:20_000])
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
            k = str(kennung) or self._ablage.neu().kennung
            g = self._ablage.anhang_hinzufuegen(k, a.name, a.text, a.info)
            return {"gespraech": g.to_json_dict(), "anhang": a.kurz()}
        r = self._guarded("gespraech_anhang", go)
        if r["ok"]:
            a = r["daten"]["anhang"]
            r["text"] = f"„{a['name']}“ gelesen ({a['info']}{', gekürzt auf die ersten 60 Tsd. Zeichen' if a['gekuerzt'] else ''}). Frag jetzt etwas dazu."
        return r

    def gespraech_bild(self, kennung: str) -> dict:
        def go():
            p = self._datei_waehlen(("Bilder (*.png;*.jpg;*.jpeg;*.webp;*.gif)", "Alle Dateien (*.*)"))
            k = str(kennung) or self._ablage.neu().kennung
            g = self._ablage.bild_hinzufuegen(k, p)
            return {"gespraech": g.to_json_dict(), "kann": bool(getattr(self._ki.server, "bilder", False))}
        r = self._guarded("gespraech_bild", go)
        if r["ok"]:
            r["text"] = "Bild dabei. Frag jetzt etwas dazu." if r["daten"]["kann"] else "Bild dabei. Dieses Gerät kann Bilder aber nur anschauen, wenn die KI auf einer Grafikkarte läuft; sonst antwortet es ohne das Bild."
        return r

    def gespraech_bild_daten(self, kennung: str, name: str, daten_b64: str) -> dict:
        def go():
            roh = str(daten_b64 or "")
            if "," in roh[:64] and roh[:5] == "data:":
                roh = roh.split(",", 1)[1]
            try:
                daten = base64.b64decode(roh, validate=True)
            except (ValueError, binascii.Error):
                raise app_core.AppError("BILD_ART", "das eingefügte Bild ließ sich nicht lesen") from None
            k = str(kennung) or self._ablage.neu().kennung
            g = self._ablage.bild_aus_bytes(k, str(name or ""), daten)
            return {"gespraech": g.to_json_dict(), "kann": bool(getattr(self._ki.server, "bilder", False))}
        r = self._guarded("gespraech_bild_daten", go)
        if r["ok"]:
            r["text"] = "Bild dabei. Frag jetzt etwas dazu." if r["daten"]["kann"] else "Bild dabei. Dieses Gerät kann Bilder aber nur anschauen, wenn die KI auf einer Grafikkarte läuft; sonst antwortet es nur zum Text."
        return r


    def gespraech_bildschirm(self, kennung: str) -> dict:
        def go():
            if self._schwach():
                raise app_core.AppError("BILD_OHNE_KARTE", "Bilder anschauen geht nur auf einem Rechner mit Grafikkarte; dieser fragt die Community, und die bekommt keine Bilder.")
            k = str(kennung) or self._ablage.neu().kennung
            ziel = self._core.base_dir / "bildschirm" / f"bildschirm-{time.strftime('%Y%m%dT%H%M%S')}.png"
            versteckt = False
            if self._window is not None and not self.versteckt:
                try:
                    self._window.hide()
                    versteckt = True
                    time.sleep(0.45)
                except Exception:
                    versteckt = False
            try:
                bildschirm.aufnehmen(ziel)
            finally:
                if versteckt:
                    try:
                        self._window.show()
                    except Exception:
                        pass
            g = self._ablage.bild_hinzufuegen(k, ziel)
            try:
                ziel.unlink()
            except OSError:
                pass
            return {"gespraech": g.to_json_dict()}
        return self._guarded("gespraech_bildschirm", go, "Bildschirm dabei. Frag jetzt etwas dazu, zum Beispiel „Was steht in dieser Fehlermeldung?“")

    def vorlesen(self, text: str) -> dict:
        def go():
            t = ohne_markdown(str(text or ""))
            if not t.strip():
                raise app_core.AppError("VORLESEN_LEER", "da ist nichts zum Vorlesen")
            if not vorlesen.moeglich():
                raise app_core.AppError("VORLESEN_FEHLT", "Windows hat auf diesem Gerät keine Sprachausgabe; unter Einstellungen → Zeit und Sprache → Sprache lässt sich eine deutsche Stimme nachladen")
            return {"stimme": vorlesen.sprechen(t, antwortsprache.frage_sprache(t))}
        return self._guarded("vorlesen", go)

    def vorlesen_stopp(self) -> dict:
        vorlesen.stopp()
        return {"ok": True, "text": "", "daten": None}

    def datenfluss(self) -> dict:
        return self._guarded("datenfluss", datenfluss.stand)


    def frage_vervollstaendigen(self, text: str) -> dict:
        def go():
            t = " ".join(str(text or "").split())[:2000]
            if len(t) < 3:
                raise app_core.AppError("FRAGE_LEER", "da steht noch keine Frage")
            b = hausordnung.pruefen(t)
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
            anweisung = ("Schreib diese Bitte so um, dass eine KI sie gut erledigen kann: vollständig, in ein oder zwei Sätzen, in der Ich-Form der Person, "
                         "in ihrer Sprache. Was fehlt und die Antwort ändern würde (für wen, wofür, bis wann, Ton, Länge, Rahmen), ergänzt du als Lücke in eckigen "
                         "Klammern, zum Beispiel [für wen] oder [bis wann]. Erfinde keine Angaben. Antworte nur mit der neuen Bitte, ohne Erklärung, ohne Anführungszeichen.\n\n"
                         f"Die Bitte: {t}")
            nachrichten = [{"role": "user", "content": anweisung}]
            neu = ""
            if self.fragt_community():
                try:
                    neu = str((self._community_antwort(nachrichten, lambda _t: None) or {}).get("text") or "")
                except app_core.AppError as exc:
                    _log(self._core, f"INFO vervollstaendigen community: {exc.code}")
            if not neu:
                self._ki_bereit_machen(einschalten=True)
                a = self._ki.frage(nachrichten, max_tokens=220, kurz=True)
                neu = a.text
            neu = ohne_markdown(neu).strip().strip("„“\"'").strip()
            if not neu:
                raise app_core.AppError("VERVOLLSTAENDIGEN", "dafür kam keine Fassung zurück")
            return {"text": neu[:2000], "vorher": t}
        return self._guarded("frage_vervollstaendigen", go)

    def einrichtung_stand(self) -> dict:
        e = self._ki.einstellung()
        return {"gemacht": bool(e.get("einrichtung")), "name": str(e.get("mein_name") or ""), "ort": morgenbericht.einstellung_lesen(e)["ort"],
                "themen": [str(t) for t in (e.get("meine_themen") or []) if str(t).strip()],
                "wofuer": meine_ki.bereinigen(e.get("meine_ki"))["wofuer"]}

    def einrichtung_speichern(self, name: str = "", ort: str = "", themen_text: str = "", wofuer: list | None = None) -> dict:
        def go():
            n = " ".join(str(name or "").split())[:60]
            o = " ".join(str(ort or "").split())[:60]
            liste = []
            for t in re.split(r"[,;\n]", str(themen_text or "")):
                t = " ".join(t.split())[:60]
                if t and t.lower() not in [x.lower() for x in liste]:
                    liste.append(t)
            gewaehlt = meine_ki.bereinigen({"wofuer": list(wofuer or [])})["wofuer"]
            titel = {b["id"]: b["titel"] for b in meine_ki.BAUSTEINE["wofuer"]}
            liste = [titel[x] for x in gewaehlt if titel[x].lower() not in [y.lower() for y in liste]] + liste
            liste = liste[:themen.MAX_THEMEN]
            for t in [n, o] + liste:
                b = hausordnung.pruefen(t)
                if not b.ok:
                    raise app_core.AppError("HAUSORDNUNG", b.text)
            self._gedaechtnis.setzen(True)
            if n:
                self._gedaechtnis.merken(f"Ich heiße {n}; so soll KIplatz mich ansprechen")
            if o:
                land = ""
                try:
                    land = self._nachschauer.land_fuer_ort(o)
                except Exception as exc:
                    _log(self._core, f"INFO einrichtung land: {type(exc).__name__}")
                self._gedaechtnis.merken(f"Ich wohne in {o}")
                self._ki.einstellung_setzen(morgen_ort=o, morgen_land=land or "")
            if gewaehlt:
                self._meine_ki_setzen({**meine_ki.bereinigen(self._ki.einstellung().get("meine_ki")), "wofuer": gewaehlt})
            self._ki.einstellung_setzen(einrichtung=True, mein_name=n, meine_themen=liste)
            _log(self._core, f"OK einrichtung: {len(liste)} Themen")
            return self.einrichtung_stand()
        return self._guarded("einrichtung_speichern", go, "Danke. KIplatz kennt dich jetzt ein bisschen. Name und Ort änderst du unter Einstellungen, alles andere unter „Meine KI“.")

    def einrichtung_spaeter(self) -> dict:
        def go():
            self._ki.einstellung_setzen(einrichtung=True)
            return self.einrichtung_stand()
        return self._guarded("einrichtung_spaeter", go)

    def themen_stand(self) -> dict:
        return self._guarded("themen_stand", lambda: self._themen.stand())


    def _meine_ki(self) -> dict:
        wahl = meine_ki.bereinigen(self._ki.einstellung().get("meine_ki"))
        namen = [b["name"] for b in self._kiste.liste()]
        return {"wahl": wahl, "bausteine": meine_ki.BAUSTEINE, "skill": meine_ki.NAME in namen,
                "immer": meine_ki.NAME in self._kiste.immer(), "text": meine_ki.skill_text(wahl) if not meine_ki.leer(wahl) else "",
                "quellen": meine_ki.QUELLEN}

    def _fachgebiete(self) -> list[str]:
        try:
            wahl = meine_ki.bereinigen(self._ki.einstellung().get("meine_ki"))
            if not wahl["wofuer"] or meine_ki.NAME not in self._kiste.immer():
                return []
            return wissen.fachgebiete_pruefen(wahl["wofuer"])
        except Exception:
            return []

    def _meine_ki_setzen(self, wahl) -> None:
        w = meine_ki.bereinigen(wahl)
        b = meine_ki.als_skill(w)
        self._kiste.speichern(b)
        self._kiste.immer_setzen(b.name, True)
        self._ki.einstellung_setzen(meine_ki=w)
        _log(self._core, f"OK meine_ki: {len(w['wofuer'])} Themen, {len(b.text)} Zeichen")

    def meine_ki_stand(self) -> dict:
        return self._guarded("meine_ki_stand", self._meine_ki)

    def meine_ki_speichern(self, wahl: dict) -> dict:
        def go():
            self._meine_ki_setzen(wahl)
            return self._meine_ki()
        return self._guarded("meine_ki_speichern", go, "Gespeichert. KIplatz antwortet ab jetzt so, in jedem Gespräch, auch wenn ein PC der Community antwortet.")

    def meine_ki_entfernen(self) -> dict:
        def go():
            self._kiste.entfernen(meine_ki.NAME)
            self._ki.einstellung_setzen(meine_ki={})
            return self._meine_ki()
        return self._guarded("meine_ki_entfernen", go, "„Meine KI“ ist zurückgesetzt. KIplatz antwortet wieder wie für alle.")

    def skill_vorlagen(self) -> dict:
        return self._guarded("skill_vorlagen", lambda: {"vorlagen": [v.kurz() for v in skills.vorlagen(community.SPRACHE)], "meine": [b["name"] for b in self._kiste.liste()]})

    def skill_vorlage_uebernehmen(self, name: str) -> dict:
        def go():
            v = next((v for v in skills.vorlagen(community.SPRACHE) + skills.vorlagen() if v.name == str(name)), None)
            if v is None:
                raise app_core.AppError("SKILL_VORLAGE", "diese Vorlage gibt es nicht")
            b = self._kiste.speichern(skills.Skill(v.name, v.beschreibung, v.text, quelle="vorlage"))
            return {"skill": b.kurz(), "skills": self._kiste.liste()}
        return self._guarded("skill_vorlage_uebernehmen", go, f"Skill „{name}“ übernommen. Du wählst ihn neben dem Eingabefeld.")

    def morgenbericht_stand(self) -> dict:
        return morgenbericht.einstellung_lesen(self._ki.einstellung())

    def morgenbericht_setzen(self, an: bool, zeit: str = "07:00", ort: str = "", vorlesen: bool = True) -> dict:
        def go():
            z = str(zeit or morgenbericht.STANDARD_ZEIT).strip()
            if not re.fullmatch(r"\d{2}:\d{2}", z):
                raise app_core.AppError("MORGEN_ZEIT", "die Uhrzeit braucht die Form 07:00")
            o = " ".join(str(ort or "").split())[:60]
            vorher = self.morgenbericht_stand()
            land = vorher.get("land", "")
            if o and o != vorher.get("ort"):
                try:
                    land = self._nachschauer.land_fuer_ort(o)
                except Exception as exc:
                    _log(self._core, f"INFO morgenbericht land: {type(exc).__name__}")
            self._ki.einstellung_setzen(morgen_an=bool(an), morgen_zeit=z, morgen_ort=o, morgen_vorlesen=bool(vorlesen), morgen_land=land or "")
            stand = self.morgenbericht_stand()
            if bool(an) and o and o != vorher.get("ort") and stand["zuletzt"] == datetime.now().strftime("%Y-%m-%d"):
                stand["gespraech"] = self._morgenbericht_erstellen()["gespraech"]["kennung"]
            return stand
        return self._guarded("morgenbericht_setzen", go, f"Morgenbericht täglich um {str(zeit or '07:00')[:5]}." if an else "Morgenbericht aus.")

    def link_oeffnen(self, adresse: str) -> dict:
        def go():
            a = str(adresse or "").strip()
            if not a.startswith("https://") or len(a) > 2000 or any(c.isspace() for c in a):
                raise app_core.AppError("LINK", "nur https-Adressen werden geöffnet")
            webbrowser.open(a)
            return {"adresse": a}
        return self._guarded("link_oeffnen", go)

    def _vorlesen_still(self, text: str, sprache: str = "de") -> None:
        try:
            vorlesen.sprechen(text, sprache)
        except Exception as exc:
            _log(self._core, f"INFO morgenbericht vorlesen: {type(exc).__name__}")

    def _morgenbericht_erstellen(self) -> dict:
        s = self.morgenbericht_stand()
        jetzt = datetime.now()
        sprache = "en" if community.SPRACHE == "en" else "de"
        text, fehler = morgenbericht.erstellen(self._nachschauer, ort=s["ort"], jetzt=jetzt, land=s.get("land") or "at", sprache=sprache)
        e = self._ki.einstellung()
        alt = str(e.get("morgen_gespraech") or "")
        if alt and str(e.get("morgen_zuletzt") or "") == jetzt.strftime("%Y-%m-%d"):
            try:
                if len(self._ablage.laden(alt).nachrichten) <= 1:
                    self._ablage.loeschen(alt)
            except app_core.AppError:
                pass
        g = self._ablage.neu()
        ls = {"modell": "Morgenbericht, ohne Modell", "geraet": "dieses Gerät", "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
              "credits": "nichts verrechnet (Morgenbericht)", "quellen": "Wetter von Open-Meteo, Schlagzeilen aus freien Nachrichtenfeeds deines Landes; nichts geht an die Community.",
              "quellen_liste": morgenbericht.links(text), "gemacht": "Morgenbericht", "erfunden": "nichts, nur nachgeschaut", "pruefung": pruefung.pruefen("", []).kurz(),
              "guthaben_vorher": self._kontobuch.stand().guthaben}
        g = self._ablage.anhaengen(g, "assistant", text, lieferschein=ls, intern=True)
        g = self._ablage.umbenennen(g.kennung, f"Morning briefing {jetzt.day} {morgenbericht.MONATE_EN[jetzt.month - 1][:3]}" if sprache == "en"
                                    else f"Morgenbericht {jetzt.strftime('%d.%m.')}")
        self._ki.einstellung_setzen(morgen_zuletzt=jetzt.strftime("%Y-%m-%d"), morgen_gespraech=g.kennung)
        _log(self._core, "OK morgenbericht" + (f" ({'; '.join(fehler)})" if fehler else ""))
        if s["vorlesen"]:
            self._vorlesen_still(morgenbericht.zum_vorlesen(text), sprache)
        if self._window is not None:
            self.fenster_zeigen()
            self._js(f"app.oeffne({json.dumps(g.kennung)})")
        return {"text": text, "gespraech": g.to_json_dict(), "fehler": fehler}

    def morgenbericht_jetzt(self) -> dict:
        return self._guarded("morgenbericht_jetzt", self._morgenbericht_erstellen, "Morgenbericht erstellt.")

    def _morgenbericht_pruefen(self) -> bool:
        try:
            if not morgenbericht.faellig(self._ki.einstellung(), datetime.now()):
                return False
            self._morgenbericht_erstellen()
            return True
        except Exception as exc:
            _log(self._core, f"FEHLER morgenbericht: {type(exc).__name__}: {exc}")
            try:
                self._ki.einstellung_setzen(morgen_zuletzt=datetime.now().strftime("%Y-%m-%d"))
            except Exception:
                pass
            return False


    def auswahl_an(self) -> bool:
        return bool(self._ki.einstellung().get("auswahl_uebernehmen", True))

    def auswahl_uebernehmen_setzen(self, an: bool) -> dict:
        return self._guarded("auswahl_uebernehmen_setzen", lambda: bool(self._ki.einstellung_setzen(auswahl_uebernehmen=bool(an)).get("auswahl_uebernehmen")),
                             "Strg + Leertaste übernimmt markierten Text." if an else "Strg + Leertaste holt nur das Fenster.")


    def gedaechtnis_stand(self) -> dict:
        return self._guarded("gedaechtnis_stand", self._gedaechtnis.stand)

    def gedaechtnis_merken(self, text: str) -> dict:
        def go():
            self._gedaechtnis.merken(str(text))
            return self._gedaechtnis.stand()
        return self._guarded("gedaechtnis_merken", go, "Gemerkt, nur auf diesem Gerät.")

    def gedaechtnis_vergessen(self, kennung: str) -> dict:
        def go():
            self._gedaechtnis.vergessen(str(kennung))
            return self._gedaechtnis.stand()
        return self._guarded("gedaechtnis_vergessen", go, "Vergessen.")

    def gedaechtnis_leeren(self) -> dict:
        def go():
            self._gedaechtnis.leeren()
            return self._gedaechtnis.stand()
        return self._guarded("gedaechtnis_leeren", go, "Alles vergessen.")

    def gedaechtnis_setzen(self, an: bool) -> dict:
        return self._guarded("gedaechtnis_setzen", lambda: self._gedaechtnis.setzen(bool(an)), "Das Gedächtnis ist an." if an else "Das Gedächtnis ist aus; die Einträge bleiben, das Modell bekommt sie nicht.")


    def _kerne(self) -> int | None:
        try:
            first = self._core.load_first_start()
            return int(first.cpu_cores) if first is not None and first.cpu_cores else None
        except Exception:
            return None

    def sprechen_zustand(self) -> dict:
        return {"ok": True, "text": "", "daten": self._sprechen.stand()}

    def sprechen_start(self) -> dict:
        return {"ok": True, "text": "", "daten": self._sprechen.start()}

    def sprechen_stopp(self) -> dict:
        return {"ok": True, "text": "", "daten": self._sprechen.stopp()}

    def sprechen_abbrechen(self) -> dict:
        return {"ok": True, "text": "", "daten": self._sprechen.abbrechen()}

    def gespraech_anhang_entfernen(self, kennung: str, nummer: int) -> dict:
        return self._guarded("gespraech_anhang_entfernen", lambda: self._ablage.anhang_entfernen(str(kennung), int(nummer)).to_json_dict(), "Datei aus dem Gespräch genommen.")


    def skills_liste(self) -> dict:
        return self._guarded("skills_liste", lambda: {"skills": self._kiste.liste(), "ordner": str(self._kiste.ordner)})

    def skill_speichern(self, text: str) -> dict:
        def go():
            b = self._kiste.speichern(skills.lesen(str(text), quelle="selbst"))
            return {"skill": b.kurz(), "skills": self._kiste.liste()}
        return self._guarded("skill_speichern", go, "Skill gespeichert. Wähle ihn unten neben dem Eingabefeld, dann gilt er für das Gespräch.")

    def skill_laden(self, name: str) -> dict:
        return self._guarded("skill_laden", lambda: {"text": self._kiste.laden(str(name)).als_skill_md(), **self._kiste.laden(str(name)).kurz()})

    def skill_entfernen(self, name: str) -> dict:
        def go():
            if not self._kiste.entfernen(str(name)):
                raise app_core.AppError("SKILL_FEHLT", "diesen Skill gibt es nicht")
            return {"skills": self._kiste.liste()}
        return self._guarded("skill_entfernen", go, "Skill entfernt.")

    def skill_exportieren(self, name: str) -> dict:
        def go():
            ziel = Path.home() / "Downloads"
            p = self._kiste.exportieren(str(name), ziel if ziel.is_dir() else Path.home())
            return {"pfad": str(p)}
        r = self._guarded("skill_exportieren", go)
        if r["ok"]:
            r["text"] = f"Als ZIP gespeichert (SKILL.md-Format, passt auch für Claude, Codex, Cursor): {r['daten']['pfad']}"
        return r

    def skill_importieren(self) -> dict:
        def go():
            p = self._datei_waehlen(("ZIP oder SKILL.md (*.zip;*.md)", "Alle Dateien (*.*)"))
            neu = self._kiste.importieren(p)
            return {"neu": [b.kurz() for b in neu], "skills": self._kiste.liste()}
        r = self._guarded("skill_importieren", go)
        if r["ok"]:
            n = len(r["daten"]["neu"])
            namen = ", ".join(b["name"] for b in r["daten"]["neu"])
            r["text"] = f"1 Skill importiert: {namen}" if n == 1 else f"{n} Skills importiert: {namen}"
        return r

    def gespraech_skill(self, kennung: str, name: str) -> dict:
        def go():
            if name:
                self._kiste.laden(str(name))
            return self._ablage.skill_setzen(str(kennung), str(name or "")).to_json_dict()
        return self._guarded("gespraech_skill", go, f"Skill „{name}“ gilt jetzt für dieses Gespräch." if name else "Kein Skill mehr für dieses Gespräch.")

    def skill_immer(self, name: str, an: bool) -> dict:
        def go():
            self._kiste.immer_setzen(str(name), bool(an))
            return {"skills": self._kiste.liste(), "immer": self._kiste.immer()}
        return self._guarded("skill_immer", go, f"„{name}“ gilt jetzt in jedem Gespräch." if an else f"„{name}“ gilt nur noch, wenn du ihn wählst.")


    def platzl_stand(self) -> dict:
        return self._guarded("platzl_stand", self._platzl.stand)

    def platzl_verbinden(self) -> dict:
        def go():
            adresse = self._platzl.verbinden_start()
            webbrowser.open(adresse)
            return {"adresse": adresse}
        return self._guarded("platzl_verbinden", go, "Im Browser öffnet sich das Platzl. Dort auf „Autorisieren“ tippen, dann geht es hier weiter.")

    def platzl_abholen(self) -> dict:
        return self._guarded("platzl_abholen", lambda: {"status": self._platzl.abholen(), **self._platzl.stand()})

    def platzl_trennen(self) -> dict:
        return self._guarded("platzl_trennen", lambda: (self._platzl.trennen(), self._platzl.stand())[1], "Vom Platzl getrennt.")

    def platzl_kategorien(self) -> dict:
        return self._guarded("platzl_kategorien", lambda: {"kategorien": self._platzl.kategorien()})

    def platzl_themen(self, slug: str = "", kategorie: int = 0) -> dict:
        return self._guarded("platzl_themen", lambda: {"themen": self._platzl.themen(str(slug or ""), int(kategorie or 0))})

    def platzl_thema(self, thema: int) -> dict:
        return self._guarded("platzl_thema", lambda: self._platzl.thema(int(thema)))

    def platzl_schreiben(self, titel: str, text: str, kategorie, thema) -> dict:
        def go():
            return self._platzl.schreiben(titel=str(titel or ""), text=str(text or ""), kategorie=int(kategorie) if kategorie else None,
                                          thema=int(thema) if thema else None)
        return self._guarded("platzl_schreiben", go, "Steht im Platzl.")

    def platzl_skills(self) -> dict:
        def go():
            kat = next((k for k in self._platzl.kategorien() if k["slug"] == "skills"), None)
            if kat is None:
                return {"skills": [], "hier": {}}
            hier = {b["quelle"].split("#", 1)[1]: b["name"] for b in self._kiste.liste() if str(b.get("quelle", "")).startswith("platzl#")}
            return {"skills": self._platzl.themen("skills", kat["id"]), "hier": hier, "kategorie": kat["id"]}
        return self._guarded("platzl_skills", go)

    def platzl_skill_holen(self, thema: int) -> dict:
        def go():
            roh, _titel = self._platzl.skill_text(int(thema))
            b = skills.lesen(roh, quelle=f"platzl#{int(thema)}")
            try:
                alt = self._kiste.laden(b.name)
            except app_core.AppError:
                alt = None
            if alt is not None and not str(alt.quelle).startswith("platzl#"):
                raise app_core.AppError("SKILL_NAME", f"du hast schon einen eigenen Skill „{b.name}“; der bleibt, wie er ist")
            gleich = alt is not None and alt.text == b.text
            self._kiste.speichern(b)
            return {"skill": b.kurz(), "skills": self._kiste.liste(), "wie": "gleich" if gleich else ("aktualisiert" if alt else "neu")}
        r = self._guarded("platzl_skill_holen", go)
        if r["ok"]:
            wie, name = r["daten"]["wie"], r["daten"]["skill"]["name"]
            r["text"] = {"neu": f"Skill „{name}“ übernommen. Wähle ihn neben dem Eingabefeld.", "aktualisiert": f"Skill „{name}“ neu geladen.",
                         "gleich": f"Skill „{name}“ ist schon aktuell."}[wie]
        return r

    def platzl_skill_entwurf(self, name: str) -> dict:
        def go():
            b = self._kiste.laden(str(name))
            md = b.als_skill_md().strip()
            zaun = "~~~~" if "```" in md else "```"
            kat = next((k for k in self._platzl.kategorien() if k["slug"] == "skills"), None)
            text = (f"{b.beschreibung}\n\nSo verwendest du ihn: in der KIplatz-App bei diesem Thema „Skill verwenden“, im Programm unter Skills "
                    f"„Aus dem Platzl“ übernehmen.\n\n{zaun}\n{md}\n{zaun}\n")
            return {"titel": f"Skill: {b.name}"[:200], "text": text, "kategorie": kat["id"] if kat else None}
        return self._guarded("platzl_skill_entwurf", go)


    def gespraech_ordner_waehlen(self, kennung: str) -> dict:
        def go():
            if self._window is None:
                raise app_core.AppError("DIALOG", "ohne Fenster gibt es keinen Ordnerdialog")
            import webview
            r = self._window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
            if not r:
                raise app_core.AppError("ABBRUCH", "kein Ordner gewählt")
            p = ordner_aufgaben.pruefen(Path(str(r[0] if isinstance(r, (list, tuple)) else r)))
            if p == self._core.base_dir.resolve() or self._core.base_dir.resolve() in p.parents:
                raise app_core.AppError("ORDNER_EIGEN", "den Datenordner des Programms selbst bitte nicht freigeben")
            k = str(kennung) or self._ablage.neu().kennung
            g = self._ablage.ordner_setzen(k, str(p))
            _log(self._core, f"OK ordner_freigegeben {app_core._mask(str(p))}")
            return {"gespraech": g.to_json_dict(), "dateien": ordner_aufgaben.uebersicht(p)}
        r = self._guarded("gespraech_ordner_waehlen", go)
        if r["ok"]:
            n = sum(1 for d in r["daten"]["dateien"] if d["lesbar"])
            ordner = Path(r['daten']['gespraech']['ordner']).name
            r["text"] = (f"Ordner „{ordner}“ freigegeben: 1 lesbare Datei. KIplatz liest daraus, was zur Frage passt, und ändert nichts; Antworten speicherst du mit einem Klick hinein." if n == 1
                         else f"Ordner „{ordner}“ freigegeben: {n} lesbare Dateien. KIplatz liest daraus, was zur Frage passt, und ändert nichts; Antworten speicherst du mit einem Klick hinein.")
        return r

    def gespraech_ordner_entfernen(self, kennung: str) -> dict:
        return self._guarded("gespraech_ordner_entfernen", lambda: self._ablage.ordner_setzen(str(kennung), "").to_json_dict(), "Der Ordner ist nicht mehr freigegeben. Es wurde nichts darin verändert.")

    def gespraech_ordner_dateien(self, kennung: str) -> dict:
        def go():
            g = self._ablage.laden(str(kennung))
            return ordner_aufgaben.uebersicht(Path(g.ordner)) if g.ordner else []
        return self._guarded("gespraech_ordner_dateien", go)

    def gespraech_in_ordner_speichern(self, kennung: str, nummer: int, name: str) -> dict:
        def go():
            g = self._ablage.laden(str(kennung))
            if not g.ordner:
                raise app_core.AppError("ORDNER_FEHLT", "für dieses Gespräch ist kein Ordner freigegeben")
            n = int(nummer)
            if not 0 <= n < len(g.nachrichten) or g.nachrichten[n].get("rolle") != "assistant":
                raise app_core.AppError("NACHRICHT", "diese Antwort gibt es nicht")
            ziel = ordner_aufgaben.speichern(Path(g.ordner), str(name), str(g.nachrichten[n].get("text", "")))
            _log(self._core, f"OK ordner_gespeichert {ziel.name}")
            return {"datei": ziel.name, "ordner": Path(g.ordner).name}
        r = self._guarded("gespraech_in_ordner_speichern", go)
        if r["ok"]:
            r["text"] = f"Gespeichert als „{r['daten']['datei']}“ im Ordner „{r['daten']['ordner']}“."
        return r

    def _datei_waehlen(self, file_types: tuple) -> Path:
        if self._window is None:
            raise app_core.AppError("DIALOG", "ohne Fenster gibt es keinen Dateidialog")
        import webview
        r = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        if not r:
            raise app_core.AppError("ABBRUCH", "keine Datei gewählt")
        return Path(str(r[0] if isinstance(r, (list, tuple)) else r))


    def gespraeche_importieren(self) -> dict:
        def go():
            p = self._datei_waehlen(("Export (*.json;*.zip;*.md;*.txt)", "Alle Dateien (*.*)"))
            gefunden = gespraeche_import.erkennen(p)
            neu = self._ablage.importieren(gefunden)
            return {"anzahl": len(neu), "herkunft": gefunden[0].herkunft if gefunden else "", "liste": self._ablage.liste()}
        r = self._guarded("gespraeche_importieren", go)
        if r["ok"]:
            d = r["daten"]
            if d["anzahl"] == 1:
                r["text"] = f"1 Gespräch von {d['herkunft']} übernommen, im Projekt „Import {d['herkunft']}“ in der Leiste."
            else:
                r["text"] = f"{d['anzahl']} Gespräche von {d['herkunft']} übernommen, im Projekt „Import {d['herkunft']}“ in der Leiste." if d["anzahl"] else "In der Datei war kein Gespräch."
        return r

    def gespraeche_projekte(self) -> dict:
        return self._guarded("gespraeche_projekte", self._ablage.projekte)

    def community_rueckmeldungen(self) -> dict:
        return self._guarded("community_rueckmeldungen", lambda: self._community.rueckmeldungen())

    def gespraech_loeschen(self, kennung: str) -> dict:
        return self._guarded("gespraech_loeschen", lambda: self._ablage.loeschen(str(kennung)), "Gespräch gelöscht (liegt noch im Ordner „papierkorb“ in deinem Datenordner).")

    def nachpruefen(self, kennung: str) -> dict:
        g = self._ablage.laden(str(kennung))
        letzte = next((n["text"] for n in reversed(g.nachrichten) if n.get("rolle") == "user"), "")
        if not letzte:
            return {"ok": False, "code": "GESPRAECH_LEER", "text": "In diesem Gespräch gibt es noch keine Frage zum Nachprüfen."}
        return self.frage(kennung, letzte, frisch=True)

    def _antwort_melden(self, dauer_s: float, wortstuecke: int) -> None:
        if self._community.geraet() is None:
            return
        def go() -> None:
            try:
                messung = messwerte.messen()
            except Exception:
                messung = {}
            try:
                self._community.antwort_gezaehlt(float(dauer_s or 0), int(wortstuecke or 0), messung)
            except app_core.AppError as exc:
                _log(self._core, f"HINWEIS antwort_gezaehlt: {exc.code}")
        threading.Thread(target=go, name="antwort-melden", daemon=True).start()

    def nochmal_vorbereiten(self, kennung: str) -> dict:
        def go():
            fund: dict = {}

            def weg(g):
                n = g.nachrichten
                if len(n) < 2 or n[-1].get("rolle") != "assistant" or n[-2].get("rolle") != "user":
                    raise app_core.AppError("NOCHMAL_NICHT", "nochmal fragen geht nur bei der letzten Antwort")
                fund["frage"] = str(n[-2].get("text") or "")
                fund["vorige"] = str(((n[-1].get("lieferschein") or {}).get("auftrag")) or "")[:32]
                del n[-2:]
            g = self._ablage.aendern(str(kennung), weg)
            if fund["vorige"]:
                self._nochmal_vorige[str(kennung)] = fund["vorige"]
            else:
                self._nochmal_vorige.pop(str(kennung), None)
            return {"frage": fund["frage"], "gespraech": g.to_json_dict()}
        return self._guarded("nochmal_vorbereiten", go)

    def frage_dateien(self, kennung: str, text: str) -> dict:
        return self.frage(kennung, text, modus="dateien")

    def frage_netz(self, kennung: str, text: str) -> dict:
        return self.frage(kennung, text, modus="netz")

    def _eigene_dateifrage(self, g, text: str, hinweis_seite) -> dict:
        self._ablage.anhaengen(g, "user", text)
        if self._zuhause.daheim() is not None and self._community.geraet() is not None:
            nachrichten = [{"role": "user", "content": text}]
            try:
                k = self._community.frage_stellen(nachrichten, zuhause=self._zuhause.unterschrift_fuer(nachrichten, modus="dateien"))
                d = self._community_warten(k, time.time(), vermittlung_basis.NUR_HAUS_WARTEN_S + 10, hinweis_seite, daheim=True)
                antwort_text, ls = str(d.get("text") or ""), dict(d.get("lieferschein") or {})
            except app_core.AppError as exc:
                antwort_text, ls = exc.detail[:1].upper() + exc.detail[1:], self._schein_ohne_modell("nicht erreicht")
        else:
            antwort_text, ls = self._dateien_antwort(text)
            ls["geraet"] = "dieses Gerät"
        self._ablage.anhaengen(g, "assistant", antwort_text, lieferschein=ls)
        hinweis_seite("")
        return {"text": antwort_text, "lieferschein": ls, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}

    def tippt(self) -> dict:
        try:
            self._rechen.tippen()
        except Exception as exc:
            _log(self._core, f"INFO tippt: {type(exc).__name__}")

        threading.Thread(target=self._beim_tippen_wecken, name="tippt-wecken", daemon=True).start()
        return {"ok": True}

    def _beim_tippen_wecken(self) -> bool:
        try:
            ki = self._ki
            if (ki.bereit() or getattr(ki, "gesperrt", "") or getattr(ki, "phase", "") in ("laden", "fehler") or self._ki_von_hand_aus
                    or not self.ki_auto() or not self._kann_fuer_andere_antworten() or not (ki.wahl and ki.ordner.modell_da(ki.wahl.modell))):
                return False
            if self.fragt_community():
                return False
            if ki.einschalten():
                _log(self._core, "OK tippt: das Modell wird schon beim Tippen geladen")
                return True
        except Exception as exc:
            _log(self._core, f"INFO tippt wecken: {type(exc).__name__}")
        return False

    def frage(self, kennung: str, text: str, *, ki_starten: bool = True, frisch: bool = False, modus: str = "") -> dict:
        knopf = frisch

        def go():
            vorher = getattr(_SCHRITT, "fn", None)
            if self._window is not None:
                _SCHRITT.fn = lambda t: self._js(f"app.schritt({json.dumps(t, ensure_ascii=False)})")
            _NETZ.an = modus == "netz"
            try:
                return frage_ohne_schritt()
            finally:
                _SCHRITT.fn = vorher
                _NETZ.an = False
                _ABSICHT.wert = None
                _FACH.wert = None
                ki_laufzeit.original_setzen("")
                _SUCHLAUF.stand = None

        def frage_ohne_schritt():
            nonlocal frisch
            g = self._ablage.laden(str(kennung))
            hinweis_seite = (lambda t: self._js(f"app.hinweis({json.dumps(t, ensure_ascii=False)})")) if self._window is not None else (lambda t: None)
            erk = self._gedaechtnis.befehl(str(text))
            if erk is not None:
                self._ablage.anhaengen(g, "user", str(text), intern=True)
                antwort_g = self._gedaechtnis.anwenden(erk, gedaechtnis.sprache(str(text)))
                ls_g = {"modell": "gemerkt, ohne Modell", "geraet": "dieses Gerät", "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
                        "credits": "nichts verrechnet (Gedächtnis)", "quellen": "Gedächtnis auf diesem Gerät; nichts davon verlässt den Rechner.",
                        "quellen_liste": [], "gemacht": "gemerkt", "erfunden": "nichts, es wurde nur gemerkt", "pruefung": pruefung.pruefen("", []).kurz(),
                        "guthaben_vorher": self._kontobuch.stand().guthaben}
                self._ablage.anhaengen(g, "assistant", antwort_g, lieferschein=ls_g, intern=True)
                _log(self._core, f"OK gedaechtnis {erk[0]}")
                return {"text": antwort_g, "lieferschein": ls_g, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}
            self.abbruch_gewuenscht = False
            if modus == "dateien":
                return self._eigene_dateifrage(g, str(text), hinweis_seite)
            if modus != "netz" and nachschauen.ist_dateifrage(str(text)):
                if self._dateien_haken_sichtbar():
                    self._ablage.anhaengen(g, "user", str(text))
                    ls = self._schein_ohne_modell("nachgefragt")
                    ls["geraet"] = "dieses Gerät"
                    self._ablage.anhaengen(g, "assistant", DATEI_HAKEN_PC, lieferschein=ls)
                    return {"text": DATEI_HAKEN_PC, "lieferschein": ls, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}
                return self._eigene_dateifrage(g, str(text), hinweis_seite)
            gemeinschaft = None
            ersatz_grund = ""
            self.abbruch_gewuenscht = False
            abbruch = getattr(self._ki.server, "abbruch", None)
            if abbruch is not None:
                abbruch.clear()
            _FACH.wert = fachgebiete = self._fachgebiete()
            if ki_starten and self.fragt_community() and hausordnung.pruefen(str(text)).ok:
                try:
                    vorige = self._nochmal_vorige.pop(str(kennung), "")
                    sk_mit, _sk_weg = skills.passend(self._kiste.fuer_gespraech(g.skill), erster_immer=False)
                    sk_reise = skills.als_eine(sk_mit) if sk_mit else None
                    gemeinschaft = self._community_antwort(g.fuer_modell() + [{"role": "user", "content": str(text)}], hinweis_seite,
                                                           **({"vorige": vorige} if vorige else {}),
                                                           **({"skill": {"name": sk_reise.name, "text": sk_reise.als_skill_md()}} if sk_reise else {}),
                                                           **({"fachgebiete": fachgebiete} if fachgebiete else {}))
                except app_core.AppError as exc:
                    if exc.code == "ABGEBROCHEN":
                        raise
                    _log(self._core, f"ABGELEHNT community_antwort: {exc.code}: {exc.detail}")
                    hinweis_seite(f"{exc.detail}; dieses Gerät antwortet selbst, das dauert hier etwa eine Minute.")
                    ersatz_grund = exc.detail
            if gemeinschaft is not None:
                self._ablage.anhaengen(g, "user", str(text))
                admin = self._community.ist_admin()
                ls = dict(gemeinschaft.get("lieferschein") or {})
                fertig = isinstance(ls.get("aus_speicher"), dict)
                stand = self._kontobuch.stand() if (admin or fertig) else self._kontobuch.frage(geraet=self._geraet_name)
                ls.setdefault("modell", "KIplatz")
                ls["geraet"] = (str(gemeinschaft.get("von") or "aus dem Antwort-Speicher der Community") if fertig
                                else f"{gemeinschaft.get('von', 'ein PC der Community')} hat deine Antwort erarbeitet (Community)")
                ls["dauer_s"] = round(float(gemeinschaft.get("dauer_s", 0) or 0), 1)
                ls["credits"] = (f"nichts verrechnet: die Antwort kam fertig aus dem Antwort-Speicher, Stand {stand.guthaben}" if fertig and not admin
                                 else ("Admin, unbegrenzt" if admin else f"1 Credit für diese Frage, Stand {stand.guthaben}") + ("" if fertig else f"; {gemeinschaft.get('von', 'der Rechner')} hat 1 verdient"))
                ls.setdefault("quellen", "")
                ls.setdefault("quellen_liste", [])
                ls.setdefault("gemacht", "geantwortet")
                ls.setdefault("erfunden", "")
                ls.setdefault("pruefung", pruefung.pruefen("", []).kurz())
                if gemeinschaft.get("auftrag"):
                    ls["auftrag"] = str(gemeinschaft["auftrag"])[:32]
                ls["guthaben_vorher"] = stand.guthaben
                antwort_text = str(gemeinschaft.get("text") or "(keine Antwort erhalten)")
                self._ablage.anhaengen(g, "assistant", antwort_text, lieferschein=ls)
                hinweis_seite("")
                return {"text": antwort_text, "lieferschein": ls, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}
            if getattr(self._ki, "probe_geladen", False):
                raise app_core.AppError("PROBE", "Dieser PC prüft gerade eine nachtrainierte Fassung. Bitte frag in einer halben Stunde noch einmal.")
            self._ki_bereit_machen(einschalten=ki_starten)
            self._ablage.anhaengen(g, "user", str(text))
            admin = self._community.ist_admin()
            stand_vorher = self._kontobuch.stand() if admin else self._kontobuch.frage(geraet=self._geraet_name)
            wahl = self._ki.wahl
            fern = self._ki.quelle() == "heimnetz"
            stueckweise = self._window is not None and not self._schwach()
            on_token = (lambda piece: self._js(f"app.token({json.dumps(piece, ensure_ascii=False)})")) if stueckweise else None
            if self._window is not None and not stueckweise:
                hinweis_seite("Einen Moment, deine Antwort wird auf diesem Gerät erstellt …")
                zaehler = {"n": 0, "t": time.time()}

                def zaehlen(piece: str) -> None:
                    zaehler["n"] += 1
                    if time.time() - zaehler["t"] >= 1.5:
                        zaehler["t"] = time.time()
                        hinweis_seite(f"Deine Antwort entsteht auf diesem Gerät … {zaehler['n']} Wortstücke")
                on_token = satzweise.Sammler(lambda text: self._js(f"app.token({json.dumps(text, ensure_ascii=False)})"), mit=zaehlen)
            am_prozessor = wahl is not None and wahl.geraet is None and not fern
            max_tokens = 320 if am_prozessor else None
            englisch_gefragt = not fern and antwortsprache.frage_sprache(str(text)) == "en"
            nachrichten_de = None

            def ohne_modell(antwort: str, gemacht: str, woher: str, fertig_en: str = "") -> dict:
                if not admin:
                    self._kontobuch.antwort(geraet=self._geraet_name)
                lieferschein = {"modell": f"{gemacht}, ohne Modell", "geraet": self._ki.geraet_de(), "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0,
                                "credits": "Admin, unbegrenzt" if admin else f"nichts verrechnet ({gemacht})", "quellen": woher,
                                "quellen_liste": [], "gemacht": gemacht, "erfunden": f"nichts, es wurde nur {gemacht}", "pruefung": pruefung.pruefen("", []).kurz(),
                                "guthaben_vorher": stand_vorher.guthaben}
                if englisch_gefragt and fertig_en:
                    antwort = fertig_en
                elif englisch_gefragt:
                    antwort, lieferschein = antwortsprache.antwort_uebersetzen(self._ki.server.frage, antwort, lieferschein, log=lambda z: _log(self._core, z))
                self._ablage.anhaengen(g, "assistant", antwort, lieferschein=lieferschein)
                return {"text": antwort, "lieferschein": lieferschein, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}
            b = hausordnung.pruefen(str(text))
            if not b.ok:
                _log(self._core, f"ABGELEHNT HAUSORDNUNG frage: {b.grund}")
                return ohne_modell(f"Das gehört nicht in diese Community ({b.grund}). {hausordnung.HAUSORDNUNG}", "abgelehnt", "Platzordnung der Community.")
            ab = absicht.letzte(g.fuer_modell())
            _ABSICHT.wert = ab
            frisch = frisch or ab.frisch
            vorab = self._antwort_vorab(g.fuer_modell(), ab=ab, en_frage=englisch_gefragt, waehrung=not fern and not g.anhaenge,
                                        bezug_an=not fern and not g.anhaenge and not getattr(g, "ordner", None), uebersetzen=not fern)
            if vorab is not None:
                return ohne_modell(*vorab[:3], fertig_en=vorab[3])
            if englisch_gefragt and not ab.antwort:
                hinweis_seite("Die Frage ist auf Englisch, die Antwort kommt auf Englisch …")
                try:
                    nachrichten_de = antwortsprache.frage_auf_deutsch(self._ki.server.frage, g.fuer_modell())
                    on_token = None
                except Exception as exc:
                    _log(self._core, f"FEHLER frage_auf_deutsch: {type(exc).__name__}")
                if nachrichten_de:
                    ki_laufzeit.original_setzen(str(text))
            fm = (lambda: nachrichten_de) if nachrichten_de else g.fuer_modell
            _SUCHLAUF.stand = {"runde": 0, "gesucht": [], "gelesen": set()}
            _FREMD.texte = []
            def vorspann_bauen() -> tuple[str, str, list[dict] | None]:
                anh = ordn = sk = ged_t = bild_satz = ""
                hinweise: list[str] = []
                if g.anhaenge and not fern:
                    anh = anhaenge.vorspann(g.anhaenge)
                    hinweise.append("1 Datei aus dem Gespräch mitgelesen." if len(g.anhaenge) == 1 else f"{len(g.anhaenge)} Dateien aus dem Gespräch mitgelesen.")
                if ersatz_grund:
                    hinweise.append(f"Kein Rechner der Community konnte übernehmen ({ersatz_grund}); dieses Gerät hat mit seinem eigenen Modell geantwortet.")
                if g.ordner and not fern:
                    try:
                        alle = ordner_aufgaben.uebersicht(Path(g.ordner))
                        gelesen = ordner_aufgaben.auswahl(Path(g.ordner), str(text))
                        for d in gelesen:
                            b_o = hausordnung.pruefen(d["text"][:20_000])
                            if not b_o.ok:
                                raise app_core.AppError("HAUSORDNUNG", f"die Datei „{d['name']}“ im Ordner: {b_o.text}")
                        ordn = ordner_aufgaben.vorspann(Path(g.ordner).name, gelesen, alle)
                        hinweis = (f"Aus dem Ordner „{Path(g.ordner).name}“ mitgelesen: " + ", ".join(d["name"] for d in gelesen) + "." if gelesen
                                   else f"Ordner „{Path(g.ordner).name}“ freigegeben ({len(alle)} Dateien), für diese Frage keine gelesen.")
                        hinweise.append(hinweis)
                        _log(self._core, f"OK ordner_gelesen {len(gelesen)} von {len(alle)}")
                    except app_core.AppError as exc:
                        if exc.code == "HAUSORDNUNG":
                            raise
                        _log(self._core, f"ABGELEHNT ordner: {exc.code}: {exc.detail}")
                        hinweise.append(f"Der freigegebene Ordner war nicht lesbar ({exc.detail}).")
                if not fern:
                    sk_mit, sk_weg = skills.passend(self._kiste.fuer_gespraech(g.skill))
                    if sk_mit:
                        sk = skills.vorspann_mehrere(sk_mit)
                    if sk_mit or sk_weg:
                        hinweise.append(skills.hinweis_angewendet(sk_mit, sk_weg))
                    ged_t, n_ged = self._gedaechtnis.anhaengen("")
                    if n_ged:
                        hinweise.append(f"Gedächtnis: {n_ged} Einträge mitgegeben.")
                    else:
                        ged_t = ""
                nachrichten_modell = list(fm())
                bilder = self._ablage.bilder_fuer_modell(g) if any(x.get("art") == "bild" for x in g.anhaenge) else []
                if bilder and not fern and not getattr(self._ki.server, "bilder", False) and self._ki.mit_bildern_einschalten():
                    hinweis_seite("Der Bild-Zusatz wird geladen, das dauert einmal ein paar Sekunden …")
                    self._ki_bereit_machen(einschalten=True)
                if bilder and not fern:
                    if getattr(self._ki.server, "bilder", False) and nachrichten_modell and nachrichten_modell[-1]["role"] == "user":
                        nachrichten_modell[-1] = {"role": "user", "content": [{"type": "text", "text": nachrichten_modell[-1]["content"]}] + bilder}
                        hinweise.append("1 Bild angeschaut." if len(bilder) == 1 else f"{len(bilder)} Bilder angeschaut.")
                    else:
                        bild_satz = ("Die Person hat ein Bild mitgeschickt, aber dieses Gerät kann Bilder nicht anschauen (der Bild-Zusatz läuft nur auf einer Grafikkarte). "
                                     "Sag das in einem Satz und beantworte, was ohne das Bild geht.")
                return "\n\n".join(t for t in (bild_satz, ged_t, sk, ordn, anh) if t), " ".join(h for h in hinweise if h), nachrichten_modell
            gemeldet: list[str] = []

            def melden(t: str) -> None:
                gemeldet.append(t)
                hinweis_seite(t)
            try:
                antwort_text, lieferschein, a = self._antwort_kern(
                    fm(), ab=ab, fuer="dich", frisch=frisch, privat=True, fern=fern,
                    kopie=None if (fern or g.anhaenge or self._kiste.fuer_gespraech(g.skill)) else "eigen",
                    vorspann=vorspann_bauen, strom=_FensterStrom(self._js, on_token) if self._window is not None else None,
                    melden=melden, knapp=am_prozessor, max_tokens=max_tokens, kurz=am_prozessor, prozessor_rueckfall=not fern,
                    knopf=knopf, nachsuche_erlaubt=not g.anhaenge and not getattr(g, "ordner", None), geraet=self._ki.geraet_de())
            except app_core.AppError:
                if not admin:
                    self._kontobuch.antwort(geraet=self._geraet_name)
                raise
            if gemeldet:
                hinweis_seite("")
            if a is None and "aus_speicher" in lieferschein:
                ls_f = lieferschein
                ls_f.update({"guthaben_vorher": stand_vorher.guthaben,
                             "credits": "Admin, unbegrenzt" if admin else f"nichts verrechnet: die Antwort kam fertig aus dem Antwort-Speicher, Stand {stand_vorher.guthaben}"})
                if englisch_gefragt:
                    antwort_text, ls_f = antwortsprache.antwort_uebersetzen(self._ki.server.frage, antwort_text, ls_f, log=lambda z: _log(self._core, z))
                self._ablage.anhaengen(g, "assistant", antwort_text, lieferschein=ls_f)
                return {"text": antwort_text, "lieferschein": ls_f, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}
            if a is None:
                return ohne_modell(antwort_text, str(lieferschein.get("gemacht", "geantwortet")), str(lieferschein.get("quellen", "")), fertig_en=str(lieferschein.get("_en", "")))
            stand = self._kontobuch.stand() if fern else self._kontobuch.antwort(geraet=self._geraet_name)
            lieferschein["credits"] = (("Admin, unbegrenzt" if admin else f"1 Credit für diese Frage, Stand {stand.guthaben}")
                                       + (f"; {self._ki.fern_name()} hat 1 verdient" if fern else ""))
            lieferschein["guthaben_vorher"] = stand_vorher.guthaben
            if englisch_gefragt:
                hinweis_seite("Die Antwort wird ins Englische übertragen …")
                antwort_text, lieferschein = antwortsprache.antwort_uebersetzen(self._ki.server.frage, antwort_text, lieferschein,
                                                                               log=lambda z: _log(self._core, z), frage=str(text))
                antwort_text, lieferschein = self.eigene_worte_englisch(antwort_text, lieferschein)
                hinweis_seite("")
            self._ablage.anhaengen(g, "assistant", antwort_text, lieferschein=lieferschein)
            if not stueckweise:
                hinweis_seite("")
            self._antwort_melden(a.dauer_s, a.completion_tokens)
            return {"text": antwort_text, "lieferschein": lieferschein, "gespraech": g.to_json_dict(), "credits": self._credits_dict()}

        def mit_vorrang():
            self._rechen.vorrang_beginn()
            try:
                return go()
            finally:
                self._rechen.vorrang_ende()
        return self._guarded("frage", mit_vorrang)


    def community(self) -> dict:
        def go():
            first = self._core.load_first_start()
            mitglieder = [{"name": self._geraet_name, "du": True, "rolle": app_core.ROLE_LABELS_DE[first.role] if first else "?", "lauf": self._core.run_state().value}]
            for g in self._dienst.geraete.liste():
                mitglieder.append({"name": g["name"], "du": False, "rolle": f"fragt KIplatz hier ({g['fragen']} Fragen)", "lauf": "ACTIVE" if g["zuletzt"] else "STOPPED"})
            v = self._ki.verbindung.daten()
            if v is not None:
                mitglieder.append({"name": v.name, "du": False, "rolle": "beantwortet deine Fragen im Heimnetz", "lauf": "ACTIVE" if self._ki.quelle() == "heimnetz" and self._ki.bereit() else "STOPPED"})
            geraet = self._community.geraet()
            rangliste, fehler = None, None
            try:
                rangliste = self._community.rangliste()
                fehler = self._community.fehler_liste()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT community rangliste/fehler: {exc.code}: {exc.detail}")
            not_aus = {"an": False, "grund": ""}
            try:
                not_aus = dict((self._community.rechenstand().get("not_aus") or {})) or not_aus
            except (app_core.AppError, ValueError, TypeError, AttributeError):
                pass
            hinweis = [f"Dieses Gerät ist als „{geraet['name']}“ bei der Community angemeldet (seit {geraet['seit'][:10]})." if geraet else "Dieses Gerät ist bei der Community noch nicht angemeldet.",
                       "Bis jetzt bist nur du hier." if len(mitglieder) == 1 else "Geräte aus deinem Heimnetz: Koppeln und entfernen geht unter „Einstellungen“."]
            return {
                "credits": self._credits_dict(),
                "mitglieder": mitglieder,
                "rangliste": rangliste, "fehler": fehler,
                "hinweis": " ".join(hinweis), "hinweis_saetze": hinweis,
                "heimnetz": self._heimnetz_dict(),
                "mitglied": geraet is not None, "admin": self._community.ist_admin(),
                "not_aus": not_aus,
                "konto": self._konto_dict(),
            }
        return self._guarded("community", go)


    def _konto_dict(self) -> dict | None:
        k = self._ki.einstellung().get("konto")
        return k if isinstance(k, dict) and k.get("name") else None

    def _konto_fertig(self, id_token: str) -> None:
        a = self._community.konto_anmelden(id_token)
        k = a.get("konto") if isinstance(a, dict) else None
        if not isinstance(k, dict) or not k.get("name"):
            raise app_core.AppError("KONTO_ANTWORT", "der Community-Server hat das Konto nicht bestätigt")
        self._ki.einstellung_setzen(konto={"name": str(k["name"])[:60], "sub": str(k.get("sub", ""))[:200]})
        _log(self._core, f"OK konto angemeldet als {k['name']}")

    def konto_anmelden_start(self) -> dict:
        def go():
            if self._community.geraet() is None:
                raise app_core.AppError("KONTO_GERAET", "zuerst muss dieses Gerät zur Community dazukommen; danach kannst du dein Konto anmelden")
            if self._konto_anmeldung is not None and self._konto_anmeldung.laeuft:
                return self._konto_anmeldung.stand()
            konfig = self._community.konto_anmeldung()
            for feld in ("authorize", "token"):
                if not str(konfig.get(feld, "")).startswith(KONTO_ISSUER.rstrip("/") + "/"):
                    raise app_core.AppError("KONTO_ISSUER", f"die Anmeldestelle {str(konfig.get(feld, ''))[:60]} ist nicht die Werkstatt von KIplatz; Anmeldung abgebrochen")
            self._konto_anmeldung = konto_basis.Anmeldung(konfig, self._konto_fertig)
            self._konto_anmeldung.start()
            return self._konto_anmeldung.stand()
        return self._guarded("konto_anmelden_start", go, "Dein Browser öffnet die Anmeldeseite von KIplatz. Melde dich dort an, danach geht es hier weiter.")

    def konto_stand(self) -> dict:
        def go():
            lauf = self._konto_anmeldung.stand() if self._konto_anmeldung else {"laeuft": False, "fertig": False, "fehler": None, "adresse": ""}
            return {**lauf, "konto": self._konto_dict()}
        return self._guarded("konto_stand", go)

    def konto_qr_start(self) -> dict:
        def go():
            if self._community.geraet() is None:
                raise app_core.AppError("KONTO_GERAET", "zuerst muss dieses Gerät zur Community dazukommen; danach kannst du dein Konto anmelden")
            d = self._community.pc_qr_start()
            code, adresse = str(d.get("code", "")), str(d.get("adresse", ""))
            if not re.fullmatch(r"[A-Za-z0-9_-]{32}", code) or adresse != "https://kiplatz.at/app/#pc=" + code:
                raise app_core.AppError("KONTO_ANTWORT", "der Community-Server hat keinen gültigen Code geschickt")
            import segno
            self._konto_qr = code
            return {"qr": segno.make(adresse, error="m").svg_data_uri(scale=5, border=2, dark="#1b1f1e", light="#ffffff"),
                    "gueltig_s": int(d.get("gueltig_s", 120))}
        return self._guarded("konto_qr_start", go)

    def konto_qr_stand(self) -> dict:
        def go():
            code = getattr(self, "_konto_qr", "")
            if not code:
                return {"status": "aus"}
            d = self._community.pc_qr_stand(code)
            st = str(d.get("status", ""))
            if st == "fertig":
                k = d.get("konto") if isinstance(d.get("konto"), dict) else {}
                if not k.get("name"):
                    raise app_core.AppError("KONTO_ANTWORT", "der Community-Server hat das Konto nicht bestätigt")
                self._ki.einstellung_setzen(konto={"name": str(k["name"])[:60], "sub": str(k.get("sub", ""))[:200]})
                _log(self._core, "OK konto angemeldet per QR-Code")
            if st != "wartet":
                self._konto_qr = ""
            return {"status": st if st in ("wartet", "fertig", "abgelaufen", "abgelehnt") else "abgelaufen",
                    "text": str(d.get("text", ""))[:200], "rest_s": int(d.get("rest_s", 0) or 0), "konto": self._konto_dict()}
        return self._guarded("konto_qr_stand", go)

    def konto_qr_abbrechen(self) -> dict:
        self._konto_qr = ""
        return {"ok": True, "text": "", "daten": None}

    def konto_anmelden_abbrechen(self) -> dict:
        def go():
            if self._konto_anmeldung is not None:
                self._konto_anmeldung.abbrechen()
            return {"laeuft": False}
        return self._guarded("konto_anmelden_abbrechen", go, "Abgebrochen.")

    def konto_abmelden(self) -> dict:
        def go():
            try:
                self._community.konto_abmelden()
            except app_core.AppError as exc:
                if exc.code != "COMMUNITY_GERAET":
                    raise
            self._ki.einstellung_setzen(konto=None)
            self._platzl.trennen()
            return {"konto": None}
        return self._guarded("konto_abmelden", go, "Abgemeldet. Dieses Gerät gehört zu keinem Konto mehr; Credits bleiben beim Gerät.")

    def _dateien_haken_sichtbar(self) -> bool:
        try:
            return self._zuhause.daheim() is not None or (self._zuhause.an() and bool(self._zuhause.liste()))
        except Exception:
            return False

    def _schein_ohne_modell(self, gemacht: str) -> dict:
        return {"modell": "ohne Modell", "geraet": "dein PC daheim", "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0, "quellen": "", "quellen_liste": [],
                "gemacht": gemacht, "erfunden": "nichts", "pruefung": pruefung.pruefen("", []).kurz()}

    def _dateien_antwort(self, frage: str) -> tuple[str, dict]:
        self._schritt("sucht in deinen Dateien …")
        englisch = antwortsprache.frage_sprache(frage) == "en"
        text, dateien = self._dateiliste.suchen(frage, self._geraet_name, englisch=englisch)
        schein = {**self._schein_ohne_modell("in deinen Dateien gesucht"), "zuhause": "mit_unterlagen", "dateien": dateien,
                  "geraet": f"{self._geraet_name}, dein PC daheim",
                  "quellen": "Names of the files in Documents, Pictures, Desktop, Downloads, Music, Videos and OneDrive on your PC; not searched on the internet."
                  if englisch else "Namen der Dateien in Dokumente, Bilder, Desktop, Downloads, Musik, Videos und OneDrive auf deinem PC; nicht im Internet gesucht."}
        _log(self._core, f"OK dateien: {len(dateien)} Treffer")
        return text, schein

    def _dateien_holen(self, z: dict) -> tuple[str, dict]:
        try:
            ids = [str(x)[:32] for x in (json.loads(str(z["nachrichten"][-1]["content"])).get("holen") or [])][:20]
        except (ValueError, TypeError, KeyError, AttributeError):
            ids = []
        schl = self._zuhause.schluessel_fuer(z["kid"])
        if not any(g["kid"] == z["kid"] and g["name"] != "Gerät" for g in self._zuhause.liste()):
            try:
                self._zuhause.abgleichen(self._community)
            except app_core.AppError:
                pass
        bereit, namen, spaeter = [], [], []
        alt, zu_gross, fehler = 0, [], []
        t0 = time.monotonic()
        for i in ids:
            if bereit and time.monotonic() - t0 > HOLEN_BUDGET_S:
                spaeter.append(i)
                continue
            e = self._dateiliste.datei(i)
            if e is None or schl is None:
                alt += 1
                continue
            try:
                if os.path.getsize(e.pfad) > zuhause.DATEI_HOECHSTENS:
                    zu_gross.append(e.name)
                    continue
                self._schritt(f"verschlüsselt „{e.name}“ und legt sie für dein Handy bereit …")
                daten = Path(e.pfad).read_bytes()
                token = self._community.zuhause_ablegen(z["kid"], zuhause.datei_verschluesseln(schl, i, daten))
            except (OSError, app_core.AppError) as exc:
                _log(self._core, f"ABGELEHNT zuhause holen: {type(exc).__name__}")
                fehler.append(e.name)
                continue
            bereit.append({"id": i, "name": e.name, "token": token, "groesse": len(daten), "art": dateisuche.art_der_datei(e.name)})
            namen.append(e.name)
        if namen:
            self._zuhause.geholt_merken(z["kid"], namen)
        _log(self._core, f"OK zuhause holen: {len(bereit)} Dateien bereit, {len(spaeter)} später, {alt + len(zu_gross) + len(fehler)} nicht")
        text = holen_satz(len(bereit), len(spaeter), alt, zu_gross, fehler)
        return text, {**self._schein_ohne_modell("für dein Handy bereitgelegt"), "zuhause": "mit_unterlagen", "abholen": bereit, "spaeter": spaeter}

    def datei_oeffnen(self, datei_id: str, zeigen: bool = False) -> dict:
        def go():
            e = self._dateiliste.datei(str(datei_id)[:32])
            if e is None:
                raise app_core.AppError("DATEI_WEG", "diese Liste ist abgelaufen; bitte noch einmal suchen")
            if zeigen:
                subprocess.Popen(["explorer.exe", "/select,", e.pfad])
            else:
                os.startfile(e.pfad)
            return {"name": e.name}
        return self._guarded("datei_oeffnen", go)

    def zuhause_holen(self, ids: list) -> dict:
        def go():
            d = self._zuhause.daheim_schluessel()
            if d is None or self._community.geraet() is None:
                raise app_core.AppError("ZUHAUSE_GERAET", "dieser Laptop ist mit keinem PC daheim gekoppelt")
            kid, schl = d
            ziel = Path.home() / "Downloads" / "Vom PC daheim"
            ziel.mkdir(parents=True, exist_ok=True)
            gespeichert, texte, offen = [], [], [str(x)[:32] for x in ids][:20]
            for _runde in range(HOLEN_RUNDEN):
                if not offen:
                    break
                nachrichten = [{"role": "user", "content": json.dumps({"holen": offen})}]
                k = self._community.frage_stellen(nachrichten, zuhause=self._zuhause.unterschrift_fuer(nachrichten, modus="holen"))
                a = self._community_warten(k, time.time(), vermittlung_basis.NUR_HAUS_WARTEN_S + 10, lambda t: None, daheim=True,
                                           warten_genommen=vermittlung_basis.FRIST_HOLEN_S + 30)
                ls = a.get("lieferschein") or {}
                offen = [str(x)[:32] for x in ls.get("spaeter") or []][:20]
                texte.append(str(a.get("text") or ""))
                gespeichert += self._holen_speichern(ziel, schl, ls.get("abholen") or [])
            return {"gespeichert": gespeichert, "text": texte[-1] if texte else ""}
        return self._guarded("zuhause_holen", go)

    def _holen_speichern(self, ziel: Path, schl: bytes, abholen: list) -> list[str]:
        gespeichert = []
        for e in abholen:
            daten = zuhause.datei_entschluesseln(schl, str(e["id"]), self._community.zuhause_abholen(str(e["token"])))
            name = re.sub(r'[\\/:*?"<>|]', "_", str(e.get("name") or "Datei"))[:180]
            p = ziel / name
            n = 1
            while p.exists():
                p = ziel / f"{Path(name).stem} ({n}){Path(name).suffix}"
                n += 1
            sicher_schreiben.roh(p, daten)
            gespeichert.append(p.name)
        return gespeichert


    def zuhause_stand(self) -> dict:
        def go():
            geraete, hinweis = None, ""
            if self._community.geraet() is not None:
                try:
                    geraete = self._zuhause.abgleichen(self._community)
                except app_core.AppError as exc:
                    hinweis = f"Community-Server gerade nicht erreichbar ({exc.detail})."
            return {"an": self._zuhause.an(), "geraete": self._zuhause.liste() if geraete is None else geraete, "daheim": self._zuhause.daheim(),
                    "verlauf": self._zuhause.verlauf()[:20],
                    "angemeldet": self._community.geraet() is not None, "hinweis": hinweis}
        return self._guarded("zuhause_stand", go)

    def zuhause_code(self) -> dict:
        def go():
            if self._community.geraet() is None:
                raise app_core.AppError("ZUHAUSE_GERAET", "dieser PC gehört noch nicht zur Community; zuerst oben beitreten")
            d = self._zuhause.code_erzeugen(self._community)
            try:
                import segno
                d["qr"] = segno.make(d["adresse"], error="m").svg_data_uri(scale=5, border=2, dark="#1b1f1e", light="#ffffff")
            except Exception as exc:
                _log(self._core, f"INFO qr nicht möglich: {type(exc).__name__}")
            return {"code": d["code"], "gilt_s": d["gilt_s"], "qr": d.get("qr", "")}
        return self._guarded("zuhause_code", go)

    def zuhause_entfernen(self, kid: str) -> dict:
        return self._guarded("zuhause_entfernen", lambda: self._zuhause.entfernen(str(kid)[:32], self._community),
                             "Entfernt. Dieses Gerät sucht hier nicht mehr.")

    def zuhause_schalter(self, an: bool) -> dict:
        return self._guarded("zuhause_schalter", lambda: self._zuhause.schalter(bool(an)),
                             "Eingeschaltet. Deine Handys und Laptops können hier wieder suchen." if an else "Ausgeschaltet. Deine Handys und Laptops suchen hier nicht, bis du es wieder einschaltest.")

    def zuhause_koppeln(self, code: str) -> dict:
        def go():
            if self._community.geraet() is None:
                raise app_core.AppError("ZUHAUSE_GERAET", "dieses Gerät gehört noch nicht zur Community; zuerst oben beitreten")
            return self._zuhause.koppeln(str(code)[:200], self._community)
        return self._guarded("zuhause_koppeln", go, "Fertig. Willst du in deinen Dateien suchen, setz beim Fragen unter dem Eingabefeld das Hakerl bei „In meinen Dateien suchen“.")

    def zuhause_vergessen(self) -> dict:
        return self._guarded("zuhause_vergessen", lambda: self._zuhause.vergessen(self._community), "Erledigt. Dieser Laptop fragt den PC daheim nicht mehr.")


    def fenster_stand(self) -> dict:
        def go():
            d = self._fenster.stand()
            d["angemeldet"] = self._community.geraet() is not None
            d["frei"] = self._community.fenster_frei()
            return d
        return self._guarded("fenster_stand", go)

    def fenster_einrichten(self, name: str, websites: list) -> dict:
        def go():
            if self._community.geraet() is None:
                raise app_core.AppError("FENSTER_GERAET", "dieser PC gehört noch nicht zur Community; zuerst oben beitreten")
            if self._window is None:
                raise app_core.AppError("DIALOG", "ohne Fenster gibt es keinen Ordnerdialog")
            import webview
            r = self._window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
            if not r:
                raise app_core.AppError("ABBRUCH", "kein Ordner gewählt")
            p = Path(str(r[0] if isinstance(r, (list, tuple)) else r))
            ws = [str(w) for w in websites if isinstance(w, str)] if isinstance(websites, list) else [str(websites or "")]
            d = self._fenster.einrichten(str(name), p, ws, self._community)
            _log(self._core, f"OK fenster_eingerichtet {d['dateien']} Dateien")
            return d
        r = self._guarded("fenster_einrichten", go)
        if r["ok"]:
            n = r["daten"]["dateien"]
            r["text"] = (f"Fertig. {n} Datei gelesen. Füge die Zeile unten in deine Website ein, dann beantwortet dieser PC die Fragen deiner Besucher." if n == 1
                         else f"Fertig. {n} Dateien gelesen. Füge die Zeile unten in deine Website ein, dann beantwortet dieser PC die Fragen deiner Besucher.")
        return r

    def fenster_schalter(self, an: bool) -> dict:
        return self._guarded("fenster_schalter", lambda: self._fenster.schalter(bool(an)),
                             "Eingeschaltet. Besucher deiner Website bekommen wieder Antworten von diesem PC." if an
                             else "Ausgeschaltet. Besucher lesen „gerade nicht erreichbar“, bis du es wieder einschaltest.")

    def fenster_neu_lesen(self) -> dict:
        r = self._guarded("fenster_neu_lesen", lambda: {"dateien": self._fenster.aktualisieren(erzwingen=True)})
        if r["ok"]:
            n = r["daten"]["dateien"]
            r["text"] = f"{n} Datei gelesen." if n == 1 else f"{n} Dateien gelesen."
        return r

    def fenster_entfernen(self) -> dict:
        return self._guarded("fenster_entfernen", lambda: self._fenster.entfernen(self._community),
                             "Das Frag-Fenster ist entfernt. Am Ordner selbst wurde nichts verändert.")


    def abgleich_stand(self) -> dict:
        return self._guarded("abgleich_stand", self._abgleich.stand)

    def abgleich_einschalten(self) -> dict:
        return self._guarded("abgleich_einschalten", self._abgleich.einschalten)

    def abgleich_zulassen(self, kennung: str) -> dict:
        return self._guarded("abgleich_zulassen", lambda: self._abgleich.zulassen(str(kennung)[:40]), "Zugelassen. Das Gerät holt sich die Gespräche beim nächsten Abgleich.")

    def abgleich_ablehnen(self, kennung: str) -> dict:
        return self._guarded("abgleich_ablehnen", lambda: self._abgleich.ablehnen(str(kennung)[:40]), "Abgelehnt.")

    def abgleich_wiederherstellen(self, text: str) -> dict:
        return self._guarded("abgleich_wiederherstellen", lambda: self._abgleich.wiederherstellen(str(text)[:60]), "Wiederhergestellt. Die Gespräche kommen beim nächsten Abgleich.")

    def abgleich_wechseln(self) -> dict:
        return self._guarded("abgleich_wechseln", self._abgleich.schluessel_wechseln)

    def abgleich_ausschalten(self, am_server_loeschen: bool = False) -> dict:
        return self._guarded("abgleich_ausschalten", lambda: self._abgleich.ausschalten(am_server_loeschen=bool(am_server_loeschen)),
                             "Am Server gelöscht und ausgeschaltet." if am_server_loeschen else "Auf diesem PC ausgeschaltet. Die Gespräche bleiben hier.")

    def abgleich_jetzt(self) -> dict:
        return self._guarded("abgleich_jetzt", self._abgleich.abgleichen)


    def _konto_weg_merken(self, exc: Exception) -> None:
        if getattr(exc, "code", "") == "COMMUNITY_KONTO_FEHLT":
            self._ki.einstellung_setzen(konto=None)

    def konto_geraete(self) -> dict:
        def go():
            try:
                return self._community.meine_geraete()
            except app_core.AppError as exc:
                self._konto_weg_merken(exc)
                raise
        return self._guarded("konto_geraete", go, "")

    def konto_geraet_abmelden(self, kennung: str) -> dict:
        def go():
            try:
                return self._community.geraet_abmelden(str(kennung))
            except app_core.AppError as exc:
                self._konto_weg_merken(exc)
                raise
        return self._guarded("konto_geraet_abmelden", go, "")

    def konto_ueberall_abmelden(self) -> dict:
        def go():
            try:
                return self._community.ueberall_abmelden()
            except app_core.AppError as exc:
                self._konto_weg_merken(exc)
                raise
        return self._guarded("konto_ueberall_abmelden", go, "")

    def konto_selbst_loeschen(self, bestaetigung: str) -> dict:
        def go():
            r = self._community.mein_konto_loeschen(str(bestaetigung))
            if r.get("geloescht"):
                self._ki.einstellung_setzen(konto=None)
                self._platzl.trennen()
            return {"geloescht": bool(r.get("geloescht")), "text": str(r.get("text", ""))}
        return self._guarded("konto_selbst_loeschen", go, "")


    def community_schluessel_wechseln(self) -> dict:
        def go():
            self._community.schluessel_wechseln()
            return {"gewechselt": True}
        return self._guarded("community_schluessel_wechseln", go, "Der Community-Schlüssel ist gewechselt. Der alte gilt ab sofort nicht mehr. Deine anderen Geräte bleiben Admin, wenn sie als Admin-Gerät benannt sind.")

    def not_aus_setzen(self, an: bool, grund: str = "") -> dict:
        return self._guarded("not_aus_setzen", lambda: self._community.not_aus_setzen(bool(an), str(grund or "")),
                             "Not-Aus ist an: Die Community vermittelt nichts mehr, jedes Gerät antwortet selbst." if an else "Not-Aus ist aus: Die Community läuft wieder.")


    def sammler_stand(self) -> dict:
        return self._guarded("sammler_stand", self._community.sammler_stand)

    def sammler_setzen(self, daten: dict) -> dict:
        return self._guarded("sammler_setzen", lambda: self._community.sammler_setzen(dict(daten or {})), "Gespeichert.")

    def sammler_jetzt(self) -> dict:
        def go():
            r = self._community.sammler_jetzt()
            b = r.get("bericht") or {}
            r["satz"] = (b.get("pause") or f"{b.get('neu', 0)} neue Seiten geholt, {b.get('uebersprungen', 0)} waren schon da"
                         + (f", {len(b['fehler'])} Fehler: {b['fehler'][-1]}" if b.get("fehler") else "") + ".")
            return r
        return self._guarded("sammler_jetzt", go)

    def community_geraet_admin(self, kennung: str, an: bool = True) -> dict:
        return self._guarded("community_geraet_admin", lambda: self._community.admin_ernennen(str(kennung), bool(an)), "Dieses Gerät ist jetzt Admin; das Programm dort merkt es beim nächsten Blick auf den Server." if an else "Dieses Gerät ist kein Admin mehr.")

    def bestenliste(self) -> dict:
        def go():
            try:
                r = self._community.rangliste()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT bestenliste: {exc.code}: {exc.detail}")
                r = None
            teams, mein = None, None
            try:
                teams = self._community.team_rangliste()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT team_rangliste: {exc.code}: {exc.detail}")
            if self._konto_dict():
                try:
                    mein = self._community.mein_team()
                except app_core.AppError as exc:
                    _log(self._core, f"ABGELEHNT mein_team: {exc.code}: {exc.detail}")
            return {"rangliste": r, "geraet_name": self._geraet_name, "mitglied": self._community.geraet() is not None,
                    "teams": teams, "mein_team": mein, "konto": bool(self._konto_dict())}
        return self._guarded("bestenliste", go)

    def lernen_stand(self, an: object = None) -> dict:
        def go():
            if not self._konto_dict() or self._community.geraet() is None:
                return {"konto": False, "an": True}
            r = self._community.lernen(None if an is None else an is True)
            return {"konto": True, "an": r.get("an") is not False}
        r = self._guarded("lernen_stand", go)
        if r["ok"] and an is not None:
            r["text"] = ("Danke. Deine Fragen helfen KIplatz ab jetzt beim Lernen." if r["daten"]["an"]
                         else "Ausgeschaltet. Deine Fragen, Daumen und Berichtigungen kommen nicht mehr in die Lernliste.")
        return r

    def team_aktion(self, aktion: str, wert: object = "") -> dict:
        def go():
            aktion_ = str(aktion)
            if aktion_ not in ("anlegen", "beitreten", "verlassen", "code_neu", "name"):
                raise app_core.AppError("AKTION", "unbekannte Aktion")
            felder = {"anlegen": {"name": str(wert)}, "beitreten": {"code": str(wert)}, "name": {"an": wert is True}}.get(aktion_, {})
            r = self._community.team_aktion(aktion_, **felder)
            seite = self.bestenliste()
            return {"text": str(r.get("text", "")), "seite": seite.get("daten")}
        r = self._guarded("team_aktion", go)
        if r["ok"]:
            r["text"] = r["daten"]["text"]
        return r

    def wiki_seite(self) -> dict:
        def go():
            if not self._konto_dict() or self._community.geraet() is None:
                return {"konto": False, "offen": None, "meine": None}
            offen, meine = None, None
            for name in ("offen", "meine"):
                try:
                    r = self._community.wiki_aktion(name)
                except app_core.AppError as exc:
                    _log(self._core, f"ABGELEHNT wiki {name}: {exc.code}: {exc.detail}")
                    continue
                if name == "offen":
                    offen = r
                else:
                    meine = r
            return {"konto": True, "offen": offen, "meine": meine}
        return self._guarded("wiki_seite", go)

    def wiki_aktion(self, aktion: str, daten: object = None) -> dict:
        felder = daten if isinstance(daten, dict) else {}
        if str(aktion) not in ("vorschlagen", "stimme", "zurueck"):
            return {"ok": False, "text": "Unbekannte Aktion.", "code": "AKTION", "daten": None}
        erlaubt = {"vorschlagen": ("frage", "text", "quelle"), "stimme": ("id", "art"), "zurueck": ("id",)}[str(aktion)]
        try:
            r = self._community.wiki_aktion(str(aktion), **{k: felder[k] for k in erlaubt if k in felder})
        except app_core.AppError as exc:
            _log(self._core, f"ABGELEHNT wiki {aktion}: {exc.code}: {exc.detail}")
            return {"ok": False, "text": str(exc.detail), "code": exc.code, "daten": None}
        _log(self._core, f"OK wiki {aktion}")
        seite = self.wiki_seite()
        return {"ok": True, "text": str(r.get("text") or ("Erledigt." if aktion == "zurueck" else "")), "daten": {"seite": seite.get("daten")}}

    def fehler_melden(self, frage: str, wer: str, falsch: str, richtig: str, quelle: str = "") -> dict:
        def go():
            text = self._community.fehler_melden(str(frage), str(wer), str(falsch), str(richtig), str(quelle))
            return {"text": text, "fehler": self._community.fehler_liste()}
        r = self._guarded("fehler_melden", go)
        if r["ok"]:
            r["text"] = r["daten"]["text"]
        return r

    def fehler_woche(self, kennung: str) -> dict:
        return self._guarded("fehler_woche", lambda: {"fehler": {"fehler": self._community.fehler_woche(str(kennung)), "wer": []}}, "Das ist jetzt der Fehler der Woche.")

    def fehler_entfernen(self, kennung: str) -> dict:
        return self._guarded("fehler_entfernen", lambda: {"fehler": {"fehler": self._community.fehler_entfernen(str(kennung)), "wer": []}}, "Eintrag entfernt.")


    def dunkel(self) -> bool:
        return bool(self._ki.einstellung().get("dunkel", False))

    def sprache_setzen(self, sprache: str) -> dict:
        community.SPRACHE = "en" if sprache == "en" else "de"
        if hasattr(self, "_sprechen"):
            self._sprechen.sprache = community.SPRACHE
        try:
            getattr(self, "_tray_beschriften", lambda: None)()
        except Exception as exc:
            _log(self._core, f"INFO tray beschriften: {type(exc).__name__}")
        return {"ok": True, "sprache": community.SPRACHE}

    def dunkel_setzen(self, an: bool) -> dict:
        def go():
            self._ki.einstellung_setzen(dunkel=bool(an))
            titel = getattr(self, "_titel", "")
            if titel:
                titelleiste_dunkel(titel, bool(an))
            return {"dunkel": self.dunkel()}
        return self._guarded("dunkel_setzen", go)


    HEIMNETZ_WARTE_S = 3.0

    def _anbieten_spaeter(self) -> None:
        def lauf():
            for versuch in range(8):
                if self._stopp.wait(self.HEIMNETZ_WARTE_S):
                    return
                r = self._guarded("heimnetz_anbieten_start", self._anbieten_start)
                if r["ok"]:
                    _log(self._core, f"OK heimnetz nach {versuch + 2} Anläufen angeboten")
                    return
                if r.get("code") != "HEIMNETZ_PORT":
                    return
            _log(self._core, "INFO heimnetz: Anschluss bleibt belegt; unter Einstellungen → Für Bastler neu anbieten")
        threading.Thread(target=lauf, name="heimnetz-spaeter", daemon=True).start()

    def _anbieten_start(self) -> dict:
        if self._ki.quelle() != "lokal":
            raise app_core.AppError("HEIMNETZ_QUELLE", "dieses Gerät fragt selbst ein anderes Gerät; anbieten kann nur ein Gerät, auf dem KIplatz selbst läuft")
        self._ki.einschalten()
        self._dienst.start()
        self._ki.einstellung_setzen(anbieten=True)
        return self._heimnetz_dict()

    def heimnetz_zustand(self) -> dict:
        return self._guarded("heimnetz_zustand", self._heimnetz_dict)

    def heimnetz_anbieten(self, an: bool) -> dict:
        if an:
            return self._guarded("heimnetz_anbieten", self._anbieten_start, "KIplatz wird jetzt im Heimnetz angeboten. Zum Koppeln eines zweiten PCs klick auf „PC im Heimnetz koppeln“.")

        def aus():
            self._dienst.stop()
            self._ki.einstellung_setzen(anbieten=False)
            return self._heimnetz_dict()
        return self._guarded("heimnetz_anbieten_aus", aus, "KIplatz wird nicht mehr im Heimnetz angeboten. Gekoppelte Geräte bleiben gemerkt.")

    def heimnetz_koppeln_oeffnen(self) -> dict:
        return self._guarded("heimnetz_koppeln_oeffnen", lambda: (self._dienst.koppeln_oeffnen(), self._heimnetz_dict())[1], "Der Code gilt 10 Minuten und für ein Gerät. Tipp ihn dort unter „Einstellungen“ ein.")

    def heimnetz_koppeln_schliessen(self) -> dict:
        return self._guarded("heimnetz_koppeln_schliessen", lambda: (self._dienst.koppeln_schliessen(), self._heimnetz_dict())[1])

    def heimnetz_geraet_entfernen(self, name: str) -> dict:
        def go():
            if not self._dienst.geraete.entfernen(str(name)):
                raise app_core.AppError("HEIMNETZ_GERAET", "dieses Gerät steht nicht in der Liste")
            return self._heimnetz_dict()
        return self._guarded("heimnetz_geraet_entfernen", go, "Gerät entfernt. Es kann erst nach einem neuen Koppeln wieder fragen.")

    def heimnetz_verbinden(self, host: str, code: str) -> dict:
        def go():
            if self._dienst.laeuft():
                raise app_core.AppError("HEIMNETZ_ROLLE", "dieses Gerät bietet selbst an; erst „im Heimnetz anbieten“ ausschalten")
            self._ki.ausschalten()
            d = self._ki.verbindung.koppeln(str(host), str(code))
            self._ki.einstellung_setzen(quelle="heimnetz")
            self._ki.phase, self._ki.meldung = "aus", ""
            _log(self._core, f"OK heimnetz_verbinden {d.name}")
            return self._heimnetz_dict()
        return self._guarded("heimnetz_verbinden", go, "Gekoppelt. Deine Fragen gehen ab jetzt an das andere Gerät; unter „Gespräche“ auf „KI einschalten“ klicken.")

    def heimnetz_trennen(self) -> dict:
        def go():
            self._ki.ausschalten()
            self._ki.verbindung.trennen()
            self._ki.einstellung_setzen(quelle="lokal")
            return self._heimnetz_dict()
        return self._guarded("heimnetz_trennen", go, "Getrennt. Deine Fragen beantwortet wieder dieses Gerät selbst.")

    def ki_quelle(self, quelle: str) -> dict:
        def go():
            q = "heimnetz" if str(quelle) == "heimnetz" else "lokal"
            if q == "heimnetz" and self._ki.verbindung.daten() is None:
                raise app_core.AppError("HEIMNETZ_NICHT_GEKOPPELT", "zuerst mit einem Gerät koppeln")
            if q == "heimnetz" and self._dienst.laeuft():
                raise app_core.AppError("HEIMNETZ_ROLLE", "dieses Gerät bietet selbst an; erst „im Heimnetz anbieten“ ausschalten")
            self._ki.ausschalten()
            self._ki.einstellung_setzen(quelle=q)
            return self._ki.zustand()
        return self._guarded("ki_quelle", go, "Umgestellt. Unter „Gespräche“ auf „KI einschalten“ klicken.")


    def _wissen_dict(self, extra: dict | None = None) -> dict:
        privat = self._wissen.liste(privat=True)
        lokal = self._wissen.liste(privat=False)
        try:
            server = [{**q, "server": True} for q in self._community.quellen()]
            st = community.Stand(True, len(server), "Community", f"{len(server)} Quellen am Community-Server")
        except app_core.AppError as exc:
            server, st = [], community.Stand(False, 0, "Community", exc.detail)
        self._community_stand = (time.time(), st)
        admin = self._community.ist_admin()
        wo = ("Wissen für alle am Community-Server (Wikipedia und Seiten mit Erlaubnis), Websites, die du hier liest, Nachgeschautes, Ordner und Gedächtnis-Pass privat nur auf diesem PC."
              if st.erreichbar else f"Wissen für alle am Community-Server (gerade nicht erreichbar: {st.text}), Websites, die du hier liest, Nachgeschautes, Ordner und Gedächtnis-Pass privat nur auf diesem PC.")
        quellen = server + lokal + privat
        meldungen, herkunft = [], {}
        if admin and st.erreichbar:
            try:
                meldungen, herkunft = self._community.meldungen()
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT meldungen: {exc.code}: {exc.detail}")
        for q in quellen:
            if q.get("server") and q["kennung"] in herkunft:
                q["von"] = herkunft[q["kennung"]]
        return {"quellen": quellen, "anzahl": len(quellen), "wo": wo, "server": {"erreichbar": st.erreichbar, "anzahl": st.anzahl, "adresse": self._community.adresse, "admin": admin, "mitglied": self._community.kann_merken()},
                "hausordnung": hausordnung.HAUSORDNUNG, "meldungen": meldungen,
                "pass_ordner": str(Path.home() / "Gedaechtnis-Pass"), "pass_da": (Path.home() / "Gedaechtnis-Pass").is_dir(), **(extra or {})}

    def wissen_zustand(self) -> dict:
        return self._guarded("wissen_zustand", self._wissen_dict)

    def ortswissen_eintragen(self, ort: str, titel: str, text: str, adresse: str = "", monate: int = 6) -> dict:
        def go():
            if not self._community.kann_merken():
                raise app_core.AppError("COMMUNITY_GERAET", "Ortswissen eintragen geht erst, wenn dieses Gerät zur Community gehört (unter „Meine Community“).")
            q = self._community.ortswissen_eintragen(str(ort), str(titel), str(text), str(adresse or ""), int(monate or 6))
            return self._wissen_dict({"neu": q, "am_server": True})
        return self._guarded("ortswissen_eintragen", go, "Danke, eingetragen. Ein anderes Gerät der Community schaut kurz drüber, dann antwortet KIplatz damit und nennt es als Quelle „Ortswissen“, ohne deinen Namen.")

    def ortswissen_bestaetigen(self, kennung: str) -> dict:
        def go():
            self._community.ortswissen_bestaetigen(str(kennung))
            return self._wissen_dict()
        return self._guarded("ortswissen_bestaetigen", go, "Danke. Der Eintrag gilt jetzt wieder 6 Monate.")

    def wissen_seite_lesen(self, adresse: str, fuer_alle: bool = False, grund: str = "", notiz: str = "") -> dict:
        def go():
            if fuer_alle:
                if not self._community.ist_admin():
                    raise app_core.AppError("SEITE_PRIVAT", "Für alle trägt nur der Admin eine Website ein. Für dich liest KIplatz sie privat auf diesem PC.")
                q = self._community.seite_lesen(str(adresse), grund=str(grund), notiz=str(notiz))
                return self._wissen_dict({"neu": q, "am_server": True})
            endgueltig, titel, text = wissen.seite_holen(str(adresse))
            b = hausordnung.pruefen(titel + "\n" + text)
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
            q = self._wissen.hinzufuegen("privatseite", titel, endgueltig, text)
            return self._wissen_dict({"neu": q.kurz(), "am_server": False})
        return self._guarded("wissen_seite_lesen", go, "Seite gelesen und privat auf diesem PC gemerkt. Ab jetzt antwortet KIplatz dir auch daraus und nennt sie als Quelle.")


    def _urteil(self, text: str) -> tuple[str, str]:
        b = hausordnung.pruefen(text)
        if not b.ok:
            return "verstoss", b.grund
        if not (self._ki.quelle() == "lokal" and self._ki.bereit()):
            raise app_core.AppError("KI_AUS", "das Modell auf diesem Gerät läuft gerade nicht")
        a = self._hintergrund_frage([{"role": "user", "content": text[:verteiler.PRUEF_TEXT]}], system=rechenarbeit.PRUEF_ZUSATZ, max_tokens=40, temperature=0.0)
        return rechenarbeit.urteil_aus_antwort(a.text)


    def _vertiefen(self, titel: str, text: str, fragen_min: int, fragen_max: int) -> dict:
        if not (self._ki.quelle() == "lokal" and self._ki.bereit()):
            raise app_core.AppError("KI_AUS", "das Modell auf diesem Gerät läuft gerade nicht")
        zusatz = rechenarbeit.VERTIEF_ZUSATZ.replace("{min}", str(fragen_min)).replace("{max}", str(fragen_max))
        inhalt = [{"role": "user", "content": f"Quelle: {titel}" + chr(10) + chr(10) + text[:verteiler.PRUEF_TEXT]}]
        fehler = ""
        for versuch, (temp, nachsatz) in enumerate(((0.2, ""), (0.4, chr(10) + "Wichtig: Halte dich genau an das Format. Jede Zeile beginnt mit ZUSAMMENFASSUNG:, FRAGE: oder ANTWORT:, "
                                                                          "die Zusammenfassung hat mindestens einen ganzen Satz, jede Antwort mindestens fünf Wörter, keine zwei gleichen Fragen.")), 1):
            a = self._hintergrund_frage(inhalt, system=zusatz + nachsatz, max_tokens=rechenarbeit.VERTIEF_MAX_TOKENS, temperature=temp)
            v = rechenarbeit.vertiefung_aus_antwort(a.text)
            try:
                return verteiler.vertiefung_pruefen_form(v)
            except verteiler.VerteilerError as exc:
                fehler = exc.detail
                _log(self._core, f"INFO vertiefen Versuch {versuch}: {exc.detail}")
        raise app_core.AppError("VERTIEF_FORM", f"KIplatz hat zweimal keine brauchbare Vertiefung geschrieben ({fehler}); ein anderer Rechner versucht es")

    def _vertiefen_pruefen(self, text: str, vertiefung: dict) -> tuple[str, str, list[int]]:
        if not (self._ki.quelle() == "lokal" and self._ki.bereit()):
            raise app_core.AppError("KI_AUS", "das Modell auf diesem Gerät läuft gerade nicht")
        fragen = [f for f in (vertiefung.get("fragen") or []) if isinstance(f, dict)]
        abschnitt = "ABSCHNITT:" + chr(10) + text[:verteiler.PRUEF_TEXT] + chr(10) + chr(10) + "AUSSAGE:" + chr(10)
        teile = ([(0, str(vertiefung.get("zusammenfassung", "")))] if str(vertiefung.get("zusammenfassung", "")).strip() else []) + [
            (i, f"Frage: {f.get('frage', '')}" + chr(10) + f"Antwort: {f.get('antwort', '')}") for i, f in enumerate(fragen, 1)]
        raus: list[int] = []
        unklar = 0
        for nr, aussage in teile:
            a = self._hintergrund_frage([{"role": "user", "content": abschnitt + aussage}], system=rechenarbeit.VERTIEF_EINZEL_ZUSATZ, max_tokens=4, temperature=0.0)
            w = rechenarbeit.ja_nein(a.text)
            if w is None:
                unklar += 1
            if not w:
                raus.append(nr)
        if not teile or unklar * 2 >= len(teile):
            return "unklar", f"{unklar} von {len(teile)} Aussagen ohne klares ja oder nein", []
        if 0 in raus or (fragen and sum(1 for n in raus if n) >= len(fragen)):
            return "falsch", ("die Zusammenfassung" if 0 in raus else "keine Antwort") + " steht so im Abschnitt", sorted(raus)
        return "ok", "", sorted(raus)

    def _hintergrund_frage(self, nachrichten: list[dict], **extra):
        a = self._ki.server.frage(nachrichten, abbruch=self._rechen.vorrang, platz=ki_laufzeit.SLOT_HINTERGRUND, **extra)
        if getattr(a, "abgebrochen", False):
            raise app_core.AppError("VORRANG", "die eigene Frage hat Vorrang; der Auftrag geht an den Server zurück")
        return a

    def wissen_melden(self, kennung: str, grund: str) -> dict:
        return self._guarded("wissen_melden", lambda: self._community.melden(str(kennung), str(grund)), "Gemeldet. Der Admin sieht die Meldung und entscheidet.")

    def wissen_freigeben(self, kennung: str) -> dict:
        def go():
            self._community.freigeben(str(kennung))
            return self._wissen_dict()
        return self._guarded("wissen_freigeben", go, "Freigegeben. Die Quelle sehen jetzt alle.")

    def wissen_meldung_inhalt(self, kennung: str) -> dict:
        return self._guarded("wissen_meldung_inhalt", lambda: self._community.meldung_inhalt(str(kennung)[:12]))

    def wissen_meldung_erledigt(self, kennung: str) -> dict:
        def go():
            self._community.meldung_erledigt(str(kennung))
            return self._wissen_dict()
        return self._guarded("wissen_meldung_erledigt", go, "Meldung erledigt.")

    def community_geraete(self) -> dict:
        return self._guarded("community_geraete", lambda: {"geraete": self._community.geraete(), "admin": self._community.ist_admin()})

    def community_geraet_sperren(self, kennung: str, gesperrt: bool, grund: str = "") -> dict:
        def go():
            self._community.geraet_sperren(str(kennung), bool(gesperrt), str(grund))
            return {"geraete": self._community.geraete(), "admin": True}
        return self._guarded("community_geraet_sperren", go, "Gerät gesperrt. Es bekommt keine Arbeit mehr und kann nichts mehr ablegen." if gesperrt else "Sperre aufgehoben.")

    def community_geraet_lebenslang(self, kennung: str, grund: str = "") -> dict:
        def go():
            self._community.geraet_lebenslang(str(kennung), str(grund))
            return {"geraete": self._community.geraete(), "admin": True}
        return self._guarded("community_geraet_lebenslang", go, "Auf Lebenszeit gesperrt. Auch das KIplatz-Konto dahinter kann sich nicht mehr anmelden.")

    def community_konto_suchen(self, q: str) -> dict:
        return self._guarded("community_konto_suchen", lambda: self._community.konto_suchen(str(q)[:60]))

    def community_konto_ueberall(self, kid: str, aktion: str, grund: str = "") -> dict:
        texte = {"sperren": "Überall gesperrt.", "entsperren": "Überall freigegeben.", "loeschen": "Überall gelöscht."}
        return self._guarded("community_konto_ueberall", lambda: self._community.konto_ueberall(str(kid)[:20], str(aktion), str(grund)[:300]),
                             texte.get(str(aktion), ""))

    def community_teams_admin(self) -> dict:
        return self._guarded("community_teams_admin", lambda: {"teams": self._community.teams_admin()})

    def community_team_admin(self, tid: str, aktion: str, grund: str = "", name: str = "") -> dict:
        def go():
            r = self._community.team_admin(str(tid)[:32], str(aktion), str(grund)[:300], str(name)[:40])
            return {"teams": list(r.get("teams") or []), "text": str(r.get("text", ""))}
        r = self._guarded("community_team_admin", go)
        if r["ok"]:
            r["text"] = r["daten"]["text"]
        return r

    def community_geraet_entfernen(self, kennung: str) -> dict:
        def go():
            self._community.geraet_entfernen(str(kennung))
            return {"geraete": self._community.geraete(), "admin": True}
        return self._guarded("community_geraet_entfernen", go, "Gerät entfernt. Es gehört nicht mehr zur Community.")

    def wissen_ordner_waehlen(self) -> dict:
        def go():
            if self._window is None:
                raise app_core.AppError("WISSEN_DIALOG", "ohne Fenster gibt es keinen Ordnerdialog")
            import webview
            r = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not r:
                raise app_core.AppError("WISSEN_ABBRUCH", "kein Ordner gewählt")
            return str(r[0] if isinstance(r, (list, tuple)) else r)
        return self._guarded("wissen_ordner_waehlen", go)

    def _ordner_uebernehmen(self, pfad: str, art: str) -> dict:
        ordner = Path(str(pfad)).expanduser()
        gelesen = self._wissen.ordner_lesen(ordner, art=art)
        if not gelesen:
            raise app_core.AppError("WISSEN_LEER", "in diesem Ordner war keine lesbare Textdatei (.txt, .md, .html)")
        return self._wissen_dict({"gelesen": len(gelesen)})

    def wissen_ordner_lesen(self, pfad: str) -> dict:
        return self._guarded("wissen_ordner_lesen", lambda: self._ordner_uebernehmen(pfad, "dokument"), "Ordner gelesen, privat, nur auf diesem Gerät. Nur Textdateien; PDF und Word kommen später.")

    def wissen_pass_lesen(self) -> dict:
        return self._guarded("wissen_pass_lesen", lambda: self._ordner_uebernehmen(str(Path.home() / "Gedaechtnis-Pass"), "pass"), "Gedächtnis-Pass gelesen, privat, nur auf diesem Gerät und nur für dich.")

    def wissen_entfernen(self, kennung: str) -> dict:
        def go():
            if self._wissen.entfernen(str(kennung)):
                return self._wissen_dict()
            self._community.entfernen(str(kennung))
            return self._wissen_dict()
        return self._guarded("wissen_entfernen", go, "Quelle entfernt.")


    def autostart_setzen(self, an: bool) -> dict:
        def go():
            info = app_install.installed_info(self._install_dir)
            if an:
                if info is None:
                    raise app_core.AppError("AUTOSTART_QUELLE", "geht nur mit der eingerichteten Programmdatei, nicht aus der Quelle")
                if info.exe_path.name in (app_install.START_NAME,) + app_install.ALTE_STARTER:
                    self._registry.set(app_install.RUN_VALUE_NAME, app_install.autostart_command_portable(info.exe_path.parent))
                else:
                    app_install.autostart_enable(info.exe_path, registry=self._registry)
            else:
                app_install.autostart_disable(registry=self._registry)
            return app_install.autostart_enabled(registry=self._registry)
        return self._guarded("do_autostart", go, "Autostart geändert. Im Task-Manager unter „Autostart-Apps“ siehst du den Eintrag und kannst ihn jederzeit abschalten.")

    def diagnose(self) -> dict:
        return self._guarded("diagnosis", lambda: self._core.write_diagnosis_report().name, "Diagnosebericht gespeichert (Ordner „diagnose“ in deinem Datenordner).")

    def ordner_oeffnen(self) -> dict:
        def go():
            self._core.ensure_directories()
            if platform.system() == "Windows":
                os.startfile(str(self._core.base_dir))
            return str(self._core.base_dir.name)
        return self._guarded("ordner_oeffnen", go)

    def entfernen(self) -> dict:
        def go():
            self._dienst.stop()
            self._ki.ausschalten()
            entfernt = app_install.uninstall(self._install_dir, registry=self._registry, desktop_dir=app_install.desktop_dir() if self._install_dir is None else None)
            if self._install_dir is None:
                sm = app_install.startmenue_dir()
                lnk = app_install.shortcut_path(sm) if sm else None
                if lnk is not None and lnk.is_file() and not lnk.is_symlink():
                    try:
                        lnk.unlink()
                        entfernt = tuple(entfernt) + (lnk,)
                    except OSError:
                        pass
                app_install.apps_eintrag_entfernen()
            self.schliessen_angefordert = True
            return len(entfernt)
        return self._guarded("do_uninstall", go, "Programm entfernt. Deine Daten und Einstellungen bleiben in deinem Benutzerordner. Das Fenster schließt sich jetzt.")

    _UPDATE_SPERRE = threading.Lock()

    def _update_holen(self) -> tuple[str, str]:
        if self._UPDATE_SPERRE.acquire(blocking=False):
            try:
                self._update_letztes = None
                self._update_letztes = self._update_holen_einmal()
                return self._update_letztes
            finally:
                self._UPDATE_SPERRE.release()
        with self._UPDATE_SPERRE:
            pass
        letztes = getattr(self, "_update_letztes", None)
        return letztes if letztes is not None else self._update_holen()

    def _update_holen_einmal(self) -> tuple[str, str]:
        if app_install.portable_root() is not None:
            was, text = app_install.update_quelle_holen(self._community.adresse, self._install_dir, eigener_bau=app_core.APP_BUILD, oeffner=self._community._oeffner)
        else:
            was, text = app_install.update_holen(self._community.adresse, self._install_dir, laufend=app_install.running_exe(), oeffner=self._community._oeffner)
        _log(self._core, f"OK update {was}")
        if was == "aktualisiert":
            self._neu_starten()
            return was, text
        if was == "grundlage":
            try:
                ziel = app_install.laufzeit_nachholen(self._community.adresse, app_install.portable_root(), oeffner=self._community._oeffner, ziel=text, eigener_bau=app_core.APP_BUILD)
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT grundlage: {exc.code}: {exc.detail}")
                if exc.code == "UPDATE_TAUSCH":
                    raise
                return "aktuell", f"Die neue Version braucht eine neue Programm-Grundlage (Python {text}); das hat gerade nicht geklappt ({exc.detail}). KIplatz probiert es später wieder."
            if ziel:
                _log(self._core, f"OK laufzeit {ziel} samt Quellen vorbereitet, Neustart über den Starter (er setzt sie ein)")
                self._neu_starten(ueber_starter=True)
                return "aktualisiert", "Eine neue Version mit neuer Programm-Grundlage wird eingespielt. KIplatz startet kurz neu."
            return "aktuell", app_install.rueckweg_hinweis(self._install_dir) or f"Version {app_core.APP_VERSION} (Bau {app_core.APP_BUILD})."
        if was == "aktuell":
            _rueckweg = app_install.rueckweg_hinweis(self._install_dir)
            if _rueckweg and _rueckweg not in text:
                text = _rueckweg + " " + text
        root = app_install.portable_root()
        if root is not None:
            try:
                geholt = app_install.pakete_nachholen(self._community.adresse, root, oeffner=self._community._oeffner)
                if geholt:
                    _log(self._core, f"OK pakete nachgeholt: {', '.join(geholt)}")
                    if "truststore" in geholt:
                        windows_zertifikate(self._core)
                    if any(g.startswith("tausch:") for g in geholt):
                        self._neu_starten()
                        return "aktualisiert", "Ein Sicherheitsupdate wird eingespielt. KIplatz startet kurz neu."
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT pakete: {exc.code}: {exc.detail}")
            try:
                ziel = app_install.laufzeit_nachholen(self._community.adresse, root, oeffner=self._community._oeffner)
                if ziel:
                    _log(self._core, f"OK laufzeit {ziel} vorbereitet, Neustart über den Starter (er setzt sie ein)")
                    self._neu_starten(ueber_starter=True)
                    return "aktualisiert", "Ein Sicherheitsupdate der Programm-Grundlage wird eingespielt. KIplatz startet kurz neu."
            except app_core.AppError as exc:
                _log(self._core, f"ABGELEHNT laufzeit: {exc.code}: {exc.detail}")
                if exc.code == "UPDATE_TAUSCH":
                    raise
        return was, text

    def _neu_starten(self, *, ueber_starter: bool = False) -> None:
        ordner = Path(self._install_dir or app_install.default_install_dir())
        starter = any((ordner / n).is_file() for n in (app_install.START_NAME, app_install.ALTE_STARTER[0]))
        if ueber_starter and (ordner / app_install.START_NAME).is_file():
            befehl = [str(ordner / app_install.START_NAME), "-"]
        else:
            befehl = app_install.start_command(ordner) if starter else [str(ordner / app_install.EXE_NAME)]
        for schritt in (self._dienst.stop, self._schnittstelle.stop, self._warmhalter.stop, self._rechen.stop, self._ki.ausschalten, self._bedeutung.ausschalten, self._bewertung.ausschalten):
            try:
                schritt()
            except Exception:
                pass
        if self.versteckt:
            befehl = befehl + ["--autostart"]
        einmal.freigeben()
        subprocess.Popen(befehl, close_fds=True, cwd=str(ordner), creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        self.schliessen_angefordert = True

    UPDATE_TAKT_S = 3600
    UPDATE_BLICK_S = 300
    UPDATE_TAUSCH_WARTE_S = 120
    UPDATE_TAUSCH_VERSUCHE = 5

    GEMEINSCHAFT_ERSTES_S = 90

    def _gemeinschaft_im_hintergrund(self) -> None:
        if self._spiegel is None:
            return

        def lauf():
            warte = self.GEMEINSCHAFT_ERSTES_S
            while not self._stopp.wait(warte):
                warte = gemeinschaft.HOLEN_ABSTAND_S
                if getattr(self._rechen, "phase", "") in ("antwortet", "laden"):
                    warte = 60
                    continue
                try:
                    if self._community.geraet() is None or not self._kann_fuer_andere_antworten():
                        continue
                    self._spiegel.aktualisieren()
                except Exception as exc:
                    _log(self._core, f"ABGELEHNT gemeinschaftswissen holen: {type(exc).__name__}: {str(exc)[:120]}")
        threading.Thread(target=lauf, name="gemeinschaftswissen", daemon=True).start()

    def _update_im_hintergrund(self) -> None:
        def lauf():
            warte = 6
            tausch_versuche = 0
            zuletzt = 0.0
            geblickt = 0.0
            while not self._stopp.wait(warte):
                warte = self.UPDATE_BLICK_S
                if self._update_warten():
                    warte = 60
                    if time.monotonic() - geblickt >= self.UPDATE_BLICK_S:
                        geblickt = time.monotonic()
                        try:
                            neu_w = app_install.neuester_bau(self._community.adresse, self._community._oeffner)
                        except Exception:
                            neu_w = ""
                        if neu_w:
                            steht = neu_w if neu_w > app_core.APP_BUILD else ""
                            if steht and steht != self._update_steht_an:
                                _log(self._core, f"OK update: der Server nennt Bau {neu_w}, dieses Programm ist {app_core.APP_BUILD}; nach der laufenden Arbeit")
                            self._update_steht_an = steht
                    continue
                if zuletzt and time.monotonic() - zuletzt < self.UPDATE_TAKT_S and tausch_versuche == 0:
                    try:
                        neu = app_install.neuester_bau(self._community.adresse, self._community._oeffner)
                    except Exception:
                        neu = ""
                    if neu and neu <= app_core.APP_BUILD:
                        self._update_steht_an = ""
                    if not neu or neu <= app_core.APP_BUILD:
                        continue
                    _log(self._core, f"OK update: der Server nennt Bau {neu}, dieses Programm ist {app_core.APP_BUILD}; jetzt holen")
                zuletzt = time.monotonic()
                self._update_steht_an = ""
                try:
                    was, text = self._update_holen()
                    if was == "aktualisiert":
                        self._js(f"app.hinweis({json.dumps(text, ensure_ascii=False)})")
                        return
                    tausch_versuche = 0
                except app_core.AppError as exc:
                    _log(self._core, f"ABGELEHNT update: {exc.code}: {exc.detail}")
                    if exc.code == "UPDATE_TAUSCH" and tausch_versuche < self.UPDATE_TAUSCH_VERSUCHE:
                        tausch_versuche += 1
                        warte = self.UPDATE_TAUSCH_WARTE_S
                except Exception as exc:
                    _log(self._core, f"FEHLER update: {type(exc).__name__}: {exc}")
                self._schluessel_pflegen()
        threading.Thread(target=lauf, name="update-pruefen", daemon=True).start()

    def _update_warten(self) -> bool:
        r = self._rechen
        frage = getattr(r, "phase", "") in ("antwortet", "laden") or getattr(r, "_mitglied_frage", None) is not None
        seit_antwort = float(getattr(r, "antwort_seit", 0.0) or 0.0)
        if seit_antwort and time.monotonic() - seit_antwort >= UPDATE_ANTWORT_HOECHSTENS_S:
            _log(self._core, f"HINWEIS update: dieses Gerät antwortet seit über {UPDATE_ANTWORT_HOECHSTENS_S // 60} Minuten, das hängt; das Update geht vor")
            return False
        seit = getattr(self, "_pruefung_seit", 0.0)
        if seit and time.monotonic() - seit < UPDATE_PRUEFRUNDE_HOECHSTENS_S:
            return True
        vorrang = bool(getattr(getattr(r, "vorrang", None), "is_set", lambda: False)()) and set(getattr(r, "_vorrang_wer", set()) or ()) != {"karte"}
        return frage or vorrang

    def update_pruefen(self) -> dict:
        def go():
            was, text = self._update_holen()
            return {"version": app_core.APP_VERSION, "bau": app_core.APP_BUILD, "was": was, "text": text}
        r = self._guarded("check_update", go)
        if r["ok"]:
            r["text"] = r["daten"]["text"]
        return r

    def ueber(self) -> dict:
        def go():
            info = app_install.installed_info(self._install_dir)
            wo = ((f"Liegt in deinem Benutzerordner (Programme, CommunityAI), eingerichtet {info.installed_at[:10]}, läuft über das signierte Python von python.org."
                   if info.exe_path.name in (app_install.START_NAME, app_install.ALTE_STARTER[0]) else f"Liegt in deinem Benutzerordner (Programme, CommunityAI), eingerichtet {info.installed_at[:10]}.")) if info else "Läuft aus der Quelle."
            return {"version": f"{app_core.APP_VERSION} (Bau {app_core.APP_BUILD})", "wo": wo, "quelltext": QUELLTEXT_SATZ,
                    "daten": app_core._mask(str(self._core.base_dir)), "ki": self._ki.zustand(), "wissen": self._wissen.anzahl(), "community": self._community_status().text, "hausordnung": hausordnung.HAUSORDNUNG, "lizenzen": LIZENZEN}
        return self._guarded("about", go)


    def js_fehler(self, text: str) -> dict:
        _log(self._core, f"FEHLER oberflaeche: {str(text)[:300]}")
        return {"ok": True, "text": "", "daten": None}

    def fehlerbericht_senden(self, oberflaeche: str = "") -> dict:
        def go():
            zeilen: list[str] = []
            try:
                p = self._core.diagnosis_dir / "protokoll.txt"
                if p.is_file():
                    zeilen = p.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            except OSError:
                zeilen = []
            zeilen = [z for z in zeilen if " OK zustand" not in z and " OK ki_zustand" not in z][-60:]
            zeilen = [re.sub(r"https?://\S+", "<adresse>", z) for z in zeilen]
            first = self._core.load_first_start()
            kopf = [f"Bau {app_core.APP_BUILD}, {app_core.APP_VERSION}", f"Windows: {platform.platform()}",
                    f"Gerät: {app_core.ROLE_LABELS_DE[first.role] if first else '?'}, {first.memory_gib if first else '?'} GiB, {len(first.gpu_names) if first else 0} Grafikkarte(n)",
                    f"KI: {self._ki.phase}, {self._ki.geraet_de()}", f"Rechenkraft: {self._rechen.phase}"]
            if oberflaeche:
                kopf.append("Oberfläche: " + str(oberflaeche)[:500])
            text = "\n".join(kopf) + "\n\n" + "\n".join(zeilen)
            return {"antwort": self._community.fehlerbericht(app_core.APP_BUILD, text[:7800], platform.platform()[:120])}
        return self._guarded("fehlerbericht_senden", go, "Danke. Der Bericht ist beim Admin, ohne deine Fragen und ohne Namen.")

    def community_fehlerberichte(self) -> dict:
        return self._guarded("community_fehlerberichte", lambda: {"fehlerberichte": self._community.fehlerberichte()})

    def neu_gesehen(self) -> dict:
        self._ki.einstellung_setzen(gesehen_bau=app_core.APP_BUILD)
        return {"ok": True, "text": "", "daten": None}

    def neu_liste(self) -> list[str]:
        saetze = neuerungen.seit(self._ki.einstellung().get("gesehen_bau"), app_core.APP_BUILD)
        return [neuerungen.englisch(s) for s in saetze] if community.SPRACHE == "en" else saetze

    def erststart_offen(self) -> bool:
        return not bool(self._ki.einstellung().get("erststart_fertig"))

    def erststart_fertig(self, name: str = "") -> dict:
        def go():
            n = " ".join(str(name or "").split())[:24]
            if n:
                self._ki.einstellung_setzen(geraet_name=n)
                self._geraet_name = n
            self._ki.einstellung_setzen(erststart_fertig=True, gesehen_bau=app_core.APP_BUILD)
            return {"geraet_name": self._geraet_name}
        return self._guarded("erststart_fertig", go)

    def fenster_schliessen(self) -> dict:
        self.versteckt = True
        if self._window is not None:
            try:
                self._window.hide()
            except Exception as exc:
                _log(self._core, f"INFO fenster ausblenden: {type(exc).__name__}")
        return {"ok": True, "text": "", "daten": None}

    def _window_vorne(self) -> bool:
        return auswahl.eigenes_fenster_vorne(app_core.APP_NAME) if self._window is not None and not self.versteckt else False

    def fenster_zeigen(self) -> dict:
        self.versteckt = False
        if self._window is not None:
            try:
                self._window.show()
                self._window.restore()
            except Exception as exc:
                _log(self._core, f"INFO fenster zeigen: {type(exc).__name__}")
        return {"ok": True, "text": "", "daten": None}

    def beenden(self) -> dict:
        _log(self._core, "OK beenden")
        self.schliessen_angefordert = True
        return {"ok": True, "text": "", "daten": None}

    def antwort_abbrechen(self) -> dict:
        self.abbruch_gewuenscht = True
        abbruch = getattr(self._ki.server, "abbruch", None)
        if abbruch is not None:
            abbruch.set()
        k = getattr(self, "_community_frage", None)
        if k:
            threading.Thread(target=self._community.frage_aufgeben, args=(k,), name="frage-zurueck", daemon=True).start()
        return {"ok": True, "text": "", "daten": None}


def _schriftstueck_nachbearbeiten(text: str, runde: str, lieferschein: dict | None = None, aufgabe=None) -> tuple[str, str]:
    if runde == "fragen":
        if aufgabe is not None and getattr(aufgabe, "offen", False) and not schriftstueck.ist_rueckfrage(text):
            neu, korrekturen = schriftstueck.rechnung_pruefen(schriftstueck.antwort_bereinigen(text))
            if korrekturen:
                neu += "\n\nVom Programm nachgerechnet und berichtigt: " + " ".join(korrekturen)
            return neu, "geantwortet"
        if not text.startswith(schriftstueck.VORSPANN):
            text = schriftstueck.VORSPANN + ":\n" + text
        if lieferschein is not None:
            lieferschein["pruefung"] = pruefung.pruefen("", []).kurz()
            lieferschein["erfunden"] = "nichts, es wurde nur nachgefragt"
        return text, "nachgefragt"
    neu, korrekturen = schriftstueck.rechnung_pruefen(text)
    if korrekturen:
        neu += "\n\nVom Programm nachgerechnet und berichtigt: " + " ".join(korrekturen)
    return neu, "geschrieben"


def wiki_messen(wiki, sekunden: float) -> None:
    try:
        z = wiki.zeiten_der_suche() if hasattr(wiki, "zeiten_der_suche") else {}
        ki_laufzeit._messen("wiki" + str(z.get("ausgang") or ""), sekunden)
        for teil in ("zaehlen", "woerter", "titel", "lesen"):
            if isinstance(z.get(teil), (int, float)):
                ki_laufzeit._messen("w" + teil, float(z[teil]))
        if isinstance(z.get("kandidaten"), int):
            ki_laufzeit._messen("wstellen", float(z["kandidaten"]))
    except Exception:
        pass


_AUFTRAG_WEG = {"live", "online", "internet", "netz", "web"}


def ohne_auftragswoerter(query: str, frage: str) -> str:
    in_frage = {w.lower() for w in re.findall(r"[\wäöüÄÖÜß-]+", frage or "")}
    w = [x for x in str(query or "").split() if not (x.lower() in _AUFTRAG_WEG and x.lower() not in in_frage)]
    return " ".join(w) if len(w) >= 2 else ""


_ABSICHT = threading.local()
_VERMISCHT = threading.local()


_GESTRICHEN = threading.local()

_SCHATTEN = threading.local()

_MESSWEG = threading.local()


def mess_weg(schein: dict, weg: dict | None) -> dict:
    w = weg if isinstance(weg, dict) else {}
    return {"gemacht": str(schein.get("gemacht") or schein.get("modell") or "")[:60], "stellen": int(w.get("stellen", 0)),
            "arten": sorted(str(a) for a in w.get("arten", []))[:8], "suchanfragen": int(w.get("suchanfragen", 0)),
            "suchrunden": int(w.get("suchrunden", 0)), "im_netz": w.get("im_netz", False),
            **({"schritte": dict(w["schritte"])} if isinstance(w.get("schritte"), dict) and w["schritte"] else {})}


def schritte_summe(ablauf: list[tuple[float, str]], gesamt_s: float) -> dict[str, int]:
    s: dict[str, float] = {}
    for name, sek in rechenarbeit.schritt_teile(ablauf, gesamt_s):
        s[name] = s.get(name, 0.0) + sek
    return {n: int(round(v)) for n, v in sorted(s.items(), key=lambda x: -x[1])[:8]}


WARTE_SCHRITTE = ("wartet auf die Suchbremse", "Probe: Richter")


def ohne_suchbremse(schritte: dict[str, int], gewartet_s: float, *, name: str = "wartet auf die Suchbremse",
                    zuerst: tuple[str, ...] = ("sucht im Internet", "prüft, welche Fundstellen wirklich passen")) -> dict[str, int]:
    g = int(round(gewartet_s))
    if g < 1:
        return schritte
    s = dict(schritte)
    for schritt in (*zuerst, *sorted((n for n in s if n not in WARTE_SCHRITTE), key=lambda n: -s[n])):
        if s.get(schritt, 0) >= g:
            s[schritt] -= g
            break
    s[name] = g
    return dict(sorted(s.items(), key=lambda x: -x[1])[:8])


def richter_stuecke(text: str) -> list[str]:
    stuecke: list[str] = []
    jetzt = ""
    for satz in re.split(r"(?<=[.!?])\s+", " ".join(str(text).split())):
        teile: list[str] = []
        for wort in satz.split(" "):
            if teile and len(teile[-1]) + 1 + len(wort) <= bewertung.MAX_ZEICHEN:
                teile[-1] += " " + wort
            else:
                teile.extend(wort[i:i + bewertung.MAX_ZEICHEN] for i in range(0, max(1, len(wort)), bewertung.MAX_ZEICHEN))
        for teil in teile:
            if jetzt and len(jetzt) + 1 + len(teil) > bewertung.MAX_ZEICHEN:
                stuecke.append(jetzt)
                jetzt = ""
            jetzt = (jetzt + " " + teil).strip()
    if jetzt:
        stuecke.append(jetzt)
    return stuecke


def schatten_notiz(liste) -> str:
    def wert(r) -> str:
        return "-" if r is None else f"{float(r):.2f}".replace(".", ",")
    teile = []
    for e in list(liste or [])[:6]:
        gegen = f"/{wert(e.get('rg'))}" if "rg" in e else ""
        teile.append(f"Z{int(bool(e.get('z')))} W{int(e.get('w') or 0)} N{int(bool(e.get('n')))} G{int(bool(e.get('g')))} R{wert(e.get('r'))}{gegen}")
    return f"Richter: {'; '.join(teile)}. " if teile else ""


def gegenprobe_satz(satz: str) -> str:
    return re.sub(r"\d+", lambda m: str((int(m.group(0)[0]) + 3) % 10 or 1) + m.group(0)[1:], satz)


def notiz_zusammen(vorne: str, hinten: str) -> str:
    hinten = hinten[:300]
    return vorne[:max(0, pruefstand.NOTIZ_MAX - len(hinten))] + hinten


def mess_bericht(eintrag: dict) -> dict:
    e = {**eintrag, "antwort": str(eintrag.get("antwort", ""))[:pruefstand.MESSREIHE_ANTWORT]}
    if e.get("notiz"):
        e["notiz"] = str(e["notiz"])[:pruefstand.NOTIZ_MAX]
    if str(e.get("kennung", "")).startswith("m-"):
        for k in ("quellen", "pruefung", "belege"):
            e.pop(k, None)
    elif isinstance(e.get("belege"), list):
        e["belege"] = [str(b)[:200] for b in e["belege"][:5]]
    return e


def gestrichen_notiz(liste) -> str:
    teile = [f"„{' '.join(str(s).split())[:50].replace('.', ',')}…“ [{', '.join(str(w).replace('.', ',') for w in list(woerter)[:3])[:40]}]"
             for s, woerter in list(liste or [])[:2]]
    return f"Gestrichen: {'; '.join(teile)}. " if teile else ""


def vermischt_notiz(liste) -> str:
    teile = [f"„{str(n).replace('.', '')[:40]}“ ← „{str(w).replace('.', '')[:30]}“" for n, w in list(liste or [])[:3]]
    return f"Vermischt: {'; '.join(teile)}. " if teile else ""


def _absicht_von(nachrichten: list[dict]) -> "absicht.Absicht":
    a = getattr(_ABSICHT, "wert", None)
    return a if a is not None else absicht.letzte(nachrichten or [])


def suchauftrag(text: str, *, hat_vorige_antwort: bool = True) -> tuple[bool, str, bool]:
    a = absicht.erkennen(text, hat_vorige_antwort=hat_vorige_antwort)
    return a.frisch, absicht.rest(text, a), a.korrektur


def suchfrage(nachrichten: list[dict]) -> str:
    letzte = next((str(n.get("content", "")) for n in reversed(nachrichten) if n.get("role") == "user"), "")
    a = _absicht_von(nachrichten) if nachrichten and nachrichten[-1].get("role") == "user" else absicht.Absicht()
    if a.frisch:
        hier = absicht.erkennen(letzte)
        rest = absicht.rest(letzte, hier) if hier.frisch else (letzte if a.sache else "")
        if not a.korrektur and len(wissen.woerter(rest)) >= 2:
            return rest
        davor = [n for n in nachrichten[:-1] if n.get("role") == "user"]
        frueher = " ".join(" ".join(str(n.get("content", "")).split())[:200] for n in davor[-2:]
                           if not absicht.erkennen(str(n.get("content", ""))).art).strip()
        if not frueher:
            return rest or letzte
        neu = set(wissen.woerter(rest)) - set(wissen.woerter(frueher))
        return f"{frueher} {rest}" if neu else frueher
    davor = nachrichten[:-1] if nachrichten and nachrichten[-1].get("role") == "user" else []
    if len(davor) >= 2 and davor[-1].get("role") == "assistant" and str(davor[-1].get("content", "")).startswith(schriftstueck.VORSPANN):
        auftrag = next((" ".join(str(n.get("content", "")).split()) for n in reversed(davor) if n.get("role") == "user"), "")
        if auftrag:
            return f"{auftrag[:300]} {letzte}".strip()
    if len(letzte.split()) >= 3 or len(letzte.strip()) > 40:
        return letzte
    teile = []
    gesehen = 0
    for n in reversed(nachrichten[:-1] if nachrichten and nachrichten[-1].get("role") == "user" else nachrichten):
        inhalt = str(n.get("content", "")).strip()
        if not inhalt:
            continue
        if n.get("role") == "assistant":
            fragen = [s.strip() for s in re.split(r"(?<=[.!?])\s+", inhalt) if s.strip().endswith("?")]
            if fragen:
                teile.append(fragen[-1][:300])
        elif n.get("role") == "user":
            teile.append(inhalt[:300])
            gesehen += 1
            if gesehen >= 1:
                break
    return " ".join(reversed(teile)) + (" " + letzte if letzte else "") if teile else letzte


_ERFUNDEN_MIN_SAETZE = 3


def erfunden_verdacht(pr, quellen: list[dict], schrift, frage: str = "") -> bool:
    if schrift is not None or not quellen or belege.rechenaufgabe(frage):
        return False
    return pr.rot >= _ERFUNDEN_MIN_SAETZE and pr.gruen == 0 and pr.gelb == 0


KLEIN_NUR_MIT_BELEG_UNTER_B = 8.0
GEKUERZT_HINWEIS = "Frage, Gespräch und Fundstellen waren zusammen länger, als das Modell auf einmal lesen kann; ein Teil wurde dafür gekürzt."
KLEIN_HINWEIS = "Ein kleines Modell beantwortet Wissensfragen nur mit frischen Quellen, darum wurde gleich im Internet nachgeschaut."
_FAKTENFRAGE_ANFANG = re.compile(r"^\s*(?:wer|wem|wen|wessen|was|wann|wo|woher|wohin|wie|wieso|weshalb|warum|welche\w*|wieviel\w*|ist|sind|war|waren|"
                                 r"hat|haben|hatte|gibt|gab|liegt|liegen|stimmt|who|what|when|where|which|how|why|is|are|was|were|does|did)\b", re.I)
_AN_DIE_KI = re.compile(r"\b(du|dir|dich|dein\w*|kiplatz|you|your)\b", re.I)
_RAT_ODER_ZEIT = re.compile(r"\b(w(?:ä|ae)ren?|k(?:ö|oe)nnte\w*|w(?:ü|ue)rde\w*|soll(?:te)? ich|kann ich|reimt\w*|idee\w*|vorschl\w*|empf[ie]hl\w*|empfehl\w*|tipps?|"
                            r"uhrzeit|wie sp[äa]t|datum|wochentag|kalenderwoche|welche[rsn]? tag|what time|which day|what day|date)\b", re.I)


def klein_wissensfrage(modellname: str, frage: str) -> bool:
    if not modellname or modell_stufe(modellname) >= KLEIN_NUR_MIT_BELEG_UNTER_B:
        return False
    f = " ".join(str(frage or "").split())
    if not _FAKTENFRAGE_ANFANG.match(f) or _AN_DIE_KI.search(f) or schriftstueck._PERSOENLICH.search(f) or _RAT_ODER_ZEIT.search(f):
        return False
    if (nachschauen._RECHNEN.search(f) and re.search(r"\d", f)) or len(re.findall(r"\d+(?:[.,]\d+)?", f)) >= 2:
        return False
    if rechnen.ist_umrechnungsfrage(f):
        return False
    return len(wissen.woerter(f)) >= 2


_SCHRITT = threading.local()

SUCHWORT_SYSTEM = (
    "Du schreibst Suchanfragen für eine Suchmaschine. Gefragt wird von überall auf der Welt. Lies das Gespräch und schreib "
    "für die LETZTE Frage zwei Suchanfragen, jede in einer eigenen Zeile: in der ersten Zeile die genaue Suche mit allem Wichtigen aus der Frage "
    "(Sache, Ort, Land, genannte Firmen oder Vereine), in der zweiten Zeile eine allgemeinere Suche mit nur 2 bis 4 Wörtern, die dieselbe Antwort "
    "auf einer anderen Seite findet. Jede Zeile 2 bis 8 Wörter, Deutsch, nur die Sache, "
    "ohne Satzzeichen, ohne Anführungszeichen, ohne Nummern, ohne Erklärung. Was die Person ausschließt, kommt nicht hinein. "
    "Nennt die Frage einen Ort oder ein Land, gehört er in beide Zeilen. "
    "Geht es um Angebote oder Preise im Geschäft, gehört „Aktion“ hinein, in die zweite Zeile auch „Flugblatt“ (in Deutschland „Prospekt“). "
    "Nennt die letzte Frage selbst ein Thema (einen Verein, eine Firma, einen Ort, ein Produkt), dann nimm aus früheren Fragen nichts dazu: "
    "auf „LASK Spielplan“ und dann „Rapid Spielplan“ gehört nur Rapid in die Suche, nicht LASK. Frühere Fragen helfen nur, wenn die letzte ohne sie unvollständig ist, "
    "etwa „und morgen?“ oder „und dort?“. Bei Spielplänen, Tabellen, Terminen und Programmen gehört die aktuelle Saison oder das Jahr hinein. "
    "Beispiel: Gespräch „Gibt es Briketts günstiger in Oberösterreich?“ und dann „nicht die Förderung, schau bei Obi, Lagerhaus und Maximarkt“ ergibt:"
    + chr(10) + "Briketts Aktion Obi Lagerhaus Maximarkt Oberösterreich" + chr(10) + "Briketts Aktion Flugblatt" + chr(10)
    + "Antworte nur mit den zwei Zeilen."
)
SUCHEN_HOECHSTENS = 2
SUCHWORT_ENTSCHEIDEN = ("Braucht die letzte Frage keine Suche, weil sie allgemeines Wissen ist, das sich nicht ändert (eine Erklärung, eine Rechnung, "
                        "ein Text zum Schreiben, ein Rat), dann antworte nur mit dem Wort KEINE. Im Zweifel suchen: Personen in Ämtern, Termine, "
                        "Preise, Öffnungszeiten, Ergebnisse, Regeln von Firmen und Behörden, alles zu einem bestimmten Ort und alles, was sich ändern kann, "
                        "braucht eine Suche.")
SUCHWORT_ANDERS = ("Diese Suchen wurden schon gemacht und haben die Antwort nicht gebracht: {bisher}. Schreib zwei neue Suchanfragen mit anderen Wörtern, "
                   "zum Beispiel mit dem Namen der Seite oder Stelle, die es sicher weiß, oder mit dem Begriff, den diese Stelle dafür verwendet.")
SUCHRUNDEN = 3
FRAGE_FOKUS = ("Gefragt ist genau: „{frage}“. Beantworte genau das. Steht die gefragte Angabe (zum Beispiel eine Dauer, eine Anzahl, ein Ort) "
               "in keiner Quelle, sag das in einem Satz, statt eine andere Zahl oder Angabe zu nennen. Schreib in eigenen Worten, nie mehr als 6 "
               "Wörter am Stück aus einer Quelle.")


REGEL_FOKUS = ("Es geht um eine Regel: beginne mit dem, was gilt, so wie es in den Quellen steht: für wen, ab wann und bis wann, was genau "
               "verlangt ist, Ausnahmen und was bei einem Verstoß droht. Was davon in keiner Quelle steht, lässt du einfach weg.")
PREIS_FOKUS = ("Es geht um einen Preis: nenne jede Variante, die in den Quellen steht (zum Beispiel nach Dauer oder Fahrzeugklasse), jede mit "
               "ihrem Betrag aus den Quellen.")


def frage_fokus(frage: str) -> str:
    f = " ".join(str(frage or "").split())[:300]
    teile = [FRAGE_FOKUS.format(frage=f)]
    if belege.preisfrage(f):
        teile.append(PREIS_FOKUS)
    elif belege.regelfrage(f):
        teile.append(REGEL_FOKUS)
    return " ".join(teile)


_MASSFRAGE = re.compile(r"\b(?:wie\s+(?:lange?|viele?|viel|hoch|weit|oft|alt|gro(?:ß|ss)|schwer|tief|breit|schnell|teuer|sp[äa]t|fr[üu]h|warm|kalt)"
                        r"|wieviele?|wann|seit\s+wann|bis\s+wann|how\s+(?:long|many|much|high|far|often|old|big|tall)|when)\b", re.IGNORECASE)


def massfrage(frage: str) -> bool:
    return bool(_MASSFRAGE.search(str(frage or "")))


ERSTE_FASSUNG_STRENG = False
ZAHLEN_NUR_AUS_QUELLEN = ("Nenne nur Zahlen, Daten, Uhrzeiten, Beträge und Namen, die genau so in den Auszügen oben stehen. Eine Zahl oder einen Namen, "
                          "der dort nicht steht, lässt du weg, auch wenn du ihn zu wissen glaubst.")


def mit_fokus(zusatz: str, frage: str) -> str:
    if ERSTE_FASSUNG_STRENG and zusatz.strip():
        zusatz = zusatz + "\n\n" + ZAHLEN_NUR_AUS_QUELLEN
    if not (massfrage(frage) or belege.preisfrage(frage) or belege.regelfrage(frage)):
        return zusatz
    return (zusatz + "\n\n" if zusatz else "") + frage_fokus(frage)


AUFTRAG_ZUSATZ = ("Die Person hat dich gebeten, im Internet nachzuschauen. Das ist geschehen, die Quellen stehen oben. Gemeint ist: „{frage}“. "
                  "„Live“ heißt hier nachschauen, nicht Livestream.")
PRUEF_ZUSATZ = ("Die Person fragt, ob deine vorige Antwort stimmt. Prüfe sie mit den Quellen oben: sag zuerst in einem Satz, ob sie stimmt, und "
                "berichtige, was nicht stimmt. Gemeint ist: „{frage}“.")
KEINE_NEUE_SUCHE = "Keine neue Suche: die vorige Antwort wurde nur umgeformt."


def _suchrunden_aufbrauchen() -> None:
    lauf = getattr(_SUCHLAUF, "stand", None)
    if lauf is not None:
        lauf["runde"] = SUCHRUNDEN
KORREKTUR_ZUSATZ = ("Sie sagt, deine vorige Antwort passte nicht. Wiederhole nichts daraus, antworte neu und nur mit dem, was in den Quellen steht; "
                    "steht dort nichts dazu, sag das in einem Satz.")


def mit_auftrag(zusatz: str, nachrichten: list[dict]) -> str:
    a = _absicht_von(nachrichten)
    if a.frisch:
        frage = " ".join(suchfrage(nachrichten).split())[:300]
        satz = (PRUEF_ZUSATZ if a.art == "pruefen" else AUFTRAG_ZUSATZ).format(frage=frage) + (" " + KORREKTUR_ZUSATZ if a.korrektur else "")
    else:
        satz = absicht.zusatz(a)
    return (zusatz + "\n\n" if zusatz else "") + satz if satz else zusatz


_SUCHLAUF = threading.local()
_FREMD = threading.local()
_EIGEN = threading.local()
_FACH = threading.local()


def _fach_vorziehen(sortiert: "bewertung.Sortierung", fachgebiete: list[str]) -> "bewertung.Sortierung":
    fg = set(fachgebiete)
    if not fg or not sortiert.treffer:
        return sortiert
    paare = [(w * wissen.FACH_FAKTOR if t.quelle.fachgebiet in fg else w, t) for t, w in zip(sortiert.treffer, sortiert.werte)]
    paare.sort(key=lambda p: p[0], reverse=True)
    return bewertung.Sortierung([t for _w, t in paare], [w for w, _t in paare], sortiert.bester)


def _woertlich_markieren(antwort: str, quellen: list[dict], lieferschein: dict) -> None:
    fremd = [str(q.get("text") or "") for q in quellen if isinstance(q, dict) and (q.get("art") not in antwortspeicher_basis.FREI_ARTEN or q.get("privat"))]
    if any(t and antwortspeicher_basis.woertlich(antwort or "", t) for t in fremd):
        lieferschein["woertlich"] = True


def _wohin_gemerkt() -> str:
    return "privat auf diesem PC gemerkt, nur für deine Fragen" if getattr(_EIGEN, "an", True) else "nur für diese Antwort gelesen, nicht gemerkt"
_NETZ = threading.local()
_FENSTERFRAGE = threading.local()


def _dateifrage(text: str) -> bool:
    return nachschauen.ist_dateifrage(text) and not getattr(_NETZ, "an", False)
_SUCH_NACH = re.compile(r"^\s*(?:bitte\s+)?(?:such(?:e|t)?(?:\s+(?:mal|bitte|mir|uns|doch|kurz|schnell|jetzt|einmal|nochmal))*\s+nach|(?:please\s+)?search\s+for):?\s+(?P<sache>\S.*?)[\s.!?]*$",
                        re.I)


def genannte_sache(verlauf: list[dict], ab, frage: str) -> str:
    if ab.frisch:
        return frage if (ab.sache and not ab.korrektur) else ""
    letzte = next((str(n.get("content", "")) for n in reversed(verlauf or []) if n.get("role") == "user"), "")
    m = _SUCH_NACH.match(" ".join(letzte.split()))
    if not m:
        return ""
    x = re.sub(r"[\s,]*\b(?:bitte|please|danke)\s*$", "", m.group("sache").strip(), flags=re.I).strip(" :,;-–„“\"'")
    return x if wissen.woerter(x) else ""


_NUR_GESPRAECH = re.compile(r"^\s*(?:hallo|hi|servus|grüß gott|griaß di|guten (?:morgen|tag|abend)|danke|dankeschön|ok|okay|super|passt|tschüss|baba|ciao)\b[\s!.,]*$", re.I)


def suche_denkbar(frage: str) -> bool:
    f = " ".join((frage or "").split())
    if len(wissen.woerter(f)) < 2 or _NUR_GESPRAECH.match(f):
        return False
    if nachschauen._SCHREIBEN.search(f) and not re.search(r"\b(?:wer|wann|wo|welche[rsmn]?|wie viel|wieviel|was kostet)\b", f, re.I):
        return False
    if (nachschauen._RECHNEN.search(f) and re.search(r"\d", f)) or belege.rechenaufgabe(f):
        return False
    return True


def frage_leitzeilen(frage: str) -> str:
    zeilen = []
    r = region.erkennen(frage)
    if r is not None:
        zeilen.append(f"Die Frage betrifft {r.text()}. Nimm nur Angaben, die dort gelten.")
    ri = nachschauen.richtung(frage)
    if ri == "naechst":
        zeilen.append("Gefragt ist das Nächste ab heute: nimm den ersten Termin nach dem heutigen Datum, nie einen vergangenen.")
    elif ri == "letzt":
        zeilen.append("Gefragt ist das Letzte vor heute: nimm das jüngste Ereignis vor dem heutigen Datum, nicht eines aus einer früheren Saison.")
    return "\n".join(zeilen)


def namen_leitzeilen(namen: list[str]) -> str:
    return "\n".join(f"„{name}“ kennst du nicht aus eigenem Wissen. Steht in den Fundstellen etwas dazu, schreib nur das und erfinde nichts "
                     f"dazu. Steht dort nichts, sag ehrlich, dass du zu „{name}“ nichts Verlässliches gefunden hast, und frag, was gemeint ist."
                     for name in namen[:2])


_ZEITGEBUNDEN_SAISON = re.compile(r"spielplan|tabelle|spieltag|saison|kader|auslosung|fixtures", re.I)
_ZEITGEBUNDEN_JAHR = re.compile(r"\btermine?\b|veranstaltungskalender|\bfahrplan|veranstaltung|festival|schulferien|\bferien\b|konzerte?\b|spielzeit|kirtag"
                                r"|\baktuelle[nrs]?\b|\baktuell\b|\bderzeit|\bgerade\b|\bheuer\b|\bnächste[nrs]?\b|leitzins|inflation|kilometergeld|pendlerpauschale|mindestlohn|klimaticket", re.I)


def saison_jetzt(heute=None) -> str:
    from datetime import date
    h = heute or ki_laufzeit.heute()
    j = h.year if h.month >= 7 else h.year - 1
    return f"{j}/{str(j + 1)[2:]}"


DACH_LAENDER = ("at", "de", "ch", "li")


def such_sprache(frage: str) -> str:
    original = ki_laufzeit.original()
    if original and any(land.lower() not in DACH_LAENDER for land in belege.laender_in(frage)):
        return "en"
    r = region.erkennen(frage)
    if r:
        return r.sprache
    if original and not (belege.laender_in(frage) | belege.laender_in(original)) & {"AT", "DE", "CH", "LI"} and region.erkennen(original) is None:
        return "en"
    return ""


SUCHWORT_ENGLISCH = ("Die Person hat auf Englisch gefragt, und die Frage betrifft keinen Ort im deutschen Sprachraum; die Suche läuft auf Englisch: schreib beide Zeilen "
                     "auf Englisch, mit den Wörtern, die man dort dafür verwendet.")


def zeitziel(frage: str, heute=None) -> tuple[int | None, int | None]:
    from datetime import date
    h = heute or ki_laufzeit.heute()
    if re.search(r"\b20\d\d\b", frage or ""):
        return None, None
    if _ZEITGEBUNDEN_SAISON.search(frage or ""):
        return int(saison_jetzt(h)[:4]), None
    if _ZEITGEBUNDEN_JAHR.search(frage or ""):
        return None, h.year
    if belege.preisfrage(frage):
        return None, h.year
    return None, None


def _verwandt(a: set[str], b: set[str]) -> bool:
    return any(x == y or (len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))) for x in a for y in b)


def _frueher_gefragt(nachrichten: list[dict] | None) -> bool:
    fragen = [n for n in (nachrichten or []) if isinstance(n, dict) and n.get("role") == "user" and str(n.get("content") or "").strip()]
    return len(fragen) > 1


_AUSGABE_ZEITWORT = re.compile(r"\b(?:letzte[nrms]?|zuletzt|vorige[nrms]?|vergangene[nrms]?|last|latest|most recent|previous)\b", re.I)


def suchwoerter_ordnen(liste: list[str], frage: str, frueher: str = "", heute=None) -> list[str]:
    from datetime import date
    h = heute or ki_laufzeit.heute()
    eigen = set(wissen.woerter(frage))
    alt = set(wissen.woerter(frueher))
    fremd = (alt - eigen) if (eigen & alt) and (eigen - alt) else set()
    bezug = eigen | alt
    out: list[str] = []
    ausgabe = nachschauen.ereignis_tag(frage, h) is None and nachschauen.juengstes_ereignis(frage)
    for q in liste:
        if bezug and not _verwandt(set(wissen.woerter(q)), bezug):
            continue
        w = [x for x in q.split() if not (fremd and set(wissen.woerter(x)) and set(wissen.woerter(x)) <= fremd)]
        q2 = " ".join(w)
        if len(q2.split()) < 2:
            q2 = " ".join(frage.split())[:120]
        if ausgabe:
            ohne = " ".join(_AUSGABE_ZEITWORT.sub(" ", q2).split())
            if len(ohne.split()) < 2:
                ohne = " ".join(_AUSGABE_ZEITWORT.sub(" ", nachschauen.suchbegriffe_regel(frage, "") or frage).split())[:120]
            if not out and not re.search(r"\b20\d\d\b", ohne):
                ohne = f"{ohne} {h.year}"
            if ohne and ohne.lower() not in (o.lower() for o in out):
                out.append(ohne)
            continue
        tag = nachschauen.ereignis_tag(frage, h)
        if tag is not None and not out and str(tag.year) not in q2:
            englisch = antwortsprache.frage_sprache(frage) == "en" or antwortsprache.frage_sprache(q2) == "en" or such_sprache(frage) == "en"
            q2 += " " + nachschauen.tag_wort(tag, englisch=englisch)
        if not re.search(r"\b20\d\d\b", q2):
            if _ZEITGEBUNDEN_SAISON.search(q2 + " " + frage):
                q2 += " " + saison_jetzt(h)
            elif _ZEITGEBUNDEN_JAHR.search(q2 + " " + frage):
                q2 += f" {h.year}"
        if q2.lower() not in (o.lower() for o in out):
            out.append(q2)
    if ausgabe and len(out) == 1:
        vorjahr = re.sub(rf"\b{h.year}\b", str(h.year - 1), out[0])
        if vorjahr != out[0]:
            out.append(vorjahr)
    return out[:SUCHEN_HOECHSTENS]


_LAND_SATZ = {"de": "Die Suche war auf Deutschland zugeschnitten.", "at": "Die Suche war auf Österreich zugeschnitten.",
              "ch": "Die Suche war auf die Schweiz zugeschnitten."}


def gesucht_satz(frage: str, gesucht: list[str], land: str = "") -> str:
    gleich = " ".join(str(frage).split()).casefold()
    selbst = any(" ".join(str(q).split()).casefold() == gleich for q in gesucht)
    if len(gesucht) > 1:
        vorne, letzte = _aufzaehlung(gesucht)
        satz = (f"Gesucht wurde nach {vorne} und „{letzte}“; dafür ging deine Frage selbst an die Suche." if selbst
                else f"Gesucht wurde nach {vorne} und „{letzte}“; nur diese Suchwörter gingen an die Suche, nicht deine Frage.")
    else:
        eins = "".join(gesucht)
        satz = (f"Gesucht wurde nach „{eins}“; dafür ging deine Frage selbst an die Suche." if selbst
                else f"Gesucht wurde nach „{eins}“; nur diese Suchwörter gingen an die Suche, nicht deine Frage.")
    return f"{satz} {_LAND_SATZ[land]}" if land in _LAND_SATZ else satz


def suchwoerter_liste(text: str) -> list[str]:
    out: list[str] = []
    for zeile in (text or "").splitlines():
        z = suchwoerter_pruefen(re.sub(r"^\s*(?:\d+[.)]|[-–•])\s*", "", zeile))
        if z and z.lower() not in (o.lower() for o in out):
            out.append(z)
    return out[:SUCHEN_HOECHSTENS]


def suchwoerter_pruefen(text: str) -> str:
    z = next((x.strip() for x in (text or "").splitlines() if x.strip()), "")
    z = re.sub(r"^(?:suchanfrage|suche|anfrage)\s*:\s*", "", z, flags=re.I).strip(" .\"'„“”»«")
    w = z.split()
    if not 2 <= len(w) <= 10 or len(z) > 120 or re.search(r"\b(?:kenne ich|ich kann|leider|entschuldig)", z, re.I):
        return ""
    if re.search(r"[,!?;()]|\bQuelle \d", z):
        return ""
    return z


ERFUNDEN_ZUSATZ = ("Prüfung: Deine vorige Antwort enthielt Einzelheiten, die in keinem der Auszüge stehen. Erfinde nichts. "
                   "Antworte jetzt in höchstens drei kurzen Sätzen: Sag, was die Auszüge dazu wirklich hergeben, und wenn sie nichts hergeben, "
                   "sag nur „Das weiß ich noch nicht.“ Schreib nie „Auszüge“. Keine Aufzählung, keine Beispiele.")


class _Teilgeber:

    def __init__(self, melden, abstand_s: float = 0.8) -> None:
        self._melden, self._abstand = melden, abstand_s
        self.text, self._t, self.gesendet = "", time.time(), ""

    def token(self, piece: str) -> None:
        self.text += piece
        if time.time() - self._t >= self._abstand:
            self._t = time.time()
            self._senden()

    def schluss(self) -> None:
        self._senden()

    def _senden(self) -> None:
        t = ohne_auszuege(ohne_markdown(self.text))
        if not t.strip() or t == self.gesendet:
            return
        self.gesendet = t
        try:
            self._melden(t)
        except Exception:
            pass

    def neu(self) -> None:
        pass

    def runde(self) -> "_Teilgeber":
        return _Teilgeber(self._melden, self._abstand)


class _Still:
    token = None

    def schluss(self) -> None:
        pass

    def neu(self) -> None:
        pass

    def runde(self) -> "_Still":
        return self


class _FensterStrom:

    def __init__(self, js, on_token) -> None:
        self._js, self._on_token = js, on_token
        self.token = on_token

    def schluss(self) -> None:
        if isinstance(self._on_token, satzweise.Sammler):
            self._on_token.rest()

    def neu(self) -> None:
        if self.token is not None:
            self._js("app.tokenNeu()")

    def runde(self) -> _Still:
        return _Still()


DATEI_NUR_DAHEIM = ("In deinen Dateien sucht nur dein eigener PC. Ist dein Handy mit ihm verbunden, tipp auf das Plus neben dem Eingabefeld, "
                    "wähl „In meinen Dateien suchen“ und frag noch einmal. Noch nicht verbunden? Das geht einmal in der App unter „PC daheim“.")
HOLEN_BUDGET_S = 200.0
HOLEN_RUNDEN = 10


def holen_satz(bereit: int, spaeter: int, alt: int, zu_gross: list[str], fehler: list[str]) -> str:
    if bereit == 1:
        teile = ["1 Datei liegt für dich bereit."]
    else:
        teile = [f"{bereit} Dateien liegen für dich bereit." if bereit else "Diesmal konnte ich keine Datei bereitlegen."]
    if spaeter:
        teile.append(f"{spaeter} weitere hole ich gleich hinterher.")
    if zu_gross:
        namen = ", ".join(f"„{x}“" for x in zu_gross)
        teile.append(f"Zu groß zum Holen (höchstens {zuhause.DATEI_HOECHSTENS // (1024 * 1024)} MB je Datei): {namen}.")
    if alt:
        teile.append("Eine Datei stammt aus einer älteren Suche; such bitte noch einmal, dann klappt es." if alt == 1
                     else f"{alt} Dateien stammen aus einer älteren Suche; such bitte noch einmal, dann klappt es.")
    if fehler:
        namen = ", ".join(f"„{x}“" for x in fehler)
        teile.append(f"Nicht geklappt hat es bei {namen}; probier es gleich noch einmal.")
    return " ".join(teile)
def verlauf_buendeln(verlauf: list[dict]) -> list[dict]:
    out: list[dict] = []
    for v in verlauf:
        if out and out[-1]["notiz"] == v.get("notiz") and out[-1]["geraet"] == v.get("geraet") and (out[-1]["betrag"] > 0) == (int(v.get("betrag", 0)) > 0):
            out[-1]["betrag"] += int(v.get("betrag", 0))
            out[-1]["anzahl"] += 1
            out[-1]["zeit"] = v.get("zeit", out[-1]["zeit"])
            continue
        out.append({**v, "betrag": int(v.get("betrag", 0)), "anzahl": 1})
    return out


DATEI_HAKEN = ("Das klingt nach einer Datei auf deinem PC daheim. Schalte „In meinen Dateien suchen“ ein (in der App über das Plus neben dem "
               "Eingabefeld) und frag noch einmal, dann suche ich sie für dich.")
DATEI_HAKEN_PC = ("Das klingt nach einer Datei auf deinem PC. Setz unten den Haken „In meinen Dateien suchen“ und frag noch einmal, dann suche ich "
                  "sie für dich.")
DATEI_NICHT_GEKOPPELT = ("Dein PC daheim kennt dieses Gerät gerade nicht, oder das Suchen ist dort ausgeschaltet. Verbinde es unter „PC daheim“ "
                         "einfach noch einmal, dann sucht er wieder für dich.")
DATEI_NICHTS_DAHEIM = ("Auf deinem PC daheim habe ich dazu keine passende Datei gefunden. Schalte „In meinen Dateien suchen“ ein (in der App über das "
                       "Plus neben dem Eingabefeld), dann schaue ich "
                       "in all deinen Ordnern nach, auch bei Word, PDF und Fotos.")
_WEISS_NICHT = re.compile(r"kenne ich (?:das |es |leider |gerade |noch )*nicht|steht nicht in den Auszügen|weiß ich (?:das |es |leider |gerade |noch )*nicht"
                          r"|\bkeine (?:der |dieser )?(?:Quellen?|Auszüge) (?:nennt|nennen|enthält|enthalten|gibt|geben|sagt|sagen)\b"
                          r"|\bin (?:keiner|den) (?:der )?(?:Quellen?|Auszügen?) (?:steht|stehen|findet sich|finden sich) (?:keine|nichts|nicht)\b"
                          r"|\bdie Quellen (?:nennen|enthalten|geben) (?:keine|nichts)\b"
                          r"|ist mir (?:leider )?nicht bekannt|habe ich keine (?:Informationen|Angaben|Daten)|liegen mir keine (?:Informationen|Angaben|Daten)|kann ich (?:dir |Ihnen )?(?:leider )?nicht (?:sagen|beantworten)", re.I)
_WEISS_NICHT_SATZ = "Das weiß ich gerade nicht sicher. Soll ich live nachprüfen?"
_NACHPRUEFEN_ANGEBOT = "Soll ich live nachprüfen?"
_GESUCHT_NICHTS_SATZ = "Das weiß ich noch nicht, und im Internet habe ich dazu gerade nichts Verlässliches gefunden."
_NICHT_ERREICHT_SATZ = "Das weiß ich noch nicht, und die Suche im Internet ist gerade nicht durchgekommen. Soll ich es gleich noch einmal versuchen?"
_AUSZUG = re.compile(r"Auszüg|Auszug\b|Wissensspeicher|\b(?:die|den|in den|laut|nur|keine|alle|beide|meine|deine)\s+Quellen\b|"
                     r"\bQuellen\s+(?:nennen|zeigen|sagen|enthalten|erwähnen|geben|liegen|belegen|bestätigen)|"
                     r"\bsteht (?:hier|dazu|darüber)(?: (?:auch|leider))? nichts\b|\bdazu steht (?:hier )?nichts\b|\bhier steht nichts\b", re.I)
_QUELLEN_ZEILE = re.compile(r"^[ \t]*(?:\*\*|__)?(?:Quellen?|Quellenangaben?|Sources?)(?:\*\*|__)?[ \t]*:(?:\*\*|__)?[^\n]*$", re.I | re.M)
_AUSZUG_KLAMMER = re.compile(r"\s*\([^()]*(?:Auszüg|Auszug\b|Wissensspeicher|\bQuellen?\b)[^()]*\)\s*", re.I)


def ohne_auszuege(text: str | None) -> str:
    t = re.sub(r"\n{3,}", "\n\n", _QUELLEN_ZEILE.sub("", text or "")).strip()
    t = antwortspeicher_basis.ohne_schlussangebot(t)
    t = _AUSZUG_KLAMMER.sub(" ", t)
    t = re.sub(r"([.!?])\s*\.", r"\1", re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", t))).strip()
    if not _AUSZUG.search(t):
        return t
    absaetze = []
    for absatz in t.split("\n"):
        saetze = [s for s in re.split(r"(?<=[.!?])\s+", absatz) if s and not _AUSZUG.search(s)]
        if saetze or not absatz.strip():
            absaetze.append(" ".join(saetze))
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(absaetze)).strip()
    return rest or "Das weiß ich noch nicht."


BELEGE_ZUSATZ = ("Prüfung: Eine erste Fassung dieser Antwort nannte eine Zahl, ein Datum oder einen Namen, der in keiner Quelle steht: „{saetze}“. "
                 "Schreib die Antwort ganz neu, als wäre es die erste. Nenne nur Zahlen, Daten, Uhrzeiten, Beträge und Namen, die genau so in den Quellen stehen, "
                 "und übernimm sie genau; die Sätze schreibst du in eigenen Worten, nie mehr als 6 Wörter am Stück aus einer Quelle. Steht die Antwort in keiner Quelle, schreib nur „Das weiß ich noch nicht.“ Erwähne nie eine erste Fassung, einen "
                 "Fehler oder eine Korrektur. Schreib nie „Quellen“ oder „Auszüge“.")


REGEL_OHNE_QUELLE = "Eine Regel ohne Quelle wurde nicht ausgegeben: Regeln, Pflichten und Fristen sind je Land anders und ändern sich, ohne Quelle nennt KIplatz keine."
REGEL_ZUSATZ = ("Eine Regel (was man braucht, muss, darf oder nicht darf) schreibst du nur so, wie sie in einer Quelle steht, mit derselben Aussage; "
                "sagt keine Quelle etwas dazu, lass sie weg.")
ANDERE_PERSON = "Die gefundenen Seiten handeln von jemand anderem; über die gefragte Person schreibt KIplatz darum nichts."


_ANLEITUNGSSCHRITT = re.compile(r"^\s*(?:\*\*)?(?:\d{1,2}[.)]|(?:Schritt|Step)\s+\d{1,2}\b)", re.IGNORECASE)


def nur_rest(vorher: str, nachher: str, raus: list[str]) -> bool:
    if not raus:
        return False
    saetze = [s for absatz in (vorher or "").split("\n") for s in belege._saetze(absatz) if re.search(r"\w\w", s) and not s.rstrip().endswith(":")]
    if not saetze:
        return False
    if saetze[0].strip()[:25] not in (nachher or ""):
        return True
    ganz_weg = [s for s in raus if s.strip()[:25] not in (nachher or "")]
    schritte = [z for z in (vorher or "").split("\n") if _ANLEITUNGSSCHRITT.match(z)]
    if any(s.strip()[:25] in z for s in ganz_weg for z in schritte):
        return True
    return len(ganz_weg) * 2 > len(saetze)


def _ohne_vermittler(zusatz: str, quellen: list[dict], adressen: set[str]) -> str:
    if not adressen:
        return zusatz
    for q in quellen:
        text = str(q.get("text") or "")
        if text and str(q.get("adresse") or "") in adressen:
            zusatz = re.sub(rf"\nQuelle {int(q.get('nummer') or 0)}: [^\n]*\n" + re.escape(text), "\n", zusatz).replace(text, " ")
    return "\n".join(z for z in zusatz.split("\n") if nachschauen.VERMITTLER_ZEILE not in z)


def _streng(t: str, belegtext: str, zusatz: str, rechnen: bool, pruefer, auszuege: list[tuple[int, str]], *, regel: bool = False,
            beispiele: bool = False, bekannt=None, regelfrage: str = "", richter=None, ableitung: bool = False) -> tuple[str, list[str], int]:
    aus_quellen = any(s.farbe == "gruen" for s in pruefung.pruefen(t, auszuege).saetze)
    quelltexte = [x for _n, x in auszuege]
    befunde = belege.streng_pruefen(t, belegtext, zahlen_pruefen=not rechnen, namen_pruefen=None if (aus_quellen or regel) else (lambda s: False),
                                    regel_frage=regelfrage, regel_quellen=quelltexte, ableitung=ableitung)
    if (not aus_quellen and not regel) or beispiele:
        befunde = [dataclasses.replace(b, zahlen=()) if b.zahlen and belege.alltag_ohne_widerspruch(b.satz, belegtext) else b
                   for b in befunde]
        befunde = [b for b in befunde if b.zahlen or b.namen or b.verdacht or b.regel]
    if beispiele:
        befunde = [dataclasses.replace(b, zahlen=()) if belege.beispiel(b.satz) else b for b in befunde]
        kandidaten = sorted({w for b in befunde if belege.beispiel(b.satz) for w in (*b.namen, *b.verdacht)})
        try:
            echt = set(bekannt(kandidaten)) if bekannt is not None and kandidaten else set()
        except Exception:
            echt = set()
        if echt:
            befunde = [dataclasses.replace(b, namen=tuple(n for n in b.namen if n not in echt), verdacht=tuple(v for v in b.verdacht if v not in echt))
                       if belege.beispiel(b.satz) else b for b in befunde]
        befunde = [b for b in befunde if b.zahlen or b.namen or b.verdacht or b.regel]
    weg = {b.satz for b in befunde if b.sicher_falsch}
    fraglich_b = [b for b in befunde if not b.sicher_falsch and b.verdacht]
    fraglich = [b.satz for b in fraglich_b]
    vom_pruefer = 0
    als_name: set = set()
    if fraglich and pruefer is not None:
        try:
            woerter = list(dict.fromkeys(w for b in fraglich_b for w in b.verdacht))
            als_name = {woerter[i] for i in (pruefer(zusatz, woerter) or set()) if 0 <= i < len(woerter)}
        except app_core.AppError:
            als_name = set()
        vom_pruefer_weg = {b.satz for b in fraglich_b if als_name & set(b.verdacht)}
        vom_pruefer = len(vom_pruefer_weg)
        weg |= vom_pruefer_weg
    if richter is not None and isinstance(getattr(_SCHATTEN, "liste", None), list):
        for b in befunde:
            if b.regel:
                continue
            eintrag = {"z": bool(b.zahlen), "w": len(b.namen) + len(b.verdacht), "n": bool(als_name & set(b.verdacht)), "g": b.satz in weg}
            for feld, satz in (("r", b.satz), ("rg", gegenprobe_satz(b.satz))):
                if feld == "rg" and satz == b.satz:
                    break
                try:
                    eintrag[feld] = richter(satz, quelltexte)
                except Exception:
                    eintrag[feld] = None
            _SCHATTEN.liste.append(eintrag)
    if not weg:
        return t, [], 0
    if isinstance(getattr(_GESTRICHEN, "liste", None), list):
        _GESTRICHEN.liste.extend((b.satz, tuple(b.zahlen) + tuple(b.namen) + tuple(b.verdacht)) for b in befunde if b.satz in weg)
    teilweise: dict[str, str] = {}
    for s in [s for s in weg if s not in fraglich]:
        teile = [x.strip(" ,;") for x in re.split(r"\s*;\s*|,?\s+(?:und|sowie)\s+|,\s+(?=[A-ZÄÖÜ])", s.rstrip(" .!")) if x.strip(" ,;")]
        if re.search(r"\b(?:aber|während|jedoch|doch|sondern)\b", s):
            continue
        if len(teile) < 2:
            continue
        gut = [x for x in teile if not any(b.sicher_falsch for b in belege.streng_pruefen(
            x + ".", belegtext, zahlen_pruefen=not rechnen, namen_pruefen=lambda _s: False, regel_frage=regelfrage, regel_quellen=quelltexte))]
        if gut and len(gut) < len(teile) and any(re.search(r"\d", x) for x in gut):
            teilweise[s] = " und ".join(gut) + "."
    for s, neu in teilweise.items():
        t = t.replace(s, neu, 1)
        weg.discard(s)
    if not weg:
        return t, list(teilweise), vom_pruefer
    rest, raus = belege.saetze_streichen(t, lambda s: s in weg, mitnehmen=True)
    return rest, raus + list(teilweise), vom_pruefer


def belege_anwenden(text: str, frage: str, zusatz: str, quellen: list[dict], *, heute: date | None = None, nochmal=None, pruefer=None,
                    umschreiben=None,
                    schreiben: bool = False, bekannt=None, richter=None) -> tuple[str, list[str]]:
    heute = heute or ki_laufzeit.heute()
    notizen: list[str] = []
    t, n = belege.ohne_platzhalter(text)
    if n:
        notizen.append(f"{n} Platzhalter in eckigen Klammern entfernt.")
    t, n = belege.wochentage_berichtigen(t, heute)
    if n:
        notizen.append("1 falschen Wochentag neben einem Datum vom Programm berichtigt." if n == 1
                       else f"{n} falsche Wochentage neben einem Datum vom Programm berichtigt.")
    if nachschauen.richtung(frage) == "naechst":
        t, raus_vorbei = belege.vergangene_streichen(t, heute)
        if raus_vorbei:
            notizen.append("1 Satz mit einem vergangenen Datum als „nächstes“ vom Programm gestrichen." if len(raus_vorbei) == 1
                           else f"{len(raus_vorbei)} Sätze mit einem vergangenen Datum als „nächstes“ vom Programm gestrichen.")
    ziel = zeitziel(frage, heute)
    if ziel != (None, None):
        gelesen = "\n".join(str(q.get("text") or "") for q in (quellen or []) if q.get("art") == "nachgeschaut")
        vor_alt = t
        t, raus_alt = belege.saetze_streichen(t, lambda s: nachschauen.veraltet_text(s, *ziel) and not belege.seit_belegt(s, gelesen))
        if raus_alt:
            notizen.append("1 Satz über eine frühere Saison oder ein früheres Jahr vom Programm gestrichen." if len(raus_alt) == 1
                           else f"{len(raus_alt)} Sätze über eine frühere Saison oder ein früheres Jahr vom Programm gestrichen.")
            if t != "Das weiß ich noch nicht." and nur_rest(vor_alt, t, raus_alt):
                notizen.append("Nach dem Streichen fehlte der Anfang der Antwort; ein Rest wird nicht ausgegeben.")
                t = "Das weiß ich noch nicht."
    if schreiben or not any(str(q.get("text") or "").strip() for q in (quellen or [])):
        if not schreiben and belege.preisfrage(frage) and any(belege.betraege(t)):
            notizen.append("Ein Preis ohne Quelle wurde nicht ausgegeben: Preise ändern sich, ohne aktuelle Quelle nennt KIplatz keinen.")
            return "Das weiß ich noch nicht.", notizen
        if not schreiben and belege.regelfrage(frage) and not belege.preisfrage(frage) and not _WEISS_NICHT.search(t):
            notizen.append(REGEL_OHNE_QUELLE)
            return "Das weiß ich noch nicht.", notizen
        t, n_eigen, _ersetzt = eigene_worte(t, belege.fremde_texte(quellen), umschreiben)
        return t, notizen + n_eigen
    if not _WEISS_NICHT.search(t) and belege.gefragter_name_fehlt(frage, t, [str(q.get("text") or "") for q in quellen]):
        notizen.append(ANDERE_PERSON)
        return "Das weiß ich noch nicht.", notizen
    vermittler = nachschauen.vermittler_adressen(quellen)
    beleg_quellen = [q for q in quellen if str(q.get("adresse") or "") not in vermittler]
    belegtext = (_ohne_vermittler(zusatz or "", quellen, vermittler) + "\n" + (frage or "") + "\n"
                 + wissen.zeit_zeile(None if heute == ki_laufzeit.heute() else datetime(heute.year, heute.month, heute.day, 12).astimezone()))
    rechnen = belege.rechnet(frage)
    ableitung = belege.ableitungsfrage(frage)
    regel = not schreiben and belege.regelfrage(frage) and not belege.preisfrage(frage)
    regelfrage = frage if (not schreiben and belege.regelfrage(frage)) else ""
    auszuege = [(int(q.get("nummer") or 0), str(q.get("text") or "")) for q in beleg_quellen if q.get("text")]
    beispiele = not (rechnen or regel or belege.zahlenfrage(frage) or belege.preisfrage(frage))
    geprueft, raus, vom_pruefer = _streng(t, belegtext, zusatz, rechnen, pruefer, auszuege, regel=regel, beispiele=beispiele, bekannt=bekannt, ableitung=ableitung,
                                          regelfrage=regelfrage, richter=richter)
    regel_saetze = {s for s, _g in belege.regel_ungestuetzt(t, regelfrage, [x for _n, x in auszuege])} if regelfrage else set()
    basis = t
    ausloeser = belege.vermischt_ausloeser(geprueft, [(str(q.get("titel") or ""), str(q.get("text") or "")) for q in quellen if q.get("text")])
    misch = [s for s, _n, _w in ausloeser]
    if misch:
        if isinstance(getattr(_VERMISCHT, "liste", None), list):
            _VERMISCHT.liste.extend((n, w) for _s, n, w in ausloeser)
        geprueft, raus_misch = belege.saetze_streichen(geprueft, lambda s: s in misch, mitnehmen=True)
        raus = raus + raus_misch
        notizen.append("1 Satz, der einer Quelle etwas aus einer anderen Quelle zuschreibt, vom Programm gestrichen." if len(raus_misch) == 1
                       else f"{len(raus_misch)} Sätze, die einer Quelle etwas aus einer anderen Quelle zuschreiben, vom Programm gestrichen.")
    if raus and geprueft != "Das weiß ich noch nicht." and not belege.brauchbar(geprueft):
        notizen.append("Nach dem Streichen blieb kein ganzer Satz; der Rest wurde nicht ausgegeben.")
        geprueft = "Das weiß ich noch nicht."
    if raus and nochmal is not None:
        try:
            regel_vorher = bool(regel_saetze & set(raus))
            neu = nochmal(BELEGE_ZUSATZ.format(saetze=" ".join(raus)[:400]) + (" " + REGEL_ZUSATZ if regel_vorher else "") + " " + frage_fokus(frage))
            neu, _ = belege.ohne_platzhalter(neu or "")
            neu, _ = belege.ohne_selbstbezug(neu)
            neu, _ = belege.wochentage_berichtigen(neu, heute)
            neu = ohne_auszuege(ohne_markdown(neu))
            geprueft2, raus2, vom2 = _streng(neu, belegtext, zusatz, rechnen, pruefer, auszuege, regel=regel, beispiele=beispiele, bekannt=bekannt, ableitung=ableitung,
                                             regelfrage=regelfrage)
            quell_z = belege.zahlenwerte(belegtext + "\n" + "\n".join(x for _n, x in auszuege))
            erste_rest = geprueft == "Das weiß ich noch nicht." or nur_rest(basis, geprueft, raus)
            if (geprueft2.strip() and belege.brauchbar(geprueft2) and not _WEISS_NICHT.search(geprueft2) and not nur_rest(neu, geprueft2, raus2)
                    and (erste_rest or len(belege.zahlenwerte(geprueft2) & quell_z) >= len(belege.zahlenwerte(geprueft) & quell_z))):
                geprueft, raus, vom_pruefer, basis = geprueft2, raus2, vom2, neu
                regel_saetze = {s for s, _g in belege.regel_ungestuetzt(neu, regelfrage, [x for _n, x in auszuege])} if regelfrage else set()
                notizen.append("Die erste Fassung nannte eine Regel, die keine Quelle so sagt; KIplatz hat neu geantwortet." if regel_vorher
                               else "Die erste Fassung nannte Zahlen, Daten oder Namen, die in keiner Quelle stehen; KIplatz hat neu geantwortet.")
        except app_core.AppError:
            pass
    if raus and geprueft != "Das weiß ich noch nicht." and nur_rest(basis, geprueft, raus):
        notizen.append("Nach dem Streichen fehlte der Anfang der Antwort; ein Rest wird nicht ausgegeben.")
        geprueft = "Das weiß ich noch nicht."
    n_regel = sum(1 for s in raus if s in regel_saetze)
    if n_regel:
        notizen.append("1 Satz mit einer Regel, die keine Quelle so sagt, vom Programm gestrichen." if n_regel == 1
                       else f"{n_regel} Sätze mit einer Regel, die keine Quelle so sagt, vom Programm gestrichen.")
    n_rest = len(raus) - n_regel
    if n_rest:
        if n_rest == 1:
            notizen.append("1 Satz mit einer Zahl, einem Datum oder einem Namen, die in keiner Quelle stehen, vom Programm gestrichen, nach einem zweiten Blick des Modells."
                           if vom_pruefer else "1 Satz mit einer Zahl, einem Datum oder einem Namen, die in keiner Quelle stehen, vom Programm gestrichen.")
        elif vom_pruefer:
            notizen.append(f"{n_rest} Sätze mit einer Zahl, einem Datum oder einem Namen, die in keiner Quelle stehen, vom Programm gestrichen ({vom_pruefer} davon nach einem zweiten Blick des Modells).")
        else:
            notizen.append(f"{n_rest} Sätze mit einer Zahl, einem Datum oder einem Namen, die in keiner Quelle stehen, vom Programm gestrichen.")
    if (regel and geprueft != "Das weiß ich noch nicht." and not any(s.farbe == "gruen" for s in pruefung.pruefen(geprueft, auszuege).saetze)
            and not belege.regel_gestuetzt(geprueft, frage, [x for _n, x in auszuege])):
        notizen.append(REGEL_OHNE_QUELLE)
        geprueft = "Das weiß ich noch nicht."
    if not schreiben and geprueft != "Das weiß ich noch nicht." and belege.zahlenfrage(frage):
        fehlend = namen_fehlen(frage, geprueft)
        if fehlend and nochmal is not None:
            try:
                neu = nochmal(NAMEN_ZUSATZ.format(namen=", ".join(fehlend)))
                neu, _ = belege.ohne_platzhalter(neu or "")
                neu, _ = belege.ohne_selbstbezug(neu)
                neu, _ = belege.wochentage_berichtigen(neu, heute)
                geprueft3, raus3, vom3 = _streng(neu, belegtext, zusatz, rechnen, pruefer, auszuege, regelfrage=regelfrage, ableitung=ableitung)
                quell_z = belege.zahlenwerte(belegtext + "\n" + "\n".join(x for _n, x in auszuege))
                if geprueft3.strip() and geprueft3 != "Das weiß ich noch nicht." and belege.brauchbar(geprueft3) \
                        and len(namen_fehlen(frage, geprueft3)) < len(fehlend) \
                        and len(belege.zahlenwerte(geprueft3) & quell_z) >= len(belege.zahlenwerte(geprueft) & quell_z):
                    geprueft, raus, vom_pruefer = geprueft3, raus3, vom3
                    notizen.append("Die erste Fassung ließ einen genannten Namen aus; KIplatz hat neu geantwortet.")
                    fehlend = namen_fehlen(frage, geprueft)
            except app_core.AppError:
                pass
        if fehlend:
            geprueft = geprueft.rstrip() + "\n\nZu " + " und ".join(fehlend) + " habe ich in meinen Quellen keine sichere Zahl gefunden."
            notizen.append("Zu " + ", ".join(fehlend) + " stand nichts Belegtes in der Antwort; das Programm sagt es dazu.")
    if geprueft != "Das weiß ich noch nicht.":
        geprueft, n_eigen, _ersetzt = eigene_worte(geprueft, belege.fremde_texte(quellen), umschreiben)
        notizen += n_eigen
    return geprueft, notizen


EIGENE_WORTE_RUNDEN = 2
_UMSCHRIEBEN = re.compile(r"(?m)^\s*(\d{1,2})\s*[.):]\s*(\S.*?)\s*$")


def umschreibung_lesen(text: str, anzahl: int) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in _UMSCHRIEBEN.finditer(text or ""):
        i = int(m.group(1)) - 1
        if 0 <= i < anzahl and i not in out:
            out[i] = m.group(2).strip().strip("„“\"")
    return out


def eigene_worte(text: str, fremd: list[str], umschreiben=None, *, englisch: bool = False) -> tuple[str, list[str], dict[str, str]]:
    weiss_nicht = belege.WEISS_NICHT_EN if englisch else "Das weiß ich noch nicht."
    woertlich = belege.woertliche_saetze(text, fremd) if fremd and text else []
    if not woertlich:
        return text, [], {}
    neu_text, ersetzt, runden = text, {}, 0
    while woertlich and umschreiben is not None and runden < EIGENE_WORTE_RUNDEN:
        runden += 1
        try:
            neue = umschreiben(woertlich, englisch) or {}
        except app_core.AppError:
            break
        for i, alt in enumerate(woertlich):
            neu = " ".join(str(neue.get(i) or "").split())
            if (neu and re.search(r"[.!?…“\")]$", neu) and belege.brauchbar(neu) and not belege.woertliche_saetze(neu, fremd)
                    and not _WEISS_NICHT.search(neu) and belege.zahlenwerte(alt) <= belege.zahlenwerte(neu) and belege.daten(alt) <= belege.daten(neu)
                    and alt in neu_text):
                neu_text = neu_text.replace(alt, neu, 1)
                ursprung = next((k for k, v in ersetzt.items() if v == alt), alt)
                ersetzt[ursprung] = neu
        woertlich = belege.woertliche_saetze(neu_text, fremd)
    if not woertlich:
        n = len(ersetzt)
        return neu_text, ["1 Satz stand fast wörtlich so in einer Quelle; KIplatz hat ihn in eigenen Worten geschrieben." if n == 1
                          else f"{n} Sätze standen fast wörtlich so in einer Quelle; KIplatz hat sie in eigenen Worten geschrieben."], ersetzt
    rest, raus = belege.saetze_streichen(neu_text, set(woertlich).__contains__)
    if rest.strip() and rest != "Das weiß ich noch nicht." and belege.brauchbar(rest) and not nur_rest(neu_text, rest, raus):
        return rest, ["1 Satz, der fast wörtlich so in einer Quelle stand, vom Programm gestrichen." if len(raus) == 1
                      else f"{len(raus)} Sätze, die fast wörtlich so in einer Quelle standen, vom Programm gestrichen."], ersetzt
    return weiss_nicht, ["Die Antwort stand fast wörtlich so in einer Quelle und ließ sich nicht in eigenen Worten schreiben; sie wurde nicht ausgegeben."], {}


NAMEN_ZUSATZ = ("Prüfung: Die Frage nennt mehrere Namen, eine erste Fassung dieser Antwort ließ aus: {namen}. Schreib die Antwort ganz neu und nenne "
                "zu jedem genannten Namen die Zahl, wie sie in den Quellen steht. Steht zu einem Namen nichts in den Quellen, schreib zu ihm genau: „Zu <Name> "
                "habe ich keine sichere Zahl gefunden.“ Erwähne nie eine erste Fassung, einen Fehler oder eine Korrektur. Schreib nie „Quellen“ oder „Auszüge“.")


def namen_fehlen(frage: str, antwort: str) -> list[str]:
    dinge = nachschauen.aufzaehlung(frage)
    if len(dinge) < 2:
        return []
    return [d for d in dinge if not re.search(r"(?i)(?<![\wäöüß])" + re.escape(d), antwort or "")]


_ORTSTEIL = re.compile(r"\b(?:Ortsteil|Stadtteil|Bezirk|Stadtbezirk|Gemeindebezirk|Gemeindeteil|Katastralgemeinde|Ortschaft|Stadtviertel|Quartier|Siedlung)\b", re.I)


def _titel_name(t) -> str:
    titel = str(getattr(t.quelle, "titel", "") or "")
    titel = titel.split(": ", 1)[1] if titel.startswith("Wikipedia: ") else titel
    return titel.split(" (")[0].strip()


def _ortsteil_stelle(t, namen: list[str]) -> bool:
    name_t = _titel_name(t)
    text = (t.text or "")[:400]
    for n in namen:
        if not n or name_t.lower() == n.lower():
            continue
        e = re.escape(n)
        if re.match(rf"(?i)^{e}[-–]", name_t) or re.search(rf"(?i)\({e}\)", str(getattr(t.quelle, "titel", ""))):
            return True
        if _ORTSTEIL.search(text) and re.search(rf"(?i)\b(?:{e}|{e}er)\b", text[:400]):
            return True
    return False


def nebenher_satz(lauf: dict | None) -> str:
    neben = lauf.get("nebenher") if lauf else None
    leer = lauf.get("nebenher_leer") if lauf else None
    if neben:
        if len(neben["anfragen"]) > 1:
            vorne, letzte = _aufzaehlung(neben["anfragen"])
            return (f"Nebenher wurde im Internet nach {vorne} und „{letzte}“ gesucht, falls die Fundstellen nicht reichen; "
                    "gebraucht wurde es nicht, gemerkt wurde nichts.")
        return (f"Nebenher wurde im Internet nach „{''.join(neben['anfragen'])}“ gesucht, falls die Fundstellen nicht reichen; "
                "gebraucht wurde es nicht, gemerkt wurde nichts.")
    if leer:
        if len(leer["anfragen"]) > 1:
            vorne, letzte = _aufzaehlung(leer["anfragen"])
            return f"Nebenher wurde im Internet nach {vorne} und „{letzte}“ gesucht, ohne brauchbare Seite."
        return f"Nebenher wurde im Internet nach „{''.join(leer['anfragen'])}“ gesucht, ohne brauchbare Seite."
    return ""


def _aufzaehlung(woerter: list[str]) -> tuple[str, str]:
    return ", ".join(f"„{x}“" for x in woerter[:-1]), woerter[-1]


def im_netz_gesucht(nachgeholt: bool, quellen: list[dict], lauf: dict | None) -> bool | str:
    stellen = (lauf or {}).get("stellen") or ()
    if nachgeholt or any(q.get("art") == "nachgeschaut" and q.get("kennung") not in stellen for q in quellen or []):
        return True
    if lauf and lauf.get("gesucht"):
        return "nicht_erreicht" if lauf.get("abgelehnt") else True
    return False


def _weiss_nicht_anwenden(antwort_text: str, lieferschein: dict, *, gesucht: bool | str = False, vorher: str | None = None) -> str:
    lieferschein["angebot"] = "nachpruefen"
    fakt = any(re.search(r"\d", s) and not _WEISS_NICHT.search(s) for s in pruefung.saetze(antwort_text))
    if not fakt and (_WEISS_NICHT.search(antwort_text) and not any(not _WEISS_NICHT.search(s) for s in pruefung.saetze(antwort_text)) or
                     len(pruefung.saetze(vorher if vorher is not None else antwort_text)) <= 2):
        lieferschein["quellen_liste"] = []
        if gesucht == "nicht_erreicht":
            lieferschein["quellen"] = "keine Antwort: das Modell hat es nicht gewusst, und die Suche im Internet ist nicht durchgekommen."
            lieferschein["pruefung"] = pruefung.pruefen("", []).kurz()
            lieferschein["erfunden"] = ""
            return _NICHT_ERREICHT_SATZ
        lieferschein["quellen"] = ("keine Antwort: das Modell hat es nicht gewusst, und die Suche im Internet hat nichts Verlässliches gebracht."
                                   if gesucht else "keine Antwort: das Modell hat es nicht gewusst; „Live nachprüfen“ schaut im Internet nach.")
        lieferschein["pruefung"] = pruefung.pruefen("", []).kurz()
        lieferschein["erfunden"] = ""
        return _GESUCHT_NICHTS_SATZ if gesucht else _WEISS_NICHT_SATZ
    if gesucht or _NACHPRUEFEN_ANGEBOT.lower() in antwort_text.lower():
        return antwort_text
    return antwort_text.rstrip() + "\n\n" + _NACHPRUEFEN_ANGEBOT


def ohne_markdown(text: str | None) -> str:
    t = pruefung.ohne_quellenmarke(text or "")
    t = "\n".join(z for z in t.split("\n") if not re.match(r"^\s*[-–—*_=]{3,}\s*$", z))
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"(?<!\w)\*([^*\n]{1,200})\*(?!\w)", r"\1", t)
    return "\n".join(re.sub(r"^\s*(#{1,4}\s+|[-*]\s+)", lambda m: "– " if m.group(1).strip() in ("-", "*") else "", z) for z in t.split("\n")).strip()


def titelleiste_dunkel(titel: str, an: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, titel)
        if not hwnd:
            return False
        wert = ctypes.c_int(1 if an else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(wert), ctypes.sizeof(wert))
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        return True
    except Exception:
        return False


def community_dienst_spielwiese_code() -> str:
    return "spielwiese"


def _fenster_icon_pfad() -> Path | None:
    p = webapp_dir() / "marke" / "kiplatz.ico"
    return p if p.is_file() else None


def _taskleisten_kennung_setzen() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KIplatz.Programm") == 0
    except (OSError, AttributeError):
        return False


TRAY_TEXTE = {"de": ("{0} läuft", "Fenster öffnen", "{0} beenden"), "en": ("{0} is running", "Open window", "Quit {0}")}


def _tray_bild() -> bytes:
    try:
        return (webapp_dir() / "marke" / "symbol-32.png").read_bytes()
    except OSError:
        return _tray_png()


def _tray_png(groesse: int = 32) -> bytes:
    import struct
    import zlib
    r, g, b = 0x1F, 0x5F, 0xA8
    mitte, radius = (groesse - 1) / 2.0, groesse / 2.0 - 1.0
    zeilen = bytearray()
    for y in range(groesse):
        zeilen.append(0)
        for x in range(groesse):
            d = ((x - mitte) ** 2 + (y - mitte) ** 2) ** 0.5
            a = 255 if d <= radius - 0.5 else (int(255 * (radius + 0.5 - d)) if d < radius + 0.5 else 0)
            zeilen += bytes((r, g, b, max(0, min(255, a))))

    def block(art: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", groesse, groesse, 8, 6, 0, 0, 0))
            + block(b"IDAT", zlib.compress(bytes(zeilen), 9)) + block(b"IEND", b""))


def run_window(core: app_core.AppCore, *, start_minimized: bool = False, registry: app_install.RegistryOps | None = None, anbieten: bool = False) -> None:
    import webview

    if not einmal.sperre_holen(core.base_dir):
        frei = False
        for _ in range(30):
            time.sleep(0.3)
            if einmal.sperre_holen(core.base_dir):
                frei = True
                break
        if not frei:
            einmal.zeigen_anfordern(core.base_dir)
            _log(core, "OK zweiter start: das laufende Fenster wird gezeigt")
            return

    api = Api(core, registry=registry, geraet_name=_geraet_name(core))
    if anbieten:
        api._ki.einstellung_setzen(anbieten=True, quelle="lokal")
    api.vorbereiten()
    html = sprache_einbauen((webapp_dir() / INDEX_NAME).read_text(encoding="utf-8"))
    breite, hoehe = 1180, 760
    try:
        s = webview.screens[0]
        breite, hoehe = max(960, min(1180, int(s.width * 0.9))), max(600, min(760, int(s.height * 0.84)))
    except Exception:
        pass
    _taskleisten_kennung_setzen()
    window = webview.create_window(
        " - ".join(t for t in (app_core.APP_NAME, "Spielwiese" if api.spielwiese else "") if t), html=html, js_api=api,
        width=breite, height=hoehe, min_size=(960, 600), hidden=start_minimized, background_color=GROUND, text_select=True,
    )
    api._window = window
    api.versteckt = bool(start_minimized)
    tray: list = []

    def _aufraeumen() -> None:
        for ni in tray:
            try:
                ni.Visible = False
                ni.Dispose()
            except Exception:
                pass
        tray.clear()
        hotkey.stoppen()
        vorlesen.stopp()
        api.herunterfahren()

    def _schliessen_abfangen():
        if api.schliessen_angefordert or not tray:
            _aufraeumen()
            return True
        threading.Timer(0.05, api.fenster_schliessen).start()
        return False

    window.events.closing += _schliessen_abfangen

    def _tray_einrichten() -> None:
        try:
            for _ in range(100):
                if getattr(window, "native", None) is not None:
                    break
                time.sleep(0.1)
            form = window.native
            if form is None:
                raise RuntimeError("kein Fenster")
            import clr
            clr.AddReference("System.Windows.Forms")
            clr.AddReference("System.Drawing")
            from System import Action, EventHandler
            from System.Drawing import Bitmap, Icon
            from System.IO import MemoryStream
            from System.Windows.Forms import CloseReason, ContextMenuStrip, FormClosingEventHandler, NotifyIcon, ToolStripMenuItem

            def bauen() -> None:
                ico = _fenster_icon_pfad()
                if ico is not None:
                    try:
                        form.Icon = Icon(str(ico))
                    except Exception as exc:
                        _log(core, f"INFO Fenster-Symbol nicht gesetzt: {type(exc).__name__}: {exc}")
                ni = NotifyIcon()
                bmp = Bitmap(MemoryStream(_tray_bild()))
                ni.Icon = Icon.FromHandle(bmp.GetHicon())
                menu = ContextMenuStrip()
                m_auf = ToolStripMenuItem()
                m_auf.Click += EventHandler(lambda s, e: api.fenster_zeigen())
                m_aus = ToolStripMenuItem()

                def beschriften() -> None:
                    t = TRAY_TEXTE["en" if community.SPRACHE == "en" else "de"]
                    ni.Text = t[0].format(app_core.APP_NAME)[:63]
                    m_auf.Text = t[1]
                    m_aus.Text = t[2].format(app_core.APP_NAME)
                beschriften()
                api._tray_beschriften = lambda: form.Invoke(Action(beschriften))
                m_aus.Click += EventHandler(lambda s, e: api.beenden())
                menu.Items.Add(m_auf)
                menu.Items.Add(m_aus)
                ni.ContextMenuStrip = menu
                ni.DoubleClick += EventHandler(lambda s, e: api.fenster_zeigen())
                ni.Visible = True

                def bei_schliessen(s, e) -> None:
                    if e.CloseReason != CloseReason.UserClosing:
                        api.schliessen_angefordert = True
                        e.Cancel = False
                form.FormClosing += FormClosingEventHandler(bei_schliessen)
                tray.append(ni)

            form.Invoke(Action(bauen))
            _log(core, "OK tray")
        except Exception as exc:
            _log(core, f"INFO kein tray: {type(exc).__name__}: {exc}")
            if api.versteckt:
                api.fenster_zeigen()

    threading.Thread(target=_tray_einrichten, name="tray", daemon=True).start()

    def _per_taste() -> None:
        vorgabe = ""
        if api.auswahl_an() and not api._window_vorne():
            try:
                vorgabe = auswahl.als_vorgabe(auswahl.windows_auswahl(app_core.APP_NAME))
            except Exception:
                vorgabe = ""
        api.fenster_zeigen()
        api._js(f"app.fokus({json.dumps(vorgabe, ensure_ascii=False)})")

    hotkey.starten(_per_taste, protokoll=lambda line: _log(core, line))

    def _watch_close() -> None:
        takt = 0
        while True:
            time.sleep(0.3)
            takt += 1
            if takt % 100 == 0:
                api._morgenbericht_pruefen()
            if einmal.zeigen_angefordert(core.base_dir):
                api.fenster_zeigen()
            if api.schliessen_angefordert:
                try:
                    window.destroy()
                except Exception:
                    pass
                return

    threading.Thread(target=_watch_close, name="fenster-schliessen", daemon=True).start()

    def _titel_nachziehen() -> None:
        for _ in range(50):
            time.sleep(0.2)
            if titelleiste_dunkel(window.title, api.dunkel()):
                return

    threading.Thread(target=_titel_nachziehen, name="titelleiste", daemon=True).start()
    api._titel = window.title
    if app_install.update_bestaetigen(api._install_dir):
        _log(core, "OK update bestaetigt")
    _rueckweg = app_install.rueckweg_hinweis(api._install_dir)
    if _rueckweg:
        _log(core, f"WARN update rueckweg {_rueckweg}")
    webview.start(gui="edgechromium", private_mode=True, debug=False)
    _aufraeumen()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def _geraet_name(core: app_core.AppCore | None = None) -> str:
    if core is not None:
        try:
            p = core.base_dir / heimnetz.DIRNAME / "einstellung.json"
            gewaehlt = json.loads(p.read_text(encoding="utf-8")).get("geraet_name") if p.exists() else None
            if isinstance(gewaehlt, str) and gewaehlt.strip():
                return gewaehlt.strip()[:24]
        except (OSError, ValueError, AttributeError):
            pass
    import hashlib
    kurz = hashlib.sha256((platform.node() or "geraet").encode("utf-8", "replace")).hexdigest()[:4]
    return f"Gerät-{kurz}"


def selftest(core: app_core.AppCore) -> int:
    import tempfile

    results = []
    api = Api(core, registry=app_install.MemoryRegistry())
    api.vorbereiten(selbst_einrichten=False, ki_auto=False)
    if api.prep_error:
        results.append(f"FEHLER vorbereiten: {api.prep_error}")
    for name, action in (
        ("start", api.start), ("pause", api.pause), ("stop", api.stopp),
        ("freigabe", lambda: api.freigabe_speichern(*(lambda e: (e.nur_im_leerlauf, e.cpu_prozent, e.ram_gib))(app_core.recommended_freigabe(core.load_first_start())))),
        ("speicher_grenzen", lambda: api.speicher_grenzen("")),
        ("diagnose", api.diagnose), ("zustand", api.zustand), ("gespraech", lambda: api.gespraech_neu()), ("community", api.community), ("ueber", api.ueber),
    ):
        r = action()
        results.append(("OK   " if r["ok"] else "FEHLER ") + name + ("" if r["ok"] else ": " + r["text"]))
    try:
        for p in (ki_laufzeit.LAUFZEIT, *ki_laufzeit.MODELLE.values()):
            assert p.url.startswith("https://") and len(p.sha256) == 64
        zaehler_vorher, ki_laufzeit.KARTE_ZAEHLER = ki_laufzeit.KARTE_ZAEHLER, False
        try:
            w = ki_laufzeit.waehlen(ki_laufzeit.geraete_parsen("  Vulkan1: NVIDIA GeForce RTX 4050 Laptop GPU (5920 MiB, 5152 MiB free)\n"), 15.7)
            assert w.modell.kennung == "3B" and w.geraet is not None
            assert ki_laufzeit.waehlen(ki_laufzeit.geraete_parsen("  Vulkan1: NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB, 7600 MiB free)\n"), 15.7).modell.kennung == "8B"
        finally:
            ki_laufzeit.KARTE_ZAEHLER = zaehler_vorher
        vorher_auto = api.ki_auto()
        api._ki.einstellung_setzen(ki_auto=False)
        try:
            g = api.gespraech_neu()["daten"]
            r = api.frage(g["kennung"], "hallo", ki_starten=False)
            assert not r["ok"] and "ausgeschaltet" in r["text"], r["text"]
        finally:
            api._ki.einstellung_setzen(ki_auto=vorher_auto)
        results.append(f"OK   ki (Katalog geprüft, Laufzeit {'vorhanden' if api._ki.ordner.laufzeit_da() else 'noch nicht geholt'}, Frage ohne KI sauber abgelehnt)")
    except Exception as exc:
        results.append(f"FEHLER ki: {type(exc).__name__}: {exc}")
    try:
        import socket as _socket

        with _socket.socket() as _s:
            _s.bind(("127.0.0.1", 0))
            port = _s.getsockname()[1]
        basis = Path(tempfile.mkdtemp(prefix="communityai-heimnetz-"))

        class _A:
            text, prompt_tokens, completion_tokens, dauer_s = "Probe.", 1, 1, 0.1
        d = heimnetz.Dienst(basis / "pc", frage_fn=lambda n, t: (t("Probe."), _A())[1], name="PC-Selbsttest", adresse="127.0.0.1", port=port, loopback_erlaubt=True)
        d.start()
        try:
            v = heimnetz.Verbindung(basis / "laptop", geraet_name_eigen="Laptop-Selbsttest", loopback_erlaubt=True)
            abgelehnt = False
            try:
                v.koppeln("127.0.0.1", "AAAA-AAAA", port=port)
            except heimnetz.HeimnetzError:
                abgelehnt = True
            code = d.koppeln_oeffnen()
            v.koppeln("127.0.0.1", code, port=port)
            a = v.frage([{"role": "user", "content": "hi"}])
            assert abgelehnt and a.text == "Probe." and d.geraete.liste()[0]["name"] == "Laptop-Selbsttest"
            assert d.geraete.entfernen("Laptop-Selbsttest")
        finally:
            d.stop()
        results.append("OK   heimnetz (Zertifikat erzeugt, Koppeln mit Code, falscher Code abgelehnt, Antwort über gepinnte Verbindung, Gerät entfernt)")
    except Exception as exc:
        results.append(f"FEHLER heimnetz: {type(exc).__name__}: {exc}")
    exe = app_install.running_exe()
    if exe is None:
        results.append("INFO install: läuft aus der Quelle, nichts zu installieren")
    else:
        try:
            tmp = Path(tempfile.mkdtemp(prefix="communityai-selbsttest-"))
            info = app_install.install(exe, tmp / "CommunityAI")
            reg = app_install.MemoryRegistry()
            app_install.autostart_enable(info.exe_path, registry=reg)
            removed = app_install.uninstall(tmp / "CommunityAI", registry=reg)
            results.append(f"OK   install/autostart/uninstall (Probe in {tmp.name}, {len(removed)} Objekte entfernt)")
        except Exception as exc:
            results.append(f"FEHLER install: {type(exc).__name__}: {exc}")
    report = core.diagnosis_dir / "selbsttest.txt"
    sicher_schreiben.text(report, app_core._mask(chr(10).join(results)) + chr(10))
    print(chr(10).join(results))
    return 0 if all(r.startswith(("OK", "INFO")) for r in results) else 1


def windows_zertifikate(core: app_core.AppCore | None = None, *, system: str | None = None) -> bool:
    if (system or platform.system()) != "Windows":
        return False
    try:
        import ssl
        import urllib.request
        import truststore
    except ImportError:
        if core is not None:
            _log(core, "FEHLER zertifikate: truststore fehlt; Seiten ohne vollständige Zertifikatskette (bmf.gv.at) lassen sich nicht lesen")
        return False
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))
    if core is not None:
        _log(core, "OK zertifikate: Webseiten werden über Windows geprüft (truststore)")
    return True


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        core, args = build_core(argv)
    except app_core.AppError as exc:
        print(f"ABGELEHNT [{exc.code}] {exc.detail}")
        return 1
    windows_zertifikate(core)
    if not (args.selbsttest or args.ki_holen or args.entfernen):
        _root = app_install.portable_root()
        if _root is not None and app_install.grundlage_beim_start_einsetzen(_root, list(sys.argv[1:] if argv is None else argv)):
            return 0
    if args.selbsttest:
        return selftest(core)
    if args.ki_holen:
        return ki_holen(core)
    if args.entfernen:
        api = Api(core, geraet_name=_geraet_name(core))
        api.beenden()
        r = api.entfernen()
        print(r["text"])
        return 0 if r["ok"] else 1
    run_window(core, start_minimized=bool(args.autostart), anbieten=bool(args.anbieten))
    return 0


def ki_holen(core: app_core.AppCore) -> int:
    ki = KiSteuerung(core)
    if ki.quelle() != "lokal":
        print("ABGELEHNT: dieses Gerät fragt ein anderes Gerät; nichts zu holen")
        return 1
    core.ensure_directories()
    ki.einschalten()
    letzte = ""
    while ki.phase in ("laden", "starten"):
        z = ki.zustand()
        f = z["fortschritt"]
        zeile = f["was"] + (f" {f['done'] // 2**20} von {f['gesamt'] // 2**20} MB" if f["gesamt"] else "")
        if zeile != letzte:
            print(zeile, flush=True)
            letzte = zeile
        time.sleep(2)
    z = ki.zustand()
    if z["phase"] != "bereit":
        print(f"FEHLER: {z['meldung']}")
        return 1
    print(f"BEREIT: {ki.meldung}")
    try:
        a = ki.server.frage([{"role": "user", "content": "Was ist die Hauptstadt von Österreich? Ein Satz."}], max_tokens=60)
        print(f"PROBE: {a.text} ({a.dauer_s} s, {a.completion_tokens} Wortstücke)")
    finally:
        ki.ausschalten()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
