# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import antwortspeicher_basis
import laender

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONATE = {"jänner": 1, "januar": 1, "jan": 1, "feber": 2, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3, "april": 4, "apr": 4,
          "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10,
          "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12}
_MONAT = "|".join(sorted(MONATE, key=len, reverse=True))
_TAG = "|".join(WOCHENTAGE + KURZ)

_DATUM_ZAHL = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4})(?![\d:])|(?<=\.)(\d{2})(?![\d:]))?")
_DATUM_WORT = re.compile(rf"(?<!\d)(\d{{1,2}})\.\s*({_MONAT})\.?(?:\s+(\d{{4}}))?(?![a-zäöü])", re.I)
_DATUM_ISO = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
MONATE_EN = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
             "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11,
             "nov": 11, "december": 12, "dec": 12}
_MONAT_EN = "|".join(m.capitalize() for m in sorted(MONATE_EN, key=len, reverse=True))
_DATUM_EN_MT = re.compile(rf"\b({_MONAT_EN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)(?:,?\s+(\d{{4}})(?!\d))?")
_DATUM_EN_TM = re.compile(rf"(?<![\d.])(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONAT_EN})\b\.?(?:,?\s+(\d{{4}})(?!\d))?")
_WOCHENTAG_DATUM = re.compile(rf"\b({_TAG})(\.?)(,?\s+(?:den\s+|dem\s+)?)(\d{{1,2}}\.\s?\d{{1,2}}\.(?:\s?\d{{2,4}})?|\d{{1,2}}\.\s*(?:{_MONAT})\.?(?:\s+\d{{4}})?)", re.I)

_BETRAG = re.compile(r"(?:€\s*(\d[\d.,]*\d|\d)|(\d[\d.,]*\d|\d)\s*(?:€|euro\b|eur\b|cent\b|%|prozent\b))", re.I)
_ZAHL = re.compile(r"\d[\d.,]*\d|\d")


def _jahr(j: str | None) -> int | None:
    if not j:
        return None
    n = int(j)
    return n + 2000 if n < 100 else n


