# SPDX-License-Identifier: AGPL-3.0-or-later
import nachschauen as n


def _quellen(zeilen):
    text = "\n".join(f"{i + 1}. https://www.youtube.com/watch?v={v} – „{t}“" for i, (v, t) in enumerate(zeilen))
    return [{"titel": n.SUCHERGEBNISSE_TITEL, "text": text}]


def _nummern(zeilen, frage):
    return [v["nummer"] for v in n.videos_aus_quellen(_quellen(zeilen), frage)]


def test_kurzname_ausgeschrieben_im_titel():
    assert _nummern([("BBBBBBBBBBB", "Grand Theft Auto VI Launch Trailer")], "Zeig mir den launch Trailer von GTA VI") == ["BBBBBBBBBBB"]
    assert _nummern([("DDDDDDDDDDD", "League of Legends Worlds Finale Highlights")], "Zeig mir LoL Worlds Finale Highlights") == ["DDDDDDDDDDD"]


def test_falsche_teilnummer_zaehlt_nie():
    zeilen = [("AAAAAAAAAAA", "Grand Theft Auto V Launch Trailer"), ("BBBBBBBBBBB", "Grand Theft Auto VI Launch Trailer")]
    assert _nummern(zeilen, "Zeig mir den launch Trailer von GTA VI") == ["BBBBBBBBBBB"]
    assert _nummern([("AAAAAAAAAAA", "Grand Theft Auto V Launch Trailer")], "Zeig mir den Trailer von GTA VI") == []


def test_ziffer_und_roemisch_gleich():
    assert _nummern([("CCCCCCCCCCC", "GTA 6 Trailer 2")], "zeig mir den trailer von gta vi") == ["CCCCCCCCCCC"]


def test_teilnummern():
    assert n._teilnummern("Zeig mir Top 10 Tipps für Minecraft") == set()
    assert n._teilnummern("Teil 3 der Doku") == set()
    assert n._teilnummern("FIFA 26 Gameplay") == {26}
    assert n._teilnummern("gta vi trailer") == {6}


def test_link_mit_seitentitel_ist_keine_uebernahme():
    import belege
    fremd = ["Der neue Rockstar-Titel von Rockstar Games erscheint bald und wird von vielen Fans erwartet."]
    antwort = ("Du findest ihn auf der offiziellen Seite unter:\n"
               "https://www.rockstargames.com/VI – „Der neue Rockstar-Titel von Rockstar Games erscheint bald und wird von vielen Fans erwartet.“")
    assert belege.woertliche_saetze(antwort, fremd) == []
    assert belege.woertliche_saetze("Der neue Rockstar-Titel von Rockstar Games erscheint bald und wird von vielen Fans erwartet.", fremd)


def test_neufassung_ohne_adresse_gilt_nicht():
    import app_web
    fremd = ["Den Trailer gibt es jetzt auf der Seite von Rockstar Games zu sehen, mit vielen neuen Szenen aus Vice City."]
    alt = "Den Trailer gibt es jetzt auf der Seite von Rockstar Games zu sehen, mit vielen neuen Szenen aus Vice City: https://www.rockstargames.com/VI"
    text, notizen, ersetzt = app_web.eigene_worte(alt, fremd, lambda saetze, en: {0: "Rockstar zeigt im Trailer neue Szenen aus Vice City."})
    assert "https://www.rockstargames.com/VI" in text or text == "Das weiß ich noch nicht."
    assert not ersetzt


def test_bisherige_faelle_bleiben():
    assert _nummern([("EEEEEEEEEEE", "Enshrouded Einsteiger Guide")], "Zeig mir einsteiger Guide Video zu Enshrouded") == ["EEEEEEEEEEE"]
    assert _nummern([("FFFFFFFFFFF", "Minecraft Let's Play Folge 1")], "Zeig mir Gameplay zu Enshrouded") == []
