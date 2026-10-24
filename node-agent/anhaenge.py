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
ENDUNGEN = (".pdf", ".docx", ".xlsx", ".txt", ".md", ".html", ".htm", ".csv")
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


MAX_ENTPACKT = 60 * 1024 * 1024


def _zip_lesen(z: zipfile.ZipFile, name: str) -> bytes:
    with z.open(name) as f:
        daten = f.read(MAX_ENTPACKT + 1)
    if len(daten) > MAX_ENTPACKT:
        raise app_core.AppError("ANHANG_GROSS", "die Datei ist ausgepackt größer als 60 MB")
    return daten


def _docx(p: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(p) as z:
            xml = _zip_lesen(z, "word/document.xml")
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


_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
XLSX_TABELLEN = 10
XLSX_ZEILEN = 3000
_DATUM_FORMATE = set(range(14, 23)) | {45, 46, 47}


XLSX_SPALTEN = 200


def _spalte(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]{0,4}", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return max(n - 1, 0) if n <= XLSX_SPALTEN else -1


def _xlsx(p: Path) -> tuple[str, str]:
    from datetime import date, timedelta
    try:
        z = zipfile.ZipFile(p)
    except (zipfile.BadZipFile, OSError):
        raise app_core.AppError("ANHANG_EXCEL", "das ist keine lesbare Excel-Datei (.xlsx)") from None
    with z:
        try:
            mappe = ElementTree.fromstring(_zip_lesen(z, "xl/workbook.xml"))
            bezuege = ElementTree.fromstring(_zip_lesen(z, "xl/_rels/workbook.xml.rels"))
        except (zipfile.BadZipFile, KeyError, OSError, ElementTree.ParseError):
            raise app_core.AppError("ANHANG_EXCEL", "das ist keine lesbare Excel-Datei (.xlsx)") from None
        ziele = {b.get("Id"): b.get("Target", "") for b in bezuege.iter(_PR + "Relationship")}
        try:
            texte = ["".join(t.text or "" for t in si.iter(_X + "t")) for si in ElementTree.fromstring(_zip_lesen(z, "xl/sharedStrings.xml")).iter(_X + "si")]
        except (KeyError, ElementTree.ParseError):
            texte = []
        datum_stil: set[int] = set()
        try:
            stile = ElementTree.fromstring(_zip_lesen(z, "xl/styles.xml"))
            eigene = {int(f.get("numFmtId", "0")) for f in stile.iter(_X + "numFmt")
                      if re.search(r"[dy]", re.sub(r'"[^"]*"|\[[^\]]*\]', "", f.get("formatCode", "")), re.I)}
            xfs = stile.find(_X + "cellXfs")
            for i, xf in enumerate(xfs if xfs is not None else []):
                fid = int(xf.get("numFmtId", "0"))
                if fid in _DATUM_FORMATE or fid in eigene:
                    datum_stil.add(i)
        except (KeyError, ElementTree.ParseError, ValueError):
            pass
        teile, zeilen_gesamt = [], 0
        blaetter = list(mappe.iter(_X + "sheet"))
        for blatt in blaetter[:XLSX_TABELLEN]:
            ziel = ziele.get(blatt.get(_R + "id"), "")
            pfad = ziel.lstrip("/") if ziel.startswith("/") else "xl/" + ziel
            try:
                daten = ElementTree.fromstring(_zip_lesen(z, pfad))
            except (KeyError, ElementTree.ParseError):
                continue
            zeilen = []
            for row in daten.iter(_X + "row"):
                werte: dict[int, str] = {}
                for c in row.iter(_X + "c"):
                    art, v = c.get("t", ""), c.find(_X + "v")
                    if art == "s" and v is not None and re.fullmatch(r"[0-9]{1,9}", v.text or "") and int(v.text) < len(texte):
                        w = texte[int(v.text)]
                    elif art == "inlineStr":
                        w = "".join(t.text or "" for t in c.iter(_X + "t"))
                    elif art == "b" and v is not None:
                        w = "WAHR" if v.text == "1" else "FALSCH"
                    elif v is not None and v.text is not None:
                        w = v.text
                        try:
                            if int(c.get("s", "-1")) in datum_stil and art in ("", "n"):
                                w = (date(1899, 12, 30) + timedelta(days=float(w))).strftime("%d.%m.%Y")
                            elif re.fullmatch(r"-?\d+\.\d{6,}", w):
                                w = f"{float(w):.6g}"
                        except (ValueError, OverflowError):
                            pass
                    else:
                        w = ""
                    spalte = _spalte(c.get("r", ""))
                    if spalte >= 0:
                        werte[spalte] = " ".join(str(w).split())
                if any(werte.values()):
                    zeilen.append(" | ".join(werte.get(i, "") for i in range(max(werte) + 1)).rstrip(" |"))
                if len(zeilen) >= XLSX_ZEILEN:
                    break
            zeilen_gesamt += len(zeilen)
            if zeilen:
                teile.append(f"[Tabelle „{blatt.get('name', '')}“, {len(zeilen)} Zeilen]\n" + "\n".join(zeilen))
    text = "\n\n".join(teile)
    if len(text) < 5:
        raise app_core.AppError("ANHANG_LEER", "in dieser Excel-Datei steht nichts")
    return text, (f"1 Tabelle, {zeilen_gesamt} Zeilen" if len(teile) == 1 else f"{len(teile)} Tabellen, {zeilen_gesamt} Zeilen")


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
        raise app_core.AppError("ANHANG_ART", "diese Dateiart kann das Programm noch nicht lesen (geht: PDF, Word .docx, Excel .xlsx, Text, Markdown, HTML, CSV)")
    if p.stat().st_size > MAX_DATEI:
        raise app_core.AppError("ANHANG_GROSS", "die Datei ist größer als 25 MB")
    if p.suffix.lower() == ".pdf":
        text, info = _pdf(p)
    elif p.suffix.lower() == ".docx":
        text, info = _docx(p)
    elif p.suffix.lower() == ".xlsx":
        text, info = _xlsx(p)
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
