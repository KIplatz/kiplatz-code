# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rechnen
import rechnen_datum
import rechnen_zeit as rz

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _uhr(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 10, 11))
    monkeypatch.setattr(rz, "jetzt_utc", lambda: datetime(2026, 10, 11, 14, 20, tzinfo=UTC))


def _zone(n):
    return rz._BEKANNT[n]


EU = {2024: (date(2024, 3, 31), date(2024, 10, 27)), 2025: (date(2025, 3, 30), date(2025, 10, 26)), 2026: (date(2026, 3, 29), date(2026, 10, 25)),
      2027: (date(2027, 3, 28), date(2027, 10, 31)), 2028: (date(2028, 3, 26), date(2028, 10, 29))}
US = {2024: (date(2024, 3, 10), date(2024, 11, 3)), 2025: (date(2025, 3, 9), date(2025, 11, 2)), 2026: (date(2026, 3, 8), date(2026, 11, 1)),
      2027: (date(2027, 3, 14), date(2027, 11, 7))}
AU_ENDE_BEGINN = {2025: (date(2025, 4, 6), date(2025, 10, 5)), 2026: (date(2026, 4, 5), date(2026, 10, 4))}
NZ_ENDE_BEGINN = {2025: (date(2025, 4, 6), date(2025, 9, 28)), 2026: (date(2026, 4, 5), date(2026, 9, 27))}


@pytest.mark.parametrize("jahr", sorted(EU))
def test_eu_umstellung(jahr):
    beginn, ende = EU[jahr]
    wien = _zone("wien")
    assert rz.versatz(wien, datetime(beginn.year, beginn.month, beginn.day, 0, 59, tzinfo=UTC)) == 60
    assert rz.versatz(wien, datetime(beginn.year, beginn.month, beginn.day, 1, 0, tzinfo=UTC)) == 120
    assert rz.versatz(wien, datetime(ende.year, ende.month, ende.day, 0, 59, tzinfo=UTC)) == 120
    assert rz.versatz(wien, datetime(ende.year, ende.month, ende.day, 1, 0, tzinfo=UTC)) == 60
    assert rz.versatz(_zone("london"), datetime(beginn.year, beginn.month, beginn.day, 1, 0, tzinfo=UTC)) == 60
    assert rz.versatz(_zone("athen"), datetime(ende.year, ende.month, ende.day, 0, 59, tzinfo=UTC)) == 180


@pytest.mark.parametrize("jahr", sorted(US))
def test_us_umstellung(jahr):
    beginn, ende = US[jahr]
    ny = _zone("new york")
    assert rz.versatz(ny, datetime(beginn.year, beginn.month, beginn.day, 6, 59, tzinfo=UTC)) == -300
    assert rz.versatz(ny, datetime(beginn.year, beginn.month, beginn.day, 7, 0, tzinfo=UTC)) == -240
    assert rz.versatz(ny, datetime(ende.year, ende.month, ende.day, 5, 59, tzinfo=UTC)) == -240
    assert rz.versatz(ny, datetime(ende.year, ende.month, ende.day, 6, 0, tzinfo=UTC)) == -300
    la = _zone("los angeles")
    assert rz.versatz(la, datetime(beginn.year, beginn.month, beginn.day, 9, 59, tzinfo=UTC)) == -480
    assert rz.versatz(la, datetime(beginn.year, beginn.month, beginn.day, 10, 0, tzinfo=UTC)) == -420


