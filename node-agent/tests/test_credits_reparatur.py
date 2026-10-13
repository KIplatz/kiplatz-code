# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_core
import credits

from test_app_web import _api


def test_zero_filled_ledger_is_set_aside_and_rebuilt_from_the_servers_count(tmp_path):
    k = credits.Kontobuch(tmp_path)
    k.frage(); k.antwort()
    k.pfad.write_bytes(b"\x00" * 39292)
    assert k.beschaedigt()
    st = k.reparieren(verdient=2369, geraet="Laptop")
    assert st.guthaben == 2469 and st.verdient == 2369 and st.ausgegeben == 0
    beiseite = [p for p in tmp_path.iterdir() if p.name.startswith("credits.beschaedigt-")]
    assert len(beiseite) == 1 and beiseite[0].read_bytes() == b"\x00" * 39292
    d = json.loads(k.pfad.read_text(encoding="utf-8"))
    assert d["verlauf"][-1]["art"] == "reparatur" and "Bestenliste" in d["verlauf"][-1]["notiz"]
    assert not k.beschaedigt() and k.reparieren(verdient=5).guthaben == 2469


def test_repair_without_the_server_starts_at_100(tmp_path):
    k = credits.Kontobuch(tmp_path)
    k.pfad.write_text("{kaputt", encoding="utf-8")
    st = k.reparieren(verdient=None)
    assert st.guthaben == credits.STARTGUTHABEN and st.verdient == 0 and "Bestenliste" not in k.verlauf(1)[0]["notiz"]


def test_window_heals_the_ledger_and_shows_a_number_again(tmp_path, monkeypatch):
    api, fake, _ = _api(tmp_path)
    api._kontobuch.pfad.write_bytes(b"\x00" * 1000)
    monkeypatch.setattr(api._community, "meine_daten", lambda: {"geraet": {"name": "Laptop", "credits": 2369}})
    c = api.zustand()["daten"]["credits"]
    assert c["guthaben"] == 2469 and c["verdient"] == 2369 and "neu angelegt" in c["text"] and "Bestenliste" in c["text"]
    assert api.zustand()["daten"]["credits"]["guthaben"] == 2469 and api._kontobuch.stand().guthaben == 2469
    assert any(p.name.startswith("credits.beschaedigt-") for p in api._kontobuch.pfad.parent.iterdir())


def test_saving_forces_the_bytes_to_disk(tmp_path, monkeypatch):
    aufrufe = []
    import os
    echt = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: aufrufe.append(fd) or echt(fd))
    credits.Kontobuch(tmp_path).antwort()
    assert aufrufe, "os.fsync must run before the new file replaces the old one"
    assert app_core.APP_BUILD >= "2026-09-22d"
