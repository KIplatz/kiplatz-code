# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import einkauf
import nachschauen
import wissen


def _seite(adresse, titel, text):
    return nachschauen.Ergebnis("suche", f"Nachgeschaut: {titel}", adresse, text, "2026-11-01T00:00:00Z", "im Internet gesucht")


@pytest.mark.parametrize("sache,pflicht,eins,worte", [
    ("CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL", ("255/55", "r20"), ("ts870p",), ()),
    ("Continental WinterContact TS 870 195/65 R15 91T", ("195/65", "r15"), ("ts870",), ()),
    ("Samsung Galaxy S25 256GB", ("256gb",), ("s25",), ()),
    ("iPhone 16 128 GB", ("128gb",), ("iphone16",), ()),
    ("Nintendo Switch 2", (), ("switch2",), ()),
    ("Sony PS5 Pro", (), ("ps5",), ("pro",)),
    ("De'Longhi Magnifica S ECAM 22.110.B", (), ("22110",), ()),
])
def test_variante(sache, pflicht, eins, worte):
    v = einkauf.variante(sache)
    assert (v.pflicht, v.eins, v.worte) == (pflicht, eins, worte)


@pytest.mark.parametrize("frage,sache", [
    ("Zeig mir günstigere Angebote aus Deutschland", ""),
    ("Wo bekomme ich den Michelin CrossClimate 2 205/55 R16 91V am günstigsten in Österreich?", "Michelin CrossClimate 2 205/55 R16 91V"),
    ("LG OLED65C49LA Preis Deutschland, wo ist er am billigsten?", "LG OLED65C49LA"),
    ("CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V DOT 2022 XL 3PMSF Suche mir günstigere Angebote", "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL"),
])
def test_sache(frage, sache):
    assert einkauf.sache(frage) == sache


def test_ist_einkauf_nur_mit_bestimmter_sache():
    assert einkauf.ist_einkauf("Samsung Galaxy S25 256GB wo am günstigsten in Deutschland?")
    assert einkauf.ist_einkauf("Kärcher K5 Power Control günstig Deutschland")
    assert not einkauf.ist_einkauf("Was kostet die Vignette in Slowenien?")
    assert not einkauf.ist_einkauf("Wie hoch ist der Großglockner?")


def test_andere_groesse_und_andere_variante_zaehlen_nicht():
    v = einkauf.variante("CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL")
    assert v.passt("Continental WinterContact TS 870 P 255/55 R20 110V XL 183,59 €")
    assert not v.passt("Continental WinterContact TS 870 P 205/60 R16 92H 90,00 €")
    s25 = einkauf.variante("Samsung Galaxy S25 256GB")
    assert s25.passt("Galaxy S25 256GB Navy 649,00 €", "Samsung Galaxy S25 256GB Navy")
    assert not s25.passt("Galaxy S25 Ultra 256GB 999,00 €", "Samsung Galaxy S25 Ultra 256GB")
    assert not s25.passt("Galaxy S25+ 256GB 799,00 €", "Samsung Galaxy S25+ 256GB")


def test_angebote_aus_seiten_und_treffern_ohne_vergleichsportal():
    v = einkauf.variante("CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL")
    seiten = [
        _seite("https://www.reifenleader.at/x", "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL", wissen.ANGEBOTE_KOPF
               + " (Produkt „Continental WinterContact TS870P 255/55 R20 110V XL“):\n- diese Seite: 183,59 EUR, lieferbar"),
        _seite("https://geizhals.de/continental-wintercontact-ts-870-p.html", "Continental WinterContact TS 870 P ab € 79,00 (2026) | Preisvergleich Geizhals",
               "Continental WinterContact TS 870 P 255/55 R20 110V XL ab 171,90 €"),
        _seite("https://www.reifen.com/y", "Continental WinterContact TS 870 P 205/60 R16", "205/60 R16 92H 90,00 €"),
    ]
    treffer = [
        {"titel": "Continental WinterContact TS870P 255/55 R20 110V XL – oponeo.at", "adresse": "https://www.oponeo.at/reifen/x", "text": "ab 176,40 € lieferbar"},
        {"titel": "Continental TS 870 P 255/55 R20 | reifendirekt", "adresse": "https://www.reifendirekt.at/z", "text": "Preis 179,90 € · lieferbar"},
        {"titel": "Continental TS870P 255/55 R20 ab 165,00 € | idealo", "adresse": "https://www.idealo.de/a", "text": "ab 165,00 €"},
        {"titel": "Winterreifen Test 2026", "adresse": "https://www.youtube.com/watch?v=x", "text": "TS870P 255/55 R20 199,00 €"},
    ]
    g = einkauf.angebote(treffer, seiten, v)
    assert [(a.haendler, a.preis, a.herkunft) for a in g] == [("oponeo.at", 176.4, "treffer"), ("reifendirekt.at", 179.9, "treffer"),
                                                              ("reifenleader.at", 183.59, "seite")]
    portale = einkauf.vergleichsseiten(treffer, seiten)
    assert [h for h, _a in portale] == ["idealo.de", "geizhals.de"]


