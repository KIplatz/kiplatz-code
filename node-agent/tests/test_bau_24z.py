# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wikipedia


def _db(tmp_path):
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    db.teil_aufnehmen(1, [
        {"id": 1, "titel": "Allalinhorn", "beliebt": 0.001, "geaendert": "", "umleitungen": [],
         "teile": ["Das Allalinhorn ist ein 4027 Meter hoher Berg in den Walliser Alpen."]},
        {"id": 2, "titel": "Minecraft", "beliebt": 0.002, "geaendert": "", "umleitungen": [],
         "teile": ["Minecraft ist ein Spiel, das 2011 erschienen und sehr berühmt geworden ist."]},
    ])
    return db


def test_the_word_counts_are_a_table_and_the_search_still_finds(tmp_path):
    db = _db(tmp_path)
    vorher = db._df("berg")
    assert not db.hat_wortzahl()
    assert db.wortzahl_anlegen() > 5 and db.hat_wortzahl()
    db._df_merk.clear()
    assert db._df("berg") == vorher == 1
    assert [t[2] for t in db.suchen("Wie hoch ist das Allalinhorn?")][:1] == ["Allalinhorn"]


def test_a_slow_search_ends_after_the_limit_and_the_next_one_does_not_wait(tmp_path, monkeypatch):
    db = _db(tmp_path)
    los = threading.Event()

    def langsam(self, *a):
        los.wait(5)
        return []
    monkeypatch.setattr(wikipedia.Datenbank, "_suchen_begrenzt", langsam)
    s = time.monotonic()
    with pytest.raises(wikipedia.Unterbrochen):
        db.suchen("Wann ist das Spiel berühmt geworden?", frist_s=0.3)
    assert time.monotonic() - s < 1.0
    s = time.monotonic()
    with pytest.raises(wikipedia.Unterbrochen, match="läuft noch"):
        db.suchen("Wie hoch ist das Allalinhorn?")
    assert time.monotonic() - s < 0.2
    los.set()


def test_stop_ends_the_wait_at_once(tmp_path, monkeypatch):
    db = _db(tmp_path)
    los = threading.Event()
    monkeypatch.setattr(wikipedia.Datenbank, "_suchen_begrenzt", lambda self, *a: los.wait(5) or [])
    stopp = threading.Event()
    threading.Timer(0.2, stopp.set).start()
    s = time.monotonic()
    with pytest.raises(wikipedia.Unterbrochen, match="gestoppt"):
        db.suchen("Wann ist das Spiel berühmt geworden?", frist_s=30, abbrechen=stopp.is_set)
    assert time.monotonic() - s < 1.0
    los.set()


def test_a_word_that_takes_long_to_count_counts_as_common(tmp_path):
    db = _db(tmp_path)
    db._teil_ende = 0.0
    alt = wikipedia.DF_FRIST_S
    try:
        wikipedia.DF_FRIST_S = -1.0
        assert db._df("spiel") == db._anzahl()
    finally:
        wikipedia.DF_FRIST_S = alt


def test_the_copy_answers_nothing_instead_of_hanging():
    src = (Path(__file__).resolve().parent.parent / "app_web.py").read_text(encoding="utf-8")
    assert "abbrechen=lambda: self.abbruch_gewuenscht" in src
