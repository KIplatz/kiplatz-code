# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import app_web
import community
import quellen_stand


class _Rechen:
    phase = "prueft_selbst"
    vorrang = threading.Event()


class _Community:
    def __init__(self, code):
        self.code = code

    def websuche(self, frage, n=8, **kw):
        if kw.get("nur_gemerkt"):
            return None
        raise community.CommunityError(self.code, "vom Server")


class _Api:
    _websuche = app_web.Api._websuche
    _mess_suche_budget = app_web.Api._mess_suche_budget

    def __init__(self, code):
        self._core, self._rechen, self._community = None, _Rechen(), _Community(code)
        self._mess_bremse = True
        self._mess_suche_zuletzt, self._mess_suchen, self._mess_suche_gemeldet = 0.0, 0, False
        self._mess_uhr, self._mess_schlafen = (lambda: 1000.0), (lambda s: None)
        self._mess_geschont = False


@pytest.mark.parametrize("code", ["COMMUNITY_SUCHE_GESCHONT", "COMMUNITY_SUCHE_GEBREMST"])
def test_a_check_search_the_server_spares_or_brakes_does_not_count(code):
    api = _Api(code)
    with pytest.raises(app_core.AppError):
        api._websuche("Wie hoch ist die Mehrwertsteuer auf Lebensmittel in Österreich?")
    assert api._mess_geschont is True


def test_any_other_search_failure_still_counts():
    api = _Api("COMMUNITY_SUCHE_AUS")
    with pytest.raises(app_core.AppError):
        api._websuche("Wie bekomme ich einen neuen Reisepass?")
    assert api._mess_geschont is False


def test_the_card_names_the_last_round_first_and_the_daily_check_by_its_name():
    html = (Path(app_web.__file__).parent / "webapp" / "index.html").read_text(encoding="utf-8")
    i = html.index("function zeichnePruefstand")
    teil = html[i:i + 6000]
    assert "p.letzte_runde" in teil and teil.index("`Letzte Prüfrunde") < teil.index("`Tagesprüfung")
    assert "keine Tagesfrage falsch" in teil


def test_the_upload_keeps_the_round_and_logs_the_devices_own_paths():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    i = quelle.index("r = b.get(\"runde\") if isinstance(b.get(\"runde\"), dict) else None")
    teil = quelle[i:i + 2500]
    assert "pruefrunde_letzte=" in teil and "Wege {sum(1 for v in wege.values() if v)} von {len(wege)}" in teil


def test_the_calendar_line_splits_nationwide_and_regional_days():
    t = quellen_stand._kalender(date(2026, 10, 26))["text"]
    assert "9 DE bundesweit und 11 in einzelnen Ländern" in t and "CH in allen Kantonen" in t


def test_wikipedia_is_named_only_as_the_source_of_the_word_list():
    class _W:
        def darf_halten(self):
            return True

        def zustand(self):
            return {"ausgabe": "20261004", "artikel": 2_788_882, "phase": "fertig"}

        def bereit(self):
            return True

        def belegt(self):
            return False
    assert quellen_stand._wikipedia(_W())["text"] == "Wikipedia: 2.788.882 Artikel, Stand 04.10.2026; nur Quelle der Wortliste, keine Antwortquelle."
