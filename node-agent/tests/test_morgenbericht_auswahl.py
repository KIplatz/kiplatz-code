# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auswahl
import morgenbericht as mb
import nachschauen

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


class _Nachschauer:
    def __init__(self, *, wetter_kaputt=False):
        self.kaputt = wetter_kaputt
        self.auftraege = []

    def wetter(self, a):
        self.auftraege.append(a)
        if self.kaputt:
            raise nachschauen.NachschauError("NACHSCHAU_ORT", "den Ort „Nirgendwo“ kenne ich nicht; bitte anders schreiben")
        return nachschauen.Ergebnis("wetter", "Wetter heute in Gmunden", "https://x", "Frage: x\nWettervorhersage für Gmunden (Österreich), nachgeschaut bei Open-Meteo am 20.09.2026 um 05:00 UTC:\nHeute, Samstag 20.09.2026: sonnig, Höchsttemperatur 21 °C, Tiefsttemperatur 9 °C, kein Regen, Wind bis 12 km/h.\nMorgen, Sonntag 21.09.2026: wechselnd, Höchsttemperatur 18 °C, Tiefsttemperatur 10 °C, Regen 2,1 mm, Wind bis 20 km/h.\nÜbermorgen, Montag 22.09.2026: bedeckt.", "x", "Wetter")

    def schlagzeilen(self, a):
        self.auftraege.append(a)
        return nachschauen.Ergebnis("schlagzeilen", "Schlagzeilen Österreich", "https://y", "Frage: y\nSchlagzeilen Österreich von ORF, nachgeschaut am 20.09.2026 um 05:00 UTC:\n\n1. Erste Meldung: mit Doppelpunkt (ORF)\nhttps://orf.at/1\nmit Beschreibung\n\n2. Zweite Meldung (news.at)\nhttps://news.at/2\n\n3. Dritte: a: b (ORF)\nhttps://orf.at/3\n\n4. Vierte (ORF)\nhttps://orf.at/4\n\n5. Fünfte (ORF)\nhttps://orf.at/5\n\n6. Sechste (ORF)\nhttps://orf.at/6", "y", "Schlagzeilen")


def test_faellig_once_a_day_after_the_chosen_time():
    e = {"morgen_an": True, "morgen_zeit": "07:00"}
    assert mb.faellig(e, datetime(2026, 9, 20, 6, 59)) is False
    assert mb.faellig(e, datetime(2026, 9, 20, 7, 0)) is True
    assert mb.faellig({**e, "morgen_zuletzt": "2026-09-20"}, datetime(2026, 9, 20, 9, 0)) is False
    assert mb.faellig({**e, "morgen_zuletzt": "2026-09-19"}, datetime(2026, 9, 20, 9, 0)) is True
    assert mb.faellig({"morgen_an": False, "morgen_zeit": "07:00"}, datetime(2026, 9, 20, 9, 0)) is False
    assert mb.einstellung_lesen({"morgen_zeit": "kaputt"})["zeit"] == "07:00" and mb.einstellung_lesen({})["vorlesen"] is True


def test_report_has_date_weather_for_today_and_tomorrow_and_five_headlines():
    n = _Nachschauer()
    text, fehler = mb.erstellen(n, ort="Gmunden", jetzt=datetime(2026, 9, 20, 7, 0))
    assert text.startswith("Guten Morgen. Heute ist Sonntag, der 20. September 2026.")
    assert "Wetter in Gmunden:\n\n**Heute, Samstag 20.09.2026:** sonnig" in text and "Wind bis 12 km/h.\n\n**Morgen, Sonntag 21.09.2026:** wechselnd" in text and "Übermorgen" not in text
    assert ("Schlagzeilen aus Österreich:\n\n**Erste Meldung: mit Doppelpunkt**\n[Zum Beitrag auf ORF.at](https://orf.at/1)\n\n"
            "**Zweite Meldung**\n[Zum Beitrag auf news.at](https://news.at/2)\n\n**Dritte: a: b**\n[Zum Beitrag auf ORF.at](https://orf.at/3)\n\n"
            "**Vierte**\n[Zum Beitrag auf ORF.at](https://orf.at/4)\n\n**Fünfte**\n[Zum Beitrag auf ORF.at](https://orf.at/5)") in text and "Sechste" not in text
    assert "(ORF)" not in text and "\nhttps://" not in text
    assert mb.links(text)[0] == {"nummer": 1, "titel": "Erste Meldung: mit Doppelpunkt", "adresse": "https://orf.at/1"} and len(mb.links(text)) == 5
    gesprochen = mb.zum_vorlesen(text)
    assert "https://" not in gesprochen and "Zum Beitrag" not in gesprochen and "**" not in gesprochen and "Erste Meldung: mit Doppelpunkt\n\nZweite" in gesprochen
    assert fehler == [] and n.auftraege[0].ort == "Gmunden" and n.auftraege[0].tag == 0
    assert mb.seite("https://www.tagesschau.de/x") == "tagesschau.de" and mb.seite("https://example.org/y") == "example.org"


