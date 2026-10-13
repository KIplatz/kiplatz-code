# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import json
import socket

import urllib.error
import pytest
from pathlib import Path

import app_core
import heimnetz as hn
import wissen as w

from test_app_web import _api


class _Antwort:
    def __init__(self, url, body, art="text/html; charset=utf-8"):
        self.url = url
        self.headers = {"Content-Type": art}
        self._b = io.BytesIO(body)

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


SEITE = b"""<html><head><title>Beispiel-Seite: KI einfach erkl\xc3\xa4rt</title><style>p{}</style><script>var x=1;</script></head>
<body><nav>Men\xc3\xbc Start News</nav><h1>KI im Alltag</h1><p>Auf beispiel.at stehen Anleitungen, wie man KI im Alltag nutzt: Werkzeuge, Vergleiche und t\xc3\xa4gliche News.</p>
<p>Die Seite geh\xc3\xb6rt zu einem Betrieb in Ober\xc3\xb6sterreich und pr\xc3\xbcft KI-Detektoren im Vergleich.</p><footer>Impressum</footer></body></html>"""


def _oeffner(req, timeout=0):
    url = req.full_url
    if "gross" in url:
        return _Antwort(url, b"x" * (w.MAX_SEITE + 5))
    if "bild" in url:
        return _Antwort(url, b"\x89PNG", "image/png")
    if "http-um" in url:
        return _Antwort("http://unsicher.example/", SEITE)
    return _Antwort(url, SEITE)


def test_words_passages_and_html_to_text():
    assert w.woerter("Die Rechner und Rechnern der Community! Übermorgen") == ["rech", "rech", "community", "uebermorg"]
    assert w.woerter("beispiel.at") == ["beispiel"]
    teile = w.abschnitte("Erster Satz. " * 80 + "\n\nZweiter Absatz. " * 5)
    assert len(teile) >= 2 and all(len(t) <= w.ABSCHNITT_ZEICHEN + 20 for t in teile)
    titel, text = w.html_zu_text(SEITE.decode("utf-8"))
    assert titel == "Beispiel-Seite: KI einfach erklärt" and "Menü" not in text and "var x" not in text and "Impressum" not in text and "beispiel.at stehen Anleitungen" in text


def test_store_reads_only_named_pages_and_refuses_the_wrong_ones(tmp_path):
    s = w.Wissensspeicher(tmp_path)
    q = s.seite_lesen("beispiel.at", oeffner=_oeffner)
    assert q.art == "seite" and q.adresse == "https://beispiel.at" and q.titel.startswith("Beispiel-Seite") and s.anzahl() == 1
    assert s.seite_lesen("https://beispiel.at", oeffner=_oeffner).kennung == q.kennung
    for adresse, code in (("http://beispiel.at", "WISSEN_ADRESSE"), ("https://x.at/gross", "WISSEN_GROSS"), ("https://x.at/bild", "WISSEN_ART"),
                          ("https://x.at/http-um", "WISSEN_ADRESSE"), ("https://x.at/a b", "WISSEN_ADRESSE")):
        try:
            s.seite_lesen(adresse, oeffner=_oeffner)
            raise AssertionError(adresse)
        except w.WissenError as exc:
            assert exc.code == code, (adresse, exc.code)
    assert s.anzahl() == 1
    assert s.entfernen(q.kennung) and not s.entfernen(q.kennung) and s.anzahl() == 0


