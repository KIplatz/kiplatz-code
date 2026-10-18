# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belege
import nachschauen
import wissen


@pytest.mark.parametrize("frage", [
    "Was brauche ich vor der Einreise in die USA, brauche ich ein Visum?",
    "Brauche ich ein Visum für Japan als Österreicher?",
    "Brauche ich für einen Urlaub in England etwas vor der Reise?",
    "Kann ich mit meinem Führerschein in Japan Auto fahren?",
    "Benötigt man für Indien ein Visum?",
    "Do I need a visa to visit Japan as a US citizen?",
    "What do I need to enter the US from the UK?",
    "Do I need a permit to drive in Brazil?",
])
def test_einreise_und_regeln_in_jedem_land_suchen_im_netz(frage):
    assert belege.regelfrage(frage) and nachschauen.nicht_im_lexikon(frage)


@pytest.mark.parametrize("frage", [
    "Wer ist Premierminister von Großbritannien?",
    "Wer ist der Bürgermeister von Tokio?",
    "Who is the prime minister of Japan?",
    "Who is the current president of Brazil?",
    "Who's the CEO of Toyota?",
    "Wer regiert Indien?",
])
def test_wer_heute_ein_amt_hat_sucht_im_netz(frage):
    assert nachschauen.amtsfrage(frage) and nachschauen.nicht_im_lexikon(frage)


@pytest.mark.parametrize("frage", [
    "Wer ist Mozart?",
    "Wer war der erste Präsident der USA?",
    "Who was the first prime minister of India?",
    "Wer hat das Wiener Riesenrad gebaut?",
    "Wie lange muss ich ein weiches Ei kochen?",
    "Darf ich meinem Hund Schokolade geben?",
    "Kann ich Kuchen einfrieren?",
    "Was muss ich in Italien essen?",
    "What can I see in Tokyo?",
    "Wo muss man im Deutschen ein Komma setzen?",
])
def test_wissensfragen_bleiben_beim_lexikon(frage):
    assert not nachschauen.nicht_im_lexikon(frage)


@pytest.mark.parametrize("frage", [
    "Who is the prime minister of the UK?",
    "How much is the ESTA fee?",
    "What is the current exchange rate of the yen?",
    "When is Memorial Day 2027?",
])
def test_englische_fragearten_wie_deutsche(frage):
    a = nachschauen.erkennen(frage)
    assert a is not None and a.art == "suche"


def test_neues_aus_einem_land_ohne_feeds_wird_gesucht_statt_orf():
    for frage in ("Was gibt es Neues in Japan?", "What is the latest news from India?"):
        assert nachschauen.erkennen(frage).art == "suche" and nachschauen.nicht_im_lexikon(frage)
    assert nachschauen.erkennen("Was gibt es Neues?").land == "at"
    assert nachschauen.erkennen("Nachrichten aus Deutschland").land == "de"


def test_kalender_des_programms_nur_fuer_dach_englisch_fuer_was_ueberall_gleich_faellt():
    import kalender_tage
    from datetime import date
    assert not kalender_tage.betrifft("Wann ist die Zeitumstellung in den USA?")
    assert not kalender_tage.betrifft("When is Father's Day 2027?")
    assert kalender_tage.betrifft("Wann ist die Zeitumstellung?")
    assert "Ostersonntag: Sonntag, 28.3.2027" in kalender_tage.text("When is Easter 2027?", date(2026, 10, 18))
    assert "Pfingstsonntag: Sonntag, 16.5.2027" in kalender_tage.text("When is Pentecost 2027?", date(2026, 10, 18))
    assert nachschauen.nicht_im_lexikon("When does daylight saving time end in the US this year?")


def test_englische_daten_in_quellen_belegen_den_satz():
    assert belege.daten("Diwali will be celebrated on Sunday, November 8, 2026.") == {(8, 11, 2026)}
    assert belege.daten("Memorial Day 2027 falls on 31 May 2027, the 31st of May") == {(31, 5, 2027), (31, 5, None)}
    assert belege.daten("you may 3 times") == set()
    assert belege.streng_pruefen("Diwali ist 2026 am Sonntag, 8. November 2026.", "Diwali will be celebrated on Sunday, November 8, 2026.") == []
    assert belege.streng_pruefen("Diwali ist 2026 am 9. November 2026.", "Diwali will be celebrated on Sunday, November 8, 2026.")[0].zahlen == ("9.11.2026",)


def test_jahreszahl_muss_zur_sache_gehoeren():
    q = ("Erst 1884 wurde der Vorschlag von Horace Jones genehmigt. Die Bauarbeiten begannen mit der Grundsteinlegung am 21. Juni 1886. "
         "Die Brücke wurde 1894 eröffnet.")
    assert belege.streng_pruefen("Der Bau begann 1884 mit der Grundsteinlegung.", q)[0].zahlen == ("1884",)
    assert belege.streng_pruefen("Der Bau begann 1886 mit der Grundsteinlegung.", q) == []
    assert belege.streng_pruefen("Die Brücke wurde 1894 eröffnet.", q) == []
    assert belege.jahre_anderswo("Der Bau begann 1884.", ["The bridge was built from 1886 to 1894."]) == []


