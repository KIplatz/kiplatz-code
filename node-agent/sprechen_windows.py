# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import subprocess
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core

_CREATE_NO_WINDOW = 0x08000000
LISTE_TIMEOUT_S = 30
ERKENNEN_TIMEOUT_S = 180
KULTUREN = {"de": ("de-DE", "de-AT", "de-CH"), "en": ("en-US", "en-GB")}

_LISTE = (
    "$ErrorActionPreference = 'Stop'\n"
    "Add-Type -AssemblyName System.Speech\n"
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
    "$n = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | ForEach-Object { $_.Culture.Name }\n"
    "[Console]::Out.Write(($n -join ' '))\n"
)

_ERKENNEN = (
    "$ErrorActionPreference = 'Stop'\n"
    "Add-Type -AssemblyName System.Speech\n"
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
    "$r = New-Object System.Speech.Recognition.SpeechRecognitionEngine([System.Globalization.CultureInfo]'{kultur}')\n"
    "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))\n"
    "$r.SetInputToWaveFile('{wav}')\n"
    "$t = @()\n"
    "while ($true) {{ try {{ $x = $r.Recognize() }} catch {{ break }}; if ($x -eq $null) {{ break }}; if ($x.Text) {{ $t += $x.Text }} }}\n"
    "$r.Dispose()\n"
    "[Console]::Out.Write(($t -join ' '))\n"
)


class WindowsError_(app_core.AppError):
    pass


def befehl(script: str) -> list[str]:
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode("ascii")]


def _ps_text(s: str) -> str:
    return s.replace("'", "''")


def kultur_fuer(sprache: str, vorhanden: list[str]) -> str:
    s = (sprache or "de").lower()[:2]
    for wunsch in KULTUREN.get(s, ()):
        if wunsch in vorhanden:
            return wunsch
    for k in vorhanden:
        if k.lower().startswith(s):
            return k
    return ""


class Erkenner:

    def __init__(self, laufen=subprocess.run) -> None:
        self._laufen = laufen
        self._kulturen: list[str] | None = None
        self._lock = threading.Lock()

    def _lauf(self, script: str, timeout: float) -> str:
        r = self._laufen(befehl(script), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                         creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if getattr(r, "returncode", 1) != 0:
            rest = (getattr(r, "stderr", "") or "")[-300:].strip().replace("\n", " ")
            raise WindowsError_("SPRECHEN_WINDOWS", f"die Windows-Spracherkennung meldet Code {r.returncode}: {rest}")
        return (getattr(r, "stdout", "") or "").strip()

    def kulturen(self) -> list[str]:
        if sys.platform != "win32":
            return []
        with self._lock:
            if self._kulturen is None:
                try:
                    self._kulturen = [k for k in self._lauf(_LISTE, LISTE_TIMEOUT_S).split() if k]
                except Exception:
                    self._kulturen = []
            return list(self._kulturen)

    def verfuegbar(self, sprache: str = "de") -> bool:
        return bool(kultur_fuer(sprache, self.kulturen()))

    def erkennen(self, wav: Path, sprache: str = "de") -> str:
        kultur = kultur_fuer(sprache, self.kulturen())
        if not kultur:
            raise WindowsError_("SPRECHEN_WINDOWS", f"Windows hat keine Spracherkennung für „{sprache}“ installiert")
        try:
            return self._lauf(_ERKENNEN.format(kultur=_ps_text(kultur), wav=_ps_text(str(wav))), ERKENNEN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise WindowsError_("SPRECHEN_WINDOWS", "das Verstehen hat zu lange gedauert") from None
        except OSError as exc:
            raise WindowsError_("SPRECHEN_WINDOWS", f"PowerShell startet nicht ({exc.__class__.__name__})") from None


class Keiner:

    def kulturen(self) -> list[str]:
        return []

    def verfuegbar(self, sprache: str = "de") -> bool:
        return False

    def erkennen(self, wav: Path, sprache: str = "de") -> str:
        raise WindowsError_("SPRECHEN_WINDOWS", "keine Windows-Spracherkennung")


__all__ = ["Erkenner", "Keiner", "WindowsError_", "befehl", "kultur_fuer", "KULTUREN"]
