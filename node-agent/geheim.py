# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import os
import platform
import secrets
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path

try:
    import win32crypt
except ImportError:
    win32crypt = None

ZWECK = "KIplatz"

BUND_DIENST = "KIplatz"
BUND_KONTO = "geheim-schluessel"
SCHLUESSEL_DATEI = "schluessel"
ART_DATEI = "art"
ORDNER: Path | None = None
BUND_AN = True
_AAD = b"KIplatz geheim v1"
_SPERRE = threading.Lock()
_GEMERKT: dict = {}


class GeheimError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code, self.detail = code, detail


def _windows() -> bool:
    return win32crypt is not None and platform.system() == "Windows"


def _posix() -> bool:
    return os.name == "posix"


def moeglich() -> bool:
    return _windows() or _posix()


def ordner() -> Path:
    if ORDNER is not None:
        return Path(ORDNER)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "KIplatz" / "geheim"
    basis = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(basis) / "kiplatz" / "geheim"


def _ordner_sicher(anlegen: bool) -> Path:
    o = ordner()
    if anlegen:
        o.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(o, 0o700)
    try:
        st = os.lstat(o)
    except FileNotFoundError:
        raise GeheimError("GEHEIM_SCHLUESSEL", "der Schlüssel zu diesem Geheimnis fehlt auf diesem Gerät") from None
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise GeheimError("GEHEIM_RECHTE", f"der Ordner für Schlüssel ({o}) darf nur dir gehören und nur von dir lesbar sein (Rechte 700)")
    return o


def _datei_lesen(p: Path) -> bytes | None:
    try:
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise GeheimError("GEHEIM_RECHTE", f"die Schlüsseldatei lässt sich nicht lesen ({exc.strerror})") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise GeheimError("GEHEIM_RECHTE", f"die Schlüsseldatei ({p}) darf nur dir gehören und nur von dir lesbar sein (Rechte 600)")
        return os.read(fd, 200)
    finally:
        os.close(fd)


def _datei_schreiben(p: Path, inhalt: bytes) -> None:
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, inhalt)
        os.fsync(fd)
    finally:
        os.close(fd)


def _secret_tool() -> str | None:
    if not (sys.platform.startswith("linux") and BUND_AN):
        return None
    if not (os.environ.get("DBUS_SESSION_BUS_ADDRESS") or (os.environ.get("XDG_RUNTIME_DIR") and Path(os.environ["XDG_RUNTIME_DIR"], "bus").exists())):
        return None
    return shutil.which("secret-tool")


def _hex_schluessel(roh: bytes) -> bytes | None:
    try:
        k = bytes.fromhex(roh.decode("ascii", "replace").strip())
    except ValueError:
        return None
    return k if len(k) == 32 else None


def _bund_konto(kennung: str) -> str:
    return f"{BUND_KONTO}-{kennung}"


