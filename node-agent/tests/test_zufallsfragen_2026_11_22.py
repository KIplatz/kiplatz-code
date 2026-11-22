# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen
import schriftstueck


def test_erklaerfrage_ueber_das_wetter_ist_keine_vorhersage():
    for f in ("Was ist der Unterschied zwischen Wetter und Klima?", "Wie funktioniert eine Wettervorhersage?",
              "Warum ist die Wettervorhersage oft falsch?", "Was bedeutet Aprilwetter?", "Why is the weather forecast often wrong?",
              "Woher kommt das Wort Wetter?"):
        a = nachschauen.erkennen(f)
        assert a is None or a.art != "wetter", f
    for f, ort in (("Wie wird das Wetter morgen in Linz?", "Linz"), ("Warum regnet es heute so viel in Wien?", "Wien"), ("Wetter Gmunden", "Gmunden"),
                   ("Was ist das Wetter heute?", ""), ("Wie ist das Wetter?", "")):
        a = nachschauen.erkennen(f)
        assert a is not None and a.art == "wetter" and a.ort == ort, f


def test_gedicht_oder_witz_mit_thema_ohne_rueckfrage():
    for f in ("Schreib mir ein kurzes Gedicht über den Herbst.", "Schreib mir einen kurzen Witz über Computer.",
              "Erzähl mir eine Gutenachtgeschichte von einem Drachen", "Schreib einen Reim zum Thema Schnee", "Schreib ein Haiku über den Regen"):
        assert schriftstueck.erkennen(f) is None, f
    for f in ("Schreib ein Gedicht für sie.", "Schreib ein Gedicht für meine Oma zum 80er Geburtstag", "Schreib mir eine Geschichte",
              "Schreib einen Text über unsere Firma", "Schreib eine Kündigung."):
        assert schriftstueck.erkennen(f) is not None, f


def test_fundstelle_zu_anderem_thema_deckt_die_frage_nicht():
    import app_web
    import wissen
    frage = "Erkläre mir den Unterschied zwischen Brutto und Netto."
    bio = wissen.Treffer(wissen.Quelle("b1", "wikipedia", "Biodiesel", "", "2026-09-26T00:00:00Z", 100),
                         "Der Unterschied zwischen Brutto- und Netto-Energie: brutto die Gesamtenergie, netto nach Abzug der Produktion.", 2.0)
    mass = wissen.Treffer(wissen.Quelle("b2", "wikipedia", "Bestimmtheitsmaß", "", "2026-09-26T00:00:00Z", 100),
                          "Zwischen brutto und netto unterscheidet man bei Außenhandelsquoten.", 1.5)
    assert not app_web.Api._deckt_ab(frage, [bio, mass])
    passt = wissen.Treffer(wissen.Quelle("b3", "wikipedia", "Bruttolohn", "", "2026-09-26T00:00:00Z", 100),
                           "Brutto ist der Lohn vor Abzug von Steuern und Sozialversicherung, netto ist, was danach übrig bleibt; der Unterschied sind die Abgaben.", 2.0)
    assert app_web.Api._deckt_ab(frage, [bio, passt])
    q = wissen.Quelle("w1", "wikipedia", "Winterreifen", "", "2026-10-01T00:00:00Z", 100)
    assert app_web.Api._deckt_ab("Wann muss ich in Österreich auf Winterreifen wechseln?",
                                 [wissen.Treffer(q, "Winterreifen sind in Österreich bei winterlichen Verhältnissen vorgeschrieben, wechseln sollte man im Herbst.", 2.0)])


def test_fable_zu_22a_schreibauftraege_bleiben():
    for f in ("Schreib eine Beschwerde über die verspätete Lieferung.", "Schreib einen Brief an die Versicherung über den Wasserschaden.",
              "Schreib eine Einladung zur Versammlung.", "Schreib eine witzige Einladung zum Sommerfest.",
              "Schreib einen Bericht über die Geschichte der Firma.", "Schreib ein Gedicht für Oma zum Muttertag",
              "Schreib ein Gedicht für Anna zum Namenstag"):
        assert schriftstueck.erkennen(f) is not None, f


def test_fable_zu_22a_wetter_bleibt_wetter():
    for f in ("Was ist das Wetter?", "Wie ist das Wetter?"):
        a = nachschauen.erkennen(f)
        assert a is not None and a.art == "wetter", f
    for f in ("Wie genau ist eine Wettervorhersage?", "Wie wird eine Wettervorhersage erstellt?"):
        a = nachschauen.erkennen(f)
        assert a is None or a.art != "wetter", f


def test_fable_zu_22a_titel():
    import app_web
    import wissen
    eu = wissen.Treffer(wissen.Quelle("e1", "wikipedia", "Europäische Union", "", "2026-09-26T00:00:00Z", 100), "Die EU ist ein Staatenverbund.", 2.0)
    assert app_web.Api._titel_trifft(set(wissen.woerter("Was ist die EU?")), eu)
    erk = wissen.Treffer(wissen.Quelle("e2", "wikipedia", "Erklärung der Menschenrechte", "", "2026-09-26T00:00:00Z", 100), "brutto netto", 2.0)
    assert not app_web.Api._titel_trifft(set(wissen.woerter("Erkläre mir den Unterschied zwischen Brutto und Netto.")), erk)


def test_fable_zu_22a_hoefliche_form():
    for f in ("Kannst du mir ein Gedicht über den Herbst schreiben?", "Ich hätte gern einen Witz über Computer",
              "Schreib mir mal ein Gedicht über den Winter", "Schreib ein kleines, lustiges Gedicht über den Frühling"):
        assert schriftstueck.erkennen(f) is None, f
    assert schriftstueck.erkennen("Kannst du mir eine Kündigung schreiben?") is not None
