# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege
import schriftstueck
import wikipedia

HEUTE = date(2026, 9, 30)
QUELLEN_ORTSTEILE = ("Charlottenburg ist ein Ortsteil im Berliner Bezirk Charlottenburg-Wilmersdorf mit 130.000 Einwohnern. "
                     "Mitte ist ein Ortsteil im gleichnamigen Bezirk von Berlin. Kreuzberg ist ein Ortsteil des Bezirks Friedrichshain-Kreuzberg.")
QUELLE_BERLIN = "Berlin ist die Hauptstadt Deutschlands und hat 3.878.100 Einwohner (Stand 2024)."


def _q(text):
    return [{"nummer": 1, "titel": "Wikipedia", "art": "wikipedia", "text": text}]


def test_brauchbar_erkennt_reste_und_laesst_ganze_antworten_durch():
    assert not belege.brauchbar("3 nennen nur Ortsteile, nicht die Gesamtzahl).")
    assert not belege.brauchbar("nicht die Gesamtzahl.")
    assert not belege.brauchbar("und hat viele Bezirke.")
    assert not belege.brauchbar("Berlin ist groß. dazu kommen Ortsteile.")
    assert not belege.brauchbar("Vergleich:\n---")
    assert not belege.brauchbar("")
    assert belege.brauchbar("Berlin hat 3.878.100 Einwohner (Stand 2024).")
    assert belege.brauchbar("Das weiß ich noch nicht.")
    assert belege.brauchbar("– Salzburg: 155.000 Einwohner\n– Wien: 2.000.000 Einwohner")
    assert belege.brauchbar("„Faust“ schrieb Goethe.\n1. Teil erschien 1808.")


def test_gerede_ueber_quellen_fliegt_ganz_auch_in_klammern():
    assert app_web.ohne_auszuege("Berlin hat 3,8 Millionen Einwohner (die Quellen 1 bis 3 nennen nur Ortsteile, nicht die Gesamtzahl).") == "Berlin hat 3,8 Millionen Einwohner."
    assert app_web.ohne_auszuege("Berlin hat 3,8 Millionen Einwohner. (Die Quellen 1 bis 3 nennen nur Ortsteile, nicht die Gesamtzahl).") == "Berlin hat 3,8 Millionen Einwohner."
    assert app_web.ohne_auszuege("Die Quellen nennen nur Ortsteile.") == "Das weiß ich noch nicht."
    assert app_web.ohne_auszuege("Die Quelle des Rheins liegt in der Schweiz.") == "Die Quelle des Rheins liegt in der Schweiz."


def test_berlin_bild_1_nie_ein_klammerrest_sondern_neu_oder_ehrlich():
    roh = "Berlin hat rund 3,8 Millionen Einwohner. (Die Quellen 1 bis 3 nennen nur Ortsteile, nicht die Gesamtzahl)."
    antwort = app_web.ohne_auszuege(app_web.ohne_markdown(roh))
    assert antwort == "Berlin hat rund 3,8 Millionen Einwohner."
    t, notizen = app_web.belege_anwenden(antwort, "Einwohner in Berlin", QUELLEN_ORTSTEILE, _q(QUELLEN_ORTSTEILE), heute=HEUTE)
    assert t == "Das weiß ich noch nicht." and ")" not in t
    t, notizen = app_web.belege_anwenden("Berlin hat rund 3,8 Millionen Einwohner. Die nennen nur Ortsteile, nicht die Gesamtzahl).", "Einwohner in Berlin",
                                         QUELLEN_ORTSTEILE, _q(QUELLEN_ORTSTEILE), heute=HEUTE)
    assert t == "Das weiß ich noch nicht." and any("kein ganzer Satz" in n for n in notizen)
    t, _ = app_web.belege_anwenden(antwort, "Einwohner in Berlin", QUELLEN_ORTSTEILE, _q(QUELLEN_ORTSTEILE), heute=HEUTE, nochmal=lambda e: "Das weiß ich noch nicht.")
    assert t == "Das weiß ich noch nicht."
    q2 = _q(QUELLEN_ORTSTEILE) + [{"nummer": 2, "titel": "Wikipedia", "art": "wikipedia", "text": QUELLE_BERLIN}]
    beleg = QUELLEN_ORTSTEILE + "\n" + QUELLE_BERLIN
    t, _ = app_web.belege_anwenden(antwort, "Einwohner in Berlin", beleg, q2, heute=HEUTE, nochmal=lambda e: "Berlin hat 3.878.100 Einwohner (Stand 2024).")
    assert t == "Berlin hat rund 3,8 Millionen Einwohner."
    t, notizen = app_web.belege_anwenden("Berlin hat 3,1 Millionen Einwohner.", "Einwohner in Berlin", beleg, q2, heute=HEUTE, nochmal=lambda e: "Berlin hat 3.878.100 Einwohner (Stand 2024).")
    assert t == "Berlin hat 3.878.100 Einwohner (Stand 2024)." and any("neu geantwortet" in n for n in notizen)
    t, _ = app_web.belege_anwenden("Berlin hat 3,1 Millionen Einwohner.", "Einwohner in Berlin", beleg, q2, heute=HEUTE, nochmal=lambda e: "nennen nur Ortsteile).")
    assert t == "Das weiß ich noch nicht."


