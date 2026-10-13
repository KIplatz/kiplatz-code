# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

OLLAMA_VERSION = "0.34.4"
OLLAMA_ZIP_SHA256 = "535193f38f3344e5b08f5d1c171c31ce11aa17f0124ff69ae26d8ec7fe06fa62"
ZIEL_NAME = f"kiplatz-laufzeit-ollama-{OLLAMA_VERSION}-vulkan-x64.zip"
ZEIT = (2026, 9, 29, 0, 0, 0)
LIZENZ_ORDNER = Path(__file__).resolve().parent / "lizenzen"
HINWEIS = f"""KIplatz KI-Laufzeit

Diese Dateien stammen unverändert aus Ollama {OLLAMA_VERSION} für Windows (https://github.com/ollama/ollama, MIT-Lizenz, siehe
OLLAMA_LICENSE) und enthalten llama.cpp und ggml (MIT-Lizenz, siehe LLAMA_CPP_LICENSE) sowie die weiteren Bausteine, deren Lizenzen
daneben liegen. Jede .exe und .dll trägt die Unterschrift „Ollama Inc.“. KIplatz hat nichts daran geändert, nur neu verpackt.
"""


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for teil in iter(lambda: f.read(1 << 20), b""):
            h.update(teil)
    return h.hexdigest()


def dateien(quelle: zipfile.ZipFile) -> dict[str, bytes]:
    aus: dict[str, bytes] = {}
    for info in quelle.infolist():
        teile = info.filename.split("/")
        if info.is_dir() or teile[:2] != ["lib", "ollama"]:
            continue
        if len(teile) == 3 or (len(teile) == 4 and teile[2] == "vulkan"):
            name, daten = teile[-1], quelle.read(info)
            if name in aus and aus[name] != daten:
                raise SystemExit(f"FEHLER: {name} gibt es zweimal mit verschiedenem Inhalt")
            aus[name] = daten
    if "llama-server.exe" not in aus or "ggml-vulkan.dll" not in aus:
        raise SystemExit("FEHLER: llama-server.exe oder ggml-vulkan.dll fehlt im Ollama-Paket")
    return aus


def bauen(ollama_zip: Path, ziel_ordner: Path) -> Path:
    if _sha256(ollama_zip) != OLLAMA_ZIP_SHA256:
        raise SystemExit("FEHLER: das Ollama-Paket hat nicht die erwartete Prüfsumme")
    with zipfile.ZipFile(ollama_zip) as q:
        inhalt = dateien(q)
    inhalt["OLLAMA_LICENSE"] = (LIZENZ_ORDNER / "OLLAMA_LICENSE").read_bytes()
    inhalt["KIPLATZ-HINWEIS.txt"] = HINWEIS.encode("utf-8")
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel_ordner / ZIEL_NAME
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(inhalt):
            info = zipfile.ZipInfo(name, ZEIT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, inhalt[name])
    return ziel


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    z = bauen(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "dist")
    print(f"{z.name}: {z.stat().st_size} Bytes, SHA-256 {_sha256(z)}")
