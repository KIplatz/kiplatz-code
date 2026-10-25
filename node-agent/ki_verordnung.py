# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

GEMACHT = "geprüft, ohne Modell"
WOHER = ("KI-Verordnung der EU (Verordnung (EU) 2024/1689) mit den Fristen nach der Omnibus-Einigung vom 7. Mai 2026, vom Programm "
         "selbst eingeordnet, ohne Modell; keine Rechtsberatung.")
RUECKFRAGE_ANFANG = "Damit ich dir sagen kann, was die KI-Verordnung für dich heißt, brauche ich noch"
RUECKFRAGE_ANFANG_EN = "So I can tell you what the AI Act means for you, I still need"

_GESETZ = re.compile(r"(?i)(?:ki[- ]?verordnung|ai[- ]?act|ki[- ]?gesetz|2024/1689|eu[- ]ki[- ]?regeln|artificial intelligence act)")
_BETRIEB = re.compile(r"(?i)\b(?:betrieb\w*|firma|unternehm\w*|gesch[äa]ft|einzelunternehm\w*|selbst[äa]ndig\w*|mich|uns|meine[nmr]?|unsere[nmr]?|"
                      r"betrifft|gilt|muss\s+ich|m[üu]ssen\s+wir|pflicht\w*|business|company|firm|me|us|my|our|apply|affect\w*|obligation\w*|"
                      r"do\s+i\s+(?:need|have)|must\s+(?:i|we))\b")

_NEIN = re.compile(r"(?i)\b(?:(?:wir\s+)?(?:nutzen|benutzen|verwenden)\s+(?:gar\s+)?keine|gar\s+keine\s+ki|keine\s+ki|nein,?\s+gar\s+nicht|"
                   r"(?:we\s+)?(?:don'?t|do\s+not)\s+use\s+(?:any\s+)?ai|no\s+ai\s+at\s+all)\b")
_UNKLAR = re.compile(r"(?i)\b(?:wei[ßs]\s+(?:ich\s+)?nicht|keine\s+ahnung|unsicher|not\s+sure|don'?t\s+know|no\s+idea)\b")
_WER = {"ich": r"\b(?:nur\s+ich|ich\s+selbst|ich\s+allein|allein|einzelunternehm\w*|ein-?personen|only\s+me|just\s+me|myself|on\s+my\s+own|"
               r"sole\s+(?:trader|proprietor)|self-employed)",
        "angestellte": r"\b(?:angestellt\w*|mitarbeiter\w*|lehrling\w*|aushilf\w*|team|kolleg\w*|belegschaft|personal\b|employees?|staff|team|apprentices?|colleagues?)",
        "extern": r"\b(?:extern\w*|agentur\w*|buchhalt\w*|freie[nr]?\s+mitarbeiter\w*|freelancer\w*|dienstleister\w*|agency|agencies|accountants?|"
                  r"contractors?|freelancers?|outsourc\w*)"}
_WOFUER = {"buero": r"(?:text\w*|e-?mails?|mails?|übersetz\w*|zusammenfass\w*|idee\w*|briefe?|angebot\w*|bürosoftware|copilot|chatgpt|"
                    r"translat\w*|summar\w*|letters?|writing|ideas?|office)",
           "chatbot": r"(?:chatbot\w*|chat-?bot\w*|chatfenster|chat\s+auf|automatische\s+antwort\w*|kundendienst\w*|kundenchat|"
                      r"customer\s+(?:chat|service|support)|automated\s+(?:replies|answers))",
           "medien": r"(?:bilder?n?|fotos?|videos?|stimmen?|grafik\w*|social\s*media|werbe(?:bild|video)\w*|images?|pictures?|voices?|audio|graphics?)",
           "personal": r"(?:bewerb\w*|personalauswahl|personal\s+aus(?:wählen|wahl)|recruit\w*|lebensl[äa]uf\w*|mitarbeiter\s+bewerten|hiring|"
                       r"job\s+applications?|applicants?|cvs?|résumés?|resumes?|hr\b)",
           "anbieter": r"(?:(?:bauen|entwickeln|verkaufen|programmieren)\s+(?:selbst\s+)?(?:\w+\s+){0,3}(?:ki|programm|app|software)|eigene[ns]?\s+ki|"
                       r"ki-?produkt\w*|we\s+(?:build|develop|sell)\s+(?:\w+\s+){0,3}(?:ai|software|app|tool)|our\s+own\s+ai)"}
