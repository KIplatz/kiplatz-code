# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import threading

import app_core
import app_install
import app_web
import dateisuche
import bedeutung
import community
import ki_laufzeit as kl


def _core(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "basis")
    core.ensure_directories()
    return core


class _FakeServer:

    def __init__(self, ordner):
        self.ordner = ordner
        self._on = False
        self.wahl = None
        self.fragen = []
        self.stopped = 0
        self.abbruch = threading.Event()

    def laeuft(self):
        return self._on

    def start(self, wahl, **kw):
        self._on = True
        self.wahl = wahl
        self.start_kw = kw

    def stop(self):
        self._on = False
        self.stopped += 1

    def vektoren(self, texte, **kw):
        import hashlib
        import math
        out = []
        for t in texte:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            raw = [((h[i % 32] + i * 7) % 97) / 97.0 - 0.5 for i in range(1024)]
            n = math.sqrt(sum(x * x for x in raw))
            out.append([x / n for x in raw])
        return out

    def frage(self, nachrichten, *, on_token=None, **kw):
        self.fragen.append(nachrichten)
        if on_token:
            for piece in ("Servus", ", ", "Huber."):
                on_token(piece)
        return kl.Antwort("Servus, Huber.", 40, 3, 1.2)


def _api(tmp_path, *, geraete=None):
    core = _core(tmp_path)
    ordner = kl.KiOrdner(core.base_dir)
    ordner.anlegen()
    ordner.laufzeit_dir.mkdir(parents=True, exist_ok=True)
    ordner.server_exe.write_bytes(b"MZ")
    fake = _FakeServer(ordner)
    geraete = geraete if geraete is not None else kl.geraete_parsen("  Vulkan1: NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB, 7600 MiB free)\n")
    downloads = []

    def herunterladen(paket, ziel, *, fortschritt=None, **kw):
        downloads.append(paket.kennung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"x" * 10)
        if fortschritt:
            fortschritt(paket.groesse, paket.groesse)
        return ziel

    ki = app_web.KiSteuerung(core, server=fake, herunterladen=herunterladen, geraete_ermitteln=lambda exe: geraete)
    bd = bedeutung.Bedeutung(core, server=_FakeServer(ordner), herunterladen=herunterladen, geraete_ermitteln=lambda exe: geraete)
    api = app_web.Api(core, registry=app_install.MemoryRegistry(), ki=ki, geraet_name="Laptop-Test", install_dir=tmp_path / "Programme" / "CommunityAI", bedeutung_=bd)

    def kein_netz(req, timeout=0):
        raise OSError("kein Netz im Test")
    api._community = community.Community(core.base_dir, oeffner=kein_netz)
    (tmp_path / "Probe-Dokumente").mkdir(exist_ok=True)
    api._dateiliste = dateisuche.Dateiliste(lambda: [("Dokumente", tmp_path / "Probe-Dokumente")])
    api.vorbereiten(ki_auto=False)
    first = core.load_first_start()
    if first is not None:
        stark = first.__class__(**{**first.__dict__, "role": app_core.Role.COMPUTE_STRONG})
        core.load_first_start = lambda: stark
    return api, fake, downloads


def test_ki_starts_with_the_window_and_with_the_first_question(tmp_path):
    api, fake, _ = _api(tmp_path)
    assert api.zustand()["daten"]["ki_auto"] is True and api._ki.phase == "aus"
    g = api.gespraech_neu()["daten"]
    r = api.frage(g["kennung"], "hallo")
    assert r["ok"], r["text"]
    assert r["daten"]["text"] == "Servus, Huber." and api._ki.bereit()
    api.ki_ausschalten()
    assert api.ki_auto_setzen(False)["ok"] and api.zustand()["daten"]["ki_auto"] is False
    r = api.frage(g["kennung"], "hallo")
    assert r["ok"] and api._ki.bereit()
    api.ki_ausschalten()
    r = api.frage(g["kennung"], "hallo", ki_starten=False)
    assert not r["ok"] and "ausgeschaltet" in r["text"]
    api2, _fake2, _ = _api(tmp_path / "zwei")
    api2.vorbereiten(ki_auto=True)
    api2._ki._thread.join(timeout=10)
    assert api2._ki.bereit()


