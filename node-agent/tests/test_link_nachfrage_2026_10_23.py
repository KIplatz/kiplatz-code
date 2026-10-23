# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege
import nachschauen

GESPRAECH = [{"role": "user", "content": "Wie löse ich das Rätsel „Untersuche die Säule“ in Runescape Dragonwilds?"},
             {"role": "assistant", "content": "Untersuche die Säule und drehe die Symbole, bis sie passen. Die Belohnung ist eine Goldtruhe mit 75 XP. "
                                              "Falls du Hilfe brauchst, gibt es auch eine Video-Anleitung auf YouTube."},
             {"role": "user", "content": "Kannst du mir den link des youtube videos bitte schicken"}]


def test_die_nachfrage_sucht_mit_der_sache_der_vorigen_frage():
    s = app_web.suchfrage(GESPRAECH)
    assert "Runescape Dragonwilds" in s and "youtube" in s.lower()
    live = GESPRAECH[:-1] + [{"role": "user", "content": "Live nachprüfen: Kannst du mir den link des youtube videos bitte schicken"}]
    assert "Runescape Dragonwilds" in app_web.suchfrage(live)
    neu = GESPRAECH[:-1] + [{"role": "user", "content": "Wie hoch ist die Zugspitze in Bayern?"}]
    assert app_web.suchfrage(neu) == "Wie hoch ist die Zugspitze in Bayern?"


def test_eine_linkfrage_bekommt_die_anweisung_und_videos_ihre_ganze_adresse():
    assert app_web.linkfrage(GESPRAECH[-1]["content"]) and not app_web.linkfrage("Wie hoch ist die Zugspitze?")
    assert app_web.LINK_FOKUS in app_web.mit_fokus("Quelle 1: …", app_web.suchfrage(GESPRAECH))
    assert nachschauen._zeilen_adresse("https://www.youtube.com/watch?v=abc123") == "https://www.youtube.com/watch?v=abc123"
    assert "watch" not in nachschauen._zeilen_adresse("https://www.chip.de/news/watch?x=1")


def test_ein_erfundener_link_faellt_ein_echter_bleibt():
    quelle = "Quelle 1: Runescape Dragonwilds Säule (https://www.youtube.com/watch?v=abc123)"
    erfunden = belege.streng_pruefen("Das Video findest du unter https://www.youtube.com/watch?v=erfunden1.", quelle)
    assert erfunden and "https://www.youtube.com/watch?v=erfunden1" in erfunden[0].namen
    echt = belege.streng_pruefen("Das Video findest du unter https://www.youtube.com/watch?v=abc123.", quelle)
    assert not any(b.namen for b in echt)


def test_fable_rueckbezug_eng_und_links_ganz():
    vf, va = "Wie hoch ist der Stephansdom?", "Der Stephansdom in Wien ist 136 Meter hoch."
    assert not app_web.nachfrage_mit_bezug("Wie ist das Wetter in Wien?", vf, va)
    assert not app_web.nachfrage_mit_bezug("Wie viele Minuten hat der Tag?", "Wie koche ich Reis?", "Reis kocht etwa 20 Minuten.")
    for f in ("Schick mir die Adresse davon", "Wie ist das Wetter dort?", "Kannst du mir den Link schicken?"):
        assert app_web.nachfrage_mit_bezug(f, vf, va), f
    quelle = "Quelle 1: Säule (https://www.youtube.com/watch?v=abcDEF1)"
    for gut in ("https://youtube.com/watch?v=abcDEF1", "https://youtu.be/abcDEF1", "https://www.youtube.com/watch?v=abcDEF1&t=30s",
                "http://www.youtube.com/watch?v=abcDEF1/"):
        assert not any(b.namen for b in belege.streng_pruefen(f"Das Video: {gut}.", quelle)), gut
    for schlecht in ("https://www.youtube.com/watch?v=abcDE", "https://www.youtube.com/watch?v=ERFUNDEN", "https://www.youtube.com"):
        b = belege.streng_pruefen(f"Das Video: {schlecht}.", quelle)
        assert b and b[0].namen, schlecht
