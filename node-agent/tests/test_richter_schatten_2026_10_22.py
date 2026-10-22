# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
import threading
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import bewertung

FRAGE = "Wie heißt der höchste Berg der Schweiz?"
SATZ = "Der höchste Berg der Schweiz ist die Dufourspitze mit 4634 Metern."
QUELLEN = [{"nummer": 1, "titel": "Wikipedia: Schweiz", "adresse": "https://de.wikipedia.org/wiki/Schweiz", "art": "wikipedia",
            "text": "Die Schweiz ist ein Binnenstaat in Mitteleuropa mit rund 9 Millionen Einwohnern. Die Alpen bedecken etwa 60 Prozent der Fläche."},
           {"nummer": 2, "titel": "Alpen", "adresse": "https://beispiel.at/alpen", "art": "nachgeschaut",
            "text": "Der Mont Blanc ist mit 4806 Metern der höchste Berg der Alpen. Viele Gipfel in der Schweiz sind höher als 4000 Meter."}]


def _anwenden(text, richter):
    quellen = [dict(q) for q in QUELLEN]
    return app_web.belege_anwenden(text, FRAGE, "\n".join(q["text"] for q in quellen), quellen, heute=date(2026, 10, 22), richter=richter)


def test_das_nachschlagen_ist_wieder_draussen():
    t, notizen = _anwenden(SATZ, None)
    assert t == "Das weiß ich noch nicht." and notizen
    src = Path(app_web.__file__).read_text(encoding="utf-8")
    assert "def nachschlagen" not in src and "nachschlagen=" not in src and '"nachgeschlagen"' not in src


def test_ohne_pruefrunde_urteilt_kein_richter():
    gerufen = []
    app_web._SCHATTEN.liste = None
    t, _ = _anwenden(SATZ, lambda s, texte: gerufen.append(s) or 0.9)
    assert gerufen == [] and t == "Das weiß ich noch nicht."


def test_in_der_pruefrunde_urteilt_der_richter_und_die_antwort_bleibt_gleich():
    ohne, notizen_ohne = _anwenden(SATZ, None)
    gesehen = []
    app_web._SCHATTEN.liste = []
    try:
        mit, notizen_mit = _anwenden(SATZ, lambda s, texte: gesehen.append((s, list(texte))) or 0.84)
        liste = list(app_web._SCHATTEN.liste)
    finally:
        app_web._SCHATTEN.liste = None
    assert (mit, notizen_mit) == (ohne, notizen_ohne)
    assert gesehen and gesehen[0][0] == SATZ and QUELLEN[1]["text"] in gesehen[0][1]
    assert liste[0] == {"z": True, "w": liste[0]["w"], "n": False, "g": True, "r": 0.84, "rg": 0.84}
    assert app_web.schatten_notiz(liste).startswith("Richter: Z1 W") and "R0,84/0,84" in app_web.schatten_notiz(liste)
    assert gesehen[1][0] == "Der höchste Berg der Schweiz ist die Dufourspitze mit 7634 Metern."


def test_ein_fehler_des_richters_stoert_keine_antwort():
    ohne = _anwenden(SATZ, None)
    app_web._SCHATTEN.liste = []
    try:
        mit = _anwenden(SATZ, lambda s, texte: (_ for _ in ()).throw(OSError("Reranker aus")))
        liste = list(app_web._SCHATTEN.liste)
    finally:
        app_web._SCHATTEN.liste = None
    assert mit == ohne and liste and liste[0]["r"] is None
    assert "R-/-" in app_web.schatten_notiz(liste)


def test_die_notiz_hat_nur_zahlen_und_urteile():
    liste = [{"z": False, "w": 2, "n": True, "g": True, "r": 0.123}] * 9
    n = app_web.schatten_notiz(liste)
    assert n == "Richter: " + "; ".join(["Z0 W2 N1 G1 R0,12"] * 6) + ". "
    assert app_web.schatten_notiz([{"z": True, "w": 0, "n": False, "g": False, "r": 0.9, "rg": 0.31}]) == "Richter: Z1 W0 N0 G0 R0,90/0,31. "
    assert app_web.schatten_notiz([]) == ""


def test_die_gegenprobe_verfaelscht_jede_zahl():
    assert (app_web.gegenprobe_satz("Die Zugspitze ist 2962 m hoch, seit 1820 bestiegen, 7 Gipfel.")
            == "Die Zugspitze ist 5962 m hoch, seit 4820 bestiegen, 1 Gipfel.")
    assert app_web.gegenprobe_satz("Ohne Zahl.") == "Ohne Zahl."


def test_die_notiz_behaelt_den_lieferschein():
    hinten = "Die erste Fassung nannte Zahlen, Daten oder Namen, die in keiner Quelle stehen; KIplatz hat neu geantwortet. "
    n = app_web.notiz_zusammen("V" * 700, hinten)
    assert n.endswith(hinten) and len(n) == app_web.pruefstand.NOTIZ_MAX
    assert app_web.notiz_zusammen("kurz. ", "") == "kurz. "


