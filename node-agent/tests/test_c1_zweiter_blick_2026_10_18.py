# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege

QUELLE = "Die Dichtung der Waschmaschine regelmäßig reinigen. Ein Ortungsgerät zeigt Leitungen in der Wand."
FRAGE = "Warum stinkt die Waschmaschine?"
HEUTE = date(2026, 10, 18)


def _quellen():
    return [{"nummer": 1, "titel": "Probe", "art": "seite", "text": QUELLE}]


def _modell(antwort_je_wort):
    auftraege = []

    def pruefer(zusatz, woerter):
        auftraege.append(belege.PRUEFER_SYSTEM + "\n\n" + belege.pruefer_auftrag(woerter))
        text = "\n".join(f"{i + 1} {antwort_je_wort(w)}" for i, w in enumerate(woerter))
        return belege.urteil_lesen(text, len(woerter))
    return pruefer, auftraege


def test_der_zweite_blick_fragt_je_wort_ob_es_ein_name_ist():
    assert "Liste von Wörtern" in belege.PRUEFER_SYSTEM and "Name oder Wort" in belege.PRUEFER_SYSTEM and "Wörterbuch" in belege.PRUEFER_SYSTEM
    assert "sonst nein" not in belege.PRUEFER_SYSTEM and "ja oder nein" not in belege.PRUEFER_SYSTEM


def test_gewoehnliche_woerter_bleiben_stehen_und_jedes_wort_kommt_einmal():
    antwort = ("Reinige die Dichtung der Waschmaschine regelmäßig. Einfach einen Eimer mit heißem Wasser und etwas Essig füllen. "
               "Danach den Eimer ausleeren und das Wasser wegschütten.")
    pruefer, auftraege = _modell(lambda w: "Wort")
    t, notizen = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=pruefer)
    assert t == antwort and notizen == []
    assert len(auftraege) == 1 and auftraege[0].endswith("Wörter:\n1. Eimer\n2. Wasser\n3. Essig")


def test_ein_erfundener_name_streicht_nur_seinen_satz():
    antwort = ("Reinige die Dichtung der Waschmaschine regelmäßig. Einfach einen Eimer mit heißem Wasser füllen. "
               "Am besten wirkt dafür Frischolin.")
    pruefer, _ = _modell(lambda w: "Eigenname" if w == "Frischolin" else "Wort")
    t, notizen = app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=pruefer)
    assert t == "Reinige die Dichtung der Waschmaschine regelmäßig. Einfach einen Eimer mit heißem Wasser füllen."
    assert "nach einem zweiten Blick des Modells" in notizen[-1]


def test_zeilen_je_wort_landen_nie_bei_einem_anderen_satz():
    assert belege.urteil_lesen("1 Wort\n2 Wort\n3 Name", 3) == {2}
    assert belege.urteil_lesen("1. Wort\n2. Name (Firma)\n3. Wort", 3) == {1}


def test_eine_unlesbare_antwort_streicht_nichts():
    antwort = "Reinige die Dichtung der Waschmaschine regelmäßig. Am besten wirkt dafür Frischolin."
    for text in ("", "1 vielleicht", "1 nein", "Frischolin ist ein Name.", "2 Name"):
        def pruefer(zusatz, woerter, text=text):
            return belege.urteil_lesen(text, len(woerter))
        assert app_web.belege_anwenden(antwort, FRAGE, QUELLE, _quellen(), heute=HEUTE, pruefer=pruefer)[0] == antwort
