# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import math
import os
import platform
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import hardware_detect
import node_local_state
import sicher_schreiben

APP_NAME = "KIplatz"
APP_VERSION = "0.4.0-community"
APP_BUILD = "2026-10-18m"

FIRST_START_FILENAME = "erststart.json"
FREIGABE_FILENAME = "freigabe.json"
CPU_CHOICES = (25, 50, 75, 100)
RAM_CHOICES_GIB = (1, 2, 4, 8, 16)
SPEICHER_CHOICES_MB = (0, 100, 500, 2000, 10000)
DEFAULT_SPEICHER_MB = 500
CPU_MIN, CPU_MAX = 1, 100
RAM_SCHRITT_GIB = 0.5
RAM_REST_GIB = 2.0
SPEICHER_MIN_MB = 50
SPEICHER_MAX_MB = 4 * 1000 * 1000
SPEICHER_EMPF_ANTEIL = 0.05
SPEICHER_EMPF_MAX_MB = 20000
SPEICHER_ORDNER = "KIplatz-Speicher"
DIAGNOSIS_DIRNAME = "diagnose"
NODE_AGENT_DIRNAME = "node-agent"
MAX_FIRST_START_SIZE_BYTES = 64 * 1024


class Profile(str, Enum):
    TEST = "test"
    PRODUKTIV = "produktiv"


PROFILE_LABELS_DE = {Profile.TEST: "", Profile.PRODUKTIV: "Produktivbetrieb"}


def default_base_dir(profile: Profile) -> Path:
    home = Path.home()
    if profile is Profile.TEST:
        return home / "CommunityAI-Test"
    return home / "AppData" / "Local" / "CommunityAINetwork"


class AppError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class Role(str, Enum):
    COMPUTE_STRONG = "rechenstark"
    COMPUTE_NORMAL = "normal"
    CLIENT_ONLY = "nur_client"


ROLE_LABELS_DE = {
    Role.COMPUTE_STRONG: "Rechenstarker Node (viel Arbeitsspeicher und Grafikkarte erkannt)",
    Role.COMPUTE_NORMAL: "Normaler Node",
    Role.CLIENT_ONLY: "Nur Mitmachen ohne Rechenarbeit (wenig Arbeitsspeicher)",
}


@dataclass(frozen=True)
class FirstStartResult:
    checked_at: str
    os_name: str
    cpu_cores: int | None
    memory_gib: float
    gpu_names: tuple[str, ...]
    role: Role

    def to_json_dict(self) -> dict:
        return {
            "checked_at": self.checked_at,
            "os": self.os_name,
            "cpu_cores": self.cpu_cores,
            "memory_gib": self.memory_gib,
            "gpus": list(self.gpu_names),
            "role": self.role.value,
            "app_version": APP_VERSION,
        }


def suggest_role(*, memory_gib: float, gpu_names: tuple[str, ...]) -> Role:
    if memory_gib < 8.0:
        return Role.CLIENT_ONLY
    real_gpu = any(not any(word in name.lower() for word in ("basic", "virtual", "remote", "vmware", "hyper-v")) for name in gpu_names)
    if memory_gib >= 15.5 and real_gpu:
        return Role.COMPUTE_STRONG
    return Role.COMPUTE_NORMAL


def _is_reparse(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)) or stat.S_ISLNK(st.st_mode)


def ensure_plain_directory(path: Path) -> Path:
    if _is_reparse(path):
        raise AppError("ORDNER_UNSICHER", f"{path.name} ist eine Verknüpfung und wird nicht benutzt")
    if path.exists():
        if not path.is_dir():
            raise AppError("ORDNER_UNSICHER", f"{path.name} existiert, ist aber kein Ordner")
        return path
    try:
        path.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise AppError("ORDNER_ANLEGEN", f"{path.name} konnte nicht angelegt werden: {exc.strerror}") from None
    return path


def _mask(text: str) -> str:
    import re

    user = os.environ.get("USERNAME") or Path.home().name
    out = text.replace(user, "<benutzer>") if user else text
    host = platform.node()
    if host and len(host) >= 3:
        out = out.replace(host, "<rechner>")
    out = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "<mail>", out)
    out = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip>", out)
    out = re.sub(r"\b(?:[0-9a-fA-F]{1,4}:){4,7}[0-9a-fA-F]{1,4}\b|(?<![\w:])[0-9a-fA-F]{0,4}::[0-9a-fA-F:]*[0-9a-fA-F]", "<ip>", out)
    out = re.sub(r"\b[0-9a-f]{64}\b", "<hash>", out)
    return out


