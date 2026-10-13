# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege
import pruefstand
import selbstauskunft

HEUTE = date(2026, 9, 24)
BMF = ("Amtliches Kilometergeld (Finanzministerium), gelesen am 24.09.2026: Auflistung der Kilometergelder (ab 1. Juli 2025): "
       "Kraftfahrzeugtype Kilometergeld in Euro (auf volle Cent aufgerundet) PKW 0,50 Motorfahrräder und Motorräder 0,25 "
       "Mitfahrerinnen/Mitfahrer 0,15 Fahrrad 0,25 Auflistung der Kilometergelder (bis 31. Dezember 2024): PKW 0,42 "
       "Letzte Aktualisierung: 1. Jänner 2026")
QUELLEN = [{"nummer": 1, "art": "nachgeschaut", "titel": "Amtliches Kilometergeld (Finanzministerium)", "text": BMF}]
FRAGE = "Wie hoch ist das amtliche Kilometergeld in Österreich?"


@pytest.mark.parametrize("frage", ["Was kostet das Klimaticket Österreich?", "Was kostet es, ein Auto anzumelden?", "Was kostet das?",
                                   "Was sind Credits bei Audible?", "Was steht in der Hausordnung meines Wohnhauses?"])
def test_other_price_and_rule_questions_go_to_the_model(frage):
    assert selbstauskunft.antwort(frage) is None


def test_a_thousands_separator_is_no_difference():
    erwartet = "Das Allalinhorn ist ein 4027 Meter hoher Berg in den Walliser Alpen in der Schweiz."
    assert pruefstand.bewerten("Das Allalinhorn ist 4.027 Meter hoch.", erwartet, ["4027"])[0]
    assert pruefstand.bewerten("Das Allalinhorn ist 4 027 Meter hoch.", erwartet, ["4027"])[0]
    assert not pruefstand.bewerten("Das Allalinhorn ist 4.207 Meter hoch.", erwartet, ["4027"])[0]
    assert pruefstand.bewerten("Classic kostet 1400,00 €.", "Classic 1.400,00 €", ["1.400,00"])[0]
    assert pruefstand.bewerten("3 × 9,90 € = 29,70 €.", "3 mal 9,90 Euro sind 29,70 Euro.", ["29,70"])[0]


def test_since_when_from_the_page_read_is_todays_state():
    antwort = "Das amtliche Kilometergeld beträgt seit 1. Juli 2025 für einen PKW 0,50 € pro Kilometer (Quelle 1)."
    text, notizen = app_web.belege_anwenden(antwort, FRAGE, BMF, QUELLEN, heute=HEUTE)
    assert "0,50" in text and not any("früheres Jahr" in n for n in notizen)


def test_an_old_state_is_still_struck():
    alt = "Das Kilometergeld beträgt seit 2024 0,44 € pro Kilometer."
    assert not belege.seit_belegt(alt, BMF)
    text, _ = app_web.belege_anwenden(alt, FRAGE, BMF, QUELLEN, heute=HEUTE)
    assert "0,44" not in text
    bis = "Bis 31. Dezember 2024 waren es 0,42 € für einen PKW."
    assert not belege.seit_belegt(bis, BMF)
    assert not belege.seit_belegt("Seit 1. Juli 2025 sind es 0,50 € (Quelle 1).", "")
