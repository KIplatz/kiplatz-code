# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from fractions import Fraction

from rechnen import Ergebnis, _Nein, bruch_text, zahl_lesen, zahl_text

_TOKEN = re.compile(r"\s*(?:(?P<z>\d+(?:[.,]\d+)*)|(?P<w>[A-Za-zÄÖÜäöüß]+)|(?P<o>[+\-*/^()=×·÷:−–²³]))")
_VOR = [
    r"(?:bitte\s+)?(?:l[öo]se|berechne|bestimme|ermittle|finde|rechne|solve)\s+(?:mir\s+)?(?:die\s+|diese\s+|the\s+)?(?:gleichung|equation)?\s*(?:nach\s+[xyz]\s+)?(?:auf\s*)?(?:für\s+[xyz]\s*)?:?\s*",
    r"(?:bitte\s+)?(?:wie\s+(?:groß|gross)|was|wieviel|wie\s+viel)\s+(?:ist|ergibt|beträgt)\s+[xyz]\s*,?\s*(?:wenn|falls|bei|if)\s+",
    r"(?:für\s+welches|bei\s+welchem|welches)\s+[xyz]\s+(?:gilt|ist|stimmt)\s+",
    r"(?:what\s+is|find|solve\s+for|for\s+what)\s+[xyz]\s*(?:if|when|in|such\s+that)?\s*:?\s*",
    r"(?:gleichung|equation)\s*:?\s*",
]


def _poly(*terme: tuple[int, Fraction]) -> dict[int, Fraction]:
    p: dict[int, Fraction] = {}
    for g, k in terme:
        p[g] = p.get(g, Fraction(0)) + k
    return {g: k for g, k in p.items() if k}


def _add(a, b, vz=1):
    r = dict(a)
    for g, k in b.items():
        r[g] = r.get(g, Fraction(0)) + vz * k
    return {g: k for g, k in r.items() if k}


