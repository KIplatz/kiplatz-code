# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import herkunft
import sicher_schreiben

DIRNAME = "gespraeche"
PAPIERKORB = "papierkorb"
MAX_NACHRICHT = 20000
MAX_NACHRICHTEN = 400
MAX_DATEI = 4 * 1024 * 1024 + 5 * 60_000 * 4
TITEL_LAENGE = 48


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


MAX_PROJEKT = 60
FARBEN = {"blau": ("Blau", "#2f7fd8"), "gruen": ("Grün", "#2e9e5b"), "gelb": ("Gelb", "#d4a106"), "orange": ("Orange", "#e07a1f"),
          "rot": ("Rot", "#d64541"), "violett": ("Violett", "#8b5cc7"), "rosa": ("Rosa", "#d9579a"), "grau": ("Grau", "#8a949c")}
PROJEKT_FARBEN = "projekte.json"
FARBEN = {"blau": ("Blau", "#2f7fd8"), "gruen": ("Grün", "#2e9e5b"), "gelb": ("Gelb", "#d4a106"), "orange": ("Orange", "#e07a1f"),
          "rot": ("Rot", "#d64541"), "violett": ("Violett", "#8b5cc7"), "rosa": ("Rosa", "#d9579a"), "grau": ("Grau", "#8a949c")}
PROJEKT_FARBEN = "projekte.json"


@dataclass
class Gespraech:
    kennung: str
    titel: str
    erstellt: str
    geaendert: str
    nachrichten: list[dict] = field(default_factory=list)
    projekt: str = ""
    archiviert: bool = False
    angeheftet: bool = False
    skill: str = ""
    herkunft: str = ""
    anhaenge: list[dict] = field(default_factory=list)
    ordner: str = ""
    farbe: str = ""
    farbe: str = ""

    def to_json_dict(self) -> dict:
        return {"kennung": self.kennung, "titel": self.titel, "erstellt": self.erstellt, "geaendert": self.geaendert, "nachrichten": self.nachrichten,
                "projekt": self.projekt, "archiviert": self.archiviert, "angeheftet": self.angeheftet, "skill": self.skill, "herkunft": self.herkunft,
                "ordner": self.ordner, "ordner_name": Path(self.ordner).name if self.ordner else "", "farbe": self.farbe,
                "anhaenge": [{k: v for k, v in a.items() if k != "text"} for a in self.anhaenge]}

    def to_datei_dict(self) -> dict:
        d = self.to_json_dict()
        d["anhaenge"] = self.anhaenge
        return d

    def als_markdown(self) -> str:
        zeilen = [f"# {self.titel}", "", f"KIplatz, Gespräch vom {self.erstellt[:10]}" + (f", Projekt „{self.projekt}“" if self.projekt else ""), ""]
        for n in self.nachrichten:
            wer = "Ich" if n.get("rolle") == "user" else "KIplatz"
            zeilen += [f"## {wer}", ""]
            et = (n.get("lieferschein") or {}).get("etikett") if n.get("rolle") == "assistant" else None
            if isinstance(et, dict):
                zeilen += ["<!-- kiplatz-ki " + json.dumps(et, ensure_ascii=False, separators=(",", ":")) + " -->"]
            zeilen += [str(n.get("text", "")).rstrip(), ""]
            ls = n.get("lieferschein") or {}
            if n.get("rolle") == "assistant" and ls.get("quellen"):
                zeilen += [f"*Woher: {ls['quellen']}*", ""]
        return "\n".join(zeilen).rstrip() + "\n"

    def fuer_modell(self, *, letzte: int = 20) -> list[dict]:
        return [{"role": n["rolle"], "content": n["text"]} for n in self.nachrichten[-letzte:] if n["rolle"] in ("user", "assistant") and not n.get("intern")]


def _etikett_fuer(text: str, etikett) -> dict:
    if isinstance(etikett, dict) and etikett.get("unterschrift") and etikett.get("pruefsumme") == herkunft.pruefsumme(text):
        return {k: etikett[k] for k in ("v", "ki_erzeugt", "von", "tag", "pruefsumme", "unterschrift") if k in etikett}
    return herkunft.etikett_ohne_unterschrift(text)


def _gesperrt(f):
    def innen(self, *a, **k):
        with self.sperre:
            return f(self, *a, **k)
    innen.__name__, innen.__doc__, innen.__wrapped__ = f.__name__, f.__doc__, f
    return innen


def ist_leer(g: Gespraech) -> bool:
    return (not g.nachrichten and g.titel == "Neues Gespräch" and not g.projekt and not g.archiviert and not g.angeheftet and not g.skill
            and not g.anhaenge and not g.ordner and not g.farbe)


