# SPDX-License-Identifier: AGPL-3.0-or-later
import ki_laufzeit as kl


LISTE = "- Elektro-Axial-Laubbläser (1.650 W) für 69,99 € statt 79,99 €, nur online bis 01.11."


def test_datum_ist_kein_satzende():
    assert kl.bis_zum_letzten_satz(LISTE + "\n\nAb 29.10. gibt es außerdem Kürbis für 1,") == LISTE


def test_ankuendigung_ohne_liste_faellt():
    roh = "Bei Lidl gibt es diese Woche viele Angebote.\n\nAb 29.10. kommen:\n- Kürbis um 1,"
    assert kl.bis_zum_letzten_satz(roh) == "Bei Lidl gibt es diese Woche viele Angebote."


def test_fertige_listenzeile_bleibt():
    roh = "Diese Angebote gibt es:\n- Äpfel rot (3 kg) für 1,99 €\n- Rupp-Käse (175 g) für 2,19 €\n- Pausenstangerl für 1,"
    assert kl.bis_zum_letzten_satz(roh) == "Diese Angebote gibt es:\n- Äpfel rot (3 kg) für 1,99 €\n- Rupp-Käse (175 g) für 2,19 €"


def test_ganze_saetze_der_letzten_zeile_bleiben():
    roh = "Am 3. Mai ist Feiertag. Ab 29.10. gibt es Kürbis. Das Lagerhaus hat eine B"
    assert kl.bis_zum_letzten_satz(roh) == "Am 3. Mai ist Feiertag. Ab 29.10. gibt es Kürbis."


def test_englisch():
    assert kl.bis_zum_letzten_satz("The store opens on Monday. Prices start at 4") == "The store opens on Monday."
