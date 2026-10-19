# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))

import app_web
import belege
import wissen
from test_app_web import _api

HEUTE = date(2026, 10, 15)
WINTER = "Wann muss ich in Österreich auf Winterreifen wechseln?"
ERFUNDEN = ("In Österreich gibt es keine gesetzliche Pflicht, zu einem bestimmten Datum auf Winterreifen zu wechseln.\n\n"
            "Die Winterreifenpflicht gilt laut Straßenverkehrsordnung (StVO) § 70 Abs. 4 auf Straßen mit Schnee- oder Eisglätte.\n\n"
            "Quelle: Österreichische Straßenverkehrsordnung (StVO) und Empfehlungen des Kuratoriums für Verkehrssicherheit (KfV).")
KFG = ("Winterreifenpflicht in Österreich: Von 1. November bis 15. April müssen Pkw und leichte Lkw bis 3,5 Tonnen bei winterlichen "
       "Fahrbahnverhältnissen wie Schneefahrbahn, Schneematsch oder Eis auf allen Rädern Winterreifen haben (KFG § 102 Abs. 8a).")


def test_eine_regelfrage_sucht_auch_wenn_ein_lexikonabsatz_die_woerter_hat(tmp_path, monkeypatch):
    api, _fake, _ = _api(tmp_path)
    gesucht: list = []
    monkeypatch.setattr(api, "_suchrunde", lambda frage, alle, lauf, treffer, frisch=False: gesucht.append(alle) or ([], ""))
    monkeypatch.setattr(api._nachschauer, "suche_runde", lambda *a, **k: ([], [], ""), raising=False)
    q = wissen.Quelle("w1", "wikipedia", "Winterreifen", "", "2026-10-01T00:00:00Z", 100)
    lexikon = [wissen.Treffer(q, "Winterreifen sind in Österreich bei winterlichen Verhältnissen vorgeschrieben, wechseln sollte man im Herbst.", 2.0)]
    assert app_web.Api._deckt_ab(WINTER, lexikon)
    api._nachschauen(WINTER, lexikon, suchen=True)
    assert gesucht, "eine Frage, die nicht im Lexikon steht, wird gesucht, auch wenn ein Lexikonabsatz ihre Wörter hat"
    gesucht.clear()
    api._nachschauen("Erzähl mir was über Winterreifen in Österreich", lexikon)
    assert not gesucht


@pytest.mark.parametrize("frage", [WINTER, "Tempolimit auf deutschen Autobahnen", "Ab wann darf man in Österreich wählen?",
                                   "Darf ich in Deutschland mit 17 Auto fahren?", "Do I have to wear a helmet in the UK?", "Kündigungsfrist in Österreich",
                                   "Gibt es ein Autobahntempolimit?", "Ist Rauchen im Auto mit Kindern verboten?"])
def test_regelfragen(frage):
    assert belege.regelfrage(frage)


@pytest.mark.parametrize("frage", ["Wie lange muss ich ein Ei kochen?", "Wie lange muss ich eine Tiefkühlpizza backen?", "Was soll ich heute kochen?",
                                   "Wie entkalke ich meine Kaffeemaschine?", "Wie hoch ist der Großglockner?", ""])
def test_keine_regelfragen(frage):
    assert not belege.regelfrage(frage)


def test_eine_regel_ohne_quelle_wird_nicht_aus_dem_gedaechtnis_genannt():
    t, notizen = app_web.belege_anwenden(app_web.ohne_auszuege(ERFUNDEN), WINTER, "", [], heute=HEUTE)
    assert t == "Das weiß ich noch nicht." and app_web.REGEL_OHNE_QUELLE in notizen
    t, _ = app_web.belege_anwenden("Ein weiches Ei braucht etwa 6 Minuten.", "Wie lange muss ich ein Ei kochen?", "", [], heute=HEUTE)
    assert t == "Ein weiches Ei braucht etwa 6 Minuten."


