# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege


def test_sentences_about_the_own_answer_never_go_out_ordinary_brackets_stay():
    assert belege.ohne_selbstbezug("(Das war eine falsche Angabe von mir, die ich korrigiere.) Die Donau ist rund 2850 km lang [1].") == \
        ("Die Donau ist rund 2850 km lang [1].", 1)
    assert belege.ohne_selbstbezug("Entschuldigung, meine vorige Antwort war falsch. Wien hat rund 2 Millionen Einwohner [1].")[0] == \
        "Wien hat rund 2 Millionen Einwohner [1]."
    gut = "Die Donau fließt durch zehn Staaten (Deutschland bis Ukraine) [1]. Ihre erste Quelle liegt im Schwarzwald [1]."
    assert belege.ohne_selbstbezug(gut) == (gut, 0)
    assert belege.ohne_selbstbezug("Korrektur: meine erste Fassung war falsch.") == ("Das weiß ich noch nicht.", 1)


def test_the_retry_instructions_never_speak_of_a_previous_answer_the_model_did_not_see():
    for z in (app_web.BELEGE_ZUSATZ, app_web.NAMEN_ZUSATZ):
        assert "vorige" not in z and "ganz neu" in z and "Erwähne nie" in z


def test_the_retry_is_cleaned_before_it_is_weighed():
    quellen = [{"nummer": 1, "text": "Die Donau ist mit 2857 Kilometern der zweitlängste Fluss Europas."}]
    zusatz = "[1] Die Donau ist mit 2857 Kilometern der zweitlängste Fluss Europas."
    erste = "Die Donau ist 3100 Kilometer lang [1]."
    neu, notizen = app_web.belege_anwenden(erste, "Wie lang ist die Donau?", zusatz, quellen,
                                           nochmal=lambda extra: "(Das war eine falsche Angabe von mir, die ich korrigiere.) Die Donau ist 2857 Kilometer lang [1].")
    assert neu == "Die Donau ist 2857 Kilometer lang [1]." and "falsche Angabe" not in neu
