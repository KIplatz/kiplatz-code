# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from fractions import Fraction

import rechnen
from rechnen import NBSP, Ergebnis, _Nein, zahl_lesen, zahl_text

ZUTATEN = [
    (("mehl", "weizenmehl", "flour"), "Mehl", "flour", Fraction(52, 100)),
    (("zucker", "kristallzucker", "sugar"), "Zucker", "sugar", Fraction(85, 100)),
    (("staubzucker", "puderzucker", "powdered sugar", "icing sugar"), "Staubzucker", "powdered sugar", Fraction(55, 100)),
    (("butter",), "Butter", "butter", Fraction(95, 100)),
    (("öl", "oel", "speiseöl", "olivenöl", "sonnenblumenöl", "oil"), "Öl", "oil", Fraction(92, 100)),
    (("honig", "honey"), "Honig", "honey", Fraction(14, 10)),
    (("salz", "salt"), "Salz", "salt", Fraction(12, 10)),
    (("kakao", "kakaopulver", "cocoa"), "Kakao", "cocoa", Fraction(45, 100)),
    (("speisestärke", "stärke", "maisstärke", "starch", "cornstarch"), "Speisestärke", "starch", Fraction(60, 100)),
    (("milch", "milk"), "Milch", "milk", Fraction(103, 100)),
    (("wasser", "water"), "Wasser", "water", Fraction(1)),
    (("sahne", "obers", "rahm", "cream"), "Obers", "cream", Fraction(1)),
    (("joghurt", "yogurt", "yoghurt"), "Joghurt", "yogurt", Fraction(103, 100)),
    (("reis", "rice"), "Reis", "rice", Fraction(80, 100)),
    (("haferflocken", "oats", "rolled oats"), "Haferflocken", "oats", Fraction(35, 100)),
    (("grieß", "gries", "semolina"), "Grieß", "semolina", Fraction(70, 100)),
    (("backpulver", "baking powder"), "Backpulver", "baking powder", Fraction(75, 100)),
]
_ZUTAT = {n: z for z in ZUTATEN for n in z[0]}
_ZUTAT_RE = "|".join(re.escape(n) for n in sorted(_ZUTAT, key=len, reverse=True))

_E = [
    (("ml", "milliliter"), "v", Fraction(1), "ml", "ml"), (("cl",), "v", Fraction(10), "cl", "cl"), (("dl", "deziliter"), "v", Fraction(100), "dl", "dl"),
    (("l", "liter", "litre", "liters", "litres"), "v", Fraction(1000), "l", "l"),
    (("el", "esslöffel", "essloeffel", "eßlöffel", "tbsp", "tablespoon", "tablespoons"), "v", Fraction(15), "EL", "tbsp"),
    (("tl", "teelöffel", "teeloeffel", "tsp", "teaspoon", "teaspoons"), "v", Fraction(5), "TL", "tsp"),
    (("tasse", "tassen"), "v", Fraction(250), "Tasse", "cup"),
    (("cup", "cups"), "v", Fraction(240), "cup", "cup"),
    (("oz", "ounce", "ounces", "unze", "unzen"), "m", Fraction("28.349523125"), "oz", "oz"), (("lb", "lbs", "pound", "pounds"), "m", Fraction("453.59237"), "lb", "lb"),
    (("stick", "sticks"), "m", Fraction("113.398092625"), "stick", "stick"),
    (("floz", "fluidounce", "fluidounces"), "v", Fraction("29.5735295625"), "fl oz", "fl oz"),
    (("pint", "pints", "pt"), "v", Fraction("473.176473"), "pint", "pint"), (("quart", "quarts", "qt"), "v", Fraction("946.352946"), "quart", "quart"),
    (("gallon", "gallons", "gal"), "v", Fraction("3785.411784"), "gallon", "gallon"),
    (("g", "gramm", "gram", "grams"), "m", Fraction(1), "g", "g"), (("dag", "deka", "dkg"), "m", Fraction(10), "dag", "dag"), (("kg", "kilo", "kilogramm", "kilogram"), "m", Fraction(1000), "kg", "kg"),
]
_EINH = {n: e for e in _E for n in e[0]}
_EINH_RE = "|".join(re.escape(n) for n in sorted(_EINH, key=len, reverse=True))
_BRUCH = {"½": Fraction(1, 2), "¼": Fraction(1, 4), "¾": Fraction(3, 4), "⅓": Fraction(1, 3), "⅔": Fraction(2, 3)}
_ZAHLW = {"ein": 1, "eine": 1, "einen": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5, "sechs": 6, "acht": 8, "zehn": 10, "halbe": Fraction(1, 2), "halber": Fraction(1, 2),
          "halbes": Fraction(1, 2), "one": 1, "two": 2, "three": 3, "half": Fraction(1, 2)}
