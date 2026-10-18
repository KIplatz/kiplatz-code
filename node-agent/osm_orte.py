# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import itertools
import math
import re
import shutil
import sqlite3
import struct
import threading
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import app_core
import sicher_schreiben
import umzug
import wissen

QUELLE = "https://download.geofabrik.de/europe/"
LAENDER = (("li", "liechtenstein", "Liechtenstein"), ("at", "austria", "Österreich"), ("ch", "switzerland", "Schweiz"), ("de", "germany", "Deutschland"))
DIRNAME = "openstreetmap"
STAND = "stand.json"
MIN_FREIGABE_MB = 100_000
FREI_RESERVE_MB = 10_000
NEU_NACH_TAGE = 30
TIMEOUT_S = 60.0
AUSGABE_TAGE_ZURUECK = 7
FEHLER_PAUSE_S = 3600
LIZENZ = "ODbL"
NENNUNG = "© OpenStreetMap-Mitwirkende, ODbL"
MAX_BLOCK = 64 * 1024 * 1024
BLOCKS_JE_SCHRITT = 40
PAUSE_S = 30
_UA = "KIplatz-Orte/1 (eine Kopie je Monat und Land für die eigene Suche; https://kiplatz.at)"


class OrteError(app_core.AppError):
    pass


KATEGORIEN: dict[tuple[str, str], str] = {
    ("amenity", "pharmacy"): "Apotheke", ("amenity", "doctors"): "Arztpraxis", ("healthcare", "doctor"): "Arztpraxis",
    ("amenity", "dentist"): "Zahnarzt", ("amenity", "veterinary"): "Tierarzt", ("amenity", "hospital"): "Krankenhaus",
    ("amenity", "clinic"): "Klinik", ("amenity", "fuel"): "Tankstelle", ("amenity", "charging_station"): "Ladestation",
    ("amenity", "atm"): "Bankomat", ("amenity", "bank"): "Bank", ("amenity", "post_office"): "Postamt", ("amenity", "police"): "Polizei",
    ("amenity", "fire_station"): "Feuerwehr", ("amenity", "townhall"): "Gemeindeamt", ("amenity", "restaurant"): "Gasthaus",
    ("amenity", "cafe"): "Café", ("amenity", "fast_food"): "Imbiss", ("amenity", "pub"): "Lokal", ("amenity", "bar"): "Bar",
    ("amenity", "cinema"): "Kino", ("amenity", "theatre"): "Theater", ("amenity", "library"): "Bücherei", ("amenity", "school"): "Schule",
    ("amenity", "kindergarten"): "Kindergarten", ("amenity", "car_wash"): "Waschanlage", ("amenity", "car_rental"): "Autoverleih",
    ("amenity", "taxi"): "Taxistand", ("amenity", "recycling"): "Altstoffsammelzentrum",
    ("shop", "supermarket"): "Supermarkt", ("shop", "bakery"): "Bäckerei", ("shop", "butcher"): "Fleischhauer", ("shop", "chemist"): "Drogerie",
    ("shop", "hairdresser"): "Friseur", ("shop", "doityourself"): "Baumarkt", ("shop", "hardware"): "Baumarkt", ("shop", "florist"): "Blumengeschäft",
    ("shop", "optician"): "Optiker", ("shop", "bicycle"): "Radgeschäft", ("shop", "car_repair"): "Autowerkstatt", ("shop", "kiosk"): "Trafik",
    ("shop", "tobacco"): "Trafik", ("shop", "convenience"): "Nahversorger", ("shop", "pastry"): "Konditorei", ("shop", "farm"): "Hofladen",
    ("shop", "books"): "Buchhandlung", ("shop", "shoes"): "Schuhgeschäft", ("shop", "sports"): "Sportgeschäft",
    ("craft", "car_repair"): "Autowerkstatt",
    ("tourism", "alpine_hut"): "Hütte", ("tourism", "wilderness_hut"): "Hütte", ("tourism", "hotel"): "Hotel", ("tourism", "guest_house"): "Pension",
    ("tourism", "hostel"): "Herberge", ("tourism", "camp_site"): "Campingplatz", ("tourism", "museum"): "Museum", ("tourism", "zoo"): "Tierpark",
    ("tourism", "viewpoint"): "Aussichtspunkt", ("tourism", "information"): "Tourismusinformation",
    ("leisure", "swimming_pool"): "Schwimmbad", ("leisure", "water_park"): "Schwimmbad", ("leisure", "playground"): "Spielplatz",
    ("leisure", "sports_centre"): "Sportzentrum", ("leisure", "golf_course"): "Golfplatz", ("leisure", "fitness_centre"): "Fitnessstudio",
    ("railway", "station"): "Bahnhof", ("aerialway", "station"): "Seilbahnstation", ("natural", "peak"): "Berg",
    ("amenity", "place_of_worship"): "Kirche", ("historic", "castle"): "Burg oder Schloss",
}
OHNE_NAMEN = {"Bankomat", "Ladestation", "Spielplatz", "Aussichtspunkt"}
ORTSARTEN = {"city": 4, "town": 3, "village": 2, "suburb": 1, "hamlet": 0}
FRAGEWOERTER: dict[str, str] = {
    "apotheke": "Apotheke", "arzt": "Arztpraxis", "ärzt": "Arztpraxis", "hausarzt": "Arztpraxis", "hausärzt": "Arztpraxis", "arztpraxis": "Arztpraxis",
    "praktischer arzt": "Arztpraxis", "zahnarzt": "Zahnarzt", "zahnärzt": "Zahnarzt", "tierarzt": "Tierarzt", "tierärzt": "Tierarzt",
    "krankenhaus": "Krankenhaus", "krankenhäus": "Krankenhaus", "spital": "Krankenhaus", "spitäl": "Krankenhaus", "klinik": "Klinik",
    "tankstelle": "Tankstelle", "tanken": "Tankstelle", "ladestation": "Ladestation", "e-tankstelle": "Ladestation", "stromtankstelle": "Ladestation",
    "bankomat": "Bankomat", "geldautomat": "Bankomat", "bank": "Bank", "postamt": "Postamt", "postfiliale": "Postamt", "postpartner": "Postamt",
    "polizei": "Polizei", "polizeiinspektion": "Polizei", "feuerwehr": "Feuerwehr", "gemeindeamt": "Gemeindeamt", "rathaus": "Gemeindeamt",
    "gasthaus": "Gasthaus", "gasthäus": "Gasthaus", "wirtshaus": "Gasthaus", "wirtshäus": "Gasthaus", "restaurant": "Gasthaus", "gasthof": "Gasthaus",
    "essen gehen": "Gasthaus", "pizzeria": "Gasthaus", "café": "Café", "cafe": "Café", "kaffeehaus": "Café", "imbiss": "Imbiss", "würstelstand": "Imbiss",
    "kino": "Kino", "theater": "Theater", "bücherei": "Bücherei", "bibliothek": "Bücherei", "schule": "Schule", "kindergarten": "Kindergarten",
    "waschanlage": "Waschanlage", "autowäsche": "Waschanlage", "taxi": "Taxistand", "altstoffsammelzentrum": "Altstoffsammelzentrum", "mistplatz": "Altstoffsammelzentrum",
    "supermarkt": "Supermarkt", "supermärkt": "Supermarkt", "bäcker": "Bäckerei", "bäckerei": "Bäckerei", "fleischhauer": "Fleischhauer", "metzger": "Fleischhauer",
    "metzgerei": "Fleischhauer", "drogerie": "Drogerie", "friseur": "Friseur", "frisör": "Friseur", "baumarkt": "Baumarkt", "baumärkt": "Baumarkt",
    "blumengeschäft": "Blumengeschäft", "blumenladen": "Blumengeschäft", "optiker": "Optiker", "radgeschäft": "Radgeschäft", "fahrradgeschäft": "Radgeschäft",
    "werkstatt": "Autowerkstatt", "autowerkstatt": "Autowerkstatt", "trafik": "Trafik", "konditorei": "Konditorei", "hofladen": "Hofladen", "ab hof": "Hofladen",
    "buchhandlung": "Buchhandlung", "hütte": "Hütte", "berghütte": "Hütte", "schutzhütte": "Hütte", "hotel": "Hotel", "pension": "Pension",
    "übernachten": "Hotel", "campingplatz": "Campingplatz", "camping": "Campingplatz", "museum": "Museum", "museen": "Museum", "tierpark": "Tierpark", "zoo": "Tierpark",
    "aussichtspunkt": "Aussichtspunkt", "tourismusinformation": "Tourismusinformation", "schwimmbad": "Schwimmbad", "freibad": "Schwimmbad",
    "hallenbad": "Schwimmbad", "therme": "Schwimmbad", "spielplatz": "Spielplatz", "spielplätz": "Spielplatz", "sportzentrum": "Sportzentrum",
    "golfplatz": "Golfplatz", "fitnessstudio": "Fitnessstudio", "bahnhof": "Bahnhof", "bahnhöf": "Bahnhof", "seilbahn": "Seilbahnstation",
    "berg": "Berg", "gipfel": "Berg", "wie hoch ist": "Berg", "kirche": "Kirche", "burg": "Burg oder Schloss", "schloss": "Burg oder Schloss",
}
_FRAGE_ART = [(re.compile(r"(?<![\wäöüß])" + re.escape(w) + r"[\wäöüß]{0,3}(?![\wäöüß])", re.I), art)
              for w, art in sorted(FRAGEWOERTER.items(), key=lambda x: -len(x[0]))]
