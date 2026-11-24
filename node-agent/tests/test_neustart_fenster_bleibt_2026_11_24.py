# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
from test_app_web import _api


def _darf_zu(api):
    return api.schliessen_angefordert and not getattr(api, "_neustart_laeuft", False)


def test_fenster_bleibt_offen_bis_die_neue_kopie_laeuft(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    ablauf = []
    echt_herunter = api.herunterfahren

    def langsam_herunter():
        echt_herunter()
        ablauf.append(("herunter", _darf_zu(api)))
    monkeypatch.setattr(api, "herunterfahren", langsam_herunter)
    echt = app_web.subprocess.Popen

    def popen(befehl, *a, **k):
        if str(befehl[0]).startswith(str(api._install_dir)):
            ablauf.append(("neu gestartet", _darf_zu(api)))
            return None
        return echt(befehl, *a, **k)
    monkeypatch.setattr(app_web.subprocess, "Popen", popen)
    monkeypatch.setattr(app_web.einmal, "freigeben", lambda: None)
    api._neu_starten()
    assert ablauf == [("herunter", False), ("neu gestartet", False)]
    assert _darf_zu(api)


def test_scheitert_der_start_geht_das_fenster_trotzdem_zu(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    echt = app_web.subprocess.Popen

    def popen(befehl, *a, **k):
        if str(befehl[0]).startswith(str(api._install_dir)):
            raise OSError("Datei fehlt")
        return echt(befehl, *a, **k)
    monkeypatch.setattr(app_web.subprocess, "Popen", popen)
    monkeypatch.setattr(app_web.einmal, "freigeben", lambda: None)
    try:
        api._neu_starten()
    except OSError:
        pass
    assert _darf_zu(api)
