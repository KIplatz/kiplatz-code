# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_install


def _portable(root: Path) -> Path:
    (root / "python").mkdir(parents=True)
    (root / "python" / "pythonw.exe").write_bytes(b"MZ-python")
    for d in app_install.STARTER_DLLS:
        (root / "python" / d).write_bytes(b"MZ-" + d.encode())
    (root / "node-agent" / "webapp").mkdir(parents=True)
    (root / "node-agent" / "app_web.py").write_text("print('app')\n", encoding="utf-8")
    (root / "node-agent" / "webapp" / "index.html").write_text("<html>", encoding="utf-8")
    app_install.starter_anlegen(root)
    return root


def test_starter_is_the_signed_pythonw_copy_with_its_dlls_and_pth(tmp_path):
    root = _portable(tmp_path / "CommunityAI")
    assert (root / "KIplatz.exe").read_bytes() == b"MZ-python"
    for d in app_install.STARTER_DLLS:
        assert (root / d).read_bytes() == b"MZ-" + d.encode()
    pth = (root / "KIplatz._pth").read_text(encoding="ascii").splitlines()
    assert pth == ["python\\python312.zip", "python", "python\\Lib\\site-packages", "node-agent", "import site"]
    assert not any(p.name.endswith(".neu") for p in root.iterdir())
    (root / "Community AI.cmd").write_text("@echo off\r\n", encoding="ascii")
    app_install.starter_anlegen(root)
    assert not (root / "Community AI.cmd").exists()
    text = (Path(__file__).resolve().parent.parent / "sitecustomize.py").read_text(encoding="utf-8")
    assert 'LAUNCHER_NAMES = ("kiplatz.exe", "community ai.exe")' in text and "os._exit(0)" in text and "app_web.py" in text and "Zone.Identifier" in text


@pytest.mark.skipif(sys.platform != "win32", reason="alternate data streams exist on Windows only")
def test_mark_of_the_web_is_removed_from_our_own_folder_and_does_not_travel_with_the_copy(tmp_path):
    root = _portable(tmp_path / "Downloads" / "CommunityAI")
    for p in root.rglob("*"):
        if p.is_file():
            Path(str(p) + ":Zone.Identifier").write_text("[ZoneTransfer]\r\nZoneId=3\r\n", encoding="ascii")
    assert Path(str(root / "KIplatz.exe") + ":Zone.Identifier").read_text(encoding="ascii").startswith("[ZoneTransfer]")
    ziel = tmp_path / "Programme" / "CommunityAI"
    assert app_install.ensure_installed_portable(root, ziel, bau="2026-09-17m")[0] == "eingerichtet"
    for p in list(root.rglob("*")) + list(ziel.rglob("*")):
        if p.is_file():
            assert not Path(str(p) + ":Zone.Identifier").exists(), p