@pytest.mark.parametrize("jahr", sorted(AU_ENDE_BEGINN))
def test_australien_neuseeland(jahr):
    ende, beginn = AU_ENDE_BEGINN[jahr]
    sydney = _zone("sydney")
    vortag = ende - timedelta(days=1)
    assert rz.versatz(sydney, datetime(vortag.year, vortag.month, vortag.day, 15, 59, tzinfo=UTC)) == 660
    assert rz.versatz(sydney, datetime(vortag.year, vortag.month, vortag.day, 16, 0, tzinfo=UTC)) == 600
    vortag = beginn - timedelta(days=1)
    assert rz.versatz(sydney, datetime(vortag.year, vortag.month, vortag.day, 15, 59, tzinfo=UTC)) == 600
    assert rz.versatz(sydney, datetime(vortag.year, vortag.month, vortag.day, 16, 0, tzinfo=UTC)) == 660
    ende, beginn = NZ_ENDE_BEGINN[jahr]
    ak = _zone("auckland")
    vortag = beginn - timedelta(days=1)
    assert rz.versatz(ak, datetime(vortag.year, vortag.month, vortag.day, 13, 59, tzinfo=UTC)) == 720
    assert rz.versatz(ak, datetime(vortag.year, vortag.month, vortag.day, 14, 0, tzinfo=UTC)) == 780
    vortag = ende - timedelta(days=1)
    assert rz.versatz(ak, datetime(vortag.year, vortag.month, vortag.day, 13, 59, tzinfo=UTC)) == 780
    assert rz.versatz(ak, datetime(vortag.year, vortag.month, vortag.day, 14, 0, tzinfo=UTC)) == 720


def test_orte_ohne_umstellung():
    for n in ("tokio", "dubai", "delhi", "peking", "moskau", "istanbul", "sao paulo", "honolulu", "brisbane", "mexiko stadt"):
        z = _zone(n)
        for monat in (1, 4, 7, 10):
            assert rz.versatz(z, datetime(2026, monat, 15, 12, tzinfo=UTC)) == z[2]


def test_sonntag_hilfe():
    for jahr in range(2000, 2060):
        for monat in range(1, 13):
            for nr in (1, 2, -1):
                d = rz._sonntag(jahr, monat, nr)
                assert d.weekday() == 6 and d.month == monat
        assert (rz._sonntag(jahr, 3, -1) + timedelta(days=7)).month == 4


def test_philipp_jetzt_in_oesterreich_16_20():
    assert rz.ortszeit(_zone("wien"), rz.jetzt_utc()).strftime("%H:%M") == "16:20"
    r = rechnen.loesen("Wie spät ist es in Wien?")
    assert "16:20 Uhr (Sonntag)" in r.de and "4:20 PM" in r.en


def test_hin_und_zurueck_ueber_viele_tage():
    wien, ny, sydney = _zone("wien"), _zone("new york"), _zone("sydney")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(0, 24 * 2 * 365 * 2, 7):
        utc = start + timedelta(minutes=30 * i)
        for z in (wien, ny, sydney):
            lokal = rz.ortszeit(z, utc)
            if rz.ortszeit(z, rz.aus_ortszeit(z, lokal)) != lokal:
                pytest.fail(f"{z[0]} {utc}")
            back = rz.aus_ortszeit(z, lokal)
            if back != utc:
                assert abs((back - utc).total_seconds()) == 3600


