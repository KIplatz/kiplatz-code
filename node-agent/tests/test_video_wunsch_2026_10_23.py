# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web

WUNSCH = [
    "Zeig mir ein Video", "Zeig mir ein Video dazu", "Zeig mir bitte Videos zu Enshrouded", "Kannst du mir ein Video schicken?",
    "Schick mir ein Video zu der Quest", "Gibt es dazu ein Video?", "Gibt es ein Video, das das erklärt?", "Hast du ein Video dazu?",
    "Ich möchte das Video dazu anschauen", "Such mir ein Video zu Enshrouded", "Finde ein Video für Anfänger", "Gib mir ein Video",
    "Live nachprüfen: Zeig mir ein Video", "Show me a video", "Is there a video for this quest?", "Can you send me a video?",
    "Do you have a video about it?", "Find a video for beginners", "Zeig mir das Video davon",
]
KEIN_WUNSCH = [
    "Wie hoch ist die Zugspitze?", "Wie schneide ich ein Video in Premiere?", "Wie lange dauert es, ein Video zu schneiden?",
    "Welche Auflösung hat ein 4K Video mit 60 Bildern?", "Zeig mir den Weg nach Wien", "Such mir ein gutes Rezept für Gulasch",
    "Wie viel kostet ein Videoprojektor?", "How do I edit a video file?", "Gib mir die Hauptstadt von Peru",
]


def test_ein_videowunsch_bekommt_die_linkanweisung():
    for f in WUNSCH:
        assert app_web.linkfrage(f), f
        assert app_web.LINK_FOKUS in app_web.mit_fokus("", f), f


def test_andere_fragen_bekommen_sie_nicht():
    for f in KEIN_WUNSCH:
        assert not app_web.linkfrage(f), f


def test_die_anweisung_verlangt_titel_und_ganze_adresse():
    assert "Titel" in app_web.LINK_FOKUS and "ganze" in app_web.LINK_FOKUS and "erfinde nie eine Adresse" in app_web.LINK_FOKUS
