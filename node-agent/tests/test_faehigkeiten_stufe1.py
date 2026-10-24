# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import nachschauen


def _anhang(name: str, info: str, text: str) -> str:
    return f"\n\nDatei „{name}“ ({info}):\n{text}"


REIFEN = _anhang("IMG_8980.png", "Text aus dem Foto", "reifenleader.at\n< Zurück | Continental > WinterContact TS870P\n"
                 "CONTINENTAL WINTERCONTACT TS870P 255/55 R20 110V DOT 2022 XL 3PMSF\nWinterreifen\nStückpreis\n183,59 €\nLieferbar")
ANGEBOT = _anhang("Angebot_Malerei.pdf", "PDF", "Malermeister Huber GmbH\nAngebot Nr. 2026-114\nInnenanstrich Wohnung 85 m² Wände und Decken, "
                  "Dispersionsfarbe weiß\nGesamt netto 3.450,00 €\nMwSt 20 % 690,00 €\nGesamt brutto 4.140,00 €")
RECHNUNG = _anhang("IMG_1.jpg", "Text aus dem Foto", "Gasthaus Post\n2 Schnitzel 31,80\n2 Bier 9,60\nSumme 41,40")
BRIEF = _anhang("IMG_2.jpg", "Text aus dem Foto", "Liebe Anna, danke für die Einladung zum Geburtstag. Wir kommen gerne.")


def _u(text: str) -> dict:
    return {"role": "user", "content": text}


def _a(text: str) -> dict:
    return {"role": "assistant", "content": text}


SZENARIEN = [
    ("Foto: günstigster Anbieter im Internet", [_u("Im Anhang der Reifen den ich kaufen möchte, such mir den günstigsten Anbieter im Internet" + REIFEN)],
     True, ["WINTERCONTACT", "TS870P"], False, False),
    ("Foto: günstigster ohne „Internet“", [_u("Wo bekomme ich den Reifen auf dem Foto am günstigsten?" + REIFEN)],
     True, ["WINTERCONTACT"], False, False),
    ("Photo: cheapest shop (EN)", [_u("Find me the cheapest shop online for the tyre in the attached photo" + REIFEN)],
     True, ["WINTERCONTACT"], False, False),
    ("PDF: günstigeres Angebot", [_u("Such mir ein günstigeres Angebot als das im Anhang" + ANGEBOT)],
     True, ["Innenanstrich"], False, False),
    ("PDF: ist das Angebot fair", [_u("Ist das Angebot im Anhang fair?" + ANGEBOT)], True, ["Innenanstrich"], False, False),
    ("Foto: Text abschreiben", [_u("Schreib mir den Text vom Foto ab" + BRIEF)], False, [], False, False),
    ("Foto: Rechnung, keine Dateifrage", [_u("Stimmt die Summe auf dem Foto?" + RECHNUNG)], None, [], False, False),
    ("Video: Gameplay", [_u("Zeig mir Gameplay zu Enshrouded")], True, ["Enshrouded"], False, True),
    ("Video: Nachfrage „Zeig es mir hier“", [_u("Zeig mir einsteiger Guide Video zu Enshrouded"), _a("Es gibt einen Einsteiger-Guide als Video."),
                                            _u("Zeig es mir hier")], True, ["Enshrouded"], False, True),
    ("Video: „das Video hier sehen“", [_u("Zeig mir einsteiger Guide Video zu Enshrouded"), _a("Es gibt einen Einsteiger-Guide als Video."),
                                      _u("Ich möchte das Video direkt hier sehen")], True, ["Enshrouded"], False, True),
    ("Reifengröße ohne Foto", [_u("Winterreifen 205/55 R16 günstig kaufen")], True, ["205", "R16"], False, False),
    ("Datei daheim", [_u("wo ist meine Stromrechnung")], None, [], True, False),
    ("Datei daheim (EN)", [_u("Where is my job application?")], None, [], True, False),
]


@pytest.mark.parametrize("name,gespraech,denkbar,woerter,datei,video", SZENARIEN, ids=[s[0] for s in SZENARIEN])
def test_szenario(name, gespraech, denkbar, woerter, datei, video):
    f = app_web.suchfrage(gespraech)
    letzte = gespraech[-1]["content"]
    if denkbar is not None:
        assert app_web.suche_denkbar(f) is denkbar, f"{name}: Suche denkbar sollte {denkbar} sein, Suchfrage „{f}“"
    regel = nachschauen.suchbegriffe_regel(f)
    for w in woerter:
        assert w in f and w in regel, f"{name}: „{w}“ fehlt in der Suche („{regel}“)"
    assert "IMG_" not in f and "Datei „" not in f, f"{name}: der Kopf des Anhangs steht in der Suche"
    assert nachschauen.ist_dateifrage(letzte) is datei, f"{name}: Dateifrage sollte {datei} sein"
    assert bool(nachschauen._VIDEO_WORT.search(f)) is video, f"{name}: Videowunsch sollte {video} sein"


@pytest.mark.parametrize("name", ["Foto: günstigster Anbieter im Internet", "Foto: günstigster ohne „Internet“", "Photo: cheapest shop (EN)"])
def test_vergleich_mit_dem_angebot_im_anhang(name):
    gespraech = next(s[1] for s in SZENARIEN if s[0] == name)
    assert app_web.belege.vergleichsfrage(app_web.suchfrage(gespraech)), name
    letzte = gespraech[-1]["content"]
    anhang = letzte[len(app_web.schriftstueck.eigene_worte(letzte)[0]):]
    neu, weg = app_web.vergleich_zeilen_pruefen("| Anbieter | Preis | Hinweis |\n|---|---|---|\n| Reifenleader | 183,59 € | aus deinem Anhang, DOT 2022 |\n"
                                                "| Reifenleader | 179,99 € | |", [], anhang=anhang)
    assert weg == 1 and "183,59" in neu and "179,99" not in neu, name
