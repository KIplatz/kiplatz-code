# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
BETRIFFT = re.compile(r"feiertag|fenstertag|herbstferien|allerheiligen|nationalfeiertag|ostern|pfingst|christi himmelfahrt|fronleichnam|"
                      r"maria empfängnis|mariä himmelfahrt|staatsfeiertag|heilige drei könige|stefanitag|weihnachtsfeiertag", re.I)


def ostersonntag(jahr: int) -> date:
    k = jahr // 100
    m = 15 + (3 * k + 3) // 4 - (8 * k + 13) // 25
    s = 2 - (3 * k + 3) // 4
    a = jahr % 19
    d = (19 * a + m) % 30
    r = (d + a // 11) // 29
    og = 21 + d - r
    sz = 7 - (jahr + jahr // 4 + s) % 7
    oe = 7 - (og - sz) % 7
    return date(jahr, 3, 1) + timedelta(days=og + oe - 1)


def feiertage(jahr: int) -> list[tuple[date, str]]:
    o = ostersonntag(jahr)
    liste = [(date(jahr, 1, 1), "Neujahr"), (date(jahr, 1, 6), "Heilige Drei Könige"), (o + timedelta(days=1), "Ostermontag"),
             (date(jahr, 5, 1), "Staatsfeiertag"), (o + timedelta(days=39), "Christi Himmelfahrt"), (o + timedelta(days=50), "Pfingstmontag"),
             (o + timedelta(days=60), "Fronleichnam"), (date(jahr, 8, 15), "Mariä Himmelfahrt"), (date(jahr, 10, 26), "Nationalfeiertag"),
             (date(jahr, 11, 1), "Allerheiligen"), (date(jahr, 12, 8), "Mariä Empfängnis"), (date(jahr, 12, 25), "Christtag"),
             (date(jahr, 12, 26), "Stefanitag")]
    return sorted(liste)


def _tag(d: date) -> str:
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}.{d.month}.{d.year}"


def text(heute: date | None = None, jahre: list[int] | None = None) -> str:
    h = heute or date.today()
    if jahre:
        kommend = [(d, n) for j in jahre for d, n in feiertage(j)]
        zeilen = [f"Gesetzliche Feiertage in Österreich {', '.join(str(j) for j in jahre)}, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}):"]
    else:
        kommend = [(d, n) for j in (h.year, h.year + 1) for d, n in feiertage(j) if d >= h][:14]
        zeilen = [f"Gesetzliche Feiertage in Österreich, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}). Die nächsten:"]
    zeilen += [f"– {n}: {_tag(d)}" for d, n in kommend]
    hj = (jahre[0] if jahre else (h.year if h <= date(h.year, 10, 31) else h.year + 1))
    zeilen.append(f"Herbstferien an allen Schulen in Österreich (alle Bundesländer, seit dem Schuljahr 2020/21): "
                  f"{_tag(date(hj, 10, 27))} bis {_tag(date(hj, 10, 31))}.")
    return "\n".join(zeilen)


def betrifft(frage: str) -> bool:
    return bool(BETRIFFT.search(frage or ""))


__all__ = ["ostersonntag", "feiertage", "text", "betrifft"]
