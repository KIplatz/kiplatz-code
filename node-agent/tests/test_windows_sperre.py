# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setattr(kl, "_windows_sperre_bis", 0.0)


def _gesperrt(*_a, **_k):
    e = OSError(22, "Eine Anwendungssteuerungsrichtlinie hat diese Datei blockiert")
    e.winerror = 4551
    raise e


def test_die_sperre_wird_erkannt_und_30_minuten_nicht_mehr_versucht(tmp_path):
    aufrufe = []

    def runner(*a, **k):
        aufrufe.append(a)
        _gesperrt()
    with pytest.raises(kl.KiError) as e:
        kl.geraete_ermitteln(tmp_path / "llama-server.exe", runner=runner)
    assert e.value.code == "KI_BLOCKIERT" and "Smart App Control" in e.value.detail and "Community" in e.value.detail
    assert kl.windows_sperre_aktiv()
    for _ in range(5):
        with pytest.raises(kl.KiError) as e:
            kl.geraete_ermitteln(tmp_path / "llama-server.exe", runner=runner)
        assert e.value.code == "KI_BLOCKIERT"
    assert len(aufrufe) == 1
    assert not kl.windows_sperre_aktiv(jetzt=kl._windows_sperre_bis + 1)


def test_ein_anderer_fehler_ist_keine_sperre(tmp_path):
    def runner(*a, **k):
        raise FileNotFoundError(2, "fehlt")
    with pytest.raises(kl.KiError) as e:
        kl.geraete_ermitteln(tmp_path / "llama-server.exe", runner=runner)
    assert e.value.code == "KI_GERAETE" and not kl.windows_sperre_aktiv()


def test_auch_der_start_des_modells_haelt_die_pause_ein(tmp_path):
    kl._windows_sperre_bis = 9e18
    srv = kl.KiServer(kl.KiOrdner(tmp_path))
    with pytest.raises(kl.KiError) as e:
        srv.start(kl.Wahl(None, kl.MODELLE["3B"], "Probe"))
    assert e.value.code == "KI_BLOCKIERT"


def test_eine_gesperrte_dll_zaehlt_auch_als_sperre(tmp_path):
    class R:
        returncode, stdout, stderr = 3236495362, "", ""
    aufrufe = []
    with pytest.raises(kl.KiError) as e:
        kl.geraete_ermitteln(tmp_path / "llama-server.exe", runner=lambda *a, **k: aufrufe.append(a) or R())
    assert e.value.code == "KI_BLOCKIERT" and kl.windows_sperre_aktiv()
    with pytest.raises(kl.KiError):
        kl.geraete_ermitteln(tmp_path / "llama-server.exe", runner=lambda *a, **k: aufrufe.append(a) or R())
    assert len(aufrufe) == 1
