# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prompt_pruefer as pp

from test_app_web import _api

VOLL = ("Prüf meinen Prompt: Du bist eine erfahrene Hausverwalterin. Schreib für meinen Vermieter eine höfliche E-Mail mit höchstens 120 Wörtern, "
        "ohne Drohungen. Sachverhalt: Seit drei Wochen ist die Heizung in meiner Wohnung im zweiten Stock kaputt, ich habe zweimal angerufen und "
        "niemand ist gekommen, bitte um einen Termin noch diese Woche")


@pytest.mark.parametrize("nachricht,wunsch", [
    ("Prüf meinen Prompt: Schreib eine E-Mail", True), ("Was fehlt meinem Prompt?", True), ("Kannst du meinen Prompt prüfen? „Schreib ein Gedicht“", True),
    ("Check my prompt: write a poem", True), ("What's missing from my prompt?", True), ("Is my prompt good: write a poem about cats", True),
    ("Schreib mir einen Prompt für ein Bewerbungsschreiben", False), ("Wie hoch ist der Großglockner?", False), ("Prüf die Rechnung im Anhang", False),
])
def test_wunsch_erkennen(nachricht, wunsch):
    assert pp.gewuenscht(nachricht) is wunsch


def test_ein_voller_prompt_hat_alle_acht():
    da, fehlt, daten = pp.pruefen(pp.prompt_aus(VOLL))
    assert not fehlt and len(da) == 8 and not daten


def test_ein_kurzer_prompt_bekommt_tipps():
    de, en = pp.antwort("Prüf meinen Prompt: Schreib eine E-Mail an meinen Vermieter wegen der Heizung.")
    assert de.startswith("Dein Prompt hat 3 von 8 Angaben") and "- Länge:" in de and "- Rolle:" in de and "Für wen:" not in de
    assert en.startswith("Your prompt has 3 of the 8 details") and "- Length:" in en


def test_persoenliche_daten_und_ohne_prompt():
    de, _ = pp.antwort(VOLL + ", meine Nummer 0664 1234567, max@beispiel.at")
    assert "eine E-Mail-Adresse und eine Telefonnummer" in de and "[Nummer]" in de
    de, en = pp.antwort("Was fehlt meinem Prompt?")
    assert de.startswith("Füg den Prompt") and en.startswith("Paste the prompt")
    assert pp.antwort("Wie hoch ist der Großglockner?") is None


def test_der_ganze_weg_ohne_modell(tmp_path):
    api, fake, _ = _api(tmp_path)
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": "Prüf meinen Prompt: Schreib eine E-Mail an meinen Vermieter."}], [], "ein Mitglied")
    assert text.startswith("Dein Prompt hat") and ls["gemacht"] == pp.GEMACHT
    text, _ = api._antwort_fuer_mitglied([{"role": "user", "content": "Check my prompt: write an email to my landlord."}], [], "ein Mitglied")
    assert text.startswith("Your prompt has")
