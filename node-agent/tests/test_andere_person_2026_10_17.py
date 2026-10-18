# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege

RABERGER = "Traueranzeige: Josefine Raberger ist am 6. Oktober 2026 verstorben. Die Beerdigung ist am Wiltener Friedhof in Innsbruck."


def test_the_asked_name_missing_everywhere_means_someone_else():
    antwort = "Josefine Raberger ist am 6. Oktober 2026 verstorben. Sie wurde in Innsbruck beerdigt."
    assert belege.gefragter_name_fehlt("Wer war Josefine Tarsberger?", antwort, [RABERGER]) == "Tarsberger"
    assert belege.gefragter_name_fehlt("Wer war Josefine Raberger?", antwort, [RABERGER]) == ""
    assert belege.gefragter_name_fehlt("Wer war Josefine Tarsberger?", "Josefine Tarsberger war Politikerin.", [RABERGER]) == "Tarsberger"
    assert belege.gefragter_name_fehlt("Was macht Josefine Tarsberger?", antwort, [RABERGER]) == ""
    assert belege.gefragter_name_fehlt("Wer ist Bundeskanzler von Österreich?", "Christian Stocker ist Bundeskanzler.",
                                       ["Bundeskanzler der Republik Österreich ist Christian Stocker."]) == ""
    assert belege.gefragter_name_fehlt("Wer ist das?", "Das ist Anna.", ["Anna"]) == ""
    assert belege.gefragter_name_fehlt("Wer war Kaiserin Adelinde von Österreich?", "Kaiserin Elisabeth von Österreich lebte in Wien.",
                                       ["Elisabeth war Kaiserin von Österreich."]) == "Adelinde"


def test_belege_anwenden_says_it_honestly():
    quellen = [{"nummer": 1, "art": "nachgeschaut", "titel": "Traueranzeige", "adresse": "https://beispiel.at/t", "text": RABERGER}]
    antwort = "Josefine Raberger ist am 6. Oktober 2026 verstorben. Sie wurde am Wiltener Friedhof in Innsbruck beerdigt."
    t, notizen = app_web.belege_anwenden(antwort, "Wer war Josefine Tarsberger?", RABERGER, quellen, heute=date(2026, 10, 17))
    assert t == "Das weiß ich noch nicht." and notizen[-1] == app_web.ANDERE_PERSON
    t2, _ = app_web.belege_anwenden(antwort, "Wer war Josefine Raberger?", RABERGER, quellen, heute=date(2026, 10, 17))
    assert "Raberger" in t2
