# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gedaechtnis

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


def test_erkennen_understands_merk_dir_vergiss_and_plain_questions():
    assert gedaechtnis.erkennen("Merk dir: ich wohne in Gmunden.") == ("merken", "ich wohne in Gmunden")
    assert gedaechtnis.erkennen("merke dir bitte, dass ich Vegetarier bin") == ("merken", "ich Vegetarier bin")
    assert gedaechtnis.erkennen("Notiere dir meine Firma heißt Huber GmbH") == ("merken", "meine Firma heißt Huber GmbH")
    assert gedaechtnis.erkennen("Vergiss das mit Gmunden") == ("vergessen", "Gmunden")
    assert gedaechtnis.erkennen("vergiss alles") == ("alles", "")
    assert gedaechtnis.erkennen("Was weißt du über mich?") == ("liste", "")
    assert gedaechtnis.erkennen("Wie wird das Wetter morgen in Linz?") is None
    assert gedaechtnis.erkennen("Merk dir") is None and gedaechtnis.erkennen("") is None


def test_memory_remembers_forgets_and_builds_the_prompt(tmp_path):
    g = gedaechtnis.Gedaechtnis(tmp_path)
    assert g.stand() == {"an": True, "anzahl": 0, "eintraege": []} and g.vorspann() == ""
    assert g.anwenden(("merken", "ich wohne in Gmunden")) == "Gemerkt: ich wohne in Gmunden"
    assert g.anwenden(("merken", "Ich wohne in Gmunden")) == "Das weiß ich schon: ich wohne in Gmunden"
    g.merken("ich bin Vegetarier")
    v = g.vorspann()
    assert v.startswith("Was die Person dir selbst über sich gesagt hat") and "- ich wohne in Gmunden" in v and "- ich bin Vegetarier" in v
    zusatz, n = g.anhaengen("Auszüge …")
    assert zusatz.startswith("Was die Person") and zusatz.endswith("Auszüge …") and n == 2
    assert "Gmunden" in g.anwenden(("liste", "")) and "Einstellungen" in g.anwenden(("liste", ""))
    assert g.anwenden(("vergessen", "gmunden")) == "Vergessen (1 Eintrag)."
    assert g.anwenden(("vergessen", "Salzburg")) == "Dazu habe ich mir nichts gemerkt: Salzburg"
    assert g.stand()["anzahl"] == 1
    g.setzen(False)
    assert g.vorspann() == "" and g.anhaengen("x") == ("x", 0) and g.stand()["anzahl"] == 1
    g.setzen(True)
    kennung = g.liste()[0]["kennung"]
    assert g.vergessen(kennung) == 1 and g.stand()["anzahl"] == 0
    g.merken("a"); g.merken("b")
    assert g.anwenden(("alles", "")) == "Alles vergessen." and g.anwenden(("alles", "")) == "Ich hatte mir nichts gemerkt."
    g.merken("ich heiße Anna")
    assert gedaechtnis.Gedaechtnis(tmp_path).liste()[0]["text"] == "ich heiße Anna"


def test_memory_caps_size(tmp_path):
    g = gedaechtnis.Gedaechtnis(tmp_path)
    for i in range(70):
        g.merken(f"Eintrag {i} " + "x" * 400)
    st = g.stand()
    assert st["anzahl"] == gedaechtnis.MAX_EINTRAEGE and all(len(e["text"]) <= gedaechtnis.MAX_ZEICHEN for e in st["eintraege"])
    assert len(g.vorspann()) <= gedaechtnis.MAX_VORSPANN


def test_window_answers_merk_dir_without_the_model_and_never_sends_memory_to_the_community(tmp_path, monkeypatch):
    from test_app_web import _api
    api, fake, _ = _api(tmp_path)
    g = api.gespraech_neu()["daten"]
    r = api.frage(g["kennung"], "Merk dir: ich wohne in Gmunden", ki_starten=False)
    assert r["ok"] and r["daten"]["text"] == "Gemerkt: ich wohne in Gmunden" and r["daten"]["lieferschein"]["gemacht"] == "gemerkt"
    assert api.gedaechtnis_stand()["daten"]["anzahl"] == 1
    gesehen = {}

    def community_antwort(nachrichten, fuer_seite):
        gesehen["nachrichten"] = nachrichten
        return {"text": "aus der Community", "lieferschein": {}, "von": "PC"}
    monkeypatch.setattr(api, "_community_antwort", community_antwort)
    monkeypatch.setattr(api, "fragt_community", lambda: True)
    r = api.frage(g["kennung"], "Wie heißt meine Stadt?")
    assert r["ok"] and r["daten"]["text"] == "aus der Community"
    assert "Gmunden" not in str(gesehen["nachrichten"])
    assert 'id="gedaechtnis-an"' in HTML and "gedaechtnis_merken" in HTML and "gedaechtnis_vergessen" in HTML and "gedaechtnis_leeren" in HTML
    r = api.gedaechtnis_vergessen(api.gedaechtnis_stand()["daten"]["eintraege"][0]["kennung"])
    assert r["ok"] and r["daten"]["anzahl"] == 0
