# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import app_core
import hausordnung
import skills

NAME = skills.MEINE_KI
BESCHREIBUNG = "So will ich, dass KIplatz antwortet (aus „Meine KI“)"
FREI_MAX = 300
SPRACHE_MAX = 40

BAUSTEINE = {
    "wofuer": [
        {"id": "programmieren", "titel": "Programmieren", "regeln": [
            "Code immer in einem Codeblock mit Angabe der Sprache.",
            "Nur Funktionen, Befehle und Bibliotheken nennen, die es wirklich gibt. Bist du nicht sicher, sag es und nenne die Stelle in der offiziellen Dokumentation, wo man nachsieht.",
            "Bei einer Fehlermeldung zuerst die Ursache in einem Satz, dann die Lösung.",
            "Nur den Teil des Codes ändern, um den es geht, und sagen, was geändert wurde."]},
        {"id": "web", "titel": "Web (HTML, CSS, JavaScript)", "regeln": [
            "Standards des Browsers vor fertigen Bibliotheken, außer ich frage nach einer.",
            "Bei CSS und JavaScript sagen, ob es in allen gängigen Browsern läuft, wenn das unsicher ist.",
            "Auf Barrierefreiheit achten (Beschriftungen, Kontrast, Bedienung mit der Tastatur)."]},
        {"id": "ki", "titel": "KI am eigenen PC", "regeln": [
            "Bei Modellen immer Größe, Speicherbedarf und Lizenz nennen, wenn sie bekannt sind.",
            "Unterscheiden, was am eigenen PC läuft und was einen Dienst im Netz braucht.",
            "Keine Zahlen zu Tempo oder Qualität erfinden; nur nennen, was gemessen oder veröffentlicht ist, mit Quelle."]},
        {"id": "linux", "titel": "Linux und Git", "regeln": [
            "Befehle einzeln in Codeblöcken, mit einem Satz, was jeder tut.",
            "Vor Befehlen, die etwas löschen oder überschreiben, deutlich warnen und einen sicheren Weg zuerst nennen.",
            "Sagen, für welche Verteilung oder Shell ein Befehl gilt, wenn es einen Unterschied macht."]},
        {"id": "schule", "titel": "Schule und Studium", "regeln": [
            "Erklären statt nur die Lösung hinschreiben; den Rechenweg zeigen.",
            "Fachbegriffe beim ersten Mal kurz erklären."]},
        {"id": "aemter", "titel": "Ämter und Briefe", "regeln": [
            "Für Österreich antworten, außer ich nenne ein anderes Land.",
            "Fristen und Zuständigkeiten nur mit Quelle nennen, sonst sagen, wo man nachfragt."]},
        {"id": "geld", "titel": "Haushalt und Geld", "regeln": [
            "Beträge und Rechnungen nachvollziehbar vorrechnen.",
            "Keine Anlageempfehlung; bei Steuer und Recht auf die zuständige Stelle verweisen."]},
        {"id": "kochen", "titel": "Kochen und Backen", "regeln": [
            "Zuerst die Zutaten mit Mengen, dann die Schritte nummeriert.",
            "Mengen und Zeiten nur nennen, wenn sie stimmen; sonst sagen, dass man sie prüfen soll."]},
        {"id": "garten", "titel": "Garten", "regeln": [
            "Für das Klima in Mitteleuropa antworten.",
            "Bei Mitteln gegen Schädlinge zuerst Wege ohne Gift nennen."]},
    ],
    "laenge": [
        {"id": "kurz", "titel": "kurz", "regel": "Antworte kurz und auf den Punkt. Das Ergebnis zuerst, Erklärung nur, wenn ich danach frage."},
        {"id": "ausfuehrlich", "titel": "ausführlich", "regel": "Antworte ausführlich und erkläre die Hintergründe."},
    ],
    "aufbau": [
        {"id": "schritte", "titel": "Schritt für Schritt", "regel": "Gliedere in nummerierte Schritte, wenn es um ein Vorgehen geht."},
        {"id": "text", "titel": "in ganzen Sätzen", "regel": "Schreib in ganzen Sätzen, ohne viele Aufzählungen."},
    ],
    "anrede": [
        {"id": "du", "titel": "Du", "regel": "Sprich mich mit Du an."},
        {"id": "sie", "titel": "Sie", "regel": "Sprich mich mit Sie an."},
    ],
    "niveau": [
        {"id": "einsteiger", "titel": "für Einsteiger", "regel": "Ich bin Einsteiger: einfache Wörter, Fachbegriffe kurz erklären."},
        {"id": "profi", "titel": "mit Fachwörtern", "regel": "Ich kenne mich aus: Fachwörter sind in Ordnung, Grundlagen kannst du weglassen."},
    ],
    "nie": [
        {"id": "vorschlaege", "titel": "keine ungefragten Vorschläge", "regel": "Keine Vorschläge oder Extras, um die ich nicht gebeten habe."},
        {"id": "einleitung", "titel": "keine langen Einleitungen", "regel": "Keine Einleitung und keine Zusammenfassung am Schluss."},
        {"id": "englisch", "titel": "kein Englisch außer im Code", "regel": "Kein Englisch, außer in Code und feststehenden Fachbegriffen."},
        {"id": "emojis", "titel": "keine Emojis", "regel": "Keine Emojis."},
    ],
}

