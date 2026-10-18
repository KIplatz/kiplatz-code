# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege
import nachschauen

HEUTE = date(2026, 10, 18)
WEISS_NICHT = "Das weiß ich noch nicht."
REGEL_NOTIZ = "1 Satz mit einer Regel, die keine Quelle so sagt, vom Programm gestrichen."


def _q(n, titel, adresse, text):
    return {"nummer": n, "titel": titel, "art": "nachgeschaut", "adresse": adresse, "text": text}


def _zusatz(quellen):
    return "\n".join(f"\nQuelle {q['nummer']}: {q['titel']} ({q['adresse']}) – nachgeschaut\n{q['text']}" for q in quellen)


def _anwenden(antwort, frage, quellen, **kw):
    return app_web.belege_anwenden(antwort, frage, _zusatz(quellen), quellen, heute=HEUTE, **kw)


JAPAN = "Brauche ich als Österreicher ein Visum für Japan?"
OEAMTC = [_q(1, "Nachgeschaut: Japan – ÖAMTC Länderinfo", "https://www.oeamtc.at/laenderinfo/japan",
             "In Japan ist für Österreicher ein Internationaler Führerschein nach dem Genfer Abkommen erforderlich. Der österreichische "
             "Führerschein allein wird nicht anerkannt. In Japan herrscht Linksverkehr.")]
BOTSCHAFT_EN = [_q(1, "Nachgeschaut: Visa – Embassy of Japan in Austria", "https://www.at.emb-japan.go.jp/visa",
                   "Austrian citizens do not need a visa for tourist stays of up to 90 days in Japan. The stay can be extended to six months at "
                   "an immigration office. A valid passport is required.")]
BMEIA = [_q(1, "Nachgeschaut: Japan – Reiseinformation", "https://www.bmeia.gv.at/reise-services/reiseinformation/land/japan",
            "Österreichische Staatsbürger benötigen für touristische Aufenthalte bis zu 90 Tagen kein Visum. Ein gültiger Reisepass ist erforderlich.")]


def test_live_18j_ja_zum_visum_ohne_quelle_faellt():
    antwort = ("Ja, du brauchst als Österreicher für Japan ein Visum. Für das Autofahren brauchst du einen Internationalen Führerschein nach "
               "dem Genfer Abkommen.")
    t, notizen = _anwenden(antwort, JAPAN, OEAMTC)
    assert t == WEISS_NICHT and REGEL_NOTIZ in notizen
    neu = "Für das Autofahren in Japan brauchst du als Österreicher einen Internationalen Führerschein nach dem Genfer Abkommen."
    gesehen = []
    t, notizen = _anwenden(antwort, JAPAN, OEAMTC, nochmal=lambda extra: gesehen.append(extra) or neu)
    assert t == neu and "Die erste Fassung nannte eine Regel, die keine Quelle so sagt; KIplatz hat neu geantwortet." in notizen
    assert app_web.REGEL_ZUSATZ in gesehen[0]


def test_ein_widerspruch_zur_quelle_faellt():
    t, notizen = _anwenden("Ja, du brauchst als Österreicher für Japan ein Visum.", JAPAN, BOTSCHAFT_EN)
    assert t == WEISS_NICHT and REGEL_NOTIZ in notizen
    t, _ = _anwenden("Ja.", JAPAN, BMEIA)
    assert t == WEISS_NICHT


@pytest.mark.parametrize("quellen", [BOTSCHAFT_EN, BMEIA], ids=["englische Quelle", "deutsche Quelle"])
@pytest.mark.parametrize("antwort", [
    "Nein, als Österreicher brauchst du für Japan kein Visum, wenn du bis zu 90 Tage bleibst.",
    "Nein, Österreicher brauchen für einen Urlaub in Japan bis zu 90 Tage kein Visum. Du brauchst einen gültigen Reisepass.",
    "Österreicher können bis zu 90 Tage visumfrei nach Japan einreisen.",
])
def test_richtige_antwort_bleibt_in_jeder_sprache(antwort, quellen):
    t, notizen = _anwenden(antwort, JAPAN, quellen)
    assert t == antwort and not notizen


USA = "Was brauche ich vor der Einreise in die USA, brauche ich ein Visum?"
ESTA_QUELLE = [_q(1, "Nachgeschaut: ESTA – Official Site", "https://esta.cbp.dhs.gov/faq",
                  "Citizens of Visa Waiver Program countries such as Austria may travel to the United States without a visa for stays of up to "
                  "90 days. Travelers must have an approved ESTA prior to boarding. Apply at least 72 hours before departure.")]


def test_usa_esta_bleibt_falsches_visum_faellt():
    richtig = "Als Österreicher brauchst du für bis zu 90 Tage kein Visum, aber eine genehmigte ESTA. Für die Einreise brauchst du eine ESTA."
    t, notizen = _anwenden(richtig, USA, ESTA_QUELLE)
    assert t == richtig and not notizen
    t, notizen = _anwenden("Österreicher brauchen für die USA ein Visum.", USA, ESTA_QUELLE)
    assert t == WEISS_NICHT and REGEL_NOTIZ in notizen


