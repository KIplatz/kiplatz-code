# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import time
from typing import Callable

import absicht
import pruefung
import rechnen

_EN = set("""the is are am be been what how why who whom whose where when which do does did can could would should will shall
i you he she we they my your his her our their me him us them a of on for to and with from about this that these those there here
it its please tell explain much many any some not no yes if than then because into over under between after before while
weather today tomorrow yesterday best good better thanks thank thx""".split())
_DE = set("""der das ist sind wie warum wer wo wann welche welcher welches ich du er sie wir ihr mein dein sein unser euer mich dich
mir dir uns euch ein eine einen einem einer und mit von für auf zu nicht kein keine bitte es gibt kann können soll sollte wird
werden hat habe haben den dem des noch auch schon nur sehr heute morgen gestern gut besser als oder aber weil dass wenn
bin hab hob zum zur im beim vom ned kaputt""".split())
_WORT = re.compile(r"[A-Za-zÄÖÜäöüß']+")
_EN_ANFANG = {"what", "what's", "how", "why", "who", "who's", "whom", "whose", "where", "where's", "when", "which", "is", "are", "do", "does", "did",
              "can", "could", "should", "would", "shall", "tell", "explain", "please", "give", "show", "the"}

SYSTEM_FRAGE = (
    "You translate English into German. Each input line starts with a number and a vertical bar, like 1| … "
    "Translate every line on its own, keep its number and bar: one line in, one line out. Never answer a question, only translate it. "
    "A line that is already German stays as it is. Keep names, numbers and units. "
    "German words or sentences in quotation marks are what the person asks about: copy them exactly, never translate them. Output only the lines.")
BEISPIEL_FRAGE = [
    {"role": "user", "content": "1| What is the minimum age for a moped licence in Italy?\n2| Give me a recipe for apple strudel.\n"
                                "3| Explain how a fridge works.\n4| Do I need a permit for a pond in my garden?\n5| What does 'Bim' mean?"},
    {"role": "assistant", "content": "1| Wie alt muss man in Italien für den Mopedführerschein mindestens sein?\n2| Gib mir ein Rezept für Apfelstrudel.\n"
                                     "3| Erkläre, wie ein Kühlschrank funktioniert.\n4| Brauche ich eine Genehmigung für einen Teich in meinem Garten?\n"
                                     "5| Was bedeutet 'Bim'?"},
]
SYSTEM_ANTWORT = (
    "You translate a German answer into natural English, the way a native English speaker would write it. "
    "The answer comes split into numbered lines, each starting with a number and a vertical bar, like 3| … "
    "Read all lines first so you understand the whole answer, then translate each line: keep its number and bar, one line in, one line out, "
    "never merge or split lines, never add or leave out anything. Translate the meaning, not word for word: use English word order and "
    "everyday English phrasing, never German sentence structure (write „The shops are closed on Sundays“, not „On Sundays are the shops closed“). "
    "Keep the value of every number, but write numbers and dates the English way (3,5 becomes 3.5, 1.200 becomes 1,200, 26. Oktober becomes "
    "26 October). Keep units, names, list dashes and marks like (Quelle 1) exactly as they are. "
    "The name of a shop, pharmacy, restaurant, street, place or organisation is a name: keep it whole and in German, "
    "also its words like Apotheke, Gasthaus or Straße. "
    "Never write in the first person about the topic (no „I descale“, „I recommend“); speak to the reader as „you“ or write impersonally. "
    "No Markdown, no asterisks. Output only the translated lines.")
