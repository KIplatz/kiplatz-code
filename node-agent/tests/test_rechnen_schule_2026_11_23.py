# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rechnen
import rechnen_schule


@pytest.mark.parametrize("frage,beginn", [
    ("Dividiere die Zahl durch 6 und du erhältst 22 Rest 2. Wie heißt die Zahl?", "Die Zahl ist 134."),
    ("Dividiere die Zahl durch 4 und du erhältst 16 Rest 1.", "Die Zahl ist 65."),
    ("Dividiere die Zahl durch 3 und du erhältst 37 Rest 1. Wie heißt die Zahl?", "Die Zahl ist 112."),
    ("Teile die Zahl durch 5 und du erhältst 9.", "Die Zahl ist 45."),
    ("Multipliziere die Zahl mit 7 und du erhältst 63. Wie heißt die Zahl?", "Die Zahl ist 9."),
    ("Addiere 25 zur Zahl und du erhältst 80.", "Die Zahl ist 55."),
])
def test_zahlenraetsel(frage, beginn):
    assert rechnen.loesen(frage).de.startswith(beginn)


def test_zahlenraetsel_mit_probe():
    de = rechnen.loesen("Dividiere die Zahl durch 6 und du erhältst 22 Rest 2. Wie heißt die Zahl?").de
    assert "6 · 22 = 132" in de and "132 + 2 = 134" in de and "Probe: 134 : 6 = 22 Rest 2." in de


def test_tiere_und_beine_kindgerecht():
    de = rechnen.loesen("Auf dem Hof gibt es Ziegen und Enten. Zusammen sind es 15 Tiere mit 42 Beinen. Wie viele sind es?").de
    assert de.startswith("Es sind 6 Ziegen und 9 Enten.")
    assert "Wären alle 15 Tiere Enten" in de and "x" not in de.replace("Ex", "")
    assert "Probe: 6 · 4 + 9 · 2 = 24 + 18 = 42 Beine." in de


def test_reihenfolge():
    de = rechnen.loesen("Mia, Selina, Nick und Elisa reiten mit den Pferden aus. Nick reitet vor Mia und hinter Elisa. Elisa reitet nicht als "
                        "Erste. In welcher Reihenfolge reiten die Kinder?").de
    assert de.startswith("Die Reihenfolge ist: Selina, Elisa, Nick und Mia.")


def test_reihenfolge_nicht_eindeutig_bleibt_beim_modell():
    assert rechnen_schule.loesen("Anna, Ben und Carla laufen. Anna läuft vor Ben. In welcher Reihenfolge laufen sie?") is None


@pytest.mark.parametrize("frage,teil", [
    ("Wo hat Flo Fehler gemacht? 319 : 3 = 105 R 4, gerechnet als 300 : 3 = 100 und 19 : 3 = 5 R 4.", "Der Rest 4 ist größer als 3"),
    ("Wo hat Flo Fehler gemacht? 259 : 3 = 66 R 1, 240 : 3 = 60, 19 : 3 = 6 R 1", "richtig ist 240 : 3 = 80"),
    ("Stimmt das? 649 : 8 = 81 R 1", "Das stimmt: 649 : 8 = 81 Rest 1."),
    ("Wo ist der Fehler? 446 : 6 = 74 R 3", "Richtig ist 446 : 6 = 74 Rest 2."),
])
def test_fehler_suchen(frage, teil):
    assert teil in rechnen.loesen(frage).de


@pytest.mark.parametrize("frage", [
    "Wie viele Einwohner hat Wien?",
    "Wie hoch ist der Großglockner?",
    "Wer ist Bundeskanzler von Österreich?",
    "Dividiere die Zahl durch 6 und du erhältst 22 Rest 7.",
    "Hühner und Hähne: 10 Tiere mit 20 Beinen.",
])
def test_gegenproben(frage):
    assert rechnen_schule.loesen(frage) is None


def test_fable_zu_23a():
    assert rechnen.loesen("Subtrahiere die Zahl von 100 und du erhältst 37.").de.startswith("Die Zahl ist 63.")
    assert rechnen.loesen("Ziehe die Zahl von 50 ab und du erhältst 20.").de.startswith("Die Zahl ist 30.")
    de = rechnen.loesen("Wo hat Flo Fehler gemacht? 17 : 5 = 3 R 2, 29 : 4 = 7 R 1, 50 : 6 = 8 R 3").de
    assert "17 : 5 = 3 Rest 2 stimmt." in de and "29 : 4 = 7 Rest 1 stimmt." in de and "50 : 6 = 8 Rest 3 stimmt nicht, richtig ist 8 Rest 2." in de
    assert rechnen_schule.loesen("Ziegen und Enten: 15 Tiere mit 42 Beinen. Schreib eine Geschichte dazu.") is None
    assert rechnen_schule.loesen("Ziegen, Schafe und Enten: Zusammen sind es 15 Tiere mit 42 Beinen. Wie viele sind es?") is None
    assert rechnen_schule.loesen("Mia, Selina, Nick und Elisa reiten aus. Nick reitet vor Mia und Selina reitet hinter Elisa. Elisa reitet nicht "
                                 "als Erste. In welcher Reihenfolge reiten sie?") is None
    assert rechnen_schule.loesen("Mia, Selina, Nick und Elisa reiten aus. Mia reitet weder vor Nick noch hinter Elisa. In welcher Reihenfolge "
                                 "reiten sie?") is None
    assert "Richtig ist 446 : 6 = 74 Rest 2." in rechnen.loesen("Wo ist der Fehler? 446 ÷ 6 = 74 r 3").de


