# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import sys
import tarfile
import threading
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit


def _archiv(pfad: Path) -> Path:
    inhalt = b"#!/bin/sh\necho llama\n" * 2000
    if ki_laufzeit.SERVER_EXE.endswith(".exe"):
        with zipfile.ZipFile(pfad, "w") as z:
            z.writestr(ki_laufzeit.SERVER_EXE, inhalt)
            z.writestr("libggml.dll", b"x" * 50000)
    else:
        with tarfile.open(pfad, "w:gz") as t:
            for name, daten in ((ki_laufzeit.SERVER_EXE, inhalt), ("libggml.so", b"x" * 50000)):
                info = tarfile.TarInfo(f"build/bin/{name}")
                info.size, info.mode = len(daten), 0o755
                t.addfile(info, io.BytesIO(daten))
    return pfad


def test_zwei_faeden_packen_die_laufzeit_nie_gleichzeitig_aus(tmp_path, monkeypatch):
    archiv = _archiv(tmp_path / ("laufzeit.zip" if ki_laufzeit.SERVER_EXE.endswith(".exe") else "laufzeit.tar.gz"))
    ziel = tmp_path / "laufzeit"
    echt = ki_laufzeit._laufzeit_entpacken
    gleichzeitig, hoechstens, ausgepackt = [0], [0], []
    riegel = threading.Lock()

    def zaehlend(zip_pfad, ziel_dir):
        with riegel:
            gleichzeitig[0] += 1
            hoechstens[0] = max(hoechstens[0], gleichzeitig[0])
        try:
            ausgepackt.append(1)
            return echt(zip_pfad, ziel_dir)
        finally:
            with riegel:
                gleichzeitig[0] -= 1
    monkeypatch.setattr(ki_laufzeit, "_laufzeit_entpacken", zaehlend)
    fehler, start = [], threading.Barrier(8)

    def faden():
        start.wait()
        try:
            ki_laufzeit.laufzeit_entpacken(archiv, ziel, schon_da=lambda: (ziel / ki_laufzeit.SERVER_EXE).is_file())
        except Exception as exc:
            fehler.append(exc)
    alle = [threading.Thread(target=faden) for _ in range(8)]
    for t in alle:
        t.start()
    for t in alle:
        t.join(timeout=30)
    assert fehler == [] and hoechstens[0] == 1 and len(ausgepackt) == 1
    assert (ziel / ki_laufzeit.SERVER_EXE).read_bytes().startswith(b"#!/bin/sh") and not list(ziel.glob(".*.neu"))
    ki_laufzeit.laufzeit_entpacken(archiv, ziel)
    assert len(ausgepackt) == 2


def test_alle_stellen_packen_mit_schon_da_aus():
    hier = Path(__file__).resolve().parent.parent
    for datei in ("app_web.py", "rechenarbeit.py", "sprechen.py"):
        text = (hier / datei).read_text(encoding="utf-8")
        aufrufe = [z for z in text.splitlines() if "ki_laufzeit.laufzeit_entpacken(" in z]
        assert aufrufe and all("schon_da=" in z for z in aufrufe), datei


def test_auf_der_spielwiese_gibt_es_nur_den_code(tmp_path):
    import app_web
    import community
    from test_app_web import _api
    api, _, _ = _api(tmp_path / "fenster")
    api._community = community.Community(api._core.base_dir, adresse=app_web.SPIELWIESE_ADRESSE, oeffner=lambda *a, **k: (_ for _ in ()).throw(OSError("kein Netz")))
    r = api.community_beitreten_konto()
    assert not r["ok"] and r["code"] == "KONTO_SPIELWIESE" and "spielwiese" in r["text"]
    prog = (Path(__file__).resolve().parent.parent / "webapp" / "index.html").read_text(encoding="utf-8")
    assert '$("#beitritt-konto-knopf").style.display = laeuft || beitrittNurCode ? "none" : "";' in prog


def test_ohne_lesbare_taktfrequenz_geht_das_einrichten_weiter(monkeypatch):
    import hardware_detect as hd

    def wirft():
        raise RuntimeError("'pmgr' entry was not found in AppleARMIODevice service")
    monkeypatch.setattr(hd.psutil, "cpu_freq", wirft)
    cpu = hd.detect_cpu()
    assert cpu.max_frequency_mhz is None and (cpu.logical_cores or 0) >= 1


def test_ein_geraet_nimmt_erst_fragen_an_wenn_laufzeit_und_modell_da_sind(tmp_path, monkeypatch):
    from test_app_web import _api
    api, _, _ = _api(tmp_path)
    monkeypatch.setattr(api, "_schwach", lambda: False)
    da = {"modell": False}
    monkeypatch.setattr(api._ki.ordner, "modell_da", lambda m: da["modell"])
    assert api._ki.ordner.server_exe.is_file()
    assert api._kann_fuer_andere_antworten() is False
    da["modell"] = True
    assert api._kann_fuer_andere_antworten() is True
    api._ki.ordner.server_exe.unlink()
    assert api._kann_fuer_andere_antworten() is False
