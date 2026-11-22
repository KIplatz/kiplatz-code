# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege
import wissen


def test_a33_bereich_zeile():
    assert wissen.bereich_zahl("Wie hoch ist das große Pendlerpauschale bei 30 km?") == (30.0, "km")
    zeile = " bei mehr als 20 km bis 40 km (Das große Pendlerpauschale steht zu, Betrag/Monat): 123,00 Euro"
    assert wissen.bereich_zeile(zeile, 30, "km") == zeile.strip()
    assert wissen.bereich_zeile(" bei mindestens 2 km bis 20 km: 31 Euro", 30, "km") == ""
    assert wissen.bereich_zeile(" von 20 bis 40 Jahren: 5 Euro", 30, "km") == ""
    assert wissen.bereich_zahl("Wie hoch ist die Pendlerpauschale?") is None


def test_a33_stelle_mit_bereich_kommt_nach_vorne():
    p = wissen.bereich_punkte("Wie viel bekommt man bei 30 km?")
    assert p("bei mehr als 20 km bis 40 km: 123 Euro") == 1.0 and p("Allgemeines zur Pendlerpauschale") == 0.0
    assert wissen.bereich_punkte("Was ist die Pendlerpauschale?") is None


def test_a33_fokus_nennt_die_zahl():
    f = app_web.frage_fokus("Wie hoch ist das große Pendlerpauschale bei 30 km?")
    assert "Die Frage nennt 30 km" in f


def test_a33_zeitraum_bleibt_im_zusatz():
    html = ("<p>Steht das große Pendlerpauschale zu, sind im Zeitraum Mai 2022 bis Juni 2023 zusätzlich folgende Beträge zu berücksichtigen.</p>"
            "<table><tr><th>Entfernung</th><th>mehr als 10 Tage</th><th>8-10 Tage</th></tr>"
            "<tr><td>bei mehr als 20 km bis 40 km</td><td>61,50 Euro</td><td>41,00 Euro</td></tr></table>")
    assert "(Steht das große Pendlerpauschale zu, Mai 2022 bis Juni 2023, mehr als 10 Tage): 61,50 Euro" in wissen.html_zu_text(html)[1]


def test_a34_tabellenname_bei_zahlenfragen():
    assert "Tabelle und Spalte" in app_web.frage_fokus("Wie hoch ist die Pendlerpauschale in Österreich?")
    assert "table and column" in app_web.frage_fokus("How much is the TV licence fee in the UK?")
    assert "Tabelle und Spalte" not in app_web.frage_fokus("Wer hat das Penicillin entdeckt?")


LOUVRE = ("The Louvre is closed today.\n\nOn other days, it opens at 9:00 and closes at 18:00 on Monday, Thursday, Saturday, and Sunday.\n"
          "On Wednesday and Friday, it stays open until 21:00.")


@pytest.mark.parametrize("wochentag,weg", [(6, ["The Louvre is closed today."]), (1, [])])
def test_a35_heute_geschlossen_widerspricht(wochentag, weg):
    assert belege.heute_widerspruch(LOUVRE, wochentag) == weg


def test_a35_gegenproben():
    assert belege.heute_widerspruch("Heute ist der Billa geschlossen. Am Sonntag hat er zu.", 6) == []
    assert belege.heute_widerspruch("Der Billa hat heute geöffnet. Sonntag: geschlossen.", 6) == ["Der Billa hat heute geöffnet."]
    assert belege.heute_widerspruch("Heute, Sonntag, ist geschlossen. Montag 8:00 bis 18:00.", 6) == []


def test_a35_grund_anderes_geschaeft_und_keine_uhrzeit():
    assert belege.heute_widerspruch("The Louvre is closed today (Christmas Day). Normally it is open Thursday 9:00–18:00.", 3) == []
    assert belege.heute_widerspruch("Billa hat heute geschlossen. Der Spar am Bahnhof hat am Sonntag von 8:00 bis 20:00 offen.", 6) == []
    assert belege.heute_widerspruch("Heute ist geschlossen. Kinder bis 14 am Sonntag gratis.", 6) == []
    assert belege.heute_widerspruch("Täglich geöffnet außer an Feiertagen, auch am Sonntag. Heute ist es geöffnet.", 6) == []


