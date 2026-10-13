# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ki_laufzeit as kl
from test_ki_laufzeit import _FakeProc, _ordner_mit_dateien, _Resp


def _server(tmp_path, *, plaetze=4, procs=None, gesehen=None, ende_mit_reuse=False):
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs = [] if procs is None else procs
    gesehen = [] if gesehen is None else gesehen

    def popen(args, **kw):
        p = _FakeProc(args, **kw)
        if ende_mit_reuse and "--cache-reuse" in args:
            p._code = 1
        procs.append(p)
        return p

    def urlopen(req, timeout=0):
        if req.full_url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        if req.full_url.endswith("/props"):
            return _Resp(json.dumps({"total_slots": plaetze}).encode())
        gesehen.append(json.loads(req.data.decode("utf-8")))
        return _Resp(json.dumps({"choices": [{"message": {"content": "Ja."}}], "usage": {}}).encode())

    s = kl.KiServer(o, popen=popen, urlopen=urlopen, schlafen=lambda _s: None, port_finder=lambda: 18571)
    s.start(wahl)
    return s, procs, gesehen


def test_without_own_places_no_request_names_a_place(tmp_path):
    s, procs, gesehen = _server(tmp_path, plaetze=4)
    assert "-np" not in procs[0].args and s.plaetze == 0
    s.frage([{"role": "user", "content": "Wie hoch ist der Großglockner?"}], zusatz="Auszug")
    s.frage([{"role": "user", "content": "Abschnitt"}], system="Vertiefe.", platz=kl.SLOT_HINTERGRUND)
    assert all("id_slot" not in b for b in gesehen) and all(b["cache_prompt"] is True for b in gesehen)
    s.stop()


def test_the_chat_server_reuses_equal_pieces_and_steps_keep_their_place(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "plaetze_fuer", lambda wahl: 4)
    s, procs, gesehen = _server(tmp_path)
    assert "--cache-reuse" in procs[0].args and s.plaetze == 4
    s.frage([{"role": "user", "content": "Wie hoch ist der Großglockner?"}], zusatz="Auszug")
    s.frage([{"role": "user", "content": "Satz 1"}], system="Prüfe.", zusatz="Auszug")
    s.frage([{"role": "user", "content": "Abschnitt"}], system="Vertiefe.", platz=kl.SLOT_HINTERGRUND)
    assert [b["id_slot"] for b in gesehen] == [kl.SLOT_ANTWORT, 3, 3]
    assert all(b["cache_prompt"] is True for b in gesehen)
    s.stop()


def test_a_server_with_one_place_gets_everything_there_and_one_without_props_none(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "plaetze_fuer", lambda wahl: 1)
    s, _p, gesehen = _server(tmp_path / "a", plaetze=1)
    s.frage([{"role": "user", "content": "x"}], platz=kl.SLOT_HINTERGRUND)
    assert gesehen[-1]["id_slot"] == 0
    s.stop()
    monkeypatch.setattr(kl, "plaetze_fuer", lambda wahl: 0)
    s, _p, gesehen = _server(tmp_path / "b", plaetze=0)
    s.frage([{"role": "user", "content": "x"}])
    assert "id_slot" not in gesehen[-1]
    s.stop()


def test_a_runtime_without_the_switch_starts_again_without_it(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "_OHNE_CACHE_REUSE", set())
    s, procs, _g = _server(tmp_path, ende_mit_reuse=True)
    assert len(procs) == 2 and "--cache-reuse" in procs[0].args and "--cache-reuse" not in procs[1].args and s.laeuft()
    s.stop()


