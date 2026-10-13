# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import re
import sys
import time
import wave
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core
import ki_laufzeit
import modell_katalog
import sprechen

HTML = (Path(__file__).resolve().parents[1] / "webapp" / "index.html").read_text(encoding="utf-8")


import sprechen_windows


@pytest.fixture(autouse=True)
def _ohne_windows_erkennung(monkeypatch):
    monkeypatch.setattr(sprechen, "WINDOWS_ERKENNER", sprechen_windows.Keiner())


class _WindowsAttrappe:
    def __init__(self, text="Wie wird das Wetter morgen in Linz", kulturen=("de-DE",)):
        self.text, self._kulturen, self.aufrufe = text, list(kulturen), []

    def kulturen(self):
        return list(self._kulturen)

    def verfuegbar(self, sprache="de"):
        return bool(sprechen_windows.kultur_fuer(sprache, self._kulturen))

    def erkennen(self, wav, sprache="de"):
        assert Path(wav).is_file()
        self.aufrufe.append((str(wav), sprache))
        return self.text


def _ordner(tmp_path: Path) -> sprechen.SprachOrdner:
    return sprechen.SprachOrdner(ki_laufzeit.KiOrdner(tmp_path))


def _da_machen(o: sprechen.SprachOrdner) -> None:
    o.laufzeit_dir.mkdir(parents=True, exist_ok=True)
    o.cli.write_bytes(b"MZ")
    o.modell.parent.mkdir(parents=True, exist_ok=True)
    with open(o.modell, "wb") as f:
        f.seek(modell_katalog.SPRACHE_MODELL.groesse - 1)
        f.write(b"\0")


def _hoer_da_machen(o: sprechen.SprachOrdner) -> None:
    o.ki.laufzeit_dir.mkdir(parents=True, exist_ok=True)
    o.ki.server_exe.write_bytes(b"MZ")
    o.ki.modelle_dir.mkdir(parents=True, exist_ok=True)
    for pfad, paket in ((o.ki.modell_pfad(modell_katalog.HOEREN), modell_katalog.HOEREN), (o.ki.bilder_pfad(modell_katalog.HOEREN), modell_katalog.HOEREN.bilder)):
        with open(pfad, "wb") as f:
            f.seek(paket.groesse - 1)
            f.write(b"\0")


class _HoerServer:

    def __init__(self, text="Test, test, dies ist ein Test", kaputt=False):
        self.text, self.kaputt, self.starts, self.gehoert, self.gestoppt = text, kaputt, [], [], 0
        self._an = False

    def laeuft(self):
        return self._an

    def start(self, wahl, *, hoeren=False, threads=None, **kw):
        assert hoeren and wahl.modell is modell_katalog.HOEREN
        self.starts.append((wahl.geraet.kennung if wahl.geraet else "cpu", threads))
        self._an = True

    def hoeren(self, wav):
        assert wav[:4] == b"RIFF"
        self.gehoert.append(len(wav))
        if self.kaputt:
            raise ki_laufzeit.KiError("KI_ANTWORT", "keine Antwort vom Hör-Modell (HTTP 500)")
        return self.text

    def stop(self):
        self._an = False
        self.gestoppt += 1


def test_catalogue_entries_are_pinned_and_mirrored():
    for p in (modell_katalog.SPRACHE_LAUFZEIT, modell_katalog.SPRACHE_MODELL, modell_katalog.HOEREN, modell_katalog.HOEREN.bilder):
        assert p.url.startswith("https://") and p.quellen == (p.url,)
        assert re.fullmatch(r"[0-9a-f]{64}", p.sha256) and p.groesse > 0
        assert p in modell_katalog.ALLE and modell_katalog.NACH_DATEI[p.datei] is p
    assert modell_katalog.SPRACHE_LAUFZEIT.datei != "whisper-bin-x64.zip"


def test_wav_bytes_is_16k_mono_16bit():
    pcm = b"\x01\x00" * 1600
    with wave.open(io.BytesIO(sprechen.wav_bytes(pcm)), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 1600)


def test_text_saeubern_drops_whispers_own_notes():
    assert sprechen.text_saeubern("\n [Musik] Wie wird das  Wetter (unverständlich) morgen?\n") == "Wie wird das Wetter morgen?"
    assert sprechen.text_saeubern("[BLANK_AUDIO]") == ""


