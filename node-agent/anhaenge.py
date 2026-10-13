# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import app_core
import wissen

MAX_DATEI = 25 * 1024 * 1024
MAX_TEXT = 60_000
MAX_SEITEN = 200
MAX_ANHAENGE = 5
ENDUNGEN = (".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".csv")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class Anhang:
    name: str
    text: str
    info: str
    gekuerzt: bool

    def kurz(self) -> dict:
        return {"name": self.name, "info": self.info, "zeichen": len(self.text), "gekuerzt": self.gekuerzt}


def _pdf(p: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise app_core.AppError("ANHANG_PDF", "PDF-Lesen ist in diesem Programm nicht eingebaut") from None
    try:
        r = PdfReader(str(p))
        if r.is_encrypted:
            try:
                r.decrypt("")
            except Exception:
                raise app_core.AppError("ANHANG_PDF", "dieses PDF ist mit einem Passwort geschützt") from None
        seiten = r.pages[:MAX_SEITEN]
        teile = []
        for i, s in enumerate(seiten, 1):
            t = (s.extract_text() or "").strip()
            if t:
                teile.append(f"[Seite {i}]\n{t}")
        text = "\n\n".join(teile)
        n = len(r.pages)
    except app_core.AppError:
        raise
    except Exception as exc:
        raise app_core.AppError("ANHANG_PDF", f"das PDF ließ sich nicht lesen ({type(exc).__name__})") from None
    if len(text) < 20:
        raise app_core.AppError("ANHANG_LEER", "in diesem PDF steht kein lesbarer Text (vermutlich ein Scan); das Lesen von Scans kommt später")
    return text, f"{n} Seite{'n' if n != 1 else ''}" + (f", nur die ersten {MAX_SEITEN} gelesen" if n > MAX_SEITEN else "")


def _docx(p: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        raise app_core.AppError("ANHANG_WORD", "das ist keine lesbare Word-Datei (.docx)") from None
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        raise app_core.AppError("ANHANG_WORD", "die Word-Datei ist beschädigt") from None
    absaetze = []
    for para in root.iter(_W + "p"):
        t = "".join(x.text or "" for x in para.iter(_W + "t"))
        if t.strip():
            absaetze.append(t.strip())
    text = "\n\n".join(absaetze)
    if len(text) < 20:
        raise app_core.AppError("ANHANG_LEER", "in dieser Word-Datei steht fast kein Text")
    return text, f"{len(text.split())} Wörter"


def _text(p: Path) -> tuple[str, str]:
    roh = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in (".html", ".htm"):
        _, text = wissen.html_zu_text(roh)
    else:
        text = roh
    text = text.strip()
    if len(text) < 20:
        raise app_core.AppError("ANHANG_LEER", "in dieser Datei steht fast kein Text")
    return text, f"{len(text.split())} Wörter"


def lesen(pfad: Path) -> Anhang:
    p = Path(pfad)
    if app_core._is_reparse(p) or not p.is_file():
        raise app_core.AppError("ANHANG_DATEI", "das ist keine gewöhnliche Datei")
    if p.suffix.lower() not in ENDUNGEN:
        raise app_core.AppError("ANHANG_ART", "diese Dateiart kann das Programm noch nicht lesen (geht: PDF, Word .docx, Text, Markdown, HTML, CSV)")
    if p.stat().st_size > MAX_DATEI:
        raise app_core.AppError("ANHANG_GROSS", "die Datei ist größer als 25 MB")
    if p.suffix.lower() == ".pdf":
        text, info = _pdf(p)
    elif p.suffix.lower() == ".docx":
        text, info = _docx(p)
    else:
        text, info = _text(p)
    text = re.sub(r"[ \t]+\n", "\n", text)
    gekuerzt = len(text) > MAX_TEXT
    return Anhang(p.name[:120], text[:MAX_TEXT], info, gekuerzt)


def vorspann(anhaenge: list[dict], *, hoechstens: int = 24_000) -> str:
    if not anhaenge:
        return ""
    teile = []
    rest = hoechstens
    texte = [a for a in anhaenge if a.get("art") != "bild"]
    if not texte:
        return ""
    for a in texte[-MAX_ANHAENGE:]:
        t = str(a.get("text", ""))[:max(rest, 0)]
        rest -= len(t)
        teile.append(f"Datei „{a.get('name', '')}“ ({a.get('info', '')}):\n{t}" + ("\n[… gekürzt]" if len(t) < len(str(a.get('text', ''))) else ""))
        if rest <= 0:
            break
    return ("Die Person hat Dateien zum Gespräch gegeben. Beziehe dich auf ihren Inhalt, wenn die Frage dazu passt, "
            "zitiere Stellen daraus mit „laut Datei …“, und erfinde nichts, was nicht in der Datei steht.\n\n" + "\n\n".join(teile))


__all__ = ["Anhang", "lesen", "vorspann", "ENDUNGEN", "MAX_ANHAENGE"]
