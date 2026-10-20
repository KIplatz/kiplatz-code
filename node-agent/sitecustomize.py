# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import sys

LAUNCHER_NAMES = ("kiplatz.exe", "community ai.exe")


def _launcher_root():
    try:
        exe = os.path.abspath(sys.executable)
    except (TypeError, OSError):
        return None
    if os.path.basename(exe).lower() not in LAUNCHER_NAMES:
        return None
    return os.path.dirname(exe)


def _internet_markierung_entfernen(root):
    for ordner, _, dateien in os.walk(root):
        for name in dateien:
            try:
                os.remove(os.path.join(ordner, name) + ":Zone.Identifier")
            except OSError:
                pass


PROBE_DATEI = "update-probe.json"
RUECKWEG_DATEI = "update-rueckweg.json"
RUECKWEG_FRIST_S = 24 * 3600
FEHLSTARTS = 2


def _rueckweg_pruefen(root, jetzt=None):
    import json
    import shutil
    import time
    probe = os.path.join(root, PROBE_DATEI)
    if not os.path.isfile(probe):
        return "keine"
    try:
        with open(probe, encoding="utf-8") as f:
            p = json.load(f)
        if not isinstance(p, dict):
            return "unlesbar"
    except (OSError, ValueError):
        return "unlesbar"
    jetzt = time.time() if jetzt is None else jetzt
    paare = [(os.path.join(root, n), os.path.join(root, n + ".alt"), os.path.join(root, n + ".kaputt")) for n in ("node-agent", "python")
             if os.path.isdir(os.path.join(root, n + ".alt"))]
    try:
        zu_alt = jetzt - float(p.get("zeit_s") or 0) > RUECKWEG_FRIST_S
    except (TypeError, ValueError):
        zu_alt = True
    if zu_alt or not paare:
        return "abgelaufen"
    try:
        starts = int(p.get("starts") or 0)
    except (TypeError, ValueError):
        starts = 0
    if starts < FEHLSTARTS:
        p["starts"] = starts + 1
        try:
            with open(probe, "w", encoding="utf-8") as f:
                json.dump(p, f)
        except OSError:
            pass
        return "gezaehlt"
    try:
        for neu, alt, kaputt in paare:
            shutil.rmtree(kaputt, ignore_errors=True)
            os.replace(neu, kaputt)
            os.replace(alt, neu)
    except OSError:
        return "fehler"
    starter = _starter_erneuern(root) if any(os.path.basename(neu) == "python" for neu, _, _ in paare) else ""
    try:
        with open(os.path.join(root, RUECKWEG_DATEI), "w", encoding="utf-8") as f:
            json.dump({"bau": p.get("bau"), "von": p.get("von"), "laufzeit": p.get("laufzeit"), "starts": starts, "zeit_s": jetzt,
                       "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(jetzt)), "starter": starter or "ok"}, f)
        os.remove(probe)
    except OSError:
        pass
    return "zurueck"


WEG_ENDUNG = ".weg"


def _starter_erneuern(root):
    py = os.path.join(root, "python")
    grund = ""
    for _ in range(5):
        grund = _starter_einmal(root, py)
        if not grund:
            return ""
        _warten(1.0)
    return grund


def _warten(s):
    import time
    time.sleep(s)


def _starter_einmal(root, py):
    try:
        namen = os.listdir(py)
        reihe = sorted(n for n in namen if n.lower().startswith("python3") and n.lower().endswith(".dll") and n.lower() != "python3.dll")
        zips = sorted(n for n in namen if n.lower().startswith("python3") and n.lower().endswith(".zip"))
        if not reihe or not zips:
            return "keine Python-DLL oder Bibliothek im Ordner python"
        teile = [("pythonw.exe", "KIplatz.exe"), (reihe[-1], reihe[-1]), ("python3.dll", "python3.dll"),
                 ("vcruntime140.dll", "vcruntime140.dll"), ("vcruntime140_1.dll", "vcruntime140_1.dll")]
        for quelle, ziel in teile:
            quelle, ziel = os.path.join(py, quelle), os.path.join(root, ziel)
            with open(quelle, "rb") as f:
                daten = f.read()
            if os.path.isfile(ziel):
                with open(ziel, "rb") as f:
                    if f.read() == daten:
                        continue
            with open(ziel + ".neu", "wb") as f:
                f.write(daten)
            try:
                os.replace(ziel + ".neu", ziel)
            except OSError:
                try:
                    os.remove(ziel + WEG_ENDUNG)
                except OSError:
                    pass
                os.replace(ziel, ziel + WEG_ENDUNG)
                os.replace(ziel + ".neu", ziel)
        with open(os.path.join(root, "KIplatz._pth"), "wb") as f:
            f.write(b"python\\" + zips[-1].encode() + b"\npython\npython\\Lib\\site-packages\nnode-agent\nimport site\n")
        for n in os.listdir(root):
            if n.lower().startswith("python3") and n.lower().endswith(".dll") and n.lower() not in (reihe[-1].lower(), "python3.dll"):
                try:
                    os.remove(os.path.join(root, n))
                except OSError:
                    os.replace(os.path.join(root, n), os.path.join(root, n + WEG_ENDUNG))
    except Exception as exc:
        return type(exc).__name__ + ": " + str(exc)[:160]
    return ""


def _weg_aufraeumen(root):
    try:
        for n in os.listdir(root):
            if n.endswith(WEG_ENDUNG):
                try:
                    os.remove(os.path.join(root, n))
                except OSError:
                    pass
    except OSError:
        pass


LAUFZEIT_NEU = "laufzeit.neu"
TAUSCH_DATEI = "tausch.json"
EINSETZ_VERSUCHE = 2
EINSETZ_WARTE_S = 20.0


def _ordner_zurueck(ziel, alt):
    import shutil
    try:
        if os.path.isdir(ziel) and os.path.isdir(alt):
            shutil.rmtree(ziel, ignore_errors=True)
        if not os.path.isdir(ziel) and os.path.isdir(alt):
            os.replace(alt, ziel)
    except OSError:
        pass


def _grundlage_einsetzen(root, jetzt=None, warte_s=None):
    import json
    import shutil
    import time
    buehne = os.path.join(root, LAUFZEIT_NEU)
    tausch = os.path.join(buehne, TAUSCH_DATEI)
    if not os.path.isfile(tausch):
        return "keine"
    try:
        with open(tausch, encoding="utf-8") as f:
            t = json.load(f)
        ziel = str(t.get("laufzeit") or "")
        mit_quellen = bool(t.get("mit_quellen"))
        versuche = int(t.get("versuche") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        shutil.rmtree(buehne, ignore_errors=True)
        return "unlesbar"
    neu_py, neu_q = os.path.join(buehne, "python"), os.path.join(buehne, "node-agent")
    if not ziel or not all(os.path.isfile(os.path.join(neu_py, n)) for n in ("python.exe", "pythonw.exe")) \
            or (mit_quellen and not os.path.isfile(os.path.join(neu_q, "app_web.py"))):
        shutil.rmtree(buehne, ignore_errors=True)
        return "unlesbar"
    jetzt = time.time() if jetzt is None else jetzt

    def aufgeben(grund):
        shutil.rmtree(buehne, ignore_errors=True)
        try:
            with open(os.path.join(root, RUECKWEG_DATEI), "w", encoding="utf-8") as f:
                json.dump({"bau": t.get("bau"), "von": t.get("von"), "laufzeit": ziel, "grund": grund, "starts": 0, "zeit_s": jetzt,
                           "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(jetzt)), "starter": "ok"}, f)
        except OSError:
            pass
        return "aufgegeben"

    if versuche >= EINSETZ_VERSUCHE:
        return aufgeben("einsetzen")
    t["versuche"] = versuche + 1
    try:
        with open(tausch, "w", encoding="utf-8") as f:
            json.dump(t, f)
    except OSError:
        return aufgeben("einsetzen")
    py, py_alt = os.path.join(root, "python"), os.path.join(root, "python.alt")
    q, q_alt = os.path.join(root, "node-agent"), os.path.join(root, "node-agent.alt")
    ende = time.time() + (EINSETZ_WARTE_S if warte_s is None else warte_s)
    while True:
        shutil.rmtree(py_alt, ignore_errors=True)
        if not os.path.isdir(py_alt):
            try:
                os.replace(py, py_alt)
                break
            except OSError:
                pass
        if time.time() >= ende:
            return "belegt"
        time.sleep(0.5)
    try:
        os.replace(neu_py, py)
    except OSError:
        _ordner_zurueck(py, py_alt)
        return aufgeben("tausch")
    if mit_quellen:
        shutil.rmtree(q_alt, ignore_errors=True)
        try:
            os.replace(q, q_alt)
        except OSError:
            _ordner_zurueck(py, py_alt)
            return aufgeben("tausch")
        try:
            os.replace(neu_q, q)
        except OSError:
            _ordner_zurueck(q, q_alt)
            _ordner_zurueck(py, py_alt)
            return aufgeben("tausch")
    try:
        with open(os.path.join(root, PROBE_DATEI), "w", encoding="utf-8") as f:
            json.dump({"bau": t.get("bau"), "von": t.get("von"), "laufzeit": ziel, "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(jetzt)),
                       "zeit_s": jetzt, "starts": 0}, f)
    except OSError:
        pass
    if mit_quellen:
        try:
            with open(os.path.join(root, "installiert.json"), encoding="utf-8") as f:
                marker = json.load(f)
            if not isinstance(marker, dict):
                marker = {}
        except (OSError, ValueError):
            marker = {}
        marker.setdefault("installed_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(jetzt)))
        marker.update({"exe_sha256": t.get("bau") or "?", "app_version": "?", "art": "portable"})
        try:
            with open(os.path.join(root, "installiert.json"), "w", encoding="utf-8") as f:
                json.dump(marker, f)
        except OSError:
            pass
    grund = _starter_erneuern(root)
    try:
        with open(os.path.join(root, "pakete-tausch.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S") + " OK laufzeit: Programm-Grundlage " + ziel + " eingesetzt (Bau " + str(t.get("bau") or "?")
                    + ", vorher " + str(t.get("von") or "?") + (", samt Quellen" if mit_quellen else "") + ")" + (", Starter: " + grund if grund else "") + "\n")
    except OSError:
        pass
    shutil.rmtree(buehne, ignore_errors=True)
    return "eingesetzt"


STANDARD_ADRESSE = "https://kiplatz.at:8444"
PROGRAMM_ZIP = "CommunityAI.zip"
MAX_PROGRAMM_ZIP_BYTES = 200 * 1024 * 1024
UPDATE_PUBKEYS_B64 = ("Mq0a5sAEHp9ba/kUL/F69I67SooKawCBS7p1mtmKWNw=", "OF758lOi5oKh6rttdYLB5Vb5oIU1KYES9pz+06YKXIw=")


def _gespeicherte_adresse():
    import json
    lokal = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    for basis in (os.path.join(lokal, "KIplatz", "daten"), os.path.join(os.path.expanduser("~"), "CommunityAI-Test")):
        try:
            with open(os.path.join(basis, "community", "einstellung.json"), encoding="utf-8") as f:
                a = json.load(f).get("adresse")
        except (OSError, ValueError, AttributeError):
            continue
        a = str(a).rstrip("/") if a else ""
        return a if a.lower().startswith("https://") else STANDARD_ADRESSE
    return STANDARD_ADRESSE


def _signatur_gueltig(daten, signatur_b64):
    import base64
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception:
        return False
    for pk in UPDATE_PUBKEYS_B64:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(pk)).verify(base64.b64decode(signatur_b64.split()[0]), daten)
            return True
        except Exception:
            continue
    return False


def _laufzeit_probe(py):
    import subprocess
    try:
        r = subprocess.run([os.path.join(py, "python.exe"), "-I", "-c", "import sys, ssl, sqlite3, json\nimport cryptography.hazmat.primitives.asymmetric.ed25519\nprint('.'.join(map(str, sys.version_info[:3])))"],
                           capture_output=True, text=True, timeout=120, cwd=py, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _grundlage_bruecke(root, oeffner=None, pruefer=None, adresse=None):
    import hashlib
    import json
    import re
    import shutil
    import time
    import urllib.request
    import zipfile
    py_alt, py, buehne = os.path.join(root, "python.alt"), os.path.join(root, "python"), os.path.join(root, "laufzeit.neu")
    zip_neu = os.path.join(root, PROGRAMM_ZIP + ".neu")
    getauscht = False
    try:
        with open(os.path.join(root, "node-agent", "laufzeit.txt"), encoding="utf-8") as f:
            ziel = f.read().strip()
        m = re.search(r'^APP_BUILD\s*=\s*"([^"\n]{1,40})"', open(os.path.join(root, "node-agent", "app_core.py"), encoding="utf-8").read(), re.M)
        bau_neu = m.group(1) if m else ""
        if not re.fullmatch(r"\d+\.\d+\.\d+", ziel) or not bau_neu:
            return False
        try:
            with open(os.path.join(root, "installiert.json"), encoding="utf-8") as f:
                bau_alt = str(json.load(f).get("exe_sha256") or "")
        except (OSError, ValueError, AttributeError):
            bau_alt = ""
        oeffner = oeffner or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))
        basis = (adresse or _gespeicherte_adresse()).rstrip("/") + "/download/"
        kopf = {"User-Agent": "KIplatz-Bruecke/" + (bau_alt or "?")}
        with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP + ".sha256", headers=kopf), timeout=15) as r:
            erwartet = r.read(200).decode("utf-8", "replace").split()[0].lower()
        with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP + ".sig", headers=kopf), timeout=15) as r:
            signatur = r.read(400).decode("ascii", "replace").strip()
        if len(erwartet) != 64:
            return False
        h = hashlib.sha256()
        done = 0
        with oeffner(urllib.request.Request(basis + PROGRAMM_ZIP, headers=kopf), timeout=120) as r, open(zip_neu, "wb") as out:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_PROGRAMM_ZIP_BYTES:
                    return False
                out.write(chunk)
                h.update(chunk)
        if h.hexdigest() != erwartet:
            return False
        with open(zip_neu, "rb") as f:
            if not _signatur_gueltig(f.read(), signatur):
                return False
        shutil.rmtree(buehne, ignore_errors=True)
        with zipfile.ZipFile(zip_neu) as z:
            for m in z.infolist():
                name = m.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/") or ":" in name:
                    return False
                if name.startswith("python/") and not name.endswith("/"):
                    ziel_p = os.path.join(buehne, *name.split("/"))
                    os.makedirs(os.path.dirname(ziel_p), exist_ok=True)
                    with z.open(m) as quelle, open(ziel_p, "wb") as aus:
                        shutil.copyfileobj(quelle, aus)
        neu_py = os.path.join(buehne, "python")
        namen = os.listdir(neu_py) if os.path.isdir(neu_py) else []
        if not all(n in namen for n in ("python.exe", "pythonw.exe", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll")) \
                or not any(n.lower().startswith("python3") and n.lower().endswith(".zip") for n in namen):
            return False
        _internet_markierung_entfernen(buehne)
        gefunden = (pruefer or _laufzeit_probe)(neu_py)
        if gefunden != ziel:
            return False
        shutil.rmtree(py_alt, ignore_errors=True)
        if os.path.isdir(py_alt):
            return False
        os.replace(py, py_alt)
        getauscht = True
        os.replace(neu_py, py)
        with open(os.path.join(root, PROBE_DATEI), "w", encoding="utf-8") as f:
            json.dump({"bau": bau_neu, "von": bau_alt, "laufzeit": ziel, "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "zeit_s": time.time(), "starts": 0}, f)
        grund = _starter_erneuern(root)
        try:
            with open(os.path.join(root, "installiert.json"), encoding="utf-8") as f:
                marker = json.load(f)
            marker.update({"exe_sha256": bau_neu, "app_version": "?", "art": "portable"})
            with open(os.path.join(root, "installiert.json"), "w", encoding="utf-8") as f:
                json.dump(marker, f)
        except (OSError, ValueError, AttributeError):
            pass
        with open(os.path.join(root, "pakete-tausch.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S") + " OK bruecke: Programm-Grundlage " + ziel + " geholt und eingesetzt (Bau " + bau_neu + ", vorher " + (bau_alt or "?") + ")" + (", Starter: " + grund if grund else "") + "\n")
        return True
    except Exception:
        if getauscht:
            try:
                if os.path.isdir(py) and not os.path.isfile(os.path.join(py, "pythonw.exe")):
                    shutil.rmtree(py, ignore_errors=True)
                if not os.path.isdir(py):
                    os.replace(py_alt, py)
            except OSError:
                pass
        return False
    finally:
        shutil.rmtree(buehne, ignore_errors=True)
        try:
            os.remove(zip_neu)
        except OSError:
            pass


def _falsche_reihe(app_web_py):
    import json
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(app_web_py)))
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if _grundlage_bruecke(root):
        try:
            subprocess.Popen([os.path.join(root, "python", "pythonw.exe"), os.path.join(root, "node-agent", "app_web.py")] + [a for a in sys.argv[1:] if a], cwd=root, close_fds=True, creationflags=flags)
        except OSError:
            pass
        os._exit(0)
    probe = os.path.join(root, PROBE_DATEI)
    try:
        with open(probe, encoding="utf-8") as f:
            p = json.load(f)
        p["starts"] = FEHLSTARTS
        with open(probe, "w", encoding="utf-8") as f:
            json.dump(p, f)
    except (OSError, ValueError, TypeError):
        pass
    if _rueckweg_pruefen(root) == "zurueck":
        pythonw = os.path.join(root, "python", "pythonw.exe")
        try:
            subprocess.Popen([pythonw, os.path.join(root, "node-agent", "app_web.py")] + [a for a in sys.argv[1:] if a], cwd=root, close_fds=True, creationflags=flags)
        except OSError:
            pass
    os._exit(0)


def _start(root):
    import subprocess
    _weg_aufraeumen(root)
    _grundlage_einsetzen(root)
    _rueckweg_pruefen(root)
    pythonw = os.path.join(root, "python", "pythonw.exe")
    script = os.path.join(root, "node-agent", "app_web.py")
    if not (os.path.isfile(pythonw) and os.path.isfile(script)):
        return
    _internet_markierung_entfernen(root)
    argv = getattr(sys, "argv", None) or getattr(sys, "orig_argv", None) or []
    args = [a for a in argv[1:] if a]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([pythonw, script] + args, cwd=root, close_fds=True, creationflags=flags)


_root = _launcher_root()
if _root is not None:
    try:
        _start(_root)
    finally:
        os._exit(0)
