# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import http.server
import ipaddress
import json
import os
import platform
import secrets
import socket
import ssl
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import geheim
import sicher_schreiben

try:
    import win32crypt
except ImportError:
    win32crypt = None

PORT = 8443
DIRNAME = "heimnetz"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_GUELTIG_S = 600
CODE_FEHLVERSUCHE = 5
HANDSCHLAG_S = 10
LESEN_S = 60
KOPPEL_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "maxmem": 64 * 1024 * 1024, "dklen": 32}
KOPPEL_STUFE = 2
MAX_BODY = 256 * 1024
MAX_NACHRICHTEN = 40
MAX_TEXT = 20000
VERBINDEN_TIMEOUT_S = 6.0
ANTWORT_TIMEOUT_S = 600.0
_TLS_MIN = ssl.TLSVersion.TLSv1_3
_UA = "CommunityAI-Heimnetz/1"


class HeimnetzError(app_core.AppError):
    pass


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomar_schreiben(pfad: Path, daten: bytes) -> None:
    app_core.ensure_plain_directory(pfad.parent)
    sicher_schreiben.roh(pfad, daten)


def ist_heimnetz(ip: str, *, loopback_erlaubt: bool = False) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.is_unspecified or a.is_multicast or a.is_reserved:
        return False
    if a.is_loopback:
        return loopback_erlaubt
    return a.is_private or a.is_link_local


def heimnetz_adressen() -> list[str]:
    gefunden: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ist_heimnetz(ip) and ip not in gefunden:
                gefunden.append(ip)
    except OSError:
        pass
    return gefunden


def geraet_name() -> str:
    return (platform.node() or "dieses-Geraet")[:24]


def spki_sha256_hex(cert_der: bytes) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    cert = x509.load_der_x509_certificate(cert_der)
    spki = cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).hexdigest()


def zertifikat_erzeugen(name: str, adressen: list[str], *, tage: int = 3650) -> tuple[bytes, bytes]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name[:64])])
    san: list[x509.GeneralName] = [x509.DNSName(name), x509.DNSName(f"{name}.local")]
    for a in adressen:
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(a)))
        except ValueError:
            continue
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=tage))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(key, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM),
            key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def _koppel_schluessel(code: str, nonce: str, spki: str) -> bytes:
    return hashlib.scrypt(code.encode("utf-8"), salt=("KIplatz Heimnetz|" + nonce + "|" + spki).encode("utf-8"), **KOPPEL_SCRYPT)


def _beweis(code: str, rolle: str, nonce: str, spki: str, geraet: str, *, schluessel: bytes | None = None) -> str:
    msg = "|".join((rolle, nonce, spki, geraet)).encode("utf-8")
    return hmac.new(schluessel if schluessel is not None else _koppel_schluessel(code, nonce, spki), msg, hashlib.sha256).hexdigest()


def code_neu() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return raw[:4] + "-" + raw[4:]


def code_normalisieren(code: str) -> str:
    return "".join(ch for ch in str(code).upper() if ch in CODE_ALPHABET)


