# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rechnen
import rechnen_fristen


@pytest.mark.parametrize("frage,teil", [
    ("Wie lange ist die Kündigungsfrist für Angestellte in Österreich nach 6 Dienstjahren?", "nach 6 vollendeten Dienstjahren 3 Monate"),
    ("Kündigungsfrist in Österreich, ich bin 1 Jahr beschäftigt", "nach 1 vollendeten Dienstjahr 6 Wochen"),
    ("Wie lange ist die Kündigungsfrist im 16. Dienstjahr in Österreich?", "nach 15 vollendeten Dienstjahren 4 Monate"),
    ("Kündigungsfrist Österreich nach 2 Dienstjahren", "2 Monate"),
    ("Kündigungsfrist Österreich nach 30 Arbeitsjahren", "5 Monate"),
])
def test_stufen(frage, teil):
    de = rechnen.loesen(frage).de
    assert teil in de and "Kündigst du selbst, gilt 1 Monat zum Monatsletzten" in de and "§ 20 Abs. 2" in de and "zum Quartalsende" in de


@pytest.mark.parametrize("frage", [
    "Kündigungsfrist Deutschland nach 6 Jahren",
    "Wie lange ist die Kündigungsfrist für Angestellte in Österreich?",
    "Kündigungsfrist für Lehrlinge in Österreich nach 2 Jahren",
    "Welche Kündigungsfrist steht im Kollektivvertrag Handel in Österreich nach 6 Dienstjahren?",
    "Kündigungsfrist Mietvertrag Österreich nach 3 Jahren",
    "Handyvertrag Kündigungsfrist nach 2 Jahren Österreich",
    "Kündigungsfrist für Arbeiter im Tourismus in Österreich nach 6 Dienstjahren",
    "Kündigungsfrist in Karenz in Österreich nach 6 Dienstjahren als Angestellte",
])
def test_gegenproben(frage):
    assert rechnen_fristen.loesen(frage) is None


def test_wer_selbst_kuendigt_liest_zuerst_die_eigene_frist():
    de = rechnen.loesen("Ich will kündigen. Welche Kündigungsfrist habe ich in Österreich nach 6 Dienstjahren als Angestellter?").de
    assert de.startswith("Kündigst du selbst, gilt 1 Monat zum Monatsletzten")
    assert "3 Monate" in de and "bis zu 6 Monate" in de
