# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import wissen

HEUTE = date(2026, 9, 30)
FRAGE = "Einwohner Salzburg und Wien vergleichen"
QUELLE = "Salzburg hat 155.416 Einwohner (Stand 2025). Wien hat 2.005.760 Einwohner und ist die Hauptstadt Österreichs."


def _q(text=QUELLE):
    return [{"nummer": 1, "titel": "Wikipedia", "art": "wikipedia", "text": text}]


def test_namen_fehlen_findet_den_ausgelassenen_ort():
    assert app_web.namen_fehlen(FRAGE, "Wien hat 2.005.760 Einwohner.") == ["Salzburg"]
    assert app_web.namen_fehlen(FRAGE, "Salzburg hat 155.416 Einwohner, Wien 2.005.760.") == []
    assert app_web.namen_fehlen("Einwohner in Berlin", "Friedenau hat 30.057 Einwohner.") == []


def test_die_zweite_fassung_nennt_beide_sonst_sagt_es_das_programm():
    auftraege = []

    def nochmal(extra):
        auftraege.append(extra)
        return "Salzburg hat 155.416 Einwohner, Wien hat 2.005.760 Einwohner. Wien ist also rund 13-mal so groß."
    t, notizen = app_web.belege_anwenden("Wien hat 2.005.760 Einwohner.", FRAGE, QUELLE, _q(), heute=HEUTE, nochmal=nochmal)
    assert t.startswith("Salzburg hat 155.416 Einwohner") and "Salzburg" in auftraege[0] and any("ließ einen genannten Namen aus" in n for n in notizen)
    t, notizen = app_web.belege_anwenden("Wien hat 2.005.760 Einwohner.", FRAGE, QUELLE, _q(), heute=HEUTE, nochmal=lambda e: "Wien hat 2.005.760 Einwohner.")
    assert t == "Wien hat 2.005.760 Einwohner.\n\nZu Salzburg habe ich in meinen Quellen keine sichere Zahl gefunden."
    t, _ = app_web.belege_anwenden("Wien hat 2.005.760 Einwohner.", FRAGE, QUELLE, _q(), heute=HEUTE)
    assert t.endswith("Zu Salzburg habe ich in meinen Quellen keine sichere Zahl gefunden.")
    beide = "Salzburg hat 155.416 Einwohner, Wien 2.005.760 Einwohner."
    assert app_web.belege_anwenden(beide, FRAGE, QUELLE, _q(), heute=HEUTE)[0] == beide
    assert app_web.belege_anwenden("Nimm das günstigere.", "Vergleiche mir zwei Handys für meine Tochter", "", [], heute=HEUTE)[0] == "Nimm das günstigere."