_MENGE = (r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?\s*[½¼¾⅓⅔]|[½¼¾⅓⅔]|\d+(?:[.,]\d+)?|"
          r"(?:eine?n?m?\s+halbe[rsn]?|ein\s+halber|halbe[rsn]?|eine?n?m?|zwei|drei|vier|fünf|fuenf|sechs|acht|zehn|one|two|three|half(?:\s+an?)?))")


def _menge(s: str) -> Fraction:
    s = s.strip().lower()
    if re.fullmatch(r"\d+\s+\d+/\d+", s):
        g, b = s.split()
        return Fraction(g) + Fraction(b)
    if re.fullmatch(r"\d+/\d+", s):
        z, n = s.split("/")
        if int(n) == 0:
            raise _Nein
        return Fraction(int(z), int(n))
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([½¼¾⅓⅔])", s)
    if m:
        return zahl_lesen(m.group(1)) + _BRUCH[m.group(2)]
    if s in _BRUCH:
        return _BRUCH[s]
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return zahl_lesen(s)
    s = re.sub(r"^(?:eine?n?m?\s+)?(halbe[rsn]?)$", r"\1", s)
    s = re.sub(r"^(ein\s+halber|half\s+an?)$", "half", s)
    for w, v in _ZAHLW.items():
        if s == w:
            return Fraction(v)
    if s.startswith(("eine halb", "einen halb", "ein halb")) or s.startswith("half"):
        return Fraction(1, 2)
    raise _Nein


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split()).strip()
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 400:
        return None
    for stufe in (_rezept, _kalorien, _stueck, _masse):
        r = stufe(t)
        if r is not None:
            return r
    return None


def _halb_auf(x: Fraction, n: int) -> Fraction:
    return Fraction(math.floor(x * n + Fraction(1, 2)), n)


def _rund(x: Fraction, en: bool = False) -> str:
    if x.denominator == 1:
        return zahl_text(x, en)
    y = _halb_auf(x, 100)
    return zahl_text(y, en) if y.denominator in (1, 2, 4, 5, 10, 20, 25, 50, 100) else zahl_text(_halb_auf(x, 100), en)


def _gerundet(x: Fraction, en: bool = False) -> str:
    if x >= 10:
        return zahl_text(_halb_auf(x, 1), en)
    return zahl_text(_halb_auf(x, 10), en)


_NICHT_METRISCH = {"Tasse", "cup", "oz", "lb", "stick", "fl oz", "pint", "quart", "gallon"}


def _einheit_name(u: tuple, q: Fraction, en: bool = False) -> str:
    if u[3] == "Tasse":
        return ("cup" if q == 1 else "cups") if en else ("Tasse" if q == 1 else "Tassen")
    if u[3] in ("cup", "pint", "quart", "gallon", "stick"):
        if en:
            return u[4] if q == 1 else u[4] + "s"
        return {"cup": "Cup", "pint": "Pint", "quart": "Quart", "gallon": "Gallone", "stick": "Stick"}[u[3]] if q == 1 else {"cup": "Cups", "pint": "Pint", "quart": "Quart", "gallon": "Gallonen", "stick": "Sticks"}[u[3]]
    return u[4] if en else u[3]


