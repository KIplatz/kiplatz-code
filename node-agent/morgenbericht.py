# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import nachschauen

WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONATE = ("Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
STANDARD_ZEIT = "07:00"
SCHLAGZEILEN = 5
SEITEN = {"orf.at": "ORF.at", "news.at": "news.at", "ots.at": "OTS.at", "tagesschau.de": "tagesschau.de", "zdfheute.de": "ZDFheute.de",
          "deutschlandfunk.de": "Deutschlandfunk.de", "dw.com": "DW.com", "srf.ch": "SRF.ch",
          "bbc.co.uk": "BBC.co.uk", "bbc.com": "BBC.com", "news.sky.com": "Sky News", "npr.org": "NPR.org"}
_LINK = re.compile(r"^\[([^\]\n]{1,160})\]\((https://[^\s)]{1,600})\)$")


def seite(link: str) -> str:
    host = (urllib.parse.urlsplit(link).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return SEITEN.get(host, host)


def einstellung_lesen(e: dict) -> dict:
    zeit = str(e.get("morgen_zeit") or STANDARD_ZEIT)
    if not re.fullmatch(r"\d{2}:\d{2}", zeit):
        zeit = STANDARD_ZEIT
    return {"an": bool(e.get("morgen_an", False)), "zeit": zeit, "ort": " ".join(str(e.get("morgen_ort") or "").split())[:60],
            "vorlesen": bool(e.get("morgen_vorlesen", True)), "zuletzt": str(e.get("morgen_zuletzt") or ""),
            "land": str(e.get("morgen_land") or "")[:2].lower()}


def faellig(e: dict, jetzt: datetime) -> bool:
    s = einstellung_lesen(e)
    if not s["an"]:
        return False
    heute = jetzt.strftime("%Y-%m-%d")
    if s["zuletzt"] == heute:
        return False
    return jetzt.strftime("%H:%M") >= s["zeit"]


def _wetter_zeilen(text: str) -> list[str]:
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    return [re.sub(r"^([^:]{1,60}:)", r"**\1**", z, count=1) for z in zeilen if z.startswith(("Heute", "Morgen"))][:2]


def _schlagzeilen_zeilen(text: str, n: int = SCHLAGZEILEN) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    zeilen = text.splitlines()
    for i, z in enumerate(zeilen):
        m = re.match(r"^\d+\.\s+(.+?)$", z)
        if not m:
            continue
        titel = m.group(1).strip()
        link = zeilen[i + 1].strip() if i + 1 < len(zeilen) and zeilen[i + 1].strip().startswith("https://") else ""
        q = re.match(r"^(.*\S)\s+\([^()]{1,40}\)$", titel)
        if q and link:
            titel = q.group(1)
        if titel:
            out.append((titel, link))
        if len(out) >= n:
            break
    return out


WOCHENTAGE_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONATE_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
WETTER_EN = {"klar": "clear", "meist klar": "mostly clear", "teils bewölkt": "partly cloudy", "bedeckt": "overcast", "Nebel": "fog",
             "Reifnebel": "freezing fog", "leichter Nieselregen": "light drizzle", "Nieselregen": "drizzle", "starker Nieselregen": "heavy drizzle",
             "gefrierender Nieselregen": "freezing drizzle", "leichter Regen": "light rain", "Regen": "rain", "starker Regen": "heavy rain",
             "gefrierender Regen": "freezing rain", "leichter Schneefall": "light snow", "Schneefall": "snow", "starker Schneefall": "heavy snow",
             "Schneegriesel": "snow grains", "leichte Regenschauer": "light showers", "Regenschauer": "showers", "heftige Regenschauer": "heavy showers",
             "Schneeschauer": "snow showers", "starke Schneeschauer": "heavy snow showers", "Gewitter": "thunderstorms",
             "Gewitter mit Hagel": "thunderstorms with hail", "Gewitter mit starkem Hagel": "thunderstorms with heavy hail", "wechselnd": "changeable"}
LAENDER_EN = {"at": "Austria", "de": "Germany", "ch": "Switzerland", "gb": "the UK", "us": "the US"}
_WETTER_ZEILE = re.compile(r"^\*\*(Heute|Morgen), (\w+) (\d{2})\.(\d{2})\.(\d{4}):\*\* (.+?), Höchsttemperatur (-?\d+) °C, Tiefsttemperatur (-?\d+) °C, "
                           r"(kein Regen|Regen ([\d,]+) mm)(?: \(Regenwahrscheinlichkeit (\d+) %\))?, Wind bis (\d+) km/h\.$")


def wetter_zeile_en(zeile: str) -> str:
    m = _WETTER_ZEILE.match(zeile)
    if not m:
        return zeile
    wann, tag, d, mo, j, wie, hoch, tief, regen, mm, chance, wind = m.groups()
    wochentag = WOCHENTAGE_EN[WOCHENTAGE.index(tag)] if tag in WOCHENTAGE else tag
    regen_en = "no rain" if regen == "kein Regen" else f"rain {mm.replace(',', '.')} mm"
    return (f"**{'Today' if wann == 'Heute' else 'Tomorrow'}, {wochentag} {int(d)} {MONATE_EN[int(mo) - 1]} {j}:** {WETTER_EN.get(wie, wie)}, "
            f"high {hoch} °C, low {tief} °C, {regen_en}" + (f" ({chance} % chance of rain)" if chance else "") + f", wind up to {wind} km/h.")


def feed_land(land: str, sprache: str) -> str:
    land = (land or "at").lower()
    if sprache != "en":
        return land if land in nachschauen.FEEDS and nachschauen.FEED_SPRACHE.get(land) == "de" else "at"
    return land if nachschauen.FEED_SPRACHE.get(land) == "en" else "en"


def erstellen(nachschauer: nachschauen.Nachschauer, *, ort: str, jetzt: datetime, land: str = "at", sprache: str = "de") -> tuple[str, list[str]]:
    if sprache == "en":
        return _erstellen_en(nachschauer, ort=ort, jetzt=jetzt, land=land)
    land = feed_land(land, "de")
    fehler: list[str] = []
    kopf = f"Guten Morgen. Heute ist {WOCHENTAGE[jetzt.weekday()]}, der {jetzt.day}. {MONATE[jetzt.month - 1]} {jetzt.year}."
    teile = [kopf]
    if ort:
        try:
            w = nachschauer.wetter(nachschauen.Auftrag("wetter", f"Wie wird das Wetter heute in {ort}?", ort=ort, tag=0))
            zeilen = _wetter_zeilen(w.text)
            teile.append(f"Wetter in {ort}:\n\n" + "\n\n".join(zeilen) if zeilen else f"Wetter in {ort}: keine Vorhersage bekommen.")
        except Exception as exc:
            fehler.append(f"Wetter: {getattr(exc, 'detail', None) or type(exc).__name__}")
            teile.append(f"Wetter in {ort}: gerade nicht abrufbar.")
    else:
        teile.append("Wetter: Trag unter Einstellungen einen Ort ein und drück dort „Jetzt erstellen“, dann steht es hier.")
    try:
        s = nachschauer.schlagzeilen(nachschauen.Auftrag("schlagzeilen", "Schlagzeilen", land=land or "at"))
        zeilen = _schlagzeilen_zeilen(s.text)
        bloecke = [f"**{t}**" + (f"\n[Zum Beitrag auf {seite(l)}]({l})" if l else "") for t, l in zeilen]
        teile.append(f"Schlagzeilen aus {nachschauen.LAENDER.get(land or 'at', 'Österreich')}:\n\n" + "\n\n".join(bloecke) if zeilen else "Schlagzeilen: der Nachrichtenfeed war leer.")
    except Exception as exc:
        fehler.append(f"Schlagzeilen: {getattr(exc, 'detail', None) or type(exc).__name__}")
        teile.append("Schlagzeilen: gerade nicht abrufbar.")
    return "\n\n".join(teile), fehler


def _erstellen_en(nachschauer: nachschauen.Nachschauer, *, ort: str, jetzt: datetime, land: str) -> tuple[str, list[str]]:
    fehler: list[str] = []
    teile = [f"Good morning. Today is {WOCHENTAGE_EN[jetzt.weekday()]}, {jetzt.day} {MONATE_EN[jetzt.month - 1]} {jetzt.year}."]
    if ort:
        try:
            w = nachschauer.wetter(nachschauen.Auftrag("wetter", f"Wie wird das Wetter heute in {ort}?", ort=ort, tag=0))
            zeilen = [wetter_zeile_en(z) for z in _wetter_zeilen(w.text)]
            teile.append(f"Weather in {ort}:\n\n" + "\n\n".join(zeilen) if zeilen else f"Weather in {ort}: no forecast received.")
        except Exception as exc:
            fehler.append(f"Wetter: {getattr(exc, 'detail', None) or type(exc).__name__}")
            teile.append(f"Weather in {ort}: not available right now.")
    else:
        teile.append("Weather: enter a place under Settings and click “Create now” there, and it will show up here.")
    fl = feed_land(land, "en")
    try:
        s = nachschauer.schlagzeilen(nachschauen.Auftrag("schlagzeilen", "Schlagzeilen", land=fl))
        zeilen = _schlagzeilen_zeilen(s.text)
        bloecke = [f"**{t}**" + (f"\n[Read more on {seite(l)}]({l})" if l else "") for t, l in zeilen]
        kopf = f"Headlines from {LAENDER_EN[fl]}:" if fl in LAENDER_EN else "International headlines:"
        teile.append(kopf + "\n\n" + "\n\n".join(bloecke) if zeilen else "Headlines: the news feed was empty.")
    except Exception as exc:
        fehler.append(f"Schlagzeilen: {getattr(exc, 'detail', None) or type(exc).__name__}")
        teile.append("Headlines: not available right now.")
    return "\n\n".join(teile), fehler


def links(text: str) -> list[dict]:
    out = []
    zeilen = text.splitlines()
    for i, z in enumerate(zeilen):
        m = _LINK.match(z.strip())
        if m and i > 0:
            titel = zeilen[i - 1].strip().strip("*").strip()
            out.append({"nummer": len(out) + 1, "titel": titel, "adresse": m.group(2)})
    return out


def zum_vorlesen(text: str) -> str:
    zeilen = [z for z in text.splitlines() if not _LINK.match(z.strip())]
    return "\n".join(zeilen).replace("**", "")
