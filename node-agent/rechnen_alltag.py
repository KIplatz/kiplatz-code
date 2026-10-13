# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from fractions import Fraction

from rechnen import (MAX_STELLEN, Ergebnis, glatt, _dezimal, _Nein, _Null, bruch_text, geld_text, zahl_lesen, zahl_mit_rund, zahl_text)

NUM = r"\d+(?:[.,]\d+)*"
EUR = r"(?:€|euro|eur)"
_ENDE = r"[\s?!.]*"
_ZAHLWORT_EN = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_EN_NENNER = {"half": "hälfte", "halves": "hälfte", "third": "drittel", "thirds": "drittel", "quarter": "viertel", "quarters": "viertel", "fourth": "viertel", "fourths": "viertel",
              "fifth": "fünftel", "fifths": "fünftel", "sixth": "sechstel", "sixths": "sechstel", "seventh": "siebtel", "sevenths": "siebtel", "eighth": "achtel", "eighths": "achtel",
              "ninth": "neuntel", "ninths": "neuntel", "tenth": "zehntel", "tenths": "zehntel", "twentieth": "zwanzigstel", "hundredth": "hundertstel"}
_EN_VIELFACH = {"double": "doppelte", "twice": "doppelte", "triple": "dreifache", "threefold": "dreifache", "fourfold": "vierfache", "quadruple": "vierfache"}
_ZAHLWORT = {"ein": 1, "eine": 1, "einen": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
             **_ZAHLWORT_EN}
_NENNER = {"half": 2, "halves": 2, "third": 3, "thirds": 3, "quarter": 4, "quarters": 4, "fourth": 4, "fourths": 4, "fifth": 5, "fifths": 5, "sixth": 6, "sixths": 6, "seventh": 7,
           "sevenths": 7, "eighth": 8, "eighths": 8, "ninth": 9, "ninths": 9, "tenth": 10, "tenths": 10, "twentieth": 20, "hundredth": 100, "hälfte": 2, "haelfte": 2, "drittel": 3, "viertel": 4, "fünftel": 5, "fuenftel": 5, "sechstel": 6, "siebtel": 7, "achtel": 8, "neuntel": 9, "zehntel": 10,
           "zwanzigstel": 20, "hundertstel": 100}
_VIELFACH = {"double": 2, "twice": 2, "triple": 3, "threefold": 3, "fourfold": 4, "quadruple": 4, "doppelte": 2, "doppelten": 2, "zweifache": 2, "dreifache": 3, "vierfache": 4, "fünffache": 5, "fuenffache": 5, "zehnfache": 10, "hundertfache": 100}
_MAX_LISTE = 40
_MAX_PRIM = 10 ** 10


def _z(x: Fraction, en: bool = False, geld: bool = False) -> str:
    return geld_text(x, en) if geld else zahl_text(x, en)


def _zr(x: Fraction, en: bool = False, geld: bool = False) -> str:
    if geld:
        cent = (x * 100).denominator == 1
        return (("" if cent else ("about " if en else "rund ")) + geld_text(x, en))
    return zahl_mit_rund(x, en)


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"^\s*(?:bitte\s+)?(?:(?:was|wie\s*viel(?:e)?)\s+(?:ist|sind|ergibt|macht)|berechne|rechne(?:\s+aus)?|what\s+is|what's|whats|how\s+much\s+is|calculate|compute|find|tell\s+me)\s+", "", t, flags=re.I)
    t = re.sub(r"(?<=\d)!+$", "!", re.sub(r"[\s?.]+$", "", t))
    t = re.sub(r"(?<![\d!])!+$", "", t).strip()
    for stufe in (_anteil, _prozent_aufschlag, _prozent_aenderung, _steuer_rabatt, _einkauf, _liste, _runden, _zahlen, _basis, _roemisch):
        r = stufe(t)
        if r is not None:
            return glatt(r, t)
    return None


def _aufz(teile: list[str], en: bool = False) -> str:
    und = " and " if en else " und "
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + und + teile[-1]


