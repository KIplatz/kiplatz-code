# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen


def _foto(name: str, zeile: str) -> str:
    return f"\n\nDatei „{name}“ (Text aus dem Foto):\nreifenleader.at\n< Zurück | Continental\n{zeile}\nWinterreifen\nStückpreis\n183,59 €\nLieferbar"


CONTI = _foto("IMG_8980.png", "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V DOT 2022 XL 3PMSF")
MICHELIN = _foto("a.png", "MICHELIN PILOT ALPIN 5 255/55 R20 110V XL")
BRIDGESTONE = _foto("b.png", "BRIDGESTONE BLIZZAK LM005 255/55 R20 110V XL")
RUECKFRAGE = "Damit ich ehrlich vergleichen kann, brauche ich noch: das Land, in dem du kaufst (die Händler dort zählen, nicht die eines anderen Landes)."


def _g(*texte):
    return [{"role": ("user", "assistant")[i % 2], "content": t} for i, t in enumerate(texte)]


def test_der_fall_vom_iphone_sucht_den_reifen():
    f = app_web.suchfrage(_g("Suche mir günstigere Angebote" + CONTI, RUECKFRAGE, "Deutschland und Österreich"))
    w = nachschauen.suchbegriffe_regel(f)
    assert w.startswith("CONTINENTAL WINTERCONTACT TS870P 255/55 R20") and "Deutschland" in w


@pytest.mark.parametrize("frage", ["Suche mir günstigere Angebote", "Wo bekomme ich das billiger?", "Was kostet der?", "Find me a cheaper offer",
                                   "Gibt es Testberichte dazu?", "Welcher ist besser?", "Lohnt sich der?", "Which one has the best reviews?"])
def test_ohne_eigene_sache_ist_der_anhang_die_sache(frage):
    assert app_web.suchfrage(_g(frage + CONTI)).startswith("CONTINENTAL WINTERCONTACT TS870P")


@pytest.mark.parametrize("frage,erwartet", [("Fass mir den Text zusammen", "Fass mir den Text zusammen"),
                                            ("Such mir Winterreifen 205/55 R16 günstig", "Such mir Winterreifen 205/55 R16 günstig"),
                                            ("Wie hoch ist der Großglockner?", "Wie hoch ist der Großglockner?")])
def test_mit_eigener_sache_bleiben_die_eigenen_worte(frage, erwartet):
    assert app_web.suchfrage(_g(frage + CONTI)) == erwartet


def test_mehrere_anhaenge_je_eine_suche_mit_den_wuenschen():
    n = _g("Wie sind die Testbewertungen und welcher ist am besten und am kostengünstigsten?" + CONTI + MICHELIN + BRIDGESTONE)
    anfragen = app_web.je_anhang([nachschauen.suchbegriffe_regel(app_web.suchfrage(n))], n)
    assert [a.split()[0] for a in anfragen] == ["CONTINENTAL", "MICHELIN", "BRIDGESTONE"]
    assert all("Testbewertungen" in a and "kostengünstigsten" in a for a in anfragen)
    n2 = _g("Welcher ist günstiger?" + CONTI + MICHELIN, RUECKFRAGE, "Österreich")
    assert app_web.je_anhang(["x"], n2) == ["CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V günstiger Österreich",
                                             "MICHELIN PILOT ALPIN 5 255/55 R20 günstiger Österreich"]
    assert app_web.je_anhang(["eins"], _g("Was kostet der?" + CONTI)) == ["eins"]


def test_tabelle_ohne_randstriche_wird_geprueft():
    t = "Anbieter | Preis | Hinweis\n---|---|---\nLidl (DE) | kein Angebot |\nBILLA (AT) | kein Angebot |\nSPAR (AT) | kein Angebot | ( ..."
    text, weg = app_web.vergleich_zeilen_pruefen(t, [])
    assert weg == 3 and "Lidl" not in text and text.startswith("Auf den gelesenen Seiten stand kein Preis")


def test_preisspalte_am_kopf_und_tabelle_ohne_preise_bleibt():
    q = [{"titel": "Reifen", "adresse": "https://www.reifenleader.at/x", "text": "Continental WinterContact TS870P 183,59 €"}]
    t = "| Reifen | Testnote | Preis |\n|---|---|---|\n| reifenleader | 1,8 | 183,59 € |\n| Billa | 2,0 | kein Angebot |"
    text, weg = app_web.vergleich_zeilen_pruefen(t, q)
    assert weg == 1 and "| reifenleader | 1,8 | 183,59 € |" in text and "Billa" not in text
    noten = "| Reifen | Testnote |\n|---|---|\n| Michelin | gut |\n| Conti | sehr gut |"
    assert app_web.vergleich_zeilen_pruefen(noten, []) == (noten, 0)