NEWLINE = os.linesep
DEFAULT_CPU_PROZENT = 25
DEFAULT_RAM_GIB = 2


@dataclass(frozen=True)
class Freigabe:
    nur_im_leerlauf: bool
    cpu_prozent: int
    ram_gib: float
    speicher_mb: int = 500
    speicher_ort: str = ""

    def text_de(self) -> str:
        wann = "nur wenn du den Rechner nicht benutzt" if self.nur_im_leerlauf else "auch während du arbeitest"
        wo = f" auf Laufwerk {laufwerk_name(self.speicher_ort)}" if self.speicher_ort else ""
        speicher = f" Auf der Festplatte{wo} hält es bis zu {groesse_de(self.speicher_mb)} des gemeinsamen Wissens." if self.speicher_mb else " Auf der Festplatte hält es nichts für die Community."
        return f"Arbeiten {wann}; höchstens {self.cpu_prozent} % Rechenkraft und {zahl_de(self.ram_gib)} GB Arbeitsspeicher.{speicher}"


def zahl_de(x: float) -> str:
    return f"{float(x):g}".replace(".", ",")


def groesse_de(mb: float) -> str:
    mb = float(mb or 0)
    if mb >= 1000 * 1000:
        return f"{zahl_de(round(mb / 1000 / 1000, 1))} TB"
    if mb >= 1000:
        return f"{zahl_de(round(mb / 1000, 1))} GB"
    return f"{int(round(mb))} MB"


def laufwerk_name(ort: str) -> str:
    o = str(ort or "")
    return o[:2] if len(o) >= 2 and o[1] == ":" else o


def ram_max_gib(first: "FirstStartResult | None") -> float:
    if first is None or not first.memory_gib:
        return 4.0
    return max(RAM_SCHRITT_GIB, math.floor((first.memory_gib - RAM_REST_GIB) / RAM_SCHRITT_GIB) * RAM_SCHRITT_GIB)


def speicher_empfehlung_mb(frei_mb: float | None) -> int:
    if not frei_mb:
        return DEFAULT_SPEICHER_MB
    mb = min(max(frei_mb * SPEICHER_EMPF_ANTEIL, DEFAULT_SPEICHER_MB), SPEICHER_EMPF_MAX_MB)
    return int(round(mb / 100.0) * 100)