_DOKU_NEIN = re.compile(r"(?i)\b(?:nichts\s+(?:schriftlich|aufgeschrieben|festgehalten)|nicht(?:s)?\s+aufgeschrieben|gar\s+nichts|bisher\s+nichts|"
                        r"keine\s+(?:regel\w*|richtlinie|unterweisung)|aufgeschrieben\s+ist\s+nichts|ist\s+nichts\s+(?:schriftlich|aufgeschrieben)|"
                        r"nothing\s+(?:written|in\s+writing)|no\s+(?:policy|rules|training)|nothing\s+yet)\b")
_DOKU_MUENDLICH = re.compile(r"(?i)\b(?:geredet|mündlich|muendlich|besprochen|verbal\w*|talked|discussed|spoken)\b")
_DOKU_JA = re.compile(r"(?i)\b(?:schriftlich\w*|regelung|richtlinie|unterweisung|geschult|schulung|in\s+writing|written\s+(?:policy|rules)|policy|"
                      r"trained|training)\b")


def gewuenscht(text: str) -> bool:
    t = str(text or "")
    return bool(_GESETZ.search(t) and _BETRIEB.search(t))


def angaben(text: str) -> dict:
    t = str(text or "")
    a: dict = {"nutzung": "", "wer": [], "wofuer": [], "doku": ""}
    if _NEIN.search(t):
        a["nutzung"] = "nein"
    elif _UNKLAR.search(t) and not re.search(r"(?i)\b(?:chatgpt|copilot|gemini|nutzen|benutzen|verwenden|use|using)\b", t):
        a["nutzung"] = "unklar"
    a["wer"] = [k for k, m in _WER.items() if re.search("(?i)" + m, t)]
    a["wofuer"] = [k for k, m in _WOFUER.items() if re.search("(?i)" + m, t)]
    if a["wofuer"] or a["wer"]:
        a["nutzung"] = a["nutzung"] if a["nutzung"] == "nein" and not a["wofuer"] else "ja"
    if _DOKU_NEIN.search(t):
        a["doku"] = "nein"
    elif _DOKU_MUENDLICH.search(t):
        a["doku"] = "muendlich"
    elif _DOKU_JA.search(t):
        a["doku"] = "ja"
    return a


def antwort(nachrichten: list[dict]) -> tuple[str, str] | None:
    if not nachrichten or nachrichten[-1].get("role") != "user":
        return None
    letzte = str(nachrichten[-1].get("content", ""))
    vorige = next((str(n.get("content", "")) for n in reversed(nachrichten[:-1]) if n.get("role") == "assistant"), "")
    nach_rueckfrage = vorige.startswith(RUECKFRAGE_ANFANG) or vorige.startswith(RUECKFRAGE_ANFANG_EN)
    if nach_rueckfrage:
        frueher = [str(n.get("content", "")) for n in nachrichten[:-1] if n.get("role") == "user"]
        text = " ".join(frueher[-1:] + [letzte])
    else:
        text = letzte
    if not gewuenscht(text):
        return None
    a = angaben(text)
    if not nach_rueckfrage and a["nutzung"] != "nein" and not (a["wer"] and a["wofuer"]):
        return _rueckfrage()
    return ergebnis(a)


def _rueckfrage() -> tuple[str, str]:
    de = (RUECKFRAGE_ANFANG + " vier kurze Angaben, in einem Satz reicht es:\n"
          "- Wird bei euch KI benutzt, etwa ChatGPT, Copilot oder eine KI-Funktion in der Bürosoftware, regelmäßig, ab und zu oder gar nicht?\n"
          "- Wer benutzt sie: nur du selbst, Angestellte oder Lehrlinge, oder Externe wie Agentur oder Buchhaltung?\n"
          "- Wofür: Texte und E-Mails, ein Chatbot, mit dem Kunden schreiben, Bilder oder Videos zum Veröffentlichen, Bewerbungen und Personal, "
          "oder baut oder verkauft ihr selbst ein Programm mit KI?\n"
          "- Gibt es etwas Schriftliches, was eure Leute damit dürfen, nur Besprochenes oder noch nichts?\n"
          "Zum Beispiel: „Ich und zwei Angestellte, für E-Mails und einen Chatbot auf der Website, aufgeschrieben ist nichts.“")
    en = (RUECKFRAGE_ANFANG_EN + " four short details, one sentence is enough:\n"
          "- Do you use AI, for example ChatGPT, Copilot or an AI feature in your office software, regularly, now and then, or not at all?\n"
          "- Who uses it: only you, employees or apprentices, or outside people such as an agency or your accountant?\n"
          "- What for: texts and emails, a chatbot customers write to, images or videos you publish, job applications and staff, "
          "or do you build or sell a program with AI yourselves?\n"
          "- Is anything written down about what your people may do with it, only talked about, or nothing yet?\n"
          "For example: “Me and two employees, for emails and a chatbot on our website, nothing written down.”")
    return de, en


