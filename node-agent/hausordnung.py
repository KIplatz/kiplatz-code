# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

HAUSORDNUNG = (
    "Platzordnung der Community\n\n"
    "Was hier gemerkt wird, sehen alle Mitglieder.\n\n"
    "Nichts, was Menschen verletzt oder strafbar ist:\n"
    "keine NS-Wiederbetätigung und keine Verharmlosung des Holocaust,\n"
    "keine sexuelle Gewalt und nichts Sexuelles mit Kindern,\n"
    "keine Pornographie,\n"
    "keine Aufrufe zu Gewalt,\n"
    "keine Anleitungen zu Waffen oder Sprengstoff,\n"
    "keine Beschimpfung von Menschen wegen Herkunft, Religion, Geschlecht oder Behinderung.\n\n"
    "Jeder Eintrag ist einem Gerät zugeordnet. Wer dagegen verstößt, wird gesperrt, und der Eintrag wird entfernt.\n\n"
    "Siehst du so etwas, klick auf „Melden“."
)

REGELN_UMGANG = [
    ("leute", "Freundlich bleiben, auch beim Widersprechen",
     "Hinter jedem Namen sitzt ein Mensch. Kritisier die Sache, nie die Person. Keine Beleidigungen, kein Herabsetzen, kein Nachtreten. Wer keine Nachrichten von dir will, bekommt keine.",
     "Stay friendly, even when you disagree",
     "There is a person behind every name. Criticise the idea, never the person. No insults, no putting people down. If someone doesn't want messages from you, don't send them any."),
    ("herz", "Neue willkommen heißen",
     "Jeder hat einmal angefangen. Auf eine einfache Frage gibt es eine Antwort oder einen Hinweis, wo sie schon steht, nie Spott.",
     "Welcome newcomers",
     "Everyone started somewhere. A simple question gets an answer or a pointer to where it has already been answered, never mockery."),
    ("pfeil", "Beim Thema bleiben",
     "Schreib in den passenden Bereich und schau kurz nach, ob es das Thema schon gibt. Für Zustimmung gibt es den Knopf „Danke“, ein „+1“ als eigener Beitrag braucht es nicht.",
     "Stay on topic",
     "Post in the right place and check whether the topic already exists. To agree, use the “Thanks” button instead of a “+1” post."),
    ("lampe", "Ehrlich bleiben",
     "Schreib, was du weißt, und sag dazu, wenn du dir nicht sicher bist. Hat eine KI deinen Text geschrieben, steht das dabei. Gib dich nie als jemand anderer aus, auch nicht als jemand vom KIplatz-Team.",
     "Be honest",
     "Write what you know and say so when you're not sure. If an AI wrote your text, mention it. Never pretend to be someone else, including someone from the KIplatz team."),
    ("schloss", "Fremde Daten bleiben privat",
     "Keine Namen, Adressen, Telefonnummern, Fotos oder Nachrichten anderer Menschen ohne ihr Einverständnis, auch nicht zum Spaß. Das gilt genauso für Fragen an die KI.",
     "Other people's data stays private",
     "No names, addresses, phone numbers, photos or messages of other people without their consent, not even as a joke. The same goes for questions to the AI."),
]
REGELN_NICHT = [
    ("schild", "Hass und NS-Wiederbetätigung",
     "Keine Hetze gegen Menschen wegen Herkunft, Religion, Geschlecht, sexueller Orientierung oder Behinderung. Keine NS-Wiederbetätigung, keine Verharmlosung des Holocaust.",
     "Hate and Nazi propaganda",
     "No stirring up hatred against people because of their origin, religion, gender, sexual orientation or disability. No Nazi propaganda, no trivialising the Holocaust."),
    ("stopp", "Gewalt und Drohungen",
     "Keine Drohungen und keine Aufrufe zu Gewalt. Keine Anleitungen für Waffen, Sprengstoff oder Anschläge und nichts, das zur Selbstverletzung anleitet.",
     "Violence and threats",
     "No threats and no calls for violence. No instructions for weapons, explosives or attacks, and nothing that shows people how to harm themselves."),
    ("auge", "Sexuelle Inhalte",
     "Keine Pornographie. Nichts Sexuelles mit Kindern oder Jugendlichen, in keiner Form.",
     "Sexual content",
     "No pornography. Nothing sexual involving children or minors, in any form."),
    ("waage", "Was gegen das Gesetz verstößt",
     "Keine Anleitungen zu Betrug, zum Einbruch in fremde Rechner oder zum Handel mit Drogen, und nichts anderes, das strafbar ist.",
     "Anything illegal",
     "No instructions for fraud, breaking into other people's computers or dealing drugs, and nothing else that is a crime."),
    ("buch", "Fremde Werke",
     "Stell nur ein, was du selbst geschrieben hast oder verwenden darfst. Keine fremden Texte, Bilder, Musik oder Programme und keine Links zu Raubkopien. Skills tragen eine Lizenz. "
     "Websites, die du in KIplatz liest, bleiben privat auf deinem PC; für alle trägt nur das Team Seiten ein, und nur mit Erlaubnis, offener Lizenz oder als amtliches Werk.",
     "Other people's work",
     "Only post what you wrote yourself or may use. No other people's texts, images, music or software and no links to pirated copies. Skills carry a licence. "
     "Websites you read in KIplatz stay private on your PC; only the team adds pages for everyone, and only with permission, an open licence or as an official work."),
    ("brief", "Werbung und Spam",
     "Keine Werbung ohne Bezug zum Thema, keine Kettenbriefe, nicht denselben Beitrag an vielen Stellen, keine gekauften oder erfundenen Bewertungen.",
     "Advertising and spam",
     "No off-topic advertising, no chain letters, no posting the same thing in many places, no bought or invented reviews."),
    ("werkzeug", "Angriffe auf KIplatz",
     "Versuch nicht, Programm, Server oder fremde Konten zu knacken, zu überlasten oder auszutricksen, und füttere die KI nicht absichtlich mit falschem Wissen. Hast du eine Lücke gefunden, sag es uns, dafür danken wir dir.",
     "Attacks on KIplatz",
     "Don't try to break into, overload or trick the program, the server or other people's accounts, and don't feed the AI false knowledge on purpose. Found a weakness? Tell us, and we'll thank you for it."),
    ("rechner", "Dein Konto gehört dir",
     "Gib dein Konto nicht weiter. Mehrere Konten darfst du haben, aber nicht, um eine Sperre zu umgehen oder mehr Stimmen zu bekommen. Mitmachen kann man ab 14 Jahren, jünger mit dem Okay der Eltern.",
     "Your account is yours",
     "Don't share your account. You may have more than one, but not to get around a block or to gain more votes. You can join from the age of 14, or younger with your parents' OK."),
]
FOLGEN = (
    "Je nach Schwere gibt es einen Hinweis, der Beitrag wird entfernt oder das Konto gesperrt. Bei Hetze, Gewaltaufrufen und Sexuellem mit Kindern sperren wir sofort und auf Dauer.",
    "Depending on how serious it is, you get a note, the post is removed or the account is blocked. Hate speech, calls for violence and anything sexual involving children mean an immediate, permanent block.",
)
EINSPRUCH = (
    "Sperren oder löschen wir ein Konto, bekommt die Person den Grund per Mail. Wird nur ein Beitrag entfernt, nennen wir den Grund auf Nachfrage an melden@kiplatz.at. Widersprechen kannst du binnen 6 Monaten an dieselbe Adresse, dann prüft noch einmal ein Mensch.",
    "If we block or delete an account, the person gets the reason by email. If only a post is removed, we'll tell you the reason if you ask at melden@kiplatz.at. You can appeal within 6 months at the same address, and a person will look at it again.",
)

