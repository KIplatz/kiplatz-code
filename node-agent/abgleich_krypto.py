# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

FASSUNG = 1
AUFFUELLEN = 4096
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class KryptoFehler(Exception):
    pass


def b64(daten: bytes) -> str:
    return base64.b64encode(daten).decode("ascii")


def unb64(text: str) -> bytes:
    try:
        return base64.b64decode(str(text), validate=True)
    except (ValueError, TypeError) as exc:
        raise KryptoFehler("kein gültiges Base64") from exc


def _hkdf(stoff: bytes, *, salt: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(stoff)


def neuer_kontoschluessel() -> bytes:
    return os.urandom(32)


def siegel(k: bytes, kennung: str, oeffentlich_: dict) -> str:
    s = _hkdf(k, salt=b"", info=b"kiplatz-abgleich-siegel-v1")
    return b64(hmac.new(s, (str(kennung) + ":" + str(oeffentlich_["punkt"])).encode("ascii"), hashlib.sha256).digest())


def siegel_pruefen(k: bytes, kennung: str, oeffentlich_: dict, wert: str) -> bool:
    try:
        return hmac.compare_digest(siegel(k, kennung, oeffentlich_), str(wert))
    except (KeyError, TypeError, ValueError):
        return False


def block_verschluesseln(k: bytes, bid: str, gespraech: dict, *, iv: bytes | None = None) -> str:
    roh = json.dumps(gespraech, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    roh += b" " * (-len(roh) % AUFFUELLEN)
    iv = iv or os.urandom(12)
    ct = AESGCM(_hkdf(k, salt=b"", info=b"kiplatz-abgleich-block-v1")).encrypt(iv, roh, ("kiplatz-block:" + bid).encode("ascii"))
    return b64(bytes([FASSUNG]) + iv + ct)


def block_entschluesseln(k: bytes, bid: str, daten: str) -> dict:
    roh = unb64(daten)
    if len(roh) < 1 + 12 + 16 or roh[0] != FASSUNG:
        raise KryptoFehler("unbekannte Fassung des Blocks")
    try:
        klar = AESGCM(_hkdf(k, salt=b"", info=b"kiplatz-abgleich-block-v1")).decrypt(roh[1:13], roh[13:], ("kiplatz-block:" + bid).encode("ascii"))
    except Exception as exc:
        raise KryptoFehler("der Block passt nicht zu diesem Schlüssel oder wurde verändert") from exc
    return json.loads(klar.decode("utf-8"))


def neues_geraet() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def oeffentlich_roh(privat: ec.EllipticCurvePrivateKey) -> bytes:
    return privat.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def oeffentlich(privat: ec.EllipticCurvePrivateKey) -> dict:
    return {"art": "p256", "punkt": b64(oeffentlich_roh(privat))}


def privat_speichern(privat: ec.EllipticCurvePrivateKey) -> bytes:
    return privat.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def privat_laden(der: bytes) -> ec.EllipticCurvePrivateKey:
    k = serialization.load_der_private_key(der, password=None)
    if not isinstance(k, ec.EllipticCurvePrivateKey) or not isinstance(k.curve, ec.SECP256R1):
        raise KryptoFehler("kein P-256-Schlüssel")
    return k


def pruefzahl(oeffentlich_: dict) -> str:
    n = int.from_bytes(hashlib.sha256(unb64(oeffentlich_["punkt"])).digest()[:4], "big") % 1_000_000
    s = f"{n:06d}"
    return s[:3] + " " + s[3:]


def fach_packen(k: bytes, geraet_oeffentlich: dict, *, wegwerf: ec.EllipticCurvePrivateKey | None = None, iv: bytes | None = None) -> dict:
    if geraet_oeffentlich.get("art") != "p256":
        raise KryptoFehler("unbekannte Art des Geräteschlüssels")
    g_roh = unb64(geraet_oeffentlich["punkt"])
    g = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), g_roh)
    e = wegwerf or neues_geraet()
    e_roh = oeffentlich_roh(e)
    w = _hkdf(e.exchange(ec.ECDH(), g), salt=e_roh + g_roh, info=b"kiplatz-abgleich-fach-v1")
    iv = iv or os.urandom(12)
    return {"art": "p256", "epk": b64(e_roh), "iv": b64(iv), "ct": b64(AESGCM(w).encrypt(iv, k, b"kiplatz-fach"))}


def fach_oeffnen(fach: dict, privat: ec.EllipticCurvePrivateKey) -> bytes:
    if not isinstance(fach, dict) or fach.get("art") != "p256":
        raise KryptoFehler("unbekannte Art des Fachs")
    e_roh, g_roh = unb64(fach["epk"]), oeffentlich_roh(privat)
    e = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), e_roh)
    w = _hkdf(privat.exchange(ec.ECDH(), e), salt=e_roh + g_roh, info=b"kiplatz-abgleich-fach-v1")
    try:
        k = AESGCM(w).decrypt(unb64(fach["iv"]), unb64(fach["ct"]), b"kiplatz-fach")
    except Exception as exc:
        raise KryptoFehler("das Fach gehört nicht zu diesem Gerät oder wurde verändert") from exc
    if len(k) != 32:
        raise KryptoFehler("der Kontoschlüssel hat nicht die erwartete Länge")
    return k


def neuer_wiederherstellungsschluessel() -> str:
    return wiederherstellung_zeigen(os.urandom(15))


def wiederherstellung_zeigen(r: bytes) -> str:
    n, zeichen = int.from_bytes(r, "big"), []
    for _ in range(24):
        zeichen.append(CROCKFORD[n & 31])
        n >>= 5
    s = "".join(reversed(zeichen))
    return "-".join(s[i:i + 4] for i in range(0, 24, 4))


def wiederherstellung_lesen(text: str) -> bytes:
    s = str(text).upper().replace("-", "").replace(" ", "").replace("O", "0").replace("I", "1").replace("L", "1")
    if len(s) != 24 or any(c not in CROCKFORD for c in s):
        raise KryptoFehler("der Wiederherstellungsschlüssel hat 24 Zeichen aus Ziffern und Buchstaben")
    n = 0
    for c in s:
        n = (n << 5) | CROCKFORD.index(c)
    return n.to_bytes(15, "big")


def wiederherstellung_packen(k: bytes, r_text: str, *, iv: bytes | None = None) -> dict:
    w = _hkdf(wiederherstellung_lesen(r_text), salt=b"kiplatz-wiederherstellung", info=b"kiplatz-abgleich-wieder-v1")
    iv = iv or os.urandom(12)
    return {"art": "wieder", "iv": b64(iv), "ct": b64(AESGCM(w).encrypt(iv, k, b"kiplatz-wieder"))}


def wiederherstellung_oeffnen(fach: dict, r_text: str) -> bytes:
    if not isinstance(fach, dict) or fach.get("art") != "wieder":
        raise KryptoFehler("unbekannte Art des Fachs")
    w = _hkdf(wiederherstellung_lesen(r_text), salt=b"kiplatz-wiederherstellung", info=b"kiplatz-abgleich-wieder-v1")
    try:
        return AESGCM(w).decrypt(unb64(fach["iv"]), unb64(fach["ct"]), b"kiplatz-wieder")
    except Exception as exc:
        raise KryptoFehler("dieser Wiederherstellungsschlüssel passt nicht") from exc