def _anteil(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:die\s+|the\s+|a\s+|an\s+)?(?:(?P<n>\d+|{'|'.join(_ZAHLWORT)})\s+)?(?P<w>{'|'.join(_NENNER)})\s+(?:von|of)\s+(?P<x>{NUM})(?P<e>\s*{EUR})?", t, re.I)
    if m:
        w = m.group("w").lower()
        w = _EN_NENNER.get(w, w)
        nenner = _NENNER[w]
        halb = w.startswith(("hälfte", "haelfte"))
        if halb and m.group("n"):
            return None
        n_ = (m.group("n") or "ein").lower()
        zaehler = 1 if halb else int(n_) if n_.isdigit() else _ZAHLWORT[n_]
        if zaehler == 0 or zaehler > 1000:
            return None
        x, geld = zahl_lesen(m.group("x")), bool(m.group("e"))
        r = x * Fraction(zaehler, nenner)
        name_de = "die Hälfte" if halb else f"{'ein' if zaehler == 1 else zaehler} {w.capitalize()}"
        name_en = "half" if halb else f"{zaehler}/{nenner}"
        if zaehler == 1:
            weg_de = f"{_z(x, False, geld)} ÷ {nenner} = {_zr(r, False, geld)}"
            weg_en = f"{_z(x, True, geld)} ÷ {nenner} = {_zr(r, True, geld)}"
        else:
            weg_de = f"{_z(x, False, geld)} ÷ {nenner} × {zaehler} = {_zr(x / nenner, False, geld)} × {zaehler} = {_zr(r, False, geld)}"
            weg_en = f"{_z(x, True, geld)} ÷ {nenner} × {zaehler} = {_zr(x / nenner, True, geld)} × {zaehler} = {_zr(r, True, geld)}"
        return Ergebnis(f"{name_de[0].upper() + name_de[1:]} von {_z(x, False, geld)} ist {_zr(r, False, geld)}. Rechnung: {weg_de}.",
                        f"{name_en[0].upper() + name_en[1:]} of {_z(x, True, geld)} is {_zr(r, True, geld)}. Working: {weg_en}.")
    m = re.fullmatch(rf"(?P<n>\d+)\s*/\s*(?P<d>\d+)\s+(?:von|of)\s+(?P<x>{NUM})(?P<e>\s*{EUR})?", t, re.I)
    if m:
        z_, n_ = int(m.group("n")), int(m.group("d"))
        if n_ == 0 or max(len(m.group("n")), len(m.group("d"))) > MAX_STELLEN:
            raise _Nein
        x, geld = zahl_lesen(m.group("x")), bool(m.group("e"))
        r = x * Fraction(z_, n_)
        return Ergebnis(f"{z_}/{n_} von {_z(x, False, geld)} ist {_zr(r, False, geld)}. Rechnung: {_z(x, False, geld)} ÷ {n_} × {z_} = {_zr(r, False, geld)}.",
                        f"{z_}/{n_} of {_z(x, True, geld)} is {_zr(r, True, geld)}. Working: {_z(x, True, geld)} ÷ {n_} × {z_} = {_zr(r, True, geld)}.")
    m = re.fullmatch(rf"(?:das\s+|the\s+)?(?P<w>{'|'.join(_VIELFACH)})(?:\s+(?:von|of))?\s+(?P<x>{NUM})(?P<e>\s*{EUR})?", t, re.I)
    if m:
        k = _VIELFACH[m.group("w").lower()]
        wd = _EN_VIELFACH.get(m.group("w").lower(), m.group("w").lower())
        x, geld = zahl_lesen(m.group("x")), bool(m.group("e"))
        r = x * k
        return Ergebnis(f"Das {wd.capitalize()} von {_z(x, False, geld)} ist {_zr(r, False, geld)}. Rechnung: {_z(x, False, geld)} × {k} = {_zr(r, False, geld)}.",
                        f"{k} times {_z(x, True, geld)} is {_zr(r, True, geld)}. Working: {_z(x, True, geld)} × {k} = {_zr(r, True, geld)}.")
    return None


def _prozent_aufschlag(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?P<x>{NUM})(?P<e>\s*{EUR})?\s*(?P<o>\+|plus|-|−|minus)\s*(?P<p>{NUM})\s*(?:%|prozent|percent)", t, re.I)
    if m:
        plus = m.group("o").lower() in ("+", "plus")
        x, p, geld = zahl_lesen(m.group("x")), zahl_lesen(m.group("p")), bool(m.group("e"))
    else:
        m = re.fullmatch(rf"(?P<p>{NUM})\s*(?:%|prozent|percent)\s*(?P<o>mehr|weniger|more|less)\s+(?:als|than)\s+(?P<x>{NUM})(?P<e>\s*{EUR})?", t, re.I)
        if m:
            plus = m.group("o").lower() in ("mehr", "more")
            x, p, geld = zahl_lesen(m.group("x")), zahl_lesen(m.group("p")), bool(m.group("e"))
        else:
            m = re.fullmatch(rf"(?:(?P<o1>increase|raise|add|up)\s+(?P<x1>{NUM})(?P<e1>\s*{EUR})?\s+by|(?P<o2>decrease|reduce|lower|cut|drop|subtract|take\s+off)\s+(?P<x2>{NUM})(?P<e2>\s*{EUR})?\s+by)"
                             rf"\s+(?P<p>{NUM})\s*(?:%|percent)"
                             rf"|(?P<x3>{NUM})(?P<e3>\s*{EUR})?\s+(?:(?P<o3>increased|raised|up)|(?P<o4>decreased|reduced|lowered|cut|down))\s+by\s+(?P<p3>{NUM})\s*(?:%|percent)", t, re.I)
            if not m:
                return None
            plus = bool(m.group("o1") or m.group("o3"))
            x = zahl_lesen(m.group("x1") or m.group("x2") or m.group("x3"))
            p = zahl_lesen(m.group("p") or m.group("p3"))
            geld = bool(m.group("e1") or m.group("e2") or m.group("e3"))
    delta = x * p / 100
    r = x + delta if plus else x - delta
    zeichen = "+" if plus else "−"
    return Ergebnis(f"{_z(x, False, geld)} {zeichen} {zahl_text(p)} % sind {_zr(r, False, geld)}. Rechnung: {zahl_text(p)} % von {_z(x, False, geld)} = {_zr(delta, False, geld)}, "
                    f"also {_z(x, False, geld)} {zeichen} {_zr(delta, False, geld)} = {_zr(r, False, geld)}.",
                    f"{_z(x, True, geld)} {zeichen} {zahl_text(p, True)}% is {_zr(r, True, geld)}. Working: {zahl_text(p, True)}% of {_z(x, True, geld)} = {_zr(delta, True, geld)}, "
                    f"so {_z(x, True, geld)} {zeichen} {_zr(delta, True, geld)} = {_zr(r, True, geld)}.")


