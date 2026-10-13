# SPDX-License-Identifier: AGPL-3.0-or-later
import calendar
import random
import re
import sys
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, getcontext
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import absicht
import antwortsprache
import kurse
import rechnen
import rechnen_datum
import rechnen_zeit

getcontext().prec = 50
N = " "
HEUTE = date(2026, 10, 11)


@pytest.fixture(autouse=True)
def _uhr(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: HEUTE)
    monkeypatch.setattr(rechnen_zeit, "jetzt_utc", lambda: datetime(2026, 10, 11, 14, 20, tzinfo=timezone.utc))


def en(frage: str) -> str:
    r = rechnen.loesen(frage)
    assert r is not None, frage
    return r.en


def zahlen(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)]


KMH = ["{v} km/h", "{v}km/h", "{v} kmh", "{v}kmH", "{v} KMH", "{v} kph", "{v} kilometers per hour", "{v} kilometres per hour", "{v} Stundenkilometer", "{v} km pro Stunde"]
MPH = ["mph", "miles per hour", "Meilen pro Stunde", "mi/h"]


@pytest.mark.parametrize("quelle", KMH)
@pytest.mark.parametrize("ziel", MPH)
def test_kmh_in_mph_jede_schreibweise(quelle, ziel):
    for v in (100, 50, 130, 7.5):
        wert = Decimal(str(v)) / Decimal("1.609344")
        for satz in ("{q} in {z}", "convert {q} to {z}", "how many {z} is {q}", "the car drives {q}, how many {z} is that?"):
            if "pro Stunde" in quelle and satz.startswith(("convert", "how", "the")):
                continue
            frage = satz.format(q=quelle.format(v=v), z=ziel)
            r = rechnen.loesen(frage)
            assert r is not None, frage
            erste = zahlen(r.en)[-1] if False else None
            zahl = [x for x in zahlen(r.en) if abs(x - float(wert)) / float(wert) < 5e-4]
            assert zahl, (frage, r.en, float(wert))


@pytest.mark.parametrize("mph", [10, 25, 55, 60, 65, 70, 80, 100, 0.5, 12.5])
def test_mph_in_kmh_genau(mph):
    r = rechnen.loesen(f"{mph} mph to km/h")
    assert r is not None
    soll = Decimal(str(mph)) * Decimal("1.609344")
    assert any(abs(x - float(soll)) < 1e-6 * max(1.0, float(soll)) for x in zahlen(r.en)), (mph, r.en)


def test_philipps_beispiel_100kmh():
    r = rechnen.loesen("100kmH in mph")
    assert r is not None and "62.1371 mph" in r.en and "62,1371 mph" in r.de
    r = rechnen.loesen("Das Auto fährt 100 kmH, wie viel ist das in Meilen pro Stunde?")
    assert r is not None and "62,1371" in r.de
    r = rechnen.loesen("The car does 100 kmH, how many miles per hour is that?")
    assert "62.1371 mph" in r.en
    r = rechnen.loesen("the car drives 60 mph how many km/h is that")
    assert "96.56064 km/h" in r.en


