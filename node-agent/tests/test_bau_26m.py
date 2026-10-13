# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import app_install
import pakete_tausch

HIER = Path(__file__).resolve().parent.parent
VORNE = "python/Lib/site-packages/"


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _geraet(tmp_path, pakete_txt=None):
    root = tmp_path / "KIplatz"
    sp = root / "python" / "Lib" / "site-packages"
    (sp / "cryptography").mkdir(parents=True)
    (sp / "cryptography" / "__init__.py").write_text("__version__ = '43.0.3'\n", encoding="utf-8")
    (sp / "cryptography-43.0.3.dist-info").mkdir()
    (sp / "cryptography-43.0.3.dist-info" / "RECORD").write_text(
        "cryptography/__init__.py,sha256=x,1\ncryptography-43.0.3.dist-info/RECORD,,\n", encoding="utf-8")
    (sp / "webview").mkdir()
    (sp / "webview" / "__init__.py").write_text("ALT = True\n", encoding="utf-8")
    (root / "node-agent").mkdir()
    (root / "node-agent" / "pakete.txt").write_text(pakete_txt or "# site-packages dieses Baus\ncryptography\ncryptography-50.0.1.dist-info\n"
                                                    "segno\nwebview\n", encoding="utf-8")
    return root, sp


def _programm_zip(record_extra=""):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(VORNE + "cryptography/__init__.py", "__version__ = '50.0.1'\n")
        z.writestr(VORNE + "cryptography/hazmat/_rust.pyd", "RUST")
        z.writestr(VORNE + "cryptography-50.0.1.dist-info/METADATA", "Name: cryptography\nVersion: 50.0.1\n")
        z.writestr(VORNE + "cryptography-50.0.1.dist-info/RECORD",
                   "cryptography/__init__.py,sha256=y,1\ncryptography/hazmat/_rust.pyd,sha256=z,4\n"
                   "cryptography-50.0.1.dist-info/METADATA,,\ncryptography-50.0.1.dist-info/RECORD,,\n" + record_extra)
        z.writestr(VORNE + "segno/__init__.py", "QR = 1\n")
        z.writestr(VORNE + "webview/__init__.py", "NEU = True\n")
    return buf.getvalue()