def _prozent_aenderung(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"wie\s*viel(?:e)?\s+prozent\s+(?P<r>mehr|weniger)\s+(?:sind|ist)\s+(?P<a>{NUM})\s+(?:als)\s+(?P<b>{NUM})", t, re.I) \
        or re.fullmatch(rf"(?:um\s+)?wie\s*viel(?:e)?\s+prozent\s+(?:(?:steigt|sinkt|fällt|wächst|erhöht\s+sich|verringert\s+sich|ändert\s+sich|ist\s+es|sind\s+das|ist\s+das|mehr|weniger|es|das|sich|der\s+preis|der\s+wert|steigt\s+es|sinkt\s+es)\s+){{0,3}}"
                        rf"(?:von|vom)\s+(?P<b>{NUM})\s+(?:auf|zu|bis)\s+(?P<a>{NUM})", t, re.I) \
        or re.fullmatch(rf"prozentuale\s+(?:änderung|veränderung|steigerung)\s+(?:von|vom)\s+(?P<b>{NUM})\s+(?:auf|zu|bis)\s+(?P<a>{NUM})", t, re.I) \
        or re.fullmatch(rf"(?:what\s+is\s+)?(?:the\s+)?(?:percent|percentage)\s+(?:change|increase|decrease|difference)\s+from\s+(?P<b>{NUM})\s+to\s+(?P<a>{NUM})", t, re.I) \
        or re.fullmatch(rf"(?:by\s+)?(?:what|how\s+many)\s+(?:percent|percentage)\s+(?:did\s+it\s+)?(?:increase|decrease|change|go\s+up|go\s+down|rise|fall)\s+from\s+(?P<b>{NUM})\s+to\s+(?P<a>{NUM})", t, re.I)
    if m:
        a, b = zahl_lesen(m.group("a")), zahl_lesen(m.group("b"))
        if b == 0:
            raise _Null
        p = (a - b) / b * 100
        if p == 0:
            return Ergebnis(f"{zahl_text(a)} und {zahl_text(b)} sind gleich, die Änderung beträgt 0 %.", f"{zahl_text(a, True)} and {zahl_text(b, True)} are equal, the change is 0%.")
        mehr = p > 0
        rechnung_de = f"({zahl_text(a)} − {zahl_text(b)}) ÷ {zahl_text(b)} × 100 = {zahl_mit_rund(p)}"
        rechnung_en = f"({zahl_text(a, True)} − {zahl_text(b, True)}) ÷ {zahl_text(b, True)} × 100 = {zahl_mit_rund(p, True)}"
        return Ergebnis(f"{zahl_text(a)} sind {zahl_mit_rund(abs(p))} % {'mehr' if mehr else 'weniger'} als {zahl_text(b)}. Rechnung: {rechnung_de}.",
                        f"{zahl_text(a, True)} is {zahl_mit_rund(abs(p), True)}% {'more' if mehr else 'less'} than {zahl_text(b, True)}. Working: {rechnung_en}.")
    m = re.fullmatch(rf"(?P<a>{NUM})\s+(?:ist|sind)\s+wie\s*viel(?:e)?\s+prozent\s+(?:von|vom)\s+(?P<b>{NUM})", t, re.I) \
        or re.fullmatch(rf"(?P<a>{NUM})\s+is\s+what\s+(?:percent|percentage)\s+of\s+(?P<b>{NUM})", t, re.I) \
        or re.fullmatch(rf"what\s+(?:percent|percentage)\s+of\s+(?P<b>{NUM})\s+is\s+(?P<a>{NUM})", t, re.I)
    if m:
        a, b = zahl_lesen(m.group("a")), zahl_lesen(m.group("b"))
        if b == 0:
            raise _Null
        p = a / b * 100
        return Ergebnis(f"{zahl_text(a)} von {zahl_text(b)} sind {zahl_mit_rund(p)} %. Rechnung: {zahl_text(a)} ÷ {zahl_text(b)} × 100 = {zahl_mit_rund(p)}.",
                        f"{zahl_text(a, True)} out of {zahl_text(b, True)} is {zahl_mit_rund(p, True)}%. Working: {zahl_text(a, True)} ÷ {zahl_text(b, True)} × 100 = {zahl_mit_rund(p, True)}.")
    return None


