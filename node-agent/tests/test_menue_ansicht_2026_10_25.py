# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_app_web import _api

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


class _Webview:
    ZoomFactor = 1.0


class _Form:
    InvokeRequired = False

    def __init__(self):
        self.webview = _Webview()


class _Fenster:
    def __init__(self):
        self.native = _Form()
        self.vollbild = 0

    def toggle_fullscreen(self):
        self.vollbild += 1


def test_zoom_stufen_gemerkt_und_ans_fenster(tmp_path):
    api, _, _ = _api(tmp_path)
    fenster = _Fenster()
    api._window = fenster
    assert api.zoom() == 1.0
    assert api.ansicht_zoom("groesser")["daten"]["zoom"] == 1.1
    r = api.ansicht_zoom("groesser")
    assert r["daten"]["zoom"] == 1.25 and r["text"] == "Ansicht 125 %" and fenster.native.webview.ZoomFactor == 1.25
    assert api.zustand()["daten"]["zoom"] == 1.25
    assert api.ansicht_zoom("kleiner")["daten"]["zoom"] == 1.1
    assert api.ansicht_zoom("normal")["daten"]["zoom"] == 1.0 and fenster.native.webview.ZoomFactor == 1.0
    for _ in range(20):
        api.ansicht_zoom("groesser")
    assert api.zoom() == 2.0
    for _ in range(20):
        api.ansicht_zoom("kleiner")
    assert api.zoom() == 0.67
    api._ki.einstellung_setzen(zoom=7)
    assert api.zoom() == 1.0
    api.ansicht_vollbild()
    assert fenster.vollbild == 1


def test_ohne_fenster_geht_nichts_kaputt(tmp_path):
    api, _, _ = _api(tmp_path)
    api._window = None
    assert api.ansicht_zoom("groesser")["ok"] and api.ansicht_vollbild()["ok"]


def test_menue_wie_bei_claude():
    leiste = HTML[HTML.index('<div id="menubar">'):HTML.index("</div>\n", HTML.index("Über KIplatz</span>"))]
    titel = re.findall(r'<div class="menu"><button type="button">([^<]+)</button>', leiste)
    assert titel == ["Datei", "Bearbeiten", "Ansicht", "Gehe zu", "Hilfe"]
    for tun, kuerzel in (("zoom-normal", "Strg+0"), ("zoom-groesser", "Strg++"), ("zoom-kleiner", "Strg+-"), ("vollbild", "F11"), ("leiste", "Strg+B"),
                         ("neu", "Strg+N"), ("suchen", "Strg+K")):
        assert re.search(rf'data-tun="{tun}"[^>]*>.*?<kbd>{re.escape(kuerzel)}</kbd>', leiste), tun
    assert 'api().ansicht_zoom(richtung)' in HTML and 'api().ansicht_vollbild()' in HTML


def test_sperren_gegen_ueberstehen():
    assert re.search(r"\.page \{[^}]*min-width: 0", HTML)
    assert "@media (max-width: 760px)" in HTML and "@media (max-width: 560px)" in HTML and "#app.leiste-schmal aside" in HTML
    assert "min-width: min(220px, 100%)" in HTML and "function menuEinpassen(m)" in HTML
    assert "max-width: calc(100vw - 8px)" in HTML
