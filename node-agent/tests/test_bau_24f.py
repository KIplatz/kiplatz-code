# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_web
import scheiben_halter
from test_app_web import _api


def test_any_value_within_the_bounds_and_sizes_read_like_a_person_says_them():
    for gut in (app_core.Freigabe(True, 1, 0.5, 0), app_core.Freigabe(True, 10, 1.5, 50), app_core.Freigabe(True, 100, 30, 4_000_000)):
        app_core.freigabe_pruefen(gut)
    assert app_core.groesse_de(50) == "50 MB" and app_core.groesse_de(1500) == "1,5 GB" and app_core.groesse_de(2_000_000) == "2 TB"
    assert app_core.zahl_de(1.5) == "1,5" and app_core.zahl_de(2.0) == "2"
    pc = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 24, 31.9, ("RX 7800 XT",), app_core.Role.COMPUTE_STRONG)
    karina = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 2, 5.9, (), app_core.Role.CLIENT_ONLY)
    assert app_core.ram_max_gib(pc) == 29.5 and app_core.ram_max_gib(karina) == 3.5
    assert app_core.speicher_empfehlung_mb(450_000) == 20000 and app_core.speicher_empfehlung_mb(40_000) == 2000 and app_core.speicher_empfehlung_mb(3_000) == 500
    assert "Laufwerk F:" in app_core.Freigabe(True, 10, 1.5, 50, "F:\\").text_de()


def test_the_holder_keeps_slices_only_on_the_chosen_drive_and_moves_them_there_checked(tmp_path):
    ort = {"pfad": None}
    h = scheiben_halter.Halter(tmp_path / "programm", None, limit_mb=500, ordner=lambda: ort["pfad"])
    assert h.dir == tmp_path / "programm" / "scheiben"
    h.dir.mkdir(parents=True)
    for k in ("aaa111", "bbb222"):
        (h.dir / f"{k}.zip").write_bytes(k.encode() * 1000)
    neu = tmp_path / "F" / app_core.SPEICHER_ORDNER / "scheiben"
    assert h.frei_mb() > 0
    assert h.umziehen(neu) == 2
    ort["pfad"] = neu
    assert h.dir == neu and sorted(k for k, _ in h.liste()) == ["aaa111", "bbb222"]
    assert not list((tmp_path / "programm" / "scheiben").glob("*.zip"))
    assert (neu / "aaa111.zip").read_bytes() == b"aaa111" * 1000


def test_the_window_offers_only_listed_drives_checks_the_room_and_moves_the_slices(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    laufwerk = tmp_path / "LaufwerkF"
    laufwerk.mkdir()
    ort = str(laufwerk)
    monkeypatch.setattr(app_core, "laufwerke", lambda: [{"ort": ort, "name": "F:", "bezeichnung": "Daten", "frei_mb": 460_000, "gesamt_mb": 500_000}])
    alt = api._halter.dir
    alt.mkdir(parents=True, exist_ok=True)
    (alt / "ccc333.zip").write_bytes(b"x" * 2048)
    z = api.zustand()["daten"]
    assert z["grenzen"]["cpu_min"] == 1 and z["grenzen"]["ram_schritt"] == 0.5 and z["laufwerke"][0]["name"] == "F:" and z["laufwerke"][0]["empfehlung_mb"] == 20000
    r = api.freigabe_speichern(True, 10, 1.5, 50, str(tmp_path / "irgendwo"))
    assert not r["ok"] and "Laufwerk" in r["text"]
    grenzen = api.speicher_grenzen(ort)["daten"]
    assert grenzen["max_mb"] > 0
    r = api.freigabe_speichern(True, 10, 1.5, grenzen["max_mb"] + 1000, ort)
    assert not r["ok"] and "höchstens" in r["text"]
    r = api.freigabe_speichern(True, 10, 1.5, 50, ort)
    assert r["ok"], r["text"]
    f = api._core.load_freigabe()
    assert (f.cpu_prozent, f.ram_gib, f.speicher_mb, f.speicher_ort) == (10, 1.5, 50, ort)
    assert api._halter.dir == app_web.speicher_pfad(ort) == laufwerk / app_core.SPEICHER_ORDNER / "scheiben"
    assert (api._halter.dir / "ccc333.zip").is_file() and not (alt / "ccc333.zip").exists()
    assert sorted(p.name for p in laufwerk.iterdir()) == [app_core.SPEICHER_ORDNER]
    r = api.freigabe_speichern(True, 10, 1.5, 50, "")
    assert r["ok"] and (alt / "ccc333.zip").is_file() and api._halter.dir == alt
