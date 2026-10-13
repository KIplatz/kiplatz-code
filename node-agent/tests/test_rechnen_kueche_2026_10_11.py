# SPDX-License-Identifier: AGPL-3.0-or-later
import math
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rechnen
import rechnen_kueche as rk

FRAGEN = [
    ("Rezept für 4 auf 6 Personen: 200 g Mehl, 3 Eier, 1/2 l Milch", ["Faktor 1,5", "200 g Mehl → 300 g Mehl", "3 Eier → 4,5 Eier", "0,5 l Milch → 0,75 l Milch", "Eier oder Zwiebeln"],
     ["factor 1.5", "3 Eier → 4.5 Eier"]),
    ("Rezept für 4 Personen umrechnen auf 10: 500 g Mehl, 2 EL Öl und Zucker", ["Faktor 2,5", "500 g Mehl → 1250 g Mehl (1,25 kg)", "2 EL Öl → 5 EL Öl", "Zucker: ohne Mengenangabe"], ["(1.25 kg)"]),
    ("Für 2 Personen statt 4: 250 g Reis, 1 Zwiebel", ["Rezept von 4 auf 2 Personen (Faktor 0,5)", "250 g Reis → 125 g Reis"], ["Recipe from 4 to 2 people"]),
    ("Rechne das Rezept für 6 auf 4 Personen um: 1,5 kg Kartoffeln; 3 Zwiebeln", ["1,5 kg Kartoffeln → 1 kg Kartoffeln", "3 Zwiebeln → 2 Zwiebeln"], ["1.5 kg Kartoffeln → 1 kg Kartoffeln"]),
    ("2 EL Mehl in Gramm", ["2 EL Mehl sind ungefähr 16 g", "1 EL Mehl ≈ 7,8 g"], ["2 tbsp flour is about 16 g"]),
    ("1 Tasse Zucker in g", ["1 Tasse Zucker sind ungefähr 213 g"], ["1 cup sugar is about 213 g"]),
    ("100 g Butter in EL", ["sind ungefähr 7 EL"], ["about 7 tbsp"]),
    ("250 ml Milch in Tassen", ["250 ml Milch sind 1 Tasse", "US-Cup hat 240 ml"], ["is 1 cup"]),
    ("3 TL in EL", ["3 TL sind 1 EL", "1 EL = 3 TL"], ["3 tsp is 1 tbsp"]),
    ("1 Tasse in ml", ["1 Tasse sind 250 ml"], ["1 cup is 250 ml"]),
    ("Wie viel Gramm sind 2 EL Honig?", ["2 EL Honig sind ungefähr 42 g"], ["2 tbsp honey is about 42 g"]),
    ("wie viel ml sind 2 EL", ["2 EL sind 30 ml"], ["2 tbsp is 30 ml"]),
    ("1,5 Tassen Mehl in Gramm", ["1,5 Tassen Mehl sind ungefähr 195 g"], ["1.5 cups flour is about 195 g"]),
    ("1 cup flour in grams", ["1 Cup Mehl sind ungefähr 125 g"], ["1 cup flour is about 125 g"]),
    ("½ Tasse Zucker in g", ["0,5 Tassen Zucker sind ungefähr 106 g"], ["0.5 cups sugar is about 106 g"]),
    ("2 Tassen Wasser in ml", ["2 Tassen Wasser sind 500 ml"], ["2 cups water is 500 ml"]),
]


@pytest.mark.parametrize("frage,de,en", FRAGEN)
def test_fragen(frage, de, en):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in de:
        assert teil in r.de.replace("\u00a0", ""), (frage, teil, r.de)
    for teil in en:
        assert teil in r.en, (frage, teil, r.en)


def test_dichte_rechnung_stimmt():
    for namen, de, en, dichte in rk.ZUTATEN:
        r = rechnen.loesen(f"150 g {namen[0]} in EL")
        assert r is not None, namen
        el = Fraction(150) / (dichte * 15)
        erwartet = rk._gerundet(el)
        assert f"sind ungefähr {erwartet} EL" in r.de.replace("\u00a0", ""), (namen, r.de, erwartet)


def test_zufaellige_rezepte_gegenprobe():
    import random
    rnd = random.Random(17)
    for _ in range(300):
        a, b = rnd.randint(1, 12), rnd.randint(1, 12)
        if a == b:
            continue
        g = rnd.randint(1, 50) * 10
        n = rnd.randint(1, 9)
        r = rechnen.loesen(f"Rezept für {a} auf {b} Personen: {g} g Mehl, {n} Eier")
        assert r is not None
        f = Fraction(b, a)
        mehl = g * f
        zeile = [x for x in r.de.split("\n") if x.startswith(f"{g} g Mehl")][0]
        assert zeile == f"{g} g Mehl → {rk._rund(mehl)} g Mehl" + (f" ({rk._rund(mehl / 1000)} kg)" if mehl >= 1000 else ""), zeile
        ei = [x for x in r.de.split("\n") if x.startswith(f"{n} Eier")][0]
        assert ei == f"{n} Eier → {rk._rund(n * f)} Eier", ei
        assert ("Eier oder Zwiebeln" in r.de) == ((n * f).denominator != 1)


@pytest.mark.parametrize("text", [
    "2 EL Mehl", "Wie backe ich einen Kuchen für 6 Personen", "Rezept für 4 Personen", "Rezept für 4 Personen: Mehl", "Rezept für 4 auf 4 Personen: 200 g Mehl", "Rezept für 0 auf 4 Personen: 200 g Mehl",
    "1 Tasse Kaffee in ml", "250 g Schokolade in EL", "5 ml in l", "500 g in kg", "2 EL Mehl in Wolken", "Für 4 Personen statt 6: ", "Rezept für 4 auf 6 Personen: " + "200 g Mehl, " * 40 + "1 Ei",
])
def test_keine_kuechenaufgabe(text):
    r = rechnen.loesen(text)
    assert r is None or ("Rezept von" not in r.de and "ungefähr" not in r.de), (text, r and r.de)
