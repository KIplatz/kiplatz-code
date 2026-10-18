# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import os
import secrets
import struct
import time
from pathlib import Path


UDP_PORT = 8447


LAENGE = 64


MAGIC = b"KT"


VERSION = 1


TYP_LEBENSZEICHEN = 1


TYP_SPIEGEL = 2


MAC = 16


_ANFRAGE = struct.Struct("!2sBB8sIII24s")


_ANTWORT = struct.Struct("!2sBB8sI4sH26s")


def _mac(schluessel: bytes, kopf: bytes) -> bytes:
    return hmac.new(schluessel, kopf, hashlib.sha256).digest()[:MAC]


def lebenszeichen(schluessel: bytes, sitzung: bytes, ablauf: int, zaehler: int, jetzt: float | None = None) -> bytes:
    kopf = _ANFRAGE.pack(MAGIC, VERSION, TYP_LEBENSZEICHEN, sitzung, ablauf, zaehler & 0xFFFFFFFF, int(jetzt if jetzt is not None else time.time()) & 0xFFFFFFFF,
                         secrets.token_bytes(24))
    return kopf + _mac(schluessel, kopf)


def spiegel_lesen(schluessel: bytes, sitzung: bytes, daten: bytes) -> tuple[int, str, int] | None:
    if len(daten) != LAENGE:
        return None
    kopf, mac = daten[:-MAC], daten[-MAC:]
    if not hmac.compare_digest(_mac(schluessel, kopf), mac):
        return None
    magic, ver, typ, s, zaehler, ip4, anschluss, _ = _ANTWORT.unpack(kopf)
    if magic != MAGIC or ver != VERSION or typ != TYP_SPIEGEL or s != sitzung:
        return None
    return zaehler, str(ipaddress.IPv4Address(ip4)), anschluss


def hauptschluessel(pfad: Path, *, anlegen: bool = False) -> bytes:
    try:
        d = pfad.read_bytes()
        if len(d) == 32:
            return d
    except OSError:
        if not anlegen:
            raise
    if not anlegen:
        raise OSError(f"{pfad} hat nicht 32 Byte")
    neu = secrets.token_bytes(32)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_name(pfad.name + ".neu")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(neu)
    os.replace(tmp, pfad)
    return neu
