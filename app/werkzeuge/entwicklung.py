# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
WWW = WURZEL / "app" / "www"
TESTS = (WURZEL / "app" / "tests").resolve()
HELFER = (WURZEL / "app" / "ki-helfer").resolve()
sys.path.insert(0, str(WURZEL / "node-agent"))

import community_dienst as cd

UEBUNG = ("**Übungsantwort vom Schein-PC.** Das ist keine echte Antwort, sie prüft nur die App.\n\n"
          "Wien ist die Hauptstadt von Österreich. Vermutlich regnet es dort morgen. Das habe ich mir ausgedacht.\n\n"
          "- ein Punkt\n- noch ein Punkt\n\n```\nprint(\"Code bleibt Code\")\n```")
LIEFERSCHEIN = {"quellen": "Übungsquelle", "quellen_liste": [{"titel": "Wikipedia: Wien"}], "modell": "Schein-PC", "dauer_s": 3.2, "gemacht": "geübt",
                "pruefung": {"gruen": 1, "gelb": 1, "rot": 1, "saetze": [
                    {"text": "Wien ist die Hauptstadt von Österreich.", "farbe": "gruen"},
                    {"text": "Vermutlich regnet es dort morgen.", "farbe": "gelb"},
                    {"text": "Das habe ich mir ausgedacht.", "farbe": "rot"}]}}


SCHAUBILD = {
    "traunstein": ("Der Traunstein ist **1691 m** hoch. Er steht am Ostufer des Traunsees bei Gmunden in Oberösterreich, "
                   "von Gmunden aus siehst du ihn direkt über dem See.\n\n"
                   "Der beliebteste Weg auf den Gipfel ist der Naturfreundesteig. Er ist steil und braucht Trittsicherheit.",
                   {"quellen": "Wikipedia, OpenStreetMap", "quellen_liste": [{"titel": "Wikipedia: Traunstein (Berg)"}, {"titel": "OpenStreetMap: Traunstein, 1691 m"}],
                    "modell": "", "dauer_s": 4.1, "gemacht": "in den Quellen der Community nachgeschlagen",
                    "pruefung": {"gruen": 2, "gelb": 1, "rot": 0, "saetze": [
                        {"text": "Der Traunstein ist 1691 m hoch.", "farbe": "gruen"},
                        {"text": "Er steht am Ostufer des Traunsees bei Gmunden in Oberösterreich, von Gmunden aus siehst du ihn direkt über dem See.", "farbe": "gruen"},
                        {"text": "Der beliebteste Weg auf den Gipfel ist der Naturfreundesteig.", "farbe": "gelb"}]}}),
    "feiertage": ("Im Dezember hat Österreich **3 gesetzliche Feiertage**:\n\n"
                  "| Datum | Feiertag |\n|---|---|\n| 8. Dezember | Mariä Empfängnis |\n| 25. Dezember | Christtag |\n| 26. Dezember | Stefanitag |\n\n"
                  "Der 24. und der 31. Dezember sind keine gesetzlichen Feiertage.",
                  {"quellen": "selbst ausgerechnet, Arbeitsruhegesetz", "quellen_liste": [{"titel": "Arbeitsruhegesetz § 7 (RIS)"}],
                   "modell": "", "dauer_s": 2.3, "gemacht": "selbst ausgerechnet",
                   "pruefung": {"gruen": 2, "gelb": 0, "rot": 0, "saetze": [
                       {"text": "Im Dezember hat Österreich 3 gesetzliche Feiertage:", "farbe": "gruen"},
                       {"text": "Der 24. und der 31. Dezember sind keine gesetzlichen Feiertage.", "farbe": "gruen"}]}}),
    "elternabend": ("Gern, zum Beispiel so:\n\n"
                    "Liebe Frau Huber,\n\nleider kann ich am Donnerstag nicht zum Elternabend kommen. "
                    "Könnten Sie mir die wichtigsten Punkte kurz schicken? Bei Fragen melde ich mich gern bei Ihnen.\n\n"
                    "Vielen Dank und liebe Grüße",
                    {"quellen": "", "quellen_liste": [], "modell": "", "dauer_s": 3.0, "gemacht": "geschrieben"}),
}


