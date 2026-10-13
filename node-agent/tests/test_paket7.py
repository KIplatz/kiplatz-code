# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import schriftstueck
import skills
import themen
import wissen

from test_app_web import _api

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


def test_plans_and_recommendations_get_the_check_for_missing_details():
    for f in ("Plane mir eine Reise nach Rom", "Empfiehl mir ein Buch für den Urlaub", "Hilf mir bei der Steuererklärung", "Vergleich die beiden Angebote für mich"):
        a = schriftstueck.erkennen(f)
        assert a is not None and a.art == "Vorhaben" and a.offen, f
    for f in ("Was ist ein Plan?", "Wie wird das Wetter?", "Wann war die Planung des Doms fertig?", "Wer ist Maria?"):
        assert schriftstueck.erkennen(f) is None, f
    a = schriftstueck.erkennen("Schreib eine Rechnung")
    assert a is not None and not a.offen
    v = schriftstueck.erkennen("Plane mir eine Reise")
    assert "höchstens zwei" in schriftstueck.vorspann_fragen(v) and "erledige das Vorhaben sofort" in schriftstueck.vorspann_fragen(v)
    assert "Annahme:" in schriftstueck.vorspann_schreiben(v)
    r = schriftstueck.runde([{"role": "user", "content": "Plane mir eine Reise"}, {"role": "assistant", "content": schriftstueck.VORSPANN + ":\n- Wohin?"}, {"role": "user", "content": "nach Rom, zu zweit"}])
    assert r is not None and r[0].offen and r[1] == "schreiben"


def test_question_completion_asks_the_model_and_hands_back_text(tmp_path):
    api, fake, _ = _api(tmp_path)
    r = api.frage_vervollstaendigen("schreib eine absage")
    assert r["ok"] and r["daten"]["text"] == "Servus, Huber." and r["daten"]["vorher"] == "schreib eine absage"
    assert fake.fragen and "eckigen Klammern" in fake.fragen[-1][-1]["content"] and "schreib eine absage" in fake.fragen[-1][-1]["content"]
    assert not api.frage_vervollstaendigen("")["ok"]
    assert 'id="btn-vervollstaendigen"' in HTML and "frage_vervollstaendigen" in HTML


def test_setup_questions_go_into_memory_place_and_topics(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api._nachschauer, "land_fuer_ort", lambda ort: "at")
    st = api.zustand()["daten"]["kennenlernen"]
    assert st["gemacht"] is False and st["themen"] == []
    r = api.einrichtung_speichern("Maria", "Gmunden", "Pferde, Garten; Steuern, pferde")
    assert r["ok"] and r["daten"]["gemacht"] and r["daten"]["name"] == "Maria" and r["daten"]["ort"] == "Gmunden" and r["daten"]["themen"] == ["Pferde", "Garten", "Steuern"]
    texte = [e["text"] for e in api._gedaechtnis.liste()]
    assert any("Maria" in t for t in texte) and any("Gmunden" in t for t in texte)
    assert not any("interessiere mich" in t for t in texte)
    assert api.morgenbericht_stand()["ort"] == "Gmunden" and api.morgenbericht_stand()["land"] == "at"
    assert api.zustand()["daten"]["kennenlernen"]["gemacht"] is True
    api2, _f2, _ = _api(tmp_path / "zwei")
    assert api2.einrichtung_spaeter()["ok"] and api2.einrichtung_stand()["gemacht"] and api2._gedaechtnis.liste() == []
    assert 'id="einrichtung-card"' in HTML and "einrichtung_speichern" in HTML and "einrichtung_spaeter" in HTML


class _Community:
    def __init__(self):
        self.gefragt = []

    def suchen(self, frage, *, n=4, vektor=None, abbrechen=None):
        self.gefragt.append(frage)
        q = wissen.Quelle("abc123def456", "seite", f"Artikel über {frage}", f"https://de.wikipedia.org/wiki/{frage}", "2026-09-23T00:00:00Z", 900)
        privat = wissen.Quelle("privat000001", "dokument", "Privat", "", "2026-09-23T00:00:00Z", 100)
        return [wissen.Treffer(q, f"{frage} sind Tiere, die seit Jahrtausenden mit Menschen leben. " * 3, 1.0),
                wissen.Treffer(q, f"Die Haltung von {frage} braucht Platz, Zeit und Wissen über Futter. " * 3, 0.9),
                wissen.Treffer(privat, "nie", 0.5)], 3


def test_own_topics_are_gathered_privately_once_a_day(tmp_path):
    sp = wissen.Wissensspeicher(tmp_path)
    com = _Community()
    uhr = {"t": 1000.0}
    einst = {"meine_themen": ["Pferde", "Garten"]}
    t = themen.Themen(lambda: einst, lambda: com, sp, jetzt=lambda: uhr["t"])
    assert t.faellig()
    assert t.sammeln() == 4 and com.gefragt == ["Pferde", "Garten"]
    assert not t.faellig()
    uhr["t"] += themen.TAKT_S
    assert t.faellig() and t.sammeln() == 0
    quellen = [q for q, _ in sp.alle()]
    assert len(quellen) == 4 and all(q.art == "thema" and q.privat and q.gueltig_bis for q in quellen)
    assert all(q.adresse.startswith("https://de.wikipedia.org/wiki/") and "#" in q.adresse for q in quellen)
    assert sp.suchen("Pferde Futter", privat_erlaubt=False) == []
    assert sp.suchen("Pferde Futter")[0].quelle.art == "thema"
    assert t.stand()["im_speicher"] == 4 and t.stand()["themen"] == ["Pferde", "Garten"]
    einst["meine_themen"] = []
    assert not t.faellig()


def test_skill_templates_are_shipped_and_can_be_adopted(tmp_path):
    v = skills.vorlagen()
    namen = [x.name for x in v]
    assert len(v) == 10 and "brief-ans-amt" in namen and "einkaufsliste" in namen and all(x.beschreibung and len(x.text) > 200 for x in v)
    api, _fake, _ = _api(tmp_path)
    r = api.skill_vorlagen()
    assert r["ok"] and len(r["daten"]["vorlagen"]) == 10 and r["daten"]["meine"] == []
    r = api.skill_vorlage_uebernehmen("brief-ans-amt")
    assert r["ok"] and r["daten"]["skill"]["name"] == "brief-ans-amt" and [b["name"] for b in api._kiste.liste()] == ["brief-ans-amt"]
    assert api.skill_vorlagen()["daten"]["meine"] == ["brief-ans-amt"]
    assert not api.skill_vorlage_uebernehmen("gibtsnicht")["ok"]
    assert 'id="skill-vorlagen"' in HTML and "skill_vorlage_uebernehmen" in HTML