FRAGEN = [
    ("Es ist 18 Uhr in Wien, wie spät in New York?", ["18:00 Uhr in Wien sind 12:00 Uhr in New York", "Wien ist New York 6 Stunden voraus"], ["18:00 in Vienna is 12:00 in New York"]),
    ("18:30 Wien in Tokio", ["sind 01:30 Uhr in Tokio (am nächsten Tag)", "Tokio 7 Stunden hinterher"], ["01:30 in Tokyo (the next day)"]),
    ("Wenn es in Tokio 9:00 Uhr ist, wie spät ist es in Wien?", ["09:00 Uhr in Tokio sind 02:00 Uhr in Wien"], ["Tokyo is 7 hours ahead of Vienna"]),
    ("What time is it in Tokyo when it's 6 pm in Vienna?", ["18:00 Uhr in Wien sind 01:00 Uhr in Tokio"], ["6:00 PM in Vienna is 1:00 AM in Tokyo"]),
    ("Wie spät ist es in New York wenn es in Wien 20:15 Uhr ist?", ["20:15 Uhr in Wien sind 14:15 Uhr in New York"], ["20:15 in Vienna is 14:15 in New York"]),
    ("12:00 London in Wien", ["12:00 Uhr in London sind 13:00 Uhr in Wien"], ["London is 1 hour behind Vienna"]),
    ("20 Uhr Wien in Los Angeles", ["sind 11:00 Uhr in Los Angeles"], ["Vienna is 9 hours ahead of Los Angeles"]),
    ("9:00 Delhi in Wien", ["sind 05:30 Uhr in Wien", "Delhi ist Wien 3,5 Stunden voraus"], ["3.5 hours ahead"]),
    ("Wie spät ist es in Sydney?", ["In Sydney ist es jetzt 01:20 Uhr (Montag)"], ["1:20 AM in Sydney right now (Monday)"]),
    ("What time is it in New York", ["10:20 Uhr (Sonntag)"], ["10:20 AM in New York right now (Sunday)"]),
    ("Wie lange dauert 22:15 bis 06:40?", ["8 Stunden und 25 Minuten", "über Mitternacht"], ["8 hours and 25 minutes", "past midnight"]),
    ("von 8:30 bis 17:00 mit 30 Minuten Pause", ["8 Stunden und 30 Minuten", "ohne 30 Minuten Pause 8 Stunden"], ["without a 30 minute break 8 hours"]),
    ("Wie viele Stunden von 8 bis 17 Uhr", ["9 Stunden"], ["is 9 hours"]),
    ("Wie lange von 7:15 bis 15:45", ["8 Stunden und 30 Minuten (8,5 Stunden)"], ["(8.5 hours)"]),
    ("14:20 plus 2 Stunden 30 Minuten", ["ist 16:50 Uhr"], ["is 16:50"]),
    ("3 Stunden nach 14:20", ["ist 17:20 Uhr"], ["plus 3 hours is 17:20"]),
    ("90 Minuten vor 8:00", ["ist 06:30 Uhr"], ["minus 1 hour and 30 minutes is 06:30"]),
    ("23:30 + 45 Minuten", ["ist 00:15 Uhr (am nächsten Tag)"], ["(the next day)"]),
    ("0:20 minus 30 Minuten", ["ist 23:50 Uhr (am Vortag)"], ["(the day before)"]),
]


@pytest.mark.parametrize("frage,de,en", FRAGEN)
def test_fragen(frage, de, en):
    r = rechnen.loesen(frage)
    assert r is not None, frage
    for teil in de:
        assert teil in r.de, (frage, teil, r.de)
    for teil in en:
        assert teil in r.en, (frage, teil, r.en)


def test_winterzeit_unterschied(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 11, 10))
    r = rechnen.loesen("Es ist 18 Uhr in Wien, wie spät in New York?")
    assert "12:00 Uhr in New York" in r.de and "6 Stunden" in r.de
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 10, 28))
    r = rechnen.loesen("Es ist 18 Uhr in Wien, wie spät in New York?")
    assert "13:00 Uhr in New York" in r.de and "5 Stunden" in r.de


def test_hinweis_vor_umstellung(monkeypatch):
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 10, 22))
    r = rechnen.loesen("18 Uhr Wien in New York")
    assert "Achtung" in r.de and "Note:" in r.en
    monkeypatch.setattr(rechnen_datum, "heute", lambda: date(2026, 7, 15))
    assert "Achtung" not in rechnen.loesen("18 Uhr Wien in New York").de


@pytest.mark.parametrize("text", [
    "Wie spät ist es?", "Wien", "18 Uhr", "Wann beginnt das Spiel in Wien um 18 Uhr", "18 Uhr in Wien", "Ich fliege um 18 Uhr von Wien nach Tokio, wie lange dauert der Flug?",
    "Wie lange dauert der Flug von Wien nach New York", "18:00 Wien in Atlantis", "Wie spät ist es in Gotham", "Wien in Tokio", "Es ist 25:61 Uhr in Wien, wie spät in Tokio",
    "von 8 bis 17", "8 bis 9", "Von 8 bis 18 Uhr.", "9 bis 20 Uhr", "Das Freibad hat von 9:00 bis 20:00 offen", "Von 8:00 bis 8:00", "13 Uhr 14 Uhr Wien Tokio", "5 plus 3 Stunden", "Wie weit ist Wien von Tokio",
])
def test_keine_zeitaufgabe(text):
    r = rechnen.loesen(text)
    assert r is None or "Uhr" not in r.de, (text, r and r.de)
