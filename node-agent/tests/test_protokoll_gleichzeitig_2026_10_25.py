# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web


class _Kern:
    def __init__(self, ordner: Path):
        self.diagnosis_dir = ordner

    def ensure_directories(self):
        self.diagnosis_dir.mkdir(parents=True, exist_ok=True)


def test_gleichzeitige_zeilen_bleiben_ganz(tmp_path):
    kern = _Kern(tmp_path / "diagnose")

    def schreiben(n: int):
        for i in range(200):
            app_web._log(kern, f"FADEN{n} ZEILE{i:03d} " + "x" * 80)

    faeden = [threading.Thread(target=schreiben, args=(n,)) for n in range(8)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    zeilen = (kern.diagnosis_dir / "protokoll.txt").read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1600
    assert all(z.split(" ", 1)[1].startswith("FADEN") and z.endswith("x" * 80) for z in zeilen)