_STEUER = r"(?:mwst\.?|ust\.?|mehrwertsteuer|umsatzsteuer|steuer|vat|gst|sales\s+tax|tax)"
_RABATT = r"(?:rabatt|nachlass|skonto|ermäßigung|ermaessigung|discount)"


def _steuer_rabatt(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?P<p>{NUM})\s*(?:%|prozent|percent)\s*{_STEUER}\s+(?:auf|von|aus|on|of)\s+(?P<x>{NUM})(?P<e>\s*{EUR})?(?:\s+netto)?", t, re.I)
    if m:
        p, x, geld = zahl_lesen(m.group("p")), zahl_lesen(m.group("x")), bool(m.group("e"))
        steuer = x * p / 100
        return Ergebnis(f"{zahl_text(p)} % Steuer auf {_z(x, False, geld)} sind {_zr(steuer, False, geld)}. Mit Steuer sind es {_zr(x + steuer, False, geld)} (brutto). "
                        f"Rechnung: {_z(x, False, geld)} × {zahl_text(p)} ÷ 100 = {_zr(steuer, False, geld)}.",
                        f"{zahl_text(p, True)}% tax on {_z(x, True, geld)} is {_zr(steuer, True, geld)}. With tax it is {_zr(x + steuer, True, geld)} (gross). "
                        f"Working: {_z(x, True, geld)} × {zahl_text(p, True)} ÷ 100 = {_zr(steuer, True, geld)}.")
    m = re.fullmatch(rf"(?P<x>{NUM})(?P<e>\s*{EUR})?\s+(?P<w>netto|brutto|net|gross)\s+(?:in|als|zu|to|as)\s+(?P<z>netto|brutto|net|gross)\s+(?:bei|mit|at|with)\s+(?P<p>{NUM})\s*(?:%|prozent|percent)(?:\s+{_STEUER})?", t, re.I)
    if m:
        von, nach = ("netto" if m.group(g).lower().startswith("net") else "brutto" for g in ("w", "z"))
        if von == nach:
            return None
        x, p, geld = zahl_lesen(m.group("x")), zahl_lesen(m.group("p")), bool(m.group("e"))
        faktor = 1 + p / 100
        netto_zu_brutto = von == "netto"
        r = x * faktor if netto_zu_brutto else x / faktor
        steuer = abs(r - x)
        if netto_zu_brutto:
            return Ergebnis(f"{_z(x, False, geld)} netto sind bei {zahl_text(p)} % Steuer {_zr(r, False, geld)} brutto (Steuer {_zr(steuer, False, geld)}). "
                            f"Rechnung: {_z(x, False, geld)} × {zahl_text(faktor)} = {_zr(r, False, geld)}.",
                            f"{_z(x, True, geld)} net is {_zr(r, True, geld)} gross at {zahl_text(p, True)}% tax (tax {_zr(steuer, True, geld)}). "
                            f"Working: {_z(x, True, geld)} × {zahl_text(faktor, True)} = {_zr(r, True, geld)}.")
        return Ergebnis(f"{_z(x, False, geld)} brutto sind bei {zahl_text(p)} % Steuer {_zr(r, False, geld)} netto (Steuer {_zr(steuer, False, geld)}). "
                        f"Rechnung: {_z(x, False, geld)} ÷ {zahl_text(faktor)} = {_zr(r, False, geld)}.",
                        f"{_z(x, True, geld)} gross is {_zr(r, True, geld)} net at {zahl_text(p, True)}% tax (tax {_zr(steuer, True, geld)}). "
                        f"Working: {_z(x, True, geld)} ÷ {zahl_text(faktor, True)} = {_zr(r, True, geld)}.")
    m = re.fullmatch(rf"(?P<p>{NUM})\s*(?:%|prozent|percent)\s*(?:{_RABATT}\s+(?:auf|von|on|off)|off|rabatt\s+auf|nachlass\s+auf)\s+(?P<x>{NUM})(?P<e>\s*{EUR})?"
                     rf"|(?P<x2>{NUM})(?P<e2>\s*{EUR})?\s*(?:minus|-)\s*(?P<p2>{NUM})\s*(?:%|prozent)\s*{_RABATT}", t, re.I)
    if m:
        p = zahl_lesen(m.group("p") or m.group("p2"))
        x = zahl_lesen(m.group("x") or m.group("x2"))
        geld = bool(m.group("e") or m.group("e2"))
        ersparnis = x * p / 100
        return Ergebnis(f"{zahl_text(p)} % Rabatt auf {_z(x, False, geld)} sind {_zr(ersparnis, False, geld)}. Du zahlst {_zr(x - ersparnis, False, geld)}. "
                        f"Rechnung: {_z(x, False, geld)} × {zahl_text(p)} ÷ 100 = {_zr(ersparnis, False, geld)}, {_z(x, False, geld)} − {_zr(ersparnis, False, geld)} = {_zr(x - ersparnis, False, geld)}.",
                        f"{zahl_text(p, True)}% off {_z(x, True, geld)} saves {_zr(ersparnis, True, geld)}. You pay {_zr(x - ersparnis, True, geld)}. "
                        f"Working: {_z(x, True, geld)} × {zahl_text(p, True)} ÷ 100 = {_zr(ersparnis, True, geld)}, {_z(x, True, geld)} − {_zr(ersparnis, True, geld)} = {_zr(x - ersparnis, True, geld)}.")
    return None


