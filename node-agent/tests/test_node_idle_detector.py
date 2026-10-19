# SPDX-License-Identifier: AGPL-3.0-or-later
import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import node_idle_detector as nid


class _FakeLastInputInfo:

    def __init__(self):
        self.cbSize = 0
        self.dwTime = 0


class _FakeUser32:
    def __init__(self, *, dw_time: int, succeed: bool = True):
        self._dw_time = dw_time
        self._succeed = succeed
        self.received_cbsize = None

    def GetLastInputInfo(self, ref):
        struct = ref._obj if hasattr(ref, "_obj") else ref
        self.received_cbsize = struct.cbSize
        if not self._succeed:
            return 0
        struct.dwTime = self._dw_time
        return 1


class _FakeKernel32:
    def __init__(self, *, tick_count: int):
        self._tick_count = tick_count

    def GetTickCount(self):
        return self._tick_count


class _FakeWindll:
    def __init__(self, *, user32: _FakeUser32, kernel32: _FakeKernel32):
        self.user32 = user32
        self.kernel32 = kernel32


def test_non_windows_platform_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(nid.platform, "system", lambda: "Linux")
    monkeypatch.setattr(nid, "LOGIND_SESSIONS", tmp_path / "kein-logind")
    with pytest.raises(nid.IdleDetectionUnavailableError):
        nid.get_idle_seconds()
    monkeypatch.setattr(nid.platform, "system", lambda: "SunOS")
    with pytest.raises(nid.IdleDetectionUnavailableError):
        nid.get_idle_seconds()


def _sitzung(ordner, name, **werte):
    ordner.mkdir(exist_ok=True)
    zeilen = ["# logind", *(f"{k}={v}" for k, v in werte.items()), "USER=anna"]
    (ordner / name).write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def test_linux_nobody_at_a_seat_counts_as_idle_someone_there_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(nid.platform, "system", lambda: "Linux")
    s = tmp_path / "sessions"
    monkeypatch.setattr(nid, "LOGIND_SESSIONS", s)
    s.mkdir()
    assert nid.get_idle_seconds() == nid.NIEMAND_DA_S
    _sitzung(s, "3", ACTIVE="1", REMOTE="1", TYPE="tty", SEAT="")
    _sitzung(s, "4", ACTIVE="0", REMOTE="0", TYPE="wayland", SEAT="seat0")
    (s / "4.ref").write_text("x", encoding="utf-8")
    assert nid.get_idle_seconds() == nid.NIEMAND_DA_S
    _sitzung(s, "5", ACTIVE="1", REMOTE="0", TYPE="wayland", SEAT="seat0")
    with pytest.raises(nid.IdleDetectionUnavailableError):
        nid.get_idle_seconds()


def test_get_idle_seconds_computes_elapsed_time_from_tick_counts(monkeypatch):
    monkeypatch.setattr(nid.platform, "system", lambda: "Windows")
    fake_windll = _FakeWindll(
        user32=_FakeUser32(dw_time=10_000),
        kernel32=_FakeKernel32(tick_count=15_000),
    )
    monkeypatch.setattr(nid.ctypes, "windll", fake_windll, raising=False)

    idle_seconds = nid.get_idle_seconds()

    assert idle_seconds == pytest.approx(5.0)


def test_get_idle_seconds_zero_when_input_was_just_now(monkeypatch):
    monkeypatch.setattr(nid.platform, "system", lambda: "Windows")
    fake_windll = _FakeWindll(
        user32=_FakeUser32(dw_time=42_000),
        kernel32=_FakeKernel32(tick_count=42_000),
    )
    monkeypatch.setattr(nid.ctypes, "windll", fake_windll, raising=False)

    assert nid.get_idle_seconds() == pytest.approx(0.0)


def test_get_last_input_info_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(nid.platform, "system", lambda: "Windows")
    fake_windll = _FakeWindll(
        user32=_FakeUser32(dw_time=0, succeed=False),
        kernel32=_FakeKernel32(tick_count=1_000),
    )
    monkeypatch.setattr(nid.ctypes, "windll", fake_windll, raising=False)

    with pytest.raises(nid.IdleDetectionUnavailableError):
        nid.get_idle_seconds()


def test_tick_count_wraparound_counts_across_the_wrap(monkeypatch):
    monkeypatch.setattr(nid.platform, "system", lambda: "Windows")
    fake_windll = _FakeWindll(
        user32=_FakeUser32(dw_time=4_294_967_290),
        kernel32=_FakeKernel32(tick_count=100),
    )
    monkeypatch.setattr(nid.ctypes, "windll", fake_windll, raising=False)

    assert nid.get_idle_seconds() == pytest.approx(0.106)


@pytest.mark.parametrize("tick, dw_time, erwartet", [
    (3_000_000_000, 2_999_990_000, 10.0),
    (3_000_000_000 - 2**32, 2_999_990_000, 10.0),
    (100, 4_294_967_200, 0.196),
])
def test_idle_is_right_after_24_9_days_of_uptime(monkeypatch, tick, dw_time, erwartet):
    monkeypatch.setattr(nid.platform, "system", lambda: "Windows")
    monkeypatch.setattr(nid.ctypes, "windll", _FakeWindll(user32=_FakeUser32(dw_time=dw_time), kernel32=_FakeKernel32(tick_count=tick)), raising=False)
    assert nid.get_idle_seconds() == pytest.approx(erwartet)


def test_the_real_gettickcount_is_read_unsigned():
    if nid.platform.system() == "Darwin":
        assert nid.get_idle_seconds() >= 0
        return
    if nid.platform.system() != "Windows":
        try:
            assert nid.get_idle_seconds() == nid.NIEMAND_DA_S
        except nid.IdleDetectionUnavailableError:
            assert nid.lokale_sitzung_aktiv() is not False
        return
    nid.get_idle_seconds()
    assert nid.ctypes.windll.kernel32.GetTickCount.restype is nid.ctypes.c_uint32


def _read_source_ast() -> ast.Module:
    source = (Path(__file__).resolve().parent.parent / "node_idle_detector.py").read_text(encoding="utf-8")
    return ast.parse(source)


def test_module_never_calls_a_keyboard_or_mouse_hook_api():
    forbidden_names = {
        "SetWindowsHookEx",
        "GetAsyncKeyState",
        "GetKeyState",
        "GetForegroundWindow",
        "GetWindowText",
        "EnumWindows",
        "EnumProcesses",
        "CreateToolhelp32Snapshot",
    }
    tree = _read_source_ast()
    called_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not (called_names & forbidden_names)


def test_module_has_no_subprocess_or_dynamic_execution():
    tree = _read_source_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "subprocess" for alias in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
