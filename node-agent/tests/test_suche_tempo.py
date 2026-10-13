# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen as ns
from test_wissen import _Antwort

TEXT = "<html><head><title>{t}</title></head><body><p>Der Großglockner ist mit 3798 Metern der höchste Berg Österreichs und liegt in den Hohen Tauern.</p></body></html>"


def _suche(adressen):
    return lambda q, **kw: [{"titel": f"Seite {i}", "adresse": a, "text": "Großglockner 3798 Meter"} for i, a in enumerate(adressen)]


def _oeffner(langsam: set[str], warten_s: float):
    def oeffner(req, timeout=0):
        url = req.full_url
        if url.endswith("/robots.txt"):
            return _Antwort(url, b"", "text/plain")
        if any(url.startswith(x) for x in langsam):
            time.sleep(warten_s)
        return _Antwort(url, TEXT.format(t=url.split("/")[2]).encode("utf-8"))
    return oeffner


def test_a_slow_page_does_not_hold_up_the_round_when_enough_pages_are_read():
    adressen = [f"https://s{i}.example/glockner" for i in range(5)]
    n = ns.Nachschauer(suche_fn=_suche(adressen), seiten_oeffner=_oeffner({"https://s0.example"}, 5.0))
    t0 = time.monotonic()
    erg, gelesen, _ = n.suche_runde(["Großglockner Höhe"], "Wie hoch ist der Großglockner?", heute=date.today())
    dauer = time.monotonic() - t0
    assert dauer < ns.RUNDE_NACHLAUF_S + 1.5, dauer
    assert len(gelesen) >= 2 and "https://s0.example/glockner" not in gelesen
    assert any("3798" in e.text for e in erg)


def test_when_too_few_pages_are_readable_the_round_still_waits_up_to_its_limit(monkeypatch):
    monkeypatch.setattr(ns, "RUNDE_WARTEN_S", 2.0)
    adressen = [f"https://t{i}.example/glockner" for i in range(3)]
    n = ns.Nachschauer(suche_fn=_suche(adressen), seiten_oeffner=_oeffner({"https://t0.example", "https://t1.example"}, 0.8))
    erg, gelesen, _ = n.suche_runde(["Großglockner Höhe"], "Wie hoch ist der Großglockner?", heute=date.today())
    assert len(gelesen) == 3
