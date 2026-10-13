# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from fractions import Fraction

from rechnen import Ergebnis, _Nein, geld_text, glatt, waehrung, zahl_lesen, zahl_mit_rund, zahl_text

NUM = r"\d+(?:[.,]\d+)*"
EUR = r"(?:€|euro|eur)"
KEST_SPARBUCH = Fraction(25, 100)
MAX_JAHRE = 100
MAX_MONATE = 1200

_ERLAUBT = set("""wie viel viele wird werden ist sind aus was ergibt macht nach bei zu zum zur auf für mit von dem den der die das ein eine einer einem im in über und oder ca circa etwa wenn ich man habe
hab lege an anlegen angelegt sparen spare sparbuch zinsen zins zinseszins verzinst verzinsung jährlich jährliche jährlichen pro p a jahr jahre jahren monat monate monaten euro eur kredit darlehen rate
monatlich monatsrate monatliche kostet kosten zahle zahlen bezahle laufzeit tilgung finanzierung hypothek wohnbaukredit konto guthaben endkapital kapital anfangskapital betrag brauche bekomme bekommt
muss müsste soll einzahlen einzahle zurücklegen lege zurück wann verdoppeln verdoppelt verdoppelt sich es dann am ende gesamt insgesamt zusammen berechne rechne aus bitte mir uns kann könnte unser
how much will become after at for with years year months month interest compound rate loan mortgage monthly payment per annual saving invest invested of the a an is my i double doubles does long
take takes when would be if put save paid pay total calculate zinssatz zinsen
on over what whats it its that this then get got have has can could should shall will am are was were do did to from into by as up out off down so than about around roughly approximately
account savings bank apr annually yearly compounded compounding finance financing borrow borrowed lend my our your me us each every once twice""".split())


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 220 or not re.search(r"\d", t):
        return None
    for stufe in (_posten, _sprit, _trinkgeld, _kredit, _sparplan, _verdoppeln, _zins):
        r = stufe(t)
        if r is not None:
            return glatt(r, t)
    return None


def _nimm(t: str, muster: str) -> tuple[list[re.Match], str]:
    treffer = list(re.finditer(muster, t, re.I))
    rest = t
    for m in reversed(treffer):
        rest = rest[:m.start()] + " " + rest[m.end():]
    return treffer, rest


def _nur_fuell(rest: str, extra: set[str] | frozenset[str] = frozenset(), orte: int = 0) -> bool:
    if re.search(r"\d", rest):
        return False
    unbekannt = []
    for w in re.findall(r"[A-Za-zÄÖÜäöüß']+", rest):
        if w.lower() in _ERLAUBT or w.lower() in extra:
            continue
        unbekannt.append(w)
    namen = [w for w in unbekannt if w[0].isupper()]
    return len(unbekannt) == len(namen) <= orte


def _betrag(s: str) -> Fraction:
    return zahl_lesen(s)


def _g(x: Fraction, en: bool = False) -> str:
    return geld_text(x, en)


def _prozent_text(p: Fraction, en: bool = False) -> str:
    return zahl_text(p, en)


def _jahre_monate(treffer: list[re.Match]) -> int:
    if len(treffer) != 1:
        raise _Nein
    n = int(treffer[0].group("n"))
    monate = n * 12 if treffer[0].group("e").lower().startswith(("j", "y")) else n
    if not 1 <= monate <= MAX_MONATE:
        raise _Nein
    return monate


_DAUER = r"(?P<n>\d+)\s*(?P<e>jahre?n?|years?|monate?n?|months?)(?![a-zäöü])"
_PROZ = rf"(?P<p>{NUM})\s*(?:%|prozent|percent)"
_GELD = rf"(?:(?P<b1>{NUM})\s*{EUR}|€\s*(?P<b2>{NUM}))"


def _geld_wert(m: re.Match) -> Fraction:
    gruppen = m.groupdict()
    return _betrag(gruppen.get("b1") or gruppen.get("b2") or m.group(0))


def _grunddaten(t: str):
    g, rest = _nimm(t, _GELD)
    p, rest = _nimm(rest, _PROZ)
    d, rest = _nimm(rest, _DAUER)
    if len(g) != 1 or len(p) != 1:
        raise _Nein
    return _geld_wert(g[0]), zahl_lesen(p[0].group("p")) / 100, _jahre_monate(d), rest


