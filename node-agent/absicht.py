# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

import rechnen
import schriftstueck

_FUELL = set("""bitte bitteschön mal doch noch nochmal jetzt gleich eh halt einfach etwas bisschen bissl ein wenig das es dies diese dieses den
die der dem davon daraus darüber dazu deine deinen deiner dein vorige vorigen letzte letzten antwort text mir uns mich bitte du kannst
kannst könntest koenntest würdest wuerdest machst schreib schreibe sag sage gib gibs es's please can could would you it this that the your
answer text me again for a an and und oder so ok okay ist war sind is was are leider aber total völlig voellig komplett voll glaub glaube
ich denke nein ne nee sorry hmm also wirklich eigentlich that's thats totally completely no nope i think really actually
dir ein eine einen einem einer eines""".split())
_WORT = re.compile(r"[A-Za-zÄÖÜäöüß']+")
_FRAGEWORT_ANFANG = re.compile(r"^\s*(?:wie|was|wer|wo|wann|warum|wieso|weshalb|welche\w*|how|what|who|where|when|why|which)\b", re.I)

_UMFORMEN = [
    (re.compile(r"\b(?:kürzer|kuerzer|knapper|kurzfassung|kürze|kuerze|in\s+kurz|shorter|briefer|shorten)\b", re.I), "kürzer"),
    (re.compile(r"\b(?:ausführlicher|ausfuehrlicher|länger|laenger|genauer|detaillierter|mehr\s+details?|longer|more\s+details?|in\s+more\s+detail|elaborate)\b", re.I), "ausführlicher"),
    (re.compile(r"\b(?:einfacher|verständlicher|verstaendlicher|leichter|in\s+einfacher\s+sprache|wie\s+für\s+ein\s+kind|für\s+kinder|kindgerecht|"
                r"simpler|simplify|more\s+simply|in\s+simple\s+(?:terms|words)|like\s+i'?m\s+(?:five|5|a\s+child))\b", re.I), "einfacher"),
    (re.compile(r"\b(?:als\s+liste|in\s+stichpunkten|stichpunkte|stichworte|aufzählung|aufzaehlung|as\s+a\s+list|bullet\s+points?|as\s+bullets?)\b", re.I), "als Liste"),
    (re.compile(r"\b(?:als\s+tabelle|tabelle\s+daraus|in\s+eine\s+tabelle|in\s+einer\s+tabelle|as\s+a\s+table|in\s+a\s+table|table)\b", re.I), "als Tabelle"),
    (re.compile(r"\b(?:fass\w*\s+(?:\w+\s+)?zusammen|zusammenfassung|zusammenfassen|summari[sz]e|summary|tl;?dr)\b", re.I), "zusammengefasst"),
    (re.compile(r"\b(?:anders\s+formulier\w*|formulier\w*\s+(?:\w+\s+)?(?:anders|neu|um)|umformulier\w*|mit\s+anderen\s+worten|in\s+eigenen\s+worten|"
                r"nochmal\s+anders|noch\s+einmal\s+anders|rephrase|reword|in\s+other\s+words|say\s+it\s+differently)\b", re.I), "anders formuliert"),
    (re.compile(r"\b(?:freundlicher|höflicher|hoeflicher|förmlicher|foermlicher|lockerer|persönlicher|persoenlicher|friendlier|more\s+formal|more\s+casual)\b", re.I), "im gewünschten Ton"),
]
_BEFEHL_VERB = set("erklär erklaer erkläre erklaere erklären erklaeren mach mache machs machen schreib schreibe schreiben formulier formuliere "
                   "formulieren fass fasse zusammenfassen sag sage sagen gib bring bringe explain make write put give say turn".split())

_WEITER = re.compile(r"^\s*(?:bitte\s+)?(?:(?:mach|schreib|erzähl|erzaehl|red)\w*\s+)?weiter\b|\b(?:fortsetzen|setz\w*\s+(?:\w+\s+)?fort|und\s+weiter|"
                     r"go\s+on|continue|keep\s+going|carry\s+on)\b", re.I)
