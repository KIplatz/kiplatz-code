# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
