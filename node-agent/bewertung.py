# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import ki_laufzeit

MAX_KANDIDATEN = 30
MAX_ZEICHEN = 900
SCHWELLE = 0.5
MIN_WERT = 0.1
TIMEOUT_S = 20.0


@dataclass(frozen=True)
class Sortierung:
    treffer: list
    werte: list[float]
    bester: float

    @property
    def deckt_ab(self) -> bool:
        return self.bester >= SCHWELLE


class Bewertung:
    def __init__(self, core: app_core.AppCore, *, server: ki_laufzeit.KiServer | None = None, herunterladen=ki_laufzeit.herunterladen,
                 geraete_ermitteln=ki_laufzeit.geraete_ermitteln, protokoll=None) -> None:
        self._core = core
        self.ordner = ki_laufzeit.KiOrdner(core.base_dir)
        self.server = server or ki_laufzeit.KiServer(self.ordner)
        self._herunterladen = herunterladen
        self._geraete_ermitteln = geraete_ermitteln
        self._log = protokoll or (lambda line: None)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.phase = "aus"
        self.meldung = ""
        self.wahl: ki_laufzeit.Wahl | None = None

    def bereit(self) -> bool:
        return self.server.laeuft()

    def zustand(self) -> dict:
        if self.phase == "bereit" and not self.server.laeuft():
            self.phase, self.meldung = "fehler", "das Bewertungs-Modell hat sich beendet"
        return {"phase": self.phase, "meldung": self.meldung, "laeuft": self.server.laeuft(),
                "geraet": self.wahl.geraet_name_de() if (self.wahl and self.server.laeuft()) else None}

    def einschalten(self) -> bool:
        with self._lock:
            if self.bereit() or (self._thread and self._thread.is_alive()):
                return False
            self.phase, self.meldung = "laden", ""
            self._thread = threading.Thread(target=self._ablauf, name="bewertung-einschalten", daemon=True)
            self._thread.start()
            return True

    def _ablauf(self) -> None:
        try:
            self.ordner.anlegen()
            if not self.ordner.laufzeit_da():
                raise app_core.AppError("KI_LAUFZEIT", "die KI-Laufzeit fehlt noch; schalte zuerst die KI ein")
            wahl = ki_laufzeit.waehlen_bewertung(self._geraete_ermitteln(self.ordner.server_exe))
            if wahl is None:
                self.phase, self.meldung = "aus", "auf diesem Gerät läuft kein Bewertungs-Modell (keine Grafikkarte mit freiem Speicher); die Suche sortiert wie bisher"
                self._log("OK bewertung übersprungen (keine Grafikkarte mit Platz)")
                return
            if not self.ordner.modell_da(ki_laufzeit.BEWERTUNG):
                self._herunterladen(ki_laufzeit.BEWERTUNG, self.ordner.modell_pfad(ki_laufzeit.BEWERTUNG))
            self.wahl = wahl
            self.server.start(wahl, bewerten=True)
            self.phase, self.meldung = "bereit", f"Bewertung der Fundstellen bereit ({wahl.geraet_name_de()})"
            self._log(f"OK bewertung einschalten {wahl.geraet.kennung if wahl.geraet else 'cpu'}")
        except app_core.AppError as exc:
            self.phase, self.meldung = "fehler", exc.detail
            self._log(f"ABGELEHNT bewertung einschalten: {exc.code}: {exc.detail}")
        except Exception as exc:
            self.phase, self.meldung = "fehler", f"Unerwarteter Fehler: {type(exc).__name__}"
            self._log(f"FEHLER bewertung einschalten: {type(exc).__name__}: {exc}")

    def ausschalten(self) -> None:
        self.server.stop()
        self.phase, self.meldung = "aus", ""

    def sortieren(self, frage: str, treffer: list) -> Sortierung | None:
        if not treffer or not self.server.laeuft():
            return None
        kandidaten, gesehen = [], set()
        for t in treffer:
            k = (t.quelle.kennung, t.text[:80])
            if k not in gesehen:
                gesehen.add(k)
                kandidaten.append(t)
            if len(kandidaten) >= MAX_KANDIDATEN:
                break
        texte = [(t.quelle.titel + "\n" if t.quelle.titel else "") + " ".join(t.text.split())[:MAX_ZEICHEN] for t in kandidaten]
        t0 = time.monotonic()
        try:
            werte = self.server.bewerten(" ".join(str(frage).split())[:1000], texte, timeout_s=TIMEOUT_S)
        except app_core.AppError as exc:
            self._log(f"ABGELEHNT bewertung: {exc.code}: {exc.detail}")
            return None
        reihe = sorted(range(len(kandidaten)), key=lambda i: werte[i], reverse=True)
        bester = werte[reihe[0]]
        behalten = [i for i in reihe if werte[i] >= MIN_WERT]
        self._log(f"OK bewertung {len(kandidaten)} Stellen in {time.monotonic() - t0:.1f} s, beste {bester:.2f}, {len(behalten)} behalten")
        return Sortierung([kandidaten[i] for i in behalten], [werte[i] for i in behalten], bester)


__all__ = ["Bewertung", "Sortierung", "SCHWELLE", "MIN_WERT", "MAX_KANDIDATEN", "MAX_ZEICHEN"]
