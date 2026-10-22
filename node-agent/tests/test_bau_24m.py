# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import belege
import stellen

HIER = Path(__file__).resolve().parent.parent
HEUTE = date(2026, 9, 24)

TABELLE = ("<html><body><main>ADMIRAL Bundesliga Tabelle 2026 / 2027 PL Tendenz Klub Spiele S U N Tore GT TD Punkte "
           "1 SCR SK Rapid 7 6 0 1 21 7 14 18 2 RBS FC Red Bull Salzburg 7 5 2 0 18 4 14 17 3 ASK LASK 7 5 1 1 19 7 12 16 "
           "4 - STU SK Puntigamer Sturm Graz 7 3 2 2 8 9 -1 11 5 - WSG WSG Tirol 7 2 2 3 9 12 -3 8 6 - HTB TSV Egger Glas Hartberg 7 2 2 3 10 13 -3 8 "
           "7 SVR SV Oberbank Ried 7 2 2 3 11 12 -1 8 8 GAK Grazer AK 1902 7 2 2 3 6 16 -10 8 9 - ALU SC Austria Lustenau 7 2 2 3 8 11 -3 8 "
           "10 FAK FK Austria Wien 7 2 1 4 7 13 -6 7 11 - WAC RZ Pellets WAC 7 1 2 4 7 13 -6 5 12 - ALT SCR Altach 7 1 0 6 5 12 -7 3 "
           "PL Tendenz Klub Spiele S U N Tore GT TD Punkte 1 - RBS FC Red Bull Salzburg 4 4 0 0 13 2 11 12</main></body></html>")
RUNDE_7 = ("<main>Freitag, 18. September 2026 7 18.09.2026 19:30 SCR SK Rapid WSG WSG Tirol 3 : 0 (1:0) "
           "Samstag, 19. September 2026 7 19.09.2026 17:00 ALU SC Austria Lustenau ALT SCR Altach 2 : 0 (0:0) "
           "Sonntag, 20. September 2026 7 20.09.2026 14:30 HTB TSV Egger Glas Hartberg ASK LASK 3 : 3 (0:2) "
           "7 20.09.2026 14:30 SVR SV Oberbank Ried WAC RZ Pellets WAC 4 : 1 (3:0)</main>")
RUNDE_8 = ("<main>Samstag, 10. Oktober 2026 8 10.10.2026 17:00 GAK Grazer AK 1902 RBS FC Red Bull Salzburg -:- "
           "Sonntag, 11. Oktober 2026 8 11.10.2026 14:30 ALT SCR Altach WAC RZ Pellets WAC -:- 8 11.10.2026 17:00 ASK LASK SCR SK Rapid -:-</main>")
RUNDE_9 = "<main>Samstag, 17. Oktober 2026 9 17.10.2026 17:00 SCR SK Rapid RBS FC Red Bull Salzburg -:- 9 18.10.2026 14:30 STU SK Puntigamer Sturm Graz ASK LASK -:-</main>"
EZB_SEITE = ("<table><tbody><tr><td>2026</td><td>16 Sep.</td><td>2.50</td><td>2.65</td><td>-</td><td>2.90</td></tr>"
             "<tr><td>2026</td><td>17 Jun.</td><td>2.25</td><td>2.40</td><td>-</td><td>2.65</td></tr>"
             "<tr><td>2025</td><td>11 Jun.</td><td>2.00</td><td>2.15</td><td>-</td><td>2.40</td></tr></tbody></table>")
KLIMATICKET_SEITE = ("<div>Allgemeine Geschäftsbedingungen für den Kauf des KlimaTicket Ö Gültig ab 01.01.2026 … Anhang 3). … "
                     "Anhang 3 Ticketpreise Preise (inkl. 10 % USt) KlimaTicket Ö Classic € 1.400,00 KlimaTicket Ö Jugend € 1.050,00 "
                     "KlimaTicket Ö Classic Familie € 1.540,00 Anhang 4 Entgelte Kündigungsentgelt (ausgenommen außerordentliche Kündigung) = "
                     "ein monatlicher Teilbetrag KlimaTicket Ö Classic € 116,70 KlimaTicket Ö Jugend, Senior, Spezial € 87,50 Mahnentgelt € 10</div>")


def leser(seiten: dict[str, str]):
    gelesen = []

    def lesen(adresse: str) -> str:
        gelesen.append(adresse)
        if adresse not in seiten:
            raise stellen.StelleError("STELLE_HOLEN", "nicht da")
        return seiten[adresse]
    lesen.gelesen = gelesen
    return lesen


