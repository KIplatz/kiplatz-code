# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wikipedia

TEXT = ("47°20′N 13°20′E﻿ / ﻿47.333°N 13.333°E﻿ / 47.333; 13.333 Austria (/ˈɒstriə/ (listen), /ˈɔːs-/; German: Österreich "
        "[ˈøːstɐraɪç] (listen)), officially the Republic of Austria, is a country in Central Europe. The capital of Austria is Vienna. "
        "Austria is more than 1000 years old. Its history can be followed to the 9th century. "
        + " ".join(f"Austria has many mountains and lakes, and people come to ski there in winter number {i}." for i in range(30))
        + " \"Die verschiedenen Amtssprachen in Österreich\". DemokratieWEBstatt.at. Archived from the original on 24 May 2018. "
          "Retrieved 23 May 2018. \"Regional Languages of Austria\". Rechtsinformationssystem des Bundes. 2013. Archived from the original "
          "on 18 October 2013. Retrieved 27 July 2013. Roach, Peter (2011), Cambridge English Pronouncing Dictionary (18th ed.), Cambridge: "
          "Cambridge University Press, ISBN 978-0-521-15253-2. \"Archived copy\" (PDF). Archived from the original (PDF) on 6 December 2021. "
          "Retrieved 13 February 2023.{{cite web}}: CS1 maint: archived copy as title (link) Media related to Austria at Wikimedia Commons")
DOK = {"namespace": 0, "page_type": "primary", "title": "Austria", "text": TEXT, "page_id": 1, "template": ["Template:Infobox country"],
       "category": ["Countries in Europe"], "auxiliary_text": ["Population 9,200,000 (2025) Area 83,879 km2 Capital Vienna Elevation 3,798 m "
                                                               "Coordinates 47.3 13.3 Currency Euro 1999 2002 Members 1995"]}


def test_ein_englischer_artikel_ohne_koordinaten_lautschrift_und_anhang():
    a = wikipedia.dokument_lesen(DOK, wikipedia.SIMPLE)
    assert a is not None
    alles = " ".join(a["teile"])
    assert a["teile"][0].startswith("Austria (German: Österreich), officially the Republic of Austria, is a country in Central Europe.")
    assert "°" not in alles and "(listen)" not in alles and "ˈ" not in alles
    assert "Retrieved" not in alles and "Archived" not in alles and "ISBN" not in alles and "Wikimedia Commons" not in alles
    assert "DemokratieWEBstatt" not in alles
    assert a["teile"][1].startswith("Key facts: Population 9,200,000")


def test_eine_begriffsklaerung_und_deutsch_unveraendert():
    bk = {**DOK, "template": ["Template:Disambiguation"]}
    assert wikipedia.dokument_lesen(bk, wikipedia.SIMPLE) is None
    bk2 = {**DOK, "category": ["Disambiguation pages"]}
    assert wikipedia.dokument_lesen(bk2, wikipedia.SIMPLE) is None
    a = wikipedia.dokument_lesen(DOK)
    assert a is not None and any(t.startswith("Kurzdaten: ") for t in a["teile"])
    assert wikipedia.dokument_lesen(DOK) == wikipedia.dokument_lesen(DOK, wikipedia.DE)


def test_englische_woerter_fuer_index_und_suche():
    assert wikipedia.woerter_en("World War II: the cities and countries, rivers, churches; Zürich; the river's length") == \
        ["world", "war", "city", "country", "river", "church", "zurich", "river", "length"]


def test_die_kopie_haelt_ihre_sprache(tmp_path):
    k = wikipedia.WikiKopie(lambda: tmp_path / "wikipedia-simple", freigabe_mb=lambda: 6_000, darf=lambda: False, sprache=wikipedia.SIMPLE)
    assert k.sprache is wikipedia.SIMPLE and k.darf_halten() and k._quelle_kennung(7) == "wikipedia-simple-7"
    d = wikipedia.WikiKopie(lambda: tmp_path / "wikipedia", freigabe_mb=lambda: 6_000, darf=lambda: False)
    assert d.sprache is wikipedia.DE and not d.darf_halten() and d._quelle_kennung(7) == "wikipedia-7"
    db = wikipedia.Datenbank(tmp_path / "s.sqlite", schreiben=True, sprache=wikipedia.SIMPLE)
    db.teil_aufnehmen(0, [wikipedia.dokument_lesen(DOK, wikipedia.SIMPLE)])
    db.teil_abschliessen(0)
    assert db.titel_artikel("What is the capital of Austria?") or db.suchen("capital of Austria", n=1)
    db.schliessen()


def test_fable_die_kopien_kommen_sich_nicht_in_die_quere(tmp_path):
    zeilen = []
    k = wikipedia.WikiKopie(lambda: tmp_path / "wikipedia-simple", freigabe_mb=lambda: 6_000, darf=lambda: False, sprache=wikipedia.SIMPLE,
                            gemeinschaft=lambda: object(), ablage=lambda: tmp_path, log=zeilen.append)
    assert k._gemeinschaft is None and k._ablage is None
    k._log("OK wikipedia: Ausgabe gefunden")
    assert zeilen == ["OK wikipedia-simple: Ausgabe gefunden"] and k._name == "wikipedia-simple"
    assert wikipedia.DE.einlese_stand == wikipedia.EINLESE_STAND and wikipedia.SIMPLE.einlese_stand == 1
    import app_web
    assert {"laedt", "liest", "vektoren"} <= app_web.WIKI_ARBEITET
    code = (Path(__file__).resolve().parents[1] / "app_web.py").read_text(encoding="utf-8")
    assert "darf=lambda: self._wiki_darf() and self._wiki.phase not in WIKI_ARBEITET" in code


def test_eine_navigationsleiste_ist_kein_key_fact():
    aux = ["v t e Albert Einstein Physics 1905 1915 1921 1933 1955 1879 Nobel Prize Relativity Photoelectric effect Brownian motion more",
           "Born 14 March 1879 Ulm Died 18 April 1955 Princeton Nobel Prize in Physics 1921 Known for General relativity Spouse 1903 1919"]
    k = wikipedia.kurzdaten(aux, sprache=wikipedia.SIMPLE)
    assert k and not any("v t e" in x for x in k) and k[0].startswith("Key facts: Born 14 March 1879")
