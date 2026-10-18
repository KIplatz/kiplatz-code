# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_web
import belege

QUELLE = ("Vincent Kompany ist seit 2024 Trainer des FC Bayern München. Die Zugspitze ist mit 2962 m ü. NHN der höchste Gipfel. "
          "Bern ist die Bundesstadt der Schweiz. Wien hat 2.005.760 Einwohner und liegt an der Donau.")
FRAGE = "Wer trainiert Bayern und wie hoch ist die Zugspitze?"
HEUTE = date(2026, 9, 24)


def _quellen(text=QUELLE):
    return [{"nummer": 1, "titel": "Probe", "art": "seite", "text": text}]


def test_numbers_and_dates_in_no_source_are_found_rounding_with_rund_is_fair():
    b = belege.streng_pruefen("Kompany kam 2023 von Burnley. Die Zugspitze ist 2962 Meter hoch. Wien hat rund 2 Millionen Einwohner. "
                              "Wien hat 3 Millionen Einwohner. Es gibt 3 Wege dorthin. Er spielt am 25.09.2026.", QUELLE + "\n" + FRAGE)
    zahlen = {x.satz: x.zahlen for x in b if x.zahlen}
    assert zahlen == {"Kompany kam 2023 von Burnley.": ("2023",), "Wien hat 3 Millionen Einwohner.": ("3",), "Er spielt am 25.09.2026.": ("25.9.2026",)}


def test_only_abbreviations_and_odd_spellings_are_sure_names_every_other_capital_is_a_suspicion():
    assert belege.namen("Laut Plan fährt die ÖBB ab Linz mit dem Railjet.")[0] == ["ÖBB"]
    sicher, verdacht = belege.namen("Der Trainer des FC Bayern München ist Vincent Kompany.")
    assert sicher == ["FC"] and "Vincent Kompany" in verdacht and "Bayern München" in verdacht
    assert belege.namen("Faust wurde von Johann Wolfgang von Goethe geschrieben.")[1] == ["Johann Wolfgang von Goethe"]
    assert belege.namen("Wien liegt an der Donau.")[1] == ["Donau"]
    assert belege.name_belegt("Kompanys", {"kompany"}) and belege.name_belegt("Goethes", {"goethe"}) and not belege.name_belegt("Tuchel", {"kompany"})


def test_the_second_look_is_read_strictly_and_a_missing_line_counts_as_wort():
    assert belege.urteil_lesen("1 Wort\n2 Name\n3: Eigenname\n4 vielleicht", 3) == {1, 2}
    assert belege.urteil_lesen("", 2) == set() and belege.urteil_lesen("7 Name", 2) == set() and belege.urteil_lesen("1 nein", 1) == set()
    assert belege.pruefer_auftrag(["Thomas  Tuchel", "Vorgänger"]) == "Wörter:\n1. Thomas Tuchel\n2. Vorgänger"


def test_an_answer_from_sources_loses_the_invented_sentences_and_says_so():
    antwort = "Der Trainer des FC Bayern München ist Vincent Kompany. Kompany kam 2023 von Burnley. Die Zugspitze ist 2962 Meter hoch."
    t, notizen = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE)
    assert t == "Der Trainer des FC Bayern München ist Vincent Kompany. Die Zugspitze ist 2962 Meter hoch."
    assert notizen == ["1 Satz mit einer Zahl, einem Datum oder einem Namen, die in keiner Quelle stehen, vom Programm gestrichen."]


def test_a_suspicious_name_goes_only_when_the_second_look_agrees():
    antwort = "Vincent Kompany ist seit 2024 Trainer des FC Bayern München. Sein Vorgänger dort war Thomas Tuchel."
    gefragt = []

    def pruefer_nein(zusatz, woerter):
        gefragt.append((zusatz, list(woerter)))
        return {i for i, w in enumerate(woerter) if "Tuchel" in w}
    t, notizen = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=pruefer_nein)
    assert t == "Vincent Kompany ist seit 2024 Trainer des FC Bayern München." and "nach einem zweiten Blick des Modells" in notizen[0]
    assert gefragt[0][0] == QUELLE and gefragt[0][1] == ["Vorgänger", "Thomas Tuchel"]
    t, notizen = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=lambda z, s: set())
    assert t == antwort and notizen == []
    t, _ = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=None)
    assert t == antwort

    def kaputt(zusatz, saetze):
        raise app_core.AppError("KI_ANTWORT", "weg")
    assert app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=kaputt)[0] == antwort


def test_general_knowledge_writing_and_arithmetic_stay_as_the_model_wrote_them():
    t, notizen = app_web.belege_anwenden("Goethe schrieb den Faust. Er lebte von 1749 bis 1832.", "Wer schrieb Faust?", "", [], heute=HEUTE)
    assert t == "Goethe schrieb den Faust. Er lebte von 1749 bis 1832." and notizen == []
    brief = "Liebe Oma, zu deinem 90. Geburtstag wünsche ich dir alles Gute. Deine Anna"
    assert app_web.belege_anwenden(brief, "Schreib eine Karte für Oma", QUELLE, _quellen(), heute=HEUTE, schreiben=True)[0] == brief
    t, _ = app_web.belege_anwenden("OpenAI ist die Firma hinter ChatGPT. Sie wurde 2015 gegründet.", "Was ist OpenAI?", QUELLE, _quellen(), heute=HEUTE,
                                   pruefer=lambda z, s: set(range(len(s))))
    assert t == "OpenAI ist die Firma hinter ChatGPT."
    q = "Ich brauche 3 Tuben Silikon zu je 9,90 Euro. Was kostet das zusammen?"
    assert app_web.belege_anwenden("Das kostet zusammen 29,70 Euro.", q, "Silikon kostet 9,90 Euro.", _quellen("Silikon kostet 9,90 Euro."), heute=HEUTE)[0] == "Das kostet zusammen 29,70 Euro."


def test_when_nothing_is_left_the_model_answers_once_more_strictly():
    auftraege = []

    def nochmal(extra):
        auftraege.append(extra)
        return "Die Zugspitze ist 2962 Meter hoch."
    t, notizen = app_web.belege_anwenden("Die Zugspitze ist 2965 Meter hoch.", FRAGE, QUELLE, _quellen(), heute=HEUTE, nochmal=nochmal)
    assert t == "Die Zugspitze ist 2962 Meter hoch." and "neu geantwortet" in notizen[0]
    assert "Zahl, ein Datum oder einen Namen" in auftraege[0] and "2965" in auftraege[0]
    t, _ = app_web.belege_anwenden("Die Zugspitze ist 2965 Meter hoch.", FRAGE, QUELLE, _quellen(), heute=HEUTE, nochmal=lambda e: "Sie ist 3000 Meter hoch.")
    assert t == "Das weiß ich noch nicht."


def test_the_known_half_stays_when_an_invented_sentence_was_struck():
    vorher = "OpenAI ist die Firma hinter ChatGPT. Sie wurde 2015 gegründet. Open Claw kenne ich nicht."
    nachher = "OpenAI ist die Firma hinter ChatGPT. Open Claw kenne ich nicht."
    ls = {}
    assert app_web._weiss_nicht_anwenden(nachher, ls, gesucht=True, vorher=vorher) == nachher
    assert app_web._weiss_nicht_anwenden("Open Claw kenne ich nicht.", {}, gesucht=True, vorher=vorher) == app_web._GESUCHT_NICHTS_SATZ
