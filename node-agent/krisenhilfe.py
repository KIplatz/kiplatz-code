# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

_DE = re.compile(
    r"\b(?:"
    r"(?:will|möchte|mag|kann)\s+(?:einfach\s+|so\s+)?nicht\s+mehr\s+(?:leben|weiterleben|da\s+sein|weiter\s*machen)"
    r"|(?:keine\s+lust|keinen\s+sinn|keinen\s+grund)\s+mehr\s+(?:zu\s+|am\s+)?leben"
    r"|(?:will|möchte|werde|sollte|wie\s+kann\s+ich|wie)\s+(?:ich\s+)?mich\s+(?:selbst\s+)?(?:umbringen|töten|erhängen|aufhängen|vergiften|ritzen|verletzen)"
    r"|mich\s+(?:selbst\s+)?(?:umbringen|töten|umzubringen|zu\s+töten|ritzen|zu\s+ritzen)"
    r"|mir\s+(?:das\s+leben\s+nehmen|etwas\s+antun|was\s+antun|das\s+leben\s+zu\s+nehmen)"
    r"|(?:ich\s+bin|bin\s+ich)\s+(?:so\s+)?(?:lebensmüde|suizidal|selbstmordgefährdet)"
    r"|(?:ich\s+)?(?:denke|dachte)\s+(?:an|über)\s+(?:selbstmord|suizid|freitod)"
    r"|(?:will|möchte)\s+(?:ich\s+)?(?:sterben|tot\s+sein|selbstmord\s+begehen|suizid\s+begehen)"
    r"|tödliche\s+(?:dosis|menge)"
    r"|wie\s+viele\s+(?:tabletten|pillen)\s+(?:brauche|braucht|nehme|muss)"
    r"|(?:schmerzlos|schnellst|sicherst)\w*\s+(?:sterben|tod|umbringen|selbstmord|suizid)"
    r"|(?:am\s+)?(?:schmerzlos|schnellst|sicherst)\w*\s+(?:weg|art|methode)\s+(?:zu\s+sterben|sich\s+umzubringen|für\s+(?:selbstmord|suizid))"
    r")", re.I)

_EN = re.compile(
    r"\b(?:"
    r"(?:want|going|plan|planning|trying)\s+to\s+(?:kill|hurt|harm|cut)\s+myself"
    r"|kill(?:ing)?\s+myself|end(?:ing)?\s+my\s+(?:own\s+)?life|take\s+my\s+(?:own\s+)?life|suicid(?:e|al)\s+(?:thoughts|feelings)"
    r"|(?:i\s+am|i'm|im|i\s+feel)\s+(?:so\s+)?suicidal"
    r"|(?:want|wanna)\s+to\s+die|(?:don't|do\s+not|dont)\s+want\s+to\s+(?:live|be\s+alive|be\s+here)\s*(?:anymore|any\s+more)?"
    r"|(?:hurt|harm|cut)(?:ing)?\s+myself|self[-\s]?harm"
    r"|lethal\s+(?:dose|amount)|how\s+many\s+(?:pills|tablets)\s+(?:to|would|do|does|will)\s+(?:die|kill)"
    r"|(?:painless|quickest|fastest|easiest|surest)\w*\s+(?:way|method)\s+to\s+(?:die|kill\s+(?:my|your)self|commit\s+suicide)"
    r")", re.I)

TEXT_DE = (
    "Es tut mir leid, dass es dir gerade so schwer geht. Du musst damit nicht allein bleiben. Bitte sprich jetzt mit einem Menschen, "
    "der dir zuhört, kostenlos und rund um die Uhr:\n"
    "– Österreich: Telefonseelsorge 142, für junge Menschen Rat auf Draht 147\n"
    "– Deutschland: Telefonseelsorge 0800 111 0 111 oder 0800 111 0 222\n"
    "– Schweiz: Die Dargebotene Hand 143\n"
    "– Woanders: der Notruf in deinem Land, in Europa 112\n"
    "Bist du in akuter Gefahr, ruf sofort den Notruf: 112, in Österreich auch die Rettung 144.\n"
    "Wenn du magst, erzähl mir, was los ist."
)

TEXT_EN = (
    "I'm sorry you're going through this. You don't have to face it alone. Please talk to someone who will listen, right now, "
    "free and at any hour:\n"
    "– If you are in danger, call your local emergency number: 112 in Europe, 911 in the US and Canada\n"
    "– US and Canada: call or text 988\n"
    "– UK and Ireland: Samaritans 116 123\n"
    "– Austria 142, Germany 0800 111 0 111, Switzerland 143\n"
    "– Anywhere else: the emergency number or a crisis line in your country\n"
    "If you want, tell me what's going on."
)

GEMACHT = "Krisenhilfe"
WOHER = "Feste Krisenhilfe von KIplatz, ohne Modell und ohne Suche."


def sprache(text: str) -> str | None:
    t = " ".join(str(text or "").split())
    if not t:
        return None
    if _DE.search(t):
        return "de"
    if _EN.search(t):
        return "en"
    return None


def antwort(text: str) -> str | None:
    s = sprache(text)
    return None if s is None else (TEXT_EN if s == "en" else TEXT_DE)


def letzte_frage(nachrichten) -> str:
    if isinstance(nachrichten, list) and nachrichten and isinstance(nachrichten[-1], dict) and nachrichten[-1].get("role", "user") == "user":
        return str(nachrichten[-1].get("content", ""))
    return ""


def lieferschein() -> dict:
    return {"modell": "ohne Modell", "dauer_s": 0.0, "wortstuecke": 0, "gelesen": 0, "quellen": WOHER, "quellen_liste": [],
            "gemacht": GEMACHT, "erfunden": "nichts", "krisenhilfe": True}


__all__ = ["sprache", "antwort", "letzte_frage", "lieferschein", "TEXT_DE", "TEXT_EN", "GEMACHT", "WOHER"]
