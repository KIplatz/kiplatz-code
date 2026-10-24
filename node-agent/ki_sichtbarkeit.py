# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import urllib.parse

import wissen

GEMACHT = "geprüft, ohne Modell"
WOHER = "robots.txt und tdmrep.json der Website, vom Programm gelesen und ausgewertet, ohne Modell."

FUER_ANTWORTEN = (("OAI-SearchBot", "ChatGPT-Suche", "ChatGPT search"), ("ChatGPT-User", "ChatGPT beim Öffnen einer Seite", "ChatGPT opening a page"),
                  ("Claude-SearchBot", "Claude-Suche", "Claude search"), ("Claude-User", "Claude beim Öffnen einer Seite", "Claude opening a page"),
                  ("PerplexityBot", "Perplexity-Suche", "Perplexity search"), ("Perplexity-User", "Perplexity beim Öffnen einer Seite", "Perplexity opening a page"),
                  ("MistralAI-User", "Le Chat", "Le Chat"), ("KIplatz", "KIplatz", "KIplatz"))
FUER_TRAINING = (("GPTBot", "Training von ChatGPT", "ChatGPT training"), ("ClaudeBot", "Training von Claude", "Claude training"),
                 ("Google-Extended", "Training von Gemini", "Gemini training"), ("Applebot-Extended", "Training von Apple Intelligence", "Apple Intelligence training"),
                 ("meta-externalagent", "Training von Meta AI", "Meta AI training"), ("CCBot", "Common Crawl (Stoff für viele KIs)", "Common Crawl (material for many AIs)"),
                 ("Amazonbot", "Amazon", "Amazon"), ("Bytespider", "Training von ByteDance", "ByteDance training"))
_WUNSCH = re.compile(
    r"(?i)\b(?:darf|dürfen|kann|können|lässt|sperrt|sperre\w*|blockier\w*|erlaubt?)\b.{0,60}?\b(?:ki\w*|chatgpt|claude|gemini|perplexity|copilot|crawler|bots?|"
    r"ki-programme|gptbot)\b.{0,60}?\b(?:website|webseite|homepage|seite|domain|shop)\b"
    r"|\b(?:ki\w*|chatgpt|claude|gemini|perplexity)\b.{0,40}?\b(?:website|webseite|homepage|seite)\b.{0,40}?\b(?:lesen|durchsuchen|crawlen|sehen|finden|"
    r"zugreifen)\b|\bki-?sichtbarkeit\w*|\brobots\.txt\b.{0,40}?\b(?:prüf\w*|check\w*|ki)"
    r"|\b(?:can|may|is|are)\b.{0,40}?\b(?:ai|chatgpt|claude|gemini|perplexity|crawlers?|bots?)\b.{0,50}?\b(?:read|crawl|access|see|index|blocked)\b"
    r".{0,40}?\b(?:website|site|homepage|domain)\b|\b(?:check|test)\b.{0,30}?\brobots\.txt\b"
    r"|\b(?:website|site|homepage)\b.{0,30}?\bblocked\b.{0,30}?\b(?:ai|crawlers?|bots?|chatgpt)\b")
_DOMAIN = re.compile(r"(?i)\b(?:https?://)?((?:[a-z0-9äöü-]+\.)+[a-z]{2,24})(?:/\S*)?")


def gewuenscht(text: str) -> bool:
    return bool(_WUNSCH.search(str(text or "")))


def adresse_aus(text: str) -> str:
    for m in _DOMAIN.finditer(str(text or "")):
        host = m.group(1).lower().rstrip(".")
        if not re.search(r"\.(?:txt|pdf|png|jpe?g|html?)$", host):
            return host
    return ""


def pruefen(host: str, *, oeffner=None) -> dict:
    oeffner = oeffner or __import__("datenfluss").oeffner("Website lesen")
    adresse = f"https://{host}/"
    parser, aus, tdm = wissen._host_regeln(host, oeffner)
    if aus:
        return {"fehler": aus}
    def darf(name: str) -> bool:
        try:
            return parser is None or bool(parser.can_fetch(name, adresse))
        except Exception:
            return False
    vorbehalt = any(str(r.get("tdm-reservation", "0")).strip() == "1" for r in tdm)
    return {"fehler": "", "antworten": [(n, w, e, darf(n)) for n, w, e in FUER_ANTWORTEN], "training": [(n, w, e, darf(n)) for n, w, e in FUER_TRAINING],
            "tdm": vorbehalt, "ohne_robots": parser is None}


