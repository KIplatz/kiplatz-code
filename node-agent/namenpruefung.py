# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

import wissen

_NAME_TEIL = re.compile(r"[\wäöüÄÖÜß]+(?:[-'][\wäöüÄÖÜß]+)*")
FACHBEGRIFF_ENDE = frozenset("""theorem satz lemma gesetz prinzip effekt paradoxon skala index modell methode verfahren syndrom krankheit formel
gleichung konstante regel algorithmus hypothese kriterium kurve zahl test diagramm schema zyklus reaktion verordnung theorie""".split())
_EIGENE_NAMEN = {"kiplatz", "platzl"}


def _name_kandidat(wort: str, *, nachbar: bool = False) -> bool:
    if len(wort) < (2 if nachbar else 4) or wort.lower() in wissen._STOPP or wort.lower() in _EIGENE_NAMEN:
        return False
    if not wort[:1].isupper() and not any(c.isupper() for c in wort[1:]) and not (not nachbar and any(c.isdigit() for c in wort) and any(c.isalpha() for c in wort)):
        return False
    return not wort.isdigit()


class Namenspruefung:

    def namen_bekannt(self, namen: list[str]) -> set[str]:
        if not namen or not self.hat_wortzahl():
            return set()
        out: set[str] = set()
        for n in namen:
            worte = [w for w in re.split(r"[\s\-]+", str(n)) if w]
            stamm = self._woerter(str(n))
            if worte and stamm and all(self._df(s) > 0 for s in stamm) and not any(self._erfundene_zusammensetzung(w) for w in worte):
                out.add(n)
        return out

    def unbekannte_namen(self, text: str, hoechstens: int = 2) -> list[str]:
        if not text or not self.hat_wortzahl():
            return []
        treffer = list(_NAME_TEIL.finditer(text))
        worte = [m.group(0) for m in treffer]
        namen: list[str] = []
        for i, w in enumerate(worte):
            if not _name_kandidat(w):
                continue
            vorne = text[:treffer[i].start()].rstrip()
            if (not vorne or vorne[-1] in ".!?:;\n") and not any(c.isupper() or c.isdigit() for c in w[1:]):
                continue
            stamm = self._woerter(w)
            if not stamm or (any(self._df(s) > 0 for s in stamm) and not self._erfundene_zusammensetzung(w)):
                continue
            von = i
            while von > 0 and i - von < 2 and _name_kandidat(worte[von - 1], nachbar=True):
                vor = text[:treffer[von - 1].start()].rstrip()
                if not vor or vor[-1] in ".!?:;\n":
                    break
                von -= 1
            if von == i and not any(c.isupper() or c.isdigit() for c in w[1:]):
                continue
            name = " ".join(worte[von:i + 1])
            if name not in namen and not any(name in n or n in name for n in namen):
                namen.append(name)
            if len(namen) >= hoechstens:
                break
        return namen

    def _erfundene_zusammensetzung(self, wort: str) -> bool:
        teile = [t for t in str(wort or "").split("-") if t]
        if len(teile) < 2 or not teile[0][:1].isupper():
            return False
        for t in teile:
            if len(t) >= 4 and t[:1].isupper():
                stamm = self._woerter(t)
                if stamm and all(self._df(s) == 0 for s in stamm):
                    return True
        return teile[-1].lower() in FACHBEGRIFF_ENDE and self.artikel_zu(wort) is None


__all__ = ["Namenspruefung", "FACHBEGRIFF_ENDE"]