SCHAUBILD_EN = {
    "how high is the traunstein": (
        "The Traunstein is **1,691 m** high. It rises on the eastern shore of Lake Traunsee near Gmunden in Upper Austria, "
        "and from Gmunden you see it right across the lake.\n\n"
        "The most popular route to the summit is the Naturfreundesteig. It is steep and you need to be sure-footed.",
        {"quellen": "Wikipedia, OpenStreetMap", "quellen_liste": [{"titel": "Wikipedia: Traunstein (mountain)"}, {"titel": "OpenStreetMap: Traunstein, 1691 m"}],
         "modell": "", "dauer_s": 4.1, "gemacht": "looked up in the community's sources",
         "pruefung": {"gruen": 2, "gelb": 1, "rot": 0, "saetze": [
             {"text": "The Traunstein is 1,691 m high.", "farbe": "gruen"},
             {"text": "It rises on the eastern shore of Lake Traunsee near Gmunden in Upper Austria, and from Gmunden you see it right across the lake.", "farbe": "gruen"},
             {"text": "The most popular route to the summit is the Naturfreundesteig.", "farbe": "gelb"}]}}),
    "public holidays": (
        "In December, Austria has **3 public holidays**:\n\n"
        "| Date | Holiday |\n|---|---|\n| 8 December | Immaculate Conception |\n| 25 December | Christmas Day |\n| 26 December | St Stephen's Day |\n\n"
        "24 and 31 December are not public holidays.",
        {"quellen": "worked out, Rest Periods Act", "quellen_liste": [{"titel": "Arbeitsruhegesetz § 7 (RIS)"}],
         "modell": "", "dauer_s": 2.3, "gemacht": "worked out",
         "pruefung": {"gruen": 2, "gelb": 0, "rot": 0, "saetze": [
             {"text": "In December, Austria has 3 public holidays:", "farbe": "gruen"},
             {"text": "24 and 31 December are not public holidays.", "farbe": "gruen"}]}}),
    "parents' evening": (
        "Sure, for example:\n\n"
        "Dear Ms Huber,\n\nunfortunately I can't make it to the parents' evening on Thursday. "
        "Could you send me the most important points? If I have any questions, I'll be in touch.\n\n"
        "Many thanks and best wishes",
        {"quellen": "", "quellen_liste": [], "modell": "", "dauer_s": 3.0, "gemacht": "written"}),
}


def _schaubild(frage: str) -> tuple[str, dict] | None:
    f = frage.lower()
    return next((v for k, v in SCHAUBILD_EN.items() if k in f), None) or next((v for k, v in SCHAUBILD.items() if k in f), None)


