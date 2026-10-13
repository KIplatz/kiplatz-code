# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

from rechnen import Ergebnis, _Nein, zahl_text

ZONEN: list[tuple[tuple[str, ...], str, str, int, str]] = [
    (("wien", "österreich", "oesterreich", "vienna", "austria", "graz", "linz", "salzburg", "innsbruck", "berlin", "deutschland", "germany", "münchen", "muenchen", "hamburg", "zürich", "zuerich",
      "zurich", "schweiz", "bern", "rom", "rome", "mailand", "paris", "frankreich", "madrid", "spanien", "barcelona", "amsterdam", "brüssel", "bruessel", "brussels", "prag", "prague",
      "budapest", "warschau", "warsaw", "stockholm", "oslo", "kopenhagen", "copenhagen", "zagreb", "ljubljana", "laibach", "bratislava", "belgrad", "belgrade"), "", "", 60, "eu"),
    (("london", "england", "großbritannien", "grossbritannien", "uk", "lissabon", "lisbon", "dublin", "irland", "ireland"), "", "", 0, "eu"),
    (("athen", "athens", "helsinki", "kiew", "kyiv", "kiev", "bukarest", "bucharest", "sofia", "riga", "vilnius", "tallinn", "griechenland", "greece"), "", "", 120, "eu"),
    (("istanbul", "ankara", "türkei", "tuerkei", "turkey"), "", "", 180, ""),
    (("moskau", "moscow", "minsk"), "", "", 180, ""),
    (("nairobi", "kenia", "kenya"), "", "", 180, ""),
    (("teheran", "tehran", "iran"), "", "", 210, ""),
    (("dubai", "abu dhabi"), "", "", 240, ""),
    (("karatschi", "karachi", "islamabad", "pakistan"), "", "", 300, ""),
    (("delhi", "neu delhi", "new delhi", "mumbai", "bombay", "kolkata", "kalkutta", "bangalore", "indien", "india"), "", "", 330, ""),
    (("dhaka", "dacca"), "", "", 360, ""),
    (("bangkok", "jakarta", "hanoi", "ho chi minh stadt", "thailand", "vietnam"), "", "", 420, ""),
    (("peking", "beijing", "shanghai", "china", "hongkong", "hong kong", "singapur", "singapore", "manila", "taipeh", "taipei", "perth"), "", "", 480, ""),
    (("tokio", "tokyo", "japan", "seoul", "südkorea", "suedkorea", "south korea", "osaka"), "", "", 540, ""),
    (("brisbane",), "", "", 600, ""),
    (("sydney", "melbourne", "canberra", "australien", "australia"), "", "", 600, "au"),
    (("auckland", "wellington", "neuseeland", "new zealand"), "", "", 720, "nz"),
    (("new york", "newyork", "washington", "boston", "miami", "atlanta", "toronto", "usa ostküste", "usa ostkueste"), "", "", -300, "us"),
    (("chicago", "dallas", "houston", "austin", "new orleans"), "", "", -360, "us"),
    (("denver", "salt lake city"), "", "", -420, "us"),
    (("los angeles", "san francisco", "seattle", "las vegas", "vancouver", "portland", "usa westküste", "usa westkueste"), "", "", -480, "us"),
    (("honolulu", "hawaii"), "", "", -600, ""),
    (("mexiko stadt", "mexiko-stadt", "mexico city", "mexiko"), "", "", -360, ""),
    (("sao paulo", "são paulo", "rio", "rio de janeiro", "brasilien", "brazil", "buenos aires", "argentinien", "argentina"), "", "", -180, ""),
    (("johannesburg", "kapstadt", "cape town", "südafrika", "suedafrika", "south africa"), "", "", 120, ""),
    (("lagos", "nigeria"), "", "", 60, ""),
    (("utc", "gmt", "weltzeit"), "", "", 0, ""),
]
_ANZEIGE_EN = {"wien": "Vienna", "österreich": "Austria", "oesterreich": "Austria", "berlin": "Berlin", "deutschland": "Germany", "münchen": "Munich", "muenchen": "Munich", "zürich": "Zurich",
               "zuerich": "Zurich", "schweiz": "Switzerland", "rom": "Rome", "mailand": "Milan", "frankreich": "France", "spanien": "Spain", "brüssel": "Brussels", "bruessel": "Brussels",
               "prag": "Prague", "warschau": "Warsaw", "kopenhagen": "Copenhagen", "laibach": "Ljubljana", "belgrad": "Belgrade", "großbritannien": "Great Britain",
               "grossbritannien": "Great Britain", "lissabon": "Lisbon", "irland": "Ireland", "athen": "Athens", "kiew": "Kyiv", "bukarest": "Bucharest", "griechenland": "Greece",
               "türkei": "Turkey", "tuerkei": "Turkey", "moskau": "Moscow", "kenia": "Kenya", "teheran": "Tehran", "karatschi": "Karachi", "indien": "India", "kalkutta": "Kolkata",
               "peking": "Beijing", "singapur": "Singapore", "hongkong": "Hong Kong", "taipeh": "Taipei", "tokio": "Tokyo", "südkorea": "South Korea", "suedkorea": "South Korea",
               "australien": "Australia", "neuseeland": "New Zealand", "mexiko stadt": "Mexico City", "mexiko-stadt": "Mexico City", "mexiko": "Mexico", "brasilien": "Brazil",
               "argentinien": "Argentina", "kapstadt": "Cape Town", "südafrika": "South Africa", "suedafrika": "South Africa", "weltzeit": "UTC", "ho chi minh stadt": "Ho Chi Minh City",
               "usa ostküste": "US East Coast", "usa ostkueste": "US East Coast", "usa westküste": "US West Coast", "usa westkueste": "US West Coast", "bombay": "Mumbai", "neu delhi": "New Delhi"}
