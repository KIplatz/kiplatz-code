# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import community
import modell_katalog

ALT = "https://alt.example:8444"
ALT_SPIELWIESE = "https://alt.example:8445"


@pytest.fixture
def umzug(monkeypatch):
    monkeypatch.setattr(community, "ALTE_ADRESSEN", {ALT: community.STANDARD_ADRESSE, ALT_SPIELWIESE: "https://kiplatz.at:8445"})


def test_standard_ist_kiplatz():
    assert community.STANDARD_ADRESSE == "https://kiplatz.at:8444" == modell_katalog.SERVER
    assert community.ALTE_ADRESSEN == {}


def test_alte_gespeicherte_adresse_wird_umgestellt(tmp_path, umzug):
    for gespeichert, erwartet in ((ALT, "https://kiplatz.at:8444"), (ALT + "/", "https://kiplatz.at:8444"),
                                  (ALT_SPIELWIESE, "https://kiplatz.at:8445"), (None, "https://kiplatz.at:8444")):
        basis = tmp_path / str(abs(hash(str(gespeichert))))
        c = community.Community(basis)
        c.dir.mkdir(parents=True, exist_ok=True)
        if gespeichert:
            (c.dir / "einstellung.json").write_text(json.dumps({"adresse": gespeichert}), encoding="utf-8")
        assert community.Community(basis).adresse == erwartet, gespeichert


def test_die_umgestellte_adresse_wird_zurueckgeschrieben(tmp_path, umzug):
    c = community.Community(tmp_path)
    c.dir.mkdir(parents=True, exist_ok=True)
    (c.dir / "einstellung.json").write_text(json.dumps({"adresse": ALT, "anderes": 1}), encoding="utf-8")
    assert community.Community(tmp_path).adresse == "https://kiplatz.at:8444"
    assert json.loads((c.dir / "einstellung.json").read_text(encoding="utf-8")) == {"adresse": "https://kiplatz.at:8444", "anderes": 1}


def test_eigene_adresse_bleibt(tmp_path):
    c = community.Community(tmp_path)
    c.dir.mkdir(parents=True, exist_ok=True)
    (c.dir / "einstellung.json").write_text(json.dumps({"adresse": "https://192.168.1.20:8444"}), encoding="utf-8")
    assert community.Community(tmp_path).adresse == "https://192.168.1.20:8444"
