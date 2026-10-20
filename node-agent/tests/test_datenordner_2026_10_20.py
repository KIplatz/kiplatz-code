# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import app_core
import app_web
import ki_laufzeit


@pytest.fixture
def heim(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "heim"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "heim" / "AppData" / "Local"))
    monkeypatch.setattr(app_core, "_andere_programme", lambda: [])
    (tmp_path / "heim").mkdir()
    return tmp_path / "heim"


def _alt_mit_daten(heim: Path) -> Path:
    alt = heim / "CommunityAI-Test"
    (alt / "ki" / "modelle").mkdir(parents=True)
    (alt / "ki" / "modelle" / "modell.gguf").write_bytes(b"\0" * 1000)
    (alt / "community").mkdir()
    (alt / "community" / "geraet.json").write_text('{"geraet": "abc"}', encoding="utf-8")
    return alt


def test_the_old_folder_moves_once_with_everything_in_it(heim):
    alt = _alt_mit_daten(heim)
    u = app_core.daten_umziehen()
    neu = heim / "AppData" / "Local" / "KIplatz" / "daten"
    assert u.ordner == neu and not alt.exists()
    assert (neu / "ki" / "modelle" / "modell.gguf").stat().st_size == 1000
    assert (neu / "community" / "geraet.json").read_text(encoding="utf-8") == '{"geraet": "abc"}'
    assert u.satz.startswith("OK daten: Ordner CommunityAI-Test nach KIplatz") and str(heim) not in u.satz
    again = app_core.daten_umziehen()
    assert again.ordner == neu and again.satz == ""


def test_a_fresh_device_gets_the_new_folder_and_nothing_moves(heim):
    u = app_core.daten_umziehen()
    assert u.ordner == app_core.default_base_dir() and u.satz == "" and not u.ordner.exists()


def test_when_both_exist_the_new_one_counts_and_the_old_one_stays_untouched(heim):
    alt = _alt_mit_daten(heim)
    neu = app_core.default_base_dir()
    neu.mkdir(parents=True)
    u = app_core.daten_umziehen()
    assert u.ordner == neu and (alt / "community" / "geraet.json").is_file()
    assert u.satz.startswith("WARNUNG daten:")


def test_a_locked_folder_keeps_working_where_it_is_and_tries_again_next_start(heim, monkeypatch):
    alt = _alt_mit_daten(heim)
    echt = os.rename

    def gesperrt(a, b):
        raise PermissionError(13, "in use")
    monkeypatch.setattr(app_core.os, "rename", gesperrt)
    u = app_core.daten_umziehen()
    assert u.ordner == alt and (alt / "community" / "geraet.json").is_file() and not app_core.default_base_dir().exists()
    assert u.satz.startswith("HINWEIS daten:") and "PermissionError" in u.satz
    monkeypatch.setattr(app_core.os, "rename", echt)
    assert app_core.daten_umziehen().ordner == app_core.default_base_dir() and not alt.exists()


def test_two_starts_at_the_same_moment_end_in_the_new_folder(heim, monkeypatch):
    _alt_mit_daten(heim)
    echt = os.rename

    def zweiter_war_schneller(a, b):
        echt(a, b)
        raise FileNotFoundError(2, "gone")
    monkeypatch.setattr(app_core.os, "rename", zweiter_war_schneller)
    u = app_core.daten_umziehen()
    assert u.ordner == app_core.default_base_dir() and (u.ordner / "community" / "geraet.json").is_file()


def test_a_linked_old_folder_is_never_moved(heim, monkeypatch):
    alt = _alt_mit_daten(heim)
    monkeypatch.setattr(app_core, "_is_reparse", lambda p: Path(p) == alt)
    u = app_core.daten_umziehen()
    assert alt.is_dir() and u.ordner == app_core.default_base_dir() and u.satz.startswith("WARNUNG daten:") and "Verknüpfung" in u.satz


def test_the_program_start_moves_and_writes_it_into_the_protocol(heim):
    _alt_mit_daten(heim)
    core, _args = app_web.build_core(["--autostart"])
    assert core.base_dir == app_core.default_base_dir()
    protokoll = (core.diagnosis_dir / "protokoll.txt").read_text(encoding="utf-8")
    assert "OK daten: Ordner CommunityAI-Test nach KIplatz" in protokoll
    assert core.datenordner_art() == "normal (KIplatz, daten)"


def test_an_own_folder_and_the_playground_never_move_anything(heim, tmp_path):
    alt = _alt_mit_daten(heim)
    core, _ = app_web.build_core(["--basis", str(tmp_path / "probe")])
    assert core.base_dir == tmp_path / "probe" and alt.is_dir()
    core, _ = app_web.build_core(["--spielwiese"])
    assert core.base_dir == heim / "CommunityAI-Spielwiese" and alt.is_dir()


def test_the_playground_follows_the_models_after_the_move(heim):
    alt = _alt_mit_daten(heim)
    spiel = heim / "CommunityAI-Spielwiese"
    app_web.spielwiese_vorbereiten(spiel)
    assert ki_laufzeit.KiOrdner(spiel).ki_dir == alt / "ki"
    app_core.daten_umziehen()
    app_web.spielwiese_vorbereiten(spiel)
    assert ki_laufzeit.KiOrdner(spiel).ki_dir == app_core.default_base_dir() / "ki"


