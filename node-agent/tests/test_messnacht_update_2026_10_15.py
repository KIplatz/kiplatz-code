# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit


def _probe(tmp_path, monkeypatch, **anders):
    monkeypatch.setattr(ki_laufzeit, "PROBE_MIN_BYTES", 10)
    o = ki_laufzeit.KiOrdner(tmp_path)
    o.modelle_dir.mkdir(parents=True)
    inhalt = b"GGUF" + b"x" * 100
    (o.modelle_dir / "ministral-14b-kiplatz-test.gguf").write_bytes(inhalt)
    d = {"datei": "ministral-14b-kiplatz-test.gguf", "sha256": hashlib.sha256(inhalt).hexdigest(), "basis": "14B", "nacht": "2026-10-14", "erledigt": ""}
    d.update(anders)
    (o.ki_dir / ki_laufzeit.PROBEMODELL).write_text(json.dumps(d), encoding="utf-8")
    return o


def _datei(o):
    return json.loads((o.ki_dir / ki_laufzeit.PROBEMODELL).read_text(encoding="utf-8"))


def test_eine_begonnene_messung_ohne_meldung_wird_in_einer_der_naechsten_naechte_nachgeholt(tmp_path, monkeypatch):
    o = _probe(tmp_path, monkeypatch, erledigt="2026-10-14")
    assert ki_laufzeit.probemodell(o, "2026-10-14") is None
    pfad, info = ki_laufzeit.probemodell(o, "2026-10-16")
    assert pfad.name == "ministral-14b-kiplatz-test.gguf" and info["nacht"] == "2026-10-16"
    assert _datei(o)["nacht"] == "2026-10-16" and _datei(o)["erledigt"] == ""
    ki_laufzeit.probemodell_erledigt(o, "2026-10-16")
    ki_laufzeit.probemodell_gemeldet(o, "2026-10-16")
    assert ki_laufzeit.probemodell(o, "2026-10-17") is None


def test_gemeldet_oder_zu_alt_wird_nicht_nachgeholt_eine_verpasste_nacht_schon(tmp_path, monkeypatch):
    o = _probe(tmp_path, monkeypatch, erledigt="2026-10-14", gemeldet="2026-10-14")
    assert ki_laufzeit.probemodell(o, "2026-10-15") is None
    o = _probe(tmp_path / "b", monkeypatch, erledigt="2026-10-14")
    assert ki_laufzeit.probemodell(o, "2026-10-17")[1]["nacht"] == "2026-10-17"
    o = _probe(tmp_path / "d", monkeypatch, erledigt="2026-10-14")
    assert ki_laufzeit.probemodell(o, "2026-10-22") is None
    o = _probe(tmp_path / "c", monkeypatch)
    assert ki_laufzeit.probemodell(o, "2026-10-15")[1]["nacht"] == "2026-10-15"


def test_eine_unterbrochene_messung_ohne_nachholen_bis_mittag_kommt_in_der_naechsten_nacht(tmp_path, monkeypatch):
    o = _probe(tmp_path, monkeypatch)
    ki_laufzeit.probemodell_erledigt(o, "2026-10-14")
    assert ki_laufzeit.probemodell_freigeben(o, "2026-10-14") and _datei(o)["unterbrochen"] == "2026-10-14"
    assert ki_laufzeit.probemodell(o, "2026-10-15")[1]["nacht"] == "2026-10-15"