def _mul(a, b):
    r: dict[int, Fraction] = {}
    for g1, k1 in a.items():
        for g2, k2 in b.items():
            if g1 + g2 > 2:
                raise _Nein
            r[g1 + g2] = r.get(g1 + g2, Fraction(0)) + k1 * k2
    return {g: k for g, k in r.items() if k}


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], var: str):
        self.t, self.i, self.var = tokens, 0, var

    def spitz(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def ausdruck(self):
        p = self.term()
        while self.spitz()[1] in ("+", "-", "−", "–"):
            op = self.t[self.i][1]
            self.i += 1
            q = self.term()
            p = _add(p, q, 1 if op == "+" else -1)
        return p

    def _faktor_folgt(self) -> bool:
        art, w = self.spitz()
        return art in ("z", "v") or w == "("

    def term(self):
        p = self.unaer()
        while True:
            art, w = self.spitz()
            if w in ("*", "×", "·"):
                self.i += 1
                p = _mul(p, self.unaer())
            elif w in ("/", "÷", ":"):
                self.i += 1
                q = self.unaer()
                if set(q) - {0} or 0 not in q:
                    raise _Nein
                p = {g: k / q[0] for g, k in p.items()}
            elif self._faktor_folgt():
                p = _mul(p, self.unaer())
            else:
                return p

    def unaer(self):
        art, w = self.spitz()
        if w in ("-", "−", "–"):
            self.i += 1
            return {g: -k for g, k in self.unaer().items()}
        if w == "+":
            self.i += 1
            return self.unaer()
        return self.potenz()

    def potenz(self):
        p = self.atom()
        art, w = self.spitz()
        if w == "^":
            self.i += 1
            art, e = self.spitz()
            if art != "z" or not e.isdigit():
                raise _Nein
            self.i += 1
            n = int(e)
            if n > 2:
                raise _Nein
            r = {0: Fraction(1)}
            for _ in range(n):
                r = _mul(r, p)
            return r
        if w in ("²", "³"):
            self.i += 1
            if w == "³":
                raise _Nein
            return _mul(p, p)
        return p

    def atom(self):
        art, w = self.spitz()
        if art == "z":
            self.i += 1
            return {0: zahl_lesen(w)} if zahl_lesen(w) else {}
        if art == "v":
            self.i += 1
            return {1: Fraction(1)}
        if w == "(":
            self.i += 1
            p = self.ausdruck()
            if self.spitz()[1] != ")":
                raise _Nein
            self.i += 1
            return p
        raise _Nein


def _lesen(seite: str, var: str) -> dict[int, Fraction]:
    tokens, pos = [], 0
    seite = seite.strip()
    while pos < len(seite):
        m = _TOKEN.match(seite, pos)
        if not m:
            raise _Nein
        pos = m.end()
        if m.group("z"):
            tokens.append(("z", m.group("z")))
        elif m.group("w"):
            if m.group("w").lower() != var:
                raise _Nein
            tokens.append(("v", var))
        else:
            tokens.append(("o", m.group("o")))
    for (a1, w1), (a2, w2) in zip(tokens, tokens[1:]):
        if a1 == "v" and a2 == "z":
            raise _Nein
    p = _Parser(tokens, var)
    if not tokens:
        raise _Nein
    erg = p.ausdruck()
    if p.i != len(tokens):
        raise _Nein
    return erg


_HOCH = {0: "", 1: "", 2: "²"}


def _koeff(k: Fraction, g: int, var: str, erster: bool, en: bool) -> str:
    vz = "-" if k < 0 else "+"
    a = abs(k)
    if g == 0:
        zahl = zahl_text(a, en) if a.denominator == 1 or _terminiert(a) else bruch_text(a)
    else:
        zahl = "" if a == 1 else (zahl_text(a, en) if a.denominator == 1 or _terminiert(a) else f"({bruch_text(a)})")
    glied = f"{zahl}{var}{_HOCH[g]}" if g else zahl
    if erster:
        return ("-" if k < 0 else "") + glied
    return f" {vz} {glied}"


def _terminiert(a: Fraction) -> bool:
    n = a.denominator
    for p in (2, 5):
        while n % p == 0:
            n //= p
    return n == 1


def _text(p: dict[int, Fraction], var: str, en: bool) -> str:
    if not p:
        return "0"
    s = ""
    for g in sorted(p, reverse=True):
        s += _koeff(p[g], g, var, not s, en)
    return s


def _wert(x: Fraction, en: bool) -> str:
    if _terminiert(x):
        return zahl_text(x, en)
    return f"{bruch_text(x)} ({'about' if en else 'rund'} {zahl_text(x, en)})"


def _auswerten(p: dict[int, Fraction], x: Fraction) -> Fraction:
    return sum((k * x ** g for g, k in p.items()), Fraction(0))


def _wurzel(d: Fraction) -> tuple[Fraction, bool]:
    zn, nn = d.numerator, d.denominator
    zr, nr = math.isqrt(zn), math.isqrt(nn)
    if zr * zr == zn and nr * nr == nn:
        return Fraction(zr, nr), True
    return Fraction(math.isqrt(zn * nn * 10 ** 24), nn * 10 ** 12), False


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split())
    if "=" not in t or t.count("=") != 1 or len(t) > 140:
        return None
    s = re.sub(r"[\s?!]+$", "", t)
    s = re.sub(r"(?<=[\d)a-zA-Z²])[.]+$", "", s)
    for muster in _VOR:
        neu = re.sub(rf"^{muster}", "", s, count=1, flags=re.I)
        if neu != s:
            s = neu
            break
    s = re.sub(r",\s*$", "", s).strip()
    buchstaben = set(re.findall(r"[A-Za-zÄÖÜäöüß]+", s))
    if len(buchstaben) != 1:
        return None
    var = next(iter(buchstaben)).lower()
    if var not in ("x", "y", "z") or len(next(iter(buchstaben))) != 1:
        return None
    if re.search(r"\d\s+[xX×]\s+\d", s):
        return None
    if s.count("=") != 1:
        return None
    try:
        links_t, rechts_t = (x.strip() for x in s.split("="))
        if not links_t or not rechts_t:
            return None
        links, rechts = _lesen(links_t, var), _lesen(rechts_t, var)
    except (_Nein, ValueError, ZeroDivisionError, RecursionError):
        return None
    if (1 not in links and 2 not in links and 1 not in rechts and 2 not in rechts):
        return None
    if re.fullmatch(rf"{var}", links_t, re.I) and not re.search(rf"{var}", rechts_t, re.I) and re.fullmatch(r"[\d.,\s]+", rechts_t):
        return None
    diff = _add(links, rechts, -1)
    grad = max(diff) if diff else 0
    if grad == 1 and (2 in links or 2 in rechts):
        return None
    zeilen_de: list[str] = []
    zeilen_en: list[str] = []

    def z(de: str, en: str | None = None) -> None:
        zeilen_de.append(de)
        zeilen_en.append(en if en is not None else de)

    gl_text = f"{_text(links, var, False)} = {_text(rechts, var, False)}"
    gl_en = f"{_text(links, var, True)} = {_text(rechts, var, True)}"
    eingabe_gleich = re.sub(r"\s+", "", s.replace(",", ".")) == re.sub(r"\s+", "", gl_text.replace(",", ".").replace("²", "^2"))
    if grad == 0:
        if not diff:
            return Ergebnis(f"{gl_text}: Beide Seiten sind immer gleich, jedes {var} ist eine Lösung.",
                            f"{gl_en}: Both sides are always equal, every {var} is a solution.")
        return Ergebnis(f"{gl_text}: Das geht nie auf, es gibt keine Lösung.", f"{gl_en}: This never holds, there is no solution.")
    if grad == 1:
        a_l, a_r = links.get(1, Fraction(0)), rechts.get(1, Fraction(0))
        b_l, b_r = links.get(0, Fraction(0)), rechts.get(0, Fraction(0))
        z(f"Gleichung: {s}", f"Equation: {s}")
        if not eingabe_gleich:
            z(f"Zusammengefasst: {gl_text}", f"Simplified: {gl_en}")
        a = a_l - a_r
        b = b_r - b_l
        akt_l, akt_r = dict(links), dict(rechts)
        if a_r:
            akt_l = _add(links, {1: a_r}, -1)
            akt_r = _add(rechts, {1: a_r}, -1)
            z(f"{_op(a_r, var + '', 'de')} auf beiden Seiten: {_text(akt_l, var, False)} = {_text(akt_r, var, False)}",
              f"{_op(a_r, var + '', 'en')} on both sides: {_text(akt_l, var, True)} = {_text(akt_r, var, True)}")
        if akt_l.get(0):
            c = akt_l[0]
            akt_l = _add(akt_l, {0: c}, -1)
            akt_r = _add(akt_r, {0: c}, -1)
            z(f"{_op(c, '', 'de')} auf beiden Seiten: {_text(akt_l, var, False)} = {_text(akt_r, var, False)}",
              f"{_op(c, '', 'en')} on both sides: {_text(akt_l, var, True)} = {_text(akt_r, var, True)}")
        x = b / a
        if a != 1:
            z(f"Durch {_klammer(a)} teilen: {var} = {_g(b)} ÷ {_klammer(a)} = {_wert(x, False)}",
              f"Divide by {_klammer(a, True)}: {var} = {_g(b, True)} ÷ {_klammer(a, True)} = {_wert(x, True)}")
        lw, rw = _auswerten(links, x), _auswerten(rechts, x)
        if lw != rw:
            return None
        z(f"Probe: Mit {var} = {_wert(x, False)} ist die linke Seite {_wert(lw, False)} und die rechte auch. ✓",
          f"Check: with {var} = {_wert(x, True)} the left side is {_wert(lw, True)} and so is the right side. ✓")
        kopf_de = f"{var} = {_wert(x, False)}"
        kopf_en = f"{var} = {_wert(x, True)}"
    else:
        a, b, c = diff.get(2, Fraction(0)), diff.get(1, Fraction(0)), diff.get(0, Fraction(0))
        z(f"Gleichung: {s}", f"Equation: {s}")
        if re.sub(r"[\s]+", "", s.replace(",", ".").replace("²", "^2")) != re.sub(r"[\s]+", "", f"{_text(diff, var, False)}=0".replace(",", ".").replace("²", "^2")):
            z(f"Alles auf eine Seite: {_text(diff, var, False)} = 0", f"Everything on one side: {_text(diff, var, True)} = 0")
        z(f"a = {_g(a)}, b = {_g(b)}, c = {_g(c)}", f"a = {_g(a, True)}, b = {_g(b, True)}, c = {_g(c, True)}")
        d = b * b - 4 * a * c
        vier = 4 * a * c
        z(f"Diskriminante: D = b² - 4ac = {_g(b * b)} {'-' if vier >= 0 else '+'} {_g(abs(vier))} = {_g(d)}",
          f"Discriminant: D = b² - 4ac = {_g(b * b, True)} {'-' if vier >= 0 else '+'} {_g(abs(vier), True)} = {_g(d, True)}")
        if d < 0:
            z("D ist kleiner als 0: Es gibt keine (reelle) Lösung.", "D is less than 0: there is no real solution.")
            return Ergebnis("Rechenweg:\n" + "\n".join(zeilen_de), "Working:\n" + "\n".join(zeilen_en))
        w, genau = _wurzel(d)
        if not genau:
            w = Fraction(round(w * 10 ** 6), 10 ** 6)
        xs = sorted({(-b + w) / (2 * a), (-b - w) / (2 * a)}, reverse=True) if d else [(-b) / (2 * a)]
        if not genau:
            xs = [Fraction(round(x * 10 ** 4), 10 ** 4) for x in xs]
        wurzel_de = zahl_text(w) if genau else f"rund {zahl_text(Fraction(round(w * 10 ** 4), 10 ** 4))}"
        wurzel_en = zahl_text(w, True) if genau else f"about {zahl_text(Fraction(round(w * 10 ** 4), 10 ** 4), True)}"
        if d:
            z(f"x = (-b ± √D) / 2a = ({zahl_text(-b)} ± {wurzel_de}) / {zahl_text(2 * a)}", f"x = (-b ± √D) / 2a = ({zahl_text(-b, True)} ± {wurzel_en}) / {zahl_text(2 * a, True)}")
        else:
            z("D = 0: Es gibt genau eine Lösung, x = -b / 2a.", "D = 0: there is exactly one solution, x = -b / 2a.")
        if genau and any(_auswerten(diff, x) != 0 for x in xs):
            return None
        z("Probe: Eingesetzt wird jede Lösung 0. ✓" if genau else "Probe: Mit den gerundeten Werten ist das Ergebnis fast 0. ✓",
          "Check: each solution gives 0. ✓" if genau else "Check: with the rounded values the result is almost 0. ✓")
        if len(xs) == 1:
            kopf_de, kopf_en = f"{var} = {_wert(xs[0], False)}", f"{var} = {_wert(xs[0], True)}"
        else:
            rd, re_ = ("", "") if genau else ("rund ", "about ")
            kopf_de = f"{var}₁ = {rd}{_wert(xs[0], False)} und {var}₂ = {rd}{_wert(xs[1], False)}"
            kopf_en = f"{var}₁ = {re_}{_wert(xs[0], True)} and {var}₂ = {re_}{_wert(xs[1], True)}"
    return Ergebnis(f"{kopf_de}.\nRechenweg:\n" + "\n".join(zeilen_de), f"{kopf_en}.\nWorking:\n" + "\n".join(zeilen_en))


def _g(k: Fraction, en: bool = False) -> str:
    return zahl_text(k, en) if _terminiert(k) else bruch_text(k)


def _klammer(a: Fraction, en: bool = False) -> str:
    t = _g(a, en)
    return f"({t})" if a < 0 or "/" in t else t


def _op(k: Fraction, var: str, sprache: str) -> str:
    betrag = _g(abs(k), sprache == "en") if (abs(k) != 1 or not var) else ""
    wort = ("Minus" if sprache == "de" else "Subtract") if k > 0 else ("Plus" if sprache == "de" else "Add")
    return f"{wort} {betrag}{var}".strip()
