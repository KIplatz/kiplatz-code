# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

STUECK = 16 * 1024 * 1024
PRUEFWERT = 32
ENDUNG = ".stuecke"


def anzahl(groesse: int) -> int:
    return max(1, -(-groesse // STUECK))


def berechnen(pfad: Path) -> bytes:
    teile = []
    with open(pfad, "rb") as f:
        while True:
            stueck = f.read(STUECK)
            if not stueck:
                break
            teile.append(hashlib.sha256(stueck).digest())
    return b"".join(teile) or hashlib.sha256(b"").digest()


def liste_ok(liste: bytes, groesse: int, liste_sha256: str) -> bool:
    return len(liste) == anzahl(groesse) * PRUEFWERT and hashlib.sha256(liste).hexdigest() == liste_sha256


def pruefwert(liste: bytes, nr: int) -> bytes:
    return liste[nr * PRUEFWERT:(nr + 1) * PRUEFWERT]


def stueck_ok(liste: bytes, nr: int, daten: bytes) -> bool:
    return hashlib.sha256(daten).digest() == pruefwert(liste, nr)


def _main(argv: list[str] | None = None) -> int:
    hier = Path(__file__).resolve().parent
    if str(hier) not in sys.path:
        sys.path.insert(0, str(hier))
    import modell_katalog as mk
    import sicher_schreiben
    ap = argparse.ArgumentParser(description="Stücklisten für die Modelldateien am Server schreiben")
    ap.add_argument("--ordner", required=True)
    a = ap.parse_args(argv)
    ordner = Path(a.ordner) / mk.ORDNER
    aus: dict[str, dict] = {}
    for p in mk.ALLE:
        z = ordner / p.datei
        try:
            if not z.is_file() or z.stat().st_size != p.groesse:
                aus[p.datei] = {"fehlt": True}
                continue
        except OSError:
            aus[p.datei] = {"fehlt": True}
            continue
        ganz = hashlib.sha256()
        teile = []
        with open(z, "rb") as f:
            while True:
                stueck = f.read(STUECK)
                if not stueck:
                    break
                ganz.update(stueck)
                teile.append(hashlib.sha256(stueck).digest())
        if ganz.hexdigest() != p.sha256:
            aus[p.datei] = {"falsch": True}
            continue
        liste = b"".join(teile)
        sicher_schreiben.roh(z.with_name(z.name + ENDUNG), liste)
        aus[p.datei] = {"stuecke_sha256": hashlib.sha256(liste).hexdigest(), "stuecke": len(teile)}
    print(json.dumps(aus, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
