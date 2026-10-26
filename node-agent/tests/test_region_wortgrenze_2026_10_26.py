# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import region


def test_kein_gebiet_mitten_im_wort():
    for frage in ("Where do I apply for a pension in Austria?", "What is a temperature inversion?", "Was ist eine Inversionswetterlage?",
                  "Beschreibe in höchstens acht Wörtern, was ein Zug ist."):
        r = region.erkennen(frage)
        assert r is None or r.gebiet not in ("VS", "ZG"), frage


def test_gebiete_werden_weiter_erkannt():
    assert region.erkennen("Wie wird das Wetter morgen in Sion?").gebiet == "VS"
    assert region.erkennen("Wann fährt der Zug nach Zermatt?").gebiet == "VS"
    assert region.erkennen("Was kostet ein Hotel im Kanton Zug?").gebiet == "ZG"
