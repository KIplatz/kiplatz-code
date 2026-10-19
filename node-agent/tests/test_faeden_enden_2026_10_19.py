# SPDX-License-Identifier: AGPL-3.0-or-later
import threading
import time

import quellen_stand
from test_app_web import _api


def _faeden(name: str) -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == name and t.is_alive()]


def test_ein_ersetztes_time_sleep_faengt_keinen_faden_des_programms(tmp_path, monkeypatch):
    monkeypatch.setattr(quellen_stand, "MELDEN_ABSTAND_S", 0.02)
    api, _fake, _ = _api(tmp_path)
    assert _faeden("quellen-melden"), "vorbereiten startet die Quellen-Wache"
    schlaf: list = []
    monkeypatch.setattr(time, "sleep", schlaf.append)
    threading.Event().wait(0.3)
    assert quellen_stand.MELDEN_ABSTAND_S not in schlaf, f"ein Faden des Programms schläft mit time.sleep: {schlaf[:5]}"
    api.herunterfahren()


def test_herunterfahren_beendet_jede_schleife_im_hintergrund(tmp_path):
    api, _fake, _ = _api(tmp_path)
    api.HEIMNETZ_WARTE_S = 30.0
    api._anbieten_spaeter()
    api._update_im_hintergrund()
    namen = ("quellen-melden", "heimnetz-spaeter", "update-pruefen")
    assert all(_faeden(n) for n in namen)
    t0 = time.monotonic()
    api.herunterfahren()
    for n in namen:
        for t in _faeden(n):
            t.join(timeout=5)
    assert not any(_faeden(n) for n in namen), [t.name for t in threading.enumerate()]
    assert time.monotonic() - t0 < 5, "die Fäden warten nicht ihre volle Zeit ab, sie enden sofort"
    assert api.schliessen_angefordert


def test_beenden_im_menue_weckt_die_faeden_sofort(tmp_path):
    api, _fake, _ = _api(tmp_path)
    assert _faeden("quellen-melden")
    assert api.beenden()["ok"]
    for t in _faeden("quellen-melden"):
        t.join(timeout=2)
    assert not _faeden("quellen-melden")
