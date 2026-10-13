# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import struct
import zlib
from pathlib import Path

MAX_BREITE = 1600


def png_aus_bgra(breite: int, hoehe: int, bgra: bytes, *, faktor: int = 1) -> bytes:
    zeile_bytes = breite * 4
    ausgabe_b, ausgabe_h = breite // faktor, hoehe // faktor
    zeilen = bytearray()
    for y in range(ausgabe_h):
        start = y * faktor * zeile_bytes
        quelle = bgra[start:start + zeile_bytes]
        zeilen.append(0)
        if faktor == 1:
            zeilen += bytes(b for px in (quelle[i:i + 3][::-1] for i in range(0, zeile_bytes, 4)) for b in px)
        else:
            zeilen += bytes(b for px in (quelle[i:i + 3][::-1] for i in range(0, zeile_bytes, 4 * faktor)) for b in px)[:ausgabe_b * 3]

    def block(art: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", ausgabe_b, ausgabe_h, 8, 2, 0, 0, 0))
            + block(b"IDAT", zlib.compress(bytes(zeilen), 6)) + block(b"IEND", b""))


def aufnehmen(ziel: Path) -> Path:
    try:
        import win32api
        import win32con
        import win32gui
        import win32ui
    except ImportError as exc:
        raise OSError("Bildschirmaufnahme geht nur unter Windows") from exc
    breite = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    hoehe = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    hdesk = win32gui.GetDesktopWindow()
    hdc = win32gui.GetWindowDC(hdesk)
    quelle = win32ui.CreateDCFromHandle(hdc)
    ziel_dc = quelle.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    try:
        bmp.CreateCompatibleBitmap(quelle, breite, hoehe)
        ziel_dc.SelectObject(bmp)
        ziel_dc.BitBlt((0, 0), (breite, hoehe), quelle, (0, 0), win32con.SRCCOPY)
        bits = bmp.GetBitmapBits(True)
    finally:
        try:
            win32gui.DeleteObject(bmp.GetHandle())
        except Exception:
            pass
        ziel_dc.DeleteDC()
        quelle.DeleteDC()
        win32gui.ReleaseDC(hdesk, hdc)
    faktor = 1
    while breite // faktor > MAX_BREITE:
        faktor += 1
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(png_aus_bgra(breite, hoehe, bits, faktor=faktor))
    return ziel
