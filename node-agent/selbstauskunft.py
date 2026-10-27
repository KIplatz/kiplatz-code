# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

_KIPLATZ = r"(?:kiplatz|ki-platz|ki platz|dieses programm|diese ki|diese community|das hier|dieser chatbot|dieses ding)"
_ANDERE = re.compile(
    r"\b(?:google gemini|microsoft copilot|meta ai|le chat|chat ?gpt|gpt[- ]?\d[\w.]*|openai|gemini|google|bard|bing|claude|anthropic|copilot|"
    r"microsoft|perplexity|deepseek|mistral|llama|grok|siri|alexa|(?:die )?konkurrenz|"
    r"(?:den |die |der )?(?:anderen?|großen|bekannten|übrigen) (?:kis?|ais?|chatbots?|anbieter|sprachmodelle|assistenten|agenten|"
    r"ki[- ]?(?:agenten|assistenten|modelle|tools|dienste|anbieter))|(?:einer |eine |einen )?anderen? (?:ki|ai|chatbot|ki[- ]?(?:agent|assistent|modell))|"
    r"other (?:ais?|ai (?:agents|assistants|models|tools|chatbots)|chatbots|assistants|models|llms)|another (?:ai|chatbot|assistant)|"
    r"the (?:big|major|large) (?:ai|tech) (?:companies|models|players)|big tech|the competition)\b", re.I)
_SELBST = re.compile(r"\b(?:du|dich|dir|dein\w*|you|your|yourself|this ai|this chatbot|this app|" + _KIPLATZ[3:-1] + r")\b", re.I)
_VERGLEICHSWORT = re.compile(
    r"\b(?:besser|schlechter|klüger|schlauer|schneller|langsamer|genauer|sicherer|intelligenter|stärker|schwächer|gleich gut|so gut|genauso|"
    r"ähnlich|anders|unterschied\w*|unterscheid\w*|statt|anstatt|anstelle|lieber|ersetz\w*|alternative\w*|vergleich\w*|mehr als|weniger als|"
    r"oder|und nicht|vs\.?|versus|gegen|so wie|du (?:\w+ )?wie|better|worse|smarter|faster|slower|stronger|more accurate|safer|as good|differ\w*|"
    r"instead|rather than|replace\w*|compar\w*|more than|less than|similar|the same as|just like|you like|or)\b", re.I)
_BITTE = re.compile(r"\b(?:kannst|könntest|würdest|magst|willst|weißt|denkst|glaubst|meinst|findest|hältst|siehst|kennst|empfiehlst) du\b|"
                    r"\b(?:can|could|would|will) you\b|\bdo you (?:know|think|recommend)\b|\bbist du sicher\b|\bare you sure\b", re.I)
_AUFTRAG = re.compile(r"^(?:schreib\w*|verfass\w*|formulier\w*|erstell\w*|übersetz\w*|dichte|write|draft|create|compose|translate)\b", re.I)
_SICHER_SELBST = re.compile(
    r"\b(?:bist|wärst|wärest) du (?:\w+ ){0,2}(?:\w+er|gut|so gut|genauso gut|ähnlich|anders|gleich|eine alternative|ein ersatz) (?:als|wie|zu|für)\b|"
    r"\bist " + _KIPLATZ + r" (?:\w+ ){0,2}(?:\w+er|gut|so gut|genauso gut|ähnlich|anders|gleich|eine alternative|ein ersatz) (?:als|wie|zu|für)\b|"
    r"\b(?:unterscheidet|trennt|abhebt) (?:dich|" + _KIPLATZ + r")|\bunterschied\w* zwischen (?:dir|" + _KIPLATZ + r")\b|\bund (?:dir|" + _KIPLATZ + r")\b|"
    r"\b(?:kannst|weißt|machst) du (?:\w+ )?(?:mehr|weniger|besser|anders)\b|\bkannst du (?:[\w-]+ ){1,3}ersetzen\b|"
    r"\b(?:are you|is kiplatz) (?:\w+ ){0,2}(?:\w+er than|more \w+ than|less \w+ than|as \w+ as|like|similar to|the same as|an alternative to|a replacement for)\b|"
    r"\b(?:are you|is kiplatz) (?:\w+ ){0,1}(?:different|differ) from\b|\bhow (?:are|do) you (?:differ|compare)\b|\b(?:different|differ) from you\b|"
    r"\bbetween you and\b|\band you\b|\bcan you (?:[\w-]+ ){0,2}(?:replace|do more|beat|compete)\b", re.I)


def _vergleich(f: str) -> bool:
    if not _ANDERE.search(f) or _AUFTRAG.search(f):
        return False
    if _SICHER_SELBST.search(f):
        return True
    return bool(_SELBST.search(_BITTE.sub(" ", f))) and bool(_VERGLEICHSWORT.search(f))