def test_gesperrter_haendler_zaehlt_mit_dem_suchtreffer():
    v = einkauf.variante("Samsung Galaxy S25 256GB")
    treffer = [{"titel": "SAMSUNG Galaxy S25 256 GB Navy | MediaMarkt", "adresse": "https://www.mediamarkt.de/p", "text": "Jetzt für 649,00 € kaufen · In den Warenkorb"},
               {"titel": "Samsung Galaxy S25 Smartphone 256GB – Amazon.de", "adresse": "https://www.amazon.de/dp/1", "text": "Preis: 639,99 € · Auf Lager"}]
    g = einkauf.angebote(treffer, [], v)
    assert [(a.haendler, a.preis) for a in g] == [("amazon.de", 639.99), ("mediamarkt.de", 649.0)]


GEIZHALS_ROH = ("<html><script>" + "".join(
    f"window._gh.merchantLinkTracking( event, {{ tracking: {{ category: 'Productpage.Result', action: 'offer_click_{i}', name: '/OUTSHOP/{h}', }}, "
    f"product: {{ id: '2566683', name: 'Michelin CrossClimate 2 205/55 R16 91V', categoryPath: 'Auto \\u0026 Motorrad/Autoreifen', categoryShort: '', "
    f"price: '{p}', merchant: '{h}', }}, }}, {{ tracking: true }} )"
    for i, (h, p) in enumerate([("Amazon.de", "88.99"), ("reifen-peters", "91.50"), ("Amazon.de", "95.00"), ("Pneus Online DE", "93.10")]))
    + "product: { id: '9', name: 'Michelin CrossClimate 2 195/65 R15 95V', categoryPath: 'x', categoryShort: '', price: '70.00', merchant: 'giga\\u002dreifen.de', }"
    + "</script></html>")


def test_haendlerliste_eines_preisvergleichs():
    liste = wissen.haendler_eines_vergleichs(GEIZHALS_ROH)
    n = "Michelin CrossClimate 2 205/55 R16 91V"
    assert liste == (f"{wissen.HAENDLER_LISTE_KOPF}:\n- giga-reifen.de: 70,00 | Michelin CrossClimate 2 195/65 R15 95V\n- Amazon.de: 88,99 | {n}\n"
                     f"- reifen-peters: 91,50 | {n}\n- Pneus Online DE: 93,10 | {n}")
    seite = _seite("https://geizhals.de/michelin-crossclimate-2-205-55-r16-91v-a2566683.html",
                   "Michelin CrossClimate 2 205/55 R16 91V ab € 88,99 (2026) | Preisvergleich Geizhals Deutschland", liste + "\n\nweiterer Text")
    v = einkauf.variante("Michelin CrossClimate 2 205/55 R16 91V")
    g = einkauf.angebote([], [seite], v, "DE")
    assert [(a.haendler, a.preis, a.herkunft) for a in g] == [("Amazon.de", 88.99, "vergleich:geizhals.de"), ("reifen-peters", 91.5, "vergleich:geizhals.de"),
                                                              ("Pneus Online DE", 93.1, "vergleich:geizhals.de")]
    assert "| Amazon.de | 88,99 € | laut geizhals.de |" in einkauf.tabelle(g, [])
    assert einkauf.angebote([], [seite], v, "AT") == []
    assert [a.haendler for a in einkauf.angebote([], [seite], einkauf.variante("Michelin CrossClimate 2 195/65 R15 95V"), "DE")] == ["giga-reifen.de"]
    assert einkauf.angebote([], [seite], einkauf.variante("Michelin CrossClimate 2 225/45 R17 94W"), "DE") == []
    eigen = einkauf.Angebot("amazon.de", 90.0, "https://www.amazon.de/x", "seite")
    assert einkauf.zusammenfassen(g + [eigen])[0] == eigen