BL_SEITEN = {f"{stellen.BL}/tabelle": TABELLE, f"{stellen.BL}/spielplan": RUNDE_7, f"{stellen.BL}/spielplan?spieltag=8": RUNDE_8,
             f"{stellen.BL}/spielplan?spieltag=9": RUNDE_9}


def test_the_next_match_comes_from_the_league_with_the_right_weekday():
    funde, fehler = stellen.lesen_fuer("Wann spielt der LASK als Nächstes?", heute=HEUTE, lesen=leser(BL_SEITEN))
    assert not fehler and len(funde) == 1
    t = funde[0].text
    assert "Nächstes Bundesliga-Spiel von LASK: Sonntag, 11.10.2026, 17:00 Uhr: LASK gegen SK Rapid (8. Runde, Heimspiel)" in t
    assert "Letztes Bundesliga-Spiel: Sonntag, 20.09.2026, 14:30 Uhr: TSV Egger Glas Hartberg gegen LASK, Ergebnis 3:3" in t
    assert "Tabellenführer nach 7 Runden ist SK Rapid mit 18 Punkten" in t
    assert "RZ Pellets WAC" in t and "Cup" in t
    funde, _ = stellen.lesen_fuer("Rapid Spielplan", heute=HEUTE, lesen=leser(BL_SEITEN))
    assert "Nächstes Bundesliga-Spiel von SK Rapid: Sonntag, 11.10.2026, 17:00 Uhr: LASK gegen SK Rapid (8. Runde, Auswärtsspiel)" in funde[0].text
    assert "Samstag, 17.10.2026" in funde[0].text


def test_which_questions_go_to_which_office():
    p = stellen.passend
    assert p("Wer führt gerade die österreichische Bundesliga an?") == ["bundesliga"]
    assert p("LASK Spielplan") == ["bundesliga"] and p("Wann spielt der LASK als Nächstes?") == ["bundesliga"]
    assert p("und Rapid?", "Wann spielt der LASK als Nächstes?") == ["bundesliga"]
    assert p("Trinkst du Red Bull?") == [] and p("Wie wird das Wetter in Tirol?") == [] and p("Wer führt die deutsche Bundesliga an?") == []
    assert p("Wie hoch ist der Leitzins der EZB?") == ["ezb"] and p("Wie hoch ist der Leitzins der Fed?") == []
    assert p("Was kostet das Klimaticket Österreich?") == ["klimaticket"] and p("Was kostet das Klimaticket OÖ?") == []
    assert p("Wie hoch ist das amtliche Kilometergeld in Österreich?") == ["kilometergeld"]
    assert p("Wie funktioniert eine Wärmepumpe?") == []


def test_ecb_rates_ticket_prices_and_a_broken_office_fall_back_to_the_search():
    funde, _ = stellen.lesen_fuer("Wie hoch ist der Leitzins der EZB?", heute=HEUTE, lesen=leser({stellen.EZB: EZB_SEITE}))
    t = funde[0].text
    assert "Seit 16.09.2026 gilt: Hauptrefinanzierungssatz 2,65 %, Einlagensatz 2,50 %" in t and "um 0,25 Prozentpunkte angehoben" in t
    funde, _ = stellen.lesen_fuer("Was kostet das Klimaticket?", heute=HEUTE, lesen=leser({stellen.KLIMATICKET: KLIMATICKET_SEITE}))
    t = funde[0].text
    assert "gültig ab 01.01.2026" in t and "Classic 1.400,00 €" in t and "Classic Familie 1.540,00 €" in t
    assert "monatlicher Teilbetrag ist: Classic 116,70 €" in t and t.index("1.400,00") < t.index("116,70")
    funde, fehler = stellen.lesen_fuer("Wie hoch ist der Leitzins der EZB?", heute=HEUTE, lesen=leser({stellen.EZB: "<p>umgebaut</p>"}))
    assert funde == [] and fehler and "ecb.europa.eu" in fehler[0]


def test_weekdays_next_to_a_date_are_computed():
    t, n = belege.wochentage_berichtigen("Das erste Spiel ist am Sa., 25.09.2026 gegen Altach. Montag, den 26. Oktober 2026 ist frei.", HEUTE)
    assert n == 1 and "am Fr., 25.09.2026" in t and "Montag, den 26. Oktober 2026" in t
    t, n = belege.wochentage_berichtigen("Am Samstag, 11.10. spielt der LASK.", HEUTE)
    assert n == 1 and t == "Am Sonntag, 11.10. spielt der LASK."


