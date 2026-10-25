# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import wissen

_SPRACHE = threading.local()


def sprache_setzen(englisch: bool) -> None:
    _SPRACHE.englisch = bool(englisch)


def englisch() -> bool:
    return getattr(_SPRACHE, "englisch", False)

GRUEN_AB = 0.6
GELB_AB = 0.3
MIN_WOERTER = 3
_ABKUERZUNG = (r"(?<![\s(.][A-Za-zÄÖÜäöü]\.)(?<!^[A-Za-zÄÖÜäöü]\.)"
               r"(?<!\bca\.)(?<!\bbzw\.)(?<!\bggf\.)(?<!\bvgl\.)(?<!\binkl\.)(?<!\bexkl\.)(?<!\bevtl\.)"
               r"(?<!\bNr\.)(?<!\bDr\.)(?<!\bSt\.)(?<!\bStr\.)(?<!\bAbs\.)(?<!\bzB\.)")
_SATZ_ENDE = re.compile(r"(?<=[.!?])(?<![\s*(]\d\.)(?<![\s*(]\d\d\.)(?<!^\d\.)(?<!^\d\d\.)" + _ABKUERZUNG + r"\s+(?=[A-ZÄÖÜ„\"(\-–0-9])")
_QUELLE = re.compile(r"\(?\s*(?:Quellen?|Sources?)\s*((?:\d+\s*(?:,|und|and|bis|&|\+)?\s*)+)\)?", re.I)
_QUELLE_MARKE = re.compile(r"\s*[\(\[]\s*(?:Quellen?|Sources?|Auszu(?:g|ege))\s*(?:\d+\s*(?:,|und|and|bis|&|\+)?\s*)+[\)\]]", re.I)


def ohne_quellenmarke(text: str) -> str:
    t = _QUELLE_MARKE.sub("", text or "")
    return re.sub(r"\s+([.,;:!?])", r"\1", t).strip()


@dataclass(frozen=True)
class Satz:
    text: str
    farbe: str
    deckung: float
    quelle: int | None
    genannt: tuple[int, ...]
    widerspruch: bool = False

    def kurz(self) -> dict:
        return {"text": ohne_quellenmarke(self.text), "farbe": self.farbe, "deckung": round(self.deckung, 2), "quelle": self.quelle, "genannt": list(self.genannt), "widerspruch": self.widerspruch}


@dataclass(frozen=True)
class Pruefung:
    saetze: tuple[Satz, ...]
    gruen: int
    gelb: int
    rot: int
    unbestimmt: int
    widersprueche: int
    text: str = field(default="")

    def kurz(self) -> dict:
        return {"saetze": [s.kurz() for s in self.saetze], "gruen": self.gruen, "gelb": self.gelb, "rot": self.rot, "unbestimmt": self.unbestimmt,
                "widersprueche": self.widersprueche, "text": self.text}


def saetze(text: str) -> list[str]:
    out: list[str] = []
    for zeile in re.split(r"\n+", text or ""):
        zeile = zeile.strip()
        if not zeile:
            continue
        for s in _SATZ_ENDE.split(zeile):
            s = s.strip()
            if not s:
                continue
            m = _QUELLE.match(s)
            if out and m and m.start() == 0:
                out[-1] = out[-1] + " " + m.group(0).strip()
                s = s[m.end():].strip()
                if not s:
                    continue
            out.append(s)
    return out


def genannte_quellen(satz: str) -> tuple[int, ...]:
    nummern: list[int] = []
    for gruppe in _QUELLE.findall(satz):
        nummern.extend(int(n) for n in re.findall(r"\d+", gruppe))
    return tuple(sorted(set(nummern)))


def _ohne_quellenmarke(satz: str) -> str:
    return _QUELLE.sub(" ", satz)


_ZAHL = re.compile(r"\d+(?:[.,:]\d+)?")
PRAEFIX_AB = 4


def _zahlen(text: str) -> list[str]:
    return [z.replace(",", ".") for z in _ZAHL.findall(text)]


_EINHEITEN = ((re.compile(r"\s*°\s*c\b|\bgrad\s+celsius\b|\bgrad\b", re.I), " "),
              (re.compile(r"\s*km\s*/\s*h\b|\bkilometer\s+pro\s+stunde\b|\bstundenkilometer\w*", re.I), " "),
              (re.compile(r"\s*mm\b|\bmillimeter\w*", re.I), " "),
              (re.compile(r"\s*%|\bprozent\b", re.I), " "))
_GLEICH = {"regn": "reg", "rege": "reg", "regnet": "reg", "regnen": "reg", "regen": "reg", "schneit": "schne", "schneien": "schne", "schnee": "schne",
           "sonnig": "sonn", "sonne": "sonn", "windig": "wind", "stuermisch": "sturm", "gewittrig": "gewitt", "gewitter": "gewitt",
           "bewoelkt": "wolk", "wolkig": "wolk", "wolk": "wolk", "neblig": "nebel", "heiss": "hitz", "hitz": "hitz", "kalt": "kael", "kael": "kael"}
_RAHMEN = {"liegt", "lieg", "erreicht", "erreich", "betraegt", "betrag", "gibt", "pro", "etwa", "rund", "zirka", "circa", "hoechstens", "mindestens",
           "werd", "wird", "sein", "sind"}
