# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import antwortspeicher_basis as ab

STAND = Path(__file__).resolve().parent / "antwortweg_stand.json"
ANTWORTWEG = ("app_web.py", "belege.py", "absicht.py", "nachschauen.py", "antwortsprache.py", "namenpruefung.py", "wortliste.py",
              "einkauf.py", "wissen.py", "bewertung.py", "ki_laufzeit.py")


def _ohne_docstrings(baum: ast.AST) -> ast.AST:
    for knoten in ast.walk(baum):
        rumpf = getattr(knoten, "body", None)
        if isinstance(rumpf, list) and rumpf and isinstance(rumpf[0], ast.Expr) and isinstance(getattr(rumpf[0], "value", None), ast.Constant) \
                and isinstance(rumpf[0].value.value, str):
            knoten.body = rumpf[1:] or [ast.Pass()]
    return baum


def pruefwert() -> str:
    h = hashlib.sha256()
    for name in ANTWORTWEG:
        baum = _ohne_docstrings(ast.parse((HIER / name).read_text(encoding="utf-8")))
        h.update(name.encode("utf-8") + b"\0" + ast.dump(baum, include_attributes=False).encode("utf-8") + b"\0")
    return h.hexdigest()[:24]


def test_der_antwortweg_hat_eine_entscheidung_zu_mindest_bau():
    stand = json.loads(STAND.read_text(encoding="utf-8"))
    assert stand["mindest_bau"] == ab.MINDEST_BAU, "antwortweg_stand.json nennt einen anderen MINDEST_BAU; mit --nachziehen festhalten"
    assert pruefwert() == stand["pruefwert"], (
        "Der Code des Antwortwegs hat sich geändert (" + ", ".join(ANTWORTWEG) + "). Ändert dieser Bau, wie Antworten entstehen? Dann "
        "antwortspeicher_basis.MINDEST_BAU auf diesen Bau setzen. In jedem Fall danach: python node-agent/tests/test_antwortweg_sperre_2026_10_26.py "
        "--nachziehen \"<Bau>: <warum>\". Siehe den Kopf dieser Datei.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--nachziehen" and sys.argv[2].strip():
        STAND.write_text(json.dumps({"pruefwert": pruefwert(), "mindest_bau": ab.MINDEST_BAU, "grund": sys.argv[2].strip()}, ensure_ascii=False, indent=1)
                         + "\n", encoding="utf-8", newline="\n")
        print("nachgezogen:", ab.MINDEST_BAU)
    else:
        print(__doc__)
        raise SystemExit(2)
