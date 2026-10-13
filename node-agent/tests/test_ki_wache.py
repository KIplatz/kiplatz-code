# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import http.server
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import ki_laufzeit as kl


class _Schein(http.server.BaseHTTPRequestHandler):
    art = "fertig"
    frei = threading.Event()

    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for wort in ("Wien ", "ist "):
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": wort}}]}).encode() + b"\n\n")
            self.wfile.flush()
        if _Schein.art == "fertig":
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": "die Hauptstadt."}}]}).encode() + b"\n\ndata: [DONE]\n\n")
            self.wfile.flush()
            return
        _Schein.frei.wait(20)


class _Proc:
    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def terminate(self):
        self.code = 1

    def wait(self, timeout=None):
        return self.code


@pytest.fixture()
def server(monkeypatch):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Schein)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    s = kl.KiServer.__new__(kl.KiServer)
    s.port, s.api_key, s.proc = httpd.server_address[1], "x", _Proc()
    s._urlopen, s._schlafen = urllib.request.urlopen, time.sleep
    s.abbruch = threading.Event()
    s.wahl = type("W", (), {"modell": type("M", (), {"kontext": 4096})()})()
    _Schein.frei.clear()
    monkeypatch.setattr(kl, "STILLSTAND_S", 1.5)
    yield s
    _Schein.frei.set()
    httpd.shutdown()


FRAGE = [{"role": "user", "content": "Hauptstadt von Österreich?"}]


def test_normal_answer_unchanged(server):
    _Schein.art = "fertig"
    worte = []
    a = server.frage(FRAGE, on_token=worte.append)
    assert a.text == "Wien ist die Hauptstadt." and worte == ["Wien ", "ist ", "die Hauptstadt."] and not a.abgebrochen


def test_stopp_ends_a_silent_answer_at_once(server):
    _Schein.art = "haengt"
    worte = []
    threading.Timer(0.8, server.abbruch.set).start()
    t0 = time.monotonic()
    a = server.frage(FRAGE, on_token=worte.append)
    assert time.monotonic() - t0 < 1.4, "Stopp must not wait for the Stillstand time"
    assert a.abgebrochen and a.text == "Wien ist"


def test_stuck_model_is_given_up_and_stopped(server):
    _Schein.art = "haengt"
    t0 = time.monotonic()
    with pytest.raises(app_core.AppError) as e:
        server.frage(FRAGE, on_token=lambda w: None)
    dauer = time.monotonic() - t0
    assert e.value.code == "KI_ANTWORT" and "nichts mehr geschrieben" in e.value.detail
    assert 1.4 < dauer < 4.0, dauer
    assert server.proc is None


def test_ended_model_is_noticed(server):
    _Schein.art = "haengt"
    proc = server.proc
    threading.Timer(0.6, lambda: setattr(proc, "code", 3)).start()
    t0 = time.monotonic()
    with pytest.raises(app_core.AppError) as e:
        server.frage(FRAGE, on_token=lambda w: None)
    assert time.monotonic() - t0 < 1.4 and "beendet" in e.value.detail
