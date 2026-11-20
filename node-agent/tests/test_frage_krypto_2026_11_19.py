# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import abgleich_krypto as ak
import frage_krypto as fk
from abgleich_krypto import KryptoFehler

INHALT = {"nachrichten": [{"role": "user", "content": "Wie hoch ist der Großglockner?"}], "zone": 60}


def _helfer(n=3):
    return [ak.neues_geraet() for _ in range(n)]


def _verschliessen(helfer, **kw):
    return fk.frage_verschliessen(INHALT, {f"w{i}": ak.oeffentlich(h) for i, h in enumerate(helfer)}, **kw)


def _auftrag(v, kennung):
    p = v.paket
    return {"fassung": p["fassung"], "frage_id": p["frage_id"], "inhalt": p["inhalt"], "fach": p["faecher"][kennung]}


def test_every_recipient_opens_the_question_and_sees_the_same_text():
    helfer = _helfer()
    v = _verschliessen(helfer)
    for i, h in enumerate(helfer):
        g = fk.frage_oeffnen(_auftrag(v, f"w{i}"), h)
        assert g.inhalt["nachrichten"] == INHALT["nachrichten"]
        assert g.frage_id == v.frage_id and g.roh == v.roh


def test_the_server_part_holds_no_plaintext():
    v = _verschliessen(_helfer(2))
    assert "Großglockner" not in str(v.paket) and "nachrichten" not in str(v.paket)
    assert (len(ak.unb64(v.paket["inhalt"])) - 1 - 12 - 16) % fk.AUFFUELLEN == 0


def test_a_pc_without_its_own_compartment_cannot_open():
    a, b, fremd = _helfer(3)
    v = _verschliessen([a, b])
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(_auftrag(v, "w0"), fremd)
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(_auftrag(v, "w0"), b)


def test_a_compartment_is_bound_to_exactly_this_question():
    h = ak.neues_geraet()
    v1, v2 = _verschliessen([h]), _verschliessen([h])
    vertauscht = {**_auftrag(v1, "w0"), "fach": v2.paket["faecher"]["w0"]}
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(vertauscht, h)


def test_changed_content_or_changed_id_fails_loudly():
    h = ak.neues_geraet()
    v = _verschliessen([h])
    blob = bytearray(ak.unb64(v.paket["inhalt"]))
    blob[40] ^= 1
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen({**_auftrag(v, "w0"), "inhalt": ak.b64(bytes(blob))}, h)
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen({**_auftrag(v, "w0"), "frage_id": fk.frage_id_neu()}, h)


def test_an_old_question_or_one_from_the_future_is_not_opened():
    h = ak.neues_geraet()
    alt = _verschliessen([h], zeit=1_000_000)
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(_auftrag(alt, "w0"), h, jetzt=1_000_000 + fk.FRAGE_FRIST_S + 1)
    assert fk.frage_oeffnen(_auftrag(alt, "w0"), h, jetzt=1_000_000 + 5).frage_id == alt.frage_id
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(_auftrag(alt, "w0"), h, jetzt=1_000_000 - fk.ZUKUNFT_S - 1)


def test_the_helper_refuses_the_same_question_twice():
    g = fk.Gesehen()
    assert g.neu("a" * 32, jetzt=100)
    assert not g.neu("a" * 32, jetzt=200)
    assert g.neu("b" * 32, jetzt=200)
    assert g.neu("a" * 32, jetzt=100 + g._frist + 1)


def test_answers_round_trip_in_order_and_replays_are_refused():
    h, sig = ak.neues_geraet(), fk.neuer_unterschrift_schluessel()
    v = _verschliessen([h])
    kanal = fk.Kanal(fk.frage_oeffnen(_auftrag(v, "w0"), h))
    empfang = fk.Empfang(v)
    t1 = kanal.verschliessen("teil", {"text": "Der Großglockner"})
    s1 = kanal.verschliessen("schritt", {"text": "sucht im Wissen"})
    a = kanal.antwort("Der Großglockner ist 3798 m hoch.", {"quellen": "Wikipedia"}, sig)
    assert empfang.oeffnen(t1).daten["text"] == "Der Großglockner"
    assert empfang.oeffnen(s1).art == "schritt"
    offen = empfang.oeffnen(a)
    text, ls, ok = empfang.antwort_lesen(offen, ak.oeffentlich(sig))
    assert text.endswith("3798 m hoch.") and ls == {"quellen": "Wikipedia"} and ok
    with pytest.raises(KryptoFehler):
        empfang.oeffnen(t1)
    for nachricht in (t1, a):
        assert "Großglockner" not in str(nachricht)


