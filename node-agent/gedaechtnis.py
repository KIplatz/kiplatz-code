# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import secrets
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import sicher_schreiben

DATEI = "gedaechtnis.json"
MAX_EINTRAEGE = 60
MAX_ZEICHEN = 300
MAX_VORSPANN = 2400

_MERKEN = re.compile(r"^\s*(?:bitte\s+)?(?:merk|merke|notier|notiere)\s+dir(?:\s+bitte)?\s*[:,]?\s*(?:dass\s+)?(?P<was>.+?)\s*[.!]?\s*$", re.I | re.S)
_VERGESSEN = re.compile(r"^\s*(?:bitte\s+)?(?:vergiss|vergesse|lösch|lösche|streich|streiche)(?:\s+bitte)?\s+(?:das\s+(?:mit|über)\s+|den\s+eintrag\s+(?:mit|über)\s+)"
                        r"(?P<was>.+?)\s*[.!]?\s*$"
                        r"|^\s*(?:bitte\s+)?(?:vergiss|vergesse)(?:\s+bitte)?\s+(?!nicht\b)(?P<was2>.+?)\s*[.!]?\s*$", re.I | re.S)
_ALLES = re.compile(r"^\s*(?:bitte\s+)?(?:vergiss|lösch|lösche)(?:\s+bitte)?\s+alles(?:\s+(?:über\s+mich|wieder|was\s+du\s+(?:dir\s+)?gemerkt\s+hast))?\s*[.!]?\s*$", re.I)
_WAS_WEISST = re.compile(r"^\s*was\s+(?:weißt|weisst)\s+du\s+(?:alles\s+)?(?:über\s+mich|von\s+mir)\s*\??\s*$", re.I)
_MERKEN_EN = re.compile(r"^\s*(?:please\s+)?(?:(?:remember|note|make\s+a\s+note|keep\s+in\s+mind)(?:\s+please)?\s*(?:[:,]\s*|\s+that\s+)"
                        r"|remember\s+(?=(?:i|i'm|i've|my|me|we|we're|our)\b))(?P<was>[^?]+?)\s*[.!]?\s*$", re.I | re.S)
_VERGESSEN_EN = re.compile(r"^\s*(?:please\s+)?(?:forget|delete|remove)(?:\s+please)?\s+(?:about\s+)?(?:the\s+(?:thing|bit|entry|note)\s+about\s+"
                           r"|what\s+i\s+(?:said|told\s+you)\s+about\s+)(?P<was>.+?)\s*[.!]?\s*$"
                           r"|^\s*(?:please\s+)?forget(?:\s+please)?\s+(?:about\s+)?(?!it\b|that\b|this\b|everything\b|all\b)(?P<was2>.+?)\s*[.!]?\s*$", re.I | re.S)
_ALLES_EN = re.compile(r"^\s*(?:please\s+)?(?:forget|delete|remove)(?:\s+please)?\s+(?:everything|all)(?:\s+(?:about\s+me|you\s+know\s+about\s+me|"
                       r"you(?:'ve|\s+have)\s+remembered(?:\s+about\s+me)?))?\s*[.!]?\s*$", re.I)
_WAS_WEISST_EN = re.compile(r"^\s*what\s+(?:do\s+you\s+know|have\s+you\s+remembered)\s+about\s+me\s*\??\s*$", re.I)
_NUR_FUERWORT = {"es", "das", "dies", "it", "that", "this", "them", "him", "her"}


def _art(text: str) -> tuple[str, str, str, bool] | None:
    t = str(text or "").strip()
    if not t or len(t) > 600:
        return None
    for alles, liste, merken, vergessen, sprache in ((_ALLES, _WAS_WEISST, _MERKEN, _VERGESSEN, "de"),
                                                     (_ALLES_EN, _WAS_WEISST_EN, _MERKEN_EN, _VERGESSEN_EN, "en")):
        if alles.match(t):
            return ("alles", "", sprache, True)
        if liste.match(t):
            return ("liste", "", sprache, True)
        m = merken.match(t)
        if m and m.group("was").strip():
            return ("merken", " ".join(m.group("was").split())[:MAX_ZEICHEN], sprache, True)
        m = vergessen.match(t)
        was = m and (m.group("was") or m.group("was2") or "").strip()
        if was and was.lower().strip(".!") not in _NUR_FUERWORT:
            return ("vergessen", " ".join(was.split())[:MAX_ZEICHEN], sprache, bool(m.group("was")))
    return None


def erkennen(text: str) -> tuple[str, str] | None:
    a = _art(text)
    return (a[0], a[1]) if a else None


def sprache(text: str) -> str:
    a = _art(text)
    return a[2] if a else "de"


