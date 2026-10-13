# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import app_core
import hausordnung
import sicher_schreiben

DIRNAME = "skills"
VORLAGEN_DIR = Path(__file__).resolve().parent / "skills_vorlagen"
DIRNAME_ALT = "bausteine"
DATEI = "SKILL.md"
MAX_TEXT = 20_000
MAX_ZIP = 2 * 1024 * 1024
MAX_SKILLS = 200
IMMER_DATEI = "immer.json"
MEINE_KI = "meine-ki"
MIT_FRAGE_MAX = 12_000
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class Skill:
    name: str
    beschreibung: str
    text: str
    quelle: str = ""

    def kurz(self) -> dict:
        return {"name": self.name, "beschreibung": self.beschreibung, "zeichen": len(self.text), "quelle": self.quelle}

    def als_skill_md(self) -> str:
        return f"---\nname: {self.name}\ndescription: {self.beschreibung}\n---\n\n{self.text.rstrip()}\n"


def lesen(text: str, *, quelle: str = "") -> Skill:
    text = (text or "").replace("\r\n", "\n")
    if len(text) > MAX_TEXT:
        raise app_core.AppError("SKILL_GROSS", f"ein Skill darf höchstens {MAX_TEXT // 1000} Tsd. Zeichen haben")
    name, beschreibung, body = "", "", text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if m:
        for zeile in m.group(1).split("\n"):
            k, _, v = zeile.partition(":")
            k, v = k.strip().lower(), v.strip().strip("\"'")
            if k == "name":
                name = v
            elif k == "description":
                beschreibung = v
        body = m.group(2)
    if not name:
        h = re.search(r"^#\s+(.+)$", body, re.M)
        name = h.group(1).strip() if h else ""
    name = name_bereinigen(name)
    if not name:
        raise app_core.AppError("SKILL_NAME", "der Skill braucht einen Namen (Zeile „name:“ oder eine Überschrift)")
    if not beschreibung:
        erste = next((z.strip() for z in body.split("\n") if z.strip() and not z.startswith("#")), "")
        beschreibung = erste[:160]
    body = body.strip()
    if len(body) < 20:
        raise app_core.AppError("SKILL_LEER", "der Skill enthält fast keine Anweisungen")
    b = hausordnung.pruefen(name + "\n" + beschreibung + "\n" + body)
    if not b.ok:
        raise app_core.AppError("HAUSORDNUNG", b.text)
    return Skill(name, beschreibung[:200], body, quelle)


def name_bereinigen(name: str) -> str:
    n = (name or "").lower().strip()
    n = n.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")[:64]
    return n if _NAME.match(n) else ""


