# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen


@pytest.mark.parametrize("frage,soll", [
    ("How much does a Schengen visa cost?", True),
    ("Wie viele Einwohner hat die Schweiz?", True),
    ("How many people live in Nigeria?", True),
    ("Wie viel kostet die Vignette in Slowenien?", True),
    ("Wie hoch ist die Inflation in Österreich?", True),
    ("Was kostet ein Big Mac in der Schweiz?", False),
    ("Was kostet ein Liter Diesel in Deutschland?", False),
    ("Wer hat das Penicillin entdeckt?", False),
    ("How much does a Eurail Global Pass cost?", False),
    ("Was kostet der Xbox Game Pass?", False),
    ("What are the fees for PayPal?", False),
    ("How much is a Windows 11 license?", False),
    ("How much does a passport cost in the UK?", True),
])
def test_amtlich_zuerst(frage, soll):
    assert nachschauen.amtlich_zuerst(frage) is soll


def test_statistikamt_ist_amtlich_zaehlerseite_ist_schaetzung():
    assert nachschauen.amtlich("https://www.statistik.at/statistiken/bevoelkerung")
    assert nachschauen.amtlich("https://www.bfs.admin.ch/bfs/de/home.html")
    assert nachschauen.amtlich("https://home-affairs.ec.europa.eu/policies/schengen")
    assert nachschauen.schaetzseite("Schweiz Bevölkerung (2026)", "https://populationtoday.com/de/ch-switzerland/")
    assert nachschauen.schaetzseite("Switzerland Population", "https://www.worldometers.info/world-population/switzerland-population/")


def test_reihung_amtliche_seite_vor_blog_bei_gebuehr():
    treffer = [
        {"adresse": "https://myschengen.com/blog/schengen-visa-costs-fees/", "titel": "Schengen visa cost and fees", "text": "Schengen visa cost €80"},
        {"adresse": "https://home-affairs.ec.europa.eu/policies/schengen/visa-policy_en", "titel": "Visa policy", "text": "Schengen visa fee"},
    ]
    out = nachschauen.treffer_reihen(treffer, "How much does a Schengen visa cost?", heute=date(2026, 11, 23))
    assert out[0]["adresse"].startswith("https://home-affairs.ec.europa.eu")


def test_amtliche_seite_ohne_kernwort_faellt_bei_zahlen():
    treffer = [{"adresse": "https://www.destatis.de/DE/Themen/Bevoelkerung", "titel": "Bevölkerung Deutschland", "text": "Einwohner 83 Mio"},
               {"adresse": "https://www.bfs.admin.ch/bfs/de/home/statistiken/bevoelkerung.html", "titel": "Bevölkerung Schweiz", "text": "Einwohner Schweiz"}]
    out = nachschauen.treffer_reihen(treffer, "Wie viele Einwohner hat die Schweiz?", heute=date(2026, 11, 23),
                                     kern=frozenset({"schweiz", "einwohn"}))
    assert out[0]["adresse"].startswith("https://www.bfs.admin.ch")


def test_visa_karte_ist_keine_behoerdengebuehr():
    assert nachschauen._AMTS_GEBUEHR.search("Welche Gebühren hat die Visa-Karte?") is None
    assert nachschauen._AMTS_GEBUEHR.search("What does a visa card cost?") is None
    assert nachschauen._AMTS_GEBUEHR.search("How much is a US visa?")
