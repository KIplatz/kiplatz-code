# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anhaenge
import app_core

X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xlsx(pfad: Path, blatt: str, *, styles: bool = True) -> Path:
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", f'<?xml version="1.0"?><workbook xmlns="{X}" xmlns:r="{R}"><sheets><sheet name="Ausgaben" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0"?><sst xmlns="{X}"><si><t>Monat</t></si><si><t>Betrag</t></si><si><t>Strom</t></si></sst>')
        if styles:
            z.writestr("xl/styles.xml", f'<?xml version="1.0"?><styleSheet xmlns="{X}"><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml", f'<?xml version="1.0"?><worksheet xmlns="{X}"><sheetData>{blatt}</sheetData></worksheet>')
    return pfad


BLATT = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
         '<row r="2"><c r="A2" s="1"><v>45930</v></c><c r="C2" t="s"><v>2</v></c><c r="D2"><v>84.5</v></c></row>')


def test_excel_wird_text_wie_in_der_app(tmp_path):
    a = anhaenge.lesen(_xlsx(tmp_path / "ausgaben.xlsx", BLATT))
    assert a.text == "[Tabelle „Ausgaben“, 2 Zeilen]\nMonat | Betrag\n30.09.2025 |  | Strom | 84.5"
    assert a.info == "1 Tabelle, 2 Zeilen" and ".xlsx" in anhaenge.ENDUNGEN


def test_ohne_formate_bleibt_die_zahl_und_kaputtes_wird_ein_satz(tmp_path):
    a = anhaenge.lesen(_xlsx(tmp_path / "ohne.xlsx", BLATT, styles=False))
    assert "45930 |  | Strom" in a.text
    kaputt = tmp_path / "kaputt.xlsx"
    kaputt.write_bytes(b"keine Tabelle")
    with pytest.raises(app_core.AppError) as e:
        anhaenge.lesen(kaputt)
    assert e.value.code == "ANHANG_EXCEL"
    with pytest.raises(app_core.AppError) as e:
        anhaenge.lesen(_xlsx(tmp_path / "leer.xlsx", ""))
    assert e.value.code == "ANHANG_LEER"


def test_zip_bombe_wird_nach_60_mb_abgebrochen(tmp_path, monkeypatch):
    monkeypatch.setattr(anhaenge, "MAX_ENTPACKT", 1000)
    p = tmp_path / "bombe.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w/>" + " " * 5000)
    with pytest.raises(app_core.AppError) as e:
        anhaenge.lesen(p)
    assert e.value.code == "ANHANG_GROSS"
    with pytest.raises(app_core.AppError) as e:
        anhaenge.lesen(_xlsx(tmp_path / "gross.xlsx", BLATT * 50))
    assert e.value.code == "ANHANG_GROSS"


def test_fable_befunde_spalten_ziffern_offene_datei(tmp_path):
    blatt = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="ZZZZZZZZZZ1"><v>9</v></c><c r="B1" t="s"><v>²</v></c></row>'
    p = _xlsx(tmp_path / "boese.xlsx", blatt)
    a = anhaenge.lesen(p)
    assert a.text == "[Tabelle „Ausgaben“, 1 Zeilen]\nMonat | ²"
    p.unlink()
