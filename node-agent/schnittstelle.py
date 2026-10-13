# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hmac
import ipaddress
import json
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import hausordnung
import herkunft

PORT = 8470
MAX_BODY = 256 * 1024
MAX_NACHRICHTEN = 40
MAX_ZEICHEN = 60_000
MAX_TOKENS = 1500
MODELL_NAME = "unser-modell"
ROLLEN = ("system", "user", "assistant")
HOSTS_GERAET = ("127.0.0.1", "localhost")
HOST_DOCKER = "host.docker.internal"


def schluessel_neu() -> str:
    return "cai-" + secrets.token_urlsafe(24)


def von_diesem_geraet(quelle: str) -> bool:
    try:
        a = ipaddress.ip_address(quelle.split("%")[0])
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped is not None:
        a = a.ipv4_mapped
    return a.is_loopback


def host_name(kopf: str) -> str:
    h = (kopf or "").strip().lower()
    if h.startswith("["):
        return ""
    return h.split(":")[0]


def tuer_pruefen(quelle: str, host_kopf: str, docker: bool) -> str | None:
    if not von_diesem_geraet(quelle):
        return "nur von diesem Gerät aus (127.0.0.1)"
    host = host_name(host_kopf)
    if host in HOSTS_GERAET:
        return None
    if host == HOST_DOCKER:
        return None if docker else "Programme in Docker brauchen im Programm unter „Einstellungen“ den Schalter „Auch Programme in Docker auf diesem PC dürfen fragen“"
    return "nur von diesem Gerät aus (127.0.0.1)"


@dataclass
class Auftrag:
    nachrichten: list[dict]
    anweisung: str
    max_tokens: int
    temperature: float
    stream: bool


@dataclass
class Ergebnis:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class SchnittstellenFehler(Exception):
    def __init__(self, status: int, text: str) -> None:
        super().__init__(text)
        self.status, self.text = status, text


def auftrag_lesen(body: dict) -> Auftrag:
    roh = body.get("messages")
    if not isinstance(roh, list) or not roh:
        raise SchnittstellenFehler(400, "messages fehlt oder ist leer")
    if len(roh) > MAX_NACHRICHTEN:
        raise SchnittstellenFehler(400, f"höchstens {MAX_NACHRICHTEN} Nachrichten je Anfrage")
    nachrichten, anweisung, gesamt = [], [], 0
    for m in roh:
        if not isinstance(m, dict) or m.get("role") not in ROLLEN:
            raise SchnittstellenFehler(400, "jede Nachricht braucht role (system, user, assistant) und content")
        c = m.get("content")
        if isinstance(c, list):
            c = "\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict) and p.get("type") == "text")
        if not isinstance(c, str):
            raise SchnittstellenFehler(400, "content muss Text sein")
        gesamt += len(c)
        if gesamt > MAX_ZEICHEN:
            raise SchnittstellenFehler(400, f"zusammen höchstens {MAX_ZEICHEN} Zeichen je Anfrage")
        if m["role"] == "system":
            anweisung.append(c.strip())
        else:
            nachrichten.append({"role": m["role"], "content": c})
    if not nachrichten or nachrichten[-1]["role"] != "user":
        raise SchnittstellenFehler(400, "die letzte Nachricht muss von der Person kommen (role user)")
    b = hausordnung.pruefen("\n".join(x["content"] for x in nachrichten if x["role"] == "user") + "\n" + "\n".join(anweisung))
    if not b.ok:
        raise SchnittstellenFehler(400, f"Das gehört nicht in diese Community ({b.grund}). {hausordnung.HAUSORDNUNG}")
    try:
        max_tokens = max(1, min(int(body.get("max_tokens") or 700), MAX_TOKENS))
        temperature = max(0.0, min(float(body.get("temperature") if body.get("temperature") is not None else 0.3), 1.0))
    except (TypeError, ValueError):
        raise SchnittstellenFehler(400, "max_tokens und temperature müssen Zahlen sein") from None
    return Auftrag(nachrichten, "\n\n".join(a for a in anweisung if a)[:8000], max_tokens, temperature, bool(body.get("stream")))


