# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege
import nachschauen
import rechnen_zeit
import wissen


@pytest.mark.parametrize("frage,soll", [
    ("How much does a Eurail Global Pass cost?", "Eurail Global Pass cost"),
    ("Wie viel kostet ein Big Mac in der Schweiz?", "kostet Big Mac Schweiz"),
    ("Wie viele Kalorien hat ein Glas Wein?", "Kalorien Glas Wein"),
    ("Who won the last Formula 1 World Championship?", "won last Formula 1 World Championship"),
    ("Wie lange dauert ein Flug von Wien nach New York?", "lange dauert Flug Wien New York"),
    ("Ich brauche 3 Eier", "Eier"),
])
def test_k1_suchwoerter(frage, soll):
    assert nachschauen.suchbegriffe_regel(frage) == soll


_PENDLER = ("<p>Das große Pendlerpauschale steht zu, wenn die Benützung eines Massenverkehrsmittels nicht zumutbar ist.</p>"
            "<table><thead><tr><th scope='col'>Entfernung</th><th scope='col'>Betrag/Monat</th><th scope='col'>Jahresbetrag</th></tr></thead>"
            "<tbody><tr><td>bei mindestens 2 km bis 20 km</td><td>31,00 Euro</td><td>372,00 Euro</td></tr></tbody></table>")


def test_k2_zelle_traegt_tabelle_und_spalte():
    _t, text = wissen.html_zu_text(_PENDLER)
    assert "bei mindestens 2 km bis 20 km (Das große Pendlerpauschale steht zu, Betrag/Monat): 31,00 Euro" in text
    assert "bei mindestens 2 km bis 20 km (Das große Pendlerpauschale steht zu, Jahresbetrag): 372,00 Euro" in text


def test_k2_zwei_spalten_bleiben_wie_bisher():
    html = ("<p>Familienbeihilfe</p><table><tr><th>Alter</th><th>Betrag</th></tr><tr><td>ab 10 Jahren</td><td>171,80 Euro</td></tr></table>")
    assert "ab 10 Jahren: 171,80 Euro" in wissen.html_zu_text(html)[1]


def test_k2_offener_absatz_beschriftung_und_verneinung():
    tab = "<table>{c}<tr><th>A</th><th>B</th><th>C</th></tr><tr><td>x</td><td>1 Euro</td><td>12 Euro</td></tr></table>"
    assert "x (Kleines Pendlerpauschale, B): 1 Euro" in wissen.html_zu_text("<p>Alt.</p><b>Kleines Pendlerpauschale</b>" + tab.format(c=""))[1]
    assert "x (Großes Pendlerpauschale, C): 12 Euro" in wissen.html_zu_text(
        "<p>Text davor.</p>" + tab.format(c="<caption>Großes Pendlerpauschale</caption>"))[1]
    nein = wissen.html_zu_text("<p>Kein Anspruch besteht, wenn du weniger fährst.</p>" + tab.format(c=""))[1]
    assert "x (B): 1 Euro" in nein and "Kein Anspruch besteht, wenn du weniger fährst. (" not in nein.replace("\n", " ").split("A B C")[1]
    assert "x (Offene Beschriftung, B): 1 Euro" in wissen.html_zu_text(
        "<table><caption>Offene Beschriftung<tr><th>A</th><th>B</th><th>C</th></tr><tr><td>x</td><td>1 Euro</td><td>12 Euro</td></tr></table>")[1]
    schief = "<p>P</p><table><tr><th>A</th><th>B</th><th>C</th></tr><tr><td>x</td><td colspan='2'>1 Euro</td></tr></table>"
    assert "(P" not in wissen.html_zu_text(schief)[1]


def test_k2_kopf_ueber_mehrere_spalten_zaehlt_nicht():
    html = ("<p>Preise</p><table><tr><th>Klasse</th><th colspan='2'>Preis</th></tr><tr><td>2A</td><td>16 Euro</td><td>32 Euro</td></tr></table>")
    assert "(Preise" not in wissen.html_zu_text(html)[1]


@pytest.mark.parametrize("frage,rueckfrage", [
    ("Was ist der Unterschied zwischen Brutto und Netto?", False),
    ("What is the difference between a Roth IRA and a traditional IRA?", False),
    ("Wie hoch ist die Mehrwertsteuer?", True),
])
def test_k3_unterschied_ist_eine_erklaerung(frage, rueckfrage):
    assert (nachschauen.land_rueckfrage([{"role": "user", "content": frage}]) is not None) is rueckfrage


@pytest.fixture
def november(monkeypatch):
    monkeypatch.setattr(rechnen_zeit, "jetzt_utc", lambda: datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc))


def test_k4_zeitumstellung_usa(november):
    r = rechnen_zeit.loesen("When does daylight saving time end in the US?")
    assert r.en.startswith("In the US, daylight saving time ends on Sunday, November 7, 2027, when clocks go back from 2 am to 1 am.")


def test_k4_winterzeit_jahr_australien(november):
    assert rechnen_zeit.loesen("Wann endet die Winterzeit?").de.startswith("In Europa (EU und Schweiz) beginnt die Sommerzeit am Sonntag, 28. März 2027")
    assert rechnen_zeit.loesen("Wann beginnt die Winterzeit?").de.startswith("In Europa (EU und Schweiz) endet die Sommerzeit am Sonntag, 31. Oktober 2027")
    assert "26. März 2028" in rechnen_zeit.loesen("Wann ist die Zeitumstellung 2028?").de
    assert rechnen_zeit.loesen("When does DST start in Australia?") is None