def test_a_partial_answer_cannot_be_passed_off_as_the_final_one():
    h = ak.neues_geraet()
    v = _verschliessen([h])
    kanal = fk.Kanal(fk.frage_oeffnen(_auftrag(v, "w0"), h))
    t = kanal.verschliessen("teil", {"text": "Halb"})
    with pytest.raises(KryptoFehler):
        fk.Empfang(v).oeffnen({**t, "art": "antwort"})
    with pytest.raises(KryptoFehler):
        fk.Empfang(v).oeffnen({**t, "n": t["n"] + 5})


def test_a_message_for_another_question_does_not_open():
    h = ak.neues_geraet()
    v1, v2 = _verschliessen([h]), _verschliessen([h])
    t = fk.Kanal(fk.frage_oeffnen(_auftrag(v1, "w0"), h)).verschliessen("teil", {"text": "x"})
    with pytest.raises(KryptoFehler):
        fk.Empfang(v2).oeffnen(t)


def test_two_helpers_count_separately_when_a_question_is_hedged():
    a, b = _helfer(2)
    v = _verschliessen([a, b])
    ka, kb = (fk.Kanal(fk.frage_oeffnen(_auftrag(v, f"w{i}"), h)) for i, h in enumerate((a, b)))
    e = fk.Empfang(v)
    assert e.oeffnen(ka.verschliessen("teil", {"text": "a"})).daten["text"] == "a"
    assert e.oeffnen(kb.verschliessen("teil", {"text": "b"})).daten["text"] == "b"
    assert e.oeffnen(ka.verschliessen("teil", {"text": "a2"})).n == 2


def test_partial_answers_are_padded_to_fixed_steps():
    h = ak.neues_geraet()
    v = _verschliessen([h])
    kanal = fk.Kanal(fk.frage_oeffnen(_auftrag(v, "w0"), h))
    kurz = len(ak.unb64(kanal.verschliessen("teil", {"text": "a"})["ct"]))
    laenger = len(ak.unb64(kanal.verschliessen("teil", {"text": "a" * 300})["ct"]))
    assert kurz == laenger == fk.TEIL_STUFEN[0] + 16


def test_the_signature_binds_question_and_answer():
    h, sig, fremd = ak.neues_geraet(), fk.neuer_unterschrift_schluessel(), fk.neuer_unterschrift_schluessel()
    v = _verschliessen([h])
    g = fk.frage_oeffnen(_auftrag(v, "w0"), h)
    innen = b'{"text":"x"}'
    s = fk.unterschreiben(sig, g.frage_id, g.roh, innen)
    assert len(ak.unb64(s)) == 64
    assert fk.unterschrift_pruefen(ak.oeffentlich(sig), v.frage_id, v.roh, innen, s)
    assert not fk.unterschrift_pruefen(ak.oeffentlich(fremd), v.frage_id, v.roh, innen, s)
    assert not fk.unterschrift_pruefen(ak.oeffentlich(sig), v.frage_id, v.roh, b'{"text":"y"}', s)
    anders = _verschliessen([h])
    assert not fk.unterschrift_pruefen(ak.oeffentlich(sig), v.frage_id, anders.roh, innen, s)
    assert not fk.unterschrift_pruefen(ak.oeffentlich(sig), v.frage_id, v.roh, innen, "kaputt")


def test_a_wrong_signature_key_shows_as_not_ok():
    h, sig, fremd = ak.neues_geraet(), fk.neuer_unterschrift_schluessel(), fk.neuer_unterschrift_schluessel()
    v = _verschliessen([h])
    a = fk.Kanal(fk.frage_oeffnen(_auftrag(v, "w0"), h)).antwort("Text", {}, sig)
    e = fk.Empfang(v)
    _, _, ok = e.antwort_lesen(e.oeffnen(a), ak.oeffentlich(fremd))
    assert not ok


def test_index_passages_are_signed_by_the_server():
    s = fk.neuer_unterschrift_schluessel()
    sig = fk.abschnitt_unterschreiben(s, "wikipedia:Großglockner", "Der Großglockner ist 3798 m hoch.")
    assert fk.abschnitt_pruefen(ak.oeffentlich(s), "wikipedia:Großglockner", "Der Großglockner ist 3798 m hoch.", sig)
    assert not fk.abschnitt_pruefen(ak.oeffentlich(s), "wikipedia:Großglockner", "Der Großglockner ist 4000 m hoch.", sig)
    assert not fk.abschnitt_pruefen(ak.oeffentlich(s), "erfunden", "Der Großglockner ist 3798 m hoch.", sig)


def test_a_key_change_keeps_the_old_key_for_a_short_grace():
    sch = fk.Schluessel(ak.neues_geraet(), fk.neuer_unterschrift_schluessel())
    alt = sch.antwort
    v = _verschliessen([alt])
    sch.wechseln(jetzt=1000, gnade_s=60)
    assert fk.frage_oeffnen(_auftrag(v, "w0"), sch.kandidaten(jetzt=1030)).frage_id == v.frage_id
    with pytest.raises(KryptoFehler):
        fk.frage_oeffnen(_auftrag(v, "w0"), sch.kandidaten(jetzt=1061))