def _schluessel(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    monkeypatch.setattr(app_install, "UPDATE_PUBKEY_B64", base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _server(daten, sig):
    aufrufe = []

    def oeffner(req, timeout):
        name = req.full_url.rsplit("/", 1)[1]
        aufrufe.append(name)
        if name.endswith(".sha256"):
            return _R(f"{hashlib.sha256(daten['zip']).hexdigest()}  CommunityAI.zip\n".encode())
        if name.endswith(".sig"):
            return _R((sig() + "\n").encode())
        return _R(daten["zip"])
    return oeffner, aufrufe


def _nachholen(root, monkeypatch, zip_bytes=None):
    pem = _schluessel(monkeypatch)
    daten = {"zip": zip_bytes or _programm_zip()}
    oeffner, aufrufe = _server(daten, lambda: app_install.signieren(daten["zip"], pem))
    return app_install.pakete_nachholen("https://srv.invalid:8444", root, oeffner=oeffner), aufrufe


def test_an_outdated_package_is_recognised_by_its_dist_info():
    assert app_install._projekt("cryptography-50.0.1.dist-info") == "cryptography"
    assert app_install._projekt("typing_extensions-4.16.0.dist-info") == "typing-extensions"


def test_the_update_stages_the_new_version_whole_and_never_puts_it_beside_the_old_one(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    assert app_install.veraltete_pakete(root) == {"cryptography-50.0.1.dist-info": "cryptography-43.0.3.dist-info"}
    geholt, _ = _nachholen(root, monkeypatch)
    assert geholt == ["segno", "tausch:cryptography 43.0.3 -> 50.0.1"]
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '43.0.3'\n"
    assert not (sp / "cryptography-50.0.1.dist-info").exists() and (sp / "cryptography-43.0.3.dist-info").is_dir()
    assert (sp / "webview" / "__init__.py").read_text(encoding="utf-8") == "ALT = True\n" and (sp / "segno").is_dir()
    plan = json.loads((root / "pakete.tausch" / "plan.json").read_text(encoding="utf-8"))
    assert plan == {"pakete": ["cryptography 43.0.3 -> 50.0.1"], "alt": ["cryptography", "cryptography-43.0.3.dist-info"],
                    "neu": ["cryptography", "cryptography-50.0.1.dist-info"]}
    assert (root / "pakete.tausch" / "cryptography" / "hazmat" / "_rust.pyd").read_text() == "RUST"
    assert not (root / "pakete.neu").exists() and not (root / "CommunityAI.zip.neu").exists()


def test_the_swap_at_the_start_puts_the_new_version_in_and_keeps_the_old_one_for_one_start(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    _nachholen(root, monkeypatch)
    assert pakete_tausch.beim_start(root, warten_s=0) == "getauscht"
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '50.0.1'\n"
    assert (sp / "cryptography-50.0.1.dist-info").is_dir() and not (sp / "cryptography-43.0.3.dist-info").exists()
    sicherung = list((root / "pakete.alt").iterdir())
    assert len(sicherung) == 1 and (sicherung[0] / "cryptography-43.0.3.dist-info").is_dir()
    assert not (root / "pakete.tausch").exists()
    assert "OK getauscht cryptography 43.0.3 -> 50.0.1" in (root / "pakete-tausch.txt").read_text(encoding="utf-8")
    assert pakete_tausch.beim_start(root, warten_s=0) == ""
    assert app_install.veraltete_pakete(root) == {} and app_install.fehlende_pakete(root) == []


def test_while_the_old_program_still_holds_the_files_everything_stays_as_it_was(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    _nachholen(root, monkeypatch)
    echt = os.replace

    def gesperrt(a, b):
        if Path(a).parent == sp and Path(a).name == "cryptography":
            raise PermissionError("die Datei wird von einem anderen Prozess verwendet")
        return echt(a, b)
    monkeypatch.setattr(pakete_tausch.os, "replace", gesperrt)
    assert pakete_tausch.beim_start(root, warten_s=0) == "wartet"
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '43.0.3'\n"
    assert (sp / "cryptography-43.0.3.dist-info").is_dir() and not (sp / "cryptography-50.0.1.dist-info").exists()
    assert (root / "pakete.tausch" / "plan.json").is_file() and (root / "pakete.tausch" / "cryptography-50.0.1.dist-info").is_dir()
    assert "WARTET" in (root / "pakete-tausch.txt").read_text(encoding="utf-8")
    geholt, aufrufe = _nachholen(root, monkeypatch)
    assert geholt == [] and aufrufe == []
    monkeypatch.setattr(pakete_tausch.os, "replace", echt)
    assert pakete_tausch.beim_start(root, warten_s=0) == "getauscht"


def test_even_if_putting_the_old_version_back_fails_nothing_is_deleted_and_the_next_start_heals_it(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    _nachholen(root, monkeypatch)
    echt = os.replace

    def kaputt(a, b):
        if Path(b).parent == sp and Path(b).name == "cryptography":
            raise PermissionError("gesperrt")
        return echt(a, b)
    monkeypatch.setattr(pakete_tausch.os, "replace", kaputt)
    assert pakete_tausch.beim_start(root, warten_s=0) == "wartet"
    sicherung = next((root / "pakete.alt").iterdir())
    assert (sicherung / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '43.0.3'\n"
    assert (root / "pakete.tausch" / "cryptography").is_dir() and (root / "pakete.tausch" / "plan.json").is_file()
    assert "FEHLER" in (root / "pakete-tausch.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(pakete_tausch.os, "replace", echt)
    assert pakete_tausch.beim_start(root, warten_s=0) == "getauscht"
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '50.0.1'\n"
    assert (sp / "cryptography-50.0.1.dist-info").is_dir() and not (sp / "cryptography-43.0.3.dist-info").exists()


@pytest.mark.parametrize("plan", [
    {"pakete": ["x"], "alt": ["../../windows"], "neu": ["cryptography"]},
    {"pakete": ["x"], "alt": ["cryptography"], "neu": ["C:\\boese"]},
    {"pakete": ["x"], "alt": [], "neu": []},
    {"pakete": ["x"], "alt": ["cryptography"], "neu": ["fehlt-auf-der-buehne"]},
    "kein json {",
])
def test_a_broken_or_foreign_plan_is_thrown_away_and_nothing_moves(tmp_path, plan):
    root, sp = _geraet(tmp_path)
    buehne = root / "pakete.tausch"
    (buehne / "cryptography").mkdir(parents=True)
    (buehne / "plan.json").write_text(plan if isinstance(plan, str) else json.dumps(plan), encoding="utf-8")
    assert pakete_tausch.beim_start(root, warten_s=0) == "verworfen"
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '43.0.3'\n"
    assert not buehne.exists() and not (root / "pakete.alt").exists()


def test_a_folder_another_package_also_owns_is_never_moved(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    (sp / "anderes-1.0.dist-info").mkdir()
    (sp / "anderes-1.0.dist-info" / "RECORD").write_text("cryptography/anderes.py,,\nanderes-1.0.dist-info/RECORD,,\n", encoding="utf-8")
    geholt, _ = _nachholen(root, monkeypatch)
    assert geholt == ["segno"]
    assert not (root / "pakete.tausch").exists() and not (sp / "cryptography-50.0.1.dist-info").exists()
    assert (sp / "cryptography" / "__init__.py").read_text(encoding="utf-8") == "__version__ = '43.0.3'\n"


def test_a_package_that_names_parts_the_build_does_not_list_is_refused(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    with pytest.raises(app_core.AppError) as e:
        _nachholen(root, monkeypatch, _programm_zip(record_extra="fremdes_modul.py,,\n"))
    assert e.value.code == "PAKETE_DATEI"
    assert not (root / "pakete.tausch").exists() and not (sp / "segno").exists()


def test_a_wrong_signature_stages_nothing(tmp_path, monkeypatch):
    root, sp = _geraet(tmp_path)
    pem = _schluessel(monkeypatch)
    daten = {"zip": _programm_zip()}
    fremd = app_install.signieren(b"etwas anderes", pem)
    oeffner, _ = _server(daten, lambda: fremd)
    with pytest.raises(app_core.AppError) as e:
        app_install.pakete_nachholen("https://srv.invalid:8444", root, oeffner=oeffner)
    assert e.value.code == "PAKETE_SIGNATUR" and not (root / "pakete.tausch").exists()


def test_a_start_from_the_source_never_swaps_anything():
    assert pakete_tausch.programm_ordner() is None
    assert pakete_tausch.beim_start() == ""


def test_the_swap_runs_before_any_module_that_could_load_cryptography():
    quelle = (HIER / "app_web.py").read_text(encoding="utf-8")
    aufruf = quelle.index("pakete_tausch.beim_start()")
    assert aufruf < quelle.index("import abgleich_geraet") and aufruf < quelle.index("import app_install")
    kopf = quelle[:aufruf]
    assert "cryptography" not in kopf.replace("# Bau 26m (27.09.2026): a package the update left waiting (e.g. a newer cryptography)", "")
    import ast
    baum = ast.parse((HIER / "pakete_tausch.py").read_text(encoding="utf-8"))
    namen = {a.name.split(".")[0] for n in ast.walk(baum) if isinstance(n, ast.Import) for a in n.names}
    namen |= {n.module.split(".")[0] for n in ast.walk(baum) if isinstance(n, ast.ImportFrom) and n.module}
    assert namen <= {"__future__", "json", "os", "shutil", "sys", "time", "datetime", "pathlib"}


def test_the_build_ships_the_patched_cryptography_with_its_checksum():
    bau = (HIER / "requirements-bau.txt").read_text(encoding="utf-8")
    assert "cryptography==50.0.1 \\" in bau and "aed8db4f6d71c51efb89530e12d9464e7bf2923d46c3205dc794a2a93f8c0648" in bau
    assert "cryptography==43" not in bau
    assert "cryptography>=50.0.1,<51" in (HIER / "requirements.txt").read_text(encoding="utf-8")