class _KeineWeiterleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_OHNE_FOLGEN = urllib.request.build_opener(_KeineWeiterleitung)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def werkstatt_starten(ordner: Path, app_port: int) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    codes: dict[str, tuple[str, str]] = {}

    class W(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _antwort(self, status: int, daten: dict | None = None, kopf: dict | None = None) -> None:
            roh = json.dumps(daten or {}).encode()
            self.send_response(status)
            for k, v in (kopf or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            if u.path == "/login/oauth/keys":
                n = key.public_key().public_numbers()
                return self._antwort(200, {"keys": [{"kty": "RSA", "alg": "RS256", "kid": "entwicklung", "n": _b64(n.n.to_bytes(256, "big")), "e": _b64(n.e.to_bytes(3, "big"))}]})
            if u.path == "/kiplatz-verbinden/frisch" and q.get("weiter", "").startswith(("/login/oauth/authorize?", "/user/oauth2/")):
                return self._antwort(302, kopf={"Location": issuer + q["weiter"]})
            if u.path in ("/user/oauth2/Google", "/user/oauth2/GitHub", "/user/oauth2/E-Mail-Code") and q.get("redirect_to", "").startswith("/login/oauth/authorize?"):
                return self._antwort(302, kopf={"Location": issuer + q["redirect_to"]})
            if u.path == "/login/oauth/authorize" and q.get("code_challenge_method") == "S256":
                code = _b64(hashlib.sha256(str(time.time_ns()).encode()).digest())[:20]
                codes[code] = (q["code_challenge"], q["redirect_uri"])
                return self._antwort(302, kopf={"Location": q["redirect_uri"] + "?" + urllib.parse.urlencode({"code": code, "state": q["state"]})})
            self._antwort(404)

        def do_POST(self):
            f = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()))
            eintrag = codes.pop(f.get("code", ""), None)
            if eintrag is None or eintrag[1] != f.get("redirect_uri") or _b64(hashlib.sha256(f.get("code_verifier", "").encode()).digest()) != eintrag[0]:
                return self._antwort(400, {"error": "invalid_grant"})
            jetzt = int(time.time())
            kopf = _b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "entwicklung"}).encode())
            daten = _b64(json.dumps({"iss": issuer, "aud": "entwicklung", "sub": "1", "name": "Test-Konto", "exp": jetzt + 600, "iat": jetzt}).encode())
            sig = key.sign((kopf + "." + daten).encode(), padding.PKCS1v15(), hashes.SHA256())
            self._antwort(200, {"access_token": "wegwerfen", "id_token": kopf + "." + daten + "." + _b64(sig)})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), W)
    issuer = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (ordner / "konto-anmeldung.json").write_text(json.dumps({"issuer": issuer, "client_id": "entwicklung", "scope": "openid profile",
        "handy_rueckkehr": [f"http://127.0.0.1:{app_port}/", f"http://localhost:{app_port}/"]}), encoding="utf-8")
    return issuer


APP_PORT = 8780