def test_englische_frage_englische_antwort():
    frage = "Do I need a visa to visit Japan as a US citizen?"
    quelle = [_q(1, "Nachgeschaut: Visa – Embassy of Japan in the USA", "https://www.us.emb-japan.go.jp/itpr_en/visa.html",
                 "U.S. citizens do not need a visa for short-term stays of up to 90 days for tourism. A passport is required.")]
    gut = "No, as a US citizen you do not need a visa for tourist stays of up to 90 days."
    assert _anwenden(gut, frage, quelle) == (gut, [])
    t, notizen = _anwenden("Yes, US citizens need a visa for Japan.", frage, quelle)
    assert t == WEISS_NICHT and REGEL_NOTIZ in notizen


def test_fuehrerschein_ohne_eigenen_gegenstand_ueber_den_wortstamm():
    frage = "Kann ich mit meinem Führerschein in Japan Auto fahren?"
    quelle = [_q(1, "Nachgeschaut: Driving in Japan – JAF", "https://jaf.or.jp/driving-in-japan",
                 "Visitors from Austria need an International Driving Permit based on the 1949 Geneva Convention. An Austrian licence alone "
                 "is not valid.")]
    gut = "Ja, mit einem Internationalen Führerschein nach dem Genfer Abkommen darfst du in Japan fahren."
    assert _anwenden(gut, frage, quelle)[0] == gut


def test_ohne_regelfrage_aendert_sich_nichts():
    frage = "Was ist die Golden Week in Japan?"
    quelle = [_q(1, "Nachgeschaut: Golden Week", "https://www.japan-guide.com/e/e2282.html",
                 "Golden Week is a collection of four national holidays within seven days, from 29 April to 5 May.")]
    antwort = "Die Golden Week sind vier Feiertage zwischen 29. April und 5. Mai. In dieser Zeit kann man kaum günstig reisen."
    assert belege.regel_aussagen(antwort, frage) == [] or not belege.regelfrage(frage)
    assert _anwenden(antwort, frage, quelle)[0] == antwort


@pytest.mark.parametrize("satz,richtung", [
    ("Österreicher brauchen kein Visum.", 1),
    ("A visa is not required.", 1),
    ("Austrians don't need a visa.", 1),
    ("Visa-free entry for 90 days is possible.", 1),
    ("Under the Visa Waiver Program you may travel.", 1),
    ("Ohne Visum ist die Einreise verboten.", 0),
    ("A visa is required.", 0),
    ("Es besteht keine Visumpflicht.", 1),
])
def test_richtung_ist_die_zahl_der_verneinungen(satz, richtung):
    gegen = [g for t in belege._TEILSATZ.split(satz) for g in belege._regel_gegenstaende(t, set())]
    assert ("Visum", richtung) in gegen


def test_rueckfragen_und_ob_saetze_sind_keine_regel():
    assert belege.regel_aussagen("Möchtest du wissen, ob du ein Visum brauchst?", JAPAN) == []
    assert belege.regel_aussagen("Frag bei der Botschaft nach, ob du ein Visum brauchst.", JAPAN) == []


ETA = "How do I get a UK ETA and how much does it cost?"


@pytest.mark.parametrize("text", [
    "This website is not affiliated with the UK Government. Apply for your ETA in minutes.",
    "We are a private visa service provider and are not affiliated with any government agency.",
    "ETA-Hilfe has no link to the UK government.",
    "The price includes the government fee and our service fee.",
    "Wir sind keine Behörde, sondern ein privater Dienstleister.",
    "Diese Website ist nicht mit der britischen Regierung verbunden.",
    "Nous ne sommes pas affiliés au gouvernement britannique.",
])
def test_vermittler_erkennt_man_an_dem_was_er_ueber_sich_sagt(text):
    assert nachschauen.vermittler(text, "https://application-eta.example/apply")


@pytest.mark.parametrize("text,adresse", [
    ("Do not use unofficial websites. You can only apply through GOV.UK or the UK ETA app.", "https://www.thelocal.at/eta"),
    ("We are not responsible for the content of external websites.", "https://www.beispiel.at/impressum"),
    ("Wir sind ein Reiseblog und schreiben über Japan.", "https://reiseblog.example/japan"),
    ("This website is not affiliated with any other government.", "https://www.gov.uk/eta"),
])
def test_keine_falschen_vermittler(text, adresse):
    assert not nachschauen.vermittler(text, adresse)


