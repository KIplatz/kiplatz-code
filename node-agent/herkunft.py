# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import unicodedata
from pathlib import Path

SCHLUESSEL_DATEI = "herkunft-schluessel.pem"
VERSION = 1
VON = "KIplatz"
TEXT_MAX = 60_000


def normalisiert(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(text)).split())


def pruefsumme(text: str) -> str:
    return hashlib.sha256(normalisiert(text).encode("utf-8")).hexdigest()


def _nachricht(tag: str, summe: str) -> bytes:
    return f"KIplatz-KI-Etikett/{VERSION}|{tag}|{summe}".encode("ascii")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    s = str(s)
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def etikett_ohne_unterschrift(text: str) -> dict:
    return {"v": VERSION, "ki_erzeugt": True, "von": VON, "tag": time.strftime("%Y-%m-%d", time.gmtime()), "pruefsumme": pruefsumme(text)}


class Herkunft:
    def __init__(self, ordner: Path) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        p = Path(ordner) / SCHLUESSEL_DATEI
        if not p.exists():
            roh = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                            serialization.NoEncryption())
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".neu")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(roh)
            os.replace(tmp, p)
        self._privat = serialization.load_pem_private_key(p.read_bytes(), password=None)
        if not isinstance(self._privat, Ed25519PrivateKey):
            raise ValueError("herkunft-schluessel ist kein Ed25519-Schlüssel")
        self._oeffentlich = self._privat.public_key()
        self.oeffentlich_b64 = _b64(self._oeffentlich.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))

    def etikett(self, text: str, *, tag: str | None = None) -> dict:
        tag = tag or time.strftime("%Y-%m-%d", time.gmtime())
        summe = pruefsumme(text)
        return {"v": VERSION, "ki_erzeugt": True, "von": VON, "tag": tag, "pruefsumme": summe,
                "unterschrift": _b64(self._privat.sign(_nachricht(tag, summe)))}

    def pruefen(self, text: str, etikett: dict) -> dict:
        try:
            if not isinstance(etikett, dict) or len(str(text)) > TEXT_MAX:
                return {"echt": False, "grund": "kein gültiges Etikett"}
            tag, summe, sig = str(etikett.get("tag", ""))[:10], str(etikett.get("pruefsumme", ""))[:64], str(etikett.get("unterschrift", ""))[:200]
            if len(tag) != 10 or len(summe) != 64 or not all(c in "0123456789abcdef" for c in summe) or not sig:
                return {"echt": False, "grund": "kein gültiges Etikett"}
            self._oeffentlich.verify(_unb64(sig), _nachricht(tag, summe))
        except Exception:
            return {"echt": False, "grund": "die Unterschrift stammt nicht von KIplatz"}
        if summe != pruefsumme(text):
            return {"echt": False, "grund": "das Etikett ist echt, aber der Text wurde verändert"}
        return {"echt": True, "tag": tag, "von": VON}


def etikett_aus_text(zeile: str) -> dict | None:
    s = str(zeile).strip()
    if not (s.startswith("<!-- kiplatz-ki ") and s.endswith("-->")):
        return None
    try:
        d = json.loads(s[len("<!-- kiplatz-ki "):-3].strip())
    except ValueError:
        return None
    return d if isinstance(d, dict) else None