def _jahre_text(monate: int, en: bool = False, akk: bool = False) -> str:
    j, m = divmod(monate, 12)
    teile = []
    if j:
        teile.append(f"{j} {'year' if j == 1 else 'years'}" if en else f"{j} {'Jahr' if j == 1 else ('Jahre' if akk else 'Jahren')}")
    if m:
        teile.append(f"{m} {'month' if m == 1 else 'months'}" if en else f"{m} {'Monat' if m == 1 else ('Monate' if akk else 'Monaten')}")
    return (" and " if en else " und ").join(teile)


def _zins(t: str) -> Ergebnis | None:
    if not re.search(r"zins|verzins|sparbuch|angelegt|anlegen|interest|invest", t, re.I) \
            and not re.search(rf"(?:€|euro|eur)\s*(?:zu|bei|mit|à|at)\s*{NUM}\s*(?:%|prozent|percent)\s*(?:auf|für|fuer|über|ueber|nach|in|for)\s*\d+\s*(?:jahre?n?|monate?n?|years?|months?)\b", t, re.I):
        return None
    if re.search(r"monatlich|rate|kredit|darlehen|verdoppel|per\s+month|monthly", t, re.I):
        return None
    try:
        k, p, monate, rest = _grunddaten(t)
    except _Nein:
        return None
    if not _nur_fuell(rest) or k <= 0 or p < 0 or p > 1:
        return None
    mit_zz = bool(re.search(r"zinseszins|compound", t, re.I))
    jahre, restm = divmod(monate, 12)
    pz = zahl_text(p * 100)
    pz_en = zahl_text(p * 100, True)
    if monate < 12:
        zinsen = k * p * monate / 12
        end = k + zinsen
        return Ergebnis(f"{_g(k)} zu {pz} % Zinsen im Jahr bringen in {_jahre_text(monate)} {_g(zinsen)} Zinsen, zusammen {_g(end)}. Rechnung: {_g(k)} × {pz} % × {monate}/12 = {_g(zinsen)}.",
                        f"{_g(k, True)} at {pz_en}% interest per year earns {_g(zinsen, True)} in {_jahre_text(monate, True)}, {_g(end, True)} in total. Working: {_g(k, True)} × {pz_en}% × {monate}/12 = {_g(zinsen, True)}.")
    if restm:
        return None
    stand = k
    zeilen_de, zeilen_en = [], []
    for j in range(1, jahre + 1):
        stand = stand * (1 + p)
        zeilen_de.append(f"Jahr {j}: {_g(stand)}")
        zeilen_en.append(f"Year {j}: {_g(stand, True)}")
    end = stand
    zinsen = end - k
    einfach = k * (1 + p * jahre)
    if len(zeilen_de) > 12:
        zeilen_de = zeilen_de[:3] + ["…"] + zeilen_de[-2:]
        zeilen_en = zeilen_en[:3] + ["…"] + zeilen_en[-2:]
    netto = k * (1 + p * (1 - KEST_SPARBUCH)) ** jahre
    de = (f"{_g(k)} zu {pz} % Zinsen im Jahr werden nach {_jahre_text(monate)} zu {_g(end)}. Das sind {_g(zinsen)} Zinsen mit Zinseszins (die Zinsen werden jedes Jahr mitverzinst).\n"
          f"Rechnung: {_g(k)} × (1 + {pz} %)^{jahre} = {_g(end)}.\n" + "\n".join(zeilen_de))
    en = (f"{_g(k, True)} at {pz_en}% interest per year becomes {_g(end, True)} after {_jahre_text(monate, True)}. That is {_g(zinsen, True)} of interest with compounding (interest earns interest each year).\n"
          f"Working: {_g(k, True)} × (1 + {pz_en}%)^{jahre} = {_g(end, True)}.\n" + "\n".join(zeilen_en))
    if not mit_zz and jahre > 1:
        de += f"\nOhne Zinseszins (Zinsen werden nicht mitverzinst) wären es nur {_g(einfach)}."
        en += f"\nWithout compounding (interest not earning interest) it would only be {_g(einfach, True)}."
    de += (f"\nNach {zahl_text(KEST_SPARBUCH * 100)} % KESt (Sparbuch und Konto in Österreich, jedes Jahr abgezogen) bleiben {_g(netto)}. Gerechnet ohne Gebühren und mit gleichbleibendem Zinssatz.")
    en += (f"\nAfter {zahl_text(KEST_SPARBUCH * 100, True)}% Austrian withholding tax (savings accounts, deducted each year) {_g(netto, True)} is left. Calculated without fees and with a constant rate.")
    return Ergebnis(de, en)