def _eta_quellen():
    vermittler_text = ("Apply for your UK ETA online with eta.beispiel.at for £59. The price includes the government fee and our service fee. "
                       "You need an ETA to visit the UK.")
    return [
        _q(1, "Suchergebnisse", "https://www.gov.uk/eta",
           "Suchergebnisse (Community-Suche), gelesen am 18.10.2026.\n\n1. www.gov.uk – Get an ETA: It costs £20.\n\n"
           f"2. eta.beispiel.at – Apply UK ETA ({nachschauen.VERMITTLER_ZEILE})"),
        _q(2, "Nachgeschaut: Get an electronic travel authorisation (ETA)", "https://www.gov.uk/eta/apply",
           "Gefunden über die Suche, Seite „Get an ETA“ (https://www.gov.uk/eta/apply), gelesen am 18.10.2026. "
           "Visitors need an ETA for the UK. Applications are made through GOV.UK or the official UK ETA app. The fee is £20, and an ETA is valid for 2 years."),
        _q(3, "Nachgeschaut: Apply UK ETA", "https://eta.beispiel.at/apply",
           nachschauen.gefunden_zeile("Apply UK ETA", "https://eta.beispiel.at/apply", "18.10.2026", vermittler_text) + " " + vermittler_text),
    ]


def test_preis_und_adresse_eines_vermittlers_fallen_der_rest_bleibt():
    quellen = _eta_quellen()
    assert nachschauen.VERMITTLER_SATZ in quellen[2]["text"]
    antwort = ("You apply for a UK ETA on GOV.UK or with the UK ETA app. It costs £20 and lasts 2 years. "
               "You can also apply through eta.beispiel.at for £59.")
    t, notizen = _anwenden(antwort, ETA, quellen)
    assert "£20" in t and "2 years" in t and "beispiel" not in t and "£59" not in t
    ohne = [dict(q, text=q["text"].replace(nachschauen.VERMITTLER_SATZ, "")) for q in quellen]
    assert "£59" in _anwenden(antwort, ETA, ohne)[0]


def test_eine_seite_nur_vom_vermittler_belegt_keine_regel():
    quellen = [_eta_quellen()[2]]
    t, _ = _anwenden("You need an ETA to visit the UK.", "Do I need an ETA to visit the UK?", quellen)
    assert t == WEISS_NICHT


def test_suchrunde_kennzeichnet_vermittler_und_nimmt_seinen_auszug_aus_der_trefferliste():
    import urllib.error
    from test_wissen import _Antwort
    seiten = {"https://www.gov.uk/eta": "<html><body><p>You need an ETA to visit the UK. An ETA costs £20 and lasts 2 years.</p></body></html>",
              "https://application-eta.example/apply": "<html><body><p>Apply for your UK ETA with us for £59.</p><p>The price includes the "
                                                       "government fee and our service fee.</p></body></html>",
              "https://www.thelocal.example/eta": "<html><body><p>Only GOV.UK and the UK ETA app are official. Other websites charge more."
                                                  "</p></body></html>"}

    def oeffner(req, timeout=0):
        url = req.full_url
        if url.endswith("/robots.txt"):
            return _Antwort(url, b"", "text/plain")
        return _Antwort(url, seiten.get(url, "<html><body><p>kurz</p></body></html>").encode("utf-8"))

    def suche(q, **kw):
        return [{"titel": "UK ETA application", "adresse": "https://application-eta.example/apply", "text": "Apply now from £59"},
                {"titel": "Get an ETA", "adresse": "https://www.gov.uk/eta", "text": "It costs £20"},
                {"titel": "UK ETA: what to know", "adresse": "https://www.thelocal.example/eta", "text": "Only GOV.UK is official"}]
    n = nachschauen.Nachschauer(suche_fn=suche, seiten_oeffner=oeffner)
    erg, _gelesen, _ = n.suche_runde(["UK ETA"], ETA, sprache="en-GB")
    texte = {e.adresse: e.text for e in erg if not e.titel.startswith("Suchergebnisse")}
    assert set(texte) == set(seiten)
    assert nachschauen.VERMITTLER_SATZ in texte["https://application-eta.example/apply"]
    assert all(nachschauen.VERMITTLER_SATZ not in t for a, t in texte.items() if a != "https://application-eta.example/apply")
    liste = next(e.text for e in erg if e.titel.startswith("Suchergebnisse"))
    assert "application-eta.example" in liste and nachschauen.VERMITTLER_ZEILE in liste and "from £59" not in liste
    assert "It costs £20" in liste


def test_adressen_in_der_antwort_muessen_in_einer_quelle_stehen():
    assert belege.adressen_in("Beantrage sie auf www.gov.uk oder über eta.beispiel.at, siehe bericht.pdf, z.B. 3.5 kg.") == ["gov.uk", "eta.beispiel.at"]
    befunde = belege.streng_pruefen("Du beantragst sie auf gov.uk oder auf eta.beispiel.at.", "Quelle: https://www.gov.uk/eta/apply")
    assert befunde and befunde[0].namen == ("eta.beispiel.at",)
    assert belege.streng_pruefen("Du beantragst sie auf gov.uk.", "Quelle: https://www.gov.uk/eta/apply") == []
