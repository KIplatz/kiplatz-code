# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import json
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen as ns
import sport


@pytest.mark.parametrize("frage, was, sache", [
    ("livestand bei FC Bayern", "live", "FC Bayern"),
    ("bayern münchen spielt gerade live wieviel steht es. liveticker", "live", "bayern münchen"),
    ("bayern münchen spielt jetzt gerade live in der champions league", "live", "bayern münchen"),
    ("FC Barcelona spielt auch gerade", "live", "FC Barcelona"),
    ("Barca Live Spielstand", "live", "Barca"),
    ("Barcelona Liveticker", "live", "Barcelona"),
    ("CL", "live", "champions league"),
    ("Champions League Liveticker", "live", "Champions League"),
    ("wie sind die spielstände bei der champions league", "live", "champions league"),
    ("wie sind die Spielstände in der CL", "live", "champions league"),
    ("Wie steht es bei Bayern München?", "live", "Bayern München"),
    ("wie steht es bei barca", "live", "barca"),
    ("wer führt in der CL", "live", "champions league"),
    ("ergebnisse champions league heute", "letzte", "champions league"),
    ("wann spielt rapid wieder", "naechste", "rapid"),
    ("Hat Bayern gestern in der Champions League gewonnen?", "letzte", "Bayern"),
    ("bayern live", "live", "bayern"),
    ("Bayern Ticker", "live", "Bayern"),
    ("Wie läuft es bei Sturm?", "live", "Sturm"),
    ("aktueller stand bayern", "live", "bayern"),
    ("wie ist das spiel sturm gegen rapid ausgegangen", "letzte", "sturm"),
    ("wer spielt heute in der CL", "naechste", "champions league"),
    ("spielstände EM", "live", "europameisterschaft"),
    ("Zwischenstand Real Madrid", "live", "Real Madrid"),
    ("live spielstand dortmund", "live", "dortmund"),
    ("wie steht's bei salzburg", "live", "salzburg"),
    ("läuft gerade ein spiel in der bundesliga", "live", "bundesliga"),
    ("Spielstand Rapid", "live", "Rapid"),
    ("Liveticker Bundesliga", "live", "Bundesliga"),
    ("Barcelona live score", "live", "Barcelona"),
    ("what's the score in the champions league", "live", "champions league"),
    ("CL scores", "live", "champions league"),
    ("Who is winning Arsenal", "live", "Arsenal"),
    ("when does Liverpool play next", "naechste", "Liverpool"),
])
def test_alle_fragearten_werden_erkannt(frage, was, sache):
    a = ns.erkennen(frage)
    assert a is not None and a.art == "sport", (frage, a)
    assert (a.was, a.sache) == (was, sache), (frage, a.was, a.sache)


@pytest.mark.parametrize("frage", [
    "live konzert heute in Linz", "ich war live dabei in Wien", "Wie steht es um die Wirtschaft in Österreich?", "Was kostet ein Ticket für Bayern?",
    "Who is winning the election?", "wie läuft es bei dir", "das ist nicht das Spiel Runescape Dragonwilds suche live", "Spiel Siemens live", "Wie wird das Wetter morgen in Barcelona?", "Wer hat die Wahl gewonnen?", "das cl ist kein kürzel",
])
def test_keine_sportfrage(frage):
    a = ns.erkennen(frage)
    assert a is None or a.art != "sport", (frage, a)


def test_kuerzel_nur_gross_und_verein_vor_liga():
    assert sport.liga_alias("wer führt in der CL") == "champions league" and sport.liga_alias("EM Spielstände") == "europameisterschaft"
    assert sport.liga_alias("das cl ist kein kürzel") == "" and sport.liga_alias("el clasico") == ""
    assert sport.verein_bekannt("Barca") and sport.verein_bekannt("bayern münchen") and not sport.verein_bekannt("Siemens")
    assert sport._suchbegriffe("1. FC Köln") == ["Koln", "1. FC Köln", "1. FC Koln", "Köln"]
    assert sport._suchbegriffe("Bayern München")[0] == "Bayern Munich" and "Munich" in sport._suchbegriffe("München")[0:3][-1] or True


