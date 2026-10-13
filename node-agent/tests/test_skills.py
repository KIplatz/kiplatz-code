# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_core
import skills
import gespraeche
import gespraeche_import as gi

SKILL = """---
name: Rechnung nach § 11 UStG
description: Eine Rechnung mit allen Pflichtangaben nach österreichischem Recht.
---

# Rechnung

1. Frag zuerst nach Menge, Preis und Empfänger.
2. Rechne netto, USt 20 %, brutto; das Programm prüft die Summen.
3. Pflichtangaben nach § 11 UStG: Name und Anschrift beider, Datum, fortlaufende Nummer, UID.
"""


def test_a_skill_is_read_stored_applied_exported_and_imported(tmp_path):
    b = skills.lesen(SKILL, quelle="selbst")
    assert b.name == "rechnung-nach-11-ustg" and b.beschreibung.startswith("Eine Rechnung") and "Pflichtangaben" in b.text
    k = skills.Skillkiste(tmp_path)
    k.speichern(b)
    assert [x["name"] for x in k.liste()] == ["rechnung-nach-11-ustg"] and (k.ordner / "rechnung-nach-11-ustg" / "SKILL.md").is_file()
    assert k.laden("rechnung-nach-11-ustg").quelle == "selbst"
    v = skills.vorspann(b)
    assert v.startswith("Für dieses Gespräch gilt der Skill „rechnung-nach-11-ustg“") and "nichts erfinden" in v and "§ 11 UStG" in v
    b2 = skills.lesen("# Bewerbung schreiben\n\nSo klingt eine Bewerbung: kurz, konkret, ohne Floskeln, mit einem Satz zum Betrieb.")
    assert b2.name == "bewerbung-schreiben" and b2.beschreibung.startswith("So klingt")
    for schlecht, code in (("---\nname: x\n---\nzu kurz", "SKILL_LEER"), ("x" * 30_000, "SKILL_GROSS")):
        with pytest.raises(app_core.AppError) as e:
            skills.lesen(schlecht)
        assert e.value.code == code
    z = k.exportieren("rechnung-nach-11-ustg", tmp_path / "raus")
    assert z.name == "rechnung-nach-11-ustg.zip" and zipfile.ZipFile(z).namelist() == ["rechnung-nach-11-ustg/SKILL.md"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zz:
        zz.writestr("skills/brief/SKILL.md", "---\nname: brief\ndescription: Ein Brief.\n---\n\nSchreib den Brief kurz, mit Anrede und Gruß, und frag nach dem Empfänger.")
        zz.writestr("skills/brief/scripts/run.py", "import os; os.system('rm -rf /')")
        zz.writestr("skills/brief/bild.png", b"x" * 10)
    k2 = skills.Skillkiste(tmp_path / "zwei")
    neu = k2.importieren(buf.getvalue())
    assert [x.name for x in neu] == ["brief"] and neu[0].quelle == "importiert"
    assert not list((k2.ordner / "brief").glob("*.py")) and not list((k2.ordner / "brief").glob("*.png"))
    boese = io.BytesIO()
    with zipfile.ZipFile(boese, "w") as zz:
        zz.writestr("../../SKILL.md", "---\nname: x\n---\n" + "a" * 40)
    with pytest.raises(app_core.AppError) as e2:
        k2.importieren(boese.getvalue())
    assert e2.value.code == "SKILL_DATEI"
    assert k.entfernen("rechnung-nach-11-ustg") and k.liste() == [] and not k.entfernen("rechnung-nach-11-ustg")


def _chatgpt_export():
    return [{"title": "Wetter und Urlaub", "create_time": 1758200000.0, "current_node": "n3", "mapping": {
        "root": {"id": "root", "parent": None, "children": ["n1"], "message": None},
        "n1": {"id": "n1", "parent": "root", "children": ["n2", "n2b"], "message": {"author": {"role": "user"}, "content": {"content_type": "text", "parts": ["Wie wird das Wetter in Linz?"]}}},
        "n2": {"id": "n2", "parent": "n1", "children": ["n3"], "message": {"author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["Sonnig, 24 Grad."]}}},
        "n2b": {"id": "n2b", "parent": "n1", "children": [], "message": {"author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["Alte Antwort, anderer Zweig."]}}},
        "n3": {"id": "n3", "parent": "n2", "children": [], "message": {"author": {"role": "user"}, "content": {"content_type": "text", "parts": ["Danke!"]}}},
    }}, {"title": "leer", "mapping": {}, "current_node": None}]


def test_conversations_of_other_assistants_are_recognised_and_taken_over(tmp_path):
    cg = gi.aus_chatgpt(_chatgpt_export())
    assert len(cg) == 1 and cg[0].titel == "Wetter und Urlaub" and cg[0].herkunft == "ChatGPT" and cg[0].erstellt.startswith("2025-09-18")
    assert [n["text"] for n in cg[0].nachrichten] == ["Wie wird das Wetter in Linz?", "Sonnig, 24 Grad.", "Danke!"]
    cl = gi.aus_claude([{"name": "Rechnung", "created_at": "2026-09-01T10:00:00Z", "chat_messages": [{"sender": "human", "text": "Schreib eine Rechnung."}, {"sender": "assistant", "text": "Gern, wer ist der Empfänger?"}]}])
    assert cl[0].herkunft == "Claude" and [n["rolle"] for n in cl[0].nachrichten] == ["user", "assistant"]
    ow = gi.aus_openwebui([{"title": "Test", "chat": {"title": "Test", "messages": [{"role": "user", "content": "Hallo"}, {"role": "assistant", "content": "Servus"}]}}])
    assert ow[0].herkunft == "Open WebUI" and ow[0].nachrichten[1]["text"] == "Servus"
    md = gi.aus_markdown("# Freibad\n\nCommunity AI Network, Gespräch vom 2026-09-18\n\n## Ich\n\nWann offen?\n\n## KIplatz\n\n9 bis 20 Uhr.\n\n*Woher: Ortswissen*\n")
    assert md[0].titel == "Freibad" and [n["text"] for n in md[0].nachrichten] == ["Wann offen?", "9 bis 20 Uhr."]
    md2 = gi.aus_markdown("User: Hallo\nAssistant: Servus, was brauchst du?\nUser: Nichts.")
    assert [n["rolle"] for n in md2[0].nachrichten] == ["user", "assistant", "user"]
    p = tmp_path / "conversations.json"; p.write_text(json.dumps(_chatgpt_export()), encoding="utf-8")
    assert gi.erkennen(p)[0].herkunft == "ChatGPT"
    zp = tmp_path / "export.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("conversations.json", json.dumps(_chatgpt_export()))
    assert gi.erkennen(zp)[0].herkunft == "ChatGPT"
    (tmp_path / "x.json").write_text("[{\"foo\": 1}]", encoding="utf-8")
    with pytest.raises(app_core.AppError) as e:
        gi.erkennen(tmp_path / "x.json")
    assert e.value.code == "IMPORT_FORM"
    a = gespraeche.Gespraechsablage(tmp_path / "ablage")
    neu = a.importieren(gi.erkennen(p))
    assert len(neu) == 1 and neu[0].projekt == "Import ChatGPT" and neu[0].herkunft == "ChatGPT" and neu[0].titel == "Wetter und Urlaub"
    g = a.laden(neu[0].kennung)
    assert len(g.nachrichten) == 3 and g.nachrichten[0]["rolle"] == "user" and a.liste()[0]["projekt"] == "Import ChatGPT"
    assert a.skill_setzen(g.kennung, "brief").skill == "brief" and a.laden(g.kennung).skill == "brief"


def test_the_old_bausteine_folder_moves_to_skills_once(tmp_path):
    alt = tmp_path / skills.DIRNAME_ALT / "brief"
    alt.mkdir(parents=True)
    (alt / skills.DATEI).write_text("---\nname: brief\ndescription: Ein Brief.\n---\n\n# Brief\n\nSchreib höflich und kurz, mit Anrede und Gruß.\n", encoding="utf-8")
    k = skills.Skillkiste(tmp_path)
    assert k.ordner == tmp_path / "skills" and not (tmp_path / "bausteine").exists()
    assert [x["name"] for x in k.liste()] == ["brief"]
    (tmp_path / "bausteine").mkdir()
    k2 = skills.Skillkiste(tmp_path)
    assert [x["name"] for x in k2.liste()] == ["brief"] and (tmp_path / "bausteine").is_dir()