_ARTEN: list[tuple[str, re.Pattern[str] | None]] = [
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
    ("vergleich", None),
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
    "vergleich": "Ich bin anders gebaut als die großen Anbieter, darum messe ich mich nicht an ihnen. Ich laufe nicht in einem "
                 "Rechenzentrum, sondern auf den Computern der Mitglieder: auf deinem PC oder auf einem Gerät der Community, das gerade "
                 "Zeit hat. Unter jeder Antwort stehen die Quellen, und wenn ich etwas nicht weiß, sage ich es, statt zu raten. Ich bin "
                 "kostenlos, ohne Werbung und ohne Konzern dahinter, und Fragen über dich selbst speichert der Server nie. Am besten "
                 "probierst du es aus: Frag mich etwas, das du wirklich wissen willst. Und je mehr Mitglieder mitmachen, desto mehr weiß ich.",
    "steckbrief": STECKBRIEF,
    "lernen": "KIplatz ist ein Programm mit einem Sprachmodell, keine Person: Es hat kein Bewusstsein und keine Gefühle. Mit deinen "
              "Gesprächen wird keine KI trainiert. Besser wird KIplatz, weil Mitglieder Antworten berichtigen: unter einer Antwort Daumen "
              "runter tippen und die richtige Fassung dazuschreiben; dein PC hält sich sofort daran, und sobald ein zweites Gerät sie "
              "geprüft hat, gilt sie für alle. Dazu bereiten die PCs der Community in freien Minuten Wissen auf und prüfen sich dabei "
              "gegenseitig, und geprüfte Antworten auf allgemeine Wissensfragen sind beim nächsten Mal sofort da. Nur wer den Haken "
              "„Meine Fragen helfen beim Lernen“ selbst setzt, hilft mit seinen allgemeinen Wissensfragen mit; ab Werk ist er aus. Was "
              "aktuell ist, schaut KIplatz im Internet nach, einen festen Wissensstand, an dem es aufhört, gibt es darum nicht. KIplatz "
              "schreibt auch Texte, Briefe und Bewerbungen, wenn du darum bittest.",
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
        if (_vergleich(f) if muster is None else muster.search(f)):
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

_WESEN = re.compile(
    r"\b(?:(?:lernst|lernt) du|du (?:\w+ ){0,2}(?:lernst|dazulernst)|kannst du (?:\w+ ){0,2}(?:lernen|dazulernen|fühlen|denken)|"
    r"wie (?:kann|könnte|lässt sich|kann man|könnte man|soll man) (?:man )?dich (?:\w+ ){0,3}(?:trainier\w*|verbesser\w*|beibring\w*|schlauer|klüger)|"
    r"(?:wer|was|womit|wie) (?:hat|wurdest|bist|wirst) (?:dich |du )?(?:\w+ ){0,2}trainiert|(?:wirst|wurdest) du (?:\w+ ){0,2}trainiert|"
    r"wie (?:intelligent|schlau|klug|gut|dumm) bist du|(?:bist|wirst) du (?:\w+ ){0,2}(?:intelligent|schlau|klug|dumm|lernfähig|besser|klüger|schlauer)\b(?! als)|"
    r"warum (?:kannst|darfst|machst|weißt) du (?:das|dies|es|so etwas|sowas)? ?nicht|was kannst du nicht|"
    r"dein(?:e|en)? (?:grenzen|schwächen|stärken|trainingsdaten|training|wissensstand|trainingsstand|gedächtnis)|"
    r"hast du (?:ein |eine |einen )?(?:bewusstsein|gefühle|gedächtnis|eigene meinung|meinung)|"
    r"do you (?:learn|remember|have feelings|have (?:a )?consciousness)|can you (?:learn|feel|think)\b|"
    r"how (?:can|do|could) (?:i|we|one|you) (?:train|improve|teach) you|how (?:smart|intelligent|clever|good) are you|"
    r"are you (?:\w+ ){0,1}(?:smart|intelligent|conscious|sentient|learning)|who (?:trained|made|built) you|"
    r"why (?:can't|can not|cannot|won't|don't) you|what can't you do|your (?:limits|limitations|weaknesses|strengths|training(?: data)?|knowledge cutoff))\b",
    re.I)

ANWEISUNG = ("Zu KIplatz selbst gilt allein die Quelle „" + QUELLE["titel"] + "“: Nenne keine anderen Orte, Personen, Preise oder Aufgaben des Servers "
             "als dort stehen. Der Server in Wien vermittelt und antwortet nicht selbst. Erfinde keine Regeln darüber, was KIplatz speichert, "
             "sich merkt, lernt oder darf, nenne keinen Trainingsstand und kein Datum, bis zu dem du etwas weißt, und beschreib dich nicht kleiner, "
             "als die Quelle sagt. Steht etwas nicht in dieser Quelle, sag das.")


def betrifft(frage: str) -> bool:
    f = " ".join((frage or "").split())
    return bool(_BETRIFFT.search(f) or _WESEN.search(f))


def treffer():
    import wissen
    q = wissen.Quelle("selbstauskunft", QUELLE["art"], QUELLE["titel"], QUELLE["adresse"], wissen._jetzt(), sum(len(t) for t in TEXTE.values()))
    return [wissen.Treffer(q, TEXTE[k], 9.0 - i * 0.1)
            for i, k in enumerate(("was", "funktion", "steckbrief", "koennen", "lernen", "wer", "kosten", "credits", "platzordnung"))]


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
