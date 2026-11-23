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
    for stufe in (_zonen, _jetzt_in, _zone_von, _umstellung, _dauer, _plus_minus):
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


_MEHRERE_ZONEN = {"australien": "sydney", "australia": "sydney", "brasilien": "sao paulo", "brazil": "sao paulo", "mexiko": "mexiko stadt",
                  "mexico": "mexico city", "spanien": "madrid", "spain": "madrid"}


def _jetzt_in(t: str) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:wie\s+sp[aä]t|wie\s*viel\s+uhr|welche\s+uhrzeit|uhrzeit|(?:what\s+is|what['’]?s)\s+the\s+(?:current\s+|local\s+)?time|"
                     rf"(?:current|local)\s+time|what\s+time|time)\s*(?:ist\s+es|is\s+it|ist|is)?\s*"
                     rf"(?:jetzt\s+|gerade\s+|aktuell\s+|now\s+|right\s+now\s+|currently\s+)?(?:in|bei|at)\s+(?P<o>{_NAMEN_RE})"
                     rf"(?:\s+(?:jetzt|gerade|aktuell|now|right\s+now|currently))?", t, re.I)
    if not m:
        return None
    land = _MEHRERE_ZONEN.get(m.group("o").lower())
    z = _zone(land or m.group("o"))
    utc = jetzt_utc()
    dort = ortszeit(z, utc)
    tag_de, tag_en = _TAGE_DE[dort.weekday()], _TAGE_EN[dort.weekday()]
    if land:
        lz = _zone(m.group("o"))
        return Ergebnis(f"{lz[0]} hat mehrere Zeitzonen. In {z[0]} ist es jetzt {_uhr(dort.hour, dort.minute, False)} ({tag_de}), nach der Uhr "
                        f"dieses Geräts und den Sommerzeit-Regeln; in anderen Landesteilen ist es früher oder später.",
                        f"{lz[1]} has several time zones. It is {_uhr(dort.hour, dort.minute, True, True)} in {z[1]} right now ({tag_en}), by this "
                        f"device's clock and daylight saving rules; other parts of the country are earlier or later.")
    return Ergebnis(f"In {z[0]} ist es jetzt {_uhr(dort.hour, dort.minute, False)} ({tag_de}), nach der Uhr dieses Geräts und den Sommerzeit-Regeln.",
                    f"It is {_uhr(dort.hour, dort.minute, True, True)} in {z[1]} right now ({tag_en}), by this device's clock and daylight saving rules.")


def _utc_text(minuten: int) -> str:
    h, m = divmod(abs(minuten), 60)
    return "UTC" + ("-" if minuten < 0 else "+") + str(h) + (f":{m:02d}" if m else "")


_ZONE_VON = re.compile(
    rf"(?:(?:what|which)\s+time\s*zone\s+(?:is|does|do|has)\s+(?P<o1>{_NAMEN_RE})(?:\s+(?:in|use|have|on))?"
    rf"|(?:what|which|what's|whats)\s+(?:is\s+)?(?:the\s+)?time\s*zone\s+(?:of|in|for)\s+(?P<o2>{_NAMEN_RE})"
    rf"|time\s*zone\s+(?:of|in|for)\s+(?P<o3>{_NAMEN_RE})"
    rf"|welche\s+zeitzone\s+(?:hat|gilt\s+(?:in|für|fuer)|ist\s+in|herrscht\s+in|gibt\s+es\s+in|haben)\s+(?:die\s+|der\s+)?(?P<o4>{_NAMEN_RE})"
    rf"|in\s+welcher\s+zeitzone\s+(?:liegt|ist|befindet\s+sich|liegen)\s+(?P<o5>{_NAMEN_RE})"
    rf"|zeitzone\s+(?:von|in|für|fuer)\s+(?P<o6>{_NAMEN_RE}))", re.I)


def _zone_von(t: str) -> Ergebnis | None:
    m = _ZONE_VON.fullmatch(t)
    if not m:
        return None
    ort = next(g for g in m.groups() if g)
    if ort.lower() in ("utc", "gmt", "weltzeit") or ort.lower() in _MEHRERE_ZONEN:
        return None
    z = _zone(ort)
    utc = jetzt_utc()
    dort = ortszeit(z, utc)
    std, regel = z[2], z[3]
    jetzt_v = versatz(z, utc)
    tag_de, tag_en = _TAGE_DE[dort.weekday()], _TAGE_EN[dort.weekday()]
    if not regel:
        de_z, en_z = f"{z[0]} hat {_utc_text(std)}, ohne Sommerzeit.", f"{z[1]} uses {_utc_text(std)}, with no daylight saving time."
    elif jetzt_v != std:
        de_z = f"{z[0]} hat gerade Sommerzeit, {_utc_text(jetzt_v)}; sonst gilt {_utc_text(std)}."
        en_z = f"{z[1]} is on daylight saving time right now, {_utc_text(jetzt_v)}; standard time is {_utc_text(std)}."
    else:
        de_z = f"{z[0]} hat gerade Normalzeit, {_utc_text(std)}; in der Sommerzeit gilt {_utc_text(std + 60)}."
        en_z = f"{z[1]} is on standard time right now, {_utc_text(std)}; during daylight saving time it is {_utc_text(std + 60)}."
    return Ergebnis(f"{de_z} Dort ist es jetzt {_uhr(dort.hour, dort.minute, False)} ({tag_de}), nach der Uhr dieses Geräts.",
                    f"{en_z} It is {_uhr(dort.hour, dort.minute, True, True)} there right now ({tag_en}), by this device's clock.")


_UMSTELLUNG = re.compile(
    r"(?i)^(?:wann\s+(?:ist|wird|kommt|beginnt|endet|startet|fängt|faengt|hört|hoert)\s+(?:die\s+|der\s+)?(?:nächste\s+|naechste\s+)?"
    r"(?:zeitumstellung|zeitumstellung|sommerzeit|winterzeit|uhr\s+umgestellt|uhrumstellung|normalzeit)(?:\s+(?:an|auf|um|zurück|vor|zu\s+ende))?"
    r"|wann\s+(?:wird|werden)\s+(?:die\s+)?uhr(?:en)?\s+(?:umgestellt|zurückgestellt|vorgestellt)"
    r"|when\s+(?:does|do|is|will)\s+(?:the\s+)?(?:daylight\s+saving(?:s)?(?:\s+time)?|dst|summer\s+time|clocks?|time\s+change|clock\s+change)"
    r"(?:\s+(?:end|start|begin|change|go\s+back|go\s+forward|spring\s+forward|fall\s+back))?)"
    rf"(?:\s+(?:in|im|für|fuer|for)\s+(?:the\s+)?(?P<o>{_NAMEN_RE}|europa|europe|eu|us|usa|united\s+states|amerika))?"
    r"(?:\s+(?P<j>this\s+year|next\s+year|next|heuer|dieses\s+jahr|nächstes\s+jahr|naechstes\s+jahr|2\d{3}))?$")


def _naechster_wechsel(regel: str, std: int, ab: datetime) -> tuple[datetime, bool] | None:
    if not regel:
        return None
    t = ab.replace(minute=0, second=0, microsecond=0)
    jetzt = sommerzeit(regel, std, t)
    for _ in range(400 * 24):
        t += timedelta(hours=1)
        s = sommerzeit(regel, std, t)
        if s != jetzt:
            return t, s
    return None


def _umstellung(t: str) -> Ergebnis | None:
    m = _UMSTELLUNG.match(t)
    if not m:
        return None
    import rechnen_datum
    gefragt = (m.group("o") or "").lower()
    if gefragt in ("australien", "australia"):
        return None
    usa = gefragt in ("us", "usa", "united states", "amerika")
    europa = gefragt in ("europa", "europe", "eu")
    englisch = bool(re.match(r"(?i)when\b", t))
    if gefragt and not (usa or europa):
        orte = [(gefragt, None, None)]
    elif usa:
        orte = [("new york", "den USA", "the US")]
    elif europa or not englisch:
        orte = [("wien", "Europa (EU und Schweiz)", "Europe (EU and Switzerland)")]
    else:
        orte = [("wien", "Europa (EU und Schweiz)", "Europe (EU and Switzerland)"), ("new york", "den USA", "the US")]
    utc = jetzt_utc()
    j = (m.group("j") or "").lower()
    jahr = int(j) if j.isdigit() else (utc.year if j in ("this year", "heuer", "dieses jahr") else
                                       utc.year + 1 if j in ("next year", "nächstes jahr", "naechstes jahr") else None)
    if jahr is not None:
        utc = datetime(jahr, 1, 1, tzinfo=timezone.utc)
    de, en = [], []
    for ort, name_de, name_en in orte:
        z = _zone(ort)
        name_de, name_en = name_de or z[0], name_en or z[1]
        w1 = _naechster_wechsel(z[3], z[2], utc)
        if w1 is None:
            de.append(f"In {name_de} gibt es keine Sommerzeit, die Uhr bleibt das ganze Jahr bei {_utc_text(z[2])}.")
            en.append(f"{name_en} has no daylight saving time; it stays on {_utc_text(z[2])} all year.")
            continue
        w2 = _naechster_wechsel(z[3], z[2], w1[0])
        wechsel = [w1, w2]
        winter = bool(re.search(r"(?i)\b(?:winterzeit|normalzeit|standard\s+time)\b", t))
        verb_ende = bool(re.search(r"(?i)\b(?:endet|enden|ends?|zu\s+ende)\b", t))
        verb_beginn = bool(re.search(r"(?i)\b(?:beginnt|beginnen|startet|fängt|faengt|starts?|begins?)\b", t))
        zurueck = bool(re.search(r"(?i)\b(?:zurück\w*|back|fall)\b", t))
        vor = bool(re.search(r"(?i)\b(?:vorgestellt|vorstellen|forward|spring)\b", t))
        will_ende = zurueck or (verb_beginn if winter else verb_ende)
        will_beginn = vor or (verb_ende if winter else verb_beginn)
        will_ende, will_beginn = will_ende and not will_beginn, will_beginn and not will_ende
        if (will_ende and w1[1]) or (will_beginn and not w1[1]):
            wechsel.reverse()
        teile = []
        for wann, beginnt in wechsel:
            vorher = ortszeit(z, wann - timedelta(minutes=1)) + timedelta(minutes=1)
            tag = vorher.date()
            nach_h = vorher.hour + (1 if beginnt else -1)
            if not (0 <= nach_h <= 23):
                return None
            von, nach = str(vorher.hour), str(nach_h)
            teile.append((beginnt, von, nach,
                          f"{_TAGE_DE[tag.weekday()]}, {tag.day}. {rechnen_datum.MONATE_DE[tag.month - 1]} {tag.year}",
                          f"{_TAGE_EN[tag.weekday()]}, {rechnen_datum.MONATE_EN[tag.month - 1]} {tag.day}, {tag.year}"))
        (b1, v1, n1, d1, e1), (b2, v2, n2, d2, e2) = teile
        de.append(f"In {name_de} {'beginnt' if b1 else 'endet'} die Sommerzeit am {d1}: die Uhr wird um {v1} Uhr auf {n1} Uhr "
                  f"{'vorgestellt' if b1 else 'zurückgestellt'}. {'Davor' if wechsel[0] is not w1 else 'Danach'} {'beginnt' if b2 else 'endet'} sie am {d2} ({v2} Uhr auf {n2} Uhr).")
        en.append(f"In {name_en}, daylight saving time {'starts' if b1 else 'ends'} on {e1}, when clocks go {'forward' if b1 else 'back'} "
                  f"from {v1} am to {n1} am. {'Before that' if wechsel[0] is not w1 else 'After that'} it {'starts' if b2 else 'ends'} on {e2} ({v2} am to {n2} am).")
    return Ergebnis(" ".join(de) + " Gerechnet nach den geltenden Regeln.", " ".join(en) + " Worked out from the current rules.")


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