def test_eine_regel_braucht_einen_satz_aus_der_quelle():
    fremd = [{"nummer": 1, "titel": "Reifen", "art": "wikipedia", "text": "Ein Reifen besteht aus Gummi, Stahl und Gewebe."}]
    t, notizen = app_web.belege_anwenden("In Österreich gibt es keine feste Pflicht, man wechselt bei Schnee.", WINTER, "Quelle 1: Reifen\n" + fremd[0]["text"],
                                         fremd, heute=HEUTE)
    assert t == "Das weiß ich noch nicht." and "1 Satz mit einer Regel, die keine Quelle so sagt, vom Programm gestrichen." in notizen
    echt = [{"nummer": 1, "titel": "Winterreifenpflicht", "art": "nachgeschaut", "text": KFG}]
    antwort = ("Von 1. November bis 15. April müssen in Österreich bei winterlichen Fahrbahnverhältnissen wie Schneefahrbahn, Schneematsch oder Eis "
               "Winterreifen montiert sein (KFG § 102 Abs. 8a).")
    t, _ = app_web.belege_anwenden(antwort, WINTER, "Quelle 1: Winterreifenpflicht\n" + KFG, echt, heute=HEUTE)
    assert "15. April" in t and "102" in t
    t, _ = app_web.belege_anwenden(antwort + " Das regelt die StVO § 70.", WINTER, "Quelle 1: Winterreifenpflicht\n" + KFG, echt, heute=HEUTE)
    assert "StVO" not in t and "15. April" in t


def test_eine_eigene_quellenzeile_des_modells_faellt_weg():
    t = app_web.ohne_auszuege(ERFUNDEN)
    assert "Quelle:" not in t and "KfV" not in t and t.startswith("In Österreich")
    assert app_web.ohne_auszuege("Text.\n**Quellen:** a, b\nSources: x") == "Text."
    assert app_web.ohne_auszuege("Eine Quelle: das bleibt mitten im Satz.") == "Eine Quelle: das bleibt mitten im Satz."


MAUT = ("In Italien ist die Autobahn mautpflichtig. Die Gebühr hängt von der Strecke ab.")


def test_ganz_oder_gar_nicht():
    quelle = [{"nummer": 1, "titel": "Maut", "art": "nachgeschaut", "text": "In Italien ist die Autobahn mautpflichtig. Bezahlt wird an der Mautstelle."}]
    zusatz = "Quelle 1: Maut\n" + quelle[0]["text"]
    auftraege: list[str] = []
    erste = "Die Maut in Italien kostet 7,80 € je 100 Kilometer. Betroffen sind alle Autobahnen."
    t, notizen = app_web.belege_anwenden(erste, "Autobahn in Italien, wie ist das geregelt?", zusatz, quelle, heute=HEUTE,
                                         nochmal=lambda e: auftraege.append(e) or "Für die Autobahnen in Italien zahlt man Maut, und zwar an der Mautstelle.")
    assert len(auftraege) == 1 and t.startswith("Für die Autobahnen in Italien zahlt man Maut") and any("neu geantwortet" in n for n in notizen)
    t, notizen = app_web.belege_anwenden(erste, "Autobahn in Italien, wie ist das geregelt?", zusatz, quelle, heute=HEUTE,
                                         nochmal=lambda e: "Die Maut kostet 9,10 € je 100 Kilometer.")
    assert t == "Das weiß ich noch nicht." and any("Anfang der Antwort" in n for n in notizen)
    assert app_web.nur_rest(erste, "Betroffen sind alle Autobahnen.", ["Die Maut in Italien kostet 7,80 € je 100 Kilometer."])
    assert not app_web.nur_rest("Anna wohnt in Gmunden. Sie fährt gern Rad. Sie liest viel.", "Anna wohnt in Gmunden. Sie liest viel.", ["Sie fährt gern Rad."])
    assert not app_web.nur_rest("Klagenfurt hat 105.734 Einwohner und München 1,48 Millionen.", "Klagenfurt hat 105.734 Einwohner.",
                                ["Klagenfurt hat 105.734 Einwohner und München 1,48 Millionen."])


def test_preise_gelten_nur_aus_dem_laufenden_jahr():
    assert app_web.zeitziel("Wie viel kostet die Vignette in Slowenien?", HEUTE) == (None, 2026)
    assert app_web.zeitziel("Was kostete die Vignette 2024?", HEUTE) == (None, None)
    assert app_web.zeitziel("Wie hoch ist der Großglockner?", HEUTE) == (None, None)
    alt = [{"nummer": 1, "titel": "Vignette Slowenien", "art": "nachgeschaut", "text": "Preise 2024: 7 Tage 16 €, Monat 32 €, Jahr 117,50 €."}]
    t, _ = app_web.belege_anwenden("Seit 2024 kostet die Wochenvignette 16 €. Die Jahresvignette kostete 2024 117,50 €.", "Wie viel kostet die Vignette in Slowenien?",
                                   "Quelle 1: Vignette Slowenien\n" + alt[0]["text"], alt, heute=HEUTE)
    assert "117,50" not in t


