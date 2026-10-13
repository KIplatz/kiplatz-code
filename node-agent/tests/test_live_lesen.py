# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wissen as w

from test_app_web import _api
from test_wissen import _oeffner


def test_addresses_are_found_in_questions_but_not_in_numbers_or_abbreviations():
    assert w.adressen_in_text("Was gibt es Neues auf news.at?") == ["news.at"]
    assert w.adressen_in_text("schau auf https://www.orf.at/stories/123, und auf ORF.at.") == ["https://www.orf.at/stories/123", "ORF.at"]
    assert w.adressen_in_text("Version 3.5 ist z.B. besser als 2.0, d.h. neuer.") == []
    assert w.adressen_in_text("mail an anna@example.at bitte") == []
    assert w.adressen_in_text("a.at b.de c.ch") == ["a.at", "b.de"]
    assert w.adressen_in_text("") == []


def test_live_page_is_read_for_the_question_and_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(w.urllib.request, "urlopen", _oeffner)
    api, fake, _ = _api(tmp_path)
    api.ki_einschalten()
    api._ki._thread.join(timeout=10)
    g = api.gespraech_neu()["daten"]
    fake_frage = fake.frage

    def frage(nachrichten, *, on_token=None, zusatz="", **kw):
        fake.zusatz = zusatz
        a = fake_frage(nachrichten, on_token=on_token)
        return type(a)("Dort stehen Anleitungen zu KI im Alltag (Quelle 1).", a.prompt_tokens, a.completion_tokens, a.dauer_s)
    fake.frage = frage
    r = api.frage(g["kennung"], "Was gibt es Neues auf beispiel.at?")
    assert r["ok"], r["text"]
    assert "Quelle 1: Beispiel-Seite" in fake.zusatz and "beispiel.at stehen Anleitungen" in fake.zusatz
    ls = r["daten"]["lieferschein"]
    assert "https://beispiel.at jetzt live gelesen" in ls["quellen"] and ls["quellen_liste"][0]["adresse"] == "https://beispiel.at"
    assert api._wissen.anzahl() == 1 and api._wissen.liste()[0]["adresse"] == "https://beispiel.at"
    r = api.frage(g["kennung"], "Was steht auf https://x.at/bild heute?")
    assert r["ok"] and "https://x.at/bild ließ sich nicht lesen" in r["daten"]["lieferschein"]["quellen"]


def test_live_lesen_picks_top_of_page_and_matching_passages():
    q, text, tr = w.live_lesen("beispiel.at", "KI-Detektoren im Vergleich", oeffner=_oeffner)
    assert q.adresse == "https://beispiel.at" and q.art == "seite" and len(text) > 40
    assert tr and any("Detektoren" in t.text for t in tr) and tr[0].text.startswith(w.abschnitte(text)[0][:20])
