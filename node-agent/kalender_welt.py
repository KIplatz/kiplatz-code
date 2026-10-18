# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date

import feiertage_namen
import kalender_at
import kalender_tage
import laender

DACH = {"AT", "DE", "CH", "LI"}
DEUTSCH = {
    "New Year's Day": "Neujahr", "Christmas Day": "Christtag, Weihnachten", "Easter Monday": "Ostermontag",
    "St. Stephen's Day": "Stefanitag, Zweiter Weihnachtstag", "Good Friday": "Karfreitag", "Labour Day": "Tag der Arbeit",
    "Labor Day": "Tag der Arbeit", "May Day": "Tag der Arbeit", "International Workers' Day": "Tag der Arbeit",
    "International Workers Day": "Tag der Arbeit", "Easter Sunday": "Ostersonntag, Ostern", "Pentecost": "Pfingstsonntag, Pfingsten",
    "Whit Monday": "Pfingstmontag", "Epiphany": "Heilige Drei Könige", "Assumption Day": "Mariä Himmelfahrt", "Assumption": "Mariä Himmelfahrt",
    "Christmas Eve": "Heiliger Abend", "Ascension Day": "Christi Himmelfahrt", "All Saints' Day": "Allerheiligen", "All Saints Day": "Allerheiligen",
    "Independence Day": "Unabhängigkeitstag", "Liberation Day": "Tag der Befreiung", "Corpus Christi": "Fronleichnam",
    "Constitution Day": "Tag der Verfassung", "Armistice Day": "Waffenstillstand 1918", "Republic Day": "Tag der Republik",
    "Immaculate Conception": "Mariä Empfängnis", "Maundy Thursday": "Gründonnerstag", "Holy Saturday": "Karsamstag",
    "Remembrance Day": "Gedenktag", "National Day": "Nationalfeiertag", "New Year's Eve": "Silvester", "Midsummer Eve": "Mittsommerabend",
    "Midsummer Day": "Mittsommertag", "Victory in Europe Day": "Tag des Sieges, Kriegsende 1945", "Bastille Day": "Nationalfeiertag",
    "St. John's Day": "Johannistag", "Thanksgiving Day": "Thanksgiving, Erntedankfest", "Columbus Day": "Kolumbus-Tag",
    "Veterans Day": "Veteranentag", "Saint Patrick's Day": "St. Patrick's Day", "All Souls' Day": "Allerseelen",
}
_FEIERTAG = re.compile(r"feiertag|holiday|nationalfeiertag|unabhängigkeitstag|independence day|thanksgiving|staatsfeiertag|\bbank holiday", re.I)
WOCHENTAGE = kalender_at.WOCHENTAGE


def land(frage: str) -> str | None:
    c = laender.erkennen(frage)
    return c if c and c not in DACH else None


_NAME = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in feiertage_namen.NAMEN) + r")(?![\w])", re.I)
ZWEITES_LAND_ANTEIL = 0.1


def gefragter_feiertag(frage: str) -> str | None:
    m = _NAME.search(frage or "")
    return " ".join(m.group(1).lower().split()) if m else None


def _laender_mit(name: str) -> set[str]:
    muster = re.compile(re.escape(name) + r"(?![\w])", re.I)
    return {c for n, cs in feiertage_namen.NAMEN.items() if muster.match(" ".join(n.split())) for c in cs}


def laender_fuer(frage: str) -> list[str]:
    genannt = laender.alle(frage)
    groesse = lambda c: -laender.EINWOHNER.get(c, 0)
    fremd = sorted((genannt - DACH) & laender.FEIERTAGE, key=groesse)
    if fremd:
        return fremd[:2]
    if genannt & DACH:
        return []
    name = gefragter_feiertag(frage)
    codes = _laender_mit(name) if name else set()
    if not codes or codes & DACH:
        return []
    reihe = sorted(codes & laender.FEIERTAGE, key=groesse)
    erste = laender.EINWOHNER.get(reihe[0], 0) if reihe else 0
    return reihe[:1] + [c for c in reihe[1:2] if laender.EINWOHNER.get(c, 0) >= erste * ZWEITES_LAND_ANTEIL]


def betrifft(frage: str) -> bool:
    return bool(_FEIERTAG.search(frage or "") or gefragter_feiertag(frage)) and bool(laender_fuer(frage))


def jahre(frage: str, heute: date | None = None) -> list[int]:
    h = heute or date.today()
    return kalender_tage.jahre(frage) or [h.year, h.year + 1]


def text(code: str, je_jahr: dict[int, list[dict]], frage: str, heute: date | None = None) -> str:
    h = heute or date.today()
    name = laender.DEUTSCH.get(code, code)
    gefragt = bool(kalender_tage.jahre(frage))
    feiertag = gefragter_feiertag(frage)

    def ist_er(t: dict) -> bool:
        return bool(feiertag) and any(re.match(re.escape(feiertag) + r"(?![\w])", " ".join(str(t.get(k) or "").lower().split()))
                                      for k in ("name", "lokal"))
    if any(ist_er(t) for ts in je_jahr.values() for t in ts):
        je_jahr = {j: [t for t in ts if ist_er(t)] for j, ts in je_jahr.items()}
    zeilen = [f"Gesetzliche Feiertage in {name} ({code}), vom Server bei Nager.Date abgefragt (heute ist {kalender_at._tag(h)})"
              + (":" if gefragt else ". Die nächsten:")]
    for j in sorted(je_jahr):
        for t in je_jahr[j]:
            try:
                d = date.fromisoformat(str(t.get("datum", "")))
            except ValueError:
                continue
            if not gefragt and d < h:
                continue
            lokal = str(t.get("lokal") or "")
            englisch = str(t.get("name") or "")
            gebiete = [str(g) for g in t.get("gebiete") or []]
            andere = [n for n in (englisch, lokal) if n and n != DEUTSCH.get(englisch)]
            zeilen.append(f"– {DEUTSCH.get(englisch, englisch)}" + (f" ({', '.join(dict.fromkeys(andere))})" if DEUTSCH.get(englisch) else
                                                                    (f" ({lokal})" if lokal and lokal != englisch else ""))
                          + f": {WOCHENTAGE[d.weekday()]}, {d.day}.{d.month}.{d.year}" + (f", nur in {', '.join(gebiete[:12])}" if gebiete else ""))
    return "\n".join(zeilen)


__all__ = ["land", "laender_fuer", "gefragter_feiertag", "betrifft", "jahre", "text", "DACH"]