QUELLEN = {
    "programmieren": "Python-Dokumentation (deutsch)",
    "web": "MDN Web Docs (deutsch): HTML, CSS, JavaScript",
    "ki": "Ollama-Dokumentation",
}


def _eins(feld: str, wert) -> dict | None:
    return next((b for b in BAUSTEINE[feld] if b["id"] == wert), None)


def _zeile(text, max_zeichen: int) -> str:
    return " ".join(str(text or "").split())[:max_zeichen]


def bereinigen(wahl: dict | None) -> dict:
    w = wahl if isinstance(wahl, dict) else {}
    ids = {f: [b["id"] for b in BAUSTEINE[f]] for f in BAUSTEINE}
    aus = {
        "wofuer": [x for x in ids["wofuer"] if x in (w.get("wofuer") or [])],
        "sprache": _zeile(w.get("sprache"), SPRACHE_MAX),
        "nie": [x for x in ids["nie"] if x in (w.get("nie") or [])],
        "frei": _zeile(w.get("frei"), FREI_MAX),
    }
    for f in ("laenge", "aufbau", "anrede", "niveau"):
        aus[f] = w.get(f) if w.get(f) in ids[f] else ""
    if "programmieren" not in aus["wofuer"]:
        aus["sprache"] = ""
    return aus


def leer(wahl: dict) -> bool:
    w = bereinigen(wahl)
    return not (w["wofuer"] or w["nie"] or w["frei"] or any(w[f] for f in ("laenge", "aufbau", "anrede", "niveau")))


def skill_text(wahl: dict) -> str:
    w = bereinigen(wahl)
    teile = ["# Meine KI"]
    if w["wofuer"]:
        titel = []
        for x in w["wofuer"]:
            t = _eins("wofuer", x)["titel"]
            titel.append(f"{t} ({w['sprache']})" if x == "programmieren" and w["sprache"] else t)
        teile.append("Ich nutze KIplatz vor allem für: " + ", ".join(titel) + ".")
    stil = [_eins(f, w[f])["regel"] for f in ("laenge", "aufbau", "anrede", "niveau") if w[f]]
    if stil:
        teile.append("So soll KIplatz antworten:\n" + "\n".join(f"- {r}" for r in stil))
    for x in w["wofuer"]:
        b = _eins("wofuer", x)
        kopf = f"{b['titel']} ({w['sprache']})" if x == "programmieren" and w["sprache"] else b["titel"]
        teile.append(f"## {kopf}\n" + "\n".join(f"- {r}" for r in b["regeln"]))
    if w["nie"]:
        teile.append("Bitte nie:\n" + "\n".join(f"- {_eins('nie', x)['regel']}" for x in w["nie"]))
    if w["frei"]:
        teile.append("Außerdem wichtig für mich: " + w["frei"])
    teile.append("Die Grundregeln gelten weiter: nichts erfinden, nachfragen statt raten.")
    return "\n\n".join(teile)


def als_skill(wahl: dict) -> skills.Skill:
    w = bereinigen(wahl)
    if leer(w):
        raise app_core.AppError("MEINE_KI_LEER", "tipp mindestens eine Antwort an")
    for t in (w["sprache"], w["frei"]):
        if t:
            b = hausordnung.pruefen(t)
            if not b.ok:
                raise app_core.AppError("HAUSORDNUNG", b.text)
    return skills.lesen(f"---\nname: {NAME}\ndescription: {BESCHREIBUNG}\n---\n\n{skill_text(w)}\n", quelle="meine-ki")


__all__ = ["NAME", "BESCHREIBUNG", "BAUSTEINE", "QUELLEN", "bereinigen", "leer", "skill_text", "als_skill"]
