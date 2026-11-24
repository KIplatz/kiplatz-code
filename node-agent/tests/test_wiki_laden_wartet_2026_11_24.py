# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quellen_stand
import wikipedia


class _Kopie:
    def __init__(self, fehler):
        k = _klasse()
        self.LADEN_NOCHMAL_S, self.LADEN_NOCHMAL_MAX_S, self.GROESSE_VERSUCHE = k.LADEN_NOCHMAL_S, k.LADEN_NOCHMAL_MAX_S, k.GROESSE_VERSUCHE
        self.fehler, self.phase, self.meldung, self.log = fehler, "laedt", "17/20", []

    def _teil_laden(self, *a):
        if self.fehler is None:
            return True
        raise self.fehler

    def _log(self, z):
        self.log.append(z)


def _klasse():
    return next(c for c in vars(wikipedia).values() if isinstance(c, type) and hasattr(c, "_laden_versuch"))


@pytest.mark.parametrize("fehler", [TimeoutError("The read operation timed out"), ConnectionResetError("reset"),
                                    urllib.error.URLError("getaddrinfo failed"), wikipedia.WikiError("WIKI_GROESSE", "Teil unvollständig"),
                                    wikipedia.WikiError("WIKI_HOLEN", "dumps.wikimedia.org antwortet nicht (TimeoutError)")])
def test_abgerissener_download_wartet(fehler):
    k = _Kopie(fehler)
    warten = _klasse()._laden_versuch(k, "https://dumps.wikimedia.org/x", Path("x"), 1, "17/20")
    assert warten == _klasse().LADEN_NOCHMAL_S and k.phase == "wartet" and "17/20" in k.meldung
    assert "wartet" in quellen_stand._LADE_PHASEN


def test_fertiger_teil_und_echter_fehler():
    assert _klasse()._laden_versuch(_Kopie(None), "https://dumps.wikimedia.org/x", Path("x"), 1, "17/20") is None
    with pytest.raises(wikipedia.WikiError):
        _klasse()._laden_versuch(_Kopie(wikipedia.WikiError("WIKI_ADRESSE", "nur von dumps.wikimedia.org")), "x", Path("x"), 1, "1/2")


def test_mb_zaehlen_als_fortschritt(tmp_path):
    t = [1_000_000.0]
    s = quellen_stand.Sammlung(tmp_path / "q.json", jetzt=lambda: t[0])

    def melden(mb):
        text = f"Wikipedia: noch keine fertige Kopie (wartet 17/20, {mb} MB von 570 MB, dumps.wikimedia.org antwortet langsam)."
        s.melden("g1", "PC", admin=True, quellen={"wikipedia": {"ok": False, "gilt": True, "laedt": True, "zahl": 2237145, "stand": "", "text": text}})
    for mb in range(10, 300, 40):
        t[0] += 3600
        melden(mb)
    assert not quellen_stand.still(s._geraete, t[0])
    t[0] += 7 * 3600
    melden(290)
    assert quellen_stand.still(s._geraete, t[0])


@pytest.mark.parametrize("fehler", [OSError(28, "No space left on device"), PermissionError("Zugriff verweigert"),
                                    urllib.error.HTTPError("https://dumps.wikimedia.org/x", 404, "Not Found", {}, None),
                                    wikipedia.WikiError("WIKI_HOLEN", "dumps.wikimedia.org antwortet nicht (HTTPError)")])
def test_echte_fehler_bleiben_fehler(fehler):
    with pytest.raises(type(fehler)):
        _klasse()._laden_versuch(_Kopie(fehler), "https://dumps.wikimedia.org/x", Path("x"), 1, "17/20")


def test_abstand_verdoppelt_sich_ohne_fortschritt_und_groesse_gibt_auf():
    k = _Kopie(TimeoutError("t"))
    w = [_klasse()._laden_versuch(k, "https://dumps.wikimedia.org/x", Path("gibt-es-nicht"), 1, "17/20") for _ in range(6)]
    assert w[0] == 120 and w[1] == 240 and w[-1] == _klasse().LADEN_NOCHMAL_MAX_S
    g = _Kopie(wikipedia.WikiError("WIKI_GROESSE", "Teil unvollständig"))
    for _ in range(_klasse().GROESSE_VERSUCHE - 1):
        _klasse()._laden_versuch(g, "https://dumps.wikimedia.org/x", Path("gibt-es-nicht"), 1, "17/20")
    with pytest.raises(wikipedia.WikiError):
        _klasse()._laden_versuch(g, "https://dumps.wikimedia.org/x", Path("gibt-es-nicht"), 1, "17/20")