def ergebnis(a: dict) -> tuple[str, str]:
    if a.get("nutzung") == "nein":
        return ("Im Moment betrifft dich die KI-Verordnung nicht: Solange in deinem Betrieb niemand KI für die Arbeit nutzt, gibt es nichts zu tun. "
                "Das ändert sich an dem Tag, an dem jemand damit anfängt, auch wenn er dich vorher nicht fragt.\n\n" + _SCHLUSS[0],
                "Right now the AI Act doesn't affect you: as long as nobody in your business uses AI for work, there's nothing to do. That changes on "
                "the day someone starts, even if they don't ask you first.\n\n" + _SCHLUSS[1])
    wer, wofuer, doku = a.get("wer") or [], a.get("wofuer") or [], a.get("doku", "")
    allein = wer == ["ich"]
    de, en = [], []
    if a.get("nutzung") == "unklar":
        de.append("Ja, es betrifft dich mit großer Wahrscheinlichkeit: KI steckt heute in Bürosoftware, Übersetzern und Kundendienst-Programmen, "
                  "oft ohne dass es draufsteht.")
        en.append("Yes, it very likely affects you: AI is built into office software, translators and customer service tools today, often "
                  "without saying so.")
    else:
        de.append("Ja, die KI-Verordnung betrifft dich: Sobald in deinem Betrieb jemand ein Programm wie ChatGPT für die Arbeit nutzt, gilt sie.")
        en.append("Yes, the AI Act affects you: as soon as someone in your business uses a program like ChatGPT for work, it applies.")
    if allein:
        de.append("Gilt jetzt, Artikel 4, KI-Kompetenz: Auch als Einzelunternehmer bist du erfasst, die Größe des Betriebs spielt keine Rolle. "
                  "Du musst selbst etwas dafür tun, zu verstehen, was das Programm kann und wo es Fehler macht.")
        en.append("Applies now, Article 4, AI literacy: sole traders are covered too, the size of the business doesn't matter. You have to "
                  "make an effort yourself to understand what the program can do and where it gets things wrong.")
    else:
        de.append("Gilt jetzt, Artikel 4, KI-Kompetenz: Alle, die im Namen des Betriebs mit KI arbeiten, müssen wissen, was sie tun. Ein "
                  "bestimmtes Niveau ist seit Juli 2026 nicht mehr vorgeschrieben, dass du etwas dafür tust, schon. Die Pflicht gilt seit "
                  "2. Februar 2025, seit 2. August 2026 dürfen die Behörden sie durchsetzen, in Österreich die RTR.")
        en.append("Applies now, Article 4, AI literacy: everyone who works with AI on behalf of your business has to know what they're doing. "
                  "Since July 2026 no particular level is required, but you do have to take measures. The duty has applied since 2 February "
                  "2025, and since 2 August 2026 the authorities can enforce it, in Austria the RTR.")
    if "extern" in wer:
        de.append("Beachten, Externe zählen mit: Setzt deine Agentur oder Buchhaltung für dich KI ein, gehört sie zu den Personen, die in "
                  "deinem Auftrag damit arbeiten. Ein Absatz im Auftrag an sie reicht dafür.")
        en.append("Note, outside people count: if your agency or accountant uses AI for you, they're among the people working with it on "
                  "your behalf. A paragraph in your contract with them covers it.")
    if "chatbot" in wofuer:
        de.append("Gilt jetzt, Artikel 50, Chatbot kennzeichnen: Wer euch schreibt, muss spätestens bei der ersten Nachricht erkennen können, "
                  "dass ein Programm antwortet und kein Mensch. Ein Satz über dem Chatfenster genügt. Gilt seit 2. August 2026, nicht verschoben.")
        en.append("Applies now, Article 50, label the chatbot: anyone writing to you must be able to tell by the first message at the latest "
                  "that a program is answering, not a person. One sentence above the chat window is enough. Applies since 2 August 2026, "
                  "not postponed.")
    if "medien" in wofuer:
        de.append("Gilt jetzt, Artikel 50, erzeugte Bilder, Videos und Stimmen kennzeichnen: Was ihr veröffentlicht und künstlich erzeugt "
                  "ist, muss als solches erkennbar sein. Gilt seit 2. August 2026.")
        en.append("Applies now, Article 50, label generated images, videos and voices: anything you publish that was artificially "
                  "generated must be recognisable as such. Applies since 2 August 2026.")
    if "personal" in wofuer:
        de.append("Gilt später, Personalauswahl: KI für Bewerbungen, Auswahl und Bewertung von Personal gilt als Hochrisiko (Anhang III). "
                  "Diese Pflichten kommen nach der Omnibus-Einigung vom 7. Mai 2026 erst ab 2. Dezember 2027, viele Seiten nennen noch den "
                  "alten Termin. Warten würde ich trotzdem nicht: Es geht um Entscheidungen über Menschen, und Artikel 4 gilt schon.")
        en.append("Applies later, recruitment: AI used for applications, selecting or assessing staff counts as high-risk (Annex III). "
                  "Under the omnibus agreement of 7 May 2026 these duties only start on 2 December 2027; many sites still give the old date. "
                  "Waiting isn't wise though: these are decisions about people, and Article 4 applies already.")
    if "anbieter" in wofuer:
        de.append("Beachten, ihr seid wohl Anbieter: Wer ein KI-Programm selbst baut oder unter eigenem Namen weitergibt, hat deutlich mehr "
                  "Pflichten als jemand, der es nur benutzt. Hier lohnt sich ein Termin bei jemandem, der rechtlich beraten darf.")
        en.append("Note, you're probably a provider: anyone who builds an AI program or passes it on under their own name has far more "
                  "duties than someone who only uses one. This is where an appointment with a lawyer pays off.")
    if doku in ("nein", "muendlich"):
        de.append("Beachten, es fehlt der Nachweis: " + ("Darüber geredet zu haben ist gut, zeigen kannst du im Ernstfall aber nur etwas "
                  "Schriftliches: was gemacht wurde, wann und mit wem. Eine Seite reicht." if doku == "muendlich" else
                  "Ohne etwas Schriftliches kannst du im Ernstfall nicht zeigen, dass du die Pflicht erfüllt hast. Eine Seite reicht: "
                  "was eure Leute dürfen, was nicht, wann ihr darüber gesprochen habt."))
        en.append("Note, there's no record: " + ("Talking about it is good, but if it ever matters you can only show something in writing: "
                  "what was done, when and with whom. One page is enough." if doku == "muendlich" else
                  "Without anything in writing you can't show you've met the duty if it ever matters. One page is enough: what your people "
                  "may do, what not, and when you talked about it."))
    elif not doku:
        if allein:
            de.append("Tipp: Halte kurz schriftlich fest, wie du dich mit dem Programm vertraut gemacht hast und wofür du es nutzt; eine Seite reicht als Nachweis.")
            en.append("Tip: write down briefly how you got to know the program and what you use it for; one page is enough as a record.")
        else:
            de.append("Tipp: Halte schriftlich fest, was eure Leute mit KI dürfen und wann ihr darüber gesprochen habt; eine Seite reicht als Nachweis.")
            en.append("Tip: write down what your people may do with AI and when you talked about it; one page is enough as a record.")
    de.append("Was du nicht brauchst: Die Verordnung schreibt weder einen Kurs noch ein Zertifikat vor; eine Unterweisung, die zu deinem "
              "Betrieb passt und festgehalten ist, genügt. Für Artikel 4 gibt es auch keine eigene Geldstrafe: Die oft genannten 15 oder "
              "35 Millionen Euro (Artikel 99) gelten für verbotene Praktiken und Hochrisiko-Systeme. Fehlt die Unterweisung, kann das im "
              "Streitfall aber als Organisationsverschulden zählen.")
    en.append("What you don't need: the regulation requires neither a course nor a certificate; a briefing that fits your business and is "
              "written down is enough. There's no separate fine for Article 4 either: the often-quoted 15 or 35 million euros (Article 99) "
              "apply to prohibited practices and high-risk systems. A missing briefing can still count as organisational negligence in a dispute.")
    de.append(_SCHLUSS[0])
    en.append(_SCHLUSS[1])
    return "\n\n".join(de), "\n\n".join(en)


_SCHLUSS = ("Das ist eine Einordnung nach dem Stand der KI-Verordnung der EU (2024/1689) mit den Fristen der Omnibus-Einigung vom 7. Mai 2026, "
            "keine Rechtsberatung. Setzt ihr KI bei Personalentscheidungen ein oder bietet ihr selbst KI-Programme an, sollte das jemand "
            "ansehen, der rechtlich beraten darf.",
            "This is an assessment based on the EU AI Act (2024/1689) with the deadlines of the omnibus agreement of 7 May 2026, not legal "
            "advice. If you use AI for staffing decisions or offer AI programs yourselves, have someone qualified to give legal advice look at it.")
