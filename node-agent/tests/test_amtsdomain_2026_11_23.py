# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen

HEUTE = date(2026, 11, 23)


def _mit_amt(liste, frage, frueher, heute):
    return app_web.amtssuche_dazu(app_web.suchwoerter_ordnen(liste, frage, frueher, heute), frage, heute)


@pytest.mark.parametrize("frage,domain", [
    ("How much does a Schengen visa cost?", "europa.eu"),
    ("How much does a passport cost in the UK?", "gov.uk"),
    ("Wie viele Einwohner hat die Schweiz?", "bfs.admin.ch"),
    ("Wie viele Menschen leben in Deutschland?", "destatis.de"),
    ("Wie viel kostet ein Reisepass in Österreich?", "gv.at"),
    ("Was kostet der EU-Führerschein in Österreich?", "gv.at"),
    ("Was kostet ein Reisepass in Großbritannien?", ""),
    ("How many people live in Germany?", ""),
    ("Wie hoch ist das Arbeitslosengeld in Österreich?", ""),
    ("Wann muss ich in Österreich auf Winterreifen wechseln?", ""),
    ("Was kostet ein Big Mac in der Schweiz?", ""),
    ("Wie viel kostet die Vignette in Slowenien?", ""),
    ("How much does a passport cost?", ""),
])
def test_amts_domain(frage, domain):
    assert nachschauen.amts_domain(frage) == domain


def test_zweite_suche_auf_der_domain_erste_bleibt_offen():
    out = _mit_amt(["Schengen visa cost", "Schengen visa fees 2026"], "How much does a Schengen visa cost?", "", HEUTE)
    assert out == ["Schengen visa fees 2026", "Schengen visa cost site:europa.eu"]
    assert _mit_amt(["Winterreifenpflicht Österreich"], "Wann muss ich in Österreich auf Winterreifen wechseln?", "",
                                      HEUTE) == ["Winterreifenpflicht Österreich"]


def test_feiertag_mit_namen():
    assert app_web.FEIERTAG_FOKUS in app_web.frage_fokus("Wann ist der nächste Feiertag in Österreich?")
    assert app_web.FEIERTAG_FOKUS_EN in app_web.frage_fokus("When is the next bank holiday in the UK?")
    assert app_web.FEIERTAG_FOKUS not in app_web.frage_fokus("Wie hoch ist die Pendlerpauschale in Österreich?")


def test_woher_zeigt_site_lesbar():
    satz = app_web.gesucht_satz("x", ["Schengen visa cost", "Schengen visa cost site:europa.eu"])
    assert "(nur auf europa.eu)" in satz and "site:" not in satz


def test_urlaub_ist_kein_feiertag():
    assert app_web.FEIERTAG_FOKUS_EN not in app_web.frage_fokus("Where should I go on holiday in July?")


def test_keine_zweite_site_und_nicht_bei_youtube_am_ende():
    out = _mit_amt(["UK passport cost site:gov.uk"], "How much does a passport cost in the UK?", "", HEUTE)
    assert sum(q.count("site:") for q in out) == 1
