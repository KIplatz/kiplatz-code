# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import random
import re
from datetime import date

import belege
import kalender_dach

ZUFALL_JE_NACHT = 10

STAEDTE = {
    "de": ["Berlin", "Hamburg", "München", "Köln", "Frankfurt", "Stuttgart", "Düsseldorf", "Leipzig", "Dresden", "Hannover", "Nürnberg", "Bremen"],
    "at": ["Wien", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt", "St. Pölten", "Wels"],
    "ch": ["Zürich", "Bern", "Basel", "Genf", "Luzern", "St. Gallen", "Winterthur"],
}
KETTEN = {"de": ["Rewe", "Edeka", "Aldi", "Lidl", "dm"], "at": ["Billa", "Spar", "Hofer", "Lidl", "dm"], "ch": ["Migros", "Coop", "Denner", "Lidl"]}
VEREINE = {"de": ["Bayern München", "Borussia Dortmund", "Bayer Leverkusen", "VfB Stuttgart", "Eintracht Frankfurt"],
           "at": ["Rapid Wien", "Sturm Graz", "Red Bull Salzburg", "Austria Wien"], "ch": ["FC Basel", "Young Boys", "FC Zürich"]}
GEBIETE = {"de": ["Bayern", "Berlin", "Nordrhein-Westfalen", "Sachsen", "Hessen", "Baden-Württemberg", "Niedersachsen", "Hamburg"]}

MIT_ORT = (
    "Wie wird das Wetter morgen in {stadt}?",
    "Wer ist Bürgermeister von {stadt}?",
    "Wie viele Einwohner hat {stadt}?",
    "Wie lange hat der {kette} in {stadt} am Samstag offen?",
    "Was kostet ein Monatsticket für Bus und Bahn in {stadt}?",
    "Welche Veranstaltungen gibt es am Wochenende in {stadt}?",
    "Was kostet ein Kita-Platz in {stadt}?",
    "Wo kann man in {stadt} am Sonntag einkaufen?",
    "Wann ist der nächste Flohmarkt in {stadt}?",
    "Wie hoch ist die Hundesteuer in {stadt}?",
)
JE_LAND = {
    "de": ("Was kostet das Deutschlandticket?", "Wie hoch ist der Mindestlohn in Deutschland?", "Was kostet eine BahnCard 50?",
           "Wer führt die deutsche Bundesliga an?", "Wie hoch ist das Kindergeld in Deutschland?", "Was kostet ein Sparpreis der Deutschen Bahn von München nach Berlin?",
           "Wie hoch ist der Rundfunkbeitrag in Deutschland?", "Wann ist die nächste Bundestagswahl?"),
    "at": ("Was kostet die Autobahnvignette in Österreich?", "Wie hoch ist die Familienbeihilfe in Österreich?", "Wer führt die österreichische Bundesliga an?",
           "Was kostet das Klimaticket Österreich?", "Wie hoch ist die ORF-Haushaltsabgabe?", "Was kostet ein ÖBB-Sparschiene-Ticket von Wien nach Salzburg?"),
    "ch": ("Was kostet die Autobahnvignette in der Schweiz?", "Was kostet ein Halbtax-Abo?", "Wie hoch ist der Leitzins der Schweizerischen Nationalbank?",
           "Wer führt die Schweizer Super League an?", "Was kostet ein Generalabonnement der SBB?", "Wie hoch ist die Serafe-Gebühr in der Schweiz?"),
}
VEREIN_FRAGEN = ("Wann spielt {verein} als Nächstes?", "Wie hat {verein} zuletzt gespielt?")


def ziehen(tag: date, n: int = ZUFALL_JE_NACHT) -> list[dict]:
    rnd = random.Random(int(tag.strftime("%Y%m%d")))
    out: list[dict] = []
    gesehen: set[str] = set()
    versuche = 0
    while len(out) < n and versuche < n * 20:
        versuche += 1
        land = rnd.choice(["de", "de", "at", "ch"])
        art = rnd.random()
        schluessel = ""
        if art < 0.45:
            stadt = rnd.choice(STAEDTE[land])
            frage = rnd.choice(MIT_ORT).format(stadt=stadt, kette=rnd.choice(KETTEN[land]))
        elif art < 0.7:
            frage = rnd.choice(JE_LAND[land])
        elif art < 0.85:
            frage = rnd.choice(VEREIN_FRAGEN).format(verein=rnd.choice(VEREINE[land]))
        else:
            if land == "de":
                gebiet = rnd.choice(GEBIETE["de"])
                frage, schluessel = f"Wann ist der nächste Feiertag in {gebiet}?", "feiertag"
            elif land == "at":
                frage, schluessel = "Wann ist der nächste Feiertag in Österreich?", "feiertag"
            else:
                frage = rnd.choice(JE_LAND["ch"])
        if frage in gesehen:
            continue
        gesehen.add(frage)
        out.append({"kennung": f"z{tag.strftime('%Y%m%d')}{len(out):02d}", "frage": frage, "schluessel": schluessel})
    return out


def aus_kennung(kennung: str) -> dict | None:
    m = re.fullmatch(r"z(\d{8})(\d{2})", kennung or "")
    if not m:
        return None
    try:
        tag = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:]))
    except ValueError:
        return None
    return next((f for f in ziehen(tag) if f["kennung"] == kennung), None)


_WEISS_NICHT = re.compile(r"weiß ich (?:\w+ )*nicht|kenne ich (?:\w+ )*nicht|nichts Verlässliches gefunden|keine (?:Informationen|Angaben)", re.I)


def bewerten(f: dict, antwort: str, *, heute: date, pruefung: dict | None = None, belege_notizen=None, quellen: str = "") -> dict:
    a = antwort or ""
    if f.get("schluessel") == "feiertag":
        kal = kalender_dach.quelle(f["frage"], heute)
        zeile = next((z for z in (kal[1].splitlines() if kal else []) if z.startswith("– ")), "")
        ds = belege.daten(zeile)
        if ds:
            t, m, _ = next(iter(ds))
            richtig = any((d[0], d[1]) == (t, m) for d in belege.daten(a))
            return {"urteil": "richtig" if richtig else "falsch", "grund": "" if richtig else "anderes Datum", "erwartet": zeile[2:]}
    if not a.strip() or a.startswith("(keine Antwort"):
        return {"urteil": "offen", "grund": "keine Antwort", "erwartet": ""}
    if _WEISS_NICHT.search(a):
        return {"urteil": "offen", "grund": "sagt ehrlich, dass es das nicht weiß", "erwartet": ""}
    p = pruefung or {}
    if re.search(r"\[[^\]\d]{1,40}\]", a) or int(p.get("rot", 0) or 0) > 0 or belege_notizen:
        grund = "Lücke in eckigen Klammern" if re.search(r"\[[^\]\d]{1,40}\]", a) else ("Satz ohne Beleg" if int(p.get("rot", 0) or 0) > 0 else "Datum oder Betrag gestrichen")
        return {"urteil": "fraglich", "grund": grund, "erwartet": ""}
    if "aus dem Wissen des Modells" in (quellen or ""):
        return {"urteil": "fraglich", "grund": "ohne gefundene Quelle, nur aus dem Wissen des Modells", "erwartet": ""}
    return {"urteil": "belegt", "grund": "", "erwartet": ""}


__all__ = ["ziehen", "aus_kennung", "bewerten", "ZUFALL_JE_NACHT"]
