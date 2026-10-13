# SPDX-License-Identifier: AGPL-3.0-or-later
import random
import re
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurse
import rechnen

N = " "


def _primteiler(n):
    p, r = 2, []
    while n > 1:
        while n % p == 0:
            r.append(p)
            n //= p
        p += 1
    return r


FRAGEN = [
    ("2x + 6 = 20", ["x = 7.", "Minus 6 auf beiden Seiten: 2x = 14", "Durch 2 teilen: x = 14 ÷ 2 = 7", "Probe"], ["x = 7.", "Subtract 6 on both sides: 2x = 14", "Divide by 2"]),
    ("3(x - 2) = 12", ["x = 6.", "Zusammengefasst: 3x - 6 = 12", "Plus 6 auf beiden Seiten: 3x = 18"], ["Simplified: 3x - 6 = 12", "Add 6 on both sides"]),
    ("x/4 = 5", ["x = 20."], ["x = 20."]),
    ("5x = 2x + 9", ["x = 3.", "Minus 2x auf beiden Seiten: 3x = 9"], ["Subtract 2x on both sides: 3x = 9"]),
    ("x² - 5x + 6 = 0", ["x₁ = 3 und x₂ = 2.", "D = b² - 4ac = 25 - 24 = 1", "(5 ± 1) / 2"], ["x₁ = 3 and x₂ = 2.", "Discriminant"]),
    ("löse 0,5x + 2 = 7", ["x = 10."], ["x = 10."]),
    ("Wie groß ist x, wenn 3x - 4 = 11?", ["x = 5."], ["x = 5."]),
    ("What is x if 3x - 4 = 11?", ["x = 5."], ["x = 5."]),
    ("Löse 2y - 7 = 15", ["y = 11."], ["y = 11."]),
    ("3x = 10", ["x = 10/3 (rund 3,3333)."], ["x = 10/3 (about 3.3333)."]),
    ("2x + 3 = 2x + 5", ["keine Lösung"], ["no solution"]),
    ("2(x+1) = 2x + 2", ["jedes x ist eine Lösung"], ["every x is a solution"]),
    ("x^2 = 2", ["x₁ = rund 1,4142 und x₂ = rund -1,4142."], ["x₁ = about 1.4142 and x₂ = about -1.4142."]),
    ("x² + 1 = 0", ["keine (reelle) Lösung"], ["no real solution"]),
    ("x² + 2x + 1 = 0", ["x = -1."], ["x = -1."]),
    ("(x+1)(x-1) = 0", ["x₁ = 1 und x₂ = -1."], ["x₁ = 1 and x₂ = -1."]),
    ("2x = 4x - 8", ["x = 4.", "Durch (-2) teilen"], ["x = 4."]),
    ("1/2x + 1/3 = 5", ["x = 28/3 (rund 9,3333)."], ["x = 28/3 (about 9.3333)."]),
    ("-2x + 4 = 10", ["x = -3."], ["x = -3."]),
]


@pytest.mark.parametrize("frage,de,en", FRAGEN)
def test_fragen(frage, de, en):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in de:
        assert teil in r.de, (frage, teil, r.de)
    for teil in en:
        assert teil in r.en, (frage, teil, r.en)


@pytest.mark.parametrize("text", [
    "3 x 4 = 12", "1 m = 100 cm", "x = 5", "2 + 3 = 5", "x^3 = 8", "xy = 6", "2x + 3y = 7", "1/x = 2", "sqrt(x) = 3", "Wo ist x = 5 in meinem Garten", "x² + x = x² + 3",
    "2x + 6 =", "= 20", "a + b = c", "Der Kurs ist 5 = 5", "x ist 3 = x", "x2 = 4", "5 % von x = 3", "x = y", "100 EUR = USD",
])
def test_keine_gleichung(text):
    assert rechnen.loesen(text) is None or "Rechenweg" not in rechnen.loesen(text).de, text


def test_zufaellige_lineare_gegenprobe():
    rnd = random.Random(20261011)
    pruefte = 0
    for _ in range(1500):
        a, b, c, d = (rnd.randint(-30, 30) for _ in range(4))
        if a == c:
            continue
        erwartet = Fraction(d - b, a - c)

        def glied(k, v):
            return f"{k}{v}" if k not in (1, -1) else ("-" if k == -1 else "") + v

        links = f"{glied(a, 'x')} + {b}" if a else f"{b}"
        rechts = f"{glied(c, 'x')} + {d}" if c else f"{d}"
        text = f"{links} = {rechts}".replace("+ -", "- ")
        r = rechnen.loesen(text)
        assert r is not None, text
        kopf = r.de.split("\n")[0]
        if erwartet.denominator == 1:
            assert kopf == f"x = {erwartet.numerator}.", (text, kopf)
        elif set(str(erwartet.denominator)) and all(p in (2, 5) for p in _primteiler(erwartet.denominator)):
            dezimal = rechnen.zahl_text(erwartet)
            assert kopf == f"x = {dezimal}.", (text, kopf)
        else:
            assert kopf.startswith(f"x = {erwartet.numerator}/{erwartet.denominator} (rund "), (text, kopf)
        assert "Probe" in r.de
        pruefte += 1
    assert pruefte > 1300


def test_zufaellige_quadratische_gegenprobe():
    rnd = random.Random(7)
    for _ in range(800):
        x1, x2 = rnd.randint(-12, 12), rnd.randint(-12, 12)
        a = rnd.choice([1, 2, 3, -1])
        b, c = -a * (x1 + x2), a * x1 * x2
        text = re.sub(r"(?<![\d])1x", "x", f"{a}x² + {b}x + {c} = 0".replace("+ -", "- "))
        r = rechnen.loesen(text)
        assert r is not None, text
        kopf = r.de.split("\n")[0]
        if x1 == x2:
            assert kopf == f"x = {x1}.", (text, kopf)
        else:
            assert kopf == f"x₁ = {max(x1, x2)} und x₂ = {min(x1, x2)}.", (text, kopf)


@pytest.mark.parametrize("text,erwartet", [
    ("1,5 Mio Euro", "1500000 Euro"), ("2 Mrd", "2000000000"), ("3 Tsd", "3000"), ("2k", "2000"), ("1.5k", "1500"), ("2,5 Millionen", "2500000"), ("3 Tausend", "3000"),
    ("1 Milliarde", "1000000000"), ("0,5 Mio", "500000"), ("5 km", "5 km"), ("20 K in °C", "20 K in °C"), ("5k", "5000"), ("100 Euro", "100 Euro"),
    ("1,2345678 Mio", "1,2345678 Mio"), ("15.12.2026", "15.12.2026"), ("Mio", "Mio"), ("a2k", "a2k"),
])
def test_kurzformen(text, erwartet):
    assert rechnen.kurzformen(text) == erwartet


def test_kurzformen_in_aufgaben():
    assert "= 6" in rechnen.loesen("3 Mio durch 500 Tsd").de
    assert rechnen.loesen("2 Mrd + 500 Mio").de.endswith("2" + N + "500" + N + "000" + N + "000.")
    f = kurse.erkennen("1,5 Mio Euro in Dollar")
    assert f is not None and f.betrag == 1500000 and f.von == "EUR" and f.nach == ("USD",)
    f = kurse.erkennen("2k Dollar in Euro")
    assert f is not None and f.betrag == 2000 and f.von == "USD"
    assert kurse.erkennen("1.5 million Euro in Dollar").betrag == 1500000
