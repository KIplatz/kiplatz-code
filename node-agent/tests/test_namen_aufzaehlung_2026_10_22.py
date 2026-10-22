# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belege

AUFZAEHLUNGEN = [
    ("Besonders Zucker, Marmelade und Fleisch ziehen sie an.", "Zucker Marmelade"),
    ("Das Ticket gilt für Busse, Bahnen und Straßenbahnen.", "Busse Bahnen"),
    ("Gerüche entstehen durch Schimmel, Bakterien und Waschmittelreste.", "Schimmel Bakterien"),
    ("Die Reihenfolge ist Rot, Orange, Gelb, Grün, Blau, Indigo und Violett.", "Rot Orange Gelb Grün Blau Indigo"),
    ("Prüfe die Ordner Spam; Werbung und Papierkorb.", "Spam Werbung"),
    ("Hilft Essig/Zitrone gegen Kalk?", "Essig Zitrone"),
]


def test_ein_beistrich_beendet_die_wortgruppe():
    for satz, frueher in AUFZAEHLUNGEN:
        _sicher, verdacht = belege.namen(satz)
        assert frueher not in verdacht, (satz, verdacht)
        assert not any(frueher.split()[0] in v and frueher.split()[1] in v for v in verdacht), (satz, verdacht)


def test_echte_namen_bleiben_eine_gruppe():
    assert belege.namen("Trainer ist Vincent Kompany.")[1] == ["Vincent Kompany"]
    assert "Bad Ischl" in belege.namen("Sie wohnt in Bad Ischl, Oberösterreich.")[1]
    assert "Rudolf Steiner" in belege.namen("Die Schule geht auf Rudolf Steiner zurück.")[1]
