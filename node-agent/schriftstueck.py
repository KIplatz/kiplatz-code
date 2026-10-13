# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

VORSPANN = "Damit ich das gut machen kann, fehlen mir noch"
WEITER = re.compile(r"^\s*(weiter|egal|mach(e)? (es )?(so|einfach|trotzdem)|passt( so)?|ohne|keine (weiteren )?angaben|so ist es gut|schreib(e)? (es )?(jetzt|einfach|trotzdem))\s*[.!]?\s*$", re.I)

_ERZEUGEN = re.compile(r"\b(schreib\w*|erstell\w*|mach\w* mir|formulier\w*|entwirf\w*|verfass\w*|setz\w* auf|brauch\w* (einen|eine|ein)|bitte um (einen|eine|ein))\b", re.I)
_ARTEN: list[tuple[str, re.Pattern[str], list[str]]] = [
    ("Auftrag", re.compile(r"\b(auftrag|auftragsbest[äa]tigung|bestellung)\b", re.I),
     ["Wer den Auftrag erteilt (Name, Adresse)", "An wen er geht (Firma oder Person, Adresse)", "Datum und eine Auftragsnummer",
      "Jede Position mit Menge, Bezeichnung und Stückpreis (netto oder brutto?)", "Umsatzsteuersatz (20 %, 10 % oder ohne USt)",
      "Liefertermin oder Leistungszeitraum", "Zahlungsbedingung (zum Beispiel 14 Tage netto)"]),
    ("Rechnung", re.compile(r"\b(rechnung|honorarnote)\b", re.I),
     ["Aussteller (Name, Adresse, UID-Nummer, falls vorhanden)", "Empfänger (Name, Adresse)", "Rechnungsdatum, Rechnungsnummer und Leistungsdatum oder -zeitraum",
      "Jede Position mit Menge, Bezeichnung und Einzelpreis", "Umsatzsteuersatz oder Hinweis auf die Kleinunternehmerregelung (§ 6 Abs 1 Z 27 UStG)",
      "Zahlungsziel und Bankverbindung (IBAN)"]),
    ("Angebot", re.compile(r"\b(angebot|offert\w*)\b", re.I),
     ["Wer anbietet (Name, Adresse)", "An wen (Firma oder Person)", "Datum und Gültigkeit des Angebots", "Jede Position mit Menge, Bezeichnung und Einzelpreis",
      "Umsatzsteuersatz", "Lieferzeit und Zahlungsbedingung"]),
    ("Kostenvoranschlag", re.compile(r"\bkostenvoranschlag\b", re.I),
     ["Wer ihn erstellt (Name, Adresse)", "Für wen und für welches Vorhaben", "Datum und Gültigkeit", "Jede Position mit Menge, Bezeichnung und Einzelpreis",
      "Umsatzsteuersatz", "Ob er verbindlich ist oder unverbindlich (§ 1170a ABGB)"]),
    ("Lieferschein", re.compile(r"\blieferschein\b", re.I),
     ["Lieferant (Name, Adresse)", "Empfänger und Lieferadresse", "Datum und Lieferscheinnummer", "Jede Position mit Menge und Bezeichnung", "Bezug auf Auftrag oder Bestellung"]),
    ("Brief", re.compile(r"\b(brief|schreiben|k[üu]ndigung|beschwerde|mahnung|einladung|bewerbung|anschreiben)\b", re.I),
     ["Wer schreibt (Name, Adresse)", "An wen (Name, Adresse, Anrede: Du oder Sie)", "Worum es genau geht und was erreicht werden soll", "Datum und Betreff", "Wie lang und in welchem Ton"]),
    ("E-Mail", re.compile(r"\b(e-?mail|mail|nachricht)\b", re.I),
     ["An wen (Name, Anrede: Du oder Sie)", "Worum es geht und was die Person tun soll", "Betreff", "Wie lang und in welchem Ton", "Wer unterschreibt"]),
    ("Text", re.compile(r"\b(text|beitrag|artikel|beschreibung|zusammenfassung|rede|gedicht|geschichte|plan|konzept|liste)\b", re.I),
     ["Für wen der Text ist und wo er erscheint", "Worum es genau geht (Stichworte, Fakten, Zahlen)", "Wie lang", "Welcher Ton (sachlich, locker, feierlich)", "Was auf keinen Fall hinein soll"]),
]

