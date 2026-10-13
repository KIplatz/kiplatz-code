# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

BUEHNE = "pakete.tausch"
ALT = "pakete.alt"
PLAN = "plan.json"
PROTOKOLL = "pakete-tausch.txt"
WARTEN_S = 30.0
ERGEBNIS = ""


def name_ok(name: str) -> bool:
    return (isinstance(name, str) and 0 < len(name) <= 120 and "/" not in name and "\\" not in name and ":" not in name
            and name not in (".", "..") and not name.startswith(".") and name != "__pycache__")


def programm_ordner() -> Path | None:
    root = Path(__file__).resolve().parent.parent
    try:
        exe = Path(sys.executable).resolve()
    except (OSError, TypeError):
        return None
    return root if exe.parent == (root / "python").resolve() else None


def _protokoll(root: Path, text: str) -> None:
    try:
        with open(root / PROTOKOLL, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
    except OSError:
        pass


def _verwerfen(root: Path) -> None:
    shutil.rmtree(root / BUEHNE, ignore_errors=True)


def beim_start(root: Path | None = None, *, warten_s: float = WARTEN_S) -> str:
    global ERGEBNIS
    try:
        ERGEBNIS = _beim_start(root, warten_s)
    except Exception as exc:
        ERGEBNIS = f"fehler {type(exc).__name__}"
    return ERGEBNIS


def _beim_start(root: Path | None, warten_s: float) -> str:
    root = root if root is not None else programm_ordner()
    if root is None:
        return ""
    root = Path(root)
    buehne = root / BUEHNE
    plan_datei = buehne / PLAN
    if not plan_datei.is_file():
        return ""
    sp = root / "python" / "Lib" / "site-packages"
    try:
        plan = json.loads(plan_datei.read_text(encoding="utf-8"))
        alt = [n for n in plan["alt"]]
        neu = [n for n in plan["neu"]]
        pakete = [str(p) for p in plan.get("pakete", [])]
    except (OSError, ValueError, KeyError, TypeError):
        _protokoll(root, "ABGELEHNT plan.json unlesbar, Tausch verworfen")
        _verwerfen(root)
        return "verworfen"
    if not neu or not all(name_ok(n) for n in alt + neu) or not sp.is_dir() or not all((buehne / n).exists() for n in neu):
        _protokoll(root, "ABGELEHNT Plan unvollständig oder unzulässig, Tausch verworfen")
        _verwerfen(root)
        return "verworfen"
    weg = list(dict.fromkeys(alt + [n for n in neu if (sp / n).exists()]))
    sicherung = root / ALT / datetime.now().strftime("%Y%m%d-%H%M%S")
    ende = time.monotonic() + max(0.0, warten_s)
    while True:
        verschoben: list[str] = []
        eingesetzt: list[str] = []
        try:
            sicherung.mkdir(parents=True, exist_ok=True)
            for n in weg:
                if (sp / n).exists():
                    os.replace(sp / n, sicherung / n)
                    verschoben.append(n)
            for n in neu:
                os.replace(buehne / n, sp / n)
                eingesetzt.append(n)
            break
        except OSError as exc:
            zurueck_fehlt = []
            for n in reversed(eingesetzt):
                try:
                    os.replace(sp / n, buehne / n)
                except OSError:
                    zurueck_fehlt.append(n)
            for n in reversed(verschoben):
                try:
                    os.replace(sicherung / n, sp / n)
                except OSError:
                    zurueck_fehlt.append(n)
            if zurueck_fehlt:
                _protokoll(root, f"FEHLER {', '.join(pakete) or 'Pakete'}: {type(exc).__name__}, nicht zurückgelegt: {', '.join(zurueck_fehlt)} "
                                 f"(liegt in {ALT}\\{sicherung.name}); nächster Versuch beim nächsten Start")
                return "wartet"
            if time.monotonic() >= ende:
                _protokoll(root, f"WARTET {', '.join(pakete) or 'Pakete'}: {type(exc).__name__}, nächster Versuch beim nächsten Start")
                shutil.rmtree(sicherung, ignore_errors=True)
                return "wartet"
            time.sleep(0.5)
    _verwerfen(root)
    for alt_ordner in sorted((root / ALT).iterdir()):
        if alt_ordner != sicherung:
            shutil.rmtree(alt_ordner, ignore_errors=True)
    _protokoll(root, f"OK getauscht {', '.join(pakete)}: {', '.join(neu)} (alt in {ALT}\\{sicherung.name})")
    return "getauscht"
