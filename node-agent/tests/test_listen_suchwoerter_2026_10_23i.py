# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

from test_app_web import _api

TABELLE = "Welche sind die 5 größten Städte Österreichs? Bitte als Tabelle mit Einwohnerzahl."


def test_listenfrage_sucht_mit_den_woertern_des_modells(tmp_path, monkeypatch):
    import app_web
    api, _fake, _ = _api(tmp_path)
    gefragt: list = []

    def suchwoerter(nachrichten, frage, *, bisher=None, ohne_modell=False):
        gefragt.append(ohne_modell)
        return ["Statistik Österreich größte Städte Einwohnerzahl 2026"]

    monkeypatch.setattr(api, "_suchwoerter", suchwoerter)
    monkeypatch.setattr(api._nachschauer, "suche_runde", lambda *a, **k: ([], [], ""), raising=False)
    for modell, erwartet in ((True, False), (False, True)):
        gefragt.clear()
        app_web._SUCHLAUF.stand = lauf = {"runde": 0, "gesucht": [], "gelesen": set()}
        api._suche_nebenher(TABELLE, None, modell=modell)
        assert gefragt == [erwartet] and lauf["nebenher"]["regel"] is erwartet
    app_web._SUCHLAUF.stand = None
    assert app_web.erdung_noetig(TABELLE)


def test_live_nachpruefen_sucht_im_faden_wie_es_war(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    aufrufe: list = []

    def nachschauen(frage, treffer, **k):
        aufrufe.append(k)
        return [], ""

    monkeypatch.setattr(api, "_nachschauen", nachschauen)
    api._nachschauen_vorab(TABELLE, [], None)()
    assert aufrufe[0].get("frisch") and "suchen" not in aufrufe[0]
