# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

import rechenarbeit

rechenarbeit.Rechenarbeit._gpu_werkzeug = None
rechenarbeit.Rechenarbeit._ram_standard = staticmethod(lambda: None)
rechenarbeit.Rechenarbeit.warten_arbeit_s = 0.0

import ki_laufzeit

ki_laufzeit.UNTERSCHRIFT_PRUEFEN = False
ki_laufzeit.KARTE_ZAEHLER = False
import app_web

app_web.PRUEFSTAND_ABSTAND_S = 0.0

import tempfile

import kartenteiler
import pytest

import atexit
import shutil

_KARTE_FALLBACK = Path(tempfile.mkdtemp(prefix="kiplatz-karte-"))
kartenteiler.ORDNER = _KARTE_FALLBACK
atexit.register(shutil.rmtree, _KARTE_FALLBACK, ignore_errors=True)

import geheim

_GEHEIM = Path(tempfile.mkdtemp(prefix="kiplatz-geheim-"))
geheim.ORDNER = _GEHEIM / "geheim"
geheim.BUND_AN = False
atexit.register(shutil.rmtree, _GEHEIM, ignore_errors=True)


@pytest.fixture(autouse=True)
def _karte_leer(tmp_path):
    ki_laufzeit._BELEGT.clear()
    alt = kartenteiler.ORDNER
    kartenteiler.ORDNER = tmp_path / "karte"
    yield
    kartenteiler.ORDNER = alt
    ki_laufzeit._BELEGT.clear()


@pytest.fixture(autouse=True)
def _eigen_zuruecksetzen():
    if hasattr(app_web._EIGEN, "an"):
        del app_web._EIGEN.an
    yield
    if hasattr(app_web._EIGEN, "an"):
        del app_web._EIGEN.an


import threading
import time

_LEERLAUF_ECHT = rechenarbeit.node_idle_detector.get_idle_seconds
_LEERLAUF_ALT = rechenarbeit.Rechenarbeit._leerlauf_windows
_ECHTE_TASTATUR: list[str] = []


def _leerlauf_test(self):
    if rechenarbeit.node_idle_detector.get_idle_seconds is not _LEERLAUF_ECHT:
        return _LEERLAUF_ALT(self)
    if threading.current_thread() is threading.main_thread():
        _ECHTE_TASTATUR.append("_leerlauf_windows")
    return 10.0 ** 6


rechenarbeit.Rechenarbeit._leerlauf_windows = _leerlauf_test


MESS_SCHLAF_MAX_S = 5.0
_LANG_GESCHLAFEN: list[float] = []
_API_INIT = app_web.Api.__init__


_PROGRAMME: list = []


def _api_init_test(self, *a, **k):
    _API_INIT(self, *a, **k)
    _PROGRAMME.append(self)

    def schlafen(s: float) -> None:
        if s > MESS_SCHLAF_MAX_S:
            _LANG_GESCHLAFEN.append(s)
            return
        time.sleep(s)
    self._mess_schlafen = schlafen


app_web.Api.__init__ = _api_init_test


@pytest.fixture(autouse=True)
def _programme_herunterfahren():
    _PROGRAMME.clear()
    yield
    while _PROGRAMME:
        _PROGRAMME.pop().herunterfahren()


@pytest.fixture(autouse=True)
def _kein_langer_mess_schlaf(request):
    _LANG_GESCHLAFEN.clear()
    yield
    lang, _LANG_GESCHLAFEN[:] = list(_LANG_GESCHLAFEN), []
    assert not lang, (f"{request.node.nodeid} wollte im Takt der Prüfnacht {lang} s wirklich schlafen. Dem Test `api._mess_schlafen = …` "
                      f"geben (17.10.2026: so wartete test_bau_05m 120 s je Prüflauf).")


@pytest.fixture(autouse=True)
def _keine_echte_tastatur(request):
    _ECHTE_TASTATUR.clear()
    yield
    gelesen, _ECHTE_TASTATUR[:] = list(_ECHTE_TASTATUR), []
    assert not gelesen, (f"{request.node.nodeid} liest die echte Tastatur und Maus (Leerlauf-Messung). Dem Test leerlauf_s=… oder "
                         f"_jemand_am_pc geben, sonst hängt er, solange jemand am Laptop arbeitet (14.10.2026).")