_PREFIX = r"(?:(?:ich|wir)\s+(?:kaufe|kaufen|nehme|nehmen|brauche|brauchen|bestelle|bestellen)\s+)?"
_DING = r"[A-Za-zÄÖÜäöüß\-]+(?:\s+[A-Za-zÄÖÜäöüß\-]+){0,2}"


def _einkauf(t: str) -> Ergebnis | None:
    frage = r"(?:\s*,?\s*(?:was|wie\s*viel)\s+(?:kostet|kosten|macht|ist|sind|zahle\s+ich|bezahle\s+ich|kommt)\s+(?:das|sie|es|alles|das\s+zusammen|zusammen|insgesamt|gesamt|dann)(?:\s+(?:zusammen|insgesamt|gesamt|dann))?)?"
    m = re.fullmatch(rf"{_PREFIX}(?P<n>\d+)\s+(?P<d>{_DING}?)\s+(?:zu\s+je|zu|à|a|je|für\s+je|kosten\s+je|kostet\s+je|zu\s+einem\s+preis\s+von(?:\s+je)?)\s+(?P<p>{NUM})\s*{EUR}"
                     rf"(?:\s+(?:das\s+stück|pro\s+stück|das\s+st\.?|je\s+stück|pro\s+st\.?))?(?:\s+(?:zusammen|insgesamt|gesamt))?{frage}", t, re.I) \
        or re.fullmatch(rf"(?:was|wie\s*viel)\s+(?:kosten|kostet|macht)\s+(?P<n>\d+)\s+(?P<d>{_DING}?)\s+(?:zu\s+je|zu|à|a|je|für\s+je)\s+(?P<p>{NUM})\s*{EUR}"
                        rf"(?:\s+(?:zusammen|insgesamt|gesamt))?", t, re.I)
    if m:
        n, p = int(m.group("n")), zahl_lesen(m.group("p"))
        if len(m.group("n")) > 9:
            raise _Nein
        d = m.group("d").strip()
        if d.lower() in ("mal", "x"):
            return None
        r = n * p
        return Ergebnis(f"{n} {d} zu je {geld_text(p)} kosten zusammen {geld_text(r)}. Rechnung: {n} × {geld_text(p)} = {geld_text(r)}.",
                        f"{n} {d} at {geld_text(p, True)} each cost {geld_text(r, True)} in total. Working: {n} × {geld_text(p, True)} = {geld_text(r, True)}.")
    m = re.fullmatch(rf"(?P<n>\d+)\s+(?P<d>{_DING}?)\s+(?:kosten|kostet)\s+(?:zusammen\s+|insgesamt\s+|gesamt\s+)?(?P<s>{NUM})\s*{EUR}\s*,?\s*(?:was|wie\s*viel)\s+(?:kostet|kosten|macht)\s+"
                     rf"(?:eines|einer|eins|ein|jedes|je|pro\s+stück|das\s+stück|ein\s+stück|einer\s+davon|eines\s+davon|eins\s+davon)(?:\s+{_DING})?", t, re.I)
    if m:
        n, s = int(m.group("n")), zahl_lesen(m.group("s"))
        if n == 0:
            raise _Null
        r = s / n
        return Ergebnis(f"{n} {m.group('d').strip()} kosten zusammen {geld_text(s)}, eines kostet {_zr(r, False, True)}. Rechnung: {geld_text(s)} ÷ {n} = {_zr(r, False, True)}.",
                        f"{n} {m.group('d').strip()} cost {geld_text(s, True)} in total, one costs {_zr(r, True, True)}. Working: {geld_text(s, True)} ÷ {n} = {_zr(r, True, True)}.")
    return None


_LISTE_ART = {"durchschnitt": "mittel", "mittelwert": "mittel", "schnitt": "mittel", "average": "mittel", "mean": "mittel", "summe": "summe", "sum": "summe",
              "produkt": "produkt", "product": "produkt", "median": "median", "maximum": "max", "minimum": "min", "größte zahl": "max", "groesste zahl": "max",
              "kleinste zahl": "min", "höchste zahl": "max", "niedrigste zahl": "min", "größten zahl": "max", "kleinsten zahl": "min"}


