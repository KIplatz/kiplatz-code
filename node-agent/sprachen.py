# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import re
from pathlib import Path

KATALOG_DATEI = Path(__file__).with_name("sprache_dienst_en.json")
FELDER = ("text", "hinweis", "grund", "titel")

_genau: dict[str, str] = {}
_muster: list[tuple[re.Pattern, str, list[int]]] = []
_geladen = False


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def laden(katalog: dict | None = None) -> None:
    global _geladen
    if katalog is None:
        try:
            katalog = json.loads(KATALOG_DATEI.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            katalog = {}
    _genau.clear()
    _muster.clear()
    for de, en in katalog.items():
        if not isinstance(en, str) or not en.strip():
            continue
        k = _norm(de)
        if re.search(r"\{\d+\}", k):
            if len(re.findall(r"[A-Za-zÄÖÜäöüß]", re.sub(r"\{\d+\}", "", k))) < 4:
                continue
            teile = re.split(r"\{(\d+)\}", k)
            re_text, reihe = "^", []
            for i, t in enumerate(teile):
                if i % 2:
                    re_text += "(.+?)"
                    reihe.append(int(t))
                else:
                    re_text += re.escape(t)
            _muster.append((re.compile(re_text + "$", re.S), en, reihe))
        else:
            _genau[k] = en
    _muster.sort(key=lambda m: -len(m[0].pattern.replace("(.+?)", "")))
    _geladen = True


def englisch(accept_language: str | None) -> bool:
    erste = (accept_language or "").split(",")[0].split(";")[0].strip().lower()
    return bool(erste) and erste != "*" and not erste.startswith("de")


def uebersetzen(text: str, vorlagen: bool = True) -> str:
    if not _geladen:
        laden()
    kern = _norm(text)
    en = _genau.get(kern)
    if en is not None:
        return en
    for re_text, e, reihe in (_muster if vorlagen else []):
        m = re_text.match(kern)
        if m:
            werte = {n: m.group(i + 1) for i, n in enumerate(reihe)}
            return re.sub(r"\{(\d+)\}", lambda z: werte.get(int(z.group(1)), ""), e)
    return text


def antwort(obj: dict, status: int = 400) -> dict:
    neu = dict(obj)
    for f in FELDER:
        if isinstance(neu.get(f), str) and neu[f]:
            neu[f] = uebersetzen(neu[f], vorlagen=status >= 400)
    return neu
