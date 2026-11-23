# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import itertools
import re

from rechnen import Ergebnis

_ZAHL = r"(\d{1,7})"


def _z(s: str) -> int:
    return int(s)


def _t(n: int) -> str:
    s = str(abs(n))
    gruppen = []
    while len(s) > 3:
        gruppen.insert(0, s[-3:])
        s = s[:-3]
    gruppen.insert(0, s)
    return ("-" if n < 0 else "") + ".".join(gruppen)


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(str(text or "").split())
    if not t or len(t) > 600:
        return None
    t = _zahlwoerter(t)
    for stufe in (_umkehr, _beine, _reihenfolge, _fehler_division, _wechselgeld, _stueck_preis, _je_zeit, _so_viele_wie, _summe_zwei,
                  _summe_aus, _alter_wochen, _alle_n_tage, _geschickt, _kalender, _altersvergleich, _bruchteil, _abfahrt_ankunft, _zahlenfolge, _rechteck):
        r = stufe(t)
        if r is not None:
            return r
    return None


_RAETSEL = re.compile(
    r"(?i)^(?:.*?:\s*)?(?:wenn\s+(?:ich|du|man)\s+)?(?P<op>dividiere|teile|multipliziere|addiere|subtrahiere|ziehe)\s+(?:die|eine)\s+zahl\s+"
    r"(?:(?:durch|mit|um)\s+" + _ZAHL + r"|(?P<b2>\d{1,7})\s+dazu|von\s+(?P<b3>\d{1,7}))?\s*(?:ab\s*)?,?\s*(?:und|dann)\s+(?:du\s+|ich\s+|man\s+)?"
    r"(?:erh[äa]ltst|erhalte|erh[äa]lt|bekommst|bekomme|bekommt|kommt\s+heraus)\s*:?\s*" + _ZAHL +
    r"(?:\s*(?:rest|r)\s*" + _ZAHL + r")?(?:\s+heraus)?\s*[.!]?\s*(?:wie\s+hei(?:ß|ss)t\s+die\s+zahl\s*\??|welche\s+zahl\s+ist\s+(?:es|das)\s*\??)?$")
_RAETSEL_VORN = re.compile(
    r"(?i)^(?:.*?:\s*)?(?P<op>addiere|subtrahiere|ziehe)\s+" + _ZAHL + r"\s+(?:zu\s+(?:der|einer)\s+zahl|zur\s+zahl|von\s+(?:der|einer)\s+zahl(?:\s+ab)?)"
    r"\s*,?\s*(?:und|dann)\s+(?:du\s+)?(?:erh[äa]ltst|bekommst)\s*:?\s*" + _ZAHL +
    r"\s*[.!]?\s*(?:wie\s+hei(?:ß|ss)t\s+die\s+zahl\s*\??)?$")


def _umkehr(t: str) -> Ergebnis | None:
    m = _RAETSEL.match(t)
    if m:
        op = m.group("op").lower()
        b = m.group(2) or m.group("b2") or m.group("b3")
        if b is None:
            return None
        von = m.group("b3") is not None
        b, erg = _z(b), _z(m.group(5))
        rest = _z(m.group(6)) if m.group(6) else None
    else:
        m = _RAETSEL_VORN.match(t)
        if not m:
            return None
        op, b, erg, rest, von = m.group("op").lower(), _z(m.group(2)), _z(m.group(3)), None, False
    if op in ("dividiere", "teile"):
        if b == 0:
            return None
        r = rest or 0
        if r >= b:
            return None
        zahl = b * erg + r
        weg = (f"Rechne rückwärts: {_t(b)} · {_t(erg)} = {_t(b * erg)}" + (f", dazu der Rest: {_t(b * erg)} + {_t(r)} = {_t(zahl)}" if r else "")
               + ".")
        probe = f"Probe: {_t(zahl)} : {_t(b)} = {_t(erg)}" + (f" Rest {_t(r)}" if r else "") + "."
        weg_en = (f"Work backwards: {_t(b)} × {_t(erg)} = {_t(b * erg)}" + (f", plus the remainder: {_t(b * erg)} + {_t(r)} = {_t(zahl)}" if r else "")
                  + ".")
        probe_en = f"Check: {_t(zahl)} ÷ {_t(b)} = {_t(erg)}" + (f" remainder {_t(r)}" if r else "") + "."
    elif rest is not None:
        return None
    elif op == "multipliziere":
        if b == 0 or erg % b:
            return None
        zahl = erg // b
        weg, probe = f"Rechne rückwärts: {_t(erg)} : {_t(b)} = {_t(zahl)}.", f"Probe: {_t(zahl)} · {_t(b)} = {_t(erg)}."
        weg_en, probe_en = f"Work backwards: {_t(erg)} ÷ {_t(b)} = {_t(zahl)}.", f"Check: {_t(zahl)} × {_t(b)} = {_t(erg)}."
    elif op == "addiere":
        zahl = erg - b
        if zahl < 0:
            return None
        weg, probe = f"Rechne rückwärts: {_t(erg)} − {_t(b)} = {_t(zahl)}.", f"Probe: {_t(zahl)} + {_t(b)} = {_t(erg)}."
        weg_en, probe_en = f"Work backwards: {_t(erg)} − {_t(b)} = {_t(zahl)}.", f"Check: {_t(zahl)} + {_t(b)} = {_t(erg)}."
    elif von:
        zahl = b - erg
        if zahl < 0:
            return None
        weg, probe = f"Rechne rückwärts: {_t(b)} − {_t(erg)} = {_t(zahl)}.", f"Probe: {_t(b)} − {_t(zahl)} = {_t(erg)}."
        weg_en, probe_en = f"Work backwards: {_t(b)} − {_t(erg)} = {_t(zahl)}.", f"Check: {_t(b)} − {_t(zahl)} = {_t(erg)}."
    else:
        zahl = erg + b
        weg, probe = f"Rechne rückwärts: {_t(erg)} + {_t(b)} = {_t(zahl)}.", f"Probe: {_t(zahl)} − {_t(b)} = {_t(erg)}."
        weg_en, probe_en = f"Work backwards: {_t(erg)} + {_t(b)} = {_t(zahl)}.", f"Check: {_t(zahl)} − {_t(b)} = {_t(erg)}."
    return Ergebnis(f"Die Zahl ist {_t(zahl)}.\n\n{weg}\n{probe}", f"The number is {_t(zahl)}.\n\n{weg_en}\n{probe_en}")


_BEINE = {
    4: ("ziege", "kuh", "kühe", "pferd", "hund", "katze", "schaf", "schwein", "hase", "kaninchen", "esel", "lamm", "kalb", "kälber", "fuchs",
        "elefant", "löwe", "tiger", "maus", "mäuse", "ratte", "igel", "reh", "hirsch", "ziegen", "pony", "ponys"),
    2: ("ente", "huhn", "hühner", "hahn", "hähne", "gans", "gänse", "vogel", "vögel", "taube", "pute", "truthahn", "strauß", "strauße",
        "pinguin", "papagei", "spatz", "spatzen", "kind", "kinder", "mensch", "menschen", "eule", "storch", "störche", "schwan", "schwäne"),
    6: ("käfer", "marienkäfer", "ameise", "biene", "fliege", "insekt", "insekten", "heuschrecke"),
    8: ("spinne", "spinnen"),
}


