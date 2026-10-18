# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app_core
import app_web
import belege
import community

HEUTE = date(2026, 9, 29)
FRAGE = "Wieviel Einwohner hat Innsbruck und Bremen vergleiche"
QUELLE = ("Innsbruck ist die Landeshauptstadt Tirols und hat 132.493 Einwohner (Stand 1. Jänner 2025). "
          "Die Freie Hansestadt Bremen hat 569.396 Einwohner.")
ANTWORT = ("Ich schaue noch einmal nach.\n---\nNachgeschaut:\nInnsbruck: 132.000 Einwohner.\nBremen: 570.000 Einwohner.\n---\n"
           "Vergleich:\nBremen ist also etwa 4,3-mal größer als Innsbruck.")


def _quellen(text=QUELLE):
    return [{"nummer": 1, "titel": "Wikipedia", "art": "seite", "text": text}]


def test_ein_geruest_aus_ueberschriften_und_trennlinien_ist_keine_antwort():
    rest, raus = belege.saetze_streichen(ANTWORT, lambda s: "Einwohner." in s)
    assert raus == ["Innsbruck: 132.000 Einwohner.", "Bremen: 570.000 Einwohner."]
    assert "Nachgeschaut:" not in rest and "---" not in rest
    assert rest == "Ich schaue noch einmal nach.\nVergleich:\nBremen ist also etwa 4,3-mal größer als Innsbruck."
    rest, _ = belege.saetze_streichen("Nachgeschaut:\nInnsbruck: 132.000 Einwohner.\n---\nVergleich:", lambda s: "Einwohner" in s)
    assert rest == "Das weiß ich noch nicht."
    assert belege.geruest_bereinigen("Vergleich:\n---") == "" and belege.geruest_bereinigen("Vergleich:\nBremen ist größer.") == "Vergleich:\nBremen ist größer."
    assert belege.saetze_streichen("Kurz:\nJa.", lambda s: False) == ("Kurz:\nJa.", [])


def test_zahlenfrage_erkannt():
    assert belege.zahlenfrage(FRAGE) and belege.zahlenfrage("Wann wurde Bremen gegründet?") and belege.zahlenfrage("Was kostet der Eintritt?")
    assert not belege.zahlenfrage("Wer ist Bürgermeister von Innsbruck?") and not belege.zahlenfrage("Schreib mir eine Karte für Oma")


def test_bei_einer_zahlenfrage_antwortet_das_modell_streng_neu_statt_ohne_zahlen():
    auftraege = []

    def nochmal(extra):
        auftraege.append(extra)
        return "Innsbruck hat 132.493 Einwohner, Bremen 569.396 Einwohner. Bremen ist also etwa 4,3-mal so groß wie Innsbruck."
    t, notizen = app_web.belege_anwenden(ANTWORT, FRAGE, QUELLE, _quellen(), heute=HEUTE, nochmal=nochmal)
    assert t.startswith("Innsbruck hat 132.493 Einwohner") and len(auftraege) == 1 and "132.000" in auftraege[0]
    assert any("neu geantwortet" in n for n in notizen)
    t, _ = app_web.belege_anwenden(ANTWORT, FRAGE, QUELLE, _quellen(), heute=HEUTE, nochmal=lambda e: "Innsbruck hat 140.000 Einwohner.")
    assert t == "Das weiß ich noch nicht."
    auftraege.clear()
    t, _ = app_web.belege_anwenden("Kompany kam 2023 von Burnley. Bremen liegt an der Weser.", "Wer trainiert Bayern?", QUELLE, _quellen(), heute=HEUTE,
                                   nochmal=lambda e: auftraege.append(e) or "Kompany kam 2023 von Burnley.")
    assert len(auftraege) == 1 and t == "Das weiß ich noch nicht."
    t, _ = app_web.belege_anwenden("Bremen hat 569.396 Einwohner. Bremen liegt an der Weser. Kompany kam 2023 von Burnley. Bremen ist eine Hansestadt.",
                                   "Erzähl mir was über Bremen", QUELLE, _quellen(), heute=HEUTE, nochmal=lambda e: "Kompany kam 2023 von Burnley.")
    assert t.startswith("Bremen hat 569.396 Einwohner.") and "Kompany" not in t


def test_der_teilgeber_schickt_den_ganzen_entwurf_am_schluss_und_nie_zweimal_dasselbe():
    gesendet = []
    g = app_web._Teilgeber(gesendet.append, abstand_s=3600)
    for stueck in ("In", "nsbruck hat 132.493 ", "Einwohner."):
        g.token(stueck)
    assert gesendet == []
    g.schluss()
    g.schluss()
    assert gesendet == ["Innsbruck hat 132.493 Einwohner."]
    kaputt = app_web._Teilgeber(lambda t: (_ for _ in ()).throw(RuntimeError("weg")), abstand_s=0)
    kaputt.token("**Bremen**")
    assert kaputt.gesendet == "Bremen"


def test_trennlinien_sind_markdown_und_verschwinden():
    assert app_web.ohne_markdown("Ich schaue nach.\n---\nNachgeschaut:\n***\nBremen ist größer.") == "Ich schaue nach.\nNachgeschaut:\nBremen ist größer."
    assert app_web.ohne_markdown("- eins\n- zwei") == "– eins\n– zwei"


def test_fehlgeschlagene_weitergaben_werden_gezaehlt(tmp_path):
    c = community.Community(tmp_path, adresse="https://127.0.0.1:1", oeffner=lambda r, timeout: (_ for _ in ()).throw(OSError("zu")))
    assert c.teil_fehler == 0
    c.antwort_teil("auftrag-1", "In")
    c.antwort_schritt("auftrag-1", "schreibt die Antwort …")
    assert c.teil_fehler == 2


def test_neuerungen_fuer_den_naechsten_bau_stehen():
    import neuerungen
    assert any("leeren Überschriften" in s for s in neuerungen.NEUERUNGEN["2026-09-29f"])
    assert app_core.APP_BUILD >= "2026-09-29f"
