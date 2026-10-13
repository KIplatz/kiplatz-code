# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gespraeche

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


def test_new_reuses_the_empty_conversation(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    erstes = a.neu()
    assert [a.neu().kennung for _ in range(5)] == [erstes.kennung] * 5
    assert len(list(a.ordner.glob("*.json"))) == 1


def test_empty_conversations_are_not_listed_and_appear_with_the_first_question(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu()
    assert a.liste() == []
    a.anhaengen(g, "user", "Wie hoch ist der Großglockner?")
    assert [e["kennung"] for e in a.liste()] == [g.kennung]
    neu = a.neu()
    assert neu.kennung != g.kennung and [e["kennung"] for e in a.liste()] == [g.kennung]


def test_a_conversation_with_settings_is_not_empty(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu()
    a.verschieben(g.kennung, "Garten")
    assert a.neu().kennung != g.kennung
    assert [e["kennung"] for e in a.liste()] == [g.kennung]


def test_the_logo_leads_to_the_start_like_new_conversation():
    i = HTML.index('const brand = document.getElementById("brand");')
    teil = HTML[i:i + 900]
    assert 'const zumStart = () => $("#btn-neu").click();' in teil
    assert 'brand.addEventListener("click", zumStart);' in teil and 'zeige("gespraeche"))' not in teil
