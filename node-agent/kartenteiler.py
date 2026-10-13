# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import sicher_schreiben

GUELTIG_S = 60.0
ERNEUERN_S = 15.0
NACHSEHEN_S = 0.5
PRAEFIX = "antwortet-"
DA_PRAEFIX = "da-"


ORDNER: Path | None = None


def sitzung() -> tuple[int, bool]:
    if sys.platform != "win32":
        return 0, True
    try:
        k = ctypes.windll.kernel32
        vorn = int(k.WTSGetActiveConsoleSessionId())
        s = ctypes.c_ulong(0)
        if not k.ProcessIdToSessionId(os.getpid(), ctypes.byref(s)):
            return 0, True
        return int(s.value), int(s.value) == vorn
    except Exception:
        return 0, True


def anderer_benutzer_vorn() -> bool:
    if sys.platform != "win32":
        return False
    try:
        s, vorn = sitzung()
        if vorn:
            return False
        k = ctypes.windll.kernel32
        wts = ctypes.windll.wtsapi32
        konsole = int(k.WTSGetActiveConsoleSessionId())
        if konsole == 0xFFFFFFFF:
            return False
        puffer, laenge = ctypes.c_wchar_p(), ctypes.c_ulong(0)
        if not wts.WTSQuerySessionInformationW(None, konsole, 5, ctypes.byref(puffer), ctypes.byref(laenge)):
            return False
        try:
            return bool((puffer.value or "").strip())
        finally:
            wts.WTSFreeMemory(puffer)
    except Exception:
        return False


def benutzer_kurz() -> str:
    name = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    return hashlib.sha256(("kiplatz-benutzer/" + name.lower()).encode("utf-8")).hexdigest()[:12]


def standard_ordner() -> Path:
    if ORDNER is not None:
        return ORDNER
    return Path(os.environ.get("PUBLIC") or r"C:\Users\Public") / "KIplatz" / "karte"


class Kartenteiler:

    def __init__(self, ordner: Path | None = None, *, jetzt=time.time, kennung: str | None = None, sitzung_fn=None, benutzer: str | None = None, fremd_vorn_fn=None) -> None:
        self._sitzung = sitzung_fn or sitzung
        self._fremd_vorn = fremd_vorn_fn or (anderer_benutzer_vorn if sitzung_fn is None else (lambda: False))
        self._benutzer = benutzer if benutzer is not None else benutzer_kurz()
        self.ordner = Path(ordner) if ordner is not None else standard_ordner()
        self._jetzt = jetzt
        self.kennung = kennung or f"{os.getpid()}-{os.urandom(4).hex()}"
        self._datei = self.ordner / f"{PRAEFIX}{self.kennung}.json"
        self._zahl = 0
        self._geschrieben = 0.0
        self._lock = threading.Lock()

    def _schreiben(self) -> None:
        try:
            self.ordner.mkdir(parents=True, exist_ok=True)
            sicher_schreiben.json_datei(self._datei, {"bis": self._jetzt() + GUELTIG_S}, indent=None)
            self._geschrieben = self._jetzt()
        except OSError:
            pass

    def beginnen(self) -> None:
        with self._lock:
            self._zahl += 1
            if self._zahl == 1:
                self._schreiben()

    def ende(self) -> None:
        with self._lock:
            self._zahl = max(0, self._zahl - 1)
            if self._zahl == 0:
                try:
                    self._datei.unlink(missing_ok=True)
                except OSError:
                    pass

    def erneuern(self) -> None:
        with self._lock:
            if self._zahl > 0 and self._jetzt() - self._geschrieben >= ERNEUERN_S:
                self._schreiben()

    def antwortet(self) -> bool:
        return self._zahl > 0

    def da_melden(self) -> None:
        t = self._jetzt()
        if t - getattr(self, "_da_geschrieben", 0.0) < ERNEUERN_S:
            return
        try:
            s, vorn = self._sitzung()
            sicher_schreiben.json_datei(self.ordner / f"{DA_PRAEFIX}{self.kennung}.json",
                                        {"bis": t + GUELTIG_S, "sitzung": s, "vorn": vorn, "benutzer": self._benutzer}, indent=None)
            self._da_geschrieben = t
        except OSError:
            pass

    def da_ende(self) -> None:
        try:
            (self.ordner / f"{DA_PRAEFIX}{self.kennung}.json").unlink(missing_ok=True)
        except OSError:
            pass
        self._da_geschrieben = 0.0

    def _andere(self) -> list[dict]:
        t = self._jetzt()
        out: list[dict] = []
        try:
            for f in self.ordner.glob(DA_PRAEFIX + "*.json"):
                if f.name == f"{DA_PRAEFIX}{self.kennung}.json":
                    continue
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    if float(d.get("bis", 0)) > t:
                        out.append(d)
                except (OSError, ValueError, AttributeError, TypeError):
                    continue
        except OSError:
            return []
        return out

    def geschwister(self) -> int:
        return len(self._andere())

    def geschwister_genau(self) -> tuple[int, int]:
        a = self._andere()
        gleich = sum(1 for d in a if d.get("benutzer") == self._benutzer)
        return gleich, len(a) - gleich

    def ruhen(self) -> bool:
        _s, vorn = self._sitzung()
        if vorn:
            return False
        return any(bool(d.get("vorn")) for d in self._andere()) or bool(self._fremd_vorn())

    def anderer_antwortet(self) -> bool:
        t = self._jetzt()
        try:
            for f in self.ordner.glob(PRAEFIX + "*.json"):
                if f.name == self._datei.name:
                    continue
                try:
                    if float(json.loads(f.read_text(encoding="utf-8")).get("bis", 0)) > t:
                        return True
                except (OSError, ValueError, AttributeError, TypeError):
                    continue
        except OSError:
            return False
        return False
