# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web


def test_eigene_suchwoerter():
    assert app_web.gesucht_satz("Wo gibt es diese Woche Holzbriketts im Angebot?", ["Holzbriketts Aktion", "Briketts Flugblatt"]) \
        == "Gesucht wurde nach „Holzbriketts Aktion“ und „Briketts Flugblatt“; nur diese Suchwörter gingen an die Suche, nicht deine Frage."
    assert app_web.gesucht_satz("Wo gibt es Holzbriketts?", ["Holzbriketts Aktion"], "at") \
        == "Gesucht wurde nach „Holzbriketts Aktion“; nur diese Suchwörter gingen an die Suche, nicht deine Frage. Die Suche war auf Österreich zugeschnitten."


def test_die_frage_selbst_ging_hinaus():
    frage = "Wo gibt es  diese Woche Holzbriketts im Angebot?"
    assert app_web.gesucht_satz(frage, ["wo gibt es diese woche holzbriketts im angebot?"]) \
        == "Gesucht wurde nach „wo gibt es diese woche holzbriketts im angebot?“; dafür ging deine Frage selbst an die Suche."
