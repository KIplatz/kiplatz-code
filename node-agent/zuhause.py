# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import collections
import hashlib
import hmac
import re
import secrets
import threading
import time
from pathlib import Path

import app_core
import geheim
import sicher_schreiben

VERSION = "KIplatz Zuhause 1"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_ZEICHEN = 20
CODE_S = 600
OFFEN_MERKEN_S = 24 * 3600
ZEIT_S = 600
MERKEN = 1000
DATEI = "zuhause.json"
ADRESSE_APP = "https://kiplatz.at/app/#zuhause="


class ZuhauseError(app_core.AppError):
    pass


def code_neu() -> str:
    roh = "".join(secrets.choice(ALPHABET) for _ in range(CODE_ZEICHEN))
    return "-".join(roh[i:i + 5] for i in range(0, CODE_ZEICHEN, 5))


def code_normal(text: str) -> str | None:
    t = str(text or "")
    if "zuhause=" in t:
        t = t.split("zuhause=", 1)[1]
    t = re.sub(r"[\s\-]", "", t).upper()
    return t if len(t) == CODE_ZEICHEN and all(c in ALPHABET for c in t) else None


def schluessel(code: str) -> bytes:
    return hashlib.sha256(f"{VERSION}\n{code}".encode("utf-8")).digest()


def kennung(schl: bytes) -> str:
    return hmac.new(schl, b"kennung", hashlib.sha256).hexdigest()[:32]


