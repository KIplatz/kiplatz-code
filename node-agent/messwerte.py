# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time

GPU_TIMEOUT_S = 4.0
_GPU_ABFRAGE = ("--query-gpu=temperature.gpu,power.draw", "--format=csv,noheader,nounits")


def _zahl(text: str) -> float | None:
    try:
        v = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return v if v == v and 0 <= v < 10_000 else None


def gpu_werkzeug() -> str | None:
    w = shutil.which("nvidia-smi")
    if w:
        return w
    if sys.platform == "win32":
        for p in (os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe"),
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            if os.path.isfile(p):
                return p
    return None


def gpu_messen(werkzeug: str | None = None, *, timeout_s: float = GPU_TIMEOUT_S) -> dict:
    w = werkzeug or gpu_werkzeug()
    if not w:
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run([w, *_GPU_ABFRAGE], capture_output=True, text=True, timeout=timeout_s, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return {}
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    teile = [t.strip() for t in r.stdout.strip().splitlines()[0].split(",")]
    out: dict = {}
    if len(teile) >= 1 and (t := _zahl(teile[0])) is not None and t > 0:
        out["gpu_temperatur_c"] = round(t, 1)
    if len(teile) >= 2 and (p := _zahl(teile[1])) is not None and p > 0:
        out["gpu_watt"] = round(p, 1)
    return out


def _systemzeiten() -> tuple[int, int] | None:
    if sys.platform != "win32":
        return None
    try:
        k32 = ctypes.windll.kernel32
        idle, kern, user = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
        if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            return None
        return idle.value, kern.value + user.value
    except (AttributeError, OSError):
        return None


def cpu_messen(dauer_s: float = 0.25) -> int | None:
    a = _systemzeiten()
    if a is None:
        return None
    time.sleep(max(0.05, dauer_s))
    b = _systemzeiten()
    if b is None or b[1] <= a[1]:
        return None
    gesamt = b[1] - a[1]
    return max(0, min(100, round(100 * (1 - (b[0] - a[0]) / gesamt))))


def ram_messen() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return None
        return int(m.dwMemoryLoad)
    except (AttributeError, OSError, ValueError):
        return None


def messen(*, gpu: bool = True) -> dict:
    out: dict = {}
    c = cpu_messen()
    if c is not None:
        out["cpu_prozent"] = c
    r = ram_messen()
    if r is not None:
        out["ram_prozent"] = r
    if gpu:
        out.update(gpu_messen())
    return out


def pruefen(messung: object) -> dict:
    if not isinstance(messung, dict):
        return {}
    grenzen = {"cpu_prozent": (0, 100), "ram_prozent": (0, 100), "gpu_temperatur_c": (1, 150), "gpu_watt": (0.1, 2000)}
    out: dict = {}
    for k, (lo, hi) in grenzen.items():
        v = _zahl(messung.get(k))
        if v is not None and lo <= v <= hi:
            out[k] = round(v, 1)
    return out


__all__ = ["messen", "pruefen", "gpu_messen", "cpu_messen", "ram_messen", "gpu_werkzeug"]