_TAGE = {"Mo": "Mo", "Tu": "Di", "We": "Mi", "Th": "Do", "Fr": "Fr", "Sa": "Sa", "Su": "So", "PH": "Feiertag", "off": "geschlossen"}
_TAGE_RE = re.compile(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH|off)\b")
_KEIN_ORT = {"wie", "wo", "was", "wann", "wer", "gibt", "ist", "die", "der", "das", "ein", "eine", "ich", "hier", "heute", "morgen", "welche",
             "apotheke", "berg", "bank", "post", "schule", "kirche", "burg", "schloss", "hütte", "hotel", "see", "bad", "au", "dorf", "ort", "hof",
             "nähe", "umgebung", "sonntag", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "offen", "geöffnet", "nächste", "nächsten"}


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _varint(b, i: int) -> tuple[int, int]:
    n = shift = 0
    while True:
        x = b[i]
        i += 1
        n |= (x & 0x7F) << shift
        if x < 0x80:
            return n, i
        shift += 7
        if shift > 63:
            raise OrteError("OSM_FORMAT", "Zahl im Format zu lang")


def _felder(b):
    i, n = 0, len(b)
    while i < n:
        k, i = _varint(b, i)
        feld, typ = k >> 3, k & 7
        if typ == 0:
            v, i = _varint(b, i)
        elif typ == 2:
            laenge, i = _varint(b, i)
            v = b[i:i + laenge]
            i += laenge
        elif typ == 1:
            v = b[i:i + 8]
            i += 8
        elif typ == 5:
            v = b[i:i + 4]
            i += 4
        else:
            raise OrteError("OSM_FORMAT", f"unbekannter Feldtyp {typ}")
        yield feld, v


def _zahlen(b) -> list[int]:
    out: list[int] = []
    ap = out.append
    n = shift = 0
    for x in bytes(b):
        n |= (x & 0x7F) << shift
        if x < 0x80:
            ap(n)
            n = shift = 0
        else:
            shift += 7
    return out


