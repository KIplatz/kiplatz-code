# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import selbstauskunft as sa


def test_asking_to_remember_gets_the_honest_sentence_and_the_real_way():
    for f in ("KIplatz gibt es seit 2026 kannst du das abspeichern?", "Merk dir das bitte", "Kannst du dir das merken?", "Speicher das ab"):
        t = sa.antwort(f)
        assert t == sa.TEXTE["merken"], f
    assert "Daumen runter" in sa.TEXTE["merken"] and "nichts merken" in sa.TEXTE["merken"]


def test_since_when_kiplatz_exists_has_a_fixed_answer_and_is_in_the_profile():
    for f in ("Seit wann gibt es KIplatz?", "Wie alt ist KIplatz", "Wann wurde KIplatz gegründet?"):
        assert sa.antwort(f) == sa.TEXTE["seit"], f
    assert "September 2026" in sa.STECKBRIEF and "September 2026" in sa.TEXTE["seit"]


def test_ordinary_questions_stay_with_the_model():
    for f in ("Wie speichere ich eine Datei in Word?", "Was ist ein Merksatz?", "Seit wann gibt es das Internet?", "Wie alt ist der Stephansdom?",
              "Kannst du mir helfen, das Dokument zu speichern und zu drucken?"):
        assert sa.antwort(f) is None, f
    assert "Erfinde keine Regeln" in sa.ANWEISUNG