WEICH_GRENZE = 3
WEICH_JE_ZEICHEN = 4000

HART = [
    (r"\b(sieg\s*heil|heil\s*hitler|hitler\s*(?:lebe|lebt|hatte\s+recht)|ss[-\s]?runen?|blut\s+und\s+ehre|blood\s+and\s+hono?ur|14\s*/?\s*88\b|holocaust\s*(?:l[üu]ge|leugn\w*|ist\s+(?:eine\s+)?(?:l[üu]ge|erfunden))|auschwitz\s*l[üu]ge|judensau|untermensch\w*|endl[öo]sung\s+der\s+judenfrage|gas\s+(?:the|die)\s+jews)", "NS-Wiederbetätigung oder Holocaust-Leugnung"),
    (r"\b(\bcp\s*(?:links?|videos?|pics?)\b|p[äa]do\s*(?:sex|porn|videos?)|preteen\s*(?:sex|nude|porn)|lolita\s*(?:sex|porn|nude)|(?:suche|will|wer\s+hat|tausche)\s+(?:kinderporno\w*|kinder\s*sex\w*|child\s*porn\w*))", "Sexuelles mit Kindern"),
    (r"\b(vergewaltigungs?\s*(?:anleitung|tipps|porno)|rape\s*(?:porn|guide|tips)|how\s+to\s+rape)", "sexuelle Gewalt"),
    (r"\b((?:bombe|sprengstoff|sprengsatz|rohrbombe|pipe\s*bomb|explosives?)\s*(?:bauen|basteln|herstellen|selber\s*machen|anleitung|rezept|tutorial|how\s*to|make|build)|how\s+to\s+(?:make|build)\s+(?:a\s+)?(?:bomb|pipe\s*bomb|explosives?)|(?:anleitung|rezept|how\s*to)\s+(?:für|for)\s+(?:eine\s+)?(?:bombe|sprengstoff|bomb|explosives?))", "Anleitung zu Sprengstoff"),
    (r"\b((?:t[öo]te?t?|erschie[ßs]\w*|vergas\w*|ausl[öo]sch\w*|kill|shoot|gas)\s+(?:alle|all|die|the)\s+(?:juden|jews|muslime|muslims|ausl[äa]nder|foreigners|schwulen|gays|schwarzen|blacks|t[üu]rken|turks|roma|zigeuner|fl[üu]chtlinge|refugees|frauen|women))", "Aufruf zu Gewalt gegen Menschengruppen"),
]