def test_rechte_maustaste_im_fenster(tmp_path):
    prog = (HIER / "webapp" / "index.html").read_text(encoding="utf-8")
    assert '<ul id="kontext-text" class="kontext" role="menu" hidden>' in prog
    for name in ("Rückgängig machen", "Wiederholen", "Ausschneiden", "Kopieren", "Einfügen", "Alles auswählen"):
        assert f">{name}</li>" in prog
    assert 'document.addEventListener("contextmenu", textMenue);' in prog and "if (e.defaultPrevented) return;" in prog
    assert "api().einfuegen_druecken()" in prog and "einfuegen_holen" not in prog
    api, _fake, _ = _api(tmp_path)
    gedrueckt: list = []
    api._strg_v = lambda: gedrueckt.append(1)
    api._window_vorne = lambda: True
    assert api.einfuegen_druecken()["ok"] and gedrueckt == [1]
    api._window_vorne = lambda: False
    r = api.einfuegen_druecken()
    assert r["code"] == "NICHT_VORNE" and gedrueckt == [1]
    assert not hasattr(app_web.Api, "einfuegen_holen") and "_zwischenablage_lesen" not in (HIER / "app_web.py").read_text(encoding="utf-8")


def test_regel_und_preis_bekommen_den_fokus_schon_in_der_ersten_fassung():
    assert app_web.REGEL_FOKUS in app_web.mit_fokus("Q", "Tempolimit auf deutschen Autobahnen")
    assert app_web.PREIS_FOKUS in app_web.mit_fokus("Q", "Was kostet die Vignette in Slowenien?")
    assert app_web.REGEL_FOKUS not in app_web.frage_fokus("Was kostet die Vignette in Slowenien?")
    assert app_web.mit_fokus("Q", "Erzähl mir was über Linz") == "Q"


def _seite(adresse, text):
    return wissen.Treffer(wissen.Quelle("k-" + adresse, "nachgeschaut", "Winterreifen", adresse, "2026-10-15", len(text)), text, 1.0)


def test_eine_seite_ohne_land_zaehlt_mit_dem_land_ihrer_adresse():
    de = _seite("https://www.reifen-ratgeber.de/m-s", "Seit 1. Oktober 2024 reicht M+S nicht mehr, nur das Alpine-Symbol zählt.")
    at = _seite("https://www.oesterreich.gv.at/winterreifen", "Winterreifen sind Reifen mit M+S oder Schneeflockensymbol, mindestens 4 mm Profil.")
    com = _seite("https://tyres.example.com/guide", "Winter tyres carry the 3PMSF symbol.")
    de_ueber_at = _seite("https://www.adac.de/oesterreich", "In Österreich gilt von 1. November bis 15. April eine situative Winterreifenpflicht.")
    behalten, weg = belege.fremdes_land_weg(WINTER, [de, at, com, de_ueber_at])
    assert behalten == [at, com, de_ueber_at] and weg == 1
    assert belege.fremdes_land_weg("Wann wechselt man auf Winterreifen?", [de, at])[1] == 0


def test_amtliche_stellen_werden_bei_regelfragen_zuerst_gelesen():
    import nachschauen
    treffer = [{"adresse": "https://www.reifenblog.example/winter", "titel": "Winterreifen Österreich wechseln", "text": "Winterreifen wechseln Österreich"},
               {"adresse": "https://www.oesterreich.gv.at/themen/winterreifen", "titel": "Winterausrüstung", "text": "Winterreifen Pflicht"}]
    reihe = nachschauen.treffer_reihen(treffer, WINTER, heute=HEUTE)
    assert reihe[0]["adresse"].startswith("https://www.oesterreich.gv.at/")
    reihe = nachschauen.treffer_reihen(treffer, "Erzähl mir was über Winterreifen in Österreich", heute=HEUTE)
    assert reihe[0]["adresse"].startswith("https://www.reifenblog.example/")
    assert nachschauen.amtlich("https://www.oeamtc.at/x") and not nachschauen.amtlich("https://fakeoeamtc.at/x")