def test_portable_root_is_detected_only_from_the_python_folder_next_to_the_start_file(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI")
    monkeypatch.setattr(sys, "executable", str(root / "python" / "pythonw.exe"))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert app_install.portable_root() == root
    assert app_install.start_command(root) == [str(root / "python" / "pythonw.exe"), str(root / "node-agent" / "app_web.py")]
    assert (root / "KIplatz.exe").is_file()
    monkeypatch.setattr(sys, "executable", str(tmp_path / "irgendwo" / "python.exe"))
    assert app_install.portable_root() is None
    monkeypatch.setattr(sys, "executable", str(root / "python" / "pythonw.exe"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app_install.portable_root() is None


def test_portable_setup_copies_once_updates_sources_and_uninstall_removes_only_its_folders(tmp_path):
    root = _portable(tmp_path / "Downloads" / "CommunityAI")
    ziel = tmp_path / "Programme" / "CommunityAI"
    was, info = app_install.ensure_installed_portable(root, ziel, bau="2026-09-17k")
    assert was == "eingerichtet" and info.exe_path == ziel / "KIplatz.exe" and info.exe_sha256 == "2026-09-17k"
    assert (ziel / "python" / "pythonw.exe").is_file() and (ziel / "node-agent" / "webapp" / "index.html").is_file() and (ziel / "KIplatz.exe").is_file() and (ziel / "python312.dll").is_file()
    assert app_install.installed_info(ziel).exe_path.name == "KIplatz.exe"
    assert app_install.ensure_installed_portable(root, ziel, bau="2026-09-17k")[0] == "unveraendert"
    (root / "node-agent" / "app_web.py").write_text("print('neu')\n", encoding="utf-8")
    was, info2 = app_install.ensure_installed_portable(root, ziel, bau="2026-09-17l")
    assert was == "aktualisiert" and info2.exe_sha256 == "2026-09-17l" and (ziel / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('neu')\n"
    assert (ziel / "node-agent.alt").is_dir()
    app_install.alt_aufraeumen(ziel)
    assert not (ziel / "node-agent.alt").exists()
    assert app_install.ensure_installed_portable(ziel, ziel, bau="2026-09-17l")[0] == "programmordner"
    (ziel / "KIplatz.exe").unlink()
    (ziel / "Community AI.cmd").write_text("@echo off\r\n", encoding="ascii")
    assert app_install.ensure_installed_portable(ziel, ziel, bau="2026-09-17l")[0] == "programmordner"
    assert (ziel / "KIplatz.exe").is_file() and not (ziel / "Community AI.cmd").exists()
    cmd = app_install.shortcut_command(ziel / "python" / "pythonw.exe", tmp_path / "Desktop" / "KIplatz.lnk", args=f'"{ziel / "node-agent" / "app_web.py"}"', arbeitsordner=ziel)
    script = cmd[-1]
    assert "pythonw.exe" in script and "$s.Arguments = '\"" in script and "app_web.py" in script and f"WorkingDirectory = '{ziel}'" in script
    auto = app_install.autostart_command_portable(ziel, produktiv=False)
    assert auto.startswith(f'"{ziel / "python" / "pythonw.exe"}" "{ziel / "node-agent" / "app_web.py"}" --autostart')
    (ziel / "meine-notiz.txt").write_text("bleibt", encoding="utf-8")
    entfernt = app_install.uninstall(ziel, registry=app_install.MemoryRegistry())
    assert not (ziel / "python").exists() and not (ziel / "node-agent").exists() and not (ziel / "KIplatz.exe").exists() and not (ziel / "python312.dll").exists() and not (ziel / "KIplatz._pth").exists()
    assert (ziel / "meine-notiz.txt").exists() and ziel.is_dir()


def _quelle_zip(text: str, bau: str = "2026-09-17l") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("node-agent/app_web.py", text)
        z.writestr("node-agent/app_core.py", f'APP_BUILD = "{bau}"\n')
        z.writestr("node-agent/webapp/index.html", "<html>neu")
    return buf.getvalue()


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_marker_follows_the_running_build_in_the_program_folder(tmp_path):
    root = _portable(tmp_path / "Downloads" / "CommunityAI")
    ziel = tmp_path / "Programme" / "CommunityAI"
    app_install.ensure_installed_portable(root, ziel, bau="2026-09-26s")
    eingerichtet = app_install.installed_info(ziel).installed_at
    app_install._marker_schreiben(ziel, exe_sha256="2026-09-26s", app_version="?", art="portable", installed_at=eingerichtet)
    was, info = app_install.ensure_installed_portable(ziel, ziel, bau="2026-09-27a")
    assert was == "programmordner" and info.exe_sha256 == "2026-09-27a" and info.app_version == app_core.APP_VERSION
    neu = app_install.installed_info(ziel)
    assert neu.exe_sha256 == "2026-09-27a" and neu.app_version == app_core.APP_VERSION and neu.installed_at == eingerichtet
    vorher = (ziel / app_install.MARKER_NAME).stat().st_mtime_ns
    app_install.ensure_installed_portable(ziel, ziel, bau="2026-09-27a")
    assert (ziel / app_install.MARKER_NAME).stat().st_mtime_ns == vorher


def test_portable_update_replaces_the_sources_only_with_a_verified_zip_and_a_new_build(tmp_path, monkeypatch):
    ziel = _portable(tmp_path / "Programme" / "CommunityAI")
    app_install.ensure_installed_portable(ziel, ziel, bau="2026-09-17k")
    server = {"bau": "2026-09-17k", "zip": _quelle_zip("print('vom server')\n")}
    server["sha"] = hashlib.sha256(server["zip"]).hexdigest()
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    monkeypatch.setattr(app_install, "UPDATE_PUBKEY_B64", base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    server["sig"] = app_install.signieren(server["zip"], pem)
    aufrufe = []

    def oeffner(req, timeout):
        aufrufe.append(req.full_url.rsplit("/", 1)[1])
        if req.full_url.endswith("bau.txt"):
            return _R(f"{server['bau']}\n".encode())
        if req.full_url.endswith(".sha256"):
            return _R(f"{server['sha']}  CommunityAI-quelle.zip\n".encode())
        if req.full_url.endswith(".sig"):
            return _R((server["sig"] + "\n").encode())
        return _R(server["zip"])

    was, _ = app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="2026-09-17k", oeffner=oeffner)
    assert was == "aktuell" and aufrufe == ["bau.txt", "neuester.txt", "neuester.txt.sig"]
    server["bau"] = "2026-09-17l"
    was, text = app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="2026-09-17k", oeffner=oeffner)
    assert was == "aktualisiert" and "2026-09-17l" in text
    assert (ziel / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('vom server')\n" and (ziel / "node-agent.alt" / "app_web.py").is_file()
    assert json.loads((ziel / "installiert.json").read_text(encoding="utf-8"))["exe_sha256"] == "2026-09-17l"
    assert not (ziel / "CommunityAI-quelle.zip.neu").exists() and not (ziel / "node-agent.neu").exists()
    server["bau"] = "2026-09-17m"
    server["zip"] = _quelle_zip("print('fremd')\n")
    with pytest.raises(app_core.AppError) as e:
        app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="2026-09-17l", oeffner=oeffner)
    assert e.value.code == "UPDATE_PRUEFSUMME" and (ziel / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('vom server')\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../boese.py", "x")
        z.writestr("node-agent/app_web.py", "x")
    server["zip"] = buf.getvalue()
    server["sha"] = hashlib.sha256(server["zip"]).hexdigest()
    server["sig"] = app_install.signieren(server["zip"], pem)
    with pytest.raises(app_core.AppError) as e2:
        app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="2026-09-17l", oeffner=oeffner)
    assert e2.value.code == "UPDATE_DATEI" and not (tmp_path / "Programme" / "boese.py").exists()
    server["zip"] = _quelle_zip("print('vom angreifer')\n")
    server["sha"] = hashlib.sha256(server["zip"]).hexdigest()
    fremd = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    server["sig"] = app_install.signieren(server["zip"], fremd)
    with pytest.raises(app_core.AppError) as e4:
        app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="2026-09-17l", oeffner=oeffner)
    assert e4.value.code == "UPDATE_SIGNATUR" and (ziel / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('vom server')\n"
    assert not app_install.signatur_gueltig(b"x", "kein base64!!") and not app_install.signatur_gueltig(server["zip"], "")
    def tot(req, timeout):
        raise OSError("aus")
    with pytest.raises(app_core.AppError) as e3:
        app_install.update_quelle_holen("https://srv.invalid:8444", ziel, eigener_bau="x", oeffner=tot)
    assert e3.value.code == "UPDATE_SERVER"