def daten(text: str) -> set[tuple[int, int, int | None]]:
    out: set[tuple[int, int, int | None]] = set()
    for m in _DATUM_ZAHL.finditer(text or ""):
        t, mo = int(m.group(1)), int(m.group(2))
        if 1 <= t <= 31 and 1 <= mo <= 12:
            out.add((t, mo, _jahr(m.group(3) or m.group(4))))
    for m in _DATUM_WORT.finditer(text or ""):
        t, mo = int(m.group(1)), MONATE[m.group(2).lower()]
        if 1 <= t <= 31:
            out.add((t, mo, _jahr(m.group(3))))
    for m in _DATUM_ISO.finditer(text or ""):
        out.add((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in _DATUM_EN_MT.finditer(text or ""):
        t = int(m.group(2))
        if 1 <= t <= 31:
            out.add((t, MONATE_EN[m.group(1).lower()], _jahr(m.group(3))))
    for m in _DATUM_EN_TM.finditer(text or ""):
        t = int(m.group(1))
        if 1 <= t <= 31:
            out.add((t, MONATE_EN[m.group(2).lower()], _jahr(m.group(3))))
    return out


def _werte(zahl: str) -> set[float]:
    z = zahl.strip(".,")
    out: set[float] = set()
    if not z:
        return out
    if "," in z and "." in z:
        a, b = (z.replace(".", "").replace(",", "."), z.replace(",", ""))
        for x in (a, b):
            try:
                out.add(round(float(x), 4))
            except ValueError:
                pass
        return out
    kandidaten = [z.replace(",", ".")]
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", z):
        kandidaten.append(z.replace(".", "").replace(",", ""))
    for x in kandidaten:
        try:
            out.add(round(float(x), 4))
        except ValueError:
            pass
    return out


def betraege(text: str) -> list[set[float]]:
    return [_werte(m.group(1) or m.group(2)) for m in _BETRAG.finditer(text or "")]


def zahlenwerte(text: str) -> set[float]:
    out: set[float] = set()
    for m in _ZAHL.finditer(text or ""):
        out |= _werte(m.group(0))
    return out


def _gedeckt_datum(d: tuple[int, int, int | None], belegt: set[tuple[int, int, int | None]]) -> bool:
    t, m, j = d
    for bt, bm, bj in belegt:
        if bt == t and bm == m and (j is None or bj is None or bj == j):
            return True
    return False


def _saetze(absatz: str) -> list[str]:
    import pruefung
    return [s for s in pruefung._SATZ_ENDE.split(absatz) if s]


_SEIT = re.compile(r"\b(?:seit|ab)\s+(?:(?:dem|\d{1,2}\.|[A-Za-zÄÖÜäöü]+)\s+){0,3}20\d\d\b", re.I)


def seit_belegt(satz: str, gelesen: str) -> bool:
    if not (gelesen or "").strip() or not _SEIT.search(satz or ""):
        return False
    werte = zahlenwerte(gelesen)
    if not all(_werte(m.group(0)) & werte for m in _ZAHL.finditer(satz)):
        return False
    d = daten(gelesen)
    return all(_gedeckt_datum(x, d) for x in daten(satz))


def unbelegte_streichen(antwort: str, belege: str, *, betraege_pruefen: bool = True) -> tuple[str, list[str]]:
    belegt_d = daten(belege)
    belegt_z = zahlenwerte(belege)
    raus: list[str] = []
    absaetze = []
    for absatz in (antwort or "").split("\n"):
        bleiben = []
        for s in _saetze(absatz):
            falsch_d = [d for d in daten(s) if not _gedeckt_datum(d, belegt_d)]
            falsch_b = [b for b in betraege(s) if b and not (b & belegt_z)] if betraege_pruefen else []
            if falsch_d or falsch_b:
                raus.append(s)
            else:
                bleiben.append(s)
        if bleiben or not absatz.strip():
            absaetze.append(" ".join(bleiben))
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(absaetze)).strip()
    if raus and not rest:
        rest = weiss_nicht_satz()
    return rest, raus


KLEINE_ZAHL = 12
_EINHEIT_NACH = re.compile(r"\s*(?:%|‰|€|°|prozent\b|euro\b|eur\b|cent\b|chf\b|fr\.|franken\b|dollar\b|\$|m\b|km\b|cm\b|mm\b|kg\b|g\b|t\b|l\b|ha\b|"
                           r"meter\b|kilometer\b|millionen?\b|mio\b|milliarden?\b|mrd\b|tausend\b|grad\b|uhr\b|jahr\w*|einwohner\w*|stunden?\b|minuten?\b|"
                           r"tage?n?\b|wochen?\b|monate?n?\b|mal\b|stück\b|punkte?n?\b|tore?n?\b|kw\b|kwh\b|ps\b|kmh\b|km/h)", re.I)
_WORT_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß'’-]*")
_KEIN_NAME = set("""der die das den dem des ein eine einer eines einem einen er sie es wir ihr du ich man dies diese dieser dieses jener
sein seine ihre ihr unser euer im in am an auf aus bei mit nach von vor zu zum zur und oder aber doch denn weil wenn als wie so da dort hier
laut ja nein nicht kein keine heute morgen gestern übrigens außerdem zudem allerdings jedoch damit dabei dazu davon insgesamt""".split())
_KEIN_NAME |= {w.lower() for w in WOCHENTAGE} | set(MONATE) | set(MONATE_EN)
_VERBINDER = {"von", "van", "de", "la", "le", "da", "di", "du", "zu", "del", "ten", "ter"}
_KUERZEL_KEIN_NAME = {"EL", "TL", "ML", "KG", "CM", "MM", "KM", "PS", "KW", "KWH", "MB", "GB", "TB", "PC", "TV", "LED", "USB", "WLAN", "PDF", "CO2",
                      "OK", "UV", "ID", "PIN", "SMS", "DIY", "XL", "XXL", "MHZ", "GHZ", "HZ", "DB", "AG", "GMBH", "EU"}
_UNGEFAEHR = re.compile(r"(?:rund|etwa|ungefähr|ca\.?|circa|zirka|knapp|fast|beinahe|über|mehr als|weniger als|gut|annähernd)\s+$", re.I)
UNGEFAEHR_ANTEIL = 0.1
_MAL = {"tausend": 1e3, "millionen": 1e6, "million": 1e6, "mio": 1e6, "milliarden": 1e9, "milliarde": 1e9, "mrd": 1e9}
_MAL_NACH = re.compile(r"\s*(tausend|millionen|million|mio|milliarden|milliarde|mrd)\b\.?", re.I)


def _zahl_pruefbar(m: re.Match, satz: str) -> bool:
    roh = m.group(0)
    if _EINHEIT_NACH.match(satz, m.end()):
        return True
    werte = _werte(roh)
    return any(w != int(w) or w > KLEINE_ZAHL for w in werte)


def _ungefaehr_belegt(m: re.Match, satz: str, belegt: set[float]) -> bool:
    if not _UNGEFAEHR.search(satz[:m.start()]):
        return False
    mal = _MAL_NACH.match(satz, m.end())
    faktor = _MAL[mal.group(1).lower()] if mal else 1.0
    for w in _werte(m.group(0)):
        x = w * faktor
        if x and any(abs(v - x) <= abs(x) * UNGEFAEHR_ANTEIL for v in belegt):
            return True
    return False


_EINHEIT_ART = (
    ("dauer", 1.0, r"sekunden?|sek\.?|seconds?|secs?"),
    ("dauer", 60.0, r"minuten?|min\.?|minutes?|mins?"),
    ("dauer", 3600.0, r"stunden?|std\.?|hours?|hrs?"),
    ("strecke", 0.001, r"mm|millimetern?|millimetres?|millimeters?"),
    ("strecke", 0.01, r"cm|zentimetern?|centimetres?|centimeters?"),
    ("strecke", 1.0, r"m|metern?|metres?|meters?"),
    ("strecke", 1000.0, r"km|kilometern?|kilometres?|kilometers?"),
    ("strecke", 1609.344, r"meilen|miles?|mi"),
    ("gewicht", 1.0, r"g|gramm|grams?"),
    ("gewicht", 1000.0, r"kg|kilos?|kilogramms?|kilograms?"),
    ("gewicht", 1e6, r"t|tonnen|tonnes?|tons?"),
)
_LAENGE = re.compile(r"(?<![\d:.])(\d{1,2}):([0-5]\d)(?::([0-5]\d))?(?![\d:])(?!\s*(?:uhr|h\b|o'clock))", re.I)
_EINHEIT_RE = [(art, faktor, re.compile(rf"[\s-]?(?:{muster})(?![\wÄÖÜäöüß²³])", re.I)) for art, faktor, muster in _EINHEIT_ART]


def _einheit(text: str, ende: int) -> tuple[str, float] | None:
    for art, faktor, r in _EINHEIT_RE:
        if r.match(text, ende):
            return art, faktor
    return None


def einheiten_werte(text: str) -> dict[str, set[float]]:
    out: dict[str, set[float]] = {}
    for m in _ZAHL.finditer(text or ""):
        e = _einheit(text, m.end())
        if e:
            out.setdefault(e[0], set()).update(round(w * e[1], 3) for w in _werte(m.group(0)))
    for m in _LAENGE.finditer(text or ""):
        a, b, c = m.group(1), m.group(2), m.group(3)
        sek = int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
        out.setdefault("dauer", set()).add(float(sek))
    return out


def _einheit_belegt(m: re.Match, satz: str, e: tuple[str, float], quell: dict[str, set[float]]) -> bool:
    werte = {round(w * e[1], 3) for w in _werte(m.group(0))}
    belegt = quell.get(e[0], set())
    if werte & belegt:
        return True
    if _UNGEFAEHR.search(satz[:m.start()]):
        return any(abs(v - x) <= abs(x) * UNGEFAEHR_ANTEIL for x in werte if x for v in belegt)
    return False


def unbelegte_zahlen(satz: str, belegt: set[float], ableitung: bool = False, einheiten: dict[str, set[float]] | None = None) -> list[str]:
    out = []
    for m in _ZAHL.finditer(satz or ""):
        if not _zahl_pruefbar(m, satz):
            continue
        e = _einheit(satz, m.end()) if einheiten is not None else None
        if e:
            if not _einheit_belegt(m, satz, e, einheiten):
                out.append(m.group(0))
        elif (not (_werte(m.group(0)) & belegt) and not _ungefaehr_belegt(m, satz, belegt)
                and not (ableitung and abgeleitet(_werte(m.group(0)), belegt))):
            out.append(m.group(0))
    return out


_ABLEITUNG = re.compile(r"(?i)\bum wie viele?\b|\bunterschied\b|\bdifferenz\b|\bwie viele? (?:mehr|weniger)\b|\bmehr als\b|\bweniger als\b|\bgrößer\b|"
                        r"\bkleiner\b|\bhöher\b|\bniedriger\b|\bzusammen\b|\binsgesamt\b|\bgesamt\b|\banteil\b|\bprozent\b|\bverglichen\b|\bvergleich\w*|"
                        r"\bhow many (?:more|fewer|less)\b|\bhow much (?:more|less|bigger|larger|higher)\b|\bdifference\b|\bbigger\b|\blarger\b|"
                        r"\bsmaller\b|\bhigher\b|\blower\b|\bcompared?\b|\bin total\b|\baltogether\b|\bcombined\b|\bshare\b|\bpercent\b")


def ableitungsfrage(frage: str) -> bool:
    return bool(_ABLEITUNG.search(frage or ""))


def abgeleitet(werte: set[float], belegt: set[float]) -> bool:
    if not belegt or len(belegt) > 400:
        return False

    def jahr(x: float) -> bool:
        return x == int(x) and 1000 <= x <= 2099
    gross = [a for a in belegt if a >= 100 and not jahr(a)]
    for w in werte:
        if w < 100 or jahr(w):
            continue
        for a in gross:
            if a == w:
                continue
            b, c = round(a - w, 4), round(w - a, 4)
            if (b >= 100 and not jahr(b) and b in belegt) or (c >= 100 and not jahr(c) and c in belegt):
                return True
    return False


def _tokens(satz: str) -> list[tuple[str, int]]:
    return [(m.group(0).strip("'’-"), m.start()) for m in _WORT_TOKEN.finditer(satz or "")]


def namen(satz: str) -> tuple[list[str], list[str]]:
    toks = _tokens(satz)
    sicher: list[str] = []
    verdacht: list[str] = []
    lauf: list[str] = []

    def lauf_ende():
        kern = [w for w in lauf if w.lower() not in _VERBINDER and w.lower() != "der"]
        if kern and (len(kern) >= 2 or len(kern[0]) >= 3):
            verdacht.append(" ".join(lauf).strip())
        lauf.clear()

    for i, (w, pos) in enumerate(toks):
        vorher = satz[:pos].rstrip()
        satzanfang = i == 0 or vorher.endswith((":", "–", "-", "•", "(", "„", "\""))
        if lauf and i > 0 and re.search(r"[,;/()]", satz[toks[i - 1][1] + len(toks[i - 1][0]):pos]):
            lauf_ende()
        if w[:1].isupper() and not satzanfang and w.lower() not in _KEIN_NAME:
            if w.upper() in _KUERZEL_KEIN_NAME:
                lauf_ende()
                continue
            if len(w) >= 2 and (w.isupper() or re.search(r"\d", w) or re.search(r"[a-zäöüß][A-ZÄÖÜ]", w)):
                lauf_ende()
                sicher.append(w)
                continue
            lauf.append(w)
        elif lauf and i + 1 < len(toks) and toks[i + 1][0][:1].isupper() and (
                w.lower() in _VERBINDER or (w.lower() == "der" and lauf[-1].lower() == "von")):
            lauf.append(w)
        else:
            lauf_ende()
    lauf_ende()
    return sicher, verdacht


def _wortstaemme(text: str) -> set[str]:
    return {w.lower() for w, _ in _tokens(text)}


def name_belegt(name: str, staemme: set[str]) -> bool:
    for teil in name.split():
        t = teil.lower().strip(".,;:")
        if not t or t in _VERBINDER:
            continue
        if t in staemme:
            continue
        kern = t[:max(4, len(t) - 2)]
        if not any(s.startswith(kern) or (len(s) >= 4 and t.startswith(s) and len(t) - len(s) <= 2) for s in staemme):
            return False
    return True


@dataclass(frozen=True)
class Befund:
    satz: str
    zahlen: tuple[str, ...]
    namen: tuple[str, ...]
    verdacht: tuple[str, ...]
    regel: tuple[str, ...] = ()

    @property
    def sicher_falsch(self) -> bool:
        return bool(self.zahlen or self.namen or self.regel)


_JAHR_IM_TEXT = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")
_FUELLWORT = set("""dass sich wird wurde wurden worden haben hatte hatten sein sind waren eine einer einem einen eines dieser diese dieses
nicht auch noch schon nach über unter durch gegen ohne wieder sowie oder aber denn weil wenn als wie dann damit dabei dazu davon heute jahr jahre
jahren erst mehr sehr""".split())


def _inhaltsstaemme(text: str) -> set[str]:
    return {w.lower()[:6] for w, _ in _tokens(text) if len(w) >= 4 and w.lower() not in _FUELLWORT and w.lower() not in _KEIN_NAME}


def jahre_anderswo(satz: str, quellsaetze: list[str]) -> list[str]:
    jahre = set(_JAHR_IM_TEXT.findall(satz))
    if not jahre:
        return []
    w = _inhaltsstaemme(_JAHR_IM_TEXT.sub(" ", satz))
    bewertet = [(len(w & _inhaltsstaemme(q)), set(_JAHR_IM_TEXT.findall(q))) for q in quellsaetze]
    out = []
    for j in sorted(jahre):
        mit = max((n for n, js in bewertet if j in js), default=-1)
        ohne = max((n for n, js in bewertet if js and j not in js), default=0)
        if mit >= 0 and ohne >= 2 and ohne > mit:
            out.append(j)
    return out


_ENDUNG_WEB = frozenset("com org net info gov edu int eu app dev io biz online site travel uk".split())
_ADRESSE = re.compile(r"(?i)(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+([a-z]{2,6}))(?![\w-])")


_LINK = re.compile(r"https?://[^\s<>\"“”„()\[\]]+", re.I)


def links_in(satz: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).rstrip(".,;:!?»'’") for m in _LINK.finditer(satz or "")))


def link_norm(adresse: str) -> str:
    import html as _html
    import urllib.parse as _up
    u = _up.unquote(_html.unescape(str(adresse or ""))).strip().rstrip("/.,;:!?»'’").lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^(?:www|m)\.", "", u)
    m = re.match(r"youtu\.be/([\w-]+)", u) or re.match(r"youtube\.com/watch\?(?:[^#]*&)?v=([\w-]+)", u)
    return f"youtube.com/watch?v={m.group(1)}" if m else u


def adressen_in(satz: str) -> list[str]:
    out = []
    for m in _ADRESSE.finditer(satz or ""):
        endung = m.group(2).lower()
        host = m.group(1).lower()
        host = host[4:] if host.startswith("www.") else host
        if (endung in _ENDUNG_WEB or endung.upper() in laender.DEUTSCH) and "." in host and len(host.split(".")[-2]) >= 2:
            out.append(host)
    return list(dict.fromkeys(out))


