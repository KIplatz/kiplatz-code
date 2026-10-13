# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import difflib
import math
import re
import threading
from dataclasses import dataclass
from fractions import Fraction

MAX_TEXT = 200
MAX_STELLEN = 40
MAX_ERGEBNIS_BITS = 4000
NBSP = " "


@dataclass(frozen=True)
class Ergebnis:
    de: str
    en: str


class _Nein(Exception):
    pass


class _Null(Exception):
    pass


_ZAHL_ROH = r"\d+(?:[.,]\d+)*"
_WAEHRUNG = threading.local()
_ENGLISCH_WOERTER = re.compile(r"\b(?:the|what|whats|how|many|much|is|are|at|for|and|with|from|years?|months?|days?|miles?|gallons?|dollars?|pounds?|percent|of|on|my|i|tip|bill|loan|mortgage|"
                               r"split|between|if|per|pay|paid|please|convert|tell|me|can|you|will|would|does|do|am|was|were|long|until|till|ago|born|old|cost|costs|total|change|each|euros|dollars|cents|yen|francs|quid)\b", re.I)
_EN_STARK_EINHEITEN = re.compile(r"\d\s*'\s*\d|\b(?:ounces?|oz|pounds?|lbs?|gallons?|pints?|quarts?|feet|foot|ft|inch(?:es)?|stone|tbsp|tsp|cups?|acres?|miles?|mpg|sq\s*ft|fl\s*oz|yards?|"
                                 r"hours?|minutes?|seconds?|weeks?|grams?|kilograms?|kilometers|kilometres?|meters|metres?|liters|litres?|centimeters|centimetres?|millimeters|millimetres?|hectares?|"
                                 r"tablespoons?|teaspoons?|binary|hexadecimal|octal|roman\s+numerals?|prime|factorial|square\s+root|solve|equation|calories|recipe|servings|baking|oven|"
                                 r"gross\s+(?:to|in)\s+net|net\s+(?:to|in)\s+gross|pm|gas\s*mark|squared|cubed|twice|double|half\s+of|quarter\s+of|third\s+of)\b", re.I)
_ENGLISCH_STARK = re.compile(r"\b(?:the|what|whats|how|many|much|years|months|miles?|gallons?|dollars|percent|loan|mortgage|between|please|convert|until|ago|born|each)\b|[$£]", re.I)
_GRUPPE_PUNKT = re.compile(r"^[1-9]\d{0,2}(?:\.\d{3})+$")
_GRUPPE_KOMMA = re.compile(r"^[1-9]\d{0,2}(?:,\d{3})+$")


def zahl_lesen(s: str) -> Fraction:
    s = s.strip()
    if not re.fullmatch(_ZAHL_ROH, s) or len(re.sub(r"\D", "", s)) > MAX_STELLEN:
        raise _Nein
    if getattr(_WAEHRUNG, "englisch", False) and not ("." in s and "," in s):
        if "," in s and _GRUPPE_KOMMA.match(s):
            return Fraction(s.replace(",", ""))
        if "." in s and "," not in s:
            if s.count(".") > 1:
                raise _Nein
            return Fraction(s)
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            ganz, _, rest = s.rpartition(",")
            if not _GRUPPE_PUNKT.match(ganz):
                raise _Nein
            s = ganz.replace(".", "") + "." + rest
        else:
            ganz, _, rest = s.rpartition(".")
            if not _GRUPPE_KOMMA.match(ganz):
                raise _Nein
            s = ganz.replace(",", "") + "." + rest
    elif "," in s:
        if s.count(",") > 1:
            if not _GRUPPE_KOMMA.match(s):
                raise _Nein
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        if _GRUPPE_PUNKT.match(s):
            s = s.replace(".", "")
        elif s.count(".") > 1:
            raise _Nein
    return Fraction(s)


_KURZ_WORT = {"mrd": 10 ** 9, "milliarde": 10 ** 9, "milliarden": 10 ** 9, "billion": 10 ** 9, "bn": 10 ** 9, "mio": 10 ** 6, "million": 10 ** 6, "millionen": 10 ** 6,
              "tsd": 1000, "tausend": 1000}
_KURZ_RE = re.compile(rf"(?<![\w.,])({_ZAHL_ROH})\s*(mrd|milliarden?|billion|bn|mio|millionen|million|tsd|tausend)\b\.?", re.I)
_KURZ_K = re.compile(rf"(?<![\w.,])({_ZAHL_ROH})k\b")


def kurzformen(text: str) -> str:
    def ersatz(faktor_fn):
        def f(m: re.Match) -> str:
            try:
                x = zahl_lesen(m.group(1)) * faktor_fn(m)
            except _Nein:
                return m.group(0)
            if x.denominator != 1 or abs(x) >= 10 ** MAX_STELLEN:
                return m.group(0)
            return str(int(x))
        return f
    t = _KURZ_RE.sub(ersatz(lambda m: _KURZ_WORT[m.group(2).lower()]), text)
    return _KURZ_K.sub(ersatz(lambda m: 1000), t)


def _nur_2_und_5(n: int) -> bool:
    for p in (2, 5):
        while n % p == 0:
            n //= p
    return n == 1


def _dezimal(x: Fraction, stellen_max: int = 12) -> tuple[str, bool]:
    neg = x < 0
    x = abs(x)
    stellen = 0
    genau = _nur_2_und_5(x.denominator)
    if genau:
        while (x * 10 ** stellen).denominator != 1:
            stellen += 1
        genau = stellen <= stellen_max
    if not genau:
        stellen = 4 if x >= Fraction(1, 10) else 8
    ganz, rest = divmod(round(x * 10 ** stellen), 10 ** stellen)
    text = str(ganz)
    if stellen:
        r = str(rest).rjust(stellen, "0")
        if not genau:
            r = r.rstrip("0")
        if r:
            text += "." + r
    return ("-" if neg and (ganz or rest) else "") + text, genau


def zahl_text(x: Fraction, en: bool = False) -> str:
    text, _ = _dezimal(x)
    neg = text.startswith("-")
    ganz, _, rest = text.lstrip("-").partition(".")
    if len(ganz) >= (4 if en else 5):
        teile = []
        while ganz:
            teile.insert(0, ganz[-3:])
            ganz = ganz[:-3]
        ganz = ("," if en else NBSP).join(teile)
    return ("-" if neg else "") + ganz + (("." if en else ",") + rest if rest else "")


def zahl_mit_rund(x: Fraction, en: bool = False) -> str:
    t = zahl_text(x, en)
    return t if _dezimal(x)[1] else (("about " if en else "rund ") + t)


def englisch_erkennen(text: str) -> bool:
    if _ENGLISCH_STARK.search(text):
        return True
    return len(_ENGLISCH_WOERTER.findall(text)) >= 2


def englisch_rechnung(text: str) -> bool:
    if re.search(r"[äöüßÄÖÜ]", text or ""):
        return False
    if not (englisch_erkennen(text or "") or _EN_STARK_EINHEITEN.search(text or "")):
        return False
    if loesen(text) is not None:
        return True
    import kurse
    return kurse.erkennen(text) is not None


def englisch_setzen(text: str) -> bool:
    _WAEHRUNG.englisch = englisch_erkennen(text)
    return _WAEHRUNG.englisch


def waehrung() -> str:
    return getattr(_WAEHRUNG, "zeichen", "€")


