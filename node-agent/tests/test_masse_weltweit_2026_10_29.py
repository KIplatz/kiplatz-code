# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import belege
import wissen


def test_masse_in_beiden_sprachen_mit_temperatur_und_alter():
    faelle = [
        ("What core temperature does chicken need to be safe?", "Cook chicken until the internal temperature reaches 74 °C (165 °F).", "Chicken is a bird."),
        ("How much cash can I bring into the EU without declaring it?", "You must declare cash of 10,000 euros or more.", "The EU has 27 members."),
        ("Ab welchem Alter darf man in Österreich Moped fahren?", "Den Mopedausweis gibt es ab 15 Jahren.", "Ein Moped hat zwei Räder."),
        ("When does school start in Upper Austria after the summer holidays?", "School starts on 7 September 2026.", "Upper Austria is a state."),
        ("How long does a football match last?", "A match lasts 90 minutes.", "Football is popular."),
    ]
    for frage, mit, ohne in faelle:
        m = wissen.mass_punkte(frage)
        assert m is not None, frage
        assert m(mit) >= 1.0 > m(ohne), frage


def test_when_mitten_im_satz_ist_kein_zeitpunkt():
    assert wissen.mass_punkte("What should I consider when travelling with a dog in the car?") is None
    assert wissen.mass_punkte("When is Easter in 2027?") is not None


def test_dreisatz_aus_der_frage_ist_gerechnet():
    frage = "Wie weit ist ein Gewitter entfernt, wenn der Donner 6 Sekunden nach dem Blitz kommt?"
    quelle = "Faustregel: Vergehen zwischen Blitz und Donner 3 Sekunden, ist das Gewitter etwa 1 Kilometer entfernt."
    assert not [b for b in belege.streng_pruefen("Das Gewitter ist etwa 2 Kilometer entfernt.", quelle + "\n" + frage, frage=frage) if b.zahlen]
    assert [b for b in belege.streng_pruefen("Das Gewitter ist etwa 5 Kilometer entfernt.", quelle + "\n" + frage, frage=frage) if b.zahlen]
    assert belege.dreisatz_werte("Wie weit ist ein Gewitter entfernt?", quelle) == {}


def test_gegenlesung_keine_falschen_treffer():
    m = wissen.mass_punkte("Ab welchem Alter darf man Moped fahren?")
    assert m("Geöffnet ab 10 Uhr.") == 0.0 and m("Den Mopedausweis gibt es ab 15 Jahren.") >= 1.0
    assert wissen.mass_punkte("Do I need a degree to teach?") is None
    frage = "Wie weit ist ein Gewitter entfernt, wenn der Donner 6 Sekunden nach dem Blitz kommt?"
    assert belege.dreisatz_werte(frage, "Die Wanderung dauert 2 Stunden und ist 8 km lang.") == {}
    assert belege.dreisatz_werte("Was passiert um 18:30 Uhr beim Blitz?", "Zwischen Blitz und Donner 3 Sekunden: 1 Kilometer.") == {}
