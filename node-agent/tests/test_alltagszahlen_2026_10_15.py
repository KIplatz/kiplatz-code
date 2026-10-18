# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege


@pytest.mark.parametrize("frage", [
    "Wie viele Zentimeter sind 2 Meter 30?",
    "Wie viele Jahre liegen zwischen 1985 und 2026?",
    "Was sind 1.200 Euro netto plus 20 Prozent Mehrwertsteuer?",
    "Was kostet eine Fahrt von 350 Kilometern bei 7 Litern auf 100 Kilometer und 1,60 Euro je Liter?",
    "What is a 15 percent tip on 48 euros?",
    "How many centimetres are 2 metres 30?",
    "How much interest do 10,000 euros earn at 3 percent in one year?",
    "3 Tuben zu je 9,90 Euro",
])
def test_rechenfragen_werden_erkannt(frage):
    assert belege.rechnet(frage)


@pytest.mark.parametrize("frage", [
    "Wie hoch ist die Inflation 2025 in %?",
    "Wie viele Einwohner hat Wien?",
    "Wie viele Einwohner hatte Wien 2020?",
    "Wie hoch sind die Zinsen der EZB 2026?",
    "Wie lange muss ich eine Tiefkühlpizza backen?",
])
def test_fragen_nach_tatsachen_bleiben_streng(frage):
    assert not belege.rechnet(frage)


def test_ein_alltagsmass_ohne_widerspruch_in_den_quellen_bleibt():
    satz = "Die Backzeit liegt meist zwischen 15 und 25 Minuten bei 180 bis 220 Grad im vorgeheizten Backofen."
    assert belege.alltag_ohne_widerspruch(satz, "Tiefkühlpizza ist ein Fertiggericht. Sie wird im Backofen gebacken.")
    assert not belege.alltag_ohne_widerspruch(satz, "Auf der Packung: 12 Minuten bei 220 °C backen.")
    assert belege.alltag_ohne_widerspruch("Gekochter Reis hält im Kühlschrank 3 bis 4 Tage.", "Reis ist ein Getreide.")


@pytest.mark.parametrize("satz", [
    "Die Vignette kostet 2026 genau 103,80 Euro.",
    "Wien hat 2.005.760 Einwohner.",
    "Die Sachertorte wurde 1832 erfunden.",
    "Am 14.10.2026 sank der Preis um 12 Minuten.",
    "Das iPhone17 ist 15 cm hoch.",
    "Die Inflation lag bei 4,1 Prozent.",
])
def test_was_eine_quelle_braucht_bleibt_streng(satz):
    assert not belege.alltag_ohne_widerspruch(satz, "Ein Text ohne passende Zahlen.")


def test_die_pruefung_streicht_die_richtige_pizza_antwort_nicht_mehr():
    text = ("Die Backzeit für eine Tiefkühlpizza hängt vom Modell und den Herstellerangaben ab, liegt aber meist zwischen 15 und 25 Minuten "
            "bei 180 bis 220 Grad im vorgeheizten Backofen.")
    quelle = "Tiefkühlpizza: Fertiggericht aus dem Tiefkühlfach. Die Zubereitung steht auf der Verpackung."
    quellen = [{"nummer": 1, "art": "nachgeschaut", "titel": "Tiefkühlpizza", "adresse": "https://beispiel.at/pizza", "text": quelle}]
    neu, notizen = app_web.belege_anwenden(text, "Wie lange muss ich eine Tiefkühlpizza backen?", quelle, quellen, heute=date(2026, 10, 15))
    assert "15 und 25 Minuten" in neu and not any("gestrichen" in n for n in notizen)
    quelle2 = "Auf der Packung steht: 12 Minuten bei 220 Grad backen."
    quellen2 = [{**quellen[0], "text": quelle2}]
    neu2, _ = app_web.belege_anwenden(text, "Wie lange muss ich eine Tiefkühlpizza backen?", quelle2, quellen2, heute=date(2026, 10, 15))
    assert "15 und 25 Minuten" not in neu2


def test_rechenergebnisse_bleiben_stehen():
    quelle = "Der Zentimeter ist eine Längeneinheit. Ein Meter hat hundert Zentimeter."
    quellen = [{"nummer": 1, "art": "wikipedia", "titel": "Zentimeter", "adresse": "https://de.wikipedia.org/wiki/Zentimeter", "text": quelle}]
    neu, _ = app_web.belege_anwenden("2 Meter 30 sind 230 Zentimeter.", "Wie viele Zentimeter sind 2 Meter 30?", quelle, quellen,
                                     heute=date(2026, 10, 15))
    assert "230 Zentimeter" in neu


