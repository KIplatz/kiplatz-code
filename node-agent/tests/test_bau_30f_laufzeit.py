# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_install
import sitecustomize


class _R:
    def __init__(self, b: bytes):
        self._b = b

    def read(self, n=-1):
        d, self._b = (self._b if n < 0 else self._b[:n]), (b"" if n < 0 else self._b[n:])
        return d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _portable(root: Path, version: str = "3.12.10", bau_laufzeit: str = "3.12.10") -> Path:
    (root / "python").mkdir(parents=True)
    for n in ("python.exe", "pythonw.exe", "python312.zip") + app_install.STARTER_DLLS:
        (root / "python" / n).write_bytes(b"ALT-" + n.encode())
    (root / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (root / "node-agent" / "webapp").mkdir(parents=True)
    (root / "node-agent" / "app_web.py").write_text("print('app')\n", encoding="utf-8")
    (root / "node-agent" / "app_core.py").write_text(f'APP_BUILD = "{app_core.APP_BUILD}"\n', encoding="utf-8")
    (root / "node-agent" / "laufzeit.txt").write_text(bau_laufzeit + "\n", encoding="utf-8")
    app_install.starter_anlegen(root)
    return root


def _programm_zip(version: str, *, ohne: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in ("python.exe", "pythonw.exe", "python312.zip") + app_install.STARTER_DLLS:
            if n != ohne:
                z.writestr("python/" + n, b"NEU-" + n.encode())
        z.writestr("python/Lib/site-packages/cryptography/__init__.py", "")
        z.writestr("node-agent/app_web.py", "print('app')\n")
        z.writestr("KIplatz.exe", b"NEU-pythonw.exe")
    return buf.getvalue()


def _server(monkeypatch, zip_bytes: bytes):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    monkeypatch.setattr(app_install, "UPDATE_PUBKEY_B64", base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    sha = hashlib.sha256(zip_bytes).hexdigest()
    sig = app_install.signieren(zip_bytes, pem)
    aufrufe = []

    def oeffner(req, timeout):
        aufrufe.append(req.full_url.rsplit("/", 1)[1])
        if req.full_url.endswith(".sha256"):
            return _R(f"{sha}  CommunityAI.zip\n".encode())
        if req.full_url.endswith(".sig"):
            return _R((sig + "\n").encode())
        return _R(zip_bytes)
    return oeffner, aufrufe


def test_veraltet_nur_bei_neuerem_python_derselben_reihe(tmp_path):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    assert app_install.laufzeit_im_bau(root) == (3, 12, 14)
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10)) == "3.12.14"
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 14)) == ""
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 15)) == ""
    assert app_install.laufzeit_veraltet(root, laufend=(3, 11, 9)) == ""
    (root / "node-agent" / "laufzeit.txt").write_text("murks\n", encoding="utf-8")
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10)) == ""
    (root / "node-agent" / "laufzeit.txt").unlink()
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10)) == ""
    (root / "node-agent" / "laufzeit.txt").write_text("3.12.14\n", encoding="utf-8")
    (root / app_install.RUECKWEG_DATEI).write_text(json.dumps({"laufzeit": "3.12.14", "zeit_s": time.time()}), encoding="utf-8")
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10)) == ""
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10), jetzt=time.time() + 2 * 86400) == "3.12.14"