def test_threads_wahl_keeps_one_core_and_caps_at_four():
    assert sprechen.threads_wahl(2) == 1 and sprechen.threads_wahl(4) == 3 and sprechen.threads_wahl(8) == 4 and sprechen.threads_wahl(None) >= 1


def test_entpacken_flattens_release_folder_and_takes_only_exe_and_dll(tmp_path):
    z = tmp_path / "w.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Release/whisper-cli.exe", b"MZ")
        zf.writestr("Release/whisper.dll", b"MZ")
        zf.writestr("Release/README.txt", b"x")
        zf.writestr("Release/../evil.exe", b"MZ")
    exe = sprechen.entpacken(z, tmp_path / "laufzeit")
    namen = sorted(p.name for p in (tmp_path / "laufzeit").iterdir())
    assert exe.name == "whisper-cli.exe" and namen == ["evil.exe", "whisper-cli.exe", "whisper.dll"]
    assert not (tmp_path / "evil.exe").exists()


def test_entpacken_refuses_archive_without_cli(tmp_path):
    z = tmp_path / "w.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Release/whisper.dll", b"MZ")
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.entpacken(z, tmp_path / "laufzeit")
    assert e.value.code == "SPRECHEN_LAUFZEIT"


def test_holen_fetches_runtime_then_hearing_model_and_add_on_with_pinned_packages(tmp_path):
    o = _ordner(tmp_path)
    geholt = []

    def laden(paket, ziel, *, fortschritt=None):
        geholt.append(paket.kennung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if paket is modell_katalog.LAUFZEIT:
            with zipfile.ZipFile(ziel, "w") as zf:
                zf.writestr("llama-server.exe", b"MZ")
        else:
            with open(ziel, "wb") as f:
                f.seek(paket.groesse - 1)
                f.write(b"\0")
        if fortschritt:
            fortschritt(1, 2)
        return ziel

    fort = []
    sprechen.holen(o, fortschritt=lambda was, d, g: fort.append(was), herunterladen=laden)
    assert geholt == [ki_laufzeit.LAUFZEIT.kennung, "qwen3-asr-0.6b-q8_0", "qwen3-asr-0.6b-mmproj"] and o.hoer_da() and not o.da()
    assert fort == ["KI-Laufzeit", "Hör-Modell", "Hör-Zusatz"]
    sprechen.holen(o, herunterladen=laden)
    assert len(geholt) == 3
    assert sprechen.HOLEN_GESAMT == modell_katalog.HOEREN.groesse + modell_katalog.HOEREN.bilder.groesse


def test_erkennen_runs_cli_writes_wav_reads_txt_and_cleans_up(tmp_path):
    o = _ordner(tmp_path)
    _da_machen(o)
    gesehen = {}

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    def laufen(cmd, **kw):
        gesehen["cmd"] = cmd
        wav = Path(cmd[cmd.index("-f") + 1])
        assert wav.is_file() and wav.suffix == ".wav"
        Path(cmd[cmd.index("-of") + 1] + ".txt").write_text(" Wie wird das Wetter morgen in Linz?\n", encoding="utf-8")
        return R()

    text = sprechen.erkennen(o, b"\0\0" * 16000, threads=3, laufen=laufen)
    assert text == "Wie wird das Wetter morgen in Linz?"
    cmd = gesehen["cmd"]
    assert cmd[0] == str(o.cli) and cmd[cmd.index("-m") + 1] == str(o.modell) and cmd[cmd.index("-l") + 1] == "de" and cmd[cmd.index("-t") + 1] == "3"
    assert "-nt" in cmd and "-np" in cmd and "-otxt" in cmd
    assert not list(o.arbeit.glob("*"))


def test_erkennen_refuses_short_or_missing_and_reports_cli_failure(tmp_path):
    o = _ordner(tmp_path)
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 100)
    assert e.value.code == "SPRECHEN_LEER"
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000)
    assert e.value.code == "SPRECHEN_FEHLT"
    _da_machen(o)

    class R:
        returncode = 3
        stdout = ""
        stderr = "error: failed to initialize whisper context"

    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000, laufen=lambda cmd, **kw: R())
    assert e.value.code == "SPRECHEN_ERKENNUNG" and "Code 3" in e.value.detail
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000, laufen=lambda cmd, **kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    assert e.value.code == "SPRECHEN_LEER"