def test_feiertag_am_namen_weltweit():
    import kalender_welt
    assert kalender_welt.laender_fuer("When is Memorial Day 2027?") == ["US", "KR"]
    assert kalender_welt.laender_fuer("Wann ist der Memorial Day 2027?") == ["US", "KR"]
    assert kalender_welt.laender_fuer("When is Juneteenth?") == ["US"]
    assert kalender_welt.laender_fuer("When is Thanksgiving 2026?") == ["US", "CA"]
    assert kalender_welt.laender_fuer("When is Bastille Day?") == ["FR"]
    assert kalender_welt.laender_fuer("When is Christmas 2026?") == []
    assert kalender_welt.laender_fuer("Feiertage in Indien") == []
    assert kalender_welt.betrifft("When is Memorial Day 2027?") and not kalender_welt.betrifft("How long do I roast a turkey?")
    t = kalender_welt.text("US", {2027: [{"datum": "2027-05-31", "name": "Memorial Day", "lokal": "Memorial Day"},
                                         {"datum": "2027-07-05", "name": "Independence Day", "lokal": "Independence Day"}]}, "When is Memorial Day 2027?")
    assert "Memorial Day: Montag, 31.5.2027" in t and "Independence" not in t


def test_mehrere_laender_fremde_quelle_faellt_weg():
    jp = _treffer("Japan", "US citizens can stay in Japan up to 90 days without a visa.")
    ua = _treffer("Tourismus in der Ukraine", "Für die Ukraine braucht man eine Reisekrankenversicherung.")
    behalten, weg = belege.fremdes_land_weg("Do I need a visa to visit Japan as a US citizen?", [jp, ua])
    assert behalten == [jp] and weg == 1


def test_behoerden_der_welt_und_bei_regeln_nur_sie():
    for a in ("https://www.gov.uk/eta", "https://esta.cbp.dhs.gov/", "https://www.mofa.go.jp/x", "https://immi.homeaffairs.gov.au/",
              "https://www.bmeia.gv.at/", "https://www.service-public.fr/"):
        assert nachschauen.amtlich(a), a
    for a in ("https://application-eta.uk/", "https://www.visasunited.com/", "https://www.gogo.jp/"):
        assert not nachschauen.amtlich(a), a
    from datetime import date
    treffer = [{"adresse": "https://application-eta.uk/apply", "titel": "UK ETA application", "text": "Apply for your UK ETA online"},
               {"adresse": "https://www.gov.uk/eta", "titel": "Get an electronic travel authorisation (ETA)", "text": "It costs £20"}]
    reihe = nachschauen.treffer_reihen(treffer, "Do I need an ETA to enter the UK?", heute=date(2026, 10, 18))
    assert [t["adresse"] for t in reihe] == ["https://www.gov.uk/eta", "https://application-eta.uk/apply"]


def _runde(gov_gesperrt: bool):
    import urllib.error
    from test_wissen import _Antwort
    seiten = {"https://www.gov.uk/eta": "<html><body><p>You need an ETA to visit the UK. An ETA costs £20 and lasts 2 years.</p></body></html>",
              "https://application-eta.uk/apply": "<html><body><p>Apply for your UK ETA with us for £59 including our service fee.</p></body></html>",
              "https://visa-hilfe.example/uk": "<html><body><p>UK ETA service: we apply for you for £45.</p></body></html>"}

    def oeffner(req, timeout=0):
        url = req.full_url
        if url.endswith("/robots.txt"):
            return _Antwort(url, b"", "text/plain")
        if gov_gesperrt and "gov.uk" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        return _Antwort(url, seiten.get(url, "<html><body><p>kurz</p></body></html>").encode("utf-8"))

    def suche(q, **kw):
        return [{"titel": "UK ETA application", "adresse": "https://application-eta.uk/apply", "text": "Apply for your UK ETA online"},
                {"titel": "Get an ETA", "adresse": "https://www.gov.uk/eta", "text": "electronic travel authorisation"},
                {"titel": "UK ETA Hilfe", "adresse": "https://visa-hilfe.example/uk", "text": "UK ETA service"}]
    nachschauen._GESPERRT.clear() if hasattr(nachschauen, "_GESPERRT") else None
    n = nachschauen.Nachschauer(suche_fn=suche, seiten_oeffner=oeffner)
    erg, gelesen, _ = n.suche_runde(["UK ETA"], "Do I need an ETA to enter the UK?", sprache="en-GB")
    return [e.adresse for e in erg if not e.titel.startswith("Suchergebnisse")], [e.titel for e in erg]


