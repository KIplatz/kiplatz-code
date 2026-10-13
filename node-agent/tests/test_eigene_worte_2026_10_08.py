# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege
import ki_laufzeit
import wissen

HEUTE = date(2026, 10, 8)
SEITE = ("Rockstar Games hat bestätigt, dass Grand Theft Auto VI am 26. Mai 2026 für PlayStation 5 und Xbox Series X erscheint. "
         "Eine Fassung für den PC wurde bisher nicht angekündigt.")
FREMD = [{"nummer": 1, "art": "nachgeschaut", "titel": "Spieleseite", "text": SEITE}]
FRAGE = "Wann erscheint GTA VI?"
KOPIE = "Rockstar Games hat bestätigt, dass Grand Theft Auto VI am 26. Mai 2026 für PlayStation 5 und Xbox Series X erscheint (Quelle 1)."
EIGEN = "GTA VI kommt am 26. Mai 2026 heraus, zuerst nur für PlayStation 5 und Xbox Series X (Quelle 1)."


def test_ten_words_in_a_row_are_found_also_across_a_sentence_end():
    assert belege.woertliche_saetze(KOPIE, [SEITE]) == [KOPIE]
    assert belege.woertliche_saetze(EIGEN, [SEITE]) == []
    quer = "Das Spiel ist am 26. Mai 2026 für PlayStation 5 da. Und Xbox Series X erscheint auch."
    assert belege.woertliche_saetze(quer, ["am 26 mai 2026 für playstation 5 und xbox series x erscheint"]) == []
    zwei = "Eine Fassung für den PC wurde. Bisher nicht angekündigt, sagt die Seite."
    assert len(belege.woertliche_saetze(zwei, ["eine fassung für den pc wurde bisher nicht angekündigt sagt die seite"])) == 2


def test_licensed_sources_and_own_files_keep_their_wording_wikipedia_does_not():
    for art in ("seite", "ortswissen", "berichtigung", "dokument", "pass"):
        assert belege.fremde_texte([{"art": art, "text": SEITE}]) == []
    assert belege.fremde_texte(FREMD) == [SEITE]
    assert belege.fremde_texte([{"art": "wikipedia", "text": SEITE}]) == [SEITE]


def test_numbers_are_facts_and_do_not_count_as_copied_words():
    quelle = "Klagenfurt hat laut Statistik Austria am 1. Jänner 2025 genau 105.734 Einwohner."
    antwort = "Laut Statistik Austria hat Klagenfurt am 1. Jänner 2025 genau 105.734 Einwohner."
    assert belege.woertliche_saetze(antwort, [quelle]) == []
    lang = "In der Statistik steht, Klagenfurt hat laut Statistik Austria am 1. Jänner 2025 genau 105.734 Einwohner gehabt."
    assert belege.woertliche_saetze(lang, [quelle]) == []


def test_a_neighbour_sentence_is_kept_when_only_one_word_touches_the_copy():
    quelle = "eine fassung für den pc wurde bisher von rockstar nicht angekündigt sagt"
    antwort = "Eine Fassung für den PC wurde bisher von Rockstar nicht angekündigt. Sagt mir, ob ihr mehr wissen wollt."
    assert belege.woertliche_saetze(antwort, [quelle]) == ["Eine Fassung für den PC wurde bisher von Rockstar nicht angekündigt."]


def test_a_copied_answer_is_rewritten_in_own_words_before_anyone_sees_it():
    auftraege = []

    def nochmal(extra):
        auftraege.append(extra)
        return EIGEN
    t, notizen = app_web.belege_anwenden(KOPIE, FRAGE, "Quelle 1: " + SEITE, FREMD, heute=HEUTE, nochmal=nochmal)
    assert t == EIGEN and len(auftraege) == 1 and "eigenen Worten" in auftraege[0]
    assert any("eigenen Worten" in n for n in notizen)


def test_an_answer_in_own_words_costs_no_extra_round():
    def nochmal(extra):
        raise AssertionError("kein zweiter Durchgang ohne Fund")
    t, notizen = app_web.belege_anwenden(EIGEN, FRAGE, "Quelle 1: " + SEITE, FREMD, heute=HEUTE, nochmal=nochmal)
    assert t == EIGEN and not any("wörtlich" in n or "eigenen Worten" in n for n in notizen)


def test_a_rewrite_that_still_copies_or_loses_the_date_is_not_taken():
    for schlecht in (KOPIE, "GTA VI erscheint bald für PlayStation 5 und Xbox Series X (Quelle 1)."):
        zweiter = "Für den PC gibt es noch keine Fassung (Quelle 1)."
        t, notizen = app_web.belege_anwenden(KOPIE + " " + zweiter, FRAGE, "Quelle 1: " + SEITE, FREMD, heute=HEUTE, nochmal=lambda _e, s=schlecht: s)
        assert t == zweiter and any("gestrichen" in n for n in notizen)


def test_a_cut_off_or_much_shorter_rewrite_is_not_taken():
    erklaerung = KOPIE + " Für den PC gibt es noch keine Fassung, und einen genauen Termin dafür hat Rockstar Games bisher nicht genannt (Quelle 1)."
    for schlecht in ("GTA VI kommt am 26. Mai 2026 heraus, zuerst nur für PlayStation 5 und", "GTA VI kommt am 26. Mai 2026 (Quelle 1)."):
        t, _ = app_web.belege_anwenden(erklaerung, FRAGE, "Quelle 1: " + SEITE, FREMD, heute=HEUTE, nochmal=lambda _e, s=schlecht: s)
        assert t != schlecht and KOPIE not in t


def test_the_fixed_rule_is_in_every_instruction():
    assert "eigenen Worten" in ki_laufzeit.SYSTEMTEXT and "nie ganze Sätze" in ki_laufzeit.SYSTEMTEXT
    assert "eigenen Worten" in ki_laufzeit.SYSTEMTEXT_KURZ
    text, _q = wissen.kontext_bauen([wissen.Treffer(wissen.Quelle("x", "nachgeschaut", "Seite", "https://example.org", "2026-10-08", 10), SEITE, 1.0)])
    assert "in eigenen Worten" in text and "gib sie daraus wieder" not in text