class _FakeAufnahme:
    instanzen: list = []

    def __init__(self) -> None:
        self.offen = False
        self.voll = False
        self.pegel = 0.3
        self.seit = time.monotonic()
        _FakeAufnahme.instanzen.append(self)

    def start(self):
        self.offen = True

    def sekunden(self):
        return 1

    def laeuft(self):
        return self.offen

    def stopp(self):
        self.offen = False
        return b"\0\0" * 16000


def _warten(st: sprechen.Steuerung, phase: str, s: float = 3.0) -> dict:
    ende = time.monotonic() + s
    while time.monotonic() < ende:
        d = st.stand()
        if d["phase"] == phase or d["text"]:
            return d
        time.sleep(0.02)
    raise AssertionError(f"phase {phase} not reached, last {st.phase}")


def test_steuerung_records_recognises_and_delivers_text_once(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    _da_machen(o)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)
    _FakeAufnahme.instanzen.clear()
    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, erkenner=lambda pcm: f"{len(pcm) // 32000} Sekunde gehört")
    d = st.start()
    assert d["phase"] == "aufnahme" and _FakeAufnahme.instanzen[0].offen
    d = st.stopp()
    assert d["phase"] == "erkennen"
    d = _warten(st, "fertig")
    assert d["text"] == "1 Sekunde gehört" and not _FakeAufnahme.instanzen[0].offen
    assert st.stand()["phase"] == "aus" and st.stand()["text"] == ""


def test_steuerung_first_click_fetches_then_says_bereit(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)
    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, holer=lambda fortschritt: (fortschritt("Sprach-Modell", 5, 10), _da_machen(o)))
    d = st.start()
    assert d["phase"] == "holen" and d["da"] is False
    d = _warten(st, "bereit")
    assert d["phase"] == "bereit" and d["da"] is True
    assert st.start()["phase"] == "aufnahme"


def test_steuerung_without_microphone_or_with_refusal_gives_a_plain_sentence(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    _da_machen(o)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: False)
    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme)
    d = st.start()
    assert d["phase"] == "fehler" and "Mikrofon" in d["meldung"] and "Traceback" not in d["meldung"]
    assert st.stand()["phase"] == "aus"

    class Verweigert(_FakeAufnahme):
        def start(self):
            raise sprechen.SprechenError("SPRECHEN_MIKROFON", "Windows gibt das Mikrofon nicht her (Code 4)")

    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)
    st = sprechen.Steuerung(o, aufnahme_klasse=Verweigert)
    d = st.start()
    assert d["phase"] == "fehler" and "Datenschutz" in d["meldung"]


def test_steuerung_recognition_error_and_abbrechen(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    _da_machen(o)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)

    def kaputt(pcm):
        raise sprechen.SprechenError("SPRECHEN_LEER", "da war nichts zu verstehen")

    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, erkenner=kaputt)
    st.start(); st.stopp()
    d = _warten(st, "fehler")
    assert d["phase"] == "fehler" and "nichts zu verstehen" in d["meldung"]
    _FakeAufnahme.instanzen.clear()
    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme)
    st.start()
    d = st.abbrechen()
    assert d["phase"] == "aus" and not _FakeAufnahme.instanzen[-1].offen


def test_steuerung_ends_by_itself_when_the_recording_is_full(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    _da_machen(o)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)

    class Voll(_FakeAufnahme):
        def start(self):
            self.offen = False
            self.voll = True

    st = sprechen.Steuerung(o, aufnahme_klasse=Voll, erkenner=lambda pcm: "lang geredet")
    st.start()
    d = _warten(st, "fertig")
    assert d["text"] == "lang geredet"


@pytest.mark.skipif(sys.platform != "win32", reason="winmm")
def test_windows_takes_16k_mono_without_opening_the_microphone():
    assert sprechen.format_moeglich() == sprechen.mikrofon_da()


def test_window_has_the_button_and_no_invitation_code_at_first_start():
    assert 'id="btn-sprechen"' in HTML and "sprechen_start" in HTML and "sprechen_stopp" in HTML and "sprechen_zustand" in HTML
    assert 'id="es-2"' not in HTML and 'id="es-code"' not in HTML
    assert "hintline" not in HTML.split("<script>")[0].split("<body>")[1]


