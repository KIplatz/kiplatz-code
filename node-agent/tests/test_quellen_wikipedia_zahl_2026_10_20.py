# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import quellen_stand as qs
import wikipedia
from test_bau_30a_wikipedia_vektoren import ART, _db


def _kopie(tmp_path):
    ordner = tmp_path / "wiki"
    ordner.mkdir()
    _db(ordner / wikipedia.DB).schliessen()
    w = wikipedia.WikiKopie(lambda: ordner, freigabe_mb=lambda: 200_000, darf=lambda: False, modell=lambda: "m")
    w._stand_setzen(fertig_ausgabe="20261004")
    return w


def test_the_count_is_there_as_soon_as_the_copy_is_open_even_if_the_device_may_not_work(tmp_path):
    w = _kopie(tmp_path)
    w._oeffnen()
    assert w.bereit()
    assert w.zustand()["artikel"] == len(ART) > 0
    e = qs._wikipedia(w)
    assert e["ok"] and e["zahl"] == len(ART)
    assert e["text"] == f"Wikipedia: {len(ART)} Artikel, Stand 04.10.2026."


def test_only_the_number_gets_thousand_points(tmp_path, monkeypatch):
    w = _kopie(tmp_path)
    w._oeffnen()
    monkeypatch.setattr(w, "zustand", lambda: {"ausgabe": "20261004", "artikel": 2_912_345, "phase": "fertig"})
    assert qs._wikipedia(w)["text"] == "Wikipedia: 2.912.345 Artikel, Stand 04.10.2026."
