# SPDX-License-Identifier: AGPL-3.0-or-later
import random
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, getcontext
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rechnen

getcontext().prec = 60
N = " "


def _euro(text: str) -> Decimal:
    m = re.search(r"(\d[\d ]*(?:,\d+)?)\s*€", text)
    return Decimal(m.group(1).replace(N, "").replace(",", "."))


def _cent(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


FRAGEN = [
    ("5.000 € zu 3 % auf 10 Jahre Zinsen", ["werden nach 10 Jahren zu 6719,58 €", "1719,58 € Zinsen mit Zinseszins", "Jahr 1: 5150 €", "Jahr 10: 6719,58 €", "wären es nur 6500 €", "25 % KESt"],
     ["becomes €6,719.58 after 10 years", "Year 10: €6,719.58", "only be €6,500"]),
    ("5.000 € zu 3 % auf 10 Jahre", ["6719,58 €"], ["€6,719.58"]),
    ("Zinseszins 5000 Euro 3 Prozent 10 Jahre", ["6719,58 €"], ["€6,719.58"]),
    ("Was wird aus 5.000 € bei 3 % Zinsen nach 10 Jahren", ["6719,58 €"], ["€6,719.58"]),
    ("Zinsen für 1.000 € bei 2 % für 6 Monate", ["bringen in 6 Monaten 10 € Zinsen, zusammen 1010 €"], ["earns €10 in 6 months"]),
    ("Rate bei 200.000 € Kredit zu 3,5 % über 25 Jahre", ["Monatliche Rate: 1001,25 €", "über 25 Jahre (300 Monate)"], ["Monthly payment: €1,001.25", "over 25 years (300 months)"]),
    ("Kredit 10.000 € 5 % 12 Monate Rate", ["Monatliche Rate: 856,07 €", "davon 272,90 € Zinsen"], ["Monthly payment: €856.07"]),
    ("100 € monatlich sparen bei 3 % für 10 Jahre", ["hat am Ende 13", "974,14 €", "Eingezahlt sind das 12"], ["gives €13,974.14"]),
    ("Wann verdoppeln sich 1.000 € bei 4 % Zinsen", ["rund 17,67 Jahren", "im 18. Jahr", "72 ÷ 4 = rund 18 Jahre"], ["about 17.67 years", "during year 18"]),
    ("2 Brote zu 3,40 € und 1 Käse zu 5,90 €, ich zahle mit 20 €, wie viel Rückgeld?",
     ["2 Brote zu 3,40 €: 2 × 3,40 € = 6,80 €", "Zusammen: 12,70 €", "Rückgeld 7,30 €"], ["Total: €12.70", "change €7.30"]),
    ("3 Tuben zu je 9,90 Euro, ich zahle mit 50 Euro, wie viel Rückgeld", ["29,70 €", "Rückgeld 20,30 €"], ["change €20.30"]),
    ("1,5 kg Äpfel zu 2,40 € das Kilo und 2 Liter Milch zu 1,19 €", ["1,5 kg Äpfel zu 2,40 € pro Kilo: 1,5 × 2,40 € = 3,60 €", "Zusammen: 5,98 €"], ["Total: €5.98"]),
    ("Brot 3,40 € und Käse 5,90 €, ich zahle mit 10 Euro", ["Zusammen: 9,30 €", "Rückgeld 0,70 €"], ["change €0.70"]),
    ("2 Brote zu 3 € und 1 Käse zu 5 €, ich zahle mit 10 Euro", ["Zusammen: 11 €", "Es fehlen noch 1 €"], ["€1 still missing"]),
    ("2 Brote zu 5 € und 3 Semmeln zu 1 € mit 10 % Rabatt", ["Abzüglich 10 % Rabatt (-1,30 €): 11,70 €"], ["Less 10% discount"]),
    ("200 km, 6,5 l/100 km, 1,65 €/l, was kostet die Fahrt?", ["braucht 13 Liter und kostet 21,45 €", "10,73 Cent je Kilometer"], ["uses 13 litres and costs €21.45"]),
    ("Wien nach Graz 200 km hin und zurück 6,5 l/100 km 1,65 Euro pro Liter", ["400 km (hin und zurück)", "26 Liter", "42,90 €"], ["400 km trip (there and back)"]),
    ("Elektroauto 300 km, 18 kWh/100 km, 0,30 €/kWh, was kostet die Fahrt?", ["54 kWh", "16,20 €"], ["54 kWh and costs €16.20"]),
    ("Rechnung 87,60 €, 4 Personen, 10 % Trinkgeld", ["Trinkgeld 10 % von 87,60 €: 8,76 €", "Gesamt: 87,60 € + 8,76 € = 96,36 €", "jede Person 24,09 €"], ["Tip 10% of €87.60: €8.76", "each person pays €24.09"]),
    ("120 € auf 5 Personen aufteilen", ["jede Person 24 €"], ["each person pays €24"]),
    ("Rechnung 87,60 € 4 Personen 10 % Trinkgeld aufrunden", ["Aufgerundet auf volle Euro zahlt jede der 4 Personen 25,00 €", "12,40 € Trinkgeld"], ["Rounded up to whole euros each of the 4 people pays €25"]),
    ("Rechnung 100 € 3 Personen", ["33,33 € je Person, 1 Cent bleiben übrig"], ["€33.33 each, 1 cent is left"]),
    ("Rechnung 50 € 15 % Trinkgeld", ["Trinkgeld 15 % von 50 €: 7,50 €", "Gesamt: 50 € + 7,50 € = 57,50 €"], ["Total: €50 + €7.50 = €57.50"]),
]


@pytest.mark.parametrize("frage,de,en", FRAGEN)
def test_fragen(frage, de, en):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in de:
        assert teil in r.de.replace(N, ""), (frage, teil, r.de)
    for teil in en:
        assert teil in r.en, (frage, teil, r.en)


def test_zinseszins_gegen_decimal():
    rnd = random.Random(11)
    for _ in range(300):
        k = rnd.randint(100, 90000)
        p = Decimal(rnd.randint(1, 120)) / 10
        j = rnd.randint(1, 40)
        r = rechnen.loesen(f"{k} € zu {str(p).replace('.', ',')} % auf {j} Jahre Zinsen")
        assert r is not None
        erwartet = _cent(Decimal(k) * (1 + p / 100) ** j)
        endwert = Decimal(re.search(r"werden nach [^z]*zu ([\d ]+(?:,\d+)?) €", r.de).group(1).replace(N, "").replace(",", "."))
        assert endwert == erwartet, (k, p, j, endwert, erwartet)


def test_kredit_gegen_float():
    rnd = random.Random(5)
    for _ in range(300):
        k = rnd.randint(1000, 500000)
        p = Decimal(rnd.randint(0, 100)) / 10
        jahre = rnd.randint(1, 35)
        r = rechnen.loesen(f"Rate für {k} € Kredit zu {str(p).replace('.', ',')} % über {jahre} Jahre")
        assert r is not None
        rate = Decimal(re.search(r"Monatliche Rate: ([\d ]+(?:,\d\d)?) €", r.de).group(1).replace(N, "").replace(",", "."))
        n = jahre * 12
        i = p / 100 / 12
        erwartet = Decimal(k) / n if i == 0 else Decimal(k) * i / (1 - (1 + i) ** (-n))
        assert rate == _cent(erwartet), (k, p, jahre, rate, erwartet)
        rest = Decimal(k)
        for _m in range(n):
            rest = rest * (1 + i) - rate
        grenze = Decimal("0.005") * (n if i == 0 else ((1 + i) ** n - 1) / i) + Decimal("0.01")
        assert abs(rest) <= grenze, (k, p, jahre, rest)


def test_sparplan_gegen_decimal():
    rnd = random.Random(8)
    for _ in range(200):
        b = rnd.randint(10, 2000)
        p = Decimal(rnd.randint(1, 100)) / 10
        j = rnd.randint(1, 40)
        r = rechnen.loesen(f"{b} € monatlich sparen bei {str(p).replace('.', ',')} % für {j} Jahre")
        assert r is not None
        i = p / 100 / 12
        n = j * 12
        erwartet = _cent(Decimal(b) * ((1 + i) ** n - 1) / i)
        end = Decimal(re.search(r"hat am Ende ([\d ]+(?:,\d\d)?) €", r.de).group(1).replace(N, "").replace(",", "."))
        assert end == erwartet, (b, p, j, end, erwartet)


def test_trinkgeld_gegen_decimal():
    rnd = random.Random(3)
    for _ in range(400):
        cent = rnd.randint(100, 100000)
        betrag = Decimal(cent) / 100
        proz = rnd.choice([0, 5, 8, 10, 12, 15, 20])
        n = rnd.randint(1, 12)
        text = f"Rechnung {betrag:.2f}".replace(".", ",") + f" € {n} Personen"
        if proz:
            text += f" {proz} % Trinkgeld"
        if n == 1 and not proz:
            continue
        r = rechnen.loesen(text)
        assert r is not None, text
        gesamt = betrag * (100 + proz) / 100
        if n > 1:
            gesamt_cent = int((gesamt * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            je, rest = divmod(gesamt_cent, n)
            teil = r.de.split("\n")[-1]
            assert f"{je // 100},{je % 100:02d} €".replace(".", "") in teil.replace(N, ""), (text, teil, je)
            if rest:
                assert f"{rest} Cent" in teil
        if proz:
            assert f"{_cent(betrag * proz / 100)}".replace(".", ",") in r.de


@pytest.mark.parametrize("text", [
    "Ich habe 5.000 € und will wissen ob ich 3 % Zinsen auf 10 Jahre Sparbuch oder ETF wählen soll", "Wie hoch ist die Rate wenn ich ein Auto kaufe",
    "Soll ich einen Kredit aufnehmen? Ich habe 10.000 € Schulden und 5 % Zinsen", "3 Tuben zu je 9,90 Euro", "Die Rechnung war 87,60 € und wir waren zu viert, wer zahlt?",
    "Wie viele Kilometer fährt man mit 40 Litern bei 6,5 l/100 km", "200 km/h in m/s", "Wie schnell ist 120 km in 2 Stunden", "5 % von 200 €", "10 € + 5 %", "Wien Graz 200 km",
    "Zinsen 3 %", "Kredit 10.000 €", "100 € monatlich", "Rechnung 50 €", "Trinkgeld 10 %", "was ist ein Zinseszins", "Zinseszins erklären: 5.000 € 3 % 10 Jahre bitte ausführlich mit Beispielen aus dem Alltag und Tabelle für mein Kind",
    "Kredit 10.000 € 5 % 0 Monate", "Kredit 10.000 € 5 % 5000 Jahre",
])
def test_keine_geldaufgabe(text):
    r = rechnen.loesen(text)
    assert r is None or not any(w in r.de for w in ("Rate:", "Zinseszins", "Rückgeld", "Trinkgeld", "Einkauf:", "Cent je Kilometer", "hat am Ende", "verdoppeln")), (text, r and r.de)


def test_ganze_betraege_ohne_nullen():
    r = rechnen.loesen("Rechnung 100 € 4 Personen")
    assert "25 €" in r.de and ",00" not in r.de and "€25.00" not in r.en
    r = rechnen.loesen("Rechnung 100,00 € 4 Personen")
    assert "25,00 €" in r.de
