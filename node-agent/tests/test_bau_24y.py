# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web


class _Api:
    _UPDATE_SPERRE = threading.Lock()
    _update_holen = app_web.Api._update_holen

    def __init__(self, ergebnisse):
        self.laeufe = 0
        self._ergebnisse = list(ergebnisse)

    def _update_holen_einmal(self):
        self.laeufe += 1
        time.sleep(0.3)
        r = self._ergebnisse.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_two_checks_at_once_fetch_once():
    api = _Api([("aktualisiert", "Neue Version")])
    out = []
    ts = [threading.Thread(target=lambda: out.append(api._update_holen())) for _ in range(2)]
    for t in ts:
        t.start()
        time.sleep(0.05)
    for t in ts:
        t.join(5)
    assert api.laeufe == 1 and out == [("aktualisiert", "Neue Version")] * 2


def test_when_the_first_fails_the_second_tries_itself():
    api = _Api([OSError("weg"), ("aktuell", "")])
    out, fehler = [], []

    def erster():
        try:
            api._update_holen()
        except OSError as exc:
            fehler.append(exc)
    t1 = threading.Thread(target=erster)
    t1.start()
    time.sleep(0.05)
    t2 = threading.Thread(target=lambda: out.append(api._update_holen()))
    t2.start()
    t1.join(5)
    t2.join(5)
    assert fehler and out == [("aktuell", "")] and api.laeufe == 2


def test_the_wikipedia_vectors_get_a_turn_beside_the_background_work():
    class Rechen:
        phase = "vertieft"
        vorrang = False

        def vorrang_aktiv(self):
            return self.vorrang

    class A:
        _wiki_karte_frei = app_web.Api._wiki_karte_frei
    a = A()
    a._rechen = Rechen()
    for phase in ("vertieft", "vertieft_prueft", "prueft", "bereit", "wartet", "themen", "aus"):
        a._rechen.phase = phase
        assert a._wiki_karte_frei(), phase
    for phase in ("antwortet", "laden", "hitze", "rechnet"):
        a._rechen.phase = phase
        assert not a._wiki_karte_frei(), phase
    a._rechen.phase, a._rechen.vorrang = "vertieft", True
    assert not a._wiki_karte_frei()


def test_one_after_the_other_both_ask_the_server():
    api = _Api([("aktuell", ""), ("aktuell", "")])
    api._update_holen()
    api._update_holen()
    assert api.laeufe == 2
