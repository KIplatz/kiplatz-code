# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

import sicher_schreiben

MARKE = "umzug.json"
STUECK = 8 * 1024 * 1024
RESERVE_MB = 2_000
BEHALTEN_PRUEFEN_S = 3600


def _gleich(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a == b


def vormerken(von: Path, nach: Path) -> bool:
    von, nach = Path(von), Path(nach)
    if _gleich(von, nach) or not von.is_dir() or von.name != nach.name:
        return False
    nach.mkdir(parents=True, exist_ok=True)
    sicher_schreiben.json_datei(nach / MARKE, {"von": str(von), "kopiert": False})
    return True


def offen(ordner: Path) -> dict | None:
    try:
        d = json.loads((Path(ordner) / MARKE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("von") else None
    except (OSError, ValueError):
        return None


def _kopieren(quelle: Path, ziel: Path, halt) -> bool:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with open(quelle, "rb") as q, open(ziel, "wb") as z:
        while True:
            if halt():
                return False
            b = q.read(STUECK)
            if not b:
                break
            h.update(b)
            z.write(b)
    g = hashlib.sha256()
    with open(ziel, "rb") as z:
        while True:
            if halt():
                return False
            b = z.read(STUECK)
            if not b:
                break
            g.update(b)
    if g.digest() != h.digest():
        raise OSError(f"Kopie von {quelle.name} weicht ab")
    return True


def schritt(ordner: Path, *, behalten: bool, schliessen, oeffnen, halt, log, name: str, platte_frei_mb, jetzt=time.time) -> float | None:
    ordner = Path(ordner)
    m = offen(ordner)
    if m is None:
        return None
    von = Path(m["von"])
    if von.name != ordner.name or _gleich(von, ordner):
        (ordner / MARKE).unlink(missing_ok=True)
        return 0
    if not m.get("kopiert") and not behalten:
        seit = float(m.get("nicht_behalten_seit") or 0) or jetzt()
        if not m.get("nicht_behalten_seit"):
            sicher_schreiben.json_datei(ordner / MARKE, {**m, "nicht_behalten_seit": seit})
        if jetzt() - seit < BEHALTEN_PRUEFEN_S:
            log(f"OK {name}: Umzug wartet, das Gerät hält die Kopie gerade nicht; nichts gelöscht, nächster Blick in 10 Minuten")
            return 600
    elif m.get("nicht_behalten_seit"):
        sicher_schreiben.json_datei(ordner / MARKE, {k: v for k, v in m.items() if k != "nicht_behalten_seit"})
    if m.get("kopiert") or not behalten:
        shutil.rmtree(von, ignore_errors=True)
        (ordner / MARKE).unlink(missing_ok=True)
        log(f"OK {name}: alte Kopie auf {von.anchor or von} gelöscht" if m.get("kopiert") else f"OK {name}: Freigabe zu klein, alte Kopie gelöscht")
        oeffnen()
        return 0
    if not von.is_dir():
        (ordner / MARKE).unlink(missing_ok=True)
        log(f"OK {name}: keine alte Kopie gefunden, sie wird neu geholt")
        return 0
    dateien = sorted((p for p in von.rglob("*") if p.is_file()), key=lambda p: (p.name == "stand.json", str(p)))
    groesse_mb = sum(p.stat().st_size for p in dateien) // 1_000_000
    frei_mb = int(platte_frei_mb(ordner))
    if frei_mb - RESERVE_MB < groesse_mb:
        log(f"OK {name}: Umzug wartet, auf dem neuen Laufwerk sind {frei_mb // 1000} GB frei, gebraucht werden {groesse_mb // 1000 + 2} GB")
        return 3600
    schliessen()
    log(f"OK {name}: Umzug beginnt, {len(dateien)} Dateien, {groesse_mb // 1000} GB")
    for p in dateien:
        if not _kopieren(p, ordner / p.relative_to(von), halt):
            log(f"OK {name}: Umzug unterbrochen, er beginnt beim nächsten Start von vorne")
            return 0
    sicher_schreiben.json_datei(ordner / MARKE, {"von": str(von), "kopiert": True})
    log(f"OK {name}: Umzug fertig, alle {len(dateien)} Dateien geprüft")
    return schritt(ordner, behalten=behalten, schliessen=schliessen, oeffnen=oeffnen, halt=halt, log=log, name=name, platte_frei_mb=platte_frei_mb, jetzt=jetzt)
