# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import re
import sys
import time

SCHWELLE_3D = 15.0
SCHWELLE_VIDEO = 3.0
MESSEN_S = 1.0
GILT_S = 20.0
NICHT_ZAEHLEN = ("dwm.exe",)

_NAME = re.compile(r"pid_(\d+)_.*engtype_([A-Za-z0-9 ]+)$")
_gemerkt: tuple[float, tuple[bool, str] | None] = (0.0, None)


def _prozesse() -> dict[int, tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    h = k32.CreateToolhelp32Snapshot(0x00000002, 0)
    if not h or h == wintypes.HANDLE(-1).value:
        return {}
    out: dict[int, tuple[int, str]] = {}
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(h, ctypes.byref(e))
        while ok:
            out[int(e.th32ProcessID)] = (int(e.th32ParentProcessID), str(e.szExeFile).lower())
            ok = k32.Process32NextW(h, ctypes.byref(e))
    finally:
        k32.CloseHandle(h)
    return out


def eigene(prozesse: dict[int, tuple[int, str]], wurzel: int) -> set[int]:
    kinder: dict[int, list[int]] = {}
    for pid, (eltern, _n) in prozesse.items():
        kinder.setdefault(eltern, []).append(pid)
    out, offen = {wurzel}, [wurzel]
    while offen:
        for k in kinder.get(offen.pop(), []):
            if k not in out:
                out.add(k)
                offen.append(k)
    return out


def auslastung(*, messen_s: float = MESSEN_S) -> dict[int, dict[str, float]]:
    import ctypes
    from ctypes import wintypes

    class WERT(ctypes.Structure):
        _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]

    class EINTRAG(ctypes.Structure):
        _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", WERT)]

    pdh = ctypes.WinDLL("pdh")
    abfrage, zaehler = wintypes.HANDLE(), wintypes.HANDLE()
    if pdh.PdhOpenQueryW(None, None, ctypes.byref(abfrage)) != 0:
        raise OSError("PdhOpenQuery")
    try:
        if pdh.PdhAddEnglishCounterW(abfrage, "\\GPU Engine(*)\\Utilization Percentage", None, ctypes.byref(zaehler)) != 0:
            raise OSError("PdhAddEnglishCounter")
        pdh.PdhCollectQueryData(abfrage)
        time.sleep(messen_s)
        if pdh.PdhCollectQueryData(abfrage) != 0:
            raise OSError("PdhCollectQueryData")
        groesse, anzahl = wintypes.DWORD(0), wintypes.DWORD(0)
        pdh.PdhGetFormattedCounterArrayW(zaehler, 0x00000200, ctypes.byref(groesse), ctypes.byref(anzahl), None)
        if not groesse.value:
            return {}
        puffer = (ctypes.c_byte * groesse.value)()
        if pdh.PdhGetFormattedCounterArrayW(zaehler, 0x00000200, ctypes.byref(groesse), ctypes.byref(anzahl), puffer) != 0:
            raise OSError("PdhGetFormattedCounterArray")
        eintraege = ctypes.cast(puffer, ctypes.POINTER(EINTRAG))
        out: dict[int, dict[str, float]] = {}
        for i in range(anzahl.value):
            m = _NAME.search(eintraege[i].szName or "")
            if not m or eintraege[i].FmtValue.CStatus not in (0, 1):
                continue
            art = m.group(2).strip().lower()
            je = out.setdefault(int(m.group(1)), {})
            je[art] = je.get(art, 0.0) + max(0.0, float(eintraege[i].FmtValue.doubleValue))
        return out
    finally:
        pdh.PdhCloseQuery(abfrage)


def fremd(last: dict[int, dict[str, float]], nicht: set[int], namen: dict[int, str] | None = None) -> str:
    namen = namen or {}
    for pid, je in last.items():
        if pid in nicht or namen.get(pid, "") in NICHT_ZAEHLEN:
            continue
        rechnen = max([v for k, v in je.items() if k.startswith("3d") or k.startswith("compute")] or [0.0])
        video = max([v for k, v in je.items() if k.startswith("video")] or [0.0])
        if rechnen >= SCHWELLE_3D or video >= SCHWELLE_VIDEO:
            return f"ein anderes Programm nutzt die Grafikkarte (3D {rechnen:.0f} %, Video {video:.0f} %)"
    return ""


def belegt(*, jetzt=time.monotonic) -> tuple[bool, str] | None:
    global _gemerkt
    if sys.platform != "win32":
        return None
    if _gemerkt[1] is not None and jetzt() - _gemerkt[0] < GILT_S:
        return _gemerkt[1]
    try:
        prozesse = _prozesse()
        satz = fremd(auslastung(), eigene(prozesse, os.getpid()), {p: n for p, (_e, n) in prozesse.items()})
    except Exception:
        return None
    _gemerkt = (jetzt(), (bool(satz), satz))
    return _gemerkt[1]


__all__ = ["belegt", "fremd", "eigene", "auslastung", "SCHWELLE_3D", "SCHWELLE_VIDEO", "GILT_S"]
