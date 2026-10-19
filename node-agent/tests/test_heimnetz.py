# SPDX-License-Identifier: AGPL-3.0-or-later
import socket
import time

import app_core
import app_install
import app_web
import heimnetz as hn
import ki_laufzeit as kl

from test_app_web import _api


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Antwort:
    def __init__(self, text, p=12, c=3, d=0.2):
        self.text, self.prompt_tokens, self.completion_tokens, self.dauer_s = text, p, c, d


def _dienst(tmp_path, frage_fn=None, **kw):
    def standard(n, on_token):
        for s in ("Hallo", " Welt", "."):
            on_token(s)
        return _Antwort("Hallo Welt.")
    d = hn.Dienst(tmp_path / "pc", frage_fn=frage_fn or standard, name="PC-Test", adresse="127.0.0.1", port=_port(), loopback_erlaubt=True, **kw)
    d.start()
    return d


def test_pairing_with_code_pinned_certificate_streamed_answer_and_removal(tmp_path):
    d = _dienst(tmp_path)
    try:
        v = hn.Verbindung(tmp_path / "laptop", geraet_name_eigen="Laptop-Test", loopback_erlaubt=True)
        assert v.daten() is None
        try:
            v.koppeln("127.0.0.1", "AAAA-AAAA", port=d.port)
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert exc.code == "HEIMNETZ_KOPPELN" and "kein Kopplungscode" in exc.detail
        code = d.koppeln_oeffnen()
        assert len(code) == 9 and code[4] == "-" and d.zustand()["kopplung"]["code"] == code
        try:
            v.koppeln("127.0.0.1", "aaaa-aaaa", port=d.port)
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert "stimmt nicht" in exc.detail and d.kopplung.fehlversuche == 1
        daten = v.koppeln("127.0.0.1", code.lower().replace("-", " "), port=d.port)
        assert daten.name == "PC-Test" and daten.fingerprint == d.fingerprint and "BEGIN CERTIFICATE" in daten.zertifikat_pem
        assert d.kopplung is None
        assert v.daten().host == "127.0.0.1"
        raw = (tmp_path / "laptop" / hn.DIRNAME / "verbindung.json").read_text(encoding="utf-8")
        assert any(f'"token": "{p}:' in raw for p in ("dpapi", "bund", "datei"))
        assert v.hallo()["name"] == "PC-Test"
        got = []
        a = v.frage([{"role": "user", "content": "hi"}], on_token=got.append)
        assert a.text == "Hallo Welt." and got == ["Hallo", " Welt", "."] and a.geraet == "PC-Test" and a.completion_tokens == 3
        liste = d.geraete.liste()
        assert liste[0]["name"] == "Laptop-Test" and liste[0]["fragen"] == 1 and liste[0]["zuletzt"]
        assert d.geraete.entfernen("Laptop-Test") and not d.geraete.entfernen("Laptop-Test")
        try:
            v.frage([{"role": "user", "content": "hi"}])
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert "nicht (mehr) gekoppelt" in exc.detail
        assert v.trennen() and v.daten() is None
    finally:
        d.stop()
    assert not d.laeuft()


def test_five_wrong_codes_close_the_pairing_and_an_expired_code_is_dead(tmp_path):
    d = _dienst(tmp_path)
    try:
        v = hn.Verbindung(tmp_path / "laptop", geraet_name_eigen="L", loopback_erlaubt=True)
        d.koppeln_oeffnen()
        for _ in range(hn.CODE_FEHLVERSUCHE):
            try:
                v.koppeln("127.0.0.1", "BBBB-BBBB", port=d.port)
            except hn.HeimnetzError:
                pass
        assert d.zustand()["kopplung"] is None
        try:
            v.koppeln("127.0.0.1", d.kopplung.code, port=d.port)
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert "kein Kopplungscode" in exc.detail
        code = d.koppeln_oeffnen()
        d.kopplung.bis = time.time() - 1
        try:
            v.koppeln("127.0.0.1", code, port=d.port)
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert "kein Kopplungscode" in exc.detail
    finally:
        d.stop()


def test_changed_certificate_is_refused_and_errors_from_the_model_arrive_as_a_sentence(tmp_path):
    def kaputt(n, on_token):
        on_token("Ha")
        raise app_core.AppError("KI_AUS", "KIplatz ist auf diesem Gerät gerade ausgeschaltet")
    d = _dienst(tmp_path, kaputt)
    v = hn.Verbindung(tmp_path / "laptop", geraet_name_eigen="L", loopback_erlaubt=True)
    try:
        v.koppeln("127.0.0.1", d.koppeln_oeffnen(), port=d.port)
        try:
            v.frage([{"role": "user", "content": "hi"}])
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert exc.code == "HEIMNETZ_KI_AUS" and "ausgeschaltet" in exc.detail
        port = d.port
    finally:
        d.stop()
    for p in (d.cert_pfad, d.key_pfad):
        p.unlink()
    d2 = hn.Dienst(tmp_path / "pc", frage_fn=kaputt, name="PC-Test", adresse="127.0.0.1", port=port, loopback_erlaubt=True)
    d2.start()
    try:
        try:
            v.hallo()
            raise AssertionError
        except hn.HeimnetzError as exc:
            assert exc.code in ("HEIMNETZ_ZERTIFIKAT", "HEIMNETZ_UNERREICHBAR")
    finally:
        d2.stop()