def test_folder_reading_takes_only_text_files_of_that_folder(tmp_path):
    ordner = tmp_path / "docs"
    (ordner / "unter").mkdir(parents=True)
    (ordner / "regeln.md").write_text("# Regeln\n\nNie Zugangsdaten in Dateien schreiben. Server nur mit Schlüssel.", encoding="utf-8")
    (ordner / "unter" / "notiz.txt").write_text("Der Stand-PC hat eine Radeon RX 7800 XT mit 16 GB Grafikspeicher und rechnet für die Community.", encoding="utf-8")
    (ordner / "seite.html").write_bytes(SEITE)
    (ordner / "bild.png").write_bytes(b"\x89PNG")
    (ordner / "riesig.txt").write_text("x" * (w.MAX_DATEI + 1), encoding="utf-8")
    (ordner / "leer.txt").write_text("kurz", encoding="utf-8")
    s = w.Wissensspeicher(tmp_path)
    gelesen = s.ordner_lesen(ordner)
    assert sorted(q.titel for q in gelesen) == ["Beispiel-Seite: KI einfach erklärt", "notiz.txt", "regeln.md"]
    assert all(q.art == "dokument" for q in gelesen)
    try:
        s.ordner_lesen(tmp_path / "gibtsnicht")
        raise AssertionError
    except w.WissenError as exc:
        assert exc.code == "WISSEN_ORDNER"
    tr = s.suchen("Welche Grafikkarte hat der Stand-PC?")
    assert tr and tr[0].quelle.titel == "notiz.txt" and "7800" in tr[0].text
    zusatz, quellen = s.kontext("Was steht auf beispiel.at?")
    assert zusatz.startswith("Auszüge aus dem Wissensspeicher") and quellen[0]["nummer"] == 1 and "Quelle 1:" in zusatz
    assert s.suchen("") == [] and s.kontext("und oder") == ("", [])
    assert w.benutzte_quellen("Das steht so drin (Quelle 2).", quellen) == [q for q in quellen if q["nummer"] == 2]
    drei = [{"nummer": n, "titel": "news.ORF.at", "adresse": "https://orf.at", "datum": "2026-09-17T07:46:54Z"} for n in (2, 3, 4)]
    assert [q["nummer"] for q in w.benutzte_quellen("A (Quelle 2). B (Quelle 3). C (Quelle 4).", drei)] == [2]
    assert w.quellen_text_de("A (Quelle 2). B (Quelle 3). C (Quelle 4).", drei, 5) == "news.ORF.at (https://orf.at), gelesen 2026-09-17"
    assert "passte nichts" in w.quellen_text_de("x", [], 3) and "noch leer" in w.quellen_text_de("x", [], 0)
    assert "nicht benutzt" in w.quellen_text_de("ohne Verweis", quellen, 3)
    assert w.quellen_text_de("(Quelle 1)", quellen, 3).startswith("Beispiel-Seite")