def _beine_von(wort: str) -> int | None:
    w = wort.lower()
    for n, namen in _BEINE.items():
        for name in namen:
            if w == name or w.startswith(name) and len(w) - len(name) <= 2:
                return n
    return None


_BEINE_RE = re.compile(
    r"(?i)(?P<a>[A-Za-zÄÖÜäöüß]+)\s+und\s+(?P<b>[A-Za-zÄÖÜäöüß]+)\b[^.?!]*[.?!]?\s*(?:zusammen\s+)?(?:sind\s+es|gibt\s+es|hat\s+(?:er|sie|der\s+hof)|"
    r"haben\s+sie)\s+(?:zusammen\s+)?(?P<n>\d{1,4})\s+tiere\s+(?:mit|und)\s+(?:zusammen\s+)?(?P<beine>\d{1,5})\s+beine")


def _beine(t: str) -> Ergebnis | None:
    m = _BEINE_RE.search(t)
    if not m or not re.search(r"(?i)\bwie\s*viele\b|\?|\bberechne|\bfinde", t) or re.search(r",\s*$", t[:m.start()]):
        return None
    a, b = m.group("a"), m.group("b")
    ba, bb = _beine_von(a), _beine_von(b)
    if ba is None or bb is None or ba == bb:
        return None
    n, beine = _z(m.group("n")), _z(m.group("beine"))
    (klein, k_name), (gross, g_name) = sorted([(ba, a), (bb, b)])
    grund = n * klein
    fehlen = beine - grund
    unterschied = gross - klein
    if fehlen < 0 or fehlen % unterschied or fehlen // unterschied > n:
        return None
    viele_g = fehlen // unterschied
    viele_k = n - viele_g
    de = (f"Es sind {_t(viele_g)} {g_name} und {_t(viele_k)} {k_name}.\n\n"
          f"So kommst du darauf: Wären alle {_t(n)} Tiere {k_name}, hätten sie {_t(n)} · {klein} = {_t(grund)} Beine. "
          f"Es sind aber {_t(beine)} Beine, also fehlen {_t(beine)} − {_t(grund)} = {_t(fehlen)}. "
          f"Jedes Tier mit {gross} statt {klein} Beinen bringt {unterschied} Beine mehr: {_t(fehlen)} : {unterschied} = {_t(viele_g)}. "
          f"Also {_t(viele_g)} {g_name}, und {_t(n)} − {_t(viele_g)} = {_t(viele_k)} {k_name}.\n"
          f"Probe: {_t(viele_g)} · {gross} + {_t(viele_k)} · {klein} = {_t(viele_g * gross)} + {_t(viele_k * klein)} = {_t(beine)} Beine.")
    en = (f"There are {_t(viele_g)} {g_name} and {_t(viele_k)} {k_name}.\n\n"
          f"How to get there: if all {_t(n)} animals were {k_name}, they would have {_t(n)} × {klein} = {_t(grund)} legs. "
          f"There are {_t(beine)} legs, so {_t(beine)} − {_t(grund)} = {_t(fehlen)} are missing. "
          f"Each animal with {gross} instead of {klein} legs adds {unterschied}: {_t(fehlen)} ÷ {unterschied} = {_t(viele_g)}.\n"
          f"Check: {_t(viele_g)} × {gross} + {_t(viele_k)} × {klein} = {_t(beine)} legs.")
    return Ergebnis(de, en)


_NAME = r"[A-ZÄÖÜ][a-zäöüß]+"
_NAMEN_RE = re.compile(rf"(?P<namen>{_NAME}(?:\s*,\s*{_NAME})*\s+und\s+{_NAME})\b")
_ORDNUNG = {"erste": 1, "erster": 1, "erstes": 1, "zweite": 2, "zweiter": 2, "dritte": 3, "dritter": 3, "vierte": 4, "vierter": 4,
            "fünfte": 5, "fünfter": 5, "letzte": -1, "letzter": -1, "letztes": -1}
_KEIN_NAME = {"Die", "Der", "Das", "Wer", "Wie", "In", "Und", "Er", "Sie", "Es", "Nicht", "Als", "Mit", "Auf", "Im", "Am", "Beim"}


def _reihenfolge(t: str) -> Ergebnis | None:
    if not re.search(r"(?i)\bin\s+welcher\s+reihenfolge\b|\bwer\s+(?:ist|steht|sitzt|läuft|reitet|kommt)\s+(?:an\s+erster|vorne|zuerst)", t):
        return None
    m = _NAMEN_RE.search(t)
    if not m:
        return None
    namen = [n for n in re.split(r"\s*,\s*|\s+und\s+", m.group("namen")) if n not in _KEIN_NAME]
    if not 3 <= len(namen) <= 7 or len(set(namen)) != len(namen):
        return None
    rest = t[m.end():]
    bedingungen: list = []
    erklaert: list[str] = []
    saetze = [s.strip() for s in re.split(r"(?<=[.!?])\s+", rest) if s.strip()]
    for satz in saetze:
        if re.search(r"(?i)\bin\s+welcher\s+reihenfolge\b", satz):
            continue
        sub = re.match(rf"({_NAME})\b", satz)
        if not sub or sub.group(1) not in namen:
            if re.search(rf"\b(?:vor|hinter|zwischen|als)\b", satz):
                return None
            continue
        s = sub.group(1)
        if re.search(r"(?i)\b(?:weder|noch|kein\w*|nie|niemals|oder)\b", satz):
            return None
        erlaubt = {s} | set(re.findall(rf"(?i)(?:vor|hinter|zwischen)\s+({_NAME})", satz)) | set(
            re.findall(rf"zwischen\s+{_NAME}\s+und\s+({_NAME})", satz))
        if any(n in namen and n not in erlaubt for n in re.findall(_NAME, satz)):
            return None
        gefunden = False
        for nicht, art, ziel in re.findall(rf"(?i)(nicht\s+)?(direkt\s+vor|direkt\s+hinter|gleich\s+hinter|gleich\s+vor|vor|hinter)\s+({_NAME})", satz):
            if ziel not in namen:
                return None
            direkt = art.lower().startswith(("direkt", "gleich"))
            vor = art.lower().endswith("vor")
            a, b = (s, ziel) if vor else (ziel, s)
            if direkt:
                bed = (lambda p, a=a, b=b: p[b] - p[a] == 1)
            else:
                bed = (lambda p, a=a, b=b: p[a] < p[b])
            bedingungen.append((lambda p, f=bed: not f(p)) if nicht else bed)
            gefunden = True
        for nicht, wort in re.findall(r"(?i)(nicht\s+)?als\s+(erste[rs]?|zweite[r]?|dritte[r]?|vierte[r]?|fünfte[r]?|letzte[rs]?)\b", satz):
            stelle = _ORDNUNG[wort.lower()]
            bed = (lambda p, s=s, k=stelle: (p[s] == len(p) - 1) if k == -1 else p[s] == k - 1)
            bedingungen.append((lambda p, f=bed: not f(p)) if nicht else bed)
            gefunden = True
        z = re.search(rf"zwischen\s+({_NAME})\s+und\s+({_NAME})", satz)
        if z:
            x, y = z.group(1), z.group(2)
            if x not in namen or y not in namen:
                return None
            bedingungen.append(lambda p, s=s, x=x, y=y: min(p[x], p[y]) < p[s] < max(p[x], p[y]))
            gefunden = True
        if not gefunden:
            if re.search(r"(?i)\b(?:vor|hinter|zwischen|als|neben)\b", satz):
                return None
            continue
        erklaert.append(satz)
    if not bedingungen:
        return None
    loesungen = []
    for folge in itertools.permutations(namen):
        p = {n: i for i, n in enumerate(folge)}
        if all(b(p) for b in bedingungen):
            loesungen.append(folge)
            if len(loesungen) > 1:
                return None
    if not loesungen:
        return None
    f = loesungen[0]
    liste = ", ".join(f[:-1]) + " und " + f[-1] if len(f) > 1 else f[0]
    liste_en = ", ".join(f[:-1]) + " and " + f[-1]
    zeilen = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(f))
    de = (f"Die Reihenfolge ist: {liste}.\n\n{zeilen}\n\nSo passt es zu jedem Hinweis: " + " ".join(erklaert)
          + " Andere Reihenfolgen passen nicht zu allen Hinweisen zugleich.")
    en = f"The order is: {liste_en}.\n\n{zeilen}"
    return Ergebnis(de, en)


