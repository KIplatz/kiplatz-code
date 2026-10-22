# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import app_web


def test_the_no_search_marker_is_found_in_german_and_in_the_models_english():
    import pruefstand
    assert pruefstand.suche_aus("Das weiß ich noch nicht, und die Suche im Internet ist gerade nicht durchgekommen.")
    assert pruefstand.suche_aus("I don’t know that yet, and the internet search isn’t working right now.")
    assert pruefstand.suche_aus("I don't know yet, and the internet search didn't get through just now.")
    assert not pruefstand.suche_aus("The internet search shows three good pages.")


def test_each_test_answer_carries_a_short_note_why_it_was_changed_and_how_long_each_step_took(tmp_path):
    import pruefstand
    q = ("Quelle 1: oesterreich.gv.at. Die erste Fassung nannte Zahlen, Daten oder Namen, die in keiner Quelle stehen; KIplatz hat neu geantwortet. "
         "Zeit je Schritt: sucht im Internet 3 s, schreibt die Antwort 5 s.")
    n = pruefstand.notiz_aus(q)
    assert "neu geantwortet" in n and "Zeit je Schritt: sucht im Internet 3 s" in n and "oesterreich.gv.at" not in n
    assert pruefstand.notiz_aus("Quelle 1: x.") == "" and len(pruefstand.notiz_aus(q * 20)) <= pruefstand.NOTIZ_MAX


def test_the_report_is_sent_up_to_three_times_before_the_round_is_lost(tmp_path, monkeypatch):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api, "_ki_starten_blockierend", lambda: None)
    monkeypatch.setattr(api, "PRUEFSTAND_WEGE", (), raising=False)
    monkeypatch.setattr(api._core, "run_state", lambda: app_web.node_local_state.RunState.ACTIVE)
    monkeypatch.setattr(api, "_antwort_fuer_mitglied", lambda nachrichten, auszuege, fuer, **kw: ("eine Antwort", {}))
    api._mess_schlafen = lambda s: None
    versuche = []

    def ergebnis(antworten, wege, *, runde=""):
        versuche.append(1)
        if len(versuche) < 3:
            raise app_core.AppError("SERVER", "gerade nicht erreichbar")
        return {"richtig": 1, "gesamt": 1}
    monkeypatch.setattr(api._community, "pruefstand_ergebnis", ergebnis, raising=False)
    api._pruefstand_fragen([{"kennung": "m-eins", "frage": "eins"}], runde={"id": "r1"}, erzwingen=True)
    assert len(versuche) == 3
