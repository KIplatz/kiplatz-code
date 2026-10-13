# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wikipedia
from test_bau_24n import DOCS, bis_fertig, doc, kopie, netz, teil_bytes

SALZBURG = doc(20, "Salzburg", "Salzburg ist die Landeshauptstadt des österreichischen Bundeslandes Salzburg und hat rund 157.000 Einwohner.",
               template=["Vorlage:Begriffsklärungshinweis", "Vorlage:Infobox Gemeinde in Österreich"])
KLAERUNG = doc(21, "Salzburg (Begriffsklärung)", "Salzburg steht für mehrere Orte.", template=["Vorlage:Begriffsklärung"])


def test_ein_artikel_mit_hinweis_oben_wird_eingelesen_die_klaerungsseite_nicht():
    assert wikipedia.dokument_lesen(SALZBURG)["titel"] == "Salzburg"
    assert wikipedia.dokument_lesen(KLAERUNG) is None


def test_eine_alte_kopie_liest_sich_neu_ein_und_findet_salzburg(tmp_path):
    teile = [teil_bytes(DOCS + [SALZBURG, KLAERUNG])]
    w = kopie(tmp_path, netz(teile))
    bis_fertig(w)
    assert w._stand()["einlese_stand"] == wikipedia.EINLESE_STAND
    st = w._stand()
    st.pop("einlese_stand")
    w._stand_setzen(**st)
    w._stand_setzen(einlese_stand=1, zuletzt_gesucht=w._jetzt())
    w.schritt()
    assert w._stand().get("bau_ausgabe") == "20260920"
    bis_fertig(w)
    assert w._stand()["einlese_stand"] == wikipedia.EINLESE_STAND and not w._stand().get("bau_ausgabe")
    assert w._db.artikel_zu("salzburg") == 20