def streng_pruefen(antwort: str, belege: str, *, zahlen_pruefen: bool = True, namen_pruefen=None, regel_frage: str = "",
                   regel_quellen: list[str] | None = None, ableitung: bool = False) -> list[Befund]:
    regel_raus = dict(regel_ungestuetzt(antwort, regel_frage, list(regel_quellen or []))) if regel_frage else {}
    belege_klein = (belege or "").lower()
    belegt_d = daten(belege)
    belegt_z = zahlenwerte(belege)
    belegt_e = einheiten_werte(belege)
    staemme = _wortstaemme(belege)
    quell_laender = laender_in(belege)
    quell_links = {link_norm(u) for u in links_in(belege)}

    def land_belegt(name: str) -> bool:
        c = laender_in(name)
        return bool(c) and c <= quell_laender
    quellsaetze = [q for zeile in (belege or "").split("\n") for q in _saetze(zeile)] if zahlen_pruefen else []
    out: list[Befund] = []
    for absatz in (antwort or "").split("\n"):
        for s in _saetze(absatz):
            if s.rstrip().endswith("?"):
                continue
            z = [f"{d[0]}.{d[1]}." + (str(d[2]) if d[2] else "") for d in daten(s) if not _gedeckt_datum(d, belegt_d)]
            if zahlen_pruefen:
                ohne_daten = _DATUM_ISO.sub(" ", _DATUM_WORT.sub(" ", _DATUM_ZAHL.sub(" ", s)))
                z += unbelegte_zahlen(ohne_daten, belegt_z, ableitung, belegt_e)
                z += [j for j in jahre_anderswo(s, quellsaetze) if j not in z]
            pruefe_namen = namen_pruefen is None or namen_pruefen(s)
            sicher, lauf = namen(s) if pruefe_namen else ([], [])
            n = [x for x in sicher if not name_belegt(x, staemme) and not land_belegt(x)]
            v = [x for x in lauf if not name_belegt(x, staemme) and not land_belegt(x)]
            belegte_hosts = set(adressen_in(" ".join(u for u in links_in(s) if link_norm(u) in quell_links)))
            if pruefe_namen:
                n += [x for x in adressen_in(s) if x not in belege_klein and x not in belegte_hosts]
            n += [u for u in links_in(s) if link_norm(u) not in quell_links and u not in n]
            r = regel_raus.get(s, ())
            if z or n or v or r:
                out.append(Befund(s, tuple(z), tuple(n), tuple(v), tuple(r)))
    return out


PRUEFER_SYSTEM = ("Du bekommst eine nummerierte Liste von Wörtern. Sag zu jedem Wort, ob es ein Eigenname ist (der Name einer bestimmten Person, "
                  "eines Ortes, einer Firma, einer Marke, eines Produkts, eines Vereins, einer Behörde oder eines Gesetzes) oder ein gewöhnliches Wort "
                  "der Sprache, das man im Wörterbuch findet. Antworte nur mit einer Zeile je Wort: die Nummer, dann Name oder Wort, zum Beispiel „1 Wort“. "
                  "Keine Erklärung.")


UMSCHREIBEN_DE = ("Schreib jeden nummerierten Satz in eigenen Worten neu: dieselbe Aussage, nichts dazu, nichts weg. Zahlen, Daten, Beträge und "
                  "Namen bleiben genau gleich. Ändere Satzbau und Wörter so, dass nie mehr als 6 Wörter am Stück wie im Original stehen. Antworte nur "
                  "mit einer Zeile je Satz: die Nummer, dann der neue Satz.")
UMSCHREIBEN_EN = ("Rewrite each numbered sentence in your own words: same statement, nothing added, nothing left out. Keep numbers, dates, amounts "
                  "and names exactly. Change the wording and sentence structure so that never more than 6 words in a row match the original. Answer "
                  "only with one line per sentence: the number, then the new sentence.")
WEISS_NICHT_EN = "I don't know that yet."
WEISS_NICHT_DE = "Das weiß ich noch nicht."


def weiss_nicht_satz() -> str:
    import pruefung
    return WEISS_NICHT_EN if pruefung.englisch() else WEISS_NICHT_DE


def pruefer_auftrag(woerter: list[str]) -> str:
    return "Wörter:\n" + "\n".join(f"{i + 1}. {' '.join(w.split())}" for i, w in enumerate(woerter))


def urteil_lesen(text: str, anzahl: int) -> set[int]:
    name: set[int] = set()
    for m in re.finditer(r"(?m)^\s*(\d{1,2})\s*[.):]?\s*[-–:]?\s*((?:eigen)?name|wort)\b", text or "", re.I):
        i = int(m.group(1)) - 1
        if 0 <= i < anzahl and m.group(2).lower() != "wort":
            name.add(i)
    return name


RICHTER_AUFTRAG = ("Prüfe die Aussage unten gegen die Auszüge oben. Antworte mit genau einem Wort: „ja“, wenn die Aussage mit allen Zahlen, Daten "
                   "und Namen so in einem Auszug steht; „nein“, wenn ein Auszug etwas anderes sagt oder eine Zahl, ein Datum oder ein Name dort anders "
                   "oder gar nicht steht; „allgemein“, wenn die Aussage Allgemeinwissen ohne bestimmte Zahl ist, das in keinem Auszug stehen muss.\n\nAussage:")


def richter_wert(text: str) -> float | None:
    w = re.findall(r"[a-zäöüß]+", (text or "").lower())
    if not w:
        return None
    return {"ja": 1.0, "allgemein": 0.5, "nein": 0.0}.get(w[0])


_TRENNER = re.compile(r"^\s*[-–—*_=]{3,}\s*$")
_ZAHLENFRAGE = re.compile(r"(?i)\b(?:wie ?viel\w*|wie hoch|wie groß|wie lang\w*|wie weit|wie alt|wie schwer|wie schnell|wie oft|wie tief|wann|"
                          r"seit wann|bis wann|was kostet|kostet|einwohner\w*|bevölkerung|preis\w*|höhe|länge|fläche|entfernung|anzahl|prozent|"
                          r"gehalt|lohn|temperatur|umsatz|gewicht|"
                          r"how (?:many|much|high|tall|big|large|long|far|old|heavy|fast|often|deep|wide)|when|since when|until when|"
                          r"what does .{1,40} cost|cost of|population|prices?|height|length|area|distance|number of|percent(?:age)?|"
                          r"salary|wages?|temperature|revenue|weight)\b")


def zahlenfrage(frage: str) -> bool:
    return bool(_ZAHLENFRAGE.search(frage or ""))


def _inhalt(zeile: str) -> bool:
    z = zeile.strip()
    return bool(z) and not _TRENNER.match(z) and not z.endswith(":") and len(_WORT_TOKEN.findall(z)) >= 2


def geruest_bereinigen(text: str) -> str:
    zeilen = (text or "").split("\n")
    out: list[str] = []
    for i, z in enumerate(zeilen):
        s = z.strip()
        if not s:
            out.append("")
            continue
        if _TRENNER.match(s):
            continue
        if s.endswith(":") and not _inhalt(s):
            folgt = next((w.strip() for w in zeilen[i + 1:] if w.strip() and not _TRENNER.match(w.strip())), "")
            if not folgt or folgt.endswith(":"):
                continue
        out.append(z)
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return rest if any(_inhalt(z) for z in rest.split("\n")) else ""


_ZEILE_ANFANG = re.compile(r"^\s*(?:[-–•*]\s+|\d|[A-ZÄÖÜ„“\"'«»(]|\d+\.\s)")
_ZEILE_FALSCH = re.compile(r"^\s*(?:[),;:.!?]|und\b|oder\b|aber\b|sowie\b|sondern\b|denn\b|weil\b|dass\b|[a-zäöüß])")
_KLAMMERN = (("(", ")"), ("[", "]"), ("„", "“"))
_KLAMMERN_EN = (("(", ")"), ("[", "]"), ("“", "”"))
_MD_ANFANG = re.compile(r"^(?:#{1,6}\s+|>\s*)?(?:\*\*|__)?")
_TRENNZEILE = re.compile(r"[-–—_*=:|\s]{3,}")
_KLEIN_NACH_SATZ = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}[.!?]\s+[a-zäöüß]")


def brauchbar(text: str) -> bool:
    import pruefung
    zeilen = [z for z in (text or "").split("\n") if z.strip()]
    if not zeilen:
        return False
    paare = _KLAMMERN_EN if pruefung.englisch() else _KLAMMERN
    worte = []
    for z in zeilen:
        s = z.strip()
        if s.startswith("|") or _TRENNZEILE.fullmatch(s):
            continue
        s = _MD_ANFANG.sub("", s).strip()
        worte.append(s)
        if not s:
            continue
        if _ZEILE_FALSCH.match(s) or not (_ZEILE_ANFANG.match(s) or not re.match(r"[\wÄÖÜäöüß]", s)):
            return False
        for auf, zu in paare:
            if s.count(auf) != s.count(zu):
                return False
        if _KLEIN_NACH_SATZ.search(s):
            return False
        for satz in _saetze(s)[1:]:
            if _ZEILE_FALSCH.match(satz):
                return False
    tabelle = any(z.strip().startswith("|") for z in zeilen)
    return tabelle or any(len(re.sub(r"^\s*[-–•*]\s+", "", z).split()) >= 3 for z in worte)


WOERTLICH_WOERTER = antwortspeicher_basis.WOERTLICH_WOERTER
WORTLAUT_FREI = antwortspeicher_basis.FREI_ARTEN
_wortliste = antwortspeicher_basis.wortliste
_LINK_MIT_TITEL = re.compile(r"https?://[^\s<>\"“”„()\[\]]+(?:\s*[–—:-]\s*[„\"“][^“\"”\n]{0,200}[“\"”])?", re.I)


def fremde_texte(quellen) -> list[str]:
    return [str(q.get("text") or "") for q in (quellen or []) if isinstance(q, dict) and q.get("art") not in WORTLAUT_FREI and q.get("text")]


def woertliche_saetze(antwort: str, fremd: list[str], n: int = WOERTLICH_WOERTER) -> list[str]:
    stuecke: set[tuple[str, ...]] = set()
    for t in fremd:
        w = _wortliste(t)
        stuecke.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    if not stuecke:
        return []
    saetze = [s for absatz in (antwort or "").split("\n") for s in _saetze(absatz)]
    woerter: list[str] = []
    satz_von: list[int] = []
    for k, s in enumerate(saetze):
        w = _wortliste(_LINK_MIT_TITEL.sub(" ", s))
        woerter += w
        satz_von += [k] * len(w)
    laenge = [satz_von.count(k) for k in range(len(saetze))]
    treffer: set[int] = set()
    for i in range(len(woerter) - n + 1):
        if tuple(woerter[i:i + n]) in stuecke:
            for k in set(satz_von[i:i + n]):
                drin = satz_von[i:i + n].count(k)
                if drin >= 5 or drin == laenge[k]:
                    treffer.add(k)
    return [saetze[k] for k in sorted(treffer)]


