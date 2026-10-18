# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belege


def test_ein_rueckbezug_faellt_mit_der_gestrichenen_behauptung():
    t = "Inflation bedeutet, dass Geld weniger wert wird. Ein Kilo Äpfel kostet 2 Euro. Dann bekommst du für dein Geld weniger. Zentralbanken steuern das."
    rest, raus = belege.saetze_streichen(t, lambda s: "Äpfel" in s, mitnehmen=True)
    assert rest == "Inflation bedeutet, dass Geld weniger wert wird. Zentralbanken steuern das." and len(raus) == 2
    assert belege.saetze_streichen(t, lambda s: "Äpfel" in s)[0].count("Dann") == 1
    eigen = "Das Wiener Riesenrad steht im Prater. Es hat 15 Gondeln. Das Riesenrad wurde 1897 eröffnet."
    assert "Das Riesenrad wurde 1897" in belege.saetze_streichen(eigen, lambda s: "15 Gondeln" in s, mitnehmen=True)[0]


def test_vergangene_termine_lassen_den_naechsten_stehen():
    t = "Am 20.9. spielte Bayern gegen Hoffenheim. Danach am 3.10. gegen Augsburg."
    assert belege.saetze_streichen(t, lambda s: "20.9." in s)[0] == "Danach am 3.10. gegen Augsburg."


def test_eine_ankuendigung_ohne_ihre_aufzaehlung_faellt_mit_und_listen_werden_neu_gezaehlt():
    t = "Nutze ein Ortungsgerät. So gehst du vor:\n\n1. Zonen kennen: 20 bis 30 Zentimeter.\n\n2. Gerät an die Wand halten.\n\n3. Nie blind bohren."
    rest, _ = belege.saetze_streichen(t, lambda s: "Zentimeter" in s, mitnehmen=True)
    assert "1. Gerät an die Wand halten." in rest and "2. Nie blind bohren." in rest and "So gehst du vor:" in rest
    rest, raus = belege.saetze_streichen("Beliebte Mittel:\n- Essig mit 5 % Säure.\n- Backpulver mit 3 g je Liter.\nLüften hilft immer.",
                                         lambda s: "%" in s or " g " in s, mitnehmen=True)
    assert rest == "Lüften hilft immer." and "Beliebte Mittel:" in raus