def test_state_start_pause_stop_and_freigabe_through_the_api(tmp_path):
    api, _fake, _dl = _api(tmp_path)
    z = api.zustand()
    assert z["ok"] and z["daten"]["lauf"]["zustand"] == "STOPPED" and z["daten"]["credits"]["guthaben"] == 100 and z["daten"]["ki"]["phase"] == "aus"
    assert z["daten"]["app"]["geraet_name"] == "Laptop-Test" and z["daten"]["app"]["quelle"] is True
    assert api.start()["daten"]["lauf"]["zustand"] == "ACTIVE" and api.pause()["daten"]["lauf"]["zustand"] == "PAUSED" and api.stopp()["daten"]["lauf"]["zustand"] == "STOPPED"
    f = api.freigabe_folgen(True, 50, 2)
    assert f["ok"] and "bleiben dir" in " ".join(f["daten"])
    s = api.freigabe_speichern(False, 50, 4)
    assert s["ok"] and s["daten"]["freigabe"] == {"nur_im_leerlauf": False, "cpu_prozent": 50, "ram_gib": 4, "speicher_mb": 500, "speicher_ort": "", "text": app_core.Freigabe(False, 50, 4).text_de()}
    assert api.freigabe_speichern(False, 50, 4, 0)["daten"]["freigabe"]["speicher_mb"] == 0 and "Auf der Festplatte hält es nichts für die Community." in api.freigabe_folgen(False, 50, 4, 0)["daten"]
    bad = api.freigabe_speichern(True, 0, 4)
    assert not bad["ok"] and "nicht geklappt" in bad["text"]
    proto = (api._core.diagnosis_dir / "protokoll.txt").read_text(encoding="utf-8")
    assert "OK start" in proto and "ABGELEHNT save_freigabe" in proto


def test_ki_switch_on_downloads_model_with_pinned_hash_picks_card_and_answers_with_lieferschein(tmp_path):
    api, fake, downloads = _api(tmp_path)
    assert api.frage("x", "hallo")["ok"] is False
    r = api.ki_einschalten()
    assert r["ok"] and "eingeschaltet" in r["text"]
    api._ki._thread.join(timeout=10)
    z = api._ki.zustand()
    assert z["phase"] == "bereit" and z["laeuft"] and z["modell"] == "Ministral 3 8B" and "RTX 4060" in z["geraet"]
    assert downloads[0] == "8B" and set(downloads) <= {"8B", "8B-bilder", kl.EMBEDDING.kennung}
    assert not api.ki_einschalten()["ok"]
    g = api.gespraech_neu()["daten"]
    pieces = []
    api._window = type("W", (), {"evaluate_js": staticmethod(lambda code: pieces.append(code))})()
    a = api.frage(g["kennung"], "Wie heißt du?")
    schritte = [x for x in pieces if x.startswith("app.schritt(")]
    pieces = [x for x in pieces if not x.startswith("app.schritt(")]
    assert a["ok"] and a["daten"]["text"] == "Servus, Huber." and len(pieces) == 3 and pieces[0].startswith("app.token(")
    assert any("schreibt die Antwort" in x for x in schritte)
    ls = a["daten"]["lieferschein"]
    assert ls["modell"] == "Ministral 3 8B" and ls["wortstuecke"] == 3 and ls["dauer_s"] == 1.2 and "ohne Quelle" in ls["erfunden"] and ls["pruefung"]["gruen"] == 0 and "Stand 100" in ls["credits"]
    assert a["daten"]["credits"]["guthaben"] == 100 and a["daten"]["credits"]["verdient"] == 1 and a["daten"]["credits"]["ausgegeben"] == 1
    assert fake.fragen[0][-1] == {"role": "user", "content": "Wie heißt du?"}
    geladen = api.gespraech_laden(g["kennung"])["daten"]
    assert [n["rolle"] for n in geladen["nachrichten"]] == ["user", "assistant"] and geladen["titel"] == "Wie heißt du?"
    assert api.gespraeche_liste()["daten"][0]["kennung"] == g["kennung"]
    off = api.ki_ausschalten()
    assert off["ok"] and fake.stopped == 1 and api._ki.zustand()["phase"] == "aus"


def test_ki_switch_on_without_card_and_download_failure_is_reported(tmp_path):
    api, fake, _dl = _api(tmp_path, geraete=())
    api._ki._herunterladen = lambda paket, ziel, **kw: (_ for _ in ()).throw(kl.KiError("KI_PRUEFSUMME", f"{paket.name}: Prüfsumme stimmt nicht"))
    api.ki_einschalten()
    api._ki._thread.join(timeout=10)
    z = api._ki.zustand()
    assert z["phase"] == "fehler" and "Prüfsumme" in z["meldung"] and not z["laeuft"]
    assert "ABGELEHNT ki_einschalten" in (api._core.diagnosis_dir / "protokoll.txt").read_text(encoding="utf-8")


def test_settings_diagnosis_autostart_uninstall_about(tmp_path, monkeypatch):
    api, _fake, _dl = _api(tmp_path)
    d = api.diagnose()
    assert d["ok"] and d["daten"].startswith("diagnose-")
    a = api.autostart_setzen(True)
    assert not a["ok"] and "Programmdatei" in a["text"]
    exe = tmp_path / "quelle" / "CommunityAI.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(app_install, "running_exe", lambda: exe)
    what, _info = app_install.ensure_installed(exe, tmp_path / "Programme" / "CommunityAI")
    assert what == "eingerichtet" and api.zustand()["daten"]["einrichtung"]["installiert"] is True
    assert api.autostart_setzen(True)["daten"] is True and api.zustand()["daten"]["einrichtung"]["autostart"] is True
    assert api.autostart_setzen(False)["daten"] is False
    u = api.ueber()
    assert u["ok"] and "Apache-2.0" in u["daten"]["lizenzen"]
    assert u["daten"]["version"] == f"{app_core.APP_VERSION} (Bau {app_core.APP_BUILD})"
    c = api.community()
    assert c["ok"] and c["daten"]["mitglieder"][0]["du"] and "nur du" in c["daten"]["hinweis"]
    up = api.update_pruefen()
    assert not up["ok"] and "nicht erreichbar" in up["text"] and not api.schliessen_angefordert
    e = api.entfernen()
    assert e["ok"] and e["daten"] == 3 and api.schliessen_angefordert
    assert not (tmp_path / "Programme" / "CommunityAI").exists() and api.zustand()["daten"]["einrichtung"]["installiert"] is False


