# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import hausordnung
import wissen

ART = "thema"
THEMA_TAGE = 30
JE_THEMA = 6
MAX_THEMEN = 10
TAKT_S = 24 * 3600


class Themen:
    def __init__(self, einstellung, gemeinschaft, speicher: wissen.Wissensspeicher, *, log=None, jetzt=time.time) -> None:
        self._einstellung = einstellung
        self._gemeinschaft = gemeinschaft
        self.speicher = speicher
        self._log = log or (lambda zeile: None)
        self._jetzt = jetzt
        self.zuletzt: float | None = None
        self.gesammelt = 0

    def liste(self) -> list[str]:
        try:
            e = self._einstellung() or {}
        except Exception:
            return []
        aus = []
        for t in e.get("meine_themen") or []:
            t = " ".join(str(t).split())[:60]
            if t and t.lower() not in [x.lower() for x in aus] and hausordnung.pruefen(t).ok:
                aus.append(t)
        return aus[:MAX_THEMEN]

    def faellig(self) -> bool:
        return bool(self.liste()) and (self.zuletzt is None or self._jetzt() - self.zuletzt >= TAKT_S)

    def sammeln(self, weiter=lambda: True) -> int:
        vorher = self.zuletzt
        self.zuletzt = self._jetzt()
        com = self._gemeinschaft() if callable(self._gemeinschaft) else self._gemeinschaft
        neu = 0
        bis = (datetime.now(timezone.utc) + timedelta(days=THEMA_TAGE)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for thema in self.liste():
            if not weiter():
                self.zuletzt = vorher
                self._log(f"OK themen: für eine Frage unterbrochen, {neu} neue Abschnitte bisher; geht danach weiter")
                self.gesammelt += neu
                return neu
            try:
                treffer, _n = com.suchen(thema, n=JE_THEMA)
            except app_core.AppError as exc:
                self._log(f"INFO themen {thema!r}: {exc.code}")
                continue
            for t in treffer:
                q = t.quelle
                if q.privat or not q.freigegeben or q.art not in ("seite", "nachgeschaut"):
                    continue
                text = " ".join(str(t.text or "").split())
                if len(text) < 40 or not hausordnung.pruefen(text).ok:
                    continue
                adresse = f"{q.adresse or q.titel}#{wissen.abschnitt_hash(text)}"
                if self.speicher._pfad(wissen.kennung_fuer(ART, adresse)).is_file():
                    continue
                try:
                    self.speicher.hinzufuegen(ART, f"{thema}: {q.titel}", adresse, text, gueltig_bis=bis)
                    neu += 1
                except app_core.AppError:
                    continue
        self.gesammelt += neu
        self._log(f"OK themen: {neu} neue Abschnitte zu {len(self.liste())} Themen, privat")
        return neu

    def stand(self) -> dict:
        return {"themen": self.liste(), "gesammelt": self.gesammelt, "zuletzt": self.zuletzt,
                "im_speicher": sum(1 for q, _ in self.speicher.alle(auch_ungeprueft=True) if q.art == ART)}


__all__ = ["Themen", "ART", "THEMA_TAGE", "JE_THEMA", "MAX_THEMEN", "TAKT_S"]