class Geraeteliste:
    def __init__(self, base_dir: Path) -> None:
        self.pfad = Path(base_dir) / DIRNAME / "geraete.json"
        self._sperre = threading.Lock()

    def _laden(self) -> list[dict]:
        if not self.pfad.exists():
            return []
        try:
            d = json.loads(self.pfad.read_bytes()[:MAX_BODY].decode("utf-8"))
            if not isinstance(d, list):
                raise ValueError
            return [g for g in d if isinstance(g, dict) and isinstance(g.get("token_sha256"), str) and len(g["token_sha256"]) == 64]
        except (OSError, ValueError):
            raise HeimnetzError("HEIMNETZ_GERAETE", "die Geräteliste ist beschädigt; sie wird nicht überschrieben") from None

    def _speichern(self, liste: list[dict]) -> None:
        _atomar_schreiben(self.pfad, (json.dumps(liste, ensure_ascii=False, indent=2) + os.linesep).encode("utf-8"))

    def liste(self) -> list[dict]:
        return [{"name": g["name"], "seit": g["seit"], "zuletzt": g.get("zuletzt"), "fragen": int(g.get("fragen", 0))} for g in self._laden()]

    def hinzufuegen(self, name: str, token: str) -> None:
        with self._sperre:
            liste = [g for g in self._laden() if g["name"] != name]
            liste.append({"name": app_core._mask(name)[:24], "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(), "seit": _jetzt(), "zuletzt": None, "fragen": 0})
            self._speichern(liste)

    def entfernen(self, name: str) -> bool:
        with self._sperre:
            liste = self._laden()
            neu = [g for g in liste if g["name"] != name]
            if len(neu) == len(liste):
                return False
            self._speichern(neu)
            return True

    def pruefen(self, token: str) -> str | None:
        h = hashlib.sha256(token.encode("ascii")).hexdigest()
        for g in self._laden():
            if hmac.compare_digest(g["token_sha256"], h):
                return g["name"]
        return None

    def gefragt(self, name: str) -> None:
        with self._sperre:
            liste = self._laden()
            if not any(g["name"] == name for g in liste):
                return
            for g in liste:
                if g["name"] == name:
                    g["zuletzt"] = _jetzt()
                    g["fragen"] = int(g.get("fragen", 0)) + 1
            self._speichern(liste)


@dataclass
class Kopplung:
    code: str
    bis: float
    fehlversuche: int = 0

    def offen(self) -> bool:
        return time.time() < self.bis and self.fehlversuche < CODE_FEHLVERSUCHE


FrageFn = Callable[[list[dict], Callable[[str], None] | None], object]


class Dienst:

    def __init__(self, base_dir: Path, *, frage_fn: FrageFn, name: str | None = None, kontobuch=None, port: int = PORT,
                 adresse: str | None = None, loopback_erlaubt: bool = False, ki_beschreibung: Callable[[], str] = lambda: "",
                 wissen_fn: Callable[[dict], dict] | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.dir = self.base_dir / DIRNAME / "dienst"
        self.cert_pfad, self.key_pfad = self.dir / "geraet-zertifikat.pem", self.dir / "geraet-schluessel.pem"
        self.geraete = Geraeteliste(base_dir)
        self._frage_fn = frage_fn
        self._kontobuch = kontobuch
        self.name = name or geraet_name()
        self.port = port
        self._adresse = adresse
        self._loopback = loopback_erlaubt
        self._ki_beschreibung = ki_beschreibung
        self._wissen_fn = wissen_fn
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._frage_lock = threading.Lock()
        self.kopplung: Kopplung | None = None
        self.fingerprint: str | None = None
        self.adresse: str | None = None
        self.protokoll: Callable[[str], None] = lambda _line: None


    def _zertifikat_sicherstellen(self) -> tuple[Path, Path]:
        if not (self.cert_pfad.is_file() and self.key_pfad.is_file()):
            cert_pem, key_pem = zertifikat_erzeugen(self.name, heimnetz_adressen())
            app_core.ensure_plain_directory(self.dir)
            _atomar_schreiben(self.key_pfad, geheim.schuetzen(key_pem.decode("ascii"), "CommunityAI Heimnetz").encode("ascii"))
            _atomar_schreiben(self.cert_pfad, cert_pem)
        else:
            roh = self.key_pfad.read_text(encoding="ascii")
            if not geheim.geschuetzt(roh):
                _atomar_schreiben(self.key_pfad, geheim.schuetzen(roh, "CommunityAI Heimnetz").encode("ascii"))
        self.fingerprint = spki_sha256_hex(ssl.PEM_cert_to_DER_cert(self.cert_pfad.read_text(encoding="ascii")))
        return self.cert_pfad, self.key_pfad

    def _schluessel_pem(self) -> bytes:
        try:
            return geheim.lesen(self.key_pfad.read_text(encoding="ascii")).encode("ascii")
        except geheim.GeheimError as exc:
            raise HeimnetzError("HEIMNETZ_SCHLUESSEL", exc.detail) from None


    def laeuft(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.laeuft():
                return
            adresse = self._adresse
            if adresse is None:
                kandidaten = heimnetz_adressen()
                if not kandidaten:
                    raise HeimnetzError("HEIMNETZ_ADRESSE", "dieses Gerät hat gerade keine Adresse im Heimnetz (WLAN oder Kabel verbunden?)")
                adresse = kandidaten[0]
            if not ist_heimnetz(adresse, loopback_erlaubt=self._loopback):
                raise HeimnetzError("HEIMNETZ_ADRESSE", f"{adresse} ist keine Adresse im eigenen Netz")
            cert, key = self._zertifikat_sicherstellen()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = _TLS_MIN
            klar = key.with_name(key.name + ".laden")
            try:
                _atomar_schreiben(klar, self._schluessel_pem())
                ctx.load_cert_chain(str(cert), str(klar))
            finally:
                try:
                    klar.unlink()
                except OSError:
                    pass
            dienst = self

            class Handler(_Handler):
                pass

            class Server(http.server.ThreadingHTTPServer):
                def finish_request(self, request, client_address) -> None:
                    if isinstance(request, ssl.SSLSocket):
                        request.settimeout(HANDSCHLAG_S)
                        request.do_handshake()
                    super().finish_request(request, client_address)

                def handle_error(self, request, client_address) -> None:
                    dienst.protokoll(f"INFO heimnetz_verbindung abgebrochen {app_core._mask(client_address[0])}")

            Handler.dienst = dienst
            try:
                srv = Server((adresse, self.port), Handler, bind_and_activate=False)
                srv.allow_reuse_address = False
                srv.daemon_threads = True
                srv.server_bind()
                srv.server_activate()
            except OSError as exc:
                raise HeimnetzError("HEIMNETZ_PORT", f"Anschluss {self.port} auf {app_core._mask(adresse)} lässt sich nicht öffnen ({exc.strerror or exc})") from None
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)
            self._server, self.adresse = srv, adresse
            self._thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.3}, name="heimnetz-dienst", daemon=True)
            self._thread.start()
            self.protokoll(f"OK heimnetz_dienst_start {app_core._mask(adresse)}:{self.port}")

    def stop(self) -> None:
        with self._lock:
            srv, self._server = self._server, None
            self.kopplung = None
            if srv is not None:
                srv.shutdown()
                srv.server_close()
                self.protokoll("OK heimnetz_dienst_stop")
            self._thread = None


    def koppeln_oeffnen(self) -> str:
        if not self.laeuft():
            raise HeimnetzError("HEIMNETZ_AUS", "zuerst „KIplatz im Heimnetz anbieten“ einschalten")
        self.kopplung = Kopplung(code_neu(), time.time() + CODE_GUELTIG_S)
        return self.kopplung.code

    def koppeln_schliessen(self) -> None:
        self.kopplung = None

    def zustand(self) -> dict:
        k = self.kopplung if (self.kopplung and self.kopplung.offen()) else None
        return {"laeuft": self.laeuft(), "name": self.name, "adresse": app_core._mask(self.adresse) if self.adresse else None, "port": self.port,
                "fingerprint": self.fingerprint[:16] if self.fingerprint else None,
                "kopplung": {"code": k.code, "noch_s": max(0, int(k.bis - time.time()))} if k else None,
                "geraete": self.geraete.liste()}


    def _koppeln(self, body: dict) -> tuple[int, dict]:
        k = self.kopplung
        if k is None or not k.offen():
            return 403, {"fehler": "KOPPLUNG_ZU", "text": "auf dem anderen Gerät ist gerade kein Kopplungscode offen"}
        geraet = app_core._mask(str(body.get("geraet", "")))[:24]
        nonce = str(body.get("nonce", ""))
        if not geraet or len(nonce) != 32 or not all(c in "0123456789abcdef" for c in nonce):
            return 400, {"fehler": "ANFRAGE", "text": "Kopplungsanfrage unvollständig"}
        if body.get("stufe") != KOPPEL_STUFE:
            return 403, {"fehler": "CODE_STUFE", "text": "das andere Gerät hat eine ältere KIplatz-Fassung; bitte dort zuerst aktualisieren, dann neu koppeln"}
        schluessel = _koppel_schluessel(code_normalisieren(k.code), nonce, self.fingerprint or "")
        erwartet = _beweis("", "geraet", nonce, self.fingerprint or "", geraet, schluessel=schluessel)
        if not hmac.compare_digest(erwartet, str(body.get("beweis", ""))):
            k.fehlversuche += 1
            self.protokoll(f"ABGELEHNT heimnetz_koppeln falscher Code ({k.fehlversuche}/{CODE_FEHLVERSUCHE})")
            return 403, {"fehler": "CODE", "text": "der Code stimmt nicht"}
        token = secrets.token_hex(32)
        self.geraete.hinzufuegen(geraet, token)
        self.kopplung = None
        self.protokoll(f"OK heimnetz_koppeln {geraet}")
        return 200, {"token": token, "name": self.name, "beweis": _beweis("", "dienst", nonce, self.fingerprint or "", geraet, schluessel=schluessel)}

    def _frage(self, handler: "_Handler", geraet: str, body: dict) -> None:
        nachrichten = body.get("nachrichten")
        if not isinstance(nachrichten, list) or not nachrichten or len(nachrichten) > MAX_NACHRICHTEN:
            handler._json(400, {"fehler": "ANFRAGE", "text": "keine oder zu viele Nachrichten"})
            return
        sauber = []
        for n in nachrichten:
            if not isinstance(n, dict) or n.get("role") not in ("user", "assistant") or not isinstance(n.get("content"), str):
                handler._json(400, {"fehler": "ANFRAGE", "text": "Nachricht in falscher Form"})
                return
            sauber.append({"role": n["role"], "content": n["content"][:MAX_TEXT]})
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.send_header("Connection", "close")
        handler.close_connection = True
        handler.end_headers()

        def chunk(obj: dict) -> None:
            data = ("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8")
            handler.wfile.write(f"{len(data):x}\r\n".encode("ascii") + data + b"\r\n")
            handler.wfile.flush()

        try:
            with self._frage_lock:
                a = self._frage_fn(sauber, lambda stueck: chunk({"stueck": stueck}))
            self.geraete.gefragt(geraet)
            if self._kontobuch is not None:
                self._kontobuch.antwort(geraet=geraet)
            chunk({"ende": {"text": a.text, "gelesen": a.prompt_tokens, "wortstuecke": a.completion_tokens, "dauer_s": a.dauer_s, "geraet": self.name, "ki": self._ki_beschreibung(),
                            "quellen": list(getattr(a, "quellen", []) or []), "im_speicher": int(getattr(a, "im_speicher", 0) or 0)}})
            self.protokoll(f"OK heimnetz_frage {geraet} {a.dauer_s}s")
        except app_core.AppError as exc:
            chunk({"fehler": exc.code, "text": exc.detail})
            self.protokoll(f"ABGELEHNT heimnetz_frage {geraet}: {exc.code}")
        except Exception as exc:
            chunk({"fehler": "INTERN", "text": f"die KI am anderen Gerät hat einen Fehler gemeldet ({type(exc).__name__})"})
            self.protokoll(f"FEHLER heimnetz_frage {geraet}: {type(exc).__name__}: {exc}")
        finally:
            try:
                handler.wfile.write(b"0\r\n\r\n")
                handler.wfile.flush()
            except OSError:
                pass


class _Handler(http.server.BaseHTTPRequestHandler):
    dienst: Dienst
    timeout = LESEN_S
    server_version = "CommunityAI"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        pass

    def _json(self, status: int, obj: dict) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        self.wfile.write(data)

    def _peer_ok(self) -> bool:
        if ist_heimnetz(self.client_address[0], loopback_erlaubt=self.dienst._loopback):
            return True
        self._json(403, {"fehler": "NETZ", "text": "nur aus dem eigenen Heimnetz"})
        return False

    def _body(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self._json(413, {"fehler": "ZU_GROSS", "text": "Anfrage zu groß"})
            return None
        try:
            d = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except ValueError:
            self._json(400, {"fehler": "ANFRAGE", "text": "Anfrage nicht lesbar"})
            return None
        if not isinstance(d, dict):
            self._json(400, {"fehler": "ANFRAGE", "text": "Anfrage nicht lesbar"})
            return None
        return d

    def do_GET(self) -> None:
        if not self._peer_ok():
            return
        if self.path == "/hallo":
            self._json(200, {"name": self.dienst.name, "programm": app_core.APP_NAME, "version": app_core.APP_VERSION, "fingerprint": self.dienst.fingerprint, "ki": self.dienst._ki_beschreibung()})
        else:
            self._json(404, {"fehler": "WEG", "text": "gibt es nicht"})

    def do_POST(self) -> None:
        if not self._peer_ok():
            return
        if self.path == "/koppeln":
            body = self._body()
            if body is not None:
                status, antwort = self.dienst._koppeln(body)
                self._json(status, antwort)
            return
        if self.path in ("/frage", "/wissen"):
            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            geraet = self.dienst.geraete.pruefen(token) if (len(token) == 64 and all(c in "0123456789abcdef" for c in token)) else None
            if geraet is None:
                self._json(401, {"fehler": "NICHT_GEKOPPELT", "text": "dieses Gerät ist nicht (mehr) gekoppelt"})
                return
            body = self._body()
            if body is None:
                return
            if self.path == "/frage":
                self.dienst._frage(self, geraet, body)
                return
            if self.dienst._wissen_fn is None:
                self._json(404, {"fehler": "WEG", "text": "dieses Gerät hat keinen Wissensspeicher"})
                return
            try:
                self._json(200, self.dienst._wissen_fn({**body, "geraet": geraet}))
                self.dienst.protokoll(f"OK heimnetz_wissen {geraet} {str(body.get('was', ''))[:20]}")
            except app_core.AppError as exc:
                self._json(400, {"fehler": exc.code, "text": exc.detail})
            except Exception as exc:
                self._json(500, {"fehler": "INTERN", "text": f"Fehler am anderen Gerät ({type(exc).__name__})"})
                self.dienst.protokoll(f"FEHLER heimnetz_wissen {geraet}: {type(exc).__name__}: {exc}")
            return
        self._json(404, {"fehler": "WEG", "text": "gibt es nicht"})


def _token_schuetzen(token: str) -> str:
    return geheim.schuetzen(token, "CommunityAI Heimnetz")


def _token_lesen(wert: str) -> str:
    if not geheim.geschuetzt(wert):
        raise HeimnetzError("HEIMNETZ_SCHLUESSEL", "die Verbindungsdatei ist beschädigt")
    try:
        return geheim.lesen(wert)
    except geheim.GeheimError as exc:
        raise HeimnetzError("HEIMNETZ_SCHLUESSEL", "der Geräteschlüssel gehört zu einem anderen Windows-Benutzer" if exc.code == "GEHEIM_BENUTZER"
                            else "der Geräteschlüssel lässt sich auf diesem Gerät nicht entschlüsseln") from None


class _IPv4HTTPSConnection(http.client.HTTPSConnection):

    def connect(self) -> None:
        infos: list = []
        for name in (self.host, self.host + ".local") if "." not in self.host else (self.host,):
            try:
                infos = socket.getaddrinfo(name, self.port, socket.AF_INET, socket.SOCK_STREAM)
            except OSError:
                infos = []
            if infos:
                break
        if not infos:
            raise OSError(f"{self.host} hat keine IPv4-Adresse")
        ip = infos[0][4][0]
        if not ist_heimnetz(ip, loopback_erlaubt=self._loopback):
            raise HeimnetzError("HEIMNETZ_ADRESSE", f"{app_core._mask(self.host)} liegt nicht im eigenen Heimnetz")
        self.sock = socket.create_connection((ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _verbindung(host: str, port: int, ctx: ssl.SSLContext, timeout: float, loopback_erlaubt: bool) -> _IPv4HTTPSConnection:
    c = _IPv4HTTPSConnection(host, port, timeout=timeout, context=ctx)
    c._loopback = loopback_erlaubt
    return c


@dataclass(frozen=True)
class Verbindungsdaten:
    host: str
    port: int
    name: str
    zertifikat_pem: str
    fingerprint: str
    seit: str


@dataclass(frozen=True)
class FernAntwort:
    text: str
    prompt_tokens: int
    completion_tokens: int
    dauer_s: float
    geraet: str
    ki: str
    quellen: tuple = ()
    im_speicher: int = 0


class Verbindung:

    def __init__(self, base_dir: Path, *, geraet_name_eigen: str | None = None, loopback_erlaubt: bool = False) -> None:
        self.pfad = Path(base_dir) / DIRNAME / "verbindung.json"
        self.eigen = geraet_name_eigen or geraet_name()
        self._loopback = loopback_erlaubt


    def daten(self) -> Verbindungsdaten | None:
        if not self.pfad.exists():
            return None
        try:
            d = json.loads(self.pfad.read_bytes()[:MAX_BODY].decode("utf-8"))
            return Verbindungsdaten(str(d["host"]), int(d["port"]), str(d["name"]), str(d["zertifikat_pem"]), str(d["fingerprint"]), str(d["seit"]))
        except (OSError, ValueError, KeyError, TypeError):
            raise HeimnetzError("HEIMNETZ_VERBINDUNG", "die Verbindungsdatei ist beschädigt; sie wird nicht überschrieben") from None

    def _token(self) -> str:
        d = json.loads(self.pfad.read_bytes()[:MAX_BODY].decode("utf-8"))
        return _token_lesen(str(d["token"]))

    def trennen(self) -> bool:
        if not self.pfad.exists():
            return False
        self.pfad.unlink()
        return True


    @staticmethod
    def _ctx_gepinnt(pem: str) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = _TLS_MIN
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cadata=pem)
        return ctx

    @staticmethod
    def _ctx_unbekannt() -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = _TLS_MIN
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


    def koppeln(self, host: str, code: str, *, port: int = PORT) -> Verbindungsdaten:
        host = str(host).strip().rstrip(".")
        if host.count(":") == 1 and host.rsplit(":", 1)[1].isdigit():
            host, port = host.rsplit(":", 1)[0], int(host.rsplit(":", 1)[1])
        if not host or any(ch in host for ch in " /\\:@"):
            raise HeimnetzError("HEIMNETZ_NAME", "bitte den Gerätenamen so eintippen, wie ihn das andere Gerät anzeigt")
        code_n = code_normalisieren(code)
        if len(code_n) != 8:
            raise HeimnetzError("HEIMNETZ_CODE", "der Code hat 8 Zeichen, zum Beispiel ABCD-EFGH")
        nonce = secrets.token_hex(16)
        conn = _verbindung(host, port, self._ctx_unbekannt(), VERBINDEN_TIMEOUT_S, self._loopback)
        try:
            try:
                conn.connect()
            except HeimnetzError:
                raise
            except (OSError, ssl.SSLError) as exc:
                raise HeimnetzError("HEIMNETZ_UNERREICHBAR", f"{app_core._mask(host)} antwortet nicht ({type(exc).__name__}); ist das Programm dort geöffnet und „im Heimnetz anbieten“ an?") from None
            der = conn.sock.getpeercert(binary_form=True)
            if not der:
                raise HeimnetzError("HEIMNETZ_ZERTIFIKAT", "das andere Gerät hat kein Zertifikat gezeigt")
            spki = spki_sha256_hex(der)
            schluessel = _koppel_schluessel(code_n, nonce, spki)
            body = json.dumps({"geraet": self.eigen, "nonce": nonce, "stufe": KOPPEL_STUFE, "beweis": _beweis("", "geraet", nonce, spki, self.eigen, schluessel=schluessel)}).encode("utf-8")
            conn.request("POST", "/koppeln", body=body, headers={"Content-Type": "application/json", "Content-Length": str(len(body)), "User-Agent": _UA})
            r = conn.getresponse()
            antwort = json.loads(r.read(MAX_BODY).decode("utf-8") or "{}")
            if r.status != 200:
                raise HeimnetzError("HEIMNETZ_KOPPELN", str(antwort.get("text") or f"Antwort {r.status}"))
            if not hmac.compare_digest(str(antwort.get("beweis", "")), _beweis("", "dienst", nonce, spki, self.eigen, schluessel=schluessel)):
                raise HeimnetzError("HEIMNETZ_KOPPELN", "das andere Gerät kennt den Code nicht; nicht gekoppelt")
            token = str(antwort.get("token", ""))
            if len(token) != 64:
                raise HeimnetzError("HEIMNETZ_KOPPELN", "das andere Gerät hat keinen Geräteschlüssel geschickt")
        finally:
            conn.close()
        daten = Verbindungsdaten(host, port, app_core._mask(str(antwort.get("name") or host))[:24], ssl.DER_cert_to_PEM_cert(der), spki, _jetzt())
        _atomar_schreiben(self.pfad, (json.dumps({"host": daten.host, "port": daten.port, "name": daten.name, "zertifikat_pem": daten.zertifikat_pem, "fingerprint": daten.fingerprint,
                                                  "seit": daten.seit, "token": _token_schuetzen(token)}, ensure_ascii=False, indent=2) + os.linesep).encode("utf-8"))
        return daten


    def _offen(self, timeout: float) -> tuple[Verbindungsdaten, _IPv4HTTPSConnection]:
        d = self.daten()
        if d is None:
            raise HeimnetzError("HEIMNETZ_NICHT_GEKOPPELT", "noch mit keinem Gerät gekoppelt (Einstellungen)")
        conn = _verbindung(d.host, d.port, self._ctx_gepinnt(d.zertifikat_pem), timeout, self._loopback)
        try:
            conn.connect()
        except HeimnetzError:
            raise
        except (OSError, ssl.SSLError) as exc:
            conn.close()
            raise HeimnetzError("HEIMNETZ_UNERREICHBAR", f"{d.name} antwortet nicht ({type(exc).__name__}); ist das Programm dort geöffnet und „im Heimnetz anbieten“ an?") from None
        der = conn.sock.getpeercert(binary_form=True)
        if not der or not hmac.compare_digest(spki_sha256_hex(der), d.fingerprint):
            conn.close()
            raise HeimnetzError("HEIMNETZ_ZERTIFIKAT", f"{d.name} zeigt ein anderes Zertifikat als beim Koppeln; aus Vorsicht keine Verbindung. Neu koppeln, wenn das Gerät neu eingerichtet wurde.")
        return d, conn

    def hallo(self) -> dict:
        d, conn = self._offen(VERBINDEN_TIMEOUT_S)
        try:
            conn.request("GET", "/hallo", headers={"User-Agent": _UA})
            r = conn.getresponse()
            antwort = json.loads(r.read(MAX_BODY).decode("utf-8") or "{}")
            if r.status != 200:
                raise HeimnetzError("HEIMNETZ_ANTWORT", str(antwort.get("text") or f"Antwort {r.status}"))
            return {"name": d.name, "ki": str(antwort.get("ki", "")), "version": str(antwort.get("version", ""))}
        finally:
            conn.close()

    def wissen(self, auftrag: dict) -> dict:
        d, conn = self._offen(VERBINDEN_TIMEOUT_S if auftrag.get("was") != "seite" else 30.0)
        try:
            body = json.dumps(auftrag, ensure_ascii=False).encode("utf-8")
            conn.request("POST", "/wissen", body=body, headers={"Content-Type": "application/json", "Content-Length": str(len(body)), "Authorization": "Bearer " + self._token(), "User-Agent": _UA})
            r = conn.getresponse()
            antwort = json.loads(r.read(MAX_BODY).decode("utf-8") or "{}")
            if r.status != 200:
                raise HeimnetzError("HEIMNETZ_" + str(antwort.get("fehler") or "ANTWORT"), str(antwort.get("text") or f"Antwort {r.status}"))
            return antwort
        except (OSError, ssl.SSLError) as exc:
            raise HeimnetzError("HEIMNETZ_ABBRUCH", f"die Verbindung zu {d.name} ist abgerissen ({type(exc).__name__})") from None
        finally:
            conn.close()

    def frage(self, nachrichten: list[dict], *, on_token: Callable[[str], None] | None = None) -> FernAntwort:
        d, conn = self._offen(ANTWORT_TIMEOUT_S)
        try:
            body = json.dumps({"nachrichten": nachrichten[-MAX_NACHRICHTEN:]}, ensure_ascii=False).encode("utf-8")
            conn.request("POST", "/frage", body=body, headers={"Content-Type": "application/json", "Content-Length": str(len(body)), "Authorization": "Bearer " + self._token(), "User-Agent": _UA})
            r = conn.getresponse()
            if r.status != 200:
                antwort = json.loads(r.read(MAX_BODY).decode("utf-8") or "{}")
                raise HeimnetzError("HEIMNETZ_ANTWORT", str(antwort.get("text") or f"Antwort {r.status}"))
            stuecke: list[str] = []
            ende: dict | None = None
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if "stueck" in ev:
                    stuecke.append(ev["stueck"])
                    if on_token is not None:
                        on_token(ev["stueck"])
                elif "ende" in ev:
                    ende = ev["ende"]
                elif "fehler" in ev:
                    raise HeimnetzError("HEIMNETZ_" + str(ev["fehler"]), str(ev.get("text") or "Fehler am anderen Gerät"))
            if ende is None:
                raise HeimnetzError("HEIMNETZ_ABBRUCH", f"die Verbindung zu {d.name} ist mitten in der Antwort abgerissen")
            text = str(ende.get("text") or "".join(stuecke))
            quellen = tuple(q for q in (ende.get("quellen") or []) if isinstance(q, dict))
            return FernAntwort(text.strip(), int(ende.get("gelesen", 0)), int(ende.get("wortstuecke", 0)), float(ende.get("dauer_s", 0.0)), str(ende.get("geraet") or d.name), str(ende.get("ki", "")),
                               quellen, int(ende.get("im_speicher", 0) or 0))
        except (OSError, ssl.SSLError) as exc:
            raise HeimnetzError("HEIMNETZ_ABBRUCH", f"die Verbindung zu {d.name} ist abgerissen ({type(exc).__name__})") from None
        finally:
            conn.close()


__all__ = ["PORT", "DIRNAME", "HeimnetzError", "Dienst", "Verbindung", "Verbindungsdaten", "FernAntwort", "Geraeteliste", "Kopplung",
           "zertifikat_erzeugen", "spki_sha256_hex", "heimnetz_adressen", "ist_heimnetz", "code_neu", "code_normalisieren", "geraet_name"]
