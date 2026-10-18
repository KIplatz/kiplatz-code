# SPDX-License-Identifier: AGPL-3.0-or-later
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import osm_orte as o


def _datei(pfad: Path, orte: list[tuple], eintraege: list[tuple]) -> o.Laenderdatei:
    db = sqlite3.connect(pfad)
    db.executescript("""
        CREATE TABLE eintrag(id INTEGER PRIMARY KEY, osm TEXT, art TEXT, name TEXT, lat REAL, lon REAL, gemeinde TEXT, text TEXT, adresse INTEGER);
        CREATE TABLE ort(name TEXT, norm TEXT, typ TEXT, rang INTEGER, lat REAL, lon REAL, einwohner INTEGER);
        CREATE TABLE info(k TEXT PRIMARY KEY, v TEXT);
        CREATE VIRTUAL TABLE eintrag_name USING fts5(name, content='eintrag', content_rowid='id');
    """)
    db.executemany("INSERT INTO ort VALUES (?,?,?,?,?,?,?)", orte)
    db.executemany("INSERT INTO eintrag(osm, art, name, lat, lon, text, adresse) VALUES (?,?,?,?,?,?,0)", eintraege)
    db.commit()
    db.close()
    return o.Laenderdatei(pfad)


def _dateien(tmp_path):
    at = _datei(tmp_path / "orte-at.sqlite", [("Passau", "passau", "hamlet", 0, 46.68, 12.95, 0), ("Linz", "linz", "city", 4, 48.30, 14.29, 210000)],
                [("node/1", "Apotheke", "Stadt-Apotheke Lienz", 46.83, 12.77, "Apotheke: Stadt-Apotheke Lienz")])
    de = _datei(tmp_path / "orte-de.sqlite", [("Passau", "passau", "town", 3, 48.575, 13.461, 52000)],
                [("node/2", "Apotheke", "Dom-Apotheke", 48.574, 13.464, "Apotheke: Dom-Apotheke Passau")])
    return [at, de]


def test_die_stadt_gewinnt_vor_dem_gleichnamigen_weiler_im_anderen_land(tmp_path):
    t = o.suchen_in(_dateien(tmp_path), "Welche Apotheken gibt es in Passau?")
    assert t and "Dom-Apotheke Passau" in t[0].text and "Lienz" not in t[0].text


def test_ein_genanntes_land_geht_vor(tmp_path):
    at = _datei(tmp_path / "orte-at.sqlite", [("Lindenau", "lindenau", "village", 2, 47.5, 14.0, 900)], [])
    de = _datei(tmp_path / "orte-de.sqlite", [("Lindenau", "lindenau", "hamlet", 0, 50.0, 11.0, 0)], [])
    assert o.bester_ort([at, de], ["Lindenau"], "Apotheken in Lindenau")[1] == 47.5
    assert o.bester_ort([at, de], ["Lindenau"], "Apotheken in Lindenau in Bayern")[1] == 50.0
    (tmp_path / "x").mkdir()
    assert o.bester_ort(_dateien(tmp_path / "x"), ["Linz"], "Apotheken in Linz")[0] == "Linz"