BEISPIEL_ANTWORT = [
    {"role": "user", "content": "1| In Italien ist es üblich, den Espresso an der Bar im Stehen zu trinken (Quelle 1).\n"
                                "2| Am Tisch zahlst du dafür oft deutlich mehr.\n"
                                "3| Für einen Lieferwagen bis 3,5 t brauchst du in Österreich den Führerschein der Klasse B.\n"
                                "4| Der Nationalfeiertag in Österreich ist am 26. Oktober.\n"
                                "5| Was genau bei dir gilt, fragst du am besten direkt am Gemeindeamt nach.\n"
                                "6| - 250 ml Milch und 2 Eier verquirlen\n"
                                "7| Die Apotheke zum Hirschen in der Linzer Straße hat bis 18 Uhr offen.\n"
                                "8| Ob das heute noch so ist, steht in den Quellen nicht."},
    {"role": "assistant", "content": "1| In Italy, people usually drink their espresso standing at the bar (Quelle 1).\n"
                                     "2| If you sit at a table, you often pay quite a bit more.\n"
                                     "3| In Austria, you need a category B licence to drive a van up to 3.5 t.\n"
                                     "4| Austria's national holiday is on 26 October.\n"
                                     "5| It's best to ask your local council directly what applies to you.\n"
                                     "6| - Whisk 250 ml milk and 2 eggs\n"
                                     "7| Apotheke zum Hirschen on Linzer Straße is open until 6 pm.\n"
                                     "8| The sources don't say whether that's still the case today."},
]
SYSTEM_ANTWORT_DEUTSCH_GEFRAGT = SYSTEM_ANTWORT.replace(
    " Output only the translated lines.",
    " The reader asked for German words: the German wording that answers the question stays German, exactly as it is, in quotation marks; "
    "translate only the explanation around it. Output only the translated lines.")
_DEUTSCH_GEFRAGT = re.compile(r"\b(?:in|into) (?:Austrian )?German\b|\bGerman (?:word|term|phrase|expression)s? for\b|\bGerman for\b", re.I)
_BETONT = re.compile(r"(\*{1,2}|_{2})(?=\S)(.+?)(?<=\S)\1")
_ZEILE = re.compile(r"^\s*(\d+)\s*\|\s?(.*)$")
_ANFUEHRUNG_DE = re.compile(r"„([^„“”]*)[“”]")


def frage_sprache(text: str) -> str:
    import schriftstueck
    eigen, mit_anhang = schriftstueck.eigene_worte(text or "")
    if mit_anhang and eigen.strip():
        text = eigen
    gewuenscht = absicht.erkennen(text or "")
    if gewuenscht.art == "sprache":
        return gewuenscht.sprache
    ohne_zitat = re.sub(r"[„“\"'‚‘’][^„“\"'‚‘’]{1,60}[“\"'‘’]", " ", text or "")
    woerter = [w.lower() for w in _WORT.findall(ohne_zitat) if not re.search(r"[äöüßÄÖÜ]", w)]
    if rechnen.englisch_rechnung(text or ""):
        return "en"
    en = sum(1 for w in woerter if w in _EN)
    de = sum(1 for w in woerter if w in _DE)
    if woerter and woerter[0] in _EN_ANFANG and de == 0:
        return "en"
    if en >= 2 and en > 2 * de:
        return "en"
    if en == 1 and de == 0 and len(woerter) <= 4:
        return "en"
    return "de"


def letzte_frage(nachrichten: list[dict]) -> str:
    for n in reversed(nachrichten or []):
        if n.get("role") == "user":
            return str(n.get("content") or "")
    return ""


FrageFn = Callable[..., object]


VERLAUF_NACHRICHTEN = 6
VERLAUF_ZEICHEN = 600


def frage_auf_deutsch(frage_fn: FrageFn, nachrichten: list[dict]) -> list[dict]:
    neu = list(nachrichten)
    stellen = [i for i, n in enumerate(neu) if n.get("role") in ("user", "assistant") and str(n.get("content") or "").strip()]
    stellen = stellen[-VERLAUF_NACHRICHTEN:]
    if not stellen or neu[stellen[-1]].get("role") != "user":
        return nachrichten
    zeilen = []
    for i in stellen:
        t = " ".join(str(neu[i].get("content") or "").split())
        zeilen.append(t if i == stellen[-1] else t[:VERLAUF_ZEICHEN])
    fertig = zeilen_uebersetzen(frage_fn, zeilen, system=SYSTEM_FRAGE, beispiel=BEISPIEL_FRAGE)
    letzte = fertig.get(len(zeilen) - 1, "").strip()
    if not letzte or len(letzte) > 3 * len(zeilen[-1]) + 40:
        return nachrichten
    for j, i in enumerate(stellen):
        if fertig.get(j, "").strip():
            neu[i] = {**neu[i], "content": fertig[j].strip()}
    return neu