def test_ein_gestrichener_satz_mitten_im_text_laesst_nie_einen_kleinanfang_stehen():
    antwort = "Wien ist die Hauptstadt Österreichs. Sie hat 1.999.999 Einwohner, davon viele im Zentrum. Die Stadt liegt an der Donau."
    quelle = "Wien ist die Hauptstadt Österreichs und liegt an der Donau."
    t, _ = app_web.belege_anwenden(antwort, "Wien", quelle, _q(quelle), heute=HEUTE)
    assert t == "Wien ist die Hauptstadt Österreichs. Die Stadt liegt an der Donau."
    assert belege.brauchbar(t)


def test_bild_2_eine_wissensfrage_ist_nie_ein_vorhaben():
    for f in ("Einwohner Salzburg und Wien vergleichen", "Vergleiche Salzburg und Wien", "Fläche von Salzburg und Wien im Vergleich",
              "Was kostet ein Klimaticket, vergleiche mit Deutschland", "Vergleich der Einwohnerzahlen von Graz und Linz", "Wie hoch ist der Großglockner"):
        assert schriftstueck.erkennen(f) is None, f
    for f in ("Vergleiche mir zwei Handys für meine Tochter und empfiehl eines", "Plane mir ein Wochenende in Wien mit zwei Kindern",
              "Welches Auto passt zu uns, vergleiche Kombi und Van", "Hilf mir bei der Entscheidung zwischen Salzburg und Wien als Wohnort"):
        a = schriftstueck.erkennen(f)
        assert a is not None and a.offen, f
    a = schriftstueck.erkennen("Schreib mir einen Brief an die Gemeinde wegen der Einwohnerzahl")
    assert a is not None and not a.offen