def test_ein_satz_schreibt_der_genannten_quelle_nichts_aus_einer_anderen_zu():
    quellen = [("Wikipedia: Kesselstein (CC BY-SA 4.0)", "Kesselstein lagert sich in Rohrleitungen ab und wird mechanisch durch Abklopfen entfernt."),
               ("Wikipedia: Entkalker (CC BY-SA 4.0)", "Reinigungstabs für Kaffeemaschinen enthalten oft Milchsäure. Zitronensäure ist verbreitet."),
               ("Wikipedia: Durgol (CC BY-SA 4.0)", "Durgol ist ein Entkalkungsmittel aus der Schweiz. Die Produkte bestehen aus Sulfonsäuren.")]
    falsch = "Falls du einen Entkalker wie Durgol nutzt, folge der Packung, die enthalten oft Milchsäure."
    richtig = "Durgol ist ein Entkalkungsmittel aus der Schweiz."
    assert belege.vermischt(falsch + " " + richtig, quellen) == [falsch]
    assert belege.vermischt("Tabs für Kaffeemaschinen enthalten oft Milchsäure.", quellen) == []
    assert belege.quellen_name("Wikipedia: Durgol (CC BY-SA 4.0)") == "Durgol"
    assert belege.quellen_name("Nachgeschaut: Rotweinflecken aus dem Teppich entfernen – so geht es") == ""


def test_die_pruefung_streicht_den_vermischten_satz():
    text = ("Nimm Zitronensäure oder einen Entkalker für Kaffeemaschinen.\n\n"
            "Falls du einen Entkalker wie Durgol nutzt, folge der Packung, die enthalten oft Milchsäure.")
    quellen = [{"nummer": 1, "art": "wikipedia", "titel": "Wikipedia: Entkalker (CC BY-SA 4.0)", "adresse": "https://de.wikipedia.org/wiki/Entkalker",
                "text": "Reinigungstabs für Kaffeemaschinen enthalten oft Milchsäure. Zitronensäure ist ein verbreiteter Entkalker."},
               {"nummer": 2, "art": "wikipedia", "titel": "Wikipedia: Durgol (CC BY-SA 4.0)", "adresse": "https://de.wikipedia.org/wiki/Durgol",
                "text": "Durgol ist ein Entkalkungsmittel aus der Schweiz. Die Produkte bestehen aus Sulfonsäuren."}]
    zusatz = "\n".join(q["text"] for q in quellen)
    neu, notizen = app_web.belege_anwenden(text, "Wie entkalke ich meine Kaffeemaschine?", zusatz, quellen, heute=date(2026, 10, 15))
    assert "Durgol" not in neu and "Zitronensäure" in neu
    assert any("aus einer anderen Quelle" in n for n in notizen)


def test_die_auszuege_sagen_dem_modell_dass_fremde_sachen_nicht_gelten():
    import wissen
    q = wissen.Quelle("k1", "seite", "Kesselstein", "https://beispiel.at/k", "2026-10-15", 10)
    zusatz, _ = wissen.kontext_bauen([wissen.Treffer(q, "Kesselstein in Rohrleitungen wird abgeklopft.", 1.0)])
    assert "von derselben Sache handelt wie die Frage" in zusatz


def _treffer(titel, text):
    import wissen
    return wissen.Treffer(wissen.Quelle("k-" + titel, "seite", titel, "https://beispiel.example/" + titel, "2026-10-15", len(text)), text, 1.0)


def test_fundstellen_ueber_ein_anderes_land_fallen_weg():
    import wissen
    de = _treffer("Winterreifen Deutschland", "In Deutschland gelten seit Oktober 2024 nur Reifen mit Schneeflockensymbol.")
    at = _treffer("Winterausrüstung", "In Österreich gilt vom 1. November bis 15. April die situative Winterreifenpflicht.")
    allgemein = _treffer("Winterreifen", "Winterreifen haben eine weichere Gummimischung.")
    behalten, weg = belege.fremdes_land_weg("Wann muss ich in Österreich auf Winterreifen wechseln?", [de, at, allgemein])
    assert behalten == [at, allgemein] and weg == 1
    behalten, _ = belege.fremdes_land_weg("Ab wann gilt in Deutschland die Winterreifenpflicht?", [de, at, allgemein])
    assert behalten == [de, allgemein]
    uk = _treffer("UK", "In the United Kingdom you can drive at 17.")
    us = _treffer("US", "In the USA most states allow driving at 16.")
    assert belege.fremdes_land_weg("From what age can you vote in the United Kingdom?", [uk, us])[0] == [uk]
    assert belege.fremdes_land_weg("Ab wann braucht man Winterreifen?", [de, at, allgemein])[1] == 0
    assert belege.fremdes_land_weg("Winterreifen in Österreich und Deutschland vergleichen", [de, at])[1] == 0
    assert belege.gefragtes_land("Is there an age limit in Australia?") == "au"