_RUECKBEZUG = re.compile(r"^\s*(?:oder|aber|und|dann|dabei|dadurch|damit|dazu|daher|darum|deshalb|deswegen|dort|dies|diese[rsmn]?|"
                         r"also|trotzdem|außerdem|ebenso|auch|stattdessen|dafür|dagegen)\b", re.I)
_LISTENPUNKT = re.compile(r"^\s*(?:[-–•*]\s+|\d{1,2}[.)]\s+)")
_NUMMER = re.compile(r"^(\s*)(\d{1,2})([.)]\s+)")


def _neu_nummeriert(zeilen: list[str]) -> list[str]:
    out, n = [], 0
    for z in zeilen:
        m = _NUMMER.match(z)
        if m:
            n += 1
            z = f"{m.group(1)}{n}{m.group(3)}{z[m.end():]}"
        elif z.strip() and not _LISTENPUNKT.match(z):
            n = 0
        out.append(z)
    return out


def saetze_streichen(antwort: str, weg, *, mitnehmen: bool = False) -> tuple[str, list[str]]:
    raus: list[str] = []
    absaetze = []
    zeilen = (antwort or "").split("\n")
    weg_zeile: set[int] = set()
    for i, absatz in enumerate(zeilen):
        bleiben = []
        davor_weg = False
        for s in _saetze(absatz):
            if weg(s) or (mitnehmen and davor_weg and _RUECKBEZUG.match(s)):
                raus.append(s)
                davor_weg = True
            else:
                bleiben.append(s)
                davor_weg = False
        marke = _LISTENPUNKT.match(absatz)
        if marke and bleiben and not _LISTENPUNKT.match(bleiben[0]):
            bleiben[0] = marke.group(0) + bleiben[0]
        if bleiben or not absatz.strip():
            absaetze.append(" ".join(bleiben))
        else:
            weg_zeile.add(i)
            absaetze.append(None)
    for i, z in enumerate(zeilen):
        if absaetze[i] and absaetze[i].rstrip().endswith(":"):
            folge = [j for j in range(i + 1, len(zeilen)) if zeilen[j].strip()]
            liste = []
            for j in folge:
                if not _LISTENPUNKT.match(zeilen[j]):
                    break
                liste.append(j)
            if liste and all(j in weg_zeile for j in liste):
                raus.append(absaetze[i])
                absaetze[i] = None
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(_neu_nummeriert([a for a in absaetze if a is not None]))).strip()
    if raus:
        rest = geruest_bereinigen(rest)
    if raus and not rest:
        rest = weiss_nicht_satz()
    return rest, raus


def vergangene_streichen(antwort: str, heute: date) -> tuple[str, list[str]]:
    def vorbei(s: str) -> bool:
        tage = []
        for t, m, j in daten(s):
            try:
                tage.append(date(j or _jahr_fuer(t, m, heute), m, t))
            except ValueError:
                continue
        return bool(tage) and all(d < heute for d in tage)
    return saetze_streichen(antwort, vorbei)


def _jahr_fuer(tag: int, monat: int, heute: date) -> int:
    best = heute.year
    for j in (heute.year - 1, heute.year, heute.year + 1):
        try:
            if abs((date(j, monat, tag) - heute).days) < abs((date(best, monat, tag) - heute).days):
                best = j
        except ValueError:
            continue
    return best


def wochentage_berichtigen(text: str, heute: date) -> tuple[str, int]:
    n = 0

    def ersetzen(m: re.Match) -> str:
        nonlocal n
        wort, punkt, zwischen, datum_text = m.group(1), m.group(2), m.group(3), m.group(4)
        ds = daten(datum_text)
        if len(ds) != 1:
            return m.group(0)
        t, mo, j = next(iter(ds))
        try:
            d = date(j or _jahr_fuer(t, mo, heute), mo, t)
        except ValueError:
            return m.group(0)
        kurz = wort[:2].capitalize() in KURZ and len(wort) <= 2
        richtig = KURZ[d.weekday()] if kurz else WOCHENTAGE[d.weekday()]
        if richtig.lower() == wort.lower():
            return m.group(0)
        n += 1
        return richtig + punkt + zwischen + datum_text

    def ersetzen_satz(m: re.Match) -> str:
        nonlocal n
        ds = daten(m.group(1))
        if len(ds) != 1:
            return m.group(0)
        t, mo, j = next(iter(ds))
        if j is None and m.group(2).lower() == "war":
            return m.group(0)
        try:
            richtig = WOCHENTAGE[date(j or _jahr_fuer(t, mo, heute), mo, t).weekday()]
        except ValueError:
            return m.group(0)
        if richtig.lower() == m.group(3).lower():
            return m.group(0)
        n += 1
        return m.group(0)[:m.start(3) - m.start(0)] + richtig + m.group(0)[m.end(3) - m.start(0):]

    t = _WOCHENTAG_DATUM.sub(ersetzen, text or "")
    return _DATUM_WOCHENTAG.sub(ersetzen_satz, t), n


_DATUM_WOCHENTAG = re.compile(rf"(?i)\b(\d{{1,2}}\.\s*(?:\d{{1,2}}\.|(?:{_MONAT})\.?)(?:\s*\d{{4}})?)\s+(ist|fällt\s+auf|war)\s+(?:ein(?:em|en)?\s+)?"
                              rf"({'|'.join(WOCHENTAGE)})\b")


_PLATZHALTER = re.compile(r"\[(?!\d)(?!Quelle)[^\[\]\n]{1,40}\]")
_GRUSS_LUECKE = re.compile(r"(?:(?<=\s)|^)(?:dein|deine|ihr|ihre|euer|eure|von)\s*,?\s*\[[^\[\]\n]{1,40}\]\s*[!.,]?", re.I | re.M)
_ANREDE_LUECKE = re.compile(r"\b(Liebe|Lieber|Hallo|Hi|Servus|Sehr geehrte[r]?)\s*\[[^\[\]\n]{1,40}\]", re.I)
_NUR_GRUSSWORT = re.compile(r"^\s*(?:dein|deine|ihr|ihre|euer|eure|von)\s*[,!.]?\s*$", re.I)


_SELBSTBEZUG = re.compile(r"falsche[nr]? Angabe von mir|ich korrigiere|korrigiere ich|berichtige ich|meine[nr]? (vorige|vorherige|erste|frühere)[nr]? "
                          r"(Antwort|Angabe|Fassung)|(vorige|vorherige)[nr]? Antwort|erste[nr]? Fassung|Entschuldigung|entschuldige|mein Fehler|"
                          r"ich habe mich (geirrt|vertan)|Korrektur:"
                          r"|\bmy (?:previous|earlier|first) (?:answer|reply|statement|version)\b|\b(?:previous|earlier) answer\b|\bfirst version\b"
                          r"|\bI apologi[sz]e\b|\bapologies\b|\bmy mistake\b|\bI was wrong\b|\bI(?:'| a)m correcting\b|\bCorrection:", re.I)
_KLAMMER_SELBST = re.compile(r"\(\s*[^()]{0,200}?\)")


def ohne_selbstbezug(text: str) -> tuple[str, int]:
    n = 0

    def klammer(m: "re.Match[str]") -> str:
        nonlocal n
        if _SELBSTBEZUG.search(m.group(0)):
            n += 1
            return ""
        return m.group(0)
    t = _KLAMMER_SELBST.sub(klammer, text or "")
    t, raus = saetze_streichen(t, lambda s: bool(_SELBSTBEZUG.search(s)))
    n += len(raus)
    if not n:
        return text or "", 0
    return re.sub(r"[ \t]{2,}", " ", t).strip() or weiss_nicht_satz(), n


def ohne_platzhalter(text: str) -> tuple[str, int]:
    t = text or ""
    n = len(_PLATZHALTER.findall(t))
    if not n:
        return t, 0
    t = _GRUSS_LUECKE.sub("", t)
    t = _ANREDE_LUECKE.sub(lambda m: "Guten Tag" if m.group(1).lower().startswith("sehr") else "Hallo", t)
    t = _PLATZHALTER.sub("", t)
    zeilen = [z for z in t.split("\n") if not _NUR_GRUSSWORT.match(z)]
    t = "\n".join(re.sub(r"[ \t]{2,}", " ", re.sub(r"\s+([,.!?])", r"\1", z)).rstrip() for z in zeilen)
    return re.sub(r"\n{3,}", "\n\n", t).strip(), n


_PRUEFEN_FRAGE = re.compile(r"\bwann\b|\bkoste\w*|\bpreis\w*|\bwie (?:viel|hoch|teuer)\b|\bgebühr\w*|\btarif\w*|\bzins\w*|\bspiel\w*|\btermin\w*|"
                            r"\bdatum\b|\bab wann\b|\bbis wann\b|\bgeöffnet\b|\bgeoeffnet\b|\böffnungszeit\w*", re.I)


def pruefen_noetig(frage: str, zeitgebunden: bool) -> bool:
    return zeitgebunden or bool(_PRUEFEN_FRAGE.search(frage or ""))


_RECHNET = re.compile(r"(?i)\bzu je\b|\bje\b|\bmal\b|\d\s*[×x*+/−-]\s*\d|\bzusammen\b|\binsgesamt\b|\bsumme\b|\bprozent von\b|%\s*von|\brabatt\b|was kostet das")
_NAME_ZAHL = re.compile(r"(?<=[A-Za-zÄÖÜäöüß])-\d+\b")
_JAHR_SCHRAEG = re.compile(r"\b(1\d{3}|20\d{2})/(\d+)\b")


def _ohne_code_zahlen(frage: str) -> str:
    def code(m: re.Match) -> str:
        jahr, rest = m.group(1), m.group(2)
        if len(rest) >= 4 or (len(rest) == 2 and int(rest) == (int(jahr) + 1) % 100):
            return " "
        return m.group(0)
    return _JAHR_SCHRAEG.sub(code, _NAME_ZAHL.sub(" ", _REIFENGROESSE.sub(" ", frage or "")))