def _masse(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    zutat = rf"(?:\s+(?P<z>{_ZUTAT_RE}))?"
    m = re.fullmatch(rf"(?:wie\s+viel(?:e)?|how\s+(?:much|many))\s+(?P<u2>{_EINH_RE})\s+(?:sind|ist|hat|hast|wiegt|wiegen|entsprechen|are|is)\s+(?P<q>{_MENGE})\s*(?P<u1>{_EINH_RE})(?:\s+(?:von|of))?{zutat}", t, re.I)         or re.fullmatch(rf"(?:was\s+sind\s+|what\s+is\s+)?(?P<q>{_MENGE})\s*(?P<u1>{_EINH_RE})(?:\s+(?:von|of))?{zutat}(?:\s+(?:in|nach|auf|to|into)\s+(?P<u2>{_EINH_RE}))?", t, re.I)
    if not m or not m.group("u2"):
        return None
    u1, u2 = _EINH[m.group("u1").lower()], _EINH[m.group("u2").lower()]
    z = _ZUTAT[m.group("z").lower()] if m.group("z") else None
    kueche = {"EL", "TL", "Tasse", "cup", "stick"}
    if u1[3] not in kueche and u2[3] not in kueche and z is None:
        return None
    try:
        q = _menge(m.group("q"))
    except _Nein:
        return None
    if q <= 0 or q > 10 ** 6:
        return None
    relation = None
    if u1[1] == u2[1]:
        wert = q * u1[2] / u2[2]
        ung = False
        gross, klein = (u1, u2) if u1[2] >= u2[2] else (u2, u1)
        relation = None if ("Tasse" in (u1[3], u2[3]) or "cup" in (u1[3], u2[3])) else (f"1 {gross[3]} = {_rund(gross[2] / klein[2])} {klein[3]}", f"1 {gross[4]} = {_rund(gross[2] / klein[2], True)} {klein[4]}")
    else:
        if z is None:
            return None
        dichte = z[3]
        if u1[1] == "v":
            wert = q * u1[2] * dichte / u2[2]
        else:
            wert = q * u1[2] / dichte / u2[2]
        ung = True
        v_einheit = u1 if u1[1] == "v" else u2
        if not (u1[1] == "v" and q == 1):
            relation = (f"1 {v_einheit[3]} {z[1]} ≈ {_gerundet(v_einheit[2] * dichte)} g", f"1 {v_einheit[4]} {z[2]} ≈ {_gerundet(v_einheit[2] * dichte, True)} g")
    name_de = f" {z[1]}" if z else ""
    name_en = f" {z[2]}" if z else ""
    zahl = _gerundet(wert) if ung else _rund(wert)
    zahl_en = _gerundet(wert, True) if ung else _rund(wert, True)
    wert_s = Fraction(zahl.replace(NBSP, "").replace(",", ".")) if zahl else wert
    de = f"{_rund(q)} {_einheit_name(u1, q)}{name_de} sind {'ungefähr ' if ung else ''}{zahl} {_einheit_name(u2, wert_s)}."
    en = f"{_rund(q, True)} {_einheit_name(u1, q, True)}{name_en} is {'about ' if ung else ''}{zahl_en} {_einheit_name(u2, wert_s, True)}."
    zusatz_de, zusatz_en = [], []
    if relation:
        zusatz_de.append(relation[0])
        zusatz_en.append(relation[1])
    if ung:
        zusatz_de.append("gestrichen bzw. locker gefüllt gemessen, je nach Sorte und Packung kann es um etwa 10 bis 20 % abweichen")
        zusatz_en.append("measured level or loosely filled, depending on the brand and how it is packed it can be off by roughly 10 to 20%")
    elif "Tasse" in (u1[3], u2[3]):
        zusatz_de.append("1 Tasse = 250 ml als Rezeptmaß, die US-Cup hat 240 ml")
        zusatz_en.append("1 cup = 250 ml as a recipe measure, the US cup is 240 ml")
    elif "cup" in (u1[3], u2[3]):
        zusatz_de.append("1 Cup = 240 ml (US); in Großbritannien und Australien oft 250 ml")
        zusatz_en.append("1 cup = 240 ml (US); in the UK and Australia often 250 ml")
    if zusatz_de:
        de += " (" + "; ".join(zusatz_de) + ")"
        en += " (" + "; ".join(zusatz_en) + ")"
    return Ergebnis(de, en)


_PERS = r"(?:\s*(?:personen|person|portionen|portion|leute|leuten|stück|stk|people|persons|servings|serving|gäste|gästen|köpfe|köpfen))?"
_STRICH = r"\s*(?:[:\-–—]|,|;)\s*"


_FAKTOR_WORT = {"double": Fraction(2), "triple": Fraction(3), "halve": Fraction(1, 2), "verdopple": Fraction(2), "verdoppeln": Fraction(2), "verdreifache": Fraction(3), "verdreifachen": Fraction(3),
                "halbiere": Fraction(1, 2), "halbieren": Fraction(1, 2), "halve ": Fraction(1, 2)}


def _metrisch(neu: Fraction, u: tuple | None, name: str, en: bool) -> str:
    if u is None or u[3] not in _NICHT_METRISCH:
        return ""
    z = next((_ZUTAT[w] for w in re.findall(r"[a-zäöüß]+", name.lower()) if w in _ZUTAT), None)
    menge = neu * u[2]
    if u[1] == "m":
        wert, einheit = menge, "g"
    elif z is not None:
        wert, einheit = menge * z[3], "g"
    else:
        wert, einheit = menge, "ml"
    if einheit == "g" and wert >= 1000:
        wert, einheit = wert / 1000, "kg"
    if einheit == "ml" and wert >= 1000:
        wert, einheit = wert / 1000, "l"
    ungefaehr = einheit in ("g", "kg") and u[1] == "v"
    zahl = _gerundet(wert, en) if ungefaehr or wert >= 10 else _rund(wert, en)
    if einheit in ("g", "kg") and u[1] == "m":
        zahl = _rund(Fraction(math.floor(wert + Fraction(1, 2))), en) if wert >= 10 else _rund(wert, en)
    return f" ({'about ' if en and ungefaehr else ('ungefähr ' if ungefaehr else '')}{zahl} {einheit})"


def _skalieren(f: Fraction, kopf_de: str, kopf_en: str, liste: str) -> Ergebnis | None:
    teile = [x.strip() for x in re.split(r"\s*(?:[;\n]|(?<!\d),|,(?!\d))\s*|\s+und\s+|\s+and\s+", liste) if x.strip()]
    if not 1 <= len(teile) <= 30:
        return None
    zeilen_de, zeilen_en = [], []
    stueck = False
    for z in teile:
        z = rechnen._vornormalisieren(z)
        mm = re.fullmatch(rf"(?P<q>{_MENGE})\s*(?:(?P<u>{_EINH_RE})\b\.?\s*)?(?:(?:of|von)\s+)?(?P<n>[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß \-]*)", z, re.I)
        if not mm:
            m2 = re.fullmatch(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß \-]*", z)
            if not m2 or len(z) > 40:
                return None
            zeilen_de.append(f"{z}: ohne Mengenangabe, nach Geschmack")
            zeilen_en.append(f"{z}: no amount given, to taste")
            continue
        try:
            q = _menge(mm.group("q"))
        except _Nein:
            return None
        u = _EINH.get((mm.group("u") or "").lower())
        name = mm.group("n").strip()
        neu = q * f
        if u:
            alt_de = f"{_rund(q)} {_einheit_name(u, q)} {name}"
            alt_en = f"{_rund(q, True)} {_einheit_name(u, q, True)} {name}"
            zusatz = zusatz_en = ""
            if u[3] in ("g", "ml") and neu >= 1000:
                zusatz = f" ({_rund(neu / 1000)} {'kg' if u[3] == 'g' else 'l'})"
                zusatz_en = f" ({_rund(neu / 1000, True)} {'kg' if u[3] == 'g' else 'l'})"
            zeilen_de.append(f"{alt_de} → {_rund(neu)} {_einheit_name(u, neu)} {name}{zusatz}{_metrisch(neu, u, name, False)}")
            zeilen_en.append(f"{alt_en} → {_rund(neu, True)} {_einheit_name(u, neu, True)} {name}{zusatz_en}{_metrisch(neu, u, name, True)}")
        else:
            if neu.denominator != 1:
                stueck = True
            zeilen_de.append(f"{_rund(q)} {name} → {_rund(neu)} {name}")
            zeilen_en.append(f"{_rund(q, True)} {name} → {_rund(neu, True)} {name}")
    de = kopf_de + "\n" + "\n".join(zeilen_de)
    en = kopf_en + "\n" + "\n".join(zeilen_en)
    if stueck:
        de += "\nGanze Stücke wie Eier oder Zwiebeln lassen sich nicht teilen: nimm etwas mehr oder weniger."
        en += "\nWhole items such as eggs or onions can't be split: use a little more or less."
    de += "\nGewürze, Backpulver und Hefe nach Geschmack und Packungsangabe anpassen, sie wachsen oft nicht im gleichen Maß mit."
    en += "\nAdjust spices, baking powder and yeast to taste and packet instructions, they often don't scale in the same proportion."
    return Ergebnis(de, en)


def _rezept(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    m = re.fullmatch(rf"(?:(?:bitte\s+)?(?:rechne|wandle|rechne\s+mir)\s+(?:das\s+|mein\s+|dieses\s+)?(?:rezept\s+)?)?(?:rezept\s+)?(?:für|fuer|for)\s+(?P<a>\d+){_PERS}\s*(?:um(?:rechnen)?\s+)?(?:auf|für|fuer|to|for)\s+(?P<b>\d+){_PERS}\s*(?:um)?{_STRICH}(?P<l>.+)", t, re.I) \
        or re.fullmatch(rf"(?:(?:bitte\s+)?(?:rechne|wandle)\s+(?:das\s+|mein\s+)?(?:rezept\s+)?)?(?:für|fuer|for)\s+(?P<b>\d+){_PERS}\s+(?:statt|anstatt|anstelle\s+von|instead\s+of)\s+(?P<a>\d+){_PERS}\s*(?:um)?{_STRICH}(?P<l>.+)", t, re.I) \
        or re.fullmatch(rf"(?:(?:please\s+)?(?:scale|convert|adjust|change)\s+(?:the\s+|this\s+|my\s+)?recipe\s+(?:from\s+)?|(?:the\s+|this\s+|my\s+)?recipe\s+for\s+)(?P<a>\d+){_PERS}\s*,?\s*(?:to|for|into|->|→|scaled\s+to)\s+(?P<b>\d+){_PERS}{_STRICH}(?P<l>.+)", t, re.I) \
        or re.fullmatch(rf"(?:(?:please\s+)?(?:make|scale)\s+(?:it|this|the\s+recipe)\s+)?for\s+(?P<b>\d+){_PERS}\s+instead\s+of\s+(?P<a>\d+){_PERS}{_STRICH}(?P<l>.+)", t, re.I)
    if m:
        a, b = int(m.group("a")), int(m.group("b"))
        if not (1 <= a <= 1000 and 1 <= b <= 1000) or a == b:
            return None
        f = Fraction(b, a)
        return _skalieren(f, f"Rezept von {a} auf {b} Personen (Faktor {_rund(f)}):", f"Recipe from {a} to {b} people (factor {_rund(f, True)}):", m.group("l"))
    m = re.fullmatch(rf"(?:please\s+|bitte\s+)?(?P<w>double|triple|halve|verdopple|verdoppeln|verdreifache|verdreifachen|halbiere|halbieren)\s+(?:the\s+|this\s+|my\s+|das\s+|dieses\s+|mein\s+)?(?:recipe|rezept)\s*(?:please|bitte)?{_STRICH}(?P<l>.+)", t, re.I) \
        or re.fullmatch(rf"(?:das\s+|dieses\s+|mein\s+)?rezept\s+(?P<w>verdoppeln|verdreifachen|halbieren){_STRICH}(?P<l>.+)", t, re.I)
    if m:
        w = m.group("w").lower()
        f = _FAKTOR_WORT[w]
        de_w = {2: "verdoppelt", 3: "verdreifacht"}.get(int(f) if f.denominator == 1 else 0, "halbiert")
        en_w = {2: "doubled", 3: "tripled"}.get(int(f) if f.denominator == 1 else 0, "halved")
        return _skalieren(f, f"Rezept {de_w} (Faktor {_rund(f)}):", f"Recipe {en_w} (factor {_rund(f, True)}):", m.group("l"))
    return None


_STUECKE = [
    (("ei", "eier", "egg", "eggs"), Fraction(55), "Ei", "egg", " (Größe M, mit Schale; ohne Schale rund 50 g)", " (size M, in the shell; without the shell about 50 g)"),
    (("eigelb", "dotter", "eidotter", "yolk", "yolks", "egg yolk", "egg yolks"), Fraction(20), "Eigelb", "egg yolk", "", ""),
    (("eiweiß", "eiweiss", "eiklar", "egg white", "egg whites", "white", "whites"), Fraction(30), "Eiweiß", "egg white", "", ""),
    (("päckchen backpulver", "packerl backpulver", "pkg backpulver", "packung backpulver", "packet of baking powder", "sachet of baking powder"), Fraction(15), "Päckchen Backpulver", "packet of baking powder", "", ""),
    (("päckchen vanillezucker", "packerl vanillezucker", "pkg vanillezucker", "packung vanillezucker", "sachet of vanilla sugar"), Fraction(8), "Päckchen Vanillezucker", "sachet of vanilla sugar", "", ""),
    (("päckchen trockenhefe", "packerl trockenhefe", "pkg trockenhefe", "packet of dry yeast", "sachet of dry yeast"), Fraction(7), "Päckchen Trockenhefe", "packet of dry yeast", "", ""),
    (("würfel hefe", "würfel frische hefe", "wuerfel hefe", "cube of yeast", "cube of fresh yeast"), Fraction(42), "Würfel frische Hefe", "cube of fresh yeast", " (ersetzt etwa 1 Päckchen Trockenhefe à 7 g × 2)", " (about two packets of dry yeast at 7 g each)"),
]
_STUECK_NAME = {n: e for e in _STUECKE for n in e[0]}
_STUECK_RE = "|".join(re.escape(n) for n in sorted(_STUECK_NAME, key=len, reverse=True))


def _stueck(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:wie\s*viel(?:e)?\s+gramm\s+(?:sind|ist|hat|haben|wiegt|wiegen)\s+|wie\s*viel\s+wiegt\s+|how\s+(?:many\s+grams|much)\s+(?:is|are|does|do)\s+)(?:a\s+|an\s+)?(?P<q>{_MENGE})?\s*(?P<i>{_STUECK_RE})(?:\s+weigh|\s+weighs|\s+wiegt|\s+wiegen)?", t, re.I) \
        or re.fullmatch(rf"(?P<q>{_MENGE})\s+(?P<i>{_STUECK_RE})\s+(?:in|auf|to)\s+(?:g|gramm|grams)", t, re.I) \
        or re.fullmatch(rf"(?:wie\s*viel\s+)?(?:wiegt|wiegen)\s+(?:ein|eine|einen|einem)?\s*(?P<q>{_MENGE})?\s*(?P<i>{_STUECK_RE})", t, re.I)
    if not m:
        return None
    e = _STUECK_NAME[m.group("i").lower()]
    try:
        q = _menge(m.group("q")) if m.group("q") else Fraction(1)
    except _Nein:
        return None
    if q <= 0 or q > 1000:
        return None
    g = q * e[1]
    mit = " (Größe M, mit Schale; ohne Schale rund " + _rund(q * 50) + " g)" if e[2] == "Ei" else e[4]
    mit_en = " (size M, in the shell; without the shell about " + _rund(q * 50, True) + " g)" if e[3] == "egg" else e[5]
    plural_de = {"Ei": "Eier"}.get(e[2], e[2]) if q != 1 else e[2]
    plural_en = {"egg": "eggs", "egg yolk": "egg yolks", "egg white": "egg whites"}.get(e[3], e[3]) if q != 1 else e[3]
    return Ergebnis(f"{_rund(q)} {plural_de} {'wiegt' if q == 1 else 'wiegen'} etwa {_rund(g)} g{mit}. Das sind Richtwerte.",
                    f"{_rund(q, True)} {plural_en} {'weighs' if q == 1 else 'weigh'} about {_rund(g, True)} g{mit_en}. These are rough values.")


_KCAL = {"zucker": 400, "butter": 740, "öl": 880, "oel": 880, "oil": 880, "milch": 65, "milk": 65, "honig": 305, "honey": 305, "haferflocken": 370, "oats": 370, "reis": 350, "rice": 350,
         "mehl": 350, "flour": 350, "obers": 290, "sahne": 290, "cream": 290, "joghurt": 65, "yogurt": 65, "sugar": 400, "staubzucker": 400, "puderzucker": 400}


def _kalorien(t: str) -> Ergebnis | None:
    t = rechnen._vornormalisieren(t)
    zutaten = "|".join(re.escape(k) for k in sorted(_KCAL, key=len, reverse=True))
    m = re.fullmatch(rf"(?:wie\s*viele?\s+(?:kalorien|kcal)\s+(?:hat|haben|sind\s+in|stecken\s+in|enthält|enthalten)\s+|how\s+many\s+(?:calories|kcal)\s+(?:are\s+)?(?:in|does|do)\s+|(?:calories|kalorien|kcal)\s+(?:in|von)\s+)"
                     rf"(?P<q>{_MENGE})\s*(?P<u>{_EINH_RE})\s+(?:of\s+|von\s+)?(?P<z>{zutaten})(?:\s+have|\s+haben)?", t, re.I)
    if not m:
        return None
    u = _EINH[m.group("u").lower()]
    z = m.group("z").lower()
    try:
        q = _menge(m.group("q"))
    except _Nein:
        return None
    if q <= 0 or q > 100000:
        return None
    zut = _ZUTAT.get(z)
    if u[1] == "m":
        g = q * u[2]
    elif zut is not None:
        g = q * u[2] * zut[3]
    else:
        return None
    kcal = g * _KCAL[z] / 100
    name_de = zut[1] if zut else z.capitalize()
    name_en = zut[2] if zut else z
    return Ergebnis(f"{_rund(q)} {_einheit_name(u, q)} {name_de} haben ungefähr {_gerundet(kcal)} kcal (Richtwert {_KCAL[z]} kcal je 100 g; auf der Packung steht der genaue Wert).",
                    f"{_rund(q, True)} {_einheit_name(u, q, True)} {name_en} has about {_gerundet(kcal, True)} kcal (rule of thumb {_KCAL[z]} kcal per 100 g; the packet gives the exact value).")
