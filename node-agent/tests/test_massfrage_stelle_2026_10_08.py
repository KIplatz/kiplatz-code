# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wissen


def _seite(abschnitte: list[str]):
    text = "\n\n".join(abschnitte)

    def oeffner(req, timeout=0):
        class _R:
            status = 200
            headers = {"Content-Type": "text/html; charset=utf-8"}

            def geturl(self):
                return "https://de.wikipedia.org/wiki/Donau"

            def read(self, n=-1):
                return ("<html><head><title>Donau – Wikipedia</title></head><body>" + "".join(f"<p>{a}</p>" for a in text.split("\n\n"))
                        + "</body></html>").encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _R()
    return oeffner


def test_the_kind_of_question_decides_not_the_topic():
    m = wissen.mass_punkte
    assert m("Wer ist Bundeskanzler in Österreich?") is None and m("Erklär mir Photovoltaik") is None
    lang, dauer = m("Wie lang ist die Donau in Österreich?"), m("Wie lange dauert der Flug nach Rom?")
    assert lang("In Österreich ist die Donau rund 349 Kilometer lang.") > lang("Die Donau ist 2.857 km lang.") > lang("Die Länge ist umstritten.") > 0
    assert lang("Die Flugzeit beträgt 2 Stunden.") == 0 and dauer("Die Flugzeit beträgt 2 Stunden.") >= 1
    assert m("Wie hoch ist der Großglockner?")("Der Großglockner ist 3.798 m hoch.") >= 1
    assert m("Wann wurde Linz gegründet?")("Linz erhielt 1236 das Stadtrecht.") >= 1
    assert m("Was kostet das Klimaticket?")("Das Klimaticket kostet 1.179,30 Euro.") >= 1
    assert m("Wie viele Einwohner hat Graz?")("Graz hat rund 300.000 Einwohner.") >= 1
    assert m("Wie groß ist der Attersee?")("Der Attersee ist 46,2 km² groß.") >= 1
    assert m("Wie schwer ist ein Elefant?")("Ein Elefant wiegt bis zu 6 Tonnen.") >= 1


def test_a_long_page_gives_the_passage_with_the_measure():
    fuell = [f"Die Donau und Österreich verbindet eine lange Geschichte, Abschnitt {i} erzählt davon ohne Zahlen und ohne Maße, "
             "mit vielen Wörtern über Schiffe, Brücken, Städte und die Monarchie, damit der Abschnitt so lang wird wie im Artikel." for i in range(40)]
    seite = ["Die Donau ist ein Strom in Mittel- und Südosteuropa und mit 2857 Kilometern der zweitlängste Fluss Europas."] + fuell + [
        "Von der deutschen bis an die slowakische Grenze durchfließt die Donau Österreich auf rund 349 Kilometern."] + fuell[:5]
    _q, _text, tr = wissen.live_lesen("https://de.wikipedia.org/wiki/Donau", "Wie lang ist die Donau in Österreich?", n=4, oeffner=_seite(seite))
    assert any("349 Kilometern" in t.text for t in tr), [t.text[:60] for t in tr]


def test_fable_details():
    lang = wissen.mass_punkte("Wie lang ist die Donau in Österreich?")
    assert lang("Die Donau fließt in Österreich ca. 350 km weit.") >= 3
    assert wissen.mass_punkte("Wie lange dauert die Fahrt?")("Die Strecke ist 349 km lang.") == 0
    viele = wissen.mass_punkte("Wie viele Einwohner hat Graz?")
    assert viele("Graz wurde 1128 erstmals erwähnt.") < 1 and viele("Graz hat 300.000 Einwohner.") >= 1
    assert wissen.mass_punkte("Was kostet das Ticket?")("Spanien wurde 3 Europameister.") < 1


def test_with_appointment_points_the_measure_rule_stays_out():
    seite = ["Spielplan"] + ["Am 3. Mai 2025 spielte Rapid gegen Sturm."] * 6 + ["Am 20. Oktober 2026 spielt Rapid gegen Austria."]
    _q, _t, tr = wissen.live_lesen("https://example.at/rapid", "Wann spielt Rapid als Nächstes?", n=2, oeffner=_seite(seite),
                                   extra=lambda s: 3.0 if "2026" in s else 0.0)
    assert "20. Oktober 2026" in tr[0].text


def test_only_the_word_for_the_measure_keeps_the_page_top():
    seite = ["Oben steht die Einleitung zum Großglockner."] + [f"Abschnitt {i}: die Höhe des Berges wird oft genannt." for i in range(8)]
    _q, _t, tr = wissen.live_lesen("https://example.at/glockner", "Wie hoch ist der Großglockner?", n=4, oeffner=_seite(seite))
    assert tr[0].text.startswith("Oben steht die Einleitung")