def test_vorbereitung_aus_dem_unterschriebenen_zip_und_der_starter_setzt_ein(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    oeffner, aufrufe = _server(monkeypatch, _programm_zip("3.12.14"))
    geprobt = []

    def pruefer(py: Path) -> str:
        geprobt.append(py)
        return "3.12.14" if (py / "python.exe").read_bytes() == b"NEU-python.exe" else ""

    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=pruefer) == "3.12.14"
    assert aufrufe == ["CommunityAI.zip.sha256", "CommunityAI.zip.sig", "CommunityAI.zip"]
    assert geprobt == [root / "laufzeit.neu" / "python"]
    assert (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe"
    assert not (root / "python.alt").exists() and not (root / app_install.PROBE_DATEI).exists() and not (root / "CommunityAI.zip.neu").exists()
    assert app_install.laufzeit_bereit(root) == "3.12.14"
    t = json.loads((root / "laufzeit.neu" / "tausch.json").read_text(encoding="utf-8"))
    assert t["laufzeit"] == "3.12.14" and t["mit_quellen"] is False and t["versuche"] == 0 and t["von"] == app_core.APP_BUILD
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=pruefer) == "3.12.14"
    assert len(aufrufe) == 3 and len(geprobt) == 1
    app_install.alt_aufraeumen(root)
    assert app_install.laufzeit_bereit(root) == "3.12.14"
    app_install.alt_aufraeumen(root, jetzt=time.time() + 2 * 86400)
    assert not (root / "laufzeit.neu").exists()
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=pruefer) == "3.12.14"
    assert sitecustomize._grundlage_einsetzen(str(root)) == "eingesetzt"
    assert (root / "python" / "python.exe").read_bytes() == b"NEU-python.exe"
    assert (root / "python" / "Lib" / "site-packages" / "cryptography" / "__init__.py").is_file()
    assert (root / "python.alt" / "python.exe").read_bytes() == b"ALT-python.exe"
    assert (root / "KIplatz.exe").read_bytes() == b"NEU-pythonw.exe"
    assert (root / "python312.dll").read_bytes() == b"NEU-python312.dll"
    assert not (root / "laufzeit.neu").exists()
    p = json.loads((root / app_install.PROBE_DATEI).read_text(encoding="utf-8"))
    assert p["laufzeit"] == "3.12.14" and p["starts"] == 0 and p["von"] == app_core.APP_BUILD
    assert "OK laufzeit: Programm-Grundlage 3.12.14 eingesetzt" in (root / "pakete-tausch.txt").read_text(encoding="utf-8")
    assert sitecustomize._grundlage_einsetzen(str(root)) == "keine"
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 14, "final", 0))
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=pruefer) == ""