class Schnittstelle:

    def __init__(self, antworten: Callable[[Auftrag, Callable[[str], None] | None], Ergebnis], schluessel: Callable[[], str | None],
                 *, port: int = PORT, log: Callable[[str], None] | None = None, docker: Callable[[], bool] | None = None) -> None:
        self._antworten = antworten
        self._schluessel = schluessel
        self._docker = docker or (lambda: False)
        self._port_wunsch = port
        self._log = log or (lambda s: None)
        self._srv: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._reihe = threading.Lock()
        self.port: int | None = None
        self.anfragen = 0

    def laeuft(self) -> bool:
        return self._srv is not None

    def start(self) -> None:
        if self._srv is not None:
            return
        aussen = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                pass

            def _rest_lesen(self) -> bytes:
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = 0
                return self.rfile.read(min(max(n, 0), MAX_BODY)) if n > 0 else b""

            def _json(self, status: int, daten: dict) -> None:
                self.close_connection = True
                raw = json.dumps(daten, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)

            def _fehler(self, status: int, text: str) -> None:
                self._json(status, {"error": {"message": text, "type": "invalid_request_error" if status == 400 else "server_error"}})

            def _zugelassen(self) -> bool:
                self._rest = self._rest_lesen()
                try:
                    docker = bool(aussen._docker())
                except Exception:
                    docker = False
                grund = tuer_pruefen(str(self.client_address[0]), self.headers.get("Host") or "", docker)
                if grund is not None:
                    aussen._log("ABGELEHNT schnittstelle: " + ("fremde Quelle" if not von_diesem_geraet(str(self.client_address[0])) else "fremder Host-Kopf"))
                    self._fehler(403, grund)
                    return False
                key = aussen._schluessel()
                auth = self.headers.get("Authorization") or ""
                gegeben = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
                if not key or not gegeben or not hmac.compare_digest(gegeben.encode(), key.encode()):
                    aussen._log("ABGELEHNT schnittstelle: Schlüssel fehlt oder falsch")
                    self.close_connection = True
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Bearer")
                    raw = json.dumps({"error": {"message": "der Schlüssel fehlt oder stimmt nicht; er steht im Programm unter „Einstellungen“", "type": "authentication_error"}}, ensure_ascii=False).encode("utf-8")
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return False
                return True

            def do_OPTIONS(self):
                self._fehler(403, "nicht für Browser-Seiten")

            def do_GET(self):
                if not self._zugelassen():
                    return
                if self.path.split("?")[0] in ("/v1/models", "/models"):
                    self._json(200, {"object": "list", "data": [{"id": MODELL_NAME, "object": "model", "owned_by": "community-ai", "created": 0}]})
                    return
                self._fehler(404, "es gibt hier /v1/models und /v1/chat/completions")

            def do_POST(self):
                if not self._zugelassen():
                    return
                if self.path.split("?")[0] not in ("/v1/chat/completions", "/chat/completions"):
                    self._fehler(404, "es gibt hier /v1/models und /v1/chat/completions")
                    return
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = 0
                if n <= 0 or n > MAX_BODY:
                    self._fehler(400 if n else 411, f"Anfrage fehlt oder ist größer als {MAX_BODY // 1024} kB")
                    return
                try:
                    body = json.loads(self._rest.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError
                    auftrag = auftrag_lesen(body)
                except SchnittstellenFehler as exc:
                    aussen._log(f"ABGELEHNT schnittstelle: {exc.text[:80]}")
                    self._fehler(exc.status, exc.text)
                    return
                except (ValueError, UnicodeDecodeError):
                    self._fehler(400, "kein gültiges JSON")
                    return
                kennung = "chatcmpl-" + secrets.token_hex(8)
                t0 = int(time.time())
                aussen.anfragen += 1
                with aussen._reihe:
                    if not auftrag.stream:
                        try:
                            e = aussen._antworten(auftrag, None)
                        except Exception as exc:
                            aussen._log(f"ABGELEHNT schnittstelle antwort: {type(exc).__name__}: {str(exc)[:120]}")
                            self._fehler(503, getattr(exc, "detail", None) or str(exc) or "KIplatz kann gerade nicht antworten")
                            return
                        self._json(200, {"id": kennung, "object": "chat.completion", "created": t0, "model": MODELL_NAME,
                                         "choices": [{"index": 0, "message": {"role": "assistant", "content": e.text}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": e.prompt_tokens, "completion_tokens": e.completion_tokens, "total_tokens": e.prompt_tokens + e.completion_tokens},
                                         "kiplatz_etikett": herkunft.etikett_ohne_unterschrift(e.text)})
                        return
                    self.close_connection = True
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    offen = [True]

                    def stueck(delta: dict, ende: str | None = None, usage: dict | None = None, etikett: dict | None = None) -> None:
                        if not offen[0]:
                            return
                        d = {"id": kennung, "object": "chat.completion.chunk", "created": t0, "model": MODELL_NAME,
                             "choices": [{"index": 0, "delta": delta, "finish_reason": ende}]}
                        if usage is not None:
                            d["usage"] = usage
                        if etikett is not None:
                            d["kiplatz_etikett"] = etikett
                        try:
                            self.wfile.write(b"data: " + json.dumps(d, ensure_ascii=False).encode("utf-8") + b"\n\n")
                            self.wfile.flush()
                        except OSError:
                            offen[0] = False
                    stueck({"role": "assistant", "content": ""})
                    try:
                        e = aussen._antworten(auftrag, lambda piece: stueck({"content": piece}))
                    except Exception as exc:
                        aussen._log(f"ABGELEHNT schnittstelle antwort: {type(exc).__name__}: {str(exc)[:120]}")
                        stueck({"content": "\n\n" + (getattr(exc, "detail", None) or str(exc) or "KIplatz kann gerade nicht antworten")}, "stop")
                    else:
                        stueck({}, "stop", {"prompt_tokens": e.prompt_tokens, "completion_tokens": e.completion_tokens, "total_tokens": e.prompt_tokens + e.completion_tokens},
                               herkunft.etikett_ohne_unterschrift(e.text))
                    if offen[0]:
                        try:
                            self.wfile.write(b"data: [DONE]\n\n")
                            self.wfile.flush()
                        except OSError:
                            pass
                    self.close_connection = True

        try:
            srv = ThreadingHTTPServer(("127.0.0.1", self._port_wunsch), Handler)
        except OSError as exc:
            raise SchnittstellenFehler(503, f"Anschluss {self._port_wunsch} auf diesem Gerät ist belegt ({exc.strerror or exc}); vielleicht läuft das Programm schon zweimal") from None
        srv.daemon_threads = True
        self._srv, self.port = srv, int(srv.server_address[1])
        self._thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5}, name="schnittstelle", daemon=True)
        self._thread.start()
        self._log(f"OK schnittstelle_start 127.0.0.1:{self.port}")

    def stop(self) -> None:
        srv, self._srv = self._srv, None
        if srv is None:
            return
        try:
            srv.shutdown()
            srv.server_close()
        except OSError:
            pass
        self.port = None
        self._log("OK schnittstelle_stop")

    def zustand(self) -> dict:
        port = self.port or self._port_wunsch
        try:
            docker = bool(self._docker())
        except Exception:
            docker = False
        return {"an": self.laeuft(), "port": port, "adresse": f"http://127.0.0.1:{port}/v1",
                "modell": MODELL_NAME, "anfragen": self.anfragen, "docker": docker, "adresse_docker": f"http://{HOST_DOCKER}:{port}/v1"}


__all__ = ["Schnittstelle", "SchnittstellenFehler", "Auftrag", "Ergebnis", "auftrag_lesen", "schluessel_neu", "tuer_pruefen",
           "von_diesem_geraet", "PORT", "MODELL_NAME", "HOST_DOCKER"]
