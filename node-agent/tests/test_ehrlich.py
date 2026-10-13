# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import pruefung


def test_a_short_yes_searches_the_previous_question_and_the_kis_question_back():
    n = [{"role": "user", "content": "Was gibt es Neues zu ChatGPT?"},
         {"role": "assistant", "content": "Aus den Auszügen gibt es nichts Neues. Möchtest du wissen, wie sich die Nutzung verändert hat?"},
         {"role": "user", "content": "Ja"}]
    f = app_web.suchfrage(n)
    assert "Neues zu ChatGPT" in f and "Nutzung verändert" in f and f.endswith("Ja")
    n2 = n[:2] + [{"role": "user", "content": "Wie wird das Wetter morgen in Linz?"}]
    assert app_web.suchfrage(n2) == "Wie wird das Wetter morgen in Linz?"
    assert app_web.suchfrage([{"role": "user", "content": "Ja"}]) == "Ja"
    assert app_web.suchfrage([]) == ""


def test_questions_back_to_the_person_get_no_colour_and_invented_answers_are_caught():
    auszuege = [(1, "ChatGPT ist ein Chatbot von OpenAI. Er beantwortet Fragen in natürlicher Sprache.")]
    pr = pruefung.pruefen("ChatGPT ist ein Chatbot von OpenAI. Möchtest du wissen, wie man Skills erstellt?", auszuege)
    assert [s.farbe for s in pr.saetze] == ["gruen", "unbestimmt"]
    erfunden = pruefung.pruefen("Der Work-Modus funktioniert wie folgt. Individuelle Vorlagen speichern Formulare. Factsheets fassen Themen zusammen. Preislisten entstehen automatisch.", auszuege)
    assert erfunden.rot >= 3 and app_web.erfunden_verdacht(erfunden, [{"nummer": 1, "text": auszuege[0][1]}], None)
    assert not app_web.erfunden_verdacht(erfunden, [], None)
    assert not app_web.erfunden_verdacht(erfunden, [{"nummer": 1, "text": "x"}], ("rechnung", object()))
    assert not app_web.erfunden_verdacht(pr, [{"nummer": 1, "text": auszuege[0][1]}], None)
