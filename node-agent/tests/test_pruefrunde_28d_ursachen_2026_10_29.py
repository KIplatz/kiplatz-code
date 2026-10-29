# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege
import namenpruefung
import wissen


class _Liste(namenpruefung.Namenspruefung):

    def __init__(self, de: set[str], ganz: set[str] = frozenset()) -> None:
        self.de, self.ganz = de, ganz

    def hat_wortzahl(self) -> bool:
        return True

    @staticmethod
    def _woerter(text: str) -> list[str]:
        return wissen.woerter(text)

    def _df(self, wort: str) -> int:
        return 1 if wort in self.de else 0

    def artikel_zu(self, titel: str):
        return None

    def _ganz_bekannt(self, wort: str) -> bool:
        return wort.lower() in self.ganz


def _liste() -> _Liste:
    de = {s for w in ("Fluss Bundesland Spitze Klöppeln Klamm Glanegg Moosbrand Klaus Mauer Berlin Geschirr Spüler Ablauf Schlauch "
                      "Bücher Autor Vorarlberg tief entspringt liegt").split() for s in wissen.woerter(w)}
    return _Liste(de, ganz={"berliner", "vorarlberger"})


def test_ein_unzerlegbares_wort_ist_ein_name_eine_zusammensetzung_nicht():
    li = _liste()
    assert li.unbekannte_namen("Welcher Fluss entspringt am Zelmkogel?") == ["Zelmkogel"]
    assert li.unbekannte_namen("Wie repariere ich den Geschirrspülerablaufschlauch?") == []


def test_ein_name_nur_ueber_den_gekuerzten_stamm_ist_unsicher():
    li = _liste()
    assert li.unbekannte_namen("Was ist eine Glanegger Spitze beim Klöppeln?") == []
    assert li.unsichere_namen("Was ist eine Glanegger Spitze beim Klöppeln?") == ["Glanegger Spitze"]
    assert li.unsichere_namen("Welche Bücher schrieb der Autor Klaus Moosbrandner?") == ["Klaus Moosbrandner"]
    assert li.unsichere_namen("Wann wurde die Berliner Mauer gebaut?") == []


def test_ein_rat_holt_keine_suche_fuer_unsichere_namen():
    assert app_web.wissensfrage("Wie tief ist die Edlwanger Klamm?")
    assert not app_web.wissensfrage("Wie lerne ich als Erwachsener Schwimmen?")


def test_bei_einer_frage_nach_einem_namen_ist_der_titel_aus_der_frage_kein_verweis():
    quellen = [("Säugetier", "Säugetiere sind Wirbeltiere. Sie säugen ihre Jungen mit Milch."),
               ("Wale", "Der Blauwal ist mit bis zu 33 Metern das größte Tier der Erde.")]
    satz = "Der Blauwal ist das größte Säugetier der Erde."
    assert belege.vermischt_ausloeser(satz, quellen) != []
    assert belege.vermischt_ausloeser(satz, quellen, "Welches ist das größte Säugetier der Erde?") == []


def test_die_suchbremse_zaehlt_die_zeit_auf_der_uhr():
    class _Api:
        _mess_suche_budget = app_web.Api._mess_suche_budget

    api = _Api()
    api._mess_suchen, api._mess_suche_gemeldet, api._mess_geschont, api._mess_gewartet = 0, False, False, 0.0
    api._mess_suche_zuletzt = 1.0
    uhr = {"t": 1.0}
    api._mess_uhr = lambda: uhr["t"]
    api._core = None

    def schlafen(s):
        import time
        time.sleep(0.01)
        uhr["t"] += s

    api._mess_schlafen = schlafen
    api._mess_suche_zuletzt = uhr["t"] - app_web.MESS_SUCHE_ABSTAND_S + 0.3
    faeden = [threading.Thread(target=api._mess_suche_budget, args=(None,)) for _ in range(4)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    assert api._mess_gewartet < 1.0
