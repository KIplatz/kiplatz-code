# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import ki_laufzeit
from test_app_web import _api

FRAGE = "Wie lange braucht eine KI sich selbst zu kopieren"


def test_a_member_question_gets_one_more_search_at_most_and_the_question_goes_along(tmp_path):
    api, fake, _ = _api(tmp_path)
    gesehen: list[str] = []
    suchen = []

    def frage(nachrichten, **kw):
        gesehen.append(str(kw.get("zusatz", "")))
        return ki_laufzeit.Antwort("Das weiß ich noch nicht.", 10, 5, 0.1)
    fake.frage = frage

    def mit_wissen(nachrichten, **kw):
        suchen.append(kw.get("frisch"))
        return "Auszug [1]: Studie 2026, Erfolg in 81 Prozent der Läufe.", [{"nummer": 1, "art": "nachgeschaut", "titel": "Studie", "text": "Erfolg in 81 Prozent der Läufe."}], 0, ""
    api._mit_wissen = mit_wissen
    api._ki_starten_blockierend()
    api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "ein Mitglied")
    assert len(gesehen) == 2, gesehen
    assert suchen.count(True) == 1
    assert FRAGE in gesehen[1] and "Beantworte genau das" in gesehen[1]
    assert app_web.SUCHRUNDEN_MITGLIED == 2 and app_web.SUCHRUNDEN == 3


def test_a_measure_question_gets_the_focus_already_in_the_first_draft(tmp_path):
    api, fake, _ = _api(tmp_path)
    gesehen: list[str] = []

    def frage(nachrichten, **kw):
        gesehen.append(str(kw.get("zusatz", "")))
        return ki_laufzeit.Antwort("In keiner Quelle steht eine Dauer.", 10, 5, 0.1)
    fake.frage = frage
    api._mit_wissen = lambda nachrichten, **kw: ("Auszug [1]: Erfolg in 81 Prozent der Läufe.", [{"nummer": 1, "art": "gemeinschaft", "titel": "Studie", "text": "Erfolg in 81 Prozent der Läufe."}], 0, "")
    api._ki_starten_blockierend()
    api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "ein Mitglied")
    assert FRAGE in gesehen[0] and "Beantworte genau das" in gesehen[0]
    gesehen.clear()
    api._antwort_fuer_mitglied([{"role": "user", "content": "Wer hat die Glühbirne erfunden?"}], [], "ein Mitglied")
    assert "Beantworte genau das" not in gesehen[0]
    assert app_web.massfrage("Wann ist Ostern 2027?") and app_web.massfrage("How many people live in Vienna?")
    assert not app_web.massfrage("Wiewohl es regnet, gehen wir") and not app_web.massfrage("Erzähl mir was über Linz")


def test_without_a_web_search_the_answer_never_claims_one_and_the_new_wording_triggers_the_search(tmp_path):
    api, fake, _ = _api(tmp_path)
    gesehen: list[str] = []
    suchen: list = []

    def frage(nachrichten, **kw):
        gesehen.append(str(kw.get("zusatz", "")))
        return ki_laufzeit.Antwort("Keine der Quellen nennt eine Dauer dafür.", 10, 5, 0.1)
    fake.frage = frage

    def ohne_netz(nachrichten, **kw):
        suchen.append(kw.get("frisch"))
        return "Auszug [1]: Studie, Erfolg in 81 Prozent.", [{"nummer": 1, "art": "gemeinschaft", "titel": "Studie", "text": "Erfolg in 81 Prozent."}], 0, ""
    api._mit_wissen = ohne_netz
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "ein Mitglied")
    assert True in suchen
    assert "im Internet" not in text and "Internet" not in ls["quellen"].split("„Live nachprüfen“")[0]
    app_web_mod = app_web
    assert app_web_mod.im_netz_gesucht(False, [{"art": "nachgeschaut"}], None) and not app_web_mod.im_netz_gesucht(False, [], {"gesucht": []})


def test_a_search_that_did_not_get_through_says_so():
    assert app_web.im_netz_gesucht(False, [], {"gesucht": ["x"], "abgelehnt": True}) == "nicht_erreicht"
    assert app_web.im_netz_gesucht(False, [], {"gesucht": ["x"]}) is True
    ls: dict = {}
    t = app_web._weiss_nicht_anwenden("Das weiß ich nicht.", ls, gesucht="nicht_erreicht")
    assert "nicht durchgekommen" in t and "nichts Verlässliches" not in t and "nicht durchgekommen" in ls["quellen"]
