# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ctypes
import platform


class IdleDetectionError(Exception):
    pass


class IdleDetectionUnavailableError(IdleDetectionError):
    pass


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    if platform.system() != "Windows":
        raise IdleDetectionUnavailableError("Idle detection is only available on Windows.")

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
