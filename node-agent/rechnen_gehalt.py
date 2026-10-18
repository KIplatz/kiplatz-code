# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from fractions import Fraction

from rechnen import Ergebnis, _Nein, geld_text, glatt, zahl_lesen

GUELTIG_JAHR = 2026
WERTE = {
    "kv": Fraction(387, 10000), "pv": Fraction(1025, 10000), "ak": Fraction(5, 1000), "wbf": Fraction(5, 1000),
    "av": [(Fraction(2225), Fraction(0)), (Fraction(2427), Fraction(1, 100)), (Fraction(2630), Fraction(2, 100))], "av_voll": Fraction(295, 10000),
    "hoechstbeitrag": Fraction(6930),
    "tarif": [(Fraction(13539), Fraction(0)), (Fraction(21992), Fraction(20, 100)), (Fraction(36458), Fraction(30, 100)), (Fraction(70365), Fraction(40, 100)),
              (Fraction(104859), Fraction(48, 100)), (Fraction(1000000), Fraction(50, 100))], "tarif_oben": Fraction(55, 100),
    "verkehrsabsetzbetrag": Fraction(496), "werbungskosten": Fraction(132),
    "sonder_freibetrag": Fraction(620), "sonder_satz": Fraction(6, 100),
}
GRENZE_VON, GRENZE_BIS = Fraction(1000), Fraction(20000)


def _cent(x: Fraction) -> Fraction:
    return Fraction(math.floor(x * 100 + Fraction(1, 2)), 100)


def _av(brutto: Fraction) -> Fraction:
    for grenze, satz in WERTE["av"]:
        if brutto <= grenze:
            return satz
    return WERTE["av_voll"]


def sv_laufend(brutto: Fraction) -> Fraction:
    grundlage = min(brutto, WERTE["hoechstbeitrag"])
    return _cent(grundlage * (WERTE["kv"] + WERTE["pv"] + _av(brutto) + WERTE["ak"] + WERTE["wbf"]))


def sv_sonder(brutto: Fraction, sonder: Fraction) -> Fraction:
    return _cent(min(sonder, WERTE["hoechstbeitrag"]) * (WERTE["kv"] + WERTE["pv"] + _av(brutto)))


def einkommensteuer(jahr: Fraction) -> Fraction:
    steuer, unten = Fraction(0), Fraction(0)
    for grenze, satz in WERTE["tarif"]:
        if jahr > unten:
            steuer += (min(jahr, grenze) - unten) * satz
        unten = grenze
    if jahr > unten:
        steuer += (jahr - unten) * WERTE["tarif_oben"]
    return steuer


def lohnsteuer_laufend(brutto: Fraction, sv: Fraction) -> Fraction:
    basis = 12 * (brutto - sv) - WERTE["werbungskosten"]
    return _cent(max(Fraction(0), einkommensteuer(max(basis, Fraction(0))) - WERTE["verkehrsabsetzbetrag"]) / 12)


def netto_rechnen(brutto: Fraction, gehaelter: int = 14) -> dict:
    sv = sv_laufend(brutto)
    lst = lohnsteuer_laufend(brutto, sv)
    erg = {"brutto": brutto, "sv": sv, "lst": lst, "netto": brutto - sv - lst, "gehaelter": gehaelter}
    if gehaelter == 14:
        svs = sv_sonder(brutto, brutto)
        s1 = _cent(max(Fraction(0), brutto - svs - WERTE["sonder_freibetrag"]) * WERTE["sonder_satz"])
        s2 = _cent(max(Fraction(0), brutto - svs) * WERTE["sonder_satz"])
        erg.update({"sv_sonder": svs, "sonder1": brutto - svs - s1, "sonder2": brutto - svs - s2, "st1": s1, "st2": s2})
        erg["jahr"] = 12 * erg["netto"] + erg["sonder1"] + erg["sonder2"]
    else:
        erg["jahr"] = 12 * erg["netto"]
    return erg


def brutto_zu_netto(netto_laufend: Fraction) -> Fraction:
    lo, hi = int(GRENZE_VON * 100), int(GRENZE_BIS * 100)
    while lo < hi:
        mid = (lo + hi) // 2
        b = Fraction(mid, 100)
        sv = sv_laufend(b)
        if b - sv - lohnsteuer_laufend(b, sv) >= netto_laufend:
            hi = mid
        else:
            lo = mid + 1
    return Fraction(lo, 100)


