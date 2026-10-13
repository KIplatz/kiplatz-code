# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import platform

try:
    import win32crypt
except ImportError:
    win32crypt = None

ZWECK = "KIplatz"


class GeheimError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code, self.detail = code, detail


def moeglich() -> bool:
    return win32crypt is not None and platform.system() == "Windows"


def schuetzen(klar: str, zweck: str = ZWECK) -> str:
    if moeglich():
        blob = win32crypt.CryptProtectData(str(klar).encode("utf-8"), zweck, None, None, None, 0)
        return "dpapi:" + base64.b64encode(blob).decode("ascii")
    return "klar:" + str(klar)


def lesen(wert: str) -> str:
    w = str(wert or "")
    if w.startswith("dpapi:"):
        if not moeglich():
            raise GeheimError("GEHEIM_SYSTEM", "dieser Schlüssel lässt sich nur auf dem Windows-Gerät lesen, auf dem er gespeichert wurde")
        try:
            _d, klar = win32crypt.CryptUnprotectData(base64.b64decode(w[6:]), None, None, None, 0)
        except Exception:
            raise GeheimError("GEHEIM_BENUTZER", "dieser Schlüssel gehört zu einem anderen Windows-Benutzer oder Gerät") from None
        return klar.decode("utf-8")
    if w.startswith("klar:"):
        return w[5:]
    return w


def geschuetzt(wert: str) -> bool:
    return str(wert or "").startswith(("dpapi:", "klar:"))


__all__ = ["schuetzen", "lesen", "geschuetzt", "moeglich", "GeheimError"]