_ANZEIGE_DE = {"vienna": "Wien", "austria": "Österreich", "germany": "Deutschland", "munich": "München", "zurich": "Zürich", "rome": "Rom", "brussels": "Brüssel", "prague": "Prag",
               "warsaw": "Warschau", "copenhagen": "Kopenhagen", "lisbon": "Lissabon", "ireland": "Irland", "athens": "Athen", "kyiv": "Kiew", "kiev": "Kiew", "bucharest": "Bukarest",
               "greece": "Griechenland", "turkey": "Türkei", "moscow": "Moskau", "kenya": "Kenia", "tehran": "Teheran", "karachi": "Karatschi", "india": "Indien", "beijing": "Peking",
               "singapore": "Singapur", "taipei": "Taipeh", "tokyo": "Tokio", "australia": "Australien", "new zealand": "Neuseeland", "mexico city": "Mexiko-Stadt", "mexico": "Mexiko",
               "brazil": "Brasilien", "argentina": "Argentinien", "cape town": "Kapstadt", "south africa": "Südafrika", "new delhi": "Neu-Delhi", "south korea": "Südkorea",
               "hong kong": "Hongkong", "milan": "Mailand", "great britain": "Großbritannien", "uk": "Großbritannien", "spain": "Spanien", "france": "Frankreich", "switzerland": "Schweiz"}
_ANZEIGE_EN.update({"uk": "UK", "utc": "UTC", "gmt": "GMT"})
_ANZEIGE_DE.update({"utc": "UTC", "gmt": "GMT"})
_BEKANNT: dict[str, tuple[str, str, int, str]] = {}
for _namen, _, _, _std, _regel in ZONEN:
    for _n in _namen:
        _BEKANNT[_n] = (_ANZEIGE_DE.get(_n) or _n.title(), _ANZEIGE_EN.get(_n) or _n.title(), _std, _regel)
_NAMEN_RE = "|".join(re.escape(n) for n in sorted(_BEKANNT, key=len, reverse=True))

_TAGE_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_TAGE_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def jetzt_utc() -> datetime:
    return datetime.now(timezone.utc)


def _heute() -> date:
    import rechnen_datum
    return rechnen_datum.heute()


