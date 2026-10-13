# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schriftstueck as s


def test_recognises_document_tasks_but_not_questions():
    a = s.erkennen("Mach mir einen Auftrag mit meinem Namen an die Firma Huber in Gmunden, 3 Tuben Silikon zu je 9,90.")
    assert a is not None and a.art == "Auftrag" and any("Stückpreis" in p for p in a.pflicht)
    assert s.erkennen("Schreib mir eine Rechnung an Max Huber").art == "Rechnung"
    assert s.erkennen("Erstell mir bitte ein Angebot für eine Gartenmauer").art == "Angebot"
    assert s.erkennen("Schreib mir einen Brief an die Gemeinde").art == "Brief"
    assert s.erkennen("Formulier mir eine E-Mail an meinen Chef").art == "E-Mail"
    assert s.erkennen("Schreib mir einen Text über den Holocaust").art == "Text"
    for frage in ("Was ist ein Auftrag?", "Wie wird das Wetter morgen in Linz?", "Wer ist Bundeskanzler?", "3 × 9,90, was kostet das?", ""):
        assert s.erkennen(frage) is None, frage


def test_reading_or_reworking_an_existing_text_is_no_new_document():
    anhang = "\n\nDatei „IMG_8635.png“ (Foto, Text erkannt):\nDie Feuerwehren Gmunden und Altmünster wurden zu einem Verkehrsunfall alarmiert. Bericht, Text, Brief."
    for f in ("Lies den Text und schreib ihn mir hin", "Test, Test, Test, Test, das ist ein Test. Lies den Text im Bild und schreib ihn mir hin.",
              "Schreib mir den Text aus dem Foto ab", "Was steht im Bild? Schreib es mir auf", "Übersetze den Text ins Englische und schreib ihn mir",
              "Fasse den Text zusammen und schreib mir drei Sätze", "Schreib den Brief um, freundlicher", "Verbessere diesen Brief und schreib ihn neu hin"):
        assert s.erkennen(f) is None, f
        assert s.erkennen(f + anhang) is None, f + " (mit Anhang)"
    assert s.erkennen("Schreib mir das schön" + anhang) is None
    assert s.eigene_worte("Frage" + anhang) == ("Frage", True) and s.eigene_worte("Frage") == ("Frage", False)
    assert s.erkennen("Schreib mir einen Brief an die Zeitung, lesen soll ihn der Chefredakteur").art == "Brief"
    assert s.erkennen("Schreib mir eine Antwort auf diesen Brief" + anhang).art == "Brief"
    assert s.erkennen("Schreib mir wieder einen Brief an die Gemeinde").art == "Brief"


def test_two_rounds_questions_then_document():
    n = [{"role": "user", "content": "Mach mir einen Auftrag an Firma Huber, 3 Tuben Silikon zu je 9,90."}]
    a, runde = s.runde(n)
    assert a.art == "Auftrag" and runde == "fragen"
    assert s.VORSPANN in s.vorspann_fragen(a) and "JETZT NOCH NICHT" in s.vorspann_fragen(a)
    n += [{"role": "assistant", "content": s.VORSPANN + ":\n- Wer den Auftrag erteilt\n- Datum"}, {"role": "user", "content": "weiter"}]
    a2, runde2 = s.runde(n)
    assert a2.art == "Auftrag" and runde2 == "schreiben" and "________" in s.vorspann_schreiben(a2)
    n += [{"role": "assistant", "content": "Auftrag …"}, {"role": "user", "content": "Wie wird das Wetter morgen in Linz?"}]
    assert s.runde(n) is None
    assert s.runde([]) is None and s.runde([{"role": "assistant", "content": "x"}]) is None


def test_price_lines_and_total_are_recalculated():
    text = ("Auftrag Nr. ________\n3 × 9,90 € = 27,90 €\n2 × 15,00 € = 30,00 €\nSumme (netto): 57,90 €\nUSt 20 %: 11,58 €\nGesamt: 69,48 €")
    neu, k = s.rechnung_pruefen(text)
    assert "3 × 9,90 € = 29,70 €" in neu and "2 × 15,00 € = 30,00 €" in neu and "Summe (netto): 59,70 €" in neu
    assert len(k) == 2 and "29,70 €" in k[0] and "59,70 €" in k[1]
    assert s.rechnung_pruefen("3 x 9.90 = 29.70\nSumme: 29,70 €")[1] == []
    assert s.rechnung_pruefen("Ein Brief ohne Zahlen.") == ("Ein Brief ohne Zahlen.", [])
    neu2, k2 = s.rechnung_pruefen("2 × 1.500,00 € = 3.000,00 €\nSumme: 3.000,00 €")
    assert k2 == [] and neu2.endswith("3.000,00 €")


def test_zahlenfrage_mit_vergleiche_ist_kein_vorhaben_und_eine_fertige_antwort_bekommt_keinen_vorspann():
    import app_web
    assert s.erkennen("Wieviele Einwohner hat Salzburg und München vergleiche") is None
    assert s.erkennen("Wie viele Einwohner hat Salzburg im Vergleich zu München?") is None
    assert s.erkennen("Was kostet ein Vergleich beim Notar") is None
    a = s.erkennen("Vergleiche mir zwei Handys für meine Tochter und empfiehl eines")
    assert a is not None and a.offen
    fertig = f"{s.VORSPANN}:\nSalzburg hat 151.500 Einwohner (Stand 2025).\nMünchen hat 1.543.000 Einwohner (Stand 2025)."
    assert not s.ist_rueckfrage(fertig)
    assert s.antwort_bereinigen(fertig).startswith("Salzburg hat")
    frage = f"{s.VORSPANN}:\n- Für wen ist das Handy?\n- Wie viel darf es kosten?\nAntworte mir kurz, oder schreib „weiter“."
    assert s.ist_rueckfrage(frage)
    ls = {}
    text, gemacht = app_web._schriftstueck_nachbearbeiten(fertig, "fragen", ls, a)
    assert gemacht == "geantwortet" and text.startswith("Salzburg hat") and "pruefung" not in ls
    text, gemacht = app_web._schriftstueck_nachbearbeiten(frage, "fragen", ls, a)
    assert gemacht == "nachgefragt" and text.startswith(s.VORSPANN) and "pruefung" in ls
    text, gemacht = app_web._schriftstueck_nachbearbeiten("Nimm das günstigere, es reicht für die Schule.", "fragen", {}, a)
    assert gemacht == "geantwortet" and text.startswith("Nimm")
    r = s.erkennen("Schreib mir eine Rechnung")
    text, gemacht = app_web._schriftstueck_nachbearbeiten("Rechnung Nr. 1 …", "fragen", {}, r)
    assert gemacht == "nachgefragt" and text.startswith(s.VORSPANN)
