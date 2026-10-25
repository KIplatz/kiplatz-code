# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import app_web
import ki_laufzeit
import nachschauen
from test_app_web import _api


@pytest.mark.parametrize("frage", [
    "Wenn ich von München nach Augsburg fahren will mit dem Zug und dann nach Wien wie lange brauch ich da",
    "Wie lange brauche ich von Linz nach Graz?",
    "Wann fährt der nächste Zug nach Salzburg?",
    "Was kostet ein Klimaticket?",
    "Hat der Spar in Gmunden heute offen?",
    "Öffnungszeiten Freibad Gmunden",
    "How long does the train from Vienna to Munich take?",
])
def test_nicht_im_lexikon(frage):
    assert nachschauen.nicht_im_lexikon(frage)


@pytest.mark.parametrize("frage", [
    "Wie viele Einwohner hat Linz?", "Wann wurde der Stephansdom gebaut?", "Wer hat die Glühbirne erfunden?",
    "Wie hoch ist der Großglockner?", "Wie lange dauerte der Dreißigjährige Krieg?", "Was ist ein ICE?", "Erzähl mir was über Linz", "",
])
def test_lexikonfragen_bleiben(frage):
    assert not nachschauen.nicht_im_lexikon(frage)


class _Wiki:
    def __init__(self):
        self.gesucht = 0

    def bereit(self):
        return True

    def suchen(self, *a, **k):
        self.gesucht += 1
        return []

    def einleitung(self, *a, **k):
        return []

    def zeiten_der_suche(self):
        return {"zaehlen": 0.2, "woerter": 4.6, "titel": 0.1, "lesen": 0.1, "kandidaten": 120, "ausgang": "grenze"}

    def ausgabe(self):
        return "20261001"


def test_eine_reisefrage_ueberspringt_die_wikipedia_und_sucht_gleich(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    wiki = _Wiki()
    api._wiki = wiki
    gesucht: list = []

    def nachschauen_(frage, treffer, **kw):
        gesucht.append((kw.get("frisch"), kw.get("suchen")))
        return [], ""
    monkeypatch.setattr(api, "_nachschauen", nachschauen_)
    monkeypatch.setattr(api, "nachschauen_an", lambda: True)
    _z, _q, _n, hinweis = api._mit_wissen([{"role": "user", "content": "Wie lange brauche ich mit dem Zug von Linz nach Graz?"}])
    assert wiki.gesucht == 0 and gesucht == [(None, True)] and "Wikipedia wurde übersprungen" in hinweis
    gesucht.clear()
    _z, _q, _n, hinweis = api._mit_wissen([{"role": "user", "content": "Wann wurde der Stephansdom gebaut?"}])
    assert wiki.gesucht == 0 and "Wikipedia-Kopie" not in hinweis
    monkeypatch.setattr(app_web, "WIKI_ALS_QUELLE", True)
    gesucht.clear()
    api._mit_wissen([{"role": "user", "content": "Wann wurde der Stephansdom gebaut?"}])
    assert wiki.gesucht >= 1 and all(not s for _f, s in gesucht)


def test_die_wikipedia_meldet_ihre_zeiten_im_ablauf():
    ki_laufzeit.messung_beginnen()
    app_web.wiki_messen(_Wiki(), 5.02)
    z = ki_laufzeit.messung_ende()
    arten = {e["art"]: e["s"] for e in z}
    assert arten["wikigrenze"] == 5.02 and arten["wwoerter"] == 4.6 and arten["wstellen"] == 120
    app_web.wiki_messen(object(), 1.0)
