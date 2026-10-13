# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
LISTE = HIER / "ki-helfer.json"
ZIEL = HIER / "ki-helfer"
JS = HIER / "www" / "js" / "helfer-pruefsummen.js"
KOPF = {"User-Agent": "KIplatz-Bau/1.0"}


def pruefsummen_js(soll: dict[str, str]) -> str:
    zeilen = "".join(f'  "{z}": "{h}",\n' for z, h in sorted(soll.items()))
    return ("// Erzeugt von app/werkzeuge/ki_helfer.py aus app/ki-helfer.json. Nicht von Hand ändern.\n"
            "export const HELFER_SHA256 = Object.freeze({\n" + zeilen + "});\n")


def _laden(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=KOPF), timeout=300) as r:
        return r.read()


def _npm(name_version: str) -> tuple[bytes, str]:
    name, version = name_version.rsplit("@", 1)
    info = json.loads(_laden(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/{version}"))
    daten = _laden(info["dist"]["tarball"])
    algo, erwartet = info["dist"]["integrity"].split("-", 1)
    if algo != "sha512" or base64.b64encode(hashlib.sha512(daten).digest()).decode() != erwartet:
        raise SystemExit(f"FEHLER {name_version}: das Paket stimmt nicht mit der Prüfsumme der npm-Registry überein")
    return daten, info["dist"]["tarball"]


def alle_dateien(liste: dict) -> dict[str, bytes]:
    aus: dict[str, bytes] = {}
    for paket, eintrag in liste["npm"].items():
        tar, _ = _npm(paket)
        with tarfile.open(fileobj=io.BytesIO(tar), mode="r:gz") as t:
            for quelle, ziel in eintrag["dateien"].items():
                aus[ziel] = t.extractfile("package/" + quelle).read()
        print(f"  {paket}: {len(eintrag['dateien'])} Dateien", flush=True)
    for modell, eintrag in liste["huggingface"].items():
        name, fassung = modell.split("@")
        for datei in eintrag["dateien"]:
            aus[eintrag["ziel"] + datei] = _laden(f"https://huggingface.co/{name}/resolve/{fassung}/{datei}")
        print(f"  {modell}: {len(eintrag['dateien'])} Dateien", flush=True)
    return aus


def main(argv: list[str]) -> int:
    art = argv[1] if len(argv) > 1 else "holen"
    liste = json.loads(LISTE.read_text(encoding="utf-8"))
    if art == "js":
        JS.write_text(pruefsummen_js(liste["sha256"]), encoding="utf-8", newline="\n")
        print(f"{JS.name}: {len(liste['sha256'])} Prüfsummen")
        return 0
    dateien = alle_dateien(liste)
    if art == "festlegen":
        liste["sha256"] = {z: hashlib.sha256(d).hexdigest() for z, d in sorted(dateien.items())}
        LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        JS.write_text(pruefsummen_js(liste["sha256"]), encoding="utf-8", newline="\n")
        print(f"{len(dateien)} Prüfsummen eingetragen, auch in {JS.name}")
        return 0
    soll = liste["sha256"]
    if not JS.is_file() or JS.read_text(encoding="utf-8") != pruefsummen_js(soll):
        raise SystemExit(f"FEHLER: {JS.name} passt nicht zu ki-helfer.json (python app/werkzeuge/ki_helfer.py js)")
    if set(soll) != set(dateien):
        raise SystemExit(f"FEHLER: Liste und Prüfsummen passen nicht zusammen: {sorted(set(soll) ^ set(dateien))}")
    for ziel, daten in dateien.items():
        if hashlib.sha256(daten).hexdigest() != soll[ziel]:
            raise SystemExit(f"FEHLER {ziel}: Prüfsumme stimmt nicht, nichts wird abgelegt")
    neu = ZIEL.with_name("ki-helfer.neu")
    shutil.rmtree(neu, ignore_errors=True)
    for ziel, daten in dateien.items():
        p = neu / ziel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(daten)
    (neu / "SHA256SUMS").write_text("".join(f"{soll[z]}  {z}\n" for z in sorted(soll)), encoding="utf-8", newline="\n")
    shutil.rmtree(ZIEL, ignore_errors=True)
    neu.replace(ZIEL)
    groesse = sum(len(d) for d in dateien.values())
    print(f"{len(dateien)} Dateien geprüft und abgelegt in {ZIEL} ({groesse / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