def test_texts_no_longer_say_mitrechnen_or_wegwerfdaten_to_members():
    sichtbar = re.sub(r"<!--.*?-->", "", HTML, flags=re.S)
    sichtbar = re.sub(r"/\*.*?\*/", "", sichtbar, flags=re.S)
    sichtbar = re.sub(r"//[^\n]*", "", sichtbar)
    treffer = [m.group(0) for m in re.finditer(r"[^\n]{0,40}mitrechnen[^\n]{0,40}", sichtbar, flags=re.I)]
    treffer = [t for t in treffer if "page-mitrechnen" not in t and 'mitrechnen"' not in t and "mitrechnen:" not in t]
    assert treffer == [], treffer
    assert app_core.PROFILE_LABELS_DE[app_core.Profile.TEST] == ""
    import credits
    assert "mitrechnen" not in credits.REGEL_DE


def test_api_exposes_sprechen_and_title_without_testbetrieb(tmp_path, monkeypatch):
    from test_app_web import _api
    api, _fake, _ = _api(tmp_path)
    z = api.sprechen_zustand()
    assert z["ok"] and z["daten"]["phase"] == "aus" and z["daten"]["da"] is False
    assert "Testbetrieb" not in api.zustand()["daten"]["app"]["profil"]
    api.sprechen_abbrechen()


def test_von_windows_blockierter_baustein_wird_in_einem_satz_gesagt(tmp_path):
    assert sprechen.blockiert(0xC0E90002) and sprechen.blockiert(-1058471934) and sprechen.blockiert(0xC0000135)
    assert not sprechen.blockiert(0) and not sprechen.blockiert(3) and not sprechen.blockiert(None)
    o = _ordner(tmp_path)
    _da_machen(o)
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000, laufen=lambda cmd, **kw: type("R", (), {"returncode": -1058471934, "stdout": "", "stderr": ""})())
    assert e.value.code == "SPRECHEN_BLOCKIERT" and "Smart App Control" in e.value.detail and "Tippen geht" in e.value.detail


def test_windows_erkennung_als_notweg_wenn_der_download_nicht_klappt(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    w = _WindowsAttrappe()
    assert sprechen.erkennen(o, b"\0\0" * 16000, windows=w) == "Wie wird das Wetter morgen in Linz"
    assert w.aufrufe and w.aufrufe[0][1] == "de" and not list(o.arbeit.glob("*.wav"))
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)
    versuche = []

    def holer(f):
        versuche.append(1)
        raise ki_laufzeit.KiError("KI_DOWNLOAD", "kein Netz")

    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, windows=w, holer=holer)
    d = st.start()
    assert d["phase"] == "holen" and d["fortschritt"]["gesamt"] == sprechen.HOLEN_GESAMT
    d = _warten(st, "bereit")
    assert d["phase"] == "bereit" and versuche == [1]
    assert st.start()["phase"] == "aufnahme" and st.stand()["da"]


def test_hoermodell_zuerst_dann_whisper_dann_windows(tmp_path, monkeypatch):
    o = _ordner(tmp_path)
    _hoer_da_machen(o)
    monkeypatch.setattr(sprechen, "mikrofon_da", lambda: True)
    monkeypatch.setattr(sprechen, "HOER_RUHE_S", 0.2)
    srv = _HoerServer()
    w = _WindowsAttrappe(text="falscher Weg")
    st = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, windows=w, server=srv, threads=3,
                            geraete_ermitteln=lambda exe: (ki_laufzeit.Geraet("Vulkan0", "NVIDIA X", 6000, 5000),))
    assert st.stand()["da"] and st.start()["phase"] == "aufnahme"
    st.stopp()
    d = _warten(st, "fertig")
    assert d["text"] == "Test, test, dies ist ein Test" and srv.starts == [("Vulkan0", None)] and srv.gehoert and not w.aufrufe
    assert not list(o.arbeit.glob("*.wav"))
    ende = time.monotonic() + 3
    while srv.laeuft() and time.monotonic() < ende:
        time.sleep(0.02)
    assert not srv.laeuft() and srv.gestoppt == 1
    srv2 = _HoerServer()
    st2 = sprechen.Steuerung(o, aufnahme_klasse=_FakeAufnahme, windows=w, server=srv2, threads=3, geraete_ermitteln=lambda exe: ())
    st2.start(); st2.stopp(); _warten(st2, "fertig")
    assert srv2.starts == [("cpu", 3)]
    st2.beenden()
    assert srv2.gestoppt >= 1
    srv3 = _HoerServer(kaputt=True)
    srv3._an = True
    assert sprechen.erkennen(o, b"\0\0" * 16000, windows=w, hoerer=srv3.hoeren) == "falscher Weg"
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000, windows=sprechen_windows.Keiner(), hoerer=srv3.hoeren)
    assert e.value.code == "SPRECHEN_ERKENNUNG" and "Hör-Modell" in e.value.detail


