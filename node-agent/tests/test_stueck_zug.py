# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import queue
import random
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl
import modell_katalog as mk
import stueck_zug as sz
import stueckliste as sl

PAAR, KEY = b"\x01" * 8, b"\x02" * 32


class Leitung:

    def __init__(self, ziel: "queue.Queue[bytes]", verlust=0.0, seed=1):
        self.ziel, self.verlust, self.r = ziel, verlust, random.Random(seed)
        self.gesendet, self._halten = [], None

    def __call__(self, paket: bytes):
        self.gesendet.append(len(paket))
        if self.r.random() < self.verlust:
            return
        if self._halten is None and self.r.random() < 0.05:
            self._halten = paket
            return
        self.ziel.put(paket)
        if self._halten is not None:
            self.ziel.put(self._halten)
            self._halten = None


@pytest.fixture
def klein(monkeypatch):
    monkeypatch.setattr(sl, "STUECK", 64 * 1024)


def _paar(tmp_path, daten, verlust=0.0, falsch_ab=None):
    datei = tmp_path / "halter.gguf"
    quelle = bytearray(daten)
    if falsch_ab is not None:
        quelle[falsch_ab] ^= 0xFF
    datei.write_bytes(bytes(quelle))
    zum_halter, zum_lader = queue.Queue(), queue.Queue()
    hin, rueck = Leitung(zum_halter, verlust, 1), Leitung(zum_lader, verlust, 2)
    halter = sz.Halter(PAAR, KEY, datei, rueck, bytes_je_s=200 * 1024 * 1024)
    lader = sz.Lader(PAAR, KEY, hin, zum_lader, len(daten))
    ergebnis = {}
    t = threading.Thread(target=lambda: ergebnis.setdefault("halter", _laufen(halter, zum_halter)), daemon=True)
    t.start()
    return halter, lader, t, ergebnis, hin, rueck


def _laufen(halter, ein):
    try:
        return halter.laufen(ein)
    except sz.ZugFehler as exc:
        return exc


def test_a_file_arrives_complete_over_a_line_that_loses_ten_percent(tmp_path, klein):
    daten = random.Random(5).randbytes(3 * 64 * 1024 + 777)
    halter, lader, t, ergebnis, hin, rueck = _paar(tmp_path, daten, verlust=0.10)
    lader.begruessen()
    with sz.LaderStrom(lader, 0) as strom:
        empfangen = b""
        while len(empfangen) < len(daten):
            empfangen += strom.read(50_000)
    t.join(15)
    assert empfangen == daten and ergebnis["halter"] >= len(daten)
    assert max(hin.gesendet + rueck.gesendet) <= 1248


def test_resuming_in_the_middle_of_a_piece_gives_exactly_the_rest(tmp_path, klein):
    daten = random.Random(6).randbytes(2 * 64 * 1024 + 100)
    halter, lader, t, *_ = _paar(tmp_path, daten)
    lader.begruessen()
    with sz.LaderStrom(lader, 70_000) as strom:
        rest = strom.read(10_000_000)
        while len(rest) < len(daten) - 70_000:
            rest += strom.read(10_000_000)
    assert rest == daten[70_000:]


def test_a_wrong_piece_from_a_holder_is_cut_out_by_the_piece_list_and_the_server_finishes(tmp_path, klein, monkeypatch):
    daten = random.Random(7).randbytes(3 * 64 * 1024)
    p = mk.Paket(kennung="t", name="Probe", datei="probe.gguf", url="https://unser.invalid/probe.gguf", sha256=hashlib.sha256(daten).hexdigest(),
                 groesse=len(daten))
    liste = b"".join(hashlib.sha256(daten[i:i + 64 * 1024]).digest() for i in range(0, len(daten), 64 * 1024))
    halter, lader, t, *_ = _paar(tmp_path, daten, falsch_ab=64 * 1024 + 5)
    lader.begruessen()
    ziel = tmp_path / "m" / p.datei
    with pytest.raises(kl.KiError) as e:
        kl._herunterladen(p, p.url, ziel, fortschritt=None, oeffner=lambda req, timeout: sz.LaderStrom(lader, 0), liste=liste)
    assert e.value.code == "KI_STUECK"
    teil = ziel.with_name(ziel.name + ".teil")
    assert teil.stat().st_size == 64 * 1024 and teil.read_bytes() == daten[:64 * 1024]

    class Resp:
        def __init__(self, b, status):
            self.b, self.status, self.pos = b, status, 0

        def read(self, n=-1):
            out = self.b[self.pos:self.pos + (n if n > 0 else len(self.b))]
            self.pos += len(out)
            return out

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def server(req, timeout):
        ab = int(req.headers["Range"].split("=")[1].rstrip("-"))
        assert ab == 64 * 1024
        return Resp(daten[ab:], 206)

    assert kl._herunterladen(p, p.url, ziel, fortschritt=None, oeffner=server, liste=liste) == ziel and ziel.read_bytes() == daten