EINHEITEN = [
    ("12 stone in kg", "76.20351816 kg"), ("8 oz in grams", "226.796185 g"), ("2 lbs in kg", "0.90718474 kg"), ("180 pounds in kg", "81.6466266 kg"), ("1 lb in oz", "16 oz"),
    ("how many ounces in a pound", "16 oz"), ("how many inches in a foot", "12 inch"), ("how many feet in a mile", "5,280 ft"), ("how many yards in a mile", "1,760 yd"),
    ("5 miles to km", "8.04672 km"), ("26.2 miles in km", "42.1648128 km"), ("1 mile in feet", "5,280"), ("72 inches in cm", "182.88 cm"), ("6 ft 2 in cm", "187.96 cm"),
    ("6'2\" in cm", "187.96 cm"), ("5 feet 10 inches in cm", "177.8 cm"), ("5'10 in cm", "177.8 cm"), ("1 yard in m", "0.9144 m"), ("100 yards in meters", "91.44 m"),
    ("1 US gallon in liters", "3.785411784"), ("1 imperial gallon in liters", "4.54609"), ("2 pints in ml", "946.352946"), ("1 imperial pint in ml", "568.26125"),
    ("1 quart in liters", "0.946352946"), ("8 fl oz in ml", "236.5882365"), ("10 acres in hectares", "4.04685642"), ("1000 sq ft in m2", "92.90304 m²"),
    ("1000 square feet to square meters", "92.90304 m²"), ("1 acre in square feet", "43,560"), ("1 short ton in kg", "907.18474"), ("1 long ton in kg", "1,016.0469088"),
    ("3 cups in ml", "720 ml"), ("how many cups in a liter", "4.1667 cups"), ("how many tablespoons in a cup", "16 tbsp"), ("how many teaspoons in a tablespoon", "3 tsp"),
    ("how many seconds in a day", "86,400 s"), ("how many hours in a week", "168 h"), ("3.5 hours in minutes", "210 min"), ("how many days in a year", "365"),
    ("1 mile per hour in feet per second", "1.4667"), ("60 mph in ft/s", "88 ft/s"), ("100 knots in mph", "115.07"), ("10 m/s in mph", "22.3694"),
]


@pytest.mark.parametrize("frage,erwartet", EINHEITEN)
def test_einheiten(frage, erwartet):
    assert erwartet in en(frage), (frage, en(frage))


def test_us_und_uk_unterschiede_werden_gesagt():
    assert "US gallon (3.785 l); the UK gallon is 4.546 l" in en("1 gallon in liters")
    assert "Calculated with the US gallon" not in en("1 imperial gallon in liters")
    assert "US pint (473 ml); the UK pint is 568 ml" in en("2 pints in ml")
    assert "US cup (240 ml)" in en("1 cup in ml") or "240 ml" in en("1 cup in ml")
    assert "US ton (907 kg)" in en("2 tons in kg")
    assert "(US)" in en("30 mpg in l/100 km") and "UK gallon" in en("30 mpg in l/100 km")
    assert "(UK)" in en("30 mpg (UK) in l/100 km")


def test_zoll_fuss_zufaellig():
    rnd = random.Random(4)
    for _ in range(300):
        ft, inch = rnd.randint(1, 8), rnd.randint(0, 11)
        soll = Decimal(ft) * Decimal("30.48") + Decimal(inch) * Decimal("2.54")
        for form in (f"{ft} ft {inch} in cm", f"{ft}'{inch}\" in cm", f"{ft} feet {inch} inches in centimeters"):
            r = rechnen.loesen(form)
            assert r is not None, form
            assert any(abs(x - float(soll)) < 1e-6 for x in zahlen(r.en)), (form, r.en, soll)


def test_temperatur_zufaellig():
    rnd = random.Random(8)
    for _ in range(400):
        f = rnd.randint(-40, 500)
        c = (Decimal(f) - 32) * 5 / 9
        for frage in (f"{f} F to C", f"{f} °F in celsius", f"{f} degrees fahrenheit in celsius", f"{f}° F to C"):
            r = rechnen.loesen(frage)
            assert r is not None, frage
            assert any(abs(x - float(c)) < 1e-3 for x in zahlen(r.en.split(" is ")[1])), (frage, r.en, c)
        cc = rnd.randint(-40, 400)
        fo = Decimal(cc) * 9 / 5 + 32
        r = rechnen.loesen(f"{cc} C to F")
        assert any(abs(x - float(fo)) < 1e-3 for x in zahlen(r.en.split(" is ")[1])), (cc, r.en)


GAS = {"1/4": 110, "1/2": 120, "1": 140, "2": 150, "3": 170, "4": 180, "5": 190, "6": 200, "7": 220, "8": 230, "9": 240}


@pytest.mark.parametrize("gas,c", sorted(GAS.items()))
def test_gas_mark(gas, c):
    assert f"{c} °C" in en(f"gas mark {gas} in celsius")
    assert f"{c} °C" in en(f"what is gas mark {gas} in C")


