# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ki_laufzeit
import selbstauskunft


@pytest.mark.parametrize("frage,art", [
    ("Was ist KIplatz?", "was"),
    ("was ist kiplatz", "was"),
    ("Erklär mir KIplatz bitte", "was"),
    ("Was macht KIplatz eigentlich?", "was"),
    ("Worum geht es hier?", "was"),
    ("Wer bist du?", "wer"),
    ("Wer hat dich gebaut?", "wer"),
    ("Bist du ChatGPT?", "wer"),
    ("Was kannst du?", "koennen"),
    ("Womit kannst du mir helfen?", "koennen"),
    ("Wie funktioniert KIplatz?", "funktion"),
    ("Woher kommen deine Antworten?", "funktion"),
    ("Wie funktioniert das?", "funktion"),
    ("Wie funktionierst du?", "funktion"),
    ("Wie funktioniert das hier?", "funktion"),
    ("Was kostet KIplatz?", "kosten"),
    ("Ist KIplatz wirklich gratis?", "kosten"),
    ("Was sind Credits bei KIplatz?", "credits"),
    ("Wofür bekomme ich Credits?", "credits"),
    ("Wofür gibt es bei KIplatz eine Platzordnung?", "platzordnung"),
    ("Wofür gibt es bei KIplatz eine Hausordnung?", "platzordnung"),
    ("Was steht in der Platzordnung?", "platzordnung"),
])
def test_erkennt_fragen_nach_kiplatz(frage, art):
    assert selbstauskunft.art(frage) == art
    assert selbstauskunft.antwort(frage) == selbstauskunft.TEXTE[art]


@pytest.mark.parametrize("frage", [
    "Was ist beispiel.at?",
    "Was macht die Firma Huber in Gmunden?",
    "Wie wird das Wetter heute in Linz?",
    "Was ist eine dezentrale KI?",
    "Wer ist Maria aus Wels?",
    "Wie funktioniert das Einwegpfand in Deutschland?",
    "Wie funktioniert das Lotto in Österreich?",
    "Wie funktioniert das bei uns?",
    "Wie geht das mit der Arbeitnehmerveranlagung?",
    "Schreib mir einen Text über KIplatz für die Vereinszeitung, mit 300 Wörtern, der erklärt, was KIplatz ist und wie man mitmacht, bitte in einfacher Sprache",
    "",
])
def test_andere_fragen_gehen_ans_modell(frage):
    assert selbstauskunft.antwort(frage) is None


def test_texte_folgen_den_regeln_der_website():
    for name, text in selbstauskunft.TEXTE.items():
        assert "KIplatz aus KIplatz" not in text, name
        assert not re.search(r"\b(kann (ich|KIplatz) nicht|noch nicht|Testbetrieb|im Aufbau|leider)\b", text), name
        assert "—" not in text and "–" not in text, name
        assert "Rechenzentrum" in text or name in ("koennen", "funktion", "credits", "platzordnung", "merken", "lernen"), name
        for satz in re.split(r"(?<=[.!?])\s+", text):
            assert len(satz.split()) <= 45, (name, satz)


def test_nur_die_letzte_nachricht_der_person_zaehlt():
    assert selbstauskunft.feste_antwort([]) is None
    assert selbstauskunft.feste_antwort([{"role": "assistant", "content": "Was ist KIplatz?"}]) is None
    assert selbstauskunft.feste_antwort([{"role": "user", "content": "Was ist KIplatz?"}, {"role": "assistant", "content": "…"}, {"role": "user", "content": "Und das Wetter?"}]) is None
    assert selbstauskunft.feste_antwort([{"role": "user", "content": "Hallo"}, {"role": "assistant", "content": "Hallo."}, {"role": "user", "content": "Was bist du?"}]) == selbstauskunft.TEXTE["wer"]


def test_server_frage_antwortet_ohne_modell():
    s = ki_laufzeit.KiServer.__new__(ki_laufzeit.KiServer)
    s.port = None
    s.laeuft = lambda: False
    stuecke: list[str] = []
    a = ki_laufzeit.KiServer.frage(s, [{"role": "user", "content": "Was ist KIplatz?"}], on_token=stuecke.append)
    assert a.text == selbstauskunft.TEXTE["was"] and a.completion_tokens == 0 and stuecke == [a.text]
    with pytest.raises(ki_laufzeit.KiError):
        ki_laufzeit.KiServer.frage(s, [{"role": "user", "content": "Was ist beispiel.at?"}])


def test_systemtext_ohne_den_alten_satz():
    assert "KIplatz aus KIplatz" not in ki_laufzeit.SYSTEMTEXT
