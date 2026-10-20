# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent
VENV = WURZEL / ".venv"
PAKETE = ["-r", str(HIER / "requirements-dev.txt"), "pywebview>=6,<7", "pytest-xdist"]
BEFEHLE = {"einrichten": "einrichten", "setup": "einrichten", "tests": "tests", "test": "tests",
           "bauen": "bauen", "build": "bauen", "pruefen": "pruefen", "check": "pruefen"}


def deutsch() -> bool:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        wert = os.environ.get(name, "")
        if wert:
            return wert.lower().startswith("de")
    return False


def _s(de: str, en: str) -> str:
    return de if deutsch() else en


def _sag(de: str, en: str) -> None:
    print(_s(de, en), flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def python() -> str:
    p = venv_python()
    return str(p) if p.is_file() else sys.executable


def _lauf(befehl: list[str], *, cwd: Path | None = None, runner=subprocess.run) -> int:
    print("> " + " ".join(befehl), flush=True)
    return runner(befehl, cwd=str(cwd) if cwd else None, check=False).returncode


def einrichten(runner=subprocess.run) -> int:
    if sys.version_info < (3, 12):
        _sag("Dafür braucht es Python 3.12 oder neuer (das Programm selbst läuft mit 3.14).",
             "This needs Python 3.12 or newer (the program itself runs on 3.14).")
        return 1
    if sys.version_info[:2] != (3, 14):
        _sag(f"Hinweis: Python {sys.version_info[0]}.{sys.version_info[1]}; die Reihe auf GitHub und das Programm nehmen 3.14.",
             f"Note: Python {sys.version_info[0]}.{sys.version_info[1]}; the GitHub run and the program use 3.14.")
    if not venv_python().is_file():
        code = _lauf([sys.executable, "-m", "venv", str(VENV)], runner=runner)
        if code:
            return code
    code = _lauf([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip"], runner=runner) or \
        _lauf([str(venv_python()), "-m", "pip", "install", *PAKETE], runner=runner)
    if code:
        return code
    npm = shutil.which("npm")
    if npm and (WURZEL / "app" / "package-lock.json").is_file():
        code = _lauf([npm, "ci", "--ignore-scripts"], cwd=WURZEL / "app", runner=runner)
        if code:
            return code
    else:
        _sag("npm fehlt: ein paar Tests brauchen esbuild aus app/ (Node.js installieren, dann „npm ci --ignore-scripts“ in app/).",
             "npm is missing: a few tests need esbuild from app/ (install Node.js, then run \"npm ci --ignore-scripts\" in app/).")
    _sag(f"Fertig. Tests: {Path(sys.argv[0]).name} tests", f"Done. Tests: {Path(sys.argv[0]).name} test")
    return 0


def tests(weiter: list[str], runner=subprocess.run) -> int:
    py = python()
    befehl = [py, "-m", "pytest", str(HIER / "tests"), "-q", "-p", "no:cacheprovider"]
    if _hat_xdist(py, runner):
        befehl += ["-n", str(max(1, (os.cpu_count() or 2) - 2))]
    return _lauf(befehl + list(weiter), cwd=HIER, runner=runner)


def _hat_xdist(py: str, runner) -> bool:
    if py == sys.executable:
        return importlib.util.find_spec("xdist") is not None
    return runner([py, "-c", "import xdist"], capture_output=True, check=False).returncode == 0


def bauen(runner=subprocess.run) -> int:
    if os.name == "nt":
        return _lauf(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(HIER / "build_app_zip.ps1"), "-OhneUnterschrift"], runner=runner)
    return _lauf([python(), str(HIER / "helfer_paket.py"), "--aus-quelle", str(HIER / "dist")], runner=runner)


def pruefen(runner=subprocess.run) -> int:
    privat = WURZEL / "werkzeuge" / "pruefen.py"
    if privat.is_file():
        return _lauf([python(), str(privat)], cwd=WURZEL, runner=runner)
    code = _lauf([python(), "-m", "compileall", "-q", str(HIER)], runner=runner)
    return code or tests([], runner=runner)


def main(argv: list[str] | None = None, runner=subprocess.run) -> int:
    args = sys.argv[1:] if argv is None else argv
    befehl = BEFEHLE.get(args[0] if args else "")
    if befehl is None:
        print(__doc__.split("\n\n")[1] if deutsch() else
              "    python node-agent/entwickeln.py setup   .venv next to node-agent/, the packages of the Linux run on GitHub, esbuild for the tests\n"
              "    python node-agent/entwickeln.py test    the tests (in parallel when pytest-xdist is there); more arguments go to pytest\n"
              "    python node-agent/entwickeln.py build   Windows: the program zip without signature; Linux and Mac: the helper packages from source\n"
              "    python node-agent/entwickeln.py check   what has to be green before a pull request")
        return 2
    if befehl == "einrichten":
        return einrichten(runner)
    if befehl == "tests":
        return tests(args[1:], runner)
    if befehl == "bauen":
        return bauen(runner)
    return pruefen(runner)


if __name__ == "__main__":
    raise SystemExit(main())
