# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta

import kalender_at
import kalender_tage
import kalender_welt
import region as region_mod

WOCHENTAGE = kalender_at.WOCHENTAGE
BETRIFFT = re.compile(kalender_at.BETRIFFT.pattern + r"|tag der deutschen einheit|reformationstag|bu(?:ß|ss)[-\s]+und[-\s]+bettag|bundesfeiertag|auffahrt|"
                      r"berchtoldstag|frauentag|weltkindertag|pfingstmontag|karfreitag|ostermontag|\bschulferien\b|\bferien\b", re.I)
_FERIEN = re.compile(r"ferien", re.I)

DE_LAENDER = {k: n for land, k, n, _ in region_mod.GEBIETE if land == "de"}


def _heute_frager():
    try:
        import ki_laufzeit
        return ki_laufzeit.heute()
    except Exception:
        from datetime import date as _d
        return _d.today()


def _buss_und_bettag(jahr: int) -> date:
    d = date(jahr, 11, 22)
    return d - timedelta(days=(d.weekday() - 2) % 7)


def feiertage_de(jahr: int) -> list[tuple[date, str, tuple[str, ...], tuple[str, tuple[str, ...]]]]:
    ohne = ("", ())
    o = kalender_at.ostersonntag(jahr)
    liste = [
        (date(jahr, 1, 1), "Neujahr", (), ohne),
        (date(jahr, 1, 6), "Heilige Drei Könige", ("BW", "BY", "ST"), ohne),
        (date(jahr, 3, 8), "Internationaler Frauentag", ("BE", "MV"), ohne),
        (o - timedelta(days=2), "Karfreitag", (), ohne),
        (o, "Ostersonntag", ("BB",), ohne),
        (o + timedelta(days=1), "Ostermontag", (), ohne),
        (date(jahr, 5, 1), "Tag der Arbeit", (), ohne),
        (o + timedelta(days=39), "Christi Himmelfahrt", (), ohne),
        (o + timedelta(days=49), "Pfingstsonntag", ("BB",), ohne),
        (o + timedelta(days=50), "Pfingstmontag", (), ohne),
        (o + timedelta(days=60), "Fronleichnam", ("BW", "BY", "HE", "NW", "RP", "SL"), ("in Sachsen und Thüringen nur in einzelnen Gemeinden", ("SN", "TH"))),
        (date(jahr, 8, 8), "Augsburger Friedensfest", ("BY",), ("nur in der Stadt Augsburg", ("BY",))),
        (date(jahr, 8, 15), "Mariä Himmelfahrt", ("SL", "BY"), ("in Bayern nur in Gemeinden mit überwiegend katholischer Bevölkerung", ("BY",))),
        (date(jahr, 9, 20), "Weltkindertag", ("TH",), ohne),
        (date(jahr, 10, 3), "Tag der Deutschen Einheit", (), ohne),
        (date(jahr, 10, 31), "Reformationstag", ("BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH"), ohne),
        (date(jahr, 11, 1), "Allerheiligen", ("BW", "BY", "NW", "RP", "SL"), ohne),
        (_buss_und_bettag(jahr), "Buß- und Bettag", ("SN",), ohne),
        (date(jahr, 12, 25), "1. Weihnachtsfeiertag", (), ohne),
        (date(jahr, 12, 26), "2. Weihnachtsfeiertag", (), ohne),
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
    return bool(BETRIFFT.search(frage or "")) or kalender_tage.betrifft(frage)


def _text_de(r: region_mod.Region, h: date, jahre: list[int] | None = None) -> str:
    alle = [x for j in jahre for x in feiertage_de(j)] if jahre else [x for j in (h.year, h.year + 1) for x in feiertage_de(j) if x[0] >= h]
    welche = f", für {', '.join(str(j) for j in jahre)}:" if jahre else ". Die nächsten:"
    if r.gebiet:
        gelten = [x for x in alle if not x[2] or r.gebiet in x[2] or r.gebiet in x[3][1]][:None if jahre else 12]
        zeilen = [f"Gesetzliche Feiertage in {r.name} (Deutschland), vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}){welche}"]
        zeilen += [f"– {n}: {_tag(d)}" + (f" ({z})" if z and r.gebiet in z_l else "") for d, n, _x_l, (z, z_l) in gelten]
    else:
        zeilen = [f"Gesetzliche Feiertage in Deutschland, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}){welche}"]
        for d, n, x_l, (z, _z_l) in alle[:None if jahre else 16]:
            wo = "bundesweit" if not x_l else "nur in " + ", ".join(DE_LAENDER[k] for k in x_l)
            zeilen.append(f"– {n}: {_tag(d)}, {wo}" + (f" ({z})" if z else ""))
    return "\n".join(zeilen)


def _text_ch(r: region_mod.Region, h: date, jahre: list[int] | None = None) -> str:
    alle = [x for j in jahre for x in feiertage_ch(j)] if jahre else [x for j in (h.year, h.year + 1) for x in feiertage_ch(j) if x[0] >= h][:14]
    wo = f" ({r.name})" if r.name else ""
    zeilen = [f"Feiertage in der Schweiz{wo}, vom Programm aus dem Kalender berechnet (heute ist {_tag(h)}). Einheitlich ist nur der Bundesfeiertag; "
              "die übrigen Feiertage legt jeder Kanton selbst fest." + (f" Für {', '.join(str(j) for j in jahre)}:" if jahre else " Die nächsten:")]
    zeilen += [f"– {n}: {_tag(d)}, {wo_}" for d, n, wo_ in alle]
    if r.name:
        zeilen.append(f"Welche dieser Feiertage im {r.name} gelten, steht nicht in diesem Kalender, sondern in den gefundenen Seiten.")
    return "\n".join(zeilen)


def quelle(frage: str, heute: date | None = None) -> tuple[str, str, bool] | None:
    welt = kalender_tage.zeitumstellung_welt(frage, heute)
    if welt is not None:
        return welt
    if not betrifft(frage):
        return None
    if kalender_welt.land(frage) is not None:
        return None
    h = heute or _heute_frager()
    jahre = kalender_tage.jahre(frage, h)
    feiertag = _feiertage(frage, h, jahre) if BETRIFFT.search(frage or "") else None
    if not kalender_tage.betrifft(frage):
        return feiertag
    termine = kalender_tage.text(frage, h)
    if feiertag is None:
        return "Termine im Kalender (vom Programm berechnet)", termine, True
    return feiertag[0], feiertag[1] + "\n\n" + termine, feiertag[2]


def _feiertage(frage: str, h: date, jahre: list[int]) -> tuple[str, str, bool] | None:
    r = region_mod.erkennen(frage)
    ferien = bool(_FERIEN.search(frage or ""))
    if r is None or r.land == "at":
        if ferien and not re.search(r"herbstferien", frage or "", re.I):
            return None
        return "Feiertage und Herbstferien in Österreich (vom Programm berechnet)", kalender_at.text(h, jahre), True
    if ferien:
        return None
    if r.land == "de":
        return f"Feiertage in {r.text()} (vom Programm berechnet)", _text_de(r, h, jahre), True
    return f"Feiertage in {r.text()} (vom Programm berechnet)", _text_ch(r, h, jahre), False


__all__ = ["feiertage_de", "feiertage_ch", "quelle", "betrifft"]
