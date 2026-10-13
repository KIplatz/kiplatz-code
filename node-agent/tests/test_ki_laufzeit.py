# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

import ki_laufzeit as kl


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _paket(data: bytes, name="probe.bin") -> kl.Paket:
    return kl.Paket(kennung="p", name="Probe", datei=name, url="https://beispiel.invalid/" + name, sha256=hashlib.sha256(data).hexdigest(), groesse=len(data))


def test_herunterladen_verifies_hash_and_size_and_reports_progress(tmp_path):
    data = b"x" * (3 * 1024 * 1024 + 17)
    seen = []
    ziel = tmp_path / "dl" / "probe.bin"
    out = kl.herunterladen(_paket(data), ziel, fortschritt=lambda d, g: seen.append((d, g)), oeffner=lambda req, timeout: _Resp(data))
    assert out == ziel and ziel.read_bytes() == data and not ziel.with_name("probe.bin.teil").exists()
    assert seen[-1] == (len(data), len(data)) and len(seen) >= 3
    assert kl.pruefsumme_ok(ziel, _paket(data))


def test_herunterladen_rejects_wrong_bytes_and_http(tmp_path):
    data = b"richtig"
    with pytest.raises(kl.KiError) as e:
        kl.herunterladen(_paket(data), tmp_path / "a.bin", oeffner=lambda req, timeout: _Resp(b"falsch!"))
    assert e.value.code == "KI_PRUEFSUMME" and not (tmp_path / "a.bin").exists() and not (tmp_path / "a.bin.teil").exists()
    with pytest.raises(kl.KiError) as e2:
        kl.herunterladen(_paket(data), tmp_path / "b.bin", oeffner=lambda req, timeout: _Resp(data + b"mehr"))
    assert e2.value.code == "KI_PRUEFSUMME"
    unsicher = kl.Paket(kennung="p", name="P", datei="c", url="http://klartext.invalid/c", sha256="0" * 64, groesse=1)
    with pytest.raises(kl.KiError) as e3:
        kl.herunterladen(unsicher, tmp_path / "c.bin", oeffner=lambda req, timeout: _Resp(b"x"))
    assert e3.value.code == "KI_QUELLE"


def test_laufzeit_entpacken_flat_and_guarded(tmp_path):
    z = tmp_path / "rt.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("unter/ordner/llama-server.exe", b"MZ-probe")
        zf.writestr("unter/ordner/ggml.dll", b"dll")
        zf.writestr("unter/ordner/", b"")
    exe = kl.laufzeit_entpacken(z, tmp_path / "laufzeit")
    assert exe.name == "llama-server.exe" and exe.read_bytes() == b"MZ-probe" and (tmp_path / "laufzeit" / "ggml.dll").exists()
    ohne = tmp_path / "ohne.zip"
    with zipfile.ZipFile(ohne, "w") as zf:
        zf.writestr("nur.dll", b"x")
    with pytest.raises(kl.KiError) as e:
        kl.laufzeit_entpacken(ohne, tmp_path / "l2")
    assert e.value.code == "KI_LAUFZEIT"


def test_geraete_parsen_and_waehlen_prefers_real_card_and_fitting_model():
    text = """Available devices:
  Vulkan0: Intel(R) UHD Graphics (8044 MiB, 7386 MiB free)
  Vulkan1: NVIDIA GeForce RTX 4050 Laptop GPU (5920 MiB, 5152 MiB free)
"""
    g = kl.geraete_parsen(text)
    assert [x.kennung for x in g] == ["Vulkan0", "Vulkan1"] and g[1].frei_mib == 5152 and not g[0].eigenstaendig and g[1].eigenstaendig
    w = kl.waehlen(g, 15.7)
    assert w.geraet is not None and w.geraet.kennung == "Vulkan1" and w.modell.kennung == "3B"
    assert kl.waehlen_rechen(g).geraet is not None and kl.waehlen_rechen(kl.geraete_parsen("  Vulkan0: NVIDIA X (6000 MiB, 1800 MiB free)\n")).geraet is None
    gross = kl.geraete_parsen("  Vulkan1: NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB, 7600 MiB free)\n")
    assert kl.waehlen(gross, 15.7).modell.kennung == "8B"
    pc = kl.geraete_parsen("  Vulkan0: AMD Radeon RX 7800 XT (16368 MiB, 15900 MiB free)\n")
    assert kl.waehlen(pc, 31.9).modell.kennung == "14B"
    klein = kl.geraete_parsen("  Vulkan0: NVIDIA GeForce GTX 1650 (4096 MiB, 3800 MiB free)\n")
    assert kl.waehlen(klein, 15.7).modell.kennung == "3B"
    nur_intel = kl.geraete_parsen("  Vulkan0: Intel(R) UHD Graphics (8044 MiB, 7386 MiB free)\n")
    assert kl.waehlen(nur_intel, 15.7).geraet is not None and kl.waehlen(nur_intel, 15.7).modell.kennung == "8B"
    assert kl.waehlen((), 5.9).modell.kennung == "3B" and kl.waehlen((), 5.9).geraet is None
    assert kl.waehlen((), 31.9).modell.kennung == "8B"


