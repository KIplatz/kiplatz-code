# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pruefstand
import selbstauskunft
import sicher_schreiben

START = {f: (e, list(p)) for f, e, p, _q in pruefstand.START_FRAGEN}

RICHTIG_ABER_ANDERS = {
    "Was kostet KIplatz?": "KIplatz kostet nichts. Das Programm, die Antworten und die Community sind kostenlos, es gibt keine Bezahlstufe und keine kaufbaren Credits.",
    "Wie hoch ist das Allalinhorn?": "Das Allalinhorn ist 4027 Meter hoch.",
    "Wann fand die Armory Show statt?": "Die Armory Show fand erstmals vom 17. Februar bis 9. März 1913 in New York statt.",
    "Was ist Alizarin?": "Alizarin ist eine orangegelbe chemische Verbindung aus der Gruppe der Anthrachinone, aus der Wurzel des Färberkrapps, früher als Farbstoff verwendet.",
    "Was war die Argentinien-Krise?": "Eine schwere Wirtschaftskrise 1998 bis 2002 mit dem Zusammenbruch des Finanzsystems 2001/02.",
    "Was ist 3 mal 9,90 Euro?": "3 × 9,90 € = 29,70 €.",
}


@pytest.mark.parametrize("frage", sorted(RICHTIG_ABER_ANDERS))
def test_a_right_answer_in_other_words_counts(frage):
    erwartet, pflicht = START[frage]
    assert pruefstand.bewerten(RICHTIG_ABER_ANDERS[frage], erwartet, pflicht)[0]


def test_wrong_and_unknown_stay_wrong():
    erwartet, pflicht = START["Wie hoch ist das Allalinhorn?"]
    assert not pruefstand.bewerten("Das Allalinhorn ist 4200 Meter hoch.", erwartet, pflicht)[0]
    assert not pruefstand.bewerten("Das weiß ich nicht sicher, vielleicht 4027 Meter.", erwartet, pflicht)[0]
    assert not pruefstand.bewerten("Das weiß ich noch nicht, und im Internet habe ich dazu gerade nichts Verlässliches gefunden.", "PKW 0,50 €", ["0,50"])[0]
    erwartet, pflicht = START["Was sind Credits bei KIplatz?"]
    assert not pruefstand.bewerten("Es gibt keine Bezahlung damit, nur mehr Einfluss auf die Reihenfolge.", erwartet, pflicht)[0]
    assert not pruefstand.bewerten("Irgendwas ganz anderes.", "Die Donau fließt durch Wien und Linz.", [])[0]
    assert pruefstand.bewerten("Die Donau fließt durch Linz und Wien.", "Die Donau fließt durch Wien und Linz.", [])[0]


@pytest.mark.parametrize("frage", ["Was kostet KIplatz?", "Was sind Credits bei KIplatz?", "Wofür gibt es bei KIplatz eine Platzordnung?"])
def test_the_three_own_questions_get_a_fixed_text_that_passes(frage):
    text = selbstauskunft.antwort(frage)
    erwartet, pflicht = START[frage]
    assert text and pruefstand.bewerten(text, erwartet, pflicht)[0]


def test_the_old_question_on_the_server_is_renamed_once(tmp_path):
    p = pruefstand.Pruefstand(tmp_path)
    fragen = p.fragen()
    for f in fragen:
        if f["frage"] == "Wofür gibt es bei KIplatz eine Platzordnung?":
            f["frage"] = "Wofür gibt es bei KIplatz eine Hausordnung?"
            f["erwartet"] = f["erwartet"].replace("Platzordnung", "Hausordnung")
            alt = f["kennung"]
    sicher_schreiben.json_datei(p.datei, {"fragen": fragen, "berichte": []})
    neu = [f for f in p.fragen() if f["kennung"] == alt][0]
    assert neu["frage"] == "Wofür gibt es bei KIplatz eine Platzordnung?" and "Hausordnung" not in neu["erwartet"]
    assert "Hausordnung" not in p.datei.read_text(encoding="utf-8")