def laufwerke() -> list[dict]:
    import shutil
    out: list[dict] = []
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            maske = k32.GetLogicalDrives()
            for i in range(26):
                if not maske & (1 << i):
                    continue
                wurzel = f"{chr(65 + i)}:\\"
                if k32.GetDriveTypeW(ctypes.c_wchar_p(wurzel)) != 3:
                    continue
                try:
                    u = shutil.disk_usage(wurzel)
                except OSError:
                    continue
                name = ctypes.create_unicode_buffer(261)
                try:
                    k32.GetVolumeInformationW(ctypes.c_wchar_p(wurzel), name, 261, None, None, None, None, 0)
                except Exception:
                    pass
                out.append({"ort": wurzel, "name": wurzel[:2], "bezeichnung": name.value[:40], "frei_mb": u.free // 1_000_000, "gesamt_mb": u.total // 1_000_000})
        except Exception:
            return []
    else:
        try:
            u = shutil.disk_usage(Path.home())
            out.append({"ort": str(Path.home()), "name": str(Path.home()), "bezeichnung": "", "frei_mb": u.free // 1_000_000, "gesamt_mb": u.total // 1_000_000})
        except OSError:
            pass
    return out


def recommended_freigabe(first: "FirstStartResult | None") -> Freigabe:
    if first is None:
        return Freigabe(True, DEFAULT_CPU_PROZENT, DEFAULT_RAM_GIB)
    quarter = first.memory_gib / 4.0
    ram = min(max(RAM_SCHRITT_GIB, math.floor(quarter / RAM_SCHRITT_GIB) * RAM_SCHRITT_GIB), ram_max_gib(first))
    cpu = 50 if (first.cpu_cores or 0) >= 8 else 25
    return Freigabe(True, cpu, ram)


def freigabe_pruefen(f: Freigabe) -> None:
    ram = f.ram_gib
    ok = (isinstance(f.cpu_prozent, int) and not isinstance(f.cpu_prozent, bool) and CPU_MIN <= f.cpu_prozent <= CPU_MAX
          and isinstance(ram, (int, float)) and not isinstance(ram, bool) and RAM_SCHRITT_GIB <= ram <= 1024
          and abs(ram / RAM_SCHRITT_GIB - round(ram / RAM_SCHRITT_GIB)) < 1e-6
          and isinstance(f.speicher_mb, int) and not isinstance(f.speicher_mb, bool) and (f.speicher_mb == 0 or SPEICHER_MIN_MB <= f.speicher_mb <= SPEICHER_MAX_MB)
          and isinstance(f.speicher_ort, str) and len(f.speicher_ort) <= 260)
    if not ok:
        raise AppError("FREIGABE_UNGUELTIG", "Prozessor-, Arbeitsspeicher- oder Festplattenwert nicht erlaubt")


def ram_choices_for(first: "FirstStartResult | None") -> tuple[int, ...]:
    if first is None:
        return RAM_CHOICES_GIB
    return tuple(g for g in RAM_CHOICES_GIB if g <= first.memory_gib - 2.0) or (RAM_CHOICES_GIB[0],)


def freigabe_folgen_saetze(freigabe: Freigabe, first: "FirstStartResult | None") -> list[str]:
    if first is None:
        return ["Sobald die Erststart-Prüfung gelaufen ist, siehst du hier, was für dich übrig bleibt."]
    rest_ram = max(first.memory_gib - freigabe.ram_gib, 0.0)
    rest_cpu = 100 - freigabe.cpu_prozent
    saetze = [f"Dein Gerät hat {zahl_de(first.memory_gib)} GB und {first.cpu_cores or '?'} Kerne."]
    if freigabe.nur_im_leerlauf:
        saetze.append(f"Mit dieser Freigabe bleiben dir {zahl_de(rest_ram)} GB und {rest_cpu} % Prozessor, gearbeitet wird nur, wenn du nicht am Rechner bist.")
    else:
        saetze.append(f"Mit dieser Freigabe bleiben dir {zahl_de(rest_ram)} GB und {rest_cpu} % Prozessor, gearbeitet wird auch, während du arbeitest.")
    if rest_ram < 4.0 or rest_cpu <= 25:
        saetze.append("Das wird dein Arbeiten spürbar bremsen.")
    elif rest_ram < 8.0 or rest_cpu <= 50:
        saetze.append("Für Büro und Internet reicht das gut, für Videoschnitt oder Spiele nicht.")
    else:
        saetze.append("Davon merkst du im Alltag praktisch nichts.")
    if freigabe.speicher_mb == 0:
        saetze.append("Auf der Festplatte hält es nichts für die Community.")
    elif freigabe.speicher_ort:
        saetze.append(f"Auf der Festplatte (Laufwerk {laufwerk_name(freigabe.speicher_ort)}) hält es bis zu {groesse_de(freigabe.speicher_mb)} des gemeinsamen Wissens, jede Scheibe geprüft und im Netz dreifach.")
    else:
        saetze.append(f"Auf der Festplatte hält es bis zu {groesse_de(freigabe.speicher_mb)} des gemeinsamen Wissens, jede Scheibe geprüft und im Netz dreifach.")
    return saetze


def freigabe_folgen_de(freigabe: Freigabe, first: "FirstStartResult | None") -> str:
    return " ".join(freigabe_folgen_saetze(freigabe, first))


class AppCore:

    def __init__(self, profile: Profile, *, base_dir: Path | None = None) -> None:
        self.profile = profile
        self.base_dir = Path(base_dir) if base_dir is not None else default_base_dir(profile)
        if not self.base_dir.is_absolute():
            raise AppError("ORDNER_UNSICHER", "Basisordner muss absolut sein")
        other = default_base_dir(Profile.PRODUKTIV if profile is Profile.TEST else Profile.TEST)
        try:
            if self.base_dir.resolve() == other.resolve() or other.resolve() in self.base_dir.resolve().parents:
                raise AppError("PROFIL_VERMISCHT", "der Basisordner gehört zum anderen Profil")
        except OSError:
            pass
        self.node_agent_dir = self.base_dir / NODE_AGENT_DIRNAME
        self.diagnosis_dir = self.base_dir / DIAGNOSIS_DIRNAME
        self.first_start_path = self.base_dir / FIRST_START_FILENAME


    def ensure_directories(self) -> tuple[Path, ...]:
        created = tuple(ensure_plain_directory(p) for p in (self.base_dir, self.node_agent_dir, self.diagnosis_dir))
        return created


    def load_first_start(self) -> FirstStartResult | None:
        if not self.first_start_path.exists():
            return None
        try:
            data = self.first_start_path.read_bytes()
            if len(data) > MAX_FIRST_START_SIZE_BYTES:
                return None
            payload = json.loads(data.decode("utf-8"))
            return FirstStartResult(
                checked_at=str(payload["checked_at"]), os_name=str(payload["os"]),
                cpu_cores=payload.get("cpu_cores"), memory_gib=float(payload["memory_gib"]),
                gpu_names=tuple(str(g) for g in payload.get("gpus", [])), role=Role(payload["role"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def run_first_start_check(self, *, report: hardware_detect.HardwareReport | None = None) -> FirstStartResult:
        existing = self.load_first_start()
        if existing is not None:
            return existing
        self.ensure_directories()
        report = report if report is not None else hardware_detect.build_report()
        memory_gib = round(report.memory.total_bytes / (1024 ** 3), 1)
        gpus = tuple(g.name for g in report.gpus)
        result = FirstStartResult(
            checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            os_name=report.os, cpu_cores=report.cpu.logical_cores, memory_gib=memory_gib, gpu_names=gpus,
            role=suggest_role(memory_gib=memory_gib, gpu_names=gpus),
        )
        sicher_schreiben.json_datei(self.first_start_path, result.to_json_dict())
        return result


    def run_state(self) -> node_local_state.RunState:
        try:
            return node_local_state.load_local_state(self.node_agent_dir).run_state
        except node_local_state.LocalStateError:
            return node_local_state.RunState.STOPPED

    def start(self) -> None:
        self.ensure_directories()
        if not (self.node_agent_dir / "local_state.json").exists():
            node_local_state.set_run_state(self.node_agent_dir, node_local_state.RunState.STOPPED)
            node_local_state.set_work_policy(self.node_agent_dir, node_local_state.WorkPolicy.IDLE_ONLY)
        node_local_state.set_run_state(self.node_agent_dir, node_local_state.RunState.ACTIVE)

    def pause(self) -> None:
        self.ensure_directories()
        node_local_state.set_run_state(self.node_agent_dir, node_local_state.RunState.PAUSED)

    def stop(self) -> None:
        self.ensure_directories()
        node_local_state.set_run_state(self.node_agent_dir, node_local_state.RunState.STOPPED)


    def load_freigabe(self) -> "Freigabe":
        try:
            policy = node_local_state.load_local_state(self.node_agent_dir).work_policy
        except node_local_state.LocalStateError:
            policy = node_local_state.WorkPolicy.IDLE_ONLY
        cpu, ram, speicher, ort = DEFAULT_CPU_PROZENT, DEFAULT_RAM_GIB, DEFAULT_SPEICHER_MB, ""
        path = self.base_dir / FREIGABE_FILENAME
        if path.exists():
            try:
                payload = json.loads(path.read_bytes()[:MAX_FIRST_START_SIZE_BYTES].decode("utf-8"))
                for feld in ("cpu_prozent", "ram_gib", "speicher_mb", "speicher_ort"):
                    wert = payload.get(feld)
                    if wert is None or isinstance(wert, bool):
                        continue
                    try:
                        probe = Freigabe(True, int(wert) if feld == "cpu_prozent" else cpu, float(wert) if feld == "ram_gib" else ram,
                                         int(wert) if feld == "speicher_mb" else speicher, str(wert) if feld == "speicher_ort" else ort)
                        freigabe_pruefen(probe)
                    except (AppError, TypeError, ValueError):
                        continue
                    cpu, ram, speicher, ort = probe.cpu_prozent, probe.ram_gib, probe.speicher_mb, probe.speicher_ort
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        return Freigabe(nur_im_leerlauf=policy is node_local_state.WorkPolicy.IDLE_ONLY, cpu_prozent=cpu, ram_gib=ram, speicher_mb=speicher, speicher_ort=ort)

    def save_freigabe(self, freigabe: "Freigabe") -> None:
        freigabe_pruefen(freigabe)
        self.ensure_directories()
        if not (self.node_agent_dir / "local_state.json").exists():
            node_local_state.set_run_state(self.node_agent_dir, node_local_state.RunState.STOPPED)
        node_local_state.set_work_policy(
            self.node_agent_dir,
            node_local_state.WorkPolicy.IDLE_ONLY if freigabe.nur_im_leerlauf else node_local_state.WorkPolicy.ALWAYS,
        )
        sicher_schreiben.json_datei(self.base_dir / FREIGABE_FILENAME, {"cpu_prozent": freigabe.cpu_prozent, "ram_gib": freigabe.ram_gib, "speicher_mb": freigabe.speicher_mb, "speicher_ort": freigabe.speicher_ort, "erzwungen_ab": "Paket 4"}, ascii_=True)


    def status_text_de(self, *, arbeit: str | None = None, kurz: bool = False) -> str:
        state = self.run_state()
        first = self.load_first_start()
        role = ROLE_LABELS_DE[first.role] if first else "Erststart-Prüfung steht noch aus"
        if state is node_local_state.RunState.ACTIVE:
            line = arbeit if arbeit else "Bereit. Aufträge kommen vom Community-Server."
        elif state is node_local_state.RunState.PAUSED:
            line = "Nichts Neues wird angenommen, bis du auf Start klickst."
        else:
            line = "Nichts läuft. Start teilt deine Rechenkraft mit der Community."
        if kurz:
            return line
        wort = {node_local_state.RunState.ACTIVE: "Eingeschaltet", node_local_state.RunState.PAUSED: "Pausiert"}.get(state, "Gestoppt")
        return f"{wort}. {line}\nGerät: {role}\nFreigabe: {self.load_freigabe().text_de()}"


    def write_diagnosis_report(self) -> Path:
        self.ensure_directories()
        first = self.load_first_start()
        lines = [
            f"{APP_NAME} - Diagnosebericht",
            f"Erstellt: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"Version: {APP_VERSION}",
            f"Profil: {self.profile.value}",
            f"Zustand: {self.run_state().value}",
            f"Windows: {platform.system()} {platform.release()} ({platform.version()})",
            f"Ausführung: {'EXE' if getattr(sys, 'frozen', False) else 'Python-Quelle'}",
        ]
        if first:
            lines += [
                f"Erststart-Prüfung: {first.checked_at}",
                f"Prozessorkerne: {first.cpu_cores}",
                f"Arbeitsspeicher: {first.memory_gib} GiB",
                f"Grafik: {', '.join(first.gpu_names) or '-'}",
                f"Rolle: {first.role.value}",
            ]
        else:
            lines.append("Erststart-Prüfung: noch nicht gemacht")
        for name, path in (("Basisordner", self.base_dir), ("node-agent", self.node_agent_dir), ("diagnose", self.diagnosis_dir)):
            lines.append(f"Ordner {name}: {'vorhanden' if path.is_dir() else 'fehlt'}")
        text = _mask("\n".join(lines)) + "\n"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.diagnosis_dir / f"diagnose-{stamp}.txt"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        fd = os.open(target, flags, 0o600)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        return target


def is_smart_app_control_on() -> bool | None:
    if platform.system() != "Windows":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as key:
            value, _ = winreg.QueryValueEx(key, "VerifiedAndReputablePolicyState")
        return int(value) == 1
    except OSError:
        return None


__all__ = ["AppCore", "AppError", "Profile", "Role", "FirstStartResult", "Freigabe", "recommended_freigabe", "ram_choices_for", "freigabe_folgen_de", "freigabe_folgen_saetze", "suggest_role", "ensure_plain_directory", "default_base_dir", "is_smart_app_control_on"]
