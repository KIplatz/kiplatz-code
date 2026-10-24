# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen

FOTO = ("\n\nDatei „IMG_8980.png“ (Text aus dem Foto):\nreifenleader.at\n< Zurück | Continental > WinterContact TS870P\n"
        "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V DOT 2022 XL 3PMSF\nWinterreifen\nStückpreis\n183,59 €\nLieferbar")


def test_die_suche_kennt_den_reifen_vom_foto_und_findet_statt():
    f = app_web.suchfrage([{"role": "user", "content": "Im Anhang der Reifen den ich kaufen möchte, such mir den günstigsten Anbieter im Internet" + FOTO}])
    assert f.startswith("CONTINENTAL WINTERCONTACT TS870P 255/55 R20") and "Anhang" not in f and "183" not in f and "IMG_8980" not in f
    assert app_web.suche_denkbar(f)
    assert "WINTERCONTACT" in nachschauen.suchbegriffe_regel(f)


def test_ohne_bezug_auf_den_anhang_nur_die_eigenen_worte():
    assert app_web.suchfrage([{"role": "user", "content": "Fass mir den Text zusammen" + FOTO}]) == "Fass mir den Text zusammen"
    assert app_web.suchfrage([{"role": "user", "content": "Wie hoch ist der Großglockner?"}]) == "Wie hoch ist der Großglockner?"


def test_im_internet_hebt_jede_regel_auf():
    assert app_web.suche_denkbar("Rechne 2022 x 3 und such den Preis im Internet")
