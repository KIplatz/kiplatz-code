# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import pruefstand


def test_the_server_counts_missing_answers_and_never_compares_with_a_broken_run():
    assert pruefstand.ohne_antwort("(keine Antwort: KIplatz ist auf diesem Gerät gerade ausgeschaltet)") and pruefstand.ohne_antwort("  ")
    assert not pruefstand.ohne_antwort("Der Großglockner ist 3798 m hoch.")
    assert pruefstand.vollstaendig({"gesamt": 1297, "ohne_antwort": 20}) and not pruefstand.vollstaendig({"gesamt": 1297, "ohne_antwort": 673})
    assert pruefstand.vollstaendig({"gesamt": 100, "ohne_antwort": 5})
    fr = [{"kennung": f"m-{i}", "art": "wissen", "antwort": "(keine Antwort: aus)" if i % 2 else "ja", "richtig": not i % 2, "dauer_s": 1.0} for i in range(100)]
    betreff, text = pruefstand.Pruefstand.runden_mail({"tag": "2026-10-17", "richtig": 50, "gesamt": 100, "fragen": fr, "je_art": {}, "runden": 1,
                                                       "bauten": ["B"]}, "rotation")
    assert "UNVOLLSTÄNDIG" in betreff and text.startswith("Achtung: 50 von 100 Fragen blieben ohne Antwort")


def test_the_log_says_why_the_ki_program_stopped():
    api = SimpleNamespace(_ki=SimpleNamespace(server=SimpleNamespace(proc=SimpleNamespace(poll=lambda: 3221225477),
                                                                     log_ende=lambda: "srv load ok\nggml_vulkan: Device lost\nprint_info: done\n")))
    g = app_web.Api._ki_ende_grund(api)
    assert "Endcode 3221225477" in g and "Device lost" in g and "srv load ok" not in g
    api._ki = SimpleNamespace(server=SimpleNamespace(proc=None, log_ende=lambda: ""))
    assert app_web.Api._ki_ende_grund(api) == ""
