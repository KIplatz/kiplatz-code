# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ki_laufzeit as kl
from test_ki_laufzeit import _FakeProc, _ordner_mit_dateien, _Resp


def _starten(tmp_path, **art):
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs, gesendet = [], []

    def urlopen(req, timeout=0):
        if req.full_url.endswith("/v1/embeddings"):
            body = json.loads(req.data.decode("utf-8"))
            gesendet.append(body["input"])
            return _Resp(json.dumps({"data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(len(body["input"]))]}).encode())
        return _Resp(b'{"status":"ok"}')
    s = kl.KiServer(o, popen=lambda a, **kw: procs.append(_FakeProc(a, **kw)) or procs[-1], urlopen=urlopen,
                    schlafen=lambda _s: None, port_finder=lambda: 18590)
    s.start(wahl, **art)
    return s, procs, gesendet, wahl


def _wert(args, schalter):
    return args[args.index(schalter) + 1]


def test_the_meaning_model_has_one_place_so_each_cut_section_fits_its_memory(tmp_path):
    s, procs, gesendet, wahl = _starten(tmp_path, embedding=True)
    a = procs[0].args
    assert _wert(a, "-np") == "1"
    kontext = int(wahl.modell.kontext)
    assert int(_wert(a, "-c")) == kontext and int(_wert(a, "-ub")) == kontext
    lang = ["Oberösterreich " * 400, "一丁丂" * 900] * 8
    s.vektoren(lang)
    assert len(gesendet[0]) == 16
    assert all(len(t.encode("utf-8")) <= kontext - kl.VEKTOR_RESERVE for t in gesendet[0])
    s.stop()


def test_answer_and_scoring_servers_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(kl, "plaetze_fuer", lambda wahl: 0)
    for art in ({}, {"bewerten": True}):
        s, procs, _g, _w = _starten(tmp_path / str(len(art)), **art)
        assert "-np" not in procs[0].args
        s.stop()
