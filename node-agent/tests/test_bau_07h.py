# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[1]
FENSTER = HIER / "webapp" / "index.html"
NODE = Path(os.environ.get("KIPLATZ_NODE") or shutil.which("node") or str(Path.home() / "Werkzeuge" / "node-v24.21.0-win-x64" / "node.exe"))


def _html() -> str:
    return FENSTER.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_meldungszeile_steht_unter_der_seite_und_nicht_daneben():
    html = _html()
    assert re.search(r'<div class="statusline" id="meldung"[^>]*></div>\s*</main>', html)
    zwischen = html.split('<div class="seitenbereich">', 1)[1].split('<div class="statusline" id="meldung"', 1)[0]
    assert zwischen.count("<div") + 1 == zwischen.count("</div>"), "der Seitenbereich muss vor der Meldungszeile zu sein"
    assert ".statusline:empty { min-height: 0; padding: 0; border: 0; }" in html


def test_rueckmeldung_geht_von_selbst_und_website_lesen_meldet_unter_dem_feld():
    html = _html()
    sag = html.split("function sag(text, bleibt) {", 1)[1].split("\n  }\n", 1)[0]
    assert "setTimeout" in sag and "12000" in sag and 'endsWith("…")' in sag and "!bleibt" in sag
    knopf = html.split('$("#btn-wissen-seite").addEventListener("click"', 1)[1].split("\n  });\n", 1)[0]
    assert "sag(" not in knopf and '$("#wissen-seite-hinweis")' in knopf
    assert "Gelesen wird genau diese eine Seite" in html
    assert 'sag(`Gemerkt: ${w.neu.titel}`)' not in html


def _hilfen() -> str:
    html = _html()
    start = html.index("  const PRUEF_VERDACHT = {")
    ende = html.index("    return null;\n  }", start) + len("    return null;\n  }")
    return html[start:ende]


@pytest.mark.skipif(not (NODE.is_file() or shutil.which("node")), reason="Node fehlt")
def test_meldungen_in_ganzen_saetzen(tmp_path):
    probe = tmp_path / "probe.cjs"
    faelle = [
        "zurückgehalten (Prüfer-Modell): (5) „Geschenk Gottes mit Zahnspange“ …",
        'zurückgehalten (Prüfer-Modell): 1) *"dunkle Jahre unter dem NS-Regime" …',
        "zurückgehalten (Prüfer-Modell): 5 Millionen Menschen",
        "entfernt (Wortfilter): Pornographie",
        "Die Öffnungszeiten stimmen nicht mehr",
    ]
    probe.write_text(
        _hilfen() + "\nconst fs = require('fs');\n"
        + "const faelle = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
        + "const t = 'Das Haus.\\nIn den dunklen Jahren unter dem NS-Regime\\ndiente es. Ein „Geschenk Gottes mit Zahnspange“, sagt er.';\n"
        + "const f = (s) => { const x = stelleFinden(t, s); return x && t.slice(x[0], x[0] + x[1]); };\n"
        + "console.log(JSON.stringify({ g: faelle.map(meldungGrund), wer: ['Prüfer abc', 'admin', 'x1'].map(meldungWer),"
        + " f: [f('dunkle Jahre unter dem NS-Regime'), f('Geschenk Gottes mit Zahnspange'), f('gibt es hier nicht'), stelleFinden('Ungeschenk', 'Geschenk Gottes')] }));\n",
        encoding="utf-8")
    daten = tmp_path / "faelle.json"
    daten.write_text(json.dumps(faelle, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([str(NODE if NODE.is_file() else shutil.which("node")), str(probe), str(daten)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    e = json.loads(r.stdout)
    g = e["g"]
    assert g[0]["art"] == "zurueck" and "Herkunft, Religion" in g[0]["satz"] and g[0]["stelle"] == "Geschenk Gottes mit Zahnspange"
    assert "Nationalsozialismus" in g[1]["satz"] and g[1]["stelle"] == "dunkle Jahre unter dem NS-Regime"
    assert "Bis du entscheidest, sieht sie niemand." in g[1]["satz"]
    assert "Verstoß gegen die Platzordnung" in g[2]["satz"] and g[2]["stelle"] == "5 Millionen Menschen"
    assert g[3]["art"] == "entfernt" and "Pornographie" in g[3]["satz"] and g[3]["stelle"] == ""
    assert g[4]["art"] == "gemeldet" and "„Die Öffnungszeiten stimmen nicht mehr“" in g[4]["satz"] and "weiter für alle sichtbar" in g[4]["satz"]
    assert e["wer"] == ["geprüft von Gerät abc", "von dir", "gemeldet von Gerät x1"]
    assert e["f"] == ["dunklen Jahren unter dem NS-Regime", "Geschenk Gottes mit Zahnspange", None, None]


def test_fables_befunde_vom_07_10():
    html = _html()
    weg = html.split("function meldungEntfernen(k) {", 1)[1].split("\n  }\n", 1)[0]
    assert "wissen_entfernen(k)" in weg and "wissen_meldung_erledigt(k)" in weg and "gibt es nicht" in weg
    assert 'meldungEntfernen(b.dataset.wissen)' in html and 'meldungEntfernen(w.dataset.weg)' in html
    assert 'data-schliessen="1">Meldung schließen' in html
    assert "const angehalten = new Set(" in html and 'd.status === "zurueckgehalten"' in html
    assert ".statusline:empty { min-height: 0; padding: 0; border: 0; }" in html and ".statusline:empty { display: none; }" not in html
    assert "function nach(r, dann) { if (!r) return; if (r.text) sag(r.text, !r.ok);" in html
    assert "sag(r.daten.app.prep_error, true)" in html


def test_meldungsliste_ohne_70_zeichen_schnitt():
    html = _html()
    liste = html.split('$("#meldungen-liste").innerHTML = teil.map(', 1)[1].split('}).join("");', 1)[0]
    assert ".slice(0, 70)" not in liste and "meldungGrund(x.grund)" in liste and "Stelle im Text" in liste
