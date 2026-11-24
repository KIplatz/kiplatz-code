# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rechnen


@pytest.mark.parametrize("frage,antwort", [
    ("Schreibe 2024 in römischen Zahlen.", "2024 ist römisch MMXXIV. (MM = 2000, XX = 20, IV = 4)"),
    ("Wie schreibt man 49 als römische Zahl?", "49 ist römisch XLIX. (XL = 40, IX = 9)"),
    ("Welche Zahl ist XLII?", "XLII ist 42. (XL = 40, II = 2)"),
    ("Was ist MMXXIV in Zahlen?", "MMXXIV ist 2024. (MM = 2000, XX = 20, IV = 4)"),
    ("MCMLXXXV in arabischen Zahlen", "MCMLXXXV ist 1985. (M = 1000, CM = 900, LXXX = 80, V = 5)"),
    ("7 in römischen Zahlen", "7 ist römisch VII."),
])
def test_roemisch(frage, antwort):
    assert rechnen.loesen(frage).de == antwort


@pytest.mark.parametrize("frage", ["Was ist CD?", "Was ist XL?", "Welche Zahl ist IIII?", "Was ist MIX?"])
def test_keine_roemische_zahl(frage):
    r = rechnen.loesen(frage)
    assert r is None or "römisch" not in r.de and " ist " not in r.de[:12]


@pytest.mark.parametrize("frage", ["Was ist XL in Zahlen?", "CL in Zahlen", "IV in Zahlen", "Welche Zahl ist X?"])
def test_abkuerzungen_ohne_roemisch(frage):
    r = rechnen.loesen(frage)
    assert r is None or " ist " not in r.de[:12]


def test_kurze_mit_roemisch():
    assert rechnen.loesen("Die römische Zahl XL in Zahlen").de.startswith("XL ist 40.")