def test_unplausible_preise_fallen_weg():
    g = [einkauf.Angebot("bosch-home.at", 0.12, "a", "seite"), einkauf.Angebot("a.at", 20.0, "a", "seite"), einkauf.Angebot("b.at", 679.32, "b", "seite"),
         einkauf.Angebot("c.at", 699.0, "c", "seite"), einkauf.Angebot("d.at", 710.0, "d", "seite")]
    assert [a.haendler for a in einkauf.zusammenfassen(g)] == ["b.at", "c.at", "d.at"]
    zwei = [einkauf.Angebot("reifen.com", 10.03, "a", "seite"), einkauf.Angebot("reifen.de", 274.48, "b", "seite")]
    assert [a.haendler for a in einkauf.zusammenfassen(zwei)] == ["reifen.de"]


def test_monatsrate_und_versand_sind_kein_preis():
    v = einkauf.variante("SAMSUNG GQ55Q80D")
    treffer = [{"titel": "Samsung GQ55Q80D QLED", "adresse": "https://www.samsung.com/de/tvs/x", "text": "ab 55,53 € / Monat oder 999,00 € einmalig · In den Warenkorb"},
               {"titel": "Samsung GQ55Q80D", "adresse": "https://www.otto.de/p", "text": "Versand 4,95 € · Preis 949,00 € · lieferbar"}]
    assert [(a.haendler, a.preis) for a in einkauf.angebote(treffer, [], v)] == [("otto.de", 949.0), ("samsung.com", 999.0)]


def test_nur_haendler_des_gefragten_markts():
    v = einkauf.variante("Kärcher K5 Power Control")
    treffer = [{"titel": "Kärcher K5 Power Control – OBI", "adresse": "https://www.obi.at/p", "text": "439,99 € lieferbar"},
               {"titel": "Kärcher K5 Power Control – OBI", "adresse": "https://www.obi.de/p", "text": "399,00 € lieferbar"},
               {"titel": "Kärcher K 5 Power Control", "adresse": "https://www.kaercher.com/de/p", "text": "404,99 € lieferbar"}]
    assert [a.haendler for a in einkauf.angebote(treffer, [], v, "DE")] == ["obi.de", "kaercher.com"]
    assert len(einkauf.angebote(treffer, [], v, "")) == 3
    assert einkauf.markt_passt("https://www.amazon.de/dp/1", "DE") and not einkauf.markt_passt("https://www.amazon.de/dp/1", "AT")


def test_tabelle_des_programms_ersetzt_die_des_modells():
    g = [einkauf.Angebot("oponeo.at", 176.4, "https://www.oponeo.at/x", "treffer"),
         einkauf.Angebot("reifenleader.at", 183.59, "https://www.reifenleader.at/x", "seite")]
    modell = ("Der WinterContact TS870P gilt als sehr guter Winterreifen.\n\n| Anbieter | Preis | Hinweis |\n|---|---|---|\n"
              "| Geizhals (Händler) | 90,00 € | Größe 205/60 R16 |\n\nAm günstigsten ist Geizhals mit 90,00 €.")
    text = einkauf.einsetzen(modell, g, [("geizhals.de", "https://geizhals.de/x")], stand="25.10.2026")
    assert text.startswith("Der WinterContact TS870P gilt als sehr guter Winterreifen.")
    assert "Geizhals (Händler)" not in text and "90,00" not in text
    assert "| oponeo.at | 176,40 € | im Suchtreffer |" in text and "| reifenleader.at | 183,59 € | auf der Seite des Händlers |" in text
    assert "Am günstigsten ist oponeo.at mit 176,40 €." in text and "Weitere Händler listet der Preisvergleich geizhals.de." in text
    en = einkauf.tabelle(g, [], englisch=True)
    assert "| oponeo.at | €176.40 | in the search result |" in en and "The cheapest is oponeo.at at €176.40." in en
    leer = einkauf.einsetzen("| A | B |\n|---|---|\n| Geizhals | 79,00 € |", [], [("geizhals.at", "https://geizhals.at/x")])
    assert leer == "Bei den Händlern, die ich lesen konnte, stand kein Preis für genau dieses Modell. Preise vergleichen kannst du hier: https://geizhals.at/x."
    assert einkauf.tabelle([], [], englisch=True) == "I couldn't find a shop page that shows a price for exactly this model."


