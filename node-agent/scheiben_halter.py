# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import shutil
import time
from pathlib import Path

import scheiben

DIRNAME = "scheiben"
RESERVE_BYTES = 1024 * 1024 * 1024
TEXTE = {
    "haelt": "Dein Gerät hält {0} Scheiben des gemeinsamen Wissens ({1} MB von {2} MB).",
    "aus": "Dein Gerät hält keine Scheiben (Freigabe: 0 MB).",
    "leer": "Dein Gerät hält noch keine Scheibe; sobald eine zu vergeben ist, kommt sie von selbst.",
}


class Halter:
    def __init__(self, base_dir: Path, gemeinschaft, *, limit_mb, log=None, jetzt=time.time, ordner=None) -> None:
        self._standard = Path(base_dir) / DIRNAME
        self._ordner = ordner
        self._gemeinschaft = gemeinschaft if callable(gemeinschaft) else (lambda: gemeinschaft)
        self._limit_mb = limit_mb if callable(limit_mb) else (lambda: int(limit_mb))
        self._log = log or (lambda zeile: None)
        self._jetzt = jetzt
        self.zuletzt = ""
        self.geliefert = 0
        self.geholt = 0


    @property
    def dir(self) -> Path:
        if self._ordner is not None:
            try:
                o = self._ordner()
            except Exception:
                o = None
            if o:
                return Path(o)
        return self._standard

    def umziehen(self, neu: Path) -> int:
        alt = self.dir
        neu = Path(neu)
        try:
            gleich = alt.resolve() == neu.resolve()
        except OSError:
            gleich = alt == neu
        if gleich:
            return 0
        n = 0
        for k, _groesse in self.liste():
            quelle = alt / f"{k}.zip"
            ziel = neu / f"{k}.zip"
            try:
                neu.mkdir(parents=True, exist_ok=True)
                shutil.copy2(quelle, ziel)
                if scheiben.pruefsumme(ziel) != scheiben.pruefsumme(quelle):
                    raise OSError("Kopie weicht ab")
                quelle.unlink()
                n += 1
            except Exception as exc:
                try:
                    ziel.unlink(missing_ok=True)
                except OSError:
                    pass
                self._log(f"FEHLER scheibe umziehen {k}: {type(exc).__name__}")
        if n:
            self._log(f"OK scheiben umgezogen: {n}")
            self.zuletzt = f"{n} Scheiben auf das gewählte Laufwerk verschoben."
        return n

    def liste(self) -> list[tuple[str, int]]:
        if not self.dir.is_dir():
            return []
        aus = []
        for p in sorted(self.dir.glob("*.zip")):
            try:
                aus.append((p.stem, p.stat().st_size))
            except OSError:
                continue
        return aus

    def belegt(self) -> int:
        return sum(n for _, n in self.liste())

    def limit_mb(self) -> int:
        try:
            return max(0, int(self._limit_mb()))
        except (TypeError, ValueError):
            return 0

    def frei_mb(self) -> int:
        limit = self.limit_mb() * 1024 * 1024 - self.belegt()
        try:
            da = self.dir
            while not da.exists() and da.parent != da:
                da = da.parent
            platte = shutil.disk_usage(da).free - RESERVE_BYTES
        except OSError:
            platte = 0
        return max(0, min(limit, platte)) // (1024 * 1024)

    def speicher(self) -> dict:
        return {"limit_mb": self.limit_mb(), "frei_mb": self.frei_mb()}


    def halten(self, auftrag: dict) -> bool:
        kennung = str(auftrag.get("scheibe", ""))
        sha = str(auftrag.get("sha256", "")).lower()
        groesse = int(auftrag.get("bytes", 0) or 0)
        if not kennung.isalnum() or len(sha) != 64 or groesse <= 0 or groesse > scheiben.MAX_SCHEIBE_BYTES:
            self._log(f"ABGELEHNT scheibe halten: unbrauchbarer Auftrag")
            return False
        if groesse > self.frei_mb() * 1024 * 1024 + 1024 * 1024:
            self.zuletzt = "Eine Scheibe passte nicht mehr in deine Freigabe."
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        ziel = self.dir / f"{kennung}.zip"
        try:
            self._gemeinschaft().scheibe_holen(kennung, ziel, sha)
            scheiben.scheibe_lesen(ziel)
            r = self._gemeinschaft().scheibe_bestaetigen(kennung, sha)
        except Exception as exc:
            try:
                ziel.unlink(missing_ok=True)
            except OSError:
                pass
            self._log(f"FEHLER scheibe halten {kennung}: {getattr(exc, 'detail', None) or type(exc).__name__}")
            self.zuletzt = "Eine Scheibe kam nicht sauber an; das Programm versucht es später wieder."
            return False
        self.geholt += 1
        self.zuletzt = f"Scheibe {kennung[:8]} geholt und geprüft ({groesse // 1024} KB)."
        self._log(f"OK scheibe halten {kennung}: {groesse} Bytes, {r.get('halter', '?')} Halter, +{r.get('credits', 0)} Credits")
        return True

    def liefern(self, auftrag: dict) -> bool:
        kennung = str(auftrag.get("scheibe", ""))
        pfad = self.dir / f"{kennung}.zip"
        if not kennung.isalnum() or not pfad.is_file():
            self._log(f"FEHLER scheibe liefern {kennung}: liegt nicht auf diesem Gerät")
            try:
                self._gemeinschaft().scheibe_abgegeben(kennung)
            except Exception:
                pass
            return False
        try:
            if scheiben.pruefsumme(pfad) != str(auftrag.get("sha256", "")).lower():
                pfad.unlink(missing_ok=True)
                self._gemeinschaft().scheibe_abgegeben(kennung)
                self._log(f"FEHLER scheibe liefern {kennung}: die Kopie hier war beschädigt und ist gelöscht")
                self.zuletzt = "Eine Scheibe auf deinem Gerät war beschädigt; sie kommt bei Gelegenheit neu."
                return False
            r = self._gemeinschaft().scheibe_liefern(kennung, pfad)
        except Exception as exc:
            self._log(f"FEHLER scheibe liefern {kennung}: {getattr(exc, 'detail', None) or type(exc).__name__}")
            return False
        self.geliefert += 1
        self.zuletzt = (f"Scheibe {kennung[:8]} für die Stichprobe geliefert, der Server hatte sie verloren und hat sie zurück." if r.get("zurueckgeholt")
                        else f"Scheibe {kennung[:8]} für die Stichprobe geliefert.")
        self._log(f"OK scheibe liefern {kennung}" + (" (zurückgeholt)" if r.get("zurueckgeholt") else "") + f", +{r.get('credits', 0)} Credits")
        return True

    def aufraeumen(self) -> int:
        weg = 0
        limit = self.limit_mb() * 1024 * 1024
        eintraege = []
        for k, n in self.liste():
            try:
                eintraege.append((self.dir.joinpath(f"{k}.zip").stat().st_mtime, k, n))
            except OSError:
                continue
        eintraege.sort()
        belegt = sum(n for _, _, n in eintraege)
        for _, k, n in eintraege:
            if belegt <= limit:
                break
            try:
                (self.dir / f"{k}.zip").unlink()
                belegt -= n
                weg += 1
                self._gemeinschaft().scheibe_abgegeben(k)
                self._log(f"OK scheibe abgegeben {k} (über der Freigabe)")
            except Exception as exc:
                self._log(f"FEHLER scheibe abgeben {k}: {type(exc).__name__}")
        if weg:
            self.zuletzt = f"{weg} Scheiben abgegeben, weil die Freigabe kleiner ist."
        return weg

    def veraltete_loeschen(self) -> int:
        try:
            weg = self._gemeinschaft().scheiben_weg()
        except Exception as exc:
            self._log(f"FEHLER scheiben weg: {getattr(exc, 'detail', None) or type(exc).__name__}")
            return 0
        n = 0
        da = {k for k, _ in self.liste()}
        for k in weg:
            k = str(k)
            if not k.isalnum():
                continue
            try:
                if k in da:
                    (self.dir / f"{k}.zip").unlink(missing_ok=True)
                    n += 1
                self._gemeinschaft().scheibe_abgegeben(k)
                self._log(f"OK scheibe gelöscht {k} (vom Server zurückgezogen)")
            except Exception as exc:
                self._log(f"FEHLER scheibe löschen {k}: {type(exc).__name__}")
        if n:
            self.zuletzt = f"{n} alte Scheiben gelöscht, die der Server zurückgezogen hat."
        return n

    def alles_loeschen(self) -> int:
        n = 0
        for k, _ in self.liste():
            try:
                (self.dir / f"{k}.zip").unlink()
                n += 1
            except OSError:
                pass
        return n

    def stand(self) -> dict:
        liste = self.liste()
        mb = round(sum(n for _, n in liste) / (1024 * 1024), 1)
        limit = self.limit_mb()
        text = TEXTE["aus"] if limit == 0 else (TEXTE["haelt"].format(len(liste), mb, limit) if liste else TEXTE["leer"])
        return {"anzahl": len(liste), "mb": mb, "limit_mb": limit, "frei_mb": self.frei_mb(), "text": text, "zuletzt": self.zuletzt, "geholt": self.geholt, "geliefert": self.geliefert}


__all__ = ["Halter", "DIRNAME", "TEXTE"]