def _kredit(t: str) -> Ergebnis | None:
    if not re.search(r"\brate\b|kredit|darlehen|hypothek|finanzier|tilgung|loan|mortgage|monthly\s+payment", t, re.I):
        return None
    try:
        k, p, monate, rest = _grunddaten(t)
    except _Nein:
        return None
    if not _nur_fuell(rest) or k <= 0 or p < 0 or p > 1:
        return None
    r = p / 12
    n = monate
    rate = k / n if r == 0 else k * r / (1 - (1 + r) ** (-n))
    gesamt = rate * n
    pz, pz_en = zahl_text(p * 100), zahl_text(p * 100, True)
    de = (f"Monatliche Rate: {_g(rate)}. Bei {_g(k)} zu {pz} % im Jahr über {_jahre_text(monate, False, True)} ({n} Monate) zahlst du insgesamt {_g(gesamt)} zurück, davon {_g(gesamt - k)} Zinsen.\n"
          f"Rechnung: Rate = Kredit × Monatszins ÷ (1 - (1 + Monatszins)^-{n}), mit Monatszins = {pz} % ÷ 12. "
          f"Gerechnet mit gleichbleibender Rate und dem Jahreszins geteilt durch 12, ohne Gebühren und Spesen; deine Bank kann leicht abweichen.")
    en = (f"Monthly payment: {_g(rate, True)}. For {_g(k, True)} at {pz_en}% per year over {_jahre_text(monate, True)} ({n} months) you repay {_g(gesamt, True)} in total, of which {_g(gesamt - k, True)} is interest.\n"
          f"Working: payment = loan × monthly rate ÷ (1 - (1 + monthly rate)^-{n}), with monthly rate = {pz_en}% ÷ 12. "
          f"Calculated with a constant payment and the yearly rate divided by 12, without fees; your bank may differ slightly.")
    return Ergebnis(de, en)


def _sparplan(t: str) -> Ergebnis | None:
    if not re.search(r"monatlich|jeden\s+monat|pro\s+monat|im\s+monat|per\s+month|monthly|every\s+month", t, re.I) or re.search(r"\brate\b|kredit|darlehen|loan|mortgage", t, re.I):
        return None
    if not re.search(r"spar|zurücklegen|zurueckleg|einzahl|anleg|invest|sav(?:e|ing)|deposit|put\s+away|contribut", t, re.I):
        return None
    try:
        b, p, monate, rest = _grunddaten(t)
    except _Nein:
        return None
    if not _nur_fuell(rest, {"jeden", "jedem", "pro", "im", "monat", "monatlich", "every", "month", "deposit", "per", "ein", "einzahlen", "lege", "zurück", "spar"}) or b <= 0 or p < 0 or p > 1:
        return None
    r = p / 12
    n = monate
    end = b * n if r == 0 else b * ((1 + r) ** n - 1) / r
    eingezahlt = b * n
    pz, pz_en = zahl_text(p * 100), zahl_text(p * 100, True)
    de = (f"Wer {n // 12 if n % 12 == 0 else n} {'Jahre' if n % 12 == 0 else 'Monate'} lang jeden Monat {_g(b)} zu {pz} % im Jahr spart, hat am Ende {_g(end)}. "
          f"Eingezahlt sind das {_g(eingezahlt)}, die Zinsen machen {_g(end - eingezahlt)} aus.\n"
          f"Gerechnet: Einzahlung am Ende jedes Monats, Monatszins = {pz} % ÷ 12, Endwert = Rate × ((1 + Monatszins)^{n} - 1) ÷ Monatszins; ohne Steuer und Gebühren.")
    en = (f"Saving {_g(b, True)} every month at {pz_en}% per year for {n // 12 if n % 12 == 0 else n} {'years' if n % 12 == 0 else 'months'} gives {_g(end, True)} at the end. "
          f"You paid in {_g(eingezahlt, True)}, the interest is {_g(end - eingezahlt, True)}.\n"
          f"Calculated with a deposit at the end of each month, monthly rate = {pz_en}% ÷ 12, final value = deposit × ((1 + monthly rate)^{n} - 1) ÷ monthly rate; without tax or fees.")
    return Ergebnis(de, en)


