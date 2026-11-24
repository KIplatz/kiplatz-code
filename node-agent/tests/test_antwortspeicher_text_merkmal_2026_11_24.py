# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import antwortspeicher_basis as ab


def _ls(bau: str) -> dict:
    return {"bau": bau, "stand": {"art": "suche"}, "gemacht": "nachgeschaut"}


def test_text_merkmal_trifft_nur_passende_antworten(monkeypatch):
    monkeypatch.setattr(ab, "ERNEUERT", (("2026-11-24x", frozenset({"text:(?i)luftlinie"}), "Probe: nur Antworten mit Luftlinie, ein Grund"),))
    assert ab.erneuert_von(_ls("2026-11-24a"), "Die Luftlinie beträgt 181 km.") == "2026-11-24x"
    assert ab.erneuert_von(_ls("2026-11-24a"), "Der Traunsee ist 191 Meter tief.") == ""
    assert ab.erneuert_von(_ls("2026-11-24y"), "Die Luftlinie beträgt 155 km.") == ""


def test_merkmal_gueltig():
    assert ab.merkmal_gueltig("suche") and ab.merkmal_gueltig("text:römisch") and not ab.merkmal_gueltig("text:(") and not ab.merkmal_gueltig("bla")


def test_traunsee_von_24c_bleibt():
    assert ab.erneuert_von(_ls("2026-11-24b"), "Der Traunsee ist 191 Meter tief.") == ""
