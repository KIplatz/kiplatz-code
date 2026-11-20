# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import abgleich_krypto as ak
from abgleich_krypto import KryptoFehler

FASSUNG = 1
AUFFUELLEN = 4096
TEIL_STUFEN = (512, 2048, 8192, 32768)
MAX_INHALT = 256 * 1024
MAX_NACHRICHT = 160 * 1024
MAX_EMPFAENGER = 64
FRAGE_FRIST_S = 900
ZUKUNFT_S = 120
ARTEN = ("teil", "schritt", "antwort")
FRAGE_INFO = b"kiplatz-frage-fach-v1"
ANTWORT_INFO = b"kiplatz-antwort-v1"
SIG_KONTEXT = b"kiplatz-antwort-sig-v1\x00"
ABSCHNITT_KONTEXT = b"kiplatz-abschnitt-v1\x00"


def _json(d) -> bytes:
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _auffuellen(roh: bytes, stufe: int) -> bytes:
    return roh + b" " * (-len(roh) % stufe)


def _teil_stufe(n: int) -> int:
    for s in TEIL_STUFEN:
        if n <= s:
            return s
    return TEIL_STUFEN[-1]


def frage_id_neu() -> str:
    return os.urandom(16).hex()


def _id_roh(frage_id) -> bytes:
    s = str(frage_id or "")
    if len(s) != 32:
        raise KryptoFehler("die Frage-Kennung hat nicht 32 Zeichen")
    try:
        return bytes.fromhex(s)
    except ValueError as exc:
        raise KryptoFehler("die Frage-Kennung ist keine Hex-Zahl") from exc


def _frage_aad(frage_id: str) -> bytes:
    return b"kiplatz-frage-v1:" + _id_roh(frage_id)


def _antwort_aad(frage_id: str, epk_roh: bytes, art: str, n: int) -> bytes:
    return b"kiplatz-antwort-v1:" + _id_roh(frage_id) + epk_roh + art.encode("ascii") + b":" + str(int(n)).encode("ascii")


def _oeffentlich_pruefen(oeffentlich: dict) -> bytes:
    if not isinstance(oeffentlich, dict) or oeffentlich.get("art") != "p256":
        raise KryptoFehler("unbekannte Art des Schlüssels")
    roh = ak.unb64(oeffentlich.get("punkt", ""))
    ak.punkt_laden(roh)
    return roh


@dataclass
class Verschlossen:
    paket: dict
    rueck: ec.EllipticCurvePrivateKey
    frage_id: str
    roh: bytes


def frage_verschliessen(inhalt: dict, empfaenger: dict, *, zeit: float | None = None, frage_id: str | None = None,
                        rueck: ec.EllipticCurvePrivateKey | None = None, k: bytes | None = None, iv: bytes | None = None) -> Verschlossen:
    if not isinstance(inhalt, dict):
        raise KryptoFehler("der Inhalt ist kein Objekt")
    if not isinstance(empfaenger, dict) or not empfaenger:
        raise KryptoFehler("keine Empfänger")
    if len(empfaenger) > MAX_EMPFAENGER:
        raise KryptoFehler("zu viele Empfänger")
    fid = frage_id or frage_id_neu()
    _id_roh(fid)
    rueck = rueck or ak.neues_geraet()
    voll = {**inhalt, "fassung": FASSUNG, "frage_id": fid, "zeit": int(time.time() if zeit is None else zeit), "rueck": ak.oeffentlich(rueck)}
    roh = _auffuellen(_json(voll), AUFFUELLEN)
    if len(roh) > MAX_INHALT:
        raise KryptoFehler("die Frage ist zu lang")
    k = k or os.urandom(32)
    iv = iv or os.urandom(12)
    blob = bytes([FASSUNG]) + iv + AESGCM(k).encrypt(iv, roh, _frage_aad(fid))
    bindung = hashlib.sha256(blob).digest()
    faecher = {}
    for kennung, oeffentlich in empfaenger.items():
        _oeffentlich_pruefen(oeffentlich)
        faecher[str(kennung)] = ak.fach_packen(k, oeffentlich, info=FRAGE_INFO, aad=bindung)
    return Verschlossen({"fassung": FASSUNG, "frage_id": fid, "inhalt": ak.b64(blob), "faecher": faecher}, rueck, fid, roh)


