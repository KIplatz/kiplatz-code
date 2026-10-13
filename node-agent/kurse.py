# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from fractions import Fraction

from rechnen import Ergebnis, englisch_setzen, kurzformen, zahl_lesen, zahl_text

KURSE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
FRISCH_S = 6 * 3600
NOTFALL_S = 4 * 24 * 3600
MAX_BYTES = 60_000
BETRAG_MAX = 10 ** 15

WAEHRUNGEN: dict[str, tuple[str, str, str]] = {
    "EUR": ("Euro", "euros", "€"), "USD": ("US-Dollar", "US dollars", "$"), "GBP": ("Pfund Sterling", "pounds sterling", "£"),
    "CHF": ("Schweizer Franken", "Swiss francs", "CHF"), "JPY": ("Yen", "yen", "¥"), "CNY": ("Yuan", "yuan", "CNY"), "PLN": ("Złoty", "zloty", "PLN"),
    "CZK": ("Tschechische Kronen", "Czech koruna", "CZK"), "HUF": ("Forint", "forint", "HUF"), "SEK": ("Schwedische Kronen", "Swedish kronor", "SEK"),
    "DKK": ("Dänische Kronen", "Danish kroner", "DKK"), "NOK": ("Norwegische Kronen", "Norwegian kroner", "NOK"), "RON": ("Lei", "lei", "RON"),
    "TRY": ("Lira", "lira", "TRY"), "AUD": ("Australische Dollar", "Australian dollars", "AUD"), "CAD": ("Kanadische Dollar", "Canadian dollars", "CAD"),
    "NZD": ("Neuseeland-Dollar", "New Zealand dollars", "NZD"), "INR": ("Indische Rupien", "Indian rupees", "INR"), "BRL": ("Real", "reais", "BRL"),
    "KRW": ("Won", "won", "KRW"), "ZAR": ("Rand", "rand", "ZAR"), "MXN": ("Mexikanische Pesos", "Mexican pesos", "MXN"), "SGD": ("Singapur-Dollar", "Singapore dollars", "SGD"),
    "HKD": ("Hongkong-Dollar", "Hong Kong dollars", "HKD"), "ILS": ("Schekel", "shekels", "ILS"), "ISK": ("Isländische Kronen", "Icelandic krona", "ISK"),
}
_NAMEN = {
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "dollar": "USD", "dollars": "USD", "usd": "USD", "pfund": "GBP", "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "sterling": "GBP",
    "franken": "CHF", "chf": "CHF", "yen": "JPY", "jpy": "JPY", "yuan": "CNY", "renminbi": "CNY", "cny": "CNY", "zloty": "PLN", "złoty": "PLN", "pln": "PLN", "czk": "CZK",
    "forint": "HUF", "huf": "HUF", "sek": "SEK", "dkk": "DKK", "nok": "NOK", "lei": "RON", "leu": "RON", "ron": "RON", "lira": "TRY", "try": "TRY", "aud": "AUD", "cad": "CAD",
    "nzd": "NZD", "rupie": "INR", "rupien": "INR", "rupees": "INR", "inr": "INR", "real": "BRL", "brl": "BRL", "won": "KRW", "krw": "KRW", "rand": "ZAR", "zar": "ZAR",
    "mxn": "MXN", "sgd": "SGD", "hkd": "HKD", "schekel": "ILS", "shekel": "ILS", "ils": "ILS", "isk": "ISK",
}
_MEHRWORT = (
    (r"us[- ]?dollars?|amerikanische[nr]?\s+dollars?", "usd"), (r"kanadische[nr]?\s+dollars?|canadian\s+dollars?", "cad"),
    (r"australische[nr]?\s+dollars?|australian\s+dollars?", "aud"), (r"neuseeland[- ]dollars?|new\s+zealand\s+dollars?", "nzd"),
    (r"singapur[- ]dollars?|singapore\s+dollars?", "sgd"), (r"hongkong[- ]dollars?|hong\s+kong\s+dollars?", "hkd"),
    (r"schweizer\s+franken|swiss\s+francs?|francs?", "chf"), (r"(?:britische[sn]?|englische[sn]?)\s+pfund|pfund\s+sterling|pounds?\s+sterling|british\s+pounds?", "gbp"),
    (r"tschechische[nr]?\s+kronen?|czech\s+kor\w+", "czk"), (r"schwedische[nr]?\s+kronen?|swedish\s+kron\w+", "sek"),
    (r"dänische[nr]?\s+kronen?|daenische[nr]?\s+kronen?|danish\s+kron\w+", "dkk"), (r"norwegische[nr]?\s+kronen?|norwegian\s+kron\w+", "nok"),
    (r"isländische[nr]?\s+kronen?|icelandic\s+kron\w+", "isk"), (r"türkische[nr]?\s+lira|tuerkische[nr]?\s+lira|turkish\s+lira", "try"),
    (r"indische[nr]?\s+rupien?|indian\s+rupees?", "inr"), (r"südkoreanische[nr]?\s+won|suedkoreanische[nr]?\s+won|korean\s+won", "krw"),
    (r"mexikanische[nr]?\s+pesos?|mexican\s+pesos?|pesos?", "mxn"), (r"japanische[nr]?\s+yen", "jpy"), (r"chinesische[nr]?\s+yuan", "cny"),
    (r"südafrikanische[nr]?\s+rand|south\s+african\s+rand", "zar"), (r"brasilianische[nr]?\s+real", "brl"), (r"israelische[nr]?\s+schekel", "ils"),
)
_SYMBOLE = (("€", " eur "), ("$", " usd "), ("£", " gbp "), ("¥", " jpy "))
_FUELL = frozenset("""wie viel viele wieviel wieviele sind ist das ergibt macht entspricht in auf zu nach um umrechnen umrechnung rechne rechnen wandle bitte mir mal kurz und oder
also gleich was der den die von zwischen kurs aktuell aktuellen aktueller heute jetzt wert wechselkurs tauschen tausche wechseln wechsle kostet kosten how many much is are convert to into what the please me
equal equals exchange rate current today and or in worth""".split())
_WORT = r"[A-Za-zÄÖÜäöüßł]+"
_TOKEN = re.compile(rf"(?P<zahl>\d+(?:[.,]\d+)*)|(?P<wort>{_WORT})|(?P<rest>\S)")