def test_a_sentence_with_an_invented_date_or_amount_is_struck():
    quelle = ("Heute ist Donnerstag, der 24.09.2026. Nächstes Bundesliga-Spiel von LASK: Sonntag, 11.10.2026, 17:00 Uhr: LASK gegen SK Rapid. "
              "KlimaTicket Ö Classic 1.400,00 €. Hauptrefinanzierungssatz 2,65 %, Einlagensatz 2,50 %.")
    a = ("Der LASK spielt als Nächstes am Sonntag, 11. Oktober 2026 gegen Rapid. Danach am Di., 28.09.2026 gegen Sturm. "
         "Das Klimaticket kostet 1.400 Euro im Jahr, 109 Euro im Monat. Der Leitzins liegt bei 2,65 %.")
    rest, raus = belege.unbelegte_streichen(a, quelle)
    assert rest == "Der LASK spielt als Nächstes am Sonntag, 11. Oktober 2026 gegen Rapid. Der Leitzins liegt bei 2,65 %."
    assert len(raus) == 2
    assert belege.unbelegte_streichen("Er spielt am 25.09.2026.", quelle) == ("Das weiß ich noch nicht.", ["Er spielt am 25.09.2026."])
    assert belege.rechnet("3 Tuben zu je 9,90 Euro, was kostet das?") and not belege.rechnet("Was kostet das Klimaticket?")


def test_placeholders_never_go_out():
    assert belege.ohne_platzhalter("Liebe Mama, alles Gute! Alles Liebe zum Geburtstag! Dein [Name]") == ("Liebe Mama, alles Gute! Alles Liebe zum Geburtstag!", 1)
    t, n = belege.ohne_platzhalter("Liebe [Name],\nalles Gute.\nDein\n[Dein Name]")
    assert n == 2 and "[" not in t and not t.rstrip().endswith("Dein") and t.startswith("Hallo,")
    assert belege.ohne_platzhalter("Siehe [1] und [Quelle 2].") == ("Siehe [1] und [Quelle 2].", 0)


def test_the_program_checks_after_the_model_and_asks_once_more_when_nothing_is_left():
    quellen = [{"nummer": 1, "art": "nachgeschaut", "text": "LASK gegen SK Rapid am Sonntag, 11.10.2026"}]
    zusatz = "Quelle 1: LASK gegen SK Rapid am Sonntag, 11.10.2026, 17:00 Uhr."
    aufrufe = []

    def nochmal(extra: str) -> str:
        aufrufe.append(extra)
        return "Der LASK spielt am Sonntag, 11.10.2026, um 17:00 Uhr gegen Rapid."
    t, notizen = app_web.belege_anwenden("Der LASK spielt am Sa., 25.09.2026 gegen den WAC.", "Wann spielt der LASK als Nächstes?", zusatz, quellen,
                                        heute=HEUTE, nochmal=nochmal)
    assert t == "Der LASK spielt am Sonntag, 11.10.2026, um 17:00 Uhr gegen Rapid." and len(aufrufe) == 1 and "25.09.2026" in aufrufe[0]
    assert any("neu geantwortet" in n for n in notizen)
    t, notizen = app_web.belege_anwenden("Christian Stocker ist seit dem 3. März 2025 Bundeskanzler.", "Wer ist Bundeskanzler von Österreich?", "", [], heute=HEUTE)
    assert t.startswith("Christian Stocker ist seit dem 3. März 2025") and notizen == []
    t, _ = app_web.belege_anwenden("3 × 9,90 € = 29,70 €.", "3 Tuben zu je 9,90 Euro, was kostet das?", "Heute ist …", [{"nummer": 1, "art": "nachgeschaut", "text": "x"}], heute=HEUTE)
    assert t == "3 × 9,90 € = 29,70 €."


def test_both_answer_paths_use_the_offices_and_the_checks():
    src = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert src.count("self._belege_nachher(") == 1 and "stellen.lesen_fuer(frage, vorher=vorher)" in src
    assert src.index("def _antwort_kern(") < src.index("self._belege_nachher(") < src.index("    def _wiki_darf(self)")
    assert "Bei der zuständigen Stelle nachgeschaut" in src


def test_a_small_decimal_never_covers_a_large_amount():
    quelle = "PKW 0,50 Motorfahrräder 0,25 Mitfahrerinnen 0,15 maximal 30.000 Kilometer pro Kalenderjahr"
    rest, raus = belege.unbelegte_streichen("Das Kilometergeld beträgt 0,50 Euro pro Kilometer. Die Obergrenze liegt bei 15.000 Euro.", quelle)
    assert rest == "Das Kilometergeld beträgt 0,50 Euro pro Kilometer." and len(raus) == 1
    assert 15.0 not in belege.zahlenwerte("0,15") and 30000.0 in belege.zahlenwerte("30.000")