def test_backofen_hinweis():
    t = en("350 F in celsius for baking")
    assert "Oven:" in t and "Gas mark: about 4" in t and "fan oven" in t
    t = rechnen.loesen("180 °C in Fahrenheit zum Backen")
    assert "356 °F" in t.de and "Backofen:" in t.de and "Umluft" in t.de
    assert "Oven" not in en("350 F in celsius")


@pytest.mark.parametrize("mpg", [10, 15, 20, 25, 28, 30, 35, 40, 50, 12.5])
def test_mpg_in_l_pro_100km(mpg):
    us = Decimal("100") * Decimal("3.785411784") / Decimal("1.609344") / Decimal(str(mpg))
    uk = Decimal("100") * Decimal("4.54609") / Decimal("1.609344") / Decimal(str(mpg))
    t = en(f"{mpg} mpg in l/100 km")
    assert any(abs(x - float(us)) < 1e-3 for x in zahlen(t)), (mpg, t)
    assert any(abs(x - float(uk)) < 1e-3 for x in zahlen(t)), "die britische Zahl steht dabei"
    t = en(f"{mpg} mpg (UK) in l/100 km")
    assert t.startswith(f"{mpg:g} mpg (UK) is") and abs(zahlen(t.split(" is ")[1].split(" l/100")[0])[0] - float(uk)) < 1e-3


@pytest.mark.parametrize("l100", [4, 5, 6.5, 8, 10, 12, 15])
def test_l_pro_100km_in_mpg_und_km_pro_l(l100):
    mpg = Decimal("100") * Decimal("3.785411784") / Decimal("1.609344") / Decimal(str(l100))
    assert any(abs(x - float(mpg)) < 1e-3 for x in zahlen(en(f"{l100} l/100 km in mpg")))
    kml = 100 / Decimal(str(l100))
    assert any(abs(x - float(kml)) < 1e-3 for x in zahlen(en(f"{l100} l/100 km in km/l")))
    assert any(abs(x - float(kml)) < 1e-3 for x in zahlen(en(f"my car uses {l100} liters per 100 km, how many km per liter is that")))


def test_verbrauch_deutsch():
    r = rechnen.loesen("Mein Auto verbraucht 7,5 l/100 km, wie viel ist das in mpg?")
    assert r is not None and "31,3619" in r.de


@pytest.mark.parametrize("frage,erwartet", [
    ("I weigh 80 kg, how many pounds is that?", "176.3698"), ("My car does 28 mpg, how many liters per 100 km is that", "8.4005"), ("The Eiffel Tower is 330 m tall, how many feet is that?", "1,082.677"),
    ("It's 30 °C outside, what is that in Fahrenheit?", "86 °F"), ("The recipe says 350 F, what's that in C", "176.6667 °C"), ("How many kilometers is 26.2 miles", "42.1648128 km"),
    ("what's 5 feet in meters", "1.524 m"), ("tell me how many ounces 2 pounds is", "32 oz"),
])
def test_fragesaetze_englisch(frage, erwartet):
    assert erwartet in en(frage), (frage, en(frage))


@pytest.mark.parametrize("frage,erwartet", [
    ("Das Auto fährt 100 kmH, wie viel ist das in mph?", "62,1371 mph"), ("Ich wiege 80 kg, wie viele Pfund sind das?", None), ("Wie viele Minuten hat eine Stunde?", "60 min"),
    ("Wie viele Zentimeter hat ein Meter?", "100 cm"), ("Wie viele Sekunden hat ein Tag?", "86"),
])
def test_fragesaetze_deutsch(frage, erwartet):
    r = rechnen.loesen(frage)
    if erwartet is None:
        return
    assert r is not None and erwartet in r.de.replace(N, ""), (frage, r and r.de)