NUM = r"\d+(?:[.,]\d+)*"
_ERLAUBT = set("""wie viel viele was wird werden ist sind bleibt bleiben bleibe netto brutto von bei ich verdiene verdient verdienst gehalt lohn gehälter gehaelter monatlich im monat pro jahr jährlich
jahres jahresbrutto jahresnetto bruttojahresgehalt jahresgehalt österreich oesterreich mit ohne kriege bekomme bekommt bekomm habe hab brauche brauchen will möchte moechte damit bekommen auszahlung ausbezahlt übrig uebrig am ende
euro eur sind ergibt rechne rechner umrechnen in nach abzügen abzuegen abzüge steuer steuern sozialversicherung monatsgehalt monatsbrutto monatsnetto gross net salary per month year austria my
take home pay of how much the is are on for a an to what do i get from after tax gehalts bruttogehalt nettogehalt mal x aufs auf das die der den dem einem einer eine ein wenn man haben ca circa etwa also dann hätte
haette verdiene brauch benötige benoetige um zu muss müsste soll sollte erreichen ausgezahlt wären waeren wäre waere auszahlen ausgezahlt kommt raus heraus herauskommt
want need needs earn earns make makes made like should have has get gets monthly yearly annual after before taxes tax income deductions deduction take-home takehome""".split())


def _zahlen_und_art(t: str):
    gehaelter = 14
    m = re.search(r"(\d+)\s*(?:gehälter|gehaelter|monatsgehälter|monatsgehaelter|gehälten|mal|x|salaries|payments)\b", t, re.I)
    if m:
        gehaelter = int(m.group(1))
        if gehaelter not in (12, 14):
            raise _Nein
        t = t[:m.start()] + " " + t[m.end():]
    zahlen = list(re.finditer(rf"(?<![\w.,]){NUM}(?![\w])", t))
    if len(zahlen) != 1:
        raise _Nein
    z = zahlen[0]
    vor, nach = t[:z.start()].lower(), t[z.end():].lower()
    phrase = None
    if re.search(r"\b(?:gross|brutto)\s+(?:to|zu|in|auf|->|→)\s+(?:net|netto)\b", t, re.I):
        phrase = "brutto"
    elif re.search(r"\b(?:net|netto)\s+(?:to|zu|in|auf|->|→)\s+(?:gross|brutto)\b", t, re.I):
        phrase = "netto"
    if phrase is not None:
        rest = t[:z.start()] + " " + t[z.end():]
        jahr = bool(re.search(r"jahres|jährlich|im\s+jahr|pro\s+jahr|per\s+year|yearly|annual", rest, re.I))
        return zahl_lesen(z.group(0)), phrase, jahr, gehaelter, rest
    nah_nach = re.match(r"\s*(?:€|euro|eur)?\s*(jahresbrutto|bruttojahresgehalt|jahresnetto|brutto|netto|gross|net)\b", nach)
    nah_vor = re.search(r"(jahresbrutto|bruttojahresgehalt|jahresnetto|brutto|netto|gross|net)\s*(?:von|bei|:|=|of|is|ist)?\s*(?:€\s*)?$", vor)
    art = (nah_nach or nah_vor)
    if not art:
        raise _Nein
    wort = art.group(1)
    gegeben = "brutto" if wort in ("brutto", "gross", "jahresbrutto", "bruttojahresgehalt") else "netto"
    betrag = zahl_lesen(z.group(0))
    rest = t[:z.start()] + " " + t[z.end():]
    jahr = wort.startswith(("jahres", "bruttojahr")) or bool(re.search(r"jahres|jährlich|im\s+jahr|pro\s+jahr|per\s+year|yearly|annual", rest, re.I))
    return betrag, gegeben, jahr, gehaelter, rest


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    t = re.sub(r"[\s?!.]+$", "", t)
    if not t or len(t) > 160 or not re.search(r"brutto|netto|gross|net\b", t, re.I):
        return None
    if re.search(r"%|prozent|mwst|\bust\b|umsatzsteuer|mehrwertsteuer|vat|rabatt|aufschlag|skonto|zoll", t, re.I):
        return None
    import rechnen
    if not rechnen.waehrung():
        rechnen._WAEHRUNG.zeichen = "€"
    try:
        betrag, gegeben, jahr, gehaelter, rest = _zahlen_und_art(t)
    except _Nein:
        return None
    bereinigt = re.sub(r"€|[.,]", " ", rest)
    unbekannt = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß']+", bereinigt) if w.lower() not in _ERLAUBT]
    if unbekannt:
        return None
    if jahr:
        if gegeben != "brutto":
            return None
        betrag = betrag / gehaelter
    if gegeben == "brutto":
        if not GRENZE_VON <= betrag <= GRENZE_BIS:
            return None
        return glatt(_antwort(betrag, gehaelter, jahr), t)
    if not Fraction(800) <= betrag <= Fraction(10000):
        return None
    b = brutto_zu_netto(betrag)
    e = netto_rechnen(b)
    if e["netto"] < betrag or e["netto"] - betrag > Fraction(50):
        return None
    return glatt(_antwort_rueck(betrag, b, gehaelter), t)


