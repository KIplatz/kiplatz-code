# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import nachschauen

FRAGE = "Wie viele Einwohner haben Klagenfurt und München?"
KLAGENFURT = ("Klagenfurt am Wörthersee ist eine Großstadt im Süden Österreichs sowie die Landeshauptstadt des österreichischen Bundeslandes "
              "Kärnten. Mit 105.734 Einwohnern (Stand: 1. Jänner 2026) ist sie die größte Stadt Kärntens.")
MUENCHEN = "Wie viele Einwohner*innen hat München? Am 31. Dezember 2025 lebten 1.612.429 Menschen mit Hauptwohnsitz in München."


def test_aufzaehlung_und_teilfragen():
    assert nachschauen.aufzaehlung(FRAGE) == ["Klagenfurt", "München"]
    assert nachschauen.teilfragen(FRAGE) == [("Klagenfurt", "Wie viele Einwohner haben Klagenfurt?"), ("München", "Wie viele Einwohner haben München?")]
    assert nachschauen.aufzaehlung("Wie hoch sind Großglockner, Zugspitze und Dachstein?") == ["Großglockner", "Zugspitze", "Dachstein"]
    for ohne in ("Wie groß ist Wien?", "Wann hat die Apotheke in Gmunden offen?", "Wie viel Einwohner hat Wien und wie groß ist es?"):
        assert nachschauen.aufzaehlung(ohne) == [] and nachschauen.teilfragen(ohne) == []


def test_eine_suche_je_stadt():
    assert nachschauen.anfragen_aufteilen(["viele Einwohner Klagenfurt München"], FRAGE) == ["viele Einwohner Klagenfurt", "viele Einwohner München",
                                                                                              "viele Einwohner Klagenfurt München"]
    assert nachschauen.anfragen_aufteilen(["Einwohner Klagenfurt München", "Klagenfurt München Vergleich"], FRAGE)[:3] ==         ["Einwohner Klagenfurt", "Einwohner München", "Einwohner Klagenfurt München"]
    assert nachschauen.anfragen_aufteilen(["Höhe Großglockner Zugspitze Dachstein"], "Wie hoch sind Großglockner, Zugspitze und Dachstein?") ==         ["Höhe Großglockner", "Höhe Zugspitze", "Höhe Dachstein"]
    assert nachschauen.anfragen_aufteilen(["Einwohner Klagenfurt"], FRAGE) == ["Einwohner Klagenfurt", "Einwohner München"]
    assert nachschauen.anfragen_aufteilen(["Wetter Wien"], "Wie wird das Wetter in Wien?") == ["Wetter Wien"]


def test_suche_runde_fragt_je_stadt(monkeypatch):
    gefragt: list[str] = []
    n = nachschauen.Nachschauer(suche_fn=lambda q, **kw: gefragt.append(q) or [])
    try:
        n.suche_runde(["viele Einwohner Klagenfurt München"], FRAGE)
    except Exception:
        pass
    assert sorted(gefragt) == ["viele Einwohner Klagenfurt", "viele Einwohner Klagenfurt München", "viele Einwohner München"]


def _pruefen(text: str, quelltext: str, nochmal=None) -> str:
    quellen = [{"nummer": 1, "text": quelltext, "art": "nachgeschaut"}]
    t, _notizen = app_web.belege_anwenden(text, FRAGE, quelltext, quellen, heute=date(2026, 9, 30), nochmal=nochmal)
    return t


def test_nur_der_unbelegte_teil_faellt():
    t = _pruefen("Klagenfurt hat 105.734 Einwohner und München hat 1,48 Millionen Einwohner.", KLAGENFURT, nochmal=lambda _z: "Das weiß ich noch nicht.")
    assert "105.734" in t and "1,48" not in t


def test_beide_belegt_bleiben_beide():
    t = _pruefen("Klagenfurt hat 105.734 Einwohner und München rund 1,6 Millionen.", KLAGENFURT + "\n\n" + MUENCHEN)
    assert "105.734" in t and "1,6 Millionen" in t


def test_weiss_nicht_loescht_keine_gefundene_zahl():
    ls: dict = {}
    t = app_web._weiss_nicht_anwenden("Klagenfurt hat 105.734 Einwohner. Zu München weiß ich es nicht.", ls, gesucht=True,
                                      vorher="Klagenfurt hat 105.734 Einwohner, München 1,48 Millionen.")
    assert "105.734" in t and t != app_web._GESUCHT_NICHTS_SATZ
    assert app_web._weiss_nicht_anwenden("Das weiß ich noch nicht.", {}, gesucht=True) == app_web._GESUCHT_NICHTS_SATZ


def test_ortsnamen_aus_mehreren_woertern():
    assert nachschauen.aufzaehlung("Wie viele Einwohner haben St. Pölten und St. Georgen?") == ["St. Pölten", "St. Georgen"]
    assert nachschauen.aufzaehlung("Wetter in Bad Ischl oder Sankt Gilgen") == ["Bad Ischl", "Sankt Gilgen"]
    assert nachschauen.aufzaehlung("Einwohner von Klagenfurt am Wörthersee und Bruck an der Mur") == ["Klagenfurt am Wörthersee", "Bruck an der Mur"]
    assert nachschauen.teilfragen("Wie viele Einwohner haben St. Pölten und St. Georgen?")[1] == ("St. Georgen", "Wie viele Einwohner haben St. Georgen?")
    assert nachschauen.anfragen_aufteilen(["Einwohner St. Pölten St. Georgen"], "Wie viele Einwohner haben St. Pölten und St. Georgen?") == \
        ["Einwohner St. Pölten", "Einwohner St. Georgen", "Einwohner St. Pölten St. Georgen"]
    assert nachschauen.aufzaehlung("Wie weit ist es zwischen Bad Ischl und Sankt Gilgen?") == []
    assert nachschauen.aufzaehlung("Einwohner von Linz oder Graz") == ["Linz", "Graz"]


def test_der_entwurf_am_handy_nennt_keine_auszuege():
    gesendet: list[str] = []
    g = app_web._Teilgeber(gesendet.append, abstand_s=3600)
    g.token("Klagenfurt hat 105.734 Einwohner. Die Einwohnerzahl von München steht nicht in den Auszügen.")
    g.schluss()
    assert gesendet and "Auszüg" not in gesendet[-1] and "105.734" in gesendet[-1]