_SPRACHE_EN = re.compile(r"\b(?:auf\s+englisch|in\s+englisch|ins\s+englische|englische\s+fassung|in\s+english|into\s+english|to\s+english|english\s+please)\b", re.I)
_SPRACHE_DE = re.compile(r"\b(?:auf\s+deutsch|in\s+deutsch|ins\s+deutsche|deutsche\s+fassung|in\s+german|into\s+german|to\s+german|german\s+please)\b", re.I)
_UEBERSETZ = re.compile(r"\b(?:übersetz\w*|uebersetz\w*|translate\w*|sag\s+(?:das|es)|schreib\w*\s+(?:das|es)|answer|antworte?)\b", re.I)
SUCHAUFTRAG = re.compile(
    r"(?<!ich\s)\b(?:such|suche|schau|sieh|guck|prüf|prüfe|pruef|pruefe|check|checke|recherchier|recherchiere|google|googel|googele)"
    r"(?:\s+(?:das|es|dazu|bitte|mal|doch|jetzt|nochmal|noch\s+mal|gleich|selbst))*"
    r"\s+(?:live|im\s+(?:internet|netz|web)|online)(?:\s+(?:nach|danach))?\b"
    r"|\blive\s+(?:suchen|nachschauen|nachsehen|nachprüfen|nachpruefen|prüfen|pruefen|recherchieren|checken|googeln)\b"
    r"|\bgoogle?\s+(?:das|es|mal|bitte)\b"
    r"|\b(?:look\s+(?:it|that|this)\s+up|search\s+(?:online|the\s+(?:web|internet)|live)|check\s+online|google\s+(?:it|that|this))\b", re.I)
KORREKTUR = re.compile(r"\b(?:stimmt\s+(?:so\s+)?nicht|falsch|nicht\s+richtig|nicht\s+korrekt|quatsch|unsinn|blödsinn|bloedsinn|"
                       r"(?:das|des|es)\s+(?:ist|war)\s+(?:aber\s+|doch\s+)?nicht\s+(?:das|der|die|den|dem|mein\w*|gemeint|richtig|korrekt|wahr)|"
                       r"wrong|incorrect|not\s+(?:right|correct|true)|(?:that|this|it)\s+(?:is|was|'s)\s+not\s+(?:the|my|what|right|correct|true))\b", re.I)
_FRAGE_FORM = re.compile(r"\?\s*$|^\s*(?:ist|sind|war|kann|darf|soll|muss|gibt|hat|wieso|warum|weshalb|wie|was|wer|wo|wann|welche\w*|"
                         r"is|are|was|can|may|should|does|do|why|how|what|who|where|when|which)\b", re.I)
_PRUEFEN = re.compile(r"\b(?:bist\s+du\s+(?:dir\s+)?sicher|stimmt\s+das|ist\s+das\s+(?:richtig|korrekt|wahr|sicher|aktuell)|woher\s+(?:hast|weißt|weisst|weist)\s+du\s+das|"
                      r"hast\s+du\s+(?:dafür\s+)?(?:eine\s+)?quellen?|quellen?|beleg\w*|are\s+you\s+sure|is\s+(?:that|this|it)\s+(?:true|right|correct|accurate)|"
                      r"sources?|where\s+did\s+you\s+get\s+(?:that|this))\b", re.I)
_FALSCH = KORREKTUR
_MISSVERSTANDEN = re.compile(r"\b(?:(?:das|des)\s+mein(?:e|te)\s+ich\s+nicht|so\s+mein(?:e|te)\s+ich\s+das\s+nicht|du\s+hast\s+mich\s+(?:falsch|miss)\s*verstanden|"
                             r"(?:i\s+)?did(?:n't|\s+not)\s+mean\s+(?:that|this)|that'?s\s+not\s+what\s+i\s+meant|you\s+misunderstood)\b", re.I)