@dataclass
class Geoeffnet:
    inhalt: dict
    frage_id: str
    roh: bytes


def frage_oeffnen(auftrag: dict, privat, *, jetzt: float | None = None, frist_s: float = FRAGE_FRIST_S) -> Geoeffnet:
    if not isinstance(auftrag, dict) or auftrag.get("fassung") != FASSUNG:
        raise KryptoFehler("unbekannte Fassung der Frage")
    fid = str(auftrag.get("frage_id", ""))
    aad = _frage_aad(fid)
    blob = ak.unb64(auftrag.get("inhalt", ""))
    if len(blob) < 1 + 12 + 16 or len(blob) > MAX_INHALT + 64 or blob[0] != FASSUNG:
        raise KryptoFehler("der verschlossene Inhalt hat nicht die erwartete Form")
    bindung = hashlib.sha256(blob).digest()
    k, fehler = None, None
    for p in (privat if isinstance(privat, (list, tuple)) else [privat]):
        try:
            k = ak.fach_oeffnen(auftrag.get("fach"), p, info=FRAGE_INFO, aad=bindung)
            break
        except KryptoFehler as exc:
            fehler = exc
    if k is None:
        raise fehler or KryptoFehler("kein Schlüssel für dieses Fach")
    try:
        roh = AESGCM(k).decrypt(blob[1:13], blob[13:], aad)
    except Exception as exc:
        raise KryptoFehler("die Frage passt nicht zu ihrer Kennung oder wurde verändert") from exc
    try:
        inhalt = json.loads(roh.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise KryptoFehler("der Inhalt ist kein gültiges JSON") from exc
    if not isinstance(inhalt, dict) or inhalt.get("frage_id") != fid or inhalt.get("fassung") != FASSUNG:
        raise KryptoFehler("der Inhalt gehört nicht zu dieser Frage")
    t = time.time() if jetzt is None else jetzt
    zeit = inhalt.get("zeit")
    if not isinstance(zeit, int) or zeit < t - frist_s or zeit > t + ZUKUNFT_S:
        raise KryptoFehler("die Frage ist zu alt oder kommt aus der Zukunft")
    _oeffentlich_pruefen(inhalt.get("rueck"))
    return Geoeffnet(inhalt, fid, roh)


class Gesehen:

    def __init__(self, frist_s: float = FRAGE_FRIST_S + ZUKUNFT_S) -> None:
        self._frist = frist_s
        self._ids: dict[str, float] = {}
        self._lock = threading.Lock()

    def neu(self, frage_id: str, *, jetzt: float | None = None) -> bool:
        t = time.time() if jetzt is None else jetzt
        with self._lock:
            if len(self._ids) > 512:
                self._ids = {k: v for k, v in self._ids.items() if v > t - self._frist}
            if frage_id in self._ids and self._ids[frage_id] > t - self._frist:
                return False
            self._ids[frage_id] = t
            return True


class Kanal:

    def __init__(self, geoeffnet: Geoeffnet, *, wegwerf: ec.EllipticCurvePrivateKey | None = None) -> None:
        h = wegwerf or ak.neues_geraet()
        self.epk_roh = ak.oeffentlich_roh(h)
        rueck_roh = _oeffentlich_pruefen(geoeffnet.inhalt.get("rueck"))
        self._k = ak._hkdf(h.exchange(ec.ECDH(), ak.punkt_laden(rueck_roh)), salt=self.epk_roh + rueck_roh, info=ANTWORT_INFO)
        self.frage_id = geoeffnet.frage_id
        self.frage_roh = geoeffnet.roh
        self.n = 0
        self._lock = threading.Lock()

    def verschliessen(self, art: str, daten: dict, *, iv: bytes | None = None) -> dict:
        if art not in ARTEN:
            raise KryptoFehler("unbekannte Art der Nachricht")
        roh = _json(daten)
        roh = _auffuellen(roh, AUFFUELLEN if art == "antwort" else _teil_stufe(len(roh)))
        if len(roh) > MAX_NACHRICHT:
            raise KryptoFehler("die Nachricht ist zu lang")
        with self._lock:
            self.n += 1
            n = self.n
        iv = iv or os.urandom(12)
        ct = AESGCM(self._k).encrypt(iv, roh, _antwort_aad(self.frage_id, self.epk_roh, art, n))
        return {"fassung": FASSUNG, "epk": ak.b64(self.epk_roh), "art": art, "n": n, "iv": ak.b64(iv), "ct": ak.b64(ct)}

    def antwort(self, text: str, lieferschein: dict, unterschrift_privat: ec.EllipticCurvePrivateKey) -> dict:
        innen = _json({"text": str(text), "lieferschein": lieferschein if isinstance(lieferschein, dict) else {}})
        sig = unterschreiben(unterschrift_privat, self.frage_id, self.frage_roh, innen)
        etikett = etikett_unterschreiben(unterschrift_privat, self.frage_id, text_pruefsumme(str(text)))
        return self.verschliessen("antwort", {"antwort": innen.decode("utf-8"), "sig": sig, "etikett_sig": etikett})


@dataclass
class Offen:
    art: str
    daten: dict
    epk: str
    n: int


def _reihe(nachricht: dict) -> str:
    return f"{nachricht.get('epk', '')}:{nachricht.get('art', '')}"


class Empfang:

    def __init__(self, verschlossen: Verschlossen) -> None:
        self.v = verschlossen
        self._rueck_roh = ak.oeffentlich_roh(verschlossen.rueck)
        self._schluessel: dict[str, bytes] = {}
        self._zuletzt: dict[str, int] = {}
        self._lock = threading.Lock()

    def ist_neu(self, nachricht) -> bool:
        try:
            with self._lock:
                return isinstance(nachricht, dict) and int(nachricht.get("n", 0)) > self._zuletzt.get(_reihe(nachricht), 0)
        except (TypeError, ValueError):
            return False

    def oeffnen(self, nachricht: dict) -> Offen:
        if not isinstance(nachricht, dict) or nachricht.get("fassung") != FASSUNG:
            raise KryptoFehler("unbekannte Fassung der Nachricht")
        art, n = nachricht.get("art"), nachricht.get("n")
        if art not in ARTEN or not isinstance(n, int) or n < 1:
            raise KryptoFehler("Art oder Zähler der Nachricht fehlen")
        epk = str(nachricht.get("epk", ""))
        epk_roh = ak.unb64(epk)
        ct = ak.unb64(nachricht.get("ct", ""))
        if len(ct) > MAX_NACHRICHT + 16:
            raise KryptoFehler("die Nachricht ist zu lang")
        with self._lock:
            k = self._schluessel.get(epk)
            if k is None:
                k = ak._hkdf(self.v.rueck.exchange(ec.ECDH(), ak.punkt_laden(epk_roh)), salt=epk_roh + self._rueck_roh, info=ANTWORT_INFO)
                if len(self._schluessel) >= 8:
                    raise KryptoFehler("zu viele Helfer für eine Frage")
                self._schluessel[epk] = k
            if n <= self._zuletzt.get(_reihe(nachricht), 0):
                raise KryptoFehler("diese Nachricht ist alt oder wiederholt")
            try:
                roh = AESGCM(k).decrypt(ak.unb64(nachricht.get("iv", "")), ct, _antwort_aad(self.v.frage_id, epk_roh, art, n))
            except Exception as exc:
                raise KryptoFehler("die Nachricht passt nicht zu dieser Frage oder wurde verändert") from exc
            self._zuletzt[_reihe(nachricht)] = n
        try:
            daten = json.loads(roh.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise KryptoFehler("die Nachricht ist kein gültiges JSON") from exc
        if not isinstance(daten, dict):
            raise KryptoFehler("die Nachricht ist kein Objekt")
        return Offen(art, daten, epk, n)

    def antwort_lesen(self, offen: Offen, unterschrift_oeffentlich: dict | None) -> tuple[str, dict, bool]:
        if offen.art != "antwort":
            raise KryptoFehler("keine Endantwort")
        innen = str(offen.daten.get("antwort", "")).encode("utf-8")
        try:
            d = json.loads(innen.decode("utf-8"))
        except ValueError as exc:
            raise KryptoFehler("die Antwort ist kein gültiges JSON") from exc
        if not isinstance(d, dict) or not isinstance(d.get("text"), str):
            raise KryptoFehler("der Antwort fehlt der Text")
        ok = bool(unterschrift_oeffentlich) and unterschrift_pruefen(unterschrift_oeffentlich, self.v.frage_id, self.v.roh, innen,
                                                                    offen.daten.get("sig"))
        ls = d.get("lieferschein") if isinstance(d.get("lieferschein"), dict) else {}
        return d["text"], ls, ok


def neuer_unterschrift_schluessel() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _roh_unterschrift(privat: ec.EllipticCurvePrivateKey, daten: bytes) -> str:
    r, s = decode_dss_signature(privat.sign(daten, ec.ECDSA(hashes.SHA256())))
    return ak.b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def _roh_pruefen(oeffentlich: dict, daten: bytes, sig) -> bool:
    try:
        roh = _oeffentlich_pruefen(oeffentlich)
        s = ak.unb64(str(sig or ""))
        if len(s) != 64:
            return False
        ak.punkt_laden(roh).verify(encode_dss_signature(int.from_bytes(s[:32], "big"), int.from_bytes(s[32:], "big")), daten,
                                   ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, KryptoFehler, ValueError, TypeError):
        return False


def _sig_daten(frage_id: str, frage_roh: bytes, antwort_roh: bytes) -> bytes:
    return SIG_KONTEXT + _id_roh(frage_id) + hashlib.sha256(frage_roh).digest() + hashlib.sha256(antwort_roh).digest()


def unterschreiben(privat: ec.EllipticCurvePrivateKey, frage_id: str, frage_roh: bytes, antwort_roh: bytes) -> str:
    return _roh_unterschrift(privat, _sig_daten(frage_id, frage_roh, antwort_roh))


def unterschrift_pruefen(oeffentlich: dict, frage_id: str, frage_roh: bytes, antwort_roh: bytes, sig) -> bool:
    try:
        daten = _sig_daten(frage_id, frage_roh, antwort_roh)
    except KryptoFehler:
        return False
    return _roh_pruefen(oeffentlich, daten, sig)


def text_pruefsumme(text: str) -> str:
    import herkunft
    return herkunft.pruefsumme(str(text))


def _etikett_daten(frage_id: str, pruefsumme: str) -> bytes:
    if not isinstance(pruefsumme, str) or len(pruefsumme) != 64:
        raise KryptoFehler("die Prüfsumme hat nicht 64 Zeichen")
    return b"kiplatz-etikett-v1\x00" + _id_roh(frage_id) + bytes.fromhex(pruefsumme)


def etikett_unterschreiben(privat: ec.EllipticCurvePrivateKey, frage_id: str, pruefsumme: str) -> str:
    return _roh_unterschrift(privat, _etikett_daten(frage_id, pruefsumme))


def etikett_pruefen(oeffentlich: dict, frage_id: str, pruefsumme: str, sig) -> bool:
    try:
        return _roh_pruefen(oeffentlich, _etikett_daten(frage_id, pruefsumme), sig)
    except (KryptoFehler, ValueError):
        return False


def _abschnitt_daten(quelle: str, text: str) -> bytes:
    return ABSCHNITT_KONTEXT + hashlib.sha256(str(quelle).encode("utf-8")).digest() + hashlib.sha256(str(text).encode("utf-8")).digest()


def abschnitt_kennung(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def abschnitt_schluessel_laden(pfad) -> ec.EllipticCurvePrivateKey:
    from pathlib import Path
    from cryptography.hazmat.primitives import serialization
    p = Path(pfad)
    if not p.exists():
        roh = neuer_unterschrift_schluessel().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                            serialization.NoEncryption())
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".neu")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(roh)
        os.replace(tmp, p)
    k = serialization.load_pem_private_key(p.read_bytes(), password=None)
    if not isinstance(k, ec.EllipticCurvePrivateKey) or not isinstance(k.curve, ec.SECP256R1):
        raise KryptoFehler("der Abschnitt-Schlüssel ist kein P-256-Schlüssel")
    return k


def abschnitt_unterschreiben(privat: ec.EllipticCurvePrivateKey, quelle: str, text: str) -> str:
    return _roh_unterschrift(privat, _abschnitt_daten(quelle, text))


def abschnitt_pruefen(oeffentlich: dict, quelle: str, text: str, sig) -> bool:
    return _roh_pruefen(oeffentlich, _abschnitt_daten(quelle, text), sig)


BEGLAUBIGUNG_DATEI = "beglaubigung.json"
BEGLAUBIGUNG_TAGE = 30
ANTWORTSCHLUESSEL_TAGE = 2


def beglaubigung_laden(ordner=None) -> list[dict] | None:
    from pathlib import Path
    p = Path(ordner or Path(__file__).resolve().parent) / BEGLAUBIGUNG_DATEI
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    roh = d.get("schluessel") if isinstance(d, dict) and isinstance(d.get("schluessel"), list) else [d]
    out = []
    for e in roh:
        try:
            _oeffentlich_pruefen(e)
            out.append({"art": "p256", "punkt": e["punkt"]})
        except (KryptoFehler, KeyError, TypeError):
            continue
    return out or None


def _wurzeln(wurzel) -> list[dict]:
    if isinstance(wurzel, dict):
        return [wurzel]
    if isinstance(wurzel, (list, tuple)):
        return [w for w in wurzel if isinstance(w, dict)]
    return []


def schluessel_kennung(oeffentlich: dict) -> str:
    return hashlib.sha256(_oeffentlich_pruefen(oeffentlich)).hexdigest()


def _bis(bis) -> bytes:
    if not isinstance(bis, int) or isinstance(bis, bool) or bis < 0:
        raise KryptoFehler("ungültige Ablaufzeit")
    return bis.to_bytes(8, "big")


ROLLEN = {"pc": b"kiplatz-beglaubigung-v1\x00", "abschnitt": b"kiplatz-beglaubigung-abschnitt-v1\x00"}


def _beglaubigung_daten(unterschrift: dict, bis: int, rolle: str = "pc") -> bytes:
    if rolle not in ROLLEN:
        raise KryptoFehler("unbekannte Rolle der Beglaubigung")
    return ROLLEN[rolle] + bytes.fromhex(schluessel_kennung(unterschrift)) + _bis(bis)


def beglaubigen(wurzel_privat: ec.EllipticCurvePrivateKey, unterschrift: dict, bis: int, *, rolle: str = "pc") -> dict:
    return {"bis": bis, "sig": _roh_unterschrift(wurzel_privat, _beglaubigung_daten(unterschrift, bis, rolle))}


def _antwortschluessel_daten(antwort: dict, bis: int) -> bytes:
    return b"kiplatz-antwortschluessel-v1\x00" + hashlib.sha256(_oeffentlich_pruefen(antwort)).digest() + _bis(bis)


def antwortschluessel_unterschreiben(unterschrift_privat: ec.EllipticCurvePrivateKey, antwort: dict, bis: int) -> str:
    return _roh_unterschrift(unterschrift_privat, _antwortschluessel_daten(antwort, bis))


def _sperrliste_daten(stand: int, eintraege) -> bytes:
    liste = sorted({str(e) for e in eintraege})
    return b"kiplatz-sperrliste-v1\x00" + _bis(stand) + hashlib.sha256("\n".join(liste).encode("ascii")).digest()


def sperrliste_unterschreiben(wurzel_privat: ec.EllipticCurvePrivateKey, stand: int, eintraege) -> dict:
    liste = sorted({str(e) for e in eintraege})
    return {"stand": stand, "gesperrt": liste, "sig": _roh_unterschrift(wurzel_privat, _sperrliste_daten(stand, liste))}


def sperrliste_pruefen(wurzel, sperrliste) -> bool:
    try:
        daten = _sperrliste_daten(sperrliste["stand"], sperrliste["gesperrt"])
        return any(_roh_pruefen(w, daten, sperrliste["sig"]) for w in _wurzeln(wurzel))
    except (KeyError, TypeError, KryptoFehler):
        return False


class Sperrstand:

    def __init__(self, wurzel: dict | None, gespeichert: dict | None = None) -> None:
        self.wurzel = wurzel
        self.liste: dict | None = gespeichert if gespeichert and wurzel and sperrliste_pruefen(wurzel, gespeichert) else None

    @property
    def gesperrt(self) -> frozenset:
        return frozenset(self.liste["gesperrt"]) if self.liste else frozenset()

    def nehmen(self, neu) -> bool:
        if not self.wurzel or not isinstance(neu, dict) or not sperrliste_pruefen(self.wurzel, neu):
            return False
        if self.liste and int(neu["stand"]) <= int(self.liste["stand"]):
            return False
        self.liste = {"stand": int(neu["stand"]), "gesperrt": sorted(neu["gesperrt"]), "sig": neu["sig"]}
        return True


def antwortschluessel_pruefen(eintrag, *, jetzt: float | None = None) -> bool:
    t = int(time.time() if jetzt is None else jetzt)
    try:
        bis = eintrag["antwort_bis"]
        return (isinstance(bis, int) and not isinstance(bis, bool) and t <= bis <= t + (ANTWORTSCHLUESSEL_TAGE + 1) * 86400
                and _roh_pruefen(eintrag["unterschrift"], _antwortschluessel_daten(eintrag["antwort"], bis), eintrag.get("antwort_sig")))
    except (KeyError, TypeError, KryptoFehler):
        return False


def beglaubigung_pruefen(wurzel, unterschrift: dict, beglaubigung, *, jetzt: float | None = None, rolle: str = "pc") -> bool:
    t = int(time.time() if jetzt is None else jetzt)
    try:
        if not (isinstance(beglaubigung, dict) and isinstance(beglaubigung.get("bis"), int) and beglaubigung["bis"] >= t):
            return False
        daten = _beglaubigung_daten(unterschrift, beglaubigung["bis"], rolle)
        return any(_roh_pruefen(w, daten, beglaubigung.get("sig")) for w in _wurzeln(wurzel))
    except (KeyError, TypeError, KryptoFehler):
        return False


def empfaenger_pruefen(eintrag, wurzel: dict | None, *, jetzt: float | None = None, gesperrt=frozenset()) -> dict | None:
    if wurzel is None or not isinstance(eintrag, dict):
        return None
    try:
        unterschrift, antwort = eintrag["unterschrift"], eintrag["antwort"]
        if schluessel_kennung(unterschrift) in gesperrt:
            return None
        if not beglaubigung_pruefen(wurzel, unterschrift, eintrag.get("beglaubigung"), jetzt=jetzt):
            return None
        if not antwortschluessel_pruefen(eintrag, jetzt=jetzt):
            return None
        return {"art": "p256", "punkt": antwort["punkt"]}
    except (KeyError, TypeError, KryptoFehler):
        return None


@dataclass
class Schluessel:
    antwort: ec.EllipticCurvePrivateKey
    unterschrift: ec.EllipticCurvePrivateKey
    seit: float = field(default_factory=time.time)
    vorher: ec.EllipticCurvePrivateKey | None = None
    vorher_bis: float = 0.0

    def oeffentlich(self) -> dict:
        antwort = ak.oeffentlich(self.antwort)
        bis = int(self.seit) + ANTWORTSCHLUESSEL_TAGE * 86400
        return {"antwort": antwort, "antwort_bis": bis, "antwort_sig": antwortschluessel_unterschreiben(self.unterschrift, antwort, bis),
                "unterschrift": ak.oeffentlich(self.unterschrift)}

    def kandidaten(self, *, jetzt: float | None = None) -> list:
        t = time.time() if jetzt is None else jetzt
        return [self.antwort] + ([self.vorher] if self.vorher is not None and t <= self.vorher_bis else [])

    def wechseln(self, *, jetzt: float | None = None, gnade_s: float = 60.0) -> None:
        t = time.time() if jetzt is None else jetzt
        self.vorher, self.vorher_bis = self.antwort, t + gnade_s
        self.antwort, self.seit = ak.neues_geraet(), t
