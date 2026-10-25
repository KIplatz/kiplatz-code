# SPDX-License-Identifier: AGPL-3.0-or-later
import bz2
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wikipedia

HIER = Path(__file__).resolve().parent.parent


def doc(i, titel, text, **mehr):
    d = {"page_id": str(i), "namespace": 0, "page_type": "primary", "title": titel, "text": text, "popularity_score": mehr.pop("beliebt", 1e-6),
         "timestamp": "2026-09-01T10:00:00Z", "redirect": mehr.pop("redirect", []), "template": mehr.pop("template", []),
         "auxiliary_text": mehr.pop("aux", [])}
    d.update(mehr)
    return d


DOCS = [
    doc(1, "Gmunden", "Gmunden ist eine Stadtgemeinde im Salzkammergut in Oberösterreich am Nordufer des Traunsees. Die Stadt ist bekannt für ihre Keramik.",
        aux=["Basisdaten Bundesland Oberösterreich Bezirk Gmunden Bürgermeister Stefan Krapf (ÖVP) Einwohner 13.000"], beliebt=5e-5),
    doc(2, "Wärmepumpe", "Eine Wärmepumpe ist eine Maschine, die unter Aufwendung von technischer Arbeit thermische Energie aus einem Reservoir "
        "mit niedrigerer Temperatur aufnimmt und als Nutzwärme auf ein zu beheizendes System mit höherer Temperatur überträgt.",
        redirect=[{"namespace": 0, "title": "Waermepumpe"}], beliebt=3e-5),
    doc(3, "Traunsee", "Der Traunsee ist ein See im Salzkammergut. An seinem Nordufer liegt Gmunden. World Meteorological Organization, abgerufen am 6. April 2012."),
    doc(4, "Linz (Begriffsklärung)", "Linz steht für mehrere Orte.", template=["Vorlage:Begriffsklärung"]),
    {"page_id": "5", "namespace": 0, "page_type": "redirect", "title": "Gmunden am Traunsee", "text": ""},
]


def teil_bytes(docs) -> bytes:
    zeilen = []
    for d in docs:
        zeilen.append(json.dumps({"index": {"_id": int(d["page_id"])}}))
        zeilen.append(json.dumps(d, ensure_ascii=False))
    return bz2.compress(("\n".join(zeilen) + "\n").encode("utf-8"))


class Antwort(io.BytesIO):
    def __init__(self, daten: bytes, status: int = 200):
        super().__init__(daten)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def netz(teile: list[bytes], ausgabe="20260920"):
    basis = f"{wikipedia.QUELLE}{ausgabe}/index_name={wikipedia.NAME}/"
    namen = [f"{wikipedia.NAME}-{ausgabe}-{i:05d}.json.bz2" for i in range(len(teile))]
    liste = "".join(f'<a href="{n}">{n}</a>   20-Sep-2026 09:15   {len(b)}\n' for n, b in zip(namen, teile)) + '<a href="_SUCCESS">_SUCCESS</a>'
    seiten = {wikipedia.QUELLE: f'<a href="20260913/">20260913/</a> <a href="{ausgabe}/">{ausgabe}/</a>', basis: liste,
              f"{wikipedia.QUELLE}20260913/index_name={wikipedia.NAME}/": "noch nicht fertig"}
    seiten.update({basis + n: b for n, b in zip(namen, teile)})
    aufrufe = []

    def oeffner(req, timeout=None):
        aufrufe.append(req.full_url)
        daten = seiten[req.full_url]
        daten = daten.encode("utf-8") if isinstance(daten, str) else daten
        bereich = req.get_header("Range")
        if bereich:
            ab = int(bereich.split("=")[1].rstrip("-"))
            return Antwort(daten[ab:], 206)
        return Antwort(daten)
    oeffner.aufrufe = aufrufe
    return oeffner


GROSSE_PLATTE = lambda p: 2_000_000


def kopie(tmp_path, oeffner, *, freigabe=500_000, darf=lambda: True, vektoren=None, platte=GROSSE_PLATTE):
    return wikipedia.WikiKopie(lambda: tmp_path / "wikipedia", freigabe_mb=lambda: freigabe, darf=darf, oeffner=oeffner, schlafen=lambda s: None,
                               vektoren=vektoren, vektoren_bereit=lambda: vektoren is not None, platte_frei_mb=platte)


def bis_fertig(w, schritte=40):
    for _ in range(schritte):
        w.schritt()
        if w.bereit() and not w._stand().get("bau_ausgabe"):
            return