def test_limits_on_recipients_and_length():
    with pytest.raises(KryptoFehler):
        fk.frage_verschliessen(INHALT, {})
    with pytest.raises(KryptoFehler):
        fk.frage_verschliessen(INHALT, {f"w{i}": ak.oeffentlich(ak.neues_geraet()) for i in range(fk.MAX_EMPFAENGER + 1)})
    with pytest.raises(KryptoFehler):
        fk.frage_verschliessen({"nachrichten": [{"role": "user", "content": "x" * (fk.MAX_INHALT + 1)}]}, {"w": ak.oeffentlich(ak.neues_geraet())})
    with pytest.raises(KryptoFehler):
        fk.frage_verschliessen(INHALT, {"w": {"art": "p256", "punkt": ak.b64(b"\x04" + b"\x00" * 64)}})


def test_the_sync_compartment_still_uses_its_old_defaults():
    g = ak.neues_geraet()
    k = ak.neuer_kontoschluessel()
    fach = ak.fach_packen(k, ak.oeffentlich(g))
    assert ak.fach_oeffnen(fach, g) == k
    with pytest.raises(KryptoFehler):
        ak.fach_oeffnen(fach, g, info=fk.FRAGE_INFO)


def _pc(wurzel, *, jetzt=1_000_000, tage=fk.BEGLAUBIGUNG_TAGE):
    sch = fk.Schluessel(ak.neues_geraet(), fk.neuer_unterschrift_schluessel(), seit=jetzt)
    e = {"kennung": "w0", **sch.oeffentlich()}
    e["beglaubigung"] = fk.beglaubigen(wurzel, e["unterschrift"], jetzt + tage * 86400)
    return sch, e


def test_a_fully_certified_helper_is_accepted():
    wurzel = fk.neuer_unterschrift_schluessel()
    sch, e = _pc(wurzel)
    pub = fk.empfaenger_pruefen(e, ak.oeffentlich(wurzel), jetzt=1_000_100)
    assert pub == ak.oeffentlich(sch.antwort)


def test_a_key_slipped_in_by_the_server_is_refused():
    wurzel = fk.neuer_unterschrift_schluessel()
    _, e = _pc(wurzel)
    fremd = ak.oeffentlich(ak.neues_geraet())
    assert fk.empfaenger_pruefen({**e, "antwort": fremd}, ak.oeffentlich(wurzel), jetzt=1_000_100) is None
    falsche_wurzel = fk.neuer_unterschrift_schluessel()
    _, e2 = _pc(falsche_wurzel)
    assert fk.empfaenger_pruefen(e2, ak.oeffentlich(wurzel), jetzt=1_000_100) is None


def test_expired_certificates_and_blocked_pcs_are_refused():
    wurzel = fk.neuer_unterschrift_schluessel()
    sch, e = _pc(wurzel, tage=1)
    assert fk.empfaenger_pruefen(e, ak.oeffentlich(wurzel), jetzt=1_000_000 + 2 * 86400) is None
    _, e = _pc(wurzel)
    assert fk.empfaenger_pruefen(e, ak.oeffentlich(wurzel), jetzt=1_000_000 + 3 * 86400) is None
    gesperrt = {fk.schluessel_kennung(e["unterschrift"])}
    assert fk.empfaenger_pruefen(e, ak.oeffentlich(wurzel), jetzt=1_000_100, gesperrt=gesperrt) is None
    assert fk.empfaenger_pruefen(e, None, jetzt=1_000_100) is None


def test_the_block_list_is_signed_and_cannot_be_edited():
    wurzel = fk.neuer_unterschrift_schluessel()
    liste = fk.sperrliste_unterschreiben(wurzel, 1_000_000, ["b" * 64, "a" * 64])
    assert liste["gesperrt"] == ["a" * 64, "b" * 64]
    assert fk.sperrliste_pruefen(ak.oeffentlich(wurzel), liste)
    assert not fk.sperrliste_pruefen(ak.oeffentlich(wurzel), {**liste, "gesperrt": ["a" * 64]})
    assert not fk.sperrliste_pruefen(ak.oeffentlich(wurzel), {**liste, "stand": 2_000_000})
    assert not fk.sperrliste_pruefen(ak.oeffentlich(fk.neuer_unterschrift_schluessel()), liste)


def test_without_the_public_certification_file_nothing_is_trusted(tmp_path):
    assert fk.beglaubigung_laden(tmp_path) is None
    w = ak.oeffentlich(fk.neuer_unterschrift_schluessel())
    (tmp_path / fk.BEGLAUBIGUNG_DATEI).write_text('{"art": "p256", "punkt": "%s"}' % w["punkt"], encoding="utf-8")
    assert fk.beglaubigung_laden(tmp_path) == [w]


