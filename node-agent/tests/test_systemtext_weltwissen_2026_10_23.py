# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ki_laufzeit as kl

LANG, KURZ = kl.SYSTEMTEXT, kl.SYSTEMTEXT_KURZ


def test_allgemeinwissen_der_ganzen_welt_sagt_das_modell_selbst():
    assert "Erklärungen und Rat aus jedem Lexikon oder Ratgeber schreibst du selbst, für die ganze Welt" in LANG
    assert "Stehen oben Auszüge, nimmst du Zahlen, Daten und Namen nur aus ihnen" in LANG
    assert "If there are passages above, you take numbers, dates and names only from them" in kl.SYSTEMTEXT_EN
    assert "Wissen der ganzen Welt sagst du selbst." in KURZ
    for beispiel in ("„Wie viele Einwohner hat Neapel?“ beantwortest du mit der Zahl aus dem Auszug", "„Was hilft gegen Sonnenbrand?“ aus deinem Wissen"):
        assert beispiel in LANG
    assert "kennst du fast nie" not in LANG and "kennst du fast nie" not in KURZ


def test_weiss_ich_nicht_bleibt_fuer_angaben_mit_quelle():
    for wort in ("Ergebnisse und Ereignisse von heute", "Preise", "Termine", "Gesetze", "eine bestimmte Firma, Person, Website"):
        assert wort in LANG, wort
    assert "„Das weiß ich noch nicht.“ Dann sucht das Programm von selbst." in LANG
    assert "„Wie ist das Spiel heute ausgegangen?“" in LANG
    assert "Ergebnisse von heute, Preise, Termine, Gesetze" in KURZ and "„Das weiß ich noch nicht.“" in KURZ


def test_kein_vermutung_mehr_und_der_feste_anfang_bleibt():
    assert "Vermutung" not in LANG and "Vermutung" not in KURZ
    assert LANG.startswith("Du bist KIplatz, eine KI aus Österreich, offen für alle auf der Welt. Antworte auf Deutsch")
    assert len(KURZ) < 1300 < len(LANG) < 4200


def test_der_vorspann_der_auszuege_sagt_dasselbe_wie_der_systemtext():
    import inspect
    import wissen
    quelle = inspect.getsource(wissen.kontext_bauen)
    assert "ein Preis, eine Zahl, ein Datum, ein Produkt" not in quelle
    assert "Lexikon- und Weltwissen (Einwohner großer Städte, Höhen, Jahreszahlen der Geschichte, bekannte Personen) sagst du auch ohne Auszug." not in quelle
    assert "Jede Zahl, jedes Datum, jede Jahreszahl und jeden Namen nimmst du aus einem Auszug, der von der gefragten Sache handelt" in quelle
    assert "„Wer war Mozart?“ beantwortest du, „Wer ist Maria Huber aus Wels?“ nicht." in LANG
