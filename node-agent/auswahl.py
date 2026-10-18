# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time

MAX_ZEICHEN = 4000
WARTEN_S = 0.18


def auswahl_holen(*, lesen, schreiben, kopieren, warten=time.sleep, eigenes_fenster: bool = False) -> str:
    if eigenes_fenster:
        return ""
    try:
        vorher = lesen()
    except Exception:
        vorher = None
    try:
        schreiben("")
        kopieren()
        warten(WARTEN_S)
        jetzt = lesen()
    except Exception:
        jetzt = None
    finally:
        try:
            if vorher is not None:
                schreiben(vorher)
        except Exception:
            pass
    text = " ".join(str(jetzt or "").split())
    return text[:MAX_ZEICHEN]


def als_vorgabe(text: str) -> str:
    t = text.strip()
    if not t:
        return ""
    return f"„{t}“\n\n"


def _zwischenablage_lesen():
    import win32clipboard
    import win32con
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()


def _zwischenablage_schreiben(text: str) -> None:
    import win32clipboard
    import win32con
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if text:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def in_zwischenablage(text: str, *, schreiben=None, versuche: int = 5, warten=time.sleep) -> bool:
    schreiben = schreiben or _zwischenablage_schreiben
    for i in range(max(1, versuche)):
        try:
            schreiben(text)
            return True
        except Exception:
            if i + 1 < versuche:
                warten(0.05)
    return False


def _strg_c() -> None:
    import win32api
    import win32con
    VK_C = 0x43
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(VK_C, 0, 0, 0)
    win32api.keybd_event(VK_C, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _strg_v() -> None:
    import win32api
    import win32con
    VK_V = 0x56
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(VK_V, 0, 0, 0)
    win32api.keybd_event(VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def eigenes_fenster_vorne(titel_anfang: str) -> bool:
    try:
        import win32gui
        return str(win32gui.GetWindowText(win32gui.GetForegroundWindow()) or "").startswith(titel_anfang)
    except Exception:
        return False


def windows_auswahl(titel_anfang: str) -> str:
    try:
        return auswahl_holen(lesen=_zwischenablage_lesen, schreiben=_zwischenablage_schreiben, kopieren=_strg_c,
                             eigenes_fenster=eigenes_fenster_vorne(titel_anfang))
    except Exception:
        return ""