class Gespraechsablage:
    def __init__(self, base_dir: Path) -> None:
        self.ordner = Path(base_dir) / DIRNAME
        self.sperre = threading.RLock()

    def _pfad(self, kennung: str) -> Path:
        if not kennung or not all(c.isalnum() or c in "-_" for c in kennung) or len(kennung) > 40:
            raise app_core.AppError("GESPRAECH_KENNUNG", "ungültige Gesprächskennung")
        return self.ordner / f"{kennung}.json"

    @_gesperrt
    def neu(self) -> Gespraech:
        app_core.ensure_plain_directory(self.ordner)
        leer = self._leeres()
        if leer is not None:
            leer.geaendert = _jetzt()
            self.speichern(leer)
            return leer
        kennung = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        g = Gespraech(kennung=kennung, titel="Neues Gespräch", erstellt=_jetzt(), geaendert=_jetzt())
        self.speichern(g)
        return g

    def speichern(self, g: Gespraech) -> None:
        app_core.ensure_plain_directory(self.ordner)
        sicher_schreiben.text(self._pfad(g.kennung), json.dumps(g.to_datei_dict(), ensure_ascii=False, indent=2) + os.linesep)

    def laden(self, kennung: str) -> Gespraech:
        pfad = self._pfad(kennung)
        try:
            for versuch in range(25):
                try:
                    roh = pfad.read_bytes()
                    break
                except PermissionError:
                    if versuch == 24:
                        raise
                    time.sleep(0.004)
            d = json.loads(roh[:MAX_DATEI].decode("utf-8"))
            return Gespraech(kennung=str(d["kennung"]), titel=str(d["titel"]), erstellt=str(d["erstellt"]), geaendert=str(d["geaendert"]), nachrichten=list(d.get("nachrichten") or []),
                             projekt=str(d.get("projekt") or "")[:MAX_PROJEKT], archiviert=bool(d.get("archiviert")), angeheftet=bool(d.get("angeheftet")),
                             skill=str(d.get("skill") or d.get("baustein") or "")[:64], herkunft=str(d.get("herkunft") or "")[:40],
                             anhaenge=[a for a in (d.get("anhaenge") or []) if isinstance(a, dict)][:10], ordner=str(d.get("ordner") or "")[:1000],
                             farbe=str(d.get("farbe") or "") if str(d.get("farbe") or "") in FARBEN else "")
        except FileNotFoundError:
            raise app_core.AppError("GESPRAECH_FEHLT", "dieses Gespräch gibt es nicht") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise app_core.AppError("GESPRAECH_DATEI", "die Gesprächsdatei ist unlesbar") from None

    @_gesperrt
    def aendern(self, kennung: str, aenderung) -> Gespraech:
        g = self.laden(kennung)
        aenderung(g)
        self.speichern(g)
        return g

    def _leeres(self) -> Gespraech | None:
        if not self.ordner.is_dir():
            return None
        leere = []
        for p in self.ordner.glob("*.json"):
            try:
                g = self.laden(p.stem)
            except app_core.AppError:
                continue
            if ist_leer(g):
                leere.append(g)
        return max(leere, key=lambda g: (g.geaendert, g.kennung)) if leere else None

    def liste(self) -> list[dict]:
        if not self.ordner.is_dir():
            return []
        out = []
        for p in self.ordner.glob("*.json"):
            try:
                g = self.laden(p.stem)
            except app_core.AppError:
                continue
            if ist_leer(g):
                continue
            out.append({"kennung": g.kennung, "titel": g.titel, "geaendert": g.geaendert, "anzahl": len(g.nachrichten), "projekt": g.projekt, "archiviert": g.archiviert, "angeheftet": g.angeheftet,
                        "farbe": g.farbe})
        out.sort(key=lambda e: (e["angeheftet"], e["geaendert"], e["kennung"]), reverse=True)
        return out

    def projekte(self) -> list[str]:
        return sorted({e["projekt"] for e in self.liste() if e["projekt"]}, key=str.lower)

    @_gesperrt
    def verschieben(self, kennung: str, projekt: str) -> Gespraech:
        projekt = " ".join((projekt or "").split())
        if len(projekt) > MAX_PROJEKT:
            raise app_core.AppError("GESPRAECH_PROJEKT", f"der Projektname ist zu lang (höchstens {MAX_PROJEKT} Zeichen)")
        g = self.laden(kennung)
        g.projekt = projekt
        g.geaendert = _jetzt()
        self.speichern(g)
        if projekt and projekt not in self.projekt_farben():
            d = self.projekt_farben(); d[projekt] = ""; self._projekte_schreiben(d)
        return g

    @_gesperrt
    def anhang_hinzufuegen(self, kennung: str, name: str, text: str, info: str) -> Gespraech:
        g = self.laden(kennung)
        if len(g.anhaenge) >= 5:
            raise app_core.AppError("ANHANG_VIELE", "höchstens 5 Dateien je Gespräch; entferne eine, dann geht es weiter")
        g.anhaenge.append({"name": str(name)[:120], "info": str(info)[:60], "text": str(text), "zeit": _jetzt()})
        g.geaendert = _jetzt()
        self.speichern(g)
        return g

    @_gesperrt
    def anhang_entfernen(self, kennung: str, nummer: int) -> Gespraech:
        g = self.laden(kennung)
        if not 0 <= nummer < len(g.anhaenge):
            raise app_core.AppError("ANHANG_FEHLT", "diese Datei ist nicht mehr da")
        a = g.anhaenge.pop(nummer)
        if a.get("art") == "bild":
            (self.ordner / f"{g.kennung}-bilder" / str(a.get("datei", ""))).unlink(missing_ok=True)
        self.speichern(g)
        return g

    BILD_ARTEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    MAX_BILD = 6 * 1024 * 1024

    @_gesperrt
    def bild_hinzufuegen(self, kennung: str, pfad: Path) -> Gespraech:
        p = Path(pfad)
        mime = self.BILD_ARTEN.get(p.suffix.lower())
        if not mime or app_core._is_reparse(p) or not p.is_file():
            raise app_core.AppError("BILD_ART", "das ist kein Bild, das das Programm lesen kann (PNG, JPG, WebP, GIF)")
        if p.stat().st_size > self.MAX_BILD:
            raise app_core.AppError("BILD_GROSS", "das Bild ist größer als 6 MB; bitte ein kleineres nehmen")
        g = self.laden(kennung)
        if sum(1 for a in g.anhaenge if a.get("art") == "bild") >= 3:
            raise app_core.AppError("BILD_VIELE", "höchstens 3 Bilder je Gespräch")
        ordner = app_core.ensure_plain_directory(self.ordner / f"{g.kennung}-bilder")
        name = f"{len(g.anhaenge) + 1:02d}-{secrets.token_hex(3)}{p.suffix.lower()}"
        sicher_schreiben.roh(ordner / name, p.read_bytes())
        g.anhaenge.append({"art": "bild", "name": p.name[:120], "info": f"Bild, {p.stat().st_size // 1024} kB", "datei": name, "mime": mime, "zeit": _jetzt()})
        g.geaendert = _jetzt()
        self.speichern(g)
        return g

    @_gesperrt
    def bild_aus_bytes(self, kennung: str, name: str, daten: bytes) -> Gespraech:
        if daten[:8] == b"\x89PNG\r\n\x1a\n":
            endung = ".png"
        elif daten[:3] == b"\xff\xd8\xff":
            endung = ".jpg"
        elif daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
            endung = ".webp"
        elif daten[:6] in (b"GIF87a", b"GIF89a"):
            endung = ".gif"
        else:
            raise app_core.AppError("BILD_ART", "das ist kein Bild, das das Programm lesen kann (PNG, JPG, WebP, GIF)")
        if len(daten) > self.MAX_BILD:
            raise app_core.AppError("BILD_GROSS", "das Bild ist größer als 6 MB; bitte ein kleineres nehmen")
        g = self.laden(kennung)
        if sum(1 for a in g.anhaenge if a.get("art") == "bild") >= 3:
            raise app_core.AppError("BILD_VIELE", "höchstens 3 Bilder je Gespräch")
        ordner = app_core.ensure_plain_directory(self.ordner / f"{g.kennung}-bilder")
        datei = f"{len(g.anhaenge) + 1:02d}-{secrets.token_hex(3)}{endung}"
        sicher_schreiben.roh(ordner / datei, daten)
        anzeige = " ".join(str(name or "").split())[:120] or f"Eingefügtes Bild{endung}"
        g.anhaenge.append({"art": "bild", "name": anzeige, "info": f"Bild, {len(daten) // 1024} kB", "datei": datei, "mime": self.BILD_ARTEN[endung], "zeit": _jetzt()})
        g.geaendert = _jetzt()
        self.speichern(g)
        return g

    def bilder_fuer_modell(self, g: Gespraech) -> list[dict]:
        import base64
        out = []
        for a in g.anhaenge:
            if a.get("art") != "bild":
                continue
            p = self.ordner / f"{g.kennung}-bilder" / str(a.get("datei", ""))
            try:
                out.append({"type": "image_url", "image_url": {"url": f"data:{a.get('mime', 'image/png')};base64," + base64.b64encode(p.read_bytes()).decode("ascii")}})
            except OSError:
                continue
        return out

    @_gesperrt
    def ordner_setzen(self, kennung: str, pfad: str) -> Gespraech:
        g = self.laden(kennung)
        g.ordner = str(pfad or "")[:1000]
        g.geaendert = _jetzt()
        self.speichern(g)
        return g

    @_gesperrt
    def skill_setzen(self, kennung: str, name: str) -> Gespraech:
        g = self.laden(kennung)
        g.skill = (name or "")[:64]
        self.speichern(g)
        return g

    @_gesperrt
    def importieren(self, eintraege: list, *, projekt: str = "") -> list[Gespraech]:
        out = []
        for e in eintraege:
            if not getattr(e, "nachrichten", None):
                continue
            g = self.neu()
            g.titel = (e.titel or "Importiertes Gespräch")[:80]
            g.erstellt = e.erstellt or g.erstellt
            g.herkunft = e.herkunft
            g.projekt = (projekt or f"Import {e.herkunft}")[:MAX_PROJEKT]
            for n in e.nachrichten[:MAX_NACHRICHTEN]:
                text = str(n.get("text", "")).strip()[:MAX_NACHRICHT]
                if n.get("rolle") in ("user", "assistant") and text:
                    g.nachrichten.append({"rolle": n["rolle"], "text": text, "zeit": g.erstellt})
            if g.nachrichten:
                self.speichern(g)
                out.append(g)
            else:
                self._pfad(g.kennung).unlink(missing_ok=True)
        return out

    @_gesperrt
    def farbe_setzen(self, kennung: str, farbe: str) -> Gespraech:
        g = self.laden(kennung)
        g.farbe = farbe if farbe in FARBEN else ""
        g.geaendert = _jetzt()
        self.speichern(g)
        return g


    def projekt_farben(self) -> dict:
        d = sicher_schreiben.json_laden(self.ordner / PROJEKT_FARBEN, {}, art=dict)
        return {" ".join(str(k).split())[:MAX_PROJEKT]: (v if v in FARBEN else "") for k, v in d.items() if str(k).strip()}

    @_gesperrt
    def _projekte_schreiben(self, d: dict) -> dict:
        app_core.ensure_plain_directory(self.ordner)
        sicher_schreiben.json_datei(self.ordner / PROJEKT_FARBEN, d)
        return d

    @staticmethod
    def _projektname(projekt: str) -> str:
        p = " ".join((projekt or "").split())
        if not p:
            raise app_core.AppError("GESPRAECH_PROJEKT", "das Projekt braucht einen Namen")
        if len(p) > MAX_PROJEKT:
            raise app_core.AppError("GESPRAECH_PROJEKT", f"der Projektname ist zu lang (höchstens {MAX_PROJEKT} Zeichen)")
        return p

    @_gesperrt
    def projekt_anlegen(self, projekt: str) -> dict:
        d = self.projekt_farben()
        d.setdefault(self._projektname(projekt), "")
        return self._projekte_schreiben(d)

    @_gesperrt
    def projekt_farbe_setzen(self, projekt: str, farbe: str) -> dict:
        d = self.projekt_farben()
        d[self._projektname(projekt)] = farbe if farbe in FARBEN else ""
        return self._projekte_schreiben(d)

    @_gesperrt
    def projekt_umbenennen(self, alt: str, neu: str) -> dict:
        alt, neu = " ".join((alt or "").split()), self._projektname(neu)
        for e in self.liste():
            if e["projekt"] == alt:
                self.verschieben(e["kennung"], neu)
        d = self.projekt_farben()
        d[neu] = d.pop(alt, "") or d.get(neu, "")
        return self._projekte_schreiben(d)

    @_gesperrt
    def projekt_entfernen(self, projekt: str) -> dict:
        d = self.projekt_farben()
        d.pop(" ".join((projekt or "").split()), None)
        return self._projekte_schreiben(d)

    @_gesperrt
    def anheften(self, kennung: str, an: bool = True) -> Gespraech:
        g = self.laden(kennung)
        g.angeheftet = bool(an)
        self.speichern(g)
        return g

    def exportieren(self, kennung: str, ziel_ordner: Path) -> Path:
        g = self.laden(kennung)
        app_core.ensure_plain_directory(Path(ziel_ordner))
        name = "".join(c if c.isalnum() or c in " -_" else "_" for c in g.titel).strip()[:60] or "gespraech"
        pfad = Path(ziel_ordner) / f"{name} ({g.kennung}).md"
        sicher_schreiben.text(pfad, g.als_markdown())
        return pfad

    @_gesperrt
    def archivieren(self, kennung: str, an: bool = True) -> Gespraech:
        g = self.laden(kennung)
        g.archiviert = bool(an)
        self.speichern(g)
        return g

    @_gesperrt
    def umbenennen(self, kennung: str, titel: str) -> Gespraech:
        titel = " ".join((titel or "").split())
        if not titel:
            raise app_core.AppError("GESPRAECH_TITEL", "der Name darf nicht leer sein")
        if len(titel) > 80:
            raise app_core.AppError("GESPRAECH_TITEL", "der Name ist zu lang (höchstens 80 Zeichen)")
        g = self.laden(kennung)
        g.titel = titel
        self.speichern(g)
        return g

    @_gesperrt
    def bewerten(self, kennung: str, nummer: int, wert: str, *, grund: str = "", vorschlag: str = "") -> str:
        if wert not in ("gut", "schlecht", ""):
            raise app_core.AppError("GESPRAECH_BEWERTUNG", "unbekannte Bewertung")
        g = self.laden(kennung)
        if not 0 <= nummer < len(g.nachrichten) or g.nachrichten[nummer].get("rolle") != "assistant":
            raise app_core.AppError("GESPRAECH_BEWERTUNG", "diese Antwort gibt es nicht")
        n = g.nachrichten[nummer]
        if wert:
            n["bewertung"] = wert
        else:
            n.pop("bewertung", None)
        if wert == "schlecht" and (grund or vorschlag):
            n["rueckmeldung"] = {"grund": " ".join(grund.split())[:600], "vorschlag": " ".join(vorschlag.split())[:600]}
        elif wert != "schlecht":
            n.pop("rueckmeldung", None)
        self.speichern(g)
        return wert

    @_gesperrt
    def loeschen(self, kennung: str) -> str:
        pfad = self._pfad(kennung)
        g = self.laden(kennung)
        korb = app_core.ensure_plain_directory(self.ordner / PAPIERKORB)
        bilder = self.ordner / f"{kennung}-bilder"
        if bilder.is_dir():
            shutil.move(str(bilder), str(korb / bilder.name))
        ziel = korb / pfad.name
        try:
            os.replace(pfad, ziel)
        except OSError as exc:
            raise app_core.AppError("GESPRAECH_LOESCHEN", f"konnte nicht verschoben werden: {exc.strerror}") from None
        return g.titel

    @_gesperrt
    def anhaengen(self, g: Gespraech, rolle: str, text: str, *, lieferschein: dict | None = None, intern: bool = False) -> Gespraech:
        if rolle not in ("user", "assistant"):
            raise app_core.AppError("GESPRAECH_ROLLE", "unbekannte Rolle")
        text = (text or "").strip()
        if not text:
            raise app_core.AppError("GESPRAECH_LEER", "leere Nachricht")
        if len(text) > MAX_NACHRICHT:
            raise app_core.AppError("GESPRAECH_LANG", f"Nachricht länger als {MAX_NACHRICHT} Zeichen")
        if len(g.nachrichten) >= MAX_NACHRICHTEN:
            raise app_core.AppError("GESPRAECH_VOLL", "dieses Gespräch ist voll, bitte ein neues beginnen")
        eintrag = {"rolle": rolle, "text": text, "zeit": _jetzt()}
        if rolle == "assistant":
            lieferschein = dict(lieferschein or {})
            lieferschein.setdefault("ki_erzeugt", True)
            lieferschein["etikett"] = _etikett_fuer(text, lieferschein.get("etikett"))
        if lieferschein:
            eintrag["lieferschein"] = lieferschein
        if intern:
            eintrag["intern"] = True
        try:
            frisch = self.laden(g.kennung)
        except app_core.AppError as exc:
            if exc.code != "GESPRAECH_FEHLT":
                raise
            frisch = g
        if frisch is not g:
            if len(frisch.nachrichten) >= MAX_NACHRICHTEN:
                raise app_core.AppError("GESPRAECH_VOLL", "dieses Gespräch ist voll, bitte ein neues beginnen")
            for f in fields(Gespraech):
                setattr(g, f.name, getattr(frisch, f.name))
        g.nachrichten.append(eintrag)
        if rolle == "user" and g.titel == "Neues Gespräch":
            g.titel = (text[:TITEL_LAENGE] + "…") if len(text) > TITEL_LAENGE else text
        g.geaendert = _jetzt()
        self.speichern(g)
        return g


__all__ = ["Gespraech", "Gespraechsablage"]
