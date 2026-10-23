# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wikipedia


def test_kennzeichen_vor_dem_ersten_satz_fallen_alle_weg():
    see = ("Vorlage:Infobox See/Wartung/NACHWEIS-SEEBREITEVorlage:Infobox See/Wartung/NACHWEIS-UMFANG Der Attersee ist ein See im "
           "Salzkammergut.")
    assert wikipedia.ohne_wartung(see) == "Der Attersee ist ein See im Salzkammergut."
    assert wikipedia.ohne_wartung("Vorlage:Coordinate/Wartung/POSKARTE unpassend Der Bodensee liegt am Rhein.") == "Der Bodensee liegt am Rhein."
    assert wikipedia.ohne_wartung("Vorlage:Infobox Ort in der Türkei/Wartung/LandkreisOhneEinwohnerOderFläche Istanbul ist groß.") == "Istanbul ist groß."
    projekt = "Wikipedia:WikiProjekt Ereignisse/Vergangenheit/fehlend Amsterdam ist die Hauptstadt der Niederlande."
    assert wikipedia.ohne_wartung(projekt) == "Amsterdam ist die Hauptstadt der Niederlande."
    assert wikipedia.ohne_wartung("pd3 pd5 fd2 Der Berg ist 6961 m hoch.") == "Der Berg ist 6961 m hoch."
    assert wikipedia.ohne_wartung("f9f8 Athen ist die Hauptstadt.") == "Athen ist die Hauptstadt."
    assert wikipedia.ohne_wartung("d1 Mumbai ist eine Stadt.") == "Mumbai ist eine Stadt."
    assert wikipedia.ohne_wartung("x86 ist eine Architektur.", "X86") == "x86 ist eine Architektur."
    assert wikipedia.ohne_wartung("-26.228.066666666667Koordinaten: 26° 12′ S, 28° 4′ O Johannesburg ist eine Stadt.") == "Johannesburg ist eine Stadt."


def test_leere_klammern_der_aussprache_fallen_weg():
    assert wikipedia.ohne_wartung("Apple Inc. [] ist ein Unternehmen.") == "Apple Inc. ist ein Unternehmen."
    assert wikipedia.ohne_wartung("Bern (französisch [], italienisch [], rätoromanisch ) ist eine Stadt.") == \
        "Bern (französisch, italienisch, rätoromanisch) ist eine Stadt."
    assert wikipedia.ohne_wartung("Deutschland (; Vollform des Staatsnamens: Bundesrepublik) ist ein Staat.") == \
        "Deutschland (Vollform des Staatsnamens: Bundesrepublik) ist ein Staat."
    assert wikipedia.ohne_wartung("Der Eiffelturm (französisch Tour Eiffel, ) ist hoch.") == "Der Eiffelturm (französisch Tour Eiffel) ist hoch."


def test_der_anhang_am_ende_faellt_weg_der_artikel_bleibt():
    artikel = "Gmunden liegt am Traunsee. " * 40
    anhang = ("Hans Huber: Der Traunsee. Verlag, Linz 1990, ISBN 3-85214-000-0. Gmunden. In: beispiel.at. Abgerufen am 6. April 2012. "
              "Bericht. In: beispiel.at, abgerufen am 7. April 2012. (Memento vom 1. Mai 2013 im Internet Archive) 47.9213.8Koordinaten: 47° N, 13° O")
    rest = wikipedia.ohne_anhang(artikel + anhang)
    assert rest.startswith(artikel.strip()) and len(rest) < len(artikel) + 30
    assert not any(w in rest for w in ("ISBN", "bgerufen", "Memento", "Koordinaten"))
    assert wikipedia.ohne_anhang(artikel) == artikel
    werke = ("Werke: Roman. Verlag, Wien 1990, ISBN 3-85214-001-0. Erzählung. Verlag, Wien 1992, ISBN 3-85214-002-0. Gedichte. Verlag, Wien 1994, "
             "ISBN 3-85214-003-0. Essay. Verlag, Wien 1996, ISBN 3-85214-004-0. ")
    danach = "Verfilmungen und Rezeption: Der Roman wurde verfilmt und erhielt den Staatspreis. " * 40
    assert wikipedia.ohne_anhang(artikel + werke + danach) == artikel + werke + danach
    assert wikipedia.ohne_anhang("Die Reihe (ISBN 1, ISBN 2, ISBN 3, ISBN 4) erschien") == "Die Reihe (ISBN 1, ISBN 2, ISBN 3, ISBN 4) erschien"
    assert wikipedia.ohne_wartung("Der Maßstab ist 1 : 50 000 und das Verhältnis 2 : 1.") == "Der Maßstab ist 1 : 50 000 und das Verhältnis 2 : 1."
    recht = "Ein Verstoß liegt nach Art. 6 S. 2 EGBGB vor. Nach § 3 Abs. 1 S. 2 gilt das auch. Siehe S. 4 und S. 5. The Star (englisch) und The Times (englisch). " * 5
    assert wikipedia.ohne_anhang(recht) == recht


