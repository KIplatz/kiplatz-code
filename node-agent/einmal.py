# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sicher_schreiben

ZEIGEN_NAME = "zeigen.txt"
_HANDLES: list = []


def _name(base_dir: Path) -> str:
    return "Local\\CommunityAI-" + hashlib.sha256(str(Path(base_dir).resolve()).lower().encode("utf-8")).hexdigest()[:16]


def sperre_holen(base_dir: Path) -> bool:
    if sys.platform != "win32":
        return True
    try:
        import win32api
        import win32event
        import winerror
    except ImportError:
        return True
    h = win32event.CreateMutex(None, False, _name(base_dir))
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return False
    _HANDLES.append(h)
    return True


def freigeben() -> None:
    while _HANDLES:
        h = _HANDLES.pop()
        try:
            import win32api
            win32api.CloseHandle(h)
        except Exception:
            pass


def _zeigen_pfad(base_dir: Path) -> Path:
    return Path(base_dir) / "diagnose" / ZEIGEN_NAME


def zeigen_anfordern(base_dir: Path) -> None:
    p = _zeigen_pfad(base_dir)
    try:
        sicher_schreiben.text(p, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
    except OSError:
        pass


def zeigen_angefordert(base_dir: Path) -> bool:
    p = _zeigen_pfad(base_dir)
    try:
        if not p.is_file():
            return False
        os.remove(p)
        return True
    except OSError:
        return False