def _zz(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _delta(b) -> list[int]:
    return list(itertools.accumulate(_zz(x) for x in _zahlen(b)))


def bloecke(pfad: Path, *, ab: int = 0):
    with open(pfad, "rb") as f:
        f.seek(ab)
        while True:
            versatz = f.tell()
            kopf_len = f.read(4)
            if not kopf_len:
                return
            if len(kopf_len) < 4:
                raise OrteError("OSM_FORMAT", "Datei endet mitten in einem Block")
            (n,) = struct.unpack(">I", kopf_len)
            if n > 64 * 1024:
                raise OrteError("OSM_FORMAT", "Blockkopf zu groß")
            art, groesse = "", 0
            for feld, v in _felder(f.read(n)):
                if feld == 1:
                    art = bytes(v).decode("ascii", "replace")
                elif feld == 3:
                    groesse = v
            if groesse <= 0 or groesse > MAX_BLOCK:
                raise OrteError("OSM_FORMAT", "Blockgröße unzulässig")
            roh = f.read(groesse)
            daten = b""
            for feld, v in _felder(roh):
                if feld == 1:
                    daten = bytes(v)
                elif feld == 3:
                    d = zlib.decompressobj()
                    daten = d.decompress(bytes(v), MAX_BLOCK)
                    if d.unconsumed_tail:
                        raise OrteError("OSM_FORMAT", "Block entpackt zu groß")
                elif feld in (4, 5, 6, 7):
                    raise OrteError("OSM_FORMAT", "Block mit unbekannter Packart")
            yield versatz, art, daten


def _block_lesen(daten: bytes, *, wege: bool, knoten_ids: set[int] | None = None):
    strings: list[str] = []
    gruppen = []
    gran, lat_off, lon_off = 100, 0, 0
    for feld, v in _felder(daten):
        if feld == 1:
            strings = [bytes(s).decode("utf-8", "replace") for f2, s in _felder(v) if f2 == 1]
        elif feld == 2:
            gruppen.append(v)
        elif feld == 17:
            gran = v
        elif feld == 19:
            lat_off = _zz(v)
        elif feld == 20:
            lon_off = _zz(v)

    def lage(la: int, lo: int) -> tuple[float, float]:
        return (lat_off + gran * la) * 1e-9, (lon_off + gran * lo) * 1e-9

    for g in gruppen:
        for feld, v in _felder(g):
            if feld == 2:
                ids = lats = lons = kv = None
                for f2, w in _felder(v):
                    if f2 == 1:
                        ids = _delta(w)
                    elif f2 == 8:
                        lats = _delta(w)
                    elif f2 == 9:
                        lons = _delta(w)
                    elif f2 == 10:
                        kv = w
                if ids is None or lats is None or lons is None:
                    continue
                if knoten_ids is not None:
                    for j, nid in enumerate(ids):
                        if nid in knoten_ids:
                            yield ("knoten", nid, *lage(lats[j], lons[j]), {})
                    continue
                if kv is None:
                    continue
                zahlen = _zahlen(kv)
                j = p = 0
                while j < len(ids) and p < len(zahlen):
                    if zahlen[p] == 0:
                        p += 1
                        j += 1
                        continue
                    tags = {}
                    while p < len(zahlen) and zahlen[p] != 0:
                        tags[strings[zahlen[p]]] = strings[zahlen[p + 1]]
                        p += 2
                    p += 1
                    yield ("knoten", ids[j], *lage(lats[j], lons[j]), tags)
                    j += 1
            elif feld == 1:
                nid, keys, vals, la, lo = 0, [], [], 0, 0
                for f2, w in _felder(v):
                    if f2 == 1:
                        nid = _zz(w)
                    elif f2 == 2:
                        keys = _zahlen(w)
                    elif f2 == 3:
                        vals = _zahlen(w)
                    elif f2 == 8:
                        la = _zz(w)
                    elif f2 == 9:
                        lo = _zz(w)
                if knoten_ids is not None:
                    if nid in knoten_ids:
                        yield ("knoten", nid, *lage(la, lo), {})
                elif keys:
                    yield ("knoten", nid, *lage(la, lo), {strings[k]: strings[x] for k, x in zip(keys, vals)})
            elif feld == 3 and wege:
                wid, keys, vals, erster = 0, [], [], None
                for f2, w in _felder(v):
                    if f2 == 1:
                        wid = w
                    elif f2 == 2:
                        keys = _zahlen(w)
                    elif f2 == 3:
                        vals = _zahlen(w)
                    elif f2 == 8 and len(w):
                        erster = _zz(_varint(w, 0)[0])
                if keys and erster is not None:
                    yield ("weg", wid, erster, {strings[k]: strings[x] for k, x in zip(keys, vals)})


def art_von(tags: dict) -> str:
    for k in ("amenity", "shop", "tourism", "leisure", "healthcare", "craft", "railway", "aerialway", "natural", "historic"):
        v = tags.get(k)
        if v and (k, v) in KATEGORIEN:
            return KATEGORIEN[(k, v)]
    return ""


def _name(tags: dict, art: str) -> str:
    n = tags.get("name:de") or tags.get("name") or ""
    if not n and art in OHNE_NAMEN:
        n = tags.get("brand") or tags.get("operator") or ""
    return " ".join(n.split())[:120]


def oeffnungszeiten_de(s: str) -> str:
    s = _TAGE_RE.sub(lambda m: _TAGE[m.group(1)], s or "")
    return re.sub(r"(?<=[\w:])-(?=[\w:])", "–", s)[:200]


def eintrag_text(art: str, name: str, tags: dict, gemeinde: str = "") -> str:
    teile = [f"{art}: {name}" if name and name.lower() != art.lower() else art]
    adresse = _adresse(tags)
    if adresse:
        teile.append(f"Adresse {adresse}")
    elif gemeinde:
        teile.append(f"bei {gemeinde}")
    if tags.get("ele") and art in ("Berg", "Hütte", "Aussichtspunkt", "Seilbahnstation"):
        hoehe = re.sub(r"[^\d.,]", "", tags["ele"]).replace(",", ".")
        try:
            teile.append(f"Höhe {round(float(hoehe)):,} m".replace(",", "."))
        except ValueError:
            pass
    if tags.get("opening_hours"):
        teile.append(f"Öffnungszeiten {oeffnungszeiten_de(tags['opening_hours'])}")
    tel = tags.get("phone") or tags.get("contact:phone")
    if tel:
        teile.append(f"Telefon {tel[:40]}")
    web = tags.get("website") or tags.get("contact:website")
    if web and web.startswith(("http://", "https://")):
        teile.append(f"Website {web[:120]}")
    if tags.get("operator") and art in ("Hütte", "Bankomat", "Ladestation", "Tankstelle"):
        teile.append(f"Betreiber {tags['operator'][:80]}")
    if tags.get("cuisine") and art in ("Gasthaus", "Imbiss"):
        teile.append("Küche " + tags["cuisine"].replace(";", ", ").replace("_", " ")[:80])
    return "; ".join(teile)


def _adresse(tags: dict) -> str:
    strasse = " ".join(x for x in (tags.get("addr:street") or tags.get("addr:place") or "", tags.get("addr:housenumber") or "") if x)
    ort = " ".join(x for x in (tags.get("addr:postcode") or "", tags.get("addr:city") or "") if x)
    return ", ".join(x for x in (strasse, ort) if x)


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\wäöüß ]", " ", (s or "").lower()).split())