def test_k4_zeitumstellung_europa_und_london(november):
    assert rechnen_zeit.loesen("Wann ist die nächste Zeitumstellung?").de.startswith(
        "In Europa (EU und Schweiz) beginnt die Sommerzeit am Sonntag, 28. März 2027: die Uhr wird um 2 Uhr auf 3 Uhr vorgestellt.")
    assert "um 2 Uhr auf 1 Uhr zurückgestellt" in rechnen_zeit.loesen("Wann endet die Sommerzeit in London?").de
    assert "no daylight saving time" in rechnen_zeit.loesen("When does DST start in Tokyo?").en
    assert rechnen_zeit.loesen("Wann ist Weihnachten?") is None


def test_k5_oeffnungszeiten_verlangen_uhrzeiten():
    assert "Öffnungszeiten" not in app_web.frage_fokus("Warum kann die Datei nicht geöffnet werden?")
    assert "Öffnungszeiten" not in app_web.frage_fokus("Wann wurde die Berliner Mauer geöffnet?")
    assert "opening hours" in app_web.frage_fokus("What are the opening hours of the Louvre?")
    assert "Uhrzeiten" in app_web.frage_fokus("Wann hat der Billa am Sonntag geöffnet?")
    assert "Öffnungszeiten" not in app_web.frage_fokus("Wie hoch ist der Mindestlohn?")


def test_k6_nachgeschaut_ist_der_lesezeitpunkt():
    from datetime import datetime, timedelta, timezone
    jetzt = datetime.now(timezone.utc).replace(microsecond=0)

    class E:
        art = "suche"
        gueltig_bis = (jetzt - timedelta(seconds=30) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert app_web._gelesen_um(E()) == (jetzt - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    class Alt:
        art = "suche"
        gueltig_bis = "2026-01-08T10:00:00Z"
    assert app_web._gelesen_um(Alt()) != "2026-01-01T10:00:00Z"
    assert app_web._gelesen_um(object())


def test_k7_schlusssatz_widerspricht():
    a = "For most others, it is 10 years of residency. The overall process can take between 1 and 3 years."
    assert belege.angehaengte_saetze(a) == ["The overall process can take between 1 and 3 years."]
    assert belege.angehaengte_saetze("Kinder zahlen 5 bis 10 Euro. Erwachsene 20 Euro. Insgesamt kostet es 30 bis 40 Euro.") == []


def test_k11_wiederholung_und_satz_ueber_die_frage():
    b = ("Parents receive 480 days of paid parental leave, which can be shared between both parents. Since the question asks about fathers, "
         "the total 480 days are available.\n\nAgain, this is shared between both parents.")
    assert belege.angehaengte_saetze(b) == ["Again, this is shared between both parents."]
    assert belege.angehaengte_saetze("Der Pass kostet 75 Euro. Noch einmal: der neue Pass gilt 10 Jahre.") == []
    assert belege.angehaengte_saetze("Parents get 480 days. Since the question is about fathers: 90 of these days are reserved for the father.") == []
    assert belege.angehaengte_saetze("It costs 60 euros. Again, it costs 75 euros, not 60.") == []
    assert belege.angehaengte_saetze("Parents get 480 days, shared between both parents. Since the question asks, shared between both parents.") \
        == ["Since the question asks, shared between both parents."]


def test_k7_gemischte_trenner_ohne_absturz():
    assert belege._anh_zahl("1.234,56") == 1234.56 and belege._anh_zahl("1,234.56") == 1234.56
    assert belege._anh_zahl("0,125") == 0.125 and belege._anh_zahl("1.100") == 1100
    assert belege.angehaengte_saetze("Der Preis ist 1.234,56 Euro. Insgesamt zahlst du 1.200 bis 1.300 Euro.") == []
    assert belege.angehaengte_saetze("Teil A kostet 2.500,00 Euro. Insgesamt zahlst du 1.000 bis 1.200 Euro.") == ["Insgesamt zahlst du 1.000 bis 1.200 Euro."]


def test_k7_tausender_und_je_monat():
    assert belege.angehaengte_saetze("Die Miete beträgt 950 Euro. Betriebskosten 150 Euro. Insgesamt zahlst du 1.100 bis 1.200 Euro.") == []
    assert belege.angehaengte_saetze("Der Kurs kostet 500 Euro. Insgesamt zahlst du pro Monat 40 bis 50 Euro.") == []


@pytest.mark.parametrize("titel,adresse,soll", [
    ("Flugzeit von Wien nach New York | Flugdauer-Rechner", "https://flightdurationcalculator.com/de/flugzeit/vienna/new-york", True),
    ("Cost of a Eurail Pass", "https://travel.costhelper.com/eurail-passes.html", True),
    ("Eurail Global Pass", "https://www.eurail.com/en/eurail-passes/global-pass", False),
    ("Brutto-Netto-Rechner", "https://www.bmf.gv.at/rechner/", False),
    ("Tarifrechner – Wien Energie", "https://www.wienenergie.at/tarifrechner", False),
    ("Rechner & PCs kaufen", "https://www.example-shop.at/rechner", False),
])
def test_k9_schaetzseite(titel, adresse, soll):
    assert nachschauen.schaetzseite(titel, adresse) is soll
    zeile = nachschauen.gefunden_zeile(titel, adresse, "22.11.2026", "Text")
    assert (nachschauen.SCHAETZ_SATZ in zeile) is soll
