# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import osm_orte as o
from test_osm_orte import KNOTEN, WEGE, _pbf


def test_jemand_am_geraet_pausiert_das_einlesen_statt_es_wegzuwerfen(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "BLOCKS_JE_SCHRITT", 1)
    pbf = tmp_path / "t.osm.pbf"
    _pbf(pbf, KNOTEN, WEGE)
    ganz = o.land_einlesen(pbf, tmp_path / "ganz.sqlite")
    antworten = iter([False, False, True] + [True] * 100)
    gewartet: list[float] = []
    z = o.land_einlesen(pbf, tmp_path / "pause.sqlite", darf=lambda: next(antworten), warten=lambda s: gewartet.append(s) or True)
    assert z == ganz and gewartet == [o.PAUSE_S]


def test_nur_ein_programmende_bricht_ab(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "BLOCKS_JE_SCHRITT", 1)
    pbf = tmp_path / "t.osm.pbf"
    _pbf(pbf, KNOTEN, WEGE)
    with pytest.raises(o.Unterbrochen):
        o.land_einlesen(pbf, tmp_path / "ende.sqlite", darf=lambda: False, warten=lambda s: False)
    assert not (tmp_path / "ende.sqlite").exists()
    with pytest.raises(o.Unterbrochen):
        o.land_einlesen(pbf, tmp_path / "alt.sqlite", darf=lambda: False)
