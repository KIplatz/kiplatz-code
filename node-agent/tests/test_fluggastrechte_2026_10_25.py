# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fluggastrechte as fg

from test_app_web import _api


def _g(*texte):
    return [{"role": ("user", "assistant")[i % 2], "content": t} for i, t in enumerate(texte)]


def test_flughafenliste_ist_da_und_vollstaendig():
    daten = fg._laden()
    assert len(daten) > 3000
    for code in ("VIE", "LNZ", "SZG", "GRZ", "INN", "KLU", "MUC", "FRA", "LHR", "JFK", "HND", "TFS", "HRG", "FCO"):
        assert code in daten


@pytest.mark.parametrize("frage,von,nach", [
    ("Mein Flug von Wien nach London war 4 Stunden verspätet, was steht mir zu?", "VIE", "LHR"),
    ("Flug Wien London 2 Stunden verspätet, Anspruch?", "VIE", "LHR"),
    ("Flug VIE-LHR 4h Verspätung, Entschädigung?", "VIE", "LHR"),
    ("Flug VIE nach HRG 2 Stunden verspätet, Anspruch?", "VIE", "HRG"),
    ("Flug Linz - Antalya 5 Stunden Verspätung, Entschädigung?", "LNZ", "AYT"),
    ("Flug von München mit Lufthansa nach Kreta annulliert, Geld?", "MUC", "HER"),
    ("My flight from London to New York was delayed 3.5 hours, what compensation can I claim?", "LHR", "JFK"),
    ("Mein Flug nach Rom war verspätet, steht mir Geld zu? ab Linz, 4 Stunden", "LNZ", "FCO"),
])
def test_strecke_erkennen(frage, von, nach):
    a, b = fg._strecke(frage)
    assert (a[0], b[0]) == (von, nach)


@pytest.mark.parametrize("frage,betrag", [
    ("Mein Flug von Wien nach London war 4 Stunden verspätet, was steht mir zu?", "250 €"),
    ("Flug Linz - Antalya 5 Stunden Verspätung, Entschädigung?", "400 €"),
    ("Flug von Wien nach Teneriffa annulliert, bekomme ich Geld?", "400 €"),
    ("Flug von Frankfurt nach Bangkok 6 Stunden verspätet, Entschädigung?", "600 €"),
    ("Flug von Frankfurt nach Bangkok 3,5 Stunden verspätet, Entschädigung?", "300 €"),
    ("My flight from London to New York was delayed 5 hours, what compensation can I claim?", "520 Pfund"),
])
def test_betraege_nach_der_verordnung(frage, betrag):
    de, en = fg.antwort(_g(frage))
    assert f"{betrag} je Person" in de and en


def test_unter_drei_stunden_und_ausserhalb_der_eu():
    de, en = fg.antwort(_g("Flug Wien London 2 Stunden verspätet, Anspruch?"))
    assert "noch keine Entschädigung" in de and "isn't enough" in en
    de, _ = fg.antwort(_g("Flug von Bangkok nach Tokio verspätet 5 Stunden, Entschädigung?"))
    assert "gilt dafür nicht" in de
    de, _ = fg.antwort(_g("My flight from New York to Paris with Delta was 6 hours late, am I entitled to compensation?"))
    assert "nur, wenn die Fluglinie aus der EU" in de and "außergewöhnlichen Umständen" in de


def test_rueckfrage_einmal_und_dann_gerechnet():
    q = "Mein Flug war verspätet, steht mir eine Entschädigung zu?"
    de, en = fg.antwort(_g(q))
    assert de.startswith(fg.RUECKFRAGE_ANFANG) and en.startswith(fg.RUECKFRAGE_ANFANG_EN) and "Stunden" in de
    de2, _ = fg.antwort(_g(q, de, "von Wien nach Hurghada, 3 Stunden"))
    assert "400 € je Person" in de2
    de3, _ = fg.antwort(_g(q, de, "weiß ich nicht"))
    assert not de3.startswith(fg.RUECKFRAGE_ANFANG)


@pytest.mark.parametrize("frage", ["Wie hoch ist der Großglockner?", "Fluggastrechte erklären", "Wann fliegt der nächste Flug nach London?",
                                   "Was kostet ein Flug von Wien nach London?"])
def test_keine_frage_nach_entschaedigung(frage):
    assert fg.antwort(_g(frage)) is None


def test_der_ganze_weg_ohne_modell(tmp_path):
    api, fake, _ = _api(tmp_path)
    api._ki_starten_blockierend()
    text, ls = api._antwort_fuer_mitglied(_g("Mein Flug von Wien nach London war 4 Stunden verspätet, was steht mir zu?"), [], "ein Mitglied")
    assert "250 € je Person" in text and ls["gemacht"] == fg.GEMACHT
    text, _ = api._antwort_fuer_mitglied(_g("My flight from Vienna to London was 4 hours late, what compensation am I entitled to?"), [], "ein Mitglied")
    assert "€250 per person" in text


def test_rueckfrage_nur_nach_der_fehlenden_seite():
    de, en = fg.antwort(_g("Mein Flug nach Rom war verspätet, steht mir Geld zu?"))
    assert "nach Rom geflogen bist" in de and "to Rome from" in en and "nach welchem" not in de
    q = "Mein Flug ab Wien wurde annulliert, was steht mir zu?"
    de, _ = fg.antwort(_g(q))
    assert "wohin du ab Wien geflogen bist" in de
    de2, _ = fg.antwort(_g(q, de, "nach Lissabon"))
    assert "Wien (VIE) nach Lissabon (LIS)" in de2 and "400 € je Person" in de2
