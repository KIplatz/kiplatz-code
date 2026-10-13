# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import app_core
import app_install
import app_web
import neuerungen
import rechenarbeit as ra
from test_app_web import _api


def test_error_texts_are_for_people_not_programmers(tmp_path):
    assert app_web.menschlich("KI_ANTWORT", "keine Antwort vom KI-Server (HTTP 500: failed to allocate)").startswith("Das Modell auf diesem Gerät hat nicht geantwortet")
    assert "HTTP" not in app_web.menschlich("XY", "keine Antwort vom KI-Server (HTTP 503: Loading model)")
    assert app_web.menschlich("XY", "die Datei fehlt (FileNotFoundError)") == "Das hat nicht geklappt: die Datei fehlt"
    assert app_web.menschlich("HAUSORDNUNG", "das gehört nicht hierher") == "Das hat nicht geklappt: das gehört nicht hierher"
    api, _fake, _ = _api(tmp_path)
    r = api._guarded("probe", lambda: (_ for _ in ()).throw(RuntimeError("kaputt")))
    assert not r["ok"] and "RuntimeError" not in r["text"] and "Fehler melden" in r["text"] and r["code"] == "UNERWARTET"
    r2 = api._guarded("probe2", lambda: (_ for _ in ()).throw(app_core.AppError("KI_START", "llama-server hat sich beendet (Code 3)")))
    assert not r2["ok"] and "Code 3" not in r2["text"] and r2["code"] == "KI_START"


def test_error_report_goes_to_the_admin_without_question_texts(tmp_path):
    api, _fake, _ = _api(tmp_path)
    geschickt = {}

    def fehlerbericht(bau, text, windows=""):
        geschickt.update(bau=bau, text=text, windows=windows)
        return "Danke."
    api._community.fehlerbericht = fehlerbericht
    api.js_fehler("TypeError: x is not a function @915")
    g = api.gespraech_neu()["daten"]
    api.frage(g["kennung"], "Wie heißt der Bürgermeister von Gmunden?")
    r = api.fehlerbericht_senden("TypeError @915")
    assert r["ok"] and geschickt["bau"] == app_core.APP_BUILD and "Bürgermeister" not in geschickt["text"]
    assert "FEHLER oberflaeche: TypeError" in geschickt["text"] and "Oberfläche: TypeError @915" in geschickt["text"] and len(geschickt["text"]) <= 7800


def test_first_start_keeps_the_chosen_device_name_and_shows_once(tmp_path):
    api, _fake, _ = _api(tmp_path)
    assert api.zustand()["daten"]["erststart"] is True
    r = api.erststart_fertig("  Laptop   Anna  ")
    assert r["ok"] and r["daten"]["geraet_name"] == "Laptop Anna" and api._geraet_name == "Laptop Anna"
    z = api.zustand()["daten"]
    assert z["erststart"] is False and z["app"]["geraet_name"] == "Laptop Anna" and z["neu"] == []
    assert app_web._geraet_name(api._core) == "Laptop Anna"


def test_news_show_once_after_an_update(tmp_path):
    assert neuerungen.fuer(app_core.APP_BUILD), "every build that goes to the server needs its three sentences"
    api, _fake, _ = _api(tmp_path)
    api.erststart_fertig("x")
    api._ki.einstellung_setzen(gesehen_bau="2026-01-01a")
    neu = api.zustand()["daten"]["neu"]
    assert neu[:len(neuerungen.fuer(app_core.APP_BUILD))] == neuerungen.fuer(app_core.APP_BUILD) and len(neu) <= 8 and len(neu) > len(neuerungen.fuer(app_core.APP_BUILD))
    api.neu_gesehen()
    assert api.zustand()["daten"]["neu"] == []
    baue = sorted(neuerungen.NEUERUNGEN)
    assert neuerungen.seit(baue[-3], baue[-1]) == neuerungen.NEUERUNGEN[baue[-1]] + neuerungen.NEUERUNGEN[baue[-2]]
    assert neuerungen.seit(baue[-2], baue[-1]) == neuerungen.NEUERUNGEN[baue[-1]]
    assert neuerungen.seit(None, baue[-1]) == neuerungen.NEUERUNGEN[baue[-1]] and neuerungen.seit(baue[-1], baue[-1]) == []


def test_windows_apps_entry_and_start_menu_values():
    w = app_install.apps_eintrag_werte(Path("C:/Programme/CommunityAI"), "0.4", "2026-09-19k")
    assert w["DisplayName"] == app_core.APP_NAME and "Bau 2026-09-19k" in w["DisplayVersion"]
    assert w["UninstallString"].endswith('app_web.py" --entfernen') and "pythonw.exe" in w["UninstallString"]
    assert w["DisplayIcon"].endswith(app_install.START_NAME) and w["NoModify"] == "1"
    if sys.platform == "win32":
        assert app_install.startmenue_dir() is not None and app_install.startmenue_dir().name == "Programs"


def test_on_battery_the_loop_pauses_and_says_so(tmp_path):
    api, _fake, _ = _api(tmp_path)
    r = api._rechen
    log = []
    r._log = log.append
    r._schlafen = lambda s: None
    r._anmelden = lambda: True
    r._am_strom = lambda: False
    r._eine_runde()
    assert r.phase == "akku" and "Akku" in r.meldung and any("akku" in z for z in log)
    assert "Akku" in ra.TEXTE["akku"] and ra.am_strom_windows() in (True, False)


def test_neuerungen_ohne_admin_saetze():
    import re
    import neuerungen
    admin = re.compile(r"Admin-Seite|Für Admins|Für den Admin|Nachschub-Karte|Karte „Nachschub|Fehlerberichte", re.I)
    for bau, saetze in neuerungen.NEUERUNGEN.items():
        for satz in saetze:
            assert not admin.search(satz), (bau, satz[:80])
    assert neuerungen.NEUERUNGEN["2026-09-23zc"] == ["Allgemeine Optimierungen wurden durchgeführt."]