def test_embedding_and_scoring_servers_stay_as_they_were(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs = []
    s = kl.KiServer(o, popen=lambda a, **kw: procs.append(_FakeProc(a, **kw)) or procs[-1],
                    urlopen=lambda req, timeout=0: _Resp(b'{"status":"ok"}'), schlafen=lambda _s: None, port_finder=lambda: 18572)
    s.start(wahl, embedding=True)
    assert "--cache-reuse" not in procs[0].args and s.plaetze == 0
    s.stop()


def test_embedding_and_scoring_keep_no_answers_in_memory_the_chat_model_does(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "_OHNE_CACHE_RAM", set())
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs = []
    s = kl.KiServer(o, popen=lambda a, **kw: procs.append(_FakeProc(a, **kw)) or procs[-1],
                    urlopen=lambda req, timeout=0: _Resp(b'{"status":"ok"}'), schlafen=lambda _s: None, port_finder=lambda: 18573)
    for art in ({"embedding": True}, {"bewerten": True}, {}):
        s.start(wahl, **art)
        s.stop()
    cram = [p.args[p.args.index("--cache-ram") + 1] if "--cache-ram" in p.args else None for p in procs]
    assert cram == ["0", "0", None]


def test_a_runtime_without_cache_ram_starts_again_without_it(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "_OHNE_CACHE_RAM", set())
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs = []

    def popen(args, **kw):
        p = _FakeProc(args, **kw)
        if "--cache-ram" in args:
            p._code = 1
        procs.append(p)
        return p
    s = kl.KiServer(o, popen=popen, urlopen=lambda req, timeout=0: _Resp(b'{"status":"ok"}'), schlafen=lambda _s: None, port_finder=lambda: 18574)
    s.start(wahl, embedding=True)
    assert len(procs) == 2 and "--cache-ram" in procs[0].args and "--cache-ram" not in procs[1].args and s.laeuft()
    s.stop()


def test_a_card_with_room_gets_own_memory_per_place_and_falls_back_when_the_runtime_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "plaetze_fuer", lambda wahl: 2)
    s, procs, _g = _server(tmp_path / "a", plaetze=2)
    a = procs[0].args
    assert a[a.index("-np") + 1] == "2" and "--no-kv-unified" in a and int(a[a.index("-c") + 1]) == 2 * s.wahl.modell.kontext
    s.stop()
    procs2: list = []
    real = kl.KiServer.start

    def popen_ohne_plaetze(args, **kw):
        p = _FakeProc(args, **kw)
        if "-np" in args:
            p._code = 1
        procs2.append(p)
        return p
    o, wahl = _ordner_mit_dateien(tmp_path / "b")
    s2 = kl.KiServer(o, popen=popen_ohne_plaetze, urlopen=lambda req, timeout=0: _Resp(b'{"status":"ok"}'), schlafen=lambda _s: None, port_finder=lambda: 18572)
    s2.start(wahl)
    assert len(procs2) == 2 and "-np" in procs2[0].args and "-np" not in procs2[1].args and s2.laeuft()
    s2.stop()
    kl._OHNE_PLAETZE.clear()


def test_slots_are_off_until_proven_on_the_pc():
    g = type("G", (), {"kennung": "X", "name": "Karte", "gesamt_mib": 0, "eigenstaendig": True, "frei_mib": 16000})()
    assert kl.PLAETZE_AN is False and kl.plaetze_fuer(type("W", (), {"modell": kl.MODELLE["14B"], "geraet": g})()) == 0


def test_slots_are_only_given_when_the_other_models_keep_their_room(monkeypatch):
    monkeypatch.setattr(kl, "PLAETZE_AN", True)
    m = kl.MODELLE["14B"]
    andere = kl.EMBEDDING.braucht_mib + kl.BEWERTUNG.braucht_mib + 2 * kl.RESERVE_MIB

    class G:
        kennung, name, gesamt_mib, eigenstaendig = "X", "Karte", 0, True

    def mit(frei):
        g = G(); g.frei_mib = frei
        return kl.plaetze_fuer(type("W", (), {"modell": m, "geraet": g})())
    assert mit(m.braucht_mib + andere + m.kv_mib - 1) == 0
    assert mit(m.braucht_mib + andere + m.kv_mib) == 2
    assert mit(m.braucht_mib + andere + 5 * m.kv_mib) == kl.PLAETZE_MAX
