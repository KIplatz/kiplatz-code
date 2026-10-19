# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import antwortspeicher_basis
import app_web
import belege

QUELLE = ("Das Wiener Riesenrad wurde im Jahr 1897 nach Plänen des englischen Ingenieurs Walter Basset im Wiener Prater errichtet. "
          "Die Baukosten wurden von Basset vorfinanziert.")
FREMD = [QUELLE]
HAUPT = "Das Wiener Riesenrad wurde im Jahr 1897 nach Plänen des englischen Ingenieurs Walter Basset im Wiener Prater errichtet."
ERSTE = HAUPT + " Die Baukosten wurden von Basset vorfinanziert."
NEU = "Gebaut hat das Riesenrad im Jahr 1897 der englische Ingenieur Walter Basset."


def test_satztrennung_nach_einer_jahreszahl_und_am_zeilenanfang():
    assert belege._saetze("Eröffnet wurde es 1897. Das Riesenrad steht im Prater.") == ["Eröffnet wurde es 1897.", "Das Riesenrad steht im Prater."]
    assert belege._saetze("Am 25. September 2026 ist es so. Dann.") == ["Am 25. September 2026 ist es so.", "Dann."]
    assert belege._saetze("1. Erster Schritt. Zweiter Satz.") == ["1. Erster Schritt.", "Zweiter Satz."]


def test_nur_der_uebernommene_satz_wird_umgeschrieben_der_rest_bleibt():
    gefragt = []

    def umschreiben(saetze, englisch):
        gefragt.append(list(saetze))
        return {i: (NEU if s == HAUPT else "Bezahlt hat den Bau zuerst Basset selbst.") for i, s in enumerate(saetze)}
    text, notizen, ersetzt = app_web.eigene_worte(ERSTE, FREMD, umschreiben)
    assert NEU in text and HAUPT not in text and not belege.woertliche_saetze(text, FREMD)
    assert "in eigenen Worten geschrieben" in notizen[0] and ersetzt[HAUPT] == NEU and len(gefragt) == 1


def test_eine_neufassung_ohne_die_jahreszahl_gilt_nicht_dann_eine_zweite_runde():
    runden = []

    def umschreiben(saetze, englisch):
        runden.append(1)
        return {0: "Gebaut hat es der Engländer Walter Basset."} if len(runden) == 1 else {0: NEU}
    text, _n, _e = app_web.eigene_worte(HAUPT, FREMD, umschreiben)
    assert text == NEU and len(runden) == 2


def test_ganz_oder_gar_nicht_kein_rest_ohne_hauptsatz():
    text, notizen, _e = app_web.eigene_worte(ERSTE, FREMD, lambda s, e: {i: x for i, x in enumerate(s)})
    assert text == "Das weiß ich noch nicht." and "nicht ausgegeben" in notizen[0]
    text, _n, _e = app_web.eigene_worte(ERSTE, FREMD, None)
    assert text == "Das weiß ich noch nicht."
    eigen = "Walter Basset hat das Riesenrad gebaut, eröffnet wurde es 1897. " + HAUPT
    text, notizen, _e = app_web.eigene_worte(eigen, FREMD, None)
    assert text == "Walter Basset hat das Riesenrad gebaut, eröffnet wurde es 1897." and "gestrichen" in notizen[0]


def test_englisch_nach_der_uebersetzung():
    quelle_en = "The Vienna Giant Ferris Wheel was built in 1897 to plans by the English engineer Walter Basset in the Prater."
    antwort_en = "The Vienna Giant Ferris Wheel was built in 1897 to plans by the English engineer Walter Basset in the Prater."
    neu_en = "Walter Basset, an engineer from England, designed the wheel, which went up in the Prater in 1897."
    gesehen = []
    text, _n, _e = app_web.eigene_worte(antwort_en, [quelle_en], lambda s, e: (gesehen.append(e) or {0: neu_en}), englisch=True)
    assert text == neu_en and gesehen == [True]
    text, _n, _e = app_web.eigene_worte(antwort_en, [quelle_en], None, englisch=True)
    assert text == belege.WEISS_NICHT_EN