def _liste(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:der\s+|die\s+|das\s+|the\s+)?(?P<a>{'|'.join(sorted(_LISTE_ART, key=len, reverse=True))})\s+(?:von|aus|der\s+zahlen|von\s+den\s+zahlen|of)?\s*(?P<l>{NUM}(?:(?:\s*;\s*|,\s+|\s+(?:und|and|,)\s+|\s+){NUM})+)", t, re.I)
    if not m:
        return None
    teile = [x for x in re.split(r"\s*;\s*|,\s+|\s+(?:und|and)\s+|\s+", m.group("l").strip()) if x]
    if not 2 <= len(teile) <= _MAX_LISTE:
        return None
    werte = [zahl_lesen(x) for x in teile]
    art = _LISTE_ART[m.group("a").lower()]
    zeigen = [zahl_text(x) for x in werte]
    zeigen_en = [zahl_text(x, True) for x in werte]
    n = len(werte)
    if art == "mittel":
        s = sum(werte, Fraction(0))
        r = s / n
        return Ergebnis(f"Der Durchschnitt von {_aufz(zeigen)} ist {zahl_mit_rund(r)}. Rechnung: ({' + '.join(zeigen)}) ÷ {n} = {zahl_text(s)} ÷ {n} = {zahl_mit_rund(r)}.",
                        f"The average of {_aufz(zeigen_en, True)} is {zahl_mit_rund(r, True)}. Working: ({' + '.join(zeigen_en)}) ÷ {n} = {zahl_text(s, True)} ÷ {n} = {zahl_mit_rund(r, True)}.")
    if art == "summe":
        s = sum(werte, Fraction(0))
        return Ergebnis(f"Die Summe von {_aufz(zeigen)} ist {zahl_text(s)}. Rechnung: {' + '.join(zeigen)} = {zahl_text(s)}.",
                        f"The sum of {_aufz(zeigen_en, True)} is {zahl_text(s, True)}. Working: {' + '.join(zeigen_en)} = {zahl_text(s, True)}.")
    if art == "produkt":
        p = Fraction(1)
        for w in werte:
            p *= w
            if p.numerator.bit_length() > 4000:
                raise _Nein
        return Ergebnis(f"Das Produkt von {_aufz(zeigen)} ist {zahl_text(p)}. Rechnung: {' × '.join(zeigen)} = {zahl_text(p)}.",
                        f"The product of {_aufz(zeigen_en, True)} is {zahl_text(p, True)}. Working: {' × '.join(zeigen_en)} = {zahl_text(p, True)}.")
    if art == "median":
        s = sorted(werte)
        r = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        geordnet = ", ".join(zahl_text(x) for x in s)
        geordnet_en = ", ".join(zahl_text(x, True) for x in s)
        return Ergebnis(f"Der Median von {_aufz(zeigen)} ist {zahl_mit_rund(r)}. Geordnet: {geordnet}; {'die mittlere Zahl' if n % 2 else 'der Mittelwert der beiden mittleren Zahlen'}.",
                        f"The median of {_aufz(zeigen_en, True)} is {zahl_mit_rund(r, True)}. Sorted: {geordnet_en}; {'the middle number' if n % 2 else 'the mean of the two middle numbers'}.")
    r = max(werte) if art == "max" else min(werte)
    return Ergebnis(f"Die {'größte' if art == 'max' else 'kleinste'} Zahl von {_aufz(zeigen)} ist {zahl_text(r)}.",
                    f"The {'largest' if art == 'max' else 'smallest'} number of {_aufz(zeigen_en, True)} is {zahl_text(r, True)}.")