_DIV_R = re.compile(r"(?i)(\d{1,6})\s*[:÷]\s*(\d{1,4})\s*=\s*(\d{1,6})\s*(?:R|Rest)\s*(\d{1,4})")
_DIV_OHNE = re.compile(r"(?i)(\d{1,6})\s*[:÷]\s*(\d{1,4})\s*=\s*(\d{1,6})(?!\s*(?:\d|R\b|Rest\b))")


def _fehler_division(t: str) -> Ergebnis | None:
    if not re.search(r"(?i)\b(?:fehler|falsch|stimmt|richtig|kann\s+das\s+stimmen|überprüf|pr[üu]fe)\b", t):
        return None
    rechnungen = [tuple(int(x) for x in r) for r in _DIV_R.findall(t)]
    if not rechnungen or any(b == 0 for _a, b, _q, _r in rechnungen):
        return None
    ohne = [tuple(int(x) for x in r) for r in _DIV_OHNE.findall(t)]
    a, b, q, r = rechnungen[0]
    schritte = rechnungen[1:] + [(x, y, z, 0) for x, y, z in ohne]
    if schritte and all(y == b for _x, y, _z, _r in schritte) and sum(x for x, *_ in schritte) == a:
        return _eine_division(a, b, q, r, schritte)
    if ohne or len(rechnungen) == 1:
        return _eine_division(a, b, q, r, []) if len(rechnungen) == 1 and not ohne else None
    zeilen, zeilen_en = [], []
    for x, y, z, w in rechnungen:
        k, kr = divmod(x, y)
        if (z, w) == (k, kr):
            zeilen.append(f"{_t(x)} : {_t(y)} = {_t(z)} Rest {_t(w)} stimmt.")
            zeilen_en.append(f"{_t(x)} ÷ {_t(y)} = {_t(z)} remainder {_t(w)} is right.")
        else:
            warum = " Der Rest ist zu groß." if w >= y else ""
            zeilen.append(f"{_t(x)} : {_t(y)} = {_t(z)} Rest {_t(w)} stimmt nicht, richtig ist {_t(k)} Rest {_t(kr)}.{warum}")
            zeilen_en.append(f"{_t(x)} ÷ {_t(y)} = {_t(z)} remainder {_t(w)} is wrong; it is {_t(k)} remainder {_t(kr)}.")
    return Ergebnis("\n".join(zeilen), "\n".join(zeilen_en))


def _eine_division(a: int, b: int, q: int, r: int, schritte: list) -> Ergebnis:
    rq, rr = divmod(a, b)
    if (q, r) == (rq, rr):
        return Ergebnis(f"Das stimmt: {_t(a)} : {_t(b)} = {_t(q)} Rest {_t(r)}.\nProbe: {_t(b)} · {_t(q)} = {_t(b * q)}, {_t(b * q)} + {_t(r)} = {_t(a)}.",
                        f"That is right: {_t(a)} ÷ {_t(b)} = {_t(q)} remainder {_t(r)}.")
    grund = []
    if r >= b:
        grund.append(f"Der Rest {_t(r)} ist größer als {_t(b)} oder gleich groß. Ein Rest muss immer kleiner sein als die Zahl, durch die geteilt "
                     f"wird; dann passt noch einmal {_t(b)} hinein.")
    if b * q + r != a:
        grund.append(f"Die Probe geht nicht auf: {_t(b)} · {_t(q)} + {_t(r)} = {_t(b * q + r)}, nicht {_t(a)}.")
    for x, y, z, w in schritte:
        k, kr = divmod(x, y)
        if (z, w) != (k, kr):
            falsch = f"{_t(x)} : {_t(y)} = {_t(z)}" + (f" Rest {_t(w)}" if w else "")
            richtig = f"{_t(x)} : {_t(y)} = {_t(k)}" + (f" Rest {_t(kr)}" if kr else "")
            grund.append(f"Falsch ist der Schritt {falsch}; richtig ist {richtig}.")
    de = (f"Das stimmt nicht. Richtig ist {_t(a)} : {_t(b)} = {_t(rq)} Rest {_t(rr)}.\n\n" + "\n".join(grund)
          + f"\nProbe: {_t(b)} · {_t(rq)} = {_t(b * rq)}, {_t(b * rq)} + {_t(rr)} = {_t(a)}.")
    en = f"That is not right. The answer is {_t(a)} ÷ {_t(b)} = {_t(rq)} remainder {_t(rr)}."
    return Ergebnis(de, en)


_ZAHLWORT = {"ein": 1, "eine": 1, "einen": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
             "zehn": 10, "elf": 11, "zwölf": 12}


def _zahlwoerter(t: str) -> str:
    return re.sub(r"\b(zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf)\b(?=\s+(?-i:[A-ZÄÖÜ])|\s+(?:jahre|wochen|tage|monate)\b)",
                  lambda m: str(_ZAHLWORT[m.group(1).lower()]), t, flags=re.I)


def _geld(s_: str) -> int | None:
    m = re.fullmatch(r"(\d{1,6})(?:,(\d{1,2}))?\s*(€|euro|ct|cent)", s_.strip(), re.I)
    if not m:
        return None
    if m.group(3).lower() in ("ct", "cent"):
        return None if m.group(2) else int(m.group(1))
    return int(m.group(1)) * 100 + int((m.group(2) or "0").ljust(2, "0"))


def _eur(cent: int) -> str:
    return f"{_t(cent // 100)},{cent % 100:02d} €"


_BETRAG = r"\d{1,6}(?:,\d{1,2})?\s*(?:€|euro\b|ct\b|cent\b)"


def _wechselgeld(t: str) -> Ergebnis | None:
    m = re.search(rf"(?i)\bhat\s+({_BETRAG})[^.?!]*[.?!]?\s*[^.?!]*?\bkauft\b[^.?!]*?\b(?:um|für|zu)\s+({_BETRAG})", t)
    if not m or not re.search(r"(?i)\b(?:bleibt|übrig|zurück|wechselgeld|rest)\b", t[m.end():]):
        return None
    if len(re.findall(_BETRAG, t, re.I)) != 2 or re.search(r"(?i)\bkauft\b[^.?!]*?(?:\b\d|\bje\b|\bjede)", t[:m.start(2)]):
        return None
    hat, preis = _geld(m.group(1)), _geld(m.group(2))
    if hat is None or preis is None or preis > hat:
        return None
    rest = hat - preis
    return Ergebnis(f"Es bleiben {_eur(rest)} übrig.\n\nRechnung: {_eur(hat)} − {_eur(preis)} = {_eur(rest)}.\nProbe: {_eur(rest)} + {_eur(preis)} = {_eur(hat)}.",
                    f"{_eur(rest)} is left.\n\n{_eur(hat)} − {_eur(preis)} = {_eur(rest)}.")