@pytest.mark.parametrize("frage", [
    "How many miles is Vienna from Berlin", "How many people live in 5 km radius", "How many calories are in 100 g of rice and 50 g of beans", "My car does 100 km in 1 hour, how fast is that in mph",
    "I ran 5 km in 30 minutes, how many miles per hour", "What is the best way to convert 5 miles to something useful for my 10 year old", "Linz is 190 km from Vienna and 250 km from Salzburg, how many miles is that",
    "How many inches of rain fell in 2020", "How many feet tall is Mount Everest", "Is 100 km/h too fast for a tractor",
])
def test_keine_umrechnung_wo_keine_ist(frage):
    r = rechnen.loesen(frage)
    assert r is None, (frage, r and r.en)


ALLTAG = [
    ("half of 80", "Half of 80 is 40"), ("a quarter of 120", "1/4 of 120 is 30"), ("three quarters of 200", "3/4 of 200 is 150"), ("a third of 90", "1/3 of 90 is 30"), ("double 12", "2 times 12 is 24"),
    ("twice 12", "is 24"), ("triple 7", "is 21"), ("what is the square root of 144", "= 12"), ("12 squared", "= 144"), ("what is 20% of 150", "is 30"), ("whats 15% of 80", "is 12"),
    ("increase 150 by 20%", "is 180"), ("80 reduced by 15%", "is 68"), ("what percent of 80 is 20", "is 25%"), ("20 is what percent of 80", "is 25%"),
    ("percent change from 80 to 100", "25% more"), ("what is 15% of $80", "$12"), ("15% off $80", "You pay $68"), ("20% sales tax on $80", "$16"), ("half of $50", "$25"),
    ("average of 3, 5 and 10", "is 6"), ("what is 7 times 8", "= 56"), ("144 divided by 12", "= 12"), ("is 91 prime", "not a prime number"), ("prime factors of 84", "2² × 3 × 7"),
    ("255 in binary", "11111111"), ("2026 in roman numerals", "MMXXVI"), ("solve 2x + 6 = 20", "x = 7"), ("what is x if 3x - 4 = 11", "x = 5"),
]


@pytest.mark.parametrize("frage,erwartet", ALLTAG)
def test_alltag_englisch(frage, erwartet):
    assert erwartet in en(frage), (frage, en(frage))


def _nter(j, m, wt, n):
    tage = [w[wt] for w in calendar.monthcalendar(j, m) if w[wt]]
    return date(j, m, tage[n - 1] if n > 0 else tage[-1])


@pytest.mark.parametrize("j", range(2020, 2041))
def test_us_feiertage_gegen_kalendermodul(j):
    tg = _nter(j, 11, 3, 4)
    assert f"{WOCHEN[tg.weekday()]}" == "Thursday"
    t = en(f"what day is Thanksgiving {j}")
    assert f"November {tg.day}, {j}" in t and "Thursday" in t
    t = en(f"what day of the week is Memorial Day {j}")
    assert f"May {_nter(j, 5, 0, -1).day}, {j}" in t and "Monday" in t
    t = en(f"what day is Labor Day {j}")
    assert f"September {_nter(j, 9, 0, 1).day}, {j}" in t
    t = en(f"what day is Mother's Day {j}")
    assert f"May {_nter(j, 5, 6, 2).day}, {j}" in t and "Sunday" in t
    t = en(f"what day of the week is July 4, {j}")
    assert WOCHEN[date(j, 7, 4).weekday()] in t and f"July 4, {j}" in t


WOCHEN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def test_wochentag_zufaellige_daten_in_allen_schreibweisen():
    rnd = random.Random(12)
    monate = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    for _ in range(400):
        d = date(rnd.randint(1700, 2400), rnd.randint(1, 12), rnd.randint(1, 28))
        soll = WOCHEN[d.weekday()]
        us = f"{monate[d.month - 1]} {d.day}, {d.year}"
        uk = f"{d.day} {monate[d.month - 1]} {d.year}"
        for frage in (f"what day of the week is {us}", f"what day was {uk}", f"what weekday is {d.month:02d}/{d.day:02d}/{d.year}" if d.day > 12 else f"what day is {us}"):
            r = rechnen.loesen(frage)
            assert r is not None, frage
            assert soll in r.en, (frage, r.en, soll)


