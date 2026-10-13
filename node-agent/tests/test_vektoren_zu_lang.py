# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl

CJK = "Unicodeblock Vereinheitlichte CJK-Ideogramme, Erweiterung G: Kurzdaten: " + " ".join(chr(0x30000 + i) for i in range(1500))


class _Bytezaehler:
    def __init__(self, kontext):
        self.kontext = kontext
        self.gesehen = []

    def __call__(self, req, timeout=0):
        texte = json.loads(req.data.decode("utf-8"))["input"]
        self.gesehen.append(texte)
        for t in texte:
            n = len(t.encode("utf-8")) + 1
            if n > self.kontext:
                fehler = json.dumps({"error": {"code": 400, "message": f"request ({n} tokens) exceeds the available context size ({self.kontext} tokens), try increasing it"}})
                raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(fehler.encode("utf-8")))
        r = io.BytesIO(json.dumps({"data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(len(texte))]}).encode("utf-8"))
        r.__enter__ = lambda *_: r
        r.__exit__ = lambda *_: False
        return r


def _server(kontext=2048):
    s = kl.KiServer.__new__(kl.KiServer)
    s.port, s.api_key = 1, "x"
    s.proc = type("P", (), {"poll": lambda self: None})()
    s._urlopen = _Bytezaehler(kontext)
    s.wahl = type("W", (), {"modell": type("M", (), {"kontext": kontext})()})()
    return s


def test_an_overlong_section_is_cut_to_fit_and_the_batch_goes_through():
    s = _server()
    normal = "Wien ist die Hauptstadt von Österreich. " * 20
    vs = s.vektoren([normal, CJK, "kurz"])
    assert len(vs) == 3
    gesendet = s._urlopen.gesehen[-1]
    assert gesendet[0] == normal and gesendet[2] == "kurz"
    assert gesendet[1] != CJK and CJK.startswith(gesendet[1])
    assert len(gesendet[1].encode("utf-8")) <= 2048 - kl.VEKTOR_RESERVE


def test_cutting_never_splits_a_character():
    assert kl._bytes_kuerzen("ab𰀀", 5) == "ab"
    assert kl._bytes_kuerzen("ab𰀀", 6) == "ab𰀀"
    assert kl._bytes_kuerzen("Größe", 100) == "Größe"


def test_a_refusal_shows_the_servers_reason_not_just_httperror():
    s = _server()
    s.wahl.modell.kontext = 100000
    with pytest.raises(kl.KiError) as e:
        s.vektoren([CJK])
    assert "HTTP 400" in e.value.detail and "exceeds the available context size" in e.value.detail
