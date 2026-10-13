# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import wissen
from test_app_web import _api

DAUER = 0.6


class _Wiki:
    def bereit(self):
        return True

    def suchen(self, *a, **k):
        time.sleep(DAUER)
        return []

    def einleitung(self, frage):
        return []

    def ausgabe(self):
        return "20260920"


def _vorbereiten(tmp_path, monkeypatch):
    api = _api(tmp_path)[0]
    api._wiki = _Wiki()
    faeden, gesucht = [], []

    def nachschauen(frage, treffer, *, frisch=False, nachrichten=None, abgedeckt=None):
        faeden.append(threading.current_thread().name)
        gesucht.append(frisch)
        time.sleep(DAUER)
        return [], "nachgeschaut"
    monkeypatch.setattr(api, "_nachschauen", nachschauen)
    monkeypatch.setattr(api, "nachschauen_an", lambda: True)
    return api, faeden, gesucht


def test_a_live_check_searches_beside_the_wikipedia(tmp_path, monkeypatch):
    api, faeden, gesucht = _vorbereiten(tmp_path, monkeypatch)
    t0 = time.time()
    _z, _q, _n, hinweis = api._mit_wissen_ohne_zeit([{"role": "user", "content": "Wie hoch ist der Großglockner?"}], privat_erlaubt=False, frisch=True)
    dauer = time.time() - t0
    assert gesucht == [True] and faeden == ["nachschauen-vorab"] and "nachgeschaut" in hinweis
    assert dauer < 2 * DAUER - 0.1, f"{dauer:.2f} s: Wikipedia und Suche liefen nacheinander"


def test_without_live_nothing_is_searched_ahead(tmp_path, monkeypatch):
    api, faeden, gesucht = _vorbereiten(tmp_path, monkeypatch)
    api._mit_wissen_ohne_zeit([{"role": "user", "content": "Wie hoch ist der Großglockner?"}], privat_erlaubt=False, frisch=False)
    assert "nachschauen-vorab" not in faeden and gesucht in ([], [False])