def _verdoppeln(t: str) -> Ergebnis | None:
    if not re.search(r"verdoppel|double", t, re.I):
        return None
    g, rest = _nimm(t, _GELD)
    p, rest = _nimm(rest, _PROZ)
    if len(p) != 1 or len(g) > 1 or not _nur_fuell(rest, {"verdoppeln", "verdoppelt", "sich", "double", "doubles", "wann", "dauert", "es", "lange", "how", "long", "does", "take", "to", "my", "money", "until", "till", "will", "it", "savings", "investment", "get", "twice", "as", "big", "years", "year", "double", "in", "if", "i", "earn", "at", "a", "rate", "of", "interest", "when", "can", "the"}):
        return None
    pr = zahl_lesen(p[0].group("p")) / 100
    if not 0 < pr <= 10:
        return None
    jahre = math.log(2) / math.log(1 + float(pr))
    ganz = math.ceil(jahre - 1e-12)
    faust = Fraction(72) / (pr * 100)
    wer_de = f"{_g(_geld_wert(g[0]))} verdoppeln sich" if g else "Das Geld verdoppelt sich"
    wer_en = f"{_g(_geld_wert(g[0]), True)} doubles" if g else "Money doubles"
    j = Fraction(round(jahre * 100), 100)
    pz, pz_en = zahl_text(pr * 100), zahl_text(pr * 100, True)
    return Ergebnis(f"{wer_de} bei {pz} % Zinsen im Jahr (mit Zinseszins) nach rund {zahl_text(j)} Jahren, also im {ganz}. Jahr. Faustregel: 72 ÷ {pz} = rund {zahl_text(Fraction(round(faust * 10), 10))} Jahre.",
                    f"{wer_en} at {pz_en}% interest per year (compounded) after about {zahl_text(j, True)} years, so during year {ganz}. Rule of thumb: 72 ÷ {pz_en} = about {zahl_text(Fraction(round(faust * 10), 10), True)} years.")


_ZAHLWORT = {"ein": 1, "eine": 1, "einen": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "zwölf": 12, "zwoelf": 12,
             "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "dozen": 12}
_MENGE = "|".join(_ZAHLWORT)
_EINHEIT = r"(?:kg|kilo|kilogramm|kilos|kilograms?|g|gramm|grams?|dag|l|liter|litres?|liters?|ml|lbs?|pounds?|oz|ounces?|stück|stk\.?|packungen?|flaschen?|dosen?|tüten?|becher|bund|stangen?|pieces?|packs?|bottles?|cans?|bags?|boxes)"
_WORT = r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]*"
_POSTEN = (rf"(?:(?P<q>{NUM}|{_MENGE})\s+(?:(?P<u>{_EINHEIT})\s+)?)?(?P<d>{_WORT}(?:\s+(?!zu\b|à\b|je\b|für\b|kostet\b|kosten\b|und\b|at\b|for\b|each\b|costs?\b|and\b){_WORT}){{0,2}})\s+"
           rf"(?:zu(?:\s+je)?|à|je|für|kostet|kosten|a(?=\s+\d)|at|@|for|costs?|priced\s+at)\s+(?P<p>{NUM})\s*{EUR}"
           rf"(?:\s+(?:pro|das|der|die|je|per|a|each|the)\s+(?P<pu>kilo|kg|liter|litre|l|stück|stk|packung|flasche|dose|dag|g|gramm|pound|lb|piece|bottle|can|dozen|pack|each))?")
_BEZAHLT = (rf"(?:ich\s+)?(?:zahle|bezahle|gebe|gebe\s+dem\s+kassier\w*|hab|habe)\s+(?:mit\s+|ihm\s+|ihr\s+)?(?:einen?\s+)?(?P<b>{NUM})\s*(?:{EUR})?(?:\s*-?\s*(?:schein|note))?"
            rf"|(?:i\s+)?(?:pay|paid|give|gave|hand|handed|tender)(?:\s+(?:the\s+cashier|him|her|them))?\s+(?:with\s+)?(?:a\s+|an\s+)?(?P<b2>{NUM})\s*(?:{EUR})?(?:\s*-?\s*(?:bill|note))?")
_RABATT = rf"(?:mit\s+|bei\s+|und\s+|with\s+|and\s+|after\s+|less\s+)?(?P<r>{NUM})\s*(?:%|prozent|percent)\s*(?:rabatt|nachlass|ermäßigung|discount|off)(?:\s+(?:auf\s+(?:alles|den\s+einkauf)|on\s+everything|off\s+everything))?"


_POSTEN_OHNE = rf"(?P<d>{_WORT})\s+(?P<p>{NUM})\s*{EUR}"