def test_slash_datum_mehrdeutig_und_eindeutig():
    t = en("what day is 03/04/2026")
    assert "March 4, 2026" in t and "can be read two ways" in t and "April 3, 2026" in t
    t = en("what day is 25/12/2026")
    assert "December 25, 2026" not in t and "25 December 2026" in t and "two ways" not in t
    t = en("what day is 12/25/2026")
    assert "December 25, 2026" in t and "Friday" in t and "two ways" not in t
    r = rechnen.loesen("Welcher Wochentag ist der 4.7.2027?")
    assert "Sonntag" in r.de and "July" not in r.de


def test_tage_bis_auf_englisch():
    assert "75 days" in en("how many days until Christmas")
    assert "46 days" in en("how many days till Thanksgiving")
    assert "81 days" in en("days until New Year's Eve")
    assert "20 days" in en("how long until Halloween")
    assert "24 weeks" in en("how many weeks until Easter")
    assert "Sunday" in en("what's today's date") and "week 41" in en("what's today's date")
    assert "59 days" in en("how many days between January 1, 2027 and March 1, 2027")
    assert "36 years, 6 months and 26 days old" in en("how old am I if I was born on 03/15/1990")
    assert "November 10, 2026" in en("what is the date 30 days from now") or "10 November 2026" in en("what is the date 30 days from now")
    assert "20 September 2026" in en("3 weeks ago")


def test_us_ausgabe_nur_bei_us_frage():
    assert "October 11, 2026" in en("how many days until Thanksgiving")
    assert "11 October 2026" in en("how many days until Christmas")
    assert "Sonntag, 11.10.2026" in rechnen.loesen("how many days until Thanksgiving").de


def test_zeit_englisch():
    assert "12:00 PM in New York" in en("what time is it in New York when it's 6 pm in Vienna") or "1:00 PM" in en("6 pm London in New York")
    assert "4:20 PM" in en("what time is it in Vienna")
    assert "10:20 AM in New York" in en("what time is it in New York")


