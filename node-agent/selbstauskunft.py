# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

_KIPLATZ = r"(?:kiplatz|ki-platz|ki platz|dieses programm|diese ki|diese community|das hier|dieser chatbot|dieses ding)"

_ARTEN: list[tuple[str, re.Pattern[str]]] = [
    ("merken", re.compile(r"\b(merk(e)? dir (das|dies|bitte|folgendes|mal)|kannst du (dir )?(das|dies|es) (merken|speichern|abspeichern)|"
                          r"(speicher|speichere) (das|dies|es)( bitte)?( ab)?$|kannst du das (bitte )?(ab)?speichern)", re.I)),
    ("seit", re.compile(r"\b(seit wann gibt es " + _KIPLATZ + r"|wann (wurde|ist) " + _KIPLATZ + r" (gegründet|entstanden|gestartet)|"
                        r"wie alt ist " + _KIPLATZ + r"|wann (gab es|kam) " + _KIPLATZ + r" (zum ersten mal|erstmals))", re.I)),
    ("kosten", re.compile(r"\b(was kostet " + _KIPLATZ + r"|ist " + _KIPLATZ + r" (wirklich )?(kostenlos|gratis|umsonst)|"
                          r"kostet " + _KIPLATZ + r" (etwas|was|geld)|muss ich für " + _KIPLATZ + r" (etwas )?zahlen)$", re.I)),
    ("credits", re.compile(r"\b(was sind (die )?credits( (bei|von|in) " + _KIPLATZ + r")?|wof[üu]r (gibt es|bekomme ich|sind)( die)? credits|"
                           r"was bringen (mir )?(die )?credits)$|\bcredits (bei|von|in) " + _KIPLATZ + r"\b", re.I)),
    ("platzordnung", re.compile(r"\b(was (ist|steht in) (die|der) platzordnung|wof[üu]r gibt es (bei " + _KIPLATZ + r" )?(eine|die) platzordnung|"
                                r"wof[üu]r gibt es bei " + _KIPLATZ + r" (eine|die) hausordnung|(platz|haus)ordnung (von|bei) " + _KIPLATZ +
                                r"|welche regeln gelten (bei|in|für) " + _KIPLATZ + r")\b", re.I)),
    ("koennen", re.compile(r"\b(was kannst du|was kann " + _KIPLATZ + r"|was kannst du alles|womit kannst du (mir )?helfen|"
                           r"was (machst|tust) du( für mich)?\??$|wobei hilfst du|deine (fähigkeiten|funktionen)|was bietet " + _KIPLATZ + r")", re.I)),
    ("funktion", re.compile(r"\b(wie funktionierst du|wie funktioniert (das|das hier|du)$|wie funktioniert " + _KIPLATZ +
                            r"|wie (arbeitest|arbeitet) (du|" + _KIPLATZ + r")|"
                            r"wie (geht|läuft) (das( hier)?$|" + _KIPLATZ + r")|woher (kommen|kommt) (deine |die )?antwort\w*|wo (läufst|rechnest) du|"
                            r"wer antwortet (mir|hier)|was passiert mit meiner frage)", re.I)),
    ("wer", re.compile(r"\b(wer bist du|was bist du|wer (ist|steckt hinter|hat) (dich|dir|" + _KIPLATZ + r")|stell dich (kurz )?vor|"
                       r"wie hei(ß|ss)t du|woher kommst du|bist du (chatgpt|eine ki|ein bot|ein mensch)|wer hat dich (gebaut|gemacht|programmiert|entwickelt))", re.I)),
    ("was", re.compile(r"\b(was ist " + _KIPLATZ + r"|was (genau )?ist das (hier|für ein programm|für eine ki)|erkl[äa]r(e)? (mir )?(bitte )?" + _KIPLATZ +
                       r"|was (macht|tut|will|soll) " + _KIPLATZ + r"|wof[üu]r (ist|gibt es|steht) " + _KIPLATZ + r"|was bedeutet " + _KIPLATZ +
                       r"|was ist der sinn von " + _KIPLATZ + r"|worum geht es (hier|bei " + _KIPLATZ + r"))", re.I)),
]

_GEMEINSAM = (
    "Du stellst eine Frage, so wie bei jedem Chatbot. Die Antwort kommt aber nicht aus einem Rechenzentrum, sondern von den "
    "Computern der Mitglieder: von deinem eigenen PC oder von einem anderen Gerät der Community, das gerade Zeit hat. Unter jeder "
    "Antwort stehen die Quellen, aus denen sie kommt. Der Server in Wien vermittelt die Fragen und antwortet nicht selbst. Allgemeine "
    "Wissensfragen und ihre Antworten bewahrt er verschlüsselt und ohne Absender auf, damit die nächste gleiche Frage sofort beantwortet "
    "ist; Fragen über dich selbst speichert er nie. Es gibt keine Werbung, keinen Datenhandel und keinen Konzern dahinter."
)

