# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import antwortsprache
import app_web
import belege


def _uebersetzer(antwort: str):
    gesehen: list[list[dict]] = []

    def frage_fn(nachrichten, *, system="", max_tokens=0, on_token=None, **_):
        gesehen.append(list(nachrichten))
        return SimpleNamespace(text=antwort)
    return frage_fn, gesehen


def test_the_question_translation_is_shown_by_example_first():
    fn, gesehen = _uebersetzer("1| Wie hoch ist die Höchstgeschwindigkeit auf Autobahnen in Österreich?")
    neu = antwortsprache.frage_auf_deutsch(fn, [{"role": "user", "content": "What is the speed limit on motorways in Austria?"}])
    assert neu[-1]["content"] == "Wie hoch ist die Höchstgeschwindigkeit auf Autobahnen in Österreich?"
    gesendet = gesehen[0]
    assert gesendet[:-1] == antwortsprache.BEISPIEL_FRAGE and gesendet[-1]["content"].startswith("1| What is the speed limit")
    vor, nach = antwortsprache.BEISPIEL_FRAGE[0]["content"], antwortsprache.BEISPIEL_FRAGE[1]["content"]
    assert vor.count("\n") == nach.count("\n") and "Gib mir" in nach and "Brauche ich" in nach and "**" not in nach
    assert "Austria" not in vor and "Kaiserschmarrn" not in vor


def test_the_answer_direction_has_no_example():
    fn, gesehen = _uebersetzer("1| Use vinegar.")
    antwortsprache.antwort_uebersetzen(fn, "Nimm Essig.", {}, frage="How do I descale a kettle?")
    assert len(gesehen[0]) == 1


def test_bold_never_reaches_the_german_chain_or_the_english_window():
    fn, _ = _uebersetzer("1| Was ist der **Krampus**?")
    assert antwortsprache.frage_auf_deutsch(fn, [{"role": "user", "content": "What is Krampus?"}])[-1]["content"] == "Was ist der Krampus?"
    fn, _ = _uebersetzer("1| Mould can *increase* in damp rooms.")
    text, _ls = antwortsprache.antwort_uebersetzen(fn, "Schimmel kann in feuchten Räumen zunehmen.", {})
    assert text == "Mould can increase in damp rooms."
    fn, _ = _uebersetzer("1| Was heißt 5 * 3?")
    assert antwortsprache.frage_auf_deutsch(fn, [{"role": "user", "content": "What is 5 * 3?"}])[-1]["content"] == "Was heißt 5 * 3?"


REZEPT = """So machst du Kaiserschmarrn:

– Trenne 4 Eier und schlag das Eiklar steif. Misch 3 EL Zucker unter.
– Verrühre die Dotter mit 250 ml Milch und 150 g Mehl.
– Heb den Eischnee vorsichtig unter.
– Reiß ihn mit zwei Gabeln in Stücke und bestreu ihn mit Staubzucker, dazu passt Zwetschkenröster."""
FERNSEHEN = ("In der Weihnachts-Edition kochte Tim Mälzer gegen Max Strohe. Als Nachspeise gab es Kaiserschmarrn: er reißt ihn mit zwei Gabeln "
             "in Stücke, bestreut ihn mit Staubzucker, dazu passt Zwetschkenröster. Die Sendung lief im Dezember.")


def _anwenden(antwort, frage, quelle):
    return app_web.belege_anwenden(antwort, frage, quelle, [{"nummer": 1, "titel": "Wikipedia: Kitchen Impossible", "text": quelle, "art": "wikipedia"}])


def test_everyday_measures_stay_beside_a_source_that_says_nothing_about_them():
    import pruefung
    assert any(x.farbe == "gruen" for x in pruefung.pruefen(REZEPT, [(1, FERNSEHEN)]).saetze)
    text, notizen = _anwenden(REZEPT, "Gib mir ein einfaches Rezept für Kaiserschmarrn.", FERNSEHEN)
    assert "250 ml Milch und 150 g Mehl" in text and not notizen


def test_a_number_question_or_a_contradicting_source_still_strikes():
    text, notizen = _anwenden(REZEPT, "Wie viel Milch braucht man für Kaiserschmarrn?", FERNSEHEN)
    assert "250 ml" not in text and notizen
    text, _ = _anwenden(REZEPT, "Gib mir ein einfaches Rezept für Kaiserschmarrn.", FERNSEHEN + " Dafür nahm er 500 ml Milch.")
    assert "250 ml" not in text
    t2 = REZEPT + "\n\nDas Rezept stammt aus dem Jahr 1854."
    text, _ = _anwenden(t2, "Gib mir ein einfaches Rezept für Kaiserschmarrn.", FERNSEHEN)
    assert "1854" not in text


def test_the_rest_of_a_list_item_keeps_its_dash_and_number():
    t = "So geht es:\n\n– Trenne die Eier. Misch den Zucker unter.\n– Verrühre die Dotter.\n1. Erster Satz. Zweiter Satz.\n2. Dritter Satz."
    rest, raus = belege.saetze_streichen(t, lambda s: s.startswith(("– Trenne", "1. Erster")))
    assert rest == "So geht es:\n\n– Misch den Zucker unter.\n– Verrühre die Dotter.\n1. Zweiter Satz.\n2. Dritter Satz."
    assert len(raus) == 2
    rest, _ = belege.saetze_streichen("1. Schalte das Gerät aus.\n2. Zieh den Stecker.\n3. Warte zehn Minuten.", lambda s: s.startswith("2."))
    assert rest == "1. Schalte das Gerät aus.\n2. Warte zehn Minuten."
    rest, _ = belege.saetze_streichen("Satz eins. Satz zwei.", lambda s: s == "Satz eins.")
    assert rest == "Satz zwei."


