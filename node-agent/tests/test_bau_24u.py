# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import types
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_web


def _core(tmp_path):
    core = app_core.AppCore(base_dir=tmp_path / "b")
    core.ensure_directories()
    return core


def test_on_windows_the_ordinary_web_calls_go_through_windows_verification(tmp_path, monkeypatch):
    erzeugt = []

    class FakeKontext:
        def __init__(self, protokoll):
            erzeugt.append(protokoll)

    monkeypatch.setitem(sys.modules, "truststore", types.SimpleNamespace(SSLContext=FakeKontext))
    installiert = []
    monkeypatch.setattr(urllib.request, "install_opener", installiert.append)
    core = _core(tmp_path)
    assert app_web.windows_zertifikate(core, system="Windows")
    import ssl
    assert erzeugt == [ssl.PROTOCOL_TLS_CLIENT] and len(installiert) == 1
    https = [h for h in installiert[0].handlers if isinstance(h, urllib.request.HTTPSHandler)]
    assert len(https) == 1 and isinstance(https[0]._context, FakeKontext)
    assert "OK zertifikate" in (core.base_dir / "diagnose" / "protokoll.txt").read_text(encoding="utf-8")


def test_other_systems_and_a_missing_package_change_nothing_but_say_so(tmp_path, monkeypatch):
    installiert = []
    monkeypatch.setattr(urllib.request, "install_opener", installiert.append)
    assert not app_web.windows_zertifikate(None, system="Linux") and not installiert
    monkeypatch.setitem(sys.modules, "truststore", None)
    core = _core(tmp_path)
    assert not app_web.windows_zertifikate(core, system="Windows") and not installiert
    assert "FEHLER zertifikate: truststore fehlt" in (core.base_dir / "diagnose" / "protokoll.txt").read_text(encoding="utf-8")


def test_a_fetched_truststore_switches_over_without_a_restart():
    src = (Path(__file__).resolve().parent.parent / "app_web.py").read_text(encoding="utf-8")
    i = src.index('_log(self._core, f"OK pakete nachgeholt:')
    assert 'if "truststore" in geholt:' in src[i:i + 500] and "windows_zertifikate(self._core)" in src[i:i + 500]


def test_the_package_is_pinned_and_the_pinned_connections_keep_their_own_context():
    hier = Path(__file__).resolve().parent.parent
    bau = (hier / "requirements-bau.txt").read_text(encoding="utf-8")
    assert "truststore==0.10.4 \\\n    --hash=sha256:adaeaecf1cbb5f4de3b1959b42d41f6fab57b2b1666adb59e89cb0b53361d981" in bau.replace("\r\n", "\n")
    assert "truststore>=0.10,<0.11" in (hier / "requirements.txt").read_text(encoding="utf-8")
    src = (hier / "app_web.py").read_text(encoding="utf-8")
    assert "inject_into_ssl" not in src and "CERT_NONE" not in src and "check_hostname = False" not in src
