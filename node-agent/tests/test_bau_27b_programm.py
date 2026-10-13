# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_install
import app_web


def test_blockierte_datei_findet_nichts_wenn_nichts_offen_ist(tmp_path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "unter").mkdir()
    (tmp_path / "unter" / "b.pyc").write_bytes(b"y")
    assert app_install.blockierte_datei(tmp_path) == ""


def test_blockierte_datei_nennt_die_datei(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "b.py").write_text("y", encoding="utf-8")
    echt = os.open

    def offen(p, *a, **k):
        if str(p).endswith("b.py"):
            raise PermissionError(13, "Der Prozess kann nicht auf die Datei zugreifen")
        return echt(p, *a, **k)

    monkeypatch.setattr(os, "open", offen)
    assert app_install.blockierte_datei(tmp_path) == "b.py"


def test_ordner_ersetzen_meldet_den_schuldigen(tmp_path, monkeypatch):
    ziel = tmp_path / "node-agent"; ziel.mkdir(); (ziel / "app_web.py").write_text("alt", encoding="utf-8")
    neu = tmp_path / "neu"; neu.mkdir(); (neu / "app_web.py").write_text("neu", encoding="utf-8")
    echt_replace = os.replace

    def klemmt(a, b):
        if str(a) == str(ziel):
            raise PermissionError(13, "Der Prozess kann nicht auf die Datei zugreifen, da sie von einem anderen Prozess verwendet wird")
        return echt_replace(a, b)

    monkeypatch.setattr(os, "replace", klemmt)
    monkeypatch.setattr(app_install, "blockierte_datei", lambda ordner: "wissen.sqlite")
    try:
        app_install._ordner_ersetzen(neu, ziel)
    except OSError as exc:
        assert "in Verwendung: wissen.sqlite" in exc.strerror
    else:
        raise AssertionError("der Fehler muss durchkommen")
    assert (ziel / "app_web.py").read_text(encoding="utf-8") == "alt"


def test_hintergrund_check_wiederholt_nach_tausch_fehler():
    assert app_web.Api.UPDATE_TAUSCH_WARTE_S < app_web.Api.UPDATE_TAKT_S and app_web.Api.UPDATE_TAUSCH_VERSUCHE >= 1


def test_statuszeile_wird_nach_dem_ki_start_geleert(monkeypatch):
    monkeypatch.setattr(app_web.time, "sleep", lambda s: None)

    class Ki:
        fortschritt = {"was": "KIplatz (großes Modell) wird auf AMD Radeon RX 7800 XT gestartet", "done": 0, "gesamt": 0}
        phase = "starten"
        meldung = ""
        stand = [False, False, True]

        def bereit(self):
            return self.stand.pop(0)

        def quelle(self):
            return "lokal"

        def einschalten(self):
            return True

    api = app_web.Api.__new__(app_web.Api)
    api._ki = Ki()
    api._window = object()
    js = []
    api._js = js.append
    api._ki_bereit_machen()
    assert js[0].startswith("app.hinweis(") and "wird auf AMD Radeon" in js[0]
    assert js[-1] == 'app.hinweis("")'
