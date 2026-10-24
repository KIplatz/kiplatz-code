# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen

FOTO = "Such mir zu dem Reifen im Anhang den günstigsten im Internet!\n\nDatei „IMG_8980.png“ (Text aus dem Foto):\nCONTINENTAL WINTERCONTACT TS870P 255/55 R20"


def test_der_kopf_eines_anhangs_ist_keine_dateifrage():
    assert not nachschauen.ist_dateifrage(FOTO)
    assert not nachschauen.ist_dateifrage(FOTO.replace(" im Internet", ""))


def test_im_internet_ist_keine_dateifrage():
    assert not nachschauen.ist_dateifrage("Such die Datei mit den Reifenpreisen im Internet")
    assert not nachschauen.ist_dateifrage("Find the cheapest tyre documents online")


def test_echte_dateifragen_bleiben():
    assert nachschauen.ist_dateifrage("Bewerbung Huber die Datei suche ich")
    assert nachschauen.ist_dateifrage("wo ist meine Stromrechnung")
    assert nachschauen.ist_dateifrage("Such meine Datei zur Bewerbung\n\nDatei „x.pdf“ (PDF):\nText")
