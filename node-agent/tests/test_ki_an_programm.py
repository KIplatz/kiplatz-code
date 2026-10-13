# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import ki_laufzeit


def _lebt(pid: int) -> bool:
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    h = k32.OpenProcess(0x1000 | 0x00100000, False, pid)
    if not h:
        return False
    try:
        return k32.WaitForSingleObject(h, 0) == 0x102
    finally:
        k32.CloseHandle(h)


@pytest.mark.skipif(os.name != "nt", reason="job objects are Windows")
def test_child_ends_when_the_program_is_killed_hard(tmp_path):
    eltern = tmp_path / "eltern.py"
    eltern.write_text(textwrap.dedent(f"""
        import subprocess, sys, time
        sys.path.insert(0, {str(HIER)!r})
        import ki_laufzeit
        kind = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(kind.pid, ki_laufzeit.an_programm_binden(kind), flush=True)
        time.sleep(120)
    """), encoding="utf-8")
    p = subprocess.Popen([sys.executable, str(eltern)], stdout=subprocess.PIPE, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    kind_pid = None
    try:
        zeile = p.stdout.readline().split()
        kind_pid, gebunden = int(zeile[0]), zeile[1] == "True"
        assert gebunden
        assert _lebt(kind_pid)
        p.kill()
        p.wait(timeout=10)
        for _ in range(50):
            if not _lebt(kind_pid):
                break
            time.sleep(0.1)
        assert not _lebt(kind_pid), "the child outlived the killed program"
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=10)


def test_test_doubles_are_left_alone():
    class Schein:
        pid = 1
    assert ki_laufzeit.an_programm_binden(Schein()) is False


def test_header_says_on_only_when_the_model_is_loaded():
    html = (HIER / "webapp" / "index.html").read_text(encoding="utf-8")
    assert 'k.laeuft && !startet ? `<span class="credits-chip"' in html
