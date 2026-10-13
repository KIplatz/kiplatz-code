# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import umzug
import wikipedia


def _alt(tmp_path: Path) -> Path:
    von = tmp_path / "F" / "KIplatz-Speicher" / "wikipedia"
    (von / "unter").mkdir(parents=True)
    (von / "wikipedia.sqlite").write_bytes(b"x" * 3_000_000)
    (von / "unter" / "teil.bz2").write_bytes(b"y" * 10)
    (von / "stand.json").write_text('{"fertig_ausgabe": "20260927"}', encoding="utf-8")
    return von


def _schritt(nach, zeilen, *, halt=lambda: False, frei=10**9, behalten=True, zu=None):
    return umzug.schritt(nach, behalten=behalten, schliessen=lambda: zu is not None and zu.append("zu"), oeffnen=lambda: None, halt=halt,
                         log=zeilen.append, name="wikipedia", platte_frei_mb=lambda p: frei)


def test_die_kopie_zieht_um_und_die_alte_geht_erst_nach_der_pruefung(tmp_path):
    von = _alt(tmp_path)
    nach = tmp_path / "G" / "KIplatz-Speicher" / "wikipedia"
    assert umzug.vormerken(von, nach)
    zeilen, zu = [], []
    assert _schritt(nach, zeilen, zu=zu) == 0
    assert (nach / "wikipedia.sqlite").read_bytes() == b"x" * 3_000_000 and (nach / "unter" / "teil.bz2").exists()
    assert (nach / "stand.json").exists() and not von.exists() and not (nach / umzug.MARKE).exists() and zu == ["zu"]
    assert any("Umzug fertig" in z for z in zeilen)
    assert _schritt(nach, zeilen) is None


def test_abgebrochen_oder_zu_wenig_platz_die_alte_bleibt(tmp_path):
    von = _alt(tmp_path)
    nach = tmp_path / "G" / "KIplatz-Speicher" / "wikipedia"
    umzug.vormerken(von, nach)
    assert _schritt(nach, [], frei=1) == 3600 and von.exists()
    assert _schritt(nach, [], halt=lambda: True) == 0 and (von / "wikipedia.sqlite").exists() and umzug.offen(nach)
    assert _schritt(nach, []) == 0 and not von.exists()


def test_nur_unser_eigener_ordner_wird_geloescht(tmp_path):
    fremd = tmp_path / "F" / "Fotos"
    fremd.mkdir(parents=True)
    nach = tmp_path / "G" / "KIplatz-Speicher" / "wikipedia"
    assert not umzug.vormerken(fremd, nach)
    nach.mkdir(parents=True)
    (nach / umzug.MARKE).write_text('{"von": "%s", "kopiert": true}' % str(fremd).replace("\\", "\\\\"), encoding="utf-8")
    _schritt(nach, [])
    assert fremd.exists() and not (nach / umzug.MARKE).exists()


def test_der_faden_zieht_um_und_oeffnet_erst_danach(tmp_path):
    von = _alt(tmp_path)
    nach = tmp_path / "G" / "KIplatz-Speicher" / "wikipedia"
    ort = {"p": nach}
    k = wikipedia.WikiKopie(lambda: ort["p"], freigabe_mb=lambda: 200_000, darf=lambda: False, platte_frei_mb=lambda p: 10**9)
    k.umzug_vormerken(von, nach)
    assert k._umzug_unterbricht()
    k._oeffnen()
    assert k._db is None
    k.schritt()
    assert not von.exists() and (nach / "wikipedia.sqlite").exists()
    k.schritt()
    assert not k._umzug_unterbricht()


def test_ein_langer_schritt_der_datenbank_bricht_fuer_den_umzug_ab(tmp_path):
    import sqlite3
    import pytest
    db = wikipedia.Datenbank(tmp_path / "b.sqlite", schreiben=True)
    db._abbrechen = lambda: True
    with pytest.raises(sqlite3.OperationalError, match="interrupt"):
        db._c.execute("WITH RECURSIVE z(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM z WHERE n < 10000000) SELECT count(*) FROM z").fetchone()
    db._abbrechen = None
    db.schliessen()


def test_der_neubau_beginnt_nach_einem_neustart_nicht_wieder_bei_der_reihenfolge(tmp_path, monkeypatch):
    k = wikipedia.WikiKopie(lambda: tmp_path, freigabe_mb=lambda: 200_000, darf=lambda: True, platte_frei_mb=lambda p: 10**9)
    k._stand_setzen(bau_ausgabe="20261001", bau_teile=[[0, "https://dumps.wikimedia.org/x", 1]])
    db = wikipedia.Datenbank(k._bau_pfad("20261001"), schreiben=True)
    db.teil_aufnehmen(0, [{"id": 1, "titel": "Linz", "umleitungen": [], "teile": ["Linz ist eine Stadt an der Donau."], "beliebt": 1.0, "geaendert": "2026-10-01"}])
    db.teil_abschliessen(0)
    db.schliessen()
    gezaehlt = []
    echt = wikipedia.Datenbank.vorrat_anlegen
    monkeypatch.setattr(wikipedia.Datenbank, "vorrat_anlegen", lambda self: gezaehlt.append(1) or echt(self))
    for _ in range(10):
        if k._stand().get("fertig_ausgabe"):
            break
        k._bau_schritt(k._stand())
    assert k._stand().get("fertig_ausgabe") == "20261001" and gezaehlt == [1]


def test_nach_dem_oeffnen_wird_die_wikipedia_einmal_angelesen(tmp_path):
    db = wikipedia.Datenbank(tmp_path / "wikipedia.sqlite", schreiben=True)
    db.teil_aufnehmen(0, [{"id": 1, "titel": "Großglockner", "umleitungen": [], "teile": ["Der Großglockner ist 3798 Meter hoch."], "beliebt": 1.0, "geaendert": "2026-10-01"}])
    db.teil_abschliessen(0)
    db.vorrat_anlegen()
    db.wortzahl_anlegen()
    db.schliessen()
    zeilen: list = []
    k = wikipedia.WikiKopie(lambda: tmp_path, freigabe_mb=lambda: 200_000, darf=lambda: False, platte_frei_mb=lambda p: 10**9, log=zeilen.append)
    k._stand_setzen(fertig_ausgabe="20261001", fertig_um=k._jetzt())
    assert k.schritt() == 0 and any("angelesen" in z for z in zeilen)
    zeilen.clear()
    assert k.schritt() == 30 and not any("angelesen" in z for z in zeilen)
