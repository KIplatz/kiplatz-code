# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sicher_schreiben

STATE_FILENAME = "local_state.json"

IDLE_THRESHOLD_SECONDS = 300.0


class RunState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class WorkPolicy(str, Enum):
    ALWAYS = "always"
    USER_PRESENT_MODE = "user_present_mode"
    IDLE_ONLY = "idle_only"


DEFAULT_RUN_STATE = RunState.ACTIVE
DEFAULT_WORK_POLICY = WorkPolicy.ALWAYS

RUN_STATE_LABELS: dict[RunState, str] = {
    RunState.ACTIVE: "Verbunden",
    RunState.PAUSED: "Pausiert",
    RunState.STOPPED: "Gestoppt",
}


class LocalStateError(Exception):
    pass


class LocalStateCorruptError(LocalStateError):
    pass


@dataclass(frozen=True)
class LocalNodeState:

    run_state: RunState
    work_policy: WorkPolicy
    updated_at: str


def _path(directory: Path) -> Path:
    return Path(directory) / STATE_FILENAME


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    sicher_schreiben.roh(path, data)


def _write_state(directory: Path, state: LocalNodeState) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_state": state.run_state.value,
        "work_policy": state.work_policy.value,
        "updated_at": state.updated_at,
    }
    _atomic_write_bytes(_path(directory), json.dumps(payload, indent=2).encode("utf-8"))


def create_default_local_state(directory: Path) -> LocalNodeState:
    directory = Path(directory)
    if _path(directory).exists():
        raise LocalStateError(f"A local state file already exists in {directory}. Refusing to overwrite it.")

    state = LocalNodeState(
        run_state=DEFAULT_RUN_STATE,
        work_policy=DEFAULT_WORK_POLICY,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_state(directory, state)
    return state


def load_local_state(directory: Path) -> LocalNodeState:
    state_path = _path(Path(directory))
    if not state_path.exists():
        raise LocalStateError(f"No local state found in {directory}.")

    try:
        for versuch in range(25):
            try:
                roh = state_path.read_text(encoding="utf-8")
                break
            except PermissionError:
                if versuch == 24:
                    raise
                time.sleep(0.004)
        payload = json.loads(roh)
        run_state = RunState(payload["run_state"])
        work_policy = WorkPolicy(payload["work_policy"])
        updated_at = payload["updated_at"]
        if not isinstance(updated_at, str) or not updated_at:
            raise ValueError("updated_at must be a non-empty string.")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        raise LocalStateCorruptError(f"{state_path.name} is unreadable or malformed.") from None

    return LocalNodeState(run_state=run_state, work_policy=work_policy, updated_at=updated_at)


_init_lock = threading.Lock()


def load_or_initialize_local_state(directory: Path) -> LocalNodeState:
    with _init_lock:
        try:
            return load_local_state(directory)
        except LocalStateError:
            if _path(Path(directory)).exists():
                raise
            return create_default_local_state(directory)


def set_run_state(directory: Path, new_run_state: RunState) -> LocalNodeState:
    current = load_or_initialize_local_state(directory)
    new_state = LocalNodeState(
        run_state=new_run_state,
        work_policy=current.work_policy,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_state(directory, new_state)
    return new_state


def set_work_policy(directory: Path, new_work_policy: WorkPolicy) -> LocalNodeState:
    current = load_or_initialize_local_state(directory)
    new_state = LocalNodeState(
        run_state=current.run_state,
        work_policy=new_work_policy,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_state(directory, new_state)
    return new_state


def may_execute_new_job(local_state: LocalNodeState, *, idle_seconds: float | None) -> bool:
    if local_state.run_state != RunState.ACTIVE:
        return False

    if local_state.work_policy == WorkPolicy.ALWAYS:
        return True

    if local_state.work_policy in (WorkPolicy.USER_PRESENT_MODE, WorkPolicy.IDLE_ONLY):
        if idle_seconds is None:
            return False
        return idle_seconds >= IDLE_THRESHOLD_SECONDS

    raise AssertionError(f"Unhandled work policy: {local_state.work_policy!r}")
