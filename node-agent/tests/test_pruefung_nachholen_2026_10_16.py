# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import app_web


def _lauf(tmp_path, monkeypatch, durch):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api, "_ki_starten_blockierend", lambda: None)
    monkeypatch.setattr(api, "PRUEFSTAND_WEGE", (), raising=False)
    monkeypatch.setattr(api._core, "run_state", lambda: app_web.node_local_state.RunState.ACTIVE)
    monkeypatch.setattr(api, "_jemand_am_pc", lambda: False)
    gemeldet: dict = {}
    monkeypatch.setattr(api._community, "pruefstand_ergebnis", lambda antworten, wege: gemeldet.update(a=antworten) or {"richtig": 0, "gesamt": len(antworten)},
                        raising=False)
    zaehler: dict = {}

    def antwort(nachrichten, auszuege, fuer, **kw):
        frage = nachrichten[-1]["content"]
        zaehler[frage] = zaehler.get(frage, 0) + 1
        if not durch(frage, zaehler[frage]):
            api._suche_ausgefallen = True
            return f"{frage}: weiß ich nicht, Suche nicht durchgekommen", {}
        return f"{frage}: mit Suche", {}
    monkeypatch.setattr(api, "_antwort_fuer_mitglied", antwort)
    fragen = [{"kennung": f"m-{k}", "frage": k} for k in ("eins", "zwei", "drei")]
    api._pruefstand_fragen(fragen, erzwingen=True)
    return gemeldet["a"], zaehler


def test_a_question_without_search_comes_again_at_the_end_and_its_new_answer_counts(tmp_path, monkeypatch):
    antworten, zaehler = _lauf(tmp_path, monkeypatch, lambda frage, mal: frage != "zwei" or mal > 1)
    assert [a["kennung"] for a in antworten] == ["m-eins", "m-zwei", "m-drei"]
    assert antworten[1]["antwort"] == "zwei: mit Suche" and zaehler == {"eins": 1, "zwei": 2, "drei": 1}


def test_when_the_search_fails_again_the_first_answer_stays_and_nothing_loops(tmp_path, monkeypatch):
    antworten, zaehler = _lauf(tmp_path, monkeypatch, lambda frage, mal: frage != "drei")
    assert len(antworten) == 3 and antworten[2]["antwort"].startswith("drei: weiß ich nicht")
    assert zaehler["drei"] == 2


def test_a_failed_test_search_marks_the_question(tmp_path, monkeypatch):
    class _Rechen:
        phase = "prueft_selbst"
        vorrang = None

    class _Community:
        def websuche(self, frage, n=8, **kw):
            raise app_core.AppError("SUCHE_GESCHONT", "geschont")

    class _Api:
        _websuche = app_web.Api._websuche

    api = _Api()
    api._rechen, api._community = _Rechen(), _Community()
    api._nacht_memo, api._memo_frage, api._memo_nutzen, api._mess_bremse = None, "", False, True
    api._mess_suche_budget = lambda vorrang: None
    api._suche_ausgefallen = False
    try:
        api._websuche("Dachstein")
    except app_core.AppError:
        pass
    assert api._suche_ausgefallen is True
    api._mess_bremse, api._rechen.phase, api._suche_ausgefallen = False, "", False
    try:
        api._websuche("meine Frage")
    except app_core.AppError:
        pass
    assert api._suche_ausgefallen is False


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


def test_the_report_is_sent_up_to_three_times_before_the_night_is_lost(tmp_path, monkeypatch):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api, "_ki_starten_blockierend", lambda: None)
    monkeypatch.setattr(api, "PRUEFSTAND_WEGE", (), raising=False)
    monkeypatch.setattr(api._core, "run_state", lambda: app_web.node_local_state.RunState.ACTIVE)
    monkeypatch.setattr(api, "_antwort_fuer_mitglied", lambda nachrichten, auszuege, fuer, **kw: ("eine Antwort", {}))
    api._mess_schlafen = lambda s: None
    versuche = []

    def ergebnis(antworten, wege):
        versuche.append(1)
        if len(versuche) < 3:
            raise app_core.AppError("SERVER", "gerade nicht erreichbar")
        return {"richtig": 1, "gesamt": 1}
    monkeypatch.setattr(api._community, "pruefstand_ergebnis", ergebnis, raising=False)
    api._pruefstand_fragen([{"kennung": "m-eins", "frage": "eins"}], erzwingen=True)
    assert len(versuche) == 3
