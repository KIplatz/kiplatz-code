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
            if von == i and not any(c.isupper() or c.isdigit() for c in w[1:]) and (len(w) < 7 or self._zerlegbar(w)):
                continue
            name = " ".join(worte[von:i + 1])
            namen = [n for n in namen if n not in name]
            if not any(name in n for n in namen):
                namen.append(name)
            if len(namen) >= hoechstens:
                break
        return namen

    def _zerlegbar(self, wort: str, teile: int = 4) -> bool:
        w = str(wort or "").lower()
        if teile <= 0 or len(w) < 4:
            return False
        for k in range(4, len(w) - 2):
            vorne = w[:k]
            if not (self._bekannt(vorne) or (vorne.endswith("s") and self._bekannt(vorne[:-1]))):
                continue
            rest = w[k:]
            if self._bekannt(rest) or self._zerlegbar(rest, teile - 1):
                return True
        return False

    def _ganz_bekannt(self, wort: str) -> bool:
        return False

    def _bekannt(self, stueck: str) -> bool:
        stamm = self._woerter(stueck)
        return bool(stamm) and all(self._df(s) > 0 for s in stamm)

    def unsichere_namen(self, text: str, hoechstens: int = 2) -> list[str]:
        if not text or not self.hat_wortzahl():
            return []
        treffer = list(_NAME_TEIL.finditer(text))
        worte = [m.group(0) for m in treffer]
        namen: list[str] = []
        for i, w in enumerate(worte):
            if not _name_kandidat(w):
                continue
            vorne = text[:treffer[i].start()].rstrip()
            if not vorne or vorne[-1] in ".!?:;\n":
                continue
            stamm = self._woerter(w)
            if not stamm or not all(self._df(s) > 0 for s in stamm):
                continue
            name = self._er_name(worte, treffer, text, i)
            if name and not any(name in n or n in name for n in namen):
                namen.append(name)
                if len(namen) >= hoechstens:
                    break
        return namen

    def _er_name(self, worte: list[str], treffer: list, text: str, i: int) -> str:
        w = worte[i]
        if len(w) < 7 or not w.lower().endswith("er") or any(c.isupper() for c in w[1:]) or self._ganz_bekannt(w):
            return ""
        vorne = text[:treffer[i].start()].rstrip()
        von = i - 1 if i > 0 and _name_kandidat(worte[i - 1], nachbar=True) and vorne and vorne[-1] not in ".!?:;\n" else i
        if von < i:
            vor = text[:treffer[von].start()].rstrip()
            if not vor or vor[-1] in ".!?:;\n":
                von = i
        bis = i + 1 if i + 1 < len(worte) and _name_kandidat(worte[i + 1], nachbar=True) and text[treffer[i].end():treffer[i + 1].start()].strip() == "" else i
        if von == i and bis == i:
            return ""
        name = " ".join(worte[von:bis + 1])
        if self.artikel_zu(w) is not None or self.artikel_zu(name) is not None:
            return ""
        return name

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