def _runden(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:runde\s+)?(?P<x>-?{NUM})\s+(?:auf\s+)?(?P<w>(?:(?P<n>\d+|eine|zwei|drei|vier|keine|null)\s+(?:nachkomma|dezimal)?stellen?|ganze(?:\s+zahl)?|einer?\s+stelle|zehner|hunderter|tausender|ganze\s+zahlen))"
                     rf"(?:\s+(?:runden|gerundet|aufrunden|abrunden))?|(?:runde|round)\s+(?P<x2>-?{NUM})\s+auf\s+(?P<w2>(?:(?P<n2>\d+|eine|zwei|drei|vier|keine|null)\s+(?:nachkomma|dezimal)?stellen?|ganze(?:\s+zahl)?|zehner|hunderter|tausender))", t, re.I)
    if not m:
        return None
    xs = m.group("x") or m.group("x2")
    w = (m.group("w") or m.group("w2")).lower()
    ns = m.group("n") or m.group("n2")
    if m.group("x") and not re.search(r"runden|gerundet|auf\s", t, re.I):
        return None
    x = zahl_lesen(xs.lstrip("-")) * (-1 if xs.startswith("-") else 1)
    if "zehner" in w:
        stellen = -1
    elif "hunderter" in w:
        stellen = -2
    elif "tausender" in w:
        stellen = -3
    elif ns:
        stellen = {"eine": 1, "zwei": 2, "drei": 3, "vier": 4, "keine": 0, "null": 0}.get(ns.lower()) if not ns.isdigit() else int(ns)
        if stellen is None or stellen > 12:
            return None
    else:
        stellen = 0
    schritt = Fraction(10) ** (-stellen)
    y = x / schritt
    r = (Fraction(math.floor(abs(y) + Fraction(1, 2))) * (1 if y >= 0 else -1)) * schritt
    name_de = {-1: "Zehner", -2: "Hunderter", -3: "Tausender", 0: "ganze Zahl"}.get(stellen, f"{stellen} Stelle{'n' if stellen != 1 else ''} nach dem Komma")
    name_en = {-1: "tens", -2: "hundreds", -3: "thousands", 0: "a whole number"}.get(stellen, f"{stellen} decimal place{'s' if stellen != 1 else ''}")
    anzeige = _gerundet_text(r, stellen, False)
    anzeige_en = _gerundet_text(r, stellen, True)
    return Ergebnis(f"{zahl_text(x)} auf {name_de} gerundet: {anzeige}.", f"{zahl_text(x, True)} rounded to {name_en}: {anzeige_en}.")


def _gerundet_text(r: Fraction, stellen: int, en: bool) -> str:
    if stellen > 0:
        text, _ = _dezimal(r, 20)
        ganz, _, rest = text.partition(".")
        rest = (rest + "0" * stellen)[:stellen]
        return zahl_text(Fraction(int(ganz)), en) + ("." if en else ",") + rest if not ganz.startswith("-") else "-" + zahl_text(Fraction(int(ganz[1:])), en) + ("." if en else ",") + rest
    return zahl_text(r, en)


def _primfaktoren(n: int) -> list[int]:
    teile, d = [], 2
    while d * d <= n:
        while n % d == 0:
            teile.append(d)
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        teile.append(n)
    return teile


def _hoch(teile: list[int]) -> str:
    sup = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    out = []
    for p in sorted(set(teile)):
        k = teile.count(p)
        out.append(str(p) + (str(k).translate(sup) if k > 1 else ""))
    return " × ".join(out)


