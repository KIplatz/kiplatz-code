# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import antwortspeicher_basis
import belege

QUELLE = ("Österreich ist ein Bundesstaat und besteht aus neun Bundesländern: Burgenland, Kärnten, Niederösterreich, Oberösterreich, "
          "Salzburg, Steiermark, Tirol, Vorarlberg und Wien. Die Hauptstadt ist Wien.")


def test_namen_mit_komma_und_und():
    antwort = ("Österreich hat neun Bundesländer: Burgenland, Kärnten, Niederösterreich, Oberösterreich, Salzburg, Steiermark, Tirol, "
               "Vorarlberg und Wien.")
    assert belege.woertliche_saetze(antwort, [QUELLE]) == []


def test_namen_als_liste_untereinander():
    antwort = "Österreich hat neun Bundesländer:\n- Burgenland\n- Kärnten\n- Niederösterreich\n- Oberösterreich\n- Salzburg\n- Steiermark\n- Tirol\n- Vorarlberg\n- Wien"
    assert belege.woertliche_saetze(antwort, [QUELLE]) == []


def test_abgeschriebener_satz_bleibt_abgeschrieben():
    quelle = ("Die Stadt liegt an der Donau und ist seit dem Mittelalter ein wichtiger Handelsplatz für Salz, Wein und Holz gewesen, "
              "der Reisende aus ganz Europa anzog und den Bürgern großen Wohlstand brachte.")
    antwort = "Die Stadt liegt an der Donau und ist seit dem Mittelalter ein wichtiger Handelsplatz gewesen."
    assert belege.woertliche_saetze(antwort, [quelle]) == [antwort]


def test_wortliste_ohne_namen():
    assert antwortspeicher_basis.wortliste("Es grenzen Deutschland, Tschechien und die Schweiz an.") == ["es", "grenzen", "an"]
    assert antwortspeicher_basis.wortliste("Zwei Namen: Anna und Paul.") == ["zwei", "namen", "anna", "und", "paul"]