@dataclass(frozen=True)
class Frage:
    betrag: Fraction | None
    von: str
    nach: tuple[str, ...]


@dataclass(frozen=True)
class Kurse:
    datum: str
    tabelle: dict


def erkennen(text: str) -> Frage | None:
    try:
        return _erkennen_kern(text)
    finally:
        englisch_setzen("")


def _erkennen_kern(text: str) -> Frage | None:
    englisch_setzen(str(text or ""))
    t = " ".join(kurzformen(str(text or "")).lower().split())
    if not t or len(t) > 120:
        return None
    for sym, wort in _SYMBOLE:
        t = re.sub(rf"{re.escape(sym)}\s*(\d+(?:[.,]\d+)*)", rf"\1{wort}", t)
        t = t.replace(sym, wort)
    t = re.sub(r"(?<=\d)\s*(?=[a-zäöü])", " ", t)
    for muster, code in _MEHRWORT:
        t = re.sub(rf"\b{muster}\b", f" {code} ", t)
    t = re.sub(r"\b(?:eur|usd|gbp|chf|jpy|cny)\s*/\s*(?:eur|usd|gbp|chf|jpy|cny)\b", lambda m: m.group().replace("/", " "), t)
    toks = [(m.lastgroup, m.group()) for m in _TOKEN.finditer(t)]
    betraege: list[tuple[Fraction, str]] = []
    ziele: list[str] = []
    i = 0
    while i < len(toks):
        art, wert = toks[i]
        if art == "zahl":
            if i + 1 >= len(toks) or toks[i + 1][0] != "wort" or toks[i + 1][1] not in _NAMEN:
                return None
            try:
                z = zahl_lesen(wert)
            except Exception:
                return None
            betraege.append((z, _NAMEN[toks[i + 1][1]]))
            i += 2
            continue
        if art == "wort":
            if wert in _NAMEN:
                ziele.append(_NAMEN[wert])
            elif wert not in _FUELL:
                return None
        elif wert not in ",.;:?!=/":
            return None
        i += 1
    ziele = [z for z in dict.fromkeys(ziele)]
    if len(betraege) == 1 and ziele:
        b, von = betraege[0]
        if abs(b) > BETRAG_MAX or b < 0 or all(z == von for z in ziele):
            return None
        return Frage(b, von, tuple(z for z in ziele))
    if not betraege and len(ziele) == 2 and re.search(r"\bkurs\b|wechselkurs|exchange\s+rate|\brate\b", t):
        return Frage(None, ziele[0], (ziele[1],))
    return None