_REIFENGROESSE = re.compile(r"(?i)\b\d{2,3}/\d{2}\s*(?:Z?R|-)\s*\d{2}(?:[.,]\d)?\b")
_RECHNET_ZWEI = re.compile(r"(?i)\bplus\b|\bminus\b|\bweniger\b|\babzüglich\b|\bzuzüglich\b|\bgeteilt\b|\bdurch\s+\d|\bprozent\b|\bpercent\b|%|\bzinsen\b|"
                           r"\binterest\b|\btrinkgeld\b|\btip\b|\bnetto\b|\bbrutto\b|\bmwst\b|\bvat\b|\bzwischen\s+\d[\d.,]*\s+und\s+\d|"
                           r"\bbetween\s+\d[\d.,]*\s+and\s+\d|\bliter\w*\s+auf\s+100\b|\blit(?:er|re)s?\s+per\s+100\b|\bquadratmeter\b|\bsquare met(?:er|re)s?\b")
_JAHRESZAHL = re.compile(r"1[0-9]{3}|20[0-9]{2}")
_RECHENZEICHEN = re.compile(r"(?i)\d\s*(?:[+×*/−]|-(?=\s*\d)|\bplus\b|\bminus\b|\bmal\b|\bgeteilt durch\b|\bdurch\b|\btimes\b|\bdivided by\b)\s*\d")
_MASS = (r"(?:zenti|milli|kilo)?meter|(?:milli)?liter|(?:kilo)?gramm|minuten|stunden|sekunden|tage|wochen|monate|jahre|cm|mm|km|kg|ml|"
         r"inch(?:es)?|feet|foot|cups?|ounces?|pounds?|gallons?|miles?|yards?|(?:centi|milli|kilo)?met(?:er|re)s?|(?:milli|centi|deci)?lit(?:er|re)s?|(?:kilo)?grams?|"
         r"minutes|hours|seconds|days|weeks|months|years")
_MASS_UM = _MASS + r"|fu[ßs]|zoll|meilen?|hektar"
_UMRECHNEN = re.compile(rf"(?i)\bumrechn|\bconvert|\bwie viele?\s+(?:{_MASS})\s+(?:sind|ergeben|macht|machen|hat|haben|liegen)\b|"
                        rf"\bwie viele?\s+(?:sind|ist|ergeben|ergibt|macht|machen)\s+[\d.,]+\s*(?:{_MASS_UM})\w*(?:\s+[\d.,]+\s*(?:{_MASS_UM})\w*)?\s+in\s+(?:{_MASS_UM})\w*|"
                        rf"\bhow many\s+(?:{_MASS})\s+(?:are|is|make|in)\b")
_ZAHL_MIT_EINHEIT = re.compile(rf"(?i)\d[\d.,]*\s*(?:{_MASS_UM}|m|l|g|mg|dl|ha|lbs?|oz|ft|st|stones?|kcal|kwh|mph|km/h|°\s*[cf]|m²|km²)\b")


_PREISFRAGE = re.compile(r"(?i)\b(?:was kostet|kostet|kosten|preis\w*|gebühr\w*|maut\w*|vignette\w*|tarif\w*|ticket\w*|eintritt\w*|"
                         r"how much (?:is|does|do|are|will)|costs?|price\w*|fees?|tolls?)\b")


_GELDBETRAG = re.compile(r"(?i)[€$£]\s*\d|\d[\d.,]*\s*(?:€|\$|£|euros?\b|eur\b|cents?\b|dollars?\b|usd\b|pounds?\b|pfund\b|gbp\b|franken\b|chf\b|yen\b|kronen?\b|"
                         r"zloty\b|forint\b)")
_WAEHRUNG = re.compile(r"(?i)\b(euros?|eur|dollars?|usd|pounds?|pfund|gbp|franken|chf|yen|kronen?|zloty|forint|lira|rupees?|pesos?|yuan|renminbi)\b|[€$£]")
_WAEHRUNG_GLEICH = {"€": "euro", "euros": "euro", "eur": "euro", "$": "dollar", "dollars": "dollar", "usd": "dollar", "£": "pound", "pounds": "pound",
                    "pfund": "pound", "gbp": "pound", "chf": "franken", "kronen": "krone", "rupees": "rupee", "pesos": "peso", "renminbi": "yuan"}


def rechenaufgabe(frage: str) -> bool:
    if not rechnet(frage):
        return False
    f = _ohne_code_zahlen(frage)
    if _PREISFRAGE.search(f) and not _GELDBETRAG.search(f):
        return False
    if len({_WAEHRUNG_GLEICH.get(w.lower(), w.lower()) for w in _WAEHRUNG.findall(f) if w} | {_WAEHRUNG_GLEICH.get(s, s) for s in re.findall(r"[€$£]", f)}) >= 2:
        return False
    zahlen = [z for z in _ZAHL.findall(f) if not _JAHRESZAHL.fullmatch(z)]
    alle = _ZAHL.findall(f)
    return len(zahlen) >= 2 or bool(_RECHENZEICHEN.search(f) or (_UMRECHNEN.search(f) and (_ZAHL_MIT_EINHEIT.search(f) or len(alle) >= 2)))


def preisfrage(frage: str) -> bool:
    return bool(_PREISFRAGE.search(frage or "")) and not rechnet(frage)


_VERGLEICH = re.compile(r"(?i)\b(?:günstigst\w*|guenstigst\w*|billigst\w*|preisvergleich\w*|preise?\s+vergleich\w*|vergleich\w*\s+(?:\S+\s+){0,3}?preise?\b|"
                        r"bester?n?\s+preis\w*|günstiger\w*\s+(?:anbieter|angebot|shop|händler|haendler)|billiger\w*\s+(?:anbieter|angebot|shop|händler)|"
                        r"wo\s+(?:\S+\s+){0,6}?(?:am\s+)?(?:günstigsten|billigsten)|cheapest|best\s+price|lowest\s+price|compare\s+prices|price\s+comparison|"
                        r"cheaper\s+(?:offer|deal|quote|shop|seller))")


def vergleichsfrage(frage: str) -> bool:
    return bool(_VERGLEICH.search(frage or ""))


_REGEL_WORT = re.compile(r"(?i)\b(?:\w*pflicht\w*|vorgeschrieben\w*|gesetzlich\w*|verordnung\w*|erlaubt|verboten|strafe\w*|bu[ßs]geld\w*|"
                         r"\w*frist(?!ig)\w*|mindestalter|altersgrenze|\w*vignette\w*|\w*maut\w*|\w*pickerl\w*|t[üu]v|hauptuntersuchung|"
                         r"\w*tempolimit\w*|\w*höchstgeschwindigkeit\w*|"
                         r"mandatory|required by law|is it legal|legally|illegal|penalt\w+|speed limit\w*|minimum age|"
                         r"visum|visa|visas|\w*einreise\w*|esta|aufenthaltstitel|aufenthaltsgenehmigung|\w*reisepass\w*|passport\w*|"
                         r"entry requirements?|travel authori[sz]ation|work permit|residence permit|"
                         r"by law|compulsory|notice period|blood alcohol|drink[- ]driving|public holidays?|bank holidays?|legal (?:age|limit|requirement)s?|"
                         r"allowed|forbidden|prohibited|deadline)\b")
_REGEL_GESETZ = re.compile(r"(?i)\b(?!natur|gesetzmäßig)\w*gesetz\w*\b")
_KEIN_RECHT = re.compile(r"(?i)\b(?:ohm\w*|newton\w*|kepler\w*|gravitation\w*|fallgesetz\w*|hebelgesetz\w*|energieerhaltung\w*|mendel\w*|murphy\w*|moore\w*|"
                         r"physik\w*|chemie\w*|chemisch\w*|mathemati\w*|naturwissenschaft\w*|thermodynami\w*|elektri\w*|strom|spannung|widerstand)\b")
_REGEL_KEINE = re.compile(r"(?i)^\s*(?:was (?:muss|soll|sollte|müssen|sollten|kann) (?:ich|man|wir)\b.*\b(?:essen|trinken|probieren|sehen|anschauen|"
                          r"besichtigen|besuchen|erleben|unternehmen)|what (?:must|should|can) (?:i|we|one)\b.*\b(?:eat|drink|try|see|visit|do))\b")
_REGEL_VERKEHR = re.compile(r"(?i)\b(?:fahren|f[äa]hrt|parken|überholen|ueberholen|ortsgebiet\w*|autobahn\w*|freiland\w*|schnellstra[ßs]e\w*|radweg\w*|"
                            r"gehsteig\w*|führerschein\w*|fuehrerschein\w*|kindersitz\w*|gurt\w*|alkohol am steuer|promille|"
                            r"drive|driving|motorways?|highways?|parking|overtak\w+|driving licen[cs]e|seat ?belts?|child seats?)\b")
_REGEL_MODAL = re.compile(r"(?i)\b(?:muss ich|muss man|müssen wir|darf ich|darf man|dürfen wir|ab wann|bis wann|ab welchem alter|"
                          r"mindestens|"
                          r"brauch(?:e|st|t|en)|benötig(?:e|st|t|en)|kann ich|kann man|"
                          r"do i (?:have|need) to|needs?|must|am i allowed|can i|from what age|"
                          r"may (?:i|you|one|we)|are you allowed|is it allowed|have to|do you need|how fast may)\b")
_REGEL_STELLE = re.compile(r"(?i)\b(?:eu|behörde\w*|polizei)\b")


def regelfrage(frage: str) -> bool:
    f = frage or ""
    if _REGEL_WORT.search(f):
        return True
    modal, land = _REGEL_MODAL.search(f), (_REGEL_STELLE.search(f) or laender_in(f))
    if _REGEL_GESETZ.search(f) and not _KEIN_RECHT.search(f):
        return True
    if modal and _REGEL_VERKEHR.search(f):
        return True
    return bool(modal and land and not _REGEL_KEINE.search(f))


