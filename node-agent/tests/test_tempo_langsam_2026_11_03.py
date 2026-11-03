# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl

PC = "Ministral 3 8B|Radeon|ministral-8b.gguf"


@pytest.fixture(autouse=True)
def leer():
    _leeren()
    yield
    _leeren()


def _leeren():
    kl._tempo_normal.clear()
    kl._tempo_zuletzt.clear()
    kl._tempo_langsam.clear()
    kl._tempo_datei[:] = [None, False, 0.0]


def _uhr():
    t = [1000.0]
    return t, (lambda: t[0])


def _schreiben(tempo: float, n: int = 150) -> dict:
    return {"predicted_n": n, "predicted_ms": n * 1000.0 / tempo}


def test_slow_writing_after_normal_writing_is_reported_and_fades():
    t, jetzt = _uhr()
    assert kl.gerade_langsam(jetzt=jetzt) is None
    for _ in range(kl.TEMPO_NORMAL_MIN):
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is False
    kl.tempo_beobachten(PC, _schreiben(5.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is True
    t[0] += kl.TEMPO_GILT_S + 1
    assert kl.gerade_langsam(jetzt=jetzt) is None
    kl.tempo_beobachten(PC, _schreiben(38.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is False


def test_hours_of_slow_writing_never_become_the_new_normal():
    t, jetzt = _uhr()
    for _ in range(10):
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt)
    for _ in range(200):
        t[0] += 60
        kl.tempo_beobachten(PC, _schreiben(5.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is True and min(kl._tempo_normal[PC]) >= 39


def test_a_device_that_became_slower_for_good_learns_its_new_normal_after_a_day():
    t, jetzt = _uhr()
    w = [1_700_000_000.0]
    for _ in range(10):
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt, wand=lambda: w[0])
    for _ in range(26):
        t[0] += 60; w[0] += 3600
        kl.tempo_beobachten(PC, _schreiben(15.0), jetzt=jetzt, wand=lambda: w[0])
    assert kl.gerade_langsam(jetzt=jetzt) is False and max(kl._tempo_normal[PC]) < 16
    _leeren()
    for _ in range(10):
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt, wand=lambda: w[0])
    for i in range(kl.TEMPO_NEU_LERNEN_N + 5):
        w[0] += 3600
        kl.tempo_beobachten(PC, _schreiben(40.0 if i == 10 else 15.0), jetzt=jetzt, wand=lambda: w[0])
    assert kl.gerade_langsam(jetzt=jetzt) is True


def test_two_calls_side_by_side_are_not_measured():
    s = kl.KiServer.__new__(kl.KiServer)
    s._fluege, s._flug_n, s._flug_lock = {}, 0, __import__("threading").Lock()
    a = s._flug_start()
    assert s._flug_ende(a) is True
    a, b = s._flug_start(), s._flug_start()
    assert s._flug_ende(b) is False and s._flug_ende(a) is False
    a = s._flug_start()
    b = s._flug_start()
    assert s._flug_ende(a) is False
    c = s._flug_start()
    assert s._flug_ende(c) is False and s._flug_ende(b) is False
    assert s._flug_ende(0) is False and s._flug_ende(999) is False


def test_short_outputs_and_broken_timings_do_not_count():
    t, jetzt = _uhr()
    for _ in range(kl.TEMPO_NORMAL_MIN):
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt)
    kl.tempo_beobachten(PC, _schreiben(2.0, n=5), jetzt=jetzt)
    kl.tempo_beobachten(PC, {"predicted_n": "x"}, jetzt=jetzt)
    kl.tempo_beobachten(None, _schreiben(1.0), jetzt=jetzt)
    kl.tempo_beobachten(PC, None, jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is False


def test_the_normal_survives_a_restart_and_a_broken_file_counts_as_empty(tmp_path):
    t, jetzt = _uhr()
    datei = tmp_path / kl.TEMPO_DATEI
    kl.tempo_datei_setzen(datei)
    for _ in range(kl.TEMPO_NORMAL_MIN):
        t[0] += kl.TEMPO_SCHREIBEN_S + 1
        kl.tempo_beobachten(PC, _schreiben(40.0), jetzt=jetzt)
    assert json.loads(datei.read_text(encoding="utf-8"))["normal"][PC]
    _leeren()
    kl.tempo_datei_setzen(datei)
    kl.tempo_beobachten(PC, _schreiben(5.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is True
    datei.write_text("{kaputt", encoding="utf-8")
    _leeren()
    kl.tempo_datei_setzen(datei)
    kl.tempo_beobachten(PC, _schreiben(5.0), jetzt=jetzt)
    assert kl.gerade_langsam(jetzt=jetzt) is None


def test_the_program_reports_slow_writing_like_a_busy_card(monkeypatch):
    import grafik_last
    import rechenarbeit
    ra = rechenarbeit.Rechenarbeit.__new__(rechenarbeit.Rechenarbeit)
    monkeypatch.setattr(ra, "_urteil_bereit", lambda: True, raising=False)
    monkeypatch.setattr(ra, "_tempo", lambda: 20.0, raising=False)
    monkeypatch.setattr(ra, "_modell", lambda: "Ministral 3 8B", raising=False)
    monkeypatch.setattr(ra, "_kopie", lambda: False, raising=False)
    ra._uebersetzen = None
    for belegt, langsam, erwartet in ((None, None, None), (False, None, "frei"), (False, True, "belegt"), (True, False, "belegt"),
                                      (None, False, "frei"), (None, True, "belegt")):
        monkeypatch.setattr(grafik_last, "belegt_sofort", lambda b=belegt: b)
        monkeypatch.setattr(kl, "gerade_langsam", lambda l=langsam: l)
        assert ra._leistung().get("karte") == erwartet
