# SPDX-License-Identifier: AGPL-3.0-or-later
import http.client
import json
import threading

import pytest

import community


class _Antwort:
    def __init__(self, status=200, body=None, will_close=False):
        self.status = status
        self.will_close = will_close
        self._body = json.dumps(body if body is not None else {"ok": True}).encode("utf-8")

    def read(self, n=-1):
        b, self._body = self._body, b""
        return b


class _Verbindung:
    def __init__(self, antworten, *, warten=None):
        self.antworten = list(antworten)
        self.anfragen = []
        self.kaputt = False
        self.zu = False
        self.sock = None
        self.timeout = None
        self._warten = warten

    def request(self, methode, weg, body=None, headers=None):
        if self.kaputt:
            raise http.client.RemoteDisconnected("Gegenseite hat getrennt")
        self.anfragen.append((methode, weg, body, dict(headers or {})))

    def getresponse(self):
        if self._warten is not None:
            self._warten.wait(5)
        return self.antworten.pop(0) if self.antworten else _Antwort()

    def close(self):
        self.zu = True


def _community(tmp_path, gebaut, antworten=None, warten=None, uhr=None):
    def verbinden(timeout):
        v = _Verbindung(antworten or [], warten=warten)
        v.timeout = timeout
        gebaut.append(v)
        return v
    return community.Community(tmp_path, adresse="https://server.test:8444", verbinden=verbinden, uhr=uhr)


def test_zwei_anfragen_gehen_ueber_eine_leitung_mit_denselben_kopfzeilen(tmp_path):
    gebaut = []
    c = _community(tmp_path, gebaut)
    assert c._anfrage("/hallo") == {"ok": True}
    assert c._anfrage("/rechenstand", timeout=3.0) == {"ok": True}
    assert len(gebaut) == 1 and [a[1] for a in gebaut[0].anfragen] == ["/hallo", "/rechenstand"]
    kopf = gebaut[0].anfragen[0][3]
    assert kopf["User-Agent"] == community._UA and kopf["Accept"] == "application/json"
    assert gebaut[0].timeout == 3.0
    assert c._leitungen.freie == 1


def test_trennt_der_server_wird_die_naechste_anfrage_neu_verbunden(tmp_path):
    gebaut = []
    c = _community(tmp_path, gebaut, antworten=[_Antwort(will_close=True)])
    c._anfrage("/hallo")
    assert gebaut[0].zu and c._leitungen.freie == 0
    c._anfrage("/hallo")
    assert len(gebaut) == 2


def test_stille_leitung_wird_nach_der_ruhezeit_nicht_mehr_benutzt(tmp_path):
    uhr = {"t": 1000.0}
    gebaut = []
    c = _community(tmp_path, gebaut, uhr=lambda: uhr["t"])
    c._anfrage("/hallo")
    uhr["t"] += community.LEITUNG_RUHE_S - 1
    c._anfrage("/hallo")
    assert len(gebaut) == 1
    uhr["t"] += community.LEITUNG_RUHE_S + 1
    c._anfrage("/hallo")
    assert len(gebaut) == 2 and gebaut[0].zu


def test_eine_alte_leitung_die_der_server_schon_zu_hat_wird_bei_get_einmal_neu_versucht_bei_post_nie(tmp_path):
    gebaut = []
    c = _community(tmp_path, gebaut)
    c._anfrage("/hallo")
    gebaut[0].kaputt = True
    assert c._anfrage("/hallo") == {"ok": True}
    assert len(gebaut) == 2 and gebaut[0].zu and gebaut[1].anfragen[0][1] == "/hallo"
    gebaut[1].kaputt = True
    with pytest.raises(community.CommunityError) as exc:
        c._anfrage("/frage-stellen", {"nachrichten": []})
    assert exc.value.code == "COMMUNITY_UNERREICHBAR" and len(gebaut) == 2
    gebaut.clear()
    c2 = _community(tmp_path / "zwei", gebaut)
    gebaut_kaputt = []

    def verbinden(timeout):
        v = _Verbindung([])
        v.kaputt = True
        gebaut_kaputt.append(v)
        return v
    c2._leitungen._verbinden = verbinden
    with pytest.raises(community.CommunityError):
        c2._anfrage("/hallo")
    assert len(gebaut_kaputt) == 1


def test_fehlerantwort_des_servers_wird_wie_bisher_gemeldet_und_die_leitung_bleibt(tmp_path):
    gebaut = []
    c = _community(tmp_path, gebaut, antworten=[_Antwort(429, {"fehler": "ZU_SCHNELL", "text": "langsam"}), _Antwort(500, None)])
    with pytest.raises(community.CommunityError) as exc:
        c._anfrage("/suche", {"frage": "x"})
    assert exc.value.code == "COMMUNITY_ZU_SCHNELL" and exc.value.detail == "langsam"
    gebaut[0].antworten = [_Antwort(500, None)]
    gebaut[0]._body = None
    with pytest.raises(community.CommunityError) as exc2:
        c._anfrage("/hallo")
    assert exc2.value.code == "COMMUNITY_500" and "500" in exc2.value.detail
    assert len(gebaut) == 1


def test_zwei_faeden_gleichzeitig_bekommen_zwei_leitungen_und_geben_beide_zurueck(tmp_path):
    frei = threading.Event()
    gebaut = []
    c = _community(tmp_path, gebaut, warten=frei)
    ergebnisse = []
    faeden = [threading.Thread(target=lambda: ergebnisse.append(c._anfrage("/hallo"))) for _ in range(2)]
    for f in faeden:
        f.start()
    for _ in range(50):
        if len(gebaut) == 2:
            break
        threading.Event().wait(0.02)
    frei.set()
    for f in faeden:
        f.join(timeout=5)
    assert len(gebaut) == 2 and ergebnisse == [{"ok": True}, {"ok": True}] and c._leitungen.freie == 2
    c._anfrage("/hallo")
    assert len(gebaut) == 2


def test_ein_eingespritzter_oeffner_geht_weiter_den_alten_weg(tmp_path):
    aufrufe = []

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b'{"ok": 1}'

    def oeffner(req, timeout):
        aufrufe.append(req.full_url)
        return _R()
    c = community.Community(tmp_path, adresse="https://server.test", oeffner=oeffner)
    assert c._anfrage("/hallo") == {"ok": 1} and aufrufe == ["https://server.test/hallo"] and c._leitungen.freie == 0
