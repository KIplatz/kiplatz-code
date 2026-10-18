# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kalender_dach
import kalender_tage

H = date(2026, 10, 18)


def test_der_advent_wird_berechnet_auch_wenn_der_24_ein_sonntag_ist():
    assert [str(kalender_tage.erster_advent(j)) for j in (2023, 2026, 2027, 2028)] == ["2023-12-03", "2026-11-29", "2027-11-28", "2028-12-03"]
    titel, text, ganz = kalender_dach.quelle("Wann beginnt der Advent 2026?", H)
    assert ganz and "berechnet" in titel
    assert "1. Advent, Beginn der Adventszeit und des Kirchenjahres: Sonntag, 29.11.2026" in text and "4. Advent: Sonntag, 20.12.2026" in text
    assert "Aschermittwoch" not in text


def test_bewegliche_tage_und_zeitumstellung():
    t = dict((n.split(" (")[0].split(",")[0], d) for d, n in kalender_tage.tage(2027))
    assert t["Ostersonntag"] == date(2027, 3, 28) and t["Aschermittwoch"] == date(2027, 2, 10) and t["Karfreitag"] == date(2027, 3, 26)
    assert t["Pfingstsonntag"] == date(2027, 5, 16) and t["Muttertag"] == date(2027, 5, 9) and t["Vatertag in Österreich"] == date(2027, 6, 13)
    assert t["Zeitumstellung auf Sommerzeit"] == date(2027, 3, 28) and t["Zeitumstellung auf Winterzeit"] == date(2027, 10, 31)
    _, text, _ = kalender_dach.quelle("Wann werden die Uhren umgestellt?", H)
    assert "Zeitumstellung auf Winterzeit (Uhr um 3 Uhr eine Stunde zurück): Sonntag, 25.10.2026" in text
    _, text, _ = kalender_dach.quelle("Wann ist Ostern 2027?", H)
    assert "Ostersonntag: Sonntag, 28.3.2027" in text and "Ostermontag: Montag, 29.3.2027" in text


def test_nur_mit_einer_frage_nach_dem_zeitpunkt():
    for frage in ("Wie mache ich einen Adventskranz?", "Was ist Halloween?", "Wie funktioniert eine Wärmepumpe?"):
        assert kalender_dach.quelle(frage, H) is None, frage


def test_feiertage_fuer_das_gefragte_jahr():
    _, text, _ = kalender_dach.quelle("Feiertage 2028 in Bayern", H)
    assert "für 2028:" in text and "Neujahr: Samstag, 1.1.2028" in text and "2027" not in text
    _, text, _ = kalender_dach.quelle("Welche Feiertage gibt es 2028 in Österreich?", H)
    assert "Österreich 2028" in text and "Nationalfeiertag: Donnerstag, 26.10.2028" in text and "2026" not in text.split("\n", 1)[1]