def test_answer_carries_its_sources_locally(tmp_path, monkeypatch):
    monkeypatch.setattr(w.urllib.request, "urlopen", _oeffner)
    api, fake, _ = _api(tmp_path)
    api._wissen.seite_lesen("beispiel.at", oeffner=_oeffner)
    api.ki_einschalten()
    api._ki._thread.join(timeout=10)
    g = api.gespraech_neu()["daten"]
    fake_frage = fake.frage

    def frage(nachrichten, *, on_token=None, zusatz="", **kw):
        fake.zusatz = zusatz
        a = fake_frage(nachrichten, on_token=on_token)
        return type(a)("Anleitungen für KI im Alltag (Quelle 1).", a.prompt_tokens, a.completion_tokens, a.dauer_s)
    fake.frage = frage
    r = api.frage(g["kennung"], "Was steht auf beispiel.at?")
    assert r["ok"], r["text"]
    assert "Quelle 1:" in fake.zusatz and "beispiel.at stehen Anleitungen" in fake.zusatz
    ls = r["daten"]["lieferschein"]
    assert ls["quellen"].startswith("Beispiel-Seite") and "https://beispiel.at" in ls["quellen"] and ls["quellen_liste"][0]["nummer"] == 1
    r2 = api.frage(g["kennung"], "Wie heißt die Hauptstadt von Frankreich?")
    assert fake.zusatz.startswith("Heute ist ") and "Quelle" not in fake.zusatz and "passte nichts" in r2["daten"]["lieferschein"]["quellen"]
    z = api.wissen_zustand()["daten"]
    assert z["anzahl"] == 2 and "privat nur auf diesem PC" in z["wo"] and {q["art"] for q in z["quellen"]} == {"seite", "nachgeschaut"} and not any(q["privat"] for q in z["quellen"])
    assert not api.wissen_ordner_lesen(str(tmp_path / "leer"))["ok"]
    assert all(api.wissen_entfernen(q["kennung"])["ok"] for q in z["quellen"]) and api.wissen_zustand()["daten"]["anzahl"] == 0


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_in_the_home_network_the_answering_device_holds_the_store(tmp_path, monkeypatch):
    monkeypatch.setattr(w.urllib.request, "urlopen", _oeffner)
    pc, pc_fake, _ = _api(tmp_path / "pc")
    pc._dienst = hn.Dienst(pc._core.base_dir, frage_fn=pc._dienst_frage, name="PC-Test", kontobuch=pc._kontobuch, adresse="127.0.0.1", port=_port(), loopback_erlaubt=True,
                           ki_beschreibung=pc._ki.ki_beschreibung, wissen_fn=pc._wissen_auftrag)
    assert pc.heimnetz_anbieten(True)["ok"]
    pc._ki._thread.join(timeout=10)
    code = pc.heimnetz_koppeln_oeffnen()["daten"]["kopplung"]["code"]
    lp, lp_fake, _ = _api(tmp_path / "laptop")
    lp._ki.verbindung = hn.Verbindung(lp._core.base_dir, geraet_name_eigen="Laptop-Test", loopback_erlaubt=True)
    try:
        assert lp.heimnetz_verbinden(f"127.0.0.1:{pc._dienst.port}", code)["ok"]
        lp.ki_einschalten()
        lp._ki._thread.join(timeout=10)
        r = lp.wissen_seite_lesen("beispiel.at")
        assert r["ok"], r["text"]
        assert r["daten"]["anzahl"] == 1 and lp._wissen.anzahl() == 1 and pc._wissen.anzahl() == 0
        ordner = tmp_path / "docs"
        ordner.mkdir()
        (ordner / "notiz.txt").write_text("Der Stand-PC hat eine Radeon RX 7800 XT mit 16 GB Grafikspeicher.", encoding="utf-8")
        assert lp.wissen_ordner_lesen(str(ordner))["ok"] and pc._wissen.anzahl() == 0 and lp._wissen.anzahl() == 2
        z = lp.wissen_zustand()["daten"]
        assert z["anzahl"] == 2 and {q["art"]: q["privat"] for q in z["quellen"]} == {"privatseite": False, "dokument": True}
        pc._wissen.seite_lesen("beispiel.at")
        (tmp_path / "pcnotiz").mkdir()
        (tmp_path / "pcnotiz" / "geheim.txt").write_text("Der Stand-PC hat eine Radeon RX 7800 XT mit 16 GB Grafikspeicher, privat notiert.", encoding="utf-8")
        pc._wissen.ordner_lesen(tmp_path / "pcnotiz")
        pc_frage = pc_fake.frage

        def frage(nachrichten, *, on_token=None, zusatz="", **kw):
            pc_fake.zusatz = zusatz
            a = pc_frage(nachrichten, on_token=on_token)
            return type(a)("Anleitungen rund um KI (Quelle 1).", a.prompt_tokens, a.completion_tokens, a.dauer_s)
        pc_fake.frage = frage
        g = lp.gespraech_neu()["daten"]
        r = lp.frage(g["kennung"], "Welche Grafikkarte hat der Stand-PC?")
        assert r["ok"], r["text"]
        assert "geheim" not in pc_fake.zusatz and "7800" not in pc_fake.zusatz
        r = lp.frage(g["kennung"], "Was steht auf beispiel.at?")
        assert "beispiel.at stehen Anleitungen" in pc_fake.zusatz
        ls = r["daten"]["lieferschein"]
        assert ls["quellen"].startswith("Beispiel-Seite") and ls["geraet"] == "PC-Test im Heimnetz"
        privat = next(q for q in lp.wissen_zustand()["daten"]["quellen"] if q["privat"])
        assert lp.wissen_entfernen(privat["kennung"])["ok"] and lp._wissen.anzahl() == 1
        assert not lp.wissen_entfernen("000000000000")["ok"]
    finally:
        pc._dienst.stop()