def test_selftest_from_source_passes_without_window(tmp_path, capsys):
    core = _core(tmp_path)
    rc = app_web.selftest(core)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "OK   ki" in out and "INFO install" in out and (core.diagnosis_dir / "selbsttest.txt").exists()
    assert app_web.Api(core, registry=app_install.MemoryRegistry()).ki_auto() is True


def test_index_html_has_the_four_areas_and_no_dark_surprises():
    html = (app_web.webapp_dir() / app_web.INDEX_NAME).read_text(encoding="utf-8")
    for needle in ("Gespräche", "Rechenkraft teilen", "Meine Community", "Einstellungen", 'color-scheme" content="light"', "pywebviewready", "Details zur Antwort", "Freigabe speichern"):
        assert needle in html
    assert "😀" not in html and "linear-gradient" not in html


def test_surface_never_names_the_base_model_and_the_instruction_refuses_to_guess():
    html = (app_web.webapp_dir() / app_web.INDEX_NAME).read_text(encoding="utf-8")
    assert "Ministral" not in html and "Mistral" not in html and "k.modell}" not in html and "l.modell}" not in html and "u.ki.modell" not in html
    assert "KIplatz ist an" in html and 'zeile("Erarbeitet von", esc(`KIplatz auf' in html
    assert "Ministral 3 von Mistral AI (Apache-2.0)" in (app_web.webapp_dir().parent / "app_web.py").read_text(encoding="utf-8")
    for needle in ("Das weiß ich noch nicht", "Erfinde nichts", "kein Team", "möglicherweise", "keine Sternchen"):
        assert needle in kl.SYSTEMTEXT


def test_ki_is_ready_only_when_the_server_answers_not_when_the_process_exists(tmp_path):
    api, fake, _ = _api(tmp_path)
    fake._on = True
    api._ki.phase = "starten"
    assert not api._ki.bereit() and not api.zustand()["daten"]["ki"]["laeuft"]
    api._ki.phase = "bereit"
    assert api._ki.bereit()
    fake._on = False
    assert not api._ki.bereit() and api.zustand()["daten"]["ki"]["phase"] == "fehler"


def test_a_model_that_fails_on_the_card_answers_once_more_from_the_processor(tmp_path):
    api, fake, _ = _api(tmp_path)
    echt = fake.frage
    fehler = {"n": 0}

    def frage(nachrichten, *, on_token=None, **kw):
        if fake.wahl is not None and fake.wahl.geraet is not None:
            fehler["n"] += 1
            raise kl.KiError("KI_ANTWORT", "keine Antwort vom KI-Server (HTTP 500: failed to allocate compute buffers)")
        return echt(nachrichten, on_token=on_token, **kw)
    fake.frage = frage
    g = api.gespraech_neu()["daten"]
    r = api.frage(g["kennung"], "hallo")
    assert r["ok"], r["text"]
    assert fehler["n"] == 1 and fake.wahl.geraet is None and api._ki.nur_prozessor and api._ki.wahl.geraet is None
    assert "Prozessor" in r["daten"]["lieferschein"]["quellen"] and "Grafikkarte hat versagt" in r["daten"]["lieferschein"]["quellen"]
    assert r["daten"]["text"] == "Servus, Huber." and fake.stopped >= 1
    fake.frage = lambda *a, **kw: (_ for _ in ()).throw(kl.KiError("KI_ANTWORT", "keine Antwort vom KI-Server (HTTP 500: x)"))
    r2 = api.frage(g["kennung"], "hallo")
    assert not r2["ok"] and r2["code"] == "KI_ANTWORT" and "HTTP" not in r2["text"] and "nicht geantwortet" in r2["text"]


def test_stop_and_hide_do_nothing_harmful_without_a_window(tmp_path):
    api, fake, _ = _api(tmp_path)
    assert api.antwort_abbrechen()["ok"] and api.abbruch_gewuenscht and fake.abbruch.is_set()
    assert api.fenster_schliessen()["ok"] and api.versteckt and not api.schliessen_angefordert
    assert api.fenster_zeigen()["ok"] and not api.versteckt
    assert api.beenden()["ok"] and api.schliessen_angefordert
    g = api.gespraech_neu()["daten"]
    r = api.frage(g["kennung"], "hallo")
    assert r["ok"] and not api.abbruch_gewuenscht and not fake.abbruch.is_set()