class Gedaechtnis:
    def __init__(self, base_dir: Path) -> None:
        self.pfad = Path(base_dir) / DATEI


    def _lesen(self) -> dict:
        d = sicher_schreiben.json_laden(self.pfad, {})
        d.setdefault("an", True)
        d["eintraege"] = [e for e in d.get("eintraege", []) if isinstance(e, dict) and str(e.get("text", "")).strip()]
        return d

    def _schreiben(self, d: dict) -> None:
        app_core.ensure_plain_directory(self.pfad.parent)
        sicher_schreiben.json_datei(self.pfad, d, indent=1)


    def an(self) -> bool:
        return bool(self._lesen().get("an", True))

    def setzen(self, an: bool) -> dict:
        d = self._lesen()
        d["an"] = bool(an)
        self._schreiben(d)
        return self.stand()

    def liste(self) -> list[dict]:
        return [{"kennung": str(e.get("kennung", "")), "text": str(e.get("text", "")), "zeit": str(e.get("zeit", ""))} for e in self._lesen()["eintraege"]]

    def stand(self) -> dict:
        d = self._lesen()
        return {"an": bool(d.get("an", True)), "anzahl": len(d["eintraege"]), "eintraege": self.liste()}


    def merken(self, text: str) -> dict:
        was = " ".join(str(text or "").split())[:MAX_ZEICHEN]
        if not was:
            raise app_core.AppError("GEDAECHTNIS_LEER", "da steht nichts zum Merken")
        d = self._lesen()
        for e in d["eintraege"]:
            if str(e.get("text", "")).lower() == was.lower():
                return {"kennung": e["kennung"], "text": e["text"], "neu": False}
        e = {"kennung": secrets.token_hex(4), "text": was, "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        d["eintraege"] = (d["eintraege"] + [e])[-MAX_EINTRAEGE:]
        self._schreiben(d)
        return {"kennung": e["kennung"], "text": was, "neu": True}

    def vergessen(self, kennung_oder_text: str) -> int:
        such = " ".join(str(kennung_oder_text or "").split()).lower()
        if not such:
            return 0
        d = self._lesen()
        vorher = len(d["eintraege"])
        d["eintraege"] = [e for e in d["eintraege"] if not (str(e.get("kennung")) == such or such in str(e.get("text", "")).lower())]
        if len(d["eintraege"]) != vorher:
            self._schreiben(d)
        return vorher - len(d["eintraege"])

    def leeren(self) -> int:
        d = self._lesen()
        n = len(d["eintraege"])
        d["eintraege"] = []
        self._schreiben(d)
        return n


    def vorspann(self) -> str:
        d = self._lesen()
        if not d.get("an", True) or not d["eintraege"]:
            return ""
        zeilen = ["Was die Person dir selbst über sich gesagt hat (gilt als sicher; benutze es, wenn es zur Frage passt, erwähne es sonst nicht):"]
        for e in d["eintraege"]:
            zeilen.append(f"- {e['text']}")
        text = "\n".join(zeilen)
        return text[:MAX_VORSPANN]

    def anhaengen(self, zusatz: str) -> tuple[str, int]:
        v = self.vorspann()
        if not v:
            return zusatz, 0
        return v + ("\n\n" + zusatz if zusatz else ""), len(self._lesen()["eintraege"])

    def befehl(self, text: str) -> tuple[str, str] | None:
        a = _art(text)
        if a is None:
            return None
        art, was, _, sicher = a
        if art == "vergessen" and not sicher:
            such = was.lower()
            if not any(such in str(e.get("text", "")).lower() for e in self._lesen()["eintraege"]):
                return None
        return (art, was)

    def anwenden(self, erk: tuple[str, str], sprache: str = "de") -> str:
        art, was = erk
        en = sprache == "en"
        if art == "merken":
            r = self.merken(was)
            if en:
                return f"Remembered: {r['text']}" if r["neu"] else f"I already know that: {r['text']}"
            return f"Gemerkt: {r['text']}" if r["neu"] else f"Das weiß ich schon: {r['text']}"
        if art == "vergessen":
            n = self.vergessen(was)
            if en:
                return f"Forgotten ({n} entry)." if n == 1 else (f"Forgotten ({n} entries)." if n else f"I haven't remembered anything about that: {was}")
            return f"Vergessen ({n} Eintrag)." if n == 1 else (f"Vergessen ({n} Einträge)." if n else f"Dazu habe ich mir nichts gemerkt: {was}")
        if art == "alles":
            n = self.leeren()
            if en:
                return "Everything forgotten." if n else "I hadn't remembered anything."
            return "Alles vergessen." if n else "Ich hatte mir nichts gemerkt."
        eintraege = self.liste()
        if not eintraege:
            if en:
                return "I haven't remembered anything about you. Say “Remember: …” and I'll remember it, on this device only."
            return "Ich habe mir nichts über dich gemerkt. Sag „Merk dir: …“, dann merke ich es mir, nur auf diesem Gerät."
        liste = "\n".join(f"- {e['text']}" for e in eintraege)
        if en:
            return "This is what you've told me:\n" + liste + "\n\nYou can delete any entry under Settings."
        return "Das hast du mir gesagt:\n" + liste + "\n\nUnter Einstellungen kannst du jeden Eintrag löschen."