def test_the_backup_of_the_registration_lies_beside_the_data_never_in_it(heim, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("die Sicherung unter LOCALAPPDATA gibt es nur unter Windows")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    sicher = app_web.anmelde_sicherung(app_core.default_base_dir())
    assert sicher == app_core.kiplatz_dir() / "sicherung" and not sicher.is_relative_to(app_core.default_base_dir())
    assert app_web.anmelde_sicherung(app_core.alter_daten_dir()) == sicher


def test_the_report_says_which_folder_without_any_path(heim):
    core = app_core.AppCore(base_dir=app_core.alter_daten_dir())
    assert core.datenordner_art() == "noch der alte (CommunityAI-Test), Umzug offen"
    text = core.write_diagnosis_report().read_text(encoding="utf-8")
    assert "Datenordner: noch der alte (CommunityAI-Test), Umzug offen" in text and str(heim) not in text


def test_never_while_another_kiplatz_still_works_in_the_old_folder(heim):
    alt = _alt_mit_daten(heim)
    zeit = {"t": 0.0}

    def schlafen(s):
        zeit["t"] += s + 0.25
    u = app_core.daten_umziehen(andere=lambda: [4711], warten_s=2.0, schlafen=schlafen, uhr=lambda: zeit["t"])
    assert u.ordner == alt and alt.is_dir() and not app_core.default_base_dir().exists()
    assert u.satz.startswith("HINWEIS daten:") and "läuft noch ein KIplatz" in u.satz and 2.0 <= zeit["t"] < 3.0
    laeuft = [4711, 4711, 4711]
    u = app_core.daten_umziehen(andere=lambda: [laeuft.pop()] if laeuft else [], schlafen=lambda s: None, uhr=lambda: 0.0)
    assert u.ordner == app_core.default_base_dir() and not alt.exists() and u.satz.startswith("OK daten:")


def test_the_scan_finds_only_scripts_of_the_program_and_never_itself():
    import psutil
    gefunden = app_core._andere_programme()
    assert os.getpid() not in gefunden
    for pid in gefunden:
        try:
            befehl = psutil.Process(pid).cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        assert any(t.lower().endswith(".py") and Path(t).parent.name.lower() == "node-agent" for t in befehl)
        assert "--spielwiese" not in befehl and "--basis" not in befehl


def test_the_old_program_is_counted_even_as_the_parent_of_the_new_one():
    quelle = (HIER / "app_core.py").read_text(encoding="utf-8")
    funktion = quelle[quelle.index("def _andere_programme"):quelle.index("def daten_ordner_jetzt")]
    assert "parents()" not in funktion and "ausgenommen = {os.getpid()}" in funktion


def test_a_file_in_the_way_never_stops_the_program(heim):
    alt = _alt_mit_daten(heim)
    kiplatz = heim / "AppData" / "Local" / "KIplatz"
    kiplatz.parent.mkdir(parents=True)
    kiplatz.write_text("keine Ordner", encoding="utf-8")
    u = app_core.daten_umziehen()
    assert u.ordner == alt and u.satz.startswith("HINWEIS daten:") and alt.is_dir()
    kiplatz.unlink()
    (kiplatz / "daten").parent.mkdir()
    (kiplatz / "daten").write_text("auch keine", encoding="utf-8")
    u = app_core.daten_umziehen()
    assert u.ordner == alt and u.satz.startswith("WARNUNG daten:") and "kein gewöhnlicher Ordner" in u.satz


def test_tools_take_the_folder_that_counts_and_never_move(heim):
    alt = _alt_mit_daten(heim)
    assert app_core.daten_ordner_jetzt() == alt and alt.is_dir()
    app_core.daten_umziehen()
    assert app_core.daten_ordner_jetzt() == app_core.default_base_dir()


def test_a_second_click_while_kiplatz_sits_in_the_tray_neither_waits_nor_moves(heim):
    alt = _alt_mit_daten(heim)
    geschlafen = []
    u = app_core.daten_umziehen(fenster_offen=lambda o: o == alt, andere=lambda: [4711], schlafen=geschlafen.append)
    assert u.ordner == alt and alt.is_dir() and geschlafen == [] and u.satz.startswith("HINWEIS daten:")


@pytest.mark.skipif(sys.platform != "win32", reason="das Fenster-Schloss gibt es nur unter Windows")
def test_looking_at_the_window_lock_never_takes_it(tmp_path):
    import einmal
    ordner = tmp_path / "ein-ordner"
    assert einmal.belegt(ordner) is False and einmal.belegt(ordner) is False
    try:
        assert einmal.sperre_holen(ordner) is True
        assert einmal.belegt(ordner) is True
    finally:
        einmal.freigeben()
    assert einmal.belegt(ordner) is False


def test_the_program_start_asks_the_window_lock_of_the_old_folder():
    quelle = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert "app_core.daten_umziehen(fenster_offen=einmal.belegt)" in quelle


def test_the_bridge_of_the_launcher_reads_the_address_from_the_real_data_folder(heim, monkeypatch):
    import json
    import sitecustomize
    echt = sitecustomize.os.path.expanduser
    monkeypatch.setattr(sitecustomize.os.path, "expanduser", lambda p: str(heim) if p == "~" else echt(p))
    assert sitecustomize._gespeicherte_adresse() == sitecustomize.STANDARD_ADRESSE
    alt = _alt_mit_daten(heim)
    (alt / "community" / "einstellung.json").write_text(json.dumps({"adresse": "https://kiplatz.at:8445/"}), encoding="utf-8")
    assert sitecustomize._gespeicherte_adresse() == "https://kiplatz.at:8445"
    app_core.daten_umziehen()
    assert (app_core.default_base_dir() / "community" / "einstellung.json").is_file()
    assert sitecustomize._gespeicherte_adresse() == "https://kiplatz.at:8445"
    (app_core.default_base_dir() / "community" / "einstellung.json").write_text(json.dumps({"adresse": "http://unsicher"}), encoding="utf-8")
    assert sitecustomize._gespeicherte_adresse() == sitecustomize.STANDARD_ADRESSE