class _Treffer:

    def __init__(self, *gruppen):
        self._g = gruppen

    def group(self, i):
        return self._g[i - 1]


def _stueck_preis(t: str) -> Ergebnis | None:
    m = re.search(rf"(?i)\b(?:kauft|kaufen|kaufe|bestellt|nimmt)\s+[^.?!]*?\b(\d{{1,4}})\s+((?-i:[A-ZÄÖÜ])[a-zäöüß]+)[^.?!]*[.?!]?\s*"
                  rf"(?:jede[rs]?|je|ein(?:e[rs]?)?|pro)\s+[^.?!]*?\b(?:kostet|kosten|um|für)\s+({_BETRAG})", t)
    if not m:
        m = re.search(rf"(?i)\b(\d{{1,4}})\s+((?-i:[A-ZÄÖÜ])[a-zäöüß]+)\b[^?]*?\b(?:kostet|kosten|zahlt|zahlen)\s+(?:für\s+|pro\s+)?"
                      rf"(?:jede[nrs]?|je|ein(?:e[rs]?)?)\s+(?-i:[A-ZÄÖÜ])[a-zäöüß]+\s+({_BETRAG})", t)
        if m:
            m = _Treffer(m.group(1), m.group(2), m.group(3))
    if not m or re.search(r"(?i)\b(?:wenn|falls|außer|ausser|ohne|rabatt|ermäßig\w*|gratis|frei|insgesamt\s+\d)\b", t):
        return None
    if not re.search(r"(?i)\bwie\s*viel\b|\binsgesamt\b|\bzusammen\b|\?", t):
        return None
    ohne_betraege = re.sub(_BETRAG, " ", t, flags=re.I)
    if len(re.findall(_BETRAG, t, re.I)) != 1 or len(re.findall(r"\b\d{1,4}\b", ohne_betraege)) != 1:
        return None
    n, preis = int(m.group(1)), _geld(m.group(3))
    if preis is None or not 1 <= n <= 1000:
        return None
    ges = n * preis
    weg = f"{n} · {_eur(preis)} = {_eur(ges)}"
    if preis % 100 in (99, 98, 95) and n <= 20:
        ganz = preis + (100 - preis % 100)
        weg += f". Geschickt gerechnet: {n} · {_eur(ganz)} = {_eur(n * ganz)}, weniger {n} · {100 - preis % 100} ct = {_eur(n * ganz - ges)}"
    return Ergebnis(f"Das kostet zusammen {_eur(ges)}.\n\nRechnung: {weg}.", f"Together that costs {_eur(ges)}.\n\n{n} × {_eur(preis)} = {_eur(ges)}.")


_ZEIT_IN = {("tag", "woche"): 7, ("woche", "jahr"): 52, ("monat", "jahr"): 12, ("tag", "jahr"): 365, ("stunde", "tag"): 24, ("minute", "stunde"): 60}


def _je_zeit(t: str) -> Ergebnis | None:
    m = re.search(r"(?i)\b(?:jede[nrs]?|pro|am|im)\s+(tag|woche|monat|stunde|minute)\b", t)
    z = re.search(r"(?i)\bin\s+(?:einer|einem|einem\s+ganzen|einer\s+ganzen)\s+(woche|jahr|monat|tag|stunde)\b", t)
    if not m or not z or not re.search(r"(?i)\bwie\s*viel", t):
        return None
    if re.search(r"(?i)\b(?:wenn|falls|außer|ausser|ohne|frei|nur|bis\s+auf|abzüglich|weniger|manchmal)\b", t):
        return None
    faktor = _ZEIT_IN.get((m.group(1).lower(), z.group(1).lower()))
    if not faktor:
        return None
    if re.search(r"(?i)\w+mal\b", t) or re.search(r"\d", t[z.end():]):
        return None
    zahlen = [x for x in re.findall(rf"(?i)({_BETRAG}|\b\d{{1,5}}\b)", t[:z.start()]) if not re.fullmatch(r"(?:19|20)\d\d", x)]
    if len(zahlen) != 1:
        return None
    betrag = _geld(zahlen[0])
    if betrag is not None and (m.group(1).lower(), z.group(1).lower()) == ("stunde", "tag"):
        return None
    einheit = {"woche": "Woche", "jahr": "Jahr", "monat": "Monat", "tag": "Tag", "stunde": "Stunde"}[z.group(1).lower()]
    hinweis = " (ein Jahr hat 52 Wochen)" if faktor == 52 else " (eine Woche hat 7 Tage)" if faktor == 7 else ""
    if betrag is not None:
        ges = betrag * faktor
        return Ergebnis(f"In einem {einheit} sind das {_eur(ges)}.\n\nRechnung: {faktor} · {_eur(betrag)} = {_eur(ges)}{hinweis}.",
                        f"That is {_eur(ges)}.\n\n{faktor} × {_eur(betrag)} = {_eur(ges)}.")
    n = int(zahlen[0])
    if einheit == "Woche":
        zeile = f"In einer Woche sind das {_t(n * faktor)}."
    else:
        zeile = f"In einem {einheit} sind das {_t(n * faktor)}."
    return Ergebnis(f"{zeile}\n\nRechnung: {faktor} · {_t(n)} = {_t(n * faktor)}{hinweis}.", f"That is {_t(n * faktor)}.\n\n{faktor} × {_t(n)} = {_t(n * faktor)}.")


_MAL = {"doppelt": 2, "zweimal": 2, "dreimal": 3, "viermal": 4, "fünfmal": 5, "halb": None}


def _so_viele_wie(t: str) -> Ergebnis | None:
    m = re.search(r"(?i)\b(doppelt|zweimal|dreimal|viermal|fünfmal)\s+so\s+viele\s+((?-i:[A-ZÄÖÜ])[a-zäöüß]+)\s+wie\s+((?-i:[A-ZÄÖÜ])[a-zäöüß]+)\b"
                  r"[^?]*?\bzusammen\s+(?:sind\s+es|gibt\s+es|haben\s+sie)?\s*(\d{1,6})", t)
    if not m:
        return None
    k, viel, wenig, n = _MAL[m.group(1).lower()], m.group(2), m.group(3), int(m.group(4))
    teile = k + 1
    if n % teile:
        return None
    w = n // teile
    return Ergebnis(f"Es sind {_t(w * k)} {viel} und {_t(w)} {wenig}.\n\nSo kommst du darauf: Die {wenig} sind 1 Teil, die {viel} {k} Teile, "
                    f"zusammen also {teile} Teile. {_t(n)} : {teile} = {_t(w)} {wenig}, und {k} · {_t(w)} = {_t(w * k)} {viel}.\n"
                    f"Probe: {_t(w * k)} + {_t(w)} = {_t(n)}.",
                    f"There are {_t(w * k)} {viel} and {_t(w)} {wenig}.\n\n{_t(n)} ÷ {teile} = {_t(w)}; {k} × {_t(w)} = {_t(w * k)}.")


