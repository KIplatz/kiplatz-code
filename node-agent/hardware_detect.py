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
        return detect_gpus_ohne_windows()

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


def _werkzeug(args: list[str], runner=subprocess.run) -> str:
    import shutil
    if shutil.which(args[0]) is None:
        return ""
    try:
        r = runner(args, capture_output=True, text=True, timeout=10, check=False)
    except (subprocess.SubprocessError, OSError):
        return ""
    return r.stdout if r.returncode == 0 else ""


_SOFTWARE_GRAFIK = ("llvmpipe", "swiftshader", "software rasterizer")


def detect_gpus_ohne_windows(runner=subprocess.run, system: str | None = None) -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    for zeile in _werkzeug(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], runner).splitlines():
        name, _, mib = zeile.rpartition(",")
        if name.strip():
            gpus.append(GpuInfo(name=name.strip(), vram_bytes=int(mib) * 1024 * 1024 if mib.strip().isdigit() else None, vram_is_estimated=True))
    roh = _werkzeug(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"], runner)
    if roh:
        try:
            karten = json.loads(roh)
        except json.JSONDecodeError:
            karten = {}
        for karte in (karten.values() if isinstance(karten, dict) else []):
            if not isinstance(karte, dict):
                continue
            name = next((str(v) for k, v in karte.items() if k in ("Card Series", "Card series", "Marketing Name", "Card SKU") and v), "")
            vram = next((v for k, v in karte.items() if "VRAM Total Memory" in k), None)
            if name:
                gpus.append(GpuInfo(name=name, vram_bytes=int(vram) if str(vram or "").isdigit() else None, vram_is_estimated=True))
    if (system or platform.system()) == "Darwin":
        roh = _werkzeug(["system_profiler", "SPDisplaysDataType", "-json"], runner)
        try:
            for g in (json.loads(roh).get("SPDisplaysDataType") or []) if roh else []:
                name = str(g.get("sppci_model") or g.get("_name") or "").strip()
                if name:
                    gpus.append(GpuInfo(name=name, vram_bytes=None, vram_is_estimated=True))
        except (json.JSONDecodeError, AttributeError):
            pass
    if not gpus:
        for zeile in _werkzeug(["vulkaninfo", "--summary"], runner).splitlines():
            schluessel, _, wert = zeile.partition("=")
            name = wert.strip()
            if schluessel.strip() == "deviceName" and name and not any(s in name.lower() for s in _SOFTWARE_GRAFIK):
                gpus.append(GpuInfo(name=name, vram_bytes=None, vram_is_estimated=True))
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