@pytest.mark.parametrize("frage,beginn", [
    ("Suri hat 10 €. Sie kauft ein Geodreieck um 1,95 €. Wie viel Geld bleibt übrig?", "Es bleiben 8,05 € übrig."),
    ("Der Lehrer kauft in der Pause sechs Tüten mit Süßigkeiten. Jede Tüte kostet 99 ct. Wie viel kostet das?", "Das kostet zusammen 5,94 €."),
    ("In der Klasse 3b sind 29 Kinder. Der Theatereintritt kostet für jedes Kind 5 €. Wie viel kostet das insgesamt?", "Das kostet zusammen 145,00 €."),
    ("Familie Kliminski kauft jede Woche eine Grüne Kiste um 12 €. Wie viel bezahlt sie in einem ganzen Jahr?", "In einem Jahr sind das 624,00 €."),
    ("Bauer Heiko muss jeden Tag 14 Schubkarren holen. Wie viele Schubkarren sind das in einer Woche?", "In einer Woche sind das 98."),
    ("Auf dem Hof leben genau doppelt so viele Kühe wie Pferde. Zusammen sind es 27 Tiere. Wie viele sind es?", "Es sind 18 Kühe und 9 Pferde."),
    ("Die Summe aus zwei Zahlen ist 444. Die erste Zahl ist 240. Wie heißt die zweite Zahl?", "Die zweite Zahl ist 204."),
    ("Die Summe aus zwei Zahlen ist 666. Die erste Zahl ist das Doppelte der zweiten.", "Die erste Zahl ist 444, die zweite 222."),
    ("Halbiere die Summe aus 297 und 133.", "Das Ergebnis ist 215."),
    ("Kann das stimmen? Felix ist sieben Jahre und vier Wochen alt. Er ist also 215 Wochen alt.", "Nein, das stimmt nicht: 7 · 52 + 4 = 368 Wochen"),
])
def test_textaufgaben_23b(frage, beginn):
    assert rechnen.loesen(frage).de.startswith(beginn)


@pytest.mark.parametrize("frage", [
    "Ich habe jeden Tag 3 Termine. Wie viele Termine habe ich in einer Woche, wenn am Sonntag frei ist?",
    "Frau Sommer kauft zwei Brote für insgesamt 5 € und drei Stücke Käse für je 3 €. Wie viel zahlt sie?",
    "Wie viel kostet eine Woche Urlaub in Kroatien?",
])
def test_textaufgaben_bleiben_beim_modell(frage):
    assert rechnen_schule.loesen(frage) is None


@pytest.mark.parametrize("frage", [
    "Die Summe aus zwei Zahlen ist 100. Die erste Zahl ist 20 größer als die zweite.",
    "Halbiere 10 und 20.",
    "Suri hat 10 €. Sie kauft ein Geodreieck um 1,95 € und einen Stift um 0,80 €. Wie viel bleibt übrig?",
    "Suri hat 10 €. Sie kauft 3 Hefte um je 1,20 €. Wie viel bleibt übrig?",
    "Mama kauft 3 Semmeln und 2 Brezen. Jede Breze kostet 1,20 €. Wie viel kosten die Brezen?",
    "29 Kinder und 2 Lehrerinnen gehen ins Theater. Der Eintritt kostet für jede Person 5 €. Wie viel kostet das?",
    "Ich nehme dreimal am Tag 2 Tabletten. Wie viele sind das in einer Woche?",
    "Ich fahre jeden Tag 30 km. Wie viele km sind das in einer Woche mit 5 Arbeitstagen?",
    "Ich verdiene 15 € pro Stunde. Wie viel ist das in einem Tag?",
])
def test_fable_zu_23b_bleibt_beim_modell(frage):
    assert rechnen_schule.loesen(frage) is None


def test_zahlwort_nur_vor_hauptwort():
    assert rechnen_schule._zahlwoerter("elf und drei") == "elf und drei"
    assert rechnen_schule._zahlwoerter("kauft sechs Tüten") == "kauft 6 Tüten"


def test_alle_zwei_tage_und_textaufgabe_sucht_nicht():
    import belege
    frage = ("In den Sommerferien fährt Opa vom 24.6. bis zum 8.7. in den Urlaub. Pjotr und Luba sollen alle zwei Tage die Blumen gießen. "
             "Sie beginnen am 25.6. An wie vielen Tagen gießen sie die Blumen?")
    de = rechnen.loesen(frage).de
    assert de.startswith("An 7 Tagen: 25.6., 27.6., 29.6., 1.7., 3.7., 5.7., 7.7.")
    assert rechnen.loesen("Lena trainiert vom 1.7. bis 15.7. alle zwei Tage. Sie beginnt am 1.7. An wie vielen Tagen trainiert sie?").de.startswith(
        "An 8 Tagen: 1.7., 3.7., 5.7., 7.7., 9.7., 11.7., 13.7., 15.7.")
    assert rechnen_schule.loesen("Lena trainiert vom 1.7. bis 15.7. alle zwei Tage. An wie vielen Tagen trainiert sie?") is None
    for wissen in ("Mein Baby ist 10 Tage alt und trinkt 60 ml. Ist das genug?", "Darf ich Ibuprofen 400 alle 2 Tage nehmen?",
                   "An wie vielen Tagen regnet es in Wien?"):
        assert not belege.rechenaufgabe(wissen)