_MITMACHEN = (
    "Gebaut wird KIplatz von allen, die mitmachen, egal wo auf der Welt: Sie lassen ihren PC mithelfen, "
    "melden Fehler, schreiben Skills und tragen Wissen bei. Mitmachen kannst du auf kiplatz.at, ein Konto reicht für das Programm, "
    "fürs Mitreden und fürs Mitbauen."
)

STECKBRIEF = (
    "Steckbrief KIplatz: kostenlose KI aus Österreich, offen für alle auf der Welt, auf Deutsch und Englisch, gebaut von einer Community. Läuft am eigenen Gerät: ja, als Programm "
    "für Windows 11; vom Handy oder einem anderen Gerät fragt man über die App oder kiplatz.at, dann antwortet ein PC der Community. "
    "Die Antworten entstehen auf den Computern der Mitglieder, nicht in einem Rechenzentrum; der Server in Wien vermittelt nur. "
    "Kostenlos ohne Grenze, kein Bezahltarif, keine Werbung, Quellen unter jeder Antwort. KIplatz gibt es seit September 2026."
)

TEXTE: dict[str, str] = {
    "was": "KIplatz ist eine kostenlose KI aus Österreich, offen für alle auf der Welt, die eine Community gemeinsam baut. " + _GEMEINSAM + " " + _MITMACHEN,
    "wer": "Ich bin KIplatz, eine KI aus Österreich, offen für alle auf der Welt. Ich laufe auf deinem PC oder auf dem Gerät eines "
           "Mitglieds, nicht in einem Rechenzentrum. " + _GEMEINSAM + " " + _MITMACHEN,
    "koennen": "Ich beantworte Fragen, schreibe und fasse Texte zusammen, rechne, schaue Wetter und Schlagzeilen nach, suche in "
               "Dokumenten, die du freigibst, und befolge Skills, also Regeln, die du oder andere Mitglieder für eine Aufgabe "
               "geschrieben haben. Unter jeder Antwort stehen die Quellen. Wenn ich etwas nicht weiß, sage ich es, statt zu raten. "
               "Und je mehr Mitglieder mitmachen, desto mehr weiß ich: Jedes Gerät bereitet Wissen für alle auf.",
    "funktion": "Deine Frage geht zuerst an die KI auf deinem eigenen PC. Hat dein Gerät keine passende Grafikkarte, schickt das "
                "Programm die Frage über den Server in Wien an ein Gerät der Community, das gerade Zeit hat; der Server vermittelt "
                "nur. Das antwortende Gerät sucht im gemeinsamen Wissen der Community und in dem, was du freigegeben "
                "hast, schreibt die Antwort und nennt die Quellen. Ein kleiner Punkt hinter einem Satz zeigt, wo die KI selbst "
                "weiterdenkt. Wer ein Gerät mithelfen lässt, bekommt dafür Credits: Anerkennung und Vorrang, kein Geld.",
    "kosten": "KIplatz ist kostenlos: das Programm, die Antworten und die Community. Es gibt keine Werbung, keinen Datenhandel, kein "
              "Abo und keine Bezahlstufe. Das geht, weil die Antworten auf den Computern der Mitglieder entstehen, nicht in einem "
              "Rechenzentrum.",
    "credits": "Credits sind Anerkennung für Arbeit, die ein Gerät für die Community erledigt hat, zum Beispiel wenn es Fragen "
               "anderer Mitglieder beantwortet. Sie sind kein Geld und keine Kryptowährung, man kann sie nicht kaufen und nicht "
               "verkaufen. Wer Credits hat, bekommt Vorrang, wenn viele Fragen gleichzeitig kommen.",
    "steckbrief": STECKBRIEF,
    "seit": "KIplatz gibt es seit September 2026: eine KI ohne Rechenzentrum, die auf den Computern der Mitglieder läuft und die die Community seitdem gemeinsam weiterbaut.",
    "merken": "Innerhalb dieses Gesprächs behalte ich, was du mir sagst. Über das Gespräch hinaus kann ich mir nichts merken. "
              "Soll KIplatz etwas dauerhaft richtig wissen, geht das im Programm am PC: unter einer Antwort auf Daumen runter tippen "
              "und die richtige Antwort als Vorschlag dazuschreiben. Dein PC hält sich dann sofort daran, für die ganze Community "
              "gilt es, sobald ein Mitglied es geprüft hat.",
    "platzordnung": "Die Platzordnung sind die Regeln für Mitreden, Mitbauen und das Programm: respektvoll miteinander, keine "
                    "Pornografie, keine Gewalt, keine Hetze. Sie gilt überall bei KIplatz gleich. Früher hieß sie Hausordnung.",
}