_LAND_DAZU = {
    "AT": re.compile(r"(?i)\b(?:österreich\w*|austria\w*|wien|oberösterreich|niederösterreich|steiermark|tirol|kärnten|vorarlberg|burgenland)\b"),
    "DE": re.compile(r"(?i)\b(?:deutschland|bundesrepublik|germany|german|niedersachsen|nordrhein-westfalen|hessen|sachsen|thüringen|brandenburg|"
                     r"mecklenburg-vorpommern|schleswig-holstein|rheinland-pfalz|saarland|baden-württemberg|bayern|berlin|hamburg)\b"),
    "CH": re.compile(r"(?i)\b(?:schweiz\w*|switzerland|swiss|eidgenoss\w*)\b"),
    "GB": re.compile(r"(?i)\b(?:united kingdom|großbritannien|grossbritannien|england|scotland|schottland|wales|britain|british|britisch\w*)\b|\bUK\b"),
    "US": re.compile(r"(?i)\b(?:united states|vereinigte\w* staaten|amerika\w*|america\w*)\b|\bUSA\b|\bU\.S\.|(?-i:\bUS\b)"),
    "IE": re.compile(r"(?i)\b(?:irland|ireland|irish|irisch\w*)\b"),
    "FR": re.compile(r"(?i)\b(?:frankreich|france|französisch\w*|french)\b"),
    "IT": re.compile(r"(?i)\b(?:italien\w*|italy|italian)\b"),
    "ES": re.compile(r"(?i)\b(?:spanien|spain|spanisch\w*|spanish)\b"),
    "NL": re.compile(r"(?i)\b(?:niederlande|netherlands|holland|niederländisch\w*|dutch)\b"),
    "CA": re.compile(r"(?i)\b(?:kanada|canada|kanadisch\w*|canadian)\b"),
    "AU": re.compile(r"(?i)\b(?:australien|australia\w*)\b"),
    "HU": re.compile(r"(?i)\b(?:ungarn|ungarisch\w*|hungary|hungarian)\b"),
    "CZ": re.compile(r"(?i)\b(?:tschechi\w*|czech\w*)\b"),
    "SK": re.compile(r"(?i)\b(?:slowak\w*|slovak\w*)\b"),
    "PL": re.compile(r"(?i)\b(?:polen|polnisch\w*|poland|(?-i:Polish))\b"),
    "SI": re.compile(r"(?i)\b(?:slowen\w*|sloven\w*)\b"),
    "HR": re.compile(r"(?i)\b(?:kroati\w*|croatia\w*)\b"),
}
_ENDUNG_ALLGEMEIN = frozenset("ad ai as bz cc cd co dj fm io la me ms nu sc sr su tv tk ws".split())


def laender_in(text: str) -> set[str]:
    t = text or ""
    return laender.alle(t) | {k for k, m in _LAND_DAZU.items() if m.search(t)}


def gefragtes_land(frage: str) -> str:
    genannt = laender_in(frage)
    return next(iter(genannt)).lower() if len(genannt) == 1 else ""


def land_der_adresse(adresse: str) -> str:
    host = re.sub(r"^[a-z]+://", "", str(adresse or "").lower()).split("/", 1)[0].split(":", 1)[0]
    endung = host.rsplit(".", 1)[-1] if "." in host else ""
    if endung == "uk":
        return "gb"
    return endung if len(endung) == 2 and endung not in _ENDUNG_ALLGEMEIN and endung.upper() in laender.DEUTSCH else ""


def fremdes_land_weg(frage: str, treffer: list) -> tuple[list, int]:
    gefragt = {c.lower() for c in laender_in(frage)}
    if not gefragt:
        return treffer, 0
    behalten = []
    for t in treffer:
        genannt = {c.lower() for c in laender_in(f"{t.quelle.titel}\n{t.text}")}
        if genannt & gefragt:
            behalten.append(t)
        elif genannt:
            continue
        elif land_der_adresse(t.quelle.adresse) not in ("", *gefragt):
            continue
        else:
            behalten.append(t)
    return behalten, len(treffer) - len(behalten)


_GEGENSTAND = (
    ("Visum", r"\w*visum\w*|visa|visas|visa-free|visafree|\w+visa"),
    ("ESTA", r"esta"),
    ("ETA", r"etas?|e-tas?|electronic travel authori[sz]ations?|travel authori[sz]ations?|\w*reisegenehmigung\w*"),
    ("ETIAS", r"etias"),
    ("Reisepass", r"\w*reisepass\w*|pass|passes|pässe|passports?|passport-\w+"),
    ("Personalausweis", r"\w*personalausweis\w*|identitätskarte\w*|identity cards?|id cards?|national id cards?"),
    ("Führerschein", r"\w*führerschein\w*|\w*fuehrerschein\w*|lenkberechtigung\w*|driving licen[cs]es?|driver'?s licen[cs]es?|driving permits?|idp"),
    ("Vignette", r"\w*vignette\w*|\w*pickerl\w*"),
    ("Maut", r"\w*maut\w*|tolls?|toll roads?"),
    ("Winterreifen", r"\w*winterreifen\w*|schneeketten|winter tyres?|winter tires?|snow tyres?|snow tires?|snow chains?"),
    ("Versicherung", r"\w*versicherung\w*|\w*insurance"),
    ("Impfung", r"\w*impfung\w*|\w*impfpflicht\w*|geimpft|vaccinations?|vaccinated|vaccines?"),
    ("Arbeitserlaubnis", r"\w*arbeitserlaubnis\w*|\w*arbeitsgenehmigung\w*|work permits?|work visas?"),
    ("Aufenthaltstitel", r"\w*aufenthaltstitel\w*|\w*aufenthaltsgenehmigung\w*|residence permits?"),
    ("Helm", r"\w*helm|\w*helme|\w*helmpflicht|helmets?"),
    ("Gurt", r"\w*gurt|\w*gurte|\w*gurtpflicht|\w*sicherheitsgurt\w*|seat ?belts?"),
    ("Kindersitz", r"\w*kindersitz\w*|child (?:car )?seats?|car seats?"),
    ("Tempolimit", r"\w*tempolimit\w*|\w*höchstgeschwindigkeit\w*|speed limits?"),
    ("Alkohol", r"\w*alkohol\w*|promille|alcohol|blood alcohol"),
    ("Zoll", r"\w*zoll\w*|customs|duty-free|duties"),
    ("Mindestalter", r"mindestalter|altersgrenze|minimum age|age limit"),
)
_GEGENSTAND_RE = [(name, re.compile(rf"(?i)(?<![\wÄÖÜäöüß'’-])(?:{muster})(?![\wÄÖÜäöüß'’-])")) for name, muster in _GEGENSTAND]
_REGEL_ZEICHEN = re.compile(r"(?i)\b(?:brauch\w*|benötig\w*|muss|musst|müss\w*|darf|darfst|dürf\w*|kann|kannst|könn\w*|\w*pflicht\w*|vorgeschrieben\w*|"
                            r"erforderlich\w*|nötig\w*|notwendig\w*|verpflichtend\w*|erlaubt\w*|zulässig\w*|unzulässig\w*|verboten\w*|untersagt\w*|gesetzlich\w*|"
                            r"gestattet\w*|ohne|\w{3,}frei|befreit\w*|need\w*|requires?|required|must|mandatory|compulsory|obligatory|allowed|"
                            r"permitted|prohibited|forbidden|banned|illegal|legal|legally|can|cannot|can't|(?-i:may)|exempt\w*|waiver\w*|without|"
                            r"\w{3,}-free|have to|has to|eligible)\b")
_NEIN_DAVOR = re.compile(r"(?i)^(?:kein\w*|no|ohne|without|befreit\w*|exempt\w*)$")
_NEIN_DAHINTER = re.compile(r"(?i)^(?:frei|free|waiver\w*|befreit\w*|exempt\w*)$")
_NEIN_IM_WORT = re.compile(r"(?i)(?:frei|-free|free)$")
_NEIN_SATZ = re.compile(r"(?i)\b(?:nicht|not|nie|niemals|never|verboten\w*|untersagt\w*|unzulässig\w*|prohibited|forbidden|banned|illegal|cannot)\b|n't\b|"
                        r"\bkein\w*\s+(?:\w+\s+)?(?:\w*pflicht\w*|notwendigkeit|erfordernis)\b|"
                        r"\b(?:required|necessary|erforderlich|nötig|notwendig|\w*pflicht)\s*[:?]?\s*(?:no|nein)\b")
_KEIN_NEIN = re.compile(r"(?i)\b(?:nicht nur|not only|nicht zuletzt)\b")
_TEILSATZ = re.compile(r"(?i)\s*;\s*|,?\s+(?:aber|sondern|jedoch|während|but|however|whereas|while|although|obwohl)\s+|\s+[–—]\s+")
_OB = re.compile(r"(?i)\b(?:ob|whether)\b")
_JA_NEIN = re.compile(r"(?i)^\s*(ja|nein|yes|no)\s*[,.!:]\s*")
_REGEL_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß'’-]*")
_RAHMEN = re.compile(r"(?i)^(?:einreis\w*|entry|enter\w*|reis\w*|travel\w*|urlaub\w*|holiday\w*|vacation\w*|aufenthalt\w*|stay\w*|besuch\w*|visit\w*|"
                     r"touris\w*|trip\w*|land|länder\w*|country|countries|\w*bürger\w*|citizens?|staatsangehörig\w*|nationals?|bleib\w*|"
                     r"geht|gehen|gibt|gelten|gilt|tage\w*|days?|wochen|weeks?|monate\w*|months?|jahre\w*|years?)$")
_REGEL_FUELL = set("""der die das den dem des ein eine einer eines einem einen und oder aber auch ist sind war waren wird werden wurde wurden hat
haben hatte ich du er sie es wir ihr mich dich sich uns euch mir dir mein meine meinem meinen dein deine deinem deinen sein unser euer in im an
am auf aus bei mit nach von vor zu zum zur über unter für durch gegen um bis als wie was wer wo wann warum welche welcher welches dass wenn
weil denn dann noch nur schon sehr mehr man hier dort da so also etwas alle alles jetzt heute bitte the a an and or of to in on at for from by
with as is are was were be been do does did i you he she it we they my your his her our their this that these those what when where who how
which if then there here also only very more some any all just ja nein yes""".split())


