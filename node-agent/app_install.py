# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import sicher_schreiben

EXE_NAME = "CommunityAI.exe"
MARKER_NAME = "installiert.json"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "KIplatz"
ALTE_RUN_VALUE_NAMES = ("CommunityAI",)
MAX_EXE_SIZE_BYTES = 200 * 1024 * 1024


def default_install_dir() -> Path:
    return Path.home() / "AppData" / "Local" / "Programs" / "CommunityAI"


def running_exe() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class InstallInfo:
    exe_path: Path
    installed_at: str
    exe_sha256: str
    app_version: str


def installed_info(install_dir: Path | None = None) -> InstallInfo | None:
    target = install_dir or default_install_dir()
    marker = target / MARKER_NAME
    exe = target / EXE_NAME
    if not exe.exists():
        for name in (START_NAME, ALTE_STARTER[0]):
            if (target / name).exists():
                exe = target / name
                break
    if not marker.exists() or not exe.exists():
        return None
    try:
        payload = json.loads(marker.read_bytes()[:4096].decode("utf-8"))
        return InstallInfo(exe_path=exe, installed_at=str(payload["installed_at"]), exe_sha256=str(payload["exe_sha256"]), app_version=str(payload.get("app_version", "?")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def install(source_exe: Path, install_dir: Path | None = None) -> InstallInfo:
    source = Path(source_exe)
    if not source.is_file() or source.is_symlink():
        raise app_core.AppError("INSTALL_QUELLE", "die Programmdatei wurde nicht gefunden")
    size = source.stat().st_size
    if size == 0 or size > MAX_EXE_SIZE_BYTES:
        raise app_core.AppError("INSTALL_QUELLE", "die Programmdatei hat eine unplausible Größe")
    target_dir = app_core.ensure_plain_directory(Path(install_dir or default_install_dir()))
    target = target_dir / EXE_NAME
    if target.exists() and source.resolve() == target.resolve():
        info = installed_info(target_dir)
        if info is not None:
            return info
    expected = _sha256(source)
    tmp = target_dir / (EXE_NAME + ".neu")
    try:
        shutil.copyfile(source, tmp)
        if _sha256(tmp) != expected:
            raise app_core.AppError("INSTALL_KOPIE", "die Kopie stimmt nicht mit dem Original überein")
        os.replace(tmp, target)
    except OSError as exc:
        raise app_core.AppError("INSTALL_KOPIE", f"kopieren fehlgeschlagen: {exc.strerror}") from None
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    info = InstallInfo(exe_path=target, installed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), exe_sha256=expected, app_version=app_core.APP_VERSION)
    sicher_schreiben.json_datei(target_dir / MARKER_NAME, {"installed_at": info.installed_at, "exe_sha256": info.exe_sha256, "app_version": info.app_version}, ascii_=True)
    return info


def ensure_installed(source_exe: Path | None, install_dir: Path | None = None) -> tuple[str, InstallInfo | None]:
    if source_exe is None:
        return "quelle", None
    target_dir = Path(install_dir or default_install_dir())
    source = Path(source_exe)
    try:
        if source.resolve().parent == target_dir.resolve():
            return "programmordner", installed_info(target_dir)
    except OSError:
        pass
    before = installed_info(target_dir)
    if before is not None and before.exe_sha256 == _sha256(source):
        return "unveraendert", before
    info = install(source, target_dir)
    return ("aktualisiert" if before is not None else "eingerichtet"), info


ALT_NAME = "CommunityAI.alt.exe"


def update_holen(adresse: str, install_dir: Path | None = None, *, laufend: Path | None = None, oeffner=None) -> tuple[str, str]:
    import urllib.request
    laufend = laufend or running_exe()
    if laufend is None:
        return "quelle", "Läuft aus der Quelle, Updates kommen über das Repository."
    oeffner = oeffner or __import__("datenfluss").oeffner("Update prüfen oder holen")
    kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
    try:
        with oeffner(urllib.request.Request(adresse.rstrip("/") + "/download/CommunityAI.exe.sha256", headers=kopf), timeout=15) as r:
            erwartet = r.read(200).decode("utf-8", "replace").split()[0].lower()
    except Exception as exc:
        raise app_core.AppError("UPDATE_SERVER", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
    if len(erwartet) != 64 or any(c not in "0123456789abcdef" for c in erwartet):
        raise app_core.AppError("UPDATE_SERVER", "der Server hat keine gültige Prüfsumme geschickt")
    if erwartet == _sha256(laufend):
        return "aktuell", f"Version {app_core.APP_VERSION} ist die aktuelle."
    target_dir = app_core.ensure_plain_directory(Path(install_dir or default_install_dir()))
    target = target_dir / EXE_NAME
    neu = target_dir / (EXE_NAME + ".neu")
    h = hashlib.sha256()
    done = 0
    try:
        with oeffner(urllib.request.Request(adresse.rstrip("/") + "/download/CommunityAI.exe", headers=kopf), timeout=60) as r, open(neu, "wb") as out:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_EXE_SIZE_BYTES:
                    raise app_core.AppError("UPDATE_DATEI", "die Programmdatei vom Server ist unplausibel groß")
                out.write(chunk)
                h.update(chunk)
    except app_core.AppError:
        _still_weg(neu)
        raise
    except Exception as exc:
        _still_weg(neu)
        raise app_core.AppError("UPDATE_DOWNLOAD", f"das Herunterladen ist abgebrochen ({type(exc).__name__})") from None
    if h.hexdigest() != erwartet:
        _still_weg(neu)
        raise app_core.AppError("UPDATE_PRUEFSUMME", "die heruntergeladene Programmdatei stimmt nicht mit der Prüfsumme überein; verworfen")
    alt = target_dir / ALT_NAME
    _still_weg(alt)
    try:
        if target.exists():
            os.replace(target, alt)
        os.replace(neu, target)
    except OSError as exc:
        _still_weg(neu)
        raise app_core.AppError("UPDATE_TAUSCH", f"die neue Datei konnte nicht eingesetzt werden: {exc.strerror}") from None
    info = InstallInfo(exe_path=target, installed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), exe_sha256=erwartet, app_version="?")
    sicher_schreiben.json_datei(target_dir / MARKER_NAME, {"installed_at": info.installed_at, "exe_sha256": info.exe_sha256, "app_version": info.app_version}, ascii_=True)
    return "aktualisiert", "Neue Version geholt und geprüft. Das Programm startet gleich neu."


def alt_aufraeumen(install_dir: Path | None = None, jetzt: float | None = None) -> None:
    target = Path(install_dir or default_install_dir())
    jetzt = time.time() if jetzt is None else jetzt
    _still_weg(target / ALT_NAME)
    shutil.rmtree(target / (QUELLE_DIRNAME + ".neu"), ignore_errors=True)
    tausch = _json_lesen(target / LAUFZEIT_NEU / TAUSCH_DATEI)
    if not laufzeit_bereit(target) or tausch is None or jetzt - float(tausch.get("zeit_s") or 0) > RUECKWEG_FRIST_S:
        shutil.rmtree(target / LAUFZEIT_NEU, ignore_errors=True)
    probe = _json_lesen(target / PROBE_DATEI)
    if probe is None or jetzt - float(probe.get("zeit_s") or 0) > RUECKWEG_FRIST_S:
        shutil.rmtree(target / (QUELLE_DIRNAME + ".alt"), ignore_errors=True)
        shutil.rmtree(target / (PYTHON_DIRNAME + ".alt"), ignore_errors=True)
        _still_weg(target / PROBE_DATEI)
    rueckweg = _json_lesen(target / RUECKWEG_DATEI)
    if rueckweg is None or jetzt - float(rueckweg.get("zeit_s") or 0) > RUECKWEG_FRIST_S:
        shutil.rmtree(target / (QUELLE_DIRNAME + KAPUTT_ENDUNG), ignore_errors=True)
        shutil.rmtree(target / (PYTHON_DIRNAME + KAPUTT_ENDUNG), ignore_errors=True)
        _still_weg(target / RUECKWEG_DATEI)


def _json_lesen(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def update_bestaetigen(install_dir: Path | None = None) -> bool:
    p = Path(install_dir or default_install_dir()) / PROBE_DATEI
    war_da = p.is_file()
    _still_weg(p)
    return war_da


def rueckweg_zeit(install_dir: Path | None = None) -> float:
    r = _json_lesen(Path(install_dir or default_install_dir()) / RUECKWEG_DATEI)
    return float((r or {}).get("zeit_s") or 0.0)


def rueckweg_hinweis(install_dir: Path | None = None, jetzt: float | None = None) -> str:
    r = _json_lesen(Path(install_dir or default_install_dir()) / RUECKWEG_DATEI)
    if r is None:
        return ""
    jetzt = time.time() if jetzt is None else jetzt
    if jetzt - float(r.get("zeit_s") or 0) > RUECKWEG_FRIST_S:
        return ""
    bau = str(r.get("bau") or "?")
    if r.get("laufzeit") and r.get("grund"):
        return f"Die neue Programm-Grundlage (Python {r['laufzeit']}) ließ sich auf diesem Gerät zweimal nicht einsetzen, weil noch eine Datei in Verwendung war. Die bisherige läuft weiter; morgen probiert das Programm es noch einmal. Wenn das öfter passiert, sag es der Community."
    if r.get("laufzeit"):
        return f"Die neue Programm-Grundlage (Python {r['laufzeit']}) ist auf diesem Gerät zweimal nicht gestartet. Die vorige läuft wieder; morgen probiert das Programm es noch einmal. Wenn das öfter passiert, sag es der Community."
    return f"Die neue Version (Bau {bau}) ist auf diesem Gerät zweimal nicht gestartet. Die vorige läuft wieder; morgen probiert das Programm das Update noch einmal. Wenn das öfter passiert, sag es der Community."


def neuester_bau(adresse: str, oeffner) -> str:
    import urllib.request
    oeffner = oeffner or __import__("datenfluss").oeffner("Update prüfen oder holen")
    basis = adresse.rstrip("/") + "/download/"
    kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
    try:
        with oeffner(urllib.request.Request(basis + NEUESTER_DATEI, headers=kopf), timeout=15) as r:
            daten = r.read(200)
        with oeffner(urllib.request.Request(basis + NEUESTER_DATEI + SIGNATUR_ENDUNG, headers=kopf), timeout=15) as r:
            signatur = r.read(400).decode("ascii", "replace").strip()
    except Exception:
        return ""
    if not signatur_gueltig(daten, signatur):
        return ""
    teile = daten.decode("utf-8", "replace").split()
    return teile[0] if len(teile) == 2 and re.fullmatch(r"\d{4}-\d{2}-\d{2}[a-z]{0,3}", teile[0]) else ""


def neuester_pruefen(adresse: str, eigener_bau: str, oeffner, jetzt: float | None = None) -> tuple[str, str]:
    import urllib.request
    basis = adresse.rstrip("/") + "/download/"
    kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
    try:
        with oeffner(urllib.request.Request(basis + NEUESTER_DATEI, headers=kopf), timeout=15) as r:
            daten = r.read(200)
        with oeffner(urllib.request.Request(basis + NEUESTER_DATEI + SIGNATUR_ENDUNG, headers=kopf), timeout=15) as r:
            signatur = r.read(400).decode("ascii", "replace").strip()
    except Exception:
        return "fehlt", "Der Server hat keine unterschriebene Auskunft über den neuesten Bau. Bitte sag es der Community, wenn das morgen noch so ist."
    if not signatur_gueltig(daten, signatur):
        return "ungueltig", "Die Auskunft des Servers über den neuesten Bau trägt keine gültige Unterschrift. Bitte sag es der Community."
    teile = daten.decode("utf-8", "replace").split()
    if len(teile) != 2:
        return "ungueltig", "Die Auskunft des Servers über den neuesten Bau ist unlesbar. Bitte sag es der Community."
    bau, zeit = teile
    if bau < eigener_bau:
        return "rueckstufung", f"Der Server nennt als neuesten Bau {bau}, dieses Programm ist schon Bau {eigener_bau}. Das darf nicht sein; bitte sag es der Community."
    try:
        seit = datetime.strptime(zeit, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return "ungueltig", "Die Auskunft des Servers über den neuesten Bau ist unlesbar. Bitte sag es der Community."
    jetzt = time.time() if jetzt is None else jetzt
    tage = int((jetzt - seit) // 86400)
    if tage > STILLSTAND_TAGE:
        return "stillstand", f"Seit {tage} Tagen kam keine unterschriebene Neuigkeit vom Update-Weg. Das ist ungewöhnlich lange; bitte schau in der Community nach, ob alles in Ordnung ist."
    return "ok", ""


START_NAME = "KIplatz.exe"
START_PTH = "KIplatz._pth"
ALTE_STARTER = ("Community AI.exe", "Community AI._pth", "Community AI.cmd")
STARTER_DLLS = ("python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll")
QUELLE_DIRNAME = "node-agent"
PYTHON_DIRNAME = "python"
QUELLE_ZIP = "CommunityAI-quelle.zip"
UPDATE_PUBKEY_B64 = "Mq0a5sAEHp9ba/kUL/F69I67SooKawCBS7p1mtmKWNw="
UPDATE_PUBKEY_RETTUNG_B64 = "OF758lOi5oKh6rttdYLB5Vb5oIU1KYES9pz+06YKXIw="
SIGNATUR_ENDUNG = ".sig"
NEUESTER_DATEI = "neuester.txt"
STILLSTAND_TAGE = 45
PROBE_DATEI = "update-probe.json"
RUECKWEG_DATEI = "update-rueckweg.json"
KAPUTT_ENDUNG = ".kaputt"
RUECKWEG_FRIST_S = 24 * 3600
PAKET_ZIP = "CommunityAI.zip"
BAU_DATEI = "bau.txt"
MAX_QUELLE_ZIP_BYTES = 50 * 1024 * 1024
PAKETE_DATEI = "pakete.txt"
PROGRAMM_ZIP = "CommunityAI.zip"
MAX_PROGRAMM_ZIP_BYTES = 200 * 1024 * 1024


def portable_root() -> Path | None:
    if getattr(sys, "frozen", False):
        return None
    try:
        exe = Path(sys.executable).resolve()
    except OSError:
        return None
    root = exe.parent.parent
    starter = (root / START_NAME).is_file() or any((root / n).is_file() for n in ALTE_STARTER)
    if exe.parent.name.lower() == PYTHON_DIRNAME and starter and (root / QUELLE_DIRNAME / "app_web.py").is_file():
        return root
    return None


def start_command(root: Path) -> list[str]:
    return [str(Path(root) / PYTHON_DIRNAME / "pythonw.exe"), str(Path(root) / QUELLE_DIRNAME / "app_web.py")]


def starter_anlegen(root: Path) -> Path:
    root = Path(root)
    py = root / PYTHON_DIRNAME
    dlls = starter_dlls(py)
    for name in (("pythonw.exe", START_NAME),) + tuple((d, d) for d in dlls):
        quelle, ziel = py / name[0], root / name[1]
        if not quelle.is_file():
            raise app_core.AppError("INSTALL_QUELLE", f"{name[0]} fehlt im Python-Ordner")
        if ziel.is_file() and _sha256(ziel) == _sha256(quelle):
            continue
        tmp = root / (name[1] + ".neu")
        shutil.copyfile(quelle, tmp)
        if _sha256(tmp) != _sha256(quelle):
            _still_weg(tmp)
            raise app_core.AppError("INSTALL_KOPIE", f"die Kopie von {name[0]} stimmt nicht mit dem Original überein")
        os.replace(tmp, ziel)
    sicher_schreiben.text(root / START_PTH, f"{PYTHON_DIRNAME}\\{stdlib_zip(py)}\n{PYTHON_DIRNAME}\n{PYTHON_DIRNAME}\\Lib\\site-packages\n{QUELLE_DIRNAME}\nimport site\n", encoding="ascii")
    for alt in ALTE_STARTER:
        _still_weg(root / alt)
    for p in root.glob("python3*.dll"):
        if p.name.lower() not in {d.lower() for d in dlls}:
            _still_weg(p)
    for p in root.glob("*.weg"):
        _still_weg(p)
    return root / START_NAME


def starter_dlls(py: Path) -> tuple[str, ...]:
    py = Path(py)
    reihe = sorted(p.name for p in py.glob("python3*.dll") if p.name.lower() != "python3.dll")
    if not reihe:
        return STARTER_DLLS
    return (reihe[-1], "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll")


def starter_passt(root: Path) -> bool:
    root = Path(root)
    py = root / PYTHON_DIRNAME
    try:
        erste = (root / START_PTH).read_text(encoding="ascii").splitlines()[0]
    except (OSError, IndexError, UnicodeDecodeError):
        return False
    return erste == f"{PYTHON_DIRNAME}\\{stdlib_zip(py)}" and all((root / d).is_file() for d in starter_dlls(py))


def stdlib_zip(py: Path) -> str:
    reihe = sorted(p.name for p in Path(py).glob("python3*.zip"))
    return reihe[-1] if reihe else "python312.zip"


def laufzeit_reihe(v: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(v[:2])


def internet_markierung_entfernen(ordner: Path) -> int:
    if os.name != "nt":
        return 0
    n = 0
    for wurzel, _, dateien in os.walk(ordner):
        for name in dateien:
            try:
                os.remove(os.path.join(wurzel, name) + ":Zone.Identifier")
                n += 1
            except OSError:
                pass
    return n


def blockierte_datei(ordner: Path) -> str:
    try:
        for p in sorted(Path(ordner).rglob("*")):
            if not p.is_file():
                continue
            try:
                fd = os.open(str(p), os.O_RDWR | getattr(os, "O_BINARY", 0))
                os.close(fd)
            except PermissionError:
                return str(p.relative_to(ordner))
            except OSError:
                continue
        os.rename(ordner, ordner)
    except PermissionError:
        return "<Ordner>"
    except OSError:
        return ""
    return ""


def _ordner_ersetzen(quelle: Path, ziel: Path) -> None:
    alt = ziel.with_name(ziel.name + ".alt")
    shutil.rmtree(alt, ignore_errors=True)
    if ziel.exists():
        try:
            os.replace(ziel, alt)
        except OSError as exc:
            wer = blockierte_datei(ziel)
            zusatz = f" (in Verwendung: {wer})" if wer else ""
            raise OSError(exc.errno, f"{exc.strerror or exc}{zusatz}", str(ziel)) from None
    os.replace(quelle, ziel)


def _marker_schreiben(target_dir: Path, *, exe_sha256: str, app_version: str, art: str, installed_at: str = "") -> InstallInfo:
    info = InstallInfo(exe_path=target_dir / START_NAME, installed_at=installed_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), exe_sha256=exe_sha256, app_version=app_version)
    sicher_schreiben.json_datei(target_dir / MARKER_NAME, {"installed_at": info.installed_at, "exe_sha256": info.exe_sha256, "app_version": info.app_version, "art": art}, ascii_=True)
    return info


def ensure_installed_portable(root: Path, install_dir: Path | None = None, *, bau: str = "") -> tuple[str, InstallInfo | None]:
    root = Path(root)
    target_dir = Path(install_dir or default_install_dir())
    try:
        if root.resolve() == target_dir.resolve():
            if not (target_dir / START_NAME).is_file() or not starter_passt(target_dir):
                try:
                    starter_anlegen(target_dir)
                except app_core.AppError:
                    pass
            for alt in ALTE_STARTER:
                _still_weg(target_dir / alt)
            info = installed_info(target_dir)
            if info is None:
                info = _marker_schreiben(target_dir, exe_sha256=bau, app_version=app_core.APP_VERSION, art="portable")
            elif bau and (info.exe_sha256 != bau or info.app_version != app_core.APP_VERSION):
                info = _marker_schreiben(target_dir, exe_sha256=bau, app_version=app_core.APP_VERSION, art="portable", installed_at=info.installed_at)
            return "programmordner", info
    except OSError:
        pass
    app_core.ensure_plain_directory(target_dir)
    before = installed_info(target_dir)
    if before is not None and before.exe_sha256 == bau and (target_dir / QUELLE_DIRNAME / "app_web.py").is_file() and (target_dir / PYTHON_DIRNAME / "pythonw.exe").is_file() and (target_dir / START_NAME).is_file():
        return "unveraendert", before
    internet_markierung_entfernen(root)
    if not (target_dir / PYTHON_DIRNAME / "pythonw.exe").is_file():
        neu = target_dir / (PYTHON_DIRNAME + ".neu")
        shutil.rmtree(neu, ignore_errors=True)
        shutil.copytree(root / PYTHON_DIRNAME, neu)
        _ordner_ersetzen(neu, target_dir / PYTHON_DIRNAME)
    neu = target_dir / (QUELLE_DIRNAME + ".neu")
    shutil.rmtree(neu, ignore_errors=True)
    shutil.copytree(root / QUELLE_DIRNAME, neu, ignore=shutil.ignore_patterns("__pycache__", "tests", "dist", "build"))
    _ordner_ersetzen(neu, target_dir / QUELLE_DIRNAME)
    starter_anlegen(target_dir)
    internet_markierung_entfernen(target_dir)
    info = _marker_schreiben(target_dir, exe_sha256=bau, app_version=app_core.APP_VERSION, art="portable")
    return ("aktualisiert" if before is not None else "eingerichtet"), info


def _zip_sicher_entpacken(zip_pfad: Path, ziel: Path) -> None:
    import zipfile
    ziel = Path(ziel)
    with zipfile.ZipFile(zip_pfad) as z:
        for m in z.infolist():
            name = m.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/") or ":" in name:
                raise app_core.AppError("UPDATE_DATEI", "das Paket vom Server enthält einen unzulässigen Pfad; verworfen")
        if sys.platform == "win32":
            z.extractall(ziel)
            return
        for m in z.infolist():
            name = m.filename.replace("\\", "/")
            if name.endswith("/"):
                (ziel / name).mkdir(parents=True, exist_ok=True)
                continue
            (ziel / name).parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as quelle, open(ziel / name, "wb") as aus:
                shutil.copyfileobj(quelle, aus, 1 << 20)


def _paketname_ok(name: str) -> bool:
    return bool(name) and len(name) <= 120 and "/" not in name and "\\" not in name and ":" not in name and name not in (".", "..") and not name.startswith(".") and name != "__pycache__"


def fehlende_pakete(root: Path) -> list[str]:
    liste = Path(root) / QUELLE_DIRNAME / PAKETE_DATEI
    if not liste.is_file():
        return []
    sp = Path(root) / PYTHON_DIRNAME / "Lib" / "site-packages"
    namen = [z.strip() for z in liste.read_text(encoding="utf-8").splitlines() if z.strip() and not z.lstrip().startswith("#")]
    return [n for n in namen if _paketname_ok(n) and not (sp / n).exists()]


def _projekt(dist_info: str) -> str:
    return dist_info[: -len(".dist-info")].rsplit("-", 1)[0].lower().replace("_", "-")


def veraltete_pakete(root: Path) -> dict[str, str]:
    sp = Path(root) / PYTHON_DIRNAME / "Lib" / "site-packages"
    if not sp.is_dir():
        return {}
    vorhanden = {_projekt(p.name): p.name for p in sp.iterdir() if p.name.endswith(".dist-info") and _paketname_ok(p.name)}
    return {n: vorhanden[_projekt(n)] for n in fehlende_pakete(root) if n.endswith(".dist-info") and _projekt(n) in vorhanden}


def _record_oben(zeilen: list[str]) -> set[str]:
    oben = set()
    for z in zeilen:
        pfad = z.split(",", 1)[0].replace("\\", "/").strip()
        if not pfad or pfad.startswith("/") or pfad.startswith("..") or ":" in pfad:
            continue
        erster = pfad.split("/", 1)[0]
        if _paketname_ok(erster):
            oben.add(erster)
    return oben


def pakete_nachholen(adresse: str, root: Path, *, oeffner=None) -> list[str]:
    import zipfile
    import pakete_tausch
    root = Path(root)
    fehlen = fehlende_pakete(root)
    if not fehlen:
        return []
    veraltet = veraltete_pakete(root)
    if veraltet and (root / pakete_tausch.BUEHNE / pakete_tausch.PLAN).is_file():
        return []
    liste = Path(root) / QUELLE_DIRNAME / PAKETE_DATEI
    im_bau = {z.strip() for z in liste.read_text(encoding="utf-8").splitlines() if z.strip() and not z.lstrip().startswith("#")}
    oeffner = oeffner or __import__("datenfluss").oeffner("Fehlende Programmteile holen")
    zip_neu = root / (PROGRAMM_ZIP + ".neu")
    try:
        _programm_zip_holen(adresse, oeffner=oeffner, zip_neu=zip_neu)
        vorne = PYTHON_DIRNAME + "/Lib/site-packages/"
        buehne = root / "pakete.neu"
        shutil.rmtree(buehne, ignore_errors=True)
        sp = root / PYTHON_DIRNAME / "Lib" / "site-packages"
        with zipfile.ZipFile(zip_neu) as z:
            eintraege = []
            for m in z.infolist():
                name = m.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/") or ":" in name:
                    raise app_core.AppError("PAKETE_DATEI", "das Programmpaket enthält einen unzulässigen Pfad; verworfen")
                if name.startswith(vorne) and not name.endswith("/"):
                    eintraege.append((m, name[len(vorne):]))
            tausch_neu: set[str] = set()
            tausch_alt: set[str] = set()
            tausch_pakete: list[str] = []
            for neu_di, alt_di in sorted(veraltet.items()):
                try:
                    neu_oben = _record_oben(z.read(vorne + neu_di + "/RECORD").decode("utf-8", "replace").splitlines()) | {neu_di}
                    alt_oben = _record_oben((sp / alt_di / "RECORD").read_text(encoding="utf-8", errors="replace").splitlines()) | {alt_di}
                except (KeyError, OSError):
                    continue
                fremd: set[str] = set()
                for di in sp.iterdir():
                    if di.name.endswith(".dist-info") and di.name != alt_di and (di / "RECORD").is_file():
                        fremd |= _record_oben((di / "RECORD").read_text(encoding="utf-8", errors="replace").splitlines()) - {di.name}
                if (neu_oben | alt_oben) & fremd:
                    continue
                if not neu_oben <= im_bau:
                    raise app_core.AppError("PAKETE_DATEI", f"das Programmpaket nennt für {_projekt(neu_di)} Teile, die der Bau nicht aufführt; verworfen")
                tausch_neu |= neu_oben
                tausch_alt |= {n for n in alt_oben if (sp / n).exists()}
                tausch_pakete.append(f"{_projekt(neu_di)} {alt_di[len(_projekt(alt_di)) + 1:-len('.dist-info')]} -> {neu_di[len(_projekt(neu_di)) + 1:-len('.dist-info')]}")
            direkt = [n for n in fehlen if n not in tausch_neu and n not in veraltet]
            gewollt = set(direkt) | tausch_neu
            for m, rest in eintraege:
                if rest.split("/", 1)[0] not in gewollt:
                    continue
                ziel = buehne / rest
                ziel.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as quelle, open(ziel, "wb") as aus:
                    shutil.copyfileobj(quelle, aus)
        geholt = []
        for n in direkt:
            if n in tausch_neu:
                continue
            if (buehne / n).exists() and not (sp / n).exists():
                os.replace(buehne / n, sp / n)
                geholt.append(n)
        if tausch_neu and all((buehne / n).exists() for n in tausch_neu):
            ziel = root / pakete_tausch.BUEHNE
            shutil.rmtree(ziel, ignore_errors=True)
            ziel.mkdir(parents=True)
            for n in sorted(tausch_neu):
                os.replace(buehne / n, ziel / n)
            plan = json.dumps({"pakete": tausch_pakete, "alt": sorted(tausch_alt), "neu": sorted(tausch_neu)}, ensure_ascii=False, indent=1)
            (ziel / (pakete_tausch.PLAN + ".neu")).write_text(plan, encoding="utf-8")
            os.replace(ziel / (pakete_tausch.PLAN + ".neu"), ziel / pakete_tausch.PLAN)
            geholt += [f"tausch:{t}" for t in tausch_pakete]
        shutil.rmtree(buehne, ignore_errors=True)
    except app_core.AppError:
        shutil.rmtree(root / "pakete.neu", ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(root / "pakete.neu", ignore_errors=True)
        raise app_core.AppError("PAKETE_DOWNLOAD", f"das Nachholen ist abgebrochen ({type(exc).__name__})") from None
    finally:
        _still_weg(zip_neu)
    if geholt:
        import importlib
        importlib.invalidate_caches()
    return geholt


def _programm_zip_holen(adresse: str, *, oeffner, zip_neu: Path) -> None:
    import urllib.request
    kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
    basis = adresse.rstrip("/") + "/download/"
    try:
        with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP + ".sha256", headers=kopf), timeout=15) as r:
            erwartet = r.read(200).decode("utf-8", "replace").split()[0].lower()
        with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP + SIGNATUR_ENDUNG, headers=kopf), timeout=15) as r:
            signatur = r.read(400).decode("ascii", "replace").strip()
    except Exception as exc:
        raise app_core.AppError("PAKETE_SERVER", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
    if len(erwartet) != 64 or any(c not in "0123456789abcdef" for c in erwartet):
        raise app_core.AppError("PAKETE_SERVER", "der Server hat keine gültige Prüfsumme geschickt")
    h = hashlib.sha256()
    done = 0
    with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP, headers=kopf), timeout=120) as r, open(zip_neu, "wb") as out:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            done += len(chunk)
            if done > MAX_PROGRAMM_ZIP_BYTES:
                raise app_core.AppError("PAKETE_DATEI", "das Programmpaket vom Server ist unplausibel groß")
            out.write(chunk)
            h.update(chunk)
    if h.hexdigest() != erwartet:
        raise app_core.AppError("PAKETE_PRUEFSUMME", "das Programmpaket stimmt nicht mit der Prüfsumme überein; verworfen")
    if not signatur_gueltig(zip_neu.read_bytes(), signatur):
        raise app_core.AppError("PAKETE_SIGNATUR", "die Unterschrift unter dem Programmpaket stimmt nicht; verworfen")