_BETRAG = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_RECHENZEILE = re.compile(r"(?P<menge>\d+(?:[.,]\d+)?)\s*(?:stk\.?|stück|tuben?|m|kg|std\.?|h)?\s*(?:[×x*]|à|a)\s*(?P<preis>" + _BETRAG + r")\s*(?:€|eur|euro)?\s*=\s*(?P<summe>" + _BETRAG + r")\s*(?:€|eur|euro)?", re.I)
_SUMME_ZEILE = re.compile(r"^(?P<vor>\s*(?:summe|gesamt(?:summe|betrag)?|netto(?:summe|betrag)?|zwischensumme)\s*(?:\(netto\))?\s*:?\s*)(?P<betrag>" + _BETRAG + r")\s*(?:€|eur|euro)?\s*$", re.I | re.M)


_VORHABEN = re.compile(r"\b(plan\w*|empfiehl\w*|empfehl\w*|vergleich\w*|organisier\w*|hilf mir|bereite\w* (mir |uns )?(\w+ )?vor|entscheid\w*|was soll ich|welche[rsn]? (soll|passt|ist besser)|vorschl[aä]g\w*|tipps?)\b", re.I)
VORHABEN_PFLICHT = ("Für wen es ist (nur ich, Familie, Kinder, Kunden)", "Wofür genau und was dabei herauskommen soll",
                    "Bis wann, wie lang oder in welchem Rahmen (Zeit, Geld, Ort)", "Was schon feststeht und was auf keinen Fall sein soll")


@dataclass(frozen=True)
class Aufgabe:
    art: str
    pflicht: tuple[str, ...]
    offen: bool = False


_ANHANG_KOPF = re.compile(r"\n\s*(?:Datei „[^“\n]*“[^\n]*:\n|\[angehängt war:)")
_VORHANDEN = re.compile(r"\b(lies|liest|lese|lesen|auslesen|vorles\w*|abschreib\w*|abtipp\w*|hinschreib\w*|herausschreib\w*|rausschreib\w*|"
                        r"schreib\w*\s+(?:\S+\s+){0,5}?(?:hin|ab|heraus|raus|um|nieder|wieder)\b|übernimm|übernehm\w*|wiedergeb\w*|"
                        r"gib\s+(?:\S+\s+){0,5}?wieder\b|übersetz\w*|korrigier\w*|verbesser\w*|kürz\w*|fass\w*\s+(?:\S+\s+){0,6}?zusammen\b|"
                        r"was steht|steht (da|drin|darin|drauf|im|in|auf)\b|im (bild|foto|screenshot|anhang|dokument)|aus dem (bild|foto|screenshot|anhang|dokument)|"
                        r"diese[nrms]? (text|brief|mail|e-mail|nachricht|beitrag|artikel)|de[nm] (text|brief|beitrag|artikel) (im|aus|auf|in|vom|von))", re.I)
_NEU = re.compile(r"\b(einen|eine|ein|neuen|neue|neues)\s+(?:\S+\s+){0,2}?(auftrag|rechnung|angebot|kostenvoranschlag|lieferschein|brief|schreiben|"
                  r"e-?mail|mail|nachricht|text|beitrag|artikel|antwort)", re.I)


def eigene_worte(frage: str) -> tuple[str, bool]:
    t = frage or ""
    m = _ANHANG_KOPF.search("\n" + t)
    return (t[: max(0, m.start() - 1)] if m else t), m is not None


_WISSENSWORT = re.compile(r"\b(einwohner\w*|bevölkerung\w*|fläche\w*|höhe|länge|breite|tiefe|entfernung|abstand|preis\w*|kosten|kostet|temperatur\w*|"
                          r"gründung\w*|gegründet|geburt\w*|geboren|gestorben|hauptstadt|bip|bruttoinlands\w*|umsatz|gehalt|lohn|löhne|anzahl|zahl der|"
                          r"größe|gewicht|geschwindigkeit|einkommen|arbeitslos\w*|inflation\w*|währung|zeitzone|postleitzahl|vorwahl|alter von|wie alt)\b", re.I)
_PERSOENLICH = re.compile(r"\b(mir|mich|mein\w*|uns|unser\w*|ich|für (?:mich|uns|meine\w*|unsere\w*)|soll(?:te)? ich|sollen wir|welche[rsn]? (?:soll|passt|ist besser)|"
                          r"empfiehl\w*|empfehl\w*|plan\w*|organisier\w*|hilf|tipps?|vorschl[aä]g\w*|entscheid\w*|bereite)\b", re.I)


