# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

GEMACHT = "geprüft, ohne Modell"
WOHER = "Formprüfung des Programms (acht Angaben eines Arbeitsauftrags), ohne Modell und ohne Quelle."

_WUNSCH = re.compile(
    r"(?i)\b(?:prüf\w*|überprüf\w*|check\w*|bewert\w*|analysier\w*|beurteil\w*)\s+(?:\S+\s+){0,3}?(?:prompt\w*|anweisung)\b"
    r"|\bwas\s+fehlt\s+(?:\S+\s+){0,4}?(?:prompt\w*|anweisung)\b|\b(?:ist|wie\s+gut\s+ist)\s+(?:mein|dieser|der)\s+prompt\b|\bprompt[-\s]?(?:prüf\w*|check\w*)\b"
    r"|\b(?:check|review|rate|analy[sz]e|evaluate)\s+(?:\S+\s+){0,3}?prompt\b|\bwhat'?s\s+missing\s+(?:in|from)\s+(?:my|this|the)\s+prompt\b"
    r"|\bis\s+(?:my|this)\s+prompt\s+(?:good|ok|okay|clear)\b")
_ANGABEN = (
    ("rolle", r"\b(?:du\s+bist|sie\s+sind|ihr\s+seid|in\s+der\s+rolle|schlüpf\w*\s+in|versetz\w*\s+dich|als\s+(?:erfahrene|professionelle|\w+(?:in|er|ent|ant|ist|eur|or))\b"
              r"|you\s+are\s+an?|act\s+as|pretend\s+to\s+be|take\s+the\s+role|as\s+an?\s+(?:expert|experienced|professional))"),
    ("auftrag", r"\b(?:schreib\w*|erstell\w*|formulier\w*|verfass\w*|fass\w*|prüf\w*|analysier\w*|übersetz\w*|erklär\w*|vergleich\w*|beantworte\w*|entwirf|"
                r"entwerfe\w*|plan\w*|list\w*|nenn\w*|gib|mach\w*|korrigier\w*|überarbeit\w*|kürz\w*|gliedere?|ordne\w*|bewerte\w*|"
                r"write|create|draft|summari[sz]e|check|analy[sz]e|translate|explain|compare|answer|list|plan|rewrite|edit|review|give|make|outline)\b"),
    ("fuer_wen", r"\b(?:für\s+(?:meine?n?|unsere?n?|die|den|das|eine?n?|kunden|kinder|laien|anfänger\w*|schüler\w*|eltern|senioren|chef\w*|kolleg\w*|leser\w*|"
                 r"mitarbeit\w*|lehrer\w*|zielgruppe|\w+innen)|zielgruppe|leserschaft|empfänger\w*|adressat\w*|for\s+(?:my|our|a|an|the|beginners|kids|children|"
                 r"customers|readers|students|colleagues)|audience|target\s+group|readers?|an\s+(?:meine?n?|unsere?n?|den|die|das|eine?n?)\s+\w+|"
                 r"to\s+(?:my|our|the|a|an)\s+\w+)\b"),
    ("laenge", r"\b(?:\d+\s*(?:wörter|worte|wort|zeichen|sätze|satz|seiten|seite|absätze|absatz|zeilen|punkte|stichpunkte|minuten|words?|characters|sentences?|"
               r"pages?|paragraphs?|lines|bullets?|points)|kurz|kürzer|knapp|ausführlich|maximal|höchstens|mindestens|nicht\s+mehr\s+als|eine\s+seite|ein\s+absatz|"
               r"short|brief|concise|detailed|at\s+most|no\s+more\s+than|under\s+\d+|max\.?)\b"),
    ("form", r"\b(?:liste|aufzählung|stichpunkt\w*|tabelle|e-?mail|brief|absätze|überschrift\w*|fließtext|format\w*|markdown|json|gliederung|nummeriert\w*|"
             r"bullets?|table|list|letter|email|paragraphs|headings?|numbered|outline)\b"),
    ("grenzen", r"\b(?:nicht|keine?[nmrs]?|ohne|vermeide\w*|verzichte\w*|ausschließlich|nur|don'?t|do\s+not|avoid|without|never|only)\b"),
    ("ton", r"\b(?:sachlich\w*|freundlich\w*|förmlich\w*|locker\w*|höflich\w*|professionell\w*|humorvoll\w*|persönlich\w*|neutral\w*|ton|tonfall|duzen|siezen|"
            r"du-form|sie-form|einfache\s+sprache|leicht\s+verständlich|formal|informal|friendly|casual|tone|polite|professional|warm|plain\s+language|simple)\b"),
)
_NAME = {"rolle": ("Rolle", "Role"), "auftrag": ("Klarer Auftrag", "Clear task"), "fuer_wen": ("Für wen", "Audience"), "laenge": ("Länge", "Length"),
         "form": ("Form der Antwort", "Format"), "grenzen": ("Grenzen", "Limits"), "material": ("Material", "Material"), "ton": ("Ton", "Tone")}