def test_saetze_enden_nie_an_datum_abkuerzung_oder_initiale():
    for text in ("Am 12. März 1938 marschierten Truppen ein.", "Der Umsatz lag bei 243 Mrd. USD im Jahr.", "Der Berg ist 3798 m ü. A. hoch.",
                 "Die Siedlung entstand um 900 v. Chr. am Fluss.", "Das geschah im 3. Jahrhundert nach der Gründung.",
                 "Seine Mutter Pauline, geb. Koch, stammte aus Cannstatt.", "Die Firma baute 2,2 Mio. Fahrzeuge."):
        assert wikipedia.saetze(text) == [text], text
    assert wikipedia.saetze("Der Krieg endete 1918. Danach kam die Republik.") == ["Der Krieg endete 1918.", "Danach kam die Republik."]
    assert wikipedia.saetze("Er wurde Dritter. Später gewann er.") == ["Er wurde Dritter.", "Später gewann er."]


def test_ein_langer_artikel_kommt_ganz_in_die_kopie_der_anhang_zaehlt_nicht():
    satz = "Die Stadt hat einen großen Hauptplatz mit vielen Häusern aus dem Mittelalter und einer Kirche. "
    text = satz * 1500 + "Hans Huber: Die Stadt. In: beispiel.at, abgerufen am 6. April 2012. ISBN 3-85214-000-0. " * 200
    d = {"namespace": "0", "page_type": "primary", "title": "Gmunden", "page_id": 1, "text": text, "auxiliary_text": []}
    teile = wikipedia.dokument_lesen(d)["teile"]
    assert 60 < len(teile) <= wikipedia.MAX_ABSCHNITTE and not any("abgerufen" in t for t in teile)
    assert wikipedia.MAX_ABSCHNITTE >= 300 and wikipedia.EINLESE_STAND >= 4


def test_eine_liste_behaelt_ihre_tabellen_in_der_reihenfolge_des_artikels():
    haupt = "Stadt VZ 1981 VZ 2001 " + " ".join(f"Ort{i} {10000 + i}" for i in range(900))
    klein = "Ort Gemeinde Einwohner von bis Jahr Anzahl Donawitz Leoben 1929 1939 2001 4202 Liesing Wien 1905 1938 1951 5950 Ruprecht Klagenfurt 1930 1938"
    kurz = wikipedia.kurzdaten([haupt, klein], liste=True)
    assert kurz[0].startswith("Kurzdaten: Stadt VZ 1981 VZ 2001 Ort0 10000")
    assert sum(len(k) for k in kurz) > wikipedia.KURZDATEN_ZEICHEN
    assert sum(len(k) for k in kurz) <= wikipedia.KURZDATEN_LISTE_ZEICHEN + 12 * len(kurz)
    assert wikipedia.kurzdaten([haupt, klein])[0].startswith("Kurzdaten: Ort Gemeinde Einwohner")