def test_the_certification_key_can_be_replaced_without_a_one_way_street(tmp_path):
    alt, neu = fk.neuer_unterschrift_schluessel(), fk.neuer_unterschrift_schluessel()
    import json as _json
    (tmp_path / fk.BEGLAUBIGUNG_DATEI).write_text(_json.dumps({"fassung": 1, "schluessel": [ak.oeffentlich(alt), ak.oeffentlich(neu)]}),
                                                  encoding="utf-8")
    beide = fk.beglaubigung_laden(tmp_path)
    _, e_alt = _pc(alt)
    _, e_neu = _pc(neu)
    assert fk.empfaenger_pruefen(e_alt, beide, jetzt=1_000_100) and fk.empfaenger_pruefen(e_neu, beide, jetzt=1_000_100)
    nur_neu = [ak.oeffentlich(neu)]
    assert fk.empfaenger_pruefen(e_alt, nur_neu, jetzt=1_000_100) is None
    assert fk.empfaenger_pruefen(e_neu, nur_neu, jetzt=1_000_100) is not None
    liste = fk.sperrliste_unterschreiben(neu, 5, [])
    assert fk.sperrliste_pruefen(beide, liste) and not fk.sperrliste_pruefen([ak.oeffentlich(alt)], liste)


def test_the_ai_label_needs_the_helpers_own_confirmation():
    h, sig, fremd = ak.neues_geraet(), fk.neuer_unterschrift_schluessel(), fk.neuer_unterschrift_schluessel()
    v = _verschliessen([h])
    e = fk.Empfang(v)
    offen = e.oeffnen(fk.Kanal(fk.frage_oeffnen(_auftrag(v, "w0"), h)).antwort("Der Text.", {}, sig))
    ps = fk.text_pruefsumme("Der Text.")
    assert fk.etikett_pruefen(ak.oeffentlich(sig), v.frage_id, ps, offen.daten["etikett_sig"])
    assert not fk.etikett_pruefen(ak.oeffentlich(sig), v.frage_id, fk.text_pruefsumme("Ein anderer Text."), offen.daten["etikett_sig"])
    assert not fk.etikett_pruefen(ak.oeffentlich(fremd), v.frage_id, ps, offen.daten["etikett_sig"])
    assert not fk.etikett_pruefen(ak.oeffentlich(sig), fk.frage_id_neu(), ps, offen.daten["etikett_sig"])


def test_an_older_block_list_never_replaces_a_newer_one():
    wurzel = fk.neuer_unterschrift_schluessel()
    w = ak.oeffentlich(wurzel)
    s = fk.Sperrstand(w)
    assert s.nehmen(fk.sperrliste_unterschreiben(wurzel, 200, ["a" * 64]))
    assert not s.nehmen(fk.sperrliste_unterschreiben(wurzel, 100, []))
    assert s.gesperrt == {"a" * 64}
    assert not s.nehmen(fk.sperrliste_unterschreiben(fk.neuer_unterschrift_schluessel(), 300, []))
    assert s.nehmen(fk.sperrliste_unterschreiben(wurzel, 300, ["a" * 64, "b" * 64]))
    assert fk.Sperrstand(w, s.liste).gesperrt == {"a" * 64, "b" * 64}
    assert fk.Sperrstand(w, {**s.liste, "gesperrt": []}).gesperrt == frozenset()


def test_the_label_checksum_is_the_same_as_the_servers():
    import herkunft
    for t in ("Der Text.", "  Der   Text.\n", "Café"):
        assert fk.text_pruefsumme(t) == herkunft.pruefsumme(t)


def test_a_late_step_line_never_turns_the_final_answer_into_an_old_one():
    import abgleich_krypto as ak
    import frage_krypto as fk
    h = ak.neues_geraet()
    v = fk.frage_verschliessen({"nachrichten": [{"role": "user", "content": "Wie hoch ist der Großglockner?"}]}, {"w": ak.oeffentlich(h)})
    g = fk.frage_oeffnen({**{k: v.paket[k] for k in ("fassung", "frage_id", "inhalt")}, "fach": v.paket["faecher"]["w"]}, h)
    k = fk.Kanal(g)
    ende = k.antwort("3798 m.", {}, fk.neuer_unterschrift_schluessel())
    spaet = k.verschliessen("schritt", {"text": "fertig"})
    e = fk.Empfang(v)
    assert e.oeffnen(spaet).daten["text"] == "fertig"
    assert e.ist_neu(ende) and e.oeffnen(ende).art == "antwort"
    with pytest.raises(fk.KryptoFehler):
        e.oeffnen(ende)
