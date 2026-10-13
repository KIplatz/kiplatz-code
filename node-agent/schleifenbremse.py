# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import threading
import time
from typing import Callable, Hashable

HOECHSTENS = 3
FENSTER_S = 3600.0
PAUSE_S = 3600.0
PAUSE_HOECHSTENS_S = 24 * 3600.0
MAX_EINTRAEGE = 20_000


class Schleifenbremse:
    def __init__(self, *, hoechstens: int = HOECHSTENS, fenster_s: float = FENSTER_S, pause_s: float = PAUSE_S, jetzt: Callable[[], float] = time.time,
                 log: Callable[[str], None] | None = None, bei_stopp: Callable[[str, Hashable], None] | None = None) -> None:
        self.hoechstens, self.fenster_s, self.pause_s = int(hoechstens), float(fenster_s), float(pause_s)
        self._jetzt = jetzt
        self._log = log or (lambda _z: None)
        self.bei_stopp = bei_stopp
        self._lock = threading.Lock()
        self._vergeben: dict[tuple[str, Hashable], list[float]] = {}
        self._gesperrt: dict[tuple[str, Hashable], float] = {}
        self._stopps_je: dict[tuple[str, Hashable], int] = {}
        self.stopps = 0

    def darf(self, geraet: str, ziel: Hashable) -> bool:
        with self._lock:
            t = self._jetzt()
            bis = self._gesperrt.get((str(geraet), ziel))
            if bis is not None and t < bis:
                return False
            zeiten = [z for z in self._vergeben.get((str(geraet), ziel), []) if t - z < self.fenster_s]
            return len(zeiten) < self.hoechstens

    def vergeben(self, geraet: str, ziel: Hashable) -> bool:
        with self._lock:
            t = self._jetzt()
            k = (str(geraet), ziel)
            zeiten = [z for z in self._vergeben.get(k, []) if t - z < self.fenster_s] + [t]
            self._vergeben[k] = zeiten
            if len(self._vergeben) > MAX_EINTRAEGE:
                for alt in sorted(self._vergeben, key=lambda x: self._vergeben[x][-1])[: MAX_EINTRAEGE // 4]:
                    self._vergeben.pop(alt, None)
            if len(zeiten) < self.hoechstens:
                return True
            n = self._stopps_je[k] = self._stopps_je.get(k, 0) + 1
            pause = min(self.pause_s * 2 ** (n - 1), max(self.pause_s, PAUSE_HOECHSTENS_S))
            self._gesperrt[k] = t + pause
            self._vergeben.pop(k, None)
            self.stopps += 1
        self._log(f"SCHLEIFE gestoppt: {ziel!r} ging {len(zeiten)} Mal ohne Ergebnis an {geraet}; {int(pause // 60)} min Pause nur für diese eine Arbeit, alles andere geht weiter")
        if self.bei_stopp is not None:
            try:
                self.bei_stopp(str(geraet), ziel)
            except Exception:
                pass
        return False

    def erledigt(self, geraet: str, ziel: Hashable) -> None:
        with self._lock:
            self._vergeben.pop((str(geraet), ziel), None)
            self._gesperrt.pop((str(geraet), ziel), None)
            self._stopps_je.pop((str(geraet), ziel), None)


__all__ = ["Schleifenbremse", "HOECHSTENS", "FENSTER_S", "PAUSE_S"]
