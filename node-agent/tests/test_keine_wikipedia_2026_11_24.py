# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quellen_stand


def test_keine_kopie_vorgesehen_und_die_wache_zaehlt_sie_nicht():
    quelle = (Path(__file__).resolve().parents[1] / "app_web.py").read_text(encoding="utf-8")
    assert quelle.count("wikipedia.WikiKopie(") == 2 and quelle.count("vorgesehen=lambda: False") == 2

    class _Wiki:
        def darf_halten(self):
            return False
    e = quellen_stand._wikipedia(_Wiki())
    assert e["gilt"] is False and e["ok"] is False