def _stellen(text: str, saetze: list[str]) -> list[tuple[int, int]] | None:
    aus, pos = [], 0
    for s in saetze:
        i = text.find(s, pos)
        if i < 0:
            return None
        aus.append((i, i + len(s)))
        pos = i + len(s)
    return aus


def zeilen_uebersetzen(frage_fn: FrageFn, zeilen: list[str], bei_zeile: Callable[[dict[int, str]], None] | None = None,
                       system: str = SYSTEM_ANTWORT, beispiel: list[dict] | None = None) -> dict[int, str]:
    if not zeilen:
        return {}
    eingabe = "\n".join(f"{i + 1}| {z}" for i, z in enumerate(zeilen))
    fertig: dict[int, str] = {}
    puffer = [""]

    def zeile_lesen(roh: str) -> None:
        m = _ZEILE.match(roh)
        if m and 1 <= int(m.group(1)) <= len(zeilen) and m.group(2).strip() and int(m.group(1)) - 1 not in fertig:
            z = m.group(2).strip()
            h = re.fullmatch(r"(\*{1,2}|_)([^*_]+)\1", z)
            fertig[int(m.group(1)) - 1] = _BETONT.sub(r"\2", h.group(2) if h else z).strip()

    def token(stueck: str) -> None:
        puffer[0] += stueck
        while "\n" in puffer[0]:
            roh, puffer[0] = puffer[0].split("\n", 1)
            vorher = len(fertig)
            zeile_lesen(roh)
            if bei_zeile is not None and len(fertig) != vorher:
                try:
                    bei_zeile(dict(fertig))
                except Exception:
                    pass

    laenge = sum(len(z) for z in zeilen)
    a = frage_fn(list(beispiel or []) + [{"role": "user", "content": eingabe}], system=system, max_tokens=min(1800, 60 + laenge // 2),
                 on_token=token)
    rest = puffer[0]
    if not fertig and getattr(a, "text", ""):
        rest = a.text
    for roh in rest.split("\n"):
        zeile_lesen(roh)
    return fertig


SYSTEM_CHAT = {
    "en": ("You translate short German chat messages into natural, casual English, the way people write in a chat. "
           "Each input line starts with a number and a vertical bar, like 1| … Keep the number and bar: one line in, one line out. "
           "Never answer a question or reply to a greeting, only translate it. Keep names, numbers and emoji. Output only the lines."),
    "de": ("You translate short English chat messages into natural, casual German, the way people write in a chat (du, not Sie). "
           "Each input line starts with a number and a vertical bar, like 1| … Keep the number and bar: one line in, one line out. "
           "Never answer a question or reply to a greeting, only translate it. Keep names, numbers and emoji. Output only the lines."),
}
BEISPIEL_CHAT = {
    "en": [{"role": "user", "content": "1| Servus, wie geht's dir heute?\n2| Wer kommt mit zum Brunnen?\n3| Was ist die Hauptstadt von Australien?"},
           {"role": "assistant", "content": "1| Hi, how are you today?\n2| Who's coming to the fountain with me?\n3| What's the capital of Australia?"}],
    "de": [{"role": "user", "content": "1| Hi everyone, I'm new here.\n2| Can you recommend a good movie?\n3| What time is it in Tokyo right now?"},
           {"role": "assistant", "content": "1| Hallo zusammen, ich bin neu hier.\n2| Kannst du mir einen guten Film empfehlen?\n3| Wie spät ist es gerade in Tokio?"}],
}


def chatzeile_uebersetzen(frage_fn: FrageFn, text: str, ziel: str) -> str:
    zeile = " ".join(str(text or "").split())
    if not zeile or ziel not in SYSTEM_CHAT:
        return ""
    a = frage_fn(list(BEISPIEL_CHAT[ziel]) + [{"role": "user", "content": f"1| {zeile}"}], system=SYSTEM_CHAT[ziel],
                 max_tokens=min(400, 40 + len(zeile)), temperature=0.1)
    for roh in str(getattr(a, "text", "") or "").split("\n"):
        m = _ZEILE.match(roh)
        if m and m.group(1) == "1" and m.group(2).strip():
            z = m.group(2).strip()
            return _BETONT.sub(r"\2", z).strip()
    return ""


def deutsch_gefragt(frage: str) -> bool:
    return bool(_DEUTSCH_GEFRAGT.search(frage or ""))


def antwort_uebersetzen(frage_fn: FrageFn, text: str, lieferschein: dict, teil_melden: Callable[[str], None] | None = None,
                        log: Callable[[str], None] | None = None, frage: str = "") -> tuple[str, dict]:
    t0 = time.time()
    system = SYSTEM_ANTWORT_DEUTSCH_GEFRAGT if deutsch_gefragt(frage) else SYSTEM_ANTWORT
    saetze = pruefung.saetze(text)
    stellen = _stellen(text, saetze)
    if stellen is None:
        saetze, stellen = [text.strip()], [(text.find(text.strip()), text.find(text.strip()) + len(text.strip()))]
    ls = dict(lieferschein or {})
    extra: list[str] = []
    zeilen = [s.replace("\n", " ") for s in saetze] + [ls[k].replace("\n", " ") for k in extra]

    def zusammensetzen(fertig: dict[int, str], nur_bis_luecke: bool) -> str:
        teile, pos = [], 0
        for i, (a, b) in enumerate(stellen):
            if i not in fertig and nur_bis_luecke:
                return "".join(teile)
            teile.append(text[pos:a])
            teile.append(fertig.get(i, text[a:b]))
            pos = b
        teile.append(text[pos:])
        return "".join(teile)

    def weitergeben(fertig: dict[int, str]) -> None:
        if teil_melden is not None:
            stueck = zusammensetzen(fertig, nur_bis_luecke=True).strip()
            if stueck:
                teil_melden(stueck)

    try:
        fertig = zeilen_uebersetzen(frage_fn, zeilen, weitergeben, system=system, beispiel=BEISPIEL_ANTWORT)
    except Exception as exc:
        if log:
            log(f"FEHLER uebersetzen: {type(exc).__name__}; die Antwort bleibt deutsch")
        return text, {**ls, "sprache": "de", "uebersetzt": "nicht möglich"}
    fehlt = [i for i in range(len(saetze)) if i not in fertig and re.search(r"[A-Za-zÄÖÜäöüß]{3}", zeilen[i])]
    if fehlt:
        try:
            nach = zeilen_uebersetzen(frage_fn, [zeilen[i] for i in fehlt], system=system, beispiel=BEISPIEL_ANTWORT)
            for j, i in enumerate(fehlt):
                if j in nach:
                    fertig[i] = nach[j]
            if log:
                log(f"OK uebersetzen: {len(fehlt)} ausgelassene Zeilen nachübersetzt, {sum(1 for j in range(len(fehlt)) if j in nach)} davon gelungen")
        except Exception as exc:
            if log:
                log(f"FEHLER uebersetzen nach: {type(exc).__name__}")
    fertig = {i: _ANFUEHRUNG_DE.sub(r"“\1”", z) for i, z in fertig.items()}
    neu = zusammensetzen(fertig, nur_bis_luecke=False)
    for j, k in enumerate(extra):
        if len(saetze) + j in fertig:
            ls[k] = fertig[len(saetze) + j]
    pr = ls.get("pruefung")
    if isinstance(pr, dict) and isinstance(pr.get("saetze"), list):
        nach = {pruefung.ohne_quellenmarke(s).strip(): pruefung.ohne_quellenmarke(fertig[i]).strip() for i, s in enumerate(saetze) if i in fertig}
        pr = {**pr, "saetze": [{**s, "text": nach.get(str(s.get("text", "")).strip(), s.get("text", ""))} if isinstance(s, dict) else s
                               for s in pr["saetze"]]}
        if isinstance(pr.get("text"), str) and "erfunden" in extra and len(saetze) + extra.index("erfunden") in fertig:
            pr["text"] = fertig[len(saetze) + extra.index("erfunden")]
        ls["pruefung"] = pr
    fehlen = len(saetze) - sum(1 for i in range(len(saetze)) if i in fertig)
    ls["sprache"] = "en"
    ls["uebersetzt_s"] = round(time.time() - t0, 2)
    if log:
        log(f"OK uebersetzt ins Englische in {ls['uebersetzt_s']} s, {len(saetze)} Sätze" + (f", {fehlen} blieben deutsch" if fehlen else ""))
    if teil_melden is not None:
        try:
            teil_melden(neu.strip())
        except Exception:
            pass
    return neu, ls
