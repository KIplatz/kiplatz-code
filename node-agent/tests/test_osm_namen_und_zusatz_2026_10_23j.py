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
        CREATE VIRTUAL TABLE eintrag_name USING fts5(name, content='eintrag', content_rowid='id', tokenize="unicode61 remove_diacritics 2");
    """)
    db.executemany("INSERT INTO ort VALUES (?,?,?,?,?,?,?)", orte)
    db.executemany("INSERT INTO eintrag(osm, art, name, lat, lon, text, adresse) VALUES (?,?,?,?,?,?,0)", eintraege)
    db.execute("INSERT INTO eintrag_name(eintrag_name) VALUES ('rebuild')")
    db.commit()
    db.close()
    return o.Laenderdatei(pfad)


def _dateien(tmp_path):
    at = _datei(tmp_path / "orte-at.sqlite",
                [("Zell am See", "zell am see", "town", 3, 47.32, 12.80, 10000), ("Vaduz", "vaduz", "town", 3, 47.14, 9.52, 5700)],
                [("node/1", "Berg", "Mount Klotz", 47.0, 13.0, "Berg: Mount Klotz; Höhe 130 m"),
                 ("node/2", "Berg", "Mont Blanc de Cheilon", 46.0, 7.4, "Berg: Mont Blanc de Cheilon; Höhe 3.870 m"),
                 ("node/3", "Berg", "Großer Priel", 47.72, 14.06, "Berg: Großer Priel; Höhe 2.515 m"),
                 ("node/4", "Apotheke", "See-Apotheke", 47.321, 12.797, "Apotheke: See-Apotheke Zell am See"),
                 ("node/5", "Museum", "Landesmuseum Vaduz", 47.140, 9.521, "Museum: Landesmuseum Vaduz"),
                 ("node/6", "Museum", "Postmuseum", 47.141, 9.522, "Museum: Postmuseum"),
                 ("node/7", "Berg", "Zugspitze", 47.42, 10.98, "Berg: Zugspitze; Höhe 2.962 m")])
    ch = _datei(tmp_path / "orte-ch.sqlite", [("Zell", "zell", "village", 2, 47.45, 8.82, 600)],
                [("node/8", "Apotheke", "Post Apotheke", 47.45, 8.82, "Apotheke: Post Apotheke Winterthur")])
    de = _datei(tmp_path / "orte-de.sqlite",
                [("Frankfurt", "frankfurt", "hamlet", 0, 49.68, 10.53, 0), ("Frankfurt am Main", "frankfurt am main", "city", 4, 50.11, 8.68, 760000)],
                [("node/9", "Apotheke", "Dom Römer Apotheke", 50.11, 8.68, "Apotheke: Dom Römer Apotheke Frankfurt am Main"),
                 ("node/10", "Apotheke", "Markt-Apotheke", 49.68, 10.53, "Apotheke: Markt-Apotheke Scheinfeld"),
                 ("node/7", "Berg", "Zugspitze", 47.42, 10.98, "Berg: Zugspitze; Höhe 2.962 m")])
    return [at, ch, de]


def test_ein_berg_ausserhalb_der_laender_bringt_nichts_falsches(tmp_path):
    d = _dateien(tmp_path)
    assert o.suchen_in(d, "Wie hoch ist der Mount Everest?") == []
    assert o.suchen_in(d, "Wie hoch ist der Mont Blanc?") == []
    t = o.suchen_in(d, "Wie hoch ist der Große Priel?")
    assert t and "Großer Priel; Höhe 2.515 m" in t[0].text
    t = o.suchen_in(d, "Wie hoch ist der Große Priel in Österreich?")
    assert t and "Großer Priel; Höhe 2.515 m" in t[0].text
    z = o.suchen_in(d, "Wie hoch ist die Zugspitze?")[0].text
    assert z.count("Zugspitze; Höhe") == 1


def test_orte_mit_zusatz_und_kurze_namen_treffen_die_stadt(tmp_path):
    d = _dateien(tmp_path)
    assert "See-Apotheke Zell am See" in o.suchen_in(d, "Apotheke in Zell am See")[0].text
    assert "Dom Römer Apotheke" in o.suchen_in(d, "Apotheke in Frankfurt am Main")[0].text
    assert "Dom Römer Apotheke" in o.suchen_in(d, "Apotheke in Frankfurt")[0].text
    assert o._ortsworte("Apotheke in Zell am See")[0] == "Zell am See"


def test_ein_museum_im_ort_wird_im_umkreis_gesucht(tmp_path):
    t = o.suchen_in(_dateien(tmp_path), "Museum in Vaduz")[0].text
    assert "Postmuseum" in t and "Landesmuseum Vaduz" in t


def test_was_ein_gipfel_ist_geht_vor_und_wegweiser_sind_keine_tourismusinformation():
    assert o.art_von({"tourism": "viewpoint", "natural": "peak", "name": "Feldberg"}) == "Berg"
    assert o.art_von({"amenity": "restaurant", "tourism": "alpine_hut", "name": "Adamekhütte"}) == "Hütte"
    assert o.art_von({"tourism": "information", "information": "guidepost"}) == ""
    assert o.art_von({"tourism": "information", "information": "office"}) == "Tourismusinformation"
