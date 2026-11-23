# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import wissen


def _stelle(adresse: str, text: str):
    q = wissen.Quelle(wissen.kennung_fuer("nachgeschaut", adresse), "nachgeschaut", "", adresse, "2026-11-23T12:00:00Z", len(text), "")
    return wissen.Treffer(q, text, 1.0)


def test_jede_seite_zuerst():
    nehammer = [_stelle("https://de.wikipedia.org/wiki/Karl_Nehammer", f"Nehammer war Bundeskanzler von Österreich, Abschnitt {i}.") for i in range(8)]
    bka = _stelle("https://www.bundeskanzleramt.gv.at/stocker", "Christian Stocker wurde am 3. März 2025 als Bundeskanzler angelobt.")
    fw = set(wissen.woerter("Wer ist Bundeskanzler von Österreich?"))

    def punkte(t):
        return len(fw & set(wissen.woerter(t.text)))
    aus = app_web.je_seite_zuerst(nehammer + [bka], punkte)
    assert aus[:2] == [nehammer[0], bka]
    assert aus[2:] == nehammer[1:]
    assert app_web.je_seite_zuerst([], punkte) == []


def test_seite_ohne_fragewort_bekommt_keinen_sicheren_platz():
    fw = set(wissen.woerter("Wie lange ist die Kündigungsfrist für Angestellte in Österreich?"))

    def punkte(t):
        return len(fw & set(wissen.woerter(t.text)))
    tabelle = [_stelle("https://www.wko.at/kuendigung", f"Kündigungsfrist Angestellte Österreich, Dienstjahre {j}: {w} Wochen") for j, w in
               [("bis 2", 6), ("ab 2", 8), ("ab 5", 12)]]
    menue = _stelle("https://www.example.at/", "Startseite Kontakt Impressum")
    aus = app_web.je_seite_zuerst(tabelle + [menue], punkte)
    assert aus == tabelle + [menue]


def test_an_der_sortierung_selbst():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert "gesucht[:] = je_seite_zuerst(sorted(gesucht, key=lambda t: -fragewoerter(t)), fragewoerter)" in quelle