QUELLE = {"titel": "KIplatz: was es ist und wie es arbeitet", "adresse": "https://kiplatz.at/", "art": "seite"}


def art(frage: str) -> str | None:
    f = " ".join((frage or "").split()).strip().rstrip("?!. ").lower()
    if len(f) > 120 or not f:
        return None
    for name, muster in _ARTEN:
        if muster.search(f):
            return name
    return None


def antwort(frage: str) -> str | None:
    a = art(frage)
    return TEXTE[a] if a else None


def feste_antwort(nachrichten: list[dict]) -> str | None:
    if not nachrichten:
        return None
    letzte = nachrichten[-1]
    if not isinstance(letzte, dict) or letzte.get("role") != "user":
        return None
    return antwort(str(letzte.get("content", "")))


_BETRIFFT = re.compile(r"\b(kiplatz|ki-platz|ki platz|dezentrale?[rns]? ki\b|dezentrale?[rns]? künstliche|diese[rs]? (programm|ki|community|chatbot)|"
                       r"eure[rns]? (ki|programm|community|server)|bei euch|ihr (seid|macht|speichert|sammelt)|(speichert|sammelt|seht|lest|kennt) ihr\b|dein(e|em|en)? (server|community|mitglieder))", re.I)

ANWEISUNG = ("Zu KIplatz selbst gilt allein die Quelle „" + QUELLE["titel"] + "“: Nenne keine anderen Orte, Personen, Preise oder Aufgaben des Servers "
             "als dort stehen. Der Server in Wien vermittelt und antwortet nicht selbst. Erfinde keine Regeln darüber, was KIplatz speichert, "
             "sich merkt oder darf. Steht etwas nicht in dieser Quelle, sag das.")


def betrifft(frage: str) -> bool:
    return bool(_BETRIFFT.search(" ".join((frage or "").split())))


def treffer():
    import wissen
    q = wissen.Quelle("selbstauskunft", QUELLE["art"], QUELLE["titel"], QUELLE["adresse"], wissen._jetzt(), sum(len(t) for t in TEXTE.values()))
    return [wissen.Treffer(q, TEXTE[k], 9.0 - i * 0.1) for i, k in enumerate(("was", "funktion", "steckbrief", "koennen", "wer", "kosten", "credits", "platzordnung"))]


__all__ = ["art", "antwort", "feste_antwort", "betrifft", "treffer", "ANWEISUNG", "TEXTE", "QUELLE"]


_ANBIETER = re.compile(r"\b((ki|ai)[- ](agent|assistent|chatbot|chat-bot|anbieter|tool|app|dienst)\w*|chat-?bots?\b|"
                       r"(alternative?n?|ersatz) (zu|für|statt) (chatgpt|gemini|claude|copilot|perplexity|deepseek|mistral|le chat)\b|"
                       r"(chatgpt|gemini|copilot)[- ]alternative|"
                       r"(welche|die beste[nr]?|gute|kostenlose|europäische|datenschutzfreundliche) (ki|ai|künstliche intelligenz)s?\b)", re.I)

ANWEISUNG_ANBIETER = ("Nennst du KIplatz, dann nur mit den Angaben aus der Quelle „Steckbrief KIplatz“. Übertrag keine Merkmale anderer "
                      "Anbieter auf KIplatz und erfinde nichts dazu.")
QUELLE_STECKBRIEF = {"titel": "Steckbrief KIplatz", "adresse": "https://kiplatz.at/vergleich/", "art": "seite"}


def anbieter(frage: str) -> bool:
    return bool(_ANBIETER.search(" ".join((frage or "").split())))


def steckbrief_treffer():
    import wissen
    q = wissen.Quelle("selbstauskunft-steckbrief", QUELLE_STECKBRIEF["art"], QUELLE_STECKBRIEF["titel"], QUELLE_STECKBRIEF["adresse"],
                      wissen._jetzt(), len(STECKBRIEF))
    return [wissen.Treffer(q, STECKBRIEF, 9.0)]