def _db(pfad):
    db = wikipedia.Datenbank(pfad, schreiben=True)
    db.teil_aufnehmen(1, [
        {"id": 1, "titel": "Berlin", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": [QUELLE_BERLIN, "Berlin hat zwölf Bezirke."]},
        {"id": 2, "titel": "Charlottenburg", "beliebt": 0.001, "geaendert": "", "umleitungen": [],
         "teile": ["Charlottenburg ist ein Ortsteil im Berliner Bezirk Charlottenburg-Wilmersdorf mit 130.000 Einwohnern."]},
        {"id": 3, "titel": "Salzburg", "beliebt": 0.005, "geaendert": "", "umleitungen": ["Stadt Salzburg"], "teile": ["Salzburg hat 155.416 Einwohner."]},
        {"id": 4, "titel": "Einwohner", "beliebt": 0.002, "geaendert": "", "umleitungen": [], "teile": ["Ein Einwohner ist eine Person, die in einem Gebiet wohnt."]},
        {"id": 5, "titel": "Wien", "beliebt": 0.008, "geaendert": "", "umleitungen": [], "teile": ["Wien hat 2.028.399 Einwohner."]},
    ])
    db.teil_abschliessen(1)
    return db


def test_der_artikel_zum_namen_kommt_mit_seiner_einleitung_immer_mit(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    assert db.einleitung(1) == ("Berlin", QUELLE_BERLIN)
    k = object.__new__(wikipedia.WikiKopie)
    k._db, k._log, k.ausgabe = db, lambda z: None, lambda: "20260929"
    e = k.einleitung("Einwohner in Berlin")
    assert [t.quelle.titel for t in e] == [f"Wikipedia: Berlin ({wikipedia.LIZENZ})"] and e[0].text == QUELLE_BERLIN
    beide = k.einleitung("Einwohner Salzburg und Berlin vergleichen")
    assert sorted(t.text for t in beide) == sorted([QUELLE_BERLIN, "Salzburg hat 155.416 Einwohner."])
    assert k.einleitung("Wie viele Ortsteile gibt es?") == []
    db.schliessen()


def test_neuerungen_stehen():
    import neuerungen
    assert any("ganz oder gar nicht" in s for s in neuerungen.NEUERUNGEN["2026-09-29r"])


def test_markdown_vorn_ist_kein_rest():
    import belege
    for t in ["**Berlin** hat rund 3,8 Millionen Einwohner.", "## Berlin\nBerlin hat 3,8 Millionen Einwohner.",
              "| Stadt | Einwohner |\n|---|---|\n| Wien | 2.000.000 |", "> Hinweis: Das gilt für 2024.", "**Wien:** rund 2 Millionen.\n---\n**Salzburg:** 155.000."]:
        assert belege.brauchbar(t), t
    for t in ["3 nennen nur Ortsteile, nicht die Gesamtzahl).", "## Berlin", "und dann noch mehr Einwohner."]:
        assert not belege.brauchbar(t), t


def test_ein_sachwort_nimmt_keinem_namen_den_platz(tmp_path):
    db = _db(tmp_path / "w.sqlite")
    k = object.__new__(wikipedia.WikiKopie)
    k._db, k._log, k.ausgabe = db, lambda z: None, lambda: "20260929"
    texte = [t.text for t in k.einleitung("Einwohner Salzburg und Wien vergleichen")]
    assert texte == ["Salzburg hat 155.416 Einwohner.", "Wien hat 2.028.399 Einwohner."]
    assert [t.text for t in k.einleitung("Einwohner in Berlin")] == [QUELLE_BERLIN]
    db.schliessen()


def test_bei_einer_ortsfrage_gilt_der_ortsartikel(tmp_path):
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    db.teil_aufnehmen(1, [
        {"id": 10, "titel": "Europäischer Wels", "beliebt": 0.003, "geaendert": "", "umleitungen": ["Wels"], "teile": ["Der Europäische Wels ist ein Fisch."]},
        {"id": 11, "titel": "Wels (Stadt)", "beliebt": 0.004, "geaendert": "", "umleitungen": [], "teile": ["Wels ist eine Statutarstadt in Oberösterreich mit 65.764 Einwohnern."]},
        {"id": 12, "titel": "Steyr (Begriffsklärung)", "beliebt": 0.001, "geaendert": "", "umleitungen": [], "teile": ["Steyr steht für: eine Stadt, einen Fluss."]},
        {"id": 13, "titel": "Steyr", "beliebt": 0.004, "geaendert": "", "umleitungen": [], "teile": ["Steyr ist eine Statutarstadt in Oberösterreich mit 38.000 Einwohnern."]},
        {"id": 14, "titel": "Einwohnerzahl", "beliebt": 0.002, "geaendert": "", "umleitungen": [], "teile": ["Die Einwohnerzahl ist die Zahl der Einwohner."]},
    ])
    db.teil_abschliessen(1)
    k = object.__new__(wikipedia.WikiKopie)
    k._db, k._log, k.ausgabe = db, lambda z: None, lambda: "20260929"
    assert [t.text for t in k.einleitung("Einwohnerzahl Wels")] == ["Wels ist eine Statutarstadt in Oberösterreich mit 65.764 Einwohnern."]
    assert [t.text for t in k.einleitung("Wie viele Einwohner hat die Stadt Wels?")] == ["Wels ist eine Statutarstadt in Oberösterreich mit 65.764 Einwohnern."]
    assert [t.text for t in k.einleitung("Wie groß wird ein Wels?")] == ["Der Europäische Wels ist ein Fisch."]
    assert [t.text for t in k.einleitung("Einwohner Steyr")] == ["Steyr ist eine Statutarstadt in Oberösterreich mit 38.000 Einwohnern."]
    db2 = wikipedia.Datenbank(tmp_path / "w2.sqlite", schreiben=True)
    db2.teil_aufnehmen(1, [{"id": 11, "titel": "Wels (Stadt)", "beliebt": 0.004, "geaendert": "", "umleitungen": [], "teile": ["Wels hat 65.764 Einwohner."]}])
    db2.teil_abschliessen(1)
    k._db = db2
    assert [t.text for t in k.einleitung("Einwohnerzahl Wels")] == ["Wels hat 65.764 Einwohner."]
    db.schliessen()
    db2.schliessen()
