# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import app_web
import bewertung
import wissen
from test_app_web import _api


def _stellen(n: int) -> list:
    q = wissen.Quelle("nachgeschaut-1", "nachgeschaut", "Nachgeschaut: Beispiel", "https://beispiel.at/seite", "2026-10-23T00:00:00Z", 100)
    return [wissen.Treffer(q, f"Stelle {i}: Gmunden hat am Traunsee eine Seepromenade.", 1.0) for i in range(n)]


def _lauf(tmp_path, monkeypatch, frage: str, n: int):
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api, "nachschauen_an", lambda: True)
    monkeypatch.setattr(api, "_nachschauen", lambda *a, **k: (_stellen(n), ""))
    monkeypatch.setattr(api._bewertung, "bereit", lambda: True)
    monkeypatch.setattr(api._bewertung, "sortieren", lambda frage, kand: bewertung.Sortierung(list(kand), [0.9] * len(kand), 0.9) if kand else None)
    app_web._SUCHLAUF.stand = {"runde": 0, "gesucht": [], "gelesen": set()}
    try:
        zusatz, quellen, _n, hinweis = api._mit_wissen_ohne_zeit([{"role": "user", "content": frage}], privat_erlaubt=False, frisch=True)
    finally:
        app_web._SUCHLAUF.stand = None
    return [q for q in quellen if q.get("art") == "nachgeschaut"], hinweis


def test_nur_die_besten_gelesenen_stellen_gehen_ans_modell(tmp_path, monkeypatch):
    live, hinweis = _lauf(tmp_path, monkeypatch, "Was gibt es an der Seepromenade in Gmunden?", 12)
    assert len(live) == app_web.LIVE_STELLEN
    assert f"bekam das Modell die ersten {app_web.LIVE_STELLEN}, {12 - app_web.LIVE_STELLEN} weitere nicht" in hinweis
    wenig, hinweis2 = _lauf(tmp_path / "b", monkeypatch, "Was gibt es an der Seepromenade in Gmunden?", 3)
    assert len(wenig) == 3 and "weitere nicht" not in hinweis2
    zwei, _ = _lauf(tmp_path / "c", monkeypatch, "Was haben Gmunden und Wels an Sehenswürdigkeiten?", 14)
    assert len(zwei) == 2 * app_web.LIVE_STELLEN


def test_eine_kuerzung_steht_im_lieferschein():
    assert "gekürzt" in app_web.GEKUERZT_HINWEIS
    quelle = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert 'if getattr(a, "gekuerzt", False):' in quelle and "+ GEKUERZT_HINWEIS" in quelle
