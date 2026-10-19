# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wikipedia

from test_bau_24n import DOCS, bis_fertig, kopie, netz, teil_bytes
from test_bau_30a_wikipedia_vektoren import _db


class _Gemeinschaft:

    def __init__(self, db):
        self.db, self.aufrufe = db, []

    def wiki_vektoren_stand(self, **kw):
        self.aufrufe.append(bool(getattr(self.db, "hash_index_da", lambda: False)()))
        return {"gesucht": False, "scheiben": []}


def _wiki(tmp_path, db, gem=None) -> wikipedia.WikiKopie:
    w = wikipedia.WikiKopie(lambda: tmp_path / "wiki", freigabe_mb=lambda: 200_000, darf=lambda: True, gemeinschaft=(lambda: gem) if gem else None,
                            modell=lambda: "bedeutung-test", vektoren=lambda texte: [[1.0] * 4 for _ in texte], vektoren_bereit=lambda: True)
    w._db = db
    w._stand_setzen(fertig_ausgabe="20260920")
    return w


def _gehalten(db):
    los, frei = threading.Event(), threading.Event()

    def halten():
        with db._lock:
            los.set()
            frei.wait(30)

    t = threading.Thread(target=halten, daemon=True)
    t.start()
    los.wait(5)
    return frei, t


def test_eine_neu_eingelesene_kopie_kommt_nur_mit_index_in_gebrauch(tmp_path):
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]))
    bis_fertig(w)
    assert w.bereit() and w._db.hashes_vollstaendig()
    assert w._db.hash_index_da()


def test_eine_kopie_ohne_index_bekommt_ihn_bevor_sie_eine_scheibe_anfasst(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    assert db.hashes_vollstaendig() and not db.hash_index_da()
    gem = _Gemeinschaft(db)
    w = _wiki(tmp_path, db, gem)
    for _ in range(6):
        w._vektor_schritt()
    assert db.hash_index_da()
    assert gem.aufrufe and all(gem.aufrufe)


def test_ohne_index_holt_das_geraet_keine_scheibe(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    gem = _Gemeinschaft(db)
    w = _wiki(tmp_path, db, gem)
    assert w._gemeinschaft_schritt({"fertig_ausgabe": "20260920"}, anbieten=False) is None
    assert gem.aufrufe == []


def test_der_index_entsteht_ohne_die_sperre_der_kopie(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    frei, t = _gehalten(db)
    try:
        s = time.monotonic()
        db.hash_index_anlegen()
        assert time.monotonic() - s < 5
    finally:
        frei.set()
        t.join(5)
    assert db.hash_index_da()


def test_die_einleitung_wartet_nie_hinter_einer_belegten_kopie(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    w = _wiki(tmp_path, db)
    frage = "Wie hoch ist das Allalinhorn?"
    assert [t.quelle.titel for t in w.einleitung(frage)] == [f"Wikipedia: Allalinhorn ({wikipedia.LIZENZ})"]
    frei, t = _gehalten(db)
    try:
        s = time.monotonic()
        assert len(w.einleitung(frage)) == 1
        assert time.monotonic() - s < wikipedia.NAMEN_WARTEN_S
    finally:
        frei.set()
        t.join(5)
    assert len(w.einleitung(frage)) == 1
