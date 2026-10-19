# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
PBS = "https://github.com/astral-sh/python-build-standalone/releases/download/20260929/"
PYTHON = {
    "linux-x64": ("cpython-3.14.7+20260929-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
                  "da5357f47b1d9c8d4c439004d463d893ef688a44c27438a62b47073d26d1377e", 36262931),
    "macos-arm64": ("cpython-3.14.7+20260929-aarch64-apple-darwin-install_only_stripped.tar.gz",
                    "44b4716f4e63bc85e1c07ea2aca730d13a0ec3557d06526d84a13b1d111cf4f9", 26638721),
}
PIP_PLATTFORM = {"linux-x64": ("manylinux2014_x86_64", "manylinux_2_17_x86_64"), "macos-arm64": ("macosx_11_0_arm64",)}
OBEN = "kiplatz-helfer"
SITE = "python/lib/python3.14/site-packages"
ZEIT = 1760832000


def archivname(plattform: str) -> str:
    return f"KIplatz-Helfer-{plattform}.tar.gz"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for stueck in iter(lambda: f.read(1 << 20), b""):
            h.update(stueck)
    return h.hexdigest()


def python_holen(plattform: str, ordner: Path, *, oeffner=urllib.request.urlopen) -> Path:
    name, sha, groesse = PYTHON[plattform]
    ziel = ordner / name
    if ziel.is_file() and ziel.stat().st_size == groesse and _sha256(ziel) == sha:
        return ziel
    teil = ziel.with_name(ziel.name + ".teil")
    with oeffner(PBS + name, timeout=120) as r, open(teil, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    if teil.stat().st_size != groesse or _sha256(teil) != sha:
        teil.unlink(missing_ok=True)
        raise SystemExit(f"{name}: Prüfsumme oder Größe stimmt nicht, nichts wird gebaut")
    os.replace(teil, ziel)
    return ziel


def pakete_holen(plattform: str, ziel: Path) -> None:
    befehl = [sys.executable, "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps", "--only-binary=:all:",
              "--python-version", "3.14", "--implementation", "cp", "--target", str(ziel), "-r", str(HIER / "requirements-helfer.txt")]
    for tag in PIP_PLATTFORM[plattform]:
        befehl += ["--platform", tag]
    r = subprocess.run(befehl, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise SystemExit(f"pip für {plattform}: {(r.stderr or r.stdout)[-800:]}")


def _info(name: str, *, groesse: int = 0, modus: int = 0o644, ordner: bool = False) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(f"{OBEN}/{name}".rstrip("/"))
    ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = ZEIT, 0, 0, "", ""
    if ordner:
        ti.type, ti.mode = tarfile.DIRTYPE, 0o755
    else:
        ti.size, ti.mode = groesse, modus
    return ti


def _baum(tar: tarfile.TarFile, quelle: Path, unter: str, *, auslassen=("__pycache__",)) -> None:
    for wurzel, ordner, dateien in os.walk(quelle):
        ordner[:] = sorted(o for o in ordner if o not in auslassen)
        rel = Path(wurzel).relative_to(quelle).as_posix()
        basis = unter if rel == "." else f"{unter}/{rel}"
        tar.addfile(_info(basis, ordner=True))
        for d in sorted(dateien):
            daten = (Path(wurzel) / d).read_bytes()
            tar.addfile(_info(f"{basis}/{d}", groesse=len(daten)), io.BytesIO(daten))


def _datei(tar: tarfile.TarFile, name: str, daten: bytes, modus: int = 0o644) -> None:
    tar.addfile(_info(name, groesse=len(daten), modus=modus), io.BytesIO(daten))


def bauen(plattform: str, node_agent: Path, dist: Path) -> Path:
    if not (node_agent / "helfer.pyc").is_file() or not (node_agent / "app_core.py").is_file():
        raise SystemExit(f"{node_agent}: kein verpackter Programmkern (helfer.pyc fehlt); erst build_app_zip.ps1 bis zum Verpacken")
    py_archiv = python_holen(plattform, dist)
    skript = (HIER / "kiplatz-helfer").read_bytes().replace(b"\r\n", b"\n")
    ziel = dist / archivname(plattform)
    neu = ziel.with_name(ziel.name + ".neu")
    try:
        with tempfile.TemporaryDirectory(prefix="helfer-pakete-") as tmp:
            site = Path(tmp) / "site"
            pakete_holen(plattform, site)
            with tarfile.open(neu, "w:gz", format=tarfile.PAX_FORMAT) as tar:
                tar.addfile(_info("", ordner=True))
                _datei(tar, "kiplatz-helfer", skript, 0o755)
                for n in ("LIES-MICH.txt", "README.txt"):
                    _datei(tar, n, (HIER / "verpackung" / f"helfer-{n}").read_bytes().replace(b"\r\n", b"\n"))
                with tarfile.open(py_archiv, "r:gz") as py:
                    import posixpath
                    for m in py.getmembers():
                        if m.name.startswith("/") or ".." in m.name.split("/") or not (posixpath.normpath(m.name) + "/").startswith("python/"):
                            raise SystemExit(f"{py_archiv.name}: unerwarteter Eintrag {m.name}")
                        if m.issym() or m.islnk():
                            ziel_name = m.linkname if m.islnk() else posixpath.join(posixpath.dirname(m.name), m.linkname)
                            ziel_name = posixpath.normpath(ziel_name)
                            if m.linkname.startswith("/") or not ziel_name.startswith("python/"):
                                raise SystemExit(f"{py_archiv.name}: Verweis nach außen {m.name} -> {m.linkname}")
                        if not (m.isfile() or m.isdir() or m.issym() or m.islnk()):
                            continue
                        neu_m = m.replace(name=f"{OBEN}/{m.name}", uid=0, gid=0, uname="", gname="", deep=False)
                        if m.islnk():
                            neu_m.linkname = f"{OBEN}/{m.linkname}"
                        tar.addfile(neu_m, py.extractfile(m) if m.isfile() else None)
                _baum(tar, site, SITE)
                _baum(tar, node_agent, "node-agent")
    except BaseException:
        neu.unlink(missing_ok=True)
        raise
    os.replace(neu, ziel)
    (dist / (ziel.name + ".sha256")).write_bytes(f"{_sha256(ziel)}  {ziel.name}\n".encode("ascii"))
    return ziel


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    node_agent, dist = Path(args[0]), Path(args[1])
    for plattform in PYTHON:
        z = bauen(plattform, node_agent, dist)
        print(f"{z.name}: {z.stat().st_size / 2**20:.1f} MB, SHA-256 {_sha256(z)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