def _sonntag(jahr: int, monat: int, nr: int) -> date:
    if nr > 0:
        d = date(jahr, monat, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=nr - 1)
    d = date(jahr + (monat == 12), monat % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _utc(d: date, stunde: int, std_min: int) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(hours=stunde, minutes=-std_min)


def sommerzeit(regel: str, std_min: int, utc: datetime) -> bool:
    j = utc.year
    if regel == "eu":
        return _utc(_sonntag(j, 3, -1), 1, 0) <= utc < _utc(_sonntag(j, 10, -1), 1, 0)
    if regel == "us":
        return _utc(_sonntag(j, 3, 2), 2, std_min) <= utc < _utc(_sonntag(j, 11, 1), 1, std_min)
    if regel == "au":
        return utc >= _utc(_sonntag(j, 10, 1), 2, std_min) or utc < _utc(_sonntag(j, 4, 1), 2, std_min)
    if regel == "nz":
        return utc >= _utc(_sonntag(j, 9, -1), 2, std_min) or utc < _utc(_sonntag(j, 4, 1), 2, std_min)
    return False


def versatz(zone: tuple[str, str, int, str], utc: datetime) -> int:
    _, _, std, regel = zone
    return std + (60 if sommerzeit(regel, std, utc) else 0)


def ortszeit(zone: tuple[str, str, int, str], utc: datetime) -> datetime:
    return (utc + timedelta(minutes=versatz(zone, utc))).replace(tzinfo=None)


def aus_ortszeit(zone: tuple[str, str, int, str], lokal: datetime) -> datetime:
    std = zone[2]
    roh = lokal.replace(tzinfo=timezone.utc) - timedelta(minutes=std)
    v = versatz(zone, roh - timedelta(minutes=60))
    for dv in (v, versatz(zone, roh - timedelta(minutes=v - std)), std):
        kand = lokal.replace(tzinfo=timezone.utc) - timedelta(minutes=dv)
        if versatz(zone, kand) == dv:
            return kand
    return roh


def _uhr(h: int, m: int, en: bool, zwoelf: bool = False) -> str:
    if en and zwoelf:
        return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    return f"{h:02d}:{m:02d}" + ("" if en else " Uhr")


def _stunden_text(minuten: int, en: bool) -> str:
    h = Fraction(abs(minuten), 60)
    if h == 1:
        return "1 hour" if en else "1 Stunde"
    return f"{zahl_text(h, en)} hours" if en else f"{zahl_text(h)} Stunden"


def _dauer_text(minuten: int, en: bool) -> str:
    h, m = divmod(minuten, 60)
    teile = []
    if h:
        teile.append(f"{h} {'hour' if h == 1 else 'hours'}" if en else f"{h} {'Stunde' if h == 1 else 'Stunden'}")
    if m or not h:
        teile.append(f"{m} {'minute' if m == 1 else 'minutes'}" if en else f"{m} {'Minute' if m == 1 else 'Minuten'}")
    return (" and " if en else " und ").join(teile)


_ZEIT = r"(?P<h{n}>\d{{1,2}})(?:[:.](?P<m{n}>\d{{2}}))?\s*(?P<u{n}>uhr|h|am|pm|a\.m\.|p\.m\.)?"


def _zeit_lesen(h: str, m: str | None, u: str | None) -> tuple[int, int, bool]:
    hh, mm = int(h), int(m or 0)
    u = (u or "").lower().replace(".", "")
    if mm > 59 or hh > 24 or (hh == 24 and mm):
        raise _Nein
    ampm = u in ("am", "pm")
    if ampm:
        if not 1 <= hh <= 12:
            raise _Nein
        hh = hh % 12 + (12 if u == "pm" else 0)
    return hh % 24, mm, ampm


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(text.split()).strip()
    t = re.sub(r"[\s?!.]+$", "", t)
    for stufe in (_zonen, _jetzt_in, _dauer, _plus_minus):
        r = stufe(t)
        if r is not None:
            return r
    return None


def _zone(name: str) -> tuple[str, str, int, str]:
    return _BEKANNT[name.lower()]


_FUELL = {"wenn", "es", "in", "ist", "wie", "spät", "spaet", "viel", "uhr", "um", "bei", "ob", "dann", "also", "ich", "nach", "zu", "für", "fuer", "der", "die", "das", "dort", "hier",
          "wieviel", "wieviele", "zeit", "zeitzone", "ortszeit", "umrechnen", "umgerechnet", "von", "auf", "bitte", "sind", "sag", "mir", "wird", "gilt", "dann", "denn", "mal", "to", "what",
          "time", "is", "it", "when", "at", "o'clock", "oclock", "be", "convert", "the", "its", "it's", "in", "into", "and", "und", "als", "gleich", "da", "so", "wieviel", "wiener", "ihr"}


def _zonen(t: str) -> Ergebnis | None:
    s = t.lower().replace("’", "'")
    gefunden: list[tuple[int, int, str]] = []
    for m in re.finditer(rf"(?<![\wäöüß])({_NAMEN_RE})(?![\wäöüß])", s):
        gefunden.append((m.start(), m.end(), m.group(1)))
    if len(gefunden) != 2:
        return None
    zeiten = list(re.finditer(rf"(?<![\d:.])(\d{{1,2}})(?:[:.](\d{{2}}))?\s*(uhr|h|am|pm|a\.m\.|p\.m\.)?(?![\d:])", s))
    zeiten = [z for z in zeiten if (z.group(2) and ":" in z.group(0)) or z.group(3)]
    if len(zeiten) != 1:
        return None
    z = zeiten[0]
    (a0, a1, an), (b0, b1, bn) = gefunden
    schnipsel = s
    for beginn, ende in sorted([(a0, a1), (b0, b1), (z.start(), z.end())], reverse=True):
        schnipsel = schnipsel[:beginn] + " " + schnipsel[ende:]
    if any(w not in _FUELL for w in re.findall(r"[a-zäöüß']+", schnipsel)):
        return None
    if re.search(r"\d", schnipsel):
        return None
    if not re.search(r"[?]|\bwie\b|\bwhat\b|\bin\b|\bnach\b|\bto\b|\bum\b|\bwenn\b|\bwhen\b", s) or t.strip() == "":
        return None
    def abstand(o0: int, o1: int) -> int:
        luecke = s[o1:z.start()] if o1 <= z.start() else s[z.end():o0]
        return len(re.findall(r"[\wäöüß']+", luecke))
    da, db = abstand(a0, a1), abstand(b0, b1)
    if da == db:
        return None
    quelle, ziel = (an, bn) if da < db else (bn, an)
    try:
        h, m, ampm = _zeit_lesen(z.group(1), z.group(2), z.group(3))
    except _Nein:
        return None
    zq, zz = _zone(quelle), _zone(ziel)
    if zq[:2] == zz[:2] or quelle == ziel:
        return None
    heute = _heute()
    lokal = datetime(heute.year, heute.month, heute.day, h, m)
    utc = aus_ortszeit(zq, lokal)
    dort = ortszeit(zz, utc)
    tag = (dort.date() - lokal.date()).days
    unterschied = versatz(zz, utc) - versatz(zq, utc)
    wechsel = any(versatz(zz, utc + timedelta(days=d)) - versatz(zq, utc + timedelta(days=d)) != unterschied for d in (-7, 7))
    de_tag = {-1: " (am Vortag)", 0: "", 1: " (am nächsten Tag)"}.get(tag, "")
    en_tag = {-1: " (the day before)", 0: "", 1: " (the next day)"}.get(tag, "")
    if unterschied == 0:
        de_u, en_u = "Kein Zeitunterschied.", "No time difference."
    else:
        de_u = f"{zq[0]} ist {zz[0]} {_stunden_text(unterschied, False)} {'voraus' if unterschied < 0 else 'hinterher'}."
        en_u = f"{zq[1]} is {_stunden_text(unterschied, True)} {'ahead of' if unterschied < 0 else 'behind'} {zz[1]}."
    de = (f"{_uhr(h, m, False)} in {zq[0]} sind {_uhr(dort.hour, dort.minute, False)} in {zz[0]}{de_tag}. {de_u} "
          f"Gerechnet mit der Sommer- und Winterzeit von heute.")
    en = (f"{_uhr(h, m, True, ampm)} in {zq[1]} is {_uhr(dort.hour, dort.minute, True, ampm)} in {zz[1]}{en_tag}. {en_u} "
          f"Calculated with today's daylight saving time rules.")
    if wechsel:
        de += " Achtung: In den nächsten Tagen wird in einem der beiden Länder die Uhr umgestellt, dann stimmt der Unterschied nicht mehr."
        en += " Note: one of the two places changes its clocks within the next days, so the difference will change."
    return Ergebnis(de, en)


def _jetzt_in(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:wie\s+sp[aä]t|wie\s*viel\s+uhr|welche\s+uhrzeit|uhrzeit|what\s+time|time)\s*(?:ist\s+es|is\s+it|ist|is)?\s*(?:jetzt\s+|gerade\s+|now\s+|right\s+now\s+)?(?:in|bei|at)\s+(?P<o>{_NAMEN_RE})(?:\s+(?:jetzt|gerade|now))?", t, re.I)
    if not m:
        return None
    z = _zone(m.group("o"))
    utc = jetzt_utc()
    dort = ortszeit(z, utc)
    tag_de, tag_en = _TAGE_DE[dort.weekday()], _TAGE_EN[dort.weekday()]
    return Ergebnis(f"In {z[0]} ist es jetzt {_uhr(dort.hour, dort.minute, False)} ({tag_de}), nach der Uhr dieses Geräts und den Sommerzeit-Regeln.",
                    f"It is {_uhr(dort.hour, dort.minute, True, True)} in {z[1]} right now ({tag_en}), by this device's clock and daylight saving rules.")


def _dauer(t: str) -> Ergebnis | None:
    pause = r"(?:\s*(?:,|und)?\s*(?P<pm>abzüglich|abzueglich|minus|mit|ohne|nach\s+abzug\s+von|inklusive|inkl\.?|less)\s+(?:einer\s+|einer\s+halben\s+)?(?P<p>\d+)\s*(?:min(?:uten)?\.?|min)\s*(?:pause)?)?"
    z1, z2 = _ZEIT.format(n=1), _ZEIT.format(n=2)
    kopf = r"(?:wie\s+(?:lange|viele\s+stunden|viel\s+zeit)\s+(?:dauert\s+(?:es\s+)?|sind\s+es\s+|ist\s+es\s+|geht\s+)?|arbeitszeit\s+|dauer\s+|how\s+(?:long|many\s+hours)\s+(?:is\s+|are\s+it\s+|from\s+)?)?"
    m = re.fullmatch(rf"{kopf}(?:von\s+|from\s+|zwischen\s+)?{z1}\s*(?:bis|-|–|—|to|und|until)\s*{z2}\s*(?:uhr)?{pause}", t, re.I)
    if not m:
        return None
    frage = re.match(r"\s*(?:wie|arbeitszeit|dauer|how)", t, re.I)
    if not frage and not m.group("pm"):
        return None
    if not (m.group("m1") or m.group("u1") or m.group("m2") or m.group("u2")) and not frage:
        return None
    try:
        h1, m1, _ = _zeit_lesen(m.group("h1"), m.group("m1"), m.group("u1") if (m.group("u1") or "").lower() not in ("h",) else "uhr")
        h2, m2, _ = _zeit_lesen(m.group("h2"), m.group("m2"), m.group("u2") if (m.group("u2") or "").lower() not in ("h",) else "uhr")
    except _Nein:
        return None
    a, b = h1 * 60 + m1, h2 * 60 + m2
    if a == b:
        return None
    ueber = b < a
    dauer = b - a + (1440 if ueber else 0)
    p = int(m.group("p")) if m.group("p") else 0
    if m.group("pm") and m.group("pm").lower() == "inklusive" or (m.group("pm") or "").lower().startswith("inkl"):
        p = 0
    if p >= dauer:
        return None
    netto = dauer - p
    dez = Fraction(netto, 60)
    de = f"Von {_uhr(h1, m1, False)} bis {_uhr(h2, m2, False)}{' (über Mitternacht)' if ueber else ''} sind es {_dauer_text(dauer, False)}"
    en = f"From {_uhr(h1, m1, True)} to {_uhr(h2, m2, True)}{' (past midnight)' if ueber else ''} is {_dauer_text(dauer, True)}"
    if p:
        de += f"; ohne {p} Minuten Pause {_dauer_text(netto, False)}"
        en += f"; without a {p} minute break {_dauer_text(netto, True)}"
    genau = netto % 60 and netto % 15 == 0
    de += f" ({zahl_text(dez)} Stunden)." if genau else "."
    en += f" ({zahl_text(dez, True)} hours)." if genau else "."
    return Ergebnis(de, en)


_EINH = r"(?:stunden?|std\.?|h|hours?|hrs?|minuten?|min\.?|minutes?)"
_DAUER = rf"(?P<d>\d+(?:[.,]\d+)?\s*{_EINH}(?:\s*(?:und|,|and)?\s*\d+\s*{_EINH})?|(?:eine|einer|eine\s+halbe|anderthalb)\s+(?:stunde|halbe\s+stunde)|(?:ein\s+)?halbe\s+stunde|(?:one|half)\s+(?:an\s+)?hour?)"


def _dauer_lesen(s: str) -> int:
    s = s.lower()
    if "halbe stunde" in s and not re.search(r"\d", s):
        return 30
    if "anderthalb" in s:
        return 90
    if re.fullmatch(r"(?:eine|einer)\s+stunde", s.strip()):
        return 60
    summe = Fraction(0)
    teile = re.findall(rf"(\d+(?:[.,]\d+)?)\s*({_EINH})", s)
    if not teile:
        raise _Nein
    for zahl, e in teile:
        z = Fraction(zahl.replace(",", "."))
        summe += z * (60 if e.startswith(("st", "h")) else 1)
    if summe.denominator != 1:
        raise _Nein
    return int(summe)


def _plus_minus(t: str) -> Ergebnis | None:
    z = _ZEIT.format(n=1)
    m = re.fullmatch(rf"(?:wie\s+sp[aä]t\s+ist\s+es\s+|was\s+ist\s+|what\s+is\s+)?{z}\s*(?P<op>\+|plus|-|–|minus)\s*{_DAUER}(?:\s+sp[aä]ter)?", t, re.I)
    vorzeichen = 1
    if m:
        vorzeichen = 1 if m.group("op").lower() in ("+", "plus") else -1
    else:
        m = re.fullmatch(rf"(?:wie\s+sp[aä]t\s+ist\s+es\s+|was\s+ist\s+|what\s+is\s+|what\s+time\s+is\s+it\s+)?{_DAUER}\s*(?P<op>nach|vor|after|before)\s+{z}", t, re.I)
        if not m:
            return None
        vorzeichen = 1 if m.group("op").lower() in ("nach", "after") else -1
    if not (m.group("m1") or m.group("u1")):
        return None
    try:
        h, mi, ampm = _zeit_lesen(m.group("h1"), m.group("m1"), m.group("u1") if (m.group("u1") or "").lower() != "h" else "uhr")
        d = _dauer_lesen(m.group("d"))
    except _Nein:
        return None
    if d > 60 * 24 * 7:
        return None
    gesamt = h * 60 + mi + vorzeichen * d
    tage, rest = divmod(gesamt, 1440)
    nh, nm = divmod(rest, 60)
    de_tag = {-1: " (am Vortag)", 0: "", 1: " (am nächsten Tag)"}.get(tage, f" ({'+' if tage > 0 else ''}{tage} Tage)" if tage > 0 else f" ({tage} Tage)")
    en_tag = {-1: " (the day before)", 0: "", 1: " (the next day)"}.get(tage, f" ({'+' if tage > 0 else ''}{tage} days)")
    op_de = "plus" if vorzeichen > 0 else "minus"
    return Ergebnis(f"{_uhr(h, mi, False)} {op_de} {_dauer_text(d, False)} ist {_uhr(nh, nm, False)}{de_tag}.",
                    f"{_uhr(h, mi, True, ampm)} {op_de} {_dauer_text(d, True)} is {_uhr(nh, nm, True, ampm)}{en_tag}.")
