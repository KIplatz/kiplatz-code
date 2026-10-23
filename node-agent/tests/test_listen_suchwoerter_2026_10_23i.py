# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

from test_app_web import _api

TABELLE = "Welche sind die 5 größten Städte Österreichs? Bitte als Tabelle mit Einwohnerzahl."


def test_listenfrage_sucht_mit_den_woertern_des_modells(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    gefragt: list = []

    def suchwoerter(nachrichten, frage, *, entscheiden=False, bisher=None, ohne_modell=False):
        gefragt.append(ohne_modell)
        return ["Statistik Österreich größte Städte Einwohnerzahl 2026"]

    monkeypatch.setattr(api, "_suchwoerter", suchwoerter)
    monkeypatch.setattr(api, "_suchrunde", lambda frage, alle, lauf, treffer, frisch=False: ([], ""))
    monkeypatch.setattr(api._nachschauer, "suche_runde", lambda *a, **k: ([], [], ""), raising=False)
    api._nachschauen(TABELLE, [], suchen=True)
    assert gefragt == [True]
    gefragt.clear()
    api._nachschauen(TABELLE, [], suchen=True, modell_woerter=True)
    assert gefragt == [False]


def test_der_faden_neben_der_kopie_gibt_den_schalter_weiter(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    aufrufe: list = []

    def nachschauen(frage, treffer, **k):
        aufrufe.append(k)
        return [], ""

    monkeypatch.setattr(api, "_nachschauen", nachschauen)
    api._nachschauen_vorab(TABELLE, [], None, frisch=False, modell=True)()
    api._nachschauen_vorab(TABELLE, [], None, frisch=False)()
    api._nachschauen_vorab(TABELLE, [], None, frisch=True, modell=True)()
    assert aufrufe[0].get("suchen") and aufrufe[0].get("modell_woerter") is True
    assert aufrufe[1].get("suchen") and aufrufe[1].get("modell_woerter") is False
    assert aufrufe[2].get("frisch") and "modell_woerter" not in aufrufe[2]