def entfernung_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(min(1.0, math.sqrt(h)))


def land_einlesen(pbf: Path, ziel: Path, *, darf=lambda: True, fortschritt=None, warten=None) -> dict:
    try:
        return _land_einlesen(pbf, ziel, darf=darf, fortschritt=fortschritt, warten=warten)
    except (IndexError, struct.error, zlib.error, UnicodeError, KeyError, ValueError) as exc:
        ziel.unlink(missing_ok=True)
        raise OrteError("OSM_FORMAT", f"die Datei ist nicht lesbar ({type(exc).__name__})") from None
    except (OrteError, Unterbrochen):
        ziel.unlink(missing_ok=True)
        raise


def _land_einlesen(pbf: Path, ziel: Path, *, darf=lambda: True, fortschritt=None, warten=None) -> dict:

    def _weiter() -> None:
        if darf():
            return
        if warten is None:
            raise Unterbrochen()
        while not darf():
            if not warten(PAUSE_S):
                raise Unterbrochen()
    ziel.unlink(missing_ok=True)
    db = sqlite3.connect(ziel)
    try:
        db.executescript("""
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            CREATE TABLE eintrag(id INTEGER PRIMARY KEY, osm TEXT, art TEXT, name TEXT, lat REAL, lon REAL, gemeinde TEXT, text TEXT, adresse INTEGER);
            CREATE TABLE ort(name TEXT, norm TEXT, typ TEXT, rang INTEGER, lat REAL, lon REAL, einwohner INTEGER);
            CREATE TABLE info(k TEXT PRIMARY KEY, v TEXT);
        """)
        einfuegen = "INSERT INTO eintrag(osm, art, name, lat, lon, text, adresse) VALUES (?,?,?,?,?,?,?)"
        orte: list[tuple[str, str, float, float, int]] = []
        stapel: list[tuple] = []
        wege: dict[int, list[tuple]] = {}
        wege_ab = 0
        for i, (versatz, art_block, daten) in enumerate(bloecke(pbf)):
            if art_block != "OSMData":
                continue
            if i % BLOCKS_JE_SCHRITT == 0:
                _weiter()
                if fortschritt:
                    fortschritt(1, versatz)
            for e in _block_lesen(daten, wege=True):
                tags = e[-1]
                if e[0] == "knoten":
                    if tags.get("place") in ORTSARTEN and tags.get("name"):
                        ew = re.sub(r"\D", "", tags.get("population", "") or "")[:9]
                        orte.append((tags.get("name:de") or tags["name"], tags["place"], e[2], e[3], int(ew) if ew else 0))
                    a = art_von(tags)
                    if a:
                        n = _name(tags, a)
                        if n or a in OHNE_NAMEN:
                            stapel.append((f"node/{e[1]}", a, n, e[2], e[3], eintrag_text(a, n, tags), 1 if _adresse(tags) else 0))
                else:
                    if not wege_ab:
                        wege_ab = versatz
                    a = art_von(tags)
                    if a and tags.get("building") != "construction":
                        n = _name(tags, a)
                        if n:
                            wege.setdefault(e[2], []).append((f"way/{e[1]}", a, n, eintrag_text(a, n, tags), 1 if _adresse(tags) else 0))
            if len(stapel) >= 5000:
                db.executemany(einfuegen, stapel)
                stapel = []
        db.executemany(einfuegen, stapel)
        stapel = []
        if wege:
            gesucht = set(wege)
            for i, (versatz, art_block, daten) in enumerate(bloecke(pbf)):
                if wege_ab and versatz >= wege_ab:
                    break
                if art_block != "OSMData":
                    continue
                if i % BLOCKS_JE_SCHRITT == 0:
                    _weiter()
                    if fortschritt:
                        fortschritt(2, versatz)
                for e in _block_lesen(daten, wege=False, knoten_ids=gesucht):
                    for osm, a, n, text, adr in wege.pop(e[1], ()):
                        stapel.append((osm, a, n, e[2], e[3], text, adr))
                if len(stapel) >= 5000:
                    db.executemany(einfuegen, stapel)
                    stapel = []
            db.executemany(einfuegen, stapel)
            wege.clear()
        db.executemany("INSERT INTO ort VALUES (?,?,?,?,?,?,?)", [(o[0], _norm(o[0]), o[1], ORTSARTEN[o[1]], o[2], o[3], o[4]) for o in orte])
        raster: dict[tuple[int, int], list] = {}
        for o in orte:
            if o[1] in ("city", "town", "village"):
                raster.setdefault((int(o[2] * 10), int(o[3] * 10)), []).append(o)

        def gemeinde(la: float, lo: float) -> str:
            best, bd = "", 1e9
            gx, gy = int(la * 10), int(lo * 10)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for o in raster.get((gx + dx, gy + dy), ()):
                        d = (o[2] - la) ** 2 + ((o[3] - lo) * 0.7) ** 2
                        if d < bd:
                            best, bd = o[0], d
            return best

        letzte = 0
        while True:
            rows = db.execute("SELECT id, lat, lon, adresse FROM eintrag WHERE id > ? ORDER BY id LIMIT 20000", (letzte,)).fetchall()
            if not rows:
                break
            neu = []
            for rid, la, lo, adr in rows:
                g = gemeinde(la, lo)
                neu.append((g, "" if adr or not g else f"; bei {g}", rid))
            db.executemany("UPDATE eintrag SET gemeinde=?, text=text || ? WHERE id=?", neu)
            letzte = rows[-1][0]
        zeilen = db.execute("SELECT COUNT(*) FROM eintrag").fetchone()[0]
        db.executescript("""
            CREATE INDEX ort_norm ON ort(norm);
            CREATE INDEX eintrag_art_lage ON eintrag(art, lat, lon);
            CREATE VIRTUAL TABLE eintrag_name USING fts5(name, content='eintrag', content_rowid='id', tokenize="unicode61 remove_diacritics 2");
            INSERT INTO eintrag_name(rowid, name) SELECT id, name FROM eintrag WHERE name != '';
        """)
        db.execute("INSERT INTO info VALUES ('erstellt', ?)", (_jetzt(),))
        db.commit()
    finally:
        db.close()
    return {"orte": len(orte), "eintraege": zeilen}