def test_der_richter_sieht_die_ganze_quelle_in_stuecken():
    text = " ".join(f"Satz {i} über die Alpen und ihre Gipfel in der Schweiz." for i in range(80))
    stuecke = app_web.richter_stuecke(text)
    assert len(stuecke) > 1 and all(len(s) <= bewertung.MAX_ZEICHEN for s in stuecke)
    assert "Satz 79 " in stuecke[-1] and " ".join(stuecke) == text
    tabelle = " | ".join(f"Gipfel {i} 4{i:03d} m" for i in range(200))
    stuecke = app_web.richter_stuecke(tabelle)
    assert all(len(s) <= bewertung.MAX_ZEICHEN for s in stuecke) and " ".join(stuecke) == tabelle
    assert app_web.richter_stuecke("") == []


class _Server:
    def __init__(self):
        self.anfragen = []

    @staticmethod
    def laeuft():
        return True

    def bewerten(self, frage, texte, *, timeout_s):
        self.anfragen.append((frage, list(texte)))
        return [0.2] + [0.7] * (len(texte) - 1)


class _Bewertung:
    def __init__(self):
        self.server = _Server()


class _Selbst:
    _belege_nachher = app_web.Api._belege_nachher

    def __init__(self):
        self._wiki = None
        self._core = None
        self._bewertung = _Bewertung()

    def _beleg_pruefer(self):
        return None

    def _umschreiber(self):
        return None

    @staticmethod
    def _schritt(_t):
        pass


def test_das_programm_fragt_den_reranker_mit_der_aussage(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda *_a, **_k: None)
    selbst = _Selbst()
    quellen = [dict(q) for q in QUELLEN]
    app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = [], 0.0
    try:
        selbst._belege_nachher(SATZ, FRAGE, "\n".join(q["text"] for q in quellen), quellen, {"quellen_liste": []}, None)
        liste, zeit = list(app_web._SCHATTEN.liste), app_web._SCHATTEN.zeit
    finally:
        app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = None, 0.0
    frage, texte = selbst._bewertung.server.anfragen[0]
    assert frage == "Stützt der Text diese Aussage? " + SATZ and len(texte) <= bewertung.MAX_KANDIDATEN
    assert liste[0]["r"] == 0.7 and zeit >= 0.0


def test_der_richter_schweigt_wenn_ein_mitglied_fragt(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda *_a, **_k: None)
    selbst = _Selbst()
    selbst._rechen = type("R", (), {"vorrang": threading.Event()})()
    selbst._rechen.vorrang.set()
    quellen = [dict(q) for q in QUELLEN]
    app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = [], 0.0
    try:
        selbst._belege_nachher(SATZ, FRAGE, "\n".join(q["text"] for q in quellen), quellen, {"quellen_liste": []}, None)
        liste = list(app_web._SCHATTEN.liste)
    finally:
        app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = None, 0.0
    assert selbst._bewertung.server.anfragen == [] and liste and liste[0]["r"] is None


def test_jede_quelle_kommt_beim_richter_dran(monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda *_a, **_k: None)
    selbst = _Selbst()
    lang = " ".join(f"Langer Satz {i} über etwas ganz anderes, das hier nichts zur Sache tut." for i in range(200))
    quellen = [{"nummer": i + 1, "titel": f"Lang {i}", "adresse": f"https://beispiel.at/{i}", "art": "nachgeschaut", "text": lang}
               for i in range(4)]
    quellen.append({"nummer": 5, "titel": "Dufourspitze", "adresse": "https://beispiel.at/dufour", "art": "nachgeschaut",
                    "text": "Die Dufourspitze im Monte-Rosa-Massiv ist der höchste Berg der Schweiz. Der Mont Blanc misst 4806 Meter."})
    app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = [], 0.0
    try:
        selbst._belege_nachher(SATZ, FRAGE, "\n".join(q["text"] for q in quellen), quellen, {"quellen_liste": []}, None)
    finally:
        app_web._SCHATTEN.liste, app_web._SCHATTEN.zeit = None, 0.0
    assert selbst._bewertung.server.anfragen
    for _frage, texte in selbst._bewertung.server.anfragen:
        assert any("Dufourspitze" in t for t in texte) and len(texte) <= bewertung.MAX_KANDIDATEN


def test_die_pruefrunde_zaehlt_das_warten_auf_die_suchbremse_nicht_als_antwortzeit():
    s = {"sucht im Internet": 43, "prüft Zahlen, Daten und Namen": 15, "schreibt die Antwort": 8}
    assert app_web.ohne_suchbremse(s, 40.2) == {"prüft Zahlen, Daten und Namen": 15, "schreibt die Antwort": 8, "sucht im Internet": 3,
                                                "wartet auf die Suchbremse": 40}
    neben = {"prüft, welche Fundstellen wirklich passen": 45, "schreibt die Antwort": 2}
    assert app_web.ohne_suchbremse(neben, 41)["prüft, welche Fundstellen wirklich passen"] == 4
    assert app_web.ohne_suchbremse(s, 0.3) == s
    r = app_web.ohne_suchbremse(s, 2, name="Probe: Richter", zuerst=())
    assert r["sucht im Internet"] == 41 and r["Probe: Richter"] == 2
    beide = app_web.ohne_suchbremse(app_web.ohne_suchbremse(s, 40.2), 3, name="Probe: Richter", zuerst=())
    assert beide["wartet auf die Suchbremse"] == 40 and beide["prüft Zahlen, Daten und Namen"] == 12
    src = Path(app_web.__file__).read_text(encoding="utf-8")
    assert '"dauer_s": round(max(0.0, time.time() - t0 - gewartet - richter_s), 1)' in src
    assert "self._mess_gewartet = getattr(self, \"_mess_gewartet\", 0.0) +" in src