def test_preis_eines_anderen_produkts_zaehlt_nicht():
    v = einkauf.variante("Michelin Alpin 6 205/55 R16 91H")
    seite = _seite("https://www.reifendirekt.at/x", "Michelin Alpin 6 205/55 R16 91H - ReifenDirekt.at",
                   "Michelin Alpin 6 205/55 R16 91H EV Suitable - ReifenDirekt.at WinterContact TS 870 205/55 R16 91H EVc 99,87 € Details")
    assert einkauf.angebote([], [seite], v, "AT") == []
    gut = _seite("https://www.reifendirekt.at/y", "Michelin Alpin 6 205/55 R16 91H", "Michelin Alpin 6 205/55 R16 91H Sofort lieferbar 112,40 € Details")
    assert [(a.haendler, a.preis) for a in einkauf.angebote([], [gut], v, "AT")] == [("reifendirekt.at", 112.4)]
    mm = _seite("https://www.mediamarkt.at/p", "SAMSUNG Galaxy S25 256 GB, Navy", "SAMSUNG Galaxy S25 256 GB, Navy, Dual SIM | 4.6 UVP € 959,–€959,00 € 779,99 inkl. MwSt. versandkostenfrei")
    assert [a.preis for a in einkauf.angebote([], [mm], einkauf.variante("Samsung Galaxy S25 256GB"), "AT")] == [779.99]


def test_von_der_uebersicht_zur_produktseite_der_variante():
    roh = ('<a href="samsung-galaxy-s25-128gb-silver-shadow-sm-s931bzsd-a3394687.html">128GB Silver Shadow</a>'
           '<a href="samsung-galaxy-s25-128gb-silver-shadow-sm-s931bzsd-a3394687.html">62 Angebote</a>'
           '<a href="samsung-galaxy-s25-256gb-blueblack-sm-s931bzkg-a3394698.html">256GB Blueblack</a>'
           '<a href="samsung-galaxy-s25-256gb-blueblack-sm-s931bzkg-a3394698.html">4 Angebote</a>'
           '<a href="samsung-galaxy-s25-256gb-navy-sm-s931bdbg-a3394694.html">256GB Navy</a>'
           '<a href="samsung-galaxy-s25-256gb-navy-sm-s931bdbg-a3394694.html">36 Angebote</a>'
           '<a href="apple-macbook-air-13-mw0y3d-a-2025-z1cv-a3435579.html">Apple MacBook Air 13&quot;, M4, 16GB RAM, 256GB SSD</a>')
    block = wissen.produktseiten_eines_vergleichs(roh, "https://geizhals.at/samsung-galaxy-s25-v188112.html")
    assert block.startswith(wissen.PRODUKTSEITEN_KOPF)
    assert "| 256GB Navy (36 Angebote): https://geizhals.at/samsung-galaxy-s25-256gb-navy-sm-s931bdbg-a3394694.html" in block
    assert "macbook" not in block
    ohne_zahl = wissen.produktseiten_eines_vergleichs(roh.split("</a>", 6)[-1], "https://geizhals.at/x-v1.html")
    assert 'Apple MacBook Air 13", M4, 16GB RAM, 256GB SSD' in ohne_zahl
    assert wissen.produktseiten_eines_vergleichs('<a href="/x-a1.html?o=2">Galaxy S25 256GB</a>', "https://geizhals.at/v") == ""
    fremd = wissen.produktseiten_eines_vergleichs('<a href="https://boese.example/s25-256gb-a1.html">Galaxy S25 256GB</a>', "https://www.beispiel.at/x")
    assert fremd == ""
    seite = _seite("https://geizhals.at/samsung-galaxy-s25-v188112.html", "Samsung Galaxy S25 ab € 548,63", block + "\n\nText")
    ziele = einkauf.produktseiten([seite], einkauf.variante("Samsung Galaxy S25 256GB"), "AT")
    assert [t["adresse"].rsplit("-", 1)[1] for t in ziele] == ["a3394694.html", "a3394698.html"]
    de = einkauf.produktseiten([seite], einkauf.variante("Samsung Galaxy S25 256GB"), "DE")
    assert de[0]["adresse"] == "https://geizhals.de/samsung-galaxy-s25-256gb-navy-sm-s931bdbg-a3394694.html"
    assert einkauf.im_markt("https://www.beispiel.at/x", "DE") == "https://www.beispiel.de/x"
    assert einkauf.im_markt("https://www.beispiel.de/x", "GB") == "https://www.beispiel.uk/x"
    assert einkauf.im_markt("https://www.beispiel.com/x", "DE") == "https://www.beispiel.com/x"
    assert einkauf.im_markt("https://www.beispiel.at/x", "") == "https://www.beispiel.at/x"


