# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import absicht
import antwortsprache

FOTO = ("\n\nDatei „561C3CD1.jpeg“ (Text aus dem Foto):\nZeitwörter (Verben) und Eigenschaftswörter (Adjektive) werden zu Namenwörtern (Nomen)\n"
        "1 Schreibe zu jedem Eigenschaftswort (Adjektiv) ein passendes Namenwort (Nomen).\ntraurig neu schön einsam dankbar heiter")
SALAT = "\n\nDatei „IMG_1.jpeg“ (Text aus dem Foto):\nis a on the it is an in on at by of a to\nthe on is in"


def test_die_sprache_kommt_aus_den_eigenen_worten():
    assert antwortsprache.frage_sprache("Schreibe mir Punkt 1" + SALAT) == "de"
    assert antwortsprache.frage_sprache("What does this say?" + FOTO) == "en"
    assert antwortsprache.frage_sprache(SALAT.strip()) == "en"


def test_aufgabe_zum_anhang_ohne_suche():
    for eigen in ("Schreibe mir Punkt 1", "Löse Aufgabe 2", "Übersetze das bitte", "Fasse den Brief zusammen", "Solve exercise 2",
                  "Risolvi l'esercizio 3", "Résume ce texte", "Was steht da?"):
        a = absicht.erkennen(eigen + FOTO)
        assert a.art == "anhang_aufgabe" and absicht.ohne_suche(a), eigen
    for eigen in ("Suche mir günstigere Angebote", "Wie sind die Testbewertungen?", "Where can I buy this cheaper?"):
        assert absicht.erkennen(eigen + FOTO).art != "anhang_aufgabe", eigen
    assert not absicht.anhang_aufgabe("Schreibe mir einen Brief an die Gemeinde")