class _FakeProc:
    def __init__(self, args, **kw):
        self.args = args
        self.kw = kw
        self.terminated = False
        self.killed = False
        self._code = None

    def poll(self):
        return self._code

    @property
    def returncode(self):
        return self._code

    def terminate(self):
        self.terminated = True
        self._code = 0

    def kill(self):
        self.killed = True
        self._code = -9

    def wait(self, timeout=None):
        return self._code


def _ordner_mit_dateien(tmp_path):
    o = kl.KiOrdner(tmp_path)
    o.anlegen()
    o.laufzeit_dir.mkdir(parents=True, exist_ok=True)
    o.server_exe.write_bytes(b"MZ")
    m = kl.MODELLE["3B"]
    o.modell_pfad(m).write_bytes(b"gguf")
    return o, kl.Wahl(kl.Geraet("Vulkan1", "Probe GPU", 8000, 7000), m, "test")


def test_kiserver_start_binds_localhost_with_key_and_stops_only_its_child(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)
    procs = []

    def popen(args, **kw):
        p = _FakeProc(args, **kw)
        procs.append(p)
        return p

    calls = {"health": 0}

    def urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        if url.endswith("/health"):
            calls["health"] += 1
            if calls["health"] < 3:
                raise OSError("noch nicht")
            return _Resp(b'{"status":"ok"}')
        assert req.get_header("Authorization") == f"Bearer {s.api_key}"
        body = json.loads(req.data.decode("utf-8"))
        assert body["messages"][0]["role"] == "system" and body["messages"][-1]["content"] == "Hallo"
        return _Resp(json.dumps({"choices": [{"message": {"content": " Servus! "}}], "usage": {"prompt_tokens": 12, "completion_tokens": 3}}).encode())

    s = kl.KiServer(o, popen=popen, urlopen=urlopen, schlafen=lambda _s: None, port_finder=lambda: 18555)
    s.start(wahl)
    assert s.laeuft() and s.port == 18555 and s.api_key and len(s.api_key) > 20
    args = procs[0].args
    assert args[0] == str(o.server_exe) and "127.0.0.1" in args and "--no-webui" in args and "--device" in args and "Vulkan1" in args
    assert "--api-key" not in args and s.api_key not in args and procs[0].kw["env"]["LLAMA_API_KEY"] == s.api_key
    assert not any(a in ("0.0.0.0", "::") for a in args)
    a = s.frage([{"role": "user", "content": "Hallo"}])
    assert a.text == "Servus!" and a.prompt_tokens == 12 and a.completion_tokens == 3
    s.stop()
    assert procs[0].terminated and not s.laeuft() and s.api_key is None
    s.stop()


def test_kiserver_reports_early_exit_and_missing_files(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)

    def popen_dies(args, **kw):
        p = _FakeProc(args, **kw)
        p._code = 3
        return p

    s = kl.KiServer(o, popen=popen_dies, urlopen=lambda r, timeout=0: (_ for _ in ()).throw(OSError()), schlafen=lambda _s: None, port_finder=lambda: 1)
    with pytest.raises(kl.KiError) as e:
        s.start(wahl)
    assert e.value.code == "KI_START" and "Code 3" in e.value.detail and not s.laeuft()
    leer = kl.KiOrdner(tmp_path / "leer")
    with pytest.raises(kl.KiError) as e2:
        kl.KiServer(leer, popen=popen_dies, urlopen=None, schlafen=lambda _s: None).start(wahl)
    assert e2.value.code == "KI_LAUFZEIT"
    with pytest.raises(kl.KiError) as e3:
        s.frage([{"role": "user", "content": "x"}])
    assert e3.value.code == "KI_AUS"


