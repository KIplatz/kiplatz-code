# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import ki_laufzeit
import verteiler

FRAGE_VORSPANN = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
MAX_FRAGE = 2000
SCHLANK_AB_MB = 2500
NEUSTART_WARTEN_S = 20.0


class Bedeutung:
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
        self._neustart = False

    def bereit(self) -> bool:
        return self.server.laeuft()

    def zustand(self) -> dict:
        if self.phase == "bereit" and not self.server.laeuft():
            self.phase, self.meldung = "fehler", "das Bedeutungs-Modell hat sich beendet"
        return {"phase": self.phase, "meldung": self.meldung, "laeuft": self.server.laeuft(),
                "geraet": self.wahl.geraet_name_de() if (self.wahl and self.server.laeuft()) else None}

    def einschalten(self) -> bool:
        with self._lock:
            if self.bereit() or (self._thread and self._thread.is_alive()):
                return False
            self.phase, self.meldung = "laden", ""
            self._thread = threading.Thread(target=self._ablauf, name="bedeutung-einschalten", daemon=True)
            self._thread.start()
            return True

    def _ablauf(self) -> None:
        try:
            self.ordner.anlegen()
            if not self.ordner.laufzeit_da():
                raise app_core.AppError("KI_LAUFZEIT", "die KI-Laufzeit fehlt noch; schalte zuerst die KI ein")
            if not self.ordner.modell_da(ki_laufzeit.EMBEDDING):
                self._herunterladen(ki_laufzeit.EMBEDDING, self.ordner.modell_pfad(ki_laufzeit.EMBEDDING))
            wahl = ki_laufzeit.waehlen_rechen(self._geraete_ermitteln(self.ordner.server_exe))
            first = self._core.load_first_start()
            if wahl.geraet is None and first is not None and first.role is not app_core.Role.COMPUTE_STRONG:
                self.phase, self.meldung = "aus", "auf diesem Gerät läuft kein Bedeutungs-Modell (keine Grafikkarte, wenig Speicher); Suche nach Wörtern"
                self._log("OK bedeutung übersprungen (schwaches Gerät)")
                return
            self.wahl = wahl
            threads = None
            if wahl.geraet is None and first is not None and first.cpu_cores:
                threads = max(1, int(first.cpu_cores) * int(self._core.load_freigabe().cpu_prozent) // 100)
            self.server.start(wahl, embedding=True, threads=threads)
            self.phase, self.meldung = "bereit", f"Bedeutungssuche bereit ({wahl.geraet_name_de()})"
            self._log(f"OK bedeutung einschalten {wahl.geraet.kennung if wahl.geraet else 'cpu'}")
        except app_core.AppError as exc:
            self.phase, self.meldung = "fehler", exc.detail
            self._log(f"ABGELEHNT bedeutung einschalten: {exc.code}: {exc.detail}")
        except Exception as exc:
            self.phase, self.meldung = "fehler", f"Unerwarteter Fehler: {type(exc).__name__}"
            self._log(f"FEHLER bedeutung einschalten: {type(exc).__name__}: {exc}")
        finally:
            self._neustart = False

    def ausschalten(self) -> None:
        self.server.stop()
        self.phase, self.meldung = "aus", ""

    def schlank_machen(self, grenze_mb: int = SCHLANK_AB_MB) -> bool:
        mb = self.server.privat_mb()
        if mb is None or mb < int(grenze_mb):
            return False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self.server.stop()
            self.phase, self.meldung = "aus", ""
            self._neustart = True
        self._log(f"OK bedeutung neu gestartet: hielt {mb} MB Arbeitsspeicher")
        if not self.einschalten():
            self._neustart = False
            return False
        return True

    def frage_vektor(self, frage: str) -> list[float] | None:
        if not self.server.laeuft():
            t = self._thread
            if not self._neustart or t is None or not t.is_alive():
                return None
            t.join(timeout=NEUSTART_WARTEN_S)
            if not self.server.laeuft():
                return None
        text = FRAGE_VORSPANN + " ".join(str(frage or "").split())[:MAX_FRAGE]
        try:
            v = self.server.vektoren([text], timeout_s=60)[0]
        except app_core.AppError as exc:
            self._log(f"ABGELEHNT bedeutung frage: {exc.code}: {exc.detail}")
            return None
        return [round(x, verteiler.NACHKOMMA) for x in v]


__all__ = ["Bedeutung", "FRAGE_VORSPANN"]