def test_surface_has_the_knowledge_page():
    import app_web
    html = (app_web.webapp_dir() / app_web.INDEX_NAME).read_text(encoding="utf-8")
    for needle in ('data-seite="wissen"', "Eine Website lesen", "Gedächtnis-Pass lesen", "wissen_seite_lesen", "Gemerkte Quellen", "quellen_liste"):
        assert needle in html


def test_a_page_whose_robots_txt_says_no_is_not_read(monkeypatch):
    import io
    w._robots.clear()

    class _R(io.BytesIO):
        def __init__(self, b, art="text/html"):
            super().__init__(b)
            self.headers = {"Content-Type": art}
            self.url = ""
        def __enter__(self): return self
        def __exit__(self, *a): return False

    seiten = {"https://zu.example/robots.txt": _R(b"User-agent: *\nDisallow: /privat/\n", "text/plain"),
              "https://zu.example/privat/seite": _R(b"<html><title>Geheim</title><body>" + b"Text " * 30 + b"</body></html>"),
              "https://zu.example/offen": _R(b"<html><title>Offen</title><body>" + b"Text " * 30 + b"</body></html>"),
              "https://frei.example/seite": _R(b"<html><title>Frei</title><body>" + b"Text " * 30 + b"</body></html>")}
    aufrufe = []

    def oeffner(req, timeout):
        aufrufe.append(req.full_url)
        if req.full_url not in seiten:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        r = seiten[req.full_url]; r.seek(0); r.url = req.full_url
        return r

    with pytest.raises(w.WissenError) as e:
        w.seite_holen("https://zu.example/privat/seite", oeffner=oeffner)
    assert e.value.code == "WISSEN_ROBOTS"
    assert w.seite_holen("https://zu.example/offen", oeffner=oeffner)[1] == "Offen"
    assert aufrufe.count("https://zu.example/robots.txt") == 1
    assert w.seite_holen("https://frei.example/seite", oeffner=oeffner)[1] == "Frei"
    seiten["https://ki.example/robots.txt"] = _R(b"User-agent: GPTBot\nDisallow: /\n", "text/plain")
    seiten["https://ki.example/seite"] = _R(b"<html><title>KI</title><body>" + b"Text " * 30 + b"</body></html>")
    with pytest.raises(w.WissenError) as e:
        w.seite_holen("https://ki.example/seite", oeffner=oeffner)
    assert "GPTBot" in e.value.detail
    seiten["https://meta.example/seite"] = _R(b"<html><head><meta name=\"robots\" content=\"index, noai\"></head><title>M</title><body>" + b"Text " * 30 + b"</body></html>")
    with pytest.raises(w.WissenError) as e:
        w.seite_holen("https://meta.example/seite", oeffner=oeffner)
    assert "Vorbehalt in der Seite" in e.value.detail
    seiten["https://tdm.example/.well-known/tdmrep.json"] = _R(b"[{\"location\": \"/\", \"tdm-reservation\": 1}]", "application/json")
    seiten["https://tdm.example/seite"] = _R(b"<html><title>T</title><body>" + b"Text " * 30 + b"</body></html>")
    assert w.vorbehalt("https://tdm.example/seite", oeffner=oeffner) == "Vorbehalt in tdmrep.json"

    def stumm(req, timeout):
        raise OSError("keine Antwort")
    assert w.vorbehalt("https://stumm.example/seite", oeffner=stumm) == "robots.txt nicht erreichbar"


def test_the_start_of_the_prompt_stays_the_same_over_the_minute():
    from datetime import datetime, timezone
    import wissen as w
    a, b = datetime(2026, 10, 3, 14, 57, tzinfo=timezone.utc), datetime(2026, 10, 3, 14, 58, tzinfo=timezone.utc)
    assert w.datum_zeile(a) == w.datum_zeile(b) and "Uhr" not in w.datum_zeile(a)
    assert w.uhrzeit_zeile(a) != w.uhrzeit_zeile(b) and "Uhr" in w.uhrzeit_zeile(a)