class Skillkiste:

    def __init__(self, base_dir: Path) -> None:
        self.ordner = Path(base_dir) / DIRNAME
        alt = Path(base_dir) / DIRNAME_ALT
        if alt.is_dir() and not self.ordner.exists() and not app_core._is_reparse(alt):
            try:
                alt.rename(self.ordner)
            except OSError:
                pass

    def _pfad(self, name: str) -> Path:
        n = name_bereinigen(name)
        if not n:
            raise app_core.AppError("SKILL_NAME", "ungültiger Skill-Name")
        return self.ordner / n / DATEI

    def liste(self) -> list[dict]:
        if not self.ordner.is_dir():
            return []
        out = []
        immer = set(self._immer_roh())
        for p in sorted(self.ordner.glob(f"*/{DATEI}")):
            try:
                out.append({**self.laden(p.parent.name).kurz(), "immer": p.parent.name in immer})
            except app_core.AppError:
                continue
        return out


    def _immer_roh(self) -> list[str]:
        try:
            d = json.loads((self.ordner / IMMER_DATEI).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [n for n in (d if isinstance(d, list) else []) if isinstance(n, str) and _NAME.match(n)][:MAX_SKILLS]

    def immer(self) -> list[str]:
        return [n for n in self._immer_roh() if (self.ordner / n / DATEI).is_file()]

    def immer_setzen(self, name: str, an: bool) -> list[str]:
        n = name_bereinigen(name)
        if not n or not (self.ordner / n / DATEI).is_file():
            raise app_core.AppError("SKILL_FEHLT", "diesen Skill gibt es nicht")
        jetzt = [x for x in self.immer() if x != n] + ([n] if an else [])
        app_core.ensure_plain_directory(self.ordner)
        sicher_schreiben.json_datei(self.ordner / IMMER_DATEI, jetzt, indent=None)
        return jetzt

    def fuer_gespraech(self, gewaehlt: str = "") -> list[Skill]:
        aus: list[Skill] = []
        immer = self.immer()
        immer = [n for n in immer if n == MEINE_KI] + [n for n in immer if n != MEINE_KI]
        for n in ([gewaehlt] if gewaehlt else []) + immer:
            if any(b.name == name_bereinigen(n) for b in aus):
                continue
            try:
                aus.append(self.laden(n))
            except app_core.AppError:
                continue
        return aus

    def laden(self, name: str) -> Skill:
        p = self._pfad(name)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise app_core.AppError("SKILL_FEHLT", "diesen Skill gibt es nicht") from None
        except OSError:
            raise app_core.AppError("SKILL_DATEI", "der Skill ist unlesbar") from None
        quelle = ""
        try:
            quelle = json.loads((p.parent / "herkunft.json").read_text(encoding="utf-8")).get("quelle", "")
        except (OSError, ValueError, AttributeError):
            pass
        return lesen(text, quelle=quelle)

    def speichern(self, b: Skill) -> Skill:
        if len(self.liste()) >= MAX_SKILLS and not self._pfad(b.name).exists():
            raise app_core.AppError("SKILL_VIELE", f"mehr als {MAX_SKILLS} Skills passen nicht in die Kiste")
        p = self._pfad(b.name)
        app_core.ensure_plain_directory(p.parent)
        sicher_schreiben.text(p, b.als_skill_md())
        sicher_schreiben.json_datei(p.parent / "herkunft.json", {"quelle": b.quelle}, indent=None)
        return b

    def entfernen(self, name: str) -> bool:
        p = self._pfad(name).parent
        if not p.is_dir():
            return False
        shutil.rmtree(p, ignore_errors=True)
        if p.name in self._immer_roh():
            sicher_schreiben.json_datei(self.ordner / IMMER_DATEI, [x for x in self._immer_roh() if x != p.name], indent=None)
        return True


    def exportieren(self, name: str, ziel_ordner: Path) -> Path:
        b = self.laden(name)
        app_core.ensure_plain_directory(Path(ziel_ordner))
        ziel = Path(ziel_ordner) / f"{b.name}.zip"
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{b.name}/{DATEI}", b.als_skill_md())
        return ziel

    def importieren(self, daten: bytes | Path) -> list[Skill]:
        if isinstance(daten, Path):
            if daten.suffix.lower() == ".md":
                return [self.speichern(lesen(daten.read_text(encoding="utf-8", errors="replace"), quelle="importiert"))]
            daten = daten.read_bytes()
        if len(daten) > MAX_ZIP:
            raise app_core.AppError("SKILL_GROSS", "die Datei ist größer als 2 MB")
        try:
            z = zipfile.ZipFile(io.BytesIO(daten))
        except zipfile.BadZipFile:
            raise app_core.AppError("SKILL_DATEI", "das ist keine ZIP-Datei und keine SKILL.md") from None
        out: list[Skill] = []
        for info in z.infolist():
            n = info.filename.replace("\\", "/")
            if ".." in n.split("/") or n.startswith("/") or ":" in n:
                raise app_core.AppError("SKILL_DATEI", "die ZIP-Datei enthält einen unzulässigen Pfad; verworfen")
            if n.split("/")[-1] != DATEI or info.file_size > MAX_TEXT * 4:
                continue
            text = z.read(info).decode("utf-8", "replace")
            out.append(self.speichern(lesen(text, quelle="importiert")))
        if not out:
            raise app_core.AppError("SKILL_LEER", "in der ZIP-Datei war keine SKILL.md")
        return out


def vorlagen() -> list[Skill]:
    aus: list[Skill] = []
    try:
        for p in sorted(VORLAGEN_DIR.glob("*.md")):
            try:
                aus.append(lesen(p.read_text(encoding="utf-8"), quelle="vorlage"))
            except (OSError, app_core.AppError):
                continue
    except OSError:
        return []
    return aus


def vorspann(b: Skill) -> str:
    return (f"Für dieses Gespräch gilt der Skill „{b.name}“ ({b.beschreibung}). Halte dich an seine Anweisungen, "
            f"soweit sie zur Frage passen; die Regeln oben (nichts erfinden, nachfragen statt raten) gelten weiter.\n\n"
            f"Skill:\n{b.text}")


def passend(liste: list[Skill], max_zeichen: int = MIT_FRAGE_MAX, *, erster_immer: bool = True) -> tuple[list[Skill], list[str]]:
    mit: list[Skill] = []
    weg: list[str] = []
    for b in liste:
        probe = mit + [b]
        if (not mit and erster_immer) or len(als_eine(probe).als_skill_md()) <= max_zeichen:
            mit = probe
        else:
            weg.append(b.name)
    return mit, weg


def als_eine(liste: list[Skill]) -> Skill:
    if len(liste) == 1:
        return liste[0]
    name = name_bereinigen("-und-".join(b.name for b in liste)) or "mehrere-skills"
    text = "\n\n".join(f"# Skill „{b.name}“ ({b.beschreibung})\n\n{b.text.strip()}" for b in liste)
    return Skill(name, ("Mehrere Skills zusammen: " + ", ".join(b.name for b in liste))[:200], text, "zusammen")


def vorspann_mehrere(liste: list[Skill]) -> str:
    if len(liste) == 1:
        return vorspann(liste[0])
    return ("Für dieses Gespräch gelten die folgenden Skills. Halte dich an ihre Anweisungen, soweit sie zur Frage passen; "
            "die Regeln oben (nichts erfinden, nachfragen statt raten) gelten weiter.\n\n"
            + "\n\n".join(f"Skill „{b.name}“ ({b.beschreibung}):\n{b.text}" for b in liste))


def hinweis_angewendet(liste: list[Skill], weggelassen: list[str] = ()) -> str:
    if not liste:
        s = ""
    elif len(liste) == 1:
        s = f"Skill „{liste[0].name}“ angewendet."
    else:
        s = "Skills " + ", ".join(f"„{b.name}“" for b in liste) + " angewendet."
    if weggelassen:
        s += (" " if s else "") + ("Nicht mehr dazu gepasst (zu viel Text auf einmal): " + ", ".join(f"„{n}“" for n in weggelassen) + ".")
    return s


__all__ = ["Skill", "Skillkiste", "lesen", "name_bereinigen", "vorspann", "vorspann_mehrere", "passend", "als_eine", "hinweis_angewendet",
           "DIRNAME", "DIRNAME_ALT", "DATEI", "MIT_FRAGE_MAX"]
