# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen


def _mit_amt(liste, frage, frueher, heute):
    return app_web.amtssuche_dazu(app_web.suchwoerter_ordnen(liste, frage, frueher, heute), frage, heute)


@pytest.mark.parametrize("frage,domain", [
    ("Wie hoch ist die Mindestpension in Österreich?", "gv.at"),
    ("Wie hoch ist die Familienbeihilfe?", "gv.at"),
    ("Wie hoch ist das Pflegegeld in Österreich?", "gv.at"),
    ("How much is the state pension in the UK?", "gov.uk"),
    ("What is the minimum wage in Canada?", "canada.ca"),
    ("Wie viel Kindergeld bekommt man in Deutschland?", ""),
    ("What is the minimum wage in Ireland?", ""),
    ("Wie hoch ist das Arbeitslosengeld in Österreich?", ""),
    ("Was kostet eine Pension in Tirol?", ""),
    ("Wer bekommt Familienbeihilfe?", ""),
    ("Wie hoch ist die Höhe des Pflegegeldes in Österreich?", "gv.at"),
    ("Wie hoch sind die Mindestpensionen in Österreich?", "gv.at"),
    ("Muss ich Familienbeihilfe zurückzahlen?", ""),
    ("Darf ich in Österreich neben der Alterspension arbeiten?", ""),
])
def test_leistung_auf_amtlicher_domain(frage, domain):
    assert nachschauen.amts_domain(frage) == domain


def test_zweite_suche_mindestpension():
    out = _mit_amt(["Mindestpension Österreich"], "Wie hoch ist die Mindestpension in Österreich?", "", date(2026, 11, 23))
    assert out == ["Mindestpension Österreich", "hoch Mindestpension Österreich site:gv.at"]


def test_amtliche_suche_mit_den_woertern_der_frage():
    modell = "Mindestpensionsbetrag Österreich 2026 offizielle Quelle Bundesministerium für Soziales"
    out = _mit_amt([modell], "Wie hoch ist die Mindestpension in Österreich?", "", date(2026, 11, 23))
    assert out[0].startswith("Mindestpensionsbetrag Österreich")
    assert out[1] == "hoch Mindestpension Österreich site:gv.at"
    out = _mit_amt(["Schengen visa fee 2026 official EU website"], "How much does a Schengen visa cost?", "", date(2026, 11, 23))
    assert out[1] == "Schengen visa cost site:europa.eu"


def test_pva_ist_amtlich():
    assert nachschauen.amtlich("https://www.pv.at/web/pensionen")
