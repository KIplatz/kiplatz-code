# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ORDNER = Path(__file__).resolve().parents[1]


def doppelte(text: str) -> dict[str, int]:
    zaehler: Counter = Counter()
    for knoten in ast.parse(text).body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            zaehler[knoten.name] += 1
        elif isinstance(knoten, (ast.Assign, ast.AnnAssign)):
            ziele = knoten.targets if isinstance(knoten, ast.Assign) else [knoten.target]
            wert = knoten.value
            for z in ziele:
                if not isinstance(z, ast.Name):
                    continue
                if wert is not None and any(isinstance(n, ast.Name) and n.id == z.id for n in ast.walk(wert)):
                    continue
                zaehler[z.id] += 1
    return {k: v for k, v in zaehler.items() if v > 1}


def test_kein_name_zweimal_auf_modulebene():
    funde = {}
    for p in sorted(ORDNER.glob("*.py")):
        d = doppelte(p.read_text(encoding="utf-8"))
        if d:
            funde[p.name] = d
    assert not funde, f"Name zweimal auf Modulebene, der zweite ersetzt den ersten in der ganzen Datei: {funde}"


def test_gegenprobe():
    assert doppelte("A = 1\ndef f():\n    return A\nA = 2\n") == {"A": 2}
    assert doppelte("S = (1,)\nS = S + (2,)\n") == {}
    assert doppelte("def g():\n    pass\ndef g():\n    pass\n") == {"g": 2}