_TIPP = {"rolle": ("sag, in welcher Rolle die KI schreiben soll, etwa „Du bist eine erfahrene Lehrerin“",
                   "say which role the AI should take, for example “You are an experienced teacher”"),
         "auftrag": ("beginne mit einem Tunwort, das genau sagt, was herauskommen soll: schreib, fasse zusammen, prüfe",
                     "start with a verb that says exactly what should come out: write, summarise, check"),
         "fuer_wen": ("nenne, wer das liest, etwa „für Kunden ohne Fachwissen“", "say who will read it, for example “for customers with no background”"),
         "laenge": ("sag, wie lang es werden soll, etwa „höchstens 150 Wörter“", "say how long it should be, for example “150 words at most”"),
         "form": ("sag, in welcher Form, etwa als E-Mail, als Liste oder als Tabelle", "say which format, for example an email, a list or a table"),
         "grenzen": ("sag, was nicht vorkommen soll, etwa „keine Fachbegriffe“", "say what to leave out, for example “no jargon”"),
         "material": ("gib das Material mit, um das es geht, ans Ende, nach einem Doppelpunkt", "add the material it is about at the end, after a colon"),
         "ton": ("sag, wie es klingen soll, etwa sachlich, freundlich oder per Sie", "say how it should sound, for example factual, friendly or formal")}
_DATEN = (("eine E-Mail-Adresse", "an email address", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
          ("eine Telefonnummer", "a phone number", r"(?:\+\d{2}|\b0)\s?\d{2,4}[\s/-]?\d{3,}[\s-]?\d{2,}"),
          ("eine Kontonummer (IBAN)", "a bank account number (IBAN)", r"\b[A-Z]{2}\d{2}(?:\s?\d{4}){3,}"),
          ("eine Sozialversicherungsnummer", "a social security number", r"\b\d{4}\s?(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])\d{2}\b"))


def gewuenscht(text: str) -> bool:
    return bool(_WUNSCH.search(str(text or "")))


def prompt_aus(text: str) -> str:
    t = str(text or "")
    m = _WUNSCH.search(t)
    rest = t[m.end():] if m else t
    teil = re.split(r":|\n", rest, maxsplit=1)
    if len(teil) == 2 and len(teil[1].split()) >= 3:
        return teil[1].strip()
    zitat = re.search(r"[„\"“»](.{12,}?)[“\"”«]", t, re.S)
    return zitat.group(1).strip() if zitat else ""


def _material(prompt: str) -> bool:
    if re.search(r"(?i)datei\s+„|\b(?:folgende[nrs]?|unten(?:stehende[nrs]?)?|hier\s+(?:ist|sind|der|die|das)|im\s+anhang|below|following|attached|here\s+is)\b", prompt):
        return True
    teile = re.split(r":\s*|\n\s*\n", prompt, maxsplit=1)
    return len(teile) == 2 and len(teile[1].split()) >= 20


def pruefen(prompt: str) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    da = [k for k, rx in _ANGABEN if re.search(rx, prompt, re.I)]
    if _material(prompt):
        da.append("material")
    reihenfolge = ["rolle", "auftrag", "fuer_wen", "form", "laenge", "grenzen", "material", "ton"]
    da = [k for k in reihenfolge if k in da]
    fehlt = [k for k in reihenfolge if k not in da]
    daten = [(de, en) for de, en, rx in _DATEN if re.search(rx, prompt)]
    return da, fehlt, daten


def antwort(nachricht: str) -> tuple[str, str] | None:
    if not gewuenscht(nachricht):
        return None
    prompt = prompt_aus(nachricht)
    if len(prompt.split()) < 3:
        return ("Füg den Prompt, den ich prüfen soll, nach einem Doppelpunkt ein, zum Beispiel: „Prüf meinen Prompt: Schreib eine E-Mail an …“. "
                "Dann sage ich dir, welche von acht Angaben ihm fehlen.",
                "Paste the prompt you want me to check after a colon, for example: “Check my prompt: Write an email to …”. "
                "Then I'll tell you which of eight details it is missing.")
    da, fehlt, daten = pruefen(prompt)
    de = [f"Dein Prompt hat {len(da)} von 8 Angaben, die einen Arbeitsauftrag an eine KI ausmachen."]
    en = [f"Your prompt has {len(da)} of the 8 details that make a clear task for an AI."]
    if da:
        de.append("Vorhanden: " + ", ".join(_NAME[k][0] for k in da) + ".")
        en.append("Present: " + ", ".join(_NAME[k][1] for k in da) + ".")
    if fehlt:
        de.append("Es fehlt:\n" + "\n".join(f"- {_NAME[k][0]}: {_TIPP[k][0]}" for k in fehlt))
        en.append("Missing:\n" + "\n".join(f"- {_NAME[k][1]}: {_TIPP[k][1]}" for k in fehlt))
    de.append("Die Reihenfolge, die am besten wirkt: Rolle und Auftrag, für wen und in welcher Form, wie lang, was nicht vorkommen soll, "
              "zum Schluss das Material.")
    en.append("The order that works best: role and task, who it's for and in what format, how long, what to leave out, and the material last.")
    if daten:
        de.append("Achtung, im Prompt steht " + " und ".join(d for d, _ in daten) + ". Das gehört nicht in eine Anweisung an eine KI; "
                  "ersetz es durch einen Platzhalter in eckigen Klammern, etwa [Nummer].")
        en.append("Careful: your prompt contains " + " and ".join(e for _, e in daten) + ". That doesn't belong in an instruction to an AI; "
                  "replace it with a placeholder in square brackets, such as [number].")
    de.append("Das ist eine Formprüfung: Sie zeigt, ob die Angaben da sind, nicht, ob der Auftrag inhaltlich das Richtige verlangt.")
    en.append("This checks the form only: it shows whether the details are there, not whether the task asks for the right thing.")
    return "\n\n".join(de), "\n\n".join(en)
