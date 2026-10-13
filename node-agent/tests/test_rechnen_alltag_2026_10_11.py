# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import absicht
import rechnen
import rechnen_datum

N = " "


@pytest.fixture(autouse=True)
def _heute(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 10, 11))


ALLTAG = [
    ("Die Hälfte von 80", ["ist 40", "80 ÷ 2 = 40"]), ("ein Viertel von 90", ["ist 22,5"]), ("drei Viertel von 200", ["ist 150", "200 ÷ 4 × 3 = 50 × 3 = 150"]),
    ("3/4 von 80", ["ist 60"]), ("das Doppelte von 12", ["ist 24"]), ("Hälfte von 25,50 €", ["12,75 €"]), ("ein Drittel von 10", ["rund 3,3333"]),
    ("120 plus 20 %", ["= 144", "20 % von 120 = 24"]), ("20 % mehr als 150", ["sind 180"]), ("80 € minus 15 %", ["68 €"]), ("15 % weniger als 200", ["sind 170"]),
    ("Wie viel Prozent mehr sind 120 als 100?", ["20 % mehr als 100"]), ("Wie viel Prozent weniger sind 80 als 100?", ["20 % weniger als 100"]),
    ("Um wie viel Prozent steigt es von 80 auf 100?", ["25 % mehr als 80"]), ("von 100 auf 80 wie viel Prozent", None),
    ("50 ist wie viel Prozent von 200", ["25 %"]),
    ("20 % MwSt auf 120 €", ["24 €", "144 € (brutto)"]), ("100 € netto in brutto bei 20 %", ["120 € brutto", "Steuer 20 €"]),
    ("120 € brutto in netto bei 20 %", ["100 € netto"]), ("15 % Rabatt auf 80 €", ["12 €", "Du zahlst 68 €"]), ("80 € minus 15 % Rabatt", ["Du zahlst 68 €"]),
    ("19 % Umsatzsteuer auf 49,90 €", ["9,48 €", "59,38 €"]),
    ("3 Tuben zu je 9,90 Euro, was kostet das?", ["29,70 €", "3 × 9,90 € = 29,70 €"]), ("Ich kaufe 5 Semmeln à 0,45 €", ["2,25 €"]),
    ("Was kosten 4 Äpfel zu je 0,80 Euro?", ["3,20 €"]), ("4 Stück kosten zusammen 10 €, was kostet eines?", ["2,50 €"]),
    ("2 Kaffee zu je 3,40 € zusammen", ["6,80 €"]),
    ("Durchschnitt von 3, 5 und 10", ["Durchschnitt von 3, 5 und 10 ist 6", "(3 + 5 + 10) ÷ 3 = 18 ÷ 3 = 6"]), ("Summe von 1, 2, 3", ["ist 6"]),
    ("größte Zahl von 4, 9, 2", ["ist 9"]), ("kleinste Zahl von 4, 9, 2", ["ist 2"]), ("Median von 7, 1, 3, 9", ["ist 5", "Geordnet: 1, 3, 7, 9"]),
    ("Produkt von 2, 3, 4", ["ist 24"]), ("Mittelwert von 1,5 und 2,5", ["ist 2"]),
    ("3,14159 auf 2 Stellen runden", ["gerundet: 3,14."]), ("1234 auf Hunderter runden", ["gerundet: 1200."]), ("2,5 auf ganze Zahl runden", ["gerundet: 3."]),
    ("runde 7,456 auf 1 Stelle", ["gerundet: 7,5."]), ("0,125 auf 2 Stellen runden", ["gerundet: 0,13."]), ("1,5 auf ganze Zahl runden", ["gerundet: 2."]),
    ("Ist 91 eine Primzahl?", ["keine Primzahl", "7 × 13"]), ("Ist 97 eine Primzahl?", ["ist eine Primzahl"]), ("Ist 17 eine Primzahl?", ["ist eine Primzahl"]),
    ("Primfaktoren von 84", ["84 = 2 × 2 × 3 × 7 = 2² × 3 × 7"]), ("Teiler von 36", ["1, 2, 3, 4, 6, 9, 12, 18, 36 (insgesamt 9)"]),
    ("5 Fakultät", ["5! = 120", "5 × 4 × 3 × 2 = 120"]), ("10!", [f"3{N}628{N}800"]), ("255 in binär", ["11111111"]), ("255 in hex", ["FF"]),
    ("1010 binär in dezimal", ["dezimal 10"]), ("2026 in römischen Zahlen", ["MMXXVI"]), ("MMXXVI in arabische Zahlen", ["2026"]), ("1994 in römisch", ["MCMXCIV"]),
]


