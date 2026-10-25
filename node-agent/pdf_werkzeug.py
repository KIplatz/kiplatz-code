# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import time
from pathlib import Path

import app_core
import sicher_schreiben

MAX_DATEIEN = 30
MAX_BYTES = 300 * 1024 * 1024
MAX_SEITEN = 5000


def zielname(ordner: Path, jetzt: float | None = None) -> Path:
    stempel = time.strftime("%Y-%m-%d %H%M", time.localtime(jetzt))
    p = ordner / f"Zusammengefügt {stempel}.pdf"
    n = 2
    while p.exists():
        p = ordner / f"Zusammengefügt {stempel} ({n}).pdf"
        n += 1
    return p


def zusammenfuegen(pfade: list[Path], ziel: Path) -> dict:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError

    pfade = sorted((Path(p) for p in pfade), key=lambda p: p.name.lower())
    if len(pfade) < 2:
        raise app_core.AppError("PDF_ZU_WENIG", "Wähle mindestens zwei PDF-Dateien aus.")
    if len(pfade) > MAX_DATEIEN:
        raise app_core.AppError("PDF_ZU_VIELE", f"Höchstens {MAX_DATEIEN} Dateien auf einmal.")
    for p in pfade:
        if p.suffix.lower() != ".pdf":
            raise app_core.AppError("PDF_ART", f"„{p.name}“ ist keine PDF-Datei.")
    if sum(p.stat().st_size for p in pfade) > MAX_BYTES:
        raise app_core.AppError("PDF_GROSS", "Die Dateien sind zusammen größer als 300 MB.")
    schreiber = PdfWriter()
    seiten = 0
    for p in pfade:
        try:
            leser = PdfReader(str(p))
            if leser.is_encrypted and not leser.decrypt(""):
                raise app_core.AppError("PDF_GESCHUETZT", f"„{p.name}“ ist mit einem Kennwort geschützt. Öffne sie, speichere sie ohne Kennwort und versuch es noch einmal.")
            n = len(leser.pages)
            if seiten + n > MAX_SEITEN:
                raise app_core.AppError("PDF_SEITEN", f"Zusammen wären es mehr als {MAX_SEITEN} Seiten.")
            for seite in leser.pages:
                schreiber.add_page(seite)
            seiten += n
        except app_core.AppError:
            raise
        except (PdfReadError, ValueError, KeyError, TypeError, OSError, RecursionError) as e:
            raise app_core.AppError("PDF_KAPUTT", f"„{p.name}“ ließ sich nicht als PDF lesen.") from e
    puffer = io.BytesIO()
    schreiber.write(puffer)
    sicher_schreiben.roh(ziel, puffer.getvalue())
    return {"dateien": len(pfade), "seiten": seiten, "pfad": str(ziel), "reihenfolge": [p.name for p in pfade]}
