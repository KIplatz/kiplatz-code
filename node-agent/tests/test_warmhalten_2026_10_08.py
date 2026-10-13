# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl
import node_local_state
import warmhalten as wh

from test_app_web import _api
from test_ki_laufzeit import _FakeProc, _Resp, _ordner_mit_dateien


class _Uhr:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class _Modell:
    def __init__(self, uhr, *, an=True, zuletzt=0.0, dauer=0.0, fehler=None):
        self.uhr, self.an, self.zuletzt_benutzt, self.dauer, self.fehler = uhr, an, zuletzt, dauer, fehler
        self.anstoesse = 0

    def laeuft(self):
        return self.an

    def anstossen(self, _server):
        if self.fehler is not None:
            raise self.fehler
        self.anstoesse += 1
        self.uhr.t += self.dauer


def _halter(modelle, *, darf=True):
    zeilen = []
    h = wh.Warmhalter([(n, (lambda m=m: m), (lambda s, m=m: m.anstossen(s))) for n, m in modelle], darf=lambda: darf, log=zeilen.append,
                      jetzt=modelle[0][1].uhr)
    return h, zeilen


def test_only_a_model_idle_for_a_minute_gets_a_mini_task_and_counts_as_used_afterwards():
    uhr = _Uhr()
    kalt = _Modell(uhr, zuletzt=uhr.t - wh.ABSTAND_S - 1)
    warm = _Modell(uhr, zuletzt=uhr.t - 5)
    aus = _Modell(uhr, an=False, zuletzt=0.0)
    h, zeilen = _halter([("antwort", kalt), ("bewertung", warm), ("bedeutung", aus)])
    h.runde()
    assert (kalt.anstoesse, warm.anstoesse, aus.anstoesse) == (1, 0, 0)
    assert kalt.zuletzt_benutzt == uhr.t and zeilen == []
    h.runde()
    assert kalt.anstoesse == 1


def test_nothing_while_the_device_does_not_take_questions():
    uhr = _Uhr()
    m = _Modell(uhr, zuletzt=0.0)
    h, _ = _halter([("antwort", m)], darf=False)
    h.runde()
    assert m.anstoesse == 0


def test_a_slow_mini_task_is_written_down_as_proof_and_errors_never_escape():
    uhr = _Uhr()
    langsam = _Modell(uhr, zuletzt=0.0, dauer=24.7)
    kaputt = _Modell(uhr, zuletzt=0.0, fehler=kl.KiError("KI_ANTWORT", "keine Antwort vom Bewertungs-Modell (TimeoutError)"))
    h, zeilen = _halter([("antwort", langsam), ("bewertung", kaputt)])
    h.runde()
    h.runde()
    assert zeilen[0] == "INFO warmhalten antwort: Mini-Aufgabe dauerte 24.7 s (Modell war ausgelagert)"
    assert zeilen[1:] == ["INFO warmhalten bewertung: keine Antwort vom Bewertungs-Modell (TimeoutError)"]


def test_the_runtime_remembers_every_use_of_all_three_models(tmp_path):
    o, _ = _ordner_mit_dateien(tmp_path)
    o.modell_pfad(kl.BEWERTUNG).write_bytes(b"gguf")
    wahl = kl.Wahl(kl.Geraet("Vulkan0", "Probe GPU", 16000, 6000), kl.BEWERTUNG, "test")
    procs = []

    def urlopen(req, timeout=0):
        if req.full_url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        if req.full_url.endswith("/v1/rerank"):
            return _Resp(json.dumps({"results": [{"index": 0, "relevance_score": 0.5}]}).encode())
        if req.full_url.endswith("/v1/embeddings"):
            return _Resp(json.dumps({"data": [{"index": 0, "embedding": [1.0, 0.0]}]}).encode())
        return _Resp(json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}).encode())

    s = kl.KiServer(o, popen=lambda a, **k: procs.append(_FakeProc(a, **k)) or procs[-1], urlopen=urlopen, schlafen=lambda _s: None, port_finder=lambda: 18571)
    assert s.zuletzt_benutzt == 0.0
    s.start(wahl, bewerten=True)
    for aufruf in (lambda: wh.bewertung_anstossen(s), lambda: wh.bedeutung_anstossen(s), lambda: wh.antwort_anstossen(s)):
        s.zuletzt_benutzt = 0.0
        aufruf()
        assert s.zuletzt_benutzt > 0.0
    s.stop()


def test_the_chat_mini_task_is_one_word_piece_with_the_answer_rules_and_yields_to_a_question():
    gesehen = {}

    class _S:
        def frage(self, nachrichten, **kw):
            gesehen.update(kw, nachrichten=nachrichten)

    ev = threading.Event()
    wh.antwort_anstossen(_S(), ev)
    assert gesehen["max_tokens"] == 1 and "system" not in gesehen and "kurz" not in gesehen and gesehen["abbruch"] is ev and gesehen["temperature"] == 0.0
    assert gesehen["nachrichten"] == [{"role": "user", "content": "ok"}]


def test_the_program_keeps_warm_only_while_sharing_and_no_question_runs(tmp_path):
    api, _fake, _dl = _api(tmp_path)
    assert isinstance(api._warmhalter, wh.Warmhalter)
    assert [n for n, _s, _a in api._warmhalter._modelle] == ["antwort", "bewertung", "bedeutung"]
    api._warmhalter.stop()
    assert api._core.run_state() is not node_local_state.RunState.ACTIVE
    assert api._warm_darf() is False
    api._core.start()
    api._kann_fuer_andere_antworten = lambda: True
    api._rechen.phase = "wartet"
    api._rechen.vorrang_aktiv = lambda: False
    assert api._warm_darf() is True
    api._rechen.vorrang_aktiv = lambda: True
    assert api._warm_darf() is False
    api._rechen.vorrang_aktiv = lambda: False
    for phase in ("akku", "hitze", "laden", "antwortet"):
        api._rechen.phase = phase
        assert api._warm_darf() is False