def test_report_without_place_and_with_a_failing_weather_stays_useful():
    text, fehler = mb.erstellen(_Nachschauer(), ort="", jetzt=datetime(2026, 9, 21, 7, 0))
    assert "Trag unter Einstellungen einen Ort ein" in text and "Schlagzeilen aus Österreich:" in text and fehler == []
    text, fehler = mb.erstellen(_Nachschauer(wetter_kaputt=True), ort="Nirgendwo", jetzt=datetime(2026, 9, 21, 7, 0))
    assert "Wetter in Nirgendwo: gerade nicht abrufbar." in text and fehler and fehler[0].startswith("Wetter:")


def test_window_settings_and_api_for_the_morning_report(tmp_path, monkeypatch):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    monkeypatch.setattr(api, "_nachschauer", _Nachschauer())
    gesprochen = []
    monkeypatch.setattr(api, "_vorlesen_still", lambda text: gesprochen.append(text))
    r = api.morgenbericht_setzen(True, "06:30", "Gmunden", True)
    assert r["ok"] and r["daten"]["an"] and r["daten"]["zeit"] == "06:30" and r["daten"]["ort"] == "Gmunden"
    assert api.zustand()["daten"]["morgenbericht"]["zeit"] == "06:30"
    r = api.morgenbericht_jetzt()
    assert r["ok"] and r["daten"]["gespraech"]["titel"].startswith("Morgenbericht") and "Guten Morgen" in r["daten"]["text"]
    assert gesprochen and "Guten Morgen" in gesprochen[0]
    assert api._ki.einstellung()["morgen_zuletzt"] == datetime.now().strftime("%Y-%m-%d")
    assert api._morgenbericht_pruefen() is False
    erste = r["daten"]["gespraech"]["kennung"]
    g = api.gespraech_laden(erste)["daten"]
    assert all(n.get("intern") for n in g["nachrichten"])
    assert 'id="morgen-an"' in HTML and "morgenbericht_setzen" in HTML and "morgenbericht_jetzt" in HTML
    r = api.morgenbericht_setzen(True, "06:30", "Linz", True)
    zweite = r["daten"].get("gespraech")
    assert r["ok"] and zweite and zweite != erste and r["daten"]["ort"] == "Linz"
    liste = api.gespraeche_liste()["daten"]
    liste = liste["liste"] if isinstance(liste, dict) else liste
    assert [e["titel"] for e in liste].count("Morgenbericht " + datetime.now().strftime("%d.%m.")) == 1 and erste not in [e["kennung"] for e in liste]
    assert "Wetter in Linz" in api.gespraech_laden(zweite)["daten"]["nachrichten"][0]["text"]
    r = api.morgenbericht_setzen(True, "06:30", "Linz", True)
    assert r["ok"] and "gespraech" not in r["daten"]
    geoeffnet = []
    monkeypatch.setattr("webbrowser.open", lambda a: geoeffnet.append(a))
    assert api.link_oeffnen("https://orf.at/stories/1/")["ok"] and geoeffnet == ["https://orf.at/stories/1/"]
    assert not api.link_oeffnen("http://orf.at/")["ok"] and not api.link_oeffnen("javascript:alert(1)")["ok"] and geoeffnet == ["https://orf.at/stories/1/"]
    assert 'class="beitrag"' in HTML and "link_oeffnen" in HTML


def test_auswahl_holen_restores_the_clipboard_and_quotes_the_text():
    ablage = {"text": "alter Inhalt"}
    gedrueckt = []

    def kopieren():
        gedrueckt.append(1)
        ablage["text"] = "  markierter   Text\naus Word "
    text = auswahl.auswahl_holen(lesen=lambda: ablage["text"], schreiben=lambda t: ablage.__setitem__("text", t), kopieren=kopieren, warten=lambda s: None)
    assert text == "markierter Text aus Word" and gedrueckt == [1] and ablage["text"] == "alter Inhalt"
    assert auswahl.als_vorgabe(text) == "„markierter Text aus Word“\n\n" and auswahl.als_vorgabe("  ") == ""
    ablage["text"] = "alter Inhalt"
    assert auswahl.auswahl_holen(lesen=lambda: ablage["text"], schreiben=lambda t: ablage.__setitem__("text", t), kopieren=lambda: None, warten=lambda s: None) == ""
    assert ablage["text"] == "alter Inhalt"
    assert auswahl.auswahl_holen(lesen=lambda: "x", schreiben=lambda t: None, kopieren=kopieren, warten=lambda s: None, eigenes_fenster=True) == ""
    def kaputt():
        raise OSError("kein Zugriff")
    assert auswahl.auswahl_holen(lesen=kaputt, schreiben=kaputt, kopieren=kaputt, warten=lambda s: None) == ""
    assert "auswahl_uebernehmen" in HTML or "vorbelegen" in HTML