def _euro_fmt(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


@pytest.mark.parametrize("zeichen,wort", [("$", "$"), ("£", "£")])
def test_zinseszins_dollar_und_pfund(zeichen, wort):
    rnd = random.Random(21)
    for _ in range(200):
        k = rnd.randint(100, 90000)
        p = Decimal(rnd.randint(1, 120)) / 10
        j = rnd.randint(1, 40)
        soll = (Decimal(k) * (1 + p / 100) ** j).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for frage in (f"{zeichen}{k:,} at {p}% for {j} years", f"compound interest on {zeichen}{k:,} at {p}% for {j} years", f"how much will {zeichen}{k} be after {j} years at {p}% interest"):
            t = en(frage)
            soll_text = f"{soll:,}"
            if soll_text.endswith(".00") and "." not in frage.split(" at ")[0]:
                soll_text = soll_text[:-3]
            assert f"becomes {wort}{soll_text}" in t, (frage, soll, t[:200])
            assert "€" not in t


def test_us_zahlen_und_deutsche_zahlen_nebeneinander():
    assert "becomes $6,719.58" in en("$5,000 at 3% for 10 years")
    r = rechnen.loesen("5,000 € zu 3 % auf 10 Jahre")
    assert r is not None and "5 € zu 3 % Zinsen" in r.de.replace(N, "")
    assert "6.719,58" in rechnen.loesen("5.000 € zu 3 % auf 10 Jahre").de.replace(N, ".") or "6719,58" in rechnen.loesen("5.000 € zu 3 % auf 10 Jahre").de
    assert zahlen(en("what is 1,500 times 2"))[-1] == 3000.0
    assert zahlen(rechnen.loesen("1,5 mal 2").en)[-1] == 3.0
    assert rechnen.zahl_lesen("1,500") == Fraction(3, 2)


@pytest.mark.parametrize("frage,erwartet", [
    ("monthly payment on a $200,000 loan at 3.5% over 25 years", "Monthly payment: $1,001.25"), ("mortgage payment $300,000 4% 30 years", "Monthly payment: $1,432.25"),
    ("saving $100 per month at 3% for 10 years", "gives $13,974.14"), ("how long until my money doubles at 4%", "about 17.67 years"),
    ("2 loaves at $3.40 and 1 cheese at $5.90, I pay with $20", "change $7.30"), ("a loaf at $3.40 and 2 apples at $0.50 each, I pay with a $10 bill", "change $5.60"),
    ("bill $87.60, 4 people, 18% tip", "Tip 18% of $87.60: $15.77"), ("what is 15% tip on $80", "Total: $80 + $12 = $92"), ("split $120 between 5 people", "each person pays $24"),
    ("tip 20% on a $50 bill split 2 ways", "each person pays $30"), ("£5,000 at 3% for 10 years", "becomes £6,719.58"), ("5000 CHF zu 2 % auf 5 Jahre", "CHF 5,520.40"),
    ("$5,000.50 at 3% for 10 years", "$5,000.50 at 3%"),
])
def test_geld_englisch(frage, erwartet):
    assert erwartet in en(frage), (frage, en(frage)[:300])


def test_kredit_dollar_gegen_decimal():
    rnd = random.Random(33)
    for _ in range(200):
        k = rnd.randint(1000, 500000)
        p = Decimal(rnd.randint(1, 100)) / 10
        jahre = rnd.randint(1, 35)
        i = p / 100 / 12
        n = jahre * 12
        rate = (Decimal(k) * i / (1 - (1 + i) ** (-n))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        t = en(f"monthly payment on a ${k:,} loan at {p}% over {jahre} years")
        soll = f"{rate:,}"
        soll = soll[:-3] if soll.endswith(".00") else soll
        assert f"Monthly payment: ${soll}" in t, (k, p, jahre, rate, t[:120])


def test_sprit_mit_meilen_gegen_decimal():
    rnd = random.Random(5)
    for _ in range(200):
        meilen = rnd.randint(10, 900)
        mpg = rnd.randint(12, 60)
        preis = Decimal(rnd.randint(250, 650)) / 100
        gallonen = Decimal(meilen) / Decimal(mpg)
        kosten = (gallonen * preis).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        t = en(f"{meilen} miles, {mpg} mpg, ${preis} per gallon")
        assert f"costs ${kosten:,}" in t, (meilen, mpg, preis, kosten, t[:160])
    t = en("200 miles round trip at 30 mpg and $3.60 a gallon")
    assert "round trip" in t and f"costs ${Decimal(400) / 30 * Decimal('3.60'):,.2f}" in t
    uk = en("150 miles at 35 mpg and £1.45 per litre")
    assert "UK gallons" in uk and "costs £28.25" in uk


def test_sprit_metrisch_und_deutsch_unveraendert():
    assert "costs €21.45" in en("200 km, 6.5 l/100 km, 1.65 euro per liter")
    r = rechnen.loesen("Wien nach Graz 200 km hin und zurück 6,5 l/100 km 1,65 Euro pro Liter")
    assert "42,90 €" in r.de and "400 km (hin und zurück)" in r.de


def test_rezept_englisch_mit_metrik():
    t = en("recipe for 4 to 6 servings: 2 cups flour, 1/2 lb butter, 8 oz sugar")
    assert "factor 1.5" in t and "2 cups flour → 3 cups flour (about 374 g)" in t
    assert "0.5 lb butter → 0.75 lb butter (340 g)" in t and "8 oz sugar → 12 oz sugar (340 g)" in t
    t = en("double this recipe: 1 cup milk, 2 eggs, 1 stick butter")
    assert "Recipe doubled (factor 2)" in t and "2 cups milk" in t and "4 eggs" in t and "2 sticks butter (227 g)" in t
    t = en("halve the recipe: 4 tbsp sugar, 1 lb flour")
    assert "Recipe halved (factor 0.5)" in t and "2 tbsp sugar" in t and "0.5 lb flour (227 g)" in t
    r = rechnen.loesen("Rezept verdoppeln: 200 g Mehl, 1 Tasse Milch")
    assert "Rezept verdoppelt (Faktor 2)" in r.de and "400 g Mehl" in r.de and "2 Tassen Milch" in r.de


@pytest.mark.parametrize("frage,erwartet", [
    ("1 stick of butter in grams", "113.4 g"), ("8 oz butter in cups", "about 1 cup"), ("3 cups flour in grams", "about 374 g"), ("1 cup sugar in grams", "about 204 g"), ("2 tbsp flour in grams", "about 16 g"),
    ("how many grams is an egg", "55 g"), ("how many grams is 3 eggs", "165 g"), ("how many calories in 100 g of butter", "740 kcal"), ("calories in 2 tbsp honey", "128 kcal"),
    ("1 cup butter in grams", "about 228 g"), ("2 sticks of butter in cups", "1 cup"), ("1 lb flour in cups", "about 3.6 cups"),
])
def test_kueche_englisch(frage, erwartet):
    assert erwartet in en(frage), (frage, en(frage))


def test_kueche_deutsch_pakete_und_kalorien():
    assert "55 g" in rechnen.loesen("Wie viel wiegt ein Ei?").de
    assert "165 g" in rechnen.loesen("3 Eier in Gramm").de
    assert "15 g" in rechnen.loesen("Wie viel Gramm sind ein Päckchen Backpulver?").de
    assert "42 g" in rechnen.loesen("Wie viel wiegt ein Würfel Hefe").de
    assert "800 kcal" in rechnen.loesen("Wie viele Kalorien haben 200 g Zucker").de


def test_cup_ist_240_tasse_ist_250():
    assert "240 ml" in en("1 cup in ml") and "250 ml" in en("1 Tasse in ml")
    assert "125 g" in en("1 cup flour in grams") and "130" in en("1 Tasse Mehl in Gramm") or "130 g" in rechnen.loesen("1 Tasse Mehl in Gramm").de


def test_gehalt_englisch():
    for frage in ("gross to net 3000 austria", "3000 gross in net", "What is the net of 3000 gross", "net salary for 3000 gross", "3000 gross to net"):
        t = rechnen.loesen(frage)
        assert t is not None and "Net per month: €2,174.08" in t.en, frage
    t = en("I want 2500 net, how much gross do I need")
    assert "€3,568.29 gross" in t


ENGLISCH_FRAGEN = [
    "convert 5 miles to km", "how many km is 26.2 miles", "100 kmh in miles per hour", "the car drives 100 kmH how many mph is that", "60 miles per hour in kilometers per hour",
    "30 mpg in l/100km", "how many ounces in a pound", "8 oz in grams", "12 stone in kg", "6 ft 2 in cm", "6'2\" in cm", "1 gallon in liters", "350 F to C", "350 F in celsius for baking",
    "gas mark 4 in celsius", "what is 20% of 150", "half of 80", "what is the square root of 144", "how many days until Christmas", "what day of the week is July 4, 2027",
    "what day is 12/25/2026", "$5,000 at 3% for 10 years", "monthly payment on a $200,000 loan at 3.5% over 25 years", "2 loaves at $3.40 and 1 cheese at $5.90, I pay with $20",
    "bill $87.60, 4 people, 18% tip", "300 miles, 28 mpg, $3.50 per gallon", "recipe for 4 to 6 servings: 2 cups flour, 1/2 lb butter, 8 oz sugar", "1 stick of butter in grams",
    "3 hours in minutes", "255 in binary", "solve 2x + 6 = 20", "100 euros to dollars", "$50 to euros", "£100 in euros", "gross to net 3000 austria",
]


@pytest.mark.parametrize("frage", ENGLISCH_FRAGEN)
def test_englische_frage_wird_englisch_beantwortet(frage):
    assert antwortsprache.frage_sprache(frage) == "en", frage
    a = absicht.erkennen(frage)
    if a.art == "rechnen":
        assert a.antwort_en
        assert a.antwort_en != a.antwort or not re.search(r"[A-Za-z]{4}", a.antwort_en.replace("sqrt", "")) or a.antwort_en.startswith("√")
        deutsch = re.search(r"\b(?:Rechnung|ungefähr|Zusammen|Jahre|Gallonen|Stunden|Minuten|sind|ergibt|Einkauf|Bezahlt|Rückgeld|Zinsen|Tage|Meilen)\b", a.antwort_en)
        assert not deutsch, (frage, a.antwort_en)
    else:
        assert kurse.erkennen(frage) is not None, frage


DEUTSCHE_FRAGEN = [
    "Wie viele Tage bis Weihnachten?", "wieviel sind 188dm in cm und milimeter", "5.000 € zu 3 % auf 10 Jahre", "Das Auto fährt 100 kmH, wie viel ist das in mph?", "2 EL Mehl in Gramm",
    "Wie viele Minuten hat eine Stunde", "3,5 Stunden in Minuten", "10 Liter in Mililiter", "Primfaktoren von 84", "2 + 2", "Rate bei 200.000 € Kredit zu 3,5 % über 25 Jahre",
    "3.000 € brutto in netto", "Welcher Wochentag ist der 4. Juli 2027?", "100 Euro in Dollar", "1,5 Mio Euro in Dollar", "wie viel sind 5 Meter in Fuß", "Rezept für 4 auf 6 Personen: 200 g Mehl",
]


@pytest.mark.parametrize("frage", DEUTSCHE_FRAGEN)
def test_deutsche_frage_bleibt_deutsch(frage):
    assert antwortsprache.frage_sprache(frage) == "de", frage


def test_zustand_einer_frage_bleibt_nicht_haengen():
    en("$5,000 at 3% for 10 years")
    assert "5 € zu 3 %" in rechnen.loesen("5,000 € zu 3 % auf 10 Jahre").de.replace(N, "")
    r = rechnen.loesen("100 € monatlich sparen bei 3 % für 10 Jahre")
    assert "€" in r.de and "$" not in r.de and "13" in r.de


def test_viele_zufaellige_englische_saetze_ohne_ausnahme():
    rnd = random.Random(77)
    vocab = ("what how many much is are the of in to at for per and with from convert miles km mph mpg ounces pounds stone gallon pint cups tbsp eggs butter flour sugar $5,000 £100 3% 18% tip bill "
             "loan years months days until Christmas Thanksgiving July 4 2027 12/25/2026 half quarter double square root 100 28 3.50 6'2\" 350 F C gas mark recipe servings").split()
    for _ in range(4000):
        s = " ".join(rnd.choice(vocab) for _ in range(rnd.randint(1, 12)))
        rechnen.loesen(s)
        antwortsprache.frage_sprache(s)


def test_ohne_waehrungszeichen_in_englischer_frage_steht_kein_zeichen():
    t = en("bill 87.60, 4 people, 18% tip")
    assert "$" not in t and "€" not in t and "£" not in t and "Tip 18% of 87.60: 15.77" in t
    assert "each person pays 24" in en("split 120 between 5 people")
    assert "Total: 80 + 12 = 92" in en("what is 15% tip on 80")
    assert rechnen.loesen("17 geteilt durch 5").de.startswith("17 ÷ 5")
    assert rechnen.loesen("120 auf 5 Personen aufteilen") is None


def test_gehalt_bleibt_euro_auch_ohne_zeichen_in_englischer_frage():
    assert "Net per month: €2,174.08" in en("3000 gross to net")


def test_ganze_betraege_ohne_nullen_auch_mit_zinssatz_mit_punkt():
    t = en("monthly payment on a $200,000 loan at 3.5% over 25 years")
    assert "For $200,000 at 3.5%" in t and "$200,000.00" not in t
    r = rechnen.loesen("Rate bei 200.000 € Kredit zu 3,5 % über 25 Jahre")
    assert "Bei 200" in r.de and ",00 €" not in r.de