def _h(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


MODI = ("dateien", "holen", "netz")
DATEI_INFO = b"kiplatz-zuhause-datei-v1"
DATEI_HOECHSTENS = 60 * 1024 * 1024


def datei_schluessel(schl: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"", info=DATEI_INFO).derive(schl)


def datei_verschluesseln(schl: bytes, datei_id: str, daten: bytes, *, iv: bytes | None = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = iv or secrets.token_bytes(12)
    return b"\x01" + iv + AESGCM(datei_schluessel(schl)).encrypt(iv, daten, f"kiplatz-datei:{datei_id}".encode("utf-8"))


def datei_entschluesseln(schl: bytes, datei_id: str, blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(blob) < 29 or blob[0] != 1:
        raise ValueError("unbekanntes Format")
    return AESGCM(datei_schluessel(schl)).decrypt(blob[1:13], blob[13:], f"kiplatz-datei:{datei_id}".encode("utf-8"))


def inhalt(nachrichten: list[dict], skill: dict | None = None, modus: str = "") -> str:
    h = hashlib.sha256()
    for n in nachrichten:
        h.update(f"{n['role']}\n{_h(n['content'])}\n".encode("utf-8"))
    if skill:
        h.update(f"skill\n{_h(str(skill.get('name', '')) + chr(10) + str(skill.get('text', '')))}\n".encode("utf-8"))
    if modus:
        h.update(f"modus\n{modus}\n".encode("utf-8"))
    return h.hexdigest()


def unterschrift(schl: bytes, kid: str, zeit: int, einmal: str, inhalt_hash: str) -> str:
    return hmac.new(schl, f"{VERSION}\n{kid}\n{int(zeit)}\n{einmal}\n{inhalt_hash}".encode("utf-8"), hashlib.sha256).hexdigest()


def unterschreiben(schl: bytes, nachrichten: list[dict], skill: dict | None = None, *, jetzt: float | None = None, modus: str = "") -> dict:
    kid, zeit, einmal = kennung(schl), int(time.time() if jetzt is None else jetzt), secrets.token_hex(8)
    return {"kid": kid, "zeit": zeit, "einmal": einmal, "sig": unterschrift(schl, kid, zeit, einmal, inhalt(nachrichten, skill, modus)),
            **({"modus": modus} if modus else {})}


class Haushalt:

    def __init__(self, base_dir: Path, *, jetzt=time.time) -> None:
        self._pfad = Path(base_dir) / DATEI
        self._jetzt = jetzt
        self._lock = threading.Lock()
        self._gesehen: collections.deque[str] = collections.deque(maxlen=MERKEN)

    def _lesen(self) -> dict:
        d = sicher_schreiben.json_laden(self._pfad, {}, art=dict)
        d.setdefault("an", True)
        d["geraete"] = d.get("geraete") if isinstance(d.get("geraete"), dict) else {}
        d["offen"] = d.get("offen") if isinstance(d.get("offen"), dict) else {}
        return d

    def _schreiben(self, d: dict) -> None:
        sicher_schreiben.json_datei(self._pfad, d)

    @staticmethod
    def _schl(wert: str) -> bytes | None:
        try:
            return bytes.fromhex(geheim.lesen(wert))
        except (geheim.GeheimError, ValueError):
            return None


    def an(self) -> bool:
        with self._lock:
            return bool(self._lesen()["an"])

    def schalter(self, an: bool) -> None:
        with self._lock:
            d = self._lesen()
            d["an"] = bool(an)
            self._schreiben(d)

    def code_erzeugen(self, community) -> dict:
        code = code_neu()
        schl = schluessel(code.replace("-", ""))
        kid = kennung(schl)
        community.zuhause_anbieten(kid)
        with self._lock:
            d = self._lesen()
            t = self._jetzt()
            d["offen"] = {k: e for k, e in d["offen"].items() if isinstance(e, dict) and float(e.get("bis", 0)) + OFFEN_MERKEN_S > t}
            d["offen"][kid] = {"schluessel": geheim.schuetzen(schl.hex()), "bis": t + CODE_S}
            self._schreiben(d)
        return {"code": code, "kid": kid, "gilt_s": CODE_S, "adresse": ADRESSE_APP + code}

    def abgleichen(self, community) -> list[dict]:
        r = community.zuhause_liste()
        am_server = {str(e.get("kid")): e for e in (r.get("geraete") or []) if isinstance(e, dict)}
        with self._lock:
            d = self._lesen()
            neu = {}
            for kid, e in am_server.items():
                alt = d["geraete"].get(kid) or d["offen"].get(kid)
                if not isinstance(alt, dict) or not alt.get("schluessel"):
                    continue
                neu[kid] = {"schluessel": alt["schluessel"], "name": " ".join(str(e.get("name", "")).split())[:60] or "Gerät",
                            "seit": str(e.get("seit", ""))[:20]}
                d["offen"].pop(kid, None)
            geaendert = neu != d["geraete"]
            d["geraete"] = neu
            if geaendert:
                self._schreiben(d)
            return [{"kid": k, "name": e["name"], "seit": e["seit"]} for k, e in neu.items()]

    def liste(self) -> list[dict]:
        with self._lock:
            return [{"kid": k, "name": e.get("name", "Gerät"), "seit": e.get("seit", "")} for k, e in self._lesen()["geraete"].items()]

    def entfernen(self, kid: str, community=None) -> bool:
        with self._lock:
            d = self._lesen()
            weg = d["geraete"].pop(str(kid), None) is not None
            weg = d["offen"].pop(str(kid), None) is not None or weg
            if weg:
                self._schreiben(d)
        if community is not None:
            try:
                community.zuhause_entfernen(str(kid))
            except Exception:
                pass
        return weg

    def pruefen(self, z: dict) -> tuple[bool, str]:
        if not isinstance(z, dict):
            return False, "ohne Unterschrift"
        kid, sig, einmal = str(z.get("kid", "")), str(z.get("sig", "")), str(z.get("einmal", ""))
        nachrichten = z.get("nachrichten")
        if not re.fullmatch(r"[0-9a-f]{32}", kid) or not re.fullmatch(r"[0-9a-f]{64}", sig) or not re.fullmatch(r"[0-9a-f]{16}", einmal) \
                or not isinstance(nachrichten, list):
            return False, "Unterschrift unlesbar"
        try:
            zeit = int(z.get("zeit"))
        except (TypeError, ValueError):
            return False, "Unterschrift unlesbar"
        with self._lock:
            d = self._lesen()
            if not d["an"]:
                return False, "am PC ausgeschaltet"
            e = d["geraete"].get(kid)
            offen = e is None
            if offen:
                e = d["offen"].get(kid)
                if not isinstance(e, dict) or float(e.get("bis", 0)) + OFFEN_MERKEN_S <= self._jetzt():
                    return False, "Gerät nicht gekoppelt"
            schl = self._schl(e.get("schluessel", ""))
            if schl is None or kennung(schl) != kid:
                return False, "Schlüssel nicht lesbar"
            if abs(self._jetzt() - zeit) > ZEIT_S:
                return False, "Unterschrift zu alt"
            if sig in self._gesehen:
                return False, "Unterschrift schon benutzt"
            try:
                modus = str(z.get("modus") or "")
                if modus and modus not in MODI:
                    return False, "Unterschrift unlesbar"
                soll = unterschrift(schl, kid, zeit, einmal, inhalt([{"role": str(n["role"]), "content": str(n["content"])} for n in nachrichten],
                                                                     z.get("skill") if isinstance(z.get("skill"), dict) else None, modus))
            except (KeyError, TypeError, UnicodeEncodeError):
                return False, "Unterschrift unlesbar"
            if not hmac.compare_digest(soll, sig):
                return False, "Unterschrift stimmt nicht"
            self._gesehen.append(sig)
            if offen:
                d["geraete"][kid] = {"schluessel": e["schluessel"], "name": "Gerät", "seit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._jetzt()))}
                d["offen"].pop(kid, None)
                self._schreiben(d)
            return True, ""

    def schluessel_fuer(self, kid: str) -> bytes | None:
        with self._lock:
            d = self._lesen()
            e = d["geraete"].get(str(kid)) or d["offen"].get(str(kid))
        return self._schl(e.get("schluessel", "")) if isinstance(e, dict) else None

    def geholt_merken(self, kid: str, namen: list[str]) -> None:
        with self._lock:
            d = self._lesen()
            name = str((d["geraete"].get(str(kid)) or {}).get("name", "Gerät"))
            v = [x for x in d.get("verlauf") or [] if isinstance(x, dict)]
            v.append({"zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._jetzt())), "geraet": name, "kid": str(kid), "dateien": [str(n)[:200] for n in namen][:50]})
            d["verlauf"] = v[-200:]
            self._schreiben(d)

    def verlauf(self) -> list[dict]:
        with self._lock:
            d = self._lesen()
            namen = {k: e.get("name") for k, e in d["geraete"].items() if isinstance(e, dict) and e.get("name") and e.get("name") != "Gerät"}
            aus = []
            for x in d.get("verlauf") or []:
                if isinstance(x, dict):
                    y = {k: v for k, v in x.items() if k != "kid"}
                    if x.get("kid") in namen:
                        y["geraet"] = namen[x["kid"]]
                    aus.append(y)
            return list(reversed(aus))


    def daheim(self) -> dict | None:
        with self._lock:
            e = self._lesen().get("daheim")
            return {"pc_name": e.get("pc_name", "dein PC"), "seit": e.get("seit", "")} if isinstance(e, dict) else None

    def koppeln(self, code: str, community) -> dict:
        c = code_normal(code)
        if c is None:
            raise ZuhauseError("ZUHAUSE_CODE", f"der Code hat {CODE_ZEICHEN} Zeichen aus Buchstaben und Ziffern; bitte genau abtippen")
        schl = schluessel(c)
        kid = kennung(schl)
        r = community.zuhause_koppeln(kid)
        with self._lock:
            d = self._lesen()
            d["daheim"] = {"kid": kid, "schluessel": geheim.schuetzen(schl.hex()), "pc_name": str(r.get("pc_name", "dein PC"))[:60],
                           "seit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._jetzt()))}
            self._schreiben(d)
        return {"pc_name": d["daheim"]["pc_name"]}

    def vergessen(self, community=None) -> None:
        with self._lock:
            d = self._lesen()
            e = d.pop("daheim", None)
            self._schreiben(d)
        if isinstance(e, dict) and community is not None:
            try:
                community.zuhause_entfernen(str(e.get("kid", "")))
            except Exception:
                pass

    def daheim_schluessel(self) -> tuple[str, bytes] | None:
        with self._lock:
            e = self._lesen().get("daheim")
        if not isinstance(e, dict):
            return None
        schl = self._schl(e.get("schluessel", ""))
        return (str(e.get("kid", "")), schl) if schl else None

    def unterschrift_fuer(self, nachrichten: list[dict], skill: dict | None = None, *, modus: str = "") -> dict | None:
        with self._lock:
            e = self._lesen().get("daheim")
        if not isinstance(e, dict):
            return None
        schl = self._schl(e.get("schluessel", ""))
        if schl is None:
            return None
        return unterschreiben(schl, nachrichten, skill, jetzt=self._jetzt(), modus=modus)


__all__ = ["Haushalt", "ZuhauseError", "code_neu", "code_normal", "schluessel", "kennung", "inhalt", "unterschrift", "unterschreiben"]
