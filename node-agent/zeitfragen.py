# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import urllib.request
from datetime import date

import belege
import kalender_at
import stellen

FRAGEN: tuple[tuple[str, str], ...] = (
    ("bl_naechstes_ASK", "Wann spielt der LASK als Nächstes?"),
    ("bl_fuehrer", "Wer führt gerade die österreichische Bundesliga an?"),
    ("ezb", "Wie hoch ist der Leitzins der EZB?"),
    ("klimaticket", "Was kostet das Klimaticket Österreich?"),
    ("kilometergeld", "Wie hoch ist das amtliche Kilometergeld in Österreich?"),
    ("feiertag", "Wann ist der nächste Feiertag in Österreich?"),
    ("herbstferien", "Wann sind die Herbstferien in Oberösterreich?"),
)


def _oeffner(req, timeout=None):
    return urllib.request.urlopen(req, timeout=timeout)


def erwartung(schluessel: str, heute: date, lesen=None) -> dict:
    lesen = lesen or stellen.Leser(oeffner=_oeffner)
    if schluessel.startswith("bl_"):
        _, tabelle = stellen.tabelle_lesen(stellen.seitentext(lesen(f"{stellen.BL}/tabelle"), nur_hauptteil=False))
        if len(tabelle) < 6:
            raise stellen.StelleError("STELLE_FORM", "Tabelle nicht lesbar")
        if schluessel == "bl_fuehrer":
            name = tabelle[0]["name"]
            return {"art": "wort", "werte": [name.split()[-1]], "text": f"Tabellenführer: {name}"}
        verein = schluessel.split("_")[-1]
        namen = {z["kurz"]: z["name"] for z in tabelle}
        spiele = []
        adressen = [f"{stellen.BL}/spielplan"]
        for adresse_nr in range(4):
            spiele += stellen.spiele_lesen(stellen.seitentext(lesen(adressen[-1]), nur_hauptteil=False), namen)
            kommend = sorted((s for s in spiele if verein in (s["heim"], s["gast"]) and not s["ergebnis"] and s["datum"] >= heute), key=lambda s: s["datum"])
            if kommend:
                s = kommend[0]
                return {"art": "datum", "werte": [(s["datum"].day, s["datum"].month)], "text": f"{s['datum'].strftime('%d.%m.%Y')}: {s['heim_name']} gegen {s['gast_name']}"}
            runde = max((x["runde"] for x in spiele), default=0) + 1
            adressen.append(f"{stellen.BL}/spielplan?spieltag={runde}")
        raise stellen.StelleError("STELLE_FORM", "kein kommendes Spiel im Spielplan")
    if schluessel == "ezb":
        r = [x for x in stellen.ezb_lesen(lesen(stellen.EZB)) if x["ab"] <= heute]
        if not r:
            raise stellen.StelleError("STELLE_FORM", "Zinstabelle nicht lesbar")
        return {"art": "zahl", "werte": [r[0]["haupt"], r[0]["einlage"]], "text": f"Hauptrefinanzierung {r[0]['haupt']} %, Einlagen {r[0]['einlage']} % seit {r[0]['ab']}"}
    if schluessel == "klimaticket":
        f = stellen.klimaticket("Klimaticket", heute, lesen)[0].text
        m = re.search(r"Classic ([\d.]+),(\d\d) €", f)
        if not m:
            raise stellen.StelleError("STELLE_FORM", "Preis nicht lesbar")
        wert = float(m.group(1).replace(".", "") + "." + m.group(2))
        return {"art": "zahl", "werte": [wert], "text": f"Classic {m.group(1)},{m.group(2)} €"}
    if schluessel == "kilometergeld":
        t = stellen.seitentext(lesen(stellen.SEITEN[0].adresse))
        m = re.search(r"PKW (\d+),(\d\d)", t)
        if not m:
            raise stellen.StelleError("STELLE_FORM", "Kilometergeld nicht lesbar")
        return {"art": "zahl", "werte": [float(f"{m.group(1)}.{m.group(2)}")], "text": f"PKW {m.group(1)},{m.group(2)} €"}
    if schluessel == "feiertag":
        d, name = next((d, n) for j in (heute.year, heute.year + 1) for d, n in kalender_at.feiertage(j) if d >= heute)
        return {"art": "datum", "werte": [(d.day, d.month)], "text": f"{name}, {d.strftime('%d.%m.%Y')}"}
    if schluessel == "herbstferien":
        j = heute.year if heute <= date(heute.year, 10, 31) else heute.year + 1
        return {"art": "datum", "werte": [(27, 10)], "text": f"27.10.{j} bis 31.10.{j}"}
    raise stellen.StelleError("STELLE_UNBEKANNT", schluessel)


def bewerten(antwort: str, erw: dict) -> tuple[bool, list[str]]:
    a = antwort or ""
    if erw["art"] == "datum":
        ds = {(t, m) for t, m, _ in belege.daten(a)}
        ok = any(tuple(w) in ds for w in erw["werte"])
        return ok, [] if ok else [erw["text"]]
    if erw["art"] == "zahl":
        zs = belege.zahlenwerte(a)
        ok = any(any(abs(z - float(w)) < 0.005 for z in zs) for w in erw["werte"])
        return ok, [] if ok else [erw["text"]]
    ok = any(str(w).lower() in a.lower() for w in erw["werte"])
    return ok, [] if ok else [erw["text"]]


__all__ = ["FRAGEN", "erwartung", "bewerten"]
