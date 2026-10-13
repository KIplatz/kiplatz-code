# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
from test_app_web import _api

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40


def test_pasted_png_lands_beside_the_conversation_and_junk_is_refused(tmp_path):
    api = _api(tmp_path)[0]
    g = api.gespraech_neu()["daten"]
    r = api.gespraech_bild_daten(g["kennung"], "Bildschirmfoto.png", "data:image/png;base64," + base64.b64encode(PNG).decode("ascii"))
    assert r["ok"] and r["daten"]["gespraech"]["anhaenge"][0]["art"] == "bild" and r["daten"]["gespraech"]["anhaenge"][0]["mime"] == "image/png"
    assert "Bild dabei" in r["text"]
    r2 = api.gespraech_bild_daten(g["kennung"], "x.png", base64.b64encode(b"kein bild").decode("ascii"))
    assert not r2["ok"] and r2["code"] == "BILD_ART"
    r3 = api.gespraech_bild_daten(g["kennung"], "x.png", "%%%nicht-base64")
    assert not r3["ok"] and r3["code"] == "BILD_ART"


def test_more_than_three_pictures_are_refused(tmp_path):
    api = _api(tmp_path)[0]
    g = api.gespraech_neu()["daten"]
    b64 = base64.b64encode(PNG).decode("ascii")
    for _ in range(3):
        assert api.gespraech_bild_daten(g["kennung"], "", b64)["ok"]
    assert api.gespraech_bild_daten(g["kennung"], "", b64)["code"] == "BILD_VIELE"
    assert app_core.APP_BUILD >= "2026-09-23za"
