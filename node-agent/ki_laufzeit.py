# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import atexit
import base64
import hashlib
import http.client
import json
import os
import platform
import random
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import weakref
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime

_ABBRUCH_FADEN = threading.local()


@contextmanager
def abbruch_bei(ereignis: threading.Event):
    vorher = getattr(_ABBRUCH_FADEN, "ev", None)
    _ABBRUCH_FADEN.ev = ereignis
    try:
        yield
    finally:
        _ABBRUCH_FADEN.ev = vorher


_ORIGINAL_FADEN = threading.local()
ORIGINAL_HINWEIS = ("Die Person hat auf Englisch gefragt: „{0}“. Die Frage im Gespräch ist eine Übersetzung davon; wenn ein Wort dort etwas "
                    "anderes heißt als im Original, gilt das Original. Antworte trotzdem auf Deutsch.")


def original_setzen(text: str) -> None:
    _ORIGINAL_FADEN.text = " ".join(str(text or "").split())[:400]


def original() -> str:
    return getattr(_ORIGINAL_FADEN, "text", "")
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import stueckliste
import selbstauskunft

KI_DIRNAME = "ki"
CHUNK = 1024 * 1024
MAX_LOG_TAIL = 4000


from modell_katalog import (
    BEWERTUNG, EMBEDDING, EMBEDDING_DIMENSION, HOEREN, MODELL_REIHENFOLGE, MODELLE, Modell, Paket, laufzeit_hier,
)

LAUFZEIT = laufzeit_hier()
SERVER_EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"

TEMPERATUR = 0.05

SYSTEMTEXT = (
    "Du bist KIplatz, eine KI aus Österreich, offen für alle auf der Welt. "
    "Antworte auf Deutsch, in einfacher, menschlicher Alltagssprache, kurz vor lang, Zahlen als Ziffern. "
    "Tu genau das, was verlangt ist, nicht mehr und nicht weniger. Mach keine ungefragten Vorschläge. "
    "Die wichtigste Regel: Erfinde nichts. Einzige Ausnahme: Bekommst du unten Auszüge aus dem Wissensspeicher der "
    "Community, dann gilt das darin als gesichert; was dort steht, gibst du in eigenen Worten wieder, auch über Websites, Firmen oder "
    "Personen, die du sonst nicht kennst, und nennst die Quelle. "
    "Schreib immer in eigenen Worten und mit eigenem Satzbau, übernimm nie ganze Sätze oder längere Wortfolgen aus den Auszügen. "
    "Zahlen, Namen und Daten übernimmst du genau so, wie sie dort stehen. "
    "Du selbst gehst nicht ins Internet; das Programm schaut für dich nach "
    "und gibt dir die Treffer als Auszüge mit, die mit „nachgeschaut“ sind von heute. "
    "Was in jedem Lexikon oder Ratgeber steht, sagst du selbst, für die ganze Welt: Länder und Städte überall, Naturwissenschaft, Geschichte, "
    "Begriffe, Kochen, Haushalt, Gesundheit allgemein, Technik im Alltag. Angaben, die sich ändern oder die nur eine bestimmte Quelle sicher weiß, "
    "sagst du nur, wenn sie in den Auszügen stehen: Ergebnisse und Ereignisse von heute oder den letzten Tagen, Preise, Termine, Öffnungszeiten, "
    "Gesetze, Fristen, Förderungen, eine bestimmte Firma, Person, Website oder ein kleiner Ort. Fehlt so etwas in den Auszügen, antwortest du mit "
    "genau einem Satz: „Das weiß ich noch nicht.“ Dann sucht das Programm von selbst. "
    "Beispiele: „Was macht die Firma Huber in Gmunden?“, „Was steht auf beispiel.at?“, „Wie ist das Spiel heute ausgegangen?“ "
    "bekommen ohne passenden Auszug diese eine Antwort; „Wie viele Einwohner hat Neapel?“ oder „Was hilft gegen Sonnenbrand?“ beantwortest du. "
    "„Wer war Mozart?“ beantwortest du, „Wer ist Maria Huber aus Wels?“ nicht. "
    "Du zählst keine Möglichkeiten auf und schreibst nicht „möglicherweise“, „könnte“, „vermutlich“ oder „wahrscheinlich“ über Dinge, die du "
    "nicht kennst. Eine Zahl, die du nur ungefähr weißt, bekommt „rund“ oder „etwa“. "
    "Zahlen, die in der Frage stehen (Mengen, Preise, Maße, Daten), sind gegeben. Rechenaufgaben damit (Menge mal Preis, Summe, Prozent, "
    "Umrechnung, Tage zwischen Daten) rechnest du selbst und zeigst den Rechenweg in einer Zeile, zum Beispiel: 3 × 9,90 € = 29,70 €. "
    "Ist ein Auftrag unklar, stell eine kurze Rückfrage, statt zu raten. "
    "In der Antwort schreibst du nie „Auszüge“ oder „Wissensspeicher“. "
    "Platzordnung: Du schreibst nichts, was Menschen verletzt oder strafbar ist: keine NS-Verherrlichung und keine Verharmlosung des Holocaust, "
    "nichts Sexuelles mit Kindern, keine Pornographie, keine Aufrufe zu Gewalt, keine Anleitungen zu Waffen oder Sprengstoff, keine Beschimpfung von "
    "Menschen wegen Herkunft, Religion, Geschlecht oder Behinderung. Wird so etwas verlangt, antwortest du mit genau einem Satz: „Das gehört nicht in diese Community.“ "
    "Keine Werbesprache, keine Floskeln, keine Emojis. Schreib in ganzen Sätzen ohne Markdown-Zeichen: "
    "keine Sternchen, keine Rauten, keine fette Schrift; Aufzählungen nur als kurze Zeilen mit einem Gedankenstrich. "
    "So schreibt ein Mensch, so schreibst du: kurze Sätze, schlichte Wörter (ist, hat, schrieb, starb), das Wichtigste zuerst. "
    "Österreichisches Deutsch (Jänner, Umsatzsteuer, Kostenvoranschlag), Umlaute immer als ä, ö, ü, ß. „Hätte“ bei Zeit und Interesse (Hätten Sie Zeit?). "
    "Keine Wörter wie „bedeutend“, „spannend“, „nahtlos“, „beleuchten“, „eintauchen“, „robust“, „entscheidend“. Kein „nicht nur, sondern auch“, "
    "kein Dreierschema (schnell, sicher und einfach), keine Absätze, die mit „Darüber hinaus“ oder „Zusätzlich“ beginnen, wenige Gedankenstriche. "
    "Kein Fazit und keine Zusammenfassung am Ende, kein „Ich hoffe, das hilft“, kein „Gerne!“. Keine Frage zurück, außer dir fehlt etwas, das du für die Aufgabe brauchst. "
    "Über dich selbst sagst du nur, was oben steht: KIplatz, eine KI aus Österreich, offen für alle auf der Welt. Du erfindest kein Team, "
    "keine Firma und keine Geschichte dazu."
)

SYSTEMTEXT_KURZ = (
    "Du bist KIplatz, eine KI aus Österreich, offen für alle. Antworte auf Deutsch, kurz, in einfacher Alltagssprache, Zahlen als Ziffern, "
    "Umlaute als ä, ö, ü, ß, ohne Markdown-Zeichen, ohne Floskeln, ohne Emojis, kein Fazit, keine Frage am Ende. Tu genau das, was verlangt ist. "
    "Erfinde nichts. Bekommst du unten Auszüge aus dem Wissensspeicher, gilt das darin als gesichert; gib es in eigenen Worten wieder und nenne die Quelle. "
    "Das Programm schaut für dich nach. Lexikon- und Alltagswissen der ganzen Welt sagst du selbst. Ergebnisse von heute, Preise, Termine, Gesetze, "
    "bestimmte Firmen, Personen, Websites, kleine Orte nur aus den Auszügen; fehlt es dort, sag nur: „Das weiß ich noch nicht.“ "
    "Schreib nicht „möglicherweise“ oder „vermutlich“ über Unbekanntes; eine ungefähre Zahl bekommt „rund“. "
    "Zahlen in der Frage sind gegeben; Rechenaufgaben damit rechnest du selbst mit dem Rechenweg in einer Zeile. Rückfrage nur, wenn unklar. "
    "Regeln: nichts, was Menschen verletzt oder strafbar ist (keine NS-Verherrlichung, nichts Sexuelles mit Kindern, keine Pornographie, "
    "keine Gewaltaufrufe, keine Waffenanleitungen, keine Beschimpfung wegen Herkunft, Religion, Geschlecht oder Behinderung); "
    "wird so etwas verlangt: „Das gehört nicht in diese Community.“ Über dich selbst sagst du nur, was oben steht."
)


class KiError(app_core.AppError):
    pass


WINDOWS_SPERRE_FEHLER = {4551, 1260}
WINDOWS_SPERRE_PAUSE_S = 30 * 60
WINDOWS_SPERRE_TEXT = ("Windows lässt die KI auf diesem Gerät gerade nicht starten (Smart App Control). Deine Fragen beantworten die PCs "
                       "der Community. Das Programm versucht es in 30 Minuten wieder von selbst.")
_windows_sperre_bis = 0.0


UNTERSCHRIFT_PRUEFEN = True
_unterschrift_gemerkt: dict[tuple, bool] = {}


