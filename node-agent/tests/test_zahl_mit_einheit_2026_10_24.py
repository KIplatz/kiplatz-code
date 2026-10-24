# SPDX-License-Identifier: AGPL-3.0-or-later
import belege

QUELLE = "Grand Theft Auto VI erscheint am 26. Mai 2026. Der Launch Trailer ist 2:46 lang und zeigt Jason und Lucia. Trailer 2 hat 26 Szenen."


def _unbelegt(satz, quelle=QUELLE):
    return belege.unbelegte_zahlen(satz, belege.zahlenwerte(quelle), einheiten=belege.einheiten_werte(quelle))


def test_dauer_ohne_dauer_in_der_quelle_faellt():
    assert _unbelegt("Die Länge beträgt rund 26 Minuten.") == ["26"]
    assert [b.satz for b in belege.streng_pruefen("Die Länge beträgt rund 26 Minuten.", QUELLE)] == ["Die Länge beträgt rund 26 Minuten."]


def test_dauer_mit_dauer_in_der_quelle_bleibt():
    q = "Das Video dauert 26 Minuten und zeigt das Spiel."
    assert _unbelegt("Das Video ist 26 Minuten lang.", q) == []
    assert _unbelegt("Das Video ist rund 25 Minuten lang.", q) == []


def test_umrechnen():
    assert _unbelegt("Die Fahrt dauert 90 Minuten.", "Fahrzeit 1,5 Stunden ab Wien.") == []
    assert _unbelegt("Die Strecke ist 4500 Meter lang.", "Die Strecke misst 4,5 km.") == []
    assert _unbelegt("Er wiegt 2 kg.", "Gewicht 2000 g") == []
    assert _unbelegt("Die Donau ist 2857 Kilometer lang.", "Die Donau ist mit 2857 Kilometern der zweitlängste Fluss Europas.") == []
    assert _unbelegt("Wien ist 415 km lang.", "Wien hat 415 km² Fläche.") == ["415"]


def test_videolaenge_aus_der_trefferliste():
    assert _unbelegt("Der Trailer dauert knapp 3 Minuten.") == []
    assert _unbelegt("Der Trailer dauert 166 Sekunden.") == []
    assert _unbelegt("Der Trailer dauert 46 Minuten.") == ["46"]


def test_falsche_art_zaehlt_nicht():
    assert _unbelegt("Der Weg ist 26 km lang.", "Er braucht 26 Minuten.") == ["26"]


def test_geld_und_ohne_einheit_wie_bisher():
    assert _unbelegt("Der Reifen kostet 183,59 €.", '"price": "183.59", "priceCurrency": "EUR"') == []
    assert _unbelegt("Es gibt 26 Szenen.") == []
    assert belege.unbelegte_zahlen("Die Länge beträgt 26 Minuten.", belege.zahlenwerte(QUELLE)) == []