def test_only_home_network_addresses_and_no_wildcard_bind(tmp_path):
    assert hn.ist_heimnetz("192.168.1.5") and hn.ist_heimnetz("10.0.0.1") and hn.ist_heimnetz("fe80::1%12")
    assert not hn.ist_heimnetz("8.8.8.8") and not hn.ist_heimnetz("127.0.0.1") and hn.ist_heimnetz("127.0.0.1", loopback_erlaubt=True)
    assert not hn.ist_heimnetz("0.0.0.0") and not hn.ist_heimnetz("kein")
    d = hn.Dienst(tmp_path / "pc", frage_fn=lambda n, t: None, name="PC", adresse="0.0.0.0", port=_port(), loopback_erlaubt=True)
    try:
        d.start()
        raise AssertionError
    except hn.HeimnetzError as exc:
        assert exc.code == "HEIMNETZ_ADRESSE"
    d = hn.Dienst(tmp_path / "pc", frage_fn=lambda n, t: None, name="PC", adresse="127.0.0.1", port=_port())
    try:
        d.start()
        raise AssertionError
    except hn.HeimnetzError as exc:
        assert exc.code == "HEIMNETZ_ADRESSE"
    cert, key = hn.zertifikat_erzeugen("PC-X", ["192.168.1.7", "kaputt"])
    assert b"BEGIN CERTIFICATE" in cert and b"PRIVATE KEY" in key


def test_two_windows_pc_offers_laptop_asks_credits_on_both_sides(tmp_path):
    pc, pc_fake, _ = _api(tmp_path / "pc")
    pc._dienst = hn.Dienst(pc._core.base_dir, frage_fn=pc._dienst_frage, name="PC-Test", kontobuch=pc._kontobuch, adresse="127.0.0.1", port=_port(), loopback_erlaubt=True, ki_beschreibung=pc._ki.ki_beschreibung)
    r = pc.heimnetz_anbieten(True)
    assert r["ok"] and r["daten"]["laeuft"] and pc._ki.einstellung()["anbieten"] is True
    pc._ki._thread.join(timeout=10)
    assert pc._ki.server.laeuft()
    code = pc.heimnetz_koppeln_oeffnen()["daten"]["kopplung"]["code"]
    lp, lp_fake, _ = _api(tmp_path / "laptop")
    lp._ki.verbindung = hn.Verbindung(lp._core.base_dir, geraet_name_eigen="Laptop-Test", loopback_erlaubt=True)
    try:
        assert not lp.heimnetz_verbinden(f"127.0.0.1:{pc._dienst.port}", "ZZZZ-ZZZZ")["ok"]
        r = lp.heimnetz_verbinden(f"127.0.0.1:{pc._dienst.port}", code)
        assert r["ok"], r["text"]
        assert lp._ki.quelle() == "heimnetz" and lp.zustand()["daten"]["ki"]["fern_name"] == "PC-Test"
        assert not lp.frage("x", "hallo")["ok"]
        assert lp.ki_einschalten()["ok"]
        lp._ki._thread.join(timeout=10)
        z = lp.ki_zustand()["daten"]
        assert z["phase"] == "bereit" and z["laeuft"] and z["geraet"] == "PC-Test im Heimnetz" and z["modell"] is None
        assert not lp_fake.laeuft()
        g = lp.gespraech_neu()["daten"]
        pieces = []
        lp._window = type("W", (), {"evaluate_js": staticmethod(lambda code: pieces.append(code))})()
        a = lp.frage(g["kennung"], "Wie heißt du?")
        assert a["ok"], a["text"]
        pieces = [x for x in pieces if not x.startswith("app.schritt(")]
        assert a["daten"]["text"] == "Servus, Huber." and len(pieces) == 3
        ls = a["daten"]["lieferschein"]
        assert ls["geraet"] == "PC-Test im Heimnetz" and ls["modell"] == "KIplatz" and "PC-Test hat 1 verdient" in ls["credits"]
        assert lp._kontobuch.stand().guthaben == 99 and pc._kontobuch.stand().guthaben == 101 and pc._kontobuch.stand().verdient == 1
        assert pc_fake.fragen[-1][-1]["content"] == "Wie heißt du?"
        c = pc.community()["daten"]
        assert [m["name"] for m in c["mitglieder"]] == ["Laptop-Test", "Laptop-Test"] or c["mitglieder"][1]["name"] == "Laptop-Test"
        assert "fragt KIplatz hier (1 Fragen)" in c["mitglieder"][1]["rolle"]
        assert lp.community()["daten"]["mitglieder"][1]["rolle"] == "beantwortet deine Fragen im Heimnetz"
        assert not pc.ki_quelle("heimnetz")["ok"]
        assert not lp.heimnetz_anbieten(True)["ok"]
        assert lp.ki_quelle("lokal")["ok"] and lp._ki.quelle() == "lokal"
        assert lp.heimnetz_trennen()["ok"] and lp._ki.verbindung.daten() is None
        assert pc.heimnetz_geraet_entfernen("Laptop-Test")["ok"] and not pc.heimnetz_geraet_entfernen("Laptop-Test")["ok"]
        assert pc.heimnetz_anbieten(False)["ok"] and not pc._dienst.laeuft() and pc._ki.einstellung()["anbieten"] is False
    finally:
        pc._dienst.stop()