def unterschrift_gueltig(pfad: Path) -> bool:
    try:
        st = Path(pfad).stat()
    except OSError:
        return False
    schluessel = (str(pfad), st.st_size, st.st_mtime_ns)
    if schluessel in _unterschrift_gemerkt:
        return _unterschrift_gemerkt[schluessel]
    ok = _winverifytrust(str(pfad))
    if len(_unterschrift_gemerkt) > 64:
        _unterschrift_gemerkt.clear()
    _unterschrift_gemerkt[schluessel] = ok
    return ok


def _winverifytrust(pfad: str) -> bool:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE), ("pgKnownSubject", ctypes.c_void_p)]

    class WINTRUST_DATA(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p), ("pSIPClientData", ctypes.c_void_p),
                    ("dwUIChoice", wintypes.DWORD), ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)), ("dwStateAction", wintypes.DWORD), ("hWVTStateData", wintypes.HANDLE),
                    ("pwszURLReference", wintypes.LPCWSTR), ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    aktion = GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    datei = WINTRUST_FILE_INFO(ctypes.sizeof(WINTRUST_FILE_INFO), pfad, None, None)
    WTD_UI_NONE, WTD_REVOKE_NONE, WTD_CHOICE_FILE = 2, 0, 1
    WTD_STATEACTION_VERIFY, WTD_STATEACTION_CLOSE = 1, 2
    WTD_CACHE_ONLY_URL_RETRIEVAL = 0x1000
    daten = WINTRUST_DATA(ctypes.sizeof(WINTRUST_DATA), None, None, WTD_UI_NONE, WTD_REVOKE_NONE, WTD_CHOICE_FILE, ctypes.pointer(datei),
                          WTD_STATEACTION_VERIFY, None, None, WTD_CACHE_ONLY_URL_RETRIEVAL, 0, None)
    try:
        wvt = ctypes.WinDLL("wintrust.dll").WinVerifyTrust
        wvt.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.c_void_p]
        wvt.restype = ctypes.c_long
        ergebnis = wvt(None, ctypes.byref(aktion), ctypes.byref(daten))
        daten.dwStateAction = WTD_STATEACTION_CLOSE
        wvt(None, ctypes.byref(aktion), ctypes.byref(daten))
        return ergebnis == 0
    except (OSError, AttributeError):
        return False


def windows_sperre_aktiv(jetzt: float | None = None) -> bool:
    return (time.time() if jetzt is None else jetzt) < _windows_sperre_bis


def _windows_sperre_pruefen() -> None:
    if windows_sperre_aktiv():
        raise KiError("KI_BLOCKIERT", WINDOWS_SPERRE_TEXT)


def _windows_sperre_merken(exc: OSError) -> None:
    global _windows_sperre_bis
    if getattr(exc, "winerror", None) in WINDOWS_SPERRE_FEHLER:
        _windows_sperre_bis = time.time() + WINDOWS_SPERRE_PAUSE_S
        raise KiError("KI_BLOCKIERT", WINDOWS_SPERRE_TEXT) from None


WINDOWS_SPERRE_CODES = {0xC0E90002, 0xC0000428}


def _sperre_am_code(returncode) -> None:
    global _windows_sperre_bis
    if isinstance(returncode, int) and (returncode & 0xFFFFFFFF) in WINDOWS_SPERRE_CODES:
        _windows_sperre_bis = time.time() + WINDOWS_SPERRE_PAUSE_S
        raise KiError("KI_BLOCKIERT", WINDOWS_SPERRE_TEXT)


def _ohne_windows_fenster() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetErrorMode(k32.SetErrorMode(0) | 0x0001 | 0x8000)
    except Exception:
        pass


KI_VERWEIS = "ki-ordner.txt"


class KiOrdner:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.ki_dir = self.base_dir / KI_DIRNAME
        try:
            verweis = (self.base_dir / KI_VERWEIS).read_text(encoding="utf-8").strip() if (self.base_dir / KI_VERWEIS).is_file() else ""
            if verweis and Path(verweis).is_dir() and not app_core._is_reparse(Path(verweis)):
                self.ki_dir = Path(verweis)
        except (OSError, UnicodeDecodeError):
            pass
        self.downloads_dir = self.ki_dir / "downloads"
        self.laufzeit_dir = self.ki_dir / "laufzeit" / LAUFZEIT.kennung
        self.modelle_dir = self.ki_dir / "modelle"
        self.server_exe = self.laufzeit_dir / SERVER_EXE
        self.log_path = self.ki_dir / "server.log"
        self.wahl_path = self.ki_dir / "wahl.json"

    def anlegen(self) -> None:
        for p in (self.ki_dir, self.downloads_dir, self.laufzeit_dir.parent, self.modelle_dir):
            app_core.ensure_plain_directory(p)

    def laufzeit_da(self) -> bool:
        if not self.server_exe.is_file():
            return False
        if not UNTERSCHRIFT_PRUEFEN:
            return True
        if sys.platform != "win32":
            return laufzeit_wie_im_archiv(self.server_exe, self.downloads_dir / LAUFZEIT.datei, LAUFZEIT)
        return not LAUFZEIT.unterschrift or unterschrift_gueltig(self.server_exe)

    def modell_pfad(self, modell: Modell) -> Path:
        return self.modelle_dir / modell.datei

    def modell_da(self, modell: Modell) -> bool:
        p = self.modell_pfad(modell)
        try:
            return p.is_file() and p.stat().st_size == modell.groesse
        except OSError:
            return False

    def bilder_pfad(self, modell: Modell) -> Path | None:
        return self.modelle_dir / modell.bilder.datei if modell.bilder else None

    def bilder_da(self, modell: Modell) -> bool:
        p = self.bilder_pfad(modell)
        try:
            return bool(p) and p.is_file() and p.stat().st_size == modell.bilder.groesse
        except OSError:
            return False


PROBEMODELL = "probemodell.json"
PROBE_MIN_BYTES = 100 * 1024 * 1024
_PROBE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.gguf")


