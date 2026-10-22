# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import osm_orte as o


def _v(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _zz(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _f(nr: int, wert) -> bytes:
    if isinstance(wert, int):
        return _v(nr << 3) + _v(wert)
    return _v((nr << 3) | 2) + _v(len(wert)) + wert


def _packed(zahlen) -> bytes:
    return b"".join(_v(z) for z in zahlen)


def _delta(werte):
    vorher, out = 0, []
    for w in werte:
        out.append(_zz(w - vorher))
        vorher = w
    return out


def _block(art: bytes, inhalt: bytes, *, packen=True) -> bytes:
    blob = _f(2, len(inhalt)) + _f(3, zlib.compress(inhalt)) if packen else _f(1, inhalt)
    kopf = _f(1, art) + _f(3, len(blob))
    return struct.pack(">I", len(kopf)) + kopf + blob


def _pbf(pfad: Path, knoten, wege) -> None:
    strings = [""]

    def s(x: str) -> int:
        if x not in strings:
            strings.append(x)
        return strings.index(x)
    kv = []
    for _, _, _, tags in knoten:
        for k, v in tags.items():
            kv += [s(k), s(v)]
        kv.append(0)
    dense = (_f(1, _packed(_delta([k[0] for k in knoten]))) + _f(8, _packed(_delta([round(k[1] * 1e7) for k in knoten])))
             + _f(9, _packed(_delta([round(k[2] * 1e7) for k in knoten]))) + _f(10, _packed(kv)))
    wege_b = b""
    for wid, refs, tags in wege:
        wege_b += _f(3, _f(1, wid) + _f(2, _packed([s(k) for k in tags])) + _f(3, _packed([s(v) for v in tags.values()])) + _f(8, _packed(_delta(refs))))
    tabelle = _f(1, b"".join(_f(1, x.encode()) for x in strings))
    kopf = _f(4, b"OsmSchema-V0.6") + _f(4, b"DenseNodes")
    with open(pfad, "wb") as f:
        f.write(_block(b"OSMHeader", kopf))
        f.write(_block(b"OSMData", tabelle + _f(2, _f(2, dense))))
        f.write(_block(b"OSMData", tabelle + _f(2, wege_b), packen=False))


KNOTEN = [
    (1, 47.918, 13.799, {"place": "town", "name": "Gmunden", "population": "13000"}),
    (2, 48.509, 15.159, {"place": "village", "name": "Schafberg"}),
    (3, 47.919, 13.800, {"amenity": "pharmacy", "name": "See-Apotheke", "addr:street": "Theatergasse", "addr:housenumber": "3",
                         "addr:postcode": "4810", "addr:city": "Gmunden", "opening_hours": "Mo-Fr 08:00-18:00; Sa 08:00-12:00"}),
    (4, 47.930, 13.810, {"amenity": "pharmacy", "name": "Traunstein-Apotheke"}),
    (5, 47.866, 13.838, {"natural": "peak", "name": "Traunstein", "ele": "1691"}),
    (6, 47.776, 13.433, {"natural": "peak", "name": "Schafberg", "ele": "1783"}),
    (7, 47.780, 13.440, {"tourism": "alpine_hut", "name": "Himmelspforthütte", "ele": "1720"}),
    (8, 47.918, 13.798, {"amenity": "atm"}),
    (9, 47.918, 13.797, {"amenity": "information"}),
    (10, 47.920, 13.802, {}),
    (11, 47.921, 13.803, {}),
]
WEGE = [(100, [10, 11, 10], {"building": "yes", "amenity": "fuel", "name": "OMV", "operator": "OMV"})]


@pytest.fixture()
def datei(tmp_path):
    pbf = tmp_path / "t.osm.pbf"
    _pbf(pbf, KNOTEN, WEGE)
    z = o.land_einlesen(pbf, tmp_path / "orte-t.sqlite")
    d = o.Laenderdatei(tmp_path / "orte-t.sqlite")
    yield z, d
    d.schliessen()


def test_reads_places_points_and_buildings(datei):
    z, d = datei
    assert z == {"orte": 2, "eintraege": 7}
    tr = o.suchen_in([d], "Wo ist eine Apotheke in Gmunden?", stand="26.09.2026")
    assert len(tr) == 1 and tr[0].quelle.art == "openstreetmap" and o.NENNUNG in tr[0].quelle.titel
    t = tr[0].text
    assert "See-Apotheke; Adresse Theatergasse 3, 4810 Gmunden; Öffnungszeiten Mo–Fr 08:00–18:00; Sa 08:00–12:00" in t
    assert t.index("See-Apotheke") < t.index("Traunstein-Apotheke") and "Stand 26.09.2026" in t and "veraltet" in t
    assert "Tankstelle: OMV" in o.suchen_in([d], "Gibt es in Gmunden eine Tankstelle?")[0].text
    assert "Bankomat; bei Gmunden" in o.suchen_in([d], "Bankomat in Gmunden")[0].text


def test_other_questions_stay_untouched(datei):
    _, d = datei
    for f in ("Wer ist Bundeskanzler?", "Wie wird das Wetter in Gmunden?", "Erklär mir die Photosynthese", ""):
        assert o.suchen_in([d], f) == [], f


def test_names_mountains_and_the_home_town(datei):
    _, d = datei
    assert "Traunstein; Höhe 1.691 m" in o.suchen_in([d], "Wie hoch ist der Traunstein?")[0].text
    t = o.suchen_in([d], "Welche Hütten gibt es am Schafberg?")[0].text
    assert "Himmelspforthütte" in t and "beim Schafberg" in t
    assert o.suchen_in([d], "Wo ist die nächste Apotheke?") == []
    assert "See-Apotheke" in o.suchen_in([d], "Wo ist die nächste Apotheke?", ort_hinweis="Gmunden")[0].text


def test_broken_files_are_refused(tmp_path):
    kaputt = tmp_path / "k.osm.pbf"
    kaputt.write_bytes(struct.pack(">I", 10) + b"\x00" * 5)
    with pytest.raises(o.OrteError):
        o.land_einlesen(kaputt, tmp_path / "k.sqlite")
    riesig = tmp_path / "r.osm.pbf"
    kopf = _f(1, b"OSMData") + _f(3, o.MAX_BLOCK + 1)
    riesig.write_bytes(struct.pack(">I", len(kopf)) + kopf)
    with pytest.raises(o.OrteError):
        o.land_einlesen(riesig, tmp_path / "r.sqlite")


class _Antwort:
    def __init__(self, daten: bytes, status=200):
        self._d, self.status = daten, status

    def read(self, n=-1):
        if n is None or n < 0:
            n = len(self._d)
        x, self._d = self._d[:n], self._d[n:]
        return x

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_copy_loads_checks_reads_and_searches_country_by_country(tmp_path):
    quelle = tmp_path / "quelle.pbf"
    _pbf(quelle, KNOTEN, WEGE)
    roh = quelle.read_bytes()
    md5 = hashlib.md5(roh).hexdigest()
    geholt = []

    def oeffner(req, timeout=None):
        geholt.append(req.full_url)
        assert req.full_url.startswith(o.QUELLE)
        return _Antwort((md5 + "  x-latest.osm.pbf\n").encode() if req.full_url.endswith(".md5") else roh)
    darf = {"ja": True}
    freigabe = {"mb": 500_000}
    k = o.OrteKopie(lambda: tmp_path / "F" / "KIplatz-Speicher" / o.DIRNAME, freigabe_mb=lambda: freigabe["mb"], darf=lambda: darf["ja"], vorgesehen=lambda: True, oeffner=oeffner,
                    platte_frei_mb=lambda p: 900_000, laender=(("t1", "liechtenstein", "Liechtenstein"), ("t2", "austria", "Österreich")))
    assert not k.bereit()
    assert k.schritt() == 0 and k.bereit() and k.laender_fertig() == ["Liechtenstein"]
    assert not (k.ordner / "t1.osm.pbf").exists() and (k.ordner / "orte-t1.sqlite").exists()
    assert "See-Apotheke" in k.suchen("Apotheke in Gmunden")[0].text
    assert k.schritt() == 0 and k.laender_fertig() == ["Liechtenstein", "Österreich"]
    assert k.schritt() == 3600 and k.phase == "fertig"
    assert "Stellen aus T1, T2, fertig" in k.text_de()
    assert all(u.startswith("https://download.geofabrik.de/europe/") for u in geholt)
    darf["ja"] = False
    assert k.schritt() == 30 and k.phase == "pause"
    freigabe["mb"] = 50_000
    assert k.schritt() == 300 and not k.ordner.exists() and not k.bereit() and k.text_de() == ""


def test_only_the_device_meant_for_it_ever_downloads(tmp_path):
    geholt = []

    def oeffner(req, timeout=None):
        geholt.append(req.full_url)
        raise AssertionError("ein normales Gerät lädt nie")
    ordner = tmp_path / "F" / "KIplatz-Speicher" / o.DIRNAME
    for freigabe in (20_000, 500_000):
        k = o.OrteKopie(lambda: ordner, freigabe_mb=lambda: freigabe, darf=lambda: True, vorgesehen=lambda: False, oeffner=oeffner)
        assert k.schritt() == 300 and k.phase == "nicht_vorgesehen" and k.text_de() == ""
    assert geholt == []
    ordner.mkdir(parents=True)
    (ordner / "at.osm.teil").write_bytes(b"x" * 1000)
    k = o.OrteKopie(lambda: ordner, freigabe_mb=lambda: 500_000, darf=lambda: True, vorgesehen=lambda: False, oeffner=oeffner)
    assert k.schritt() == 300 and not ordner.exists()
    k = o.OrteKopie(lambda: ordner, freigabe_mb=lambda: 99_000, darf=lambda: True, vorgesehen=lambda: True, oeffner=oeffner)
    assert k.schritt() == 300 and geholt == []


def test_a_wrong_checksum_is_never_read(tmp_path):
    quelle = tmp_path / "quelle.pbf"
    _pbf(quelle, KNOTEN, WEGE)

    def oeffner(req, timeout=None):
        return _Antwort(("0" * 32 + "\n").encode() if req.full_url.endswith(".md5") else quelle.read_bytes())
    k = o.OrteKopie(lambda: tmp_path / "osm", freigabe_mb=lambda: 500_000, darf=lambda: True, vorgesehen=lambda: True, oeffner=oeffner, platte_frei_mb=lambda p: 900_000,
                    laender=(("t1", "liechtenstein", "Liechtenstein"),))
    with pytest.raises(o.OrteError):
        k.schritt()
    assert not k.bereit() and not any((tmp_path / "osm").glob("*.pbf")) and not any((tmp_path / "osm").glob("*.teil"))
    with pytest.raises(o.OrteError):
        k._holen("https://example.com/boese.pbf")


def test_program_asks_the_places_before_searching_the_net():
    code = (Path(__file__).resolve().parent.parent / "app_web.py").read_text(encoding="utf-8")
    assert "self._osm = osm_orte.OrteKopie(" in code and "self._osm.start()" in code
    assert "if not live and self.nachschauen_an():" in code and "kandidaten = ergaenzend + orte + server + lokal" in code
    assert "self._wiki.belegt_mb() - self._osm.belegt_mb()" in code
    assert "vorgesehen=lambda: self._community.ist_admin()" in code