@pytest.mark.parametrize("frage,erwartet", [x for x in ALLTAG if x[1] is not None])
def test_alltagsrechnung(frage, erwartet):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in erwartet:
        assert teil in r.de, (frage, teil, r.de)
    assert r.en, frage
    if not any(c in frage for c in "äöüÄÖÜ"):
        assert "ü" not in r.en and "ä" not in r.en, r.en


DATUM = [
    ("Welcher Tag ist heute?", ["Heute ist Sonntag, 11.10.2026, Kalenderwoche 41."]), ("Welches Datum ist heute?", ["Sonntag, 11.10.2026"]),
    ("Den wievielten haben wir heute?", ["11.10.2026"]), ("Welche Kalenderwoche ist heute?", ["Kalenderwoche 41"]),
    ("Welche Kalenderwoche ist der 24.12.2026?", ["Kalenderwoche 52"]),
    ("Wie viele Tage bis Weihnachten?", ["Von Sonntag, 11.10.2026 bis Donnerstag, 24.12.2026 sind es 74 Tage (10 Wochen und 4 Tage)."]),
    ("Wie viele Tage sind es bis zum 24.12.2026?", ["74 Tage"]), ("Wie viele Wochen bis Silvester?", ["11 Wochen und 4 Tage (81 Tage)"]),
    ("Wie viele Monate bis 1.5.2027?", ["6 Monate und 20 Tage"]), ("Wie viele Tage bis morgen?", ["1 Tag"]),
    ("Tage zwischen 01.03.2026 und 15.05.2026", ["75 Tage"]), ("Wie viele Tage seit 1.1.2000?", ["9780 Tage"]),
    ("Was ist in 100 Tagen?", ["In 100 Tagen ist Dienstag, 19.1.2027."]), ("Datum in 6 Wochen", ["Sonntag, 22.11.2026"]), ("vor 30 Tagen", ["Vor 30 Tagen war Freitag, 11.9.2026."]),
    ("in 3 Monaten", ["Montag, 11.1.2027"]), ("30 Tage nach dem 1.1.2027", ["Sonntag, 31.1.2027"]), ("31.1.2026 plus 1 Monat", ["Samstag, 28.2.2026"]),
    ("Welcher Wochentag war der 1.1.2000?", ["Der 1.1.2000 war ein Samstag."]), ("Auf welchen Tag fällt Silvester?", ["31.12.2026 wird ein Donnerstag"]),
    ("Welcher Wochentag ist der 24.12.2026?", ["Donnerstag"]), ("Was für ein Tag war der 9.11.1989?", ["Donnerstag"]),
    ("Wie alt ist jemand der am 15.03.1985 geboren ist?", ["41 Jahre, 6 Monate und 26 Tage"]),
    ("Ist 2028 ein Schaltjahr?", ["ist ein Schaltjahr", "366 Tage"]), ("Ist 1900 ein Schaltjahr?", ["ist kein Schaltjahr", "365 Tage"]), ("Ist 2000 ein Schaltjahr?", ["ist ein Schaltjahr", "durch 400"]),
    ("Wie viele Tage hat der Februar 2028?", ["29 Tage"]), ("Wie viele Tage hat der Februar 2027?", ["28 Tage"]), ("Wie viele Tage hat 2028?", ["366 Tage"]),
    ("Wann ist Ostern 2027?", ["Sonntag, 28.3.2027"]), ("Wann ist Ostern?", ["28.3.2027"]), ("Wann ist Pfingsten 2026?", ["Sonntag, 24.5.2026"]),
]


