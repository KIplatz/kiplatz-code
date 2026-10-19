# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kalender_dach
import kalender_tage
import kalender_welt
import laender

HEUTE = date(2026, 10, 18)


def test_the_us_ist_ein_land_us_allein_nicht():
    assert laender.alle("When does daylight saving time end in the US this year?") == {"US"}
    assert laender.alle("Do I need a visa for the U.S.?") == {"US"}
    assert laender.alle("Can you help us with the recipe?") == set()


def test_ein_jahr_ohne_zahl_zaehlt_vom_heutigen_tag():
    assert kalender_tage.jahre("When is Thanksgiving in Canada this year?", HEUTE) == [2026]
    assert kalender_tage.jahre("Wann ist heuer der erste Advent?", HEUTE) == [2026]
    assert kalender_tage.jahre("Wann ist nächstes Jahr Ostern?", HEUTE) == [2027]
    assert kalender_tage.jahre("When was Easter last year?", HEUTE) == [2025]
    assert kalender_tage.jahre("Ostern 2028", HEUTE) == [2028]
    assert kalender_tage.jahre("Wann ist Ostern?", HEUTE) == []


def test_thanksgiving_this_year_nennt_den_tag_dieses_jahres_auch_wenn_er_vorbei_ist():
    frage = "When is Thanksgiving in Canada this year?"
    je_jahr = {j: [{"datum": d, "name": "Thanksgiving", "lokal": "Thanksgiving"}]
               for j, d in ((2026, "2026-10-12"), (2027, "2027-10-11"))}
    gefragt = {j: je_jahr[j] for j in kalender_welt.jahre(frage, HEUTE)}
    text = kalender_welt.text("CA", gefragt, frage, HEUTE)
    assert "12.10.2026" in text and "2027" not in text.split("(heute")[0] + text.split(":", 1)[1]


def test_zeitumstellung_usa_kanada_europa_suedhalbkugel():
    titel, text, ganz = kalender_dach.quelle("When does daylight saving time end in the US this year?", HEUTE)
    assert ganz and "Vereinigte Staaten" in titel
    assert "Ende der Sommerzeit (die Uhr springt um 2 Uhr eine Stunde zurück auf 1 Uhr): Sonntag, 1.11.2026" in text
    assert "Beginn der Sommerzeit (die Uhr springt um 2 Uhr eine Stunde vor auf 3 Uhr): Sonntag, 8.3.2026" in text and "Arizona" in text
    _t, text, _g = kalender_dach.quelle("Wann ist die Zeitumstellung in Kanada?", HEUTE)
    assert "Sonntag, 1.11.2026" in text and "Sonntag, 14.3.2027" in text and "8.3.2026" not in text
    _t, text, _g = kalender_dach.quelle("When do the clocks go back in the UK in 2026?", HEUTE)
    assert "um 2 Uhr eine Stunde zurück auf 1 Uhr): Sonntag, 25.10.2026" in text and "29.3.2026" in text
    _t, text, _g = kalender_dach.quelle("Wann ist die Zeitumstellung in Australien 2026?", HEUTE)
    assert "Ende der Sommerzeit (die Uhr springt um 3 Uhr eine Stunde zurück auf 2 Uhr): Sonntag, 5.4.2026" in text
    assert "Beginn der Sommerzeit (die Uhr springt um 2 Uhr eine Stunde vor auf 3 Uhr): Sonntag, 4.10.2026" in text and "Queensland" in text
    _t, text, _g = kalender_dach.quelle("When does daylight saving start in New Zealand in 2026?", HEUTE)
    assert "Sonntag, 27.9.2026" in text and "Sonntag, 5.4.2026" in text
    _t, text, _g = kalender_dach.quelle("When does daylight saving time start in Greece in 2027?", HEUTE)
    assert "um 3 Uhr eine Stunde vor auf 4 Uhr): Sonntag, 28.3.2027" in text


def test_ohne_zeitumstellung_und_ohne_bekannte_regel():
    titel, text, ganz = kalender_dach.quelle("When do the clocks change in Japan?", HEUTE)
    assert ganz and "keine Zeitumstellung" in text
    assert "seit Oktober 2022" in kalender_dach.quelle("Does Mexico change the clocks? When?", HEUTE)[1]
    assert kalender_tage.zeitumstellung_welt("Wann ist die Zeitumstellung in Ägypten?", HEUTE) is None
    assert kalender_tage.zeitumstellung_welt("Was kann man zur Sommerzeit in Japan machen?", HEUTE) is None
    assert kalender_tage.zeitumstellung_welt("Is Japan nice in summertime?", HEUTE) is None


def test_ein_genanntes_jahr_ist_keine_frage_nach_dem_naechsten_termin():
    import nachschauen
    assert nachschauen.richtung("Wann ist Thanksgiving in Kanada dieses Jahr?") == ""
    assert nachschauen.richtung("Wann ist heuer Thanksgiving in Kanada?") == ""
    assert nachschauen.richtung("Wann ist Ostern 2026?") == ""
    assert nachschauen.richtung("Wann ist Ostern?") == "naechst"
    assert nachschauen.richtung("Wann ist nächstes Jahr Ostern?") == "naechst"
    assert nachschauen.richtung("Wann spielt Rapid als Nächstes?") == "naechst"


def test_deutsche_frage_zum_dach_raum_bleibt_beim_kalender_des_kirchenjahrs():
    assert kalender_tage.zeitumstellung_welt("Wann ist die Zeitumstellung 2026?", HEUTE) is None
    _t, text, _g = kalender_dach.quelle("Wann ist die Zeitumstellung 2026?", HEUTE)
    assert "Zeitumstellung auf Winterzeit (Uhr um 3 Uhr eine Stunde zurück): Sonntag, 25.10.2026" in text
