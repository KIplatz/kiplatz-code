# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import node_local_state as nls


def _dir(tmp_path) -> Path:
    return tmp_path / "local_state"


def test_load_or_initialize_creates_conservative_defaults_on_first_run(tmp_path):
    state = nls.load_or_initialize_local_state(_dir(tmp_path))
    assert state.run_state == nls.RunState.ACTIVE
    assert state.work_policy == nls.WorkPolicy.ALWAYS
    assert state.updated_at


def test_load_or_initialize_persists_the_default_so_a_second_call_sees_the_same_file(tmp_path):
    directory = _dir(tmp_path)
    first = nls.load_or_initialize_local_state(directory)
    second = nls.load_or_initialize_local_state(directory)
    assert first == second


def test_create_default_local_state_refuses_to_overwrite_an_existing_file(tmp_path):
    directory = _dir(tmp_path)
    nls.create_default_local_state(directory)
    with pytest.raises(nls.LocalStateError):
        nls.create_default_local_state(directory)


def test_load_local_state_without_load_or_initialize_raises_when_missing(tmp_path):
    with pytest.raises(nls.LocalStateError):
        nls.load_local_state(_dir(tmp_path))


def test_set_run_state_persists_and_survives_a_fresh_load_a_restart_simulation(tmp_path):
    directory = _dir(tmp_path)
    nls.load_or_initialize_local_state(directory)

    nls.set_run_state(directory, nls.RunState.STOPPED)

    reloaded = nls.load_local_state(directory)
    assert reloaded.run_state == nls.RunState.STOPPED


def test_set_run_state_keeps_the_existing_work_policy(tmp_path):
    directory = _dir(tmp_path)
    nls.load_or_initialize_local_state(directory)
    nls.set_work_policy(directory, nls.WorkPolicy.IDLE_ONLY)

    nls.set_run_state(directory, nls.RunState.PAUSED)

    reloaded = nls.load_local_state(directory)
    assert reloaded.run_state == nls.RunState.PAUSED
    assert reloaded.work_policy == nls.WorkPolicy.IDLE_ONLY


def test_set_work_policy_keeps_the_existing_run_state(tmp_path):
    directory = _dir(tmp_path)
    nls.set_run_state(directory, nls.RunState.PAUSED)

    nls.set_work_policy(directory, nls.WorkPolicy.USER_PRESENT_MODE)

    reloaded = nls.load_local_state(directory)
    assert reloaded.run_state == nls.RunState.PAUSED
    assert reloaded.work_policy == nls.WorkPolicy.USER_PRESENT_MODE


def test_a_stopped_node_stays_stopped_across_repeated_reloads(tmp_path):
    directory = _dir(tmp_path)
    nls.set_run_state(directory, nls.RunState.STOPPED)
    for _ in range(5):
        assert nls.load_or_initialize_local_state(directory).run_state == nls.RunState.STOPPED


def test_concurrent_first_run_initialization_never_races(tmp_path):
    directory = _dir(tmp_path)
    errors: list[Exception] = []
    results: list[nls.LocalNodeState] = []
    barrier = threading.Barrier(8)

    def _worker():
        try:
            barrier.wait(timeout=5.0)
            results.append(nls.load_or_initialize_local_state(directory))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    assert not errors, f"concurrent initialization raised: {errors}"
    assert len(results) == 8
    assert all(r == results[0] for r in results)


def test_load_local_state_fails_closed_on_malformed_json(tmp_path):
    directory = _dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / nls.STATE_FILENAME).write_text("not json", encoding="utf-8")

    with pytest.raises(nls.LocalStateCorruptError):
        nls.load_local_state(directory)


def test_load_local_state_fails_closed_on_invalid_run_state_value(tmp_path):
    directory = _dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / nls.STATE_FILENAME).write_text(
        '{"run_state": "SOMETHING_ELSE", "work_policy": "always", "updated_at": "2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    with pytest.raises(nls.LocalStateCorruptError):
        nls.load_local_state(directory)


def test_load_local_state_fails_closed_on_invalid_work_policy_value(tmp_path):
    directory = _dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / nls.STATE_FILENAME).write_text(
        '{"run_state": "ACTIVE", "work_policy": "turbo", "updated_at": "2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    with pytest.raises(nls.LocalStateCorruptError):
        nls.load_local_state(directory)


def test_load_local_state_fails_closed_on_missing_field(tmp_path):
    directory = _dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / nls.STATE_FILENAME).write_text('{"run_state": "ACTIVE"}', encoding="utf-8")

    with pytest.raises(nls.LocalStateCorruptError):
        nls.load_local_state(directory)


def test_load_or_initialize_never_papers_over_a_corrupt_existing_file(tmp_path):
    directory = _dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / nls.STATE_FILENAME).write_text("not json", encoding="utf-8")

    with pytest.raises(nls.LocalStateCorruptError):
        nls.load_or_initialize_local_state(directory)


def _state(run_state: nls.RunState, work_policy: nls.WorkPolicy = nls.WorkPolicy.ALWAYS) -> nls.LocalNodeState:
    return nls.LocalNodeState(run_state=run_state, work_policy=work_policy, updated_at="2026-01-01T00:00:00+00:00")


def test_paused_never_allows_a_new_job_regardless_of_policy():
    for policy in nls.WorkPolicy:
        assert not nls.may_execute_new_job(_state(nls.RunState.PAUSED, policy), idle_seconds=10_000.0)


def test_stopped_never_allows_a_new_job_regardless_of_policy():
    for policy in nls.WorkPolicy:
        assert not nls.may_execute_new_job(_state(nls.RunState.STOPPED, policy), idle_seconds=10_000.0)


def test_active_with_always_policy_allows_a_job_regardless_of_idle_time():
    state = _state(nls.RunState.ACTIVE, nls.WorkPolicy.ALWAYS)
    assert nls.may_execute_new_job(state, idle_seconds=0.0)
    assert nls.may_execute_new_job(state, idle_seconds=None)


@pytest.mark.parametrize("policy", [nls.WorkPolicy.USER_PRESENT_MODE, nls.WorkPolicy.IDLE_ONLY])
def test_active_with_idle_gated_policy_requires_the_threshold_to_be_met(policy):
    state = _state(nls.RunState.ACTIVE, policy)
    assert not nls.may_execute_new_job(state, idle_seconds=nls.IDLE_THRESHOLD_SECONDS - 1.0)
    assert nls.may_execute_new_job(state, idle_seconds=nls.IDLE_THRESHOLD_SECONDS)
    assert nls.may_execute_new_job(state, idle_seconds=nls.IDLE_THRESHOLD_SECONDS + 1.0)


@pytest.mark.parametrize("policy", [nls.WorkPolicy.USER_PRESENT_MODE, nls.WorkPolicy.IDLE_ONLY])
def test_active_with_idle_gated_policy_fails_closed_when_idle_time_is_unknown(policy):
    state = _state(nls.RunState.ACTIVE, policy)
    assert not nls.may_execute_new_job(state, idle_seconds=None)


def test_every_run_state_has_a_simple_german_label():
    for run_state in nls.RunState:
        assert run_state in nls.RUN_STATE_LABELS
        assert nls.RUN_STATE_LABELS[run_state]
