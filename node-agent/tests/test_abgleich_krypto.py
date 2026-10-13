# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import abgleich_krypto as ak
import abgleich_vektoren_erzeugen as vektor

GESPRAECH = {"id": "a" * 32, "titel": "Steuer", "nachrichten": [{"rolle": "user", "text": "Wie hoch ist die Pendlerpauschale?", "zeit": 1}]}


def test_the_shared_examples_file_matches_this_code():
    datei = json.loads(vektor.ZIEL.read_text(encoding="utf-8"))
    assert datei == json.loads(json.dumps(vektor.vektoren(), ensure_ascii=False))


def test_a_block_round_trips_and_hides_its_length():
    k = ak.neuer_kontoschluessel()
    b = ak.block_verschluesseln(k, "a" * 32, GESPRAECH)
    assert "Pendler" not in b and ak.block_entschluesseln(k, "a" * 32, b) == GESPRAECH
    assert (len(ak.unb64(b)) - 1 - 12 - 16) % ak.AUFFUELLEN == 0
    assert ak.block_verschluesseln(k, "a" * 32, GESPRAECH) != b


def test_a_block_does_not_open_with_another_key_another_id_or_after_tampering():
    k = ak.neuer_kontoschluessel()
    b = ak.block_verschluesseln(k, "a" * 32, GESPRAECH)
    with pytest.raises(ak.KryptoFehler):
        ak.block_entschluesseln(ak.neuer_kontoschluessel(), "a" * 32, b)
    with pytest.raises(ak.KryptoFehler):
        ak.block_entschluesseln(k, "b" * 32, b)
    roh = bytearray(ak.unb64(b)); roh[40] ^= 1
    with pytest.raises(ak.KryptoFehler):
        ak.block_entschluesseln(k, "a" * 32, ak.b64(bytes(roh)))


def test_only_the_device_it_was_packed_for_opens_a_compartment():
    k, ich, fremd = ak.neuer_kontoschluessel(), ak.neues_geraet(), ak.neues_geraet()
    fach = ak.fach_packen(k, ak.oeffentlich(ich))
    assert ak.fach_oeffnen(fach, ich) == k
    with pytest.raises(ak.KryptoFehler):
        ak.fach_oeffnen(fach, fremd)
    assert ak.fach_oeffnen(fach, ak.privat_laden(ak.privat_speichern(ich))) == k


def test_the_check_number_changes_with_the_key_so_the_server_cannot_swap_it():
    a, b = ak.neues_geraet(), ak.neues_geraet()
    pa = ak.pruefzahl(ak.oeffentlich(a))
    assert len(pa) == 7 and pa[3] == " " and pa == ak.pruefzahl(ak.oeffentlich(a))
    assert pa != ak.pruefzahl(ak.oeffentlich(b))


def test_the_recovery_key_is_readable_and_forgiving():
    k = ak.neuer_kontoschluessel()
    r = ak.neuer_wiederherstellungsschluessel()
    assert len(r) == 29 and r.count("-") == 5
    fach = ak.wiederherstellung_packen(k, r)
    assert ak.wiederherstellung_oeffnen(fach, r.lower().replace("-", " ")) == k
    assert ak.wiederherstellung_oeffnen(fach, r.replace("0", "O").replace("1", "l")) == k
    with pytest.raises(ak.KryptoFehler):
        ak.wiederherstellung_oeffnen(fach, ak.neuer_wiederherstellungsschluessel())
    with pytest.raises(ak.KryptoFehler):
        ak.wiederherstellung_lesen("zu kurz")


def test_the_seal_binds_a_device_key_to_its_kennung_and_the_account_key():
    k, g = ak.neuer_kontoschluessel(), ak.oeffentlich(ak.neues_geraet())
    s = ak.siegel(k, "abc", g)
    assert ak.siegel_pruefen(k, "abc", g, s)
    assert not ak.siegel_pruefen(ak.neuer_kontoschluessel(), "abc", g, s)
    assert not ak.siegel_pruefen(k, "abd", g, s)
    assert not ak.siegel_pruefen(k, "abc", ak.oeffentlich(ak.neues_geraet()), s)
