# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

import anhaenge
import app_core
import sicher_schreiben
import wissen

DATEI = "fenster.json"
ART = "fenster"
MAX_DATEIEN = 200
MAX_ZEICHEN_JE_DATEI = wissen.MAX_TEXT
NEU_LESEN_S = 300.0
ENDUNGEN = anhaenge.ENDUNGEN
SKILL_NAME = "frag-fenster"


class FensterError(app_core.AppError):
    pass


def skill_text(name: str) -> str:
    n = " ".join(str(name or "").split())[:60] or "diesem Betrieb"
    return (f"# Frag-Fenster von {n}\n\n"
            f"Du antwortest Besuchern der Website von {n}. Du sprichst für {n}, aber du bist eine KI und sagst das, wenn jemand fragt.\n"
            f"- Antworte nur mit dem, was in den Auszügen aus den Unterlagen von {n} steht. Zahlen, Preise, Zeiten und Namen genau so, wie sie dort stehen.\n"
            f"- Steht es nicht in den Unterlagen, sag ehrlich, dass du es nicht weißt, und bitte die Person, sich direkt an {n} zu wenden.\n"
            "- Erfinde keine Preise, Termine, Zusagen oder Rechtsauskünfte. Verspreche nichts im Namen des Betriebs.\n"
            "- Antworte in der Sprache der Frage, kurz und freundlich, mit Sie.\n"
            "- Frag nie nach persönlichen Daten (Name, Adresse, Telefonnummer, Zahlungsdaten).\n"
            "Die Grundregeln gelten weiter: nichts erfinden, nachfragen statt raten.")


def als_skill(name: str) -> dict:
    return {"name": SKILL_NAME, "text": f"---\nname: {SKILL_NAME}\ndescription: Antworten für Besucher der Website\n---\n\n{skill_text(name)}\n"}


def einbettcode(kennung: str, name: str, adresse: str = "https://kiplatz.at") -> str:
    k = re.sub(r"[^0-9a-f]", "", str(kennung))[:16]
    titel = " ".join(str(name or "").split())[:60].replace('"', "'")
    return (f'<iframe src="{adresse}/fenster-seite?f={k}" title="Frag {titel}" '
            'style="width:100%;max-width:420px;height:520px;border:0;border-radius:12px" loading="lazy"></iframe>')


