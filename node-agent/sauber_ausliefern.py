# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
_ESBUILD_UNTER = Path("app") / "node_modules" / "@esbuild" / "win32-x64" / "esbuild.exe"
ESBUILD = WURZEL / _ESBUILD_UNTER


def _esbuild_version_soll() -> str:
    try:
        m = re.search(r'"esbuild"\s*:\s*"[~^]?(\d+\.\d+\.\d+)"', (WURZEL / "app" / "package.json").read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def _hauptordner() -> Path | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=WURZEL, capture_output=True, text=True, check=False, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    gemeinsam = (WURZEL / r.stdout.strip()).resolve()
    haupt = gemeinsam.parent
    return None if haupt == WURZEL else haupt


_ESBUILD_GEFUNDEN: Path | None = None


def esbuild_pfad() -> Path:
    global _ESBUILD_GEFUNDEN
    if _ESBUILD_GEFUNDEN is not None and _ESBUILD_GEFUNDEN.is_file():
        return _ESBUILD_GEFUNDEN
    soll = _esbuild_version_soll()
    kandidaten = [ESBUILD]
    haupt = _hauptordner()
    if haupt is not None:
        kandidaten.append(haupt / _ESBUILD_UNTER)
    falsch = []
    for pfad in kandidaten:
        if not pfad.is_file():
            continue
        if soll:
            r = subprocess.run([str(pfad), "--version"], capture_output=True, text=True, check=False, timeout=30)
            ist = r.stdout.strip()
            if ist != soll:
                falsch.append(f"{pfad} ist {ist or '?'}, package.json will {soll}")
                continue
        _ESBUILD_GEFUNDEN = pfad
        return pfad
    hinweis = "; ".join(falsch)
    raise SystemExit(f"esbuild fehlt ({ESBUILD}{'; ' + hinweis if hinweis else ''}); im Ordner app/ einmal `npm ci --ignore-scripts` ausführen")


def esbuild_vorhanden() -> bool:
    try:
        esbuild_pfad()
        return True
    except SystemExit:
        return False

VERBOTEN: list[tuple[re.Pattern[bytes], str]] = [
    (re.compile(rb"[A-Za-z0-9._%+-]+@(?!kiplatz\.at\b)[A-Za-z0-9-]+\.[A-Za-z]{2,}"), "E-Mail-Adresse"),
    (re.compile(rb"BEGIN [A-Z ]*PRIVATE KEY"), "Schlüssel"),
    (re.compile(rb"192\.168\.\d+\.\d+"), "Heimnetz-Adresse"),
]
ERLAUBT: tuple[bytes, ...] = ()
GERAETENAMEN: tuple[bytes, ...] = ()
LISTEN_DATEI = WURZEL / "werkzeuge" / "sauber_verboten.txt"
_LISTEN_GELADEN = False


def listen_laden(pfad: Path = LISTEN_DATEI) -> bool:
    global ERLAUBT, GERAETENAMEN, _LISTEN_GELADEN
    if _LISTEN_GELADEN:
        return True
    if not pfad.is_file():
        return False
    abschnitt = ""
    erlaubt, geraete = list(ERLAUBT), list(GERAETENAMEN)
    for z in pfad.read_text(encoding="utf-8").splitlines():
        z = z.rstrip()
        if not z or z.startswith("#"):
            continue
        if z.startswith("[") and z.endswith("]"):
            abschnitt = z[1:-1]
            continue
        if abschnitt == "verboten":
            was, _, regex = z.partition("\t")
            if not regex:
                raise SystemExit(f"{pfad.name}: Zeile ohne Tabulator: {z[:60]}")
            VERBOTEN.append((re.compile(regex.encode("utf-8"), re.I), was.strip()))
        elif abschnitt == "erlaubt":
            erlaubt.append(z.encode("utf-8"))
        elif abschnitt == "geraetenamen":
            geraete.append(z.encode("utf-8"))
    ERLAUBT, GERAETENAMEN = tuple(erlaubt), tuple(geraete)
    _LISTEN_GELADEN = True
    return True


TEXT = {".html", ".js", ".css", ".scss", ".yml", ".tmpl", ".sh", ".ini", ".py", ".pyc", ".md", ".txt", ".json", ".webmanifest", ".svg", ".xml", ".plist"}


def _esbuild(text: str, loader: str, *, modul: bool = False) -> str:
    args = [str(esbuild_pfad()), f"--loader={loader}", "--minify-whitespace", "--minify-syntax", "--legal-comments=none", "--charset=utf8"]
    if modul:
        args += ["--format=esm", "--target=es2022"]
    r = subprocess.run(args, input=text.encode("utf-8"), capture_output=True, check=False)
    if r.returncode != 0:
        raise SystemExit(f"esbuild ({loader}): {r.stderr.decode('utf-8', 'replace')[:500]}")
    return r.stdout.decode("utf-8")


def js(text: str, *, modul: bool = True) -> str:
    return _esbuild(text, "js", modul=modul)


def css(text: str) -> str:
    return _esbuild(text, "css")


_SKRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)
_STIL = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)


