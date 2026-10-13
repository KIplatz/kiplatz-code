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
_VERGESSEN = re.compile(r"^\s*(?:bitte\s+)?(?:vergiss|vergesse|lösch|lösche|streich|streiche)(?:\s+bitte)?\s+(?:das\s+(?:mit|über)\s+|den\s+eintrag\s+(?:mit|über)\s+)?(?P<was>.+?)\s*[.!]?\s*$", re.I | re.S)
_ALLES = re.compile(r"^\s*(?:bitte\s+)?(?:vergiss|lösch|lösche)(?:\s+bitte)?\s+alles(?:\s+(?:über\s+mich|wieder|was\s+du\s+(?:dir\s+)?gemerkt\s+hast))?\s*[.!]?\s*$", re.I)
_WAS_WEISST = re.compile(r"^\s*was\s+(?:weißt|weisst)\s+du\s+(?:alles\s+)?(?:über\s+mich|von\s+mir)\s*\??\s*$", re.I)


def erkennen(text: str) -> tuple[str, str] | None:
    t = str(text or "").strip()
    if not t or len(t) > 600:
        return None
    if _ALLES.match(t):
        return ("alles", "")
    if _WAS_WEISST.match(t):
        return ("liste", "")
    m = _MERKEN.match(t)
    if m and m.group("was").strip():
        return ("merken", " ".join(m.group("was").split())[:MAX_ZEICHEN])
    m = _VERGESSEN.match(t)
    if m and m.group("was").strip():
        return ("vergessen", " ".join(m.group("was").split())[:MAX_ZEICHEN])
    return None


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

    def anwenden(self, erk: tuple[str, str]) -> str:
        art, was = erk
        if art == "merken":
            r = self.merken(was)
            return f"Gemerkt: {r['text']}" if r["neu"] else f"Das weiß ich schon: {r['text']}"
        if art == "vergessen":
            n = self.vergessen(was)
            return f"Vergessen ({n} Eintrag)." if n == 1 else (f"Vergessen ({n} Einträge)." if n else f"Dazu habe ich mir nichts gemerkt: {was}")
        if art == "alles":
            n = self.leeren()
            return "Alles vergessen." if n else "Ich hatte mir nichts gemerkt."
        eintraege = self.liste()
        if not eintraege:
            return "Ich habe mir nichts über dich gemerkt. Sag „Merk dir: …“, dann merke ich es mir, nur auf diesem Gerät."
        return "Das hast du mir gesagt:\n" + "\n".join(f"- {e['text']}" for e in eintraege) + "\n\nUnter Einstellungen kannst du jeden Eintrag löschen."
