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
    for stufe in (_umkehr, _beine, _reihenfolge, _fehler_division):
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
