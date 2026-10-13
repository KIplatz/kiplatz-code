# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen
from test_app_web import _api


class _Suche:
    def __init__(self, dauer: float = 0.0) -> None:
        self.aufrufe: list[list[str]] = []
        self.dauer = dauer
        self.faeden: list[str] = []

    def suche_runde(self, anfragen, frage, **kw):
        self.aufrufe.append(list(anfragen))
        self.faeden.append(threading.current_thread().name)
        time.sleep(self.dauer)
        e = nachschauen.Ergebnis("suche", "Mur", "https://example.org/mur", "Die Mur ist 464 Kilometer lang.", "2026-10-09T00:00:00Z", "im Internet")
        return [e], ["https://example.org/mur"], "im Internet"


def _lauf() -> dict:
    lauf = {"runde": 0, "gesucht": [], "gelesen": set()}
    app_web._SUCHLAUF.stand = lauf
    return lauf


def test_the_search_runs_beside_the_answer_and_is_picked_up_without_a_second_search(tmp_path):
    api, _fake, _ = _api(tmp_path)
    suche = _Suche(dauer=0.3)
    api._nachschauer = suche
    lauf = _lauf()
    try:
        t0 = time.monotonic()
        api._suche_nebenher("Wie lang ist die Mur?", None)
        assert time.monotonic() - t0 < 0.2
        assert "nebenher" in lauf and lauf["gesucht"] == []
        api._suche_nebenher("Wie lang ist die Mur?", None)
        lauf["runde"] = 1
        treffer, _satz = api._nachschauen("Wie lang ist die Mur?", [], frisch=True)
        assert len(suche.aufrufe) == 1 and suche.faeden == ["suche-nebenher"]
        assert treffer and "464 Kilometer" in treffer[0].text
        assert "nebenher" not in lauf and lauf["gesucht"] == suche.aufrufe[0]
        assert app_web.nebenher_satz(lauf) == ""
    finally:
        app_web._SUCHLAUF.stand = None


def test_a_search_beside_without_pages_falls_back_to_the_usual_way(tmp_path):
    api, _fake, _ = _api(tmp_path)

    class _Leer(_Suche):
        def suche_runde(self, anfragen, frage, **kw):
            if not self.aufrufe:
                self.aufrufe.append(list(anfragen))
                return [], [], "im Internet"
            return super().suche_runde(anfragen, frage, **kw)
    suche = _Leer()
    api._nachschauer = suche
    api._suchwoerter = lambda nachrichten, frage, **kw: ["Mur Länge Kilometer"] if not kw.get("ohne_modell") else ["Mur lang"]
    lauf = _lauf()
    try:
        api._suche_nebenher("Wie lang ist die Mur?", None)
        lauf["runde"] = 1
        treffer, _satz = api._nachschauen("Wie lang ist die Mur?", [], frisch=True)
        assert suche.aufrufe == [["Mur lang"], ["Mur Länge Kilometer"]]
        assert treffer and "464 Kilometer" in treffer[0].text
        assert app_web.nebenher_satz(lauf).endswith("ohne brauchbare Seite.")
    finally:
        app_web._SUCHLAUF.stand = None


def test_an_unused_search_is_named_in_the_delivery_note_and_nothing_is_kept(tmp_path):
    api, _fake, _ = _api(tmp_path)
    suche = _Suche()
    api._nachschauer = suche
    gemerkt: list = []
    api._nachgeschaut_merken = gemerkt.append
    lauf = _lauf()
    try:
        api._suche_nebenher("Wie lang ist die Mur?", None)
        satz = app_web.nebenher_satz(lauf)
        assert satz.startswith("Nebenher wurde im Internet nach „") and "gebraucht wurde es nicht" in satz
        lauf["nebenher"]["holen"]()
        assert gemerkt == []
    finally:
        app_web._SUCHLAUF.stand = None


def test_no_search_beside_once_this_answer_has_searched_or_a_later_round_runs(tmp_path):
    api, _fake, _ = _api(tmp_path)
    api._nachschauer = _Suche()
    lauf = _lauf()
    try:
        lauf["gesucht"] = ["Mur Länge"]
        api._suche_nebenher("Wie lang ist die Mur?", None)
        assert "nebenher" not in lauf
        lauf["gesucht"], lauf["runde"] = [], 1
        api._suche_nebenher("Wie lang ist die Mur?", None)
        assert "nebenher" not in lauf
    finally:
        app_web._SUCHLAUF.stand = None


def test_only_measure_questions_search_beside(tmp_path):
    assert app_web.massfrage("Wie lang ist die Mur?") and app_web.massfrage("Wann wurde Graz gegründet?")
    assert app_web.massfrage("Wie viele Einwohner hat Linz?")
    assert not app_web.massfrage("Erzähl mir etwas über die Mur.") and not app_web.massfrage("Schreib mir ein Gedicht über Graz.")
