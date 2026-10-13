# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import nachschauen

VON_STUNDE = 5
BIS_STUNDE = 9
LAENDER = ("at", "de", "ch")
ORTE = ("Wien", "Berlin", "Bern", "Zürich", "München", "Hamburg", "Graz", "Linz", "Salzburg", "Innsbruck", "Köln", "Frankfurt am Main", "Basel", "Genf")


def einstellung_lesen(e: dict) -> dict:
    return {"an": bool(e.get("vorwaermen", True)), "zuletzt": str(e.get("vorwaermen_zuletzt") or ""), "ort": " ".join(str(e.get("morgen_ort") or "").split())[:60]}


def faellig(e: dict, jetzt: datetime) -> bool:
    s = einstellung_lesen(e)
    if not s["an"] or s["zuletzt"] == jetzt.strftime("%Y-%m-%d"):
        return False
    return VON_STUNDE <= jetzt.hour < BIS_STUNDE


def auftraege(ort_eigen: str = "") -> list[nachschauen.Auftrag]:
    out = [nachschauen.Auftrag("schlagzeilen", "Schlagzeilen", land=land) for land in LAENDER]
    orte = ([ort_eigen] if ort_eigen else []) + [o for o in ORTE if o != ort_eigen]
    out += [nachschauen.Auftrag("wetter", f"Wie wird das Wetter heute in {o}?", ort=o, tag=0) for o in orte]
    return out


def laufen(nachschauer: nachschauen.Nachschauer, merken, *, ort_eigen: str = "", weiter=lambda: True, ab: int = 0,
           stand: dict | None = None) -> tuple[int, list[str]]:
    n = 0
    fehler: list[str] = []
    liste = auftraege(ort_eigen)
    for i, a in enumerate(liste):
        if i < ab:
            continue
        if not weiter():
            if stand is not None:
                stand["weiter_ab"] = i
            break
        try:
            for e in nachschauer.ausfuehren(a):
                merken(e)
                n += 1
        except Exception as exc:
            fehler.append(f"{a.titel}: {getattr(exc, 'detail', None) or type(exc).__name__}")
    return n, fehler


__all__ = ["faellig", "auftraege", "laufen", "einstellung_lesen", "ORTE", "LAENDER", "VON_STUNDE", "BIS_STUNDE"]