def _summe_zwei(t: str) -> Ergebnis | None:
    m = re.search(r"(?i)\bdie\s+summe\s+(?:aus|von)\s+(?:zwei|2)\s+zahlen\s+ist\s+(\d{1,7})\b[^.]*\.\s*die\s+erste\s+zahl\s+ist\s+"
                  r"(?:(\d{1,7})\s*(?:[.?!]|$)|das\s+doppelte\s+der\s+zweiten)", t)
    if not m:
        return None
    summe = int(m.group(1))
    if m.group(2):
        a = int(m.group(2))
        if a > summe:
            return None
        b = summe - a
        return Ergebnis(f"Die zweite Zahl ist {_t(b)}.\n\nRechnung: {_t(summe)} − {_t(a)} = {_t(b)}.\nProbe: {_t(a)} + {_t(b)} = {_t(summe)}.",
                        f"The second number is {_t(b)}.\n\n{_t(summe)} − {_t(a)} = {_t(b)}.")
    if summe % 3:
        return None
    b = summe // 3
    return Ergebnis(f"Die erste Zahl ist {_t(2 * b)}, die zweite {_t(b)}.\n\nSo kommst du darauf: Die erste ist doppelt so groß, zusammen sind es 3 "
                    f"gleiche Teile: {_t(summe)} : 3 = {_t(b)}, und 2 · {_t(b)} = {_t(2 * b)}.\nProbe: {_t(2 * b)} + {_t(b)} = {_t(summe)}.",
                    f"The first number is {_t(2 * b)}, the second {_t(b)}.")


_re_summe = re.compile(r"(?i)\bdie\s+summe\s+(?:aus|von)\b")


def _summe_aus(t: str) -> Ergebnis | None:
    m = re.fullmatch(r"(?i)(?:.*?:\s*)?(halbiere|verdopple|bilde|addiere)\s+(?:die\s+summe\s+(?:aus|von)\s+)?(\d{1,7})\s+und\s+(\d{1,7})\s*[.!]?"
                     r"(?:\s*was\s+kommt\s+heraus\??)?", t)
    if not m:
        return None
    op, a, b = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    if op in ("halbiere", "verdopple") and not _re_summe.search(t):
        return None
    summe = a + b
    if op == "halbiere":
        if summe % 2:
            return None
        return Ergebnis(f"Das Ergebnis ist {_t(summe // 2)}.\n\nRechnung: {_t(a)} + {_t(b)} = {_t(summe)}, die Hälfte: {_t(summe)} : 2 = {_t(summe // 2)}.",
                        f"The result is {_t(summe // 2)}.")
    if op == "verdopple":
        return Ergebnis(f"Das Ergebnis ist {_t(2 * summe)}.\n\nRechnung: {_t(a)} + {_t(b)} = {_t(summe)}, das Doppelte: 2 · {_t(summe)} = {_t(2 * summe)}.",
                        f"The result is {_t(2 * summe)}.")
    return Ergebnis(f"Die Summe ist {_t(summe)}.\n\nRechnung: {_t(a)} + {_t(b)} = {_t(summe)}.", f"The sum is {_t(summe)}.")


def _alter_wochen(t: str) -> Ergebnis | None:
    m = re.search(r"(?i)\b(\d{1,2})\s+jahre?\s+und\s+(\d{1,2})\s+wochen\s+alt\b[^.]*\.\s*(?:er|sie|es)\s+ist\s+also\s+(\d{1,4})\s+wochen\s+alt", t)
    if not m:
        return None
    j, w, behauptet = int(m.group(1)), int(m.group(2)), int(m.group(3))
    echt = j * 52 + w
    ja = echt == behauptet
    return Ergebnis(("Ja, das stimmt" if ja else "Nein, das stimmt nicht") + f": {j} · 52 + {w} = {_t(echt)} Wochen (ein Jahr hat 52 Wochen)."
                    + ("" if ja else f" {_t(behauptet)} Wochen wären erst gut {behauptet // 52} Jahre."),
                    ("Yes" if ja else "No") + f": {j} × 52 + {w} = {_t(echt)} weeks.")


