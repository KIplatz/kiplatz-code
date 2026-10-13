# SPDX-License-Identifier: AGPL-3.0-or-later
import json

import pytest

import credits


def test_start_100_question_costs_1_answer_earns_1_and_persists(tmp_path):
    k = credits.Kontobuch(tmp_path)
    assert k.stand() == credits.Kontostand(100, 0, 0) and not k.pfad.exists()
    assert k.frage(geraet="Laptop").guthaben == 99
    assert k.antwort(geraet="Laptop") == credits.Kontostand(100, 1, 1)
    again = credits.Kontobuch(tmp_path)
    assert again.stand() == credits.Kontostand(100, 1, 1)
    v = again.verlauf()
    assert [e["art"] for e in v] == ["frage", "antwort"] and v[0]["betrag"] == -1 and v[1]["betrag"] == 1
    assert "100 Credits" in again.stand().text_de()


def test_never_below_zero_and_broken_file_is_not_overwritten(tmp_path):
    k = credits.Kontobuch(tmp_path)
    k.pfad.parent.mkdir(parents=True, exist_ok=True)
    k.pfad.write_text(json.dumps({"guthaben": 0, "verdient": 0, "ausgegeben": 100, "verlauf": [], "neustart": credits.NEUSTART}), encoding="utf-8")
    with pytest.raises(credits.CreditsError) as e:
        k.frage()
    assert e.value.code == "KEIN_GUTHABEN" and "Rechenkraft" in e.value.detail and "mitrechnen" not in e.value.detail
    assert k.antwort().guthaben == 1
    k.pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(credits.CreditsError) as e2:
        k.stand()
    assert e2.value.code == "CREDITS_DATEI" and k.pfad.read_text(encoding="utf-8") == "{kaputt"


def test_rule_text_is_plain_and_free_of_money():
    assert "100" in credits.REGEL_DE and "Geld" in credits.REGEL_DE and "Gerät" not in credits.REGEL_DE and "€" not in credits.REGEL_DE
