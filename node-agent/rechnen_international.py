# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from fractions import Fraction

import rechnen
from rechnen import Ergebnis, _Nein, zahl_lesen, zahl_mit_rund, zahl_text

_NUM = rechnen._ZAHL_ROH
_WORT = r"[A-Za-zÄÖÜäöüß°²³µ]+[23]?(?:/[A-Za-zÄÖÜäöüß]+)?"
_MAX_WOERTER = 18
_ZIEL_AUSLOESER = re.compile(rf"(?:\b(?:in|to|into|as|auf|nach)\s+|\bhow\s+(?:many|much)\s+|\bwie\s*viele?\s+|\bwieviel(?:e)?\s+)({_WORT})", re.I)
_ZIEL_FOLGE = re.compile(rf"\s*(?:,|and|und|&)\s*({_WORT})", re.I)


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 160 or len(t.split()) > _MAX_WOERTER:
        return None
    for stufe in (_verbrauch, _wie_viele_in, _fragesatz):
        r = stufe(t)
        if r is not None:
            return r
    return None


def loesen_vorab(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 160 or len(t.split()) > _MAX_WOERTER:
        return None
    return _wie_viele_in(t)


def loesen_nach(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 160 or len(t.split()) > _MAX_WOERTER:
        return None
    for stufe in (_verbrauch, _fragesatz, _zahl_hinten):
        r = stufe(t)
        if r is not None:
            return r
    return None


def _zahl_hinten(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    m = re.fullmatch(rf"(?:convert\s+)?(?P<u>{_WORT})\s+(?:to|in|into|nach|zu|auf)\s+(?P<z>{_WORT}(?:\s*(?:,|and|und)\s*{_WORT})*)\s+(?P<q>{_NUM})", t, re.I)
    if not m or _einheit(m.group("u")) is None:
        return None
    ziele = re.split(r"\s*(?:,|and|und)\s*", m.group("z"))
    if any(_einheit(z) is None for z in ziele):
        return None
    return _rechnen(f"{m.group('q')} {m.group('u')} in {' und '.join(ziele)}")


def _einheit(wort: str):
    try:
        return rechnen._einheit_von(wort)
    except Exception:
        return None


def _rechnen(canon: str) -> Ergebnis | None:
    try:
        return rechnen._umrechnen(canon)
    except (_Nein, ValueError, ZeroDivisionError, OverflowError):
        return None


def _wie_viele_in(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    m = re.fullmatch(rf"(?:please\s+)?how\s+many\s+(?P<z>{_WORT})\s+(?:are\s+|is\s+)?(?:there\s+)?(?:in|per|to)\s+(?:a\s+|an\s+|one\s+|1\s+|the\s+)?(?P<u>{_WORT})", t, re.I) \
        or re.fullmatch(rf"wie\s*viele?\s+(?P<z>{_WORT})\s+(?:hat|haben|sind|gehen\s+in|sind\s+in|hat\s+in|enthält|enthalten|ergibt|ergeben)\s+(?:in\s+)?(?:ein|eine|einem|einer|einen|1)\s+(?P<u>{_WORT})", t, re.I) \
        or re.fullmatch(rf"wie\s*viele?\s+(?P<z>{_WORT})\s+(?:in|pro)\s+(?:ein|eine|einem|einer|einen|1)\s+(?P<u>{_WORT})", t, re.I)
    if not m:
        return None
    z, u = m.group("z"), m.group("u")
    if _einheit(z) is None or _einheit(u) is None:
        return None
    return _rechnen(f"1 {u} in {z}")


def _fragesatz(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    mengen = []
    for m in re.finditer(rf"(?<![\w.,])(-?\s?{_NUM})\s*({_WORT})", t):
        if _einheit(m.group(2)) is not None or m.group(2).lower() in rechnen._TEMP or m.group(2).lower() in ("grad", "degrees", "degree"):
            mengen.append(m)
    if not mengen:
        return None
    gruppe = [mengen[0]]
    for m in mengen[1:]:
        e0, e1 = _einheit(gruppe[-1].group(2)), _einheit(m.group(2))
        if e0 and e1 and e0[0] == e1[0] == "länge" and t[gruppe[-1].end():m.start()].strip() == "":
            gruppe.append(m)
        else:
            return None
    if re.sub(rf"(?<![\w.,]){_NUM}\s*{_WORT}", " ", t, flags=re.I).strip() and re.search(rf"(?<![\w.,]){_NUM}", re.sub(rf"(?<![\w.,]){_NUM}\s*{_WORT}", " ", t)):
        return None
    ziele: list[str] = []
    ort = None
    for m in _ZIEL_AUSLOESER.finditer(t):
        if m.start() >= gruppe[0].start() and m.start() < gruppe[-1].end():
            continue
        w = m.group(1)
        if _einheit(w) is None and w.lower() not in rechnen._TEMP:
            continue
        ziele.append(w)
        ort = m.end()
        while True:
            f = _ZIEL_FOLGE.match(t, ort)
            if not f or (_einheit(f.group(1)) is None and f.group(1).lower() not in rechnen._TEMP):
                break
            ziele.append(f.group(1))
            ort = f.end()
    if not ziele:
        return None
    e0 = _einheit(gruppe[0].group(2))
    if e0 is not None and e0[2] in ("Tasse", "cup", "EL", "TL"):
        return None
    ziele = [z for z in ziele if (_einheit(z) or ("",))[-1] != e0[2]] if e0 is not None else ziele
    if not ziele:
        return None
    quelle = " ".join(f"{g.group(1)} {g.group(2)}" for g in gruppe)
    return _rechnen(f"{quelle} in {' und '.join(ziele)}")


_US_GAL_L = Fraction("3.785411784")
_UK_GAL_L = Fraction("4.54609")
_MILE_KM = Fraction("1.609344")
_US_K = 100 * _US_GAL_L / _MILE_KM
_UK_K = 100 * _UK_GAL_L / _MILE_KM

_VERBR = [
    (r"\b(?:miles?\s+per\s+(?:us\s+|imperial\s+|uk\s+)?gallons?|meilen\s+pro\s+gallone|mi/gal|mpg(?:\s*\((?:us|uk)\))?)", "mpg"),
    (r"\b(?:l(?:iter|itre)s?|l)\s*(?:/|per|pro|auf|je)\s*100\s*(?:km|kilomet(?:er|re)s?)\b|\bl/100km\b|\blp100km\b", "lverbr"),
    (r"\bkm\s*(?:/|per|pro|je)\s*(?:l\b|lit(?:er|re)s?\b)|\bkmpl\b|\bkm/l\b|\bkilomet(?:er|re)s?\s+per\s+lit(?:er|re)\b", "kml"),
]
_VERBR_RE = [(re.compile(m, re.I), k) for m, k in _VERBR]


def _verbrauch(t: str) -> Ergebnis | None:
    s = t
    for muster, kurz in _VERBR_RE:
        s = muster.sub(f" {kurz} ", s)
    if not re.search(r"\b(?:mpg|lverbr|kml)\b", s):
        return None
    uk = bool(re.search(r"\b(?:uk|imperial|british|britain|england|£|gbp)\b|£", t, re.I))
    m = re.search(rf"(?<![\w.,])({_NUM})\s*(mpg|lverbr|kml)\b", s)
    if not m:
        return None
    rest = (s[:m.start()] + " " + s[m.end():])
    ziel = re.search(rf"(?:\b(?:in|to|into|as|auf|nach)\s+|\bhow\s+many\s+|\bwie\s*viele?\s+)(mpg|lverbr|kml)\b", rest, re.I)
    if not ziel or re.search(r"\d", rest):
        return None
    von, nach = m.group(2), ziel.group(1).lower()
    if von == nach:
        return None
    zahl = zahl_lesen(m.group(1))
    if zahl <= 0:
        return None
    k_us, k_uk = _US_K, _UK_K

    def zu_lverbr(x: Fraction, art: str, britisch: bool) -> Fraction:
        return {"lverbr": x, "kml": 100 / x, "mpg": (k_uk if britisch else k_us) / x}[art]

    def von_lverbr(l: Fraction, art: str, britisch: bool) -> Fraction:
        return {"lverbr": l, "kml": 100 / l, "mpg": (k_uk if britisch else k_us) / l}[art]

    namen = {"mpg": "mpg", "lverbr": "l/100 km", "kml": "km/l"}

    def zeile(britisch: bool, en: bool) -> str:
        l = zu_lverbr(zahl, von, britisch)
        erg = von_lverbr(l, nach, britisch)
        zusatz_von = (" (UK)" if britisch else " (US)") if von == "mpg" else ""
        zusatz_nach = (" (UK)" if britisch else " (US)") if nach == "mpg" else ""
        return f"{zahl_text(zahl, en)} {namen[von]}{zusatz_von} {'is' if en else 'sind'} {zahl_mit_rund(erg, en)} {namen[nach]}{zusatz_nach}"

    if von == "mpg" or nach == "mpg":
        haupt = uk
        andere = not uk
        de = zeile(haupt, False) + ". Rechnung: l/100 km = " + zahl_text(k_uk if haupt else k_us) + " ÷ mpg (" + ("UK" if haupt else "US") + ")."
        en = zeile(haupt, True) + ". Working: l/100 km = " + zahl_text(k_uk if haupt else k_us, True) + " ÷ mpg (" + ("UK" if haupt else "US") + ")."
        de += f" Mit der {'britischen ' if andere else 'US-'}Gallone wäre es {zahl_mit_rund(von_lverbr(zu_lverbr(zahl, von, andere), nach, andere))} {namen[nach]}."
        en += f" With the {'UK' if andere else 'US'} gallon it would be {zahl_mit_rund(von_lverbr(zu_lverbr(zahl, von, andere), nach, andere), True)} {namen[nach]}."
        return Ergebnis(de, en)
    de = zeile(False, False) + ". Rechnung: km/l = 100 ÷ (l/100 km)."
    en = zeile(False, True) + ". Working: km/l = 100 ÷ (l/100 km)."
    return Ergebnis(de, en)