_BILD_VERB = r"(?:erstelle|erstell|mach|mache|zeichne|male|mal|generiere|generier|entwirf|gestalte|draw|create|make|generate|design|paint)"
_BILD_VERB_INF = r"(?:erstellen|machen|zeichnen|malen|generieren|entwerfen|gestalten|draw|create|make|generate|design|paint)"
_BILD_DING = r"(?:bild|bilder|bildchen|logo|logos|foto|fotos|zeichnung|grafik|icon|illustration|gemälde|gemaelde|comic|image|images|picture|pictures|photo|drawing|illustration|painting|logo)"
_BILD_FUELL = r"(?:mir|uns|dir|bitte|mal|schnell|ein|eine|einen|ein\s+paar|zwei|drei|neues|neue|neuen|schönes|schöne|schönen|kleines|kleine|kleinen|"
_BILD_FUELL += r"me|us|a|an|the|some|new|nice|quick|small)"
_BITTE_ANFANG = r"^\s*(?:bitte\s+|(?:kannst|könntest|koenntest|würdest|wuerdest)\s+du\s+|(?:can|could|would)\s+you\s+|please\s+)?"
_BILD = re.compile(rf"{_BITTE_ANFANG}{_BILD_VERB}\s+(?:{_BILD_FUELL}\s+){{0,3}}{_BILD_DING}\b"
                   rf"|{_BITTE_ANFANG}(?:{_BILD_FUELL}\s+){{0,3}}{_BILD_DING}\s+{_BILD_VERB_INF}\b", re.I)
_ZEICHNE = re.compile(r"^\s*(?:bitte\s+)?(?:zeichne|male|mal\s+mir|draw|paint)\b(?!\s+up\b)(?!.*\?\s*$)", re.I)
_DANK = re.compile(r"^\s*(?:(?:ok(?:ay)?|super|perfekt|passt|top|alles\s+klar|sehr\s+gut|great|perfect|cool|nice)[,!.\s]*)?"
                   r"(?:danke(?:schön|schoen)?|vielen\s+dank|merci|thx|thanks|thank\s+you|dankeschön)"
                   r"(?:[,!.\s]+(?:dir|sehr|vielmals|schön|schoen|so\s+much|a\s+lot|für\s+(?:die|deine)\s+(?:hilfe|antwort)|for\s+(?:the|your)\s+(?:help|answer)|"
                   r"passt|super|perfekt|top|great))*[\s!.]*$", re.I)

BILD_SATZ = ("Bilder und Logos kann KIplatz noch nicht zeichnen. Ich kann dir aber beschreiben, wie es aussehen könnte, mit Farben, Schrift und Form, "
             "oder einen Auftrag für einen Grafiker schreiben. Sag einfach, was dir davon hilft.")
DANK_SATZ = "Gern geschehen."
MISSVERSTANDEN_SATZ = "Dann hab ich dich falsch verstanden. Was genau meinst du?"
SAETZE_EN = {BILD_SATZ: "KIplatz can't draw pictures or logos yet. But I can describe how it could look, with colours, font and shape, "
                        "or write a brief for a designer. Just tell me what would help.",
             DANK_SATZ: "You're welcome.",
             MISSVERSTANDEN_SATZ: "Then I misunderstood you. What exactly do you mean?"}


@dataclass(frozen=True)
class Absicht:
    art: str = ""
    wie: str = ""
    sprache: str = ""
    antwort: str = ""
    korrektur: bool = False
    sache: bool = False
    en: str = ""

    @property
    def antwort_en(self) -> str:
        return self.en or SAETZE_EN.get(self.antwort, "")

    @property
    def gemacht(self) -> str:
        return {"missverstanden": "nachgefragt", "rechnen": "gerechnet"}.get(self.art, "geantwortet")

    @property
    def frisch(self) -> bool:
        return self.art in ("suchen", "pruefen", "berichtigen")


def rest(text: str, a: Absicht) -> str:
    t = " ".join(str(text or "").split())
    for m in (SUCHAUFTRAG, KORREKTUR, _PRUEFEN) if a.frisch else ():
        t = m.sub(" ", t)
    return " ".join(t.split()).strip(" ,.;:!?-–")


def _woerter(text: str) -> list[str]:
    return [w.lower() for w in _WORT.findall(text or "")]


def _rest_ohne(text: str, *muster: re.Pattern) -> list[str]:
    t = text or ""
    for m in muster:
        t = m.sub(" ", t)
    return [w for w in _woerter(t) if w not in _FUELL and w not in _BEFEHL_VERB and len(w) > 1]