def test_behoerden_vorn_aber_keine_seite_faellt_weg():
    adressen, _ = _runde(gov_gesperrt=False)
    assert adressen[0] == "https://www.gov.uk/eta" and len(adressen) >= 2
    adressen, _ = _runde(gov_gesperrt=True)
    assert adressen and "https://www.gov.uk/eta" not in adressen


def test_ampel_gilt_fuer_den_gezeigten_text():
    import types
    import app_web
    roh = "Für eine Reise brauchst du **meistens** eine Genehmigung. Welches Visum du brauchst, hängt vom Zweck ab."
    sichtbar = app_web.ohne_markdown(roh)
    fake = types.SimpleNamespace(_schritt=lambda t: None, _beleg_pruefer=lambda: None, _wiki=None, _core=None)
    ls = {"pruefung": app_web.pruefung.pruefen(roh, []).kurz()}
    text = app_web.Api._belege_nachher(fake, sichtbar, "Was ist eine Genehmigung?", "", [], ls, None)
    assert text == sichtbar and all(s["text"] in sichtbar for s in ls["pruefung"]["saetze"]) and len(ls["pruefung"]["saetze"]) == 2
    ls2 = {"pruefung": {"saetze": [{"text": "x", "farbe": "gruen"}]}}
    app_web.Api._belege_nachher(fake, sichtbar, "Frage?", "", [], ls2, None, ampel=False)
    assert ls2["pruefung"]["saetze"][0]["farbe"] == "gruen"


def test_live_probe_nach_18i():
    for frage in ("Brauchen Österreicher für einen Urlaub in den USA ein Visum?", "Benötigen Deutsche einen Reisepass für England?",
                  "Do Austrians need a visa to visit the United States?"):
        assert belege.regelfrage(frage) and nachschauen.nicht_im_lexikon(frage), frage
    for frage in ("Brauche ich Backpulver für einen Kuchen?", "How many eggs do I need for a cake?", "Wie lange muss ich ein weiches Ei kochen?"):
        assert not nachschauen.nicht_im_lexikon(frage), frage
    assert nachschauen.suchbegriffe_regel("Brauche ich als Österreicher ein Visum für Japan?") == "Österreicher Visum Japan"
    assert nachschauen.suchbegriffe_regel("Do Austrians need a visa to visit the United States?") == "Austrians visa visit United States"
    q = "Austrian citizens can stay in Japan for up to 90 days without a visa. The United States require an ESTA."
    assert not any(b.namen or "Staatsbürger Österreichs" in b.verdacht
                   for b in belege.streng_pruefen("Als Staatsbürger Österreichs kannst du bis zu 90 Tage ohne Visum nach Japan reisen.", q))
    assert belege.streng_pruefen("In den Vereinigten Staaten braucht man eine ESTA.", q) == []
    assert belege.streng_pruefen("In Frankreich braucht man keine ESTA.", q)[0].verdacht == ("Frankreich",)


def _treffer(titel, text, adresse="https://beispiel.example/x"):
    return wissen.Treffer(wissen.Quelle("k-" + titel, "seite", titel, adresse, "2026-10-18", len(text)), text, 1.0)


def test_laender_der_ganzen_welt():
    assert belege.gefragtes_land("Brauche ich ein Visum für Japan?") == "jp"
    assert belege.gefragtes_land("Wie hoch ist der Mindestlohn in Brasilien?") == "br"
    assert belege.gefragtes_land("Do I need a visa for Japan as a US citizen?") == ""
    assert {"JP", "AT"} <= belege.laender_in("Österreicher reisen bis 90 Tage ohne Visum nach Japan")


def test_fundstelle_ueber_ein_fremdes_land_faellt_weg_auch_ausserhalb_europas():
    jp = _treffer("Japan Einreise", "Für Japan gilt: bis 90 Tage ohne Visum.")
    th = _treffer("Thailand Einreise", "Für Thailand gilt: 60 Tage ohne Visum.")
    allgemein = _treffer("Visum", "Ein Visum ist eine Erlaubnis zur Einreise.")
    behalten, weg = belege.fremdes_land_weg("Brauche ich ein Visum für Japan?", [jp, th, allgemein])
    assert behalten == [jp, allgemein] and weg == 1


def test_land_der_adresse_weltweit_ohne_allgemeine_endungen():
    assert belege.land_der_adresse("https://www.mofa.go.jp/j_info/visit/visa/") == "jp"
    assert belege.land_der_adresse("https://www.gov.uk/eta") == "gb"
    assert belege.land_der_adresse("https://www.adac.de/x") == "de"
    for adresse in ("https://kiplatz.com/", "https://ki.io/", "https://news.co/", "https://beispiel.example/", "https://europa.eu/"):
        assert belege.land_der_adresse(adresse) == ""
    jp_seite = _treffer("Visa", "Short-term stay up to 90 days.", "https://www.mofa.go.jp/visa")
    assert belege.fremdes_land_weg("Brauche ich ein Visum für Thailand?", [jp_seite])[1] == 1
