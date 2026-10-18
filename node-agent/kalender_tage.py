# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta

import kalender_at
import laender

WOCHENTAGE = kalender_at.WOCHENTAGE

BETRIFFT = re.compile(r"advent|aschermittwoch|fasching|fastnacht|rosenmontag|palmsonntag|gründonnerstag|karfreitag|karsamstag|ostersonntag|"
                      r"\bostern\b|pfingstsonntag|\bpfingsten\b|muttertag|vatertag|zeit-?umstellung|uhren-?umstellung|sommerzeit|winterzeit|uhr(?:en)?\b.{0,25}\bum(?:ge)?stell|"
                      r"umstellung der uhr|totensonntag|ewigkeitssonntag|volkstrauertag|nikolaus|heilige[nr]? abend|heiligabend|silvester|"
                      r"valentinstag|halloween|martini|weihnachten|"
                      r"\beaster\b|good friday|ash wednesday|palm sunday|pentecost|whitsun|shrove tuesday|valentine'?s day|\badvent\b", re.I)
_WANN = re.compile(r"\bwann\b|\bwelche[mnrs]?\b.{0,25}\b(?:tag|datum|sonntag|wochentag|termin)\b|\bdatum\b|\bf[äa]llt\b|\bbeginn\w*\b|\bstartet\b|"
                   r"\bend(?:et|e)\b|\bwie viele tage\b|\bwie lange (?:noch|bis)\b|\bist\b.{0,40}\b(?:19|20)\d\d\b|\bam wievielten\b|"
                   r"\bwhen\b|\bwhat (?:date|day)\b|\bwhich (?:date|day|sunday)\b|\bhow many days\b|\bis\b.{0,40}\b(?:19|20)\d\d\b", re.I)
_DACH = frozenset({"AT", "DE", "CH", "LI"})
_JAHR = re.compile(r"\b(19[5-9]\d|20\d\d|21\d\d)\b")


def _letzter_sonntag(jahr: int, monat: int) -> date:
    ende = date(jahr + (monat == 12), monat % 12 + 1, 1) - timedelta(days=1)
    return ende - timedelta(days=(ende.weekday() + 1) % 7)


def _nter_sonntag(jahr: int, monat: int, n: int) -> date:
    erster = date(jahr, monat, 1)
    return erster + timedelta(days=(6 - erster.weekday()) % 7 + 7 * (n - 1))


def erster_advent(jahr: int) -> date:
    heiligabend = date(jahr, 12, 24)
    return heiligabend - timedelta(days=(heiligabend.weekday() + 1) % 7) - timedelta(days=21)


def tage(jahr: int) -> list[tuple[date, str]]:
    o = kalender_at.ostersonntag(jahr)
    a1 = erster_advent(jahr)
    liste = [
        (o - timedelta(days=48), "Rosenmontag"), (o - timedelta(days=47), "Faschingsdienstag (Fastnacht)"),
        (o - timedelta(days=46), "Aschermittwoch, Beginn der Fastenzeit"), (o - timedelta(days=7), "Palmsonntag"),
        (o - timedelta(days=3), "Gründonnerstag"), (o - timedelta(days=2), "Karfreitag"), (o - timedelta(days=1), "Karsamstag"),
        (o, "Ostersonntag"), (o + timedelta(days=49), "Pfingstsonntag"),
        (_nter_sonntag(jahr, 5, 2), "Muttertag (Österreich, Deutschland, Schweiz)"), (_nter_sonntag(jahr, 6, 2), "Vatertag in Österreich"),
        (_letzter_sonntag(jahr, 3), "Zeitumstellung auf Sommerzeit (Uhr um 2 Uhr eine Stunde vor)"),
        (_letzter_sonntag(jahr, 10), "Zeitumstellung auf Winterzeit (Uhr um 3 Uhr eine Stunde zurück)"),
        (a1 - timedelta(days=14), "Volkstrauertag (Deutschland)"), (a1 - timedelta(days=7), "Totensonntag (Ewigkeitssonntag)"),
        (a1, "1. Advent, Beginn der Adventszeit und des Kirchenjahres"), (a1 + timedelta(days=7), "2. Advent"),
        (a1 + timedelta(days=14), "3. Advent"), (a1 + timedelta(days=21), "4. Advent"),
        (date(jahr, 2, 14), "Valentinstag"), (date(jahr, 10, 31), "Halloween"), (date(jahr, 11, 11), "Martini"),
        (date(jahr, 12, 6), "Nikolaus"), (date(jahr, 12, 24), "Heiliger Abend"), (date(jahr, 12, 31), "Silvester"),
    ]
    return sorted(liste)


def _tag(d: date) -> str:
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}.{d.month}.{d.year}"


def jahre(frage: str) -> list[int]:
    return list(dict.fromkeys(int(j) for j in _JAHR.findall(frage or "")))[:3]


def betrifft(frage: str) -> bool:
    return bool(BETRIFFT.search(frage or "")) and bool(_WANN.search(frage or "")) and not (laender.alle(frage) - _DACH)


_GLEICH = {"uhren": "zeitu", "umges": "zeitu", "umste": "zeitu", "somme": "zeitu", "winte": "zeitu", "weihn": "heili", "heili": "heili",
           "fastn": "fasch", "karne": "rosen", "ewigk": "toten", "easte": "oster", "frida": "karfr", "wedne": "asche", "pente": "pfing",
           "whits": "pfing", "shrov": "fasch", "valen": "valen"}


def _gefragt(frage: str, name: str) -> bool:
    kern = re.split(r"[,(]", name, maxsplit=1)[0].lower()
    stamm = {w[:5] for w in re.findall(r"[a-zäöüß]{5,}", kern)}
    worte = {w[:5] for w in re.findall(r"[a-zäöüß]{5,}", (frage or "").lower())}
    return bool(stamm & (worte | {_GLEICH[w] for w in worte if w in _GLEICH}))


def text(frage: str, heute: date | None = None) -> str:
    h = heute or date.today()
    gefragt = jahre(frage)
    if gefragt:
        eintraege = [x for j in gefragt for x in tage(j)]
        kopf = f"Termine im Kalender {', '.join(str(j) for j in gefragt)}, vom Programm berechnet (heute ist {_tag(h)}):"
    else:
        eintraege = [x for j in (h.year, h.year + 1) for x in tage(j) if x[0] >= h]
        kopf = f"Termine im Kalender, vom Programm berechnet (heute ist {_tag(h)}). Die nächsten:"
    passend = [x for x in eintraege if _gefragt(frage, x[1])]
    return "\n".join([kopf] + [f"– {n}: {_tag(d)}" for d, n in (passend or eintraege)])


__all__ = ["erster_advent", "tage", "jahre", "betrifft", "text"]
