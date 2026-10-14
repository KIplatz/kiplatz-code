# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import app_web


class _Core:
    def __init__(self):
        self.zeilen = []

    def log(self, zeile):
        self.zeilen.append(zeile)


class _Rechen:
    phase = "prueft_selbst"
    vorrang = threading.Event()


class _Community:
    def __init__(self):
        self.suchen = []

    def websuche(self, frage, n=8, **kw):
        self.suchen.append(frage)
        return [{"titel": frage, "adresse": "https://x.example/1", "text": "t"}]


class _Api:
    _websuche = app_web.Api._websuche
    _mess_suche_budget = app_web.Api._mess_suche_budget

    def __init__(self):
        self._core, self._rechen, self._community = _Core(), _Rechen(), _Community()
        self._nacht_memo, self._memo_frage, self._memo_nutzen = {}, "m-w001", False
        self._mess_suche_zuletzt, self._mess_suchen, self._mess_suche_gemeldet = 0.0, 0, False
        self.uhr, self.geschlafen = 1000.0, []
        self._mess_uhr = lambda: self.uhr
        self._mess_schlafen = self._schlafen

    def _schlafen(self, s):
        self.geschlafen.append(s)
        self.uhr += s


def _log_zeilen(api):
    return [z for z in api._core.zeilen if "Internet-Suchen" in z]


def test_between_two_live_searches_the_night_waits_the_spacing(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda core, zeile: core.log(zeile))
    api = _Api()
    api._websuche("Dachstein Höhe")
    assert api.geschlafen == [] and api._mess_suchen == 1
    api._memo_frage = "m-w002"
    api._websuche("Großglockner Höhe")
    assert sum(api.geschlafen) == pytest.approx(app_web.MESS_SUCHE_ABSTAND_S) and api._community.suchen == ["Dachstein Höhe", "Großglockner Höhe"]
    assert max(api.geschlafen) <= 0.5


def test_after_the_night_limit_questions_run_without_search_and_it_is_logged_once(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda core, zeile: core.log(zeile))
    monkeypatch.setattr(app_web, "MESS_SUCHEN_NACHT_MAX", 2)
    api = _Api()
    api._websuche("eins")
    api.uhr += 100
    api._websuche("zwei")
    api.uhr += 100
    with pytest.raises(app_core.AppError) as e:
        api._websuche("drei")
    assert e.value.code == "SUCHE_GESCHONT"
    with pytest.raises(app_core.AppError):
        api._websuche("vier")
    assert api._community.suchen == ["eins", "zwei"] and len(_log_zeilen(api)) == 1
    assert api._nacht_memo.get("m-w001") and all("drei" not in str(k) for k in api._nacht_memo["m-w001"])


def test_the_persons_own_question_ends_the_wait_and_the_check_question_goes_without_search(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda core, zeile: core.log(zeile))
    api = _Api()
    api._websuche("eins")
    api._rechen.vorrang = threading.Event()
    api._rechen.vorrang.set()
    api._websuche("meine eigene Frage")
    assert api._mess_suchen == 1 and api._community.suchen[-1] == "meine eigene Frage"
    api._rechen.vorrang.clear()
    api._memo_frage = "m-w002"
    eigene = threading.Event()
    api._rechen.vorrang = eigene

    def schlafen(s):
        api.uhr += s
        eigene.set()
    api._mess_schlafen = schlafen
    with pytest.raises(app_core.AppError) as e:
        api._websuche("zwei")
    assert e.value.code == "SUCHE_GESCHONT" and api._community.suchen == ["eins", "meine eigene Frage"]


def test_outside_the_night_and_for_the_probe_there_is_no_budget(monkeypatch):
    monkeypatch.setattr(app_web, "MESS_SUCHEN_NACHT_MAX", 1)
    api = _Api()
    api._nacht_memo = None
    for i in range(5):
        api._websuche(f"frage {i}")
    assert len(api._community.suchen) == 5 and api._mess_suchen == 0
    api._nacht_memo, api._memo_nutzen = {"m-w001": {}}, True
    api._websuche("frage neu")
    assert len(api._community.suchen) == 6 and api._mess_suchen == 0


def test_the_night_start_resets_the_budget():
    assert "self._mess_suche_zuletzt, self._mess_suchen, self._mess_suche_gemeldet = 0.0, 0, False" in Path(app_web.__file__).read_text(encoding="utf-8").split("self._nacht_memo = {} if nacht else None", 1)[1][:400]
    assert app_web.MESS_SUCHE_ABSTAND_S >= 15 and app_web.MESS_SUCHEN_NACHT_MAX <= 500
    assert app_core.APP_BUILD >= "2026-10-14a"