def _wissensfrage(f: str) -> bool:
    if re.search(r"\b(schreib|erstell|formulier|entwirf|verfass)", f, re.I):
        return False
    if _WISSENSWORT.search(f):
        return True
    return bool(re.search(r"\bvergleich\w*", f, re.I)) and not _PERSOENLICH.search(f)


def erkennen(frage: str) -> Aufgabe | None:
    worte, mit_anhang = eigene_worte(frage)
    f = " ".join(worte.split())
    if not f:
        return None
    if _ERZEUGEN.search(f):
        if re.match(r"^\s*(was|wer|wie|wann|wo|warum|welche\w*)\b", f, re.I) and "?" in f and not re.search(r"\b(schreib|erstell|formulier|entwirf|verfass)", f, re.I):
            return None
        if _VORHANDEN.search(f) and not _NEU.search(f):
            return None
        if mit_anhang and not _NEU.search(f):
            return None
        for art, muster, pflicht in _ARTEN:
            if muster.search(f):
                return Aufgabe(art, tuple(pflicht))
    if _VORHABEN.search(f) and not re.match(r"^\s*(was ist|was sind|was kostet|wer ist|wer hat|wie ?viel\w*|wie hoch|wie groß|wie lang\w*|wie weit|wie alt|wann|wo|woher|warum|wieso)\b", f, re.I) and len(f) < 600 and not _wissensfrage(f):
        return Aufgabe("Vorhaben", VORHABEN_PFLICHT, offen=True)
    return None


def vorspann_fragen(a: Aufgabe) -> str:
    liste = "\n".join(f"- {p}" for p in a.pflicht)
    if a.offen:
        return (f"Die Person bittet dich um ein Vorhaben (planen, empfehlen, vergleichen, entscheiden). Prüf zuerst still, ob dir etwas Entscheidendes fehlt:\n{liste}\n"
                f"Fehlt davon etwas, das deine Antwort wirklich ändern würde, dann antworte NUR so: erste Zeile „{VORSPANN}:“, dann höchstens zwei Zeilen mit einem "
                f"Gedankenstrich davor, je eine kurze Frage, zum Schluss der Satz „Antworte mir kurz, oder schreib „weiter“, dann mache ich es mit Annahmen.“ "
                f"Hat die Person schon genug gesagt oder ändert das Fehlende nichts, dann erledige das Vorhaben sofort und stell keine Frage.")
    return (f"Die Person will, dass du etwas schreibst: {a.art}. Schreib es JETZT NOCH NICHT. Erst kommt die Rückfrage, wie ein guter Mitarbeiter, "
            f"der nicht rät. Vergleiche, was die Person schon gesagt hat, mit dieser Liste der nötigen Angaben:\n{liste}\n"
            f"Antworte genau so: erste Zeile „{VORSPANN}:“, dann eine Zeile je fehlender Angabe mit einem Gedankenstrich davor, in der Reihenfolge der Liste, "
            f"nur die Punkte, die wirklich fehlen (was die Person genannt hat, fragst du nicht noch einmal). Zum Schluss ein Satz: "
            f"„Antworte mir Punkt für Punkt, oder schreib „weiter“, dann lasse ich Offenes als Strich zum Ausfüllen frei.“ Keine Einleitung, keine Erklärung, keine Höflichkeitsfloskel.")


def vorspann_schreiben(a: Aufgabe) -> str:
    if a.offen:
        return ("Jetzt erledigst du das Vorhaben mit allem, was die Person in diesem Gespräch gesagt hat. Was offen blieb, entscheidest du vernünftig und "
                "schreibst „Annahme:“ davor, damit die Person es sieht. Kein Markdown, keine Sternchen; kurze Absätze oder Zeilen mit einem Gedankenstrich.")
    return (f"Jetzt schreibst du den {a.art} fertig, mit allem, was die Person in diesem Gespräch gesagt hat. Was sie nicht beantwortet hat, bleibt als "
            f"Lücke mit einem Strich „________“ zum Ausfüllen, du erfindest nichts (keine Adressen, keine Nummern, keine Namen, kein Datum außer dem heutigen, wenn es passt). "
            f"Bei Positionen mit Menge und Preis schreibst du jede Zeile so: Menge × Einzelpreis = Summe, zum Beispiel „3 × 9,90 € = 29,70 €“, "
            f"darunter „Summe (netto): …“. Hat die Person den Umsatzsteuersatz genannt, folgt die Umsatzsteuer als eigene Zeile und dann „Gesamt: …“; hat sie ihn nicht genannt, "
            f"schreibst du „Umsatzsteuer: ________“ und „Gesamt: ________“ und rechnest keine Steuer aus (nichts erfinden, auch keine 20 %). Zahlen mit Komma und €. "
            f"Kein Markdown, keine Sternchen, keine Tabellen; schlichte Zeilen, wie ein Formular auf Papier. Keine Erklärung davor, kein Satz danach, keine Frage am Ende.")


