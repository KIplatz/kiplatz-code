# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import io
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ki_laufzeit as kl
import wikipedia
from test_bau_30a_wikipedia_vektoren import _db
from test_wiki_index_2026_10_17 import _gehalten, _wiki


def test_einleitung_und_namenspruefung_gehen_ueber_den_leser_und_warten_nie_auf_den_schreiber(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    db.wortzahl_anlegen()
    w = _wiki(tmp_path, db)
    frage = "Wie hoch ist das Allalinhorn?"
    frei, t = _gehalten(db)
    try:
        s = time.monotonic()
        assert [x.quelle.titel for x in w.einleitung(frage)] == [f"Wikipedia: Allalinhorn ({wikipedia.LIZENZ})"]
        assert w.namen_bekannt(["Allalinhorn", "Zwergstadt"]) == {"Allalinhorn"}
        assert w.unbekannte_namen("Wer ist Josefine Tarsberger?") == ["Josefine Tarsberger"]
        assert time.monotonic() - s < 1.5
        assert db.leser() is db.leser() and db.leser() is not db and db.leser()._lock is not db._lock
    finally:
        frei.set()
        t.join(5)


def test_eine_laufende_suche_haelt_die_einleitung_hoechstens_kurz_auf(tmp_path, monkeypatch):
    monkeypatch.setattr(wikipedia, "NAMEN_WARTEN_S", 0.3)
    db = _db(tmp_path / "w.sqlite")
    w = _wiki(tmp_path, db)
    frei, t = _gehalten(db.leser())
    try:
        s = time.monotonic()
        assert w.einleitung("Wie hoch ist das Allalinhorn?") == []
        assert time.monotonic() - s < 2
    finally:
        frei.set()
        t.join(5)
    assert len(w.einleitung("Wie hoch ist das Allalinhorn?")) == 1


def test_hashes_sicherstellen_gibt_die_sperre_zwischen_den_stapeln_frei(tmp_path, monkeypatch):
    monkeypatch.setattr(wikipedia, "HASH_SCHRITT", 1)
    db = _db(tmp_path / "w.sqlite")
    with db._lock:
        db._c.execute("DELETE FROM abschnitt_hash")
        n = db._c.execute("SELECT count(*) FROM abschnitt").fetchone()[0]
    assert n >= 3 and not db.hashes_vollstaendig()
    bekommen, fertig = [], threading.Event()

    def beobachter():
        while not fertig.is_set():
            if db._lock.acquire(timeout=0.005):
                bekommen.append(time.monotonic())
                db._lock.release()
            time.sleep(0.001)

    b = threading.Thread(target=beobachter, daemon=True)
    b.start()
    neu = db.hashes_sicherstellen(hoechstens=None)
    fertig.set()
    b.join(5)
    assert neu == n and db.hashes_vollstaendig() and db.hash_index_da()
    assert len(bekommen) >= 1


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _paket(data: bytes, name: str) -> kl.Paket:
    return kl.Paket(kennung=name, name=name, datei=name, url="https://beispiel.invalid/" + name, sha256=hashlib.sha256(data).hexdigest(), groesse=len(data))


def test_zwei_verschiedene_dateien_laden_nebeneinander_dieselbe_nur_einmal(tmp_path):
    gross, klein = b"g" * 200_000, b"k" * 1000
    halt, laeuft = threading.Event(), threading.Event()

    def oeffner_gross(req, timeout):
        laeuft.set()
        halt.wait(10)
        return _Resp(gross)

    t = threading.Thread(target=lambda: kl.herunterladen(_paket(gross, "chat.gguf"), tmp_path / "chat.gguf", oeffner=oeffner_gross), daemon=True)
    t.start()
    assert laeuft.wait(5)
    s = time.monotonic()
    out = kl.herunterladen(_paket(klein, "bedeutung.gguf"), tmp_path / "bedeutung.gguf", oeffner=lambda req, timeout: _Resp(klein))
    assert out.read_bytes() == klein and time.monotonic() - s < 2
    halt.set()
    t.join(5)
    assert (tmp_path / "chat.gguf").read_bytes() == gross
    zaehler = []
    halt2, laeuft2 = threading.Event(), threading.Event()

    def oeffner_zaehlt(req, timeout):
        zaehler.append(1)
        laeuft2.set()
        halt2.wait(10)
        return _Resp(klein)

    t2 = threading.Thread(target=lambda: kl.herunterladen(_paket(klein, "x.gguf"), tmp_path / "x.gguf", oeffner=oeffner_zaehlt), daemon=True)
    t2.start()
    assert laeuft2.wait(5)
    t3 = threading.Thread(target=lambda: kl.herunterladen(_paket(klein, "x.gguf"), tmp_path / "x.gguf", oeffner=oeffner_zaehlt), daemon=True)
    t3.start()
    time.sleep(0.2)
    halt2.set()
    t2.join(5)
    t3.join(5)
    assert zaehler == [1] and (tmp_path / "x.gguf").read_bytes() == klein
