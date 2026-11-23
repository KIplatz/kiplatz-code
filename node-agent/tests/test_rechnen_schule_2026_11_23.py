# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rechnen
import rechnen_schule


@pytest.mark.parametrize("frage,beginn", [
    ("Dividiere die Zahl durch 6 und du erhältst 22 Rest 2. Wie heißt die Zahl?", "Die Zahl ist 134."),
    ("Dividiere die Zahl durch 4 und du erhältst 16 Rest 1.", "Die Zahl ist 65."),
    ("Dividiere die Zahl durch 3 und du erhältst 37 Rest 1. Wie heißt die Zahl?", "Die Zahl ist 112."),
    ("Teile die Zahl durch 5 und du erhältst 9.", "Die Zahl ist 45."),
    ("Multipliziere die Zahl mit 7 und du erhältst 63. Wie heißt die Zahl?", "Die Zahl ist 9."),
    ("Addiere 25 zur Zahl und du erhältst 80.", "Die Zahl ist 55."),
])
def test_zahlenraetsel(frage, beginn):
    assert rechnen.loesen(frage).de.startswith(beginn)


def test_zahlenraetsel_mit_probe():
    de = rechnen.loesen("Dividiere die Zahl durch 6 und du erhältst 22 Rest 2. Wie heißt die Zahl?").de
    assert "6 · 22 = 132" in de and "132 + 2 = 134" in de and "Probe: 134 : 6 = 22 Rest 2." in de


def test_tiere_und_beine_kindgerecht():
    de = rechnen.loesen("Auf dem Hof gibt es Ziegen und Enten. Zusammen sind es 15 Tiere mit 42 Beinen. Wie viele sind es?").de
    assert de.startswith("Es sind 6 Ziegen und 9 Enten.")
    assert "Wären alle 15 Tiere Enten" in de and "x" not in de.replace("Ex", "")
    assert "Probe: 6 · 4 + 9 · 2 = 24 + 18 = 42 Beine." in de


def test_reihenfolge():
    de = rechnen.loesen("Mia, Selina, Nick und Elisa reiten mit den Pferden aus. Nick reitet vor Mia und hinter Elisa. Elisa reitet nicht als "
                        "Erste. In welcher Reihenfolge reiten die Kinder?").de
    assert de.startswith("Die Reihenfolge ist: Selina, Elisa, Nick und Mia.")


def test_reihenfolge_nicht_eindeutig_bleibt_beim_modell():
    assert rechnen_schule.loesen("Anna, Ben und Carla laufen. Anna läuft vor Ben. In welcher Reihenfolge laufen sie?") is None


@pytest.mark.parametrize("frage,teil", [
    ("Wo hat Flo Fehler gemacht? 319 : 3 = 105 R 4, gerechnet als 300 : 3 = 100 und 19 : 3 = 5 R 4.", "Der Rest 4 ist größer als 3"),
    ("Wo hat Flo Fehler gemacht? 259 : 3 = 66 R 1, 240 : 3 = 60, 19 : 3 = 6 R 1", "richtig ist 240 : 3 = 80"),
    ("Stimmt das? 649 : 8 = 81 R 1", "Das stimmt: 649 : 8 = 81 Rest 1."),
    ("Wo ist der Fehler? 446 : 6 = 74 R 3", "Richtig ist 446 : 6 = 74 Rest 2."),
])
def test_fehler_suchen(frage, teil):
    assert teil in rechnen.loesen(frage).de


@pytest.mark.parametrize("frage", [
    "Wie viele Einwohner hat Wien?",
    "Wie hoch ist der Großglockner?",
    "Wer ist Bundeskanzler von Österreich?",
    "Dividiere die Zahl durch 6 und du erhältst 22 Rest 7.",
    "Hühner und Hähne: 10 Tiere mit 20 Beinen.",
])
def test_gegenproben(frage):
    assert rechnen_schule.loesen(frage) is None


def test_fable_zu_23a():
    assert rechnen.loesen("Subtrahiere die Zahl von 100 und du erhältst 37.").de.startswith("Die Zahl ist 63.")
    assert rechnen.loesen("Ziehe die Zahl von 50 ab und du erhältst 20.").de.startswith("Die Zahl ist 30.")
    de = rechnen.loesen("Wo hat Flo Fehler gemacht? 17 : 5 = 3 R 2, 29 : 4 = 7 R 1, 50 : 6 = 8 R 3").de
    assert "17 : 5 = 3 Rest 2 stimmt." in de and "29 : 4 = 7 Rest 1 stimmt." in de and "50 : 6 = 8 Rest 3 stimmt nicht, richtig ist 8 Rest 2." in de
    assert rechnen_schule.loesen("Ziegen und Enten: 15 Tiere mit 42 Beinen. Schreib eine Geschichte dazu.") is None
    assert rechnen_schule.loesen("Ziegen, Schafe und Enten: Zusammen sind es 15 Tiere mit 42 Beinen. Wie viele sind es?") is None
    assert rechnen_schule.loesen("Mia, Selina, Nick und Elisa reiten aus. Nick reitet vor Mia und Selina reitet hinter Elisa. Elisa reitet nicht "
                                 "als Erste. In welcher Reihenfolge reiten sie?") is None
    assert rechnen_schule.loesen("Mia, Selina, Nick und Elisa reiten aus. Mia reitet weder vor Nick noch hinter Elisa. In welcher Reihenfolge "
                                 "reiten sie?") is None
    assert "Richtig ist 446 : 6 = 74 Rest 2." in rechnen.loesen("Wo ist der Fehler? 446 ÷ 6 = 74 r 3").de
