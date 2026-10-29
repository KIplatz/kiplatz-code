# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import functools
import re


ART = "antwort"


UEBERSETZ_ART = "uebersetzen"
UEBERSETZ_MAX_TEXT = 300
UEBERSETZ_SPRACHEN = ("de", "en")


MAX_NACHRICHTEN = 12


MAX_TEXT = 8000


STARK_AB_B = 8.0


ANTWORT_AB_B = 8.0


_STUFE = re.compile(r"(\d+(?:[.,]\d+)?)\s*B\b", re.IGNORECASE)


def modell_stufe(name) -> float:
    return _stufe_aus(str(name or ""))


@functools.lru_cache(maxsize=4096)
def _stufe_aus(name: str) -> float:
    treffer = _STUFE.findall(name)
    if not treffer:
        return 0.0
    try:
        return float(treffer[-1].replace(",", "."))
    except ValueError:
        return 0.0


class VermittlungError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b")


_TELEFON = re.compile(r"(?<!\w)(?:\+|00)?\(?0?\d{2,4}\)?[\s/.-]?\d{3,}(?:[\s/.-]?\d{2,}){1,4}(?!\w)")


def unkenntlich(text: str) -> str:
    t = _EMAIL.sub("[E-Mail-Adresse entfernt]", text or "")
    t = _IBAN.sub("[Kontonummer entfernt]", t)
    def _tel(m: "re.Match[str]") -> str:
        ziffern = re.sub(r"\D", "", m.group(0))
        return "[Telefonnummer entfernt]" if len(ziffern) >= 8 else m.group(0)
    return _TELEFON.sub(_tel, t)


SKILL_MAX = 12000


FRIST_HOLEN_S = 300


ZUHAUSE_AUS_TEXT = "Dein PC daheim ist gerade nicht eingeschaltet oder nicht im Internet. Sobald er läuft, frag einfach noch einmal."


NUR_HAUS_WARTEN_S = 45.0


def _nachrichten_pruefen(nachrichten, *, maskieren: bool = True) -> list[dict]:
    if not isinstance(nachrichten, list) or not nachrichten:
        raise VermittlungError("FRAGE_LEER", "keine Frage")
    out = []
    for n in nachrichten[-MAX_NACHRICHTEN:]:
        if not isinstance(n, dict) or n.get("role") not in ("user", "assistant") or not isinstance(n.get("content"), str):
            raise VermittlungError("FRAGE_FORM", "Nachricht nicht lesbar")
        inhalt = unkenntlich(n["content"]) if n["role"] == "user" and maskieren else n["content"]
        if out and out[-1]["role"] == n["role"]:
            out[-1]["content"] = (out[-1]["content"] + "\n\n" + inhalt)[:MAX_TEXT]
            continue
        out.append({"role": n["role"], "content": inhalt[:MAX_TEXT]})
    if out and out[0]["role"] == "assistant":
        out = out[1:]
    if not out or out[-1]["role"] != "user" or not out[-1]["content"].strip():
        raise VermittlungError("FRAGE_LEER", "keine Frage")
    return out
