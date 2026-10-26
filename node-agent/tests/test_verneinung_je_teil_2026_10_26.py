# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import belege


def _richtung(antwort: str, frage: str) -> dict[str, int]:
    return {g: r for _s, gs in belege.regel_aussagen(antwort, frage) for g, r in gs}


def test_zweiter_teil_mit_eigener_regel_ist_nicht_verneint():
    assert _richtung("Ein Visum brauchst du nicht, und einen Reisepass musst du mitnehmen.",
                     "Brauche ich für Japan ein Visum und einen Reisepass?") == {"Visum": 1, "Reisepass": 0}
    assert _richtung("You do not need a visa, and you must carry a valid passport.",
                     "Do I need a visa and a passport for Japan?") == {"Visum": 1, "Reisepass": 0}


def test_auch_nicht_und_auch_bleiben_verneint():
    assert _richtung("Rauchen ist im Zug nicht erlaubt, und Alkohol auch nicht.", "Ist Rauchen und Alkohol im Zug erlaubt?")["Alkohol"] == 1
    assert _richtung("Alcohol is not allowed on the train, and smoking either.", "Are alcohol and smoking allowed on the train?")["Alkohol"] == 1


def test_aufzaehlung_behaelt_ihre_aussage():
    assert _richtung("Small potatoes need about 15 minutes, medium ones about 20 minutes, and large ones about 30 minutes.",
                     "How long do potatoes need to boil?") == {"potato": 0}


def test_ohne_und_wie_bisher():
    assert _richtung("Für Kanada brauchst du kein Visum.", "Brauche ich für Kanada ein Visum?") == {"Visum": 1}
    assert _richtung("Du brauchst ein Visum, aber einen Reisepass brauchst du nicht.",
                     "Brauche ich ein Visum und einen Reisepass?") == {"Visum": 0, "Reisepass": 1}