def _posten(t: str) -> Ergebnis | None:
    bez = re.search(_BEZAHLT, t, re.I)
    rest = t if not bez else t[:bez.start()] + " " + t[bez.end():]
    rab = re.search(_RABATT, rest, re.I)
    if rab:
        rest = rest[:rab.start()] + " " + rest[rab.end():]
    posten = list(re.finditer(_POSTEN, rest, re.I))
    if not posten:
        posten = list(re.finditer(_POSTEN_OHNE, rest, re.I))
        if len(posten) < 2:
            return None
    for m in reversed(posten):
        rest = rest[:m.start()] + " " + rest[m.end():]
    if len(posten) < 2 and not bez:
        return None
    extra = {"und", "sowie", "plus", "dazu", "außerdem", "ausserdem", "kaufe", "kaufen", "kaufte", "gekauft", "nehme", "nehmen", "bekomme", "einkauf", "rückgeld", "rueckgeld", "wechselgeld",
             "kassa", "kasse", "kassier", "kassiererin", "gesamt", "gesamtsumme", "summe", "dann", "bezahlt", "schein", "ich", "mit", "einem", "einer", "einen", "alles", "das", "insgesamt",
             "wieviel", "wie", "viel", "kostet", "kosten", "bekomm", "krieg", "kriege", "zurück", "zurueck", "zahlen", "zahle", "bezahle", "gesamtpreis", "preis", "den", "beim", "bäcker",
             "supermarkt", "hofer", "billa", "spar", "merkur", "lidl", "markt", "bei", "heute", "habe", "hab", "mir", "ist", "sind", "bleibt", "übrig", "uebrig", "macht", "ergibt",
             "i", "bought", "buy", "buying", "get", "got", "pay", "paid", "with", "how", "much", "change", "total", "cost", "costs", "does", "do", "it", "that", "all", "what", "is", "my", "the",
             "will", "would", "back", "get", "store", "shop", "grocery", "groceries", "and", "plus", "also", "then", "left", "over", "me", "cashier", "bill", "tax", "before", "after"}
    if not _nur_fuell(rest, extra):
        return None
    zeilen_de, zeilen_en = [], []
    summe = Fraction(0)
    for m in posten:
        q = m.groupdict().get("q")
        menge = Fraction(_ZAHLWORT[q.lower()]) if q and q.lower() in _ZAHLWORT else (zahl_lesen(q) if q else Fraction(1))
        if menge <= 0 or menge > 10 ** 6:
            return None
        preis = zahl_lesen(m.group("p"))
        einheit = m.groupdict().get("u") or ""
        d = m.group("d").strip()
        if d.lower() in ("mal", "x", "euro", "eur"):
            return None
        betrag = menge * preis
        summe += betrag
        mt = zahl_text(menge)
        mt_en = zahl_text(menge, True)
        pro = m.groupdict().get("pu")
        name = f"{mt} {einheit + ' ' if einheit else ''}{d}".replace("  ", " ")
        name_en = f"{mt_en} {einheit + ' ' if einheit else ''}{d}".replace("  ", " ")
        if q is None:
            name, name_en = d, d
        zeilen_de.append(f"{name} zu {_g(preis)}{' pro ' + pro if pro else ''}: {mt} × {_g(preis)} = {_g(betrag)}" if q else f"{name} zu {_g(preis)}: {_g(betrag)}")
        zeilen_en.append(f"{name_en} at {_g(preis, True)}{' per ' + pro if pro else ''}: {mt_en} × {_g(preis, True)} = {_g(betrag, True)}" if q else f"{name_en} at {_g(preis, True)}: {_g(betrag, True)}")
    de = "Einkauf:\n" + "\n".join(zeilen_de)
    en = "Shopping:\n" + "\n".join(zeilen_en)
    if len(posten) > 1:
        de += f"\nZusammen: {_g(summe)}"
        en += f"\nTotal: {_g(summe, True)}"
    if rab:
        proz = zahl_lesen(rab.group("r"))
        if not 0 < proz < 100:
            return None
        abzug = summe * proz / 100
        summe -= abzug
        de += f"\nAbzüglich {zahl_text(proz)} % Rabatt (-{_g(abzug)}): {_g(summe)}"
        en += f"\nLess {zahl_text(proz, True)}% discount (-{_g(abzug, True)}): {_g(summe, True)}"
    if bez:
        gegeben = zahl_lesen(bez.group("b") or bez.group("b2"))
        rueck = gegeben - summe
        de += f"\nBezahlt mit {_g(gegeben)}: " + (f"Rückgeld {_g(rueck)}" if rueck >= 0 else f"Es fehlen noch {_g(-rueck)}")
        en += f"\nPaid with {_g(gegeben, True)}: " + (f"change {_g(rueck, True)}" if rueck >= 0 else f"{_g(-rueck, True)} still missing")
    return Ergebnis(de, en)


def _r2(x: Fraction, en: bool = False) -> str:
    y = Fraction(math.floor(x * 100 + Fraction(1, 2)), 100)
    t = zahl_text(y, en)
    return t if y == x else (("about " if en else "rund ") + t)


