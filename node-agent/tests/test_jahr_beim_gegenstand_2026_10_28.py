# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belege

FRAGE = "Seit wann gibt es den Europark in Salzburg"
QUELLE = ("Ihr Entwurf ging als Sieger aus einem Gutachterverfahren hervor, das Anfang 1994 durchgeführt worden war. Die Eröffnung erfolgte nach "
          "30-monatiger Bauzeit am 24. September 1997. Der Europark wurde von Anfang 2004 bis Herbst 2005 baulich erweitert.\n"
          "Seit Anfang 2026 wird am Europark Salzburg gebaut. Rund 40 Millionen Euro investiert die Firma in die Erweiterung.")


def test_das_jahr_der_eroeffnung_bleibt_stehen():
    for satz in ("Den Europark in Salzburg gibt es seit dem 24. September 1997.", "Den Europark in Salzburg gibt es seit 1997."):
        assert belege.streng_pruefen(satz, QUELLE, frage=FRAGE) == [], satz


def test_ein_jahr_ohne_quelle_faellt_weiter():
    assert belege.streng_pruefen("Den Europark in Salzburg gibt es seit 1999.", QUELLE, frage=FRAGE)[0].zahlen == ("1999",)


def test_ein_belegtes_ganzes_datum_braucht_keinen_wortvergleich():
    assert belege.streng_pruefen("Den Europark in Salzburg gibt es seit dem 24. September 1997.", QUELLE) == []


def test_das_jahr_gehoert_weiter_zur_sache():
    q = ("Erst 1884 wurde der Vorschlag von Horace Jones genehmigt. Die Bauarbeiten begannen mit der Grundsteinlegung am 21. Juni 1886. "
         "Die Brücke wurde 1894 eröffnet.")
    assert belege.streng_pruefen("Der Bau begann 1884 mit der Grundsteinlegung.", q, frage="Wann wurde die Tower Bridge gebaut?")[0].zahlen == ("1884",)
    assert belege.streng_pruefen("Der Bau begann 1886 mit der Grundsteinlegung.", q, frage="Wann wurde die Tower Bridge gebaut?") == []
    assert belege.gegenstand_staemme(FRAGE) == {"europa", "salzbu"}