_FRAGEZEILE = re.compile(r"^\s*[-–•]\s*.+|\?\s*$", re.M)


def ist_rueckfrage(text: str) -> bool:
    zeilen = [z for z in (text or "").strip().splitlines() if z.strip()]
    if not zeilen:
        return False
    rest = zeilen[1:] if zeilen[0].strip().rstrip(":").rstrip().lower() == VORSPANN.lower() else zeilen
    if not rest:
        return False
    fragen = sum(1 for z in rest if _FRAGEZEILE.search(z) or z.rstrip().endswith("?"))
    return fragen >= max(1, len(rest) // 2) and not any(len(z) > 200 for z in rest)


def antwort_bereinigen(text: str) -> str:
    zeilen = (text or "").strip().splitlines()
    if zeilen and zeilen[0].strip().rstrip(":").rstrip().lower() == VORSPANN.lower():
        return "\n".join(zeilen[1:]).strip()
    return (text or "").strip()


def runde(nachrichten: list[dict]) -> tuple[Aufgabe, str] | None:
    if not nachrichten:
        return None
    letzte = nachrichten[-1]
    if letzte.get("role") != "user":
        return None
    vorher = [n for n in nachrichten[:-1]]
    if len(vorher) >= 2 and vorher[-1].get("role") == "assistant" and str(vorher[-1].get("content", "")).startswith(VORSPANN):
        auftrag = next((str(n.get("content", "")) for n in reversed(vorher) if n.get("role") == "user"), "")
        a = erkennen(auftrag)
        if a is not None:
            return a, "schreiben"
    a = erkennen(str(letzte.get("content", "")))
    return (a, "fragen") if a is not None else None


def _zahl(s: str) -> float:
    s = s.strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) == 3:
        s = s.replace(".", "")
    return float(s)


def _geld(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def rechnung_pruefen(text: str) -> tuple[str, list[str]]:
    korrekturen: list[str] = []
    summen: list[float] = []

    def ersetzen(m: re.Match) -> str:
        try:
            menge, preis, summe = _zahl(m.group("menge")), _zahl(m.group("preis")), _zahl(m.group("summe"))
        except ValueError:
            return m.group(0)
        richtig = round(menge * preis, 2)
        summen.append(richtig)
        if abs(richtig - summe) < 0.005:
            return m.group(0)
        korrekturen.append(f"{m.group('menge')} × {m.group('preis')} € ist {_geld(richtig)}, nicht {_geld(summe)}; berichtigt.")
        return m.group(0)[: m.start("summe") - m.start()] + _geld(richtig).replace(" €", "") + m.group(0)[m.end("summe") - m.start():]

    neu = _RECHENZEILE.sub(ersetzen, text or "")
    if summen:
        gesamt = round(sum(summen), 2)

        def summe_ersetzen(m: re.Match) -> str:
            try:
                betrag = _zahl(m.group("betrag"))
            except ValueError:
                return m.group(0)
            kopf = m.group("vor").lower()
            if "netto" not in kopf and "zwischen" not in kopf and not kopf.strip().startswith("summe"):
                return m.group(0)
            if abs(betrag - gesamt) < 0.005:
                return m.group(0)
            korrekturen.append(f"Die Summe der Positionen ist {_geld(gesamt)}, nicht {_geld(betrag)}; berichtigt.")
            return m.group("vor") + _geld(gesamt)

        neu = _SUMME_ZEILE.sub(summe_ersetzen, neu, count=1)
    return neu, korrekturen


__all__ = ["Aufgabe", "erkennen", "runde", "vorspann_fragen", "vorspann_schreiben", "rechnung_pruefen", "ist_rueckfrage", "antwort_bereinigen", "VORSPANN", "WEITER"]