def test_ein_haendler_aus_seite_und_preisvergleich_steht_einmal_da():
    g = [einkauf.Angebot("hartlauer.at", 239.0, "a", "seite"), einkauf.Angebot("Hartlauer", 239.0, "b", "vergleich:geizhals.at"),
         einkauf.Angebot("obi.at", 400.0, "c", "seite"), einkauf.Angebot("obi.de", 399.0, "d", "seite")]
    assert [a.haendler for a in einkauf.zusammenfassen(g)] == ["hartlauer.at", "obi.de", "obi.at"]


def test_gebrauchte_listen_und_kopfzeilen_bringen_keinen_preis():
    v = einkauf.variante("Apple AirPods Pro 2 mit USB-C")
    refurb = _seite("https://www.mediamarkt.at/de/product/_apple-airpods-pro-2.html", "APPLE AIRPODS PRO 2ND GEN. | MediaMarkt",
                    "APPLE AIRPODS PRO 2ND GEN. In-ear Kopfhörer + € 0,– Refurbished Produkte von Beispiel AT Zum Impressum € 159,95 inkl. MwSt.")
    assert einkauf.angebote([], [refurb], v, "AT") == []
    liste = _seite("https://www.mediamarkt.at/de/list/ps5", "Sony PlayStation®5 Pro online kaufen | MediaMarkt", "PlayStation 5 Pro 799,99 €")
    assert einkauf.angebote([], [liste], einkauf.variante("Sony PS5 Pro"), "AT") == []
    kopf = _seite("https://www.reifendirekt.at/r", "Michelin Alpin 6 205/55 R16 91H - ReifenDirekt.at",
                  "Fragekennung: abc\n\nGefunden über die Suche, Seite „Michelin Alpin 6 205/55 R16 91H“ (https://www.reifendirekt.at/r/Alpin-6/205-55-R16), "
                  "gelesen am 25.10.2026.\n\nWinterContact TS 870 205/55 R16 91H 99,87 € Details")
    assert einkauf.angebote([], [kopf], einkauf.variante("Michelin Alpin 6 205/55 R16 91H"), "AT") == []


def test_dieselbe_sache_unter_zwei_namen():
    assert einkauf.variante("Sony PS5 Pro").passt("Sony PlayStation®5 Pro Konsole", "Sony PlayStation®5 Pro Konsole")
    assert not einkauf.variante("Sony WH-1000XM5").passt("Sony WF-1000XM5", "Sony WF-1000XM5")


