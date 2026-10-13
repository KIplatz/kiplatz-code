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
          "deutschlandfunk.de": "Deutschlandfunk.de", "dw.com": "DW.com", "srf.ch": "SRF.ch"}
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


def erstellen(nachschauer: nachschauen.Nachschauer, *, ort: str, jetzt: datetime, land: str = "at") -> tuple[str, list[str]]:
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
