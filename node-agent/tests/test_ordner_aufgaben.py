# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import gespraeche
import ordner_aufgaben as oa
import test_app_web


def _ordner(tmp_path):
    o = tmp_path / "Rechnungen"
    o.mkdir()
    (o / "Pool Wartung 2026.txt").write_text("Die Poolpumpe braucht jedes Jahr im Mai einen neuen Filter. Kosten etwa 80 Euro bei der Firma Wasserklar.", encoding="utf-8")
    (o / "Auto.md").write_text("Das Auto war am 3. März beim Service. Nächster Termin: Ölwechsel im Herbst, Reifen wechseln im Oktober.", encoding="utf-8")
    (o / "Notizen.csv").write_text("a;b;c\n1;2;3\nviele Zeilen mit nichts drin\n", encoding="utf-8")
    (o / "bild.png").write_bytes(b"\x89PNG")
    (o / ".versteckt.txt").write_text("nicht zeigen, hier steht was über Pool", encoding="utf-8")
    (o / "unter").mkdir()
    return o


def test_the_folder_is_listed_and_only_fitting_files_are_read(tmp_path):
    o = _ordner(tmp_path)
    u = oa.uebersicht(o)
    assert [e["name"] for e in u] == ["Auto.md", "bild.png", "Notizen.csv", "Pool Wartung 2026.txt"]
    assert [e["lesbar"] for e in u] == [True, False, True, True]
    w = oa.auswahl(o, "Wann braucht die Poolpumpe einen neuen Filter?")
    assert [d["name"] for d in w][0] == "Pool Wartung 2026.txt" and "Wasserklar" in w[0]["text"]
    assert oa.auswahl(o, "Was steht in Auto?")[0]["name"] == "Auto.md"
    v = oa.vorspann("Rechnungen", w, u)
    assert "Rechnungen" in v and "bild.png" in v and "Wasserklar" in v and "nichts erfinden" in v or "erfinde nichts" in v
    with pytest.raises(app_core.AppError):
        oa.uebersicht(tmp_path / "gibt-es-nicht")
    with pytest.raises(app_core.AppError) as e:
        oa.pruefen(Path(o.anchor))
    assert e.value.code == "ORDNER_WURZEL"


def test_saving_never_overwrites_and_never_leaves_the_folder(tmp_path):
    o = _ordner(tmp_path)
    p1 = oa.speichern(o, "Brief ans Amt", "Sehr geehrte Damen und Herren")
    p2 = oa.speichern(o, "Brief ans Amt", "zweiter")
    assert p1.name == "Brief ans Amt.md" and p2.name == "Brief ans Amt (2).md" and p1.read_text(encoding="utf-8").startswith("Sehr")
    p3 = oa.speichern(o, "../../raus.txt", "x")
    assert p3.parent == o.resolve() and p3.name == "raus.txt"
    assert oa.dateiname('a/b:c*?"<>|.txt') == "abc.txt" and oa.dateiname("") == "Antwort.md" and oa.dateiname("  .. ") == "Antwort.md"
    assert set(x.name for x in o.iterdir()) >= {"Brief ans Amt.md", "Brief ans Amt (2).md", "raus.txt"}


def test_the_conversation_reads_its_folder_and_saves_an_answer_into_it(tmp_path):
    o = _ordner(tmp_path)
    api, fake, _ = test_app_web._api(tmp_path / "api")
    g = api.gespraech_neu()["daten"]
    api._ablage.ordner_setzen(g["kennung"], str(o))
    assert api.gespraech_ordner_dateien(g["kennung"])["daten"][0]["name"] == "Auto.md"
    r = api.frage(g["kennung"], "Wann ist der nächste Termin fürs Auto?")
    assert r["ok"], r["text"]
    assert "Auto.md" in r["daten"]["lieferschein"]["quellen"] and "Ordner „Rechnungen“ mitgelesen" in r["daten"]["lieferschein"]["quellen"]
    nummer = len(r["daten"]["gespraech"]["nachrichten"]) - 1
    s = api.gespraech_in_ordner_speichern(g["kennung"], nummer, "Termine")
    assert s["ok"] and (o / "Termine.md").read_text(encoding="utf-8").strip() == "Servus, Huber."
    assert not api.gespraech_in_ordner_speichern(g["kennung"], nummer - 1, "x")["ok"]
    r2 = api.gespraech_ordner_entfernen(g["kennung"])
    assert r2["ok"] and r2["daten"]["ordner"] == "" and not api.gespraech_in_ordner_speichern(g["kennung"], nummer, "y")["ok"]
    assert gespraeche.Gespraechsablage(api._core.base_dir).laden(g["kennung"]).ordner == ""