@pytest.mark.parametrize("frage,erwartet", DATUM)
def test_datum(frage, erwartet):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in erwartet:
        assert teil in r.de, (frage, teil, r.de)
    assert r.en and "Sonntag" not in r.en and "Tage" not in r.en, r.en


def test_datum_formen_und_grenzen():
    h = date(2026, 10, 11)
    assert rechnen_datum.datum_lesen("24.12.", h) == date(2026, 12, 24) and rechnen_datum.datum_lesen("1.1.", h) == date(2027, 1, 1)
    assert rechnen_datum.datum_lesen("1.1.", h, vorwaerts=False) == date(2026, 1, 1)
    assert rechnen_datum.datum_lesen("24. Dezember 2026", h) == date(2026, 12, 24) and rechnen_datum.datum_lesen("2026-12-24", h) == date(2026, 12, 24)
    assert rechnen_datum.datum_lesen("31.2.2026", h) is None and rechnen_datum.datum_lesen("30.2.", h) is None
    assert rechnen_datum.datum_lesen("1.1.1500", h) is None
    assert rechnen_datum.datum_lesen("ostern 2027", h) == date(2027, 3, 28) and rechnen_datum.datum_lesen("heute", h) == h
    assert rechnen.loesen("Wie viele Tage bis 31.2.2027?") is None
    assert rechnen.loesen("Was ist in 99999999 Jahren?") is None


def test_wochentag_stimmt_gegen_kalender():
    def zeller(j, m, t):
        if m < 3:
            m += 12
            j -= 1
        k, c = j % 100, j // 100
        w = (t + (13 * (m + 1)) // 5 + k + k // 4 + c // 4 + 5 * c) % 7
        return ["Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][w]
    for j in range(1600, 2400, 37):
        for m, t in ((1, 1), (2, 28), (3, 1), (7, 14), (12, 31)):
            r = rechnen.loesen(f"Welcher Wochentag war der {t}.{m}.{j}?")
            assert r is not None and zeller(j, m, t) in r.de, (j, m, t, r)


def test_gewoehnliche_fragen_mit_datum_oder_zahl_bleiben_beim_modell():
    for f in ("Wann ist der nächste Feiertag in Österreich?", "Was war am 9.11.1989 los?", "Wie wird das Wetter am 24.12.?", "Wie lange dauert 3 Stunden Backen?",
              "Wer wurde 1985 geboren?", "Wie viele Tage hat der Urlaub?", "Ist Ostern ein Feiertag?", "Wie alt ist Mozart?", "Wie hoch ist der Dachstein 2026?",
              "Was kostet ein Kilo Brot zu je 2 Euro?", "Berechne mein Gehalt", "Welcher Tag ist ein guter Tag zum Heiraten?", "Wie viele Tage braucht ein Paket?",
              "Durchschnitt der Schüler in Linz", "Summe aller Zahlen", "Runde Zahl", "Ich bin 41 Jahre alt, wie alt bin ich in 5 Jahren?"):
        assert rechnen.loesen(f) is None, f
        assert absicht.erkennen(f).art != "rechnen", f


def test_absicht_nimmt_datum_und_alltag():
    assert absicht.erkennen("Welcher Tag ist heute?").art == "rechnen"
    assert absicht.erkennen("3 Tuben zu je 9,90 Euro, was kostet das?").art == "rechnen"
    assert absicht.erkennen("Ist 91 eine Primzahl?", hat_vorige_antwort=False).art == "rechnen"