def test_preisanker_anschluss_versandgrenze_und_zweite_hand():
    v = einkauf.variante("Michelin Alpin 6 205/55 R16 91H")
    treffer = [{"titel": "Michelin Alpin 6 205/55 R16 91H ab € 323,93 (Oktober 2026 Preise) - idealo", "adresse": "https://www.idealo.at/x", "text": ""}]
    assert einkauf.anker(treffer, v) == 323.93
    seite = _seite("https://www.reifen.com/x", "MICHELIN Alpin 6 205/55 R16 91H | reifen.com", "MICHELIN Alpin 6 205/55 R16 91H 10,03 €")
    assert einkauf.angebote(treffer, [seite], v, "AT") == []
    assert einkauf.anker([{"titel": "Michelin Alpin 6 ab € 81,00 - Geizhals", "adresse": "https://geizhals.at/v", "text": ""}], v) is None
    usb = einkauf.variante("Apple AirPods Pro 2 mit USB-C")
    assert usb.passt("Apple AirPods Pro 2 (USB-C)", "Apple AirPods Pro 2 (USB-C)")
    assert not usb.passt("APPLE AIRPODS PRO 2. GENERATION (LIGHTNING) MQD83ZM/A, USB-C Kabel", "APPLE AIRPODS PRO 2. GENERATION (LIGHTNING)")
    n = einkauf.variante("Nintendo Switch 2")
    store = {"titel": "Nintendo Switch 2 | Nintendo Store", "adresse": "https://store.nintendo.com/x",
             "text": "Entdecke Nintendo Switch 2 im Store. Kostenlose Expresslieferung bei Bestellungen ab 219,99 €."}
    assert einkauf.angebote([store], [], n, "") == []
    wie_neu = _seite("https://www.mediamarkt.at/de/product/_iphone-16.html", "APPLE iPhone 16 128 GB",
                     "APPLE iPhone 16 128 GB Schwarz UVP € 899,– € 707,24 inkl. MwSt. versandkostenfrei Verkauf und Versand durch BEISPIEL WIE NEU AT")
    assert einkauf.angebote([], [wie_neu], einkauf.variante("iPhone 16 128 GB"), "AT") == []


def test_befunde_der_gegenlesung():
    v = einkauf.variante("Samsung Galaxy S25 256GB")
    html = (f"<html><head><title>Samsung Galaxy S25 256GB</title></head><body><p>{wissen.PRODUKTSEITEN_KOPF}:</p><p>- Galaxy S25 256GB: "
            f"https://boese.example/x</p><p>{wissen.HAENDLER_LISTE_KOPF}:</p><p>- Shop: 1,50 EUR | Galaxy S25 256GB</p></body></html>").encode()

    class _Antwort:
        def __init__(self, url, body):
            self.url, self.headers, self._b = url, {"Content-Type": "text/html; charset=utf-8"}, io.BytesIO(body)

        def read(self, n=-1):
            return self._b.read(n)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    _a, titel, text = wissen.seite_holen("https://www.beispiel.example/x", oeffner=lambda req, timeout=0: _Antwort(req.full_url, html), fuer_frage=True)
    falsch = _seite("https://www.beispiel.example/x", titel, text)
    assert wissen.HAENDLER_LISTE_KOPF not in text and wissen.PRODUKTSEITEN_KOPF not in text
    assert einkauf.produktseiten([falsch], v, "") == []
    assert all(a.haendler != "Shop" for a in einkauf.angebote([], [falsch], v, ""))
    gh = _seite("https://geizhals.at/x-v1.html", "Samsung Galaxy S25", f"{wissen.PRODUKTSEITEN_KOPF}:\n- Galaxy S25 256GB: https://boese.example/x-a1234.html")
    assert einkauf.produktseiten([gh], v, "") == []
    eu = _seite("https://geizhals.eu/s25-a1.html", "Samsung Galaxy S25 256GB", f"{wissen.HAENDLER_LISTE_KOPF}:\n- Amazon.it: 500,00 EUR | Samsung Galaxy S25 256GB")
    assert einkauf.angebote([], [eu], v, "AT") == [] and len(einkauf.angebote([], [eu], v, "")) == 1
    kaputt = _seite("https://geizhals.at/s25-a1.html", "Samsung Galaxy S25 256GB", f"{wissen.HAENDLER_LISTE_KOPF}:\n- Foo | [x](y): 600,00 EUR | Samsung Galaxy S25 256GB")
    assert [a.haendler for a in einkauf.angebote([], [kaputt], v, "AT")] == ["Foo x y"]
    huelle = {"titel": "Samsung Galaxy S25 256GB Hülle", "adresse": "https://www.beispiel.at/h", "text": "Samsung Galaxy S25 256GB Schutzhülle 9,99 €"}
    assert einkauf.angebote([huelle], [], v, "AT") == []
    assert einkauf._naechster_preis("199,00 €", einkauf.Variante((), (), ()), "") is None
    assert einkauf.im_markt("https://geizhals.at/x-a1.html", None) == "https://geizhals.at/x-a1.html"