def geld_text(x: Fraction, en: bool = False) -> str:
    cent = math.floor(abs(x) * 100 + Fraction(1, 2))
    ganz = zahl_text(Fraction(cent // 100), en)
    text = f"{ganz}{'.' if en else ','}{cent % 100:02d}"
    neg = "-" if x < 0 and cent else ""
    z = waehrung()
    if not z:
        return f"{neg}{text}"
    if en:
        return f"{neg}{z} {text}" if z == "CHF" else f"{neg}{z}{text}"
    return f"{neg}{text} {z}"


_NUM_W = r"\d+(?:[.,]\d+)*"
_WAEHRUNG_WORTE = (
    ("$", re.compile(r"\$|\bus\$|\busd\b|\b(?:us[- ]?)?dollars?\b|\bbucks?\b|\bcents?\b(?=.*\$)", re.I)),
    ("£", re.compile(r"£|\bgbp\b|\bpounds?\s+sterling\b|\bquids?\b", re.I)),
    ("CHF", re.compile(r"\bchf\b|\bfranken\b|\bswiss\s+francs?\b|\bsfr\.?", re.I)),
)


def waehrung_normalisieren(t: str) -> tuple[str, str]:
    zeichen = "€"
    if re.search(r"€|\beuros?\b|\beur\b", t, re.I):
        return t, "€"
    for z, muster in _WAEHRUNG_WORTE:
        if muster.search(t):
            zeichen = z
            break
    if zeichen == "€":
        return t, ("" if getattr(_WAEHRUNG, "englisch", False) else "€")
    t = re.sub(rf"(?:us)?[$£]\s*({_NUM_W})", r"\1 €", t, flags=re.I)
    t = re.sub(rf"({_NUM_W})\s*(?:\$|£|(?:us[- ]?)?dollars?|bucks?|usd|gbp|quids?|chf|franken|(?:swiss\s+)?francs?|sfr\.?)(?![A-Za-z])", r"\1 €", t, flags=re.I)
    t = re.sub(r"\bpounds?\s+sterling\b", "", t, flags=re.I)
    return t, zeichen


def glatt(r: "Ergebnis", t: str) -> "Ergebnis":
    engl = getattr(_WAEHRUNG, "englisch", False)
    betraege = re.findall(r"(\d[\d.,]*)\s*€", t)
    if betraege:
        if any(re.search(r"\.\d{1,2}$" if engl else r",\d{1,2}$|\.\d{1,2}$", b) for b in betraege):
            return r
    elif re.search(r"\d\.\d{1,2}(?!\d)" if engl else r"\d,\d|\d\.\d{1,2}(?!\d)", t):
        return r
    z = waehrung()
    if not z:
        if re.search(r"\d\.\d{1,2}(?!\d)", t):
            return r
        return Ergebnis(r.de.replace(",00", ""), re.sub(r"(\d)\.00(?!\d)", r"\1", r.en))
    de = r.de.replace(f",00 {z}", f" {z}")
    pre = re.escape(z) + (" " if z == "CHF" else "")
    en = re.sub(rf"({pre}[\d,]+)\.00(?!\d)", r"\1", r.en)
    return Ergebnis(de, en)


def bruch_text(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def gemischt_text(x: Fraction) -> str:
    if x.denominator == 1 or abs(x.numerator) < x.denominator:
        return ""
    g, r = divmod(abs(x.numerator), x.denominator)
    return f"{'-' if x < 0 else ''}{g} {r}/{x.denominator}"


def _f(z: int | str, n: int = 1) -> Fraction:
    return Fraction(z) / n


_EINHEITEN: dict[str, tuple[str, Fraction, str]] = {}
_LOKAL = threading.local()
_LANGE_NAMEN: list[str] = []
_SINGULAR = {"Tage": "Tag", "Wochen": "Woche", "Meilen": "Meile", "Seemeilen": "Seemeile", "Monate": "Monat", "Jahre": "Jahr"}
_ENGLISCH = {"Monate": ("month", "months"), "Jahre": ("year", "years"), "Tage": ("day", "days"), "Wochen": ("week", "weeks"), "Meilen": ("mile", "miles"), "Seemeilen": ("nautical mile", "nautical miles"),
             "Zoll": ("inch", "inches"), "Pfund": ("German pound", "German pounds")}


def _einheit(groesse: str, faktor: Fraction, kurz: str, *namen: str) -> None:
    for n in (kurz, *namen):
        _EINHEITEN[n.lower()] = (groesse, faktor, kurz)


_einheit("länge", _f(1, 1000000), "µm", "mikrometer")
_einheit("länge", _f(1, 1000), "mm", "millimeter", "millimetern", "millimetre", "millimetres")
_einheit("länge", _f(1, 100), "cm", "zentimeter", "zentimetern", "centimeter", "centimeters", "centimetre", "centimetres")
_einheit("länge", _f(1, 10), "dm", "dezimeter", "dezimetern", "decimeter", "decimeters", "decimetre", "decimetres")
_einheit("länge", _f(1), "m", "meter", "metern", "metre", "metres", "meters")
_einheit("länge", _f(1000), "km", "kilometer", "kilometern", "kilometre", "kilometres", "kilometers")
_einheit("länge", Fraction("0.0254"), "Zoll", "inch", "inches")
_einheit("länge", Fraction("0.3048"), "ft", "fuß", "fuss", "foot", "feet", "füße")
_einheit("länge", Fraction("0.9144"), "yd", "yard", "yards")
_einheit("länge", Fraction("1609.344"), "Meilen", "meile", "mile", "miles", "mi")
_einheit("länge", _f(1852), "Seemeilen", "seemeile", "nmi")
_einheit("masse", _f(1, 1000000), "mg", "milligramm")
_einheit("masse", _f(1, 1000), "g", "gramm", "gram", "grams")
_einheit("masse", _f(1, 100), "dag", "dekagramm", "deka")
_einheit("masse", _f(1), "kg", "kilogramm", "kilo", "kilos", "kilogram", "kilograms")
_einheit("masse", _f(1000), "t", "tonne", "tonnen", "metrictonne", "tonnes")
_einheit("masse", _f(1, 2), "Pfund")
_einheit("masse", Fraction("0.45359237"), "lb", "lbs", "pound", "pounds")
_einheit("masse", Fraction("0.028349523125"), "oz", "unze", "unzen", "ounce", "ounces")
_einheit("volumen", _f(1, 1000), "ml", "milliliter", "millilitern", "millilitre")
_einheit("volumen", _f(1, 100), "cl", "zentiliter", "zentilitern", "centiliter")
_einheit("volumen", _f(1, 10), "dl", "deziliter", "dezilitern", "deciliter")
_einheit("volumen", _f(1), "l", "liter", "litern", "litre", "litres", "liters")
_einheit("volumen", _f(100), "hl", "hektoliter", "hektolitern")
_einheit("volumen", _f(1000), "m³", "m3", "kubikmeter", "kubikmetern", "cbm")
_einheit("volumen", _f(1, 1000000), "cm³", "cm3", "kubikzentimeter", "ccm")
_einheit("fläche", _f(1, 1000000), "mm²", "mm2", "quadratmillimeter")
_einheit("fläche", _f(1, 10000), "cm²", "cm2", "quadratzentimeter")
_einheit("fläche", _f(1, 100), "dm²", "dm2", "quadratdezimeter")
_einheit("fläche", _f(1), "m²", "m2", "quadratmeter", "qm", "quadratmetern")
_einheit("fläche", _f(10000), "ha", "hektar", "hectare", "hectares")
_einheit("fläche", _f(1000000), "km²", "km2", "quadratkilometer", "qkm")
_einheit("zeit", _f(1), "s", "sek", "sekunde", "sekunden", "second", "seconds", "sec")
_einheit("zeit", _f(60), "min", "minute", "minuten", "minutes")
_einheit("zeit", _f(3600), "h", "std", "stunde", "stunden", "hour", "hours")
_einheit("zeit", _f(86400), "Tage", "tag", "tage", "tagen", "day", "days")
_einheit("zeit", _f(604800), "Wochen", "woche", "wochen", "week", "weeks")
_einheit("zeit", _f(365 * 86400, 12), "Monate", "monat", "monate", "monaten", "month", "months")
_einheit("zeit", _f(365 * 86400), "Jahre", "jahr", "jahre", "jahren", "year", "years")
_einheit("geschwindigkeit", _f(1), "m/s", "meter/sekunde")
_einheit("geschwindigkeit", _f(1000, 3600), "km/h", "kmh", "stundenkilometer")
_einheit("geschwindigkeit", Fraction("1609.344") / 3600, "mph")
_einheit("geschwindigkeit", Fraction(1852, 3600), "kn", "knoten", "knots")
_einheit("geschwindigkeit", _f(1000, 3600), "km/h", "kph", "kmph", "kmh")
_einheit("geschwindigkeit", Fraction("1609.344") / 3600, "mph", "mi/h")
_einheit("geschwindigkeit", Fraction("0.3048"), "ft/s", "fps")
_einheit("masse", Fraction("6.35029318"), "stone", "stones", "st")
_einheit("masse", Fraction("907.18474"), "short ton", "ton", "tons", "shortton", "shorttons")
_einheit("masse", Fraction("1016.0469088"), "long ton", "longton", "longtons")
_einheit("volumen", Fraction("3.785411784"), "gal", "gallon", "gallons", "usgal")
_einheit("volumen", Fraction("0.946352946"), "qt", "quart", "quarts")
_einheit("volumen", Fraction("0.473176473"), "pt", "pint", "pints")
_einheit("volumen", Fraction("0.0295735295625"), "fl oz", "floz", "fluidounce", "fluidounces")
_einheit("volumen", Fraction("0.24"), "cup", "cups")
_einheit("volumen", Fraction("4.54609"), "UK gal", "ukgal")
_einheit("volumen", Fraction("1.1365225"), "UK qt", "ukqt")
_einheit("volumen", Fraction("0.56826125"), "UK pt", "ukpt")
_einheit("volumen", Fraction("0.0284130625"), "UK fl oz", "ukfloz")
_einheit("fläche", Fraction("0.09290304"), "sq ft", "sqft", "ft²", "ft2")
_einheit("fläche", Fraction("0.00064516"), "sq in", "sqin", "in²", "in2")
_einheit("fläche", Fraction("0.83612736"), "sq yd", "sqyd", "yd²", "yd2")
_einheit("fläche", Fraction("2589988.110336"), "sq mi", "sqmi", "mi²", "mi2")
_einheit("fläche", Fraction("4046.8564224"), "acre", "acres")
_UNKLAR = {
    "gal": ("Gerechnet mit der US-Gallone (3,785 l); die britische Gallone hat 4,546 l („imperial gallon“ schreiben).",
            "Calculated with the US gallon (3.785 l); the UK gallon is 4.546 l (write “imperial gallon”)."),
    "qt": ("Gerechnet mit dem US-Quart (0,946 l); das britische hat 1,137 l.", "Calculated with the US quart (0.946 l); the UK quart is 1.137 l."),
    "pt": ("Gerechnet mit dem US-Pint (473 ml); das britische Pint hat 568 ml („imperial pint“ schreiben).",
           "Calculated with the US pint (473 ml); the UK pint is 568 ml (write “imperial pint”)."),
    "fl oz": ("Gerechnet mit der US-Flüssigunze (29,57 ml); die britische hat 28,41 ml.", "Calculated with the US fluid ounce (29.57 ml); the UK one is 28.41 ml."),
    "cup": ("Gerechnet mit der US-Cup (240 ml); in Großbritannien und Australien zählt die Cup oft 250 ml.",
            "Calculated with the US cup (240 ml); in the UK and Australia a cup is often 250 ml."),
    "short ton": ("Gerechnet mit der US-Tonne (907 kg); die britische Tonne hat 1016 kg, die metrische 1000 kg.",
                  "Calculated with the US ton (907 kg); the UK ton is 1016 kg, the metric tonne 1000 kg."),
}
_einheit("volumen", _f(15, 1000), "EL", "el", "esslöffel", "essloeffel", "tbsp", "tablespoon", "tablespoons")
_einheit("volumen", _f(5, 1000), "TL", "tl", "teelöffel", "teeloeffel", "tsp", "teaspoon", "teaspoons")
_einheit("volumen", _f(250, 1000), "Tasse", "tasse", "tassen")
_ENGLISCH.update({"stone": ("stone", "stone"), "acre": ("acre", "acres"), "EL": ("tbsp", "tbsp"), "TL": ("tsp", "tsp"), "Tasse": ("cup", "cups"), "cup": ("cup", "cups"),
                  "gal": ("gallon", "gallons"), "qt": ("quart", "quarts"), "pt": ("pint", "pints"), "fl oz": ("fl oz", "fl oz"), "UK gal": ("UK gallon", "UK gallons"),
                  "UK qt": ("UK quart", "UK quarts"), "UK pt": ("UK pint", "UK pints"), "UK fl oz": ("UK fl oz", "UK fl oz"), "short ton": ("short ton", "short tons"),
                  "long ton": ("long ton", "long tons")})
_DE_NAMEN = {"gal": ("Gallone", "Gallonen"), "qt": ("Quart", "Quart"), "pt": ("Pint", "Pint"), "cup": ("Cup", "Cups"), "Tasse": ("Tasse", "Tassen"), "short ton": ("US-Tonne", "US-Tonnen"),
             "long ton": ("britische Tonne", "britische Tonnen"), "UK gal": ("britische Gallone", "britische Gallonen"), "UK qt": ("britisches Quart", "britische Quart"),
             "UK pt": ("britisches Pint", "britische Pint"), "stone": ("Stone", "Stone"), "acre": ("Acre", "Acres")}
_LANGE_NAMEN.extend(sorted(n for n, e in _EINHEITEN.items() if len(n) >= 6 and n.isalpha() and e[0] != "zeit" and not n.endswith(("tre", "tres"))))
_TEMP = {"°c": "C", "celsius": "C", "°f": "F", "fahrenheit": "F", "kelvin": "K", "°k": "K", "k": "K", "f": "F", "c": "C", "gasmark": "G"}
_TEMP_ZEICHEN = {"C": " °C", "F": " °F", "K": " K", "G": " (Gas Mark)"}
_GAS = {Fraction(1, 4): 110, Fraction(1, 2): 120, Fraction(1): 140, Fraction(2): 150, Fraction(3): 170, Fraction(4): 180, Fraction(5): 190, Fraction(6): 200, Fraction(7): 220,
        Fraction(8): 230, Fraction(9): 240}
_OFEN_WOERTER = frozenset("oven bake baking baked backofen ofen backen umluft heißluft heissluft temperature temperatur gas for degrees grad zum beim fürs für bei the a at set preheat".split())

_FUELLWOERTER = frozenset("""wie viel viele wieviel wieviele sind ist das ergibt ergeben macht machen entspricht in auf zu nach um umrechnen umrechnung
rechne rechnen rechnet wandle wandel wandeln konvertiere umwandeln umwandlung bitte mir mal kurz und oder also gleich was
groß gross lang lange how many much is are convert to into what the please me equal equals equivalent and or per that this does it whats tell give show""".split())

_WORT = r"[A-Za-zÄÖÜäöüß°²³µ]+[23]?(?:/[A-Za-zÄÖÜäöüß]+)?"

_GRUPPEN = [
    (r"\b(?:kilomet(?:er|re)s?|kilometer|km)\s*(?:per|pro|an|in\s+der|je|/|a)\s*(?:hour|stunde|std|h)\b", "km/h"),
    (r"\b(?:miles?|meilen?|mi)\s*(?:per|pro|an|in\s+der|je|/|a)\s*(?:hour|stunde|std|h)\b", "mph"),
    (r"\b(?:met(?:er|re)s?|meter)\s*(?:per|pro|je|/)\s*(?:second|sekunde|sek|s)\b", "m/s"),
    (r"\b(?:feet|foot|ft)\s*(?:per|pro|/)\s*(?:second|sekunde|sec|s)\b", "ft/s"),
    (r"\bknots?\b", "knots"),
    (r"\bnautical\s+miles?\b", "nmi"),
    (r"\bsquare\s+(?:feet|foot)\b|\bsq\.?\s*ft\b", "sqft"),
    (r"\bsquare\s+inch(?:es)?\b|\bsq\.?\s*in\b", "sqin"),
    (r"\bsquare\s+yards?\b|\bsq\.?\s*yd\b", "sqyd"),
    (r"\bsquare\s+miles?\b|\bsq\.?\s*mi\b", "sqmi"),
    (r"\bsquare\s+met(?:er|re)s?\b|\bsq\.?\s*m\b", "m²"),
    (r"\bsquare\s+kilomet(?:er|re)s?\b|\bsq\.?\s*km\b", "km²"),
    (r"\b(?:imperial|uk|british)\s+gallons?\b", "ukgal"),
    (r"\b(?:imperial|uk|british)\s+pints?\b", "ukpt"),
    (r"\b(?:imperial|uk|british)\s+quarts?\b", "ukqt"),
    (r"\b(?:imperial|uk|british)\s+(?:fl\.?\s*oz|fluid\s+ounces?)\b", "ukfloz"),
    (r"\b(?:us|american)\s+(gallons?|pints?|quarts?|cups?)\b", r"\1"),
    (r"\bfl\.?\s*oz\b|\bfluid\s+ounces?\b", "floz"),
    (r"\b(?:long|imperial|uk|british)\s+tons?\b", "longton"),
    (r"\b(?:short|us|american)\s+tons?\b", "shortton"),
    (r"\bmetric\s+tons?\b", "tonne"),
    (r"\bdegrees?\s+(celsius|fahrenheit|centigrade)\b", r"\1"),
    (r"\bcentigrade\b", "celsius"),
    (r"°\s*([cfk])\b", r"°\1"),
    (r"\bgas\s*mark\s*(?:1/4|¼)", "0.25 gasmark"),
    (r"\bgas\s*mark\s*(?:1/2|½)", "0.5 gasmark"),
    (r"\bgas\s*mark\s*(\d+(?:[.,]\d+)?)", r"\1 gasmark"),
    (r"\bgas\s*mark\b", "gasmark"),
]
_GRUPPEN_RE = [(re.compile(m, re.I), e) for m, e in _GRUPPEN]
_ZOLL_FUSS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:'|′|ft\.?|feet|foot)\s*(\d+(?:[.,]\d+)?)\s*(?:\"|″|”|''|in\b\.?|inch(?:es)?\b)?(?!\w)", re.I)
_FUSS_ZOLL_IN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ft\.?|feet|foot)\s+(\d+(?:[.,]\d+)?)\s*in\b(\s+(?:in|to|into|as|auf|nach)\b)?", re.I)


def _vornormalisieren(t: str) -> str:
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:'|′)\s*(\d+(?:[.,]\d+)?)\s*(?:\"|″|”|'')", r"\1 ft \2 inch", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:'|′)\s*(\d+(?:[.,]\d+)?)(?![\d'\"″”])", r"\1 ft \2 inch", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:'|′)(?!\w)", r"\1 ft", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:\"|″|”|'')", r"\1 inch", t)
    t = _FUSS_ZOLL_IN.sub(lambda m: f"{m.group(1)} ft {m.group(2)} inch" + (m.group(3) if m.group(3) else " in"), t)
    for muster, ersatz in _GRUPPEN_RE:
        t = muster.sub(ersatz, t)
    return t
_TOKEN = re.compile(rf"(?P<zahl>{_ZAHL_ROH})|(?P<wort>{_WORT})|(?P<rest>\S)")


def _einheit_von(wort: str) -> tuple[str, Fraction, str] | None:
    w = wort.lower()
    if w in _EINHEITEN:
        e = _EINHEITEN[w]
        if e[2] in _UNKLAR:
            if getattr(_LOKAL, "sammeln", False):
                _LOKAL.__dict__.setdefault("unklar", []).append(e[2])
        return e
    if len(w) >= 6:
        for k in (w[:-1], w[:-2]):
            if k in _EINHEITEN and _EINHEITEN[k][0] != "zeit":
                return _EINHEITEN[k]
    if len(w) >= 7 and w.isalpha():
        nah = difflib.get_close_matches(w, _LANGE_NAMEN, n=1, cutoff=0.88)
        if nah:
            if getattr(_LOKAL, "sammeln", False):
                _LOKAL.__dict__.setdefault("fix", []).append((wort, nah[0]))
            return _EINHEITEN[nah[0]]
    return None


def enthaelt_masseinheit(text: str) -> bool:
    for m in re.finditer(rf"(?<![\w.,])({_ZAHL_ROH})\s*({_WORT})", text):
        if m.group(2).lower() in _EINHEITEN or _einheit_von(m.group(2)) is not None:
            return True
    return False


def ist_umrechnungsfrage(text: str) -> bool:
    if not enthaelt_masseinheit(text):
        return False
    for m in re.finditer(rf"\b(?:in|nach|zu|auf|to|into)\s+({_WORT})", text, re.I):
        if _einheit_von(m.group(1)) is not None:
            return True
    return False


def _name(zahl: Fraction, kurz: str, en: bool = False) -> str:
    if en and kurz in _ENGLISCH:
        return _ENGLISCH[kurz][0 if zahl == 1 else 1]
    if not en and kurz in _DE_NAMEN:
        return _DE_NAMEN[kurz][0 if zahl == 1 else 1]
    return _SINGULAR.get(kurz, kurz) if zahl == 1 else kurz


def _quelle_lesen(text: str):
    text = _vornormalisieren(text)
    t = text.lower().replace("grad celsius", "celsius").replace("grad fahrenheit", "fahrenheit").replace("wie viel", "wieviel")
    toks = [(m.lastgroup, m.group()) for m in _TOKEN.finditer(t)]
    teile: list[tuple[Fraction, tuple[str, Fraction, str]]] = []
    ziele: list[tuple[str, Fraction, str]] = []
    temp_quelle: tuple[Fraction, str] | None = None
    temp_ziele: list[str] = []
    i = 0
    vorzeichen = 1
    while i < len(toks):
        art, wert = toks[i]
        if art == "rest" and wert in ("-", "−", "–") and i + 1 < len(toks) and toks[i + 1][0] == "zahl" and not teile and temp_quelle is None:
            vorzeichen = -1
            i += 1
            continue
        if art == "zahl":
            if i + 1 >= len(toks) or toks[i + 1][0] != "wort":
                raise _Nein
            nxt = toks[i + 1][1]
            zahl_v, vorzeichen = zahl_lesen(wert) * vorzeichen, 1
            if _einheit_von(nxt) is not None:
                teile.append((zahl_v, _einheit_von(nxt)))
            elif nxt in _TEMP and temp_quelle is None:
                temp_quelle = (zahl_v, _TEMP[nxt])
            elif nxt in ("grad", "degrees", "degree") and temp_quelle is None:
                temp_quelle = (zahl_v, "?")
            else:
                raise _Nein
            i += 2
            continue
        if art == "wort":
            if _einheit_von(wert) is not None:
                ziele.append(_einheit_von(wert))
            elif wert in _TEMP:
                temp_ziele.append(_TEMP[wert])
            elif wert in _OFEN_WOERTER:
                _LOKAL.ofen = True
            elif wert not in _FUELLWOERTER:
                raise _Nein
        elif wert not in ",.;:?!=":
            raise _Nein
        i += 1
    return teile, ziele, temp_quelle, temp_ziele


def _aufteilen(menge: Fraction, ziele: list[tuple[str, Fraction, str]]) -> list[tuple[Fraction, str]]:
    ordnung = sorted(ziele, key=lambda e: e[1], reverse=True)
    rest = menge
    out = []
    for j, (_, faktor, kurz) in enumerate(ordnung):
        if j == len(ordnung) - 1:
            out.append((rest / faktor, kurz))
        else:
            n = math.floor(rest / faktor)
            out.append((Fraction(n), kurz))
            rest -= n * faktor
    return out


def _umrechnen(text: str) -> Ergebnis:
    _LOKAL.fix, _LOKAL.unklar, _LOKAL.ofen, _LOKAL.celsius, _LOKAL.sammeln = [], [], False, None, True
    try:
        r = _umrechnen_kern(text)
    finally:
        _LOKAL.sammeln = False
    unklar = list(dict.fromkeys(_LOKAL.unklar))
    if unklar:
        trenn = "\n" if "\n" in r.de else " "
        r = Ergebnis(r.de + trenn + "(" + " ".join(_UNKLAR[k][0] for k in unklar) + ")", r.en + trenn + "(" + " ".join(_UNKLAR[k][1] for k in unklar) + ")")
    if _LOKAL.ofen and _LOKAL.celsius is not None and 100 <= _LOKAL.celsius <= 300:
        c = _LOKAL.celsius
        gas = min(_GAS, key=lambda g: abs(_GAS[g] - c))
        umluft = round(c - 20)
        r = Ergebnis(r.de + f"\nBackofen: das gilt für Ober- und Unterhitze; bei Umluft nimmt man etwa 20 °C weniger (hier rund {umluft} °C). Gas Mark: etwa {zahl_text(gas)}.",
                     r.en + f"\nOven: this is for a conventional oven; a fan oven usually runs about 20 °C (25 °F) cooler (here about {umluft} °C). Gas mark: about {zahl_text(gas, True)}.")
    fix = list(dict.fromkeys(_LOKAL.fix))
    if fix:
        wie = ", ".join(f"„{a}“ als „{b.capitalize()}“" for a, b in fix)
        wie_en = ", ".join(f"“{a}” as “{b.capitalize()}”" for a, b in fix)
        trenn = "\n" if "\n" in r.de else " "
        r = Ergebnis(r.de + f"{trenn}(Ich habe {wie} gelesen.)", r.en + f"{trenn}(I read {wie_en}.)")
    if re.search(r"Monat|Jahr", r.de) and not (re.search(r"Monat", r.de) and re.search(r"Jahr", r.de)):
        return Ergebnis(r.de + " (Ein Jahr zählt hier 365 Tage, ein Monat ein Zwölftel davon.)", r.en + " (A year counts as 365 days here, a month as a twelfth of that.)")
    return r


def _umrechnen_kern(text: str) -> Ergebnis:
    teile, ziele, temp_quelle, temp_ziele = _quelle_lesen(text)
    if temp_quelle is not None or temp_ziele:
        if temp_quelle is None or not temp_ziele or teile or ziele:
            raise _Nein
        if temp_quelle[1] == "?":
            if "C" in temp_ziele:
                raise _Nein
            temp_quelle = (temp_quelle[0], "C")
        return _temperatur(temp_quelle, temp_ziele)
    if not teile or not ziele:
        raise _Nein
    groesse = teile[0][1][0]
    if any(e[0] != groesse for _, e in teile) or any(z[0] != groesse for z in ziele):
        raise _Nein
    menge = sum((zahl * e[1] for zahl, e in teile), Fraction(0))
    quelle = {en: " ".join(f"{zahl_text(z, en)} {_name(z, e[2], en)}" for z, e in teile) for en in (False, True)}
    einzig: list[tuple[str, Fraction, str]] = []
    for z in ziele:
        if z[2] not in [u[2] for u in einzig]:
            einzig.append(z)

    def zeile(z: tuple[str, Fraction, str], en: bool) -> str:
        return f"{zahl_mit_rund(menge / z[1], en)} {_name(menge / z[1], z[2], en)}"

    if len(einzig) == 1:
        z = einzig[0]
        weg = {False: "", True: ""}
        if len(teile) == 1 and teile[0][1][2] != z[2] and teile[0][0] != 1:
            zahl, e = teile[0]
            v = e[1] / z[1]
            mal = v >= 1 or ((1 / v).denominator != 1 and _dezimal(v)[1])
            for en in (False, True):
                ein, wort = ("Rechnung", "also") if not en else ("Working", "so")
                eins = Fraction(1)
                if mal:
                    weg[en] = (f" {ein}: 1 {_name(eins, e[2], en)} = {zahl_text(v, en)} {_name(v, z[2], en)}, {wort} {zahl_text(zahl, en)} × {zahl_text(v, en)} = {zahl_text(zahl * v, en)}.")
                else:
                    teiler = 1 / v
                    weg[en] = (f" {ein}: 1 {_name(eins, z[2], en)} = {zahl_text(teiler, en)} {_name(teiler, e[2], en)}, {wort} {zahl_text(zahl, en)} ÷ {zahl_text(teiler, en)} = {zahl_text(zahl * v, en)}.")
        return Ergebnis(f"{quelle[False]} sind {zeile(z, False)}.{weg[False]}", f"{quelle[True]} is {zeile(z, True)}.{weg[True]}")
    de = f"{quelle[False]} sind:\n" + "\n".join("– " + zeile(z, False) for z in einzig)
    en_t = f"{quelle[True]} equals:\n" + "\n".join("– " + zeile(z, True) for z in einzig)
    aufg = [(n, k) for n, k in _aufteilen(menge, einzig) if n != 0] if menge >= 0 else []
    if len(aufg) >= 2:
        de += "\nAufgeteilt: " + " ".join(f"{zahl_text(n)} {k}" for n, k in aufg) + "."
        en_t += "\nBroken down: " + " ".join(f"{zahl_text(n, True)} {k}" for n, k in aufg) + "."
    return Ergebnis(de, en_t)


def _temperatur(q: tuple[Fraction, str], ziele: list[str]) -> Ergebnis:
    zahl, von = q
    if von == "G":
        if zahl not in _GAS:
            raise _Nein
        c = Fraction(_GAS[zahl])
    else:
        c = zahl if von == "C" else (zahl - 32) * Fraction(5, 9) if von == "F" else zahl - Fraction("273.15")
    if c < Fraction("-273.15"):
        raise _Nein
    _LOKAL.celsius = c
    einzig = list(dict.fromkeys(z for z in ziele if not (z == "G" and von == "G")))
    if not einzig:
        raise _Nein

    def wert(z: str) -> Fraction:
        if z == "G":
            return min(_GAS, key=lambda g: abs(_GAS[g] - c))
        return c if z == "C" else c * Fraction(9, 5) + 32 if z == "F" else c + Fraction("273.15")

    def text(z: str, en: bool) -> str:
        if z == "G":
            return ("gas mark " if en else "Gas Mark ") + ("about " if en else "etwa ") + zahl_text(wert(z), en)
        return f"{zahl_mit_rund(wert(z), en)}{_TEMP_ZEICHEN[z]}"

    de = [text(z, False) for z in einzig]
    en = [text(z, True) for z in einzig]
    qd = f"Gas Mark {zahl_text(zahl)}" if von == "G" else f"{zahl_text(zahl)}{_TEMP_ZEICHEN[von]}"
    qe = f"gas mark {zahl_text(zahl, True)}" if von == "G" else f"{zahl_text(zahl, True)}{_TEMP_ZEICHEN[von]}"
    if len(de) == 1:
        return Ergebnis(f"{qd} sind {de[0]}.", f"{qe} is {en[0]}.")
    return Ergebnis(f"{qd} sind:\n" + "\n".join("– " + x for x in de), f"{qe} equals:\n" + "\n".join("– " + x for x in en))


_FRAGE_VORSPANN = re.compile(
    r"^\s*(?:(?:bitte\s+)?(?:was\s+(?:ist|ergibt|macht|sind)|wie\s*viel(?:e)?\s+(?:ist|ergibt|macht|sind)|berechne|berechnen|rechne(?:\s+aus)?|rechne\s+mir|"
    r"löse|loese|ergibt|how\s+much\s+is|what\s+is|what's|whats|calculate|compute|solve)\s+)+", re.I)
_FRAGE_NACHSPANN = re.compile(r"(?:\s*(?:bitte|ergibt\s+das|ist\s+das|macht\s+das|gleich|=|\?|!|\.|,|please))*\s*$", re.I)
_OPERATOREN = (
    (re.compile(r"\bgeteilt\s+durch\b|\bdividiert\s+durch\b|\bdivided\s+by\b|\bdurch\b", re.I), "/"),
    (re.compile(r"\bmal\b|\bmultipliziert\s+mit\b|\btimes\b|\bmultiplied\s+by\b", re.I), "*"),
    (re.compile(r"\bplus\b", re.I), "+"),
    (re.compile(r"\bminus\b", re.I), "-"),
    (re.compile(r"\bhoch\b|\bto\s+the\s+power\s+of\b", re.I), "^"),
)
_BRUCH = re.compile(r"(?<![\d.,/])(\d+)/(\d+)(?![\d/])")
_GEMISCHT = re.compile(r"(?<![\d.,/])(\d+)\s+(\d+)/(\d+)(?![\d/])")
_OPS = ("+", "-", "*", "/", "^")


def _vorbehandeln(text: str) -> str:
    t = " ".join(text.lower().split())
    t = _FRAGE_VORSPANN.sub("", t)
    return _FRAGE_NACHSPANN.sub("", t).strip()


class _Rechner:

    def __init__(self, teile: list[str], werte: dict[str, Fraction]) -> None:
        self.t, self.w, self.i, self.ops, self.inexakt = teile, werte, 0, 0, False

    def _peek(self) -> str:
        return self.t[self.i] if self.i < len(self.t) else ""

    def _nimm(self) -> str:
        v = self._peek()
        self.i += 1
        return v

    def lauf(self) -> Fraction:
        x = self._summe()
        if self.i != len(self.t):
            raise _Nein
        return x

    def _pruefen(self, x: Fraction) -> Fraction:
        self.ops += 1
        if self.ops > 60 or x.numerator.bit_length() > MAX_ERGEBNIS_BITS or x.denominator.bit_length() > MAX_ERGEBNIS_BITS:
            raise _Nein
        return x

    def _summe(self) -> Fraction:
        x = self._produkt()
        while self._peek() in ("+", "-"):
            op = self._nimm()
            y = self._produkt()
            x = self._pruefen(x + y if op == "+" else x - y)
        return x

    def _produkt(self) -> Fraction:
        x = self._potenz()
        while self._peek() in ("*", "/"):
            op = self._nimm()
            y = self._potenz()
            if op == "/":
                if y == 0:
                    raise _Null
                x = self._pruefen(x / y)
            else:
                x = self._pruefen(x * y)
        return x

    def _potenz(self) -> Fraction:
        x = self._vorzeichen()
        if self._peek() == "^":
            self._nimm()
            y = self._potenz()
            if y.denominator != 1 or abs(y) > 200:
                raise _Nein
            if x == 0 and y < 0:
                raise _Null
            if abs(x.numerator).bit_length() * abs(int(y)) > MAX_ERGEBNIS_BITS:
                raise _Nein
            x = self._pruefen(x ** int(y))
        return x

    def _vorzeichen(self) -> Fraction:
        if self._peek() in ("-", "+"):
            return -self._vorzeichen() if self._nimm() == "-" else self._vorzeichen()
        return self._atom()

    def _atom(self) -> Fraction:
        t = self._nimm()
        if t == "(":
            x = self._summe()
            if self._nimm() != ")":
                raise _Nein
            return x
        if t == "sqrt":
            if self._nimm() != "(":
                raise _Nein
            x = self._summe()
            if self._nimm() != ")":
                raise _Nein
            return self._wurzel(x)
        if t in self.w:
            return self.w[t]
        raise _Nein

    def _wurzel(self, x: Fraction) -> Fraction:
        if x < 0:
            raise _Nein
        zr, nr = math.isqrt(x.numerator), math.isqrt(x.denominator)
        if zr * zr == x.numerator and nr * nr == x.denominator:
            return Fraction(zr, nr)
        if x.numerator.bit_length() > 200 or x.denominator.bit_length() > 200:
            raise _Nein
        self.inexakt = True
        return Fraction(round(math.sqrt(x.numerator / x.denominator) * 10 ** 8), 10 ** 8)


def _rechnung_vorbereiten(text: str):
    t = _vorbehandeln(text)
    if not t or len(t) > MAX_TEXT or re.search(r"\d/\d+/\d", t):
        raise _Nein
    t = re.sub(r"(?<=\d)\s*(?:€|\beuro\b|\beur\b)", "€", t)
    t = re.sub(rf"€\s*({_ZAHL_ROH})", r"\1€", t)
    geld = "€" in t
    t = t.replace("×", "*").replace("·", "*").replace("÷", " / ").replace("−", "-").replace("–", "-").replace("√", " sqrt ")
    t = re.sub(r"(?<=\d)\s*[x*]\s*(?=[\d(])", " * ", t)
    t = re.sub(r"(?<=\d)\s*:\s*(?=\d)", " / ", t)
    t = re.sub(r"\b(?:wurzel\s+aus|(?:the\s+)?square\s+root\s+of)\s+", "sqrt ", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s+squared\b", r"(\1)^2", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s+cubed\b", r"(\1)^3", t)
    t = re.sub(r"\bwurzel\s*\(", "sqrt(", t)
    t = re.sub(r"\bsqrt\s+(\d+(?:[.,]\d+)?)", r"sqrt(\1)", t)
    t = re.sub(r"\bquadrat\s+von\s+(\d+(?:[.,]\d+)?)", r"(\1)^2", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*²", r"(\1)^2", t)
    t = re.sub(r"(\d+(?:[.,]\d+)?)\s*³", r"(\1)^3", t)
    for muster, op in _OPERATOREN:
        t = muster.sub(f" {op} ", t)
    werte: dict[str, Fraction] = {}
    texte: dict[str, str] = {}
    bruchmodus = False
    marken: set[str] = set()

    def neu(wert: Fraction, getippt: str) -> str:
        k = f"#{len(werte)}"
        werte[k], texte[k] = wert, getippt
        return f" {k} "

    def gemischt(m: re.Match) -> str:
        nonlocal bruchmodus
        n, z, d = (int(g) for g in m.groups())
        if d == 0 or z >= d or max(len(g) for g in m.groups()) > MAX_STELLEN:
            raise _Nein
        bruchmodus = True
        return neu(n + Fraction(z, d), m.group(0))

    def bruch(m: re.Match) -> str:
        nonlocal bruchmodus
        z, d = int(m.group(1)), int(m.group(2))
        if d == 0:
            raise _Null
        if max(len(g) for g in m.groups()) > MAX_STELLEN:
            raise _Nein
        bruchmodus = True
        return neu(Fraction(z, d), m.group(0))

    t = _GEMISCHT.sub(gemischt, t)
    t = _BRUCH.sub(bruch, t)
    def zahl(m: re.Match) -> str:
        k = neu(zahl_lesen(m.group(1)), m.group(1) + (" €" if m.group(2) else "")).strip()
        if m.group(2):
            marken.add(k)
        return f" {k} "

    t = re.sub(rf"(?<![#\w])({_ZAHL_ROH})(€)?", zahl, t)
    if geld and (bruchmodus or "sqrt" in t or "^" in t):
        raise _Nein
    teile = re.findall(r"#\d+|sqrt|[()+\-*/^]|\S", t)
    if any(x not in werte and x not in ("sqrt", "(", ")", *_OPS) for x in teile):
        raise _Nein
    if not any(x in _OPS or x == "sqrt" for x in teile) or (sum(1 for x in teile if x in werte) < 2 and "sqrt" not in teile):
        raise _Nein
    return teile, werte, texte, bruchmodus, (geld and bool(marken))


def _anzeige(teile: list[str], texte: dict[str, str]) -> str:
    sym = {"*": "×", "/": "÷", "sqrt": "√"}
    out = ""
    vorzeichen = False
    for i, x in enumerate(teile):
        teil = texte.get(x) or sym.get(x, x)
        einstellig = x in ("+", "-") and (i == 0 or teile[i - 1] in ("(", *_OPS))
        klebt = out == "" or out.endswith(("(", "√")) or vorzeichen or x == ")"
        out += teil if klebt else " " + teil
        vorzeichen = einstellig
    return out


def _bruchweg(teile: list[str], werte: dict[str, Fraction], texte: dict[str, str]) -> tuple[str, Fraction] | None:
    if len(teile) != 3 or teile[1] not in ("+", "-", "*", "/") or teile[0] not in werte or teile[2] not in werte:
        return None
    a, b = werte[teile[0]], werte[teile[2]]
    ta, tb, op = texte[teile[0]], texte[teile[2]], teile[1]
    if op in ("+", "-"):
        sym = "+" if op == "+" else "−"
        nenner = math.lcm(a.denominator, b.denominator)
        za, zb = a.numerator * (nenner // a.denominator), b.numerator * (nenner // b.denominator)
        zs = za + zb if op == "+" else za - zb
        weg = [f"{ta} {sym} {tb}"]
        if a.denominator != b.denominator:
            weg.append(f"{za}/{nenner} {sym} {zb}/{nenner}")
        weg.append(f"{zs}/{nenner}")
        r = a + b if op == "+" else a - b
    elif op == "*":
        r = a * b
        weg = [f"{ta} × {tb}", f"{a.numerator * b.numerator}/{a.denominator * b.denominator}"]
    else:
        if b == 0:
            raise _Null
        r = a / b
        weg = [f"{ta} ÷ {tb}", f"{ta} × {b.denominator}/{b.numerator}", f"{a.numerator * b.denominator}/{a.denominator * b.numerator}"]
    if bruch_text(r) != weg[-1]:
        weg.append(bruch_text(r))
    return " = ".join(weg), r


_STUFE = {"^": 3, "*": 2, "/": 2, "+": 1, "-": 1}
_MAX_ZEILEN = 8


def _zahl_im_weg(x: Fraction, bruch: bool, geld: bool, en: bool) -> str:
    if geld:
        if (x * 100).denominator != 1:
            raise _Nein
        return geld_text(x, en)
    if bruch:
        return bruch_text(x)
    if not _dezimal(x)[1]:
        raise _Nein
    return zahl_text(x, en)


def _weg_zeile(items: list, bruch: bool, geld: bool, en: bool) -> str:
    out = ""
    for it in items:
        tx = _zahl_im_weg(it, bruch, geld, en) if isinstance(it, Fraction) else {"*": "×", "/": "÷", "sqrt": "√"}.get(it, it)
        out += tx if (out == "" or out.endswith(("(", "√")) or tx == ")") else " " + tx
    return out


def _schritte(teile: list[str], werte: dict[str, Fraction], bruch: bool, geld: bool, en: bool = False) -> list[str] | None:
    items: list = []
    i = 0
    while i < len(teile):
        x = teile[i]
        if x in ("+", "-") and (i == 0 or teile[i - 1] in ("(", *_OPS)):
            if i + 1 < len(teile) and teile[i + 1] in werte:
                items.append(-werte[teile[i + 1]] if x == "-" else werte[teile[i + 1]])
                i += 2
                continue
            return None
        items.append(werte[x] if x in werte else x)
        i += 1
    zeilen: list[str] = []
    for _ in range(40):
        if len(items) == 1 and isinstance(items[0], Fraction):
            break
        start, ende = -1, len(items)
        for j, it in enumerate(items):
            if it == "(":
                start = j
            elif it == ")":
                ende = j
                break
        innen = items[start + 1:ende]
        if len(innen) == 1 and isinstance(innen[0], Fraction):
            if start > 0 and items[start - 1] == "sqrt":
                x = innen[0]
                zr, nr = math.isqrt(x.numerator), math.isqrt(x.denominator)
                if x < 0 or zr * zr != x.numerator or nr * nr != x.denominator:
                    return None
                items[start - 1:ende + 1] = [Fraction(zr, nr)]
                zeilen.append(_weg_zeile(items, bruch, geld, en))
            else:
                items[start:ende + 1] = [innen[0]]
            continue
        stufen = [_STUFE[it] for it in innen if isinstance(it, str) and it in _STUFE]
        if not stufen:
            return None
        top = max(stufen)
        seq = list(innen)
        angewandt = 0
        while True:
            ks = [k for k, it in enumerate(seq) if isinstance(it, str) and _STUFE.get(it) == top]
            if not ks or len(seq) < 3:
                break
            k = ks[-1] if top == 3 else ks[0]
            if bruch and angewandt:
                break
            a, op, b = seq[k - 1], seq[k], seq[k + 1]
            if not (isinstance(a, Fraction) and isinstance(b, Fraction)):
                return None
            if op == "/" and b == 0:
                raise _Null
            if op == "^" and (b.denominator != 1 or abs(b) > 200):
                return None
            wert = a + b if op == "+" else a - b if op == "-" else a * b if op == "*" else a / b if op == "/" else a ** int(b)
            seq[k - 1:k + 2] = [wert]
            angewandt += 1
        if start == -1:
            items = seq
        else:
            items[start + 1:ende] = seq
            if len(seq) == 1 and not (start > 0 and items[start - 1] == "sqrt"):
                items[start:start + 3] = [seq[0]]
        zeilen.append(_weg_zeile(items, bruch, geld, en))
        if len(zeilen) > _MAX_ZEILEN:
            return None
    else:
        return None
    return zeilen if len(zeilen) >= 2 else None


def _rechnen(text: str) -> Ergebnis:
    teile, werte, texte, bruchmodus, geld = _rechnung_vorbereiten(text)
    rechner = _Rechner(teile, werte)
    r = rechner.lauf()
    links = _anzeige(teile, texte)

    def weg(en: bool) -> list[str] | None:
        if rechner.inexakt:
            return None
        try:
            z = _schritte(teile, werte, bruchmodus, geld, en)
        except _Nein:
            return None
        return z if z and z[-1] == _zahl_im_weg(r, bruchmodus, geld, en) else None

    if bruchmodus:
        zwei = _bruchweg(teile, werte, texte)
        z = weg(False)
        if zwei:
            kette = zwei[0]
        elif z:
            kette = " = ".join([links] + z)
        else:
            kette = f"{links} = {bruch_text(r)}"
        gem = gemischt_text(r)
        if gem:
            kette += f" = {gem}"
        dez = {en: "" if r.denominator == 1 else f" ({zahl_mit_rund(r, en)})" for en in (False, True)}
        return Ergebnis(f"{kette}{dez[False]}.", f"{kette}{dez[True]}.")
    if geld:
        genau = (r * 100).denominator == 1
        rund = {False: "" if genau else "rund ", True: "" if genau else "about "}
        text_de = f"{links} = {rund[False]}{geld_text(r)}."
        text_en = f"{_anzeige_en(teile, texte)} = {rund[True]}{geld_text(r, True)}."
        z, ze = weg(False), weg(True)
        if z:
            text_de = " = ".join([links] + z) + "."
        if ze:
            text_en = " = ".join([_anzeige_en(teile, texte)] + ze) + "."
        if all("," not in v and "." not in v for v in texte.values()):
            text_de, text_en = text_de.replace(",00 €", " €"), re.sub(r"(€\d+)\.00(?!\d)", r"\1", text_en)
        return Ergebnis(text_de, text_en)
    if rechner.inexakt:
        runde = Fraction(round(r * 10000), 10000)
        return Ergebnis(f"{links} = rund {zahl_text(runde)}.", f"{links} = about {zahl_text(runde, True)}.")
    z, ze = weg(False), weg(True)
    if z:
        return Ergebnis(" = ".join([links] + z) + ".", " = ".join([links] + ze) + ".")
    rest_de = rest_en = ""
    if len(teile) == 3 and teile[1] == "/" and r.denominator != 1 and all(werte[teile[i]].denominator == 1 for i in (0, 2)):
        q, rest = divmod(werte[teile[0]].numerator, werte[teile[2]].numerator)
        if rest and q >= 1:
            rest_de, rest_en = f" ({q} Rest {rest})", f" ({q} remainder {rest})"
    return Ergebnis(f"{links} = {zahl_mit_rund(r)}{rest_de}.", f"{links} = {zahl_mit_rund(r, True)}{rest_en}.")


def _anzeige_en(teile: list[str], texte: dict[str, str]) -> str:
    ersatz = {k: (f"€{v[:-2].replace(',', '.')}" if v.endswith(" €") else v) for k, v in texte.items()}
    return _anzeige(teile, ersatz)


def _prozent(text: str) -> Ergebnis | None:
    t = _vorbehandeln(text)
    m = re.match(rf"^({_ZAHL_ROH})\s*(?:%|prozent|percent)\s*(?:von|of)\s*({_ZAHL_ROH})\s*(€|euro|eur)?$", t)
    if m:
        p, g = zahl_lesen(m.group(1)), zahl_lesen(m.group(2))
        r = p * g / 100
        if m.group(3):
            return glatt(Ergebnis(f"{zahl_text(p)} % von {geld_text(g)} sind {geld_text(r)}. Rechnung: {geld_text(g)} × {zahl_text(p)} ÷ 100 = {geld_text(r)}.",
                                  f"{zahl_text(p, True)}% of {geld_text(g, True)} is {geld_text(r, True)}. Working: {geld_text(g, True)} × {zahl_text(p, True)} ÷ 100 = {geld_text(r, True)}."), text)
        return Ergebnis(f"{zahl_text(p)} % von {zahl_text(g)} sind {zahl_mit_rund(r)}. Rechnung: {zahl_text(g)} × {zahl_text(p)} ÷ 100 = {zahl_mit_rund(r)}.",
                        f"{zahl_text(p, True)}% of {zahl_text(g, True)} is {zahl_mit_rund(r, True)}. Working: {zahl_text(g, True)} × {zahl_text(p, True)} ÷ 100 = {zahl_mit_rund(r, True)}.")
    m = re.match(rf"^(?:wieviel|wie\s+viel|wie\s+viele?|what)\s*(?:prozent|percent|%)\s*(?:sind|ist|are|is)\s*({_ZAHL_ROH})\s*(?:von|of)\s*({_ZAHL_ROH})$", t)
    if m:
        a, g = zahl_lesen(m.group(1)), zahl_lesen(m.group(2))
        if g == 0:
            raise _Null
        r = a / g * 100
        return Ergebnis(f"{zahl_text(a)} von {zahl_text(g)} sind {zahl_mit_rund(r)} %. Rechnung: {zahl_text(a)} ÷ {zahl_text(g)} × 100 = {zahl_mit_rund(r)}.",
                        f"{zahl_text(a, True)} out of {zahl_text(g, True)} is {zahl_mit_rund(r, True)}%. Working: {zahl_text(a, True)} ÷ {zahl_text(g, True)} × 100 = {zahl_mit_rund(r, True)}.")
    return None


def _gcd_lcm(text: str) -> Ergebnis | None:
    m = re.match(r"^\s*(?:bitte\s+)?(?:(?:berechne|rechne|was\s+ist|wie\s+(?:groß|gross)\s+ist)\s+)?(?:den\s+|das\s+)?(ggt|kgv|größten?\s+gemeinsamen?\s+teiler|"
                 r"groessten?\s+gemeinsamen?\s+teiler|kleinste[sn]?\s+gemeinsame[sn]?\s+vielfache[sn]?|gcd|lcm)\s*(?:von|of|\()?\s*(\d+)\s*(?:und|,|and|;)\s*(\d+)\s*\)?\s*[?.!]*\s*$",
                 text, re.I)
    if not m:
        return None
    a, b = int(m.group(2)), int(m.group(3))
    if a <= 0 or b <= 0 or len(m.group(2)) > MAX_STELLEN or len(m.group(3)) > MAX_STELLEN:
        raise _Nein
    if m.group(1).lower().startswith(("ggt", "gro", "grö", "gcd")):
        r = math.gcd(a, b)
        return Ergebnis(f"Der größte gemeinsame Teiler von {a} und {b} ist {r}.", f"The greatest common divisor of {a} and {b} is {r}.")
    r = math.lcm(a, b)
    return Ergebnis(f"Das kleinste gemeinsame Vielfache von {a} und {b} ist {r}.", f"The least common multiple of {a} and {b} is {r}.")


def _bruch_aufgabe(text: str) -> Ergebnis | None:
    t = re.sub(r"[?!.]+$", "", " ".join(text.lower().split())).strip()
    m = (re.match(r"^(?:bitte\s+)?(?:kürze|kuerze|kürzen|kuerzen|kürz|kuerz|simplify|reduce)\s+(?:den\s+bruch\s+)?(\d+)/(\d+)$", t)
         or re.match(r"^(?:bitte\s+)?(\d+)/(\d+)\s+(?:kürzen|kuerzen|simplify)$", t))
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0 or max(len(m.group(1)), len(m.group(2))) > MAX_STELLEN:
            raise _Nein
        g = math.gcd(a, b)
        if g == 1:
            return Ergebnis(f"{a}/{b} lässt sich nicht weiter kürzen.", f"{a}/{b} can't be reduced any further.")
        return Ergebnis(f"{a}/{b} gekürzt (durch {g}): {a // g}/{b // g}.", f"{a}/{b} reduced (by {g}): {a // g}/{b // g}.")
    m = re.match(r"^(?:bitte\s+)?(?:erweitere|erweitern)\s+(\d+)/(\d+)\s+(?:mit|auf)\s+(\d+)$", t)
    if m:
        a, b, k = (int(g) for g in m.groups())
        if b == 0 or k == 0 or max(len(g) for g in m.groups()) > MAX_STELLEN:
            raise _Nein
        return Ergebnis(f"{a}/{b} mit {k} erweitert: {a * k}/{b * k}.", f"{a}/{b} expanded by {k}: {a * k}/{b * k}.")
    m = re.match(r"^(?:bitte\s+)?(?:(?:wandle|wandel|rechne|schreib\w*)\s+)?(?:den\s+bruch\s+)?(\d+)/(\d+)\s+(?:in|als|to|as)\s+(?:eine\s+|a\s+)?"
                 r"(dezimalzahl|dezimal|kommazahl|decimal|prozent|percent|%)$", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0 or max(len(m.group(1)), len(m.group(2))) > MAX_STELLEN:
            raise _Nein
        x = Fraction(a, b)
        if m.group(3) in ("prozent", "percent", "%"):
            return Ergebnis(f"{a}/{b} = {zahl_mit_rund(x * 100)} %.", f"{a}/{b} = {zahl_mit_rund(x * 100, True)}%.")
        return Ergebnis(f"{a}/{b} = {zahl_mit_rund(x)}.", f"{a}/{b} = {zahl_mit_rund(x, True)}.")
    m = re.match(r"^(?:bitte\s+)?(?:(?:wandle|wandel|rechne|schreib\w*)\s+)?(?:die\s+(?:dezimal|komma)zahl\s+)?(\d+(?:[.,]\d+)?)\s+(?:in|als|to|as)\s+"
                 r"(?:einen\s+|a\s+)?(?:bruch|fraction)$", t)
    if m:
        x = zahl_lesen(m.group(1))
        gem = gemischt_text(x)
        return Ergebnis(f"{m.group(1)} = {bruch_text(x)}" + (f" (das sind {gem})" if gem else "") + ".",
                        f"{m.group(1)} = {bruch_text(x)}" + (f" (that is {gem})" if gem else "") + ".")
    return None


_LEBEN = ("rechnen_zeit", "rechnen_gleichung", "rechnen_geld", "rechnen_kueche", "rechnen_gehalt", "rechnen_international")


def loesen(text: str) -> Ergebnis | None:
    try:
        return _loesen_kern(text)
    finally:
        _WAEHRUNG.englisch, _WAEHRUNG.zeichen = False, "€"


def _loesen_kern(text: str) -> Ergebnis | None:
    t = " ".join(str(text or "").split())
    if not t or len(t) > MAX_TEXT:
        return None
    _WAEHRUNG.englisch = englisch_erkennen(t)
    t = kurzformen(t)
    t, _WAEHRUNG.zeichen = waehrung_normalisieren(t)
    import rechnen_alltag
    import rechnen_datum
    import rechnen_gehalt
    import rechnen_geld
    import rechnen_gleichung
    import rechnen_international
    import rechnen_kueche
    import rechnen_zeit
    try:
        for modul in (rechnen_zeit, rechnen_gleichung, rechnen_geld, rechnen_kueche, rechnen_gehalt):
            if modul.__name__ not in _LEBEN:
                continue
            r = modul.loesen(t)
            if r is not None:
                return r
        r = rechnen_datum.loesen(t)
        if r is not None:
            return r
        r = rechnen_alltag.loesen(t)
        if r is not None:
            return r
        if "rechnen_international" in _LEBEN:
            r = rechnen_international.loesen_vorab(t)
            if r is not None:
                return r
        if not re.search(r"\d", t):
            return None
        for stufe in (_gcd_lcm, _bruch_aufgabe, _prozent):
            r = stufe(t)
            if r is not None:
                return r
        try:
            return _umrechnen(t)
        except _Nein:
            pass
        if "rechnen_international" in _LEBEN:
            r = rechnen_international.loesen_nach(t)
            if r is not None:
                return r
        return _rechnen(t)
    except _Null:
        return Ergebnis("Durch 0 kann man nicht teilen.", "You can't divide by zero.")
    except (_Nein, ValueError, OverflowError, ZeroDivisionError, RecursionError):
        return None
