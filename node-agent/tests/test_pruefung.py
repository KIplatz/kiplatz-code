# SPDX-License-Identifier: AGPL-3.0-or-later
import pruefung as p

AUSZUEGE = [
    (1, "Auf beispiel.at stehen Anleitungen, wie man KI im Alltag nutzt: Werkzeuge, Vergleiche und tägliche News. Die Seite gehört zu einem Betrieb in Oberösterreich."),
    (2, "Der Stand-PC hat eine Radeon RX 7800 XT mit 16 GB Grafikspeicher und rechnet für die Community."),
]


def test_sentences_and_named_sources():
    assert p.saetze("Erster Satz. Zweiter Satz! Dritter?\n- Zeile eins\n- Zeile zwei") == ["Erster Satz.", "Zweiter Satz!", "Dritter?", "- Zeile eins", "- Zeile zwei"]
    assert p.genannte_quellen("Das steht so drin (Quelle 1 und 3).") == (1, 3)
    assert p.genannte_quellen("Quellen 2, 4") == (2, 4) and p.genannte_quellen("ohne") == ()
    assert p.saetze("Erster Satz. (Quelle 1) Zweiter Satz.") == ["Erster Satz. (Quelle 1)", "Zweiter Satz."]


def test_green_yellow_red_and_contradiction():
    antwort = ("Auf beispiel.at stehen Anleitungen, wie man KI im Alltag nutzt, mit Werkzeugen und täglichen News (Quelle 1). "
               "Der Betrieb aus Oberösterreich verkauft vermutlich auch Schulungen an Firmen. "
               "Die Website wurde 1998 von einem Konzern aus Berlin gegründet. "
               "Der Konzern besitzt außerdem eine Bank in Zürich (Quelle 2).")
    r = p.pruefen(antwort, AUSZUEGE)
    farben = [s.farbe for s in r.saetze]
    assert farben == ["gruen", "gelb", "rot", "rot"], farben
    assert r.saetze[0].quelle == 1 and r.saetze[0].genannt == (1,)
    assert r.saetze[3].widerspruch and not r.saetze[2].widerspruch
    assert r.gruen == 1 and r.gelb == 1 and r.rot == 2 and r.widersprueche == 1
    assert r.text.startswith("4 Sätze: 1 aus Quellen, 1 Schlussfolgerungen, 2 ohne Quelle.") and "Widerspruch" in r.text and "keine Wahrheitsprüfung" in r.text
    d = r.kurz()
    assert d["saetze"][0]["farbe"] == "gruen" and d["rot"] == 2


def test_numbers_and_word_stems_count_the_weather_answer_from_17_09(tmp_path=None):
    passage = [(1, "Wettervorhersage für Linz (Österreich), nachgeschaut bei Open-Meteo am 17.09.2026 um 20:10 UTC:\n"
                   "Morgen, Freitag 18.09.2026: Nebel, Höchsttemperatur 21 °C, Tiefsttemperatur 11 °C, kein Regen (Regenwahrscheinlichkeit 0 %), Wind bis 8 km/h.")]
    antwort = ("Morgen, Freitag 18.09.2026, ist in Linz mit Nebel zu rechnen. Die Höchsttemperatur beträgt 21 °C, die Tiefsttemperatur 11 °C. "
               "Es regnet nicht, und die Windgeschwindigkeit bleibt bei maximal 8 km/h. (Quelle 1)")
    r = p.pruefen(antwort, passage)
    farben = [s.farbe for s in r.saetze]
    assert farben[0] == "gruen" and farben[1] == "gruen" and farben[2] in ("gruen", "gelb"), farben
    assert r.rot == 0 and r.widersprueche == 0
    r2 = p.pruefen("Die Höchsttemperatur beträgt 35 °C, die Tiefsttemperatur 2 °C.", passage)
    assert r2.saetze[0].deckung < 0.6


def test_without_passages_everything_is_red_and_short_sentences_are_undecided():
    r = p.pruefen("Der Chef heißt Thomas Zweitling (Quelle N).", AUSZUEGE)
    assert r.saetze[0].farbe == "rot" and r.saetze[0].widerspruch and r.saetze[0].genannt == ()
    r = p.pruefen("Canberra ist die Hauptstadt von Australien. Ja.", [])
    assert [s.farbe for s in r.saetze] == ["rot", "unbestimmt"] and "alle ohne Quelle" in r.text
    r = p.pruefen("Ja.", AUSZUEGE)
    assert r.saetze[0].farbe == "unbestimmt" and "zu kurz" in r.text
    assert p.pruefen("", AUSZUEGE).text == "keine Sätze"


def test_quellenmarke_verschwindet_fuer_den_leser():
    assert p.ohne_quellenmarke("Offen ist Montag bis Freitag von 10 bis 20 Uhr (Quelle 5). Samstag länger [Quellen 2, 3].") ==         "Offen ist Montag bis Freitag von 10 bis 20 Uhr. Samstag länger."
    assert p.ohne_quellenmarke("Laut Quelle 1 regnet es.") == "Laut Quelle 1 regnet es."
    r = p.pruefen("Es regnet morgen in Linz (Quelle 1).", [(1, "Morgen regnet es in Linz bei 12 Grad.")])
    assert r.saetze[0].genannt == (1,) and r.saetze[0].kurz()["text"] == "Es regnet morgen in Linz."


def test_nach_abkuerzungen_endet_kein_satz():
    import belege
    assert p.saetze("Ich versuche es (z. B. wo Zutaten enden)? Das geht. Er fährt z. B. Rad. Dann kam Peter B. Huber.") == [
        "Ich versuche es (z. B. wo Zutaten enden)?", "Das geht.", "Er fährt z. B. Rad.", "Dann kam Peter B. Huber."]
    assert p.saetze("Er wohnt in der Str. Nr. 5 seit ca. 2010. Das ist d. h. gut. Am 3. Juni kam Dr. Huber. Ende.") == [
        "Er wohnt in der Str. Nr. 5 seit ca. 2010.", "Das ist d. h. gut.", "Am 3. Juni kam Dr. Huber.", "Ende."]
    assert belege._saetze("Er fährt z. B. Rad. Dann geht er heim.") == ["Er fährt z. B. Rad.", "Dann geht er heim."]
