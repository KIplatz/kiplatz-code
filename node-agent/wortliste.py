# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import gzip
import json
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import app_core
import modell_katalog
import namenpruefung
import sicher_schreiben
import wissen

STAND = "stand.json"
FEHLER_PAUSE_S = 3600
DF_MERK_MAX = 50_000


def _titel_norm(t: str) -> str:
    return " ".join(str(t or "").replace("_", " ").lower().split())


class Liste(namenpruefung.Namenspruefung):

    def __init__(self, pfad: Path, sprache: str) -> None:
        self.pfad = Path(pfad)
        self.sprache = sprache
        if sprache == "de":
            self._woerter = wissen.woerter
        else:
            import wikipedia
            self._woerter = wikipedia.woerter_en
        self._lock = threading.Lock()
        self._c = sqlite3.connect(f"file:{self.pfad.as_posix()}?mode=ro&immutable=1", uri=True, check_same_thread=False)
        self._merk: dict[str, int] = {}
        try:
            self.ausgabe = str((self._c.execute("SELECT v FROM info WHERE k = 'ausgabe'").fetchone() or [""])[0])
            self._c.execute("SELECT 1 FROM wort LIMIT 1").fetchone()
        except sqlite3.Error:
            self._c.close()
            raise

    def hat_wortzahl(self) -> bool:
        return True

    def _df(self, wort: str) -> int:
        if wort in self._merk:
            return self._merk[wort]
        with self._lock:
            d = 1 if self._c.execute("SELECT 1 FROM wort WHERE term = ?", (wort,)).fetchone() else 0
        if len(self._merk) < DF_MERK_MAX:
            self._merk[wort] = d
        return d

    def artikel_zu(self, titel: str) -> int | None:
        with self._lock:
            return 1 if self._c.execute("SELECT 1 FROM titel WHERE norm = ?", (_titel_norm(titel),)).fetchone() else None

    def schliessen(self) -> None:
        with self._lock:
            self._c.close()


class _Zusammen(namenpruefung.Namenspruefung):

    def __init__(self, listen: list[Liste]) -> None:
        self._listen = listen
        self._merk: dict[str, int] = {}

    def hat_wortzahl(self) -> bool:
        return bool(self._listen)

    @staticmethod
    def _woerter(text: str) -> list[str]:
        return [t.lower() for t in re.findall(r"\w+", str(text or ""))]

    def _df(self, wort: str) -> int:
        d = self._merk.get(wort)
        if d is None:
            leer, d = True, 0
            for liste in self._listen:
                stamm = liste._woerter(wort)
                if stamm:
                    leer = False
                    if all(liste._df(s) > 0 for s in stamm):
                        d = 1
                        break
            d = 1 if leer else d
            if len(self._merk) >= DF_MERK_MAX:
                self._merk.clear()
            self._merk[wort] = d
        return d

    def artikel_zu(self, titel: str) -> int | None:
        return next((1 for liste in self._listen if liste.artikel_zu(titel) is not None), None)


class Wortlisten:

    def __init__(self, ordner, *, holen=None, log=None, schlafen=time.sleep, pakete: dict | None = None) -> None:
        self._ordner_fn = ordner
        self._holen = holen
        self._log = log or (lambda _z: None)
        self._schlafen = schlafen
        self._pakete = pakete if pakete is not None else modell_katalog.WORTLISTEN
        self._listen: dict[str, Liste] = {}
        self._zusammen_merk: _Zusammen | None = None
        self._riegel = threading.Lock()
        self._faden: threading.Thread | None = None
        self.phase, self.meldung = "aus", ""


    def start(self) -> None:
        with self._riegel:
            if self._faden is not None and self._faden.is_alive():
                return
            self._faden = threading.Thread(target=self._lauf, name="wortliste", daemon=True)
            self._faden.start()

    def _lauf(self) -> None:
        while True:
            if self.bereitstellen():
                return
            self._schlafen(FEHLER_PAUSE_S)

    def bereitstellen(self) -> bool:
        ordner = Path(self._ordner_fn())
        app_core.ensure_plain_directory(ordner)
        stand = self._stand_lesen(ordner)
        alle = True
        for sprache, paket in self._pakete.items():
            if sprache in self._listen:
                continue
            ziel = ordner / f"wortliste-{sprache}.sqlite"
            try:
                if stand.get(sprache) != paket.sha256 or not ziel.is_file():
                    self.phase = "holen"
                    gz = ordner / paket.datei
                    (self._holen or _holen_standard)(paket, gz)
                    teil = ziel.with_name(ziel.name + ".teil")
                    with gzip.open(gz, "rb") as ein, open(teil, "wb") as aus:
                        shutil.copyfileobj(ein, aus, 8 * 1024 * 1024)
                    teil.replace(ziel)
                    gz.unlink(missing_ok=True)
                    stand[sprache] = paket.sha256
                    self._stand_schreiben(ordner, stand)
                    self._log(f"OK wortliste {sprache}: {paket.datei} geholt und entpackt")
                try:
                    self._listen[sprache] = Liste(ziel, sprache)
                except sqlite3.Error:
                    ziel.unlink(missing_ok=True)
                    stand.pop(sprache, None)
                    self._stand_schreiben(ordner, stand)
                    raise
            except Exception as exc:
                alle = False
                self.phase, self.meldung = "fehler", f"{sprache}: {getattr(exc, 'code', type(exc).__name__)}"
                self._log(f"FEHLER wortliste {sprache}: {getattr(exc, 'detail', None) or type(exc).__name__}")
        if alle:
            self.phase, self.meldung = "bereit", ""
            self._aufraeumen(ordner)
        return alle

    def _aufraeumen(self, ordner: Path) -> None:
        bleibt = {STAND} | {f"wortliste-{s}.sqlite" for s in self._pakete}
        for p in ordner.glob("wortliste-*"):
            if p.name not in bleibt:
                try:
                    p.unlink()
                except OSError:
                    pass

    @staticmethod
    def _stand_lesen(ordner: Path) -> dict:
        try:
            d = json.loads((ordner / STAND).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _stand_schreiben(ordner: Path, stand: dict) -> None:
        sicher_schreiben.json_datei(ordner / STAND, stand, indent=1)


    def bereit(self) -> bool:
        return bool(self._listen)

    def _zusammen(self) -> _Zusammen:
        listen = [self._listen[s] for s in sorted(self._listen)]
        z = self._zusammen_merk
        if z is None or z._listen != listen:
            z = self._zusammen_merk = _Zusammen(listen)
        return z

    def namen_bekannt(self, namen: list[str]) -> set[str]:
        return self._zusammen().namen_bekannt(list(namen or []))

    def unbekannte_namen(self, text: str) -> list[str]:
        return self._zusammen().unbekannte_namen(text)

    def zustand(self) -> dict:
        return {"phase": self.phase, "meldung": self.meldung, "sprachen": sorted(self._listen),
                "ausgabe": next((x.ausgabe for x in self._listen.values() if x.ausgabe), "")}


def _holen_standard(paket, ziel: Path) -> None:
    import ki_laufzeit
    ki_laufzeit.herunterladen(paket, ziel)


__all__ = ["Liste", "Wortlisten"]
