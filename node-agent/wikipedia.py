# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import bz2
import dataclasses
import hashlib
import json
import math
import re
import shutil
import sqlite3
import struct
import threading
import time
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

import app_core
import namenpruefung
import scheiben
import sicher_schreiben
import umzug
import wissen

QUELLE = "https://dumps.wikimedia.org/other/cirrus_search_index/"
NAME = "dewiki_content"
DIRNAME = "wikipedia"
DB = "wikipedia.sqlite"
STAND = "stand.json"
MIN_FREIGABE_MB = 100_000
PLATZ_MB = 80_000
FREI_RESERVE_MB = 20_000
NEU_NACH_TAGE = 30
ABSCHNITT = 900
BEGRIFFSKLAERUNG_VORLAGEN = frozenset({"Vorlage:Begriffsklärung", "Template:Begriffsklärung"})
EINLESE_STAND = 4
MAX_ABSCHNITTE = 300
NAMEN_WARTEN_S = 2.0
VEKTOR_ZUERST_JE_ARTIKEL = 3
VEKTOR_BATCH = 8
VEKTOR_FENSTER = 20_000
HASH_SCHRITT = 5_000
HASH_STAPEL = 20_000
_INT8_MAGIE = b"KIq8"
GEMEINSCHAFT_ABSTAND_S = 3600
GEMEINSCHAFT_WARTEN_S = 600
WIKI_STICHPROBE = 3
WIKI_AEHNLICH = 0.98
GEMEINSCHAFT_TEMPO_S = 60
EINLESEN_SCHRITT = 3000
TIMEOUT_S = 60.0
LIZENZ = "CC BY-SA 4.0"
_UA = "KIplatz-Wikipedia/1 (eine Kopie je Monat für die eigene Suche; https://kiplatz.at)"
_TEIL = re.compile(r'href="(' + re.escape(NAME) + r'-(\d{8})-(\d{5})\.json\.bz2)"')


def _teil_muster(name: str) -> re.Pattern:
    return _TEIL if name == NAME else re.compile(r'href="(' + re.escape(name) + r'-(\d{8})-(\d{5})\.json\.bz2)"')


_AUSGABE = re.compile(r'href="(\d{8})/"')


class WikiError(app_core.AppError):
    pass


class Unterbrochen(Exception):
    pass


ANWAERMEN = ("Wie hoch ist der Großglockner?", "Was ist die Hauptstadt von Österreich?", "Wer war Wolfgang Amadeus Mozart?")
ANWAERMEN_EN = ("How high is Mount Everest?", "What is the capital of Austria?", "Who was Wolfgang Amadeus Mozart?")
SUCH_FRIST_S = 5.0
DF_FRIST_S = 0.5
HAEUFIG_ANTEIL = 0.005


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _titel_norm(t: str) -> str:
    return " ".join(str(t or "").replace("_", " ").lower().split())


def _grundformen(wort: str) -> set[str]:
    w = _titel_norm(wort).translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}))
    for endung in ("en", "er", "e", "n", "s"):
        if len(w) - len(endung) >= 3 and w.endswith(endung):
            return {w, w[:-len(endung)]}
    return {w}


def _ortsadjektive(ort: str) -> list[str]:
    out = [ort + "er"]
    if ort.endswith("en") and len(ort) >= 6:
        out += [ort[:-2] + "er", ort[:-2] + "ner"]
    if ort.endswith("e"):
        out.append(ort[:-1] + "er")
    return out


_SACHWORT = re.compile(r"(?i)(?:einwohner\w*|bevölkerung\w*|fläche|höhe|tiefe|länge|größe|gewicht|preis\w*|kosten|anzahl|datum|jahr|jahre|dauer|"
                       r"entfernung|strecke|distanz|alter|kilometer|meter|euro|prozent|temperatur|hauptstadt|vergleich\w*|unterschied\w*|zahl|zahlen|"
                       r"stadt|städte|land|länder|bundesland|bundesländer|gemeinde|bezirk|gründung|geburt|wetter|klima|geschichte|wirtschaft|"
                       r"politik|lage|währung|sprache|religion|welt|tabelle|liste|übersicht|aufzählung|auflistung|rangliste|reihenfolge|tag|tage|"
                       r"woche|monat|stunde|minute|sekunde|uhr|uhrzeit|wort|wörter|satz|text|beispiel|frage|antwort)")


_WARTUNG = re.compile(r"Vorlage:[^\s/]+(?: [^\s/]+){0,4}/Wartung/(?:(?!Vorlage:|Wikipedia:)\S)*(?:\s+(?:fehlt|unpassend))?")
_VORLAGE_WORT = re.compile(r"Vorlage:\S+(?: \S+){0,2}(?= |$)")
_PROJEKT = re.compile(r"Wikipedia:WikiProjekt [^\s/]+(?:/(?:(?!Vorlage:|Wikipedia:)\S)*)+")
_KOORDINATEN = re.compile(r"-?\d{1,3}\.\d+-?\d{1,3}\.\d+Koordinaten: [^A-Za-zÄÖÜäöü]{0,40}?[NS],? [^A-Za-zÄÖÜäöü]{0,40}?[OW](?:; CH1903: [\d /]+)?")
_BILDWUNSCH = re.compile(r"(?:[a-z]{1,2}\d[a-z0-9]{0,3}|BW)")
_LEERE_KLAMMER = re.compile(r"\[\s*(?:auch\s*)?\]")


def ohne_wartung(text: str, titel: str = "", sprache: "Sprache | None" = None) -> str:
    englisch = sprache is not None and sprache.code != "de"
    if englisch:
        t = _LAUTSCHRIFT_EN.sub("", _KOORDINATEN_EN.sub(" ", str(text or "")))
    else:
        t = _KOORDINATEN.sub(" ", _PROJEKT.sub(" ", _WARTUNG.sub(" ", str(text or ""))))
    worte = t.split()
    erstes = (titel or "").split(" ")[0].lower()
    i = 0
    while not englisch and i < len(worte) - 1 and _BILDWUNSCH.fullmatch(worte[i]) and worte[i].lower() != erstes:
        i += 1
    t = " ".join(worte[i:])
    t = _LEERE_KLAMMER.sub("", t)
    t = re.sub(r"\(\s*(?:[,;:]\s*)+", "(", t)
    t = re.sub(r"(?:\s*[,;]\s*)+\)", ")", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([,;)])", r"\1", t)
    t = re.sub(r"([,;:])(?:\s*[,;])+", r"\1", t)
    return " ".join(t.split())


_ANHANG = re.compile(r"abgerufen am|eingesehen am|\bISBN\b|\bISSN\b|\bdoi:|Memento vom|Archiviert vom|\bIn: ", re.I)
ANHANG_DICHT = 4
ANHANG_FENSTER = 2000


def ohne_anhang(text: str, sprache: "Sprache | None" = None) -> str:
    text = text or ""
    stellen = [m.start() for m in (sprache.anhang if sprache else _ANHANG).finditer(text)]
    luecke = max(ANHANG_FENSTER, len(text) // 20)
    if len(stellen) < ANHANG_DICHT or len(text) - stellen[-1] > luecke:
        return text
    erste = len(stellen) - 1
    while erste > 0 and stellen[erste] - stellen[erste - 1] <= luecke:
        erste -= 1
    if len(stellen) - erste < ANHANG_DICHT:
        return text
    ende = max(text.rfind(". ", 0, stellen[erste]), text.rfind(".“ ", 0, stellen[erste]))
    return text[:ende + 1] if ende >= 0 else text


_SATZENDE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9„\"(])")
_MONAT = re.compile(r"(?:Jänner|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jahrhunderts?|Jahrtausends?|Jh)\b")
_ABKUERZUNG = re.compile(r"(?:^|[\s(])(?:[a-zäöü]|bzw|ca|Nr|St|Dr|Prof|Mio|Mrd|Chr|Jh|Abb|vgl|ggf|bspw|inkl|Bd|Hrsg|geb|gest|verh|ehem|evtl|Tsd|Mill|"
                         r"Ing|Mag|Hl|Kap|Abs|Art|Univ|sog|insb|Mt|Ft|Jr|Sr|Mr|Mrs|Gen|Lt|Fr|Hr|röm|kath|evang|jun|sen|engl|franz|ital|lat|griech)\.$")
_ORDNUNGSZAHL = re.compile(r"(?:^|\s)(?:der|die|das|dem|den|des|im|am|zum|zur|vom|beim|ins|seit|bis|ab|um|nach|vor|in|an|auf|für|zwischen|und|oder)"
                           r"\s+\d{1,3}\.$", re.I)


def _kein_satzende(davor: str, danach: str, sprache: "Sprache | None" = None) -> bool:
    if sprache is not None and sprache.code != "de":
        return bool(sprache.abkuerzung.search(davor) or re.search(r"(?:^|[\s(])[A-Z]\.$", davor))
    if re.search(r"(?:^|[\s(–-])\d{1,4}\.$", davor) and _MONAT.match(danach):
        return True
    return bool(_ORDNUNGSZAHL.search(davor) or _ABKUERZUNG.search(davor) or re.search(r"(?:^|[\s(])[A-ZÄÖÜ]\.$", davor))


