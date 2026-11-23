# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web

HEUTE = date(2026, 11, 23)


def test_nach_den_zweigen_dazu():
    assert app_web.amtssuche_dazu(["ESTA USA fee", "ESTA USA visa waiver fee official website 2026"], "How much is the ESTA for the USA?",
                                  HEUTE) == ["ESTA USA fee", "ESTA USA site:gov"]
    assert app_web.amtssuche_dazu(["hoch Familienbeihilfe", "Familienbeihilfe Österreich 2026 Beträge"], "Wie hoch ist die Familienbeihilfe?",
                                  HEUTE) == ["Familienbeihilfe Österreich 2026 Beträge", "hoch Familienbeihilfe site:gv.at"]


def test_nicht_doppelt_und_nicht_in_spaeteren_runden():
    assert app_web.amtssuche_dazu(["UK passport cost site:gov.uk"], "How much does a passport cost in the UK?", HEUTE) == ["UK passport cost site:gov.uk"]
    assert app_web.amtssuche_dazu(["ESTA cost latest"], "How much is the ESTA for the USA?", HEUTE,
                                  bisher=["ESTA fee", "ESTA USA site:gov"]) == ["ESTA cost latest"]
    assert app_web.amtssuche_dazu(None, "How much is the ESTA for the USA?", HEUTE) is None
    assert app_web.amtssuche_dazu(["Winterreifenpflicht Österreich"], "Wann muss ich in Österreich auf Winterreifen wechseln?",
                                  HEUTE) == ["Winterreifenpflicht Österreich"]


def test_eine_stelle():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert quelle.count("amtssuche_dazu(self._suchwoerter_alle(") == 1
    assert "mit_amtssuche" not in quelle and quelle.count("nachschauen.amts_domain(frage)") == 1


def test_zwei_dinge_behalten_beide_suchen():
    for frage, liste in [("Wie viele Einwohner haben Klagenfurt und München?", ["Einwohner Klagenfurt", "Einwohner München"]),
                         ("Was kostet ein Reisepass in Österreich und in Deutschland?", ["Reisepass Kosten Österreich", "Reisepass Kosten Deutschland"])]:
        assert app_web.amtssuche_dazu(liste, frage, HEUTE) == liste
