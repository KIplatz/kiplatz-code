# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import belege


def test_luecke_im_satz_wird_strich():
    t, n = belege.ohne_platzhalter("Betreff: Krankmeldung – [Name des Kindes]\n\nmein Kind, [Name], ist heute krank. "
                                   "Mein Sohn kann morgen, den [Datum], nicht kommen.\n\nMit freundlichen Grüßen,\n[Ihr Name]", strich=True)
    assert n == 4 and "[" not in t
    assert "Krankmeldung – ________" in t and "mein Kind, ________, ist heute krank" in t and "morgen, den ________, nicht" in t
    assert t.endswith("Mit freundlichen Grüßen,")


def test_quellenmarken_bleiben():
    assert belege.ohne_platzhalter("Siehe [1] und [Quelle 2].") == ("Siehe [1] und [Quelle 2].", 0)


def test_ohne_schriftstueck_faellt_die_luecke_weg_wie_bisher():
    t, n = belege.ohne_platzhalter("Die Hauptstadt ist Wien [Name der Hauptstadt].")
    assert n == 1 and "____" not in t and "[" not in t


def test_kein_strich_fuer_klammern_die_kein_feld_sind_und_nicht_in_code():
    t, _ = belege.ohne_platzhalter("Der Bericht [PDF] zeigt es. Lieber Herr [Name], hier `arr[name]` und arr[Name].", strich=True)
    assert "Bericht zeigt es" in t and "`arr[name]`" in t and "____" not in t.split("Bericht")[1].split(".")[0]


def test_vorlage_gefragt():
    import schriftstueck
    assert schriftstueck.vorlage_gefragt("Wie schreibt man eine Entschuldigung für die Schule, wenn mein Kind krank ist?")
    assert not schriftstueck.vorlage_gefragt("Wie schreibt man Rhythmus?")
