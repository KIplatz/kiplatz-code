# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_web
import hardware_detect as hw
import node_local_state as nls


def _report(memory_gib: float, gpus: tuple[str, ...]) -> hw.HardwareReport:
    return hw.HardwareReport(
        hostname="testhost", os="Windows 11", cpu=hw.CpuInfo(4, 8, 3000.0, "AMD64"),
        memory=hw.MemoryInfo(int(memory_gib * 1024 ** 3), 1024 ** 3), disks=[], gpus=[hw.GpuInfo(g, None, True) for g in gpus],
    )


def test_fresh_node_is_stopped_and_start_pause_stop_go_through_node_local_state(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "t")
    assert core.run_state() is nls.RunState.STOPPED
    assert not (tmp_path / "t").exists()
    core.start()
    assert core.run_state() is nls.RunState.ACTIVE
    assert nls.load_local_state(core.node_agent_dir).run_state is nls.RunState.ACTIVE
    core.pause()
    assert core.run_state() is nls.RunState.PAUSED
    core.stop()
    assert core.run_state() is nls.RunState.STOPPED
    assert (core.base_dir / "node-agent").is_dir() and (core.base_dir / "diagnose").is_dir()
    assert "Gestoppt" in core.status_text_de() and "Freigabe:" in core.status_text_de()


def test_corrupt_state_fails_closed_to_stopped(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "t")
    core.start()
    (core.node_agent_dir / "local_state.json").write_text("{kaputt", encoding="utf-8")
    assert core.run_state() is nls.RunState.STOPPED


def test_first_start_check_is_persisted_once_and_suggests_a_role(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "t")
    first = core.run_first_start_check(report=_report(32.0, ("AMD Radeon RX 7800 XT",)))
    assert first.role is app_core.Role.COMPUTE_STRONG and first.memory_gib == 32.0
    again = core.run_first_start_check(report=_report(4.0, ()))
    assert again == first
    assert core.load_first_start() == first
    assert "Rechenstarker" in core.status_text_de()


@pytest.mark.parametrize("memory, gpus, role", [
    (5.9, (), app_core.Role.CLIENT_ONLY),
    (16.0, ("Microsoft Basic Display Adapter",), app_core.Role.COMPUTE_NORMAL),
    (8.0, ("NVIDIA GeForce RTX 4050 Laptop GPU",), app_core.Role.COMPUTE_NORMAL),
    (16.0, ("NVIDIA GeForce RTX 4050 Laptop GPU",), app_core.Role.COMPUTE_STRONG),
    (15.7, ("Intel(R) UHD Graphics", "NVIDIA GeForce RTX 4050 Laptop GPU"), app_core.Role.COMPUTE_STRONG),
    (15.4, ("NVIDIA GeForce RTX 4050 Laptop GPU",), app_core.Role.COMPUTE_NORMAL),
])
def test_role_suggestion_is_conservative(memory, gpus, role):
    assert app_core.suggest_role(memory_gib=memory, gpu_names=gpus) is role


def test_one_data_folder_and_never_the_old_network_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert app_core.default_base_dir() == tmp_path / "Local" / "KIplatz" / "daten"
    assert app_core.alter_daten_dir() == tmp_path / "CommunityAI-Test"
    assert app_core.AppCore().base_dir == app_core.default_base_dir()
    with pytest.raises(app_core.AppError) as excinfo:
        app_core.AppCore(base_dir=tmp_path / "Local" / "CommunityAINetwork" / "unter")
    assert excinfo.value.code == "ORDNER_FREMD"
    with pytest.raises(app_core.AppError):
        app_core.AppCore(base_dir=Path("relativ"))


def test_directories_are_created_but_never_replaced(tmp_path):
    base = tmp_path / "t"
    base.mkdir()
    (base / "node-agent").write_text("ich bin eine Datei", encoding="utf-8")
    core = app_core.AppCore(base_dir=base)
    with pytest.raises(app_core.AppError) as excinfo:
        core.ensure_directories()
    assert excinfo.value.code == "ORDNER_UNSICHER"
    assert (base / "node-agent").read_text(encoding="utf-8") == "ich bin eine Datei"


