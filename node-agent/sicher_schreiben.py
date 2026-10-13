# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ENDUNG_NEU = ".neu"
MAX_JSON = 8 * 1024 * 1024

_lock = threading.Lock()
_reparaturen: list[dict] = []
_zaehler = 0
_gemeldet = 0


def roh(pfad: Path | str, daten: bytes) -> Path:
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    global _zaehler
    with _lock:
        _zaehler += 1
        nr = _zaehler
    tmp = pfad.with_name(f"{pfad.name}.{os.getpid()}-{threading.get_ident()}-{nr}{ENDUNG_NEU}")
    try:
        with open(tmp, "wb") as f:
            f.write(daten)
            f.flush()
            os.fsync(f.fileno())
        for versuch in range(25):
            try:
                os.replace(tmp, pfad)
                break
            except PermissionError:
                if versuch == 24:
                    raise
                time.sleep(0.005 * (versuch + 1))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return pfad


def text(pfad: Path | str, inhalt: str, *, encoding: str = "utf-8") -> Path:
    return roh(pfad, str(inhalt).encode(encoding))


def json_datei(pfad: Path | str, obj, *, indent: int | None = 2, ascii_: bool = False) -> Path:
    if indent is None:
        s = json.dumps(obj, ensure_ascii=ascii_, separators=(",", ":"))
    else:
        s = json.dumps(obj, ensure_ascii=ascii_, indent=indent)
    return text(pfad, s + "\n")


def beiseite_legen(pfad: Path | str, *, grund: str = "") -> Path | None:
    pfad = Path(pfad)
    if not pfad.exists():
        return None
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ziel = pfad.with_name(f"{pfad.stem}.beschaedigt-{stempel}{pfad.suffix}")
    n = 1
    while ziel.exists():
        n += 1
        ziel = pfad.with_name(f"{pfad.stem}.beschaedigt-{stempel}-{n}{pfad.suffix}")
    try:
        groesse = pfad.stat().st_size
    except OSError:
        groesse = -1
    os.replace(pfad, ziel)
    with _lock:
        _reparaturen.append({"datei": pfad.name, "beiseite": ziel.name, "zeit": stempel, "bytes": groesse, "grund": grund})
        del _reparaturen[:-50]
    return ziel


def json_laden(pfad: Path | str, standard, *, art: type | tuple[type, ...] | None = None, hoechstens: int = MAX_JSON):
    pfad = Path(pfad)
    if art is None and standard is not None:
        art = type(standard)
    try:
        if not pfad.exists():
            return standard
        for versuch in range(25):
            try:
                roh_ = pfad.read_bytes()
                break
            except PermissionError:
                if versuch == 24:
                    raise
                time.sleep(0.004)
        if len(roh_) > hoechstens:
            raise ValueError("zu groß")
        d = json.loads(roh_.decode("utf-8"))
        if art is not None and not isinstance(d, art):
            raise ValueError("falsche Form")
        return d
    except FileNotFoundError:
        return standard
    except OSError:
        raise
    except ValueError as exc:
        try:
            beiseite_legen(pfad, grund=type(exc).__name__)
        except OSError:
            pass
        return standard


_gemerkt: dict[str, tuple[tuple[int, int, int], object]] = {}


def json_laden_gemerkt(pfad: Path | str, standard, *, art: type | tuple[type, ...] | None = None, hoechstens: int = MAX_JSON):
    pfad = Path(pfad)
    try:
        st = pfad.stat()
    except FileNotFoundError:
        return standard
    except OSError:
        with _lock:
            e = _gemerkt.get(str(pfad))
        if e is not None:
            return e[1]
        raise
    stempel = (st.st_ino, st.st_mtime_ns, st.st_size)
    schluessel = str(pfad)
    with _lock:
        e = _gemerkt.get(schluessel)
    if e is not None and e[0] == stempel:
        return e[1]
    d = json_laden(pfad, standard, art=art, hoechstens=hoechstens)
    if d is not standard:
        with _lock:
            _gemerkt[schluessel] = (stempel, d)
    return d


def reparaturen() -> list[dict]:
    with _lock:
        return [dict(r) for r in _reparaturen]


def neue_reparaturen() -> list[dict]:
    global _gemeldet
    with _lock:
        neu = [dict(r) for r in _reparaturen[_gemeldet:]]
        _gemeldet = len(_reparaturen)
        return neu


def satz_de(r: dict) -> str:
    return (f"Die Datei {r['datei']} war beschädigt (zum Beispiel nach einem harten Ausschalten). Sie liegt als "
            f"{r['beiseite']} daneben; das Programm hat sie neu angelegt.")
