# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import threading

MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
_KENNUNG = 0x4341

_thread_id: list[int] = []


def starten(callback, *, protokoll=None) -> bool:
    if not callable(callback):
        return False
    try:
        import win32api
        import win32gui
    except ImportError:
        return False
    ergebnis: dict = {}
    fertig = threading.Event()

    def lauf() -> None:
        try:
            win32gui.RegisterHotKey(None, _KENNUNG, MOD_CONTROL | MOD_NOREPEAT, VK_SPACE)
        except Exception as exc:
            ergebnis["fehler"] = f"{type(exc).__name__}"
            fertig.set()
            return
        _thread_id.append(win32api.GetCurrentThreadId())
        ergebnis["ok"] = True
        fertig.set()
        try:
            while True:
                ret, msg = win32gui.GetMessage(None, 0, 0)
                if ret == 0:
                    break
                if msg[1] == WM_HOTKEY:
                    try:
                        callback()
                    except Exception as exc:
                        if protokoll:
                            protokoll(f"FEHLER hotkey: {type(exc).__name__}: {exc}")
        finally:
            try:
                win32gui.UnregisterHotKey(None, _KENNUNG)
            except Exception:
                pass

    threading.Thread(target=lauf, name="hotkey", daemon=True).start()
    fertig.wait(3.0)
    if ergebnis.get("ok"):
        if protokoll:
            protokoll("OK hotkey Strg+Leertaste")
        return True
    if protokoll:
        protokoll(f"INFO hotkey nicht möglich: {ergebnis.get('fehler', 'keine Antwort')} (Strg+Leertaste gehört einem anderen Programm)")
    return False


def stoppen() -> None:
    try:
        import win32api
        for tid in _thread_id:
            win32api.PostThreadMessage(tid, WM_QUIT, 0, 0)
    except Exception:
        pass
    _thread_id.clear()
