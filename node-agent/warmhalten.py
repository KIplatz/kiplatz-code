# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import threading
import time
from typing import Callable

ABSTAND_S = 60.0
TAKT_S = 10.0
LANGSAM_S = 3.0
FEHLER_ABSTAND_S = 600.0

NACHRICHTEN = [{"role": "user", "content": "ok"}]


def antwort_anstossen(server, abbruch: threading.Event | None = None) -> None:
    server.frage(list(NACHRICHTEN), max_tokens=1, temperature=0.0, abbruch=abbruch)


def bewertung_anstossen(server) -> None:
    server.bewerten("ok", ["ok"], timeout_s=60.0)


def bedeutung_anstossen(server) -> None:
    server.vektoren(["ok"], timeout_s=60.0)


class Warmhalter:

    def __init__(self, modelle: list[tuple[str, Callable, Callable]], *, darf: Callable[[], bool], log: Callable[[str], None] | None = None,
                 jetzt: Callable[[], float] = time.monotonic) -> None:
        self._modelle = list(modelle)
        self._darf = darf
        self._log = log or (lambda z: None)
        self._jetzt = jetzt
        self._halt = threading.Event()
        self._faden: threading.Thread | None = None
        self._fehler_zuletzt: dict[str, float] = {}
        self.angestossen: dict[str, int] = {}

    def start(self) -> None:
        if self._faden is not None and self._faden.is_alive():
            return
        self._halt.clear()
        self._faden = threading.Thread(target=self._lauf, name="warmhalten", daemon=True)
        self._faden.start()

    def stop(self) -> None:
        self._halt.set()

    def _lauf(self) -> None:
        while not self._halt.wait(TAKT_S):
            self.runde()

    def runde(self) -> None:
        for name, server_fn, anstossen in self._modelle:
            if self._halt.is_set():
                return
            try:
                server = server_fn()
                if server is None or not server.laeuft():
                    continue
                if self._jetzt() - float(getattr(server, "zuletzt_benutzt", 0.0) or 0.0) < ABSTAND_S:
                    continue
                if not self._darf():
                    return
                t0 = self._jetzt()
                anstossen(server)
                server.zuletzt_benutzt = self._jetzt()
                self.angestossen[name] = self.angestossen.get(name, 0) + 1
                d = self._jetzt() - t0
                if d >= LANGSAM_S:
                    self._log(f"INFO warmhalten {name}: Mini-Aufgabe dauerte {d:.1f} s (Modell war ausgelagert)")
            except Exception as exc:
                t = self._jetzt()
                if t - self._fehler_zuletzt.get(name, -FEHLER_ABSTAND_S) >= FEHLER_ABSTAND_S:
                    self._fehler_zuletzt[name] = t
                    self._log(f"INFO warmhalten {name}: {getattr(exc, 'detail', None) or type(exc).__name__}")


__all__ = ["Warmhalter", "ABSTAND_S", "TAKT_S", "LANGSAM_S", "antwort_anstossen", "bewertung_anstossen", "bedeutung_anstossen"]