def test_junction_is_refused(tmp_path):
    import subprocess

    target = tmp_path / "ziel"
    target.mkdir()
    link = tmp_path / "t"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        os.symlink(target, link, target_is_directory=True)
    core = app_core.AppCore(base_dir=link)
    with pytest.raises(app_core.AppError) as excinfo:
        core.ensure_directories()
    assert excinfo.value.code == "ORDNER_UNSICHER"


def test_diagnosis_report_contains_no_user_name_ip_or_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("USERNAME", "rainer-test")
    core = app_core.AppCore(base_dir=tmp_path / "rainer-test-ordner")
    core.run_first_start_check(report=_report(16.0, ("GPU 192.168.1.5 " + "a" * 64,)))
    core.start()
    path = core.write_diagnosis_report()
    text = path.read_text(encoding="utf-8")
    assert path.parent == core.diagnosis_dir and path.name.startswith("diagnose-")
    assert "rainer-test" not in text and "192.168.1.5" not in text and "a" * 64 not in text
    assert "Zustand: ACTIVE" in text and f"Bau: {app_core.APP_BUILD}" in text and "Datenordner: ein anderer" in text
    assert "Arbeitsspeicher: 16.0 GiB" in text and "Profil" not in text
    assert "<benutzer>" in text or "rainer" not in text


def test_argument_parsing_without_a_window(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(app_core, "_andere_programme", lambda: [])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    core, args = app_web.build_core(["--basis", str(tmp_path / "x")])
    assert core.base_dir == tmp_path / "x" and not args.autostart
    core, args = app_web.build_core(["--autostart"])
    assert core.base_dir == tmp_path / "Local" / "KIplatz" / "daten" and args.autostart
    with pytest.raises(SystemExit):
        app_web.build_core(["--produktiv"])


def test_freigabe_defaults_are_conservative_and_idle_only_is_the_real_work_policy(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "t")
    f = core.load_freigabe()
    assert f.nur_im_leerlauf and f.cpu_prozent == 25 and f.ram_gib == 2
    core.start()
    state = nls.load_local_state(core.node_agent_dir)
    assert state.work_policy is nls.WorkPolicy.IDLE_ONLY and state.run_state is nls.RunState.ACTIVE
    assert not nls.may_execute_new_job(state, idle_seconds=10.0)
    assert nls.may_execute_new_job(state, idle_seconds=10 * 60.0)
    core.save_freigabe(app_core.Freigabe(nur_im_leerlauf=False, cpu_prozent=50, ram_gib=4))
    state = nls.load_local_state(core.node_agent_dir)
    assert state.work_policy is nls.WorkPolicy.ALWAYS and state.run_state is nls.RunState.ACTIVE
    assert core.load_freigabe() == app_core.Freigabe(False, 50, 4)
    assert "50 % Rechenkraft" in core.status_text_de()
    core.save_freigabe(app_core.Freigabe(True, 10, 1.5, 50))
    assert core.load_freigabe() == app_core.Freigabe(True, 10, 1.5, 50)
    for falsch in (app_core.Freigabe(True, 0, 4), app_core.Freigabe(True, 101, 4), app_core.Freigabe(True, 50, 1.3), app_core.Freigabe(True, 50, 0),
                   app_core.Freigabe(True, 50, 4, 20), app_core.Freigabe(True, 50, 4, -1)):
        with pytest.raises(app_core.AppError):
            core.save_freigabe(falsch)
    (core.base_dir / "freigabe.json").write_text("{kaputt", encoding="utf-8")
    assert core.load_freigabe().cpu_prozent == 25


def _fake_exe(tmp_path: Path) -> Path:
    exe = tmp_path / "quelle" / "CommunityAI.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ" + bytes(range(256)) * 100)
    return exe


