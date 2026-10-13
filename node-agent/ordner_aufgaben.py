# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from pathlib import Path

import anhaenge
import app_core
import sicher_schreiben

MAX_DATEIEN = 60
MAX_LESEN = 3
MAX_JE_DATEI = 20_000
MAX_ZEICHEN = 40_000
MAX_SCHREIBEN = 200_000
ENDUNGEN_SCHREIBEN = (".md", ".txt")

_cache: dict[tuple[str, int, int], anhaenge.Anhang] = {}


def pruefen(pfad: Path) -> Path:
    p = Path(pfad)
    if not p.is_absolute() or app_core._is_reparse(p) or not p.is_dir():
        raise app_core.AppError("ORDNER_ART", "das ist kein gewöhnlicher Ordner")
    if p.parent == p:
        raise app_core.AppError("ORDNER_WURZEL", "ein ganzes Laufwerk freizugeben geht nicht; bitte einen Ordner darin wählen")
    return p.resolve()


def uebersicht(pfad: Path) -> list[dict]:
    p = pruefen(pfad)
    out = []
    try:
        eintraege = sorted(p.iterdir(), key=lambda x: x.name.lower())
    except OSError:
        raise app_core.AppError("ORDNER_LESEN", "der Ordner lässt sich nicht lesen") from None
    for e in eintraege:
        if e.name.startswith(".") or app_core._is_reparse(e) or not e.is_file():
            continue
        try:
            groesse = e.stat().st_size
        except OSError:
            continue
        out.append({"name": e.name, "kb": max(1, groesse // 1024), "lesbar": e.suffix.lower() in anhaenge.ENDUNGEN and groesse <= anhaenge.MAX_DATEI})
        if len(out) >= MAX_DATEIEN:
            break
    return out


def _lesen(p: Path) -> anhaenge.Anhang | None:
    try:
        st = p.stat()
        k = (str(p), int(st.st_mtime_ns), st.st_size)
    except OSError:
        return None
    a = _cache.get(k)
    if a is None:
        try:
            a = anhaenge.lesen(p)
        except app_core.AppError:
            return None
        if len(_cache) > 200:
            _cache.clear()
        _cache[k] = a
    return a


_WORT = re.compile(r"[a-zäöüß0-9]{4,}", re.I)


def auswahl(pfad: Path, frage: str, *, hoechstens: int = MAX_LESEN) -> list[dict]:
    p = pruefen(pfad)
    liste = [e for e in uebersicht(p) if e["lesbar"]]
    if not liste:
        return []
    woerter = {w.lower() for w in _WORT.findall(frage or "")}
    frage_klein = (frage or "").lower()
    bewertet = []
    for e in liste:
        a = _lesen(p / e["name"])
        if a is None:
            continue
        stamm = Path(e["name"]).stem.lower()
        genannt = len(stamm) >= 3 and stamm in frage_klein
        text_woerter = {w.lower() for w in _WORT.findall(a.text[:MAX_JE_DATEI])}
        treffer = len(woerter & text_woerter)
        bewertet.append((0 if genannt else 1, -treffer, e["name"], a))
    bewertet.sort(key=lambda x: (x[0], x[1], x[2]))
    out, rest = [], MAX_ZEICHEN
    for genannt, minus_treffer, name, a in bewertet[:hoechstens]:
        if not genannt and -minus_treffer == 0 and len(bewertet) > hoechstens:
            continue
        t = a.text[:min(MAX_JE_DATEI, rest)]
        if not t:
            break
        rest -= len(t)
        out.append({"name": name, "info": a.info, "text": t, "gekuerzt": len(t) < len(a.text)})
    return out


def vorspann(ordner_name: str, dateien: list[dict], alle: list[dict]) -> str:
    namen = ", ".join(e["name"] for e in alle[:MAX_DATEIEN]) or "(leer)"
    kopf = (f"Die Person hat den Ordner „{ordner_name}“ freigegeben. Darin liegen: {namen}. "
            "Beziehe dich auf die mitgelesenen Dateien, wenn die Frage dazu passt, sag „laut Datei …“, und erfinde nichts, was nicht darin steht. "
            "Du kannst nichts im Ordner ändern; wenn die Person etwas gespeichert haben will, schreib den fertigen Text, sie speichert ihn mit einem Klick.")
    if not dateien:
        return kopf
    teile = [f"Datei „{d['name']}“ ({d['info']}):\n{d['text']}" + ("\n[… gekürzt]" if d.get("gekuerzt") else "") for d in dateien]
    return kopf + "\n\n" + "\n\n".join(teile)


def dateiname(name: str, *, endung: str = ".md") -> str:
    n = re.sub(r"[^\w .\-äöüÄÖÜß]", "", (name or "").strip())[:80].strip(" .")
    if not n:
        n = "Antwort"
    if not n.lower().endswith(ENDUNGEN_SCHREIBEN):
        n += endung
    return n


def speichern(pfad: Path, name: str, text: str) -> Path:
    p = pruefen(pfad)
    if len(text or "") > MAX_SCHREIBEN:
        raise app_core.AppError("ORDNER_GROSS", "der Text ist zu lang zum Speichern")
    n = dateiname(name)
    ziel = p / n
    i = 2
    while ziel.exists():
        ziel = p / f"{Path(n).stem} ({i}){Path(n).suffix}"
        i += 1
    if ziel.resolve().parent != p:
        raise app_core.AppError("ORDNER_WEG", "der Name führt aus dem Ordner hinaus")
    try:
        sicher_schreiben.text(ziel, (text or "").rstrip() + "\n")
    except OSError as exc:
        raise app_core.AppError("ORDNER_SCHREIBEN", f"in diesen Ordner kann nicht geschrieben werden ({exc.__class__.__name__})") from None
    _cache.clear()
    return ziel


__all__ = ["pruefen", "uebersicht", "auswahl", "vorspann", "speichern", "dateiname", "MAX_LESEN"]