def test_starter_zaehlt_belegte_versuche_und_gibt_nach_zwei_auf(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    oeffner, aufrufe = _server(monkeypatch, _programm_zip("3.12.14"))
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14") == "3.12.14"
    echt = sitecustomize.os.replace

    def belegt(a, b):
        if str(a) == str(root / "python"):
            raise PermissionError(13, "Zugriff verweigert")
        return echt(a, b)

    monkeypatch.setattr(sitecustomize.os, "replace", belegt)
    assert sitecustomize._grundlage_einsetzen(str(root), warte_s=0) == "belegt"
    assert (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe" and app_install.laufzeit_bereit(root) == "3.12.14"
    assert json.loads((root / "laufzeit.neu" / "tausch.json").read_text(encoding="utf-8"))["versuche"] == 1
    assert sitecustomize._grundlage_einsetzen(str(root), warte_s=0) == "belegt"
    assert sitecustomize._grundlage_einsetzen(str(root), warte_s=0) == "aufgegeben"
    assert not (root / "laufzeit.neu").exists() and not (root / "python.alt").exists()
    r = json.loads((root / sitecustomize.RUECKWEG_DATEI).read_text(encoding="utf-8"))
    assert r["laufzeit"] == "3.12.14" and r["grund"] == "einsetzen"
    assert "zweimal nicht einsetzen" in app_install.rueckweg_hinweis(root)
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14") == ""
    assert len(aufrufe) == 3
    monkeypatch.setattr(sitecustomize.os, "replace", echt)
    (root / "laufzeit.neu").mkdir()
    (root / "laufzeit.neu" / "tausch.json").write_text(json.dumps({"laufzeit": "3.12.14", "versuche": 0}), encoding="utf-8")
    assert sitecustomize._grundlage_einsetzen(str(root)) == "unlesbar" and not (root / "laufzeit.neu").exists()
    assert (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe"


def test_programm_setzt_vor_dem_fenster_selbst_ein_wenn_der_starter_uebergangen_wurde(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    assert app_install.grundlage_beim_start_einsetzen(root, ["--autostart"]) is False
    oeffner, _ = _server(monkeypatch, _programm_zip("3.12.14"))
    app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14")
    gestartet = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda befehl, **k: gestartet.append((befehl, k.get("cwd"))))
    assert app_install.grundlage_beim_start_einsetzen(root, ["--autostart", ""]) is True
    assert gestartet == [([str(root / "python" / "pythonw.exe"), str(root / "node-agent" / "app_web.py"), "--autostart"], str(root))]
    assert (root / "python" / "python.exe").read_bytes() == b"NEU-python.exe" and (root / "python.alt").is_dir() and not (root / "laufzeit.neu").exists()


def test_kein_tausch_ohne_probe_ohne_vollstaendiges_paket_oder_fremde_unterschrift(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    oeffner, _ = _server(monkeypatch, _programm_zip("3.12.14"))
    with pytest.raises(app_core.AppError) as e:
        app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "")
    assert e.value.code == "LAUFZEIT_PROBE"
    assert (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe" and not (root / "python.alt").exists() and not (root / "laufzeit.neu").exists()
    assert not (root / app_install.PROBE_DATEI).exists()
    oeffner, _ = _server(monkeypatch, _programm_zip("3.12.14", ohne="python3.dll"))
    with pytest.raises(app_core.AppError) as e2:
        app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14")
    assert e2.value.code == "LAUFZEIT_DATEI" and (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe"
    zip_bytes = _programm_zip("3.12.14")
    oeffner, _ = _server(monkeypatch, zip_bytes)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    fremd = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    sig = app_install.signieren(zip_bytes, fremd)

    def boese(req, timeout):
        if req.full_url.endswith(".sha256"):
            return _R(f"{hashlib.sha256(zip_bytes).hexdigest()}  CommunityAI.zip\n".encode())
        if req.full_url.endswith(".sig"):
            return _R((sig + "\n").encode())
        return _R(zip_bytes)
    with pytest.raises(app_core.AppError) as e3:
        app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=boese, pruefer=lambda py: "3.12.14")
    assert e3.value.code == "PAKETE_SIGNATUR" and not (root / "laufzeit.neu").exists()


def test_starter_holt_nach_zwei_fehlstarts_auch_das_alte_python_zurueck(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.14")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    oeffner, _ = _server(monkeypatch, _programm_zip("3.12.14"))
    app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14")
    assert sitecustomize._grundlage_einsetzen(str(root)) == "eingesetzt"
    assert sitecustomize._rueckweg_pruefen(root) == "gezaehlt" and sitecustomize._rueckweg_pruefen(root) == "gezaehlt"
    assert sitecustomize._rueckweg_pruefen(root) == "zurueck"
    assert (root / "python" / "python.exe").read_bytes() == b"ALT-python.exe"
    assert (root / "python.kaputt" / "python.exe").read_bytes() == b"NEU-python.exe"
    assert not (root / "python.alt").exists() and not (root / "node-agent.kaputt").exists()
    r = json.loads((root / sitecustomize.RUECKWEG_DATEI).read_text(encoding="utf-8"))
    assert r["laufzeit"] == "3.12.14"
    assert "Programm-Grundlage (Python 3.12.14)" in app_install.rueckweg_hinweis(root)
    assert app_install.laufzeit_veraltet(root, laufend=(3, 12, 10)) == ""
    app_install.alt_aufraeumen(root, jetzt=time.time() + 2 * 86400)
    assert not (root / "python.kaputt").exists()
    app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=oeffner, pruefer=lambda py: "3.12.14")
    assert sitecustomize._grundlage_einsetzen(str(root)) == "eingesetzt"
    assert app_install.update_bestaetigen(root) and (root / "python.alt").is_dir()
    app_install.alt_aufraeumen(root)
    assert not (root / "python.alt").exists()


def _programm_zip_313(bau: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in ("python.exe", "pythonw.exe", "python313.zip", "python313.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            z.writestr("python/" + n, b"313-" + n.encode())
        z.writestr("python/Lib/site-packages/cryptography/__init__.py", "")
        z.writestr("node-agent/app_web.py", "print('app 313')\n")
        z.writestr("node-agent/app_core.py", f'APP_BUILD = "{bau}"\n')
        z.writestr("node-agent/laufzeit.txt", "3.13.2\n")
    return buf.getvalue()


def _quelle_zip_313(bau: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("node-agent/app_web.py", "print('app 313')\n")
        z.writestr("node-agent/app_core.py", f'APP_BUILD = "{bau}"\n')
        z.writestr("node-agent/laufzeit.txt", "3.13.2\n")
    return buf.getvalue()


def test_neue_reihe_kommt_nur_mit_quellen_zusammen_und_der_starter_folgt(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.10")
    monkeypatch.setattr(app_install.sys, "version_info", (3, 12, 10, "final", 0))
    bau_neu = "2026-10-15a"
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    monkeypatch.setattr(app_install, "UPDATE_PUBKEY_B64", base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    q = _quelle_zip_313(bau_neu)
    q_sha, q_sig = hashlib.sha256(q).hexdigest(), app_install.signieren(q, pem)

    def quelle_oeffner(req, timeout):
        u = req.full_url
        if u.endswith("bau.txt"):
            return _R(f"{bau_neu}\n".encode())
        if u.endswith("quelle.zip.sha256"):
            return _R(f"{q_sha}  CommunityAI-quelle.zip\n".encode())
        if u.endswith("quelle.zip.sig"):
            return _R((q_sig + "\n").encode())
        return _R(q)
    was, text = app_install.update_quelle_holen("https://srv.invalid:8444", root, eigener_bau="2026-09-30g", oeffner=quelle_oeffner)
    assert was == "grundlage" and text == "3.13.2"
    assert (root / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('app')\n" and not (root / "node-agent.neu").exists()
    p = _programm_zip_313(bau_neu)
    p_sha, p_sig = hashlib.sha256(p).hexdigest(), app_install.signieren(p, pem)

    def paket_oeffner(req, timeout):
        u = req.full_url
        if u.endswith("CommunityAI.zip.sha256"):
            return _R(f"{p_sha}  CommunityAI.zip\n".encode())
        if u.endswith("CommunityAI.zip.sig"):
            return _R((p_sig + "\n").encode())
        return _R(p)
    assert app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=paket_oeffner, pruefer=lambda py: "3.13.2", ziel="3.13.2", eigener_bau="2026-09-30g") == "3.13.2"
    assert (root / "python" / "python312.dll").is_file() and (root / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('app')\n"
    t = json.loads((root / "laufzeit.neu" / "tausch.json").read_text(encoding="utf-8"))
    assert t["mit_quellen"] is True and t["bau"] == bau_neu and t["von"] == "2026-09-30g" and (root / "laufzeit.neu" / "node-agent" / "app_web.py").is_file()
    assert sitecustomize._grundlage_einsetzen(str(root)) == "eingesetzt"
    assert (root / "python" / "python313.dll").is_file() and not (root / "python" / "python312.dll").exists()
    assert (root / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('app 313')\n"
    assert (root / "python.alt" / "python312.dll").is_file() and (root / "node-agent.alt" / "app_web.py").is_file()
    assert (root / "python313.dll").read_bytes() == b"313-python313.dll" and not (root / "python312.dll").exists()
    assert "python\\python313.zip" in (root / "KIplatz._pth").read_text(encoding="ascii").splitlines()[0]
    pr = json.loads((root / app_install.PROBE_DATEI).read_text(encoding="utf-8"))
    assert pr["bau"] == bau_neu and pr["von"] == "2026-09-30g" and pr["laufzeit"] == "3.13.2"
    assert json.loads((root / "installiert.json").read_text(encoding="utf-8"))["exe_sha256"] == bau_neu
    p_alt = _programm_zip_313("2026-09-01a")
    p_sha, p_sig = hashlib.sha256(p_alt).hexdigest(), app_install.signieren(p_alt, pem)
    p = p_alt
    with pytest.raises(app_core.AppError) as e:
        app_install.laufzeit_nachholen("https://srv.invalid:8444", root, oeffner=paket_oeffner, pruefer=lambda py: "3.13.2", ziel="3.13.2", eigener_bau=bau_neu)
    assert e.value.code == "UPDATE_ALT"
    assert sitecustomize._rueckweg_pruefen(root) == "gezaehlt" and sitecustomize._rueckweg_pruefen(root) == "gezaehlt"
    assert sitecustomize._rueckweg_pruefen(root) == "zurueck"
    assert (root / "python" / "python312.dll").is_file() and (root / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('app')\n"
    assert (root / "python.kaputt" / "python313.dll").is_file() and (root / "node-agent.kaputt" / "app_web.py").is_file()
    assert (root / "python312.dll").read_bytes() == b"ALT-python312.dll" and not (root / "python313.dll").exists()
    assert (root / "KIplatz.exe").read_bytes() == b"ALT-pythonw.exe"
    assert (root / "KIplatz._pth").read_text(encoding="ascii").splitlines()[0] == "python\\python312.zip"
    (root / "python313.dll").write_bytes(b"313-python313.dll"); (root / "python312.dll").unlink()
    (root / "KIplatz._pth").write_text("python\\python313.zip\npython\n", encoding="ascii")
    assert not app_install.starter_passt(root)
    assert app_install.ensure_installed_portable(root, root, bau="2026-09-30g")[0] == "programmordner"
    assert app_install.starter_passt(root)
    assert (root / "python312.dll").is_file() and not (root / "python313.dll").exists()
    assert (root / "KIplatz._pth").read_text(encoding="ascii").splitlines()[0] == "python\\python312.zip"


def test_bruecke_bringt_ein_geraet_vor_30g_auf_die_neue_reihe(tmp_path, monkeypatch):
    assert sitecustomize.UPDATE_PUBKEYS_B64 == (app_install.UPDATE_PUBKEY_B64, app_install.UPDATE_PUBKEY_RETTUNG_B64)
    root = _portable(tmp_path / "CommunityAI", bau_laufzeit="3.12.10")
    (root / "installiert.json").write_text(json.dumps({"exe_sha256": "2026-09-30e", "app_version": "0.4.0", "art": "portable"}), encoding="utf-8")
    (root / "node-agent").rename(root / "node-agent.alt")
    (root / "node-agent").mkdir()
    (root / "node-agent" / "app_web.py").write_text("print('app 313')\n", encoding="utf-8")
    (root / "node-agent" / "app_core.py").write_text('APP_BUILD = "2026-10-15a"\n', encoding="utf-8")
    (root / "node-agent" / "laufzeit.txt").write_text("3.13.2\n", encoding="utf-8")
    (root / app_install.PROBE_DATEI).write_text(json.dumps({"bau": "2026-10-15a", "von": "2026-09-30e", "zeit_s": time.time(), "starts": 0}), encoding="utf-8")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    monkeypatch.setattr(sitecustomize, "UPDATE_PUBKEYS_B64", (pub, pub))
    p = _programm_zip_313("2026-10-15a")
    p_sha, p_sig = hashlib.sha256(p).hexdigest(), app_install.signieren(p, pem)
    aufrufe = []

    def oeffner(req, timeout):
        aufrufe.append(req.full_url)
        if req.full_url.endswith(".sha256"):
            return _R(f"{p_sha}  CommunityAI.zip\n".encode())
        if req.full_url.endswith(".sig"):
            return _R((p_sig + "\n").encode())
        return _R(p)
    assert sitecustomize._grundlage_bruecke(str(root), oeffner=oeffner, pruefer=lambda py: "3.13.2", adresse="https://srv.invalid:8444")
    assert aufrufe[0].startswith("https://srv.invalid:8444/download/")
    assert (root / "python" / "python313.dll").is_file() and (root / "python.alt" / "python312.dll").is_file()
    assert (root / "python313.dll").is_file() and not (root / "python312.dll").exists()
    assert (root / "KIplatz._pth").read_bytes().startswith(b"python\\python313.zip\n")
    pr = json.loads((root / app_install.PROBE_DATEI).read_text(encoding="utf-8"))
    assert pr["bau"] == "2026-10-15a" and pr["von"] == "2026-09-30e" and pr["laufzeit"] == "3.13.2" and pr["starts"] == 0
    assert json.loads((root / "installiert.json").read_text(encoding="utf-8"))["exe_sha256"] == "2026-10-15a"
    assert not (root / "laufzeit.neu").exists() and not (root / "CommunityAI.zip.neu").exists()
    assert "OK bruecke: Programm-Grundlage 3.13.2" in (root / "pakete-tausch.txt").read_text(encoding="utf-8")
    assert sitecustomize._rueckweg_pruefen(str(root)) == "gezaehlt" and sitecustomize._rueckweg_pruefen(str(root)) == "gezaehlt"
    assert sitecustomize._rueckweg_pruefen(str(root)) == "zurueck"
    assert (root / "python" / "python312.dll").is_file() and (root / "node-agent" / "app_web.py").read_text(encoding="utf-8") == "print('app')\n"
    (root / "node-agent").rename(root / "node-agent.x"); (root / "node-agent.kaputt").rename(root / "node-agent"); (root / "node-agent.x").rename(root / "node-agent.alt")
    (root / "python.kaputt").rename(root / "python.weg-test")
    assert not sitecustomize._grundlage_bruecke(str(root), oeffner=oeffner, pruefer=lambda py: "", adresse="https://srv.invalid:8444")
    assert (root / "python" / "python312.dll").is_file() and not (root / "python.alt").exists() and not (root / "laufzeit.neu").exists()
    fremd = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    p_sig = app_install.signieren(p, fremd)
    assert not sitecustomize._grundlage_bruecke(str(root), oeffner=oeffner, pruefer=lambda py: "3.13.2", adresse="https://srv.invalid:8444")
    assert not (root / "laufzeit.neu").exists() and not (root / "CommunityAI.zip.neu").exists()


def test_bau_schreibt_laufzeit_und_das_fenster_nennt_es():
    ps1 = (Path(__file__).resolve().parent.parent / "build_app_zip.ps1").read_text(encoding="utf-8")
    assert 'node-agent\\laufzeit.txt' in ps1 and '"$pyVersion`n"' in ps1
    assert '$pyTag = "python"' in ps1 and '"$pyTag.dll"' in ps1 and 'python312.dll' not in ps1
    import neuerungen
    assert any("Programm-Grundlage" in s for s in neuerungen.NEUERUNGEN["2026-09-30f"])
    assert app_install.starter_dlls(Path(__file__).parent / "gibt-es-nicht") == app_install.STARTER_DLLS


def test_signatur_ohne_krypto_baustein_ist_ein_nein(monkeypatch):
    import builtins
    echt = builtins.__import__

    def ohne(name, *a, **k):
        if name.startswith("cryptography"):
            raise ImportError("DLL load failed")
        return echt(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", ohne)
    assert app_install.signatur_gueltig(b"daten", base64.b64encode(b"x" * 64).decode()) is False


def test_starter_tritt_zur_seite_wenn_eine_datei_belegt_ist(tmp_path, monkeypatch):
    root = _portable(tmp_path / "CommunityAI")
    (root / "python314.dll").write_bytes(b"314")
    (root / "KIplatz.exe").write_bytes(b"314-pythonw.exe")
    echt = sitecustomize.os.replace

    def belegt(a, b):
        if str(b).endswith("KIplatz.exe") and str(a).endswith(".neu") and not (root / "KIplatz.exe.weg").exists():
            raise PermissionError("belegt")
        return echt(a, b)

    monkeypatch.setattr(sitecustomize.os, "replace", belegt)
    assert sitecustomize._starter_erneuern(str(root)) == ""
    assert (root / "KIplatz.exe").read_bytes() == b"ALT-pythonw.exe" and (root / "KIplatz.exe.weg").is_file()
    assert not (root / "python314.dll").exists()
    monkeypatch.setattr(sitecustomize.os, "replace", echt)
    sitecustomize._weg_aufraeumen(str(root))
    assert not list(root.glob("*.weg"))