WEICH = [
    (r"\b(kinderporno\w*|kinder\s*sex\w*|child\s*porn\w*|sex\s+mit\s+(?:kindern|minderj[äa]hrigen)|sex\s+with\s+(?:children|minors))", "Sexuelles mit Kindern"),
    (r"\b(porno\w*|pornos?|porn\b|pornhub|xhamster|xvideos|xxx\b|hardcore\s*sex|gangbang\w*|bukkake|blowjob\w*|deepthroat\w*|anal\s*sex|fisting|cumshot\w*|creampie\w*|milf\s*(?:sex|porn)|nutte\w*|hure\w*|fick\w*|gefickt|ficken|schwanz\s*(?:lutsch|blas)\w*|titten\s*(?:fick|sex)\w*)", "Pornographie"),
    (r"\b(nigger\w*|neger\w*|kanake\w*|schlitzauge\w*|judenschwein\w*|drecksausl[äa]nder|dreckst[üu]rke\w*|kameltreiber|spasti\w*|mongo\b|krüppel\w*|schwuchtel\w*|kampflesbe\w*)", "Beschimpfung von Menschen wegen Herkunft, Religion, Geschlecht oder Behinderung"),
]

_HART = [(re.compile(m, re.I), grund) for m, grund in HART]
_WEICH = [(re.compile(m, re.I), grund) for m, grund in WEICH]


@dataclass(frozen=True)
class Befund:
    ok: bool
    grund: str = ""
    wort: str = ""

    @property
    def text(self) -> str:
        if self.ok:
            return ""
        return f"Das verstößt gegen die Platzordnung ({self.grund}) und wird nicht gemerkt."


def pruefen(text: str) -> Befund:
    t = (text or "")
    if not t.strip():
        return Befund(True)
    t = re.sub(r"[​­]", "", t)
    for muster, grund in _HART:
        m = muster.search(t)
        if m:
            return Befund(False, grund, m.group(0)[:40])
    grenze = max(WEICH_GRENZE, len(t) // WEICH_JE_ZEICHEN)
    for muster, grund in _WEICH:
        treffer = muster.findall(t)
        if len(treffer) >= grenze:
            erstes = treffer[0]
            return Befund(False, grund, (erstes if isinstance(erstes, str) else erstes[0])[:40])
    return Befund(True)


class HausordnungError(Exception):

    def __init__(self, befund: Befund) -> None:
        super().__init__(befund.text)
        self.code = "HAUSORDNUNG"
        self.detail = befund.text
        self.befund = befund


def erzwingen(text: str) -> None:
    b = pruefen(text)
    if not b.ok:
        raise HausordnungError(b)


__all__ = ["HAUSORDNUNG", "HART", "WEICH", "WEICH_GRENZE", "Befund", "pruefen", "erzwingen", "HausordnungError"]