def _zahlen(t: str) -> Ergebnis | None:
    m = re.fullmatch(r"(?:ist|is)\s+(?:die\s+zahl\s+)?(?P<n>\d+)\s+(?:eine\s+|a\s+)?(?:primzahl|prime(?:\s+number)?)", t, re.I)
    if m:
        n = int(m.group("n"))
        if n > _MAX_PRIM:
            return None
        if n < 2:
            return Ergebnis(f"{n} ist keine Primzahl. Primzahlen sind Zahlen ab 2, die nur durch 1 und sich selbst teilbar sind.", f"{n} is not a prime number. Primes start at 2.")
        f = _primfaktoren(n)
        if len(f) == 1:
            return Ergebnis(f"{n} ist eine Primzahl. Sie ist nur durch 1 und durch sich selbst teilbar.", f"{n} is a prime number. It is only divisible by 1 and itself.")
        return Ergebnis(f"{n} ist keine Primzahl, denn {n} = {' × '.join(str(x) for x in f)}.", f"{n} is not a prime number, because {n} = {' × '.join(str(x) for x in f)}.")
    m = re.fullmatch(r"(?:primfaktoren\s+(?:von|der\s+zahl)\s+(?P<n>\d+)|(?:zerlege\s+)?(?P<n2>\d+)\s+in\s+primfaktoren(?:\s+zerlegen)?|primfaktorzerlegung\s+(?:von\s+)?(?P<n3>\d+)|prime\s+factors?\s+of\s+(?P<n4>\d+))", t, re.I)
    if m:
        n = int(next(g for g in m.groups() if g))
        if not 2 <= n <= _MAX_PRIM:
            return None
        f = _primfaktoren(n)
        if len(f) == 1:
            return Ergebnis(f"{n} ist selbst eine Primzahl.", f"{n} is a prime number itself.")
        kurz = _hoch(f)
        mal = " × ".join(str(x) for x in f)
        return Ergebnis(f"{n} = {mal}" + (f" = {kurz}" if kurz != mal else "") + ".", f"{n} = {mal}" + (f" = {kurz}" if kurz != mal else "") + ".")
    m = re.fullmatch(r"(?:teiler\s+(?:von|der\s+zahl)\s+(?P<n>\d+)|(?:alle\s+)?teiler\s+von\s+(?P<n2>\d+)|divisors\s+of\s+(?P<n3>\d+))", t, re.I)
    if m:
        n = int(next(g for g in m.groups() if g))
        if not 1 <= n <= 10 ** 9:
            return None
        klein, gross = [], []
        d = 1
        while d * d <= n:
            if n % d == 0:
                klein.append(d)
                if d * d != n:
                    gross.append(n // d)
            d += 1
        alle = klein + gross[::-1]
        return Ergebnis(f"Die Teiler von {n} sind: {', '.join(str(x) for x in alle)} (insgesamt {len(alle)}).", f"The divisors of {n} are: {', '.join(str(x) for x in alle)} ({len(alle)} in total).")
    m = re.fullmatch(r"(?:fakultät\s+(?:von\s+)?(?P<n>\d+)|(?P<n2>\d+)\s*(?:!|fakultät)|(?P<n3>\d+)\s+factorial|factorial\s+of\s+(?P<n4>\d+))", t, re.I)
    if m:
        n = int(next(g for g in m.groups() if g))
        if n > 100:
            return None
        r = math.factorial(n)
        weg = " × ".join(str(i) for i in range(n, 1, -1)) if 2 < n <= 8 else ""
        return Ergebnis(f"{n}! = {zahl_text(Fraction(r))}" + (f". Rechnung: {weg} = {r}." if weg else "."), f"{n}! = {zahl_text(Fraction(r), True)}" + (f". Working: {weg} = {r}." if weg else "."))
    return None


def _basis(t: str) -> Ergebnis | None:
    m = re.fullmatch(r"(?P<n>\d+)\s+(?:in|als|to|as)\s+(?P<b>binär|binaer|dual|binary|hex|hexadezimal|hexadecimal|oktal|octal)(?:\s+(?:zahl|system))?", t, re.I)
    if m:
        n = int(m.group("n"))
        if n > 10 ** 18:
            return None
        b = m.group("b").lower()
        if b in ("binär", "binaer", "dual", "binary"):
            return Ergebnis(f"{n} ist binär {bin(n)[2:]}.", f"{n} in binary is {bin(n)[2:]}.")
        if b in ("oktal", "octal"):
            return Ergebnis(f"{n} ist oktal {oct(n)[2:]}.", f"{n} in octal is {oct(n)[2:]}.")
        return Ergebnis(f"{n} ist hexadezimal {hex(n)[2:].upper()}.", f"{n} in hexadecimal is {hex(n)[2:].upper()}.")
    m = re.fullmatch(r"(?:(?:binär|binaer|binary|dual)\s+(?P<a>[01]{1,64})|(?P<a2>[01]{1,64})\s+(?:binär|binaer|binary|dual)|hex(?:adezimal)?\s+(?:0x)?(?P<h>[0-9a-f]{1,16})|(?:0x)(?P<h2>[0-9a-f]{1,16})|"
                     r"(?P<h3>[0-9a-f]{1,16})\s+hex(?:adezimal)?)\s+(?:in|als|to|as)\s+(?:dezimal|decimal)(?:zahl)?", t, re.I)
    if m:
        a = m.group("a") or m.group("a2")
        if a:
            return Ergebnis(f"Binär {a} ist dezimal {int(a, 2)}.", f"Binary {a} is {int(a, 2)} in decimal.")
        h = m.group("h") or m.group("h2") or m.group("h3")
        return Ergebnis(f"Hexadezimal {h.upper()} ist dezimal {int(h, 16)}.", f"Hexadecimal {h.upper()} is {int(h, 16)} in decimal.")
    return None


_ROEMISCH = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _roemisch(t: str) -> Ergebnis | None:
    m = re.fullmatch(r"(?P<n>\d{1,4})\s+(?:in|als|to|as)\s+(?:römischen?\s+(?:zahlen|ziffern|schreibweise)|römisch|roemisch(?:en\s+zahlen)?|roman\s+numerals?|roman)", t, re.I)
    if m:
        n = int(m.group("n"))
        if not 1 <= n <= 3999:
            return None
        r, rest = "", n
        for wert, zeichen in _ROEMISCH:
            while rest >= wert:
                r += zeichen
                rest -= wert
        return Ergebnis(f"{n} ist römisch {r}.", f"{n} in Roman numerals is {r}.")
    m = re.fullmatch(r"(?P<r>[MDCLXVImdclxvi]{1,15})\s+(?:in|als|to|as)\s+(?:arabische[nr]?\s+(?:zahlen|ziffern)|dezimal|decimal|arabic(?:\s+numerals?)?)", t, re.I)
    if m and m.group("r").isupper():
        s = m.group("r")
        wert, i = 0, 0
        for v, rz in _ROEMISCH:
            while s.startswith(rz, i):
                wert += v
                i += len(rz)
        if i != len(s) or wert == 0:
            return None
        r, rest = "", wert
        for v, rz in _ROEMISCH:
            while rest >= v:
                r += rz
                rest -= v
        if r != s:
            return None
        return Ergebnis(f"{s} ist {wert}.", f"{s} is {wert}.")
    return None
