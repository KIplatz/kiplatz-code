# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen

HEUTE = date(2026, 11, 22)


def test_veraltetes_jahr_faellt_aus_den_suchwoertern():
    out = app_web.suchwoerter_ordnen(["Headphones driving laws Spain 2024 official traffic regulations"],
                                     "Is it legal to drive with headphones in Spain?", "", HEUTE)
    assert out == ["Headphones driving laws Spain official traffic regulations"]


@pytest.mark.parametrize("frage,liste", [
    ("Wie viele Medaillen hat Österreich bei Olympia 2024 gewonnen?", ["Olympia 2024 Medaillen Österreich"]),
    ("Who won the last Champions League?", ["champions league winner 2025"]),
    ("Wann wurde Google gegründet?", ["Google gegründet 1998"]),
    ("Bis wann muss ich die Arbeitnehmerveranlagung machen?", ["Arbeitnehmerveranlagung 2025 Frist"]),
    ("Welche Pflichten gelten nach dem Gebäudeenergiegesetz?", ["Pflichten GEG 2024"]),
    ("Darf man in der Bundesliga fünfmal wechseln?", ["Bundesliga Wechsel Regel 2025/26"]),
    ("Wie hoch ist die Pendlerpauschale in Österreich?", ["Pendlerpauschale 2025 Österreich"]),
])
def test_gewolltes_jahr_bleibt(frage, liste):
    out = app_web.suchwoerter_ordnen(liste, frage, "", HEUTE)
    jahr = next(w for w in liste[0].split() if w[:4].isdigit())
    assert any(jahr in q for q in out), out


@pytest.mark.parametrize("frage,rueckfrage", [
    ("What is the income tax rate in Dubai?", False),
    ("Wie hoch ist die Einkommensteuer in Dubai?", False),
    ("How much is income tax in Ontario?", False),
    ("What is the speed limit in Tokyo?", False),
    ("What is the minimum wage?", True),
    ("Wie hoch ist die Mehrwertsteuer?", True),
    ("What is the VAT rate for a hotel?", True),
    ("Was ist der Mindestlohn in Höhe von 10 Euro?", True),
])
def test_ort_legt_das_land_fest(frage, rueckfrage):
    assert (nachschauen.land_rueckfrage([{"role": "user", "content": frage}]) is not None) is rueckfrage


def test_gebremste_suche_heisst_nicht_nichts_gefunden():
    assert app_web.im_netz_gesucht(False, [], {"gesucht": ["x"], "abgelehnt": True}) == "nicht_erreicht"
    assert app_web.im_netz_gesucht(False, [], {"gesucht": ["x"]}) is True
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert 'if im_netz_gesucht(nachgeholt, quellen, lauf) == "nicht_erreicht":\n                a = dataclasses.replace(a, text=_satz(_NICHT_ERREICHT_SATZ' in quelle


@pytest.mark.parametrize("text", ["How much tax do I pay on profits in Bitcoin?", "Do I pay tax on gifts for Christmas?",
                                  "What Is The Income Tax Rate For Small Businesses?", "What is the retirement age for a male?",
                                  "Kann ich Essen von der Steuer absetzen?"])
def test_kein_ort(text):
    assert not nachschauen.ort_genannt(text)
