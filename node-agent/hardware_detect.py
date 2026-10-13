# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import dataclasses
import json
import os
import platform
import shutil
import subprocess
from typing import Optional

import psutil


@dataclasses.dataclass
class CpuInfo:
    physical_cores: Optional[int]
    logical_cores: Optional[int]
    max_frequency_mhz: Optional[float]
    architecture: str


@dataclasses.dataclass
class MemoryInfo:
    total_bytes: int
    available_bytes: int


@dataclasses.dataclass
class DiskInfo:
    path: str
    total_bytes: int
    free_bytes: int


@dataclasses.dataclass
class GpuInfo:
    name: str
    vram_bytes: Optional[int]
    vram_is_estimated: bool


@dataclasses.dataclass
class HardwareReport:
    hostname: str
    os: str
    cpu: CpuInfo
    memory: MemoryInfo
    disks: list[DiskInfo]
    gpus: list[GpuInfo]


def detect_cpu() -> CpuInfo:
    freq = psutil.cpu_freq()
    return CpuInfo(
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        max_frequency_mhz=freq.max if freq else None,
        architecture=platform.machine(),
    )


def detect_memory() -> MemoryInfo:
    vm = psutil.virtual_memory()
    return MemoryInfo(total_bytes=vm.total, available_bytes=vm.available)


def detect_disks(paths: list[str]) -> list[DiskInfo]:
    disks = []
    for path in paths:
        usage = shutil.disk_usage(path)
        disks.append(DiskInfo(path=path, total_bytes=usage.total, free_bytes=usage.free))
    return disks


def detect_gpus() -> list[GpuInfo]:
    if platform.system() != "Windows":
        return []

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, AdapterRAM | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    raw = completed.stdout.strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    entries = data if isinstance(data, list) else [data]

    gpus = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("Name") or "unknown"
        adapter_ram = entry.get("AdapterRAM")
        vram_bytes = adapter_ram if isinstance(adapter_ram, int) and adapter_ram > 0 else None
        gpus.append(GpuInfo(name=name, vram_bytes=vram_bytes, vram_is_estimated=True))
    return gpus


def _default_disk_paths() -> list[str]:
    if platform.system() == "Windows":
        drive = os.path.splitdrive(os.getcwd())[0]
        return [drive + "\\"] if drive else ["C:\\"]
    return ["/"]


def build_report(disk_paths: Optional[list[str]] = None) -> HardwareReport:
    return HardwareReport(
        hostname=platform.node(),
        os=f"{platform.system()} {platform.release()}",
        cpu=detect_cpu(),
        memory=detect_memory(),
        disks=detect_disks(disk_paths if disk_paths is not None else _default_disk_paths()),
        gpus=detect_gpus(),
    )


def report_to_dict(report: HardwareReport) -> dict:
    return dataclasses.asdict(report)


def main() -> None:
    report = build_report()
    print(json.dumps(report_to_dict(report), indent=2))


if __name__ == "__main__":
    main()