LAUFZEIT_DATEI = "laufzeit.txt"
LAUFZEIT_NEU = "laufzeit.neu"
TAUSCH_DATEI = "tausch.json"


def _ausgabe(text: str) -> tuple[int, ...]:
    import re
    m = re.match(r"\s*v?(\d+)\.(\d+)\.(\d+)", str(text or ""))
    return tuple(int(x) for x in m.groups()) if m else ()


def laufzeit_im_bau(root: Path) -> tuple[int, ...]:
    try:
        return _ausgabe((Path(root) / QUELLE_DIRNAME / LAUFZEIT_DATEI).read_text(encoding="utf-8"))
    except OSError:
        return ()


def laufzeit_veraltet(root: Path, *, laufend: tuple[int, ...] | None = None, jetzt: float | None = None) -> str:
    root = Path(root)
    bau = laufzeit_im_bau(root)
    laufend = tuple(laufend) if laufend is not None else tuple(sys.version_info[:3])
    if not bau or laufzeit_reihe(bau) != laufzeit_reihe(laufend) or bau <= laufend:
        return ""
    return "" if rueckweg_laufzeit(root, ".".join(map(str, bau)), jetzt) else ".".join(map(str, bau))


def rueckweg_laufzeit(root: Path, ziel: str, jetzt: float | None = None) -> bool:
    r = _json_lesen(Path(root) / RUECKWEG_DATEI)
    jetzt = time.time() if jetzt is None else jetzt
    return r is not None and str(r.get("laufzeit") or "") == ziel and jetzt - float(r.get("zeit_s") or 0) <= RUECKWEG_FRIST_S