def test_kiserver_streams_tokens(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)
    events = [
        {"choices": [{"delta": {"content": "Gr"}}]},
        {"choices": [{"delta": {"content": "üß "}}]},
        {"choices": [{"delta": {"content": "dich"}}]},
        {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 3}},
    ]
    sse = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events) + "data: [DONE]\n\n"

    def urlopen(req, timeout=0):
        url = req.full_url
        if url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        assert json.loads(req.data.decode("utf-8"))["stream"] is True
        return _Resp(sse.encode("utf-8"))

    s = kl.KiServer(o, popen=lambda a, **k: _FakeProc(a, **k), urlopen=urlopen, schlafen=lambda _s: None, port_finder=lambda: 2)
    s.start(wahl)
    got = []
    a = s.frage([{"role": "user", "content": "hi"}], on_token=got.append)
    assert got == ["Gr", "üß ", "dich"] and a.text == "Grüß dich" and a.completion_tokens == 3 and a.prompt_tokens == 9
    s.stop()


def test_catalogue_is_pinned_and_https():
    for p in (kl.LAUFZEIT, *kl.MODELLE.values()):
        assert p.url.startswith("https://") and len(p.sha256) == 64 and p.groesse > 1_000_000
    assert kl.MODELLE["14B"].braucht_mib > kl.MODELLE["8B"].braucht_mib > kl.MODELLE["3B"].braucht_mib
    assert "erfinde nichts" in kl.SYSTEMTEXT.lower() and "deutsch" in kl.SYSTEMTEXT.lower()


def test_weak_machine_ignores_the_chip_on_the_processor_and_loads_no_image_addon(tmp_path):
    vega = kl.geraete_parsen("  Vulkan0: AMD Radeon(TM) Graphics (2048 MiB, 1900 MiB free)\n  Vulkan1: AMD Radeon(TM) Graphics (3900 MiB, 3500 MiB free)\n")
    assert not vega[1].eigenstaendig
    w = kl.waehlen(vega, 5.9)
    assert w.geraet is None and w.modell.kennung == "3B"
    assert kl.waehlen(vega, 15.7).geraet is not None
    o, _ = _ordner_mit_dateien(tmp_path)
    m = kl.MODELLE["3B"]
    o.bilder_pfad(m).write_bytes(b"mmproj")
    o.bilder_da = lambda modell: True
    procs = []

    def popen(args, **kw):
        p = _FakeProc(args, **kw)
        procs.append(p)
        return p
    ok = lambda req, timeout=0: _Resp(b'{"status":"ok"}')
    s = kl.KiServer(o, popen=popen, urlopen=ok, schlafen=lambda _s: None, port_finder=lambda: 18560)
    s.start(kl.Wahl(None, m, "prozessor"))
    assert "--no-mmproj" in procs[0].args and "--mmproj" not in procs[0].args and not s.bilder
    s.stop()
    s.start(kl.Wahl(vega[1], m, "chip"))
    assert "--mmproj" not in procs[1].args and not s.bilder
    s.stop()
    s.start(kl.Wahl(kl.Geraet("Vulkan2", "NVIDIA GeForce RTX 4050 Laptop GPU", 5920, 5152), m, "karte"))
    assert "--mmproj" in procs[2].args and s.bilder
    s.stop()


