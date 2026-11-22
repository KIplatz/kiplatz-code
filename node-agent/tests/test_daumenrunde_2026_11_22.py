# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen
import rechnen
import rechnen_zeit

WINTER = datetime(2026, 11, 22, 18, 4, tzinfo=timezone.utc)
SOMMER = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def uhr(monkeypatch):
    def stellen(t):
        monkeypatch.setattr(rechnen_zeit, "jetzt_utc", lambda: t)
    return stellen


def test_zeitzone_perth_rechnet_das_programm(uhr):
    uhr(WINTER)
    r = rechnen_zeit.loesen("What time zone is Perth in?")
    assert r.en == "Perth uses UTC+8, with no daylight saving time. It is 2:04 AM there right now (Monday), by this device's clock."
    assert r.de.startswith("Perth hat UTC+8, ohne Sommerzeit. Dort ist es jetzt 02:04")


@pytest.mark.parametrize("frage,soll", [
    ("Welche Zeitzone hat Indien?", "UTC+5:30, ohne Sommerzeit"),
    ("In welcher Zeitzone liegt New York?", "gerade Normalzeit, UTC-5; in der Sommerzeit gilt UTC-4"),
    ("Zeitzone von Sydney", "gerade Sommerzeit, UTC+11; sonst gilt UTC+10"),
    ("Which time zone does Tokyo use", "UTC+9, ohne Sommerzeit"),
    ("time zone of London", "gerade Normalzeit, UTC+0"),
])
def test_zeitzone_mit_sommerzeit(uhr, frage, soll):
    uhr(WINTER)
    assert soll in rechnen_zeit.loesen(frage).de


def test_zeitzone_im_sommer(uhr):
    uhr(SOMMER)
    assert "gerade Sommerzeit, UTC+2; sonst gilt UTC+1" in rechnen_zeit.loesen("Welche Zeitzone hat Wien?").de


@pytest.mark.parametrize("frage", ["What time zone is Australia in?", "Welche Zeitzone hat Brasilien?", "Zeitzone von Mexiko",
                                   "What time zone is Mars in?", "Welche Zeitzone ist die beste für Meetings?"])
def test_zeitzone_raet_nicht(uhr, frage):
    uhr(WINTER)
    assert rechnen_zeit.loesen(frage) is None


def test_temperatur_mit_rechenweg():
    r = rechnen.loesen("How do I convert 350 Fahrenheit to Celsius?")
    assert r.en == "350 °F is about 176.6667 °C. Formula: (°F − 32) × 5 ÷ 9."
    assert rechnen.loesen("180 Grad Celsius in Fahrenheit").de == "180 °C sind 356 °F. Gerechnet: °C × 9 ÷ 5 + 32."
    assert rechnen.loesen("100 C in K").de == "100 °C sind 373,15 K."
    assert "Gerechnet" not in rechnen.loesen("200 C in F und K").de


@pytest.mark.parametrize("frage,soll", [
    ("Wie hoch ist das Kindergeld?", ("Kindergeld", "Deutschland")),
    ("How much is Kindergeld per child?", ("Kindergeld", "Deutschland")),
    ("Wie hoch ist die Familienbeihilfe?", ("Familienbeihilfe", "Österreich")),
    ("Wie hoch ist das Kindergeld in Österreich?", None),
    ("Wie hoch ist das Kindergeld in der Schweiz?", None),
    ("Wann ist die Matura?", None),
    ("Abitur oder Matura, was ist schwerer?", None),
    ("Wie hoch ist der Mindestlohn?", None),
    ("Was frisst eine Elster?", None),
    ("Flights from AMS to JFK", None),
    ("Is PVA glue waterproof?", None),
    ("Wer ist Peter Hartz?", None),
    ("E-Card zum Geburtstag verschicken", None),
    ("Was regelt ein Kollektivvertrag?", None),
])
def test_land_aus_begriff(frage, soll):
    assert nachschauen.land_aus_begriff(frage) == soll


def test_fokus_nennt_das_land():
    assert "mit „Kindergeld“ ist meist die Leistung in Deutschland gemeint" in app_web.frage_fokus("Wie hoch ist das Kindergeld?")
    en = app_web.frage_fokus("How much is Kindergeld per child?")
    assert "usually means the one in Germany" in en and "Deutschland" not in en
    assert "meist die Leistung" not in app_web.frage_fokus("Wie hoch ist der Mindestlohn in Deutschland?")


def test_whats_the_time_zone(uhr):
    uhr(WINTER)
    assert rechnen_zeit.loesen("What's the time zone in London?").en.startswith("London is on standard time right now, UTC+0")


@pytest.mark.parametrize("frage,soll", [
    ("Wie heißt der Bundeskanzler von Deutschland?", True),
    ("What's the name of the president of France?", True),
    ("Wie heißt der erste Bundeskanzler von Deutschland?", False),
    ("Wie heißt die Hauptstadt von Kanada?", False),
    ("Wie heißt die Bürgermeisterin von Paris?", True),
    ("Wie heißt der König der Löwen?", False),
    ("Wie heißt der Präsident in Star Wars?", False),
    ("Wie heißt Kaiserschnitt auf Englisch?", False),
    ("Wie heißt Königsberg heute?", False),
])
def test_wie_heisst_ist_eine_amtsfrage(frage, soll):
    assert nachschauen.amtsfrage(frage) is soll


def test_amtsfrage_sucht_ohne_vermuteten_namen():
    from datetime import date
    out = app_web.suchwoerter_ordnen(["Olaf Scholz Bundeskanzler Deutschland 2024–2026 Amtssitz Berlin offizielle Website",
                                      "Bundeskanzler Deutschland aktuell 2026"], "Wie heißt der Bundeskanzler von Deutschland?", "", date(2026, 11, 22))
    assert out == ["Bundeskanzler Deutschland 2026", "Bundeskanzler Deutschland"]
    assert not any("Scholz" in q for q in out)
    assert app_web.suchwoerter_ordnen(["Ottawa Hauptstadt Kanada"], "Wie heißt die Hauptstadt von Kanada?", "", date(2026, 11, 22)) == ["Ottawa Hauptstadt Kanada"]


def test_amtsfrage_erbt_kein_fremdes_thema():
    from datetime import date
    d = date(2026, 11, 22)
    out = app_web.suchwoerter_ordnen(["Papst Franziskus"], "Wer ist Papst?", "Wie wird das Wetter in Linz?", d)
    assert out and not any("Linz" in q or "Franziskus" in q for q in out)
    assert any("Linz" in q for q in app_web.suchwoerter_ordnen(["x"], "Wer ist dort Bürgermeister?", "Wie viele Einwohner hat Linz?", d))


def test_amtsfrage_behaelt_das_gefragte_jahr():
    from datetime import date
    out = app_web.suchwoerter_ordnen(["Bürgermeister Wien"], "Wer ist 2020 Bürgermeister von Wien?", "", date(2026, 11, 22))
    assert out and all("2020" in q and "2026" not in q for q in out)
    out = app_web.suchwoerter_ordnen([], "Wer ist Bundeskanzler von Deutschland?", "", date(2026, 11, 22))
    assert not any(q.count("2026") > 1 for q in out)