_UK_GAL, _US_GAL, _MEILE = Fraction("4.54609"), Fraction("3.785411784"), Fraction("1.609344")


def _sprit(t: str) -> Ergebnis | None:
    s = re.sub(r"\bmiles?\s+per\s+(?:us\s+|imperial\s+|uk\s+)?gallons?\b|\bmi/gal\b", "mpg", t, flags=re.I)
    verbrauch, rest = _nimm(s, rf"(?P<v>{NUM})\s*(?P<e>mpg|kwh\s*(?:/|per|pro|auf|je)\s*100\s*(?:km|kilomet(?:er|re)s?)|(?:l|liters?|litres?)\s*(?:/|per|pro|auf|je)\s*100\s*(?:km|kilomet(?:er|re)s?)|km\s*/\s*l\b|km\s+per\s+lit(?:er|re))")
    dist, rest = _nimm(rest, rf"(?<![\d/])(?P<d>{NUM})\s*(?P<du>km|kilomet(?:er|re)s?|miles?|mi)(?![a-zäöü])(?!\s*/\s*h\b)(?!\s+per\s+hour)")
    preis, rest = _nimm(rest, rf"(?P<p>{NUM})\s*{EUR}\s*(?:/|per|pro|je|das|der|a|each|the)\s*(?P<pe>kwh|l\b|liters?|litres?|gallons?|gal\b)")
    if len(dist) != 1 or len(verbrauch) != 1 or len(preis) != 1:
        return None
    hin_zurueck, rest = _nimm(rest, r"hin\s*(?:und|&|-)?\s*(?:zurück|zurueck|retour|rück)\w*|retour|round\s*trip|and\s+back|return(?:\s+trip)?|there\s+and\s+back")
    art = verbrauch[0].group("e").lower().replace(" ", "")
    kind = "mpg" if art == "mpg" else "kwh" if art.startswith("kwh") else "kml" if art.startswith("km") else "l100"
    pe = preis[0].group("pe").lower()
    preis_art = "kwh" if pe == "kwh" else "gal" if pe.startswith("gal") else "l"
    if (kind == "kwh") != (preis_art == "kwh"):
        return None
    extra = {"fahrt", "strecke", "spritkosten", "sprit", "benzin", "diesel", "tanken", "tank", "fahren", "verbrauch", "reise", "kostet", "kosten", "liter", "kilometer", "auto", "stromkosten",
             "strom", "laden", "mein", "meine", "bei", "hin", "zurück", "trip", "drive", "driving", "cost", "costs", "does", "what", "the", "of", "a", "km", "ev", "elektroauto", "tour", "wie", "viel",
             "was", "die", "der", "das", "ein", "eine", "und", "von", "nach", "für", "mit", "ca", "circa", "etwa", "ist", "sind", "wird", "werden", "how", "much", "would", "it", "will", "gas",
             "gasoline", "petrol", "fuel", "miles", "mile", "car", "my", "gets", "get", "at", "and", "back", "round", "there", "to", "is", "fill", "up", "tank", "my", "i", "if", "for", "on",
             "price", "per", "gallon", "litre", "liter", "tesla", "electric", "charging", "charge", "cheaper", "total", "journey", "road", "from", "in", "this", "that", "mileage", "efficiency"}
    if not _nur_fuell(rest, extra, orte=4):
        return None
    meilen = dist[0].group("du").lower().startswith("mi")
    d = zahl_lesen(dist[0].group("d"))
    if hin_zurueck:
        d *= 2
    v = zahl_lesen(verbrauch[0].group("v"))
    if v <= 0 or d <= 0:
        return None
    uk = bool(re.search(r"£|\buk\b|imperial|british|britain", t, re.I)) or waehrung() == "£"
    gal = _UK_GAL if uk else _US_GAL
    km = d * (_MEILE if meilen else 1)
    l100 = {"mpg": 100 * gal / _MEILE / v, "l100": v, "kwh": v, "kml": 100 / v}[kind]
    menge = km * l100 / 100
    p = zahl_lesen(preis[0].group("p"))
    je_einheit = p / gal if preis_art == "gal" else p
    kosten = menge * je_einheit
    pro_km = kosten / km
    imperial = meilen or kind == "mpg" or preis_art == "gal"
    ev = kind == "kwh"
    gal_name = ("UK gallons", "britische Gallonen") if uk else ("gallons", "Gallonen")
    if imperial and not ev:
        gallonen = menge / gal
        de = (f"Die Fahrt über {zahl_text(d)} {'Meilen' if meilen else 'km'}{' (hin und zurück)' if hin_zurueck else ''} braucht {_r2(gallonen)} {gal_name[1]} und kostet {_g(kosten)}. "
              f"Rechnung: {zahl_text(d)} {'Meilen' if meilen else 'km'} ÷ {zahl_mit_rund(Fraction(100) * gal / _MEILE / l100) if kind != 'mpg' else zahl_text(v)} mpg = {_r2(gallonen)} {gal_name[1]}; "
              f"× {_g(p)} je Gallone = {_g(kosten)}. Zum Vergleich in Metrik: {_r2(menge)} Liter für {_r2(km)} km.")
        en = (f"The {zahl_text(d, True)} {'mile' if meilen else 'km'} trip{' (round trip)' if hin_zurueck else ''} uses {_r2(gallonen, True)} {gal_name[0]} and costs {_g(kosten, True)}. "
              f"Working: {zahl_text(d, True)} {'miles' if meilen else 'km'} ÷ {zahl_mit_rund(Fraction(100) * gal / _MEILE / l100, True) if kind != 'mpg' else zahl_text(v, True)} mpg = {_r2(gallonen, True)} {gal_name[0]}; "
              f"× {_g(p, True)} per gallon = {_g(kosten, True)}. In metric: {_r2(menge, True)} litres for {_r2(km, True)} km.")
        if kind != "mpg" and preis_art != "gal":
            pass
        return Ergebnis(de, en)
    einheit, einheit_en = ("kWh", "kWh") if ev else ("Liter", "litres")
    de = (f"Die Fahrt über {zahl_text(d)} {'Meilen' if meilen else 'km'}{' (hin und zurück)' if hin_zurueck else ''} braucht {zahl_mit_rund(menge)} {einheit} und kostet {_g(kosten)}. "
          f"Rechnung: {zahl_text(km)} km × {zahl_mit_rund(l100)} {einheit} ÷ 100 = {zahl_mit_rund(menge)} {einheit}; × {_g(je_einheit)} = {_g(kosten)}. "
          f"Das sind {zahl_text(Fraction(math.floor(pro_km * 10000 + Fraction(1, 2)), 100))} Cent je Kilometer.")
    en = (f"The {zahl_text(d, True)} {'mile' if meilen else 'km'} trip{' (there and back)' if hin_zurueck else ''} uses {zahl_mit_rund(menge, True)} {einheit_en} and costs {_g(kosten, True)}. "
          f"Working: {zahl_text(km, True)} km × {zahl_mit_rund(l100, True)} {einheit_en} ÷ 100 = {zahl_mit_rund(menge, True)} {einheit_en}; × {_g(je_einheit, True)} = {_g(kosten, True)}. "
          f"That is {zahl_text(Fraction(math.floor(pro_km * 10000 + Fraction(1, 2)), 100), True)} cents per kilometre.")
    return Ergebnis(de, en)