def test_the_wikipedia_copy_prefers_the_section_with_the_measure(tmp_path):
    import wikipedia
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    teile = (["Die Donau ist ein Strom in Mittel- und Südosteuropa."]
             + [f"Die Donau prägt Österreich seit Jahrhunderten, Teil {i} über Schifffahrt, Brücken und Städte in Österreich." for i in range(6)]
             + ["Von der deutschen bis an die slowakische Grenze durchfließt die Donau Österreich auf rund 349 Kilometern."])
    db.teil_aufnehmen(1, [{"id": 1, "titel": "Donau", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": teile}])
    treffer = db.suchen("Wie lang ist die Donau in Österreich?", n=3)
    assert any("349 Kilometern" in t[4] for t in treffer), [t[4][:50] for t in treffer]


def test_the_named_article_beats_other_articles_with_numbers(tmp_path):
    import wikipedia
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    donau = (["Die Donau ist mit einer Gesamtlänge von 2857 Kilometern nach der Wolga der zweitlängste Fluss Europas."]
             + [f"Die Donau in Österreich, Teil {i}: Schifffahrt, Brücken und Städte entlang der Donau." for i in range(21)]
             + ["Von der deutschen bis an die slowakische Grenze durchfließt die Donau Österreich auf rund 349 Kilometern."]
             + [f"Die Donau, Teil {i} über Mündung und Delta." for i in range(38)])
    db.teil_aufnehmen(1, [
        {"id": 1, "titel": "Donau", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": donau},
        {"id": 2, "titel": "Donauradweg", "beliebt": 0.002, "geaendert": "", "umleitungen": [],
         "teile": ["Der Donauradweg ist ein Radweg.", "Er führt durch Österreich.", "Etappen.", "Karten.", "Unterkünfte.",
                   "Der Donauradweg ist in Österreich rund 380 km lang und folgt der Donau von Passau bis Wien, lang und flach."]},
        {"id": 3, "titel": "Aschacher Straße", "beliebt": 0.001, "geaendert": "", "umleitungen": [],
         "teile": ["Die Aschacher Straße ist eine Landesstraße.", "Die Landesstraße B131 in Österreich ist 14,5 km lang und führt entlang der Donau bei Aschach."]},
    ] + [
        {"id": 100 + k, "titel": f"Gemeinde {k}", "beliebt": 0.0001, "geaendert": "", "umleitungen": [],
         "teile": [f"Gemeinde {k} liegt im Bezirk {k % 7} und hat eine Kirche, eine Schule und einen Sportverein Nummer {j}." for j in range(10)]}
        for k in range(300)])
    db._c.execute("INSERT OR REPLACE INTO teile (nr, artikel, abschnitte) VALUES (1, ?, ?)",
                  (int(db._c.execute("SELECT count(*) FROM artikel").fetchone()[0]), int(db._c.execute("SELECT count(*) FROM abschnitt").fetchone()[0])))
    treffer = db.suchen("Wie lang ist die Donau in Österreich?", n=3)
    assert any("349 Kilometern" in t[4] for t in treffer), [(t[2], t[3]) for t in treffer]
    reihe = [t[2] for t in treffer]
    assert reihe.index("Donau") < reihe.index("Donauradweg") if "Donauradweg" in reihe else True, reihe


def _kopie(tmp_path, artikel):
    import wikipedia
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    db.teil_aufnehmen(1, artikel + [
        {"id": 100 + k, "titel": f"Gemeinde {k}", "beliebt": 0.0001, "geaendert": "", "umleitungen": [],
         "teile": [f"Gemeinde {k} liegt im Bezirk {k % 7} und hat eine Kirche, eine Schule und einen Sportverein Nummer {j}." for j in range(10)]}
        for k in range(300)])
    db._c.execute("INSERT OR REPLACE INTO teile (nr, artikel, abschnitte) VALUES (1, ?, ?)",
                  (int(db._c.execute("SELECT count(*) FROM artikel").fetchone()[0]), int(db._c.execute("SELECT count(*) FROM abschnitt").fetchone()[0])))
    return db


def test_a_number_about_something_else_in_the_same_article_does_not_win(tmp_path):
    lang = wissen.mass_punkte("Wie lang ist die Donau in Österreich?", pflicht="Donau")
    eng = "Es ist Teil des 68 km langen Donauengtals zwischen Vilshofen (Deutschland) und Aschach (Österreich) im Südosten."
    richtig = "Von der deutschen bis an die slowakische Grenze durchfließt die Donau Österreich auf rund 349 Kilometern."
    assert lang(richtig) > lang(eng) and lang(eng) == 1.0
    donau = (["Die Donau ist mit einer Gesamtlänge von 2857 Kilometern nach der Wolga der zweitlängste Fluss Europas."]
             + [f"Die Donau in Österreich, Teil {i}: Schifffahrt, Brücken und Städte entlang der Donau." for i in range(21)]
             + [richtig] + [f"Die Donau, Teil {i} über Mündung und Delta." for i in range(25)] + [eng] + [f"Die Donau, Teil {i}." for i in range(12)])
    db = _kopie(tmp_path, [{"id": 1, "titel": "Donau", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": donau},
                           {"id": 2, "titel": "Österreich", "beliebt": 0.02, "geaendert": "", "umleitungen": [],
                            "teile": ["Österreich ist ein Staat in Mitteleuropa.", "Österreich ist ein Gebirgsland mit 83.882 km² Fläche."]}])
    treffer = db.suchen("Wie lang ist die Donau in Österreich?", n=8)
    texte = [t[4] for t in treffer]
    stelle = next(i for i, t in enumerate(texte) if "349 Kilometern" in t)
    eng = next((i for i, t in enumerate(texte) if "Donauengtals" in t), len(texte))
    assert stelle < eng, [(t[2], t[3]) for t in treffer]


def test_a_place_after_in_is_not_the_thing_asked_about(tmp_path):
    db = _kopie(tmp_path, [
        {"id": 1, "titel": "Inn", "beliebt": 0.005, "geaendert": "", "umleitungen": [],
         "teile": ["Der Inn ist ein Nebenfluss der Donau."] + [f"Der Inn, Teil {i}, mit Brücken und Kraftwerken." for i in range(8)]
                  + ["Der Inn ist insgesamt 517 km lang, davon fließen rund 280 km durch Österreich."]},
        {"id": 2, "titel": "Österreich", "beliebt": 0.02, "geaendert": "", "umleitungen": [],
         "teile": ["Österreich ist ein Staat in Mitteleuropa.", "Österreich ist ein Gebirgsland.", "Die Grenze Österreichs ist 2.562 km lang."]}])
    assert 1 in db.titel_artikel("Wie lang ist der Inn in Österreich?")
    assert db._subjekt("Wie lang ist der Inn in Österreich?", db.titel_artikel("Wie lang ist der Inn in Österreich?"))[1] == "Inn"
    assert db._subjekt("Wie viele Einwohner leben in Graz?", [2])[1] == "Österreich"
    treffer = db.suchen("Wie lang ist der Inn in Österreich?", n=8)
    assert any("517 km" in t[4] for t in treffer), [(t[2], t[3]) for t in treffer]
    assert not db.titel_artikel("Wie ist das Wetter?")


def test_third_round_einwohner_is_no_subject_and_variants_with_brackets_count(tmp_path):
    db = _kopie(tmp_path, [
        {"id": 1, "titel": "Einwohner", "beliebt": 0.01, "geaendert": "", "umleitungen": [], "teile": ["Der Einwohner einer Ortschaft ist ihr Bewohner."]},
        {"id": 2, "titel": "Graz", "beliebt": 0.01, "geaendert": "", "umleitungen": [],
         "teile": ["Graz ist die Landeshauptstadt der Steiermark.", "Graz hat 303.270 Einwohner und ist die zweitgrößte Stadt Österreichs."]},
        {"id": 3, "titel": "Enns", "beliebt": 0.01, "geaendert": "", "umleitungen": [],
         "teile": ["Enns ist eine Stadt mit 12.191 Einwohnern in Oberösterreich.", "Enns liegt an der Donau."]},
        {"id": 4, "titel": "Enns (Fluss)", "beliebt": 0.005, "geaendert": "", "umleitungen": [],
         "teile": ["Die Enns ist ein 254 km langer rechter Nebenfluss der Donau in Österreich."]},
        {"id": 5, "titel": "Mur (Fluss)", "beliebt": 0.005, "geaendert": "", "umleitungen": [],
         "teile": ["Die Mur ist ein 453 km langer Fluss in Österreich, Slowenien, Kroatien und Ungarn."]},
    ])
    ids = db.titel_artikel("Wie viele Einwohner hat Graz?")
    assert db._subjekt("Wie viele Einwohner hat Graz?", ids)[1] == "Graz"
    assert any("303.270" in t[4] for t in db.suchen("Wie viele Einwohner hat Graz?", n=8))
    assert any("254 km" in t[4] for t in db.suchen("Wie lang ist die Enns?", n=8))
    assert any("453 km" in t[4] for t in db.suchen("Wie lang ist die Mur?", n=8))


def test_fourth_round_the_intro_of_a_bracket_article_is_kept(tmp_path):
    mur = (["Die Mur ist ein 453 km langer Fluss in Österreich, Slowenien, Kroatien und Ungarn."]
           + [f"An der Mur steht bei Kilometer {10 + i} km das Kraftwerk Nummer {i}, die Mur ist dort 80 m breit." for i in range(8)])
    db = _kopie(tmp_path, [{"id": 5, "titel": "Mur (Fluss)", "beliebt": 0.005, "geaendert": "", "umleitungen": [], "teile": mur},
                           {"id": 6, "titel": "Mur (Begriffsklärung)", "beliebt": 0.0001, "geaendert": "", "umleitungen": [],
                            "teile": ["Mur steht für einen Fluss und mehrere Orte."]}])
    treffer = db.suchen("Wie lang ist die Mur?", n=3)
    assert any("453 km" in t[4] for t in treffer), [(t[2], t[3]) for t in treffer]
    assert len(treffer) <= 3


def test_a_question_without_a_measure_picks_as_before():
    seite = ["Oben steht die Einleitung zur Donau."] + [f"Abschnitt {i} über die Donau in Wien, Linz und Krems." for i in range(12)]
    _q, _t, tr1 = wissen.live_lesen("https://de.wikipedia.org/wiki/Donau", "Erzähl mir etwas über die Donau", n=4, oeffner=_seite(seite))
    assert tr1 and tr1[0].text.startswith("Oben steht die Einleitung")
