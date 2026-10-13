# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZIEL = HERE / "requirements-bau.txt"
EXTRA = ["pywebview>=6,<7",
         "pythonnet>=3.1,<3.2"]


def _name_version(datei: str) -> tuple[str, str]:
    if datei.endswith(".whl"):
        name, version = datei.split("-")[:2]
    else:
        m = re.match(r"(.+)-(\d[^-]*)\.(tar\.gz|zip)$", datei)
        if not m:
            raise SystemExit(f"unbekannte Datei: {datei}")
        name, version = m.group(1), m.group(2)
    return name.replace("_", "-").lower(), version


def schreiben(ordner: Path) -> str:
    zeilen = ["# Erzeugt von requirements_bau_erneuern.py; nicht von Hand ändern. Jede Zeile: Paket, feste Version, SHA-256 der Datei",
              f"# von PyPI (Fundament 2, {__import__('datetime').date.today().isoformat()}). build_app_zip.ps1 installiert nur damit (--require-hashes).",
              f"# Räder für Windows und Python {reihe_des_baus()} (die Reihe aus $pyVersion in build_app_zip.ps1)."]
    for p in sorted(ordner.iterdir()):
        if p.suffix not in (".whl", ".gz", ".zip"):
            continue
        name, version = _name_version(p.name)
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        marker = ' ; sys_platform == "win32"' if name in ("pywin32", "pythonnet", "clr-loader") else ""
        zeilen.append(f"{name}=={version}{marker} \\" + chr(10) + f"    --hash=sha256:{h}")
    return "\n".join(zeilen) + "\n"


NUR_QUELLTEXT = ("proxy-tools",)


def reihe_des_baus() -> str:
    m = re.search(r'^\$pyVersion\s*=\s*"(\d+)\.(\d+)\.\d+"', (HERE / "build_app_zip.ps1").read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("$pyVersion fehlt in build_app_zip.ps1")
    return f"{m.group(1)}.{m.group(2)}"


def main() -> int:
    reihe = reihe_des_baus()
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as ziel:
        cmd = [sys.executable, "-m", "pip", "download", "-q", "-r", str(HERE / "requirements.txt"), *EXTRA, "--dest", tmp]
        subprocess.run(cmd, check=True)
        for p in sorted(Path(tmp).iterdir()):
            if p.suffix not in (".whl", ".gz", ".zip"):
                continue
            name, version = _name_version(p.name)
            nur_rad = [] if name in NUR_QUELLTEXT else ["--only-binary=:all:"]
            subprocess.run([sys.executable, "-m", "pip", "download", "-q", "--no-deps", "--python-version", reihe, "--implementation", "cp",
                            "--platform", "win_amd64", *nur_rad, f"{name}=={version}", "--dest", ziel], check=True)
        text = schreiben(Path(ziel))
    ZIEL.write_text(text, encoding="utf-8")
    print(f"{ZIEL.name}: {text.count('--hash=')} Pakete mit Prüfsumme")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
