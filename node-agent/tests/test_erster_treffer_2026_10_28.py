# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nachschauen as ns
import wissen

from test_wissen import _Antwort

FRAGE = "Seit wann gibt es den Europark in Salzburg"
LEXIKON = "https://lexikon.example/wiki/Europark_(Einkaufszentrum)"
TREFFER = [
    {"titel": "Europark (Einkaufszentrum) - Lexikon", "adresse": LEXIKON, "text": "Ihr Entwurf ging als Sieger aus einem Gutachterverfahren hervor. Die Eröffnung erfolgte"},
    {"titel": "Der Europark in Salzburg - Betreiber", "adresse": "https://betreiber.example/europark", "text": "Der Europark in Salzburg steht für Einkaufen."},
    {"titel": "Europark Salzburg: Meldungen", "adresse": "https://presse.example/europark", "text": "Seit Jahresbeginn mehr Besucher im Europark Salzburg."},
    {"titel": "Europark Salzburg wird erweitert", "adresse": "https://bezirk.example/europark", "text": "Seit Anfang 2026 wird am Europark Salzburg gebaut."},
    {"titel": "Europark Salzburg Shops", "adresse": "https://shops.example/europark", "text": "Über 130 Shops im Europark Salzburg."},
    {"titel": "Europark Salzburg Kulinarik", "adresse": "https://essen.example/europark", "text": "Essen im Europark Salzburg."},
]


def _oeffner(langsam: float = 0.0):
    gelesen = []

    def oeffner(req, timeout=0):
        url = req.full_url
        if url.endswith("/robots.txt"):
            return _Antwort(url, b"", "text/plain")
        gelesen.append(url)
        if url == LEXIKON:
            time.sleep(langsam)
            text = "<p>Europark Salzburg. Standort: Salzburg-Taxham. Eröffnung: 24. September 1997; Neueröffnung am 7. Oktober 2005. Geschäfte: 130.</p>"
        else:
            text = "<p>Seit Anfang 2026 wird am Europark Salzburg gebaut. Die Erweiterung bringt neue Shops und Gastronomie in Salzburg.</p>"
        return _Antwort(url, f"<html><head><title>{url}</title></head><body>{text}</body></html>".encode("utf-8"))
    return oeffner, gelesen


def test_die_fragewendung_ist_kein_wort_der_sache_in_keiner_sprache():
    for frage, rest in ((FRAGE, "gibt es den Europark in Salzburg"), ("Ab wann gilt in Österreich die Winterreifenpflicht?", "gilt in Österreich die Winterreifenpflicht?"),
                        ("Since when does the Eiffel Tower exist?", "does the Eiffel Tower exist?"), ("Depuis quand existe la tour Eiffel ?", "existe la tour Eiffel ?"),
                        ("Da quando esiste il Colosseo?", "esiste il Colosseo?"), ("¿Desde cuándo existe la Sagrada Familia?", "¿ existe la Sagrada Familia?"),
                        ("Bis wann gilt das Klimaticket?", "gilt das Klimaticket?"), ("Sinds wanneer bestaat het Rijksmuseum?", "bestaat het Rijksmuseum?")):
        assert " ".join(wissen.ohne_fragewendung(frage).split()) == rest, frage
    for frage in ("Seit welchem Jahr gibt es den Europark?", "Since what year has the Eiffel Tower existed?", "Depuis quelle année existe la tour Eiffel ?"):
        assert not {"seit", "since", "depuis", "jahr", "year", "anne"} & set(wissen.woerter(wissen.ohne_fragewendung(frage))), frage
    assert ns.richtung("Seit wann ist Wien die Hauptstadt von Österreich?") == "" and ns.richtung("Since when is Rome the capital of Italy?") == ""
    assert ns.richtung("Wann ist das nächste Spiel von Sturm Graz?") == "naechst"
    assert "seit" in wissen.woerter(wissen.ohne_fragewendung("Was hat sich seit dem Umbau geändert?"))
    assert ns.suchbegriffe_regel(FRAGE) == "Seit Europark Salzburg"


def test_die_reihung_zaehlt_seit_nicht_mehr_als_wort_der_frage():
    reihe = ns.treffer_reihen(TREFFER, FRAGE, heute=date(2026, 10, 28))
    adressen = [t["adresse"] for t in reihe]
    assert adressen.index("https://betreiber.example/europark") < adressen.index("https://bezirk.example/europark")


def test_der_erste_treffer_der_suche_wird_gelesen_und_steht_vorn():
    oeffner, gelesen = _oeffner()
    n = ns.Nachschauer(suche_fn=lambda q, **k: TREFFER, seiten_oeffner=oeffner)
    erg, gelesen_adr, _ = n.suche_runde([ns.suchbegriffe_regel(FRAGE)], FRAGE, heute=date(2026, 10, 28))
    assert gelesen_adr[0] == LEXIKON
    seiten = [e for e in erg if not e.titel.startswith("Suchergebnisse")]
    assert seiten[0].adresse == LEXIKON and "24. September 1997" in seiten[0].text


def test_auf_einen_langsamen_ersten_treffer_wartet_die_runde():
    oeffner, gelesen = _oeffner(langsam=ns.RUNDE_NACHLAUF_S + 1.0)
    n = ns.Nachschauer(suche_fn=lambda q, **k: TREFFER, seiten_oeffner=oeffner)
    erg, gelesen_adr, _ = n.suche_runde([ns.suchbegriffe_regel(FRAGE)], FRAGE, heute=date(2026, 10, 28))
    assert LEXIKON in gelesen_adr and any("24. September 1997" in e.text for e in erg)


def test_mit_zeitrichtung_reiht_weiter_die_reihung():
    oeffner, _gelesen = _oeffner()
    treffer = [{"titel": "Saison 2024/25", "adresse": "https://alt.example/2024", "text": "Spielplan 2024/25 am 12.05.2025 und 19.05.2025"}] + TREFFER[1:]
    n = ns.Nachschauer(suche_fn=lambda q, **k: treffer, seiten_oeffner=oeffner)
    _erg, gelesen_adr, _ = n.suche_runde(["Europark Salzburg Termine"], "Wann ist im Europark Salzburg als Nächstes ein Markt?", heute=date(2026, 10, 28))
    assert not gelesen_adr or gelesen_adr[0] != "https://alt.example/2024"