def antwort(nachricht: str, *, oeffner=None, adresse_pruefen=None) -> tuple[str, str] | None:
    if not gewuenscht(nachricht):
        return None
    host = adresse_aus(nachricht)
    if not host:
        return ("Nenn mir die Adresse der Website, zum Beispiel: „Darf KI meine Website lesen? beispiel.at“. Dann lese ich ihre robots.txt und sage dir "
                "je KI-Programm, ob es lesen darf.",
                "Tell me the website's address, for example: “Can AI read my website? example.com”. Then I'll read its robots.txt and tell you for "
                "each AI program whether it may read it.")
    try:
        (adresse_pruefen or wissen.nur_oeffentlich)("https://" + host + "/")
    except Exception:
        return (f"„{host}“ ist keine öffentliche Website, die ich prüfen kann. Schreib die Adresse so, wie sie im Browser steht, etwa beispiel.at.",
                f"“{host}” isn't a public website I can check. Write the address as it appears in your browser, for example example.com.")
    r = pruefen(host, oeffner=oeffner)
    if r["fehler"]:
        return (f"Die robots.txt von {host} ließ sich nicht lesen ({r['fehler']}). Nach dem Standard dafür gilt die Website dann für alle Programme als "
                "gesperrt, auch für KI. Prüf, ob die Website erreichbar ist und /robots.txt ohne Fehler antwortet.",
                f"The robots.txt of {host} couldn't be read. Under the standard for it, the site then counts as blocked for all programs, including AI. "
                "Check that the site is reachable and that /robots.txt answers without an error.")
    def liste(eintraege, gesperrt: bool, sprache: int) -> list[str]:
        return [(f"{e[1 + sprache]} ({e[0]})" if gesperrt else e[1 + sprache]) for e in eintraege if (not e[3]) == gesperrt]
    nein_a, nein_a_en, ja_a, ja_a_en = liste(r["antworten"], True, 0), liste(r["antworten"], True, 1), liste(r["antworten"], False, 0), liste(r["antworten"], False, 1)
    nein_t, nein_t_en, ja_t, ja_t_en = liste(r["training"], True, 0), liste(r["training"], True, 1), liste(r["training"], False, 0), liste(r["training"], False, 1)
    de = [f"Ich habe die robots.txt von {host} gelesen." + (" Es gibt keine, also dürfen alle Programme lesen." if r["ohne_robots"] else "")]
    en = [f"I read the robots.txt of {host}." + (" There isn't one, so every program may read the site." if r["ohne_robots"] else "")]
    if not nein_a:
        de.append("Die Website kann in KI-Antworten vorkommen: Alle Programme, die für eine Antwort nachschauen, dürfen lesen (ChatGPT, Claude, "
                  "Perplexity, Le Chat, KIplatz).")
        en.append("The site can appear in AI answers: every program that looks things up for an answer may read it (ChatGPT, Claude, Perplexity, "
                  "Le Chat, KIplatz).")
    else:
        de.append("Für Antworten gesperrt: " + "; ".join(nein_a) + ". Dort kann die Website in Antworten nicht vorkommen."
                  + (" Erlaubt: " + "; ".join(ja_a) + "." if ja_a else ""))
        en.append("Blocked for answers: " + "; ".join(nein_a_en) + ". The site can't appear in those answers." + (" Allowed: " + "; ".join(ja_a_en) + "." if ja_a_en else ""))
    if nein_t:
        de.append("Für das Training gesperrt: " + "; ".join(nein_t) + ". Das ändert nichts daran, ob die Website in Antworten vorkommt."
                  + (" Für das Training erlaubt: " + "; ".join(ja_t) + "." if ja_t else ""))
        en.append("Blocked for training: " + "; ".join(nein_t_en) + ". That doesn't change whether the site appears in answers."
                  + (" Allowed for training: " + "; ".join(ja_t_en) + "." if ja_t_en else ""))
    else:
        de.append("Auch alle Programme, die Stoff für ein Training sammeln, dürfen lesen. Wer das nicht will, sperrt sie in der robots.txt, etwa mit "
                  "„User-agent: GPTBot“ und „Disallow: /“; in Antworten kommt die Website trotzdem vor.")
        en.append("Every program that collects material for training may read it too. If you don't want that, block them in robots.txt, for example "
                  "with “User-agent: GPTBot” and “Disallow: /”; the site will still appear in answers.")
    if r["tdm"]:
        de.append("Dazu behält sich die Website in tdmrep.json Text- und Data-Mining vor.")
        en.append("The site also reserves text and data mining in tdmrep.json.")
    de.append("Geprüft ist die Startseite und nur die robots.txt. Ob der Server ein Programm trotzdem abweist, sieht man darin nicht.")
    en.append("This checks the home page and only the robots.txt. Whether the server still turns a program away doesn't show there.")
    return "\n\n".join(de), "\n\n".join(en)
