# SPDX-License-Identifier: AGPL-3.0-or-later
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import absicht
import app_web as aw
import rechnen
import rechnen_geld

KLEIN = "Ministral 3 3B"
N = " "


def test_philipps_frage_wird_gerechnet_mit_hinweis_auf_den_tippfehler():
    r = rechnen.loesen("wieviel sind 188dm in cm und milimeter")
    assert r is not None
    assert "1880 cm" in r.de and "18" + N + "800 mm" in r.de
    assert "Ich habe „milimeter“ als „Millimeter“ gelesen." in r.de
    assert "I read “milimeter” as “Millimeter”." in r.en
    a = absicht.erkennen("wieviel sind 188dm in cm und milimeter")
    assert a.art == "rechnen" and a.gemacht == "gerechnet" and "1880 cm" in a.antwort


@pytest.mark.parametrize("text,erwartet,gelesen", [
    ("wieviel sind 5 kilometr in meter", "5000 m", "„kilometr“ als „Kilometer“"),
    ("wie viel sind 3 zentimter in millimeter", "30 mm", "„zentimter“ als „Zentimeter“"),
    ("10 Liter in Mililiter", "10" + N + "000 ml", "„mililiter“ als „Milliliter“"),
    ("2 kilogram in gramm", "2000 g", None),
])
def test_tippfehler_in_einheiten(text, erwartet, gelesen):
    r = rechnen.loesen(text)
    assert r is not None, text
    assert erwartet in r.de, (text, r.de)
    if gelesen:
        assert gelesen in r.de, r.de


@pytest.mark.parametrize("text", [
    "Wie viel Meterware kostet 5 Meter", "5 Hektarbüchse in Quadratmetern", "5 Bananen in Kilo", "5 Wurzelmeterstunden in cm", "5 Millimetern in blau",
])
def test_unbekannte_woerter_werden_nicht_zur_einheit_erraten(text):
    r = rechnen.loesen(text)
    assert r is None or "gelesen" not in r.de, (text, r and r.de)


def test_tippfehler_markierung_bleibt_nicht_haengen():
    rechnen.loesen("10 Liter in Mililiter")
    r = rechnen.loesen("10 Liter in Milliliter")
    assert "gelesen" not in r.de


@pytest.mark.parametrize("frage", [
    "wieviel sind 188dm in cm und milimeter", "wieviel sind 3 Stunden in Minuten", "wieviel sind 5 Zoll in cm", "Wie viel sind 2 Pfund in Gramm?", "Wieviel km sind 20 Meilen in km",
    "wieviel sind 100 km/h in m/s",
])
def test_umrechnung_ist_keine_wissensfrage(frage):
    assert rechnen.ist_umrechnungsfrage(frage), frage
    assert not aw.klein_wissensfrage(KLEIN, frage), frage


@pytest.mark.parametrize("frage", [
    "Wer betrat als erster Mensch den Mond?", "Wie viel kostet 1 kg Äpfel in Linz", "Wie viele Einwohner hat Linz in 2 km Umkreis", "Wann wurde die Burg Krevenstein in Kärnten erbaut?",
    "Welcher ist der längste Fluss Europas?", "Wie hoch ist der Mount Everest in Metern",
])
def test_wissensfragen_bleiben_wissensfragen(frage):
    assert not rechnen.ist_umrechnungsfrage(frage), frage
    if frage.startswith(("Wer", "Wann", "Welcher")):
        assert aw.klein_wissensfrage(KLEIN, frage), frage


def test_kein_steuerzeichen_im_regulaeren_ausdruck():
    for datei in sorted(Path(rechnen_geld.__file__).parent.glob("*.py")):
        quelle = datei.read_text(encoding="utf-8")
        assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", quelle), datei.name
    r = rechnen.loesen("100 km/h, 6,5 l/100 km, 1,65 €/l")
    assert r is None or "Fahrt" not in r.de


def test_hinweis_steht_bei_aufzaehlungen_in_eigener_zeile():
    r = rechnen.loesen("wieviel sind 188dm in cm und milimeter")
    zeilen = r.de.split("\n")
    assert zeilen[-1] == "(Ich habe „milimeter“ als „Millimeter“ gelesen.)" and zeilen[-2].startswith("– 18" + N + "800 mm") and "gelesen" not in zeilen[-2]
    assert r.en.split("\n")[-1] == "(I read “milimeter” as “Millimeter”.)"
    e = rechnen.loesen("wieviel sind 5 kilometr in meter")
    assert "\n" not in e.de and e.de.endswith("(Ich habe „kilometr“ als „Kilometer“ gelesen.)")
