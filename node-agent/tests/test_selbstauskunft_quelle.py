# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pruefung
import selbstauskunft
from test_app_web import _api


def test_betrifft_recognises_the_own_name_and_decentralised_ai():
    assert selbstauskunft.betrifft("Sag mir was zu KIplatz")
    assert selbstauskunft.betrifft("Was ist eine Dezentrale KI?")
    assert selbstauskunft.betrifft("speichert ihr meine Fragen?")
    assert not selbstauskunft.betrifft("Wie wird das Wetter morgen in Wels?")
    t = selbstauskunft.treffer()
    assert len(t) == 8 and t[0].quelle.kennung == "selbstauskunft" and t[0].punkte > t[1].punkte and "kostenlose KI" in t[0].text


def test_the_window_puts_the_self_description_first_with_the_instruction(tmp_path):
    api = _api(tmp_path)[0]
    zusatz, quellen, _n, hinweis = api._mit_wissen([{"role": "user", "content": "Sag mir was zu KIplatz"}])
    assert hinweis.startswith("Selbstauskunft von KIplatz als erste Quelle.")
    assert selbstauskunft.ANWEISUNG in zusatz and quellen and quellen[0]["titel"] == selbstauskunft.QUELLE["titel"]
    zusatz2, _q2, _n2, hinweis2 = api._mit_wissen([{"role": "user", "content": "Wie wird das Wetter morgen in Wels?"}])
    assert "Selbstauskunft" not in hinweis2 and selbstauskunft.ANWEISUNG not in zusatz2


def test_a_loose_paraphrase_with_a_citation_is_red_but_no_contradiction():
    quelle = "Auf beispiel.at geht es darum, KI einfach und ohne Fachchinesisch zu erklären. Es gibt kostenlose Werkzeuge und Anleitungen."
    r = pruefung.pruefen("Es geht also um praktische Beispiele, ohne komplizierte Begriffe. (Quelle 1)", [(1, quelle)])
    s = r.saetze[0]
    assert s.farbe in ("rot", "gelb") and not s.widerspruch
    r2 = pruefung.pruefen("Der Sitz der Firma liegt am Nordpol, siehe Quelle 1.", [(1, quelle)])
    assert r2.saetze[0].farbe == "rot" and r2.saetze[0].widerspruch


def test_a_question_about_ai_providers_gets_the_fact_sheet_not_all_texts(tmp_path):
    for f in ("Welche alternativen KI Agenten gibt es", "Gibt es eine Alternative zu ChatGPT?", "Welche KI ist die beste?", "Gute KI-Tools für Schüler?"):
        assert selbstauskunft.anbieter(f), f
    for f in ("Wie hoch ist der Großglockner?", "Welche Kirchen gibt es in Wels?", "Wer ist der Kiapp-Gründer?", "Welche Kiwis sind reif?"):
        assert not selbstauskunft.anbieter(f), f
    assert "Läuft am eigenen Gerät: ja" in selbstauskunft.STECKBRIEF
    api = _api(tmp_path)[0]
    zusatz, quellen, _n, hinweis = api._mit_wissen([{"role": "user", "content": "Welche alternativen KI Agenten gibt es"}])
    assert hinweis.startswith("Steckbrief von KIplatz als Quelle")
    assert selbstauskunft.ANWEISUNG_ANBIETER in zusatz and selbstauskunft.STECKBRIEF in zusatz
    assert quellen[0]["titel"] == "Steckbrief KIplatz" and selbstauskunft.TEXTE["kosten"] not in zusatz


def test_the_self_texts_no_longer_say_the_server_stores_no_question():
    alles = " ".join(selbstauskunft.TEXTE.values()) + selbstauskunft.ANWEISUNG
    assert "speichert keine Frage" not in alles and "speichert die Frage nicht" not in alles and "weder Wissen noch Fragen" not in alles
    assert "verschlüsselt und ohne Absender" in selbstauskunft.TEXTE["was"]
