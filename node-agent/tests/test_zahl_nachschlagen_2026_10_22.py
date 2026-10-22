# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import wikipedia

FRAGE = "Wie heißt der höchste Berg der Schweiz?"
SATZ = "Der höchste Berg der Schweiz ist die Dufourspitze mit 4634 Metern."
DUFOUR = "Die Dufourspitze ist mit 4634 m ü. M. der höchste Berg der Schweiz und liegt im Monte-Rosa-Massiv."
QUELLEN = [{"nummer": 1, "titel": "Wikipedia: Schweiz", "adresse": "https://de.wikipedia.org/wiki/Schweiz", "art": "wikipedia",
            "text": "Die Schweiz ist ein Binnenstaat in Mitteleuropa mit rund 9 Millionen Einwohnern. Die Alpen bedecken etwa 60 Prozent der Fläche."},
           {"nummer": 2, "titel": "Alpen", "adresse": "https://beispiel.at/alpen", "art": "nachgeschaut",
            "text": "Der Mont Blanc ist mit 4806 Metern der höchste Berg der Alpen. Viele Gipfel in der Schweiz sind höher als 4000 Meter."}]


def _anwenden(text, nachschlagen):
    quellen = [dict(q) for q in QUELLEN]
    return app_web.belege_anwenden(text, FRAGE, "\n".join(q["text"] for q in quellen), quellen, heute=date(2026, 10, 22), nachschlagen=nachschlagen)


def test_die_richtige_zahl_bleibt_die_erfundene_faellt():
    t, notizen = _anwenden(SATZ, None)
    assert t == "Das weiß ich noch nicht." and notizen
    t, notizen = _anwenden(SATZ, lambda s: DUFOUR if "Dufourspitze" in s else "")
    assert t == SATZ and notizen == []
    t, _ = _anwenden("Der höchste Berg der Schweiz ist die Dufourspitze mit 5120 Metern.", lambda s: DUFOUR)
    assert t == "Das weiß ich noch nicht."
    t, _ = _anwenden(SATZ, lambda s: "")
    assert t == "Das weiß ich noch nicht."
    t, _ = _anwenden(SATZ, lambda s: (_ for _ in ()).throw(OSError("Kopie belegt")))
    assert t == "Das weiß ich noch nicht."


def _kopie(tmp_path):
    db = wikipedia.Datenbank(tmp_path / "w.sqlite", schreiben=True)
    db.teil_aufnehmen(1, [
        {"id": 1, "titel": "Schweiz", "beliebt": 0.009, "geaendert": "", "umleitungen": [], "teile": [QUELLEN[0]["text"]]},
        {"id": 2, "titel": "Dufourspitze", "beliebt": 0.002, "geaendert": "", "umleitungen": [], "teile": [DUFOUR]},
        {"id": 3, "titel": "Berg", "beliebt": 0.004, "geaendert": "", "umleitungen": [], "teile": ["Ein Berg ist eine Landform."]},
    ])
    db.teil_abschliessen(1)
    k = object.__new__(wikipedia.WikiKopie)
    k._db, k._log, k.ausgabe = db, lambda z: None, lambda: "20261020"
    return k


class _Selbst:
    _belege_nachher = app_web.Api._belege_nachher

    def __init__(self, wiki):
        self._wiki = wiki
        self._core = None

    def _beleg_pruefer(self):
        return None

    def _umschreiber(self):
        return None

    @staticmethod
    def _schritt(_t):
        pass


def test_mit_der_echten_kopie_steht_der_artikel_unter_der_antwort(tmp_path, monkeypatch):
    monkeypatch.setattr(app_web, "_log", lambda *_a, **_k: None)
    k = _kopie(tmp_path)
    assert "Wikipedia: Dufourspitze" in " ".join(t.quelle.titel for t in k.einleitung(SATZ, hoechstens=5))
    quellen = [dict(q) for q in QUELLEN]
    lieferschein = {"quellen_liste": []}
    text = _Selbst(k)._belege_nachher(SATZ, FRAGE, "\n".join(q["text"] for q in quellen), quellen, lieferschein, None)
    assert text == SATZ
    assert any("Dufourspitze" in q["titel"] for q in lieferschein["quellen_liste"]) and "belege" not in lieferschein
    assert lieferschein["nachgeschlagen"] == [f"Wikipedia: Dufourspitze ({wikipedia.LIZENZ})"]
    assert lieferschein["pruefung"]["gruen"] >= 1


def test_die_pruefrunde_zaehlt_das_warten_auf_die_suchbremse_nicht_als_antwortzeit():
    s = {"sucht im Internet": 43, "prüft Zahlen, Daten und Namen": 15, "schreibt die Antwort": 8}
    assert app_web.ohne_suchbremse(s, 40.2) == {"prüft Zahlen, Daten und Namen": 15, "schreibt die Antwort": 8, "sucht im Internet": 3,
                                                "wartet auf die Suchbremse": 40}
    neben = {"prüft, welche Fundstellen wirklich passen": 45, "schreibt die Antwort": 2}
    assert app_web.ohne_suchbremse(neben, 41)["prüft, welche Fundstellen wirklich passen"] == 4
    assert app_web.ohne_suchbremse(s, 0.3) == s
    src = (Path(app_web.__file__)).read_text(encoding="utf-8")
    assert '"dauer_s": round(max(0.0, time.time() - t0 - gewartet), 1)' in src and "self._mess_gewartet = getattr(self, \"_mess_gewartet\", 0.0) +" in src