def html(text: str) -> str:
    text = re.sub(r"<!--(?!/?[a-z0-9-]+-->).*?-->", "", text, flags=re.S)
    def skript(m: re.Match) -> str:
        attr = m.group(1).lower()
        if not m.group(2).strip() or ("type=" in attr and "module" not in attr and "javascript" not in attr):
            return m.group(0)
        return m.group(1) + js(m.group(2), modul="module" in m.group(1).lower()) + m.group(3)
    text = _SKRIPT.sub(skript, text)
    text = _STIL.sub(lambda m: m.group(1) + css(m.group(2)) + m.group(3), text)
    return text


def scss(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?<=[;{}])[ \t]+//[^\n]*", "", text)
    return "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("//")) + "\n"


def datei_reinigen(quelle: Path, ziel: Path) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    art = quelle.suffix.lower()
    if art in (".html", ".js", ".css", ".scss"):
        text = quelle.read_text(encoding="utf-8")
        neu = (html(text) if art == ".html" else css(text) if art == ".css" else scss(text) if art == ".scss"
               else js(text, modul="vendor" not in quelle.parts))
        ziel.write_text(neu, encoding="utf-8", newline="\n")
    else:
        shutil.copyfile(quelle, ziel)


def reinigen(quelle: Path, ziel: Path) -> list[Path]:
    if quelle.is_file():
        datei_reinigen(quelle, ziel)
        return [ziel]
    if ziel.exists():
        shutil.rmtree(ziel)
    out = []
    for q in sorted(quelle.rglob("*")):
        if q.is_file():
            z = ziel / q.relative_to(quelle)
            datei_reinigen(q, z)
            out.append(z)
    return out


def treffer(pfad: Path, *, website: bool = False) -> list[str]:
    if not listen_laden():
        print(f"Hinweis: {LISTEN_DATEI.name} fehlt, geprüft werden nur die allgemeinen Muster (Mailadressen, Schlüssel, Heimnetz).")
    dateien = [pfad] if pfad.is_file() else [p for p in pfad.rglob("*") if p.is_file()]
    funde = []
    for d in dateien:
        if d.suffix.lower() not in TEXT:
            continue
        roh = d.read_bytes()
        for e in ERLAUBT + (GERAETENAMEN if website else ()):
            roh = roh.replace(e, b"")
        for muster, was in VERBOTEN:
            m = muster.search(roh)
            if m:
                funde.append(f"{d}: {was} („{m.group(0).decode('utf-8', 'replace')[:40]}“)")
    return funde


def main(argv: list[str]) -> int:
    website = "--website" in argv
    argv = [a for a in argv if a != "--website"]
    if len(argv) == 3 and argv[1] == "--pruefen":
        f = treffer(Path(argv[2]), website=website)
    elif len(argv) == 3:
        reinigen(Path(argv[1]), Path(argv[2]))
        f = treffer(Path(argv[2]), website=website)
    else:
        print(__doc__)
        return 2
    for z in f:
        print("NICHT SAUBER:", z)
    print("sauber" if not f else f"{len(f)} Funde, nichts darf so hinaus")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
