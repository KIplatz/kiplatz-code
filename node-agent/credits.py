# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
import threading
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import sicher_schreiben

STARTGUTHABEN = 100
KOSTEN_FRAGE = 1
LOHN_ANTWORT = 1
DATEINAME = "credits.json"
MAX_VERLAUF = 200
MAX_DATEI = 256 * 1024
NEUSTART = "2026-10-06"


class CreditsError(app_core.AppError):
    pass


@dataclass(frozen=True)
class Kontostand:
    guthaben: int
    verdient: int
    ausgegeben: int

    def text_de(self) -> str:
        return f"{self.guthaben} Credits (verdient {self.verdient}, ausgegeben {self.ausgegeben})"


def _gesperrt(f):
    def innen(self, *a, **k):
        with self._sperre:
            return f(self, *a, **k)
    innen.__name__, innen.__doc__, innen.__wrapped__ = f.__name__, f.__doc__, f
    return innen


class Kontobuch:
    def __init__(self, base_dir: Path) -> None:
        self.pfad = Path(base_dir) / DATEINAME
        self._sperre = threading.RLock()

    def _laden(self) -> dict:
        if not self.pfad.exists():
            return {"guthaben": STARTGUTHABEN, "verdient": 0, "ausgegeben": 0, "verlauf": [], "neustart": NEUSTART}
        try:
            d = json.loads(self.pfad.read_bytes()[:MAX_DATEI].decode("utf-8"))
            g, v, a = int(d["guthaben"]), int(d["verdient"]), int(d["ausgegeben"])
            if g < 0 or v < 0 or a < 0:
                raise ValueError
            stempel = str(d.get("neustart", ""))
        except (OSError, ValueError, KeyError, TypeError):
            raise CreditsError("CREDITS_DATEI", "die Credits-Datei ist beschädigt; sie wird nicht überschrieben") from None
        if stempel != NEUSTART:
            return self._neu_starten()
        return {"guthaben": g, "verdient": v, "ausgegeben": a, "verlauf": list(d.get("verlauf") or [])[-MAX_VERLAUF:], "neustart": NEUSTART}

    def _neu_starten(self) -> dict:
        with self._sperre:
            beiseite = self.pfad.with_name(f"credits.vor-neustart-{NEUSTART}.json")
            if not beiseite.exists():
                os.replace(self.pfad, beiseite)
            d = {"guthaben": STARTGUTHABEN, "verdient": 0, "ausgegeben": 0, "verlauf": [], "neustart": NEUSTART}
            self._buchen(d, "neustart", STARTGUTHABEN, "dieses Gerät", "Start für alle: jedes Gerät beginnt wieder mit dem Startguthaben")
            self._speichern(d)
            return d

    def _speichern(self, d: dict) -> None:
        app_core.ensure_plain_directory(self.pfad.parent)
        sicher_schreiben.text(self.pfad, json.dumps(d, ensure_ascii=False, indent=2) + os.linesep)

    def beschaedigt(self) -> bool:
        try:
            self._laden()
            return False
        except CreditsError:
            return True

    @_gesperrt
    def reparieren(self, *, verdient: int | None, geraet: str = "dieses Gerät") -> Kontostand:
        if not self.beschaedigt():
            return self.stand()
        beiseite = self.pfad.with_name(f"credits.beschaedigt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        os.replace(self.pfad, beiseite)
        v = max(0, int(verdient)) if verdient is not None else 0
        d = {"guthaben": STARTGUTHABEN + v, "verdient": v, "ausgegeben": 0, "verlauf": [], "neustart": NEUSTART}
        self._buchen(d, "reparatur", v, geraet,
                     "Kontobuch neu angelegt; die alte Datei war beschädigt und liegt daneben" + (", Stand aus der Bestenliste der Community übernommen" if verdient is not None else ""))
        self._speichern(d)
        return Kontostand(d["guthaben"], d["verdient"], d["ausgegeben"])

    def stand(self) -> Kontostand:
        d = self._laden()
        return Kontostand(d["guthaben"], d["verdient"], d["ausgegeben"])

    def verlauf(self, n: int = 20) -> list[dict]:
        return list(self._laden()["verlauf"])[-n:]

    def _buchen(self, d: dict, art: str, betrag: int, geraet: str, notiz: str) -> None:
        d["verlauf"].append({"zeit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "art": art, "betrag": betrag, "geraet": app_core._mask(geraet), "notiz": notiz})
        d["verlauf"] = d["verlauf"][-MAX_VERLAUF:]

    @_gesperrt
    def frage(self, *, geraet: str = "dieses Gerät") -> Kontostand:
        d = self._laden()
        if d["guthaben"] < KOSTEN_FRAGE:
            raise CreditsError("KEIN_GUTHABEN", "keine Credits mehr; teil deine Rechenkraft, dann verdienst du welche")
        d["guthaben"] -= KOSTEN_FRAGE
        d["ausgegeben"] += KOSTEN_FRAGE
        self._buchen(d, "frage", -KOSTEN_FRAGE, geraet, "Frage gestellt")
        self._speichern(d)
        return Kontostand(d["guthaben"], d["verdient"], d["ausgegeben"])

    @_gesperrt
    def antwort(self, *, geraet: str = "dieses Gerät") -> Kontostand:
        d = self._laden()
        d["guthaben"] += LOHN_ANTWORT
        d["verdient"] += LOHN_ANTWORT
        self._buchen(d, "antwort", LOHN_ANTWORT, geraet, "Antwort gerechnet")
        self._speichern(d)
        return Kontostand(d["guthaben"], d["verdient"], d["ausgegeben"])

    @_gesperrt
    def rechenarbeit(self, betrag: int, *, abschnitte: int, geraet: str = "dieses Gerät", was: str = "") -> Kontostand:
        betrag = max(0, int(betrag))
        d = self._laden()
        d["guthaben"] += betrag
        d["verdient"] += betrag
        notiz = was or (f"{int(abschnitte)} Abschnitte für die Community in Zahlen gerechnet" if int(abschnitte) else "Arbeit für die Community erledigt")
        self._buchen(d, "rechenarbeit", betrag, geraet, notiz)
        self._speichern(d)
        return Kontostand(d["guthaben"], d["verdient"], d["ausgegeben"])


REGEL_DE = f"Du startest mit {STARTGUTHABEN} Credits, jede Frage kostet {KOSTEN_FRAGE}. Rechenkraft teilen bringt 1 Credit je Auftrag. Kein Geld, keine Token, nur Anerkennung."

__all__ = ["Kontobuch", "Kontostand", "CreditsError", "STARTGUTHABEN", "KOSTEN_FRAGE", "LOHN_ANTWORT", "REGEL_DE"]