def test_ein_preis_ohne_quelle_wird_nicht_aus_dem_gedaechtnis_genannt():
    neu, notizen = app_web.belege_anwenden("Die Vignette für Österreich kostet 2026 9,90 € für 10 Tage.",
                                           "Wie viel kostet die Autobahnvignette 2026 in Österreich?", "", [], heute=date(2026, 10, 15))
    assert neu == "Das weiß ich noch nicht." and any("Preis ohne Quelle" in n for n in notizen)
    assert belege.rechnet("Was sind 1.200 Euro netto plus 20 Prozent?") and not belege.preisfrage("Was sind 1.200 Euro netto plus 20 Prozent?")
    neu2, _ = app_web.belege_anwenden("Die Vignette gibt es als Jahres-, 2-Monats-, 10-Tages- und 1-Tages-Vignette.",
                                      "Was kostet die Vignette?", "", [], heute=date(2026, 10, 15))
    assert "Jahres" in neu2


def test_die_englische_fassung_hat_keine_sternchen_und_spricht_nicht_in_der_ich_form():
    import antwortsprache
    assert "first person" in antwortsprache.SYSTEM_ANTWORT and "No Markdown" in antwortsprache.SYSTEM_ANTWORT

    def modell(nachrichten, **kw):
        class A:
            text = "1| Brief bursts of air can *increase* mold growth.\n2| Use **vinegar**."
        return A()
    text, ls = antwortsprache.antwort_uebersetzen(modell, "Kurzes Lüften kann Schimmel fördern. Nimm Essig.", {})
    assert "*" not in text and "increase mold" in text and "vinegar" in text


def test_einheiten_in_jeder_schreibweise_widersprechen_sich():
    assert not belege.alltag_ohne_widerspruch("Die Zugspitze ist 2965 Meter hoch.", "Die Zugspitze ist mit 2962 m der höchste Gipfel.")
    assert not belege.alltag_ohne_widerspruch("Die Donau ist 3100 Kilometer lang.", "Die Donau ist mit 2857 Kilometern der zweitlängste Fluss.")
    assert not belege.alltag_ohne_widerspruch("Gib 500 ml Wasser dazu.", "Man nimmt 0,3 Liter Wasser.")
    assert belege.alltag_ohne_widerspruch("Gib 500 ml Wasser dazu.", "Man nimmt 200 g Mehl.")


def test_wiederholungen_und_loeffel_sind_alltagsmasse():
    satz = "Wiederhole das 2–3 Mal, um den Kalk zu lösen."
    assert belege.alltag_ohne_widerspruch(satz, "Zitronensäure löst Kalk.")
    assert not any(b.sicher_falsch for b in belege.streng_pruefen("Gib 2 EL Zitronensäure und 1 TL Salz dazu.", "Zitronensäure löst Kalk."))
    assert belege.namen("Fahr mit der ÖBB oder frag die EZB.")[0] == ["ÖBB", "EZB"]
    assert not belege.alltag_ohne_widerspruch(satz, "Den Durchlauf 5 Mal wiederholen.")


@pytest.mark.parametrize("frage,erwartet", [
    ("Wann muss ich in Österreich auf Winterreifen wechseln?", True),
    ("Ab wann gilt in Deutschland die Winterreifenpflicht?", True),
    ("Darf man in der Schweiz mit 17 Auto fahren?", True),
    ("From what age can you vote in the United Kingdom?", True),
    ("Wie hoch ist die Strafe für Falschparken in Wien?", True),
    ("Wie funktioniert eine Wärmepumpe?", False),
    ("Wer hat die Sachertorte erfunden?", False),
])
def test_fragen_nach_regeln_und_pflichten_gehen_gleich_ins_internet(frage, erwartet):
    import nachschauen
    assert nachschauen.nicht_im_lexikon(frage) is erwartet
