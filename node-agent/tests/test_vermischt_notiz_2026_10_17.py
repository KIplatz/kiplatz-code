# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege

QUELLEN = [("Wikipedia: Durgol (CC BY-SA 4.0)", "Durgol ist ein Entkalker aus der Schweiz. Er enthält Amidosulfonsäure."),
           ("Entkalken mit Hausmitteln", "Viele Entkalker enthalten Milchsäure oder Zitronensäure.")]


def test_the_trigger_names_source_and_word_and_vermischt_stays_the_same():
    antwort = "Entkalker wie Durgol enthalten oft Milchsäure. Durgol kommt aus der Schweiz."
    a = belege.vermischt_ausloeser(antwort, QUELLEN)
    assert a == [("Entkalker wie Durgol enthalten oft Milchsäure.", "Durgol", "Milchsäure")]
    assert belege.vermischt(antwort, QUELLEN) == ["Entkalker wie Durgol enthalten oft Milchsäure."]
    assert belege.vermischt_ausloeser("Durgol kommt aus der Schweiz.", QUELLEN) == []


def test_a_topic_word_in_several_sources_is_no_reference_to_one_of_them():
    quellen = [("Nachgeschaut: Bausparvertrag – Wikipedia", "Ein Bausparvertrag ist ein Finanzprodukt, das der Anleger mit einer Bausparkasse abschließt."),
               ("Nachgeschaut: Bausparvertrag erklärt: Definition, Funktionen & Vorteile | LBS.de",
                "Mit einem Bausparvertrag sparen Sie zuerst an und bekommen später ein Darlehen für die Finanzierung einer Immobilie."),
               ("Nachgeschaut: Bausparvertrag Grenzgaenger 2026 | bausparen.one", "Der Bausparvertrag dient der Finanzierung von Wohneigentum.")]
    satz = "Ein Bausparvertrag verbindet Sparen mit einer späteren Finanzierung für eine Immobilie."
    assert belege.quellen_name(quellen[0][0]) == "Bausparvertrag"
    assert belege.vermischt(satz, quellen) == []
    assert belege.vermischt("Entkalker wie Durgol enthalten oft Milchsäure.", QUELLEN) == ["Entkalker wie Durgol enthalten oft Milchsäure."]


def test_the_note_is_short_and_comes_first():
    assert app_web.vermischt_notiz([]) == ""
    n = app_web.vermischt_notiz([("Durgol", "Milchsäure"), ("ORF.at", "Paracetamol"), ("A", "B"), ("C", "D")])
    assert n == "Vermischt: „Durgol“ ← „Milchsäure“; „ORFat“ ← „Paracetamol“; „A“ ← „B“. "
    assert n.count(".") == 1


def test_belege_anwenden_collects_the_triggers_only_when_asked():
    quellen = [{"nummer": 1, "titel": QUELLEN[0][0], "text": QUELLEN[0][1]}, {"nummer": 2, "titel": QUELLEN[1][0], "text": QUELLEN[1][1]}]
    text = "Durgol ist ein Entkalker aus der Schweiz. Entkalker wie Durgol enthalten oft Milchsäure."
    app_web._VERMISCHT.liste = []
    try:
        neu, notizen = app_web.belege_anwenden(text, "Was ist Durgol?", "", quellen)
        assert ("Durgol", "Milchsäure") in app_web._VERMISCHT.liste
        assert "Milchsäure" not in neu and any("anderen Quelle" in n for n in notizen)
    finally:
        app_web._VERMISCHT.liste = None
    neu2, _ = app_web.belege_anwenden(text, "Was ist Durgol?", "", quellen)
    assert neu2 == neu and app_web._VERMISCHT.liste is None
