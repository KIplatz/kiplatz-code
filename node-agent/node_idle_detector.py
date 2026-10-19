# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ctypes
import platform
from pathlib import Path


class IdleDetectionError(Exception):
    pass


class IdleDetectionUnavailableError(IdleDetectionError):
    pass


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    if platform.system() == "Darwin":
        return _mac_idle_seconds()
    if platform.system() == "Linux":
        return _linux_idle_seconds()
    if platform.system() != "Windows":
        raise IdleDetectionUnavailableError("Idle detection is only available on Windows, macOS and Linux.")

    last_input_info = _LastInputInfo()
    last_input_info.cbSize = ctypes.sizeof(_LastInputInfo)

    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)):
        raise IdleDetectionUnavailableError("GetLastInputInfo failed.")

    get_tick_count = ctypes.windll.kernel32.GetTickCount
    try:
        get_tick_count.restype = ctypes.c_uint32
    except AttributeError:
        pass
    tick_count = int(get_tick_count()) & 0xFFFFFFFF
    idle_milliseconds = (tick_count - (int(last_input_info.dwTime) & 0xFFFFFFFF)) & 0xFFFFFFFF

    return idle_milliseconds / 1000.0


LOGIND_SESSIONS = Path("/run/systemd/sessions")
NIEMAND_DA_S = 10.0 ** 6
_LOKALE_ARTEN = {"x11", "wayland", "mir", "tty"}


def lokale_sitzung_aktiv(ordner: Path | None = None) -> bool | None:
    ordner = LOGIND_SESSIONS if ordner is None else Path(ordner)
    try:
        dateien = [p for p in ordner.iterdir() if p.is_file() and "." not in p.name]
    except OSError:
        return None
    for p in dateien:
        werte: dict[str, str] = {}
        try:
            for zeile in p.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
                k, _, v = zeile.partition("=")
                if k in ("ACTIVE", "REMOTE", "SEAT", "TYPE"):
                    werte[k] = v.strip()
        except OSError:
            return None
        if werte.get("ACTIVE") == "1" and werte.get("REMOTE", "0") != "1" and werte.get("SEAT") and werte.get("TYPE") in _LOKALE_ARTEN:
            return True
    return False


def _linux_idle_seconds() -> float:
    if lokale_sitzung_aktiv() is False:
        return NIEMAND_DA_S
    raise IdleDetectionUnavailableError("Someone may be logged in at this Linux device; its idle time cannot be read.")


def _mac_idle_seconds() -> float:
    try:
        iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    except OSError:
        raise IdleDetectionUnavailableError("IOKit is not available.") from None
    iokit.IOServiceMatching.restype = ctypes.c_void_p
    iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
    iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
    iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
    iokit.IORegistryEntryCreateCFProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]
    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    dienst = iokit.IOServiceGetMatchingService(0, iokit.IOServiceMatching(b"IOHIDSystem"))
    if not dienst:
        raise IdleDetectionUnavailableError("IOHIDSystem not found.")
    name = wert = None
    try:
        name = cf.CFStringCreateWithCString(None, b"HIDIdleTime", 0x08000100)
        wert = iokit.IORegistryEntryCreateCFProperty(dienst, name, None, 0)
        ns = ctypes.c_int64(0)
        if not wert or not cf.CFNumberGetValue(wert, 4, ctypes.byref(ns)):
            raise IdleDetectionUnavailableError("HIDIdleTime could not be read.")
        return max(0, ns.value) / 1e9
    finally:
        for obj in (wert, name):
            if obj:
                cf.CFRelease(obj)
        iokit.IOObjectRelease(dienst)
