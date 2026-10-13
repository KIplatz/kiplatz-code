# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anhaenge
import app_core
import gespraeche


def _docx(p: Path, absaetze):
    body = "".join(f"<w:p><w:r><w:t>{a}</w:t></w:r></w:p>" for a in absaetze)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)


def _pdf(p: Path, text: str):
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=300, height=300)
    from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject
    page = w.pages[0]
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = w._add_object(stream)
    with open(p, "wb") as f:
        w.write(f)


def test_files_become_text_and_stay_with_the_conversation(tmp_path):
    d = tmp_path / "brief.docx"; _docx(d, ["Sehr geehrte Frau Muster,", "hiermit kündige ich zum 31.12.2026.", "Mit freundlichen Grüßen"])
    a = anhaenge.lesen(d)
    assert a.name == "brief.docx" and "kündige ich zum 31.12.2026" in a.text and a.info.endswith("Wörter") and not a.gekuerzt
    p = tmp_path / "angebot.pdf"; _pdf(p, "Angebot Nr. 17: 3 Stueck Holz zu je 9,90 Euro.")
    b = anhaenge.lesen(p)
    assert b.info == "1 Seite" and "Angebot Nr. 17" in b.text and b.text.startswith("[Seite 1]")
    t = tmp_path / "notiz.md"; t.write_text("# Notiz\n\nDas Freibad hat von 9 bis 20 Uhr offen, Tageskarte 5 Euro.", encoding="utf-8")
    c = anhaenge.lesen(t)
    assert "Tageskarte 5 Euro" in c.text
    for name, code in (("x.exe", "ANHANG_ART"), ("leer.txt", "ANHANG_LEER")):
        f = tmp_path / name; f.write_bytes(b"MZ" if name.endswith(".exe") else b"x")
        with pytest.raises(app_core.AppError) as e:
            anhaenge.lesen(f)
        assert e.value.code == code
    ab = gespraeche.Gespraechsablage(tmp_path / "ablage")
    g = ab.neu()
    g = ab.anhang_hinzufuegen(g.kennung, a.name, a.text, a.info)
    g = ab.anhang_hinzufuegen(g.kennung, b.name, b.text, b.info)
    assert [x["name"] for x in ab.laden(g.kennung).anhaenge] == ["brief.docx", "angebot.pdf"] and ab.laden(g.kennung).anhaenge[0]["text"] == a.text
    assert "text" not in g.to_json_dict()["anhaenge"][0]
    v = anhaenge.vorspann(ab.laden(g.kennung).anhaenge)
    assert v.startswith("Die Person hat Dateien zum Gespräch gegeben") and "Datei „brief.docx“" in v and "Angebot Nr. 17" in v and "laut Datei" in v
    assert anhaenge.vorspann([{"name": "gross.txt", "info": "", "text": "x" * 50_000}], hoechstens=1000).count("[… gekürzt]") == 1
    for _ in range(3):
        g = ab.anhang_hinzufuegen(g.kennung, "n.txt", "Text " * 10, "10 Wörter")
    with pytest.raises(app_core.AppError) as e2:
        ab.anhang_hinzufuegen(g.kennung, "n.txt", "Text " * 10, "10 Wörter")
    assert e2.value.code == "ANHANG_VIELE"
    assert len(ab.anhang_entfernen(g.kennung, 0).anhaenge) == 4 and ab.laden(g.kennung).anhaenge[0]["name"] == "angebot.pdf"


def test_pictures_are_kept_beside_the_conversation_and_handed_to_the_model(tmp_path):
    import base64
    import modell_katalog
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    bild = tmp_path / "foto.png"; bild.write_bytes(png)
    ab = gespraeche.Gespraechsablage(tmp_path / "ablage")
    g = ab.neu(); ab.anhaengen(g, "user", "Was ist auf dem Bild?")
    g = ab.bild_hinzufuegen(g.kennung, bild)
    a = ab.laden(g.kennung).anhaenge[0]
    assert a["art"] == "bild" and a["name"] == "foto.png" and a["mime"] == "image/png" and (ab.ordner / f"{g.kennung}-bilder" / a["datei"]).is_file()
    teile = ab.bilder_fuer_modell(ab.laden(g.kennung))
    assert len(teile) == 1 and teile[0]["type"] == "image_url" and teile[0]["image_url"]["url"].startswith("data:image/png;base64,iVBORw0KGgo")
    assert anhaenge.vorspann(ab.laden(g.kennung).anhaenge) == ""
    for name, code in (("x.bmp", "BILD_ART"),):
        f = tmp_path / name; f.write_bytes(b"BM")
        with pytest.raises(app_core.AppError) as e:
            ab.bild_hinzufuegen(g.kennung, f)
        assert e.value.code == code
    for _ in range(2):
        g = ab.bild_hinzufuegen(g.kennung, bild)
    with pytest.raises(app_core.AppError) as e2:
        ab.bild_hinzufuegen(g.kennung, bild)
    assert e2.value.code == "BILD_VIELE"
    ordner = ab.ordner / f"{g.kennung}-bilder"
    assert len(list(ordner.iterdir())) == 3
    g = ab.anhang_entfernen(g.kennung, 0)
    assert len(list(ordner.iterdir())) == 2 and len(g.anhaenge) == 2
    ab.loeschen(g.kennung)
    assert not ordner.exists() and (ab.ordner / "papierkorb" / ordner.name).is_dir()
    import ki_laufzeit
    for m in modell_katalog.MODELLE.values():
        assert m.bilder and m.bilder.datei.endswith("-mmproj.gguf") and len(m.bilder.sha256) == 64 and m.bilder.groesse > 800_000_000
    o = ki_laufzeit.KiOrdner(tmp_path / "ki")
    assert not o.bilder_da(modell_katalog.MODELLE["3B"]) and o.bilder_pfad(modell_katalog.MODELLE["3B"]).name == "Ministral-3-3B-Instruct-2512-BF16-mmproj.gguf"