def _regel_teile(text: str) -> list[str]:
    return [t for zeile in (text or "").split("\n") for s in _saetze(zeile) for t in _TEILSATZ.split(s) if t and t.strip()]


def _kern_regel(w: str) -> str:
    w = w.lower()
    return w[:max(4, len(w) - 2)]


def _kern_gleich(a: str, b: str) -> bool:
    return a.startswith(b) or b.startswith(a)


def _regel_gegenstaende(teil: str, rest_kerne: set[str] | None) -> list[tuple[str, int]]:
    t = _KEIN_NEIN.sub(" ", teil)
    toks = [(m.group(0).strip("'’-"), m.start(), m.end()) for m in _REGEL_TOKEN.finditer(t)]
    satz_nein = len(_NEIN_SATZ.findall(t))
    out: list[tuple[str, int]] = []
    belegt_bis: list[tuple[int, int]] = []
    for name, muster in _GEGENSTAND_RE:
        for m in muster.finditer(t):
            belegt_bis.append((m.start(), m.end()))
            davor = [w for w, _a, e in toks if e <= m.start()][-3:]
            dahinter = next((w for w, a, _e in toks if a >= m.end()), "")
            nein = sum(1 for w in davor if _NEIN_DAVOR.match(w)) + (1 if _NEIN_DAHINTER.match(dahinter) else 0)
            nein += 1 if _NEIN_IM_WORT.search(m.group(0)) else 0
            ohne_ihn = len(_NEIN_SATZ.findall(t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]))
            out.append((name, (nein + ohne_ihn) % 2))
    if out:
        return out
    for w, a, e in toks:
        lw = w.lower()
        if (len(w) < 4 or lw in _REGEL_FUELL or _RAHMEN.match(w) or _REGEL_ZEICHEN.fullmatch(w) or _NEIN_SATZ.fullmatch(w) or laender_in(w)
                or any(a < bis and e > von for von, bis in belegt_bis)):
            continue
        k = _kern_regel(w)
        if rest_kerne is None or any(_kern_gleich(k, r) for r in rest_kerne):
            davor = [x for x, _a, ende in toks if ende <= a][-3:]
            nein = sum(1 for x in davor if _NEIN_DAVOR.match(x))
            out.append((k, (nein + satz_nein) % 2))
    return out


def _frage_kerne(frage: str) -> set[str]:
    return {_kern_regel(w) for w in _REGEL_TOKEN.findall(frage or "") if len(w) >= 4 and w.lower() not in _REGEL_FUELL and not _RAHMEN.match(w)
            and not _REGEL_ZEICHEN.fullmatch(w) and not _NEIN_SATZ.fullmatch(w) and not laender_in(w)}


def _regel_aussagen_teile(antwort: str, frage: str) -> list[tuple[str, list[list[tuple[str, int]]]]]:
    kerne = _frage_kerne(frage)
    out = []
    for absatz in (antwort or "").split("\n"):
        for s in _saetze(absatz):
            if s.rstrip().endswith("?"):
                continue
            jn = _JA_NEIN.match(s)
            rest = s[jn.end():] if jn else s
            if jn and not re.search(r"\w", rest):
                umgekehrt = 1 if jn.group(1).lower() in ("nein", "no") else 0
                frage_teile = [g for t in _TEILSATZ.split(frage or "") for g in _regel_gegenstaende(t, kerne)]
                if frage_teile:
                    out.append((s, [[(g, (r + umgekehrt) % 2) for g, r in frage_teile]]))
                continue
            gruppen: list[list[tuple[str, int]]] = []
            for teil in _TEILSATZ.split(rest):
                if _OB.search(teil) or not (_REGEL_ZEICHEN.search(teil) or jn):
                    continue
                g_teil = _regel_gegenstaende(teil, kerne)
                if g_teil:
                    gruppen.append(list(dict.fromkeys(g_teil)))
            if gruppen:
                out.append((s, gruppen))
    return out


def regel_aussagen(antwort: str, frage: str) -> list[tuple[str, list[tuple[str, int]]]]:
    return [(s, list(dict.fromkeys(g for gruppe in gruppen for g in gruppe))) for s, gruppen in _regel_aussagen_teile(antwort, frage)]


def regel_gestuetzt(antwort: str, frage: str, quelltexte: list[str]) -> bool:
    aussagen = regel_aussagen(antwort, frage)
    ohne = {s for s, _g in regel_ungestuetzt(antwort, frage, quelltexte)} if aussagen else set()
    return any(s not in ohne for s, _g in aussagen)


def regel_ungestuetzt(antwort: str, frage: str, quelltexte: list[str]) -> list[tuple[str, tuple[str, ...]]]:
    if not regel_aussagen(antwort, frage):
        return []
    namen = {n for n, _m in _GEGENSTAND}

    def gedeckt(g: str, r: int, stuetze: dict[int, frozenset[str]]) -> bool:
        return g in stuetze[r] if g in namen else any(_kern_gleich(g, s) for s in stuetze[r] if s not in namen)
    je_satz = regel_stuetzen_je_satz(quelltexte)
    out = []
    for satz, gruppen in _regel_aussagen_teile(antwort, frage):
        fehlt: list[str] = []
        for gruppe in gruppen:
            fehlt_je = [[g for g, r in gruppe if not gedeckt(g, r, st)] for st in je_satz] or [[g for g, _r in gruppe]]
            fehlt += min(fehlt_je, key=len)
        if fehlt:
            out.append((satz, tuple(dict.fromkeys(fehlt))))
    return out


def regel_stuetzen_je_satz(quelltexte: list[str]) -> list[dict[int, frozenset[str]]]:
    return _regel_stuetzen_je_satz(tuple(quelltexte))


@lru_cache(maxsize=16)
def _regel_stuetzen_je_satz(quelltexte: tuple[str, ...]) -> list[dict[int, frozenset[str]]]:
    out: list[dict[int, frozenset[str]]] = []
    for text in quelltexte:
        for teil in _regel_teile(text):
            if _REGEL_ZEICHEN.search(teil) and not _OB.search(teil):
                gegen = _regel_gegenstaende(teil, None)
                if gegen:
                    out.append({r: frozenset(g for g, rr in gegen if rr == r) for r in (0, 1)})
    return out


def rechnet(frage: str) -> bool:
    f = _ohne_code_zahlen(frage)
    if not re.search(r"\d", f):
        return False
    if _RECHENZEICHEN.search(f) or _UMRECHNEN.search(f):
        return True
    zahlen = [z for z in _ZAHL.findall(f) if not _JAHRESZAHL.fullmatch(z)]
    if not zahlen:
        return False
    return bool(_RECHNET.search(f) or _UMRECHNEN.search(f) or (len(zahlen) >= 2 and _RECHNET_ZWEI.search(f)))


_EINHEITEN = (
    ("grad", r"°\s*c|°|grad|degrees?"),
    ("min", r"minuten?|minutes?|min"),
    ("h", r"stunden?|hours?|std"),
    ("s", r"sekunden?|seconds?|sek"),
    ("tag", r"tage?n?|days?"),
    ("woche", r"wochen?|weeks?"),
    ("monat", r"monate?n?|months?"),
    ("km/h", r"km/h|kmh|stundenkilometer[n]?"),
    ("km", r"kilometer[ns]?|kilomet(?:er|re)s?|km"),
    ("cm", r"zentimeter[ns]?|centimet(?:er|re)s?|cm"),
    ("mm", r"millimeter[ns]?|millimet(?:er|re)s?|mm"),
    ("m", r"meter[ns]?|met(?:er|re)s?|m"),
    ("kg", r"kilogramm[s]?|kilograms?|kilo|kg"),
    ("g", r"gramm[s]?|grams?|g"),
    ("ml", r"milliliter[ns]?|millilit(?:er|re)s?|ml"),
    ("l", r"liter[ns]?|lit(?:er|re)s?|l"),
    ("kwh", r"kwh|kilowattstunden?"),
    ("kw", r"kw|kilowatt"),
    ("w", r"watt"),
    ("mal", r"mal|times"),
    ("el", r"el|esslöffel|tablespoons?|tbsp"),
    ("tl", r"tl|teelöffel|teaspoons?|tsp"),
    ("tasse", r"tassen?|cups?"),
    ("prise", r"prisen?|pinch(?:es)?"),
)
_ALLTAG_EINHEIT = re.compile(r"\s*(" + "|".join(f"(?P<e{i}>{muster})" for i, (_n, muster) in enumerate(_EINHEITEN)) + r")(?![\wÄÖÜäöüß])", re.I)
_SPANNE = re.compile(r"\s*(?:bis|-|–|und|oder|to|and|or)\s*\d[\d.,]*", re.I)


def _alltag_einheit(satz: str, ende: int) -> str:
    m = _ALLTAG_EINHEIT.match(satz, ende)
    if m is None:
        s = _SPANNE.match(satz, ende)
        m = _ALLTAG_EINHEIT.match(satz, s.end()) if s else None
    if m is None:
        return ""
    e = next(_EINHEITEN[i][0] for i in range(len(_EINHEITEN)) if m.group(f"e{i}") is not None)
    return _GROESSE.get(e, e)


_GROESSE = {"km": "länge", "m": "länge", "cm": "länge", "mm": "länge", "l": "volumen", "ml": "volumen", "kg": "gewicht", "g": "gewicht",
            "kw": "leistung", "w": "leistung"}


def _einheiten(text: str) -> set[str]:
    return {e for m in _ZAHL.finditer(text or "") if (e := _alltag_einheit(text, m.end()))}


_TITEL_VORN = re.compile(r"^(?:Wikipedia|Nachgeschaut|Seite)\s*:\s*", re.I)


def quellen_name(titel: str) -> str:
    t = _TITEL_VORN.sub("", str(titel or "")).strip()
    t = re.split(r"\s+[–—|-]\s+|\s*\(", t)[0].strip()
    return t if t and len(t) >= 4 and len(t.split()) <= 3 else ""


