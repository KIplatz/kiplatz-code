# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

EINHEIT = "kiplatz-helfer.service"
LAUNCH_NAME = "at.kiplatz.helfer"
STARTER = "kiplatz-helfer"


def system() -> str:
    if sys.platform == "darwin":
        return "macos"
    return "windows" if sys.platform == "win32" else "linux"


def _xdg(name: str, standard: str) -> Path:
    wert = os.environ.get(name, "")
    return Path(wert) if wert and Path(wert).is_absolute() else Path.home() / standard


def daten_ordner() -> Path:
    if system() == "macos":
        return Path.home() / "Library" / "Application Support" / "KIplatz" / "Daten"
    return _xdg("XDG_DATA_HOME", ".local/share") / "kiplatz" / "daten"


def sicherungs_ordner() -> Path:
    if system() == "macos":
        return Path.home() / "Library" / "Application Support" / "KIplatz" / "Sicherung"
    return _xdg("XDG_STATE_HOME", ".local/state") / "kiplatz" / "sicherung"


def programm_ordner() -> Path:
    return Path(__file__).resolve().parent.parent


def systemd_einheit(programm: Path) -> str:
    starter = Path(programm) / STARTER
    return "\n".join((
        "[Unit]",
        "Description=KIplatz-Helfer: dieser PC hilft der Community",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f'ExecStart="{starter}" start',
        "Restart=on-failure",
        "RestartSec=60",
        "Nice=10",
        "KillMode=control-group",
        "TimeoutStopSec=30",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ))


def launchd_plist(programm: Path, protokoll: Path) -> str:
    from xml.sax.saxutils import escape
    starter = escape(str(Path(programm) / STARTER))
    log = escape(str(protokoll))
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
        '<plist version="1.0">',
        "<dict>",
        f"  <key>Label</key><string>{LAUNCH_NAME}</string>",
        f"  <key>ProgramArguments</key><array><string>{starter}</string><string>start</string></array>",
        "  <key>RunAtLoad</key><true/>",
        "  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>",
        "  <key>ProcessType</key><string>Standard</string>",
        "  <key>Nice</key><integer>10</integer>",
        "  <key>ThrottleInterval</key><integer>60</integer>",
        f"  <key>StandardOutPath</key><string>{log}</string>",
        f"  <key>StandardErrorPath</key><string>{log}</string>",
        "</dict>",
        "</plist>",
        "",
    ))


def _einheit_pfad() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "systemd" / "user" / EINHEIT


def _plist_pfad() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_NAME}.plist"


def _ruf(args: list[str], runner=subprocess.run) -> tuple[int, str]:
    if shutil.which(args[0]) is None:
        return 127, f"{args[0]} fehlt"
    try:
        r = runner(args, capture_output=True, text=True, timeout=30, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        return 1, type(exc).__name__
    return r.returncode, (r.stderr or r.stdout or "").strip()[:300]


def _schreiben(p: Path, text: str) -> None:
    import sicher_schreiben
    p.parent.mkdir(parents=True, exist_ok=True)
    sicher_schreiben.text(p, text)


def autostart_an(programm: Path | None = None, *, protokoll: Path | None = None, runner=subprocess.run) -> str:
    programm = Path(programm or programm_ordner())
    if system() == "macos":
        p = _plist_pfad()
        _schreiben(p, launchd_plist(programm, protokoll or (daten_ordner() / "helfer.log")))
        dom = f"gui/{os.getuid()}"
        _ruf(["launchctl", "bootout", dom, str(p)], runner)
        code, text = _ruf(["launchctl", "bootstrap", dom, str(p)], runner)
        return "Der Helfer startet jetzt und nach jeder Anmeldung von selbst." if code == 0 else f"Autostart eingetragen, Start meldet: {text}"
    if system() != "linux":
        return "Autostart gibt es hier nur für Linux und macOS."
    _schreiben(_einheit_pfad(), systemd_einheit(programm))
    _ruf(["systemctl", "--user", "daemon-reload"], runner)
    code, text = _ruf(["systemctl", "--user", "enable", "--now", EINHEIT], runner)
    if code != 0:
        return f"Autostart eingetragen, systemd meldet: {text}. Ohne systemd: „{programm / STARTER} start“ von Hand."
    satz = "Der Helfer startet jetzt und nach jeder Anmeldung von selbst."
    code, linger = _ruf(["loginctl", "show-user", str(os.getuid()), "--property=Linger", "--value"], runner)
    if code == 0 and linger.strip() == "no":
        satz += "\n" + ("Er läuft, solange du angemeldet bist. Soll er auch ohne Anmeldung laufen (Rechner ohne Bildschirm), "
                       "einmal: loginctl enable-linger")
    return satz


def autostart_aus(*, runner=subprocess.run) -> str:
    if system() == "macos":
        p = _plist_pfad()
        _ruf(["launchctl", "bootout", f"gui/{os.getuid()}", str(p)], runner)
        p.unlink(missing_ok=True)
        return "Autostart ist aus, der Helfer ist gestoppt."
    if system() != "linux":
        return "Autostart gibt es hier nur für Linux und macOS."
    _ruf(["systemctl", "--user", "disable", "--now", EINHEIT], runner)
    _einheit_pfad().unlink(missing_ok=True)
    _ruf(["systemctl", "--user", "daemon-reload"], runner)
    return "Autostart ist aus, der Helfer ist gestoppt."


def autostart_an_ist() -> bool:
    return (_plist_pfad() if system() == "macos" else _einheit_pfad()).is_file()


class Sperre:

    def __init__(self, ordner: Path) -> None:
        self.pfad = Path(ordner) / "helfer.sperre"
        self._fd: int | None = None

    def holen(self) -> bool:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.pfad, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
        self._fd = fd
        return True

    def freigeben(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def zertifikate_des_systems() -> bool:
    try:
        import ssl
        import urllib.request

        import truststore
    except ImportError:
        return False
    import community

    def kontext():
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=kontext())))
    community.TLS_KONTEXT = kontext
    return True