class Unterbrochen(Exception):
    pass


def frage_art(frage: str) -> str:
    for muster, art in _FRAGE_ART:
        if muster.search(frage or ""):
            return art
    return ""


def _ortsworte(frage: str) -> list[str]:
    w = re.findall(r"[A-ZÄÖÜ][\wäöüß.\-]*", frage or "")
    w = [x.rstrip(".") if not x.endswith("St.") else x for x in w]
    out = []
    for n in (3, 2, 1):
        for i in range(len(w) - n + 1):
            k = " ".join(w[i:i + n])
            if n == 1 and (k.lower() in _KEIN_ORT or len(k) < 3 or frage_art(k)):
                continue
            out.append(k)
    return out


class Laenderdatei:
    def __init__(self, pfad: Path) -> None:
        self.pfad = pfad
        self._db = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, check_same_thread=False)
        self._lock = threading.Lock()

    def schliessen(self) -> None:
        with self._lock:
            self._db.close()

    def ort(self, kandidaten: list[str]) -> tuple[str, float, float, int] | None:
        t = self.ort_treffer(kandidaten)
        return t[0][3:7] if t else None

    def ort_treffer(self, kandidaten: list[str]) -> list[tuple[int, int, int, str, float, float, int]]:
        out = []
        with self._lock:
            for i, k in enumerate(kandidaten):
                norm = _norm(k.replace("St.", "Sankt"))
                for n in {norm, _norm(k)}:
                    r = self._db.execute("SELECT name, lat, lon, rang, einwohner FROM ort WHERE norm=? ORDER BY rang DESC, einwohner DESC LIMIT 1",
                                         (n,)).fetchone()
                    if r:
                        out.append((i, int(r[3] or 0), int(r[4] or 0), r[0], r[1], r[2], r[3]))
                        break
        return out

    def naechste(self, art: str, lat: float, lon: float, *, km: float, n: int) -> list[tuple[float, str, str]]:
        d_lat = km / 111.0
        d_lon = km / (111.0 * max(0.2, math.cos(math.radians(lat))))
        with self._lock:
            rows = self._db.execute("SELECT lat, lon, text, osm FROM eintrag WHERE art=? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                                    (art, lat - d_lat, lat + d_lat, lon - d_lon, lon + d_lon)).fetchall()
        mit = sorted(((entfernung_km((lat, lon), (a, b)), t, o) for a, b, t, o in rows), key=lambda x: x[0])
        return [x for x in mit if x[0] <= km][:n]

    def namen(self, art: str, worte: list[str], n: int) -> list[tuple[float, str, str, float, float]]:
        ausdruck = " OR ".join('"' + w.replace('"', "") + '"*' for w in worte if len(w) >= 3)
        if not ausdruck:
            return []
        with self._lock:
            try:
                rows = self._db.execute("SELECT e.text, e.osm, e.lat, e.lon FROM eintrag_name JOIN eintrag e ON e.id = eintrag_name.rowid "
                                        "WHERE eintrag_name MATCH ? AND e.art=? ORDER BY bm25(eintrag_name) LIMIT ?", (ausdruck, art, n)).fetchall()
            except sqlite3.Error:
                return []
        return [(0.0, t, o, la, lo) for t, o, la, lo in rows]


NACH_NAMEN = ("Berg", "Hütte", "Burg oder Schloss", "Museum", "Tierpark", "Seilbahnstation")
BERGNAH = ("Hütte", "Aussichtspunkt", "Seilbahnstation")


def bester_ort(dateien: list, kandidaten: list[str], frage: str = "") -> tuple[str, float, float, int] | None:
    import region as region_mod
    r = region_mod.erkennen(frage or "")
    gewuenscht = r.land if r is not None else ""
    if not gewuenscht:
        import laender
        gewuenscht = (laender.erkennen(frage or "") or "").lower()
    alle = []
    for d in dateien:
        land = Path(getattr(d, "pfad", "")).stem.removeprefix("orte-") if getattr(d, "pfad", None) else ""
        for i, rang, ew, name, la, lo, rang_roh in d.ort_treffer(kandidaten):
            alle.append(((i, 0 if land == gewuenscht else 1, -rang, -ew), (name, la, lo, rang_roh)))
    return min(alle, key=lambda x: x[0])[1] if alle else None


def suchen_in(dateien: list[Laenderdatei], frage: str, *, stand: str = "", ort_hinweis: str = "") -> list[wissen.Treffer]:
    art = frage_art(frage)
    if not art or not dateien:
        return []
    kandidaten = _ortsworte(frage)
    ort = bester_ort(dateien, kandidaten, frage)
    worte = list(dict.fromkeys(w for k in kandidaten for w in k.split() if w.lower() not in _KEIN_ORT and not frage_art(w)))
    liste: list[tuple[float, str, str]] = []
    titel = ""
    if art in NACH_NAMEN and worte:
        for d in dateien:
            liste += [x[:3] for x in d.namen(art, worte, 4)]
        if liste:
            titel = f"{art}: nach dem Namen gesucht"
    gruppen: list[tuple[str, list]] = []
    if not liste and worte and (art in BERGNAH or not ort):
        berge = [b for d in dateien for b in d.namen("Berg", worte, 3)][:3]
        ohne = []
        for _, btext, _, bla, blo in berge:
            nah = sorted((x for d in dateien for x in d.naechste(art, bla, blo, km=5.0, n=5)), key=lambda x: x[0])[:5]
            if nah:
                gruppen.append((f"{art} beim {btext.removeprefix('Berg: ')}", nah))
            else:
                ohne.append(btext.removeprefix("Berg: "))
        if gruppen and ohne:
            gruppen.append((f"Weitere Berge dieses Namens, ohne eingetragene {art} im Umkreis von 5 km", [(0.0, x, "") for x in ohne]))
    if not ort and not liste and not gruppen and ort_hinweis:
        ort = bester_ort(dateien, [ort_hinweis], frage)
    if not liste and not gruppen and ort:
        name, la, lo, rang = ort
        km = 8.0 if rang >= 3 else 15.0
        for d in dateien:
            liste += d.naechste(art, la, lo, km=km, n=6)
        liste.sort(key=lambda x: x[0])
        liste = liste[:6]
        titel = f"{art} bei {name}"
    if liste:
        gruppen = [(titel, liste)]
    if not gruppen:
        return []
    teile = []
    for titel_g, eintraege in gruppen:
        zeilen = [f"{titel_g}:"]
        for km_, text, _osm in eintraege:
            weit = f" (etwa {km_:.1f} km entfernt)".replace(".", ",") if km_ > 0 else ""
            zeilen.append(f"- {text}{weit}")
        teile.append("\n".join(zeilen))
    kopf = "Laut OpenStreetMap" + (f", Stand {stand}" if stand else "") + ". Die Daten tragen Freiwillige ein; Öffnungszeiten können veraltet sein."
    text = kopf + "\n" + "\n\n".join(teile)
    echte = [g for g in gruppen if g[1] and g[1][0][2]]
    titel = echte[0][0] if len(echte) == 1 else f"{art}, {len(echte)} Orte dieses Namens"
    adresse = "https://www.openstreetmap.org/" + gruppen[0][1][0][2]
    q = wissen.Quelle(wissen.kennung_fuer("osm", titel + "|" + gruppen[0][1][0][2]), "openstreetmap", f"OpenStreetMap: {titel} ({NENNUNG})", adresse,
                      _jetzt(), len(text))
    return [wissen.Treffer(q, text, 9.0)]


def ordner_groesse_mb(ordner: Path) -> int:
    try:
        return sum(p.stat().st_size for p in Path(ordner).rglob("*") if p.is_file()) // 1_000_000
    except OSError:
        return 0


class OrteKopie:

    def __init__(self, ordner, *, freigabe_mb, darf, vorgesehen=lambda: False, oeffner=None, log=None, schlafen=None, jetzt=time.time, platte_frei_mb=None,
                 laender=LAENDER) -> None:
        self._ordner_fn = ordner
        self._freigabe_mb = freigabe_mb
        self._darf = darf
        self._vorgesehen = vorgesehen
        self._oeffner = oeffner
        self._log = log or (lambda z: None)
        self._halt = threading.Event()
        self._schlafen = schlafen or (lambda s: self._halt.wait(s))
        self._jetzt = jetzt
        self._platte_frei_mb = platte_frei_mb or (lambda p: shutil.disk_usage(p).free // 1_000_000)
        self._laender = laender
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._dateien: dict[str, Laenderdatei] = {}
        self.phase, self.meldung = "aus", ""
        self._belegt = (0.0, 0)
        self._fest: Path | None = None

    @property
    def ordner(self) -> Path:
        return self._fest if self._fest is not None else Path(self._ordner_fn())

    def _stand(self) -> dict:
        return sicher_schreiben.json_laden(self.ordner / STAND, {})

    def _stand_setzen(self, **werte) -> dict:
        d = self._stand()
        d.update(werte)
        self.ordner.mkdir(parents=True, exist_ok=True)
        sicher_schreiben.json_datei(self.ordner / STAND, d)
        return d

    def belegt_mb(self) -> int:
        t, mb = self._belegt
        if self._jetzt() - t > 300:
            mb = ordner_groesse_mb(self.ordner) if self.ordner.exists() else 0
            self._belegt = (self._jetzt(), mb)
        return mb

    def darf_halten(self) -> bool:
        try:
            vorgesehen = bool(self._vorgesehen())
        except Exception:
            vorgesehen = False
        return vorgesehen and int(self._freigabe_mb() or 0) >= MIN_FREIGABE_MB

    def bereit(self) -> bool:
        return bool(self._dateien)

    def laender_fertig(self) -> list[str]:
        st = self._stand()
        return [name for kurz, _, name in self._laender if st.get(f"fertig_{kurz}")]


    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._halt.clear()
            self._oeffnen()
            self._thread = threading.Thread(target=self._schleife, name="openstreetmap", daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout_s: float = 10.0) -> None:
        self._halt.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=timeout_s)

    def _oeffnen(self) -> None:
        if umzug.offen(self.ordner):
            return
        st = self._stand()
        for kurz, _, _ in self._laender:
            pfad = self.ordner / f"orte-{kurz}.sqlite"
            if kurz not in self._dateien and st.get(f"fertig_{kurz}") and pfad.exists():
                try:
                    self._dateien[kurz] = Laenderdatei(pfad)
                except sqlite3.Error as exc:
                    self._log(f"FEHLER openstreetmap öffnen {kurz}: {exc}")

    def loeschen(self) -> None:
        with self._lock:
            for d in self._dateien.values():
                d.schliessen()
            self._dateien = {}
            shutil.rmtree(self.ordner, ignore_errors=True)
            self._belegt = (0.0, 0)
            self.phase, self.meldung = "aus", ""

    def umzug_vormerken(self, von: Path, nach: Path) -> None:
        if umzug.vormerken(Path(von), Path(nach)):
            self._log("OK openstreetmap: Umzug auf das gewählte Laufwerk vorgemerkt")

    def _schliessen(self) -> None:
        with self._lock:
            for d in self._dateien.values():
                d.schliessen()
            self._dateien = {}
            self._belegt = (0.0, 0)


    def _holen(self, adresse: str, *, bereich: int | None = None, fehlt_ok: bool = False):
        if not adresse.startswith(QUELLE):
            raise OrteError("OSM_ADRESSE", "nur von download.geofabrik.de")
        kopf = {"User-Agent": _UA}
        if bereich:
            kopf["Range"] = f"bytes={bereich}-"
        oeffner = self._oeffner or __import__("datenfluss").oeffner("Orte aus OpenStreetMap von Geofabrik laden (einmal im Monat je Land)")
        try:
            return oeffner(urllib.request.Request(adresse, headers=kopf), timeout=TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            if fehlt_ok and exc.code == 404:
                return None
            raise OrteError("OSM_HOLEN", f"download.geofabrik.de antwortet nicht (HTTP {exc.code} für {adresse.rsplit('/', 1)[-1]})") from None
        except Exception as exc:
            raise OrteError("OSM_HOLEN", f"download.geofabrik.de antwortet nicht ({type(exc).__name__})") from None

    @staticmethod
    def _md5_lesen(r) -> str:
        with r:
            m = re.match(r"\s*([0-9a-f]{32})\b", r.read(1000).decode("ascii", "replace"))
        if not m:
            raise OrteError("OSM_MD5", "Prüfsumme bei Geofabrik nicht lesbar")
        return m.group(1)

    def _ausgabe(self, name: str) -> tuple[str, str]:
        r = self._holen(f"{QUELLE}{name}-latest.osm.pbf.md5", fehlt_ok=True)
        if r is not None:
            return f"{name}-latest.osm.pbf", self._md5_lesen(r)
        heute = datetime.fromtimestamp(self._jetzt(), timezone.utc).date()
        for tage in range(AUSGABE_TAGE_ZURUECK + 1):
            datei = f"{name}-{(heute - timedelta(days=tage)).strftime('%y%m%d')}.osm.pbf"
            r = self._holen(f"{QUELLE}{datei}.md5", fehlt_ok=True)
            if r is not None:
                return datei, self._md5_lesen(r)
        raise OrteError("OSM_AUSGABE", f"bei download.geofabrik.de keine Ausgabe für {name} aus den letzten {AUSGABE_TAGE_ZURUECK} Tagen")

    def _laden(self, datei: str, ziel: Path, md5: str) -> bool:
        teil = ziel.with_suffix(".teil")
        schon = teil.stat().st_size if teil.exists() else 0
        with self._holen(f"{QUELLE}{datei}", bereich=schon or None) as r, open(teil, "ab" if schon else "wb") as f:
            if schon and getattr(r, "status", 206) == 200:
                f.seek(0)
                f.truncate()
            while True:
                if not self._darf() or self._halt.is_set():
                    return False
                stueck = r.read(1024 * 1024)
                if not stueck:
                    break
                f.write(stueck)
        h = hashlib.md5(usedforsecurity=False)
        with open(teil, "rb") as f:
            for stueck in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(stueck)
        if h.hexdigest() != md5:
            teil.unlink(missing_ok=True)
            raise OrteError("OSM_MD5", "Prüfsumme stimmt nicht, die Datei wird neu geladen")
        teil.replace(ziel)
        return True


    def _schleife(self) -> None:
        while not self._halt.is_set():
            try:
                self._fest = Path(self._ordner_fn())
                warten = self.schritt()
            except OrteError as exc:
                self.phase, self.meldung = "fehler", exc.detail
                self._log(f"ABGELEHNT openstreetmap: {exc.code}: {exc.detail}")
                warten = 600
            except Exception as exc:
                self.phase, self.meldung = "fehler", type(exc).__name__
                self._log(f"FEHLER openstreetmap: {type(exc).__name__}: {str(exc)[:200]}")
                warten = 600
            finally:
                self._fest = None
            if warten:
                self._schlafen(warten)

    def schritt(self) -> float:
        if umzug.offen(self.ordner):
            self.phase, self.meldung = "zieht_um", ""
        w = umzug.schritt(self.ordner, behalten=self.darf_halten(), schliessen=self._schliessen, oeffnen=self._oeffnen,
                          halt=self._halt.is_set, log=self._log, name="openstreetmap", platte_frei_mb=self._platte_frei_mb)
        if w is not None:
            self.phase, self.meldung = "zieht_um", ""
            return w
        if not self.darf_halten():
            if self.ordner.exists():
                self._log("OK openstreetmap: dieses Gerät bereitet die Orte nicht auf, Orte gelöscht")
                self.loeschen()
            self.phase = "nicht_vorgesehen"
            return 300
        if not self._darf():
            self.phase = "pause"
            return 30
        st = self._stand()
        faellig = [(k, n, d) for k, n, d in self._laender
                   if not st.get(f"fertig_{k}") or self._jetzt() - float(st.get(f"fertig_um_{k}", 0)) > NEU_NACH_TAGE * 86400]
        if not faellig:
            self.phase = "fertig"
            return 3600
        offen = [(k, n, d) for k, n, d in faellig if self._jetzt() - float(st.get(f"fehler_um_{k}", 0)) >= FEHLER_PAUSE_S]
        if not offen:
            self.phase = "fertig" if self._dateien else "pause"
            return 600
        kurz, name, deutsch = offen[0]
        pbf = self.ordner / f"{kurz}.osm.pbf"
        if not pbf.exists():
            frei = int(self._platte_frei_mb(self.ordner if self.ordner.exists() else self.ordner.parent))
            if frei - FREI_RESERVE_MB < 6_000:
                self.phase, self.meldung = "zu_wenig_platz", f"auf dem Laufwerk sind nur {frei // 1000} GB frei"
                return 3600
            self.phase, self.meldung = "laedt", deutsch
            self.ordner.mkdir(parents=True, exist_ok=True)
            try:
                md5, datei = st.get(f"md5_{kurz}"), st.get(f"datei_{kurz}") or f"{name}-latest.osm.pbf"
                if not md5:
                    datei, md5 = self._ausgabe(name)
                self._stand_setzen(**{f"md5_{kurz}": md5, f"datei_{kurz}": datei})
                if not self._laden(datei, pbf, md5):
                    return 30
            except OrteError:
                self._stand_setzen(**{f"md5_{kurz}": "", f"datei_{kurz}": "", f"fehler_um_{kurz}": self._jetzt()})
                raise
            self._log(f"OK openstreetmap: {deutsch} geladen ({pbf.stat().st_size // 1_000_000} MB)")
        self.phase, self.meldung = "liest", deutsch
        bau = self.ordner / f"orte-{kurz}.bau.sqlite"
        beginn = time.monotonic()
        try:
            z = land_einlesen(pbf, bau, darf=lambda: self._darf() and not self._halt.is_set(), warten=lambda s: not self._halt.wait(s))
        except Unterbrochen:
            bau.unlink(missing_ok=True)
            return 30
        except OrteError:
            bau.unlink(missing_ok=True)
            pbf.unlink(missing_ok=True)
            self._stand_setzen(**{f"fehler_um_{kurz}": self._jetzt(), f"md5_{kurz}": "", f"datei_{kurz}": ""})
            raise
        with self._lock:
            alt = self._dateien.pop(kurz, None)
            if alt:
                alt.schliessen()
            ziel = self.ordner / f"orte-{kurz}.sqlite"
            bau.replace(ziel)
            self._dateien[kurz] = Laenderdatei(ziel)
        pbf.unlink(missing_ok=True)
        self._stand_setzen(**{f"fertig_{kurz}": datetime.now(timezone.utc).strftime("%Y%m%d"), f"fertig_um_{kurz}": self._jetzt(), f"md5_{kurz}": "", f"datei_{kurz}": "",
                              f"eintraege_{kurz}": z["eintraege"], f"orte_{kurz}": z["orte"]})
        self._belegt = (0.0, 0)
        self._log(f"OK openstreetmap: {deutsch} bereit, {z['eintraege']} Stellen und {z['orte']} Orte ({time.monotonic() - beginn:.0f} s)")
        return 0


    def suchen(self, frage: str, *, ort_hinweis: str = "") -> list[wissen.Treffer]:
        with self._lock:
            dateien = [self._dateien[k] for k, _, _ in self._laender if k in self._dateien]
        if not dateien:
            return []
        st = self._stand()
        tage = sorted(str(st.get(f"fertig_{k}", "")) for k, _, _ in self._laender if st.get(f"fertig_{k}"))
        stand = f"{tage[0][6:8]}.{tage[0][4:6]}.{tage[0][:4]}" if tage and len(tage[0]) == 8 else ""
        try:
            return suchen_in(dateien, frage, stand=stand, ort_hinweis=ort_hinweis)
        except sqlite3.Error as exc:
            self._log(f"ABGELEHNT openstreetmap suchen: {type(exc).__name__}")
            return []

    def zustand(self) -> dict:
        return {"phase": self.phase, "meldung": self.meldung, "laender": self.laender_fertig(), "belegt_mb": self.belegt_mb(), "text": self.text_de()}

    def text_de(self) -> str:
        fertig = self.laender_fertig()
        st = self._stand()
        n = sum(int(st.get(f"eintraege_{k}", 0)) for k, _, _ in self._laender if st.get(f"fertig_{k}"))
        zahl = f"{n:,}".replace(",", ".")
        bereit = f"{zahl} Stellen aus {', '.join(fertig)}" if fertig else ""
        if self.phase == "zieht_um":
            return "Orte (OpenStreetMap): ziehen auf das gewählte Laufwerk um."
        if self.phase == "laedt":
            return f"Orte (OpenStreetMap): lädt {self.meldung}." + (f" Bereit: {bereit}." if bereit else "")
        if self.phase == "liest":
            return f"Orte (OpenStreetMap): bereitet {self.meldung} auf." + (f" Bereit: {bereit}." if bereit else "")
        if self.phase == "nicht_vorgesehen":
            return ""
        if self.phase == "zu_wenig_platz":
            return f"Orte (OpenStreetMap): {self.meldung}."
        if self.phase == "fehler":
            return f"Orte (OpenStreetMap): gerade geht es nicht ({self.meldung}), nächster Versuch später."
        if self.phase == "pause" and not fertig:
            return "Orte (OpenStreetMap): wartet, bis das Gerät arbeiten darf."
        return f"Orte (OpenStreetMap): {bereit}, fertig aufbereitet." if bereit else ""


__all__ = ["OrteKopie", "land_einlesen", "suchen_in", "frage_art", "Laenderdatei", "KATEGORIEN", "LAENDER", "NENNUNG", "MIN_FREIGABE_MB"]
