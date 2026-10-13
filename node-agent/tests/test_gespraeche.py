# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

import app_core
import gespraeche


def test_new_conversation_title_from_first_question_and_reload(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu()
    assert g.titel == "Neues Gespräch" and (a.ordner / f"{g.kennung}.json").exists()
    a.anhaengen(g, "user", "Was ist ein Arbeitsspeicher und wozu braucht man ihn im Alltag wirklich?")
    a.anhaengen(g, "assistant", "Kurz gesagt: das Kurzzeitgedächtnis.", lieferschein={"modell": "Ministral 3 8B", "dauer_s": 2.5})
    assert g.titel.endswith("…") and len(g.titel) <= 49
    neu = a.laden(g.kennung)
    assert [n["rolle"] for n in neu.nachrichten] == ["user", "assistant"] and neu.nachrichten[1]["lieferschein"]["modell"] == "Ministral 3 8B"
    assert neu.fuer_modell() == [{"role": "user", "content": neu.nachrichten[0]["text"]}, {"role": "assistant", "content": "Kurz gesagt: das Kurzzeitgedächtnis."}]
    liste = a.liste()
    assert liste and liste[0]["kennung"] == g.kennung and liste[0]["anzahl"] == 2


def test_limits_and_bad_ids(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu()
    with pytest.raises(app_core.AppError) as e:
        a.anhaengen(g, "user", "   ")
    assert e.value.code == "GESPRAECH_LEER"
    with pytest.raises(app_core.AppError):
        a.anhaengen(g, "system", "nein")
    with pytest.raises(app_core.AppError):
        a.laden("../boese")
    with pytest.raises(app_core.AppError) as e2:
        a.laden("gibtsnicht")
    assert e2.value.code == "GESPRAECH_FEHLT"
    assert gespraeche.Gespraechsablage(tmp_path / "leer").liste() == []


def test_rename_and_delete_from_the_right_click_menu(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu()
    a.anhaengen(g, "user", "Wie wird das Wetter?")
    assert a.umbenennen(g.kennung, "  Wetter   Fragen ").titel == "Wetter Fragen" and a.laden(g.kennung).titel == "Wetter Fragen"
    with pytest.raises(app_core.AppError) as e:
        a.umbenennen(g.kennung, "   ")
    assert e.value.code == "GESPRAECH_TITEL"
    with pytest.raises(app_core.AppError):
        a.umbenennen(g.kennung, "x" * 81)
    g = a.laden(g.kennung)
    a.anhaengen(g, "assistant", "Nebel, 21 Grad.")
    assert a.bewerten(g.kennung, 1, "gut") == "gut" and a.laden(g.kennung).nachrichten[1]["bewertung"] == "gut"
    assert a.bewerten(g.kennung, 1, "") == "" and "bewertung" not in a.laden(g.kennung).nachrichten[1]
    with pytest.raises(app_core.AppError):
        a.bewerten(g.kennung, 0, "gut")
    with pytest.raises(app_core.AppError):
        a.bewerten(g.kennung, 1, "super")
    assert a.loeschen(g.kennung) == "Wetter Fragen"
    assert not (a.ordner / f"{g.kennung}.json").exists() and (a.ordner / "papierkorb" / f"{g.kennung}.json").exists()
    assert a.liste() == []
    with pytest.raises(app_core.AppError) as e2:
        a.loeschen(g.kennung)
    assert e2.value.code == "GESPRAECH_FEHLT"


def test_projects_archive_and_thumbs_down_with_reason(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    g = a.neu(); a.anhaengen(g, "user", "Wann hat das Freibad offen?"); g = a.laden(g.kennung); a.anhaengen(g, "assistant", "Von 8 bis 22 Uhr.")
    h = a.neu(); a.anhaengen(h, "user", "Rechnung schreiben")
    assert a.projekte() == []
    assert a.verschieben(g.kennung, "  Familie  ").projekt == "Familie" and a.laden(g.kennung).projekt == "Familie"
    assert a.verschieben(h.kennung, "Betrieb").projekt == "Betrieb" and a.projekte() == ["Betrieb", "Familie"]
    with pytest.raises(app_core.AppError) as e:
        a.verschieben(g.kennung, "x" * 61)
    assert e.value.code == "GESPRAECH_PROJEKT"
    assert a.verschieben(h.kennung, "").projekt == "" and a.projekte() == ["Familie"]
    assert a.archivieren(h.kennung).archiviert is True and a.laden(h.kennung).archiviert is True
    liste = {e["kennung"]: e for e in a.liste()}
    assert liste[g.kennung]["projekt"] == "Familie" and liste[g.kennung]["archiviert"] is False and liste[h.kennung]["archiviert"] is True
    assert a.archivieren(h.kennung, False).archiviert is False
    assert a.bewerten(g.kennung, 1, "schlecht", grund="Das Bad hat erst ab 9 offen.", vorschlag="9 bis 20 Uhr") == "schlecht"
    n = a.laden(g.kennung).nachrichten[1]
    assert n["bewertung"] == "schlecht" and n["rueckmeldung"] == {"grund": "Das Bad hat erst ab 9 offen.", "vorschlag": "9 bis 20 Uhr"}
    assert a.bewerten(g.kennung, 1, "gut") == "gut" and "rueckmeldung" not in a.laden(g.kennung).nachrichten[1]


def test_pin_and_export(tmp_path):
    a = gespraeche.Gespraechsablage(tmp_path)
    alt = a.neu(); a.anhaengen(alt, "user", "Erstes Gespräch")
    alt = a.laden(alt.kennung); alt.geaendert = "2026-01-01T00:00:00Z"; a.speichern(alt)
    neu = a.neu(); a.anhaengen(neu, "user", "Zweites Gespräch"); neu = a.laden(neu.kennung)
    a.anhaengen(neu, "assistant", "Eine Antwort.", lieferschein={"quellen": "Freibad Gmunden (https://x), gelesen 2026-09-18"})
    assert [e["kennung"] for e in a.liste()] == [neu.kennung, alt.kennung]
    assert a.anheften(alt.kennung).angeheftet is True and [e["kennung"] for e in a.liste()] == [alt.kennung, neu.kennung]
    assert a.anheften(alt.kennung, False).angeheftet is False and [e["kennung"] for e in a.liste()][0] == neu.kennung
    p = a.exportieren(neu.kennung, tmp_path / "raus")
    t = p.read_text(encoding="utf-8")
    assert p.name.endswith(f"({neu.kennung}).md") and t.startswith("# Zweites Gespräch") and "## Ich" in t and "## KIplatz" in t and "*Woher: Freibad Gmunden" in t