def test_kiserver_hoeren_sends_wav_as_input_audio_and_reads_the_words(tmp_path):
    import json
    o = ki_laufzeit.KiOrdner(tmp_path)
    gesehen = {}

    class Antwort:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return self.body

    def urlopen(req, timeout=0):
        gesehen["url"] = req.full_url
        gesehen["body"] = json.loads(req.data.decode("utf-8"))
        gesehen["auth"] = req.get_header("Authorization")
        return Antwort(json.dumps({"choices": [{"message": {"content": "language Portuguese<asr_text>Test, test"}}]}).encode("utf-8"))

    class Proc:
        def poll(self):
            return None

    s = ki_laufzeit.KiServer(o, urlopen=urlopen)
    s.proc, s.port, s.api_key = Proc(), 8477, "k"
    assert s.hoeren(b"RIFF....WAVE") == "Test, test"
    teil = gesehen["body"]["messages"][0]["content"][0]
    assert gesehen["url"] == "http://127.0.0.1:8477/v1/chat/completions" and gesehen["auth"] == "Bearer k"
    assert teil["type"] == "input_audio" and teil["input_audio"]["format"] == "wav" and gesehen["body"]["temperature"] == 0.0
    assert ki_laufzeit.hoer_text("Hallo") == "Hallo" and ki_laufzeit.hoer_text("") == ""
    assert ki_laufzeit.waehlen_hoeren(()).geraet is None and ki_laufzeit.waehlen_hoeren((ki_laufzeit.Geraet("Vulkan0", "X", 8000, 4000),)).geraet is not None


def test_whisper_blockiert_dann_windows_und_gemerkt(tmp_path):
    o = _ordner(tmp_path)
    _da_machen(o)
    w = _WindowsAttrappe(text="test test")
    blockiert = lambda cmd, **kw: type("R", (), {"returncode": -1058471934, "stdout": "", "stderr": ""})()
    assert sprechen.erkennen(o, b"\0\0" * 16000, laufen=blockiert, windows=w) == "test test"
    assert o.blockiert() and len(w.aufrufe) == 1
    assert sprechen.erkennen(o, b"\0\0" * 16000, laufen=lambda cmd, **kw: pytest.fail("whisper darf nicht laufen"), windows=w) == "test test"
    with pytest.raises(sprechen.SprechenError) as e:
        sprechen.erkennen(o, b"\0\0" * 16000, laufen=blockiert, windows=sprechen_windows.Keiner())
    assert e.value.code == "SPRECHEN_BLOCKIERT"


def test_windows_erkenner_befehl_und_kulturen():
    assert sprechen_windows.kultur_fuer("de", ["en-US", "de-DE"]) == "de-DE"
    assert sprechen_windows.kultur_fuer("de", ["de-AT"]) == "de-AT" and sprechen_windows.kultur_fuer("de", ["en-US"]) == ""
    assert sprechen_windows.kultur_fuer("en", ["en-GB", "de-DE"]) == "en-GB"
    cmd = sprechen_windows.befehl("Write-Output 'x'")
    assert cmd[0] == "powershell.exe" and "-EncodedCommand" in cmd and "-NoProfile" in cmd and "Bypass" not in " ".join(cmd)
    laeufe = []

    def laufen(cmd, **kw):
        laeufe.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "de-DE en-US" if len(laeufe) == 1 else "Hallo Welt", "stderr": ""})()
    e = sprechen_windows.Erkenner(laufen=laufen)
    if sys.platform == "win32":
        assert e.verfuegbar("de") and e.kulturen() == ["de-DE", "en-US"] and len(laeufe) == 1
        assert e.erkennen(Path("C:/x/y's.wav"), "de") == "Hallo Welt"
        import base64
        script = base64.b64decode(laeufe[-1][-1]).decode("utf-16-le")
        assert "'de-DE'" in script and "y''s.wav" in script and "DictationGrammar" in script
    assert not sprechen_windows.Keiner().verfuegbar()