def _bund_lesen(kennung: str) -> bytes | None:
    if sys.platform == "darwin" and BUND_AN:
        return _mac_lesen(_bund_konto(kennung))
    st = _secret_tool()
    if st is None:
        return None
    try:
        r = subprocess.run([st, "lookup", "dienst", BUND_DIENST, "konto", _bund_konto(kennung)], capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        raise GeheimError("GEHEIM_GESPERRT", "der Schlüsselbund antwortet gerade nicht") from None
    return _hex_schluessel(r.stdout) if r.returncode == 0 else None


def _bund_schreiben(kennung: str, schluessel: bytes) -> bool:
    if sys.platform == "darwin" and BUND_AN:
        return _mac_schreiben(_bund_konto(kennung), schluessel)
    st = _secret_tool()
    if st is None:
        return False
    try:
        r = subprocess.run([st, "store", "--label", "KIplatz", "dienst", BUND_DIENST, "konto", _bund_konto(kennung)],
                           input=schluessel.hex().encode("ascii"), capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _mac_security():
    import ctypes
    try:
        sec = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Security.framework/Security")
    except OSError:
        raise GeheimError("GEHEIM_GESPERRT", "der Schlüsselbund des Systems ist nicht erreichbar") from None
    sec.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    sec.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p,
                                                   ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    sec.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    sec.SecKeychainAddGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p,
                                                  ctypes.c_uint32, ctypes.c_char_p, ctypes.c_void_p]
    sec.SecKeychainItemFreeContent.restype = ctypes.c_int32
    sec.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    return ctypes, sec


_MAC_NICHT_DA = -25300


def _mac_lesen(konto: str) -> bytes | None:
    ctypes, sec = _mac_security()
    d, k = BUND_DIENST.encode(), konto.encode()
    laenge, daten = ctypes.c_uint32(0), ctypes.c_void_p()
    rc = sec.SecKeychainFindGenericPassword(None, len(d), d, len(k), k, ctypes.byref(laenge), ctypes.byref(daten), None)
    if rc == _MAC_NICHT_DA:
        return None
    if rc != 0:
        raise GeheimError("GEHEIM_GESPERRT", f"der Schlüsselbund ist gerade gesperrt oder antwortet nicht (Code {rc})")
    try:
        roh = ctypes.string_at(daten, laenge.value)
    finally:
        sec.SecKeychainItemFreeContent(None, daten)
    return _hex_schluessel(roh)


def _mac_schreiben(konto: str, schluessel: bytes) -> bool:
    try:
        _ctypes, sec = _mac_security()
    except GeheimError:
        return False
    d, k, w = BUND_DIENST.encode(), konto.encode(), schluessel.hex().encode("ascii")
    return sec.SecKeychainAddGenericPassword(None, len(d), d, len(k), k, len(w), w, None) == 0


def _bund_schluessel(kennung: str) -> bytes:
    with _SPERRE:
        if ("bund", kennung) in _GEMERKT:
            return _GEMERKT[("bund", kennung)]
        k = _bund_lesen(kennung)
        if k is None:
            raise GeheimError("GEHEIM_GESPERRT", "der Schlüssel liegt im Schlüsselbund, der ist gerade nicht lesbar; nach dem Anmelden noch einmal")
        _GEMERKT[("bund", kennung)] = k
        return k


def _datei_schluessel(anlegen: bool) -> bytes | None:
    o = _ordner_sicher(anlegen=anlegen)
    roh = _datei_lesen(o / SCHLUESSEL_DATEI)
    if roh is None:
        return None
    k = _hex_schluessel(roh)
    if k is None:
        raise GeheimError("GEHEIM_SCHLUESSEL", "die Schlüsseldatei ist beschädigt")
    return k


def _schluessel_fuer_neue() -> tuple[str, bytes]:
    with _SPERRE:
        if "neu" in _GEMERKT:
            return _GEMERKT["neu"]
        o = _ordner_sicher(anlegen=True)
        marke = (_datei_lesen(o / ART_DATEI) or b"").decode("ascii", "replace").strip()
    if marke.startswith("bund:") and len(marke) > 5:
        kennung = marke[5:]
        ergebnis = (f"bund:{kennung}.", _bund_schluessel(kennung))
    else:
        with _SPERRE:
            k = _datei_schluessel(anlegen=True)
            if k is not None:
                ergebnis = ("datei:", k)
            else:
                k, kennung = secrets.token_bytes(32), secrets.token_hex(8)
                try:
                    in_den_bund = _bund_schreiben(kennung, k) and _bund_lesen(kennung) == k
                except GeheimError:
                    in_den_bund = False
                if in_den_bund:
                    _datei_neu(o / ART_DATEI, f"bund:{kennung}".encode("ascii"))
                    _GEMERKT[("bund", kennung)] = k
                    ergebnis = (f"bund:{kennung}.", k)
                else:
                    _datei_neu(o / SCHLUESSEL_DATEI, k.hex().encode("ascii"))
                    k = _datei_schluessel(anlegen=False) or k
                    ergebnis = ("datei:", k)
    with _SPERRE:
        _GEMERKT["neu"] = ergebnis
    return ergebnis


def _datei_neu(p: Path, inhalt: bytes) -> None:
    try:
        _datei_schreiben(p, inhalt)
    except FileExistsError:
        pass


def vergessen() -> None:
    with _SPERRE:
        _GEMERKT.clear()


def schuetzen(klar: str, zweck: str = ZWECK) -> str:
    if _windows():
        blob = win32crypt.CryptProtectData(str(klar).encode("utf-8"), zweck, None, None, None, 0)
        return "dpapi:" + base64.b64encode(blob).decode("ascii")
    if _posix():
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        praefix, k = _schluessel_fuer_neue()
        nonce = secrets.token_bytes(12)
        return praefix + base64.b64encode(nonce + AESGCM(k).encrypt(nonce, str(klar).encode("utf-8"), _AAD)).decode("ascii")
    return "klar:" + str(klar)


def lesen(wert: str) -> str:
    w = str(wert or "")
    if w.startswith("dpapi:"):
        if not _windows():
            raise GeheimError("GEHEIM_SYSTEM", "dieser Schlüssel lässt sich nur auf dem Windows-Gerät lesen, auf dem er gespeichert wurde")
        try:
            _d, klar = win32crypt.CryptUnprotectData(base64.b64decode(w[6:]), None, None, None, 0)
        except Exception:
            raise GeheimError("GEHEIM_BENUTZER", "dieser Schlüssel gehört zu einem anderen Windows-Benutzer oder Gerät") from None
        return klar.decode("utf-8")
    art, _, rest = w.partition(":")
    if art in ("bund", "datei") and rest:
        if not _posix():
            raise GeheimError("GEHEIM_SYSTEM", "dieser Schlüssel lässt sich nur auf dem Gerät lesen, auf dem er gespeichert wurde")
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if art == "bund":
            kennung, _, rest = rest.partition(".")
            if not kennung or not rest:
                raise GeheimError("GEHEIM_BENUTZER", "dieser Schlüssel ist beschädigt")
            k = _bund_schluessel(kennung)
        else:
            with _SPERRE:
                k = _datei_schluessel(anlegen=False)
            if k is None:
                raise GeheimError("GEHEIM_SCHLUESSEL", "der Schlüssel zu diesem Geheimnis fehlt auf diesem Gerät")
        try:
            roh = base64.b64decode(rest, validate=True)
            return AESGCM(k).decrypt(roh[:12], roh[12:], _AAD).decode("utf-8")
        except (ValueError, InvalidTag, UnicodeDecodeError):
            raise GeheimError("GEHEIM_BENUTZER", "dieser Schlüssel gehört zu einem anderen Benutzer oder Gerät, oder er ist beschädigt") from None
    if w.startswith("klar:"):
        return w[5:]
    return w


def geschuetzt(wert: str) -> bool:
    w = str(wert or "")
    return w.startswith(("dpapi:", "bund:", "datei:")) or (w.startswith("klar:") and not moeglich())


__all__ = ["schuetzen", "lesen", "geschuetzt", "moeglich", "GeheimError"]