def test_surface_has_the_home_network_card():
    html = (app_web.webapp_dir() / app_web.INDEX_NAME).read_text(encoding="utf-8")
    for needle in ("KIplatz im Heimnetz", "Im Heimnetz anbieten", "PC im Heimnetz koppeln", "Nicht fürs Handy", "btn-hn-verbinden", "Wer beantwortet deine Fragen?", "heimnetz_verbinden", "ki_quelle"):
        assert needle in html


def test_a_silent_connection_does_not_block_the_service_or_its_stop(tmp_path):
    d = _dienst(tmp_path)
    stumm = socket.create_connection(("127.0.0.1", d.port))
    try:
        time.sleep(0.3)
        v = hn.Verbindung(tmp_path / "laptop", geraet_name_eigen="L", loopback_erlaubt=True)
        code = d.koppeln_oeffnen()
        t0 = time.monotonic()
        v.koppeln("127.0.0.1", code, port=d.port)
        assert time.monotonic() - t0 < 5
        t0 = time.monotonic()
        d.stop()
        assert time.monotonic() - t0 < 3
    finally:
        stumm.close()
        d.stop()


def test_b_the_proof_seen_by_someone_in_between_costs_scrypt_per_guess_and_old_versions_get_a_clear_sentence(tmp_path):
    t0 = time.monotonic()
    hn._beweis("ABCDEFGH", "geraet", "0" * 32, "f" * 64, "L")
    assert time.monotonic() - t0 > 0.005
    assert hn.KOPPEL_SCRYPT["n"] >= 2 ** 14
    d = _dienst(tmp_path)
    try:
        d.koppeln_oeffnen()
        status, antwort = d._koppeln({"geraet": "L", "nonce": "0" * 32, "beweis": "x"})
        assert status == 403 and "aktualisieren" in antwort["text"]
    finally:
        d.stop()


def test_c_a_question_finishing_after_removal_does_not_bring_the_device_back(tmp_path):
    import threading
    liste = hn.Geraeteliste(tmp_path)
    liste.hinzufuegen("Laptop", "a" * 64)
    gelesen, weiter = threading.Event(), threading.Event()
    laden = liste._laden

    def langsam():
        d = laden()
        if threading.current_thread().name == "frage":
            gelesen.set()
            weiter.wait(2)
        return d
    liste._laden = langsam
    t = threading.Thread(target=liste.gefragt, args=("Laptop",), name="frage")
    t.start()
    gelesen.wait(2)
    r = threading.Thread(target=liste.entfernen, args=("Laptop",))
    r.start()
    time.sleep(0.2)
    weiter.set()
    t.join(3)
    r.join(3)
    assert liste.liste() == [] and liste.pruefen("a" * 64) is None


def test_d_a_paired_device_cannot_make_the_pc_read_pages_in_its_own_network(tmp_path, monkeypatch):
    import wissen
    for adresse in ("https://192.168.1.1/", "https://localhost/", "https://router.local/", "https://10.0.0.138/admin"):
        try:
            wissen.nur_oeffentlich(adresse)
            raise AssertionError(adresse)
        except wissen.WissenError:
            pass
    ki = app_web.Api.__new__(app_web.Api)
    gelesen = []
    monkeypatch.setattr(wissen, "seite_holen", lambda *a, **k: gelesen.append(a) or ("x", "x", "x"))
    try:
        ki._wissen_auftrag({"was": "seite", "adresse": "https://192.168.1.1/"})
        raise AssertionError
    except wissen.WissenError:
        pass
    assert gelesen == []


def test_ein_entferntes_geraet_hoert_nicht_gekoppelt_auch_bei_einer_langen_frage(tmp_path):
    d = _dienst(tmp_path)
    try:
        v = hn.Verbindung(tmp_path / "laptop", geraet_name_eigen="Laptop-Test", loopback_erlaubt=True)
        v.koppeln("127.0.0.1", d.koppeln_oeffnen(), port=d.port)
        assert d.geraete.entfernen("Laptop-Test")
        lang = [{"role": "user", "content": "x" * 19000}] * 13
        for _ in range(5):
            try:
                v.frage(lang)
                raise AssertionError
            except hn.HeimnetzError as exc:
                assert "nicht (mehr) gekoppelt" in exc.detail, exc.detail
    finally:
        d.stop()
