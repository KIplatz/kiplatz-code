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


def _form(k) -> str:
    if isinstance(k, ast.AST):
        return type(k).__name__ + "(" + ",".join(f"{n}={_form(v)}" for n, v in ast.iter_fields(k) if v is not None and v != []) + ")"
    if isinstance(k, list):
        return "[" + ",".join(_form(v) for v in k) + "]"
    return repr(k)


def pruefwert() -> str:
    h = hashlib.sha256()
    for name in ANTWORTWEG:
        baum = _ohne_docstrings(ast.parse((HIER / name).read_text(encoding="utf-8")))
        h.update(name.encode("utf-8") + b"\0" + _form(baum).encode("utf-8") + b"\0")
    return h.hexdigest()[:24]


def test_der_antwortweg_hat_eine_entscheidung():
    stand = json.loads(STAND.read_text(encoding="utf-8"))
    assert stand["mindest_bau"] == ab.MINDEST_BAU, "antwortweg_stand.json nennt einen anderen MINDEST_BAU; mit --nachziehen festhalten"
    assert stand.get("erneuert") == ab.ERNEUERT[-1][0], "antwortweg_stand.json nennt einen anderen letzten Eintrag in ERNEUERT; mit --nachziehen festhalten"
    assert pruefwert() == stand["pruefwert"], (
        "Der Code des Antwortwegs hat sich geändert (" + ", ".join(ANTWORTWEG) + "). Welche gespeicherten Antworten betrifft dieser Bau? "
        "Eine Zeile in antwortspeicher_basis.ERNEUERT mit diesem Bau und den Merkmalen (leer, wenn keine). Danach: python "
        "node-agent/tests/test_antwortweg_sperre_2026_10_26.py --nachziehen \"<Bau>: <warum>\". Siehe den Kopf dieser Datei.")


def test_mindest_bau_bleibt_der_boden():
    assert ab.MINDEST_BAU == "2026-10-26k", "MINDEST_BAU nicht anheben (verwirft alle Antworten); den Bau in antwortspeicher_basis.ERNEUERT eintragen"


def test_erneuert_ist_ordentlich():
    baue = [b for b, _m, _g in ab.ERNEUERT]
    assert baue == sorted(baue) and len(set(baue)) == len(baue) and all(b > ab.MINDEST_BAU for b in baue)
    for b, m, grund in ab.ERNEUERT:
        assert isinstance(m, frozenset) and m <= ab.MERKMALE, f"{b}: unbekanntes Merkmal {sorted(m - ab.MERKMALE)}"
        assert len(grund.strip()) >= 20, f"{b}: der Grund fehlt"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--nachziehen" and sys.argv[2].strip():
        import app_core
        if ab.ERNEUERT[-1][0] != app_core.APP_BUILD:
            print(f"Zuerst eine Zeile für Bau {app_core.APP_BUILD} in antwortspeicher_basis.ERNEUERT (welche Antworten betrifft er, leer wenn keine).")
            raise SystemExit(2)
        STAND.write_text(json.dumps({"pruefwert": pruefwert(), "mindest_bau": ab.MINDEST_BAU, "erneuert": ab.ERNEUERT[-1][0], "grund": sys.argv[2].strip()},
                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print("nachgezogen:", ab.ERNEUERT[-1][0])
    else:
        print(__doc__)
        raise SystemExit(2)