def test_preise_und_regeln_kommen_nie_aus_dem_antwortspeicher():
    import antwortspeicher_basis as a

    def taugt(f):
        return a.frage_taugt([{"role": "user", "content": f}])
    for f in ("Was kostet die Vignette in Slowenien?", "Autobahn Maut in Italien", "Tempolimit auf deutschen Autobahnen",
              "Gibt es eine Winterreifenpflicht in Tirol?", "Wie hoch ist das Bußgeld fürs Telefonieren am Steuer?"):
        assert taugt(f) == "", f
    assert taugt("Wie viele Einwohner hat Innsbruck?") == "einwohner innsbruck" and taugt("Wie hoch ist der Großglockner?")


def test_kein_satz_ueber_das_was_nicht_dasteht():
    t = app_web.ohne_auszuege("In Deutschland gibt es kein generelles Tempolimit auf Autobahnen.\n\nÜber Studien, Meinungen oder Debatten dazu steht hier nichts.")
    assert t == "In Deutschland gibt es kein generelles Tempolimit auf Autobahnen."
    assert "Studien" not in app_web.REGEL_FOKUS and "Debatten" not in app_web.REGEL_FOKUS
    import nachschauen
    assert nachschauen.nicht_im_lexikon("Tempolimit auf deutschen Autobahnen") and not nachschauen.nicht_im_lexikon("Wie hoch ist der Großglockner?")


def test_neufassungen_bekommen_die_wortgrenze_gleich_mit():
    for z in (app_web.BELEGE_ZUSATZ, app_web.FRAGE_FOKUS):
        assert "nie mehr als 6 Wörter am Stück" in z
    assert "nie mehr als 6 Wörter am Stück" in belege.UMSCHREIBEN_DE and "never more than 6 words in a row" in belege.UMSCHREIBEN_EN
    assert 6 < belege.WOERTLICH_WOERTER


def test_zeit_je_schritt_fuer_die_details():
    import rechenarbeit
    ablauf = [(0.0, "sucht im Wissen der Community …"), (0.6, "prüft, welche Fundstellen wirklich passen …"),
              (1.2, "sucht im Internet nach „Autobahn Maut Italien“ und liest die besten Seiten …"), (10.4, "schreibt die Antwort …"),
              (15.0, "prüft Zahlen, Daten und Namen gegen die Quellen …"), (19.0, "prüft Zahlen, Daten und Namen gegen die Quellen …")]
    z = rechenarbeit.zeit_je_schritt(ablauf, 31.0)
    assert z == "Zeit je Schritt: sucht im Internet 9 s, schreibt die Antwort 5 s, prüft Zahlen, Daten und Namen 16 s."
    assert "Autobahn" not in z and rechenarbeit.zeit_je_schritt([], 3.0) == ""


def test_der_pruefer_beginnt_wie_die_antwort(tmp_path, monkeypatch):
    from types import SimpleNamespace
    api, _fake, _ = _api(tmp_path)
    aufrufe: list = []

    class Server:
        def frage(self, nachrichten, **kw):
            aufrufe.append((nachrichten, kw))
            return SimpleNamespace(text="1 Name\n2 Wort")
    ki = SimpleNamespace(server=Server(), quelle=lambda: "lokal", bereit=lambda: True,
                         wahl=SimpleNamespace(modell=SimpleNamespace(kennung=next(iter(app_web.PRUEFER_MODELLE)))))
    monkeypatch.setattr(api, "_ki", ki)
    pruefer = api._beleg_pruefer()
    assert pruefer("Quelle 1: ARBÖ\nMaut in Italien", ["Asfinag", "Mautstelle"]) == {0}
    nachrichten, kw = aufrufe[0]
    assert "system" not in kw and kw["zusatz"] == "Quelle 1: ARBÖ\nMaut in Italien" and kw["art"] == "pruefer" and kw["temperature"] == 0.0
    assert nachrichten[0]["content"].startswith(belege.PRUEFER_SYSTEM) and nachrichten[0]["content"].endswith("Wörter:\n1. Asfinag\n2. Mautstelle")