def test_install_copies_and_verifies_then_uninstall_removes_only_its_own_files(tmp_path):
    import app_install

    exe = _fake_exe(tmp_path)
    target = tmp_path / "Programme" / "CommunityAI"
    info = app_install.install(exe, target)
    assert info.exe_path == target / "CommunityAI.exe" and (target / "installiert.json").exists()
    assert (target / "CommunityAI.exe").read_bytes() == exe.read_bytes()
    assert app_install.installed_info(target) == info
    assert app_install.install(exe, target).exe_sha256 == info.exe_sha256
    (target / "fremd.txt").write_text("gehört nicht uns", encoding="utf-8")
    reg = app_install.MemoryRegistry()
    app_install.autostart_enable(info.exe_path, registry=reg)
    assert app_install.autostart_enabled(registry=reg) and reg.values[app_install.RUN_VALUE_NAME].endswith('CommunityAI.exe" --autostart')
    removed = app_install.uninstall(target, registry=reg)
    assert set(p.name for p in removed) == {"CommunityAI.exe", "installiert.json"}
    assert (target / "fremd.txt").exists() and target.is_dir()
    assert not app_install.autostart_enabled(registry=reg)
    assert app_install.installed_info(target) is None


def test_install_refuses_bad_sources_and_autostart_needs_an_installed_exe(tmp_path):
    import app_install

    with pytest.raises(app_core.AppError) as excinfo:
        app_install.install(tmp_path / "gibt-es-nicht.exe", tmp_path / "ziel")
    assert excinfo.value.code == "INSTALL_QUELLE"
    empty = tmp_path / "leer.exe"
    empty.write_bytes(b"")
    with pytest.raises(app_core.AppError):
        app_install.install(empty, tmp_path / "ziel")
    reg = app_install.MemoryRegistry()
    with pytest.raises(app_core.AppError) as excinfo:
        app_install.autostart_enable(tmp_path / "nicht-installiert.exe", registry=reg)
    assert excinfo.value.code == "AUTOSTART_QUELLE" and not reg.values
    app_install.autostart_disable(registry=reg)
    assert app_install.uninstall(tmp_path / "nie-installiert", registry=reg) == ()
    assert app_install.running_exe() is None


def test_recommendation_fits_the_device_and_never_offers_all_the_memory():
    laptop = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 12, 15.7, ("RTX 4050",), app_core.Role.COMPUTE_STRONG)
    rec = app_core.recommended_freigabe(laptop)
    assert rec == app_core.Freigabe(True, 50, 3.5)
    assert app_core.ram_choices_for(laptop) == (1, 2, 4, 8)
    karina = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 2, 5.9, (), app_core.Role.CLIENT_ONLY)
    assert app_core.recommended_freigabe(karina) == app_core.Freigabe(True, 25, 1)
    assert app_core.ram_choices_for(karina) == (1, 2)
    assert app_core.recommended_freigabe(None) == app_core.Freigabe(True, 25, 2)
    pc = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 24, 31.9, ("RX 7800 XT",), app_core.Role.COMPUTE_STRONG)
    assert app_core.recommended_freigabe(pc) == app_core.Freigabe(True, 50, 7.5)


def test_consequence_sentence_is_honest_about_what_stays():
    laptop = app_core.FirstStartResult("2026-09-16T12:00:00Z", "Windows 11", 12, 15.7, ("RTX 4050",), app_core.Role.COMPUTE_STRONG)
    mild = app_core.freigabe_folgen_de(app_core.Freigabe(True, 25, 2), laptop)
    assert "13,7 GB" in mild and "75 % Prozessor" in mild and "praktisch nichts" in mild
    harsh = app_core.freigabe_folgen_de(app_core.Freigabe(False, 100, 8), laptop)
    assert "spürbar bremsen" in harsh and "auch, während du arbeitest" in harsh
    assert "Erststart" in app_core.freigabe_folgen_de(app_core.Freigabe(True, 25, 2), None)


def test_ensure_installed_sets_itself_up_silently_and_updates_on_new_bytes(tmp_path):
    import app_install

    target = tmp_path / "Programme" / "CommunityAI"
    assert app_install.ensure_installed(None, target) == ("quelle", None)
    exe = _fake_exe(tmp_path)
    what, info = app_install.ensure_installed(exe, target)
    assert what == "eingerichtet" and info is not None and info.exe_path == target / "CommunityAI.exe"
    assert app_install.ensure_installed(exe, target)[0] == "unveraendert"
    exe.write_bytes(exe.read_bytes() + b"neu")
    what, info2 = app_install.ensure_installed(exe, target)
    assert what == "aktualisiert" and info2.exe_sha256 != info.exe_sha256
    assert app_install.ensure_installed(target / "CommunityAI.exe", target)[0] == "programmordner"
