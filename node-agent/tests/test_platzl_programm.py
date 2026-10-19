# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import io
import json
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import platzl_programm as pp

SKILL = "---\nname: brief-ans-amt\ndescription: Briefe an Ämter\n---\n\nSchreibe sachlich, mit Betreff & Grußformel.\n"


class Server:

    def __init__(self):
        self.tickets, self.schluessel, self.gesehen = {}, set(), []

    def platzl_start(self, ticket):
        self.tickets[ticket] = None
        return {"ok": True}

    def platzl_abholen(self, ticket):
        p = self.tickets.get(ticket)
        return {"status": "fertig", "payload": p} if p else {"status": "wartet"}

    def erlauben(self, adresse):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(adresse).query))
        assert q["padding"] == "oaep" and q["scopes"] == "read,write,session_info" and q["auth_redirect"].startswith("https://kiplatz.at/platzl-zurueck?t=")
        k = "k" * 20 + "1234"
        self.schluessel.add(k)
        roh = json.dumps({"key": k, "nonce": q["nonce"], "push": False, "api": 4}).encode()
        geheim = serialization.load_pem_public_key(q["public_key"].encode()).encrypt(roh, padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
        self.tickets[q["auth_redirect"].split("t=")[1]] = base64.encodebytes(geheim).decode()

    def oeffner(self, req, timeout):
        weg = req.full_url.replace(pp.API, "")
        self.gesehen.append((req.get_method(), weg, dict(req.header_items())))
        if req.get_header("User-api-key") not in self.schluessel:
            raise urllib.error.HTTPError(req.full_url, 403, "nein", {}, io.BytesIO(b"{}"))
        if weg == "/session/current.json":
            d = {"current_user": {"username": "rainer"}}
        elif weg == "/categories.json":
            d = {"category_list": {"categories": [{"id": 7, "name": "Skills", "slug": "skills", "color": "2f7fd8"}, {"id": 9, "name": "X", "slug": "x", "color": "red;x"}]}}
        elif weg == "/t/24.json":
            d = {"title": "Skill: Briefe ans Amt", "slug": "brief", "category_id": 7, "post_stream": {"posts": [{"username": "anna", "cooked": "<p>Hier:</p><pre><code>" + SKILL.replace("&", "&amp;") + "</code></pre>"}]}}
        elif weg == "/posts.json":
            b = json.loads(req.data)
            d = {"topic_id": b.get("topic_id", 30), "post_number": 2}
        elif weg == "/user-api-key/revoke":
            self.schluessel.discard(req.get_header("User-api-key"))
            d = {"success": "OK"}
        else:
            raise urllib.error.HTTPError(req.full_url, 404, "fehlt", {}, io.BytesIO(b"{}"))
        return io.BytesIO(json.dumps(d).encode())


@pytest.fixture
def p(tmp_path):
    s = Server()
    pl = pp.Platzl(tmp_path, s, oeffner=lambda r, timeout: _mit(s.oeffner(r, timeout)))
    pl.server = s
    return pl


class _mit(io.BytesIO):
    def __init__(self, b):
        super().__init__(b.getvalue())


def _verbinden(p):
    adresse = p.verbinden_start()
    assert p.abholen() == "wartet"
    p.server.erlauben(adresse)
    assert p.abholen() == "fertig"


def test_connect_stores_the_key_protected_and_nothing_readable(p, tmp_path):
    _verbinden(p)
    roh = (tmp_path / pp.DATEI).read_text(encoding="utf-8")
    assert "k" * 20 not in roh and any(f"{p}:" in roh for p in ("dpapi", "bund", "datei"))
    assert p.stand() == {"verbunden": True, "name": "rainer", "wartet": False}


def test_a_foreign_answer_is_refused(p):
    adresse = p.verbinden_start()
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(adresse).query))
    p.server.tickets[q["auth_redirect"].split("t=")[1]] = base64.b64encode(b"x" * 256).decode()
    with pytest.raises(app_core.AppError):
        p.abholen()
    assert not p.stand()["verbunden"]


def test_only_allowed_ways_and_writing_checks_first(p):
    _verbinden(p)
    for weg in ("/admin/users.json", "/t/1.json/../../admin", "/posts.json?x=1"):
        with pytest.raises(app_core.AppError):
            p.api(weg)
    vorher = len(p.server.gesehen)
    for f in ({"text": "kurz", "thema": 5}, {"text": "lang genug für das Platzl hier", "titel": "kurz", "kategorie": 7}, {"text": "lang genug für das Platzl hier", "titel": "ein Titel mit genug Zeichen"}):
        with pytest.raises(app_core.AppError):
            p.schreiben(**f)
    assert len(p.server.gesehen) == vorher
    assert p.schreiben(text="Eine Antwort mit genug Zeichen.", thema=24) == {"thema": 24, "nummer": 2}
    methode, weg, kopf = p.server.gesehen[-1]
    assert methode == "POST" and weg == "/posts.json" and "Cookie" not in kopf


def test_skill_from_a_topic_and_colours(p):
    _verbinden(p)
    roh, titel = p.skill_text(24)
    assert roh.strip() == SKILL.strip() and titel == "Briefe ans Amt"
    assert [k["farbe"] for k in p.kategorien()] == ["#2f7fd8", "#8a949c"]
    assert pp.skill_im_beitrag("<p>kein Skill</p>") is None


def test_disconnect_revokes_and_forgets(p, tmp_path):
    _verbinden(p)
    p.trennen()
    assert not (tmp_path / pp.DATEI).exists() and not p.server.schluessel
    with pytest.raises(app_core.AppError) as e:
        p.api("/latest.json")
    assert e.value.code == "PLATZL_AUS"


def test_a_skill_from_the_platzl_never_overwrites_your_own(tmp_path):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)

    class F:
        fassung = "Schreibe sachlich, mit Betreff und Grußformel."

        def skill_text(self, thema):
            return f"---\nname: brief-ans-amt\ndescription: Briefe\n---\n\n{self.fassung}\n", "Briefe ans Amt"
    api._platzl = F()
    r = api.platzl_skill_holen(24)
    assert r["ok"] and r["daten"]["wie"] == "neu" and r["daten"]["skill"]["quelle"] == "platzl#24"
    assert api.platzl_skill_holen(24)["daten"]["wie"] == "gleich"
    F.fassung = "Schreibe kurz und freundlich, immer mit Betreff."
    assert api.platzl_skill_holen(24)["daten"]["wie"] == "aktualisiert"
    api.skill_speichern("---\nname: mein-brief\ndescription: Meiner\n---\n\nSo schreibe ich meine Briefe ans Amt.")
    F.skill_text = lambda self, thema: ("---\nname: mein-brief\ndescription: fremd\n---\n\nFremde Anweisungen, die meine ersetzen würden.\n", "x")
    r = api.platzl_skill_holen(25)
    assert not r["ok"] and "eigenen Skill" in r["text"]
    assert "So schreibe ich" in api.skill_laden("mein-brief")["daten"]["text"]