def test_kiserver_waits_while_the_model_loads_and_names_other_http_errors(tmp_path):
    import urllib.error
    o, wahl = _ordner_mit_dateien(tmp_path)
    calls = {"n": 0}

    def urlopen(req, timeout=0):
        if req.full_url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        if req.full_url.endswith("/props"):
            raise OSError("ältere Laufzeit ohne /props")
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b'{"error":{"message":"Loading model","code":503}}'))
        if calls["n"] == 3:
            return _Resp(json.dumps({"choices": [{"message": {"content": "Da bin ich."}}], "usage": {}}).encode())
        raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, io.BytesIO(b'{"error":{"message":"failed to allocate compute buffers","code":500}}'))

    geschlafen = []
    s = kl.KiServer(o, popen=lambda a, **kw: _FakeProc(a, **kw), urlopen=urlopen, schlafen=geschlafen.append, port_finder=lambda: 18561)
    s.start(wahl)
    a = s.frage([{"role": "user", "content": "Hallo"}])
    assert a.text == "Da bin ich." and calls["n"] == 3 and geschlafen.count(1.0) == 2
    with pytest.raises(kl.KiError) as e:
        s.frage([{"role": "user", "content": "Hallo"}])
    assert e.value.code == "KI_ANTWORT" and "HTTP 500" in e.value.detail and "compute buffers" in e.value.detail


def test_kiserver_stop_button_keeps_what_came_so_far(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)
    events = [{"choices": [{"delta": {"content": w}}]} for w in ("Erst", "ens ", "zweit", "ens ", "dritt", "ens")]
    sse = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"

    def urlopen(req, timeout=0):
        if req.full_url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        return _Resp(sse.encode("utf-8"))

    s = kl.KiServer(o, popen=lambda a, **kw: _FakeProc(a, **kw), urlopen=urlopen, schlafen=lambda _s: None, port_finder=lambda: 18562)
    s.start(wahl)
    stuecke = []

    def on_token(t):
        stuecke.append(t)
        if len(stuecke) == 2:
            s.abbruch.set()
    a = s.frage([{"role": "user", "content": "Zähl"}], on_token=on_token)
    assert a.abgebrochen and a.text == "Erstens" and len(stuecke) == 2
    a2 = s.frage([{"role": "user", "content": "Zähl"}], on_token=lambda t: None)
    assert not a2.abgebrochen and a2.text == "Erstens zweitens drittens"


def test_kiserver_start_says_abgebrochen_when_stopped_meanwhile(tmp_path):
    o, wahl = _ordner_mit_dateien(tmp_path)
    s = kl.KiServer(o, popen=lambda a, **kw: _FakeProc(a, **kw), urlopen=lambda r, timeout=0: (_ for _ in ()).throw(OSError("noch nicht")),
                    schlafen=lambda _s: s.stop(), port_finder=lambda: 18563)
    with pytest.raises(kl.KiError) as e:
        s.start(wahl)
    assert e.value.code == "KI_START" and "abgebrochen" in e.value.detail and not s.laeuft()


def test_einmal_second_start_only_asks_the_first_window_to_show(tmp_path):
    import einmal
    assert einmal.sperre_holen(tmp_path) is True
    zweite = einmal.sperre_holen(tmp_path)
    assert zweite is (False if __import__("sys").platform == "win32" else True)
    assert einmal.sperre_holen(tmp_path / "anderer") is True
    assert not einmal.zeigen_angefordert(tmp_path)
    einmal.zeigen_anfordern(tmp_path)
    assert (tmp_path / "diagnose" / einmal.ZEIGEN_NAME).is_file()
    assert einmal.zeigen_angefordert(tmp_path) and not einmal.zeigen_angefordert(tmp_path)


def test_die_karte_zaehlt_was_das_programm_schon_daraufgelegt_hat(tmp_path):
    karte = kl.Geraet("Vulkan1", "NVIDIA GeForce RTX 4050 Laptop GPU", 6141, 5900)
    o, _ = _ordner_mit_dateien(tmp_path)
    o.modell_pfad(kl.EMBEDDING).write_bytes(b"gguf")
    procs = []
    gesund = lambda req, timeout=0: _Resp(b'{"status":"ok"}')
    antwort = kl.KiServer(o, popen=lambda a, **k: procs.append(_FakeProc(a, **k)) or procs[-1], urlopen=gesund, schlafen=lambda _s: None, port_finder=lambda: 3)
    w = kl.waehlen([karte], 16)
    assert w.modell.kennung == "3B"
    antwort.start(w)
    assert kl.belegt_mib("Vulkan1") == w.modell.braucht_mib
    b = kl.waehlen_rechen([karte])
    assert b.geraet is not None
    bedeutung = kl.KiServer(o, popen=lambda a, **k: procs.append(_FakeProc(a, **k)) or procs[-1], urlopen=gesund, schlafen=lambda _s: None, port_finder=lambda: 4)
    bedeutung.start(b, embedding=True)
    assert kl.waehlen_bewertung([karte]) is None
    bedeutung.stop()
    assert kl.belegt_mib("Vulkan1") == w.modell.braucht_mib and kl.waehlen_bewertung([karte]) is not None
    antwort.stop()
    assert kl.belegt_mib("Vulkan1") == 0