def test_ein_bau_mit_alten_einleseregeln_beginnt_neu(tmp_path):
    import json
    w = wikipedia.WikiKopie(lambda: tmp_path / "wiki", freigabe_mb=lambda: 200_000, darf=lambda: True, karte_frei=lambda: True)
    w.ordner.mkdir(parents=True)
    (w.ordner / wikipedia.STAND).write_text(json.dumps({"bau_ausgabe": "20261018", "bau_teile": [[0, "x", 1]], "einlesen_teil": 0,
                                                        "einlesen_zeile": 456002, "fertig_ausgabe": "20261004", "einlese_stand": 2}), encoding="utf-8")
    (w.ordner / "wikipedia-20261018.bau.sqlite").write_bytes(b"halb")
    (w.ordner / "teil-00000.json.bz2").write_bytes(b"teil")
    assert w.schritt() == 0
    st = json.loads((w.ordner / wikipedia.STAND).read_text(encoding="utf-8"))
    assert st["bau_ausgabe"] == "" and st["einlesen_zeile"] == 0 and st["fertig_ausgabe"] == "20261004"
    assert not (w.ordner / "wikipedia-20261018.bau.sqlite").exists() and not (w.ordner / "teil-00000.json.bz2").exists()
    (w.ordner / wikipedia.STAND).write_text(json.dumps({**st, "bau_ausgabe": "20261018", "bau_stand": wikipedia.EINLESE_STAND}), encoding="utf-8")
    gerufen = []
    w._bau_schritt = lambda s: gerufen.append(s["bau_ausgabe"]) or 0
    w.schritt()
    assert gerufen == ["20261018"]


def _kopie(tmp_path):
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    a = lambda i, titel, text, umleitungen=(): {"id": i, "titel": titel, "beliebt": 0.01, "geaendert": "", "umleitungen": list(umleitungen),
                                               "teile": [text]}
    db.teil_aufnehmen(1, [
        a(1, "Stadt", "Eine Stadt ist eine größere Siedlung.", ["Städte"]),
        a(2, "Tabelle", "Eine Tabelle ist eine geordnete Zusammenstellung."),
        a(3, "Österreich", "Österreich ist ein Binnenstaat in Mitteleuropa."),
        a(4, "Liste der Städte in Österreich", "Die Liste der Städte in Österreich bietet einen Überblick über die Einwohnerzahl."),
        a(5, "Liste der größten Städte", "Diese Liste enthält große Städte."),
        a(6, "Fluss", "Ein Fluss ist ein fließendes Gewässer.", ["Flüsse"]),
        a(7, "Liste der längsten Flüsse der Erde", "Die Liste enthält die längsten Flüsse."),
        a(8, "Jahr", "Das Jahr ist eine Zeitdauer."),
        a(9, "Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart war ein Komponist."),
        a(10, "Liste der österreichischen Arbeitsminister", "Die Liste enthält Minister."),
        a(11, "Hauptstadt", "Eine Hauptstadt ist ein Zentrum."),
        a(12, "Australien", "Australien ist ein Staat."),
    ])
    db.teil_abschliessen(1)
    return db


def test_listenfragen_finden_ihren_listenartikel_und_sachwoerter_zaehlen_nicht(tmp_path):
    db = _kopie(tmp_path)
    titel = lambda f: [db._c.execute("SELECT titel FROM artikel WHERE id=?", (i,)).fetchone()[0] for i in db.titel_artikel(f)]
    assert titel("Welche sind die 5 größten Städte Österreichs? Bitte als Tabelle mit Einwohnerzahl.")[0] == "Liste der Städte in Österreich"
    assert "Tabelle" not in titel("Welche sind die 5 größten Städte Österreichs? Bitte als Tabelle mit Einwohnerzahl.")
    assert titel("Die zehn längsten Flüsse der Welt?") == ["Liste der längsten Flüsse der Erde"]
    assert titel("In welchem Jahr wurde Wolfgang Amadeus Mozart geboren?") == ["Wolfgang Amadeus Mozart"]
    assert titel("Was ist die Hauptstadt von Australien?") == ["Australien"]
    assert titel("Wie lange darf man in Österreich arbeiten?") == ["Österreich"]
    assert titel("Wie viele Tage hat ein Jahr?") == ["Jahr"]
