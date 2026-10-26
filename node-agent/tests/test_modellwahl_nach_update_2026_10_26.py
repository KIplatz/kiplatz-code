# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import app_core
import app_web
import ki_laufzeit as kl

KARTE = "  Vulkan0: AMD Radeon RX 7800 XT (16368 MiB, 16000 MiB free)\n"


class _Kern:
    def __init__(self, tmp):
        self.base_dir = Path(tmp)
        self.diagnosis_dir = Path(tmp) / "diagnose"

    def ensure_directories(self):
        self.diagnosis_dir.mkdir(parents=True, exist_ok=True)

    def zeilen(self):
        p = self.diagnosis_dir / "protokoll.txt"
        return p.read_text(encoding="utf-8") if p.is_file() else ""


def _steuerung(tmp_path, monkeypatch, fremd_folge):
    folge = list(fremd_folge)
    monkeypatch.setattr(kl, "fremd_mib", lambda g: folge[0] if len(folge) == 1 else folge.pop(0))
    k = object.__new__(app_web.KiSteuerung)
    k._core = _Kern(tmp_path)
    k.ordner = type("O", (), {"server_exe": Path("x")})()
    k._geraete_ermitteln = lambda exe: kl.geraete_parsen(KARTE)
    k.fortschritt = {}
    t = [0.0]
    k._uhr = lambda: t[0]
    k._schlafen = lambda s: t.__setitem__(0, t[0] + s)
    return k, t


def test_nach_dem_update_wartet_der_start_bis_die_karte_frei_ist(tmp_path, monkeypatch):
    k, t = _steuerung(tmp_path, monkeypatch, [9000, 9000, 9000, 1200])
    erste = kl.waehlen(k._geraete_ermitteln(None), 32.0)
    assert erste.modell.kennung == "8B"
    w = k._wahl_mit_geduld(erste, 32.0)
    assert w.modell.kennung == "14B" and t[0] <= k.START_WARTEN_S
    assert "14B statt 8B" in k._core.zeilen()


def test_bleibt_die_karte_voll_geht_es_nach_der_frist_mit_dem_kleineren_weiter(tmp_path, monkeypatch):
    k, t = _steuerung(tmp_path, monkeypatch, [9000])
    w = k._wahl_mit_geduld(kl.waehlen(k._geraete_ermitteln(None), 32.0), 32.0)
    assert w.modell.kennung == "8B" and t[0] >= k.START_WARTEN_S and "weiter belegt" in k._core.zeilen()


def test_eine_freie_karte_wartet_keinen_augenblick_und_nur_der_erste_start_wartet(tmp_path, monkeypatch):
    k, t = _steuerung(tmp_path, monkeypatch, [1200])
    w = k._wahl_mit_geduld(kl.waehlen(k._geraete_ermitteln(None), 32.0), 32.0)
    assert w.modell.kennung == "14B" and t[0] == 0.0
    k2, t2 = _steuerung(tmp_path, monkeypatch, [9000])
    k2._geduld_genutzt = True
    assert k2._wahl_mit_geduld(kl.waehlen(k2._geraete_ermitteln(None), 32.0), 32.0).modell.kennung == "8B" and t2[0] == 0.0


def test_eine_kleine_karte_wartet_nie(tmp_path, monkeypatch):
    k, t = _steuerung(tmp_path, monkeypatch, [0])
    k._geraete_ermitteln = lambda exe: kl.geraete_parsen("  Vulkan0: NVIDIA GeForce RTX 4050 Laptop GPU (6144 MiB, 6000 MiB free)\n")
    w = k._wahl_mit_geduld(kl.waehlen(k._geraete_ermitteln(None), 16.0), 16.0)
    assert w.modell.kennung == "3B" or w.modell.kennung == "8B"
    assert t[0] == 0.0


def test_der_grund_der_wahl_steht_im_protokoll():
    src = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert '+ f" ({wahl.grund})")' in src and "self._wahl_mit_geduld(wahl" in src
    assert app_core is not None
