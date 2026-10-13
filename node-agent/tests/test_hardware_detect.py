# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hardware_detect as hd


def test_detect_cpu_uses_psutil(monkeypatch):
    monkeypatch.setattr(hd.psutil, "cpu_count", lambda logical=True: 8 if logical else 4)
    monkeypatch.setattr(hd.psutil, "cpu_freq", lambda: MagicMock(max=3200.0))

    info = hd.detect_cpu()

    assert info.physical_cores == 4
    assert info.logical_cores == 8
    assert info.max_frequency_mhz == 3200.0
    assert info.architecture == platform.machine()


def test_detect_cpu_handles_missing_frequency(monkeypatch):
    monkeypatch.setattr(hd.psutil, "cpu_count", lambda logical=True: 4)
    monkeypatch.setattr(hd.psutil, "cpu_freq", lambda: None)

    info = hd.detect_cpu()

    assert info.max_frequency_mhz is None


def test_detect_memory_uses_psutil(monkeypatch):
    monkeypatch.setattr(
        hd.psutil,
        "virtual_memory",
        lambda: MagicMock(total=16_000_000_000, available=8_000_000_000),
    )

    info = hd.detect_memory()

    assert info.total_bytes == 16_000_000_000
    assert info.available_bytes == 8_000_000_000


def test_detect_disks_reports_real_usage(tmp_path):
    disks = hd.detect_disks([str(tmp_path)])

    assert len(disks) == 1
    assert disks[0].path == str(tmp_path)
    assert disks[0].total_bytes > 0
    assert disks[0].free_bytes >= 0


def test_detect_gpus_parses_powershell_json(monkeypatch):
    fake_output = json.dumps(
        [{"Name": "NVIDIA RTX 4050 Laptop GPU", "AdapterRAM": 6_000_000_000}]
    )
    monkeypatch.setattr(hd.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hd.subprocess, "run", lambda *a, **k: MagicMock(stdout=fake_output)
    )

    gpus = hd.detect_gpus()

    assert len(gpus) == 1
    assert gpus[0].name == "NVIDIA RTX 4050 Laptop GPU"
    assert gpus[0].vram_bytes == 6_000_000_000
    assert gpus[0].vram_is_estimated is True


def test_detect_gpus_marks_negative_wmi_vram_as_unknown(monkeypatch):
    fake_output = json.dumps([{"Name": "AMD Radeon RX 7800 XT", "AdapterRAM": -1}])
    monkeypatch.setattr(hd.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hd.subprocess, "run", lambda *a, **k: MagicMock(stdout=fake_output)
    )

    gpus = hd.detect_gpus()

    assert gpus[0].vram_bytes is None
    assert gpus[0].vram_is_estimated is True


def test_detect_gpus_returns_empty_on_subprocess_failure(monkeypatch):
    monkeypatch.setattr(hd.platform, "system", lambda: "Windows")

    def raise_error(*args, **kwargs):
        raise hd.subprocess.SubprocessError("boom")

    monkeypatch.setattr(hd.subprocess, "run", raise_error)

    assert hd.detect_gpus() == []


def test_detect_gpus_returns_empty_on_malformed_json(monkeypatch):
    monkeypatch.setattr(hd.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hd.subprocess, "run", lambda *a, **k: MagicMock(stdout="not json")
    )

    assert hd.detect_gpus() == []


def test_detect_gpus_skipped_on_non_windows(monkeypatch):
    monkeypatch.setattr(hd.platform, "system", lambda: "Linux")

    assert hd.detect_gpus() == []


def test_build_report_produces_serializable_dict(monkeypatch, tmp_path):
    monkeypatch.setattr(hd, "detect_gpus", lambda: [])

    report = hd.build_report(disk_paths=[str(tmp_path)])
    data = hd.report_to_dict(report)

    json.dumps(data)
    assert data["hostname"] == platform.node()
    assert data["disks"][0]["path"] == str(tmp_path)