def erkennen(text: str, *, hat_vorige_antwort: bool = True) -> Absicht:
    t = " ".join(str(text or "").split())
    if not t:
        return Absicht()
    if _DANK.match(t):
        return Absicht("dank", antwort=DANK_SATZ)
    if (_BILD.search(t) or _ZEICHNE.search(t)) and not _FRAGEWORT_ANFANG.match(t):
        return Absicht("bild", antwort=BILD_SATZ)
    rechnung = rechnen.loesen(t)
    if rechnung is not None:
        return Absicht("rechnen", antwort=rechnung.de, en=rechnung.en)
    sache =len(_rest_ohne(t, SUCHAUFTRAG, KORREKTUR, _PRUEFEN)) >= 2
    if SUCHAUFTRAG.search(t):
        return Absicht("suchen", korrektur=bool(KORREKTUR.search(t)) and hat_vorige_antwort, sache=sache)
    if not hat_vorige_antwort:
        return Absicht()
    kurz = len(_woerter(t)) <= 12
    if kurz and _MISSVERSTANDEN.search(t) and not _rest_ohne(t, _MISSVERSTANDEN):
        return Absicht("missverstanden", antwort=MISSVERSTANDEN_SATZ)
    if kurz and (_SPRACHE_EN.search(t) or _SPRACHE_DE.search(t)) and not _rest_ohne(t, _SPRACHE_EN, _SPRACHE_DE, _UEBERSETZ):
        return Absicht("sprache", sprache="en" if _SPRACHE_EN.search(t) else "de")
    eigenes = _rest_ohne(t, KORREKTUR)
    if kurz and KORREKTUR.search(t) and len(eigenes) <= 4 and (not _FRAGE_FORM.search(t) or not eigenes):
        return Absicht("berichtigen", korrektur=True, sache=sache)
    if kurz and _PRUEFEN.search(t) and not _rest_ohne(t, _PRUEFEN):
        return Absicht("pruefen")
    if kurz and _WEITER.search(t) and not _rest_ohne(t, _WEITER):
        return Absicht("weiter")
    if kurz:
        for muster, wie in _UMFORMEN:
            if muster.search(t) and not _rest_ohne(t, *(m for m, _ in _UMFORMEN)):
                return Absicht("umformen", wie=wie)
    return Absicht()


def letzte(nachrichten: list[dict]) -> Absicht:
    if not nachrichten or nachrichten[-1].get("role") != "user":
        return Absicht()
    inhalt = nachrichten[-1].get("content", "")
    if isinstance(inhalt, list):
        inhalt = " ".join(str(x.get("text", "")) for x in inhalt if isinstance(x, dict))
    vorige = any(n.get("role") == "assistant" and str(n.get("content") or "").strip() for n in nachrichten[:-1])
    letzte_antwort = next((str(n.get("content") or "") for n in reversed(nachrichten[:-1]) if n.get("role") == "assistant"), "")
    if letzte_antwort.lstrip().startswith(schriftstueck.VORSPANN):
        vorige = False
    return erkennen(str(inhalt), hat_vorige_antwort=vorige)


_UMFORM_ZUSATZ = ("Die Person möchte deine vorige Antwort {wie}. Nimm dafür nur, was in deiner vorigen Antwort steht, und erfinde nichts dazu; "
                  "Zahlen, Namen und Daten bleiben genau so.")
_AUSFUEHRLICH_ZUSATZ = ("Die Person möchte deine vorige Antwort ausführlicher. Erkläre genauer, was dort steht; neue Zahlen, Namen oder Daten nur, "
                        "wenn sie in den Quellen oben stehen.")
_WEITER_ZUSATZ = "Die Person möchte, dass du deine vorige Antwort fortsetzt. Mach dort weiter, wo du aufgehört hast, ohne etwas zu wiederholen."
_SPRACHE_ZUSATZ = "Gib deine vorige Antwort inhaltlich gleich noch einmal wieder{auf}. Lass nichts weg und füge nichts hinzu."


def zusatz(a: Absicht) -> str:
    if a.art == "umformen":
        return _AUSFUEHRLICH_ZUSATZ if a.wie == "ausführlicher" else _UMFORM_ZUSATZ.format(wie=a.wie)
    if a.art == "weiter":
        return _WEITER_ZUSATZ
    if a.art == "sprache":
        return _SPRACHE_ZUSATZ.format(auf=" auf Deutsch" if a.sprache == "de" else "")
    return ""


def ohne_suche(a: Absicht) -> bool:
    return a.art in ("weiter", "sprache") or (a.art == "umformen" and a.wie != "ausführlicher")