def test_a35_altes_uhrzeit_muster_bleibt():
    assert belege._UHRZEIT.groups == 2


@pytest.mark.parametrize("frage,soll", [("bei 30.000 km", (30000.0, "km")), ("bei 2000 €", (2000.0, "geld")), ("bei 20 %", (20.0, "prozent"))])
def test_a33_tausender_euro_prozent(frage, soll):
    assert wissen.bereich_zahl(frage) == soll


@pytest.mark.parametrize("zahl,zeile,passt", [
    (20, " bei mehr als 20 km bis 40 km: 123", False),
    (30, " bei mehr als 20 km bis 40 km: 123", True),
    (20, " bei mindestens 2 km bis 20 km: 31", True),
    (80, " bei mehr als 60 km: 168", True),
    (60, " bei mehr als 60 km: 168", False),
])
def test_a33_grenzen_und_offene_stufen(zahl, zeile, passt):
    assert bool(wissen.bereich_zeile(zeile, zahl, "km")) is passt


def test_a33_euro_stufen_mit_tausenderpunkt():
    assert wissen.bereich_zeile(" über 12.816 bis 20.818 Euro: 20 %", 15000, "geld")


def test_a33_fokus_nur_bei_zahlenfragen():
    assert "Die Frage nennt" not in app_web.frage_fokus("Was kann man für 50 Euro schenken?")


def test_a33_jahr_ohne_gueltigkeitswort_kommt_nicht_mit():
    tab = ("<table><tr><th>Entfernung</th><th>Monat</th><th>Jahr</th></tr>"
           "<tr><td>bei mehr als 20 km bis 40 km</td><td>58 Euro</td><td>696 Euro</td></tr></table>")
    assert "(Pendlerpauschale, Monat): 58 Euro" in wissen.html_zu_text("<p>Pendlerpauschale, laut Budgetbegleitgesetz 2025 neu berechnet.</p>" + tab)[1]
    assert "(Pendlerpauschale, ab 2026, Monat): 58 Euro" in wissen.html_zu_text("<p>Pendlerpauschale, ab 2026 gelten:</p>" + tab)[1]


def test_a35_deutsch_und_englisch_mit_hauptwoertern():
    assert belege.heute_widerspruch("Der Billa hat heute geschlossen. Die Öffnungszeiten am Sonntag sind 9:00 bis 12:00 Uhr.", 6) \
        == ["Der Billa hat heute geschlossen."]
    assert belege.heute_widerspruch("The museum is closed today. Opening hours on Sunday are 9:00–18:00.", 6) == ["The museum is closed today."]
    assert belege.heute_widerspruch("Billa hat heute geschlossen. Der Spar am Bahnhof hat am Sonntag von 8:00 bis 20:00 offen.", 6) == []
    assert belege.heute_widerspruch("Heute zu Mittag ist geöffnet. Sonntag 11:00–14:00.", 6) == []


def test_a33_zwischen_und_aber_keine_aufzaehlung():
    assert wissen.bereich_zeile(" zwischen 20 und 40 km: 5 Euro", 30, "km")
    assert not wissen.bereich_zeile(" Filialen in 5 und 30 km Entfernung", 10, "km")


def test_a33_punkte_nur_bei_zahlenfragen():
    assert wissen.bereich_punkte("Rezept für 4 Personen") is None
    assert wissen.bereich_punkte("Wie hoch ist die Pendlerpauschale bei 30 km?") is not None


def test_a35_nachmessung_am_pm():
    a = ("The Louvre is closed today. Normally, it opens from 9:00 AM to 6:00 PM on Sundays, except it stays open until 9:00 PM on Wednesdays "
         "and Fridays. Entry closes one hour before closing time.")
    assert belege.heute_widerspruch(a, 6) == ["The Louvre is closed today."]


def test_a35_namen_mit_zwei_zeichen_bleiben_gegenstand():
    assert belege.heute_widerspruch("A1 hat heute geschlossen. Der Magenta-Shop hat am Sonntag von 9:00 bis 18:00 offen.", 6) == []