def probemodell(ordner: KiOrdner, nacht: str) -> tuple[Path, dict] | None:
    try:
        d = json.loads((ordner.ki_dir / PROBEMODELL).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(d, dict):
        return None
    datei, sha, basis = str(d.get("datei", "")), str(d.get("sha256", "")).lower(), str(d.get("basis", ""))
    bestellt = str(d.get("nacht", ""))
    if bestellt != nacht and _nachholen(bestellt, nacht) and str(d.get("gemeldet", "")) != bestellt:
        d["nacht"], d["erledigt"] = nacht, ""
        try:
            (ordner.ki_dir / PROBEMODELL).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        except OSError:
            return None
        bestellt = nacht
    if (bestellt != nacht or str(d.get("erledigt", "")) == nacht or not _PROBE_NAME.fullmatch(datei)
            or not re.fullmatch(r"[0-9a-f]{64}", sha) or basis not in MODELLE
            or any(datei == m.datei or (m.bilder and datei == m.bilder.datei) for m in MODELLE.values())):
        return None
    p = ordner.modelle_dir / datei
    try:
        if not p.is_file() or p.stat().st_size < PROBE_MIN_BYTES:
            return None
    except OSError:
        return None
    return p, {"datei": datei, "sha256": sha, "basis": basis, "nacht": nacht}


PROBE_NACHHOLEN_TAGE = 7


def _nachholen(bestellt: str, nacht: str) -> bool:
    try:
        tage = (datetime.strptime(nacht, "%Y-%m-%d").date() - datetime.strptime(bestellt, "%Y-%m-%d").date()).days
    except ValueError:
        return False
    return 0 < tage <= PROBE_NACHHOLEN_TAGE


def probemodell_gemeldet(ordner: KiOrdner, nacht: str) -> None:
    p = ordner.ki_dir / PROBEMODELL
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and str(d.get("nacht", "")) == nacht:
            d["gemeldet"] = nacht
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    except (OSError, ValueError, UnicodeDecodeError):
        pass


def probemodell_erledigt(ordner: KiOrdner, nacht: str) -> None:
    p = ordner.ki_dir / PROBEMODELL
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d["erledigt"] = nacht
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    except (OSError, ValueError, UnicodeDecodeError):
        pass


def probemodell_nochmal(ordner: KiOrdner, nacht: str, neu: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(neu or "")) or not str(neu) > str(nacht):
        return False
    p = ordner.ki_dir / PROBEMODELL
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or str(d.get("nacht", "")) != nacht:
            return False
        d["nacht"], d["erledigt"] = str(neu), ""
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        return True
    except (OSError, ValueError, UnicodeDecodeError):
        return False


def probemodell_freigeben(ordner: KiOrdner, nacht: str) -> bool:
    p = ordner.ki_dir / PROBEMODELL
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or str(d.get("nacht", "")) != nacht or str(d.get("erledigt", "")) != nacht:
            return False
        d["erledigt"], d["unterbrochen"] = "", nacht
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        return True
    except (OSError, ValueError, UnicodeDecodeError):
        return False


def probe_pruefsumme_ok(pfad: Path, sha256: str) -> bool:
    h = hashlib.sha256()
    try:
        with open(pfad, "rb") as f:
            for stueck in iter(lambda: f.read(8 * 1024 * 1024), b""):
                h.update(stueck)
    except OSError:
        return False
    return h.hexdigest() == sha256.lower()


Fortschritt = Callable[[int, int], None]


_download_locks: dict[str, threading.Lock] = {}
_download_locks_riegel = threading.Lock()


def _download_lock_fuer(ziel: Path) -> threading.Lock:
    with _download_locks_riegel:
        return _download_locks.setdefault(str(Path(ziel)), threading.Lock())


WARTEN_TEXT = "Einen kurzen Moment bitte, unser Server ist gerade ausgelastet. Dein KIplatz wird gleich fertig eingerichtet."
AUSGELASTET_PAUSE_S = (4.0, 12.0)
AUSGELASTET_HOECHSTENS_S = 45 * 60
UNTERBROCHEN_VERSUCHE = 3
UNTERBROCHEN_PAUSE_S = 3.0


def herunterladen(paket: Paket, ziel: Path, *, fortschritt: Fortschritt | None = None, oeffner=None,
                  warten: Callable[[str], None] | None = None, schlafen=time.sleep, pc_quellen=None) -> Path:
    if oeffner is None:
        oeffner = __import__("datenfluss").oeffner("Modell oder KI-Laufzeit holen")
    return _herunterladen_von_quellen(paket, ziel, fortschritt=fortschritt, oeffner=oeffner, warten=warten, schlafen=schlafen, pc_quellen=pc_quellen)


def _herunterladen_von_quellen(paket: Paket, ziel: Path, *, fortschritt: Fortschritt | None = None, oeffner=urllib.request.urlopen,
                               warten: Callable[[str], None] | None = None, schlafen=time.sleep, pc_quellen=None) -> Path:
    quellen = paket.quellen
    if not quellen or any(not q.startswith("https://") for q in quellen):
        raise KiError("KI_QUELLE", "nur verschlüsselte Quellen (https) sind erlaubt")
    url = quellen[0]
    with _download_lock_fuer(ziel):
        if pruefsumme_ok(ziel, paket):
            return ziel
        anfang = time.monotonic()
        abgerissen = 0
        liste = _stueckliste(paket, url, oeffner)
        if liste and pc_quellen is not None:
            try:
                for pc_oeffner, melden, fertig in pc_quellen(paket):
                    try:
                        return _herunterladen(paket, url, ziel, fortschritt=fortschritt, oeffner=pc_oeffner, liste=liste)
                    except KiError as exc:
                        if exc.code == "KI_STUECK":
                            melden()
                    finally:
                        fertig()
            except Exception:
                pass
        while True:
            try:
                return _herunterladen(paket, url, ziel, fortschritt=fortschritt, oeffner=oeffner, liste=liste)
            except KiError as exc:
                if exc.code == "KI_AUSGELASTET":
                    if time.monotonic() - anfang > AUSGELASTET_HOECHSTENS_S:
                        raise KiError("KI_DOWNLOAD", f"{paket.name}: unser Server war länger ausgelastet; das Programm versucht es beim nächsten Start wieder") from None
                    if warten:
                        warten(WARTEN_TEXT)
                    vorgabe = getattr(exc, "warte_s", None)
                    pause = (vorgabe + random.uniform(0, AUSGELASTET_PAUSE_S[0])) if vorgabe else random.uniform(*AUSGELASTET_PAUSE_S)
                    schlafen(pause)
                    if liste is None:
                        liste = _stueckliste(paket, url, oeffner)
                    continue
                if exc.code in ("KI_DOWNLOAD", "KI_STUECK") and abgerissen < UNTERBROCHEN_VERSUCHE:
                    abgerissen += 1
                    schlafen(UNTERBROCHEN_PAUSE_S)
                    continue
                if exc.code == "KI_STUECK":
                    raise KiError("KI_PRUEFSUMME", f"{paket.name}: ein Stück kam dreimal falsch an; beim nächsten Start geht es ab dort weiter") from None
                if exc.code == "KI_ABGELEHNT":
                    raise KiError("KI_DOWNLOAD", exc.detail) from None
                raise


def _stueckliste(paket: Paket, url: str, oeffner) -> bytes | None:
    soll = getattr(paket, "stuecke_sha256", "")
    if not soll:
        return None
    try:
        req = urllib.request.Request(url + stueckliste.ENDUNG, headers={"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"})
        with oeffner(req, timeout=30) as resp:
            daten = resp.read(stueckliste.anzahl(paket.groesse) * stueckliste.PRUEFWERT + 1)
    except (OSError, ValueError):
        return None
    return daten if stueckliste.liste_ok(daten, paket.groesse, soll) else None


def _herunterladen(paket: Paket, url: str, ziel: Path, *, fortschritt: Fortschritt | None, oeffner, liste: bytes | None = None) -> Path:
    app_core.ensure_plain_directory(ziel.parent)
    teil = ziel.with_name(ziel.name + ".teil")
    h, done = _teil_aufnehmen(teil, paket)
    try:
        kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
        if done:
            kopf["Range"] = f"bytes={done}-"
        req = urllib.request.Request(url, headers=kopf)
        with oeffner(req, timeout=60) as resp:
            if done and getattr(resp, "status", 206) != 206:
                h, done = hashlib.sha256(), 0
            stueck_h = _stueck_anfang(teil, done) + [None] if liste else None
            with open(teil, "ab" if done else "wb") as out:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    if done + len(chunk) > paket.groesse:
                        raise KiError("KI_PRUEFSUMME", f"{paket.name}: die Datei ist größer als erwartet")
                    out.write(chunk)
                    if liste:
                        try:
                            _stuecke_pruefen(paket, liste, stueck_h, chunk, done, out, h)
                        except KiError as exc:
                            if exc.code == "KI_STUECK" and stueck_h[1] is not None:
                                _teil_merken(teil, stueck_h[1][0], stueck_h[1][1])
                            raise
                    h.update(chunk)
                    done += len(chunk)
                    if fortschritt:
                        fortschritt(done, paket.groesse)
    except urllib.error.HTTPError as exc:
        _teil_merken(teil, done, h)
        if exc.code in (429, 500, 502, 503, 504):
            fehler = KiError("KI_AUSGELASTET", f"{paket.name}: {_kurz(url)} ist ausgelastet ({exc.code})")
            fehler.warte_s = _retry_after(exc)
            raise fehler from None
        raise KiError("KI_ABGELEHNT", f"{paket.name}: Download von {_kurz(url)} abgelehnt ({exc.code})") from None
    except OSError as exc:
        _teil_merken(teil, done, h)
        raise KiError("KI_DOWNLOAD", f"{paket.name}: Download von {_kurz(url)} unterbrochen ({exc.__class__.__name__})") from None
    except KiError as exc:
        _teil_stand.pop(str(teil), None)
        if exc.code != "KI_STUECK":
            _still_loeschen(teil)
        raise
    _teil_stand.pop(str(teil), None)
    if done != paket.groesse or h.hexdigest() != paket.sha256:
        _still_loeschen(teil)
        raise KiError("KI_PRUEFSUMME", f"{paket.name}: Prüfsumme oder Größe stimmt nicht, Datei verworfen")
    os.replace(teil, ziel)
    return ziel


_teil_stand: dict[str, tuple[int, "hashlib._Hash"]] = {}


def _stueck_anfang(teil: Path, done: int):
    sh = hashlib.sha256()
    vorn = done % stueckliste.STUECK
    if vorn:
        with open(teil, "rb") as f:
            f.seek(done - vorn)
            sh.update(f.read(vorn))
    return [sh]


def _stuecke_pruefen(paket: Paket, liste: bytes, stueck_h: list, chunk: bytes, done: int, out, h=None) -> None:
    pos = done
    rest = chunk
    while rest:
        im = pos % stueckliste.STUECK
        nimm = min(len(rest), stueckliste.STUECK - im)
        stueck_h[0].update(rest[:nimm])
        pos += nimm
        rest = rest[nimm:]
        if pos % stueckliste.STUECK == 0 or pos == paket.groesse:
            nr = (pos - 1) // stueckliste.STUECK
            if stueck_h[0].digest() != stueckliste.pruefwert(liste, nr):
                out.flush()
                out.truncate(nr * stueckliste.STUECK)
                raise KiError("KI_STUECK", f"{paket.name}: Stück {nr + 1} von {stueckliste.anzahl(paket.groesse)} stimmt nicht, wird neu geholt")
            stueck_h[0] = hashlib.sha256()
            if h is not None:
                g = h.copy()
                g.update(chunk[:pos - done])
                stueck_h[1] = (pos, g)


def _teil_merken(teil: Path, done: int, h) -> None:
    if done > 0:
        _teil_stand[str(teil)] = (done, h.copy())


def _retry_after(exc) -> float | None:
    try:
        w = float((exc.headers or {}).get("Retry-After", ""))
    except (TypeError, ValueError, AttributeError):
        return None
    return w if 0 < w <= 600 else None


def _teil_aufnehmen(teil: Path, paket: Paket) -> tuple["hashlib._Hash", int]:
    h = hashlib.sha256()
    try:
        n = teil.stat().st_size
    except OSError:
        return h, 0
    gemerkt = _teil_stand.get(str(teil))
    if gemerkt and gemerkt[0] == n and 0 < n < paket.groesse:
        return gemerkt[1].copy(), n
    if n <= 0 or n >= paket.groesse:
        _still_loeschen(teil)
        return hashlib.sha256(), 0
    try:
        with open(teil, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        _still_loeschen(teil)
        return hashlib.sha256(), 0
    return h, n


def _kurz(url: str) -> str:
    try:
        return url.split("/", 3)[2]
    except IndexError:
        return url


def _still_loeschen(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


def pruefsumme_ok(pfad: Path, paket: Paket) -> bool:
    try:
        if pfad.stat().st_size != paket.groesse:
            return False
        h = hashlib.sha256()
        with open(pfad, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.update(chunk)
        return h.hexdigest() == paket.sha256
    except OSError:
        return False


def _tar_mitglieder(tar) -> dict[str, "object"]:
    alle = {m.name: m for m in tar.getmembers()}
    out = {}
    for m in alle.values():
        name = Path(m.name).name
        if not name or name.startswith(".") or m.isdir():
            continue
        quelle = m
        for _ in range(8):
            if not (quelle.issym() or quelle.islnk()):
                break
            ziel = quelle.linkname if quelle.islnk() else str(Path(quelle.name).parent / quelle.linkname)
            ziel = os.path.normpath(ziel).replace(os.sep, "/")
            quelle = alle.get(ziel) or alle.get("./" + ziel)
            if quelle is None:
                break
        if quelle is not None and quelle.isfile():
            out[name] = quelle
    return out


_archiv_gemerkt: dict[tuple, bool] = {}


def laufzeit_wie_im_archiv(exe: Path, archiv: Path, paket: Paket) -> bool:
    import tarfile
    ordner = exe.parent
    try:
        sa = archiv.stat()
        stand = tuple(sorted((q.name, q.stat().st_size, q.stat().st_mtime_ns) for q in ordner.iterdir() if q.is_file()))
    except OSError:
        return False
    schluessel = (str(ordner), stand, sa.st_size, sa.st_mtime_ns)
    if schluessel in _archiv_gemerkt:
        return _archiv_gemerkt[schluessel]
    ok = False
    if exe.is_file() and pruefsumme_ok(archiv, paket):
        try:
            with tarfile.open(archiv, "r:*") as tar:
                mitglieder = _tar_mitglieder(tar)
                ok = exe.name in mitglieder
                for name, m in mitglieder.items():
                    ziel = ordner / name
                    if not ok:
                        break
                    if ziel.is_symlink() or not ziel.is_file() or ziel.stat().st_size != m.size:
                        ok = False
                        break
                    h_archiv, h_datei = hashlib.sha256(), hashlib.sha256()
                    with tar.extractfile(m) as f, open(ziel, "rb") as g:
                        for chunk in iter(lambda: f.read(CHUNK), b""):
                            h_archiv.update(chunk)
                        for chunk in iter(lambda: g.read(CHUNK), b""):
                            h_datei.update(chunk)
                    ok = h_archiv.digest() == h_datei.digest()
        except (tarfile.TarError, OSError):
            ok = False
    if len(_archiv_gemerkt) > 16:
        _archiv_gemerkt.clear()
    _archiv_gemerkt[schluessel] = ok
    return ok


_entpacken_locks: dict[str, threading.Lock] = {}
_entpacken_locks_riegel = threading.Lock()


def laufzeit_entpacken(zip_pfad: Path, ziel_dir: Path, *, schon_da: Callable[[], bool] | None = None) -> Path:
    with _entpacken_locks_riegel:
        sperre = _entpacken_locks.setdefault(str(Path(ziel_dir).resolve()), threading.Lock())
    with sperre:
        if schon_da is not None and schon_da():
            return Path(ziel_dir).resolve() / SERVER_EXE
        return _laufzeit_entpacken(zip_pfad, ziel_dir)


def _laufzeit_entpacken(zip_pfad: Path, ziel_dir: Path) -> Path:
    app_core.ensure_plain_directory(ziel_dir)
    root = ziel_dir.resolve()
    if not zipfile.is_zipfile(zip_pfad):
        import tarfile
        try:
            with tarfile.open(zip_pfad, "r:*") as tar:
                for name, m in _tar_mitglieder(tar).items():
                    target = root / name
                    if target.parent != root:
                        raise KiError("KI_LAUFZEIT", "Archiv enthält einen unerlaubten Pfad")
                    neu = root / f".{name}.neu"
                    with tar.extractfile(m) as src, open(neu, "wb") as dst:
                        for chunk in iter(lambda: src.read(CHUNK), b""):
                            dst.write(chunk)
                    if os.name == "posix":
                        os.chmod(neu, 0o755 if m.mode & 0o111 else 0o644)
                    os.replace(neu, target)
        except (tarfile.TarError, OSError) as exc:
            raise KiError("KI_LAUFZEIT", f"Laufzeit konnte nicht entpackt werden ({exc.__class__.__name__})") from None
        exe = root / SERVER_EXE
        if not exe.is_file():
            raise KiError("KI_LAUFZEIT", f"{SERVER_EXE} fehlt im Archiv")
        return exe
    try:
        with zipfile.ZipFile(zip_pfad) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if not name or name.startswith("."):
                    continue
                target = (root / name)
                if target.parent != root:
                    raise KiError("KI_LAUFZEIT", "Archiv enthält einen unerlaubten Pfad")
                with z.open(info) as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(CHUNK)
                        if not chunk:
                            break
                        dst.write(chunk)
    except (zipfile.BadZipFile, OSError) as exc:
        raise KiError("KI_LAUFZEIT", f"Laufzeit konnte nicht entpackt werden ({exc.__class__.__name__})") from None
    exe = root / SERVER_EXE
    if not exe.is_file():
        raise KiError("KI_LAUFZEIT", f"{SERVER_EXE} fehlt im Archiv")
    return exe


@dataclass(frozen=True)
class Geraet:
    kennung: str
    name: str
    gesamt_mib: int
    frei_mib: int

    @property
    def eigenstaendig(self) -> bool:
        n = self.name.lower()
        return not any(k in n for k in ("intel(r) uhd", "intel(r) iris", "radeon(tm) graphics", "radeon graphics", "llvmpipe", "microsoft basic", "swiftshader"))


_DEVICE_RE = re.compile(r"^\s*(\S+):\s+(.+?)\s+\((\d+)\s+MiB,\s+(\d+)\s+MiB free\)\s*$")


def geraete_parsen(text: str) -> tuple[Geraet, ...]:
    out = []
    for line in text.splitlines():
        m = _DEVICE_RE.match(line)
        if m:
            out.append(Geraet(kennung=m.group(1), name=m.group(2), gesamt_mib=int(m.group(3)), frei_mib=int(m.group(4))))
    return tuple(out)


def kind_umgebung(exe: Path, extra: dict | None = None) -> dict:
    env = {**os.environ, **(extra or {})}
    if sys.platform != "win32":
        name = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
        env[name] = os.pathsep.join(p for p in (str(Path(exe).parent), env.get(name, "")) if p)
    return env


def geraete_ermitteln(server_exe: Path, *, runner=subprocess.run) -> tuple[Geraet, ...]:
    _windows_sperre_pruefen()
    _ohne_windows_fenster()
    try:
        res = runner([str(server_exe), "--list-devices"], capture_output=True, text=True, timeout=60,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=kind_umgebung(server_exe))
    except (OSError, subprocess.SubprocessError) as exc:
        if isinstance(exc, OSError):
            _windows_sperre_merken(exc)
        raise KiError("KI_GERAETE", f"Grafikkarten konnten nicht abgefragt werden ({exc.__class__.__name__})") from None
    _sperre_am_code(getattr(res, "returncode", None))
    return geraete_parsen((res.stdout or "") + "\n" + (res.stderr or ""))


PROZESSOR_OHNE_KARTE, PROZESSOR_KARTE_VOLL, PROZESSOR_KARTE_VERSAGT = "ohne_karte", "karte_voll", "karte_versagt"
PROZESSOR_NAME_DE = {PROZESSOR_OHNE_KARTE: "Prozessor (keine passende Grafikkarte)",
                     PROZESSOR_KARTE_VOLL: "Prozessor (kein freier Grafikspeicher)",
                     PROZESSOR_KARTE_VERSAGT: "Prozessor (die Grafikkarte hat versagt)"}


@dataclass(frozen=True)
class Wahl:
    geraet: Geraet | None
    modell: Modell
    grund: str
    prozessor: str = PROZESSOR_OHNE_KARTE

    def __post_init__(self) -> None:
        if self.prozessor not in PROZESSOR_NAME_DE:
            raise ValueError(f"unbekannter Grund für den Prozessor: {self.prozessor}")

    def geraet_name_de(self) -> str:
        return self.geraet.name if self.geraet else PROZESSOR_NAME_DE[self.prozessor]


def _prozessor_grund(geraete: list[Geraet], braucht_mib: int) -> str:
    passt_leer = any(g.eigenstaendig and g.gesamt_mib >= braucht_mib for g in geraete)
    return PROZESSOR_KARTE_VOLL if passt_leer else PROZESSOR_OHNE_KARTE


KARTE_RESERVE_MIB = 300
_BELEGT: "weakref.WeakKeyDictionary[KiServer, tuple[str, int]]" = weakref.WeakKeyDictionary()
_BELEGT_LOCK = threading.Lock()


def belegt_mib(kennung: str) -> int:
    with _BELEGT_LOCK:
        eintraege = list(_BELEGT.items())
    return sum(mib for s, (k, mib) in eintraege if k == kennung and getattr(s, "proc", None) is not None and s.proc.poll() is None)


KARTE_ZAEHLER = sys.platform == "win32"
KARTE_ZAEHLER_GILT_S = 5.0
_ZAEHLER_RE = re.compile(r"GPU (Adapter|Process) Memory\((?:pid_(\d+)_)?(luid_0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)_phys_\d+\)")
_zaehler_stand: tuple[float, "tuple[dict[str, int], dict[int, tuple[str, int]]] | None"] = (-1e9, None)
_ZAEHLER_LOCK = threading.Lock()


def zaehler_parsen(text: str) -> "tuple[dict[str, int], dict[int, tuple[str, int]]] | None":
    zeilen = [z for z in text.splitlines() if z.startswith('"')]
    if len(zeilen) < 2:
        return None
    kopf = [s.strip('"') for s in zeilen[0].split('","')]
    werte = [s.strip('"') for s in zeilen[1].split('","')]
    karten: dict[str, int] = {}
    prozesse: dict[int, tuple[str, int]] = {}
    for name, wert in zip(kopf[1:], werte[1:]):
        m = _ZAEHLER_RE.search(name)
        if not m:
            continue
        try:
            mib = int(float(wert) / (1024 * 1024))
        except ValueError:
            continue
        luid = m.group(3).lower()
        if m.group(1) == "Adapter":
            karten[luid] = karten.get(luid, 0) + mib
        else:
            pid = int(m.group(2))
            alt = prozesse.get(pid, (luid, 0))
            prozesse[pid] = (luid, alt[1] + mib) if alt[0] == luid else (alt if alt[1] >= mib else (luid, mib))
    return (karten, prozesse) if karten else None


def _zaehler_lesen():
    global _zaehler_stand
    if not KARTE_ZAEHLER:
        return None
    with _ZAEHLER_LOCK:
        jetzt = time.monotonic()
        if jetzt - _zaehler_stand[0] < KARTE_ZAEHLER_GILT_S:
            return _zaehler_stand[1]
        try:
            res = subprocess.run(["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage", r"\GPU Process Memory(*)\Dedicated Usage", "-sc", "1"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            daten = zaehler_parsen(res.stdout or "")
        except (OSError, subprocess.SubprocessError, ValueError):
            daten = None
        _zaehler_stand = (jetzt, daten)
        return daten


def _eigene_pids(kennung: str) -> set[int]:
    with _BELEGT_LOCK:
        eintraege = list(_BELEGT.items())
    return {getattr(s.proc, "pid", None) for s, (k, _mib) in eintraege
            if k == kennung and getattr(s, "proc", None) is not None and s.proc.poll() is None} - {None}


def fremd_mib(g: Geraet) -> int:
    if not g.eigenstaendig:
        return 0
    daten = _zaehler_lesen()
    if not daten:
        return 0
    karten, prozesse = daten
    eigene = _eigene_pids(g.kennung)
    luids = {prozesse[p][0] for p in eigene if p in prozesse}
    if len(luids) == 1:
        luid = luids.pop()
    elif not luids:
        luid = max(karten, key=lambda x: karten[x])
    else:
        return 0
    eigen_echt = sum(mib for p, (l, mib) in prozesse.items() if p in eigene and l == luid)
    return max(0, karten.get(luid, 0) - eigen_echt)


def frei_mib(g: Geraet) -> int:
    if g.gesamt_mib <= 0:
        return g.frei_mib
    return max(0, min(g.frei_mib, g.gesamt_mib - belegt_mib(g.kennung) - fremd_mib(g) - KARTE_RESERVE_MIB))


def waehlen(geraete: Iterable[Geraet], memory_gib: float) -> Wahl:
    karten = sorted(geraete, key=lambda g: (g.eigenstaendig, g.frei_mib), reverse=True)
    for g in karten:
        if not g.eigenstaendig and any(k.eigenstaendig for k in karten):
            continue
        if not g.eigenstaendig and memory_gib < 8.0:
            continue
        for kennung in MODELL_REIHENFOLGE:
            m = MODELLE[kennung]
            if m.braucht_mib <= frei_mib(g):
                fremd = fremd_mib(g)
                return Wahl(g, m, f"{m.name} passt in die {frei_mib(g)} MiB freien Grafikspeicher von {g.name}"
                                  + (f" (andere Programme belegen gerade {fremd} MiB darauf)" if fremd >= 256 else ""))
    if _prozessor_grund(karten, min(m.braucht_mib for m in MODELLE.values())) == PROZESSOR_KARTE_VOLL:
        if memory_gib >= 15.5:
            return Wahl(None, MODELLE["8B"], "kein freier Grafikspeicher, aber genug Arbeitsspeicher für das 8B-Modell", PROZESSOR_KARTE_VOLL)
        return Wahl(None, MODELLE["3B"], "kein freier Grafikspeicher, deshalb das kleine 3B-Modell", PROZESSOR_KARTE_VOLL)
    if memory_gib >= 15.5:
        return Wahl(None, MODELLE["8B"], "keine passende Grafikkarte, aber genug Arbeitsspeicher für das 8B-Modell")
    return Wahl(None, MODELLE["3B"], "keine passende Grafikkarte, deshalb das kleine 3B-Modell")


def waehlen_rechen(geraete: Iterable[Geraet]) -> Wahl:
    karten = sorted(geraete, key=lambda g: (g.eigenstaendig, g.frei_mib), reverse=True)
    for g in karten:
        if g.eigenstaendig and EMBEDDING.braucht_mib + RESERVE_MIB <= frei_mib(g):
            return Wahl(g, EMBEDDING, f"{EMBEDDING.name} passt in die {frei_mib(g)} MiB freien Grafikspeicher von {g.name}")
    if _prozessor_grund(karten, EMBEDDING.braucht_mib + RESERVE_MIB) == PROZESSOR_KARTE_VOLL:
        return Wahl(None, EMBEDDING, "kein freier Grafikspeicher, deshalb rechnet der Prozessor", PROZESSOR_KARTE_VOLL)
    return Wahl(None, EMBEDDING, "keine passende Grafikkarte, deshalb rechnet der Prozessor")


RESERVE_MIB = 512
BEWERTUNG_PUFFER = 1024


def waehlen_bewertung(geraete: Iterable[Geraet]) -> Wahl | None:
    karten = sorted(geraete, key=lambda g: (g.eigenstaendig, g.frei_mib), reverse=True)
    for g in karten:
        if g.eigenstaendig and BEWERTUNG.braucht_mib + RESERVE_MIB <= frei_mib(g):
            return Wahl(g, BEWERTUNG, f"{BEWERTUNG.name} passt in die {frei_mib(g)} MiB freien Grafikspeicher von {g.name}")
    return None


def waehlen_hoeren(geraete: Iterable[Geraet]) -> Wahl:
    karten = sorted(geraete, key=lambda g: (g.eigenstaendig, g.frei_mib), reverse=True)
    for g in karten:
        if g.eigenstaendig and HOEREN.braucht_mib + RESERVE_MIB <= frei_mib(g):
            return Wahl(g, HOEREN, f"{HOEREN.name} passt in die {frei_mib(g)} MiB freien Grafikspeicher von {g.name}")
    if _prozessor_grund(karten, HOEREN.braucht_mib + RESERVE_MIB) == PROZESSOR_KARTE_VOLL:
        return Wahl(None, HOEREN, "kein freier Grafikspeicher, deshalb hört der Prozessor zu", PROZESSOR_KARTE_VOLL)
    return Wahl(None, HOEREN, "keine passende Grafikkarte, deshalb hört der Prozessor zu")


HOEREN_MARKE = "<asr_text>"


def hoer_text(roh: str) -> str:
    t = str(roh or "")
    if HOEREN_MARKE in t:
        t = t.split(HOEREN_MARKE, 1)[1]
    return " ".join(t.replace("</asr_text>", " ").split()).strip()


@dataclass(frozen=True)
class Antwort:
    text: str
    prompt_tokens: int
    completion_tokens: int
    dauer_s: float
    abgebrochen: bool = False
    gekuerzt: bool = False


PLATZ_REST = 96
_KONTEXT_ZU_KLEIN = re.compile(r"request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)")
_SATZENDE = re.compile(r"[.!?…:][\")»“]?(?=\s|$)")


def bis_zum_letzten_satz(text: str) -> str:
    t = (text or "").rstrip()
    ende = [m.end() for m in _SATZENDE.finditer(t)]
    if ende and ende[-1] >= len(t) * 0.4:
        return t[:ende[-1]].rstrip()
    return t + " …" if t else t


VEKTOR_RESERVE = 16


def _bytes_kuerzen(text: str, grenze: int) -> str:
    roh = text.encode("utf-8")
    if len(roh) <= grenze:
        return text
    return roh[:max(0, grenze)].decode("utf-8", errors="ignore")


def _kuerzen(zusatz: str, zeichen: int) -> str:
    if zeichen >= len(zusatz):
        return zusatz
    if zeichen <= 0:
        return ""
    t = zusatz[:zeichen]
    i = t.rfind(chr(10))
    return (t[:i] if i > zeichen * 0.6 else t).rstrip() + chr(10) + "[weitere Auszüge aus Platzgründen weggelassen]"


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


LADEN_WARTEN_S = 120.0
STILLSTAND_S = 90.0


class _Wache:

    def __init__(self, antwort, abbruch: threading.Event, lebt: Callable[[], bool], stillstand_s: float | None = None) -> None:
        self.grund = ""
        self.zuletzt = 0.0
        self._antwort, self._abbruch, self._lebt = antwort, abbruch, lebt
        self._still = STILLSTAND_S if stillstand_s is None else stillstand_s
        self._ende = threading.Event()
        self._t = threading.Thread(target=self._laufen, name="ki-wache", daemon=True)
        self._t.start()

    def wort(self) -> None:
        self.zuletzt = time.monotonic()

    def _laufen(self) -> None:
        while not self._ende.wait(0.5):
            if self._abbruch.is_set():
                self.grund = "abbruch"
            elif not self._lebt():
                self.grund = "beendet"
            elif self.zuletzt and time.monotonic() - self.zuletzt > self._still:
                self.grund = "stillstand"
            else:
                continue
            try:
                sock = self._antwort.fp.raw._sock
            except AttributeError:
                return
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, ValueError):
                pass
            try:
                socket.close(sock.detach())
            except (AttributeError, OSError, ValueError):
                pass
            return

    def aus(self) -> None:
        self._ende.set()
MAX_SERVER_LOG = 1_000_000


def _log_kuerzen(pfad: Path) -> None:
    try:
        if pfad.stat().st_size > MAX_SERVER_LOG:
            pfad.write_bytes(pfad.read_bytes()[-MAX_SERVER_LOG // 4:])
    except OSError:
        pass


_JOB = None
_JOB_LOCK = threading.Lock()


def an_programm_binden(proc) -> bool:
    if os.name != "nt" or not hasattr(proc, "_handle"):
        return False
    global _JOB
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        class Grund(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class Ein(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                       "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Erweitert(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Grund), ("IoInfo", Ein), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        with _JOB_LOCK:
            if _JOB is None:
                job = k32.CreateJobObjectW(None, None)
                if not job:
                    return False
                info = Erweitert()
                info.BasicLimitInformation.LimitFlags = 0x2000
                if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                    k32.CloseHandle(job)
                    return False
                _JOB = job
            return bool(k32.AssignProcessToJobObject(_JOB, wintypes.HANDLE(int(proc._handle))))
    except (OSError, AttributeError, ValueError, TypeError):
        return False


CACHE_REUSE = 256
SLOT_ANTWORT = 0
SLOT_HINTERGRUND = 1
_OHNE_CACHE_REUSE: set[str] = set()

PLAETZE_MAX = 3
PLAETZE_AN = False
_OHNE_PLAETZE: set[str] = set()

_OHNE_CACHE_RAM: set[str] = set()


def plaetze_fuer(wahl) -> int:
    m, g = getattr(wahl, "modell", None), getattr(wahl, "geraet", None)
    if not PLAETZE_AN or g is None or m is None or int(getattr(m, "kv_mib", 0) or 0) <= 0:
        return 0
    andere = EMBEDDING.braucht_mib + BEWERTUNG.braucht_mib + 2 * RESERVE_MIB
    weitere = (frei_mib(g) - int(m.braucht_mib) - andere) // int(m.kv_mib)
    n = min(PLAETZE_MAX, 1 + max(0, weitere))
    return n if n >= 2 else 0


class KiServer:

    def __init__(self, ordner: KiOrdner, *, popen=subprocess.Popen, urlopen=urllib.request.urlopen, schlafen=time.sleep, port_finder=_freier_port) -> None:
        self.ordner = ordner
        self._popen = popen
        self._urlopen = urlopen
        self._schlafen = schlafen
        self._port_finder = port_finder
        self.proc = None
        self.port: int | None = None
        self.api_key: str | None = None
        self.wahl: Wahl | None = None
        self.gestartet_um: float | None = None
        self.zuletzt_benutzt = 0.0
        self.gebunden = False
        self._atexit_registriert = False
        self.abbruch = threading.Event()


    def laeuft(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, wahl: Wahl, *, timeout_s: float = 180.0, embedding: bool = False, threads: int | None = None, hoeren: bool = False,
              bilder: bool | None = None, bewerten: bool = False, modell_pfad: Path | None = None) -> None:
        if self.laeuft():
            return
        _windows_sperre_pruefen()
        _ohne_windows_fenster()
        exe = self.ordner.server_exe
        modell = modell_pfad if modell_pfad is not None and not (embedding or bewerten or hoeren) else self.ordner.modell_pfad(wahl.modell)
        if not exe.is_file():
            raise KiError("KI_LAUFZEIT", "die KI-Laufzeit fehlt noch")
        if not modell.is_file():
            raise KiError("KI_MODELL", f"die Modelldatei {wahl.modell.name} fehlt noch")
        port = self._port_finder()
        key = secrets.token_urlsafe(24)
        args = [str(exe), "-m", str(modell), "--host", "127.0.0.1", "--port", str(port),
                "--no-webui", "-c", str(wahl.modell.kontext), "--no-warmup"]
        self.bilder = False
        if hoeren:
            if not self.ordner.bilder_da(wahl.modell):
                raise KiError("KI_MODELL", f"der Hör-Zusatz zu {wahl.modell.name} fehlt noch")
            args += ["--mmproj", str(self.ordner.bilder_pfad(wahl.modell))]
        elif not embedding and not bewerten and bilder is not False and wahl.geraet is not None and wahl.geraet.eigenstaendig and self.ordner.bilder_da(wahl.modell):
            args += ["--mmproj", str(self.ordner.bilder_pfad(wahl.modell))]
            self.bilder = True
        else:
            args += ["--no-mmproj"]
        reuse = not (embedding or bewerten or hoeren) and str(exe) not in _OHNE_CACHE_REUSE
        if reuse:
            args += ["--cache-reuse", str(CACHE_REUSE)]
        n_plaetze = plaetze_fuer(wahl) if not (embedding or bewerten or hoeren) and str(exe) not in _OHNE_PLAETZE else 0
        self._eigene_plaetze = n_plaetze
        if n_plaetze:
            args[args.index("-c") + 1] = str(int(wahl.modell.kontext) * n_plaetze)
            args += ["-np", str(n_plaetze), "--no-kv-unified"]
        if embedding:
            args += ["--embedding", "--pooling", "last", "-ub", str(wahl.modell.kontext), "-b", str(wahl.modell.kontext), "-np", "1"]
        elif bewerten:
            args += ["--reranking", "-ub", str(BEWERTUNG_PUFFER), "-b", str(BEWERTUNG_PUFFER)]
        cache_ram_aus = (embedding or bewerten) and str(exe) not in _OHNE_CACHE_RAM
        if cache_ram_aus:
            args += ["--cache-ram", "0"]
        if threads:
            args += ["-t", str(max(1, int(threads)))]
        if wahl.geraet is not None:
            args += ["--device", wahl.geraet.kennung, "-ngl", "99"]
        else:
            args += ["-ngl", "0"]
        self.ordner.anlegen()
        _log_kuerzen(self.ordner.log_path)
        log = open(self.ordner.log_path, "ab")
        try:
            self.proc = self._popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=kind_umgebung(exe, {"LLAMA_API_KEY": key}),
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), cwd=str(exe.parent))
        except OSError as exc:
            log.close()
            _windows_sperre_merken(exc)
            raise KiError("KI_START", f"llama-server konnte nicht gestartet werden ({exc.__class__.__name__})") from None
        finally:
            try:
                log.close()
            except OSError:
                pass
        self.gebunden = an_programm_binden(self.proc)
        self.port, self.api_key, self.wahl = port, key, wahl
        self.gestartet_um = time.time()
        self.zuletzt_benutzt = time.monotonic()
        with _BELEGT_LOCK:
            if wahl.geraet is not None:
                _BELEGT[self] = (wahl.geraet.kennung, int(wahl.modell.braucht_mib) + max(0, n_plaetze - 1) * int(getattr(wahl.modell, "kv_mib", 0) or 0))
            else:
                _BELEGT.pop(self, None)
        if not self._atexit_registriert:
            atexit.register(self.stop)
            self._atexit_registriert = True
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            proc = self.proc
            if proc is None:
                raise KiError("KI_START", "der Start wurde abgebrochen")
            if proc.poll() is not None:
                code = proc.returncode
                self.proc = None
                _sperre_am_code(code)
                if n_plaetze and time.time() - self.gestartet_um < 30:
                    _OHNE_PLAETZE.add(str(exe))
                    with _BELEGT_LOCK:
                        _BELEGT.pop(self, None)
                    return self.start(wahl, timeout_s=timeout_s, embedding=embedding, threads=threads, hoeren=hoeren, bilder=bilder, bewerten=bewerten)
                if reuse and time.time() - self.gestartet_um < 30:
                    _OHNE_CACHE_REUSE.add(str(exe))
                    with _BELEGT_LOCK:
                        _BELEGT.pop(self, None)
                    return self.start(wahl, timeout_s=timeout_s, embedding=embedding, threads=threads, hoeren=hoeren, bilder=bilder, bewerten=bewerten)
                if cache_ram_aus and time.time() - self.gestartet_um < 30:
                    _OHNE_CACHE_RAM.add(str(exe))
                    with _BELEGT_LOCK:
                        _BELEGT.pop(self, None)
                    return self.start(wahl, timeout_s=timeout_s, embedding=embedding, threads=threads, hoeren=hoeren, bilder=bilder, bewerten=bewerten)
                raise KiError("KI_START", f"llama-server hat sich beendet (Code {code}); Details in ki/server.log")
            if self._gesund():
                eigene = int(getattr(self, "_eigene_plaetze", 0) or 0)
                self.plaetze = min(eigene, self._plaetze_lesen() or eigene) if eigene and not (embedding or bewerten) else 0
                return
            self._schlafen(0.5)
        self.stop()
        raise KiError("KI_START", "llama-server wurde nicht rechtzeitig bereit")

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        with _BELEGT_LOCK:
            _BELEGT.pop(self, None)
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        except OSError:
            pass
        self.port = self.api_key = None

    def privat_mb(self) -> int | None:
        proc = self.proc
        if proc is None or proc.poll() is not None or os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class _Zaehler(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                                                   "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                                                   "PrivateUsage")]
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = wintypes.HANDLE
            h = k32.OpenProcess(0x1000, False, int(proc.pid))
            if not h:
                return None
            try:
                z = _Zaehler()
                z.cb = ctypes.sizeof(_Zaehler)
                if not ctypes.WinDLL("psapi").GetProcessMemoryInfo(h, ctypes.byref(z), z.cb):
                    return None
                return int(z.PrivateUsage // (1024 * 1024))
            finally:
                k32.CloseHandle(h)
        except Exception:
            return None


    def _url(self, pfad: str) -> str:
        return f"http://127.0.0.1:{self.port}{pfad}"

    def _plaetze_lesen(self) -> int:
        try:
            req = urllib.request.Request(self._url("/props"), headers={"Authorization": f"Bearer {self.api_key}"})
            with self._urlopen(req, timeout=5) as r:
                return max(0, int(json.loads(r.read(200_000).decode("utf-8")).get("total_slots") or 0))
        except Exception:
            return 0

    def _gesund(self) -> bool:
        try:
            with self._urlopen(urllib.request.Request(self._url("/health")), timeout=2) as r:
                return b'"ok"' in r.read(200)
        except OSError:
            return False
        except Exception:
            return False

    def _stuecke(self, text: str) -> int:
        try:
            req = urllib.request.Request(self._url("/tokenize"), data=json.dumps({"content": text}).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
            with self._urlopen(req, timeout=15) as r:
                return len(json.loads(r.read().decode("utf-8")).get("tokens") or [])
        except Exception:
            return len(text or "") // 3 + 1

    def _einpassen(self, basis: str, zusatz: str, nachrichten: list[dict], max_tokens: int) -> tuple[str, list[dict], bool]:
        kontext = int(getattr(getattr(self.wahl, "modell", None), "kontext", 0) or 0)
        if kontext <= 0:
            return zusatz, nachrichten, False
        grenze = kontext - min(max_tokens, kontext // 4) - PLATZ_REST

        def text_von(n: dict) -> str:
            c = n.get("content")
            if isinstance(c, str):
                return c
            teile = [t for t in (c or []) if isinstance(t, dict)]
            return " ".join(str(t.get("text", "")) for t in teile) + " " + "x" * 2400 * sum(1 for t in teile if t.get("type") != "text")

        def zaehlen(z: str, ns: list[dict]) -> int:
            return self._stuecke(basis + chr(10) + chr(10) + z + chr(10) + chr(10).join(text_von(n) for n in ns)) + 8 * len(ns)

        grob = len(basis) + len(zusatz) + sum(len(text_von(x)) for x in nachrichten)
        if grob / 2.2 + 8 * len(nachrichten) <= grenze:
            return zusatz, nachrichten, False
        n = zaehlen(zusatz, nachrichten)
        if n <= grenze:
            return zusatz, nachrichten, False
        while len(nachrichten) > 4 and n > grenze:
            nachrichten = nachrichten[2:]
            n = zaehlen(zusatz, nachrichten)
        teile = zusatz.split("\n\n")
        schwanz: list[str] = []
        while teile and (teile[-1].startswith("Es ist ") or teile[-1].startswith("Gefragt ist genau")):
            schwanz.insert(0, teile.pop())
        kern, anhang = "\n\n".join(teile), ("\n\n" + "\n\n".join(schwanz) if schwanz else "")
        for _ in range(4):
            if n <= grenze or not kern:
                break
            z_n = max(1, self._stuecke(kern))
            rest = max(0, grenze - (n - z_n))
            kern = _kuerzen(kern, int(len(kern) * rest / z_n * 0.95))
            zusatz = kern + anhang
            n = zaehlen(zusatz, nachrichten)
        while len(nachrichten) > 1 and n > grenze:
            nachrichten = nachrichten[1:]
            n = zaehlen(zusatz, nachrichten)
        if n > grenze and nachrichten and isinstance(nachrichten[-1].get("content"), str):
            c = nachrichten[-1]["content"]
            halb = max(0, (len(c) - int((n - grenze) * 4.2) - 200) // 2)
            nachrichten = nachrichten[:-1] + [{**nachrichten[-1], "content": c[:halb] + chr(10) + "[… gekürzt …]" + chr(10) + c[len(c) - halb:]}]
        return zusatz, nachrichten, True

    def frage(self, nachrichten: list[dict], *, max_tokens: int = 700, temperature: float = TEMPERATUR, on_token: Callable[[str], None] | None = None,
              zusatz: str = "", kurz: bool = False, abbruch: threading.Event | None = None, system: str | None = None,
              platz: int = SLOT_ANTWORT, art: str | None = None) -> Antwort:
        fest = selbstauskunft.feste_antwort(nachrichten) if system is None else None
        if fest:
            if on_token is not None:
                on_token(fest)
            return Antwort(fest, 0, 0, 0.0)
        if not self.laeuft() or self.port is None:
            raise KiError("KI_AUS", "die KI ist gerade nicht eingeschaltet")
        self.zuletzt_benutzt = time.monotonic()
        basis = system if system is not None else (SYSTEMTEXT_KURZ if kurz else SYSTEMTEXT)
        original = getattr(_ORIGINAL_FADEN, "text", "") if system is None else ""
        if original:
            basis = basis + chr(10) + chr(10) + ORIGINAL_HINWEIS.format(original)
        zusatz, nachrichten, gekuerzt = self._einpassen(basis, zusatz, list(nachrichten), max_tokens)
        if abbruch is None:
            abbruch = getattr(_ABBRUCH_FADEN, "ev", None)
        stream = on_token is not None or abbruch is not None
        body = {"messages": [{"role": "system", "content": basis + (chr(10) + chr(10) + zusatz if zusatz else "")}] + nachrichten,
                "max_tokens": max_tokens, "temperature": temperature, "stream": stream, "cache_prompt": True}
        plaetze = int(getattr(self, "plaetze", 0) or 0)
        if plaetze > 0:
            if platz == SLOT_HINTERGRUND or (system is not None and platz == SLOT_ANTWORT and plaetze >= 2):
                body["id_slot"] = plaetze - 1
            else:
                body["id_slot"] = min(max(0, int(platz)), plaetze - 1)
        if stream:
            body["stream_options"] = {"include_usage": True}
        req = urllib.request.Request(self._url("/v1/chat/completions"), data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        t0 = time.time()
        nochmal_kleiner = True
        if abbruch is None:
            abbruch = self.abbruch
            abbruch.clear()
        while True:
            try:
                with self._urlopen(req, timeout=600) as r:
                    if not stream:
                        data = json.loads(r.read().decode("utf-8"))
                        text = data["choices"][0]["message"]["content"]
                        if data["choices"][0].get("finish_reason") == "length":
                            text = bis_zum_letzten_satz(text)
                        u = data.get("usage") or {}
                        _messen(art or ("eigen" if system is not None else "antwort"), time.time() - t0, data.get("timings"), max=max_tokens)
                        return Antwort(text.strip(), int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), round(time.time() - t0, 1), gekuerzt=gekuerzt)
                    parts: list[str] = []
                    usage: dict = {}
                    timings: dict | None = None
                    abgebrochen = False
                    zu_lang = False
                    wache = _Wache(r, abbruch, self.laeuft)
                    try:
                        for raw in r:
                            wache.wort()
                            if abbruch.is_set():
                                abgebrochen = True
                                break
                            line = raw.decode("utf-8", "replace").strip()
                            if not line.startswith("data:"):
                                continue
                            payload = line[5:].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                ev = json.loads(payload)
                            except ValueError:
                                continue
                            if ev.get("usage"):
                                usage = ev["usage"]
                            if isinstance(ev.get("timings"), dict):
                                timings = ev["timings"]
                            for ch in ev.get("choices") or []:
                                if ch.get("finish_reason") == "length":
                                    zu_lang = True
                                delta = (ch.get("delta") or {}).get("content")
                                if delta:
                                    parts.append(delta)
                                    if on_token is not None:
                                        on_token(delta)
                    except (OSError, http.client.HTTPException, ValueError):
                        if not wache.grund:
                            raise
                    finally:
                        wache.aus()
                    if wache.grund == "abbruch":
                        abgebrochen = True
                    elif wache.grund == "beendet":
                        raise KiError("KI_ANTWORT", "der KI-Server hat sich mitten in der Antwort beendet")
                    elif wache.grund == "stillstand":
                        self.stop()
                        raise KiError("KI_ANTWORT", f"die KI hat {int(STILLSTAND_S)} Sekunden lang nichts mehr geschrieben")
                    text = "".join(parts)
                    if zu_lang and not abgebrochen:
                        text = bis_zum_letzten_satz(text)
                    _messen(art or ("eigen" if system is not None else "antwort"), time.time() - t0, timings, max=max_tokens, **({"abgebrochen": 1} if abgebrochen else {}))
                    return Antwort(text.strip(), int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", len(parts))), round(time.time() - t0, 1), abgebrochen, gekuerzt)
            except urllib.error.HTTPError as exc:
                try:
                    grund = exc.read(400).decode("utf-8", "replace")
                except Exception:
                    grund = ""
                try:
                    grund = str((json.loads(grund).get("error") or {}).get("message") or grund)
                except (ValueError, AttributeError):
                    pass
                grund = " ".join(grund.split())[:160]
                if exc.code == 503 and time.time() - t0 < LADEN_WARTEN_S and not abbruch.is_set():
                    self._schlafen(1.0)
                    continue
                m = _KONTEXT_ZU_KLEIN.search(grund)
                if m and nochmal_kleiner and zusatz:
                    nochmal_kleiner, gekuerzt = False, True
                    zuviel = int(m.group(1)) - int(m.group(2)) + min(max_tokens, int(m.group(2)) // 4) + PLATZ_REST
                    zusatz = _kuerzen(zusatz, max(0, len(zusatz) - int(zuviel * 4.2 * 1.2)))
                    body["messages"][0]["content"] = basis + (chr(10) + chr(10) + zusatz if zusatz else "")
                    req = urllib.request.Request(self._url("/v1/chat/completions"), data=json.dumps(body).encode("utf-8"),
                                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
                    continue
                raise KiError("KI_ANTWORT", f"keine Antwort vom KI-Server (HTTP {exc.code}" + (f": {grund}" if grund else "") + ")") from None
            except OSError as exc:
                raise KiError("KI_ANTWORT", f"keine Antwort vom KI-Server ({exc.__class__.__name__})") from None
            except (KeyError, ValueError, TypeError):
                raise KiError("KI_ANTWORT", "die Antwort des KI-Servers war unlesbar") from None

    def hoeren(self, wav: bytes, *, timeout_s: float = 180.0) -> str:
        if not self.laeuft() or self.port is None:
            raise KiError("KI_AUS", "das Hör-Modell ist gerade nicht eingeschaltet")
        daten = base64.b64encode(wav).decode("ascii")
        body = {"messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": daten, "format": "wav"}}]}],
                "temperature": 0.0, "max_tokens": 400}
        req = urllib.request.Request(self._url("/v1/chat/completions"), data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        t0 = time.time()
        while True:
            try:
                with self._urlopen(req, timeout=timeout_s) as r:
                    data = json.loads(r.read().decode("utf-8"))
                return hoer_text(data["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as exc:
                if exc.code == 503 and time.time() - t0 < LADEN_WARTEN_S:
                    self._schlafen(1.0)
                    continue
                raise KiError("KI_ANTWORT", f"keine Antwort vom Hör-Modell (HTTP {exc.code})") from None
            except OSError as exc:
                raise KiError("KI_ANTWORT", f"keine Antwort vom Hör-Modell ({exc.__class__.__name__})") from None
            except (KeyError, ValueError, TypeError):
                raise KiError("KI_ANTWORT", "die Antwort des Hör-Modells war unlesbar") from None

    def vektoren(self, texte: list[str], *, timeout_s: float = 300.0) -> list[list[float]]:
        if not self.laeuft() or self.port is None:
            raise KiError("KI_AUS", "das Bedeutungs-Modell ist gerade nicht eingeschaltet")
        if not texte:
            return []
        self.zuletzt_benutzt = time.monotonic()
        grenze = (self.wahl.modell.kontext if self.wahl is not None else EMBEDDING.kontext) - VEKTOR_RESERVE
        body = {"input": [_bytes_kuerzen(str(t), grenze) for t in texte]}
        req = urllib.request.Request(self._url("/v1/embeddings"), data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        t0 = time.time()
        try:
            with self._urlopen(req, timeout=timeout_s) as r:
                data = json.loads(r.read().decode("utf-8"))
            _messen("bedeutung", time.time() - t0, n=len(texte))
            eintraege = sorted(data["data"], key=lambda e: int(e.get("index", 0)))
            out = []
            for e in eintraege:
                v = [float(x) for x in e["embedding"]]
                laenge = sum(x * x for x in v) ** 0.5
                out.append([x / laenge for x in v] if laenge > 0 else v)
        except urllib.error.HTTPError as exc:
            try:
                grund = exc.read(400).decode("utf-8", "replace")
                grund = str((json.loads(grund).get("error") or {}).get("message") or grund)
            except Exception:
                grund = ""
            grund = " ".join(grund.split())[:160]
            raise KiError("KI_ANTWORT", f"keine Antwort vom KI-Server (HTTP {exc.code}" + (f": {grund}" if grund else "") + ")") from None
        except OSError as exc:
            raise KiError("KI_ANTWORT", f"keine Antwort vom KI-Server ({exc.__class__.__name__})") from None
        except (KeyError, ValueError, TypeError):
            raise KiError("KI_ANTWORT", "die Antwort des KI-Servers war unlesbar") from None
        if len(out) != len(texte):
            raise KiError("KI_ANTWORT", "der KI-Server hat nicht für jeden Abschnitt einen Vektor geliefert")
        return out

    def bewerten(self, frage: str, texte: list[str], *, timeout_s: float = 30.0) -> list[float]:
        if not self.laeuft() or self.port is None:
            raise KiError("KI_AUS", "das Bewertungs-Modell ist gerade nicht eingeschaltet")
        if not texte:
            return []
        self.zuletzt_benutzt = time.monotonic()
        body = {"query": str(frage), "documents": list(texte), "top_n": len(texte)}
        req = urllib.request.Request(self._url("/v1/rerank"), data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        t0 = time.time()
        try:
            with self._urlopen(req, timeout=timeout_s) as r:
                data = json.loads(r.read().decode("utf-8"))
            _messen("bewertung", time.time() - t0, n=len(texte), zeichen=sum(len(t) for t in texte))
            werte: dict[int, float] = {int(e["index"]): float(e["relevance_score"]) for e in data["results"]}
        except OSError as exc:
            raise KiError("KI_ANTWORT", f"keine Antwort vom Bewertungs-Modell ({exc.__class__.__name__})") from None
        except (KeyError, ValueError, TypeError):
            raise KiError("KI_ANTWORT", "die Antwort des Bewertungs-Modells war unlesbar") from None
        if sorted(werte) != list(range(len(texte))):
            raise KiError("KI_ANTWORT", "das Bewertungs-Modell hat nicht jeden Abschnitt bewertet")
        return [werte[i] for i in range(len(texte))]

    def log_ende(self) -> str:
        try:
            data = self.ordner.log_path.read_bytes()[-MAX_LOG_TAIL:]
            return app_core._mask(data.decode("utf-8", "replace"))
        except OSError:
            return ""


_MESSUNG = threading.local()
MESSUNG_MAX = 40


def messung_beginnen() -> None:
    _MESSUNG.liste = []


def messung_liste() -> list | None:
    return getattr(_MESSUNG, "liste", None)


def messung_teilen(liste: list | None) -> None:
    _MESSUNG.liste = liste


def messung_ende() -> list[dict]:
    liste = getattr(_MESSUNG, "liste", None) or []
    _MESSUNG.liste = None
    return liste


def _messen(art: str, sekunden: float, timings: dict | None = None, **mehr) -> None:
    liste = getattr(_MESSUNG, "liste", None)
    if liste is None or len(liste) >= MESSUNG_MAX:
        return
    e: dict = {"art": art, "s": round(float(sekunden), 2), **mehr}
    if isinstance(timings, dict):
        for schluessel, name in (("prompt_n", "ein"), ("cache_n", "cache"), ("prompt_ms", "ein_ms"), ("predicted_n", "aus"), ("predicted_ms", "aus_ms")):
            try:
                if timings.get(schluessel) is not None:
                    e[name] = round(float(timings[schluessel]), 0 if schluessel.endswith("_n") else 1)
            except (TypeError, ValueError):
                pass
    liste.append(e)


def ist_windows() -> bool:
    return platform.system() == "Windows"


__all__ = ["LAUFZEIT", "MODELLE", "MODELL_REIHENFOLGE", "EMBEDDING", "EMBEDDING_DIMENSION", "BEWERTUNG", "waehlen_bewertung", "SYSTEMTEXT", "SYSTEMTEXT_KURZ", "KiError", "KiOrdner", "Paket", "Modell", "Geraet", "Wahl",
           "herunterladen", "pruefsumme_ok", "laufzeit_entpacken", "geraete_parsen", "geraete_ermitteln", "waehlen", "waehlen_rechen", "waehlen_hoeren",
           "hoer_text", "HOEREN", "KiServer", "Antwort"]