def _laufzeit_pruefen(py: Path) -> str:
    import subprocess
    try:
        r = subprocess.run([str(py / "python.exe"), "-I", "-c", "import sys, ssl, sqlite3, json\nimport cryptography.hazmat.primitives.asymmetric.ed25519\nprint('.'.join(map(str, sys.version_info[:3])))"],
                           capture_output=True, text=True, timeout=120, cwd=str(py), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def laufzeit_bereit(root: Path) -> str:
    root = Path(root)
    t = _json_lesen(root / LAUFZEIT_NEU / TAUSCH_DATEI)
    if t is None or not (root / LAUFZEIT_NEU / PYTHON_DIRNAME / "pythonw.exe").is_file():
        return ""
    if t.get("mit_quellen") and not (root / LAUFZEIT_NEU / QUELLE_DIRNAME / "app_web.py").is_file():
        return ""
    return str(t.get("laufzeit") or "")


def grundlage_beim_start_einsetzen(root: Path, args: list[str]) -> bool:
    import subprocess
    root = Path(root)
    if not laufzeit_bereit(root):
        return False
    import sitecustomize
    if sitecustomize._grundlage_einsetzen(str(root)) != "eingesetzt":
        return False
    subprocess.Popen([str(root / PYTHON_DIRNAME / "pythonw.exe"), str(root / QUELLE_DIRNAME / "app_web.py")] + [a for a in args if a], cwd=str(root),
                     close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return True


def laufzeit_nachholen(adresse: str, root: Path, *, oeffner=None, pruefer=None, ziel: str = "", eigener_bau: str = "") -> str:
    import zipfile
    root = Path(root)
    ziel = ziel or laufzeit_veraltet(root)
    if not ziel:
        return ""
    mit_quellen = laufzeit_reihe(_ausgabe(ziel)) != laufzeit_reihe(tuple(sys.version_info[:3]))
    if mit_quellen and rueckweg_laufzeit(root, ziel):
        return ""
    if laufzeit_bereit(root) == ziel:
        return ziel
    oeffner = oeffner or __import__("datenfluss").oeffner("Neue Programm-Grundlage holen")
    zip_neu = root / (PROGRAMM_ZIP + ".neu")
    buehne = root / LAUFZEIT_NEU
    shutil.rmtree(buehne, ignore_errors=True)
    paket_bau = app_core.APP_BUILD
    try:
        _programm_zip_holen(adresse, oeffner=oeffner, zip_neu=zip_neu)
        ordner = (PYTHON_DIRNAME + "/",) + ((QUELLE_DIRNAME + "/",) if mit_quellen else ())
        with zipfile.ZipFile(zip_neu) as z:
            for m in z.infolist():
                name = m.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/") or ":" in name:
                    raise app_core.AppError("PAKETE_DATEI", "das Programmpaket enthält einen unzulässigen Pfad; verworfen")
                if name.startswith(ordner) and not name.endswith("/"):
                    ziel_p = buehne / name
                    ziel_p.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(m) as quelle, open(ziel_p, "wb") as aus:
                        shutil.copyfileobj(quelle, aus)
        neu_py = buehne / PYTHON_DIRNAME
        if not all((neu_py / n).is_file() for n in ("python.exe", "pythonw.exe") + starter_dlls(neu_py)) or not list(neu_py.glob("python3*.zip")):
            raise app_core.AppError("LAUFZEIT_DATEI", "das Programmpaket enthält keine vollständige Programm-Grundlage; verworfen")
        if mit_quellen:
            neu_q = buehne / QUELLE_DIRNAME
            paket_bau = _bau_im_paket(neu_q)
            if not (neu_q / "app_web.py").is_file() or not paket_bau or paket_bau <= eigener_bau:
                raise app_core.AppError("UPDATE_ALT", f"das Programmpaket ist nicht neuer als dieses Programm (Paket: {paket_bau or 'ohne Bau-Nummer'}, hier: {eigener_bau}); verworfen")
            if laufzeit_reihe(_ausgabe((neu_q / LAUFZEIT_DATEI).read_text(encoding="utf-8") if (neu_q / LAUFZEIT_DATEI).is_file() else "")) != laufzeit_reihe(_ausgabe(ziel)):
                raise app_core.AppError("LAUFZEIT_DATEI", "die Quellen im Programmpaket passen nicht zur neuen Programm-Grundlage; verworfen")
        internet_markierung_entfernen(buehne)
        gefunden = (pruefer or _laufzeit_pruefen)(neu_py)
        if _ausgabe(gefunden) != _ausgabe(ziel):
            raise app_core.AppError("LAUFZEIT_PROBE", f"die neue Programm-Grundlage ({ziel}) läuft auf diesem Gerät nicht (Probe: {gefunden or 'kein Start'}); verworfen")
        sicher_schreiben.json_datei(buehne / TAUSCH_DATEI, {"laufzeit": ziel, "bau": paket_bau, "von": eigener_bau or app_core.APP_BUILD, "mit_quellen": mit_quellen,
                                                            "zeit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "zeit_s": time.time(), "versuche": 0}, ascii_=True)
    except app_core.AppError:
        shutil.rmtree(buehne, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(buehne, ignore_errors=True)
        raise app_core.AppError("UPDATE_TAUSCH", f"die neue Programm-Grundlage konnte nicht vorbereitet werden: {exc.strerror or exc}") from None
    finally:
        _still_weg(zip_neu)
    return ziel


def signatur_gueltig(daten: bytes, signatur_b64: str, pubkey_b64: str | None = None) -> bool:
    import base64
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception:
        return False
    schluessel = (pubkey_b64,) if pubkey_b64 else (UPDATE_PUBKEY_B64, UPDATE_PUBKEY_RETTUNG_B64)
    for pk in schluessel:
        try:
            pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pk))
            pub.verify(base64.b64decode(signatur_b64.split()[0]), daten)
            return True
        except (InvalidSignature, ValueError, IndexError, ImportError):
            continue
        except Exception:
            continue
    return False


def signieren(daten: bytes, schluessel_pem: bytes) -> str:
    import base64
    from cryptography.hazmat.primitives import serialization
    k = serialization.load_pem_private_key(schluessel_pem, password=None)
    return base64.b64encode(k.sign(daten)).decode("ascii")


def update_quelle_holen(adresse: str, install_dir: Path | None = None, *, eigener_bau: str, oeffner=None) -> tuple[str, str]:
    import urllib.request
    oeffner = oeffner or __import__("datenfluss").oeffner("Update prüfen oder holen")
    kopf = {"User-Agent": f"{app_core.APP_NAME}/{app_core.APP_VERSION}"}
    basis = adresse.rstrip("/") + "/download/"
    try:
        with oeffner(urllib.request.Request(basis + BAU_DATEI, headers=kopf), timeout=15) as r:
            server_bau = r.read(100).decode("utf-8", "replace").strip()
    except Exception as exc:
        raise app_core.AppError("UPDATE_SERVER", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
    if not server_bau or len(server_bau) > 40 or any(c in server_bau for c in "\r\n\t"):
        raise app_core.AppError("UPDATE_SERVER", "der Server hat keine gültige Bau-Nummer geschickt")
    if server_bau == eigener_bau:
        code, hinweis = neuester_pruefen(adresse, eigener_bau, oeffner)
        text = f"Version {app_core.APP_VERSION} (Bau {eigener_bau}) ist die aktuelle."
        return "aktuell", (text + " " + hinweis) if hinweis else text
    rueckweg = _json_lesen(Path(install_dir or default_install_dir()) / RUECKWEG_DATEI)
    if rueckweg is not None and str(rueckweg.get("bau") or "") == server_bau and time.time() - float(rueckweg.get("zeit_s") or 0) <= RUECKWEG_FRIST_S:
        return "aktuell", rueckweg_hinweis(install_dir)
    try:
        with oeffner(urllib.request.Request(basis + QUELLE_ZIP + ".sha256", headers=kopf), timeout=15) as r:
            erwartet = r.read(200).decode("utf-8", "replace").split()[0].lower()
    except Exception as exc:
        raise app_core.AppError("UPDATE_SERVER", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
    if len(erwartet) != 64 or any(c not in "0123456789abcdef" for c in erwartet):
        raise app_core.AppError("UPDATE_SERVER", "der Server hat keine gültige Prüfsumme geschickt")
    target_dir = app_core.ensure_plain_directory(Path(install_dir or default_install_dir()))
    zip_neu = target_dir / (QUELLE_ZIP + ".neu")
    h = hashlib.sha256()
    done = 0
    try:
        with oeffner(urllib.request.Request(basis + QUELLE_ZIP, headers=kopf), timeout=60) as r, open(zip_neu, "wb") as out:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_QUELLE_ZIP_BYTES:
                    raise app_core.AppError("UPDATE_DATEI", "das Paket vom Server ist unplausibel groß")
                out.write(chunk)
                h.update(chunk)
    except app_core.AppError:
        _still_weg(zip_neu)
        raise
    except Exception as exc:
        _still_weg(zip_neu)
        raise app_core.AppError("UPDATE_DOWNLOAD", f"das Herunterladen ist abgebrochen ({type(exc).__name__})") from None
    if h.hexdigest() != erwartet:
        _still_weg(zip_neu)
        raise app_core.AppError("UPDATE_PRUEFSUMME", "das heruntergeladene Paket stimmt nicht mit der Prüfsumme überein; verworfen")
    try:
        with oeffner(urllib.request.Request(basis + QUELLE_ZIP + SIGNATUR_ENDUNG, headers=kopf), timeout=15) as r:
            signatur = r.read(400).decode("ascii", "replace").strip()
    except Exception as exc:
        _still_weg(zip_neu)
        raise app_core.AppError("UPDATE_SIGNATUR", f"der Server hat keine Unterschrift für das Paket ({type(exc).__name__}); verworfen") from None
    if not signatur_gueltig(zip_neu.read_bytes(), signatur):
        _still_weg(zip_neu)
        raise app_core.AppError("UPDATE_SIGNATUR", "die Unterschrift unter dem Paket stimmt nicht; verworfen")
    neu = target_dir / (QUELLE_DIRNAME + ".neu")
    shutil.rmtree(neu, ignore_errors=True)
    try:
        _zip_sicher_entpacken(zip_neu, neu)
        if not (neu / QUELLE_DIRNAME / "app_web.py").is_file():
            raise app_core.AppError("UPDATE_DATEI", "das Paket vom Server enthält kein Programm; verworfen")
        paket_bau = _bau_im_paket(neu / QUELLE_DIRNAME)
        if not paket_bau or paket_bau <= eigener_bau:
            raise app_core.AppError("UPDATE_ALT", f"das Paket vom Server ist nicht neuer als dieses Programm (Paket: {paket_bau or 'ohne Bau-Nummer'}, hier: {eigener_bau}); verworfen")
        server_bau = paket_bau
        lz = neu / QUELLE_DIRNAME / LAUFZEIT_DATEI
        neue_reihe = _ausgabe(lz.read_text(encoding="utf-8")) if lz.is_file() else ()
        if neue_reihe and laufzeit_reihe(neue_reihe) != laufzeit_reihe(tuple(sys.version_info[:3])):
            shutil.rmtree(neu, ignore_errors=True)
            _still_weg(zip_neu)
            return "grundlage", ".".join(map(str, neue_reihe))
        _ordner_ersetzen(neu / QUELLE_DIRNAME, target_dir / QUELLE_DIRNAME)
    except app_core.AppError:
        shutil.rmtree(neu, ignore_errors=True)
        _still_weg(zip_neu)
        raise
    except OSError as exc:
        shutil.rmtree(neu, ignore_errors=True)
        _still_weg(zip_neu)
        raise app_core.AppError("UPDATE_TAUSCH", f"die neue Version konnte nicht eingesetzt werden: {exc.strerror}") from None
    shutil.rmtree(neu, ignore_errors=True)
    _still_weg(zip_neu)
    sicher_schreiben.json_datei(target_dir / PROBE_DATEI, {"bau": server_bau, "von": eigener_bau, "zeit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "zeit_s": time.time(), "starts": 0}, ascii_=True)
    if sys.platform != "win32":
        _marker_schreiben(target_dir, exe_sha256=server_bau, app_version="?", art="helfer")
        return "aktualisiert", f"Neue Version (Bau {server_bau}) geholt und geprüft. Der Helfer startet gleich neu."
    try:
        starter_anlegen(target_dir)
    except app_core.AppError as exc:
        _still_weg(target_dir / (START_NAME + ".neu"))
        raise app_core.AppError("UPDATE_TAUSCH", f"die neue Version ist da, nur der Starter konnte nicht erneuert werden: {exc.detail}") from None
    _marker_schreiben(target_dir, exe_sha256=server_bau, app_version="?", art="portable")
    return "aktualisiert", f"Neue Version (Bau {server_bau}) geholt und geprüft. Das Programm startet gleich neu."


def _bau_im_paket(ordner: Path) -> str:
    import re
    try:
        m = re.search(r'^APP_BUILD\s*=\s*"([^"\n]{1,40})"', (ordner / "app_core.py").read_text(encoding="utf-8"), re.M)
    except OSError:
        return ""
    return m.group(1) if m else ""


def autostart_command_portable(install_dir: Path) -> str:
    cmd = start_command(install_dir)
    return f'"{cmd[0]}" "{cmd[1]}" --autostart'


def _still_weg(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


def uninstall(install_dir: Path | None = None, *, registry: "RegistryOps | None" = None, desktop_dir: Path | None = None) -> tuple[Path, ...]:
    target_dir = Path(install_dir or default_install_dir())
    autostart_disable(registry=registry)
    removed: list[Path] = []
    lnk = shortcut_path(desktop_dir) if desktop_dir is not None else None
    if lnk is not None and lnk.is_file() and not lnk.is_symlink():
        try:
            lnk.unlink()
            removed.append(lnk)
        except OSError:
            pass
    if desktop_dir is not None:
        for alt in ALTE_SHORTCUTS:
            p = Path(desktop_dir) / alt
            if p.is_file() and not p.is_symlink():
                try:
                    p.unlink()
                    removed.append(p)
                except OSError:
                    pass
    if not target_dir.is_dir():
        return ()
    for name in (EXE_NAME, MARKER_NAME, EXE_NAME + ".neu", MARKER_NAME + ".neu", START_NAME, START_NAME + ".neu", START_PTH, START_PTH + ".neu") + ALTE_STARTER + STARTER_DLLS + tuple(d + ".neu" for d in STARTER_DLLS):
        path = target_dir / name
        if path.is_file() and not path.is_symlink():
            try:
                path.unlink()
                removed.append(path)
            except OSError as exc:
                raise app_core.AppError("DEINSTALL_FEHLER", f"{name} konnte nicht entfernt werden: {exc.strerror} (läuft das Programm noch?)") from None
    for name in (QUELLE_DIRNAME, PYTHON_DIRNAME, QUELLE_DIRNAME + ".alt", QUELLE_DIRNAME + ".neu", PYTHON_DIRNAME + ".neu",
                 QUELLE_DIRNAME + KAPUTT_ENDUNG, PYTHON_DIRNAME + ".alt", PYTHON_DIRNAME + KAPUTT_ENDUNG, LAUFZEIT_NEU):
        path = target_dir / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                removed.append(path)
    try:
        if not any(target_dir.iterdir()):
            target_dir.rmdir()
            removed.append(target_dir)
    except OSError:
        pass
    return tuple(removed)


SHORTCUT_NAME = "KIplatz.lnk"
ALTE_SHORTCUTS = ("Community AI.lnk",)


def _alte_verknuepfungen_weg(ordner: Path) -> None:
    for alt in ALTE_SHORTCUTS:
        p = Path(ordner) / alt
        if p.is_file() and not p.is_symlink():
            _still_weg(p)


def desktop_dir() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except (OSError, AttributeError):
        pass
    p = Path.home() / "Desktop"
    return p if p.is_dir() else None


def shortcut_path(desktop: Path | None = None) -> Path | None:
    d = desktop if desktop is not None else desktop_dir()
    return (d / SHORTCUT_NAME) if d else None


def marken_ico(install_dir: Path) -> Path | None:
    p = Path(install_dir) / QUELLE_DIRNAME / "webapp" / "marke" / "kiplatz.ico"
    return p if p.is_file() else None


def shortcut_command(exe_path: Path, lnk: Path, *, args: str = "", arbeitsordner: Path | None = None, icon: Path | None = None) -> list[str]:
    q = lambda s: str(s).replace("'", "''")
    exe, ziel = q(exe_path), q(lnk)
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{ziel}'); $s.TargetPath = '{exe}'; "
              + (f"$s.Arguments = '{q(args)}'; " if args else "")
              + f"$s.WorkingDirectory = '{q(arbeitsordner or Path(exe_path).parent)}'; $s.Description = 'KIplatz'; $s.IconLocation = '{q(icon) + ",0" if icon else exe + ",0"}'; $s.Save()")
    return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]


def ensure_shortcut(exe_path: Path, desktop: Path | None = None, *, runner: Callable[[list[str]], int] | None = None, args: str = "", arbeitsordner: Path | None = None) -> str:
    lnk = shortcut_path(desktop)
    if lnk is None or not Path(exe_path).is_file():
        return "nicht_moeglich"
    if lnk.exists():
        _alte_verknuepfungen_weg(lnk.parent)
        return "vorhanden"
    if runner is None:
        def runner(cmd: list[str]) -> int:
            import subprocess
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            return subprocess.run(cmd, capture_output=True, timeout=30, creationflags=flags, check=False).returncode
    try:
        ordner = Path(arbeitsordner) if arbeitsordner is not None else Path(exe_path).parent.parent
        rc = runner(shortcut_command(Path(exe_path), lnk, args=args, arbeitsordner=arbeitsordner, icon=marken_ico(ordner)))
    except Exception:
        return "nicht_moeglich"
    if rc == 0 and lnk.exists():
        _alte_verknuepfungen_weg(lnk.parent)
        return "angelegt"
    return "nicht_moeglich"


_LNK_LESEN = ("$s = New-Object -ComObject WScript.Shell; [Console]::OutputEncoding = [Text.Encoding]::UTF8; "
              "foreach ($d in @(ORDNER)) { if (Test-Path -LiteralPath $d) { Get-ChildItem -LiteralPath $d -Filter *.lnk -File | ForEach-Object { "
              "$l = $s.CreateShortcut($_.FullName); [Console]::Out.WriteLine($_.FullName + '|' + $l.TargetPath + '|' + $l.Arguments + '|' + $l.IconLocation) } } }")


def desktop_ordner() -> list[Path]:
    kandidaten = [desktop_dir(), Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"]
    out: list[Path] = []
    for d in kandidaten:
        if d is not None and d.is_dir() and not any(str(d).lower() == str(o).lower() for o in out):
            out.append(d)
    return out


def ist_unsere_verknuepfung(ziel: str, argumente: str, install_dir: Path) -> bool:
    unten = (ziel + " " + argumente).lower().replace("/", "\\")
    ordner = str(Path(install_dir)).lower().replace("/", "\\").rstrip("\\") + "\\"
    return ordner in unten or any(alt in unten for alt in ("\\communityai.exe", "\\community ai.exe", "\\programs\\communityai\\"))


def verknuepfungen_aufraeumen(install_dir: Path, ordner: list[Path] | None = None, *, runner: Callable[[list[str]], tuple[int, str]] | None = None,
                              anlegen: Callable[[Path], str] | None = None) -> str:
    ordner = desktop_ordner() if ordner is None else ordner
    if not ordner:
        return "kein Desktop"
    if runner is None:
        def runner(cmd: list[str]) -> tuple[int, str]:
            import subprocess
            r = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
            return r.returncode, r.stdout.decode("utf-8", "replace")
    try:
        liste = ", ".join("'" + str(o).replace("'", "''") + "'" for o in ordner)
        rc, aus = runner(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _LNK_LESEN.replace("ORDNER", liste)])
    except Exception:
        return "nicht lesbar"
    if rc != 0:
        return "nicht lesbar"
    ico = marken_ico(install_dir)
    weg, neu_icon = 0, 0
    for zeile in aus.splitlines():
        teile = zeile.strip().split("|")
        if len(teile) < 4:
            continue
        lnk, ziel, argumente, icon = Path(teile[0]), teile[1], teile[2], teile[3]
        if not ist_unsere_verknuepfung(ziel, argumente, install_dir) or lnk.is_symlink():
            continue
        if lnk.name.lower() != SHORTCUT_NAME.lower():
            if not (lnk.parent / SHORTCUT_NAME).exists() and anlegen is not None:
                try:
                    anlegen(lnk.parent)
                except Exception:
                    pass
            if (lnk.parent / SHORTCUT_NAME).exists():
                _still_weg(lnk)
                weg += 1
            continue
        if ico is not None and str(ico).lower() not in icon.lower():
            try:
                q = lambda t: str(t).replace("'", "''")
                runner(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                        f"$l = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}'); $l.IconLocation = '{q(ico)},0'; $l.Description = 'KIplatz'; $l.Save()"])
                neu_icon += 1
            except Exception:
                pass
    return f"{weg} alte entfernt, {neu_icon} mit neuem Logo"


class RegistryOps(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class WinRegistryRunKey:

    def get(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
                value, kind = winreg.QueryValueEx(key, name)
                return str(value) if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) else None
        except OSError:
            return None

    def set(self, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


class MemoryRegistry:

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def _registry(registry: RegistryOps | None) -> RegistryOps:
    return registry if registry is not None else WinRegistryRunKey()


def autostart_command(exe_path: Path) -> str:
    return f'"{exe_path}" --autostart'


def autostart_enabled(*, registry: RegistryOps | None = None) -> bool:
    reg = _registry(registry)
    return reg.get(RUN_VALUE_NAME) is not None or any(reg.get(n) is not None for n in ALTE_RUN_VALUE_NAMES)


def autostart_enable(exe_path: Path, *, registry: RegistryOps | None = None) -> str:
    exe = Path(exe_path)
    if not exe.is_file():
        raise app_core.AppError("AUTOSTART_QUELLE", "Autostart geht erst nach der Installation")
    command = autostart_command(exe)
    _registry(registry).set(RUN_VALUE_NAME, command)
    return command


def autostart_disable(*, registry: RegistryOps | None = None) -> None:
    reg = _registry(registry)
    for n in (RUN_VALUE_NAME,) + ALTE_RUN_VALUE_NAMES:
        reg.delete(n)


def autostart_erneuern(install_dir: Path, *, registry: RegistryOps | None = None) -> str | None:
    reg = _registry(registry)
    alt = reg.get(RUN_VALUE_NAME)
    alter_name = next((n for n in ALTE_RUN_VALUE_NAMES if reg.get(n) is not None), None)
    if alt is None and alter_name is None:
        return None
    neu = autostart_command_portable(install_dir)
    if alter_name is not None:
        reg.delete(alter_name)
    if alt == neu and alter_name is None:
        return None
    reg.set(RUN_VALUE_NAME, neu)
    return neu


__all__ = [
    "EXE_NAME", "MARKER_NAME", "RUN_VALUE_NAME", "InstallInfo", "default_install_dir", "running_exe", "installed_info",
    "install", "uninstall", "RegistryOps", "WinRegistryRunKey", "MemoryRegistry", "autostart_command", "autostart_enabled",
    "autostart_enable", "autostart_disable", "autostart_erneuern", "SHORTCUT_NAME", "desktop_dir", "shortcut_path", "shortcut_command", "ensure_shortcut",
]


APPS_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CommunityAI"


def startmenue_dir() -> Path | None:
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" if appdata else None


def apps_eintrag_werte(install_dir: Path, version: str, bau: str) -> dict[str, str]:
    d = Path(install_dir)
    py = d / PYTHON_DIRNAME / "pythonw.exe"
    skript = d / QUELLE_DIRNAME / "app_web.py"
    return {
        "DisplayName": app_core.APP_NAME,
        "DisplayVersion": f"{version} (Bau {bau})",
        "Publisher": "KIplatz",
        "InstallLocation": str(d),
        "DisplayIcon": str(marken_ico(d) or d / START_NAME),
        "UninstallString": f'"{py}" "{skript}" --entfernen',
        "URLInfoAbout": "https://kiplatz.at/",
        "HelpLink": "https://kiplatz.at/kontakt/",
        "NoModify": "1",
        "NoRepair": "1",
    }


def _ordner_kb(d: Path) -> int:
    n = 0
    try:
        for p in Path(d).rglob("*"):
            try:
                if p.is_file() and not p.is_symlink():
                    n += p.stat().st_size
            except OSError:
                continue
    except OSError:
        return 0
    return n // 1024


def apps_eintrag_setzen(install_dir: Path, version: str, bau: str) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APPS_KEY_PATH) as key:
            for name, wert in apps_eintrag_werte(install_dir, version, bau).items():
                if name in ("NoModify", "NoRepair"):
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, wert)
            kb = _ordner_kb(install_dir)
            if kb:
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, min(kb, 0xFFFFFFFF))
        return True
    except OSError:
        return False


def apps_eintrag_entfernen() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, APPS_KEY_PATH)
        return True
    except OSError:
        return False