def _hinweis(en: bool) -> str:
    import rechnen_datum
    heute_jahr = rechnen_datum.heute().year
    spaeter = heute_jahr > GUELTIG_JAHR
    if en:
        s = (f" Calculated with the {GUELTIG_JAHR} values for employees (not apprentices, civil servants or the self-employed), without commuter allowance, family bonus, other tax credits, "
             f"overtime, church tax or union fees. A rough estimate, not a payslip; your employer's payroll is what counts.")
        if spaeter:
            s += f" Note: these are the {GUELTIG_JAHR} values, the rates for {heute_jahr} may differ."
        return s
    s = (f" Gerechnet mit den Werten {GUELTIG_JAHR} für Angestellte und Arbeiter (nicht für Lehrlinge, Beamte und Selbständige), ohne Pendlerpauschale, Familienbonus und andere Absetzbeträge, "
         f"Überstunden, Kirchenbeitrag und Gewerkschaft. Ein Überschlag, kein Lohnzettel; verbindlich rechnet deine Lohnverrechnung.")
    if spaeter:
        s += f" Achtung: das sind die Werte von {GUELTIG_JAHR}, {heute_jahr} kann es anders sein."
    return s


def _g(x: Fraction, en: bool = False) -> str:
    return geld_text(x, en)


def _antwort(brutto: Fraction, gehaelter: int, jahr: bool) -> Ergebnis:
    e = netto_rechnen(brutto, gehaelter)
    kopf_de = f"Bei {_g(brutto)} brutto im Monat" + (f" ({_g(brutto * gehaelter)} im Jahr)" if jahr else "") + f" mit {gehaelter} Gehältern:"
    kopf_en = f"At {_g(brutto, True)} gross per month" + (f" ({_g(brutto * gehaelter, True)} per year)" if jahr else "") + f" with {gehaelter} salaries:"
    de = [kopf_de, f"Netto im Monat: {_g(e['netto'])} (Sozialversicherung {_g(e['sv'])}, Lohnsteuer {_g(e['lst'])})"]
    en = [kopf_en, f"Net per month: {_g(e['netto'], True)} (social insurance {_g(e['sv'], True)}, income tax {_g(e['lst'], True)})"]
    if gehaelter == 14:
        de.append(f"13. und 14. Gehalt: {_g(e['sonder1'])} und {_g(e['sonder2'])} (Sozialversicherung {_g(e['sv_sonder'])} je Zahlung, dazu nur 6 % Steuer, das erste mit 620 € Freibetrag)")
        en.append(f"13th and 14th salary: {_g(e['sonder1'], True)} and {_g(e['sonder2'], True)} (social insurance {_g(e['sv_sonder'], True)} each, plus only 6% tax, the first with a €620 allowance)")
    de.append(f"Im Jahr: {_g(e['jahr'])} netto, das sind im Schnitt {_g(e['jahr'] / gehaelter)} je Gehalt.")
    en.append(f"Per year: {_g(e['jahr'], True)} net, which is {_g(e['jahr'] / gehaelter, True)} on average per salary.")
    return Ergebnis("\n".join(de) + "\n" + _hinweis(False).strip(), "\n".join(en) + "\n" + _hinweis(True).strip())


def _antwort_rueck(netto: Fraction, brutto: Fraction, gehaelter: int) -> Ergebnis:
    e = netto_rechnen(brutto, gehaelter)
    de = [f"Für {_g(netto)} netto im Monat brauchst du ungefähr {_g(brutto)} brutto (Sozialversicherung {_g(e['sv'])}, Lohnsteuer {_g(e['lst'])}, netto laufend {_g(e['netto'])}).",
          f"Das sind bei {gehaelter} Gehältern rund {_g(brutto * gehaelter)} brutto im Jahr."]
    en = [f"For {_g(netto, True)} net per month you need about {_g(brutto, True)} gross (social insurance {_g(e['sv'], True)}, income tax {_g(e['lst'], True)}, net {_g(e['netto'], True)}).",
          f"With {gehaelter} salaries that is about {_g(brutto * gehaelter, True)} gross per year."]
    return Ergebnis("\n".join(de) + "\n" + _hinweis(False).strip(), "\n".join(en) + "\n" + _hinweis(True).strip())