_ZAHL_TAGE = {"zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}
_DATUM = r"(\d{1,2})\.\s?(\d{1,2})\."


def _alle_n_tage(t: str) -> Ergebnis | None:
    from datetime import date, timedelta
    if not re.search(r"(?i)\ban\s+wie\s+vielen\s+tagen\b", t):
        return None
    n = re.search(r"(?i)\balle\s+(zwei|drei|vier|fünf|\d)\s+tage\b", t) or re.search(r"(?i)\bjeden\s+(zweiten|dritten)\s+tag\b", t)
    span = re.search(rf"(?i)\bvom\s+{_DATUM}\s+bis\s+(?:zum\s+)?{_DATUM}", t)
    beginn = re.search(rf"(?i)\b(?:beginn\w*|fang\w*\s+an|ab)\s+(?:am\s+)?{_DATUM}", t) or re.search(rf"(?i)\bam\s+{_DATUM}\s+(?:an|los)\b", t)
    if not n or not span or not beginn:
        return None
    schritt = {"zweiten": 2, "dritten": 3}.get(n.group(1).lower()) or _ZAHL_TAGE.get(n.group(1).lower())
    if not schritt:
        return None
    jahr = 2027
    try:
        von = date(jahr, int(span.group(2)), int(span.group(1)))
        bis = date(jahr, int(span.group(4)), int(span.group(3)))
        erst = date(jahr, int(beginn.group(2)), int(beginn.group(1))) if beginn else von + timedelta(days=1)
    except ValueError:
        return None
    if not von <= erst < bis or (bis - von).days > 120 or {von.month, bis.month} & {1, 2, 12}:
        return None
    weg = bool(re.search(r"(?i)\b(?:urlaub|verreis\w*|fährt\w*\s+(?:weg|fort)|ist\s+weg|kommt\s+\w*\s*zurück|reise)\b", t))
    tage = []
    d = erst
    while d < bis or (d == bis and not weg):
        tage.append(d)
        d += timedelta(days=schritt)
    liste = ", ".join(f"{x.day}.{x.month}." for x in tage)
    grund = (f"am {bis.day}.{bis.month}. ist wieder jemand da, darum zählt er nicht mehr mit" if weg
             else f"der {bis.day}.{bis.month}. zählt mit, wenn er dran ist")
    return Ergebnis(f"An {len(tage)} Tagen: {liste}\n\nSo kommst du darauf: Ab dem {erst.day}.{erst.month}. jeden {schritt}. Tag; {grund}.",
                    f"On {len(tage)} days: {liste}")


def _geschickt(t: str) -> Ergebnis | None:
    if not re.search(r"(?i)\bgeschickt\b", t):
        return None
    m = re.fullmatch(r"(?i)(?:.*?:\s*)?(?:rechne\s+geschickt\s*:?\s*)?(\d{1,4})\s*[·x×*]\s*(\d{1,4})\s*=?\s*\??(?:\s*rechne\s+geschickt\.?)?", t.strip())
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    for x, y in ((a, b), (b, a)):
        if x % 10 == 9 and x <= 99:
            rund = x + 1
            ergebnis = x * y
            return Ergebnis(f"{_t(a)} · {_t(b)} = {_t(ergebnis)}.\n\nGeschickt gerechnet: {x} ist {rund} weniger 1. Erst {rund} · {_t(y)} = "
                            f"{_t(rund * y)}, dann 1 · {_t(y)} weg: {_t(rund * y)} − {_t(y)} = {_t(ergebnis)}.",
                            f"{_t(a)} × {_t(b)} = {_t(ergebnis)}. Smart way: {rund} × {_t(y)} = {_t(rund * y)}, minus {_t(y)} = {_t(ergebnis)}.")
    return None


_KALENDER = (
    (r"wie\s+viele\s+wochen\s+(?:hat|haben)\s+(?:ein|das)\s+jahr\b(?!\s*\d)", "Ein Jahr hat 52 Wochen und 1 Tag (im Schaltjahr 2 Tage).",
     "A year has 52 weeks and 1 day (2 in a leap year)."),
    (r"wie\s+viele\s+tage\s+(?:hat|haben)\s+(?:ein|das)\s+schaltjahr", "Ein Schaltjahr hat 366 Tage.", "A leap year has 366 days."),
    (r"(?:wie\s+oft|alle\s+wie\s+viele\s+jahre)\s+(?:gibt\s+es\s+)?(?:ein\s+)?schaltjahr", "Ein Schaltjahr gibt es meistens alle 4 Jahre "
     "(nicht in vollen Jahrhunderten, außer sie sind durch 400 teilbar, etwa 2000).", "There is usually a leap year every 4 years."),
)


_KALENDER_FUELL = r"(?:\s+(?:genau|eigentlich|normalerweise|insgesamt|denn|ungefähr|überhaupt))*"


def _kalender(t: str) -> Ergebnis | None:
    rest = re.sub(r"(?i)\b(?:und|sowie)\b", ".", t)
    teile = [x.strip(" ,;") for x in re.split(r"[.?!;]", rest) if x.strip(" ,;")]
    if not teile or len(teile) > 4:
        return None
    de, en = [], []
    for teil in teile:
        teil_h = teil if re.search(r"(?i)\b(?:hat|haben)\b", teil) else re.sub(r"(?i)^(wie\s+viele\s+\w+)\s+", r"\1 hat ", teil)
        for muster, satz_de, satz_en in _KALENDER:
            if re.fullmatch(rf"(?i)\s*{muster}{_KALENDER_FUELL}\s*", teil_h):
                if satz_de not in de:
                    de.append(satz_de)
                    en.append(satz_en)
                break
        else:
            return None
    return Ergebnis(" ".join(de), " ".join(en))


_NAME_A = r"((?-i:[A-ZÄÖÜ])[a-zäöüß]+)"
_ALTER = r"(\d{1,2})\s+jahre?(?:\s+und\s+(\d{1,3})\s+tage?)?"


def _altersvergleich(t: str) -> Ergebnis | None:
    m = re.search(rf"(?i){_NAME_A}\s+ist\s+{_ALTER}\s+alt\s*,?\s*(?:und\s+)?{_NAME_A}\s+(?:ist\s+)?{_ALTER}(?:\s+alt)?\s*\.\s*"
                  rf"{_NAME_A}\s+ist\s+also\s+(\d{{1,2}}|ein|zwei|drei)\s+jahre?\s+(älter|jünger)\s+als\s+{_NAME_A}", t)
    if not m:
        return None
    rahmen = r"[\s.?!:]*(?:(?:kann|könnte)\s+das\s+(?:wirklich\s+)?stimmen|stimmt\s+das(?:\s+wirklich)?)?[\s.?!:]*"
    if not re.search(r"(?i)\bstimm", t) or not re.fullmatch(rf"(?i){rahmen}", t[:m.start()]) or not re.fullmatch(rf"(?i){rahmen}", t[m.end():]):
        return None
    n1, j1, d1, n2, j2, d2, wer, diff, richtung, als = m.groups()
    alter = {n1: int(j1) * 365 + int(d1 or 0), n2: int(j2) * 365 + int(d2 or 0)}
    if wer not in alter or als not in alter or wer == als:
        return None
    diff = {"ein": 1, "zwei": 2, "drei": 3}.get(diff.lower(), None) or int(diff)
    unterschied = alter[wer] - alter[als]
    behauptet = diff * 365 * (1 if richtung.lower() == "älter" else -1)
    jahre = abs(unterschied) // 365
    tage = abs(unterschied) % 365
    wie = f"{jahre} Jahr{'e' if jahre != 1 else ''}" + (f" und {tage} Tag{'e' if tage != 1 else ''}" if tage else "")
    if unterschied == 0:
        wahr = f"{wer} und {als} sind gleich alt."
    else:
        wahr = f"{wer} ist {wie} {'älter' if unterschied > 0 else 'jünger'} als {als}."
    ungefaehr = unterschied != behauptet and unterschied * behauptet > 0 and jahre == diff
    if unterschied == behauptet:
        anfang_de, anfang_en = "Ja, das stimmt. ", "Yes. "
    elif ungefaehr:
        anfang_de, anfang_en = "Ja, in vollen Jahren stimmt das. Genau gerechnet: ", "Yes, in full years. Exactly: "
    else:
        anfang_de, anfang_en = "Nein, das stimmt nicht. ", "No. "

    def _alt(j: str, d: str | None) -> str:
        return f"{j} Jahr{'e' if j != '1' else ''}" + (f" und {d} Tag{'e' if d != '1' else ''}" if d else "")

    return Ergebnis(anfang_de + wahr + f"\n\n{n1} ist {_alt(j1, d1)} alt, {n2} {_alt(j2, d2)}.", anfang_en + wahr)


_NENNER = {"hälfte": 2, "drittel": 3, "viertel": 4, "fünftel": 5, "sechstel": 6, "achtel": 8, "zehntel": 10}
_ZAEHLER = {"ein": 1, "eine": 1, "die": 1, "zwei": 2, "drei": 3, "vier": 4}
_BRUCH = re.compile(r"(?i)\b(ein|eine|die|zwei|drei|vier|\d)\s+(hälfte|drittel|viertel|fünftel|sechstel|achtel|zehntel)\s+(?:davon|von\s+ihnen)\b")
_REST_FRAGE = re.compile(r"(?i)\b(?:noch|übrig\w*|bleib\w*|rest\w*|andere\w*|nicht)\b")


_NOCH_EIN_ANTEIL = re.compile(r"(?i)\b(?:hälfte|drittel|viertel|fünftel|sechstel|achtel|zehntel|prozent|doppelt\w*|halb\w*|dreifach\w*)\b|%|\bmal\s+so\b")
_FUELL = frozenset("wie viele viel sind ist es hat haben hatte hätte in im am an der die das den dem des ein eine einer einen und sie er ich du wir ihr man "
                   "dann also davon jetzt insgesamt denn eigentlich genau zusammen von mit für".split())


def _inhalt(satz: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", satz) if w.lower() not in _FUELL}


def _bruchteil(t: str) -> Ergebnis | None:
    b = _BRUCH.search(t)
    q = re.search(r"(?i)(?:^|[.!?:]\s*)(wie\s+viele\s+(\w+)[^.?!]*\?)\s*$", t)
    if not b or not q or len(_BRUCH.findall(t)) != 1 or _NOCH_EIN_ANTEIL.search(t[:b.start()] + " " + t[b.end():]):
        return None
    zahlen = [int(z) for z in re.findall(r"(?<![\d.,])\d{1,5}(?![\d.,])", t[:b.start()] + " " + t[b.end():])]
    if len(zahlen) != 1:
        return None
    n = zahlen[0]
    zaehler = _ZAEHLER.get(b.group(1).lower()) or int(b.group(1))
    nenner = _NENNER[b.group(2).lower()]
    if zaehler >= nenner or (n * zaehler) % nenner:
        return None
    teil = n * zaehler // nenner
    anfang = t.rfind(".", 0, b.start()) + 1
    ende = t.find(".", b.end())
    grund, bruchsatz = t[:anfang], t[anfang:ende if ende != -1 else len(t)]
    frage, wort = q.group(1), q.group(2)
    w_frage, w_bruch, w_grund = _inhalt(frage), _inhalt(bruchsatz), _inhalt(grund)
    if _REST_FRAGE.search(frage):
        rest = True
    elif w_frage & w_bruch:
        rest = False
    elif len(w_frage - w_grund) == 1 and w_frage & w_grund:
        rest = True
    else:
        return None
    name = b.group(1).capitalize() + " " + b.group(2).capitalize()
    weg = f"{name} von {n} ist {n} : {nenner} = {n // nenner}" + (f", mal {zaehler} = {teil}" if zaehler > 1 else "") + "."
    nomen = f" {wort}" if wort[:1].isupper() else ""
    if rest:
        return Ergebnis(f"{_t(n - teil)}{nomen}.\n\n{weg} Übrig bleiben {n} − {teil} = {_t(n - teil)}.",
                        f"{_t(n - teil)}. {teil} of {n} is the fraction; {n} − {teil} = {_t(n - teil)}.")
    return Ergebnis(f"{_t(teil)}{nomen}.\n\n{weg}", f"{_t(teil)}.")


_UHR = r"(?P<h>[01]?\d|2[0-3])[:.](?P<m>[0-5]\d)(?:\s*uhr)?"
_DAUER_SCHULE = (r"(?P<halb>eine\s+halbe\s+stunde|eineinhalb\s+stunden|anderthalb\s+stunden|eine\s+viertelstunde|eine\s+dreiviertelstunde)"
                 r"|(?=\d|eine?r?\s|zwei\s|drei\s)(?:(?P<std>\d{1,2}|eine|einer|zwei|drei)\s+stunden?)?(?:\s*(?:und\s+)?(?P<min>\d{1,3})\s+minuten?)?")
_HALB = {"eine halbe stunde": 30, "eineinhalb stunden": 90, "anderthalb stunden": 90, "eine viertelstunde": 15, "eine dreiviertelstunde": 45}
_STD_WORT = {"eine": 1, "einer": 1, "zwei": 2, "drei": 3}
_FRAGE_AN = re.compile(r"(?i)\b(?:wann|um\s+wie\s+viel\s+uhr)\b[^?]*\b(?:an|ankunft|ankommt|ankommen|da|dort|fertig|aus|zu\s+ende|vorbei|am\s+ziel|"
                       r"zu\s+hause|daheim)\s*\?\s*$")
_FRAGE_AB = re.compile(r"(?i)\b(?:wann|um\s+wie\s+viel\s+uhr)\b[^?]*\b(?:ab(?:fahren|fährt|fahrt)?|los(?:fahren|gehen)?|weg(?:fahren)?|aufbrechen|starten)\b[^?]*\?\s*$")


def _abfahrt_ankunft(t: str) -> Ergebnis | None:
    if re.search(r"(?i)\b(?:flug\w*|flieg\w*|fliegt|landet|landen|flugzeug\w*|nächste[nrs]?|naechste[nrs]?)\b", t):
        return None
    uhren = list(re.finditer(rf"(?i)\bum\s+{_UHR}", t))
    if len(uhren) != 1 or len(re.findall(r"\b\d{1,2}[:.]\d{2}\b", t)) != 1:
        return None
    dauer = [d for d in re.finditer(rf"(?i)\b(?:braucht|brauchen|dauert|dauern|ist\s+(?:\S+\s+){{0,3}}?unterwegs|fährt|fahren|geht|gehen|läuft|laufen)\s+(?:(?:er|sie|es|die\s+fahrt|der\s+weg)\s+)?(?:\S+\s+){{0,3}}?(?:{_DAUER_SCHULE})", t)
             if any(d.group(g) for g in ("std", "min", "halb"))]
    if len(dauer) != 1 or re.search(r"(?i)\b(?:verspät\w*|später|früher|pause|umsteig\w*|halt\w*|wartet?|warten)\b", t):
        return None
    d = dauer[0]
    tt = re.sub(r"(?<=\d)\.(?=\d)", ":", t)
    satz_uhr = tt.count(".", 0, uhren[0].start()) + tt.count("?", 0, uhren[0].start())
    satz_dauer = tt.count(".", 0, d.start()) + tt.count("?", 0, d.start())
    dauer_satz = tt[tt.rfind(".", 0, d.start()) + 1:d.end()]
    if re.search(r"(?i)\bzu[mr]\b", dauer_satz):
        return None
    if satz_dauer != satz_uhr and not re.match(r"(?i)\s*(?:er|sie|es|die\s+fahrt|die\s+reise|der\s+film|das\s+spiel)\b", dauer_satz):
        return None
    if d.group("halb"):
        minuten = _HALB[" ".join(d.group("halb").lower().split())]
    else:
        std = d.group("std")
        minuten = (_STD_WORT.get(std.lower(), 0) if std and not std.isdigit() else int(std or 0)) * 60 + int(d.group("min") or 0)
    if not 0 < minuten < 24 * 60:
        return None
    u = uhren[0]
    h, m = int(u.group("h")), int(u.group("m"))
    vor_der_uhr = t[:u.start()]
    ab = re.search(r"(?i)\b(?:fährt|fahren|startet|starten|geht|gehen|beginnt|beginnen|los)\b[^.?!]*$", vor_der_uhr) or \
        re.search(r"(?i)^[^.?!]*\b(?:ab|los|weg)\b", t[u.end():])
    an = re.search(r"(?i)\b(?:kommt|kommen|landet|landen|ist|sind)\b[^.?!]*$", vor_der_uhr) and re.search(r"(?i)^[^.?!]*\b(?:an|da)\b", t[u.end():])
    if ab and _FRAGE_AN.search(t) and not an:
        z = h * 60 + m + minuten
        richtung, satz_de = 1, "kommt"
    elif an and _FRAGE_AB.search(t) and not ab:
        z = h * 60 + m - minuten
        richtung, satz_de = -1, "muss"
    else:
        return None
    tag = "" if 0 <= z < 1440 else (" (am nächsten Tag)" if z >= 1440 else " (am Vortag)")
    zh, zm = divmod(z % 1440, 60)
    dauer_de = (f"{minuten // 60} Stunde{'n' if minuten // 60 != 1 else ''}" if minuten >= 60 else "") + \
        (" und " if minuten >= 60 and minuten % 60 else "") + (f"{minuten % 60} Minuten" if minuten % 60 else "")
    if richtung > 0:
        return Ergebnis(f"Um {zh}:{zm:02d} Uhr{tag}.\n\n{h}:{m:02d} Uhr plus {dauer_de} ist {zh}:{zm:02d} Uhr.",
                        f"At {zh}:{zm:02d}{tag}. {h}:{m:02d} plus {minuten} minutes is {zh}:{zm:02d}.")
    return Ergebnis(f"Um {zh}:{zm:02d} Uhr{tag}.\n\n{h}:{m:02d} Uhr minus {dauer_de} ist {zh}:{zm:02d} Uhr.",
                    f"At {zh}:{zm:02d}{tag}. {h}:{m:02d} minus {minuten} minutes is {zh}:{zm:02d}.")


_FOLGE_FRAGE = re.compile(r"(?i)\b(?:nächste\w*|naechste\w*|weiter|fort(?:setzen|setzung|gesetzt)?|setze\w*|folgt|folgende\w*|reihe|folge|zahlenfolge|zahlenreihe)\b")


_FOLGE_FORM = re.compile(r"(?i)\s*(?:(?:welche|was\s+für\s+eine)\s+zahl\s+(?:kommt\s+(?:als\s+)?(?:nächstes|nächste|naechstes|danach|dann)|folgt)"
                         r"|(?:bitte\s+)?(?:setze?|ergänze?|ergaenze?)\s+(?:die\s+)?(?:zahlen)?(?:folge|reihe)?(?:\s+fort)?"
                         r"|wie\s+geht\s+(?:die|diese|es)\s*(?:zahlen)?(?:folge|reihe)?\s+weiter)\s*[:?.]?\s*#\s*(?:fort)?\s*[.?!…]*\s*"
                         r"|\s*#\s*[,.…]*\s*(?:welche\s+zahl\s+kommt\s+als\s+nächstes|wie\s+geht\s+es\s+weiter)\s*\??\s*")


def _zahlenfolge(t: str) -> Ergebnis | None:
    if not _FOLGE_FRAGE.search(t):
        return None
    m = re.search(r"(-?\d{1,6}(?:\s*[,;]\s*-?\d{1,6}){3,9})\s*(?:[,;]\s*)?(?:\.{3}|…|_+|\?)?", t)
    if not m or re.search(r"\d", t[:m.start()] + t[m.end():]):
        return None
    if not _FOLGE_FORM.fullmatch(t[:m.start()] + " # " + t[m.end():]):
        return None
    z = [int(x) for x in re.split(r"\s*[,;]\s*", m.group(1))]
    d = [b - a for a, b in zip(z, z[1:])]
    letzte = z[-1]
    if len(set(d)) == 1 and d[0] != 0:
        n = letzte + d[0]
        regel = (f"Es kommt jedes Mal {d[0]} dazu: {_t(letzte)} + {d[0]} = {_t(n)}." if d[0] > 0
                 else f"Es wird jedes Mal {-d[0]} weniger: {_t(letzte)} − {-d[0]} = {_t(n)}.")
        en = f"Each time {d[0]:+d}: {letzte} {'+' if d[0] > 0 else '−'} {abs(d[0])} = {n}."
    elif 0 not in z and all(b % a == 0 for a, b in zip(z, z[1:])) and len({b // a for a, b in zip(z, z[1:])}) == 1 and z[1] // z[0] > 1:
        k = z[1] // z[0]
        n = letzte * k
        regel, en = f"Jede Zahl wird mal {k} genommen: {_t(letzte)} · {k} = {_t(n)}.", f"Each number times {k}: {letzte} × {k} = {n}."
    elif 0 not in z and all(a % b == 0 for a, b in zip(z, z[1:])) and len({a // b for a, b in zip(z, z[1:])}) == 1 and z[0] // z[1] > 1 \
            and letzte % (z[0] // z[1]) == 0:
        k = z[0] // z[1]
        n = letzte // k
        regel, en = f"Jede Zahl wird durch {k} geteilt: {_t(letzte)} : {k} = {_t(n)}.", f"Each number divided by {k}: {letzte} ÷ {k} = {n}."
    elif (len(z) >= 5 or all(x >= 0 and round(x ** 0.5) ** 2 == x for x in z)) and len({b - a for a, b in zip(d, d[1:])}) == 1 and d[1] != d[0]:
        dd = d[1] - d[0]
        schritt = d[-1] + dd
        n = letzte + schritt
        regel = (f"Der Abstand wird jedes Mal um {abs(dd)} {'größer' if dd > 0 else 'kleiner'} ({', '.join(str(x) for x in d)}, dann {schritt}): "
                 f"{_t(letzte)} {'+' if schritt >= 0 else '−'} {abs(schritt)} = {_t(n)}.")
        en = f"The gap changes by {dd:+d} each time: {letzte} + {schritt} = {n}."
    else:
        return None
    return Ergebnis(f"Die nächste Zahl ist {_t(n)}.\n\n{regel}", f"The next number is {n}. {en}")


_LAENGE = r"(\d{1,4}(?:,\d{1,2})?)\s*(mm|cm|dm|m|km)\b"


def _rechteck(t: str) -> Ergebnis | None:
    from fractions import Fraction
    form = re.search(r"(?i)\b(rechteck\w*|quadrat(?!meter|zentimeter|kilometer|dezimeter|millimeter|zahl|wurzel)\w*)\b", t)
    umfang, flaeche = re.search(r"(?i)\bumfang\b", t), re.search(r"(?i)\b(?:fläche\w*|flaeche\w*|flächeninhalt)\b", t)
    if not form or not (umfang or flaeche) or re.search(r"(?i)\b(?:kreis|dreieck|würfel|quader|volumen|prozent|kostet|preis|€|euro|diagonale\w*|"
                                                         r"verdoppel\w*|halbier\w*|vergrößer\w*|verkleiner\w*|maßstab\w*|doppelt\w*|dreimal|wenn)\b", t):
        return None
    if re.search(r"(?i)\b(?:umfang|fläche\w*|flaeche\w*|flächeninhalt)\b\s*(?:von|beträgt|betraegt|ist|hat|misst|=|:)?\s*(?:\S+\s+){0,2}?\d", t):
        return None
    masse = re.findall(rf"(?i){_LAENGE}", t)
    if not masse or len({e.lower() for _z, e in masse}) != 1:
        return None
    e = masse[0][1].lower()
    zahlen = [Fraction(z.replace(",", ".")) for z, _e in masse]
    quadrat = form.group(1).lower().startswith("quadrat")
    if quadrat and len(zahlen) == 1:
        a = b = zahlen[0]
    elif not quadrat and len(zahlen) == 2 and re.search(r"(?i)\b(?:lang|länge|breit|breite|seite\w*|mal)\b", t):
        a, b = zahlen
    else:
        return None
    def z(x):
        return _t(int(x)) if x.denominator == 1 else str(float(x)).replace(".", ",")
    teile_de, teile_en = [], []
    name = "Quadrats" if quadrat else "Rechtecks"
    if umfang:
        u = 2 * (a + b)
        teile_de.append(f"Der Umfang des {name} ist {z(u)} {e}: " + (f"4 · {z(a)} {e} = {z(u)} {e}." if quadrat else
                        f"2 · ({z(a)} {e} + {z(b)} {e}) = 2 · {z(a + b)} {e} = {z(u)} {e}."))
        teile_en.append(f"Perimeter: {z(u)} {e}.")
    if flaeche:
        f = a * b
        teile_de.append(f"Die Fläche ist {z(f)} {e}²: {z(a)} {e} · {z(b)} {e} = {z(f)} {e}².")
        teile_en.append(f"Area: {z(f)} {e}².")
    return Ergebnis("\n".join(teile_de), " ".join(teile_en))