def test_an_article_is_read_as_passages_without_references_disambiguations_or_redirects():
    a = wikipedia.dokument_lesen(DOCS[0])
    assert a["titel"] == "Gmunden" and a["teile"][1].startswith("Kurzdaten: ") and "Stefan Krapf" in a["teile"][1]
    assert wikipedia.dokument_lesen(DOCS[3]) is None and wikipedia.dokument_lesen(DOCS[4]) is None
    t = wikipedia.dokument_lesen(DOCS[2])
    assert not any("abgerufen am" in x for x in t["teile"])
    assert wikipedia.dokument_lesen(DOCS[1])["umleitungen"] == ["Waermepumpe"]


def test_the_newest_complete_edition_is_fetched_read_and_searched(tmp_path):
    o = netz([teil_bytes(DOCS[:2]), teil_bytes(DOCS[2:])])
    w = kopie(tmp_path, o)
    assert not w.bereit()
    bis_fertig(w)
    assert w.bereit() and w.ausgabe() == "20260920"
    assert not any(p.suffix == ".bz2" for p in (tmp_path / "wikipedia").iterdir())
    z = w._db.zahlen()
    assert z["artikel"] == 3 and z["vorrat"] == z["abschnitte"] >= 4
    tr = w.suchen("Wie heißt der Bürgermeister von Gmunden?")
    assert tr and tr[0].quelle.titel == "Wikipedia: Gmunden (CC BY-SA 4.0)" and any("Stefan Krapf" in t.text for t in tr)
    assert tr[0].quelle.adresse == "https://de.wikipedia.org/wiki/Gmunden" and tr[0].quelle.art == "wikipedia" and tr[0].quelle.datum.startswith("2026-09-20")
    assert w.suchen("Was ist eine Waermepumpe?")[0].quelle.titel.startswith("Wikipedia: Wärmepumpe")
    assert w.suchen("Wie wird das Wetter morgen?") == []
    assert "3 Artikel" in w.text_de() and "20.09.2026" in w.text_de()


def test_an_interrupted_import_goes_on_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(wikipedia, "EINLESEN_SCHRITT", 1)
    erlaubt = {"n": 3}

    def darf():
        erlaubt["n"] -= 1
        return erlaubt["n"] > 0
    o = netz([teil_bytes(DOCS)])
    w = kopie(tmp_path, o, darf=darf)
    for _ in range(6):
        w.schritt()
    assert not w.bereit() and w.phase in ("pause", "liest")
    erlaubt["n"] = 10_000
    bis_fertig(w)
    assert w.bereit() and w._db.zahlen()["artikel"] == 3


def test_in_idle_minutes_the_device_adds_vectors_and_the_search_uses_them(tmp_path):
    gesehen = []

    def vektoren(texte):
        gesehen.extend(texte)
        return [[1.0 if "Wärmepumpe" in t else 0.0, 0.0 if "Wärmepumpe" in t else 1.0] for t in texte]
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]), vektoren=vektoren)
    bis_fertig(w)
    for _ in range(10):
        w.schritt()
    z = w._db.zahlen()
    assert z["vektoren"] == z["vorrat"] and w.phase == "fertig" and "fertig aufbereitet" in w.text_de()
    assert gesehen[0].startswith("Gmunden: ")
    r = w._db.suchen("Wärmepumpe Energie", vektor=[1.0, 0.0])
    assert r[0][2] == "Wärmepumpe"


def test_only_a_device_with_100_gb_shared_keeps_the_copy_and_lowering_it_deletes_it(tmp_path):
    frei = {"mb": 500_000}
    w = wikipedia.WikiKopie(lambda: tmp_path / "wikipedia", freigabe_mb=lambda: frei["mb"], darf=lambda: True, oeffner=netz([teil_bytes(DOCS)]), platte_frei_mb=GROSSE_PLATTE,
                            schlafen=lambda s: None)
    bis_fertig(w)
    assert w.bereit()
    frei["mb"] = 50_000
    w.schritt()
    assert not w.bereit() and not (tmp_path / "wikipedia").exists() and w.phase == "zu_wenig_platz"
    klein = wikipedia.WikiKopie(lambda: tmp_path / "w2", freigabe_mb=lambda: 500, darf=lambda: True, oeffner=lambda *a, **k: 1 / 0, schlafen=lambda s: None)
    klein.schritt()
    assert klein.phase == "zu_wenig_platz" and not (tmp_path / "w2").exists()


def test_only_wikimedia_and_the_program_wires_it_in():
    w = wikipedia.WikiKopie(lambda: Path("."), freigabe_mb=lambda: 0, darf=lambda: True)
    try:
        w._holen("https://example.org/x")
        raise AssertionError("fremde Adresse angenommen")
    except wikipedia.WikiError as exc:
        assert exc.code == "WIKI_ADRESSE"
    src = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert "self._wiki.suchen(" not in src
    assert "speicher_mb - self._wiki.belegt_mb()" in src
    assert "if not self.spielwiese:" in src and "self._wiki.start()" in src and "Profile.TEST and not self.spielwiese" not in src