def dienst_starten(ordner: Path) -> tuple[cd.Server, str]:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / cd.SCHLUESSEL_DATEI
    if not datei.exists():
        datei.write_text("ab" * 32, encoding="ascii")
    cd.Handler.dienst = cd.Dienst(ordner, datei.read_text(encoding="ascii").strip(), "Spielwiese App", spielwiese=True)
    (ordner / "geheim").mkdir(exist_ok=True)
    (ordner / "geheim" / "mailcode.json").write_text(json.dumps({
        "client_id": "entwicklung-email", "client_secret": "e" * 43, "sub_schluessel": "s" * 43, "code_schluessel": "c" * 43,
        "redirect_uris": ["http://127.0.0.1/entwicklung"], "aussteller": f"http://127.0.0.1:{APP_PORT}/konto-code"}), encoding="utf-8")
    cd.Handler.dienst.codemail = lambda an, code, sprache="de": print(f"E-Mail-Code für {an}: {code}", flush=True) or True
    srv = cd.Server(("127.0.0.1", 0), cd.Handler)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _json(adresse: str, weg: str, body: dict | None = None, kopf: dict | None = None) -> dict:
    req = urllib.request.Request(adresse + weg, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(kopf or {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def schein_pc(adresse: str, schaubild: bool = False) -> None:
    d = _json(adresse, "/geraet-mit-code", {"code": "spielwiese", "name": "Wohnzimmer-PC" if schaubild else "Schein-PC"})
    kopf = {"X-Geraet": d["kennung"], "X-Geraet-Schluessel": d["schluessel"]}
    while True:
        try:
            a = _json(adresse, "/auftrag?antworten=1&warm=1&skills=1", kopf=kopf)
            if a.get("auftrag") and a.get("art") == "antwort":
                k = a["auftrag"]
                sb = _schaubild(json.dumps(a, ensure_ascii=False)) if schaubild else None
                if sb:
                    _json(adresse, "/antwort", {"auftrag": k, "text": sb[0], "lieferschein": sb[1], "dauer_s": sb[1]["dauer_s"]}, kopf)
                    continue
                for i, schritt in enumerate(("liest die Frage …", "sucht in den Quellen …", "schreibt die Antwort …")):
                    _json(adresse, "/antwort-teil", {"auftrag": k, "text": UEBUNG[: 40 * (i + 1)], "schritt": schritt}, kopf)
                    time.sleep(1.2)
                sk = a.get("skill") or {}
                text = (f"**Skill angekommen:** {sk.get('name')} ({len(sk.get('text', ''))} Zeichen).\n\n" if sk else "") + UEBUNG
                _json(adresse, "/antwort", {"auftrag": k, "text": text, "lieferschein": {**LIEFERSCHEIN, **({"skill": sk.get("name")} if sk else {})}, "dauer_s": 3.2}, kopf)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print("Schein-PC:", exc, file=sys.stderr)
        time.sleep(0.5)


class ScheinPlatzl:
    FALLE = ('<p>Hallo <strong>Community</strong>, schaut euch <a href="https://kiplatz.at/wiki/">das Wiki</a> an.</p>'
             '<script>window.platzlFalle=1</script><img src="x" onerror="window.platzlFalle=2" alt="Foto vom Stammtisch">'
             '<p><a href="javascript:window.platzlFalle=3">klick</a> <img class="emoji" alt=":smile:" src="e.png"></p>'
             '<aside class="quote" data-username="anna"><blockquote><p>Zitat von Anna</p></blockquote></aside>'
             '<iframe src="https://example.org"></iframe><pre><code>print("hallo")</code></pre>')

    def __init__(self):
        self.schluessel: set[str] = set()
        self.fassung = 1
        self.neu: dict[int, dict] = {}

    def freigeben(self, q: dict) -> str:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        assert q.get("padding") == "oaep" and set(q["scopes"].split(",")) <= {"read", "write", "session_info"}
        oeff = serialization.load_pem_public_key(q["public_key"].encode())
        k = hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:32]
        self.schluessel.add(k)
        roh = json.dumps({"key": k, "nonce": q["nonce"], "push": False, "api": 4}).encode()
        geheim = oeff.encrypt(roh, padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
        b = base64.encodebytes(geheim).decode()
        return q["auth_redirect"] + "&payload=" + urllib.parse.quote(b)

    def antwort(self, weg: str, key: str, methode: str, body: dict | None = None) -> tuple[int, dict]:
        if key not in self.schluessel:
            return 403, {"errors": ["not allowed"]}
        if weg == "/posts.json" and methode == "POST":
            b = body or {}
            raw = str(b.get("raw", ""))
            if len(raw) < 20:
                return 422, {"errors": ["Beitrag muss mindestens 20 Zeichen lang sein"]}
            post = {"username": "test-philipp", "created_at": "2026-09-26T12:00:00Z", "cooked": "<p>" + raw.replace("<", "&lt;").replace("\n", "<br>") + "</p>"}
            if b.get("topic_id"):
                t = self.neu.setdefault(int(b["topic_id"]), {"title": "Wie gießt man Tomaten richtig?", "category_id": 5, "posts": []})
                t["posts"].append(post)
                return 200, {"topic_id": int(b["topic_id"]), "post_number": len(t["posts"]) + 2}
            if len(str(b.get("title", ""))) < 15:
                return 422, {"errors": ["Titel muss mindestens 15 Zeichen lang sein"]}
            k = 100 + len(self.neu)
            self.neu[k] = {"title": str(b["title"]), "category_id": int(b.get("category") or 0), "posts": [post]}
            return 200, {"topic_id": k, "post_number": 1}
        import re as _re
        m = _re.fullmatch(r"/t/(\d+)\.json", weg)
        if m and int(m.group(1)) >= 100 and int(m.group(1)) in self.neu:
            t = self.neu[int(m.group(1))]
            return 200, {"id": int(m.group(1)), "title": t["title"], "slug": "neu", "category_id": t["category_id"], "post_stream": {"posts": t["posts"]}}
        if weg == "/user-api-key/revoke" and methode == "POST":
            self.schluessel.discard(key)
            return 200, {"success": "OK"}
        if weg == "/session/current.json":
            return 200, {"current_user": {"username": "test-philipp"}}
        if weg == "/categories.json":
            return 200, {"category_list": {"categories": [
                {"id": 5, "name": "Fragen an KIplatz", "slug": "fragen", "color": "3F9A7E"},
                {"id": 7, "name": "Skills", "slug": "skills", "color": "2f7fd8"},
                {"id": 9, "name": "Böse", "slug": "boese", "color": "red;background:url(x)"}]}}
        if weg in ("/latest.json", "/c/fragen/5/l/latest.json", "/c/skills/7/l/latest.json"):
            themen = [{"id": 11, "title": "Wie gießt man Tomaten richtig?", "posts_count": 3, "category_id": 5, "last_posted_at": "2026-09-26T08:00:00Z"},
                      {"id": 12, "title": "Skill: Briefe ans Amt <b>fett</b>", "posts_count": 1, "category_id": 7, "last_posted_at": "2026-09-20T08:00:00Z"}]
            if "/c/" in weg:
                themen = [t for t in themen if f"/{t['category_id']}/" in weg]
            return 200, {"topic_list": {"topics": themen}}
        if weg == "/t/12.json":
            skill = ("---\nname: brief-ans-amt\ndescription: Schreibt höfliche, klare Briefe an Ämter und Behörden.\n---\n\n"
                     "Schreibe sachlich und freundlich. Immer mit Betreff, Anrede, einem klaren Anliegen, Frist falls nötig, Grußformel.\n"
                     f"Fassung {self.fassung}.")
            import html as _h
            return 200, {"id": 12, "title": "Skill: Briefe ans Amt", "slug": "briefe-ans-amt", "category_id": 7, "post_stream": {"posts": [
                {"username": "anna", "created_at": "2026-09-20T08:00:00Z",
                 "cooked": f"<p>Damit klappt jeder Brief ans Amt.</p><pre><code>{_h.escape(skill)}</code></pre>"}]}}
        if weg in ("/t/11.json",):
            return 200, {"id": int(weg[3:5]), "title": "Wie gießt man Tomaten richtig?", "slug": "tomaten", "post_stream": {"posts": [
                {"username": "anna", "created_at": "2026-09-26T07:00:00Z", "cooked": "<p>Wie oft soll ich gießen?</p>"},
                {"username": "test-philipp", "created_at": "2026-09-26T08:00:00Z", "cooked": self.FALLE}]}}
        return 404, {"errors": ["not found"]}


STOER: dict[str, int] = {}


def webserver(port: int, dienst: str) -> http.server.ThreadingHTTPServer:
    platzl = ScheinPlatzl()

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(WWW), **kw)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a):
            pass

        def _gestoert(self) -> bool:
            p = self.path.split("?")[0].lstrip("/")
            if STOER.get(p, 0) <= 0:
                return False
            STOER[p] -= 1
            self.send_response(429)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "0")
            self.end_headers()
            print(f"gestört: 429 für {p}, noch {STOER[p]}-mal", flush=True)
            return True

        def translate_path(self, path: str) -> str:
            p = path.split("?")[0].split("#")[0]
            if p == "/tests" or p.startswith("/tests/"):
                rest = p[len("/tests"):].lstrip("/") or "index.html"
                ziel = (TESTS / rest).resolve()
                return str(ziel) if ziel.is_relative_to(TESTS) else str(TESTS / "fehlt")
            if p.startswith("/ki-helfer/"):
                ziel = (HELFER / p[len("/ki-helfer/"):]).resolve()
                return str(ziel) if ziel.is_relative_to(HELFER) else str(HELFER / "fehlt")
            return super().translate_path(path)

        def _datei(self) -> bool:
            p = self.path.split("?")[0].split("#")[0]
            return p in ("/", "/tests", "/tests/") or Path(self.translate_path(self.path)).is_file()

        def _weiter(self, methode: str) -> None:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            kopf = {k: v for k, v in self.headers.items() if k.lower() in ("content-type", "accept", "x-geraet", "x-geraet-schluessel", "x-geraet-art", "x-app-version", "cookie", "authorization")}
            req = urllib.request.Request(dienst + self.path, data=body, headers=kopf, method=methode)
            durchreichen = ("location", "set-cookie", "content-security-policy", "referrer-policy", "x-frame-options", "www-authenticate")
            try:
                with _OHNE_FOLGEN.open(req, timeout=30) as r:
                    status, daten, art, extra = r.status, r.read(), r.headers.get("Content-Type", "application/json"), [(k, v) for k, v in r.headers.items() if k.lower() in durchreichen]
            except urllib.error.HTTPError as e:
                status, daten, art, extra = e.code, e.read(), e.headers.get("Content-Type", "application/json"), [(k, v) for k, v in e.headers.items() if k.lower() in durchreichen]
            self.send_response(status)
            self.send_header("Content-Type", art)
            self.send_header("Content-Length", str(len(daten)))
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(daten)

        def _platzl(self, methode: str) -> bool:
            p = self.path.split("?")[0]
            if p == "/schein-platzl/user-api-key/new" and methode == "GET":
                ziel = platzl.freigeben(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query)))
                self.send_response(302)
                self.send_header("Location", ziel)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return True
            if p == "/schein-platzl/skill-bearbeiten":
                platzl.fassung += 1
                self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()
                return True
            if p.startswith("/platzl-api/"):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else None
                status, d = platzl.antwort(p[len("/platzl-api"):], self.headers.get("User-Api-Key", ""), methode, body)
                roh = json.dumps(d).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)
                return True
            return False

        def do_GET(self):
            if self._platzl("GET"):
                return
            if self.path.startswith("/stoer-setzen?"):
                q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
                STOER[q.get("datei", "").lstrip("/")] = int(q.get("n", "1") or 1)
                self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()
                return
            if self._datei():
                if self._gestoert():
                    return
                return super().do_GET()
            self._weiter("GET")

        def do_POST(self):
            if self._platzl("POST"):
                return
            self._weiter("POST")

    H.extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".woff2": "font/woff2", ".css": "text/css", ".mjs": "text/javascript", ".wasm": "application/wasm", ".onnx": "application/octet-stream", ".gz": "application/gzip"}
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), H)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--ordner", type=Path, default=None, help="Wegwerf-Ordner für die Spielwiese (Standard: ein neuer im Temp-Ordner)")
    ap.add_argument("--ohne-pc", action="store_true", help="kein Schein-PC: Fragen bleiben liegen")
    ap.add_argument("--www", type=Path, default=None, help="anderer Ordner statt app/www, etwa die gereinigte Fassung app/auslieferung")
    ap.add_argument("--schaubild", action="store_true", help="Schein-PC antwortet auf die Fragen für die Store-Bildschirmfotos (SCHAUBILD)")
    ap.add_argument("--stoer", action="append", default=[], metavar="DATEI:N",
                    help="Probe der Lade-Wache: diese Datei der App (z. B. js/symbole.js:2) bekommt N-mal 429 wie von der Bremse des Live-Servers")
    a = ap.parse_args()
    for s in a.stoer:
        weg, _, n = s.rpartition(":")
        STOER[weg.lstrip("/")] = int(n or 1)
    global WWW
    if a.www is not None:
        WWW = a.www.resolve()
    ordner = a.ordner or Path(tempfile.mkdtemp(prefix="kiplatz-app-spielwiese-"))
    ordner.mkdir(parents=True, exist_ok=True)
    global APP_PORT
    APP_PORT = a.port
    werkstatt = werkstatt_starten(ordner, a.port)
    _, dienst = dienst_starten(ordner)
    if not a.ohne_pc:
        threading.Thread(target=schein_pc, args=(dienst, a.schaubild), daemon=True).start()
    web = webserver(a.port, dienst)
    print(f"KIplatz-App: http://127.0.0.1:{a.port}/  (Dienst {dienst}, Werkstatt zum Probieren {werkstatt}, Ordner {ordner}, Code „spielwiese“)", flush=True)
    web.serve_forever()


if __name__ == "__main__":
    main()
