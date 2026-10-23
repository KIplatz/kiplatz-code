# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web

FRAGE = "Ist eine Liguster Hecke immergrün?"
QUELLE = ("Der Gewöhnliche Liguster ist ein sommergrüner bis halbimmergrüner Strauch. Er wird oft als Hecke gepflanzt. "
          "In kalten Wintern verliert er seine Blätter.")
QUELLEN = [{"nummer": 1, "titel": "Wikipedia: Liguster", "adresse": "https://de.wikipedia.org/wiki/Liguster", "art": "wikipedia", "text": QUELLE}]
ERSTE = ("Die Sorte Aureum behält ihr Laub. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün. Bei starkem Frost wirft er die "
         "Blätter ab, als Hecke ist er trotzdem beliebt.")
NEU = ("Manche Sorten wie Atrovirens behalten ihr Laub länger. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün. Bei starkem Frost "
       "wirft er die Blätter ab, als Hecke ist er trotzdem beliebt.")


def _pruefer(*namen):
    return lambda zusatz, woerter: {i for i, w in enumerate(woerter) if any(n in w for n in namen)}


def _anwenden(text, frage, nochmal):
    return app_web.belege_anwenden(text, frage, QUELLE, [dict(q) for q in QUELLEN], heute=date(2026, 10, 23), nochmal=nochmal,
                                   pruefer=_pruefer("Aureum", "Atrovirens", "Musterstadt"))


def test_ein_name_im_ersten_satz_kostet_bei_einer_alltagsfrage_nicht_die_antwort():
    auftraege = []

    def nochmal(auftrag):
        auftraege.append(auftrag)
        return NEU
    t, notizen = _anwenden(ERSTE, FRAGE, nochmal)
    assert len(auftraege) == 1 and "Aureum“" in auftraege[0] and "lass genau diese Namen weg" in auftraege[0]
    assert "Das weiß ich noch nicht" not in auftraege[0]
    assert t.startswith("Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün") and "Atrovirens" not in t
    assert not any("fehlte der Anfang" in n for n in notizen)


def test_ohne_brauchbare_neufassung_bleibt_der_rest_der_ersten():
    t, notizen = _anwenden(ERSTE, FRAGE, lambda auftrag: "Das weiß ich noch nicht.")
    assert t.startswith("Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün") and "Aureum" not in t
    assert not any("fehlte der Anfang" in n for n in notizen)


def test_eine_zahlenfrage_bleibt_ganz_oder_gar_nicht():
    frage = "Wie hoch wird eine Liguster Hecke?"
    t, notizen = _anwenden(ERSTE, frage, lambda auftrag: NEU)
    assert t == "Das weiß ich noch nicht." and any("fehlte der Anfang" in n for n in notizen)


def test_faellt_in_der_neufassung_mehr_als_ein_name_gilt_sie_nicht():
    zwei = ("Die Sorte Atrovirens behält ihr Laub. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün. Bei starkem Frost wirft er die "
            "Blätter ab. Auch Musterstadt pflanzt ihn gern.")
    t, _notizen = _anwenden(ERSTE, FRAGE, lambda auftrag: zwei)
    assert "Atrovirens" not in t and "Musterstadt" not in t and "Aureum" not in t
    assert t.startswith("Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün")


def _weiss_nicht(text, frage):
    t, notizen = _anwenden(text, frage, lambda auftrag: "Das weiß ich noch nicht.")
    return t == "Das weiß ich noch nicht."


def test_preis_regel_und_namensfragen_bleiben_ganz_oder_gar_nicht():
    for frage in ("Was kostet eine Liguster Hecke?", "Ist es erlaubt, eine Liguster Hecke im Sommer zu schneiden?", "Welche Liguster Sorte ist immergrün?",
                  "Wie heißt die Liguster Sorte, die immergrün ist?", "Which privet hedge is evergreen?"):
        assert _weiss_nicht(ERSTE, frage), frage


def test_keine_ausnahme_bei_mehr_als_einem_satz_bei_zahl_oder_rueckbezug():
    zwei = ("Die Sorte Aureum behält ihr Laub. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün. Auch Musterstadt pflanzt ihn gern.")
    assert _weiss_nicht(zwei, FRAGE)
    mit_zahl = ("Die Sorte Aureum behält bis 1850 ihr Laub. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün. Bei starkem Frost wirft "
                "er die Blätter ab, als Hecke ist er trotzdem beliebt.")
    assert _weiss_nicht(mit_zahl, FRAGE)
    pronomen = ("Die Sorte Aureum behält ihr Laub. Sie ist bei Gärtnern sehr beliebt. Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün.")
    assert _weiss_nicht(pronomen, FRAGE)


def test_ein_mitgenommener_rueckbezug_in_der_neufassung_kostet_sie_nicht():
    neu = ("Manche Sorten wie Atrovirens behalten ihr Laub länger. Dann bleibt die Hecke auch im Winter dicht. Der Gewöhnliche Liguster ist "
           "sommergrün bis halbimmergrün. Bei starkem Frost wirft er die Blätter ab, als Hecke ist er trotzdem beliebt.")
    t, notizen = _anwenden(ERSTE, FRAGE, lambda auftrag: neu)
    assert t.startswith("Der Gewöhnliche Liguster ist sommergrün bis halbimmergrün") and "Atrovirens" not in t and "Dann bleibt" not in t
    assert any("neu geantwortet" in n for n in notizen)