def _typeperf(karte_mib: int, prozesse: dict) -> str:
    luid, chip = "luid_0x00000000_0x000112DF_phys_0", "luid_0x00000000_0x00010EDB_phys_0"
    kopf = ['"(PDH-CSV 4.0)"', f'"\\\\TEST-PC\\GPU Adapter Memory({chip})\\Dedicated Usage"',
            f'"\\\\TEST-PC\\GPU Adapter Memory({luid})\\Dedicated Usage"']
    werte = ['"10/01/2026 22:53:28.793"', '"0.000000"', f'"{karte_mib * 1048576:.6f}"']
    for pid, mib in prozesse.items():
        kopf += [f'"\\\\TEST-PC\\GPU Process Memory(pid_{pid}_{chip})\\Dedicated Usage"',
                 f'"\\\\TEST-PC\\GPU Process Memory(pid_{pid}_{luid})\\Dedicated Usage"']
        werte += ['"0.000000"', f'"{mib * 1048576:.6f}"']
    return ",".join(kopf) + "\n" + ",".join(werte) + "\n \nVorgang wird beendet...\n"


def test_bau_01d_die_karte_zaehlt_auch_was_andere_windows_benutzer_daraufgelegt_haben(tmp_path, monkeypatch):
    assert kl.zaehler_parsen("") is None and kl.zaehler_parsen("Fehler: Zähler gibt es nicht\n") is None
    k, p = kl.zaehler_parsen(_typeperf(4876, {24500: 632, 42492: 2560}))
    assert k["luid_0x00000000_0x000112df"] == 4876 and p[42492] == ("luid_0x00000000_0x000112df", 2560)
    karte = kl.Geraet("Vulkan1", "AMD Radeon RX 7800 XT", 16368, 16000)
    lesungen = []
    ausgabe = [_typeperf(6200, {})]

    def typeperf(args, **kw):
        lesungen.append(args)
        return subprocess.CompletedProcess(args, 0, ausgabe[0], "")
    monkeypatch.setattr(kl, "KARTE_ZAEHLER", True)
    monkeypatch.setattr(kl, "_zaehler_stand", (-1e9, None))
    monkeypatch.setattr(kl.subprocess, "run", typeperf)
    assert kl.fremd_mib(karte) == 6200
    assert kl.frei_mib(karte) == 16368 - 6200 - kl.KARTE_RESERVE_MIB
    w = kl.waehlen([karte], 32)
    assert "andere Programme belegen gerade 6200 MiB" in w.grund and lesungen[0][0] == "typeperf" and len(lesungen) == 1
    o, _ = _ordner_mit_dateien(tmp_path)
    o.modell_pfad(w.modell).write_bytes(b"gguf")
    proc = _FakeProc(["x"])
    proc.pid = 777
    antwort = kl.KiServer(o, popen=lambda a, **k: proc, urlopen=lambda req, timeout=0: _Resp(b'{"status":"ok"}'), schlafen=lambda _s: None, port_finder=lambda: 3)
    antwort.start(w)
    ausgabe[0] = _typeperf(6200 + 5900, {777: 5900})
    monkeypatch.setattr(kl, "_zaehler_stand", (-1e9, None))
    assert kl.fremd_mib(karte) == 6200
    assert kl.frei_mib(karte) == 16368 - w.modell.braucht_mib - 6200 - kl.KARTE_RESERVE_MIB
    antwort.stop()
    def kaputt(args, **kw):
        raise OSError("typeperf fehlt")
    monkeypatch.setattr(kl.subprocess, "run", kaputt)
    monkeypatch.setattr(kl, "_zaehler_stand", (-1e9, None))
    assert kl.fremd_mib(karte) == 0 and kl.frei_mib(karte) == 16000
    assert kl.fremd_mib(kl.Geraet("Vulkan0", "AMD Radeon(TM) Graphics", 2048, 2000)) == 0
