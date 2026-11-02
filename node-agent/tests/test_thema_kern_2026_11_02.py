# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen
import wissen

FRAGE = "Enshrouded wie kann ich mehrere lager bauen und auf alle kisten zugreifen"
SPIEL = [{"adresse": f"https://seite{i}.example/enshrouded-guide-{i}", "titel": f"Enshrouded Guide {i}: Truhen", "text": "Kisten im Spiel"}
         for i in range(5)]
FREMD = {"adresse": "https://www.appvizer.de/logistik/lagerverwaltung", "titel": "Die 16 Besten Lagerverwaltung Software im Jahr 2026",
         "text": "Control WMS für Unternehmen mit mehreren Lagern"}


def test_der_gegenstand_ist_was_die_meisten_treffer_tragen():
    kern = nachschauen.kernwoerter(FRAGE, SPIEL + [FREMD])
    assert "enshrouded" in kern and "lager" not in kern and "mehr" not in kern


def test_eine_seite_ohne_den_gegenstand_wird_nicht_gelesen():
    kern = nachschauen.kernwoerter(FRAGE, SPIEL + [FREMD])
    reihe = nachschauen.treffer_reihen([FREMD] + SPIEL, FRAGE, heute=date(2026, 11, 1), kern=kern)
    assert FREMD["adresse"] not in [t["adresse"] for t in reihe] and len(reihe) == len(SPIEL)


def test_wenige_treffer_sagen_nichts_dann_bleibt_es_wie_bisher():
    assert nachschauen.kernwoerter(FRAGE, SPIEL[:2] + [FREMD]) == frozenset()
    reihe = nachschauen.treffer_reihen([FREMD] + SPIEL[:2], FRAGE, heute=date(2026, 11, 1))
    assert FREMD["adresse"] in [t["adresse"] for t in reihe]


def test_zahlen_und_kurze_woerter_sind_nie_gegenstand():
    treffer = [{"adresse": f"https://s{i}.example/a", "titel": "Steuer 2026 in AT", "text": ""} for i in range(5)]
    assert nachschauen.kernwoerter("Steuer 2026 in AT", treffer) == frozenset(wissen.woerter("Steuer"))


def test_die_spaetere_runde_sucht_mit_dem_gegenstand_wie_in_der_frage_geschrieben():
    kern = frozenset({"enshrouded"})
    assert nachschauen.mit_kern("mehrere Lager verwalten Kisten", FRAGE, kern) == "mehrere Lager verwalten Kisten Enshrouded"
    assert nachschauen.mit_kern("Enshrouded Truhen", FRAGE, kern) == "Enshrouded Truhen"


def test_englisch_genauso():
    frage = "how do I share storage chests between bases in Valheim"
    treffer = [{"adresse": f"https://g{i}.example/valheim-storage", "titel": "Valheim storage tips", "text": "chests"} for i in range(4)]
    fremd = {"adresse": "https://shop.example/storage-chests", "titel": "Storage chests for your home", "text": "bases and chests"}
    kern = nachschauen.kernwoerter(frage, treffer + [fremd])
    assert "valheim" in kern
    reihe = nachschauen.treffer_reihen([fremd] + treffer, frage, heute=date(2026, 11, 1), kern=kern)
    assert reihe[-1]["adresse"] == fremd["adresse"]


def test_nur_treue_anfragen_bestimmen_den_gegenstand():
    regel = nachschauen.suchbegriffe_regel(FRAGE)
    lagersoftware = [{"adresse": f"https://wms{i}.example/lager", "titel": "Lagerverwaltung mehrere Lager", "text": "Kisten zugreifen"} for i in range(6)]
    auftraege = [(regel, ""), ("mehrere Lager verwalten Kisten", "")]
    kern = nachschauen.kernwoerter_runde(FRAGE, auftraege, [(SPIEL, "x"), (lagersoftware, "x")])
    assert "enshrouded" in kern
    assert nachschauen.kernwoerter_runde(FRAGE, auftraege[1:], [(lagersoftware, "x")]) == frozenset()


def test_eine_aufgeteilte_frage_bekommt_keinen_gegenstand():
    frage = "Wie viele Einwohner haben Klagenfurt und München?"
    kla = [{"adresse": f"https://k{i}.example/klagenfurt", "titel": "Klagenfurt Einwohner", "text": ""} for i in range(5)]
    mue = [{"adresse": f"https://m{i}.example/muenchen", "titel": "München Einwohner", "text": ""} for i in range(4)]
    auftraege = [(q, "") for q in nachschauen.anfragen_aufteilen([nachschauen.suchbegriffe_regel(frage)], frage)]
    assert len(auftraege) >= 2
    assert nachschauen.kernwoerter_runde(frage, auftraege, [(kla, "x"), (mue, "x"), (kla + mue, "x")][:len(auftraege)]) == frozenset()


def test_wer_nur_einen_teil_traegt_rueckt_nach_hinten_und_faellt_nicht():
    frage = "Seit wann gibt es den Europark in Salzburg"
    kern = frozenset(wissen.woerter("Europark Salzburg"))
    wiki = {"adresse": "https://de.wikipedia.org/wiki/Europark", "titel": "Europark – Wikipedia", "text": "Einkaufszentrum"}
    beide = {"adresse": "https://shop.example/europark-salzburg", "titel": "Europark Salzburg Shops", "text": ""}
    reihe = nachschauen.treffer_reihen([wiki, beide], frage, heute=date(2026, 11, 1), kern=kern)
    assert [t["adresse"] for t in reihe] == [beide["adresse"], wiki["adresse"]]
