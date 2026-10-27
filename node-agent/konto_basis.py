# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from html import escape


SCOPE = "openid profile email"


FRIST_S = 300


_UA = "CommunityAI-Konto/1"


class TokenFehler(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _b64url(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode("ascii")


WERKSTATT_HOST = "werkstatt.kiplatz.at"


PLATZL_ANMELDEN = "https://forum.kiplatz.at/login"


_SEITE_GUT = """<!doctype html><html lang="de"><head><meta charset="utf-8">{kopf}<title>KIplatz: angemeldet</title>
<style>body{{font-family:system-ui,sans-serif;background:#E6F1ED;color:#1B1F1E;margin:0;display:grid;place-items:center;min-height:100vh}}
main{{background:#fff;border:1px solid #B9D3C9;border-radius:14px;padding:28px 32px;max-width:32em}}h1{{font-size:1.4rem;margin:0 0 10px;color:#1F3630}}</style></head>
<body><main><h1>{titel}</h1><p>{text}</p>{mehr}</main></body></html>"""


_SCHLIESSEN = '<p style="color:#5C6663">Dieses Fenster kannst du schließen.</p>'


_WEITER = ('<p style="color:#5C6663">Du wirst jetzt auch im Platzl angemeldet, dem Treffpunkt der Community. '
           '<a href="{adresse}">Weiter zum Platzl</a></p>')


class Anmeldung:

    def __init__(self, konfig: dict, danach, *, browser=None, oeffner=None, frist_s: float = FRIST_S) -> None:
        self.konfig = dict(konfig)
        self._danach = danach
        self._browser = browser or webbrowser.open
        self._oeffner = oeffner or urllib.request.urlopen
        self.frist_s = frist_s
        self.state = secrets.token_urlsafe(24)
        self._verifier = secrets.token_urlsafe(48)
        self.laeuft = False
        self.fertig = False
        self.fehler: str | None = None
        self.adresse = ""
        self._srv: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None


    def _rueckkehr(self) -> str:
        assert self._srv is not None
        return f"http://127.0.0.1:{self._srv.server_address[1]}/rueckkehr"

    def start(self) -> str:
        challenge = _b64url(hashlib.sha256(self._verifier.encode("ascii")).digest())
        lauf = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass

            def _seite(self, code: int, titel: str, text: str, weiter: str = "") -> None:
                kopf = f'<meta http-equiv="refresh" content="1;url={escape(weiter)}">' if weiter else ""
                mehr = _WEITER.format(adresse=escape(weiter)) if weiter else _SCHLIESSEN
                body = _SEITE_GUT.format(kopf=kopf, titel=escape(titel), text=escape(text), mehr=mehr).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                teile = urllib.parse.urlsplit(self.path)
                if teile.path != "/rueckkehr":
                    self._seite(404, "Nichts hier", "Diese Adresse gehört zur Anmeldung von KIplatz und hat sonst nichts.")
                    return
                q = urllib.parse.parse_qs(teile.query)
                if q.get("state", [""])[0] != lauf.state:
                    self._seite(400, "Das passt nicht zusammen", "Die Rückkehr kam nicht von der Anmeldung, die das Programm gestartet hat. Bitte im Programm noch einmal auf „Anmelden“ klicken.")
                    lauf.fehler = "die Rückkehr aus dem Browser passte nicht zur gestarteten Anmeldung"
                    return
                if q.get("error"):
                    self._seite(400, "Anmeldung abgebrochen", "Die Werkstatt hat die Anmeldung nicht bestätigt. Im Programm kannst du es noch einmal versuchen.")
                    lauf.fehler = "die Werkstatt hat die Anmeldung abgelehnt (" + q.get("error_description", q["error"])[0][:120] + ")"
                    return
                code = q.get("code", [""])[0]
                if not code:
                    self._seite(400, "Kein Code", "Die Werkstatt hat keinen Anmeldecode mitgeschickt.")
                    lauf.fehler = "die Werkstatt hat keinen Anmeldecode mitgeschickt"
                    return
                self._seite(200, "Angemeldet", "Du bist mit deinem KIplatz-Konto angemeldet. Im Programm geht es weiter.", weiter=lauf.platzl_weiter())
                lauf._code = code

        self._srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._srv.timeout = 1.0
        self._code: str | None = None
        params = {"client_id": self.konfig["client_id"], "redirect_uri": self._rueckkehr(), "response_type": "code",
                  "scope": self.konfig.get("scope") or SCOPE, "state": self.state, "code_challenge": challenge, "code_challenge_method": "S256"}
        self.adresse = str(self.konfig["authorize"]) + "?" + urllib.parse.urlencode(params)
        self.laeuft = True
        self._thread = threading.Thread(target=self._lauf, name="konto-anmeldung", daemon=True)
        self._thread.start()
        try:
            self._browser(self.adresse)
        except Exception:
            pass
        return self.adresse

    def _lauf(self) -> None:
        assert self._srv is not None
        ende = time.time() + self.frist_s
        try:
            while self.laeuft and self._code is None and self.fehler is None and time.time() < ende:
                self._srv.handle_request()
            if self._code is None and self.fehler is None:
                self.fehler = "keine Rückkehr aus dem Browser innerhalb von 5 Minuten; bitte noch einmal auf „Anmelden“ klicken" if self.laeuft else "abgebrochen"
                return
            if self._code is None:
                return
            id_token = self._tauschen(self._code)
            self._danach(id_token)
            self.fertig = True
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            self.fehler = str(detail or exc)[:200] or "die Anmeldung ist fehlgeschlagen"
        finally:
            self.laeuft = False
            try:
                self._srv.server_close()
            except OSError:
                pass

    def _tauschen(self, code: str) -> str:
        daten = urllib.parse.urlencode({"grant_type": "authorization_code", "client_id": self.konfig["client_id"], "code": code,
                                        "redirect_uri": self._rueckkehr(), "code_verifier": self._verifier}).encode("ascii")
        req = urllib.request.Request(str(self.konfig["token"]), data=daten, method="POST",
                                     headers={"User-Agent": _UA, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
        with self._oeffner(req, timeout=20) as r:
            antwort = json.loads(r.read(64 * 1024).decode("utf-8") or "{}")
        token = str(antwort.get("id_token", "")) if isinstance(antwort, dict) else ""
        if token.count(".") != 2:
            raise TokenFehler("KONTO_TOKEN", "die Werkstatt hat keinen Anmeldenachweis geschickt")
        return token

    def platzl_weiter(self) -> str:
        host = urllib.parse.urlsplit(str(self.konfig.get("authorize", ""))).hostname or ""
        return PLATZL_ANMELDEN if host == WERKSTATT_HOST else ""

    def stand(self) -> dict:
        return {"laeuft": self.laeuft, "fertig": self.fertig, "fehler": self.fehler, "adresse": self.adresse if self.laeuft else ""}

    def abbrechen(self) -> None:
        self.laeuft = False


HANDY_ARTEN = ("iPhone", "iPad", "Android-Handy", "Android-Tablet", "Handy", "Tablet", "Mac", "Browser")
PC_ARTEN = ("Windows-PC", "Linux-PC", "Mac")