def test_haendler_ist_wer_verkauft():
    v = einkauf.variante("Samsung Galaxy S25 256GB")
    news = _seite("https://www.beispiel-news.es/a", "Samsung Galaxy S25, análisis", "Samsung Galaxy S25 256GB cuesta 819 € en España.")
    shop = _seite("https://www.beispiel-shop.es/p", "Samsung Galaxy S25 256GB", "Samsung Galaxy S25 256GB 799,00 € Añadir al carrito")
    assert [a.haendler for a in einkauf.angebote([], [news, shop], v, "ES")] == ["beispiel-shop.es"]
    verlauf = {"titel": "Sony WH-1000XM5 price history and price tracker", "adresse": "https://beispiel.example/p", "text": "$278.00 in stock"}
    assert einkauf.angebote([verlauf], [], einkauf.variante("Sony WH-1000XM5"), "US") == []


def test_alternativen_mit_produktnamen_ohne_das_gefragte_modell():
    frage = "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V XL Zeige mir günstigere Alternativen"
    assert einkauf.ist_alternative(frage) and einkauf.anfragen(frage) == ["255/55 R20"]
    v, ohne = einkauf.suchvariante(frage)
    treffer = [{"titel": "Continental WinterContact TS870P 255/55 R20 110V XL – Shop", "adresse": "https://a.beispiel.at/x", "text": "183,59 € lieferbar"},
               {"titel": "Pirelli Scorpion Winter 2 255/55 R20 110V XL | Shop B", "adresse": "https://b.beispiel.at/x", "text": "162,40 € lieferbar"}]
    g = einkauf.angebote(treffer, [], v, "AT", ohne, True)
    assert [(a.produkt, a.haendler) for a in g] == [("Pirelli Scorpion Winter 2 255/55 R20 110V XL", "b.beispiel.at")]
    assert "| Produkt | Händler | Preis | Geprüft |" in einkauf.tabelle(g, [])
    assert not einkauf.ist_alternative("Suche mir günstigere Angebote")


def test_preise_in_jeder_schreibweise_und_waehrung():
    b = [(w, i) for _a, _e, w, i in einkauf.betraege("$1,299.99 · 1.299,99 € · CHF 1'299.90 · ¥59,980 · 1 299,99 € · 899,– €", "")]
    assert b == [(1299.99, "USD"), (1299.99, "EUR"), (1299.9, "CHF"), (59980.0, ""), (1299.99, "EUR"), (899.0, "EUR")]
    assert einkauf.betraege("¥59,980", "JP")[0][2:] == (59980.0, "JPY")
    assert einkauf.betraege("12,99 $", "CA")[0][3] == "CAD" and einkauf.betraege("kr 1 299", "SE")[0][3] == "SEK"
    assert einkauf._geld(59980, True, "JPY") == "¥59,980" and einkauf._geld(1299.9, False, "CHF") == "1.299,90 CHF"
    t = [{"titel": "Sony WH-1000XM5", "adresse": "https://a.beispiel.com/p", "text": "$278.00 in stock"},
         {"titel": "Sony WH-1000XM5", "adresse": "https://b.beispiel.com/p", "text": "259,00 € lieferbar"}]
    assert [(a.preis, a.waehrung) for a in einkauf.angebote(t, [], einkauf.variante("Sony WH-1000XM5"), "US")] == [(278.0, "USD")]