INFIX_AB = 6


_EINHEITEN_EN = ((re.compile(r"\s*°\s*f\b|\bdegrees?(?:\s+(?:celsius|fahrenheit))?\b", re.I), " "),
                 (re.compile(r"\bmph\b|\bmiles?\s+per\s+hour\b|\bkilomet(?:er|re)s?\s+per\s+hour\b", re.I), " "),
                 (re.compile(r"\bmillimet(?:er|re)s?\b|\binch(?:es)?\b", re.I), " "),
                 (re.compile(r"\bper\s?cent\b", re.I), " "))
_RAHMEN_EN = set(wissen.woerter(
    "the and with that this these those from have has had been were are for not but you your our their there here which what when where who how "
    "than then into onto over under about after before also just only very more most some any such each other they them its can could would should "
    "shall may might must does did doing because while around stands reaches amounts"))
_RAHMEN_BEIDE = _RAHMEN | _RAHMEN_EN


def _einheitlich(text: str) -> str:
    t = text or ""
    for muster, ersatz in _EINHEITEN + (_EINHEITEN_EN if englisch() else ()):
        t = muster.sub(ersatz, t)
    return t


def _woerter(text: str) -> list[str]:
    rahmen = _RAHMEN_BEIDE if englisch() else _RAHMEN
    return [_GLEICH.get(w, w) for w in wissen.woerter(_einheitlich(text)) if w not in rahmen]


def _gedeckt(w: str, pw: set[str]) -> bool:
    if w in pw:
        return True
    if len(w) < PRAEFIX_AB:
        return False
    return any(len(p) >= PRAEFIX_AB and (p.startswith(w) or w.startswith(p) or (len(w) >= INFIX_AB and len(p) > len(w) + 2 and w in p)) for p in pw)


def pruefen(antwort: str, auszuege: list[tuple[int, str]]) -> Pruefung:
    passagen = [(n, set(_woerter(t)) | set(_zahlen(t))) for n, t in auszuege]
    ergebnis: list[Satz] = []
    for s in saetze(antwort):
        genannt = genannte_quellen(s)
        kern = _ohne_quellenmarke(s)
        woerter = _woerter(kern) + _zahlen(kern)
        zahlen = _zahlen(kern)
        if not woerter or (len(woerter) < MIN_WOERTER and not passagen) or kern.rstrip().endswith("?"):
            ergebnis.append(Satz(s, "unbestimmt", 0.0, None, genannt))
            continue
        beste_n, beste, zahlen_da = None, 0.0, False
        for n, pw in passagen:
            d = sum(1 for w in woerter if _gedeckt(w, pw)) / len(woerter)
            if d > beste:
                beste_n, beste, zahlen_da = n, d, bool(zahlen) and all(z in pw for z in zahlen)
        if zahlen_da and GELB_AB <= beste < GRUEN_AB:
            beste = GRUEN_AB
        if len(woerter) < MIN_WOERTER and beste < GRUEN_AB and not zahlen:
            farbe = "unbestimmt"
        elif beste >= GRUEN_AB:
            farbe = "gruen"
        elif beste >= GELB_AB:
            farbe = "gelb"
        else:
            farbe = "rot"
        if zahlen and passagen and farbe != "unbestimmt" and not any(z in pw for _n, pw in passagen for z in zahlen):
            farbe = "rot"
        widerspruch = farbe == "rot" and beste == 0.0 and (bool(genannt) or bool(re.search(r"\bQuelle", s)))
        ergebnis.append(Satz(s, farbe, beste, beste_n if farbe in ("gruen", "gelb") else None, genannt, widerspruch))
    gruen = sum(1 for x in ergebnis if x.farbe == "gruen")
    gelb = sum(1 for x in ergebnis if x.farbe == "gelb")
    rot = sum(1 for x in ergebnis if x.farbe == "rot")
    unbestimmt = sum(1 for x in ergebnis if x.farbe == "unbestimmt")
    wid = sum(1 for x in ergebnis if x.widerspruch)
    n = len(ergebnis)
    if n == 0:
        text = "keine Sätze"
    elif not auszuege:
        text = f"{n} {'Satz' if n == 1 else 'Sätze'}, alle ohne Quelle (der Speicher hatte nichts Passendes)."
    else:
        teile = [f"{gruen} aus Quellen", f"{gelb} Schlussfolgerungen", f"{rot} ohne Quelle"]
        if unbestimmt:
            teile.append(f"{unbestimmt} zu kurz zum Prüfen oder Fragen an dich")
        text = f"{n} {'Satz' if n == 1 else 'Sätze'}: " + ", ".join(teile) + "."
        if wid:
            text += f" {wid} {'Satz nennt' if wid == 1 else 'Sätze nennen'} eine Quelle, deckt sich aber nicht damit (Widerspruch)."
        text += " Wortabgleich mit den Auszügen, keine Wahrheitsprüfung."
    return Pruefung(tuple(ergebnis), gruen, gelb, rot, unbestimmt, wid, text)


__all__ = ["Satz", "Pruefung", "saetze", "genannte_quellen", "pruefen", "GRUEN_AB", "GELB_AB"]
