# SPDX-License-Identifier: AGPL-3.0-or-later
import random
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rechnen
import rechnen_datum
import rechnen_gehalt as rg

N = "\u00a0"


@pytest.fixture(autouse=True)
def _heute(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 10, 11))


def F(*a):
    return Fraction(*a)


BELEGT = {
    F(3000): dict(sv=F("542.10"), lst=F("283.82"), netto=F("2174.08"), sonder1=F("2375.83"), sonder2=F("2338.63")),
    F(2690): dict(sv=F("486.08"), lst=F("207.63"), netto=F("1996.29"), sonder1=F("2134.17"), sonder2=F("2096.97")),
    F(6660): dict(sv=F("1203.46"), lst=F("1424.15"), netto=F("4032.39")),
}


@pytest.mark.parametrize("brutto", sorted(BELEGT))
def test_gegen_veroeffentlichte_beispiele(brutto):
    e = rg.netto_rechnen(brutto, 14)
    for k, v in BELEGT[brutto].items():
        assert e[k] == v, (brutto, k, e[k], v)


def test_jahresnetto_3000_wie_quelle():
    assert abs(rg.netto_rechnen(F(3000))["jahr"] - F("30803.41")) <= F("0.01")


def test_tarif_gegen_fixbetragsformeln_der_wko():
    stufen = [(F(13539), F(21992), F(20, 100), F("2707.80")), (F(21992), F(36458), F(30, 100), F("4907.00")), (F(36458), F(70365), F(40, 100), F("8552.80")),
              (F(70365), F(104859), F(48, 100), F("14182.00")), (F(104859), F(1000000), F(50, 100), F("16279.18")), (F(1000000), F(10 ** 7), F(55, 100), F("66279.18"))]
    rnd = random.Random(1)
    for von, bis, satz, fix in stufen:
        for _ in range(200):
            x = von + Fraction(rnd.randint(1, 10 ** 6), 10 ** 6) * (bis - von)
            assert abs(rg.einkommensteuer(x) - (x * satz - fix)) <= F("0.5"), (von, x)
    assert rg.einkommensteuer(F(13539)) == 0 and rg.einkommensteuer(F(10000)) == 0


def test_netto_waechst_mit_brutto():
    letzter, av_letzt = Fraction(0), None
    for b in range(1000, 20001, 7):
        e = rg.netto_rechnen(Fraction(b))
        if rg._av(Fraction(b)) == av_letzt:
            assert e["netto"] >= letzter - F("0.02"), b
        letzter, av_letzt = e["netto"], rg._av(Fraction(b))
        assert e["netto"] + e["sv"] + e["lst"] == b
        assert 0 <= e["lst"] < b and 0 < e["sv"] < b


def test_rueckwaerts_trifft_das_netto():
    rnd = random.Random(2)
    for _ in range(200):
        ziel = Fraction(rnd.randint(90000, 1000000), 100)
        b = rg.brutto_zu_netto(ziel)
        e = rg.netto_rechnen(b)
        assert e["netto"] >= ziel
        e2 = rg.netto_rechnen(b - F("0.01"))
        assert e2["netto"] < ziel


FRAGEN = [
    ("3.000 € brutto in netto", ["Bei 3000 € brutto im Monat mit 14 Gehältern", "Netto im Monat: 2174,08 € (Sozialversicherung 542,10 €, Lohnsteuer 283,82 €)", "2375,83 € und 2338,63 €", "Überschlag, kein Lohnzettel"],
     ["At €3,000 gross per month with 14 salaries", "Net per month: €2,174.08", "not a payslip"]),
    ("Was bleibt netto von 2.690 brutto?", ["Netto im Monat: 1996,29 €", "2134,17 € und 2096,97 €"], ["Net per month: €1,996.29"]),
    ("6660 brutto netto", ["Netto im Monat: 4032,39 €"], ["Net per month: €4,032.39"]),
    ("Brutto 3000, 12 Gehälter", ["mit 12 Gehältern", "Netto im Monat: 2174,08 €", "Im Jahr: 26088,96 € netto"], ["with 12 salaries"]),
    ("40.000 € Jahresbrutto netto", ["2857,14 € brutto im Monat (40"], ["per year"]),
    ("Ich will 2.500 € netto, wie viel brutto brauche ich?", ["Für 2500 € netto im Monat brauchst du ungefähr 3568,29 € brutto", "netto laufend 2500 €"], ["For €2,500 net per month you need about €3,568.29 gross"]),
    ("What is the net of 3000 gross", ["Netto im Monat: 2174,08 €"], ["Net per month: €2,174.08"]),
]


@pytest.mark.parametrize("frage,de,en", FRAGEN)
def test_fragen(frage, de, en):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in de:
        assert teil in r.de.replace(N, ""), (frage, teil, r.de)
    for teil in en:
        assert teil in r.en, (frage, teil, r.en)


@pytest.mark.parametrize("text", [
    "100 € netto in brutto bei 20 %", "Was kostet das netto?", "brutto", "Netto", "Mein Gehalt ist zu niedrig, was soll ich tun? 3000 brutto", "3000 brutto 4000 netto", "300 brutto", "500000 brutto", "100 netto", "Brutto netto erklärt",
    "Ich verdiene 3000 brutto, soll ich kündigen oder Vollzeit bleiben und ein Haus kaufen", "Was ist der Unterschied zwischen brutto und netto", "3000 brutto 7 Gehälter", "3000 € brutto Mwst", "Brutto 3000 netto Rabatt 10%",
])
def test_keine_gehaltsaufgabe(text):
    r = rechnen.loesen(text)
    assert r is None or "Sozialversicherung" not in r.de, (text, r and r.de)


def test_spaeteres_jahr_wird_offen_gesagt(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2027, 2, 1))
    r = rechnen.loesen("3000 brutto in netto")
    assert "Achtung: das sind die Werte von 2026, 2027 kann es anders sein." in r.de
    assert "these are the 2026 values" in r.en
