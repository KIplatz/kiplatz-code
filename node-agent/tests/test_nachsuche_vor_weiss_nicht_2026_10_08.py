# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import ki_laufzeit
from test_app_web import _api

FRAGE = "Wie lang ist die Donau in Österreich?"
ERSTE = "Die Donau ist in Österreich rund 350 Kilometer lang."
GEFUNDEN = "Die Donau ist in Österreich rund 350 Kilometer lang (Quelle 1)."
GESTRICHEN = "Das weiß ich gerade nicht sicher."


def _streichen_ohne_beleg(text, frage, zusatz, quellen, **kw):
    if "350" in text and not any("350" in str(q.get("text", "")) for q in quellen):
        return GESTRICHEN, ["Die Zahl 350 stand in keiner Fundstelle und wurde gestrichen."]
    return text, []


def _wissen(suchen: list, internet_hat_es: bool):
    def mit_wissen(nachrichten, **kw):
        suchen.append(bool(kw.get("frisch")))
        lauf = getattr(app_web._SUCHLAUF, "stand", None)
        if kw.get("frisch") and lauf is not None:
            lauf["gesucht"] += ["Donau Länge Österreich"]
        if kw.get("frisch") and internet_hat_es:
            return ("Auszug [1]: Die Donau fließt auf rund 350 Kilometern durch Österreich.",
                    [{"nummer": 1, "art": "nachgeschaut", "titel": "Donau", "adresse": "https://de.wikipedia.org/wiki/Donau", "datum": "2026-10-08T09:00:00Z",
                      "text": "Die Donau fließt auf rund 350 Kilometern durch Österreich."}], 0, "")
        return ("Auszug [1]: Die Donau ist der zweitlängste Fluss Europas.",
                [{"nummer": 1, "art": "gemeinschaft", "titel": "Donau", "adresse": "", "datum": "2026-10-01T00:00:00Z", "text": "Die Donau ist der zweitlängste Fluss Europas."}], 0, "")
    return mit_wissen


def _modell(gesehen: list):
    def frage(nachrichten, **kw):
        z = str(kw.get("zusatz", ""))
        gesehen.append(z)
        return ki_laufzeit.Antwort(GEFUNDEN if "350 Kilometern" in z else ERSTE, 10, 5, 0.1)
    return frage


def test_a_member_question_is_looked_up_when_the_check_struck_the_number(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    api, fake, _ = _api(tmp_path)
    suchen: list = []
    gesehen: list = []
    fake.frage = _modell(gesehen)
    api._mit_wissen = _wissen(suchen, internet_hat_es=True)
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "Besucher auf kiplatz.at")
    assert suchen.count(True) == 1, suchen
    assert "350 Kilometer" in text and "weiß ich" not in text and "live nachprüfen" not in text
    assert ls["gemacht"] == "nachgeschaut und geantwortet" and ls.get("angebot") != "nachpruefen"
    assert "darum wurde im Internet nachgeschaut" in ls["quellen"]


def test_when_the_internet_has_nothing_either_the_member_hears_it_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    api, fake, _ = _api(tmp_path)
    suchen: list = []
    fake.frage = _modell([])
    api._mit_wissen = _wissen(suchen, internet_hat_es=False)
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "Besucher auf kiplatz.at")
    assert True in suchen
    assert "350" not in text
    assert text == app_web._GESUCHT_NICHTS_SATZ and "Soll ich live nachprüfen?" not in text


def test_an_own_question_is_looked_up_too_before_it_says_it_does_not_know(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    api, fake, _ = _api(tmp_path)
    suchen: list = []
    gesehen: list = []
    fake_frage = _modell(gesehen)

    def frage(nachrichten, **kw):
        if kw.get("system"):
            return ki_laufzeit.Antwort("KEINE", 1, 1, 0.1)
        return fake_frage(nachrichten, **kw)
    fake.frage = frage
    api._mit_wissen = _wissen(suchen, internet_hat_es=True)
    api.ki_einschalten()
    api._ki._thread.join(timeout=10)
    g = api.gespraech_neu()["daten"]
    r = api.frage(g["kennung"], FRAGE)
    assert r["ok"], r
    assert suchen.count(True) == 1, suchen
    assert "350 Kilometer" in r["daten"]["text"] and "live nachprüfen" not in r["daten"]["text"]
    assert r["daten"]["lieferschein"]["gemacht"] == "nachgeschaut und geantwortet"


def test_the_look_up_runs_once_and_never_in_a_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    api, fake, _ = _api(tmp_path)
    suchen: list = []

    def mit_wissen(nachrichten, **kw):
        suchen.append(bool(kw.get("frisch")))
        lauf = getattr(app_web._SUCHLAUF, "stand", None)
        if kw.get("frisch") and lauf is not None:
            lauf["gesucht"] += ["Donau Österreich"]
        art = "nachgeschaut" if kw.get("frisch") else "gemeinschaft"
        return ("Auszug [1]: Die Donau ist ein Fluss.", [{"nummer": 1, "art": art, "titel": "Donau", "adresse": "", "datum": "2026-10-08T09:00:00Z",
                                                          "text": "Die Donau ist ein Fluss."}], 0, "")
    fake.frage = lambda nachrichten, **kw: ki_laufzeit.Antwort(ERSTE, 10, 5, 0.1)
    api._mit_wissen = mit_wissen
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "Besucher auf kiplatz.at")
    assert suchen.count(True) == 1, suchen
    assert text == app_web._GESUCHT_NICHTS_SATZ and "350" not in text


def test_no_extra_look_up_when_this_answer_already_searched(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    monkeypatch.setattr(app_web, "im_netz_gesucht", lambda nachgeholt, quellen, lauf: True)
    api, fake, _ = _api(tmp_path)
    suchen: list = []
    fake.frage = _modell([])
    api._mit_wissen = _wissen(suchen, internet_hat_es=True)
    api._ki_starten_blockierend()
    api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "Besucher auf kiplatz.at")
    assert True not in suchen


def test_after_a_search_with_the_rules_words_only_one_more_round_with_the_models_words(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "belege_anwenden", _streichen_ohne_beleg)
    monkeypatch.setattr(app_web, "im_netz_gesucht", lambda nachgeholt, quellen, lauf: True)
    api, fake, _ = _api(tmp_path)
    suchen: list = []
    fake.frage = _modell([])
    innen = _wissen(suchen, internet_hat_es=True)

    def mit_wissen(nachrichten, **kw):
        lauf = getattr(app_web._SUCHLAUF, "stand", None)
        if lauf is not None and not kw.get("frisch"):
            lauf["nur_regel"] = True
        return innen(nachrichten, **kw)
    api._mit_wissen = mit_wissen
    api._ki_starten_blockierend()
    text, _ls = api._antwort_fuer_mitglied([{"role": "user", "content": FRAGE}], [], "Besucher auf kiplatz.at")
    assert suchen.count(True) == 1 and "350 Kilometer" in text
