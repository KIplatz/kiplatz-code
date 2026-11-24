# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quellen_stand


def _wiki(teil: str, zahl: int = 0) -> dict:
    return {"wikipedia": {"ok": False, "gilt": True, "laedt": True, "zahl": zahl, "stand": "", "text": f"Wikipedia: noch keine fertige Kopie (liest {teil})."}}


def _befund(s, t):
    return quellen_stand.still(s._geraete, t)


def test_fortschritt_haelt_die_wache_ruhig_und_nicht_ok_seit_bleibt(tmp_path):
    t = [1_000_000.0]
    s = quellen_stand.Sammlung(tmp_path / "q.json", jetzt=lambda: t[0])
    erst = s.melden("g1", "PC - Mitglied", admin=True, quellen=_wiki("1/40"))["nicht_ok_seit"]["wikipedia"]
    for teil in range(2, 9):
        t[0] += 3600
        e = s.melden("g1", "PC - Mitglied", admin=True, quellen=_wiki(f"{teil}/40"))
    assert e["nicht_ok_seit"]["wikipedia"] == erst and not _befund(s, t[0])
    t[0] += 7 * 3600
    s.melden("g1", "PC - Mitglied", admin=True, quellen=_wiki("8/40"))
    assert _befund(s, t[0])


def test_rueckschritt_ist_kein_fortschritt(tmp_path):
    t = [1_000_000.0]
    s = quellen_stand.Sammlung(tmp_path / "q.json", jetzt=lambda: t[0])
    s.melden("g1", "PC", admin=True, quellen=_wiki("7/40", 1000))
    t[0] += 7 * 3600
    s.melden("g1", "PC", admin=True, quellen=_wiki("1/40", 10))
    assert _befund(s, t[0])


def test_neue_phase_ist_fortschritt(tmp_path):
    t = [1_000_000.0]
    s = quellen_stand.Sammlung(tmp_path / "q.json", jetzt=lambda: t[0])
    s.melden("g1", "PC", admin=True, quellen=_wiki("40/40", 1000))
    t[0] += 5 * 3600
    s.melden("g1", "PC", admin=True, quellen={"wikipedia": {**_wiki("1/12", 1000)["wikipedia"], "text": "Wikipedia: noch keine fertige Kopie (baut 1/12)."}})
    t[0] += 3 * 3600
    s.melden("g1", "PC", admin=True, quellen={"wikipedia": {**_wiki("1/12", 1000)["wikipedia"], "text": "Wikipedia: noch keine fertige Kopie (baut 1/12)."}})
    assert not _befund(s, t[0])


def test_nach_48_stunden_trotzdem_befund(tmp_path):
    t = [1_000_000.0]
    s = quellen_stand.Sammlung(tmp_path / "q.json", jetzt=lambda: t[0])
    for i in range(50):
        t[0] += 3600
        s.melden("g1", "PC", admin=True, quellen=_wiki(f"{i + 1}/400", i * 1000))
    assert _befund(s, t[0])
