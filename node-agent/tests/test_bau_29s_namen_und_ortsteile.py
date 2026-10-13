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


def _t(titel, text):
    q = wissen.Quelle(f"wikipedia-{abs(hash(titel)) % 1000}", "wikipedia", f"Wikipedia: {titel} (CC BY-SA 4.0)", "https://de.wikipedia.org/wiki/x", "2026-09-29T00:00:00Z", len(text))
    return wissen.Treffer(q, text, 0.5)


def test_ortsteil_stellen_fallen_bei_einer_zahlenfrage_zum_ort_weg():
    namen = ["Berlin"]
    assert app_web._titel_name(_t("Berlin", "x")) == "Berlin"
    assert app_web._ortsteil_stelle(_t("Berlin-Friedenau", "Friedenau ist ein Ortsteil im Berliner Bezirk Tempelhof-Schöneberg mit 30.057 Einwohnern."), namen)
    assert app_web._ortsteil_stelle(_t("Mitte (Berlin)", "Mitte ist ein Ortsteil im gleichnamigen Bezirk."), namen)
    assert app_web._ortsteil_stelle(_t("Charlottenburg", "Charlottenburg ist ein Ortsteil im Berliner Bezirk Charlottenburg-Wilmersdorf."), namen)
    assert not app_web._ortsteil_stelle(_t("Berlin", "Berlin ist die Hauptstadt Deutschlands mit zwölf Bezirken."), namen)
    assert not app_web._ortsteil_stelle(_t("Potsdam", "Potsdam ist die Hauptstadt Brandenburgs und grenzt an Berlin."), namen)
    assert not app_web._ortsteil_stelle(_t("Wien", "Wien hat 23 Gemeindebezirke."), ["Salzburg", "Wien"])


def test_die_einleitung_kommt_auch_neben_einer_suche_im_netz_mit(tmp_path):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    salzburg, wien = _t("Salzburg", "Salzburg hat 155.416 Einwohner."), _t("Wien", "Wien hat 2.005.760 Einwohner.")

    class _Wiki:
        def bereit(self):
            return True

        def suchen(self, *a, **k):
            return []

        def einleitung(self, frage):
            return [salzburg, wien]

        def ausgabe(self):
            return "20260929"
    api._wiki = _Wiki()
    api._community.suchen = lambda *a, **k: ([], 0)
    netz = wissen.Treffer(wissen.Quelle("netz-1", "nachgeschaut", "Nachgeschaut: Größte Städte Österreichs", "https://example.org", "2026-09-30T00:00:00Z", 40),
                          "Wien ist mit 2,04 Millionen die größte Stadt Österreichs.", 0.9)
    api._nachschauen = lambda *a, **k: ([netz], "Im Netz nachgeschaut.")
    zusatz, _quellen, _n, _hinweis = api._mit_wissen_ohne_zeit([{"role": "user", "content": FRAGE}], privat_erlaubt=False, frisch=False)
    assert "Salzburg hat 155.416 Einwohner." in zusatz and "Wien hat 2.005.760 Einwohner." in zusatz and "2,04 Millionen" in zusatz
