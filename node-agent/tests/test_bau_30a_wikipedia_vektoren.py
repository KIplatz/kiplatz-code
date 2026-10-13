# SPDX-License-Identifier: AGPL-3.0-or-later
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wikipedia

ART = [
    {"id": 1, "titel": "Allalinhorn", "beliebt": 0.001, "geaendert": "", "umleitungen": [],
     "teile": ["Das Allalinhorn ist ein 4027 Meter hoher Berg in den Walliser Alpen."]},
    {"id": 2, "titel": "Minecraft", "beliebt": 0.002, "geaendert": "", "umleitungen": [],
     "teile": ["Minecraft ist ein Spiel, das 2011 erschienen und sehr berühmt geworden ist.", "Es gibt einen Kreativmodus."]},
]


def _db(pfad, artikel=ART):
    db = wikipedia.Datenbank(pfad, schreiben=True)
    db.teil_aufnehmen(1, artikel)
    db.teil_abschliessen(1)
    db.vorrat_anlegen()
    return db


def _vek(seed: int, n: int = 64) -> list[float]:
    return [math.sin(seed * 0.37 + i * 0.11) for i in range(n)]


def _kos(a, b):
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def test_int8_packt_halb_so_gross_und_liest_alte_float16_weiter():
    v = _vek(3, 1024)
    b = wikipedia._v_packen(v)
    assert len(b) == 8 + 1024 and b[:4] == b"KIq8"
    assert _kos(v, wikipedia._v_lesen(b)) > 0.9995
    alt = struct.pack("<1024e", *v)
    assert len(alt) == 2048 and _kos(v, wikipedia._v_lesen(alt)) > 0.9999
    assert wikipedia._v_lesen(wikipedia._v_packen([0.0] * 8)) == [0.0] * 8


def test_die_neue_ausgabe_uebernimmt_die_vektoren_unveraenderter_abschnitte(tmp_path):
    alt = _db(tmp_path / "alt.sqlite")
    assert alt.hashes_vollstaendig()
    offen = alt.vektor_offen(0, 10)
    assert sorted(sid for _, sid, _, _ in offen) == [1, 2, 3]
    alt.vektoren_schreiben([(sid, _vek(sid)) for _, sid, _, _ in offen])
    assert alt.vektor_offen(0, 10) == []
    alt.hashes_sicherstellen()
    alt.schliessen()
    neu_art = [
        dict(ART[0]),
        {**ART[1], "teile": ["Minecraft ist ein Spiel, das 2011 erschienen ist und 2026 noch gespielt wird.", "Es gibt einen Kreativmodus."]},
        {"id": 3, "titel": "Bremen", "beliebt": 0.003, "geaendert": "", "umleitungen": [], "teile": ["Bremen liegt an der Weser."]},
    ]
    neu = _db(tmp_path / "neu.sqlite", neu_art)
    assert neu.vektoren_uebernehmen(tmp_path / "alt.sqlite") == 2
    rest = neu.vektor_offen(0, 10)
    assert sorted((t, x[:12]) for _, _, t, x in rest) == [("Bremen", "Bremen liegt"), ("Minecraft", "Minecraft is")]
    ids = {t: sid for _, sid, t, _ in neu.vektor_offen(0, 10)}
    row = neu._c.execute("SELECT v FROM vektor WHERE id = (SELECT id FROM abschnitt WHERE artikel = 1)").fetchone()
    assert row and _kos(wikipedia._v_lesen(row[0]), _vek(1)) > 0.999
    assert ids["Bremen"] != ids["Minecraft"]
    neu.schliessen()


def test_eine_alte_datei_ohne_hash_tabelle_bekommt_ihre_hashes_in_stapeln(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    db._c.execute("DROP TABLE abschnitt_hash")
    assert not db.hashes_vollstaendig()
    assert db.hashes_sicherstellen(hoechstens=2) == 2 and not db.hashes_vollstaendig()
    assert db.hashes_sicherstellen(hoechstens=2) == 1 and db.hashes_vollstaendig()
    assert db.hashes_sicherstellen() == 0
    assert db._c.execute("SELECT count(*) FROM sqlite_master WHERE type = 'index' AND name = 'abschnitt_hash_h'").fetchone()[0] == 1
    db.schliessen()


def test_das_fenster_ueberspringt_uebernommene_vektoren_ohne_lange_zu_suchen(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    offen = db.vektor_offen(0, 10)
    db.vektoren_schreiben([(offen[0][1], _vek(1)), (offen[1][1], _vek(2))])
    assert db.vektor_offen(0, 10, fenster=2) == []
    assert [p for p, *_ in db.vektor_offen(2, 10, fenster=2)] == [3]
    db.schliessen()


def test_die_kopie_uebernimmt_vor_dem_tausch_und_faellt_bei_einem_fehler_auf_neu_rechnen_zurueck(tmp_path):
    alt = _db(tmp_path / "wikipedia.sqlite")
    alt.vektoren_schreiben([(sid, _vek(sid)) for _, sid, _, _ in alt.vektor_offen(0, 10)])
    alt.schliessen()
    neu = _db(tmp_path / "neu.sqlite")
    k = object.__new__(wikipedia.WikiKopie)
    zeilen, stand = [], {}
    k._log = zeilen.append
    k._stand_setzen = lambda **w: stand.update(w) or stand
    assert k._vektoren_uebernehmen(neu, tmp_path / "wikipedia.sqlite") == 3
    assert stand == {"vektoren_uebernommen": 3} and zeilen and zeilen[0].startswith("OK wikipedia: 3 Vektoren aus der vorigen Ausgabe übernommen")
    assert neu.vektor_offen(0, 10) == []
    (tmp_path / "kaputt.sqlite").write_bytes(b"kein sqlite")
    neu2 = _db(tmp_path / "neu2.sqlite")
    assert k._vektoren_uebernehmen(neu2, tmp_path / "kaputt.sqlite") == 0
    assert zeilen[-1].startswith("FEHLER wikipedia: Übernahme") and len(neu2.vektor_offen(0, 10)) == 3
    neu.schliessen()
    neu2.schliessen()


def test_neuerungen_fuer_den_bau_stehen():
    import neuerungen
    assert any("nur noch die Abschnitte neu" in s for s in neuerungen.NEUERUNGEN["2026-09-29g"])