def test_a_silent_holder_ends_after_the_greeting_and_a_stranger_gets_nothing(tmp_path, klein, monkeypatch):
    monkeypatch.setattr(sz, "BEGRUESSUNG_S", 0.8)
    monkeypatch.setattr(sz, "BEGRUESSUNG_ZEITEN", (0.0, 0.3, 0.6))
    gesendet = []
    lader = sz.Lader(PAAR, KEY, gesendet.append, queue.Queue(), 1000)
    with pytest.raises(sz.ZugFehler):
        lader.begruessen()
    assert len(gesendet) <= 8 and all(len(x) <= 64 for x in gesendet)
    fremd = sz.Seite(PAAR, b"\x09" * 32, halter=False)
    echt = sz.Seite(PAAR, KEY, halter=True)
    assert echt.lesen(fremd.bauen(sz.WUNSCH, b"x" * 72)) is None
    assert echt.lesen(b"KW" + b"\x00" * 60) is None


def test_the_holder_keeps_to_its_speed_limit(tmp_path, klein):
    daten = random.Random(8).randbytes(64 * 1024)
    zum_halter, zum_lader = queue.Queue(), queue.Queue()
    uhr = [0.0]
    pausen = []

    def schlafen(s):
        pausen.append(s)
        uhr[0] += s

    datei = tmp_path / "h.gguf"
    datei.write_bytes(daten)
    halter = sz.Halter(PAAR, KEY, datei, zum_lader.put, bytes_je_s=64 * 1024, uhr=lambda: uhr[0], schlafen=schlafen)
    l_seite = sz.Seite(PAAR, KEY, halter=False)
    zum_halter.put(l_seite.bauen(sz.HALLO))
    bitmap = bytes([0xFF] * 7) + bytes(57)
    zum_halter.put(l_seite.bauen(sz.WUNSCH, sz.WUNSCH_KOPF.pack(0, 0) + bitmap))
    zum_halter.put(l_seite.bauen(sz.FERTIG))
    assert halter.laufen(zum_halter) == len(daten)
    assert 0.9 <= uhr[0] <= 1.2


def test_a_holder_sending_empty_packets_cannot_keep_the_loader_in_a_loop(tmp_path, klein, monkeypatch):
    monkeypatch.setattr(sz, "STILL_S", 0.6)
    zum_lader = queue.Queue()
    boese = sz.Seite(PAAR, KEY, halter=True)
    gesendet = []

    def senden(paket):
        gesendet.append(paket)
        p = boese.lesen(paket)
        if p is not None and p[0] == sz.WUNSCH:
            s, start = sz.WUNSCH_KOPF.unpack(p[1][:sz.WUNSCH_KOPF.size])
            for i in range(start, start + 4):
                zum_lader.put(boese.bauen(sz.DATEN, sz.DATEN_KOPF.pack(s, i)))
                zum_lader.put(boese.bauen(sz.DATEN, sz.DATEN_KOPF.pack(s, i) + b"x"))

    lader = sz.Lader(PAAR, KEY, senden, zum_lader, 3 * sl.STUECK)
    strom = sz.LaderStrom(lader, 0)
    fertig = {}
    t = threading.Thread(target=lambda: fertig.setdefault("r", _lesen(strom)), daemon=True)
    t.start()
    t.join(10)
    assert not t.is_alive() and isinstance(fertig["r"], sz.ZugFehler)
    assert len(gesendet) < 200


def _lesen(strom):
    try:
        return strom.read(1 << 20)
    except sz.ZugFehler as exc:
        return exc


def test_a_recorded_packet_does_not_work_twice_but_swapped_packets_still_arrive():
    lader = sz.Seite(PAAR, KEY, halter=False)
    halter = sz.Seite(PAAR, KEY, halter=True)
    p1, p2, p3 = (lader.bauen(sz.WUNSCH, bytes([i]) * 72) for i in range(3))
    assert halter.lesen(p2) is not None and halter.lesen(p1) is not None
    assert halter.lesen(p2) is None and halter.lesen(p1) is None
    assert halter.lesen(p3) is not None
    assert halter.lesen(sz.Seite(PAAR, KEY, halter=False).bauen(sz.WUNSCH, b"x" * 72)) is None
    for _ in range(sz.WIEDERHOLUNG_FENSTER + 10):
        letzte = lader.bauen(sz.HALLO)
    assert halter.lesen(letzte) is not None and len(halter._gesehen) <= 2 * sz.WIEDERHOLUNG_FENSTER + 1