def _kopie(tmp_path, artikel):
    import wikipedia
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    db.teil_aufnehmen(1, artikel)
    return db


def test_a_thing_named_after_its_town_is_found(tmp_path):
    db = _kopie(tmp_path, [
        {"id": 1, "titel": "Riesenrad", "beliebt": 0.01, "geaendert": "", "umleitungen": [],
         "teile": ["Ein Riesenrad ist ein Fahrgeschäft. Das erste baute George Ferris 1893 in Chicago."]},
        {"id": 2, "titel": "Wiener Riesenrad", "beliebt": 0.01, "geaendert": "", "umleitungen": [],
         "teile": ["Das Wiener Riesenrad im Prater wurde 1897 nach Plänen von Walter Basset errichtet."]},
        {"id": 3, "titel": "Wien", "beliebt": 0.02, "geaendert": "", "umleitungen": [], "teile": ["Wien ist die Hauptstadt Österreichs."]},
        {"id": 4, "titel": "Kölner Dom", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": ["Der Kölner Dom ist eine Kathedrale."]},
        {"id": 5, "titel": "Dom", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": ["Ein Dom ist eine große Kirche."]},
        {"id": 6, "titel": "Köln", "beliebt": 0.02, "geaendert": "", "umleitungen": [], "teile": ["Köln liegt am Rhein."]},
        {"id": 7, "titel": "Inn", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": ["Der Inn ist ein Fluss."]},
        {"id": 8, "titel": "Österreich", "beliebt": 0.02, "geaendert": "", "umleitungen": [], "teile": ["Österreich ist ein Staat."]},
    ])
    ids = db.titel_artikel("Wer hat das Riesenrad in Wien gebaut?")
    assert ids[0] == 2 and 1 not in ids and 3 in ids
    assert db.titel_artikel("Wann wurde der Dom in Köln gebaut?")[0] == 4
    assert db.titel_artikel("Wie lang ist der Inn in Österreich?") == [7, 8]
    assert db.titel_artikel("Wie hoch ist das Wiener Riesenrad?")[0] == 2
    assert db.titel_artikel("Was ist ein Riesenrad?") == [1]


def test_town_adjectives():
    import wikipedia
    assert wikipedia._ortsadjektive("Wien") == ["Wiener"]
    assert "Münchner" in wikipedia._ortsadjektive("München") and "Bremer" in wikipedia._ortsadjektive("Bremen")
    assert "Haller" in wikipedia._ortsadjektive("Halle") and wikipedia._ortsadjektive("Graz") == ["Grazer"]


def test_a_note_in_the_calendar_belongs_only_to_the_states_it_names():
    import kalender_dach
    bayern = kalender_dach.quelle("Welche gesetzlichen Feiertage gibt es in Bayern im Jahr 2027?")[1]
    fron = next(z for z in bayern.splitlines() if "Fronleichnam" in z)
    assert fron == "– Fronleichnam: Donnerstag, 27.5.2027"
    assert "(in Bayern nur in Gemeinden mit überwiegend katholischer Bevölkerung)" in bayern
    sachsen = kalender_dach.quelle("Welche Feiertage gibt es 2027 in Sachsen?")[1]
    assert "– Fronleichnam: Donnerstag, 27.5.2027 (in Sachsen und Thüringen nur in einzelnen Gemeinden)" in sachsen
    assert "Mariä" not in sachsen
    de = kalender_dach.quelle("Welche Feiertage gibt es 2027 in Deutschland?")[1]
    assert "(in Sachsen und Thüringen nur in einzelnen Gemeinden)" in de and "(in Bayern nur in Gemeinden mit überwiegend" in de


def test_a_list_in_the_words_of_the_own_calendar_is_no_copy():
    zeile = "– Mariä Himmelfahrt: Sonntag, 15.8.2027 (in Bayern nur in Gemeinden mit überwiegend katholischer Bevölkerung)"
    antwort = "In Bayern gibt es 2027 diese Feiertage:\n\n– Neujahr: Freitag, 1.1.2027\n" + zeile
    kalender = "Gesetzliche Feiertage in Bayern (Deutschland), vom Programm aus dem Kalender berechnet:\n– Neujahr: Freitag, 1.1.2027\n" + zeile
    for art in ("berechnet", "abgefragt"):
        text, notizen = app_web._eigene_worte(antwort, "Welche Feiertage gibt es 2027 in Bayern?", [{"nummer": 1, "art": art, "text": kalender}], None, date(2026, 10, 18))
        assert text == antwort and not notizen, art
    text, notizen = app_web._eigene_worte(antwort, "Welche Feiertage gibt es 2027 in Bayern?", [{"nummer": 1, "art": "wikipedia", "text": kalender}], None, date(2026, 10, 18))
    assert "Mariä" not in text and notizen
