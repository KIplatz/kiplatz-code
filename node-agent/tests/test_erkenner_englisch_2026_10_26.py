# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen
import region


@pytest.mark.parametrize("frage, ort, tag", [
    ("What will the weather be like in London tomorrow?", "London", 1),
    ("Will it rain in Tokyo today?", "Tokyo", 0),
    ("Weather forecast New York the day after tomorrow", "New York", 2),
    ("Wie wird das Wetter morgen in Wien?", "Wien", 1),
    ("Is it sunny in Rome?", "Rome", 0),
    ("What are the temperatures in Vienna?", "Vienna", 0),
])
def test_wetter_in_beiden_sprachen(frage, ort, tag):
    a = nachschauen.erkennen(frage)
    assert a is not None and a.art == "wetter" and a.ort == ort and a.tag == tag, frage


@pytest.mark.parametrize("frage", ["Why does it rain?", "What is a temperature inversion?", "Write a poem about the rain",
                                   "Warum regnet es?", "At how many degrees Fahrenheit does water boil?",
                                   "What is the economic forecast for Austria next year?", "Is it worth buying snow chains?",
                                   "Does it make sense to buy a heat pump?", "Is it dangerous to look at the sun?", "Kann es im Sommer schneien?"])
def test_erklaeren_und_schreiben_ist_kein_wetter(frage):
    a = nachschauen.erkennen(frage)
    assert a is None or a.art != "wetter", frage


def test_schlagzeilen_englisch_mit_land():
    a = nachschauen.erkennen("What are the latest headlines in Germany?")
    assert a is not None and a.art == "schlagzeilen" and a.land == "de"


@pytest.mark.parametrize("frage, land, gebiet", [
    ("When are the semester holidays in Upper Austria?", "at", "OÖ"),
    ("Is November 1 a public holiday in Bavaria?", "de", "BY"),
    ("What is the speed limit in Vienna?", "at", "W"),
    ("How do I register as unemployed in Austria?", "at", ""),
    ("How much is VAT in Switzerland?", "ch", ""),
    ("Which trains go from Munich to Cologne?", "de", "BY"),
])
def test_orte_auch_englisch(frage, land, gebiet):
    r = region.erkennen(frage)
    assert r is not None and (r.land, r.gebiet) == (land, gebiet), frage


@pytest.mark.parametrize("frage", ["What is a Wiener Schnitzel Viennese style?", "Translate this into German", "Who was Hermann Hesse?",
                                   "What is the best cologne for men?", "What do the Geneva Conventions say?", "Who was the House of Hanover?"])
def test_keine_falschen_orte(frage):
    assert region.erkennen(frage) is None, frage


def test_schlagzeilen_nur_wenn_gemeint():
    a = nachschauen.erkennen("What is happening in my body when I fast?")
    assert a is None or a.art != "schlagzeilen"