def saetze(text: str, sprache: "Sprache | None" = None) -> list[str]:
    out: list[str] = []
    for s in _SATZENDE.split(text or ""):
        if out and _kein_satzende(out[-1], s, sprache):
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def stuecke(text: str, zeichen: int = ABSCHNITT) -> list[str]:
    worte = " ".join(str(text or "").split())
    out = []
    while len(worte) > zeichen:
        schnitt = worte.rfind(" ", zeichen // 2, zeichen)
        if schnitt < 0:
            schnitt = zeichen
        out.append(worte[:schnitt].strip())
        worte = worte[schnitt:].strip()
    if worte:
        out.append(worte)
    return out


def abschnitte(text: str, *, zeichen: int = ABSCHNITT, titel: str = "", sprache: "Sprache | None" = None) -> list[str]:
    beleg = sprache.beleg if sprache else _BELEG
    gute = [s for s in saetze(ohne_anhang(ohne_wartung(text, titel, sprache), sprache), sprache) if not beleg.search(s)]
    out, aktuell = [], ""
    for s in gute:
        while len(s) > zeichen:
            if aktuell:
                out.append(aktuell)
                aktuell = ""
            out.append(s[:zeichen])
            s = s[zeichen:]
        if aktuell and len(aktuell) + 1 + len(s) > zeichen:
            out.append(aktuell)
            aktuell = s
        else:
            aktuell = (aktuell + " " + s).strip()
    if aktuell:
        out.append(aktuell)
    return out


_BELEG = re.compile(r"abgerufen am|\bISBN\b|\bdoi:|Archiviert vom Original|Memento vom|Wikipedia:[A-Z]\w*|\bS\. \d+|\bIn: [\w.-]+\.(?:at|de|ch|com|org|net|eu)\b"
                    r"|Archivlink|Vorlage:|\bIABot\b|@1@2", re.I)


def ist_beleg(stueck: str, sprache: "Sprache | None" = None) -> bool:
    n = len((sprache.beleg if sprache else _BELEG).findall(stueck or ""))
    return n >= 3 or (n >= 1 and len(stueck) < 250)


KURZDATEN_MIN_ZEICHEN = 120
KURZDATEN_MIN_ZIFFERN = 10
KURZDATEN_ZEICHEN = 6000
KURZDATEN_LISTE_ZEICHEN = 20_000
_INFOBOX_WORT = re.compile(r"\b(?:Basisdaten|Einwohner|Fläche|Höhe|Koordinaten|Länge)\b")
_JAHRESKLAMMER = re.compile(r"\(\d{4}[–-]\d{4}\)")


def kurzdaten(aux: list[str], *, liste: bool = False, sprache: "Sprache | None" = None) -> list[str]:
    sp = sprache or DE
    wert = []
    gesehen: set[tuple[int, str, str]] = set()
    for a in aux:
        a = " ".join(_VORLAGE_WORT.sub(" ", _WARTUNG.sub(" ", str(a or ""))).split())
        if len(a) < KURZDATEN_MIN_ZEICHEN or sum(c.isdigit() for c in a) < KURZDATEN_MIN_ZIFFERN or ist_beleg(a, sp):
            continue
        if sp is not DE and re.match(r"(?:v t e|vte)\b", a):
            continue
        if len(_JAHRESKLAMMER.findall(a)) >= 3 and not sp.infobox_wort.search(a):
            continue
        schluessel = (len(a), a[:120], a[-80:])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        wert.append((0 if sp.infobox_wort.search(a[:200]) and not liste else 1, len(wert), a))
    wert.sort()
    out: list[str] = []
    rest = KURZDATEN_LISTE_ZEICHEN if liste else KURZDATEN_ZEICHEN
    for _, _, a in wert:
        if rest <= 0:
            break
        for stueck in stuecke(a[:rest]):
            out.append(sp.kurz + stueck)
        rest -= len(a)
    return out


@dataclasses.dataclass(frozen=True)
class Sprache:
    code: str
    name: str
    dirname: str
    adresse: str
    titel: str
    anhang: re.Pattern
    beleg: re.Pattern
    abkuerzung: re.Pattern
    infobox_wort: re.Pattern
    begriffsklaerung: frozenset
    kurz: str
    liste: str
    min_freigabe_mb: int
    platz_mb: int
    einlese_stand: int


_ANHANG_EN = re.compile(r"\bRetrieved\b|Archived from the original|Archived copy|\bISBN\b|\bISSN\b|\bdoi:|\{\{cite|CS1 maint|at Wikimedia Commons|"
                        r"from Wikivoyage|University Press\b|\bpp?\.\s?\d|\((?:in [A-Z][a-z]+|PDF)\)|\(Accessed \d|\bThe World Factbook\b|"
                        r"\"\.\s+[A-Z][^\"]{1,50}?\.(?=\s|$)")
_BELEG_EN = re.compile(r"\bRetrieved\b|Archived from the original|Archived copy|\bISBN\b|\bdoi:|\{\{cite|CS1 maint|Wikimedia Commons|\bIABot\b", re.I)
_ABKUERZUNG_EN = re.compile(r"(?:^|[\s(])(?:[a-z]|e\.g|i\.e|etc|vs|approx|ca|No|Nos|St|Mt|Dr|Mr|Mrs|Ms|Jr|Sr|Prof|Gen|Lt|Col|Capt|Inc|Ltd|Corp|Co|"
                            r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|U\.S|U\.K)\.$")
_INFOBOX_WORT_EN = re.compile(r"\b(?:Population|Area|Elevation|Coordinates|Length|Capital|Height)\b")
_KOORDINATEN_EN = re.compile(r"^[\s﻿ ]*\d{1,3}°[\d°′″.\s﻿ ]*[NS][\s﻿ ]+\d{1,3}°[\d°′″.\s﻿ ]*[EW]"
                             r"[\s﻿ ]*/[\s﻿ ]*-?[\d.]+°[NS][\s﻿ ]+-?[\d.]+°[EW][\s﻿ ]*/[\s﻿ ]*"
                             r"-?[\d.]+;[\s﻿ ]*-?[\d.]+")
_LAUTSCHRIFT_EN = re.compile(r"[/\[][^/\[\]\s]{0,20}[ˈˌːəɐɪʊɔæɒʃʒθðŋɛʁøœɑɹʌɜɚɝɡ][^/\[\]]{0,40}[/\]]|\(\s*listen\s*\)")

DE = Sprache("de", "dewiki_content", "wikipedia", "https://de.wikipedia.org/wiki/", "Wikipedia", _ANHANG, _BELEG, _ABKUERZUNG, _INFOBOX_WORT,
             BEGRIFFSKLAERUNG_VORLAGEN, "Kurzdaten: ", "Liste ", 100_000, 80_000, EINLESE_STAND)
SIMPLE = Sprache("simple", "simplewiki_content", "wikipedia-simple", "https://simple.wikipedia.org/wiki/", "Simple English Wikipedia", _ANHANG_EN,
                 _BELEG_EN, _ABKUERZUNG_EN, _INFOBOX_WORT_EN,
                 frozenset({"Template:Disambiguation", "Template:Disambig", "Template:Dab", "Template:Geodis", "Template:Hndis",
                            "Template:Disambiguation page"}), "Key facts: ", "List of ", 5_000, 8_000, 1)


_STOPP_EN = frozenset("""the and for with that this from are was were has have had which who whom whose what where when why how its his her
their they them not but also been into than then there these those about more most such only other some can will would could should
may might must did does doing done any all each both very one two after before over under between during while because since until
being out off our your you she him theirs ours yours just like than""".split())
_WORT_EN = re.compile(r"[a-z0-9]+")


def woerter_en(text: str) -> list[str]:
    import unicodedata
    roh = unicodedata.normalize("NFKD", str(text or "").lower().replace("’", "'"))
    roh = "".join(c for c in roh if not unicodedata.combining(c)).replace("'s ", " ")
    out = []
    for w in _WORT_EN.findall(roh):
        if len(w) < 3 or w in _STOPP_EN:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes", "zes")):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        out.append(w)
    return out


def dokument_lesen(d: dict, sprache: Sprache | None = None) -> dict | None:
    sp = sprache or DE
    if str(d.get("namespace", "")) != "0" or d.get("page_type", "primary") != "primary":
        return None
    text = str(d.get("text") or "").strip()
    titel = str(d.get("title") or "").strip()
    if not text or not titel:
        return None
    if any(str(v).strip() in sp.begriffsklaerung for v in (d.get("template") or [])):
        return None
    if sp is not DE and any("disambiguation pages" in str(k).lower() for k in (d.get("category") or [])):
        return None
    aux_alle = [str(a or "").strip() for a in (d.get("auxiliary_text") or [])]
    teile = [t for t in abschnitte(text, titel=titel, sprache=sp) if not ist_beleg(t, sp)][:MAX_ABSCHNITTE]
    if not teile:
        return None
    kurz = kurzdaten(aux_alle, liste=titel.startswith(sp.liste), sprache=sp)
    if kurz:
        teile[1:1] = kurz
    else:
        aux = " ".join(aux_alle[:3])[:1500].strip()
        if aux:
            teile.insert(min(1, len(teile)), sp.kurz + aux)
    umleitungen = [str(r.get("title")) for r in (d.get("redirect") or []) if isinstance(r, dict) and str(r.get("namespace", "0")) == "0" and r.get("title")]
    try:
        beliebt = float(d.get("popularity_score") or 0.0)
    except (TypeError, ValueError):
        beliebt = 0.0
    try:
        seite = int(d.get("page_id"))
    except (TypeError, ValueError):
        return None
    return {"id": seite, "titel": titel, "teile": teile, "umleitungen": umleitungen[:50], "beliebt": beliebt,
            "geaendert": str(d.get("timestamp") or "")[:10]}


def _v_packen(v: list[float]) -> bytes:
    m = max((abs(x) for x in v), default=0.0)
    mass = (m / 127.0) if m else 1.0
    q = [max(-127, min(127, int(round(x / mass)))) for x in v]
    return _INT8_MAGIE + struct.pack("<f", mass) + struct.pack(f"<{len(q)}b", *q)


def _v_lesen(b: bytes) -> list[float]:
    if b[:4] == _INT8_MAGIE:
        mass = struct.unpack("<f", b[4:8])[0]
        return [x * mass for x in struct.unpack(f"<{len(b) - 8}b", b[8:])]
    return list(struct.unpack(f"<{len(b) // 2}e", b))


def _hash(titel: str, text: str) -> bytes:
    return hashlib.blake2b(f"{titel}: {text}".encode("utf-8"), digest_size=16).digest()


def _kosinus(a: list[float], b: list[float]) -> float:
    try:
        return math.sumprod(a, b)
    except AttributeError:
        return sum(x * y for x, y in zip(a, b))


class Datenbank(namenpruefung.Namenspruefung):

    def __init__(self, pfad: Path, *, schreiben: bool = False, sprache: Sprache | None = None) -> None:
        self.pfad = Path(pfad)
        self.sprache = sprache or DE
        self._woerter = wissen.woerter if self.sprache is DE else woerter_en
        self._lock = threading.RLock()
        self._c = sqlite3.connect(str(self.pfad), check_same_thread=False, isolation_level=None, timeout=30)
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA synchronous=NORMAL")
        if schreiben:
            self._c.executescript(
                "CREATE TABLE IF NOT EXISTS artikel (id INTEGER PRIMARY KEY, titel TEXT NOT NULL, beliebt REAL NOT NULL, geaendert TEXT NOT NULL, teil INTEGER NOT NULL);"
                "CREATE TABLE IF NOT EXISTS abschnitt (id INTEGER PRIMARY KEY, artikel INTEGER NOT NULL, nr INTEGER NOT NULL, text BLOB NOT NULL);"
                "CREATE TABLE IF NOT EXISTS titel (norm TEXT PRIMARY KEY, artikel INTEGER NOT NULL) WITHOUT ROWID;"
                "CREATE TABLE IF NOT EXISTS vektor (id INTEGER PRIMARY KEY, v BLOB NOT NULL);"
                "CREATE TABLE IF NOT EXISTS abschnitt_hash (id INTEGER PRIMARY KEY, h BLOB NOT NULL);"
                "CREATE TABLE IF NOT EXISTS vorrat (pos INTEGER PRIMARY KEY, abschnitt INTEGER NOT NULL);"
                "CREATE TABLE IF NOT EXISTS teile (nr INTEGER PRIMARY KEY, artikel INTEGER NOT NULL, abschnitte INTEGER NOT NULL);"
                "CREATE VIRTUAL TABLE IF NOT EXISTS suche USING fts5(titel, woerter, content='', tokenize='unicode61 remove_diacritics 0');"
                "CREATE INDEX IF NOT EXISTS abschnitt_artikel ON abschnitt(artikel, nr);"
                "CREATE INDEX IF NOT EXISTS artikel_teil ON artikel(teil);")
        self._n: int | None = None
        self.zeiten: dict = {}
        self.zeiten_letzte: dict = {}
        self._df_merk: dict[str, int] = {}
        self._wortzahl_da = False
        self._ende: float | None = None
        self._teil_ende = math.inf
        self._abbrechen = None
        self._c.set_progress_handler(self._halt, 20_000)
        self._leser: Datenbank | None = None
        self._leser_anlegen = threading.Lock()
        self._such_frei = threading.Lock()

    def leser(self) -> "Datenbank":
        if self._leser is None:
            with self._leser_anlegen:
                if self._leser is None:
                    self._leser = Datenbank(self.pfad, sprache=self.sprache)
        return self._leser

    def schliessen(self) -> None:
        if self._leser is not None:
            self._leser._abbrechen = lambda: True
            try:
                self._leser.schliessen()
            except Exception:
                pass
        with self._lock:
            try:
                self._c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            self._c.close()


    def teil_fertig(self, nr: int) -> bool:
        with self._lock:
            return self._c.execute("SELECT 1 FROM teile WHERE nr = ?", (nr,)).fetchone() is not None

    def teil_aufnehmen(self, nr: int, artikel: list[dict]) -> tuple[int, int]:
        n_a = n_s = 0
        with self._lock:
            self._c.execute("BEGIN")
            try:
                for a in artikel:
                    if self._c.execute("SELECT 1 FROM artikel WHERE id = ?", (a["id"],)).fetchone():
                        continue
                    self._c.execute("INSERT INTO artikel VALUES (?, ?, ?, ?, ?)", (a["id"], a["titel"], a["beliebt"], a["geaendert"], nr))
                    for t in [a["titel"]] + a["umleitungen"]:
                        self._c.execute("INSERT OR IGNORE INTO titel VALUES (?, ?)", (_titel_norm(t), a["id"]))
                    tw = " ".join(self._woerter(a["titel"]))
                    for i, t in enumerate(a["teile"]):
                        cur = self._c.execute("INSERT INTO abschnitt (artikel, nr, text) VALUES (?, ?, ?)", (a["id"], i, zlib.compress(t.encode("utf-8"), 6)))
                        self._c.execute("INSERT INTO abschnitt_hash VALUES (?, ?)", (cur.lastrowid, _hash(a["titel"], t)))
                        self._c.execute("INSERT INTO suche (rowid, titel, woerter) VALUES (?, ?, ?)", (cur.lastrowid, tw, " ".join(self._woerter(t))))
                        n_s += 1
                    n_a += 1
                self._c.execute("COMMIT")
            except BaseException:
                self._c.execute("ROLLBACK")
                raise
        self._n = None
        return n_a, n_s

    def teil_abschliessen(self, nr: int) -> None:
        with self._lock:
            a = self._c.execute("SELECT count(*) FROM artikel WHERE teil = ?", (nr,)).fetchone()[0]
            s = self._c.execute("SELECT count(*) FROM abschnitt s JOIN artikel a ON a.id = s.artikel WHERE a.teil = ?", (nr,)).fetchone()[0]
            self._c.execute("INSERT OR REPLACE INTO teile VALUES (?, ?, ?)", (nr, a, s))

    def teil_verwerfen(self, nr: int) -> None:
        with self._lock:
            ids = [r[0] for r in self._c.execute("SELECT s.id FROM abschnitt s JOIN artikel a ON a.id = s.artikel WHERE a.teil = ?", (nr,))]
            if not ids:
                return
            self._c.execute("BEGIN")
            for sid in ids:
                r = self._c.execute("SELECT a.titel, s.text FROM abschnitt s JOIN artikel a ON a.id = s.artikel WHERE s.id = ?", (sid,)).fetchone()
                self._c.execute("INSERT INTO suche (suche, rowid, titel, woerter) VALUES ('delete', ?, ?, ?)",
                                (sid, " ".join(self._woerter(r[0])), " ".join(self._woerter(zlib.decompress(r[1]).decode("utf-8")))))
            self._c.execute("DELETE FROM abschnitt_hash WHERE id IN (SELECT s.id FROM abschnitt s JOIN artikel a ON a.id = s.artikel WHERE a.teil = ?)", (nr,))
            self._c.execute("DELETE FROM abschnitt WHERE artikel IN (SELECT id FROM artikel WHERE teil = ?)", (nr,))
            self._c.execute("DELETE FROM titel WHERE artikel IN (SELECT id FROM artikel WHERE teil = ?)", (nr,))
            self._c.execute("DELETE FROM artikel WHERE teil = ?", (nr,))
            self._c.execute("COMMIT")

    def vorrat_anlegen(self) -> int:
        with self._lock:
            self._c.execute("DELETE FROM vorrat")
            self._c.execute(f"INSERT INTO vorrat (abschnitt) SELECT s.id FROM abschnitt s JOIN artikel a ON a.id = s.artikel "
                            f"ORDER BY (s.nr >= {VEKTOR_ZUERST_JE_ARTIKEL}), a.beliebt DESC, s.nr")
            self._c.execute("INSERT INTO suche (suche) VALUES ('optimize')")
            return int(self._c.execute("SELECT count(*) FROM vorrat").fetchone()[0])


    def vektor_offen(self, ab: int, n: int, fenster: int | None = None) -> list[tuple[int, int, str, str]]:
        with self._lock:
            bis = ab + int(fenster) if fenster else None
            rows = self._c.execute("SELECT v.pos, s.id, a.titel, s.text FROM vorrat v JOIN abschnitt s ON s.id = v.abschnitt JOIN artikel a ON a.id = s.artikel "
                                   "LEFT JOIN vektor k ON k.id = s.id WHERE v.pos > ? AND (? IS NULL OR v.pos <= ?) AND k.id IS NULL ORDER BY v.pos LIMIT ?",
                                   (ab, bis, bis, n)).fetchall()
        return [(p, sid, t, zlib.decompress(b).decode("utf-8")) for p, sid, t, b in rows]


    def hashes_vollstaendig(self) -> bool:
        with self._lock:
            self._c.execute("CREATE TABLE IF NOT EXISTS abschnitt_hash (id INTEGER PRIMARY KEY, h BLOB NOT NULL)")
            a = self._c.execute("SELECT coalesce(max(id), 0) FROM abschnitt").fetchone()[0]
            h = self._c.execute("SELECT coalesce(max(id), 0) FROM abschnitt_hash").fetchone()[0]
            return int(h) >= int(a)

    def hashes_sicherstellen(self, hoechstens: int | None = None) -> int:
        n = 0
        with self._lock:
            self._c.execute("CREATE TABLE IF NOT EXISTS abschnitt_hash (id INTEGER PRIMARY KEY, h BLOB NOT NULL)")
        while True:
            grenze = hoechstens - n if hoechstens is not None else HASH_SCHRITT
            if grenze <= 0:
                break
            with self._lock:
                rows = self._c.execute("SELECT s.id, a.titel, s.text FROM abschnitt s JOIN artikel a ON a.id = s.artikel "
                                       "WHERE s.id > (SELECT coalesce(max(id), 0) FROM abschnitt_hash) ORDER BY s.id LIMIT ?", (min(grenze, HASH_SCHRITT),)).fetchall()
                if not rows:
                    break
                self._c.execute("BEGIN")
                self._c.executemany("INSERT OR REPLACE INTO abschnitt_hash VALUES (?, ?)",
                                    [(sid, _hash(t, zlib.decompress(b).decode("utf-8"))) for sid, t, b in rows])
                self._c.execute("COMMIT")
            n += len(rows)
        fertig = self.hashes_vollstaendig()
        if fertig:
            self.hash_index_anlegen()
        return n

    def hash_index_da(self) -> bool:
        with self._lock:
            return self._c.execute("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'abschnitt_hash_h'").fetchone() is not None

    def hash_index_anlegen(self) -> None:
        c = sqlite3.connect(str(self.pfad), timeout=30, isolation_level=None)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS abschnitt_hash_h ON abschnitt_hash(h)")
        finally:
            c.close()

    def vektoren_uebernehmen(self, alt_pfad: Path) -> int:
        with self._lock:
            self._c.execute("ATTACH DATABASE ? AS alt", (str(alt_pfad),))
            try:
                self._c.execute("BEGIN")
                self._c.execute("INSERT OR IGNORE INTO main.vektor (id, v) SELECT n.id, o.v FROM main.abschnitt_hash n "
                                "JOIN alt.abschnitt_hash oh ON oh.h = n.h JOIN alt.vektor o ON o.id = oh.id")
                n = int(self._c.execute("SELECT changes()").fetchone()[0])
                self._c.execute("COMMIT")
            except BaseException:
                self._c.execute("ROLLBACK")
                raise
            finally:
                self._c.execute("DETACH DATABASE alt")
        return n

    def vektoren_schreiben(self, paare: list[tuple[int, list[float]]]) -> None:
        with self._lock:
            self._c.execute("BEGIN")
            self._c.executemany("INSERT OR REPLACE INTO vektor VALUES (?, ?)", [(sid, _v_packen(v)) for sid, v in paare])
            self._c.execute("COMMIT")


    def scheiben_paare(self, nr: int, je: int) -> list[tuple[bytes, bytes]]:
        with self._lock:
            return [(bytes(h), bytes(v)) for h, v in self._c.execute(
                "SELECT h.h, v.v FROM abschnitt_hash h JOIN vektor v ON v.id = h.id ORDER BY h.h, h.id LIMIT ? OFFSET ?", (int(je), int(nr) * int(je)))]

    def gemeinsame_hashes(self, hashes: list[bytes], n: int) -> list[bytes]:
        with self._lock:
            self._c.execute("CREATE TEMP TABLE IF NOT EXISTS wiki_probe (h BLOB NOT NULL)")
            self._c.execute("DELETE FROM wiki_probe")
            self._c.executemany("INSERT INTO wiki_probe VALUES (?)", [(bytes(h),) for h in hashes])
            r = self._c.execute("SELECT p.h FROM wiki_probe p WHERE EXISTS (SELECT 1 FROM abschnitt_hash x WHERE x.h = p.h) "
                                "ORDER BY random() LIMIT ?", (int(n),)).fetchall()
            self._c.execute("DELETE FROM wiki_probe")
        return [bytes(h) for (h,) in r]

    def texte_zu_hashes(self, hashes: list[bytes], n: int) -> list[tuple[bytes, str, str]]:
        out: list[tuple[bytes, str, str]] = []
        with self._lock:
            for h in hashes:
                r = self._c.execute("SELECT a.titel, s.text FROM abschnitt_hash x JOIN abschnitt s ON s.id = x.id JOIN artikel a ON a.id = s.artikel "
                                    "WHERE x.h = ? LIMIT 1", (bytes(h),)).fetchone()
                if r:
                    out.append((bytes(h), r[0], zlib.decompress(r[1]).decode("utf-8")))
                    if len(out) >= n:
                        break
        return out

    def vektoren_einlesen(self, paare: list[tuple[bytes, bytes]]) -> int:
        with self._lock:
            self._c.execute("CREATE TEMP TABLE IF NOT EXISTS wiki_neu (h BLOB NOT NULL, v BLOB NOT NULL)")
            self._c.execute("DELETE FROM wiki_neu")
            self._c.execute("BEGIN")
            try:
                self._c.executemany("INSERT INTO wiki_neu VALUES (?, ?)", paare)
                self._c.execute("INSERT OR IGNORE INTO vektor (id, v) SELECT a.id, n.v FROM wiki_neu n JOIN abschnitt_hash a ON a.h = n.h")
                n = int(self._c.execute("SELECT changes()").fetchone()[0])
                self._c.execute("DELETE FROM wiki_neu")
                self._c.execute("COMMIT")
            except BaseException:
                self._c.execute("ROLLBACK")
                raise
            return n


    def zahlen(self, vektor_pos: int | None = None) -> dict:
        with self._lock:
            vorrat = int(self._c.execute("SELECT coalesce(max(pos), 0) FROM vorrat").fetchone()[0])
            return {"artikel": int(self._c.execute("SELECT coalesce(sum(artikel), 0) FROM teile").fetchone()[0]),
                    "abschnitte": int(self._c.execute("SELECT coalesce(sum(abschnitte), 0) FROM teile").fetchone()[0]),
                    "vektoren": min(int(vektor_pos), vorrat) if vektor_pos is not None
                    else int(self._c.execute("SELECT count(*) FROM vektor").fetchone()[0]),
                    "vorrat": vorrat}

    def _anzahl(self) -> int:
        if self._n is None:
            with self._lock:
                self._n = int(self._c.execute("SELECT coalesce(sum(abschnitte), 0) FROM teile").fetchone()[0]) or 1
        return self._n

    def hat_wortzahl(self) -> bool:
        if not self._wortzahl_da:
            with self._lock:
                self._wortzahl_da = self._c.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'wortzahl'").fetchone() is not None
        return self._wortzahl_da

    def wortzahl_anlegen(self) -> int:
        with self._lock:
            self._c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.wortschatz USING fts5vocab(main, suche, 'row')")
            self._c.execute("DROP TABLE IF EXISTS wortzahl_neu")
            self._c.execute("CREATE TABLE wortzahl_neu (term TEXT PRIMARY KEY, doc INTEGER NOT NULL) WITHOUT ROWID")
            self._c.execute("BEGIN")
            self._c.execute("INSERT INTO wortzahl_neu SELECT term, doc FROM temp.wortschatz")
            self._c.execute("ALTER TABLE wortzahl_neu RENAME TO wortzahl")
            self._c.execute("COMMIT")
            n = int(self._c.execute("SELECT count(*) FROM wortzahl").fetchone()[0])
        self._wortzahl_da = True
        return n

    def _df(self, wort: str) -> int:
        if wort in self._df_merk:
            return self._df_merk[wort]
        if self.hat_wortzahl():
            with self._lock:
                r = self._c.execute("SELECT doc FROM wortzahl WHERE term = ?", (wort,)).fetchone()
            return int(r[0]) if r else 0
        with self._lock:
            alt, self._teil_ende = self._teil_ende, time.monotonic() + DF_FRIST_S
            try:
                self._c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.wortschatz USING fts5vocab(main, suche, 'row')")
                r = self._c.execute("SELECT doc FROM temp.wortschatz WHERE term = ?", (wort,)).fetchone()
                d = int(r[0]) if r else 0
            except sqlite3.OperationalError as exc:
                if "interrupt" not in str(exc).lower():
                    return 0
                if self._vorbei():
                    raise
                d = self._anzahl()
            except sqlite3.Error:
                return 0
            finally:
                self._teil_ende = alt
        if len(self._df_merk) < 50_000:
            self._df_merk[wort] = d
        return d

    def einleitung(self, aid: int) -> tuple[str, str] | None:
        with self._lock:
            r = self._c.execute("SELECT a.titel, s.text FROM abschnitt s JOIN artikel a ON a.id = s.artikel WHERE s.artikel = ? AND s.nr = 0", (int(aid),)).fetchone()
        return (r[0], zlib.decompress(r[1]).decode("utf-8")) if r else None

    def varianten(self, titel: str) -> list[tuple[int, str]]:
        n = _titel_norm(titel)
        with self._lock:
            rows = self._c.execute("SELECT t.artikel, a.titel FROM titel t JOIN artikel a ON a.id = t.artikel WHERE t.norm >= ? AND t.norm < ? LIMIT 40",
                                   (n + " (", n + " )")).fetchall()
        gesehen: set[int] = set()
        return [(int(r[0]), str(r[1])) for r in rows if not (int(r[0]) in gesehen or gesehen.add(int(r[0])))]

    def artikel_zu(self, titel: str) -> int | None:
        with self._lock:
            r = self._c.execute("SELECT artikel FROM titel WHERE norm = ?", (_titel_norm(titel),)).fetchone()
        return int(r[0]) if r else None

    def titel_artikel(self, frage: str) -> list[int]:
        worte = re.findall(r"[\wäöüÄÖÜß.-]+", frage or "")
        treffer: list[tuple[int, int]] = []
        gattung: set[int] = set()
        with self._lock:
            for laenge in (4, 3, 2, 1):
                for i in range(0, max(0, len(worte) - laenge + 1)):
                    stueck = worte[i:i + laenge]
                    if laenge == 1 and (len(stueck[0]) < 3 or (len(stueck[0]) == 3 and i == 0) or not stueck[0][:1].isupper()
                                        or stueck[0].lower() in wissen._STOPP):
                        continue
                    norm = _titel_norm(" ".join(stueck).strip(".-"))
                    r = self._c.execute("SELECT t.artikel, a.titel FROM titel t JOIN artikel a ON a.id = t.artikel WHERE t.norm = ?", (norm,)).fetchone()
                    if r and r[0] not in [t for t, _ in treffer]:
                        treffer.append((r[0], laenge))
                        wort = stueck[0].strip(".-")
                        if laenge == 1 and (_SACHWORT.fullmatch(wort) or _SACHWORT.fullmatch(r[1])
                                            or (norm != _titel_norm(r[1]) and _grundformen(wort) & _grundformen(r[1]))):
                            gattung.add(r[0])
            listen = self._listen_artikel(worte)
            gross = [(i, w.strip(".-")) for i, w in enumerate(worte) if w[:1].isupper() and len(w.strip(".-")) >= 3 and w.lower() not in wissen._STOPP]
            for i, sache in gross:
                for j, ort in gross:
                    if j <= i:
                        continue
                    for adj in _ortsadjektive(ort):
                        r = self._c.execute("SELECT artikel FROM titel WHERE norm = ?", (_titel_norm(f"{adj} {sache}"),)).fetchone()
                        if r and r[0] not in [t for t, _ in treffer]:
                            allgemein = self._c.execute("SELECT artikel FROM titel WHERE norm = ?", (_titel_norm(sache),)).fetchone()
                            treffer = [(r[0], 9)] + [(t, n) for t, n in treffer if not (allgemein and t == allgemein[0])]
                            break
        namen = [t for t, _ in treffer if t not in gattung and t not in listen]
        return (listen + namen if listen or namen else [t for t, _ in treffer])[:3]

    def _listen_artikel(self, worte: list[str]) -> list[int]:
        stamm = set(self._woerter(" ".join(worte)))
        for s in list(stamm):
            stamm.add(s + "land")
            if s.endswith("isch") and len(s) >= 7:
                stamm |= {s[:-4], s[:-4] + "land"}
        if stamm & {"welt", "erde"}:
            stamm |= {"welt", "erde"}
        namen = {s for w in worte[1:] if w[:1].isupper() and not _SACHWORT.fullmatch(w.strip(".-")) for s in self._woerter(w)}

        def gleich(a: str, b: str) -> bool:
            return a == b or (min(len(a), len(b)) >= 5 and abs(len(a) - len(b)) <= 2 and (a.startswith(b) or b.startswith(a)))

        def gedeckt(t: str) -> bool:
            return any(gleich(t, q) for q in stamm)

        beste: tuple[float, int, int] | None = None
        gesehen: set[str] = set()
        for i, w in enumerate(worte):
            w = w.strip(".-").lower()
            if len(w) < 4 or w in wissen._STOPP:
                continue
            for anfang in (f"liste der {w}", f"liste von {w}"):
                for norm, aid in self._c.execute("SELECT norm, artikel FROM titel WHERE norm >= ? AND norm < ? LIMIT 3000", (anfang, anfang + "~")):
                    if norm in gesehen:
                        continue
                    gesehen.add(norm)
                    t = set(self._woerter(norm)) - {"list", "liste"}
                    if len(t) < 2 or not all(gedeckt(x) for x in t):
                        continue
                    fehlt = sum(1 for n in namen if not any(gleich(n, x) for x in t))
                    wert = (len(t) - 0.5 * fehlt, -len(norm), int(aid))
                    if beste is None or wert > beste:
                        beste = wert
        return [beste[2]] if beste is not None and beste[0] >= 2 else []

    def _subjekt(self, frage: str, titel_ids: list[int]) -> tuple[int | None, str]:
        if not titel_ids:
            return None, ""
        titel = []
        with self._lock:
            for aid in titel_ids:
                r = self._c.execute("SELECT titel FROM artikel WHERE id = ?", (aid,)).fetchone()
                t = str(r[0]) if r else ""
                if not _SACHWORT.fullmatch(t.strip()):
                    titel.append((aid, t))
        if not titel:
            return None, ""
        if len(titel) == 1:
            return titel[0]
        for aid, t in titel:
            name = re.escape(re.sub(r"\s*\([^)]*\)$", "", t).strip())
            if name and not re.search(rf"(?i)\b(?:in|im|nach|aus|von|vom|bei|beim|an|am|auf|für|zu|zum|zur|über|unter)\s+(?:der|die|das|dem|den)?\s*{name}\b", frage or ""):
                return aid, t
        return titel[0]

    def _subjekte(self, frage: str, titel_ids: list[int]) -> tuple[list[int], str]:
        aid, titel = self._subjekt(frage, titel_ids)
        name = re.sub(r"\s*\([^)]*\)$", "", titel).strip() if titel else ""
        if not name:
            for i, w in enumerate(re.findall(r"[\wäöüÄÖÜß-]+", frage or "")):
                if i and len(w) >= 3 and w[:1].isupper() and w.lower() not in wissen._STOPP and not _SACHWORT.fullmatch(w):
                    name = w
                    break
        if not name:
            return [], ""
        n = _titel_norm(name)
        with self._lock:
            varianten = [r[0] for r in self._c.execute("SELECT artikel FROM titel WHERE norm >= ? AND norm < ? LIMIT 6", (n + " (", n + " )"))]
        ids = ([aid] if aid is not None else []) + varianten
        return list(dict.fromkeys(ids))[:4], name

    def _halt(self) -> int:
        t = time.monotonic()
        if t > self._teil_ende or (self._ende is not None and t > self._ende):
            return 1
        a = self._abbrechen
        return 1 if a is not None and a() else 0

    def _vorbei(self) -> bool:
        a = self._abbrechen
        return (self._ende is not None and time.monotonic() > self._ende) or (a is not None and bool(a()))

    def suchen(self, frage: str, *, vektor: list[float] | None = None, n: int = 3, frist_s: float = SUCH_FRIST_S,
               abbrechen=None) -> list[tuple[float, int, str, int, str]]:
        if not self._such_frei.acquire(blocking=False):
            raise Unterbrochen("eine frühere Suche läuft noch")
        ende = time.monotonic() + frist_s
        ergebnis: dict = {}

        def lauf() -> None:
            try:
                leser = self.leser()
                ergebnis["ok"] = leser._suchen_begrenzt(frage, vektor, n, ende, abbrechen)
            except BaseException as exc:
                ergebnis["fehler"] = exc
            finally:
                self.zeiten_letzte = dict(getattr(self._leser, "zeiten", {}) or {})
                self._such_frei.release()
        t = threading.Thread(target=lauf, name="wikipedia-suche", daemon=True)
        t.start()
        while t.is_alive():
            if abbrechen is not None and abbrechen():
                raise Unterbrochen("gestoppt")
            if time.monotonic() > ende:
                raise Unterbrochen(f"länger als {frist_s:g} s")
            t.join(0.05)
        if "fehler" in ergebnis:
            raise ergebnis["fehler"]
        return ergebnis["ok"]

    def _suchen_begrenzt(self, frage: str, vektor: list[float] | None, n: int, ende: float, abbrechen) -> list[tuple[float, int, str, int, str]]:
        with self._lock:
            self._ende, self._abbrechen = ende, abbrechen
            try:
                return self._suchen(frage, vektor, n)
            except sqlite3.OperationalError as exc:
                if "interrupt" in str(exc).lower():
                    raise Unterbrochen("gestoppt" if abbrechen is not None and abbrechen() else "Zeit abgelaufen") from None
                raise
            finally:
                self._ende, self._abbrechen = None, None

    def _suchen(self, frage: str, vektor: list[float] | None, n: int) -> list[tuple[float, int, str, int, str]]:
        z = self.zeiten = {}
        t0 = time.monotonic()
        fw = list(dict.fromkeys(self._woerter(frage)))
        if not fw:
            return []
        gesamt = self._anzahl()
        df = {w: self._df(w) for w in fw}
        z["zaehlen"] = time.monotonic() - t0
        if self._vorbei():
            raise sqlite3.OperationalError("interrupted")
        selten = sorted((w for w in fw if df[w] > 0), key=lambda w: df[w])
        worte = [w for w in selten if df[w] < gesamt * HAEUFIG_ANTEIL][:6] or [w for w in selten if df[w] < gesamt * 0.03][:2]
        kandidaten: dict[int, float] = {}
        if worte:
            abfrage = " OR ".join(f'"{w}"' for w in worte if w.replace("_", "").isalnum())
            with self._lock:
                rows = self._c.execute("SELECT rowid, bm25(suche, 3.0, 1.0) FROM suche WHERE suche MATCH ? ORDER BY rank LIMIT 120", (abfrage,)).fetchall()
            beste = max((-p for _, p in rows), default=1.0) or 1.0
            kandidaten = {sid: max(0.0, -p) / beste for sid, p in rows}
        z["woerter"] = time.monotonic() - t0 - z["zaehlen"]
        t1 = time.monotonic()
        titel_ids = self.titel_artikel(frage)
        z["titel"] = time.monotonic() - t1
        t1 = time.monotonic()
        bonus: dict[int, float] = {}
        mass = wissen.mass_punkte(frage)
        with self._lock:
            subjekte, subjekt_name = (self._subjekte(frage, titel_ids) if mass is not None else ([], ""))
            mass_subjekt = wissen.mass_punkte(frage, pflicht=subjekt_name) if subjekte else None
            for rang, aid in enumerate(titel_ids):
                for sid, nr in self._c.execute("SELECT id, nr FROM abschnitt WHERE artikel = ? AND nr < 3", (aid,)):
                    bonus[sid] = max(bonus.get(sid, 0.0), (0.9 if nr == 0 else 0.6) - 0.15 * rang)
                    kandidaten.setdefault(sid, 0.0)
            for subjekt in subjekte:
                for (sid,) in self._c.execute("SELECT id FROM abschnitt WHERE artikel = ? LIMIT 400", (subjekt,)):
                    kandidaten.setdefault(sid, 0.0)
            if not kandidaten:
                return []
            ids = list(kandidaten)
            rows = []
            for i in range(0, len(ids), 500):
                teil = ids[i:i + 500]
                rows += self._c.execute(f"SELECT s.id, s.artikel, s.nr, s.text, a.titel, a.beliebt, v.v FROM abschnitt s JOIN artikel a ON a.id = s.artikel "
                                        f"LEFT JOIN vektor v ON v.id = s.id WHERE s.id IN ({','.join('?' * len(teil))})", teil).fetchall()
        fs = set(fw)
        wertung = []
        for sid, aid, nr, blob, titel, beliebt, vb in rows:
            text = zlib.decompress(blob).decode("utf-8")
            abgedeckt = len(fs & set(self._woerter(titel + " " + text))) / len(fs)
            s = 0.35 * kandidaten.get(sid, 0.0) + 0.35 * abgedeckt + bonus.get(sid, 0.0) + 0.02 * math.log10(1 + beliebt * 1e7)
            if mass is not None:
                if aid in subjekte:
                    m = mass_subjekt(text)
                    s += 0.25 * min(m, 4.0)
                    if m >= 2.0 and sid not in bonus:
                        s += 0.6
                else:
                    s += (0.1 if subjekte else 0.25) * min(mass(text), 4.0)
            if vektor is not None and vb:
                s += 0.6 * max(0.0, _kosinus(vektor, _v_lesen(vb)))
            if sid not in bonus and abgedeckt < (0.34 if bonus else (0.99 if len(fs) <= 2 else 0.67)):
                continue
            wertung.append((round(s, 4), aid, titel, nr, text))
        z["lesen"] = time.monotonic() - t1
        z["kandidaten"] = len(rows)
        wertung.sort(key=lambda w: -w[0])
        out, je = [], {}
        if subjekte:
            vorn = [w for w in wertung if w[1] in subjekte and w[3] == 0][:min(2, max(1, n - 1))]
            for w in vorn:
                je[w[1]] = je.get(w[1], 0) + 1
            out = list(vorn)
            wertung = [w for w in wertung if w not in vorn]
        for w in wertung:
            if len(out) >= n:
                break
            if je.get(w[1], 0) >= (4 if w[1] in subjekte else 2):
                continue
            je[w[1]] = je.get(w[1], 0) + 1
            out.append(w)
            if len(out) >= n:
                break
        return out


def ordner_groesse_mb(ordner: Path) -> int:
    try:
        return sum(p.stat().st_size for p in Path(ordner).rglob("*") if p.is_file()) // 1_000_000
    except OSError:
        return 0


_ORTSFRAGE = re.compile(r"(?i)\b(?:einwohner\w*|bevölkerung\w*|stadt|städte|gemeinde\w*|ort|ortschaft|bürgermeister\w*|bezirk\w*|postleitzahl|plz|"
                        r"vorwahl|fläche|seehöhe|höhe über|liegt|lage|hauptplatz|sehenswürdigkeit\w*)\b")
_ORT_KLAMMER = re.compile(r"(?i)\((?:stadt|gemeinde|marktgemeinde|stadtgemeinde|markt|statutarstadt|ort|ortschaft|oberösterreich|niederösterreich|"
                          r"salzburg|tirol|vorarlberg|kärnten|steiermark|burgenland|wien|österreich|deutschland|schweiz|bayern|baden-württemberg|"
                          r"sachsen|thüringen|hessen|nordrhein-westfalen|niedersachsen|rheinland-pfalz|brandenburg|südtirol|kanton \w+|landkreis [^)]+|"
                          r"bezirk [^)]+)\)$")
_BEGRIFFSKLAERUNG = re.compile(r"(?i)\b(?:steht für|bezeichnet|ist der name)\b[^.]{0,40}:|begriffsklärung")


_NAME_TEIL, _name_kandidat = namenpruefung._NAME_TEIL, namenpruefung._name_kandidat
_FACHBEGRIFF_ENDE = namenpruefung.FACHBEGRIFF_ENDE


class WikiKopie:

    sprache: Sprache = DE

    def __init__(self, ordner, *, freigabe_mb, darf, karte_frei=lambda: True, vektoren=None, vektoren_bereit=lambda: False,
                 oeffner=None, log=None, schlafen=None, jetzt=time.time, platte_frei_mb=None, gemeinschaft=None, modell=None, ablage=None,
                 sprache: Sprache | None = None, vorgesehen=lambda: True) -> None:
        self._ordner_fn = ordner
        self._vorgesehen = vorgesehen
        self.sprache = sprache or DE
        if self.sprache is not DE:
            gemeinschaft = ablage = None
        self._gemeinschaft = gemeinschaft
        self._modell = modell or (lambda: "")
        self._ablage = ablage
        self._gem_naechst = 0.0
        self._platte_frei_mb = platte_frei_mb or (lambda p: shutil.disk_usage(p).free // 1_000_000)
        self._freigabe_mb = freigabe_mb
        self._darf = darf
        self._karte_frei = karte_frei
        self._vektoren = vektoren
        self._vektoren_bereit = vektoren_bereit
        self._zahlen_merk: dict | None = None
        self._oeffner = oeffner
        self._name = "wikipedia" if self.sprache is DE else f"wikipedia-{self.sprache.code}"
        _log_roh = log or (lambda z: None)
        self._log = _log_roh if self.sprache is DE else (lambda z: _log_roh(z.replace("wikipedia:", self._name + ":", 1)))
        self._halt = threading.Event()
        self._schlafen = schlafen or (lambda s: self._halt.wait(s))
        self._jetzt = jetzt
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._db: Datenbank | None = None
        self._db_pfad: Path | None = None
        self.phase = "aus"
        self.meldung = ""
        self._belegt_mb_cache = (0.0, 0)
        self._fest: Path | None = None
        self._umzug_wartet = False
        self._angewaermt: Datenbank | None = None


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
        t, mb = self._belegt_mb_cache
        if self._jetzt() - t > 300:
            mb = ordner_groesse_mb(self.ordner) if self.ordner.exists() else 0
            self._belegt_mb_cache = (self._jetzt(), mb)
        return mb

    def _quelle_kennung(self, aid: int) -> str:
        return f"wikipedia-{aid}" if self.sprache is DE else f"wikipedia-{self.sprache.code}-{aid}"

    def darf_halten(self) -> bool:
        try:
            vorgesehen = bool(self._vorgesehen())
        except Exception:
            vorgesehen = False
        return vorgesehen and int(self._freigabe_mb() or 0) >= self.sprache.min_freigabe_mb

    def bereit(self) -> bool:
        return self._db is not None

    def zeiten_der_suche(self) -> dict:
        db = self._db
        if db is None:
            return {}
        z = dict(db.zeiten_letzte or getattr(getattr(db, "_leser", None), "zeiten", {}) or {})
        z["ausgang"] = getattr(self, "ausgang_letzte", "")
        return z

    def ausgabe(self) -> str:
        return str(self._stand().get("fertig_ausgabe") or "")


    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._halt.clear()
            self._oeffnen()
            self._thread = threading.Thread(target=self._schleife, name=self._name, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout_s: float = 10.0) -> None:
        self._halt.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=timeout_s)

    def _oeffnen(self) -> None:
        pfad = self.ordner / DB
        if umzug.offen(self.ordner):
            return
        if self._db is None and pfad.exists() and self._stand().get("fertig_ausgabe"):
            try:
                self._db = Datenbank(pfad, sprache=self.sprache)
                self._db_pfad = pfad
                self._zahlen_holen()
            except sqlite3.Error as exc:
                self._log(f"FEHLER wikipedia öffnen: {exc}")

    def loeschen(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.schliessen()
                self._db = None
            shutil.rmtree(self.ordner, ignore_errors=True)
            self._belegt_mb_cache = (0.0, 0)
            self.phase, self.meldung = "aus", ""

    def umzug_vormerken(self, von: Path, nach: Path) -> None:
        if not umzug.vormerken(Path(von), Path(nach)):
            return
        self._umzug_wartet = True
        self._log("OK wikipedia: Umzug auf das gewählte Laufwerk vorgemerkt")

    def _schliessen(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.schliessen()
                self._db = None
            self._belegt_mb_cache = (0.0, 0)


    def _holen(self, adresse: str, *, bereich: int | None = None, max_bytes: int = 2_000_000):
        if not adresse.startswith("https://dumps.wikimedia.org/"):
            raise WikiError("WIKI_ADRESSE", "nur von dumps.wikimedia.org")
        kopf = {"User-Agent": _UA}
        if bereich:
            kopf["Range"] = f"bytes={bereich}-"
        oeffner = self._oeffner or __import__("datenfluss").oeffner("Wikipedia-Kopie von Wikimedia laden (einmal im Monat)")
        try:
            return oeffner(urllib.request.Request(adresse, headers=kopf), timeout=TIMEOUT_S)
        except Exception as exc:
            raise WikiError("WIKI_HOLEN", f"dumps.wikimedia.org antwortet nicht ({type(exc).__name__})") from None

    def _seite(self, adresse: str) -> str:
        with self._holen(adresse) as r:
            return r.read(2_000_000).decode("utf-8", errors="replace")

    def neueste_ausgabe(self) -> tuple[str, list[tuple[int, str, int]]] | None:
        uebersicht = self._seite(QUELLE)
        for ausgabe in sorted(set(_AUSGABE.findall(uebersicht)), reverse=True)[:4]:
            basis = f"{QUELLE}{ausgabe}/index_name={self.sprache.name}/"
            try:
                liste = self._seite(basis)
            except WikiError:
                continue
            if "_SUCCESS" not in liste:
                continue
            teile = []
            for m in _teil_muster(self.sprache.name).finditer(liste):
                groesse = re.search(re.escape(m.group(1)) + r'</a>\s+\S+\s+\S+\s+(\d+)', liste)
                teile.append((int(m.group(3)), basis + m.group(1), int(groesse.group(1)) if groesse else 0))
            if teile:
                return ausgabe, sorted(set(teile))
        return None

    def _teil_laden(self, adresse: str, ziel: Path, groesse: int) -> bool:
        teil = ziel.with_suffix(ziel.suffix + ".teil")
        schon = teil.stat().st_size if teil.exists() else 0
        if groesse and schon >= groesse:
            teil.replace(ziel)
            return True
        with self._holen(adresse, bereich=schon or None) as r, open(teil, "ab" if schon else "wb") as f:
            if schon and getattr(r, "status", 206) == 200:
                f.seek(0)
                f.truncate()
            while True:
                if not self._darf() or self._umzug_unterbricht():
                    return False
                stueck = r.read(1024 * 1024)
                if not stueck:
                    break
                f.write(stueck)
        if groesse and teil.stat().st_size != groesse:
            raise WikiError("WIKI_GROESSE", f"Teil unvollständig ({teil.stat().st_size} statt {groesse} Bytes)")
        teil.replace(ziel)
        return True


    def _schleife(self) -> None:
        while not self._halt.is_set():
            try:
                self._fest = Path(self._ordner_fn())
                wartezeit = self.schritt()
            except WikiError as exc:
                self.phase, self.meldung = "fehler", exc.detail
                self._log(f"ABGELEHNT wikipedia: {exc.code}: {exc.detail}")
                wartezeit = 600
            except sqlite3.OperationalError as exc:
                if "full" in str(exc).lower():
                    self.phase, self.meldung = "zu_wenig_platz", "das Laufwerk ist voll, die Kopie wartet"
                    self._log("FEHLER wikipedia: Laufwerk voll, die Kopie wartet eine Stunde")
                    wartezeit = 3600
                else:
                    self.phase, self.meldung = "fehler", "OperationalError"
                    self._log(f"FEHLER wikipedia: OperationalError: {str(exc)[:200]}")
                    wartezeit = 600
            except Exception as exc:
                self.phase, self.meldung = "fehler", f"{type(exc).__name__}"
                self._log(f"FEHLER wikipedia: {type(exc).__name__}: {str(exc)[:200]}")
                wartezeit = 600
            finally:
                self._fest = None
            if self._umzug_wartet:
                wartezeit = 0
            if wartezeit:
                self._schlafen(wartezeit)

    def _umzug_unterbricht(self) -> bool:
        return self._umzug_wartet or self._halt.is_set()

    def schritt(self) -> float:
        if umzug.offen(self.ordner):
            self.phase, self.meldung = "zieht_um", ""
        w = umzug.schritt(self.ordner, behalten=self.darf_halten(), schliessen=self._schliessen, oeffnen=self._oeffnen,
                          halt=self._halt.is_set, log=self._log, name=self._name, platte_frei_mb=self._platte_frei_mb)
        if w is not None:
            self.phase, self.meldung = "zieht_um", ""
            return w
        self._umzug_wartet = False
        if not self.darf_halten():
            try:
                vorgesehen = bool(self._vorgesehen())
            except Exception:
                vorgesehen = False
            if self.ordner.exists() and (self.ordner / STAND).exists():
                self._log(f"OK wikipedia: Freigabe unter {self.sprache.min_freigabe_mb // 1000} GB, Kopie gelöscht" if vorgesehen
                          else "OK wikipedia: dieses Gerät hält keine Kopie (nur das Admin-Gerät), Kopie gelöscht")
                self.loeschen()
            self.phase = "zu_wenig_platz" if vorgesehen else "nicht_vorgesehen"
            return 300
        if self._db is None:
            self._oeffnen()
        if self._db is not None and self._angewaermt is not self._db and self._db.hat_wortzahl():
            self._angewaermt = self._db
            self._anwaermen(self._db.pfad)
            return 0
        if not self._darf():
            self.phase = "pause"
            return 30
        st = self._stand()
        if not st.get("bau_ausgabe"):
            veraltet = bool(st.get("fertig_ausgabe")) and int(st.get("einlese_stand", 1)) < self.sprache.einlese_stand
            faellig = not st.get("fertig_ausgabe") or veraltet or (self._jetzt() - float(st.get("fertig_um", 0))) > NEU_NACH_TAGE * 86400
            if not faellig or (self._jetzt() - float(st.get("zuletzt_gesucht", 0))) < 6 * 3600 and st.get("fertig_ausgabe") and not veraltet:
                return self._vektor_schritt()
            self.phase = "sucht"
            self._stand_setzen(zuletzt_gesucht=self._jetzt())
            neu = self.neueste_ausgabe()
            if neu is None:
                raise WikiError("WIKI_KEINE", "keine vollständige Ausgabe gefunden")
            ausgabe, teile = neu
            if ausgabe == st.get("fertig_ausgabe") and not veraltet:
                return self._vektor_schritt()
            gesamt_gb = sum(g for _, _, g in teile) / 1e9
            frei_mb = int(self._platte_frei_mb(self.ordner.parent if not self.ordner.exists() else self.ordner))
            halb = self.sprache.platz_mb // 2
            bedarf_mb = max(self.belegt_mb(), halb) if st.get("fertig_ausgabe") else halb
            if frei_mb - FREI_RESERVE_MB < bedarf_mb:
                self.phase = "zu_wenig_platz"
                self.meldung = (f"auf dem Laufwerk sind nur {frei_mb // 1000} GB frei, zum Neu-Einlesen braucht die Kopie noch einmal "
                                f"{bedarf_mb // 1000} GB; die bisherige bleibt so lange in Gebrauch" if st.get("fertig_ausgabe")
                                else f"auf dem Laufwerk sind nur {frei_mb // 1000} GB frei")
                self._log(f"OK wikipedia: zu wenig Platz ({frei_mb // 1000} GB frei, Bedarf {(bedarf_mb + FREI_RESERVE_MB) // 1000} GB), nächster Blick in einer Stunde")
                return 3600
            self._stand_setzen(bau_ausgabe=ausgabe, bau_teile=[[n, a, g] for n, a, g in teile], bau_gb=round(gesamt_gb, 1), bau_seit=_jetzt(),
                               bau_stand=self.sprache.einlese_stand)
            self._log(f"OK wikipedia: Ausgabe {ausgabe} mit {len(teile)} Teilen ({gesamt_gb:.1f} GB) wird geholt")
            return 0
        if int(st.get("bau_stand", 0)) != self.sprache.einlese_stand:
            self._bau_verwerfen(st)
            return 0
        return self._bau_schritt(st)

    def _bau_verwerfen(self, st: dict) -> None:
        bau = self._bau_pfad(st["bau_ausgabe"])
        for p in [bau, bau.with_name(bau.name + "-wal"), bau.with_name(bau.name + "-shm")] + list(self.ordner.glob("teil-*.json.bz2")):
            p.unlink(missing_ok=True)
        self._stand_setzen(bau_ausgabe="", bau_teile=[], bau_vorrat="", bau_uebernommen="", einlesen_teil=-1, einlesen_zeile=0, bau_stand=0)
        self._log(f"OK wikipedia: Bau der Ausgabe {st['bau_ausgabe']} mit Einleseregeln {st.get('bau_stand', 'vor 23j')} verworfen, "
                  f"beginnt neu mit Stand {self.sprache.einlese_stand}")

    def _bau_pfad(self, ausgabe: str) -> Path:
        return self.ordner / f"wikipedia-{ausgabe}.bau.sqlite"

    def _vektoren_uebernehmen(self, neu: "Datenbank", alt_pfad: Path) -> int:
        s = time.monotonic()
        try:
            alt_db = Datenbank(alt_pfad, sprache=self.sprache)
            try:
                nach = alt_db.hashes_sicherstellen()
            finally:
                alt_db.schliessen()
            n = neu.vektoren_uebernehmen(alt_pfad)
            self._stand_setzen(vektoren_uebernommen=n)
            self._log(f"OK wikipedia: {n} Vektoren aus der vorigen Ausgabe übernommen ({nach} Hashes nachgetragen, {time.monotonic() - s:.0f} s)")
            return n
        except Exception as exc:
            self._log(f"FEHLER wikipedia: Übernahme der Vektoren aus der vorigen Ausgabe: {type(exc).__name__}: {str(exc)[:120]}; es wird neu gerechnet")
            return 0

    def _bau_schritt(self, st: dict) -> float:
        ausgabe = st["bau_ausgabe"]
        frei_mb = int(self._platte_frei_mb(self.ordner if self.ordner.exists() else self.ordner.parent))
        if frei_mb < FREI_RESERVE_MB:
            self.phase, self.meldung = "zu_wenig_platz", f"auf dem Laufwerk sind nur {frei_mb // 1000} GB frei, der Bau der Kopie wartet"
            self._log(f"OK wikipedia: Bau der Ausgabe {ausgabe} wartet, nur {frei_mb // 1000} GB frei")
            return 3600
        teile = [(int(n), str(a), int(g)) for n, a, g in st.get("bau_teile", [])]
        db = Datenbank(self._bau_pfad(ausgabe), schreiben=True, sprache=self.sprache)
        db._abbrechen = self._umzug_unterbricht
        try:
            offen = [(n, a, g) for n, a, g in teile if not db.teil_fertig(n)]
            if not offen:
                if st.get("bau_vorrat") != ausgabe:
                    self.phase = "ordnet"
                    n = db.vorrat_anlegen()
                    self._stand_setzen(bau_vorrat=ausgabe)
                    self._log(f"OK wikipedia: Ausgabe {ausgabe} eingelesen, {n} Abschnitte; Reihenfolge für die Vektoren steht")
                    return 0
                if not db.hashes_vollstaendig():
                    self.phase = "merkt"
                    db.hashes_sicherstellen(hoechstens=HASH_STAPEL)
                    return 0
                if not db.hash_index_da():
                    self.phase = "merkt"
                    db.hash_index_anlegen()
                    return 0
                alt = self.ordner / DB
                if alt.exists() and st.get("bau_uebernommen") != ausgabe:
                    self.phase = "uebernimmt"
                    quelle = self._db if self._db is not None and self._db.pfad == alt else None
                    if quelle is not None and not quelle.hashes_vollstaendig():
                        quelle.hashes_sicherstellen(hoechstens=HASH_STAPEL)
                        return 0
                    self._vektoren_uebernehmen(db, alt)
                    if self._umzug_unterbricht():
                        return 0
                    self._stand_setzen(bau_uebernommen=ausgabe)
                    return 0
            else:
                nr, adresse, groesse = offen[0]
                datei = self.ordner / f"teil-{nr:05d}.json.bz2"
                if not datei.exists():
                    self.phase, self.meldung = "laedt", f"{len(teile) - len(offen) + 1}/{len(teile)}"
                    if not self._teil_laden(adresse, datei, groesse):
                        return 30
                self.phase, self.meldung = "liest", f"{len(teile) - len(offen) + 1}/{len(teile)}"
                fertig = self._teil_einlesen(db, nr, datei)
                if fertig:
                    db.teil_abschliessen(nr)
                    datei.unlink(missing_ok=True)
                    self._stand_setzen(einlesen_teil=-1, einlesen_zeile=0)
                    z = db.zahlen(vektor_pos=0)
                    self._zahlen_merk = z
                    self._log(f"OK wikipedia: Teil {nr + 1}/{len(teile)} eingelesen ({z['artikel']} Artikel bisher)")
                return 0 if fertig else 30
        finally:
            db.schliessen()
        with self._lock:
            if self._db is not None:
                self._db.schliessen()
                self._db = None
            ziel = self.ordner / DB
            for alt in (ziel, ziel.with_name(DB + "-wal"), ziel.with_name(DB + "-shm")):
                alt.unlink(missing_ok=True)
            self._bau_pfad(ausgabe).replace(ziel)
            for rest in (self._bau_pfad(ausgabe).with_name(self._bau_pfad(ausgabe).name + s) for s in ("-wal", "-shm")):
                rest.unlink(missing_ok=True)
            self._stand_setzen(fertig_ausgabe=ausgabe, fertig_um=self._jetzt(), bau_ausgabe="", bau_teile=[], vektor_pos=0, bau_vorrat="", bau_uebernommen="",
                               einlese_stand=self.sprache.einlese_stand)
            self._db = Datenbank(ziel, sprache=self.sprache)
            self._db_pfad = ziel
        self.phase, self.meldung = "bereit", ""
        self._log(f"OK wikipedia: Ausgabe {ausgabe} ist jetzt die Kopie für die Suche")
        return 0

    def _teil_einlesen(self, db: Datenbank, nr: int, datei: Path) -> bool:
        st = self._stand()
        schon = int(st.get("einlesen_zeile", 0)) if int(st.get("einlesen_teil", -1)) == nr else 0
        if schon == 0:
            db.teil_verwerfen(nr)
        stapel: list[dict] = []
        zeile_nr = 0
        with bz2.open(datei, "rt", encoding="utf-8") as f:
            for zeile in f:
                zeile_nr += 1
                if zeile_nr <= schon:
                    continue
                if not zeile.startswith('{"index"'):
                    try:
                        a = dokument_lesen(json.loads(zeile), self.sprache)
                    except ValueError:
                        a = None
                    if a:
                        stapel.append(a)
                if len(stapel) >= EINLESEN_SCHRITT:
                    db.teil_aufnehmen(nr, stapel)
                    stapel = []
                    self._stand_setzen(einlesen_teil=nr, einlesen_zeile=zeile_nr)
                    if not self._darf() or self._halt.is_set():
                        return False
        if stapel:
            db.teil_aufnehmen(nr, stapel)
        return True

    def _anwaermen(self, pfad: Path) -> None:
        s = time.monotonic()
        w: Datenbank | None = None
        try:
            w = Datenbank(pfad, sprache=self.sprache)
            for sql in ("SELECT count(*) FROM wortzahl", "SELECT count(*) FROM titel"):
                if self._halt.is_set():
                    return
                w._c.execute(sql).fetchone()
            for frage in (ANWAERMEN if self.sprache is DE else ANWAERMEN_EN):
                if self._halt.is_set():
                    return
                try:
                    w._suchen_begrenzt(frage, None, 3, time.monotonic() + 30, self._halt.is_set)
                except (Unterbrochen, sqlite3.Error):
                    pass
            self._log(f"OK wikipedia: für die Suche angelesen ({time.monotonic() - s:.1f} s)")
        except sqlite3.Error as exc:
            self._log(f"FEHLER wikipedia anlesen: {str(exc)[:120]}")
        finally:
            if w is not None:
                w.schliessen()

    def _vektor_schritt(self) -> float:
        if self._db is None:
            self._oeffnen()
        if self._db is None:
            self.phase = "aus"
            return 600
        st = self._stand()
        z = self._zahlen_holen(st)
        if not self._db.hat_wortzahl():
            self.phase = "zaehlt"
            s = time.monotonic()
            n = self._db.wortzahl_anlegen()
            self._log(f"OK wikipedia: {n} Wörter für die schnelle Suche gezählt ({time.monotonic() - s:.0f} s)")
            return 0
        if not self._db.hashes_vollstaendig():
            self.phase = "merkt"
            n = self._db.hashes_sicherstellen(hoechstens=HASH_STAPEL)
            if self._db.hashes_vollstaendig():
                self._log(f"OK wikipedia: Hashes aller Abschnitte stehen (zuletzt {n}); die nächste Ausgabe übernimmt die Vektoren")
            return 0
        if not self._db.hash_index_da():
            self.phase = "merkt"
            s = time.monotonic()
            self._db.hash_index_anlegen()
            self._log(f"OK wikipedia: Index über die Hashes nachgetragen ({time.monotonic() - s:.0f} s); Scheiben der Community gehen jetzt schnell")
            return 0
        pos = int(st.get("vektor_pos", 0))
        if pos >= z["vorrat"]:
            w = self._gemeinschaft_schritt(st, anbieten=True)
            if w is not None:
                return w
            self.phase = "fertig"
            return 600
        w = self._gemeinschaft_schritt(st, anbieten=False)
        if w is not None:
            return w
        if self._vektoren is None or not self._vektoren_bereit() or not self._karte_frei():
            self.phase = "fertig_wartet"
            return 20
        self.phase = "vektoren"
        stapel = self._db.vektor_offen(pos, VEKTOR_BATCH, fenster=VEKTOR_FENSTER)
        if not stapel:
            self._stand_setzen(vektor_pos=min(pos + VEKTOR_FENSTER, z["vorrat"]))
            return 0
        vs = self._vektoren([f"{t}: {x}" for _, _, t, x in stapel])
        self._db.vektoren_schreiben([(sid, [round(a, 4) for a in v]) for (_, sid, _, _), v in zip(stapel, vs)])
        self._stand_setzen(vektor_pos=stapel[-1][0])
        self._zahlen_merk = {**z, "vektoren": min(stapel[-1][0], z["vorrat"])}
        return 0


    def _gemeinschaft_schritt(self, st: dict, *, anbieten: bool) -> float | None:
        gem = self._gemeinschaft() if self._gemeinschaft is not None else None
        modell, ausgabe = str(self._modell() or ""), str(st.get("fertig_ausgabe") or "")
        if gem is None or not modell or len(ausgabe) != 8 or self._jetzt() < self._gem_naechst or not self._karte_frei():
            return None
        if self._db is None or not self._db.hash_index_da():
            return None

        try:
            stand = gem.wiki_vektoren_stand(ausgabe=ausgabe, modell=modell, brauche=not anbieten, biete=anbieten)
        except Exception as exc:
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_ABSTAND_S
            self._log(f"INFO wikipedia gemeinschaft: {getattr(exc, 'detail', None) or type(exc).__name__}")
            return None
        return self._anbieten(gem, stand, st, ausgabe, modell) if anbieten else self._uebernehmen(gem, stand, st, modell)

    def _uebernehmen(self, gem, stand: dict, st: dict, modell: str) -> float | None:
        geholt = set(st.get("wiki_geholt") or [])
        offen = [s for s in stand.get("scheiben") or [] if isinstance(s, dict) and re.fullmatch(r"[0-9a-f]{16}", str(s.get("kennung", "")))
                 and s["kennung"] not in geholt and not s.get("geholt")]
        bereit = [s for s in offen if s.get("am_server")]
        if not bereit:
            self._gem_naechst = self._jetzt() + (GEMEINSCHAFT_WARTEN_S if offen else GEMEINSCHAFT_ABSTAND_S)
            return None
        s = bereit[0]
        k = str(s["kennung"])
        ziel = self.ordner / f"gemeinschaft-{k}.zip"
        self.phase = "uebernimmt"
        try:
            self.ordner.mkdir(parents=True, exist_ok=True)
            gem.scheibe_holen(k, ziel, str(s.get("sha256", "")))
            m, paare = scheiben.wiki_lesen(ziel, modell=modell)
            probe = self._stichprobe_ok(paare)
            if probe is None:
                self._gem_naechst = self._jetzt() + GEMEINSCHAFT_WARTEN_S
                return None
            if not probe:
                raise scheiben.ScheibenError("WIKI_FALSCH", "die Stichprobe passt nicht zu den eigenen Abschnitten; die Scheibe wird nicht übernommen")
            n = self._db.vektoren_einlesen(paare)
        except Exception as exc:
            self._log(f"ABGELEHNT wikipedia übernehmen {k}: {getattr(exc, 'detail', None) or type(exc).__name__}")
            if getattr(exc, "code", "") in ("WIKI_MODELL", "WIKI_FORMAT", "WIKI_FALSCH"):
                geholt.add(k)
                self._stand_setzen(wiki_geholt=sorted(geholt)[-5000:])
                try:
                    gem.wiki_vektoren_geholt(k, ok=False, grund=str(exc.code))
                except Exception:
                    pass
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_WARTEN_S
            return None
        finally:
            try:
                ziel.unlink(missing_ok=True)
            except OSError:
                pass
        geholt.add(k)
        self._stand_setzen(wiki_geholt=sorted(geholt)[-5000:])
        try:
            gem.wiki_vektoren_geholt(k)
        except Exception:
            pass
        self._log(f"OK wikipedia: {n} Vektoren von der Community übernommen (Scheibe {k}, Ausgabe {m.get('ausgabe')} Nr. {m.get('nr')})")
        self._gem_naechst = self._jetzt() + GEMEINSCHAFT_TEMPO_S
        return 0

    def _stichprobe_ok(self, paare: list[tuple[bytes, bytes]]) -> bool | None:
        import random
        if self._vektoren is None or not self._vektoren_bereit():
            return None
        kandidaten = self._db.gemeinsame_hashes([h for h, _ in paare], WIKI_STICHPROBE)
        random.shuffle(kandidaten)
        proben = self._db.texte_zu_hashes(kandidaten, WIKI_STICHPROBE)
        if not proben:
            return True
        soll = dict(paare)
        gerechnet = self._vektoren([f"{t}: {x}" for _, t, x in proben])
        for (h, _, _), v in zip(proben, gerechnet):
            a, b = [float(x) for x in v], _v_lesen(soll[h])
            na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
            if not na or not nb or sum(x * y for x, y in zip(a, b)) / (na * nb) < WIKI_AEHNLICH:
                return False
        return True

    def _anbieten(self, gem, stand: dict, st: dict, ausgabe: str, modell: str) -> float | None:
        if not stand.get("gesucht"):
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_ABSTAND_S
            return None
        da = {int(x) for x in stand.get("nr_da") or [] if isinstance(x, int)}
        nr = 0
        while nr in da:
            nr += 1
        ende = int(st.get("wiki_angeboten_ende", -1)) if st.get("wiki_angeboten_ausgabe") == ausgabe else -1
        if 0 <= ende <= nr:
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_ABSTAND_S
            return None
        je = int(stand.get("je_scheibe") or scheiben.WIKI_JE_SCHEIBE)
        self.phase = "teilt"
        paare = self._db.scheiben_paare(nr, je)
        if not paare:
            self._stand_setzen(wiki_angeboten_ausgabe=ausgabe, wiki_angeboten_ende=nr)
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_ABSTAND_S
            return None
        ablage = Path(self._ablage()) if self._ablage is not None else self.ordner / "gemeinschaft"
        info = scheiben.wiki_packen(paare, ausgabe=ausgabe, modell=modell, nr=nr, ordner=ablage)
        del paare
        if info is None or info["bytes"] > int(stand.get("platz") or 0):
            if info is not None:
                info["pfad"].unlink(missing_ok=True)
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_WARTEN_S
            return None
        try:
            r = gem.wiki_vektoren_anbieten(info["pfad"])
        except Exception as exc:
            info["pfad"].unlink(missing_ok=True)
            self._log(f"INFO wikipedia anbieten Nr. {nr}: {getattr(exc, 'detail', None) or type(exc).__name__}")
            self._gem_naechst = self._jetzt() + GEMEINSCHAFT_WARTEN_S
            return None
        self._log(f"OK wikipedia: Vektoren Nr. {nr} ({info['anzahl']} Stück, {info['bytes'] // 1_000_000} MB) für ein anderes Gerät angeboten, Scheibe {r.get('scheibe', info['kennung'])}")
        self._gem_naechst = self._jetzt() + GEMEINSCHAFT_TEMPO_S
        return 0

    _LEER = {"artikel": 0, "abschnitte": 0, "vektoren": 0, "vorrat": 0}

    def _zahlen_holen(self, st: dict | None = None) -> dict:
        if self._db is None:
            return dict(self._LEER)
        st = st if st is not None else self._stand()
        self._zahlen_merk = self._db.zahlen(vektor_pos=int(st.get("vektor_pos", 0)))
        return self._zahlen_merk

    def _zahlen_zeigen(self) -> dict:
        return dict(self._zahlen_merk or self._LEER)


    def suchen(self, frage: str, *, vektor: list[float] | None = None, n: int = 3, abbrechen=None) -> list[wissen.Treffer]:
        db = self._db
        if db is None:
            return []
        ausgabe = self.ausgabe()
        datum = f"{ausgabe[:4]}-{ausgabe[4:6]}-{ausgabe[6:8]}T00:00:00Z" if len(ausgabe) == 8 else _jetzt()
        out = []
        db.zeiten_letzte = {}
        self.ausgang_letzte = ""
        try:
            gefunden = db.suchen(frage, vektor=vektor, n=n, abbrechen=abbrechen)
            self.ausgang_letzte = "fertig"
        except Unterbrochen as exc:
            self._log(f"INFO wikipedia suchen ohne Ergebnis: {exc}")
            self.ausgang_letzte = "besetzt" if "früher" in str(exc) else ("gestoppt" if "gestoppt" in str(exc) else "grenze")
            return []
        except (sqlite3.Error, sqlite3.ProgrammingError) as exc:
            self._log(f"ABGELEHNT wikipedia suchen: {type(exc).__name__}")
            return []
        for punkte, aid, titel, _nr, text in gefunden:
            adresse = self.sprache.adresse + urllib.parse.quote(titel.replace(" ", "_"))
            q = wissen.Quelle(self._quelle_kennung(aid), "wikipedia", f"{self.sprache.titel}: {titel} ({LIZENZ})", adresse, datum, len(text))
            out.append(wissen.Treffer(q, text, punkte))
        return out

    def einleitung(self, frage: str, hoechstens: int = 3) -> list[wissen.Treffer]:
        db = self._leser_der_kopie()
        if db is None:
            return []
        ausgabe = self.ausgabe()
        datum = f"{ausgabe[:4]}-{ausgabe[4:6]}-{ausgabe[6:8]}T00:00:00Z" if len(ausgabe) == 8 else _jetzt()
        out: list[wissen.Treffer] = []
        if not db._lock.acquire(timeout=NAMEN_WARTEN_S):
            self._log("HINWEIS wikipedia einleitung ausgelassen: eine Suche in der Kopie läuft noch")
            return []
        try:
            ortsfrage = bool(_ORTSFRAGE.search(frage or ""))
            gewaehlt: list[int] = []
            kandidaten = list(db.titel_artikel(frage))
            if ortsfrage:
                for w in re.findall(r"\b[A-ZÄÖÜ][\wäöüß.-]{2,}", frage or ""):
                    if w.lower() in wissen._STOPP or _SACHWORT.fullmatch(w):
                        continue
                    ort = next((v for v, t in db.varianten(w) if _ORT_KLAMMER.search(t.strip())), None)
                    if ort is None or ort in kandidaten:
                        continue
                    allein = db.artikel_zu(w)
                    if allein in kandidaten:
                        kandidaten[kandidaten.index(allein)] = ort
                    else:
                        kandidaten.append(ort)
            for aid in kandidaten:
                e = db.einleitung(aid)
                if not e:
                    continue
                titel, text = e
                if _BEGRIFFSKLAERUNG.search(text[:300]) or aid in gewaehlt:
                    continue
                gewaehlt.append(aid)
                if len(gewaehlt) > hoechstens:
                    break
                adresse = self.sprache.adresse + urllib.parse.quote(titel.replace(" ", "_"))
                q = wissen.Quelle(self._quelle_kennung(aid), "wikipedia", f"{self.sprache.titel}: {titel} ({LIZENZ})", adresse, datum, len(text))
                out.append(wissen.Treffer(q, text, 1.0))
        except (sqlite3.Error, sqlite3.ProgrammingError) as exc:
            self._log(f"ABGELEHNT wikipedia einleitung: {type(exc).__name__}")
            return []
        finally:
            db._lock.release()
        return out

    def _leser_der_kopie(self) -> "Datenbank | None":
        db = self._db
        if db is None:
            return None
        try:
            return db.leser()
        except sqlite3.Error as exc:
            self._log(f"ABGELEHNT wikipedia leser: {type(exc).__name__}")
            return None

    def zustand(self) -> dict:
        st = self._stand()
        z = self._zahlen_zeigen()
        return {"phase": self.phase, "meldung": self.meldung, "ausgabe": st.get("fertig_ausgabe", ""), "bau": st.get("bau_ausgabe", ""),
                "belegt_mb": self.belegt_mb(), **z, "text": self.text_de(st, z)}

    def belegt(self) -> bool:
        db = self._db
        if db is None:
            return False
        if not db._lock.acquire(timeout=NAMEN_WARTEN_S):
            return True
        db._lock.release()
        return False

    def text_de(self, st: dict | None = None, z: dict | None = None) -> str:
        st = st if st is not None else self._stand()
        if z is None:
            z = self._zahlen_zeigen()
        def zahl(n: int) -> str:
            return f"{n:,}".replace(",", ".")
        if self.phase == "zieht_um":
            return "Wikipedia: zieht auf das gewählte Laufwerk um und prüft jede Datei; so lange antwortet KIplatz ohne sie."
        if self.phase == "zaehlt":
            return "Wikipedia: zählt einmal alle Wörter, damit die Suche schnell bleibt."
        if self.phase == "laedt":
            return f"Wikipedia: lädt Teil {self.meldung} der Ausgabe vom {_datum_de(st.get('bau_ausgabe', ''))} herunter."
        if self.phase == "liest":
            return f"Wikipedia: liest Teil {self.meldung} ein."
        if self.phase == "ordnet":
            return "Wikipedia: ordnet die Abschnitte für die Suche nach Bedeutung."
        if self.phase == "nicht_vorgesehen":
            return ""
        if self.phase == "zu_wenig_platz":
            return f"Wikipedia: {self.meldung}." if self.meldung else ("Wikipedia: erst ab 100 GB Speicher-Freigabe." if not z["artikel"] else "")
        if self.phase == "pause" and not z["artikel"]:
            return "Wikipedia: wartet, bis das Gerät arbeiten darf (Rechenkraft teilen eingeschaltet, am Strom, bei „nur im Leerlauf“ niemand am Gerät)."
        if self.phase == "sucht":
            return "Wikipedia: sucht die neueste Ausgabe bei Wikimedia."
        if self.phase == "uebernimmt":
            return "Wikipedia: übernimmt fertige Zahlenreihen von der Community, statt sie selbst zu rechnen."
        if self.phase == "teilt":
            return "Wikipedia: gibt fertige Zahlenreihen an ein anderes Gerät der Community weiter."
        if self.phase == "aus" and not z["artikel"]:
            return "Wikipedia: startet gleich."
        if self.phase == "fehler":
            return f"Wikipedia: gerade geht es nicht ({self.meldung}), nächster Versuch in 10 Minuten."
        if z["artikel"]:
            anteil = f"{100 * z['vektoren'] / z['vorrat']:.1f}".replace(".", ",") if z["vorrat"] else "0"
            if self.phase == "vektoren":
                return f"Wikipedia: {zahl(z['artikel'])} Artikel für die Suche bereit; bereitet sie für die Suche nach Bedeutung auf ({anteil} %)."
            if z["vektoren"] >= z["vorrat"] and z["vorrat"]:
                return f"Wikipedia: {zahl(z['artikel'])} Artikel, Stand {_datum_de(st.get('fertig_ausgabe', ''))}, fertig aufbereitet."
            return f"Wikipedia: {zahl(z['artikel'])} Artikel, Stand {_datum_de(st.get('fertig_ausgabe', ''))}; nach Bedeutung aufbereitet: {anteil} %."
        return ""


def _datum_de(ausgabe: str) -> str:
    return f"{ausgabe[6:8]}.{ausgabe[4:6]}.{ausgabe[:4]}" if len(ausgabe or "") == 8 else "?"


__all__ = ["WikiKopie", "Datenbank", "dokument_lesen", "abschnitte", "MIN_FREIGABE_MB", "LIZENZ"]
