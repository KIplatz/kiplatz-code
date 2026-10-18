# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

ANTWORT = ("Worauf beziehst du dich? Schreib mir bitte kurz, worum es geht, oder füge den Text ein, den du meinst. "
           "Dann kann ich dir richtig helfen.")
ANTWORT_EN = ("What do you mean exactly? Please tell me briefly what it is about, or paste the text you are referring to. "
              "Then I can really help.")

_HOEFLICH = r"(?:(?:kannst|könntest|koenntest|würdest|wuerdest) du (?:mir )?(?:bitte )?)?"
_TUN = re.compile(r"^" + _HOEFLICH + r"(?:mach\w*|fass\w*|schick\w*|send\w*|korrigier\w*|prüf\w*|pruef\w*|übersetz\w*|uebersetz\w*|kürz\w*|kuerz\w*|"
                  r"verbesser\w*|lies|les\w*|erklär\w*|erklaer\w*|bewert\w*|überarbeit\w*|ueberarbeit\w*|schreib\w*|rechn\w*)"
                  r"(?: (?:mir|bitte|nochmal|noch einmal))* (?:es|das|dies|ihn|den|die|ihm)\b", re.I)
_VERWEIS = re.compile(r"\b(dazu|davon|daraus|dort|dorthin|damit|darüber|darueber|daran|dafür|dafuer|dabei|ihm|ihn)\b", re.I)
_TUN_HINTEN = re.compile(r"^(?:kannst|könntest|koenntest|würdest|wuerdest) du (?:mir )?(?:bitte )?(?:das|es|die|den|ihn|dies)\b.*\b(?:korrigier\w*|formulier\w*|kürz\w*|kuerz\w*|"
                         r"übersetz\w*|uebersetz\w*|prüf\w*|pruef\w*|mach\w*|rechn\w*|verbesser\w*|zusammenfass\w*|erklär\w*|erklaer\w*)$", re.I)
_ENDE = re.compile(r"(?:\b(?:das|den|ihn|dies)(?: (?:nochmal|noch einmal|denn|eigentlich|überhaupt|ueberhaupt))?$|^wie heißt der(?: nochmal)?$|^wie heisst der(?: nochmal)?$|"
                   r"^wie viel kostet (?:es|das)$|^was kostet (?:es|das)$|^welche[rs]? (?:ist|sind|passt) (?:besser|günstiger|guenstiger|billiger|schöner|schoener)$|"
                   r"^wann (?:fährt|faehrt|kommt|geht) der nächste$|^wann (?:fährt|faehrt|kommt|geht) der naechste$)", re.I)
_IST = re.compile(r"^(?:ist|war|wird|sind|waren) (?:das|der|die|dies|denn das)\b", re.I)
_ALLGEMEIN = re.compile(r"^(?:was|wann|wie|wo|wer) (?:ist|war|sind|waren) (?:der|die|das) (?:termin|ergebnis|unterschied|preis|problem|fehler|grund|"
                        r"frist|stand|plan|text|link|code|name)$", re.I)
_OFFEN = re.compile(r"^(?:was hältst du davon|was haeltst du davon|was meinst du dazu|und jetzt|und dann|wie geht es weiter|"
                    r"was soll ich als nächstes tun|was soll ich als naechstes tun|ist das so in ordnung|passt das so|"
                    r"wo bekomme ich (?:das|es|den|die|ihn)|wann muss ich (?:das|es|den|die|ihn) abgeben)$", re.I)
_ALLGEMEINE_NOMEN = {"Gesetz", "Ergebnis", "Termin", "Unterschied", "Preis", "Problem", "Fehler", "Grund", "Frist", "Stand", "Plan", "Text", "Link",
                     "Code", "Name", "Ordnung", "Uhr", "Brief", "Datei", "Mail", "E-Mail", "Tabelle", "Hälfte", "Zahlen", "Liste", "Farbe",
                     "Zusammenfassung", "Absatz", "Satz", "Sätze"}


_ALLGEMEIN_KLEIN = {x.lower() for x in _ALLGEMEINE_NOMEN}
_FUELL = {"zusammen", "kürzer", "kuerzer", "länger", "laenger", "schöner", "schoener", "einfacher", "besser", "genauer", "freundlicher", "höflicher",
          "hoeflicher", "formeller", "lockerer", "klarer", "verständlicher", "verstaendlicher", "neu", "um", "durch", "fertig", "schnell", "kurz",
          "nochmal", "noch", "einmal", "mal", "bitte", "so", "auch", "jetzt", "gleich", "ihm", "ihr", "ihnen", "mir", "uns", "dir", "für", "fuer",
          "an", "auf", "aus", "ins", "in", "englisch", "englische", "englischen", "deutsch", "deutsche", "deutschen", "wieder", "richtig", "sauber",
          "ordentlich", "weg", "vor", "ab", "eigentlich", "wirklich", "denn", "überhaupt", "ueberhaupt", "ok", "okay", "gut", "sehr", "ganz", "etwas",
          "als", "wie", "nur", "oder", "und", "dann", "das", "die", "der", "den", "dem", "es", "ein", "eine", "einen", "andere", "anderen", "anderes",
          "anders", "gleiche", "gleichen", "selbe", "selben"}
_BINDEWORT = re.compile(r"\b(?:damit|dafür|dafuer) (?=(?:er|sie|es|ich|du|wir|ihr|man|der|die|das)\b)", re.I)


def _woerter(f: str) -> list[str]:
    return re.findall(r"[\wÄÖÜäöüß-]+", f)


def _ding_dahinter(k: str) -> bool:
    for muster, mindest in ((_TUN, 1), (_IST, 2)):
        m = muster.match(k)
        if m:
            rest = [x for x in _woerter(k[m.end():]) if x not in _FUELL and x not in _ALLGEMEIN_KLEIN and not x.isdigit()]
            return len(rest) >= mindest
    return False


def fehlt(frage: str) -> bool:
    f = " ".join(str(frage or "").split()).strip().rstrip("?!. ")
    if not f or len(f) > 80:
        return False
    w = _woerter(f)
    if len(w) > 9:
        return False
    nomen = [x for x in w[1:] if x[:1].isupper() and x not in _ALLGEMEINE_NOMEN]
    if nomen:
        return False
    k = f.lower()
    if _ding_dahinter(k):
        return False
    return bool(_OFFEN.match(k) or _ALLGEMEIN.match(k) or (_TUN.match(k) and len(w) <= 7) or (_IST.match(k) and len(w) <= 7)
                or (_TUN_HINTEN.match(k) and len(w) <= 9) or (_ENDE.search(k) and len(w) <= 6)
                or (_VERWEIS.search(_BINDEWORT.sub("", k)) and len(w) <= 8))


def rueckfrage(nachrichten: list[dict]) -> str | None:
    echte = [n for n in (nachrichten or []) if isinstance(n, dict) and n.get("role") in ("user", "assistant") and str(n.get("content") or "").strip()]
    if len(echte) != 1 or echte[0].get("role") != "user":
        return None
    return ANTWORT if fehlt(str(echte[0].get("content") or "")) else None


__all__ = ["ANTWORT", "ANTWORT_EN", "fehlt", "rueckfrage"]
