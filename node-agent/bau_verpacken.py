# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ast
import re
import shutil
import sys
from importlib._bootstrap_external import _code_to_timestamp_pyc
from pathlib import Path

START = ("app_web", "sitecustomize", "helfer")
QUELLE_BLEIBT = ("sitecustomize",)
STUMMEL = ("app_web", "app_core")


def _importe(datei: Path) -> set[str]:
    text = datei.read_text(encoding="utf-8")
    namen: set[str] = set()
    for n in ast.walk(ast.parse(text, filename=datei.name)):
        if isinstance(n, ast.Import):
            namen.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            namen.add(n.module.split(".")[0])
    namen.update(re.findall(r'__import__\(\s*["\']([A-Za-z_0-9]+)["\']', text))
    namen.update(re.findall(r'import_module\(\s*["\']([A-Za-z_0-9]+)["\']', text))
    return namen


def gebraucht(ordner: Path) -> set[str]:
    eigene = {p.stem for p in ordner.glob("*.py")}
    fehlt = [s for s in START if s not in eigene]
    if fehlt:
        raise SystemExit(f"Startdatei fehlt im Bauordner: {fehlt}")
    gesehen: set[str] = set()
    offen = list(START)
    while offen:
        m = offen.pop()
        if m in gesehen:
            continue
        gesehen.add(m)
        offen.extend((_importe(ordner / f"{m}.py") & eigene) - gesehen)
    return gesehen


def _ohne_docstrings(baum: ast.Module) -> ast.Module:
    def lose(s: ast.stmt) -> bool:
        return isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str)
    for n in ast.walk(baum):
        for feld in ("body", "orelse", "finalbody"):
            koerper = getattr(n, feld, None)
            if isinstance(koerper, list) and koerper and all(isinstance(s, ast.stmt) for s in koerper):
                rest = [s for s in koerper if not lose(s)]
                if len(rest) != len(koerper):
                    setattr(n, feld, rest or [ast.Pass()])
    return ast.fix_missing_locations(baum)


def _stummel(name: str, quelle: str) -> str:
    zeilen = ["# KIplatz: dieser Programmteil liegt übersetzt daneben (" + name + ".pyc)."]
    if name == "app_core":
        m = re.search(r'^APP_BUILD\s*=\s*"[^"\n]{1,40}"', quelle, re.M)
        if not m:
            raise SystemExit("APP_BUILD fehlt in app_core.py")
        zeilen.append(m.group(0))
    if name == "app_web":
        reihe = tuple(sys.version_info[:2])
        zeilen.append(f"import sys as _s\nif _s.version_info[:2] != {reihe!r}: import pathlib as _q; _g = {{'__name__': 'kiplatz_reihe'}}; "
                      "exec(_q.Path(__file__).with_name('sitecustomize.py').read_text(encoding='utf-8'), _g); _g['_falsche_reihe'](__file__)")
    zeilen.append("import marshal as _m, pathlib as _p")
    zeilen.append('exec(_m.loads(_p.Path(__file__).with_suffix(".pyc").read_bytes()[16:]), globals())')
    return "\n".join(zeilen) + "\n"


def verpacken(ordner: Path) -> tuple[list[str], list[str]]:
    reihe = f"python{sys.version_info[0]}{sys.version_info[1]}.dll"
    if not (Path(ordner).resolve().parent / "python" / reihe).is_file():
        raise SystemExit(f"falsches Python {sys.version.split()[0]}: der Bytecode muss zum Python im Bauordner passen ({reihe} fehlt dort)")
    brauch = gebraucht(ordner)
    weg, uebersetzt = [], []
    for datei in sorted(ordner.glob("*.py")):
        name = datei.stem
        if name not in brauch:
            datei.unlink()
            weg.append(name)
            continue
        if name in QUELLE_BLEIBT:
            quelle = datei.read_text(encoding="utf-8")
            datei.write_text(ast.unparse(_ohne_docstrings(ast.parse(quelle, filename=datei.name))) + "\n", encoding="utf-8", newline="\n")
            continue
        quelle = datei.read_text(encoding="utf-8")
        code = compile(_ohne_docstrings(ast.parse(quelle, filename=datei.name)), datei.name, "exec", dont_inherit=True, optimize=0)
        datei.with_suffix(".pyc").write_bytes(_code_to_timestamp_pyc(code, 0, 0))
        if name in STUMMEL:
            datei.write_text(_stummel(name, quelle), encoding="utf-8", newline="\n")
        else:
            datei.unlink()
        uebersetzt.append(name)
    for p in ordner.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return weg, uebersetzt


def pruefen(ordner: Path) -> int:
    import importlib
    sys.path.insert(0, str(ordner))
    fehler = 0
    namen = sorted({p.stem for p in ordner.glob("*.pyc")} - {"app_web"})
    for name in namen:
        try:
            importlib.import_module(name)
        except Exception as exc:
            fehler += 1
            print(f"FEHLER beim Laden von {name}: {type(exc).__name__}: {exc}")
    lesbar = sorted(p.name for p in ordner.glob("*.py"))
    if lesbar != sorted(f"{n}.py" for n in QUELLE_BLEIBT + STUMMEL):
        fehler += 1
        print(f"FEHLER: lesbar geblieben: {lesbar}")
    print(f"{len(namen)} Module geladen, {fehler} Fehler; lesbar nur {', '.join(lesbar)}")
    return 1 if fehler else 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--pruefen":
        raise SystemExit(pruefen(Path(sys.argv[2])))
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    w, u = verpacken(Path(sys.argv[1]))
    print(f"verpackt: {len(u)} Module als Bytecode, {len(w)} nicht gebraucht und weggelassen: {', '.join(w)}")