def _aus_xml(roh: bytes) -> Kurse:
    text = roh.decode("utf-8", "replace")
    m = re.search(r"<Cube\s+time=['\"](\d{4}-\d{2}-\d{2})['\"]", text)
    tab = {c: Fraction(r) for c, r in re.findall(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([0-9]+(?:\.[0-9]+)?)['\"]", text)}
    if not m or len(tab) < 15 or any(v <= 0 for v in tab.values()):
        raise ValueError("Kurstabelle nicht lesbar")
    tab["EUR"] = Fraction(1)
    return Kurse(m.group(1), tab)


_SPEICHER: dict = {"zeit": 0.0, "kurse": None}
_SPERRE = threading.Lock()


def holen(oeffner=None, jetzt=time.time) -> Kurse | None:
    with _SPERRE:
        k, z = _SPEICHER["kurse"], _SPEICHER["zeit"]
        if k is not None and jetzt() - z < FRISCH_S:
            return k
        try:
            import nachschauen
            roh = nachschauen._holen(KURSE_URL, oeffner=oeffner or __import__("datenfluss").oeffner("Euro-Kurse der Europäischen Zentralbank"), akzeptiert="application/xml")
            neu = _aus_xml(roh[:MAX_BYTES])
        except Exception:
            return k if k is not None and jetzt() - z < NOTFALL_S else None
        _SPEICHER["kurse"], _SPEICHER["zeit"] = neu, jetzt()
        return neu


def vergessen() -> None:
    with _SPERRE:
        _SPEICHER["kurse"], _SPEICHER["zeit"] = None, 0.0


def _tage_alt(datum: str, heute_s: float) -> int:
    try:
        t = time.mktime(time.strptime(datum, "%Y-%m-%d"))
    except ValueError:
        return 0
    return max(0, int((heute_s - t) // 86400))


def _betrag(x: Fraction, code: str, en: bool) -> str:
    st = 0 if code in ("JPY", "KRW", "HUF", "ISK") else 2
    q = round(x * 10 ** st)
    ganz, rest = divmod(abs(q), 10 ** st)
    text = zahl_text(Fraction(ganz), en) + ((("." if en else ",") + str(rest).rjust(st, "0")) if st else "")
    return "-" + text if q < 0 else text


def _name(code: str, en: bool) -> str:
    return "€" if code == "EUR" else WAEHRUNGEN[code][1 if en else 0]


def antwort(f: Frage, kurse: Kurse, heute_s: float | None = None) -> Ergebnis | None:
    codes = (f.von, *f.nach)
    if any(c not in kurse.tabelle for c in codes) or any(c not in WAEHRUNGEN for c in codes):
        return None
    d = kurse.datum
    datum_de = f"{d[8:10]}.{d[5:7]}.{d[0:4]}"
    datum_en = f"{d[8:10]} {('January February March April May June July August September October November December').split()[int(d[5:7]) - 1]} {d[0:4]}"
    alt = _tage_alt(d, heute_s if heute_s is not None else time.time())
    hinweis_de = f"EZB-Referenzkurs vom {datum_de}, dein Bankkurs kann abweichen"
    hinweis_en = f"ECB reference rate of {datum_en}; your bank's rate may differ"
    if alt > 5:
        hinweis_de += f" (der Kurs ist {alt} Tage alt, die EZB war gerade nicht erreichbar)"
        hinweis_en += f" (the rate is {alt} days old, the ECB could not be reached just now)"

    def kurs(von: str, nach: str) -> Fraction:
        return kurse.tabelle[nach] / kurse.tabelle[von]

    if f.betrag is None:
        z = f.nach[0]
        k = kurs(f.von, z)
        return Ergebnis(f"1 {_name(f.von, False)} = {_kursformat(k)} {_name(z, False)} ({hinweis_de}).", f"1 {_name(f.von, True)} = {_kursformat(k, True)} {_name(z, True)} ({hinweis_en}).")
    quelle_de = f"{zahl_text(f.betrag)} {_name(f.von, False)}"
    quelle_en = f"{zahl_text(f.betrag, True)} {_name(f.von, True)}"
    zeilen_de = [f"{_betrag(f.betrag * kurs(f.von, z), z, False)} {_name(z, False)}" for z in f.nach]
    zeilen_en = [f"{_betrag(f.betrag * kurs(f.von, z), z, True)} {_name(z, True)}" for z in f.nach]
    k1 = f.nach[0]
    wege_de = f"1 {_name(f.von, False)} = {_kursformat(kurs(f.von, k1))} {_name(k1, False)}"
    wege_en = f"1 {_name(f.von, True)} = {_kursformat(kurs(f.von, k1), True)} {_name(k1, True)}"
    if len(f.nach) == 1:
        return Ergebnis(f"{quelle_de} sind rund {zeilen_de[0]} ({hinweis_de}; {wege_de}).", f"{quelle_en} is about {zeilen_en[0]} ({hinweis_en}; {wege_en}).")
    return Ergebnis(f"{quelle_de} sind rund:\n" + "\n".join("– " + z for z in zeilen_de) + f"\n({hinweis_de}.)",
                    f"{quelle_en} is about:\n" + "\n".join("– " + z for z in zeilen_en) + f"\n({hinweis_en}.)")


def _kursformat(k: Fraction, en: bool = False) -> str:
    stellen = 4 if k >= 1 else 6
    t = zahl_text(Fraction(round(k * 10 ** stellen), 10 ** stellen), en)
    return t


def frage_beantworten(text: str, oeffner=None) -> Ergebnis | None:
    f = erkennen(text)
    if f is None:
        return None
    k = holen(oeffner=oeffner)
    return antwort(f, k) if k is not None else None
