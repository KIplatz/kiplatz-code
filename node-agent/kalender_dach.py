# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta

import kalender_at
import region as region_mod

WOCHENTAGE = kalender_at.WOCHENTAGE
BETRIFFT = re.compile(kalender_at.BETRIFFT.pattern + r"|tag der deutschen einheit|reformationstag|bu(?:ß|ss)[-\s]+und[-\s]+bettag|bundesfeiertag|auffahrt|"
                      r"berchtoldstag|frauentag|weltkindertag|pfingstmontag|karfreitag|ostermontag|\bschulferien\b|\bferien\b", re.I)
_FERIEN = re.compile(r"ferien", re.I)

DE_LAENDER = {k: n for land, k, n, _ in region_mod.GEBIETE if land == "de"}


def _buss_und_bettag(jahr: int) -> date:
    d = date(jahr, 11, 22)
    return d - timedelta(days=(d.weekday() - 2) % 7)


def feiertage_de(jahr: int) -> list[tuple[date, str, tuple[str, ...], str]]:
    o = kalender_at.ostersonntag(jahr)
    liste = [
        (date(jahr, 1, 1), "Neujahr", (), ""),
        (date(jahr, 1, 6), "Heilige Drei Könige", ("BW", "BY", "ST"), ""),
        (date(jahr, 3, 8), "Internationaler Frauentag", ("BE", "MV"), ""),
        (o - timedelta(days=2), "Karfreitag", (), ""),
        (o, "Ostersonntag", ("BB",), ""),
        (o + timedelta(days=1), "Ostermontag", (), ""),
        (date(jahr, 5, 1), "Tag der Arbeit", (), ""),
        (o + timedelta(days=39), "Christi Himmelfahrt", (), ""),
        (o + timedelta(days=49), "Pfingstsonntag", ("BB",), ""),
        (o + timedelta(days=50), "Pfingstmontag", (), ""),
        (o + timedelta(days=60), "Fronleichnam", ("BW", "BY", "HE", "NW", "RP", "SL"), "in Sachsen und Thüringen nur in einzelnen Gemeinden"),
        (date(jahr, 8, 8), "Augsburger Friedensfest", ("BY",), "nur in der Stadt Augsburg"),
        (date(jahr, 8, 15), "Mariä Himmelfahrt", ("SL", "BY"), "in Bayern nur in Gemeinden mit überwiegend katholischer Bevölkerung"),
        (date(jahr, 9, 20), "Weltkindertag", ("TH",), ""),
        (date(jahr, 10, 3), "Tag der Deutschen Einheit", (), ""),
        (date(jahr, 10, 31), "Reformationstag", ("BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH"), ""),
        (date(jahr, 11, 1), "Allerheiligen", ("BW", "BY", "NW", "RP", "SL"), ""),
        (_buss_und_bettag(jahr), "Buß- und Bettag", ("SN",), ""),
        (date(jahr, 12, 25), "1. Weihnachtsfeiertag", (), ""),
        (date(jahr, 12, 26), "2. Weihnachtsfeiertag", (), ""),
    ]
    return sorted(liste, key=lambda x: x[0])


def feiertage_ch(jahr: int) -> list[tuple[date, str, str]]:
    o = kalender_at.ostersonntag(jahr)
    liste = [
        (date(jahr, 1, 1), "Neujahr", "in allen Kantonen"),
        (date(jahr, 1, 2), "Berchtoldstag", "in vielen Kantonen"),
        (o - timedelta(days=2), "Karfreitag", "in den meisten Kantonen"),
        (o + timedelta(days=1), "Ostermontag", "in den meisten Kantonen"),
        (date(jahr, 5, 1), "Tag der Arbeit", "in einigen Kantonen"),
        (o + timedelta(days=39), "Auffahrt", "in allen Kantonen"),
        (o + timedelta(days=50), "Pfingstmontag", "in den meisten Kantonen"),
        (o + timedelta(days=60), "Fronleichnam", "in katholischen Kantonen"),
        (date(jahr, 8, 1), "Bundesfeiertag", "in der ganzen Schweiz"),
        (date(jahr, 8, 15), "Mariä Himmelfahrt", "in katholischen Kantonen"),
        (date(jahr, 11, 1), "Allerheiligen", "in katholischen Kantonen"),
        (date(jahr, 12, 8), "Mariä Empfängnis", "in katholischen Kantonen"),
        (date(jahr, 12, 25), "Weihnachtstag", "in allen Kantonen"),
        (date(jahr, 12, 26), "Stephanstag", "in den meisten Kantonen"),
    ]
    return sorted(liste, key=lambda x: x[0])


def _tag(d: date) -> str:
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}.{d.month}.{d.year}"


def betrifft(frage: str) -> bool:
    return bool(BETRIFFT.search(frage or ""))


def _text_de(r: region_mod.Region, h: date) -> str:
    alle = [x for j in (h.year, h.year + 1) for x in feiertage_de(j) if x[0] >= h]
    if r.gebiet:
        gelten = [x for x in alle if not x[2] or r.gebiet in x[2]][:12]
        zeilen = [f"Gesetzliche Feiertage in {r.name} (Deutschland), vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}). Die nächsten:"]
        zeilen += [f"– {n}: {_tag(d)}" + (f" ({z})" if z and r.gebiet in x_l else "") for d, n, x_l, z in gelten]
    else:
        zeilen = [f"Gesetzliche Feiertage in Deutschland, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}). Die nächsten:"]
        for d, n, x_l, z in alle[:16]:
            wo = "bundesweit" if not x_l else "nur in " + ", ".join(DE_LAENDER[k] for k in x_l)
            zeilen.append(f"– {n}: {_tag(d)}, {wo}" + (f" ({z})" if z else ""))
    return "\n".join(zeilen)


def _text_ch(r: region_mod.Region, h: date) -> str:
    alle = [x for j in (h.year, h.year + 1) for x in feiertage_ch(j) if x[0] >= h][:14]
    wo = f" ({r.name})" if r.name else ""
    zeilen = [f"Feiertage in der Schweiz{wo}, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}). Einheitlich ist nur der Bundesfeiertag; "
              "die übrigen Feiertage legt jeder Kanton selbst fest. Die nächsten:"]
    zeilen += [f"– {n}: {_tag(d)}, {wo_}" for d, n, wo_ in alle]
    if r.name:
        zeilen.append(f"Welche dieser Feiertage im {r.name} gelten, steht nicht in diesem Kalender, sondern in den gefundenen Seiten.")
    return "\n".join(zeilen)


def quelle(frage: str, heute: date | None = None) -> tuple[str, str, bool] | None:
    if not betrifft(frage):
        return None
    h = heute or date.today()
    r = region_mod.erkennen(frage)
    ferien = bool(_FERIEN.search(frage or ""))
    if r is None or r.land == "at":
        if ferien and not re.search(r"herbstferien", frage or "", re.I):
            return None
        return "Feiertage und Herbstferien in Österreich (vom Programm berechnet)", kalender_at.text(h), True
    if ferien:
        return None
    if r.land == "de":
        return f"Feiertage in {r.text()} (vom Programm berechnet)", _text_de(r, h), True
    return f"Feiertage in {r.text()} (vom Programm berechnet)", _text_ch(r, h), False


__all__ = ["feiertage_de", "feiertage_ch", "quelle", "betrifft"]
