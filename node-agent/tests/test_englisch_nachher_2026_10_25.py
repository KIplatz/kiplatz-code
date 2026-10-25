# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import antwortspeicher_basis
import app_web
import belege
import pruefung
import zufallsfragen


@contextmanager
def englisch():
    pruefung.sprache_setzen(True)
    try:
        yield
    finally:
        pruefung.sprache_setzen(False)


def test_der_merker_ist_aus_und_gilt_nur_im_eigenen_faden():
    import threading
    assert pruefung.englisch() is False
    gesehen = []
    with englisch():
        t = threading.Thread(target=lambda: gesehen.append(pruefung.englisch()))
        t.start()
        t.join()
        assert pruefung.englisch() is True
    assert gesehen == [False] and pruefung.englisch() is False


@pytest.mark.parametrize("text", ["I don't know that yet.", "I don’t know that yet.", "I do not know.", "I can't say for sure.",
                                  "None of the sources mention a date.", "The sources don't say how long it takes."])
def test_ein_englisches_weiss_nicht_loest_die_nachsuche_aus(text):
    assert app_web._WEISS_NICHT.search(text)


@pytest.mark.parametrize("text", ["I don't know that yet.", "I don’t know that yet.", "I do not know.",
                                  "I don't know that yet, and I couldn't find anything reliable on the internet just now."])
def test_ein_englisches_weiss_nicht_kommt_nicht_in_den_speicher_und_zaehlt_als_offen(text):
    assert antwortspeicher_basis._WEISS_NICHT.search(text)
    assert zufallsfragen._WEISS_NICHT.search(text)


@pytest.mark.parametrize("text", ["Vienna has about 2 million inhabitants.", "The Danube is 2,850 km long.",
                                  "Wien hat rund 2 Millionen Einwohner.", "Die Donau ist 2.850 km lang."])
def test_eine_antwort_mit_inhalt_ist_kein_weiss_nicht(text):
    assert not app_web._WEISS_NICHT.search(text)
    assert not antwortspeicher_basis._WEISS_NICHT.search(text)
    assert not zufallsfragen._WEISS_NICHT.search(text)


def test_die_deutschen_saetze_bleiben_wie_sie_waren():
    assert belege.weiss_nicht_satz() == "Das weiß ich noch nicht."
    assert app_web.ohne_auszuege("Das steht nicht in den Auszügen.") == "Das weiß ich noch nicht."
    assert app_web.auftrag_sprache("Fokus: „Das weiß ich noch nicht.“") == "Fokus: „Das weiß ich noch nicht.“"
    ls: dict = {}
    assert app_web._weiss_nicht_anwenden("Das weiß ich noch nicht.", ls) == app_web._WEISS_NICHT_SATZ
    assert app_web._weiss_nicht_anwenden("Das weiß ich noch nicht.", {}, gesucht=True) == app_web._GESUCHT_NICHTS_SATZ
    assert app_web._weiss_nicht_anwenden("Das weiß ich noch nicht.", {}, gesucht="nicht_erreicht") == app_web._NICHT_ERREICHT_SATZ
    assert app_web.ohne_auszuege("Die Passage in Linz hat bis 19 Uhr offen.") == "Die Passage in Linz hat bis 19 Uhr offen."


def test_eine_englische_antwort_bekommt_englische_saetze_des_programms():
    with englisch():
        assert belege.weiss_nicht_satz() == "I don't know that yet."
        assert app_web.ohne_auszuege("The sources do not mention the opening hours.") == "I don't know that yet."
        assert app_web.ohne_auszuege("Vienna has about 2 million inhabitants. The passages don't say more.") == "Vienna has about 2 million inhabitants."
        assert app_web._weiss_nicht_anwenden("I don't know that yet.", {}) == app_web._WEISS_NICHT_SATZ_EN
        assert app_web._weiss_nicht_anwenden("I don't know that yet.", {}, gesucht=True) == app_web._GESUCHT_NICHTS_SATZ_EN
        lang = "Vienna is the capital of Austria. It lies on the Danube. It has many museums."
        assert app_web._weiss_nicht_anwenden(lang, {}).endswith("\n\n" + app_web._NACHPRUEFEN_ANGEBOT_EN)
        for satz in (app_web._WEISS_NICHT_SATZ_EN, app_web._NACHPRUEFEN_ANGEBOT_EN, app_web._GESUCHT_NICHTS_SATZ_EN, app_web._NICHT_ERREICHT_SATZ_EN):
            assert not any(w in satz.lower() for w in ("weiß", "nicht", " und ", "soll ich"))


def test_ein_rest_ohne_anfang_heisst_auf_englisch_auch_englisch():
    with englisch():
        rest, raus = belege.saetze_streichen("The opening hours are 9 to 5.", lambda s: True)
        assert rest == "I don't know that yet." and raus
        t, n = belege.ohne_selbstbezug("My previous answer was wrong. Correction: the museum opens at 10.")
        assert n >= 1 and "previous" not in t and "Correction" not in t


def test_der_auftrag_an_das_modell_verlangt_englisch_und_den_englischen_satz():
    with englisch():
        z = app_web.auftrag_sprache(app_web.ERFUNDEN_ZUSATZ)
        assert "„Das weiß ich noch nicht.“" not in z and "“I don't know that yet.”" in z
        assert z.endswith(app_web.AUFTRAG_ENGLISCH)
        assert app_web.auftrag_sprache("") == app_web.AUFTRAG_ENGLISCH


def test_englische_anfuehrungszeichen_sind_kein_satzrest():
    satz = "In Vienna, a “Melange” is a coffee with milk foam."
    assert not belege.brauchbar(satz)
    with englisch():
        assert belege.brauchbar(satz)
    assert belege.brauchbar("In Wien ist eine „Melange“ ein Kaffee mit Milchschaum.")


def test_die_belegpruefung_liest_englisch_ohne_fuellwoerter():
    quelle = [(1, "The Grossglockner is the highest mountain in Austria, with a height of 3,798 metres.")]
    erfunden = "The mountain was first climbed by the Romans with their armies."
    with englisch():
        gedeckt = pruefung.pruefen("The Grossglockner is the highest mountain in Austria (Source 1).", quelle)
        falsch = pruefung.pruefen(erfunden, quelle)
        assert gedeckt.saetze[0].farbe == "gruen" and gedeckt.saetze[0].genannt == (1,)
        assert falsch.saetze[0].farbe != "gruen"
        assert pruefung.ohne_quellenmarke("It is 3,798 metres high (Source 1).") == "It is 3,798 metres high."
        assert "the" not in pruefung._woerter("the highest mountain with snow")
    assert "the" in pruefung._woerter("the highest mountain with snow")


def test_der_antwortkern_setzt_den_merker_und_beide_eingaenge_heben_ihn_auf():
    import inspect
    assert inspect.signature(app_web.Api._antwort_kern).parameters["englisch"].default is False
    assert "pruefung.sprache_setzen(englisch)" in inspect.getsource(app_web.Api._antwort_kern)
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert quelle.count("pruefung.sprache_setzen(False)") == 2