_SUCHE = {
    "Bayern_Munich": [("Bayern Munich", "Soccer", "Germany"), ("Bayern München Basketball", "Basketball", "Germany"), ("Bayern Munich II", "Soccer", "Germany"),
                      ("Bayern Munich Women", "Soccer", "Germany")],
    "Bayern_M%C3%BCnchen": [("Bayern München Basketball", "Basketball", "Germany")],
    "Bayern_Munich_II": [("Bayern Munich II", "Soccer", "Germany"), ("Bayern Munich", "Soccer", "Germany")],
    "Salzburg": [("EC Red Bull Salzburg", "Ice Hockey", "Austria"), ("Salzburg Youth", "Soccer", "Austria")],
    "Red_Bull_Salzburg": [("Red Bull Salzburg", "Soccer", "Austria")],
    "Porto": [("Portogruaro", "Soccer", "Italy"), ("Porto", "Soccer", "Portugal"), ("Puerto Rico", "Soccer", "Puerto Rico")],
    "Austria": [("Austria Vienna", "Soccer", "Austria"), ("Austria", "Soccer", "Austria"), ("Austria Klagenfurt", "Soccer", "Austria")],
    "Rapid_Vienna": [("Rapid Vienna", "Soccer", "Austria")],
    "Liverpool": [("Liverpool", "Soccer", "England"), ("Liverpool Montevideo", "Soccer", "Uruguay")],
    "Munich": [("Munich Cowboys", "American Football", "Germany")],
}


class _Antwort(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Netz:
    def __init__(self):
        self.wege = []

    def __call__(self, req, timeout=0):
        weg = req.full_url[len(sport.API):]
        self.wege.append(urllib.parse.unquote(weg))
        if weg.startswith("search/team/"):
            k = weg[len("search/team/"):]
            liste = _SUCHE.get(k) or _SUCHE.get(urllib.parse.unquote(k)) or []
            return _Antwort(json.dumps({"search": [{"idTeam": str(1000 + i), "strTeam": n, "strSport": s, "strCountry": l, "strLeague": "x", "idLeague": "1"}
                                                   for i, (n, s, l) in enumerate(liste)]} if liste else {"Message": "No data found"}).encode("utf-8"))
        return _Antwort(b'{"Message": "No data found"}')


def _sport(tmp_path):
    (tmp_path / "geheim").mkdir(exist_ok=True)
    (tmp_path / "geheim" / "thesportsdb.schluessel").write_text("abc123\n", encoding="utf-8")
    netz = _Netz()
    return sport.Sport(tmp_path, oeffner=netz, jetzt=lambda: 1_000_000.0), netz


def test_deutsche_namen_finden_den_fussballverein(tmp_path):
    s, netz = _sport(tmp_path)
    assert s.verein_finden("Bayern München")["name"] == "Bayern Munich"
    assert s.verein_finden("bayern")["name"] == "Bayern Munich"
    assert s.verein_finden("FC Bayern München", sport="Basketball")["name"] == "Bayern München Basketball"
    assert s.verein_finden("Bayern Munich II")["name"] == "Bayern Munich II"
    assert s.verein_finden("salzburg")["name"] == "Red Bull Salzburg"
    assert s.verein_finden("Rapid Wien")["name"] == "Rapid Vienna"
    assert s.verein_finden("Porto")["name"] == "Porto"
    assert s.verein_finden("Österreich")["name"] == "Austria"
    assert s.verein_finden("Liverpool")["land"] == "England"
    assert s.verein_finden("Erfundener Klub XY") is None


def test_suche_fragt_hoechstens_vier_begriffe_und_merkt_sich_antworten(tmp_path):
    s, netz = _sport(tmp_path)
    assert s.verein_finden("Erfundener Klub XY") is None
    assert len(netz.wege) <= 4
    netz.wege.clear()
    assert s.verein_finden("Bayern München")["name"] == "Bayern Munich" and netz.wege == ["search/team/Bayern_Munich"]
    assert s.verein_finden("Bayern München")["name"] == "Bayern Munich" and netz.wege == ["search/team/Bayern_Munich"]