def test_die_neufassung_fuer_fehlende_namen_wird_auch_geprueft():
    q = "Klagenfurt hat laut Statistik Austria am 1. Jänner 2025 genau 105.734 Einwohner und ist die Landeshauptstadt von Kärnten mit vielen Seen."
    quellen = [{"nummer": 1, "art": "wikipedia", "titel": "Klagenfurt", "text": q}]
    woertlich = "Klagenfurt hat 105.734 Einwohner. Es ist die Landeshauptstadt von Kärnten mit vielen Seen und hat 105.734 Einwohner."
    t, notizen = app_web.belege_anwenden("Klagenfurt hat 105.734 Einwohner.", "Wie viele Einwohner haben Klagenfurt und Villach?",
                                         "Quelle 1: " + q, quellen, heute=date(2026, 10, 18), nochmal=lambda extra: woertlich, umschreiben=None)
    assert not belege.woertliche_saetze(t, [q])


def test_eine_liste_und_eine_zaehlung_fuer_antwort_und_speicher():
    assert belege.WORTLAUT_FREI is antwortspeicher_basis.FREI_ARTEN and "berechnet" in antwortspeicher_basis.FREI_ARTEN
    assert belege._wortliste("Am 1. Mai [1] kam er") == antwortspeicher_basis.wortliste("Am 1. Mai [1] kam er") == ["am", "mai", "kam", "er"]


def test_die_ampel_folgt_den_ersetzten_saetzen_nach_der_uebersetzung():
    import types
    quelle_en = "The Vienna Giant Ferris Wheel was built in 1897 to plans by the English engineer Walter Basset in the Prater."
    alt = quelle_en
    neu = "Walter Basset, an engineer from England, designed the wheel, which went up in the Prater in 1897."
    app_web._FREMD.texte = [quelle_en]
    fake = types.SimpleNamespace(_umschreiber=lambda: (lambda s, e: {0: neu}), _core=None)
    schein = {"belege": [], "pruefung": {"saetze": [{"text": alt, "farbe": "gruen"}]}}
    try:
        text, schein2 = app_web.Api.eigene_worte_englisch(fake, alt, schein)
    finally:
        app_web._FREMD.texte = []
    assert text == neu and schein2["pruefung"]["saetze"] == [{"text": neu, "farbe": "gruen"}] and schein2["belege"]


def test_ein_fehlender_schritt_einer_anleitung_ist_ein_loch():
    vorher = ("So machst du Pfannkuchen:\n1. Verrühre 250 g Mehl mit 500 ml Milch und 3 Eiern.\n2. Lass den Teig 10 Minuten ruhen.\n"
              "3. Brate die Pfannkuchen in einer heißen Pfanne goldbraun.")
    nachher = "So machst du Pfannkuchen:\n2. Lass den Teig 10 Minuten ruhen.\n3. Brate die Pfannkuchen in einer heißen Pfanne goldbraun."
    assert app_web.nur_rest(vorher, nachher, ["1. Verrühre 250 g Mehl mit 500 ml Milch und 3 Eiern."])
    englisch = "Step 1 Mix the flour and milk.\nStep 2 Fry them."
    assert app_web.nur_rest("Here is how.\n" + englisch, "Here is how.\nStep 2 Fry them.", ["Step 1 Mix the flour and milk."])
    assert not app_web.nur_rest("Anna wohnt in Gmunden. Sie fährt gern Rad. Sie liest viel.", "Anna wohnt in Gmunden. Sie liest viel.",
                                ["Sie fährt gern Rad."])
    assert not app_web.nur_rest(vorher, vorher.replace(" und 3 Eiern", ""), ["1. Verrühre 250 g Mehl mit 500 ml Milch und 3 Eiern."])
