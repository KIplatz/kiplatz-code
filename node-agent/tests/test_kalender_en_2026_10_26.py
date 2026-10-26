# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kalender_dach
import kalender_en
import pruefung
import region

_DEUTSCH = re.compile(r"[äöüÄÖÜß]|\b(?:der|die|das|und|nur|ist|im|in den|gesetzlich\w*|Feiertag\w*|Kanton\b|Uhr|vom|bis|für|Für|heute|nächsten|"
                      r"Termine|Kalender\b|Programm\b|bundesweit|Gemeinden|Jahr\b|gibt|Sonntag|Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|"
                      r"Jänner|Februar|März|Mai|Juni|Juli|Oktober|Dezember)\b")
_ERLAUBT = re.compile(r"Baden-Württemberg|Labour Day \(Staatsfeiertag\)")

FRAGEN = ["Ist der 8. Dezember ein Feiertag?", "Ist der 24. Dezember in Österreich ein gesetzlicher Feiertag?", "Feiertage 2027",
          "Wie viele Feiertage hat Österreich?", "Wann ist Ostern 2027?", "Wann beginnt der Advent?", "Wann ist die Zeitumstellung?",
          "Herbstferien Österreich", "Wann ist Fasching?", "Wann ist Muttertag?", "Ist der 1. November ein Feiertag?", "Feiertage 2028",
          "Wann ist Allerheiligen?", "Ist der 31. Oktober ein Feiertag?", "Ist Fronleichnam ein Feiertag?", "Ist der 6. Jänner ein Feiertag?"]
GEBIETE = [""] + sorted({n for land, _k, n, _m in region.GEBIETE}) + ["Deutschland", "Schweiz"]


def _texte():
    for heute in (date(2026, 10, 26), date(2027, 3, 1), date(2027, 12, 20)):
        for gebiet in GEBIETE:
            for frage in FRAGEN:
                f = frage if not gebiet else frage.rstrip("?") + f" in {gebiet}?"
                k = kalender_dach.quelle(f, heute)
                if k:
                    yield f, k[0], k[1]


def test_kein_deutsches_wort_bleibt():
    rest = []
    n = 0
    for f, titel, text in _texte():
        n += 1
        for z in (titel, *text.split("\n")):
            en = _ERLAUBT.sub("", kalender_en.zeile(z))
            if _DEUTSCH.search(en):
                rest.append((f, z, kalender_en.zeile(z)))
    assert n > 300
    assert not rest, "\n".join(f"{f} | {z} → {e}" for f, z, e in rest[:15])


def test_die_probe_wird_gruen():
    k = kalender_dach.quelle("Ist der 1. November in Bayern ein Feiertag?", date(2026, 10, 26))
    try:
        pruefung.sprache_setzen(True)
        pr = pruefung.pruefen("Yes, November 1 (All Saints' Day) is a public holiday in Bavaria.", [(1, kalender_en.text(k[1]))])
    finally:
        pruefung.sprache_setzen(False)
    assert pr.gruen == 1, pr.text


@pytest.mark.parametrize("frage, antwort, bleibt", [
    ("Is December 8 a public holiday in Austria?", "Yes, 8 December is a public holiday in Austria (Immaculate Conception).", True),
    ("Is December 8 a public holiday in Austria?", "No, 8 December is not a public holiday in Austria.", False),
    ("Is 24 December a public holiday in Austria?", "No, 24 December is not a public holiday in Austria.", True),
    ("Is 24 December a public holiday in Austria?", "Yes, 24 December is a public holiday in Austria.", False),
    ("How many public holidays does Austria have a year?", "Austria has 13 public holidays a year.", True),
    ("How many public holidays does Austria have a year?", "Austria has 15 public holidays a year.", False),
    ("Is November 1 a public holiday in Bavaria?", "Yes, November 1 (All Saints' Day) is a public holiday in Bavaria.", True),
    ("Is November 1 a public holiday in Bavaria?", "No, November 1 is not a public holiday in Bavaria.", False),
])
def test_englisch_wie_deutsch_richtig_bleibt_falsch_faellt(frage, antwort, bleibt):
    import app_web
    heute = date(2026, 10, 26)
    k = kalender_dach.quelle(frage, heute)
    t = kalender_en.text(k[1])
    try:
        pruefung.sprache_setzen(True)
        neu = app_web.belege_anwenden(antwort, frage, "Source 1: " + t, [{"nummer": 1, "art": "berechnet", "text": t, "titel": "", "adresse": ""}],
                                      heute=heute)[0]
    finally:
        pruefung.sprache_setzen(False)
    assert (neu == antwort) is bleibt, neu


def test_die_uhrzeit_belegt_keine_anzahl():
    import belege
    werte = belege.zahlenwerte("Heute ist Montag, der 26.10.2026, es ist 17:15 Uhr. Geöffnet 9:00 bis 18:30.")
    assert belege.unbelegte_zahlen(belege._ohne_daten("Austria has 15 public holidays."), werte) == ["15"]
    assert belege.unbelegte_zahlen(belege._ohne_daten("Open from 9:00 to 18:30, it is 17:15 now."), werte) == []


@pytest.mark.parametrize("de, en", [
    ("– Allerheiligen: Sonntag, 1.11.2026, nur in Baden-Württemberg, Bayern", "– All Saints' Day: Sunday, 1 November 2026, only in Baden-Württemberg, Bavaria"),
    ("Der 8. Dezember 2026 (Dienstag) ist in Österreich ein gesetzlicher Feiertag: Mariä Empfängnis.",
     "8 December 2026 (Tuesday) is a public holiday in Austria: Immaculate Conception."),
    ("Der 24. Dezember 2026 (Donnerstag) ist in Österreich kein gesetzlicher Feiertag.", "24 December 2026 (Thursday) is not a public holiday in Austria."),
])
def test_saetze(de, en):
    assert kalender_en.zeile(de) == en