class Fragfenster:

    def __init__(self, base_dir: Path, speicher: wissen.Wissensspeicher, *, jetzt=time.time) -> None:
        self._pfad = Path(base_dir) / DATEI
        self._base = Path(base_dir)
        self._wissen = speicher
        self._jetzt = jetzt
        self._lock = threading.Lock()
        self._gelesen_um = 0.0
        self._signatur: tuple | None = None

    def _lesen(self) -> dict:
        d = sicher_schreiben.json_laden(self._pfad, {}, art=dict)
        return {"an": bool(d.get("an", False)), "name": str(d.get("name", ""))[:60], "ordner": str(d.get("ordner", "")),
                "websites": [str(w) for w in d.get("websites") or [] if isinstance(w, str)][:5], "kennung": re.sub(r"[^0-9a-f]", "", str(d.get("kennung", "")))[:16],
                "seit": str(d.get("seit", ""))[:20], "dateien": int(d.get("dateien", 0) or 0)}

    def _schreiben(self, d: dict) -> None:
        sicher_schreiben.json_datei(self._pfad, d)


    def stand(self) -> dict:
        with self._lock:
            d = self._lesen()
        d["eingerichtet"] = bool(d["kennung"] and d["ordner"])
        d["ordner_name"] = Path(d["ordner"]).name if d["ordner"] else ""
        d["einbetten"] = einbettcode(d["kennung"], d["name"]) if d["kennung"] else ""
        d.pop("ordner", None)
        return d

    def ordner(self) -> Path | None:
        with self._lock:
            o = self._lesen()["ordner"]
        return Path(o) if o else None

    def einrichten(self, name: str, ordner: Path, websites: list[str], community) -> dict:
        p = Path(ordner)
        if not p.is_absolute() or app_core._is_reparse(p) or not p.is_dir():
            raise FensterError("FENSTER_ORDNER", "das ist kein gewöhnlicher Ordner")
        if p.parent == p:
            raise FensterError("FENSTER_ORDNER", "ein ganzes Laufwerk freizugeben geht nicht; bitte einen Ordner darin wählen")
        p = p.resolve()
        if p == self._base.resolve() or self._base.resolve() in p.parents:
            raise FensterError("FENSTER_ORDNER", "den Datenordner des Programms selbst bitte nicht freigeben")
        n = " ".join(str(name or "").split())[:60]
        if len(n) < 2:
            raise FensterError("FENSTER_NAME", "bitte einen Namen, zum Beispiel den Namen des Betriebs oder Vereins")
        ws = [w.strip() for w in (websites or []) if isinstance(w, str) and w.strip()][:5]
        if not ws:
            raise FensterError("FENSTER_WEBSITE", "bitte die Website, auf der das Fenster stehen soll (https://…)")
        r = community.fenster_anlegen(n, ws)
        with self._lock:
            d = self._lesen()
            d.update(an=True, name=str(r.get("name", n))[:60], ordner=str(p), websites=[str(w) for w in r.get("websites") or ws][:5],
                     kennung=re.sub(r"[^0-9a-f]", "", str(r.get("kennung", "")))[:16], seit=str(r.get("seit", ""))[:20])
            self._schreiben(d)
            self._signatur = None
        self.aktualisieren(erzwingen=True)
        return self.stand()

    def schalter(self, an: bool) -> dict:
        with self._lock:
            d = self._lesen()
            if not d["kennung"]:
                raise FensterError("FENSTER_FEHLT", "zuerst das Fenster einrichten (Name, Ordner, Website)")
            d["an"] = bool(an)
            self._schreiben(d)
        if an:
            self.aktualisieren(erzwingen=True)
        return self.stand()

    def entfernen(self, community=None) -> dict:
        with self._lock:
            self._quellen_weg()
            self._schreiben({"an": False})
            self._signatur = None
        if community is not None:
            try:
                community.fenster_entfernen()
            except Exception:
                pass
        return self.stand()


    def gilt(self, fe: dict | None) -> tuple[bool, str]:
        if not isinstance(fe, dict):
            return False, "ohne Fenster"
        with self._lock:
            d = self._lesen()
        if not d["kennung"] or not d["ordner"]:
            return False, "kein Fenster eingerichtet"
        if not d["an"]:
            return False, "Fenster ausgeschaltet"
        if str(fe.get("kennung", "")) != d["kennung"]:
            return False, "fremde Kennung"
        return True, d["name"]


    def _dateien(self, ordner: Path) -> list[Path]:
        aus: list[Path] = []
        for wurzel, unter, namen in os.walk(ordner):
            unter[:] = [u for u in sorted(unter) if not u.startswith(".") and not app_core._is_reparse(Path(wurzel) / u)]
            for n in sorted(namen):
                p = Path(wurzel) / n
                if n.startswith(".") or p.suffix.lower() not in ENDUNGEN or app_core._is_reparse(p):
                    continue
                aus.append(p)
                if len(aus) >= MAX_DATEIEN:
                    return aus
        return aus

    @staticmethod
    def _signatur_von(dateien: list[Path]) -> tuple:
        sig = []
        for p in dateien:
            try:
                st = p.stat()
                sig.append((str(p), int(st.st_mtime_ns), st.st_size))
            except OSError:
                continue
        return tuple(sig)

    def _quellen_weg(self) -> int:
        n = 0
        for q, _ in self._wissen.alle():
            if q.art == ART and self._wissen.entfernen(q.kennung):
                n += 1
        return n

    def aktualisieren(self, *, erzwingen: bool = False) -> int:
        with self._lock:
            d = self._lesen()
            t = self._jetzt()
            if not d["ordner"] or not d["kennung"]:
                return 0
            if not erzwingen and self._signatur is not None and t - self._gelesen_um < NEU_LESEN_S:
                return d["dateien"]
            ordner = Path(d["ordner"])
            self._gelesen_um = t
            if app_core._is_reparse(ordner) or not ordner.is_dir():
                self._quellen_weg()
                self._signatur = ()
                d["dateien"] = 0
                self._schreiben(d)
                return 0
            dateien = self._dateien(ordner)
            sig = self._signatur_von(dateien)
            if sig == self._signatur and not erzwingen:
                return d["dateien"]
            self._quellen_weg()
            n = 0
            for p in dateien:
                try:
                    a = anhaenge.lesen(p)
                except app_core.AppError:
                    continue
                titel = p.stem.replace("_", " ").replace("-", " ").strip() or p.name
                try:
                    self._wissen.hinzufuegen(ART, titel, f"{ordner.name}/{p.relative_to(ordner).as_posix()}", a.text[:MAX_ZEICHEN_JE_DATEI])
                    n += 1
                except wissen.WissenError:
                    continue
            self._signatur = sig
            d["dateien"] = n
            self._schreiben(d)
            return n


__all__ = ["Fragfenster", "FensterError", "ART", "SKILL_NAME", "skill_text", "als_skill", "einbettcode"]
