# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege

MINDEST = ("Die Mindestpension in Österreich ist aktuell (Stand September 2026) nicht als feste Summe festgelegt. Genauere Angaben zu den "
           "konkreten Beträgen für 2026 gibt es noch nicht auf den aktuellen Seiten des AMS.")


@pytest.mark.parametrize("text,soll", [
    (MINDEST, True),
    ("Dazu gibt es noch keine konkreten Zahlen.", True),
    ("No official figures are available yet.", True),
    ("Die Ausgleichszulage beträgt 2025 1.273,99 Euro. Für 2026 gibt es noch keine Angaben.", False),
    ("Buchstaben sind keine Zahlen.", False),
    ("Aktuelle Informationen gibt es nicht nur auf der Website, sondern auch in der App.", False),
    ("Für Privatpersonen gibt es keine gesetzliche Pflicht.", False),
])
def test_keine_angabe_sucht_weiter(text, soll):
    assert app_web.keine_angabe(text) is soll


def test_keine_angabe_ist_kein_weiss_nicht():
    assert not app_web._WEISS_NICHT.search(MINDEST)
    assert not app_web._WEISS_NICHT.search("Zur Zahl der Verletzten gibt es noch keine Angaben.")


@pytest.mark.parametrize("text,weg", [
    ("Facing her first term as prime minister since 21 October 2025, Sanae Takaichi is the first woman to hold that role. "
     "She was the first woman to hold this role.", ["She was the first woman to hold this role."]),
    ("Viele glauben, dass Spinat besonders viel Eisen enthält. Spinat enthält nicht besonders viel Eisen.", []),
    ("Darf man in Österreich am Sonntag Rasen mähen? In Österreich darf man am Sonntag nicht Rasen mähen.", []),
    ("Wien ist größer als Graz und Linz zusammen. Graz ist größer als Linz.", []),
    ("Tokio liegt östlich von Osaka und Kyoto. Kyoto liegt östlich von Osaka.", []),
    ("Wien hat 2 Millionen Einwohner. Wien ist die größte Stadt Österreichs. Die Stadt Wien liegt an der Donau.", []),
])
def test_wortgleiche_wiederholung(text, weg):
    assert belege.angehaengte_saetze(text) == weg


def test_nicht_bei_schreibauftraegen():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert "angehaengt = belege.angehaengte_saetze(geprueft) if not schreiben else []" in quelle


def test_zeichengleich_doppelt_nur_die_wiederholung_faellt():
    t = "Canberra is the capital of Australia. It was chosen as a compromise. Canberra is the capital of Australia."
    quelle = [{"nummer": 1, "titel": "x", "adresse": "https://x.gov.au",
               "text": "Australia: the national capital, Canberra, was picked in 1908 as a compromise site between rivals Sydney and Melbourne."}]
    out, _n = app_web.belege_anwenden(t, "What is the capital of Australia?", "", quelle)
    assert out == "Canberra is the capital of Australia. It was chosen as a compromise."
