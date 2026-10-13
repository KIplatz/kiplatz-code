# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Callable

ENDEN = ("\n", ". ", "! ", "? ", ": ")
MAX_PUFFER = 240


class Sammler:
    def __init__(self, ausgabe: Callable[[str], None], mit: Callable[[str], None] | None = None) -> None:
        self._ausgabe = ausgabe
        self._mit = mit
        self._puffer = ""
        self.gezeigt = 0

    def __call__(self, piece: str) -> None:
        if self._mit is not None:
            self._mit(piece)
        self._puffer += piece
        idx = max(self._puffer.rfind(e) for e in ENDEN)
        if idx >= 0:
            ende = idx + (1 if self._puffer[idx] == "\n" else 2)
            self._zeigen(self._puffer[:ende])
            self._puffer = self._puffer[ende:]
        elif len(self._puffer) >= MAX_PUFFER:
            self._zeigen(self._puffer)
            self._puffer = ""

    def rest(self) -> None:
        if self._puffer:
            self._zeigen(self._puffer)
            self._puffer = ""

    def _zeigen(self, text: str) -> None:
        self.gezeigt += 1
        self._ausgabe(text)


__all__ = ["Sammler", "ENDEN", "MAX_PUFFER"]