def _trinkgeld(t: str) -> Ergebnis | None:
    if not re.search(r"trinkgeld|tip\b|tipping|gratuity|aufteilen|teilen|geteilt|pro\s+person|je\s+person|jede[rn]?\s+zahlt|split|each|rechnung|bill|check\b", t, re.I):
        return None
    g, rest = _nimm(t, _GELD)
    if not g:
        g, rest = _nimm(t, rf"(?:rechnung|bill|check|total|gesamtbetrag)\s*(?:of|von|:|is|ist|=)?\s*(?P<b1>{NUM})")
    tip, rest = _nimm(rest, rf"(?:(?P<p1>{NUM})\s*(?:%|prozent|percent)\s*(?:trinkgeld|tip|gratuity|bedienung|service)|(?:trinkgeld|tip|gratuity)\s*(?:von|of|:|at)?\s*(?P<p2>{NUM})\s*(?:%|prozent|percent))")
    pers, rest = _nimm(rest, r"(?:(?:auf|durch|unter|für|fuer|for|between|among|among\s+us)\s+(?P<n1>\d+)\s*(?:personen|leute|leuten|freunde|freunden|gäste|gästen|köpfe|köpfen|people|persons|friends|ways)?|(?P<n2>\d+)\s*(?:personen|leute|leuten|freunde|freunden|gäste|gästen|köpfe|köpfen|people|persons|friends|ways))")
    if not g and (tip or re.search(r"\bsplit\b|\bbetween\b|\beach\b", t, re.I)) and pers is not None:
        g, rest = _nimm(rest, rf"(?<![\w.,]){NUM}(?![\w])")
    if len(g) != 1 or len(tip) > 1 or len(pers) > 1 or (not tip and not pers):
        return None
    aufrunden, rest = _nimm(rest, r"(?:auf\s+(?:volle|ganze|den\s+nächsten)\s*(?:euro|eur)?\s*)?(?:aufrunden|aufgerundet|round\s+up|rounded\s+up)(?:\s+auf\s+(?:volle|ganze)\s*(?:euro|eur)?)?|auf\s+(?:volle|ganze)\s*(?:euro|eur)\s*aufrunden")
    extra = {"rechnung", "trinkgeld", "personen", "person", "pro", "je", "jede", "jeder", "zahlt", "teilen", "aufteilen", "geteilt", "tip", "bill", "split", "each", "people", "pay", "beträgt", "betrug",
             "gesamt", "gesamtbetrag", "restaurant", "essen", "lokal", "wirt", "kellner", "bedienung", "lokalrechnung", "und", "von", "wir", "sind", "waren", "mit", "inkl", "plus", "das", "die", "der",
             "wie", "viel", "was", "kostet", "zahlen", "zahle", "einer", "einzeln", "gleichmäßig", "gleichmaessig", "gerecht", "aufrunden", "volle", "ganze", "freunde", "gäste", "leute", "teile", "teilt",
             "wollen", "wir", "ihr", "alle", "zu", "gleichen", "teilen", "ca", "circa", "etwa", "bei", "ein", "eine", "euro", "eur", "köpfe", "an", "tischen", "tisch",
             "what", "is", "on", "a", "an", "of", "if", "i", "we", "should", "leave", "how", "much", "total", "with", "each", "person", "pays", "pay", "per", "evenly", "equally", "dinner",
             "lunch", "meal", "check", "waiter", "waitress", "service", "gratuity", "tipping", "my", "our", "the", "was", "were", "and", "between", "among", "split", "ways", "way",
             "round", "up", "does", "it", "come", "to", "out", "that", "this"}
    if not _nur_fuell(rest, extra):
        return None
    betrag = _geld_wert(g[0])
    if betrag <= 0 or betrag > 10 ** 9:
        return None
    n = 1
    if pers:
        n = int(pers[0].group("n1") or pers[0].group("n2"))
        if not 1 <= n <= 1000:
            return None
    p = Fraction(0)
    if tip:
        p = zahl_lesen(tip[0].group("p1") or tip[0].group("p2"))
        if not 0 <= p <= 100:
            return None
    trinkgeld = betrag * p / 100
    gesamt = betrag + trinkgeld
    zeilen_de, zeilen_en = [], []
    if tip:
        zeilen_de.append(f"Trinkgeld {zahl_text(p)} % von {_g(betrag)}: {_g(trinkgeld)}")
        zeilen_en.append(f"Tip {zahl_text(p, True)}% of {_g(betrag, True)}: {_g(trinkgeld, True)}")
        zeilen_de.append(f"Gesamt: {_g(betrag)} + {_g(trinkgeld)} = {_g(gesamt)}")
        zeilen_en.append(f"Total: {_g(betrag, True)} + {_g(trinkgeld, True)} = {_g(gesamt, True)}")
    if n > 1:
        if aufrunden:
            je = Fraction(math.ceil(gesamt / n))
            summe = je * n
            zeilen_de.append(f"Aufgerundet auf volle Euro zahlt jede der {n} Personen {_g(je)}. Zusammen sind das {_g(summe)}, also {_g(summe - betrag)} Trinkgeld.")
            zeilen_en.append(f"Rounded up to whole euros each of the {n} people pays {_g(je, True)}. Together that is {_g(summe, True)}, i.e. {_g(summe - betrag, True)} tip.")
        else:
            cent = math.floor(gesamt * 100 + Fraction(1, 2))
            je, rest_c = divmod(cent, n)
            if rest_c == 0:
                zeilen_de.append(f"Auf {n} Personen geteilt zahlt jede Person {_g(Fraction(je, 100))}.")
                zeilen_en.append(f"Split between {n} people, each person pays {_g(Fraction(je, 100), True)}.")
            else:
                zeilen_de.append(f"Auf {n} Personen geteilt sind es {_g(Fraction(je, 100))} je Person, {rest_c} Cent bleiben übrig (eine Person kann {rest_c} Cent mehr zahlen).")
                zeilen_en.append(f"Split between {n} people it is {_g(Fraction(je, 100), True)} each, {rest_c} cent is left over (one person can pay {rest_c} cent more).")
    return Ergebnis("\n".join(zeilen_de), "\n".join(zeilen_en))
