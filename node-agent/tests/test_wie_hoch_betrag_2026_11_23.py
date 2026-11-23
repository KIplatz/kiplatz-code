# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wissen

GELD = "Höhe der Mindestpension in Österreich: Der Richtsatz für 2026 beträgt € 1.308,39 für Alleinstehende."
LEER = "Die Mindestpension in Österreich ist keine eigene Pensionsart, sondern heißt Ausgleichszulage."
BERG = "Der Großglockner ist mit 3.798 m der höchste Berg Österreichs."


@pytest.mark.parametrize("frage", [
    "Wie hoch ist die Mindestpension in Österreich?",
    "Wie hoch ist die Familienbeihilfe?",
    "Wie hoch ist der Mindestlohn in Deutschland?",
    "Welche Höhe hat die Pendlerpauschale?",
    "How much is the state pension in the UK?",
])
def test_betrag_vor_meter(frage):
    m = wissen.mass_punkte(frage)
    assert m is not None and m(GELD) >= 1.0 > m(LEER) and m(BERG) < 1.0


@pytest.mark.parametrize("frage", [
    "Wie hoch ist der Großglockner?",
    "Wie hoch fliegt ein Flugzeug?",
    "Welche Höhe hat der Stephansdom?",
    "Wie hoch ist ein Wohnwagen?",
    "Wie hoch springen Delfine?",
    "Wie hoch ist der höchste Berg im Trentino?",
    "Wie hoch ist die Kaffeemaschine?",
    "Wie hoch ist der Schneeberg, lohnt sich der Aufstieg?",
    "Wie hoch ist der Dachstein? Welche Gebühr zahlt man für die Seilbahn?",
])
def test_hoehe_bleibt_hoehe(frage):
    m = wissen.mass_punkte(frage)
    assert m is not None and m(BERG) >= 1.0 and m(GELD) < 1.0


@pytest.mark.parametrize("frage,geld", [
    ("How much caffeine is in coffee?", False),
    ("How much current does a fridge draw?", False),
    ("How much is the rent in Vienna?", True),
    ("Wie hoch ist das Bruttogehalt einer Pflegerin?", True),
    ("Wie hoch ist der Alkoholgehalt von Bier?", False),
])
def test_geldwort_nur_als_ganzes(frage, geld):
    m = wissen.mass_punkte(frage)
    assert (m is not None and m(GELD) >= 1.0) is geld
