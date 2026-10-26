# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app_web
import ki_laufzeit
import pruefung


@pytest.mark.parametrize("frage", [
    "Who was Mozart?",
    "How many people live in Tokyo?",
    "Do I need a visa to visit Japan as a British citizen?",
    "What is the capital of Australia?",
    "How do I make a French omelette?",
    "Should I tip in the United States?",
    "What is the speed limit on Italian motorways?",
    "When is the best time to visit Barcelona?",
    "How does a heat pump work?",
])
def test_englisch_gefragt_ohne_ort_im_deutschen_sprachraum_geht_direkt(frage):
    assert app_web.englisch_direkt(frage)
    assert ki_laufzeit.original() == ""


@pytest.mark.parametrize("frage", [
    "What is the speed limit on motorways in Austria?",
    "Do I need a vignette in Switzerland?",
    "Which pharmacies are open in Linz today?",
    "How much is a train ticket from Munich to Berlin?",
    "What are the opening hours of shops in Wien on Sunday?",
])
def test_eine_frage_zum_deutschen_sprachraum_geht_seit_3a3_auch_direkt(frage):
    assert app_web.englisch_direkt(frage)


@pytest.mark.parametrize("frage", ["Who was Mozart?", "What is the speed limit on motorways in Austria?", "Which pharmacies are open in Linz today?",
                                   "Shops in Vienna on Sunday?", "How do I make a French omelette?"])
def test_direkt_genau_dann_wenn_die_suche_englisch_laeuft(frage):
    ki_laufzeit.original_setzen(frage)
    try:
        sucht_englisch = app_web.such_sprache(frage) == "en"
    finally:
        ki_laufzeit.original_setzen("")
    assert app_web.englisch_direkt(frage) is sucht_englisch


def test_ein_deutscher_text_des_programms_wird_noch_uebersetzt():
    assert app_web.noch_deutsch("Für welchen Ort möchtest du das Wetter wissen?")
    assert not app_web.noch_deutsch("Mozart was a composer from Salzburg who lived from 1756 to 1791.")


def test_englische_regeln_nur_wenn_die_antwort_englisch_entsteht(tmp_path):
    from test_zwischenspeicher import _server
    s, _p, gesehen = _server(tmp_path)
    try:
        pruefung.sprache_setzen(True)
        ki_laufzeit.original_setzen("Who was Mozart?")
        s.frage([{"role": "user", "content": "Who was Mozart?"}])
        s.frage([{"role": "user", "content": "Who was Mozart?"}], kurz=True)
        s.frage([{"role": "user", "content": "1| x"}], system="Übersetze.")
        pruefung.sprache_setzen(False)
        s.frage([{"role": "user", "content": "Wer war Mozart?"}])
    finally:
        pruefung.sprache_setzen(False)
        ki_laufzeit.original_setzen("")
        s.stop()
    lang, kurz, hilfe, deutsch = (g["messages"][0]["content"] for g in gesehen)
    assert lang.startswith(ki_laufzeit.SYSTEMTEXT_EN) and "Antworte" not in lang and "Die Person hat auf Englisch gefragt" not in lang
    assert kurz.startswith(ki_laufzeit.SYSTEMTEXT_KURZ_EN)
    assert hilfe.startswith("Übersetze.")
    assert deutsch.startswith(ki_laufzeit.SYSTEMTEXT) and "Antworte trotzdem auf Deutsch" in deutsch


def test_die_englischen_regeln_sind_die_deutschen():
    lang, kurz = ki_laufzeit.SYSTEMTEXT_EN, ki_laufzeit.SYSTEMTEXT_KURZ_EN
    assert len(kurz) < 1300 < len(lang)
    for regel in ("never make anything up", "own words", "I don't know that yet.", "That doesn't belong in this community.", "no emojis",
                  "open to everyone"):
        assert regel.lower() in lang.lower(), regel
    for regel in ("make anything up", "own words", "I don't know that yet.", "That doesn't belong in this community.", "open to everyone"):
        assert regel.lower() in kurz.lower(), regel
    assert app_web._WEISS_NICHT.search("I don't know that yet.")
    for t in (lang, kurz):
        assert not any(w in t for w in ("ä", "ö", "ü", "ß", "Antworte", "Österreichisch"))


def test_beide_eingaenge_fragen_englisch_direkt_und_geben_es_an_den_kern():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert quelle.count("englisch_direkt(") == 3
    assert "englisch=direkt)" in quelle and "messen=messen, englisch=direkt)" in quelle


def test_der_feste_quelltitel_steht_unter_einer_englischen_antwort_englisch():
    ls = {"quellen_liste": [{"nummer": 1, "titel": "Suchergebnisse", "adresse": "https://en.wikipedia.org/"},
                            {"nummer": 2, "titel": "Mount Kilimanjaro Height", "adresse": "https://mountkilimanjaro.guide/"}], "quellen": "x"}
    neu = app_web.quellen_titel_englisch(ls)
    assert [q["titel"] for q in neu["quellen_liste"]] == ["Search results", "Mount Kilimanjaro Height"] and neu["quellen"] == "x"
    assert ls["quellen_liste"][0]["titel"] == "Suchergebnisse"
    assert app_web.quellen_titel_englisch({"quellen": "ohne Liste"}) == {"quellen": "ohne Liste"}
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert quelle.count("quellen_titel_englisch(") == 3


@pytest.mark.parametrize("frage", ["Translate 'I come from Austria' into German.", "How do you say 'good morning' in Austrian German?",
                                   "What is the German word for Christmas market in Vienna?"])
def test_fragen_nach_deutschen_woertern_gehen_direkt_auch_mit_ort_im_deutschen_sprachraum(frage):
    assert app_web.englisch_direkt(frage)
    assert "German words or a translation into German" in ki_laufzeit.SYSTEMTEXT_EN and "German words asked for stay German" in ki_laufzeit.SYSTEMTEXT_KURZ_EN


def test_eine_deutsche_antwort_auf_eine_frage_nach_deutschen_woertern_bleibt_deutsch():
    assert not app_web.noch_deutsch("Auf Deutsch heißt das: „Ich komme aus Österreich.“", "Translate 'I come from Austria' into German.")
    assert app_web.noch_deutsch("Für welchen Ort möchtest du das Wetter wissen?", "What's the weather like?")


def test_die_englische_suche_aus_zaehlt_im_pruefstand():
    import pruefstand
    assert pruefstand.suche_aus(app_web._NICHT_ERREICHT_SATZ_EN) and pruefstand.suche_aus(app_web._NICHT_ERREICHT_SATZ)
