# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nachschauen
import rechnen_zeit


@pytest.mark.parametrize("frage", [
    "What time is it in Sydney right now?", "What is the time in Sydney?", "What's the time in Sydney now?", "What’s the time in Sydney?", "Current time in Sydney",
    "Wie spät ist es aktuell in London?", "What time is it in Sydney?", "Wie spät ist es gerade in New York?",
])
def test_uhrzeit_wird_gerechnet(frage):
    assert rechnen_zeit.loesen(frage) is not None


@pytest.mark.parametrize("frage,domain", [
    ("Wie viele Einwohner hat Graz?", "statistik.at"),
    ("Wie viele Einwohner hat Zürich?", "bfs.admin.ch"),
    ("Wie viel kostet ein Reisepass in Linz?", "gv.at"),
    ("Wie viele Einwohner haben Klagenfurt und München?", ""),
    ("Was kostet ein Big Mac in Graz?", ""),
])
def test_land_aus_dem_ort(frage, domain):
    assert nachschauen.amts_domain(frage) == domain


def test_land_mit_mehreren_zeitzonen():
    e = rechnen_zeit.loesen("What is the local time in Australia?")
    assert e.en.startswith("Australia has several time zones. It is ") and " in Sydney right now" in e.en
    assert rechnen_zeit.loesen("Wie spät ist es in Australien?").de.startswith("Australien hat mehrere Zeitzonen. In Sydney ist es jetzt ")
    assert rechnen_zeit.loesen("What time zone is Australia in?") is None