def test_the_night_judges_questions_about_today_against_the_office(tmp_path):
    from datetime import datetime, timezone
    import pruefstand
    import test_bau_24m as m
    p = pruefstand.Pruefstand(tmp_path, jetzt=lambda: datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc), zeit_lesen=m.leser(m.BL_SEITEN | {m.stellen.EZB: m.EZB_SEITE}))
    k = {f["frage"]: f["kennung"] for f in p.fragen()}
    b = p.bericht_annehmen("g1", "PC", [
        {"kennung": k["Wann spielt der LASK als Nächstes?"], "antwort": "Der LASK spielt am Sonntag, 11. Oktober 2026 gegen Rapid.", "dauer_s": 5},
        {"kennung": k["Wer führt gerade die österreichische Bundesliga an?"], "antwort": "Salzburg führt.", "dauer_s": 5},
        {"kennung": k["Wie hoch ist der Leitzins der EZB?"], "antwort": "Der Leitzins liegt bei 2,65 %.", "dauer_s": 5},
        {"kennung": k["Was kostet das Klimaticket Österreich?"], "antwort": "109 Euro im Monat.", "dauer_s": 5},
        {"kennung": k["Wann ist der nächste Feiertag in Österreich?"], "antwort": "Am Freitag, 25.09.2026.", "dauer_s": 5},
    ])
    ergebnis = {f["frage"]: f["richtig"] for f in b["fragen"]}
    assert ergebnis == {"Wann spielt der LASK als Nächstes?": True, "Wer führt gerade die österreichische Bundesliga an?": False,
                        "Wie hoch ist der Leitzins der EZB?": True, "Wann ist der nächste Feiertag in Österreich?": False}
    assert b["richtig"] == 2 and b["gesamt"] == 4 and b["nicht_bewertet"][0]["frage"] == "Was kostet das Klimaticket Österreich?"
    falsch = next(f for f in b["fragen"] if f["frage"].startswith("Wer führt"))
    assert falsch["fehlt"] == ["Tabellenführer: SK Rapid"] and falsch["erwartet_heute"] == "Tabellenführer: SK Rapid"


def test_a_full_drive_stops_the_download_before_it_starts(tmp_path):
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]), platte=lambda p: 5_000)
    w.schritt()
    assert w.phase == "zu_wenig_platz" and "5 GB" in w.meldung and not w.bereit()


def test_a_finished_copy_is_not_rebuilt_when_the_new_file_would_not_fit_beside_it(tmp_path):
    frei = {"mb": 2_000_000}
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]), platte=lambda p: frei["mb"])
    bis_fertig(w)
    assert w.bereit()
    w._stand_setzen(einlese_stand=1)
    frei["mb"] = wikipedia.FREI_RESERVE_MB + 5_000
    assert w.schritt() == 3600
    assert w.phase == "zu_wenig_platz" and "25 GB frei" in w.meldung and "Neu-Einlesen" in w.meldung
    assert not w._stand().get("bau_ausgabe") and w.bereit() and (tmp_path / "wikipedia" / wikipedia.DB).exists()
    frei["mb"] = 2_000_000
    w.schritt()
    assert w._stand().get("bau_ausgabe") == "20260920"
    bis_fertig(w)
    assert w._stand()["einlese_stand"] == wikipedia.EINLESE_STAND and not w._stand().get("bau_ausgabe") and w.bereit()


def test_a_drive_that_fills_up_during_the_build_pauses_it_and_keeps_the_old_copy(tmp_path):
    frei = {"mb": 2_000_000}
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]), platte=lambda p: frei["mb"])
    bis_fertig(w)
    w._stand_setzen(einlese_stand=1)
    w.schritt()
    assert w._stand().get("bau_ausgabe") == "20260920"
    frei["mb"] = wikipedia.FREI_RESERVE_MB - 1_000
    assert w.schritt() == 3600 and w.phase == "zu_wenig_platz" and "wartet" in w.meldung
    assert w._stand().get("bau_ausgabe") == "20260920" and w.bereit()
    frei["mb"] = 2_000_000
    bis_fertig(w)
    assert w._stand()["einlese_stand"] == wikipedia.EINLESE_STAND and not w._stand().get("bau_ausgabe") and w.bereit()


def test_a_full_disk_error_from_sqlite_waits_an_hour_instead_of_ten_minutes(tmp_path):
    import sqlite3
    w = kopie(tmp_path, netz([teil_bytes(DOCS)]))
    bis_fertig(w)
    gewartet = []
    w._schlafen = lambda s: (gewartet.append(s), w._halt.set())

    def voll():
        raise sqlite3.OperationalError("database or disk is full")
    w.schritt = voll
    w._schleife()
    assert gewartet == [3600] and w.phase == "zu_wenig_platz"
