# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import io
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import osm_orte as o

from test_osm_orte import KNOTEN, WEGE, _Antwort, _pbf

JETZT = datetime(2026, 10, 17, 20, 0, tzinfo=timezone.utc).timestamp()


def _fehlt(adresse: str):
    return urllib.error.HTTPError(adresse, 404, "Not Found", {}, io.BytesIO(b""))


def _geofabrik(tmp_path, *, dateien: dict[str, bytes]):
    geholt: list[str] = []

    def oeffner(req, timeout=None):
        geholt.append(req.full_url)
        assert req.full_url.startswith(o.QUELLE)
        name = req.full_url[len(o.QUELLE):]
        if name not in dateien:
            raise _fehlt(req.full_url)
        return _Antwort(dateien[name])
    return oeffner, geholt


def _kopie(tmp_path, oeffner, laender, uhr):
    return o.OrteKopie(lambda: tmp_path / "osm", freigabe_mb=lambda: 500_000, darf=lambda: True, vorgesehen=lambda: True, oeffner=oeffner,
                       platte_frei_mb=lambda p: 900_000, laender=laender, jetzt=lambda: uhr["t"])


def test_deutschland_kommt_ueber_die_ausgabe_mit_datum(tmp_path):
    quelle = tmp_path / "quelle.pbf"
    _pbf(quelle, KNOTEN, WEGE)
    roh = quelle.read_bytes()
    md5 = hashlib.md5(roh).hexdigest()
    oeffner, geholt = _geofabrik(tmp_path, dateien={"germany-261016.osm.pbf.md5": f"{md5}  germany-261016.osm.pbf\n".encode(),
                                                     "germany-261016.osm.pbf": roh})
    k = _kopie(tmp_path, oeffner, (("de", "germany", "Deutschland"),), {"t": JETZT})
    assert k.schritt() == 0
    assert k.laender_fertig() == ["Deutschland"] and "See-Apotheke" in k.suchen("Apotheke in Gmunden")[0].text
    assert geholt == [o.QUELLE + "germany-latest.osm.pbf.md5", o.QUELLE + "germany-261017.osm.pbf.md5",
                      o.QUELLE + "germany-261016.osm.pbf.md5", o.QUELLE + "germany-261016.osm.pbf"]
    assert not k._stand().get("datei_de") and not k._stand().get("md5_de")


def test_ein_land_mit_latest_bleibt_beim_alten_weg(tmp_path):
    quelle = tmp_path / "quelle.pbf"
    _pbf(quelle, KNOTEN, WEGE)
    roh = quelle.read_bytes()
    oeffner, geholt = _geofabrik(tmp_path, dateien={"austria-latest.osm.pbf.md5": f"{hashlib.md5(roh).hexdigest()}  austria-latest.osm.pbf\n".encode(),
                                                     "austria-latest.osm.pbf": roh})
    k = _kopie(tmp_path, oeffner, (("at", "austria", "Österreich"),), {"t": JETZT})
    assert k.schritt() == 0 and k.laender_fertig() == ["Österreich"]
    assert geholt == [o.QUELLE + "austria-latest.osm.pbf.md5", o.QUELLE + "austria-latest.osm.pbf"]


def test_ein_land_das_nicht_kommt_wartet_eine_stunde_und_haelt_die_anderen_nicht_auf(tmp_path):
    quelle = tmp_path / "quelle.pbf"
    _pbf(quelle, KNOTEN, WEGE)
    roh = quelle.read_bytes()
    md5 = hashlib.md5(roh).hexdigest()
    oeffner, geholt = _geofabrik(tmp_path, dateien={"austria-latest.osm.pbf.md5": f"{md5}  austria-latest.osm.pbf\n".encode(), "austria-latest.osm.pbf": roh})
    uhr = {"t": JETZT}
    k = _kopie(tmp_path, oeffner, (("de", "germany", "Deutschland"), ("at", "austria", "Österreich")), uhr)
    with pytest.raises(o.OrteError) as e:
        k.schritt()
    assert e.value.code == "OSM_AUSGABE" and "germany" in e.value.detail
    n = len(geholt)
    assert k.schritt() == 0 and k.laender_fertig() == ["Österreich"]
    assert not any("germany" in u for u in geholt[n:])
    assert k.schritt() == 600 and not any("germany" in u for u in geholt[n:])
    uhr["t"] += o.FEHLER_PAUSE_S
    with pytest.raises(o.OrteError):
        k.schritt()
    assert any("germany" in u for u in geholt[n:])


def test_der_http_code_steht_in_der_meldung(tmp_path):
    def oeffner(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b""))
    k = _kopie(tmp_path, oeffner, (("de", "germany", "Deutschland"),), {"t": JETZT})
    with pytest.raises(o.OrteError) as e:
        k.schritt()
    assert "HTTP 503" in e.value.detail and "germany-latest.osm.pbf.md5" in e.value.detail