_WER_FRAGE = re.compile(r"^\s*wer\s+(?:war|ist|sind|waren)\b", re.I)
_BESCHREIBUNG = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "mein", "meine", "dein", "deine", "unser", "unsere",
                 "euer", "eure", "sein", "seine", "ihr", "ihre", "diese", "dieser", "dieses", "jener", "jene", "aktuell", "aktuelle", "derzeit", "momentan",
                 "heute", "gerade", "jetzt", "zurzeit"}


def gefragter_name_fehlt(frage: str, antwort: str, quellen_texte: list[str]) -> str:
    if not _WER_FRAGE.search(frage or ""):
        return ""
    t = _tokens(frage)
    if len(t) > 2 and t[2][0].lower() in _BESCHREIBUNG:
        return ""
    staemme = [_wortstaemme(t) for t in quellen_texte]
    for i, (w, _p) in enumerate(_tokens(frage)):
        if i == 0 or not w[:1].isupper() or len(w) < 4 or w.lower() in _KEIN_NAME:
            continue
        if not any(name_belegt(w, st) for st in staemme):
            return w
    return ""


def vermischt_ausloeser(antwort: str, quellen: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    alle = [_wortstaemme(text) for _t, text in quellen]
    benannt = [(n, alle[i]) for i, (titel, _text) in enumerate(quellen)
               if (n := quellen_name(titel)) and not any(name_belegt(n, st) for j, st in enumerate(alle) if j != i)]
    if len(alle) < 2 or not benannt:
        return []
    out: list[tuple[str, str, str]] = []
    for absatz in (antwort or "").split("\n"):
        for s in _saetze(absatz):
            for name, eigene in benannt:
                if not re.search(rf"(?<![\wÄÖÜäöüß]){re.escape(name)}(?![\wÄÖÜäöüß])", s):
                    continue
                namensteile = {w.lower() for w in name.split()}
                worte = [w for i, (w, _p) in enumerate(_tokens(s)) if i > 0 and w[:1].isupper() and len(w) >= 6
                         and w.lower() not in namensteile and w.lower() not in _KEIN_NAME]
                wort = next((w for w in worte if not name_belegt(w, eigene) and any(name_belegt(w, st) for st in alle)), None)
                if wort is not None:
                    out.append((s, name, wort))
                    break
    return out


def vermischt(antwort: str, quellen: list[tuple[str, str]]) -> list[str]:
    return [s for s, _n, _w in vermischt_ausloeser(antwort, quellen)]


def alltag_ohne_widerspruch(satz: str, belege: str) -> bool:
    belegt_d = daten(belege)
    if any(not _gedeckt_datum(d, belegt_d) for d in daten(satz)) or namen(satz)[0]:
        return False
    belegt_z = zahlenwerte(belege)
    ohne_daten = _DATUM_ISO.sub(" ", _DATUM_WORT.sub(" ", _DATUM_ZAHL.sub(" ", satz)))
    in_quellen = None
    gefunden = False
    for m in _ZAHL.finditer(ohne_daten):
        if not _zahl_pruefbar(m, ohne_daten) or (_werte(m.group(0)) & belegt_z) or _ungefaehr_belegt(m, ohne_daten, belegt_z):
            continue
        e = _alltag_einheit(ohne_daten, m.end())
        if not e:
            return False
        if in_quellen is None:
            in_quellen = _einheiten(belege)
        if e in in_quellen:
            return False
        gefunden = True
    return gefunden


_BEISPIEL = re.compile(r"\b(?:könnte[nst]?|würde[nst]?|wäre[nst]?|hätte[nst]?|angenommen|nehmen wir an|stell dir vor|stellen Sie sich vor|"
                       r"gesetzt den Fall|sagen wir|zum Beispiel|beispielsweise|ein Beispiel)\b|\bz\.\s?B\.|^\s*(?:[-–•*]\s*)?wenn\b", re.I)


def beispiel(satz: str) -> bool:
    return bool(_BEISPIEL.search(satz or ""))


__all__ = ["daten", "betraege", "unbelegte_streichen", "wochentage_berichtigen", "ohne_platzhalter", "pruefen_noetig", "rechnet", "zahlenfrage", "geruest_bereinigen", "brauchbar",
           "streng_pruefen", "Befund", "namen", "name_belegt", "unbelegte_zahlen", "KLEINE_ZAHL", "PRUEFER_SYSTEM", "pruefer_auftrag", "urteil_lesen"]


ZUKUNFT_WORTE = (
    "kommt", "kommen", "erscheint", "erscheinen", "wird", "werden", "startet", "starten", "folgt", "folgen", "soll", "sollen", "geplant",
    "angekündigt", "bevorsteh", "demnächst", "künftig", "ab dem",
    "will", "is coming", "are coming", "comes out", "come out", "coming", "releases", "is releasing", "launches", "is set to", "are set to",
    "upcoming", "scheduled", "due out", "is expected", "are expected", "is due",
    "uscirà", "usciranno", "arriverà", "arriveranno", "sarà", "saranno", "in uscita", "previsto", "prevista", "sortira", "sortiront",
    "arrivera", "arriveront", "sera", "seront", "à paraître", "prévu", "prévue", "saldrá", "saldrán", "llegará", "llegarán", "será", "serán",
    "próximamente", "sairá", "chegará", "estreia em",
    "verschijnt", "komt uit", "zal", "zullen", "gepland", "ukaże się", "pojawi się", "będzie", "kommer", "udkommer", "släpps",
    "発売予定", "予定", "公開予定",
)
_ZUKUNFT = re.compile(r"(?i)(?<![^\W\d_])(?:" + "|".join(re.escape(w) for w in sorted(ZUKUNFT_WORTE, key=len, reverse=True)) + r")(?![^\W\d_])"
                      + r"|発売予定|公開予定|予定")
_MONAT_JAHR: re.Pattern | None = None
_JAPANISCH = re.compile(r"((?:19|20)\d\d)\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?")
_JAHR_ALLEIN = re.compile(r"(?<![\d.,/-])((?:19|20)\d\d)(?![\d,/-]|\.\d)")


def _monat_jahr() -> re.Pattern:
    global _MONAT_JAHR
    if _MONAT_JAHR is None:
        namen = set(laender.MONATE) | set(MONATE) | set(MONATE_EN)
        teile = "|".join(re.escape(n) for n in sorted(namen, key=len, reverse=True) if len(n) >= 3)
        _MONAT_JAHR = re.compile(rf"(?i)(?<![^\W\d_])({teile})\.?\s*(?:de\s+|del\s+|of\s+|,\s*)?((?:19|20)\d\d)(?!\d)")
    return _MONAT_JAHR


def _monat_von(name: str) -> int:
    n = name.lower()
    return laender.MONATE.get(n) or MONATE.get(n) or MONATE_EN.get(n) or 0


def zeitpunkte(satz: str, heute: date) -> list[date]:
    import calendar
    out: list[date] = []
    belegt: list[tuple[int, int]] = []
    for t, m, j in daten(satz):
        try:
            out.append(date(j or _jahr_fuer(t, m, heute), m, t))
        except ValueError:
            continue
    for m in _JAPANISCH.finditer(satz):
        j, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            out.append(date(j, mo, int(m.group(3)) if m.group(3) else calendar.monthrange(j, mo)[1]))
            belegt.append(m.span())
    for m in _monat_jahr().finditer(satz):
        mo, j = _monat_von(m.group(1)), int(m.group(2))
        if mo:
            out.append(date(j, mo, calendar.monthrange(j, mo)[1]))
            belegt.append(m.span())
    for m in _JAHR_ALLEIN.finditer(satz):
        if not any(a <= m.start() < e for a, e in belegt) and not out:
            out.append(date(int(m.group(1)), 12, 31))
    return out


_SEIT = re.compile(r"(?i)(?<![^\W\d_])(?:seit|since|depuis|desde|dal|dalla|sinds|od|siden|sedan|alkaen)(?![^\W\d_])|以来")


def zukunft_vorbei(satz: str, heute: date) -> bool:
    zp = zeitpunkte(satz, heute)
    return bool(zp) and max(zp) < heute and bool(_ZUKUNFT.search(satz)) and not _SEIT.search(satz)


ZEITFORM_DE = ("Heute ist der {heute}. Jeder nummerierte Satz nennt ein Datum, das schon vorbei ist, spricht aber so, als käme es noch. Schreib "
               "jeden Satz so, wie es heute stimmt: was an diesem Datum erschienen, gestartet oder passiert ist, steht in der Vergangenheit. Daten, "
               "Zahlen und Namen bleiben genau gleich, nichts dazu, nichts weg. Antworte nur mit einer Zeile je Satz: die Nummer, dann der neue Satz.")
ZEITFORM_EN = ("Today is {heute}. Each numbered sentence names a date that has already passed but speaks as if it were still to come. Rewrite each "
               "sentence so it is true today: what came out, started or happened on that date is in the past tense. Keep dates, numbers and names "
               "exactly, add nothing, leave nothing out. Answer only with one line per sentence: the number, then the new sentence.")


def zeitform_berichtigen(antwort: str, heute: date, umschreiben=None, *, englisch: bool = False) -> tuple[str, int, list[str]]:
    falsch = [s for absatz in (antwort or "").split("\n") for s in _saetze(absatz) if zukunft_vorbei(s, heute)]
    if not falsch:
        return antwort, 0, []
    neu: dict[str, str] = {}
    if umschreiben is not None:
        anweisung = (ZEITFORM_EN if englisch else ZEITFORM_DE).format(heute=heute.strftime("%d %B %Y" if englisch else "%d.%m.%Y"))
        try:
            vorschlaege = umschreiben(falsch, englisch, anweisung) or {}
        except Exception:
            vorschlaege = {}
        for i, s in enumerate(falsch):
            v = " ".join(str(vorschlaege.get(i) or "").split())
            if v and sorted(zeitpunkte(v, heute)) == sorted(zeitpunkte(s, heute)) and not zukunft_vorbei(v, heute):
                neu[s] = v
    text = antwort
    for alt, ersatz in neu.items():
        text = text.replace(alt, ersatz, 1)
    text, raus = saetze_streichen(text, lambda s: s in falsch and s not in neu)
    return text, len(neu), raus
