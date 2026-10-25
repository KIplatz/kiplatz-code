# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege

HEUTE = date(2026, 10, 25)

FALSCH = [
    "Ein weiterer Thriller, „Die Ehefrau“, kommt im März 2026 auf den Markt.",
    "Die Staffel startet 2025.",
    "The new season will premiere on March 5, 2026.",
    "Il nuovo romanzo uscirà a marzo 2026.",
    "Le film sortira en juin 2026.",
    "La nueva temporada saldrá en abril de 2026.",
    "De nieuwe roman verschijnt in mei 2026.",
    "新作は2026年3月に発売予定です。",
]
RICHTIG = [
    "Das neue Buch heißt „Die verschlossene Tür“ und ist am 28. August 2026 erschienen.",
    "„Der Unfall“ erscheint am 11. November 2026 bei Heyne.",
    "Das Album erschien 2025, das nächste kommt 2027.",
    "Seit 2020 wird das Buch in 40 Ländern verkauft.",
    "The sequel is coming in spring 2027.",
    "Il romanzo è uscito a marzo 2026.",
]


def test_zukunft_mit_vergangenem_datum_erkannt():
    assert [s for s in FALSCH if not belege.zukunft_vorbei(s, HEUTE)] == []
    assert [s for s in RICHTIG if belege.zukunft_vorbei(s, HEUTE)] == []


def test_das_modell_schreibt_in_der_vergangenheit_sonst_faellt_der_satz():
    antwort = ("Das neue Buch heißt „Die verschlossene Tür“ und ist am 28. August 2026 erschienen. "
               "Ein weiterer Thriller, „Die Ehefrau“, kommt im März 2026 auf den Markt.")
    gut = {0: "Ein weiterer Thriller, „Die Ehefrau“, ist im März 2026 erschienen."}
    t, n, raus = belege.zeitform_berichtigen(antwort, HEUTE, lambda s, e, a: gut)
    assert n == 1 and raus == [] and "ist im März 2026 erschienen" in t and "kommt im März" not in t
    for schlecht in ({0: "„Die Ehefrau“ kommt im März 2027."}, {0: "„Die Ehefrau“ kommt im März 2026 heraus."}, {}):
        t, n, raus = belege.zeitform_berichtigen(antwort, HEUTE, lambda s, e, a, x=schlecht: x)
        assert n == 0 and len(raus) == 1 and "Die Ehefrau" not in t and "verschlossene Tür" in t
    t, n, raus = belege.zeitform_berichtigen(antwort, HEUTE, None)
    assert n == 0 and len(raus) == 1


def test_neuheitsfrage_und_suche_nach_dem_naechsten():
    for f in ("Wie heißt das neue Buch von Freida Mc Fadden?", "Wann kommt die neue Staffel von Stranger Things?",
              "What is the latest Taylor Swift album?", "Qual è il nuovo romanzo di Elena Ferrante?", "Neue Kollektion von Zara",
              "Quel est le dernier livre de Joël Dicker ?", "最新の映画は？"):
        assert app_web.neuheitsfrage(f), f
    for f in ("Was kostet ein neues iPhone?", "Wie ist das Wetter morgen?", "Neue Reifen für den Golf"):
        assert not app_web.neuheitsfrage(f), f
    anfragen, _ = app_web.vergleich_runde("Wie heißt das neue Buch von Freida Mc Fadden?", ["Freida McFadden neues Buch"])
    jahr = app_web.ki_laufzeit.heute().year
    assert anfragen == ["Freida McFadden neues Buch", f"Freida McFadden neues Buch {jahr}", f"Freida McFadden neues Buch {jahr + 1}"]
    assert "zuletzt erschienen" in app_web.frage_fokus("Wie heißt das neue Buch von Freida Mc Fadden?")
