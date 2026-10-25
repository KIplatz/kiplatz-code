# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import pdf_werkzeug as pw


def _pdf(pfad: Path, seiten: int, breite: int = 200, kennwort: str = "") -> Path:
    w = PdfWriter()
    for _ in range(seiten):
        w.add_blank_page(width=breite, height=300)
    if kennwort:
        w.encrypt(kennwort)
    with open(pfad, "wb") as f:
        w.write(f)
    return pfad


def test_zusammen_nach_dateinamen(tmp_path):
    b = _pdf(tmp_path / "2 Zeugnis.pdf", 2, breite=222)
    a = _pdf(tmp_path / "1 Anschreiben.pdf", 1, breite=111)
    c = _pdf(tmp_path / "3 Lebenslauf.PDF", 3, breite=333)
    ziel = pw.zielname(tmp_path)
    d = pw.zusammenfuegen([b, c, a], ziel)
    assert d["dateien"] == 3 and d["seiten"] == 6 and d["reihenfolge"] == ["1 Anschreiben.pdf", "2 Zeugnis.pdf", "3 Lebenslauf.PDF"]
    seiten = PdfReader(str(ziel)).pages
    assert [round(float(s.mediabox.width)) for s in seiten] == [111, 222, 222, 333, 333, 333]
    assert ziel.name.startswith("Zusammengefügt ") and pw.zielname(tmp_path) != ziel


def test_grenzen_und_fehler_als_satz(tmp_path):
    a = _pdf(tmp_path / "a.pdf", 1)
    with pytest.raises(app_core.AppError) as e:
        pw.zusammenfuegen([a], tmp_path / "x.pdf")
    assert e.value.code == "PDF_ZU_WENIG"
    txt = tmp_path / "b.txt"
    txt.write_text("kein PDF", encoding="utf-8")
    with pytest.raises(app_core.AppError) as e:
        pw.zusammenfuegen([a, txt], tmp_path / "x.pdf")
    assert e.value.code == "PDF_ART"
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"%PDF-1.4 nichts")
    with pytest.raises(app_core.AppError) as e:
        pw.zusammenfuegen([a, kaputt], tmp_path / "x.pdf")
    assert e.value.code == "PDF_KAPUTT" and "kaputt.pdf" in e.value.detail
    geheim = _pdf(tmp_path / "geheim.pdf", 1, kennwort="geheim")
    with pytest.raises(app_core.AppError) as e:
        pw.zusammenfuegen([a, geheim], tmp_path / "x.pdf")
    assert e.value.code == "PDF_GESCHUETZT"
    assert not (tmp_path / "x.pdf").exists()


def test_zu_viele_seiten(tmp_path, monkeypatch):
    monkeypatch.setattr(pw, "MAX_SEITEN", 3)
    with pytest.raises(app_core.AppError) as e:
        pw.zusammenfuegen([_pdf(tmp_path / "a.pdf", 2), _pdf(tmp_path / "b.pdf", 2)], tmp_path / "x.pdf")
    assert e.value.code == "PDF_SEITEN"


def test_knopf_im_fenster_und_methode(tmp_path, monkeypatch):
    html = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")
    assert 'id="btn-pdf-zusammen"' in html and "api().pdf_zusammenfuegen()" in html
    from test_app_web import _api
    api, _, _ = _api(tmp_path)
    pdfs = [_pdf(tmp_path / "b.pdf", 1), _pdf(tmp_path / "a.pdf", 2)]
    monkeypatch.setattr(api, "_dateien_waehlen", lambda arten: pdfs)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    r = api.pdf_zusammenfuegen()
    assert r["ok"] and r["text"].startswith("2 PDFs mit zusammen 3 Seiten zusammengefügt") and str(tmp_path) in r["text"]
