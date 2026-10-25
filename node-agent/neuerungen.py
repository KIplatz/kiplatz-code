# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations


def dank(satz: str, wer: str, art: str = "Meldung") -> str:
    wer = " ".join(str(wer or "").split())[:40]
    if not wer or "@" in wer:
        return satz
    zusatz = "Umgesetzt dank einer Idee von" if art == "Idee" else "Behoben dank einer Meldung von"
    return f"{satz.rstrip()} {zusatz} {wer.rstrip('.')}."


NEUERUNGEN: dict[str, list[str]] = {
    "2026-10-25p": [
        "Schickst du deine Frage ab, während die App ein Foto noch liest, geht sie jetzt von selbst los, sobald das Foto gelesen ist. Fotos liest die App deutlich schneller, und was dabei passiert, steht direkt über dem Eingabefeld. Steht auf einem Foto kein Text, sagt sie dir das nach wenigen Sekunden.",
    ],
    "2026-10-25q": [
        "Stellst du auf kiplatz.at eine Frage, ist sie jetzt als erste dran, vor allen anderen. Und während der PC die Antwort erarbeitet, siehst du auf der deutschen Seite gleich, was er gerade tut, etwa dass er im Internet nachschaut.",
    ],
    "2026-10-25o": [],
    "2026-10-25n": [],
    "2026-10-25m": [],
    "2026-10-25l": [],
    "2026-10-25k": [],
    "2026-10-25j": [
        "Die Seitenleiste mit deinen Gesprächen ziehst du jetzt mit der Maus breiter oder schmaler, im Programm und in der App am großen Bildschirm, damit lange Titel ganz zu sehen sind. Ein Doppelklick auf den Rand stellt die normale Breite wieder her, KIplatz merkt sich deine Breite.",
    ],
    "2026-10-25i": [
        "Fotos, die quer oder auf dem Kopf liegen, liest die App jetzt richtig: Ist sich die Texterkennung unsicher, dreht sie das Foto und liest es noch einmal, etwa die Seite aus dem Schulbuch, die du quer fotografiert hast.",
        "Schickst du ein Foto oder eine Datei mit einem Auftrag, etwa „Schreibe mir Punkt 1“ zur Seite aus dem Schulbuch, „Übersetze das“ oder „Fasse den Brief zusammen“, erledigt KIplatz genau das aus deinem Anhang, statt im Internet zu suchen. Und es antwortet immer in der Sprache, in der du schreibst, egal welche Sprache auf dem Foto steht.",
        "Fragst du nach dem neuen Buch einer Autorin, der neuen Staffel einer Serie, dem neuesten Album oder einer neuen Kollektion, sagt dir KIplatz jetzt beides: was zuletzt erschienen ist und was als Nächstes kommt, jeweils mit Datum, und ob die deutsche Ausgabe später erscheint.",
        "KIplatz prüft jetzt jedes Datum in einer Antwort gegen den heutigen Tag. Was schon erschienen ist, steht nie mehr so da, als käme es erst, in jeder Sprache.",
    ],
    "2026-10-25h": [
        "Der Preisvergleich funktioniert jetzt in jedem Land und jeder Sprache: Fragst du auf Italienisch, Französisch, Spanisch oder Japanisch nach dem günstigsten Preis, sucht KIplatz bei den Händlern dort und zeigt die Preise in der Währung des Landes, ob Euro, Dollar, Pfund, Franken oder Yen.",
        "Fragst du nach günstigeren Alternativen, etwa zu deinem Reifen auf dem Foto, zeigt die Tabelle andere Produkte in derselben Größe, jedes mit seinem Namen. Und als Händler zählt nur, wer wirklich verkauft, keine Nachrichtenseite und kein Preisverlauf. Neu, wir verbessern es laufend.",
    ],
    "2026-10-25g": [
        "Fragst du, wo ein bestimmtes Gerät oder ein Reifen am günstigsten ist, liest KIplatz jetzt die Händlerlisten der Preisvergleiche und die Seiten der Shops selbst. In der Tabelle steht nur, was es genau in deiner Größe oder Variante gibt, neu und nicht gebraucht, und daneben, wo der Preis geprüft wurde.",
        "Findet KIplatz für genau dein Modell keinen Händler mit Preis, sagt es dir das ehrlich und nennt dir Preisvergleiche zum Weitersuchen, statt einen Preis für etwas anderes hinzuschreiben. Neu, wir verbessern es laufend.",
    ],
    "2026-10-25f": [
        "Hängst du ein Foto oder mehrere an und fragst nur „Wo ist das günstiger?“ oder „Welcher hat die besten Tests?“, sucht KIplatz jetzt genau die Dinge auf deinen Fotos, jedes für sich, auch nach einer Rückfrage nach dem Land.",
    ],
    "2026-10-25e": [
        "Neu im Programm: Unter „Ansicht“ machst du alles größer oder kleiner, mit Strg und Plus, Strg und Minus oder Strg und 0. Das Fenster ordnet sich dabei neu, nichts steht über und nichts wird abgeschnitten. KIplatz merkt sich die Größe.",
        "Die Menüleiste im Programm ist neu geordnet, in Datei, Bearbeiten, Ansicht, Gehe zu und Hilfe, mit den Tastenkürzeln daneben und einem Häkchen bei allem, was eingeschaltet ist. Dazu kommen Vollbild mit F11 und ein neues Gespräch mit Strg und N.",
    ],
    "2026-10-25d": [
        "Neu: Lass dir von KIplatz einen Lebenslauf, ein Anschreiben oder einen Brief schreiben und sichere die Antwort gleich als PDF, in der App über „Mehr zu dieser Antwort“, im Programm über „…“ und „Drucken oder als PDF“. Ohne Wasserzeichen, und nichts geht hinaus.",
    ],
    "2026-10-25c": [
        "Neu im Programm: Über das Plus fügst du mehrere PDFs am PC zu einer zusammen, etwa Anschreiben, Lebenslauf und Zeugnisse für eine Bewerbung. Die Dateien verlassen deinen PC dabei nicht.",
        "Neu in der App: Auch am Handy fügst du über das Plus mehrere PDFs zu einer zusammen und sicherst oder teilst sie gleich. Die Dateien verlassen dein Handy dabei nicht.",
    ],
    "2026-10-25b": [
        "Neu: Frag „Betrifft die KI-Verordnung meinen Betrieb?“, und KIplatz sagt dir nach vier kurzen Angaben, was davon jetzt für dich gilt, was erst später kommt und was du nicht brauchst, etwa einen Kurs oder ein Zertifikat.",
        "Fehlt bei einer Frage zur Flugverspätung nur der Abflug oder nur das Ziel, fragt KIplatz jetzt nur danach.",
    ],
    "2026-10-25a": [
        "Neu: Frag „Mein Flug von Wien nach London war 4 Stunden verspätet, was steht mir zu?“, und KIplatz rechnet dir nach der EU-Verordnung für Fluggastrechte aus, ob dir 250, 400 oder 600 € zustehen. Fehlt die Strecke oder die Verspätung, fragt KIplatz kurz nach.",
    ],
    "2026-10-24s": [
        "Neu: Häng eine Excel-Datei an, und KIplatz liest jede Tabelle darin, mit Datum statt Zahlencode. Frag dann zum Beispiel, wofür du am meisten ausgegeben hast. Das gilt in der App, im Programm und auf kiplatz.at.",
    ],
    "2026-10-24r": [
        "Neu: Frag „Darf KI meine Website lesen?“ mit der Adresse dazu, und KIplatz sagt dir je KI-Programm, ob es die Seite für Antworten oder fürs Training lesen darf, so wie es in der robots.txt steht.",
        "Antworten, die KIplatz ohne KI-Modell selbst erarbeitet, etwa Rechnungen oder Prüfungen, stehen auf der Website jetzt auch so da.",
    ],
    "2026-10-24q": [
        "Neu: KIplatz prüft deinen Prompt. Schreib „Prüf meinen Prompt:“ und füge deine Anweisung an, dann siehst du sofort, welche von acht Angaben fehlen, etwa Rolle, Länge oder Ton, und ob persönliche Daten drinstehen.",
    ],
    "2026-10-24p": [
        "Sagt eine Antwort, auf welchen Wochentag ein Datum fällt, rechnet KIplatz das jetzt selbst nach und berichtigt einen falschen Tag.",
    ],
    "2026-10-24o": [],
    "2026-10-24n": [
        "Vergleichst du Strom, Gas, Flüge, Zugtickets oder Hotels, fragt KIplatz zuerst nach dem, wovon der Preis abhängt: bei Strom nach Postleitzahl und Jahresverbrauch, bei Reisen nach dem Datum. Dann vergleicht es mit Preisen, die für dich gelten, statt mit Beispielrechnungen.",
        "Bei Strom und Gas in Österreich steht unter dem Vergleich jetzt auch der Link zum amtlichen Tarifkalkulator der E-Control.",
        "Der Preisvergleich sucht jetzt in dem Land, in dem du kaufst, von Deutschland und Italien bis Großbritannien und den USA. Steht das Land nicht in deiner Frage, fragt KIplatz kurz danach.",
    ],
    "2026-10-24m": [],
    "2026-10-24l": [
        "Längen, Strecken und Gewichte prüft KIplatz jetzt genauer: Eine Angabe wie „26 Minuten“ bleibt nur stehen, wenn eine Quelle wirklich diese Dauer nennt, nicht bloß irgendwo die Zahl 26.",
    ],
    "2026-10-24k": [],
    "2026-10-24j": [
        "Videos mit Kurznamen erscheinen jetzt auch als Karte: Wer nach dem Trailer von „GTA VI“ fragt, bekommt das Video „Grand Theft Auto VI“, und nie eines zu GTA V. Ein Link in der Antwort bleibt stehen, auch wenn KIplatz den Satz daneben in eigenen Worten schreibt.",
    ],
    "2026-10-24i": [
        "Der Preisvergleich findet jetzt die echten Shops: KIplatz liest jeden Preis so, wie ihn der Shop selbst für Suchmaschinen angibt, und zeigt jeden Händler mit seinem Preis. Preisvergleichsseiten und Zahlungsdienste stehen nicht mehr als Anbieter in der Tabelle.",
        "Hast du ein Angebot als Foto angehängt, steht es jetzt als eigene Zeile in der Tabelle, mit Baujahr, wenn es draufsteht. So siehst du gleich, ob es woanders günstiger geht.",
        "Sperrt ein Shop nur das Sammeln für KI-Training, liest KIplatz seine Seite für deine Frage, lernt aber nie daraus. Wer KIplatz das Lesen verbietet, wird weiter nicht gelesen.",
    ],
    "2026-10-24h": [
        "Steht ein Video als Karte unter der Antwort, schreibt KIplatz nicht mehr darüber, es könne das Video hier nicht zeigen.",
    ],
    "2026-10-24g": [
        "Willst du ein Video sehen, etwa „Zeig mir Gameplay zu Enshrouded“, zeigt KIplatz es dir direkt in der Antwort, mit Vorschaubild. Abgespielt wird erst nach deinem Klick, vorher geht nichts an YouTube. Das gilt in der App, im Programm und auf kiplatz.at.",
        "Fragst du nach dem günstigsten Anbieter, vergleicht KIplatz jetzt mehrere Shops und zeigt dir eine Tabelle nach Preis. Jeder Preis muss auf der Seite dieses Shops stehen, sonst fliegt die Zeile raus. Die Funktion ist neu, wir verbessern sie laufend.",
        "Häng ein Foto oder ein PDF an und sag „such das im Internet“: KIplatz liest den Text darauf und sucht genau nach dem, was dort steht, etwa nach dem Reifen auf deinem Screenshot.",
    ],
    "2026-10-24f": [],
    "2026-10-24e": [],
    "2026-10-24d": [],
    "2026-10-24c": [],
    "2026-10-24b": [],
    "2026-10-24a": [],
    "2026-10-23v": [],
    "2026-10-23u": [],
    "2026-10-23t": [],
    "2026-10-23s": [],
    "2026-10-23r": [],
    "2026-10-23q": [],
    "2026-10-23p": [],
    "2026-10-23o": [],
    "2026-10-23n": [],
    "2026-10-23m": [],
    "2026-10-23l": [],
    "2026-10-23k": [],
    "2026-10-23j": [],
    "2026-10-23i": [],
    "2026-10-23h": [],
    "2026-10-23g": [],
    "2026-10-23f": [],
    "2026-10-23e": [],
    "2026-10-23d": [],
    "2026-10-23c": [],
    "2026-10-23b": [],
    "2026-10-23a": [],
    "2026-10-22h": [],
    "2026-10-22g": [],
    "2026-10-22f": [],
    "2026-10-22e": [],
    "2026-10-22d": [],
    "2026-10-22c": [],
    "2026-10-22b": [],
    "2026-10-22a": [],
    "2026-10-21d": [],
    "2026-10-21c": [],
    "2026-10-21b": [
        "Bei „Ja, live nachprüfen“ sucht KIplatz jetzt immer im Internet, auch wenn ein Berg oder Ort mit diesem Namen schon auf der Karte steht.",
    ],
    "2026-10-21a": [],
    "2026-10-20d": [],
    "2026-10-20c": [
        "Endet eine Antwort mit einer Frage wie „Gibt es noch etwas dazu?“, nimmt KIplatz sie jetzt weg. Eine Rückfrage, weil eine Angabe zur Frage nötig ist, bleibt stehen.",
        "In der App führt Zurückwischen jetzt immer ins vorherige Menü, nicht mehr auf die Startseite, und „Meine KI“ steht nicht mehr über der Fragezeile.",
    ],
    "2026-10-20b": [
        "Auf Linux und am Mac mit Apple-Chip gibt es jetzt den Helfer: ohne Fenster arbeitet dein Rechner still für die Community mit.",
        "Der Helfer läuft als Dienst deines Benutzers, nie mit erhöhten Rechten, und bekommt dieselben unterschriebenen Updates wie das Programm.",
        "Der Quelltext des Helfers ist offen wie der von Programm und App, und die Anleitung mit allen Befehlen steht auf kiplatz.at/linux-und-mac.",
        "Dein PC kommt jetzt mit deinem KIplatz-Konto zur Community dazu, wie die App: im Programm „Mit KIplatz-Konto dazukommen“ anklicken, im Browser anmelden und „Einen neuen PC verbinden?“ bestätigen. Einen Code brauchst du dafür nicht mehr.",
        "Am Linux-Rechner oder Mac zeigt „kiplatz-helfer status“ jetzt, was der Helfer gerade tut: ob er online ist, welches Modell läuft, wie viele Fragen er beantwortet hat, seine Credits und mit wem er seit dem Start verbunden war. Dazu schreibt er ein Protokoll in klaren Sätzen.",
    ],
    "2026-10-20a": [
        "Unter jeder Antwort steht jetzt richtig, wo nachgeschlagen wurde. Hat ein anderer PC der Community geantwortet, sagt KIplatz das, statt „auf diesem Gerät“.",
        "Die englische Oberfläche ist vollständiger: Fehlermeldungen und Hinweise zum Stand des Programms kommen jetzt auf Englisch, große Zahlen mit Komma statt Punkt.",
        "Deine Daten liegen jetzt im Ordner KIplatz unter AppData. Das Programm zieht sie beim Update einmal selbst dorthin um, nichts geht verloren.",
    ],
    "2026-10-19e": [],
    "2026-10-19d": [],
    "2026-10-19c": [],
    "2026-10-19b": [],
    "2026-10-19a": [
        "Einleitung und Namensprüfung aus der Wikipedia-Kopie kommen jetzt auch, während das Gerät im Hintergrund an der Kopie arbeitet; vorher fielen sie dabei still aus.",
        "Das Bedeutungs-Modell für deine Frage wartet nicht mehr, bis ein großer Download der Rechenarbeit fertig ist.",
        "Fragst du nach einem Termin mit Jahreszahl oder „this year“, antwortet KIplatz aus dem Kalender statt mit „nicht sicher“.",
    ],
    "2026-10-18r": [],
    "2026-10-18q": [
        "Wann in den USA, in Kanada, Großbritannien, Australien oder Neuseeland die Uhr umgestellt wird, rechnet KIplatz jetzt selbst aus, und fragst du nach einem Termin „heuer“ oder „this year“, bekommst du den Tag dieses Jahres, auch wenn er schon vorbei ist.",
    ],
    "2026-10-18p": [
        "Fällt bei einer Anleitung oder einem Rezept ein Schritt bei der Prüfung weg, gibt KIplatz die Antwort nicht mehr mit einer Lücke aus, sondern schreibt sie neu oder sucht weiter.",
    ],
    "2026-10-18o": [
        "Wer KIplatz auf Englisch nutzt, bekommt jetzt alles auf Englisch: den Morgenbericht mit Schlagzeilen aus dem eigenen Land, die zehn Skill-Vorlagen und das Gedächtnis mit „Remember: …“, und vorgelesen wird mit einer englischen Stimme.",
        "Englische Antworten klingen jetzt natürlich statt Wort für Wort übersetzt, und bei englischen Fragen zu Ländern außerhalb des deutschen Sprachraums sucht KIplatz auf Englisch und findet so die Seiten der Behörden dort.",
        "Knöpfe und Hinweise heißen auf Englisch jetzt in Programm, App und Website gleich und klingen natürlich.",
    ],
    "2026-10-18n": [
        "Steht ein Satz fast wörtlich auf einer Seite oder in der Wikipedia, schreibt KIplatz genau diesen Satz in eigenen Worten neu, statt die Antwort zu kürzen, und das jetzt auch bei Antworten auf Englisch.",
    ],
    "2026-10-18m": [],
    "2026-10-18l": [],
    "2026-10-18k": [
        "„Frag dein Zuhause“ versteht jetzt auch englische Fragen wie „Where is my CV?“: Antwort, Dateiart und Ordner kommen auf Englisch, und die Karte am PC ist ganz auf Englisch.",
    ],
    "2026-10-18j": [],
    "2026-10-18i": [],
    "2026-10-18h": [
        "Fragen zu Einreise, Visum, Regeln und Ämtern beantwortet KIplatz jetzt in jedem Land der Welt mit dem, was die Behörden dort aktuell sagen, und Feiertage erkennt es auch beim Namen, etwa Memorial Day.",
        "Englische Datumsangaben auf Webseiten zählen jetzt als Beleg, eine Jahreszahl muss zur Sache passen, und auf der Startseite passen die Farben je Satz zum gezeigten Text.",
    ],
    "2026-10-18g": [
        "Englische Fragen kommen jetzt sauber übersetzt bei KIplatz an: Fragst du nach dem Tempolimit oder nach einem Rezept, bekommst du die Antwort statt „I don't know yet“.",
        "Rezepte behalten ihre Mengen, auch wenn KIplatz zum Gericht nur nebenbei etwas gefunden hat, und Listen bleiben ordentlich, wenn ein unsicherer Satz wegfällt.",
        "Was nach seiner Stadt heißt, findet KIplatz jetzt beim Namen: „Wer hat das Riesenrad in Wien gebaut?“ führt zum Wiener Riesenrad.",
        "Die Feiertage eines deutschen Bundeslands nennt KIplatz jetzt vollständig und nur mit den Hinweisen, die für dieses Land gelten.",
        "Auf Englisch bleiben Namen von Apotheken, Lokalen und Straßen, wie sie sind, damit du sie vor Ort findest.",
    ],
    "2026-10-18f": [
        "Wer KIplatz auf Englisch nutzt, kann sein Konto jetzt löschen: zur Bestätigung gilt „delete“ genauso wie „löschen“.",
    ],
    "2026-10-18e": [
        "Auf Geräten ohne passende Grafikkarte steht oben jetzt „Community antwortet“ statt „KI aus“, und die Einstellungen sagen, warum die eigene KI dort am besten aus bleibt.",
    ],
    "2026-10-18d": [
        "Feiertage anderer Länder nennt KIplatz jetzt vollständig und mit ihrem deutschen Namen.",
        "Eine Antwort, an der KIplatz Sätze weglassen musste, gibt es nicht mehr fertig für alle: die nächste Frage bekommt eine frisch erarbeitete.",
        "Beispiele wie „zum Beispiel GMX oder Gmail“ bleiben in der Antwort, wenn es die Namen wirklich gibt.",
        "Bei gleichnamigen Orten meint KIplatz die bekannte Stadt, außer du nennst das Land: „Apotheken in Passau“ findet jetzt die Stadt Passau.",
    ],
    "2026-10-18c": [
        "Termine wie den ersten Advent, Ostern oder die Zeitumstellung rechnet KIplatz jetzt selbst aus, für das Jahr, nach dem du fragst.",
        "Feiertage kennt KIplatz jetzt weltweit: Fragst du nach Frankreich oder den USA, bekommst du die Feiertage dieses Landes, nicht die österreichischen.",
        "Erklärungen behalten ihre Beispiele, und lässt KIplatz einen unsicheren Satz weg, bleibt keine Lücke mehr in der Antwort.",
        "Orte in Deutschland: Dein PC liest die Karte jetzt auch dann fertig ein, wenn du zwischendurch an ihm arbeitest.",
    ],
    "2026-10-18b": [
        "Antworten auf Alltagsfragen verlieren seltener Sätze: Gewöhnliche Wörter wie „Eimer“ oder „Passwort“ hält KIplatz nicht mehr für erfundene Namen.",
    ],
    "2026-10-18a": [],
    "2026-10-17n": [],
    "2026-10-17m": [],
    "2026-10-17l": [
        "Kurze Fragen in Kleinschreibung wie „erklär mir die inflation“ bekommen gleich eine Antwort statt der Rückfrage, worauf du dich beziehst.",
        "Fragen wie „Wer war der erste Mensch im Weltall?“ beantwortet KIplatz wieder, auch wenn die Quelle ein anderes Wort wie „Weltraum“ verwendet.",
        "Alltagsfragen wie „Wie lange muss ich ein weiches Ei kochen?“ oder „Wie kann ich langfristig abnehmen?“ bekommen wieder eine Antwort mit dem Wissen aus der Wikipedia.",
        "Der Liveticker ist wieder draußen. Fragen nach Spielständen sucht KIplatz im Internet, und Alltagsfragen gelten nicht mehr als Sportfragen.",
        "Hängt eine Antwort, holt sich KIplatz ein Update trotzdem nach spätestens zehn Minuten.",
    ],
    "2026-10-17k": [
        "Eine Frage bleibt nicht mehr minutenlang hängen, während dein PC Wikipedia-Daten von anderen PCs der Community übernimmt.",
    ],
    "2026-10-17j": [],
    "2026-10-17i": [],
    "2026-10-17h": [],
    "2026-10-17g": [],
    "2026-10-17f": [
        "Fragt jemand nach einer Person, über die keine gefundene Seite etwas sagt, schreibt KIplatz nicht über jemand anderen, sondern sagt ehrlich, dass es nichts Verlässliches weiß.",
    ],
    "2026-10-17e": [
        "Antworten auf Alltagsfragen kommen oft schneller: KIplatz streicht keinen richtigen Satz mehr, nur weil darin ein gewöhnliches Wort wie „Einstellung“ oder „Familie“ steht.",
    ],
    "2026-10-17d": [],
    "2026-10-17c": [],
    "2026-10-17b": [
        "Fragen wie „Was soll ich tun, wenn die Sicherung immer wieder rausfliegt?“ bekommen jetzt gleich eine Antwort statt Rückfragen.",
        "Englische Fragen nach österreichischen Wörtern wie „What does 'Feber' mean?“ kommen jetzt richtig an und bekommen die richtige Bedeutung.",
    ],
    "2026-10-17a": [],
    "2026-10-16l": [],
    "2026-10-16k": [],
    "2026-10-16j": [
        "Fängt ein Gespräch mit „Mach es kürzer“ oder „Ist das gesund?“ an, fragt KIplatz sofort nach, worum es geht, statt etwas zu erraten.",
    ],
    "2026-10-16i": [
        "Englische Fragen mit einem deutschen Wort, etwa „What are Erdäpfel?“ oder „Up to what age do children travel free with ÖBB?“, bekommen jetzt eine englische Antwort.",
    ],
    "2026-10-16h": [
        "KIplatz kennt österreichische Wörter: Wer fragt, was Paradeiser, Feber, ein Kasten oder ein Haberer ist, bekommt die richtige Bedeutung und das schneller als bisher.",
    ],
    "2026-10-16g": [
        "Fragen wie „Wer spielt die Hauptrolle in Titanic?“, „Warum gibt es Gewitter?“, „Wie erstelle ich eine E-Mail-Adresse?“ oder „Wie viele Tage sind es vom 1. März bis zum 1. Juni?“ bekommen jetzt eine richtige Antwort statt einer falschen Rückfrage.",
    ],
    "2026-10-16f": [],
    "2026-10-16e": [
        "Fragen wie „Wie funktioniert das Lotto in Österreich?“ bekommen wieder eine echte Antwort statt einer Erklärung, wie KIplatz arbeitet.",
    ],
    "2026-10-16c": [],
    "2026-10-16b": [],
    "2026-10-16a": [
        "Neue Fassungen unserer KI werden jetzt verlässlich nachts geprüft, bevor sie zu euch kommen; fällt eine Nacht aus, wird die Prüfung nachgeholt.",
    ],
    "2026-10-15j": [
        "Erfundene Fachbegriffe wie „Mertens-Lindauer-Theorem“ erkennt KIplatz jetzt auch, wenn jeder Teil echt klingt; es sucht dann im Internet und sagt ehrlich, wenn es nichts findet.",
    ],
    "2026-10-15i": [
        "Geprüfte Antworten sind schneller: der zweite Blick auf Zahlen und Namen liest die Quellen nicht mehr jedes Mal neu ein.",
    ],
    "2026-10-15h": [
        "Muss KIplatz eine Antwort neu schreiben, schreibt es sie gleich in eigenen Worten; das spart einen Durchgang und es fallen keine Sätze mehr weg.",
        "In den Details zur Antwort steht jetzt, wie lange jeder Schritt gedauert hat, etwa die Suche im Internet und das Prüfen.",
    ],
    "2026-10-15g": [
        "Fragen nach Preisen und Regeln erarbeitet immer ein PC neu, statt eine gespeicherte Antwort zu nehmen; Preise und Regeln ändern sich.",
        "Auch Fragen wie „Tempolimit auf deutschen Autobahnen“ sucht KIplatz jetzt gleich im Internet, mit den amtlichen Stellen vorn.",
    ],
    "2026-10-15f": [
        "Bei Fragen nach Regeln liest KIplatz zuerst amtliche Stellen und Automobilclubs, etwa oesterreich.gv.at oder den ÖAMTC.",
        "Fragst du nach einem Land, fallen Seiten aus einem anderen Land weg, auch wenn sie das Land nicht beim Namen nennen; so kommt keine deutsche Regel mehr in eine Antwort über Österreich.",
    ],
    "2026-10-15e": [
        "Einfügen über die rechte Maustaste funktioniert jetzt zuverlässig; KIplatz drückt dafür Strg+V für dich und liest die Zwischenablage nicht selbst.",
        "Bei Fragen nach einer Regel nennt KIplatz zuerst, was gilt, und bei Preisen jede Variante, etwa 7 Tage, Monat und Jahr.",
    ],
    "2026-10-15d": [
        "Fragen nach Regeln, Pflichten und Fristen sucht KIplatz jetzt immer im Internet, auch wenn im eigenen Wissen schon etwas Ähnliches steht; ohne Quelle nennt es keine Regel aus dem Gedächtnis.",
        "Muss KIplatz einen Satz einer Antwort streichen, schreibt es die Antwort einmal ganz neu; ein Rest ohne Anfang wird nie ausgegeben.",
        "Preise nennt KIplatz nur aus Seiten des laufenden Jahres.",
        "Im Programmfenster öffnet die rechte Maustaste jetzt ein Menü mit Rückgängig, Ausschneiden, Kopieren, Einfügen und Alles auswählen.",
    ],
    "2026-10-15c": [
        "Eine Antwort erscheint jetzt einmal und fertig geprüft; ein Entwurf, der sich danach noch ändert, steht nicht mehr im Fenster, Schritt und Sekunden zeigen, woran KIplatz arbeitet.",
        "Fragen nach Regeln, Pflichten und Fristen, etwa ab wann Winterreifen nötig sind, sucht KIplatz gleich im Internet, für jedes Land.",
        "Findet die erste Suche nichts Verlässliches, sucht KIplatz von selbst ein zweites Mal mit eigenen Suchwörtern, ohne dass du „Ja, live nachprüfen“ drücken musst.",
    ],
    "2026-10-15b": [
        "Rechen- und Alltagsfragen wie Umrechnungen, Prozent oder Backzeiten bekommen wieder eine Antwort, wo vorher manchmal „Das weiß ich noch nicht“ stand.",
        "Nennt ein Satz eine Quelle beim Namen, schreibt KIplatz ihr nichts mehr zu, was nur in einer anderen Quelle steht.",
        "Fragst du nach einem bestimmten Land, zählen Fundstellen über ein anderes Land nicht mehr als Quelle, für Österreich genauso wie für Deutschland, die Schweiz, Großbritannien oder die USA.",
        "Einen Preis nennt KIplatz nur noch mit einer aktuellen Quelle, nie aus dem Gedächtnis.",
    ],
    "2026-10-15a": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-14c": [
        "Unter einer belegten Antwort stehen jetzt alle Quellen, aus denen sie stammt, auch wenn im Text keine Quellennummer dabeisteht.",
        "Klappt das Abholen einer Antwort aus der Community einmal nicht, versucht es dein PC gleich noch einmal. Vorher hat er die fertige Antwort verworfen und selbst geantwortet, und das konnte Minuten dauern.",
        "Fragen nach Orten in deiner Nähe nutzen wieder deinen Wohnort aus den drei Fragen beim ersten Start.",
    ],
    "2026-10-14b": [
        "Die ersten 100 PCs, die für andere mithelfen, sind Gründungsmitglieder: Die Nummer steht in der Bestenliste, in deiner Geräteliste und als Abzeichen im Platzl, und sie bleibt.",
    ],
    "2026-10-14a": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-13f": [
        "Spielstände nennen die Vereine jetzt so, wie wir sie sagen: Inter Mailand, AC Mailand, Bayern München, Rapid Wien, und die Ligen heißen Deutsche Bundesliga oder Europameisterschaft.",
    ],
    "2026-10-13e": [
        "Der Liveticker versteht jetzt auch „Barca Live Spielstand“, „CL“ oder klein geschriebene Vereinsnamen und findet Bayern München, Rapid oder Salzburg auch dann, wenn die Datenbank sie anders schreibt.",
    ],
    "2026-10-13d": [
        "Der Server kann neue Funktionen einzeln freischalten; das Programm zeigt sie erst dann.",
    ],
    "2026-10-13c": [
        "Der Quelltext von Programm und App ist offen, Lizenz GNU AGPL 3. Unter „Über KIplatz“ im Programm und in den Einstellungen der App steht, wo du ihn findest: kiplatz.at/quelltext.",
        "Die Probefrage auf der Website darf mehr, je mehr PCs gerade online sind: Besucher ohne Konto bekommen pro Tag und alle zusammen pro Stunde so viele Fragen, wie die Community gerade hergibt.",
    ],
    "2026-10-13b": [
        "KIplatz hat jetzt einen Liveticker: Frag nach dem Spielstand, und du bekommst den Livescore aus Fußball, Eishockey, NFL und NBA, dazu Spielpläne, Ergebnisse und die nächsten Formel-1-Termine.",
        "Zum Beispiel: „Wie steht es bei Sturm Graz?“, „Wer spielt heute in der Bundesliga?“ oder „Wann ist das nächste Formel-1-Rennen?“ Die Antwort sagt dazu, von wann der Stand ist.",
    ],
    "2026-10-13a": [
        "„Meine KI“ kennt jetzt Fachgebiete: Wer Programmieren, Web oder KI am eigenen PC wählt, bekommt bei passenden Fragen zuerst Fundstellen aus geprüften Quellen, der Python-Dokumentation, den MDN Web Docs und der Ollama-Dokumentation, mit der Quelle unter der Antwort.",
    ],
    "2026-10-12d": [
        "Antwortest du auf die Rückfragen zu einem Brief oder einer Rechnung mit „weiter“, schreibt KIplatz ihn jetzt wirklich, mit Lücken für das Offene.",
    ],
    "2026-10-12c": [
        "Auch bei Unbekanntem sagt KIplatz jetzt ehrlich, wenn die Suche nichts findet.",
    ],
    "2026-10-12b": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-12a": [
        "Neu ist das Wiki: Du schlägst eine bessere Antwort mit Quelle vor, andere stimmen ab, und ab 5 Ja gilt sie für alle.",
    ],
    "2026-10-11f": [
        "KIplatz rechnet jetzt auch für Amerika und England: km/h in mph, Meilen, Pfund, Unzen, Gallonen, Fahrenheit, Dollar und Pfund, und antwortet auf Englisch, wenn man auf Englisch fragt. In der Küche gehen jetzt Cups, Unzen und Backofen-Grad.",
    ],
    "2026-10-11e": [
        "Der Hinweis auf einen berichtigten Tippfehler steht bei Aufzählungen jetzt in einer eigenen Zeile unter der Antwort.",
    ],
    "2026-10-11d": [
        "Findet die Internetsuche wirklich nichts, sagt KIplatz das jetzt ehrlich.",
    ],
    "2026-10-11c": [
        "Tippt man eine Einheit falsch, etwa „milimeter“, liest KIplatz sie trotzdem richtig und sagt es dazu. Und eine richtig gerechnete Umrechnung verschwindet nicht mehr hinterher durch den Satz „Das weiß ich noch nicht“.",
    ],
    "2026-10-11b": [
        "KIplatz rechnet jetzt noch mehr selbst und genau: Uhrzeit in anderen Orten, Gleichungen, Zinsen und Kreditrate, Einkauf mit Rückgeld, Spritkosten, Trinkgeld, Rezepte und Brutto zu Netto in Österreich (ein Überschlag).",
    ],
    "2026-10-11a": [
        "KIplatz rechnet jetzt selbst und genau, statt zu raten. „789 mm in dm, cm und mm“, „3/4 + 1/6“, „20 % MwSt auf 120 €“, „100 Euro in Dollar“ oder „Wie viele Tage bis Weihnachten?“ beantwortet es sofort und richtig, meist mit Rechenweg.",
    ],
    "2026-10-10j": [
        "Schreibst du „such nach …“, sucht KIplatz genau danach und mischt keine Angaben aus früheren Nachrichten dazu.",
        "Ein Klick auf „Neues Gespräch“ legt kein weiteres leeres Gespräch mehr an, leere Gespräche stehen nicht mehr in der Liste, und das KIplatz-Logo oben links führt wieder zum Start.",
    ],
    "2026-10-10i": [
        "Fragst du nach Tipps zu einem Spiel oder einem Vorhaben, sucht KIplatz jetzt auch dann im Wissen und im Internet, wenn ein PC aus der Community antwortet. Bei „such live nach …“ sucht es genau das, was du nennst.",
    ],
    "2026-10-10h": [
        "Kommt in deiner Frage ein Name vor, den KIplatz nicht kennt, sucht es jetzt gleich im Internet danach. Findet es nichts Verlässliches, sagt es das ehrlich, statt etwas Passendes zu erfinden.",
        "Tippst du im Programm eine Frage, legt dein PC seine Arbeit im Hintergrund sofort weg, damit die Antwort schneller kommt. Was du tippst, bleibt dabei auf deinem Gerät.",
    ],
    "2026-10-10g": [
        "KIplatz versteht jetzt die kurzen Befehle, die man oft tippt. „Kürzer“, „als Liste“, „weiter“ oder „auf Englisch“ formen die letzte Antwort um, ohne neu zu suchen, und „bist du sicher?“ oder „das stimmt nicht“ lassen es frisch nachprüfen.",
        "Auf „danke“ antwortet KIplatz sofort, und wer um ein Bild oder Logo bittet, erfährt ehrlich, dass es das noch nicht zeichnen kann.",
    ],
    "2026-10-10f": [
        "Schreibst du „such live“ oder „schau im Internet nach“, sucht KIplatz jetzt frisch nach deiner Sache, nicht nach dem Wort „live“. Sagst du dazu, dass die Antwort nicht stimmt, antwortet es neu und wiederholt die falsche nicht.",
    ],
    "2026-10-10e": [
        "Während KIplatz schreibt, verschwindet die Antwort nicht mehr kurz und springt nicht mehr. Der Entwurf steht gleich mit Absätzen da, und kommt die geprüfte Fassung, bleibst du an der Stelle, an der du gerade liest.",
    ],
    "2026-10-10d": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-10c": [
        "Ist das Programm auf Englisch gestellt, kommen jetzt auch der Tagesbericht, die Angaben unter „Woher“ und die Meldungen beim Holen von Dateien ganz auf Englisch.",
    ],
    "2026-10-10b": [
        "Schickst du ein Bild kurz nach dem Start der KI, lädt der Bild-Zusatz jetzt zuverlässig; vorher konnte die KI dabei ausgehen.",
    ],
    "2026-10-10a": [
        "Die Internetsuche fällt seltener aus: Bremst eine Suchmaschine, fragt KIplatz von selbst andere, statt „die Suche ist nicht durchgekommen“ zu sagen.",
    ],
    "2026-10-09g": [
        "Nach einem Neustart oder Update schaltet dein PC seine KI wieder von selbst ein, auch wenn gerade ein anderer PC der Community online ist.",
    ],
    "2026-10-09f": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-09e": [
        "Beim ersten Öffnen fragt die App nur noch nach Name und Wohnort, beides freiwillig. Die weiteren Fragen zum Start findest du unter Einstellungen, „Meine KI“, ein Link führt direkt hin. Der Hinweis auf einen Apple-Fehler nach der Anmeldung ist weg, das war keiner.",
    ],
    "2026-10-09d": [
        "Beim Aufbereiten des Wissens bleibt dein PC an sehr langen Abschnitten nicht mehr hängen, sondern arbeitet gleich weiter.",
    ],
    "2026-10-09c": [
        "Nach dem Anmelden bist du gleich in der App, ohne dass die Seite mit leeren Knöpfen stehen bleibt. Lädt die App einmal nicht ganz, etwa in einem Funkloch, sagt sie es und lädt von selbst noch einmal.",
    ],
    "2026-10-09b": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-09a": [
        "Wer KIplatz auf Englisch nutzt, sieht im Programm und in der App keine deutschen Reste mehr, auch nicht bei Zahlen, Meldungen und der Platzordnung.",
    ],
    "2026-10-08h": [
        "Ein PC, der Fragen der Community beantwortet, hält seine KI zwischen zwei Fragen wach. So wartet auch die erste Frage nach einer Pause nicht darauf, dass die KI von der Festplatte geladen wird.",
    ],
    "2026-10-08g": [
        "Jede vorbereitete Antwort der Community prüft ein zweiter PC einzeln gegen ihre Quelle. Was dort nicht steht, nimmt KIplatz heraus, der Rest bleibt.",
    ],
    "2026-10-08f": [
        "KIplatz schreibt seine Antworten selbst und nennt die Quelle mit Link, damit du beim Original nachlesen kannst. Zahlen, Namen und Daten übernimmt es genau so, wie sie dort stehen. So bleibt die Arbeit der Menschen, die diese Texte schreiben, bei ihnen.",
    ],
    "2026-10-08e": [
        "Fragst du nach einer Zahl, einem Datum oder einer Dauer, sucht KIplatz im Internet jetzt gleich mit, während es die Antwort schreibt. Reicht das Wissen der Community nicht, ist das Ergebnis schon da, und die Antwort kommt Sekunden früher. Unter der Antwort steht, wonach dabei gesucht wurde.",
    ],
    "2026-10-08d": [
        "Fragst du nach einer Zahl zu etwas, das in der Wikipedia steht, etwa nach der Länge der Donau in Österreich, findet KIplatz die Stelle jetzt direkt in der Wikipedia, die auf den PCs der Community liegt. Die Antwort kommt damit in wenigen Sekunden, ohne Umweg über eine Suche im Internet. Die Zahl kommt dabei immer aus dem Artikel über die Sache, nach der du fragst.",
    ],
    "2026-10-08c": [
        "Fragst du nach einer Länge, Höhe, Dauer, Anzahl, einem Preis oder Datum, sucht KIplatz auf jeder gelesenen Seite und in der Wikipedia gezielt die Stelle mit genau dieser Angabe.",
    ],
    "2026-10-08b": [
        "Steht eine Zahl oder ein Datum aus der ersten Antwort in keiner Quelle, schaut KIplatz jetzt gleich im Internet nach und antwortet mit Quelle. Findet auch das Internet nichts Verlässliches, sagt KIplatz das, statt zu raten.",
    ],
    "2026-10-08a": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-07i": [
        "Was KIplatz für dich im Internet nachschaut, bleibt privat auf deinem PC und hilft nur bei deinen Fragen. Mit der Community teilt KIplatz nur seine Antwort, in eigenen Worten und mit Link zur Quelle. Eine Website, die du unter Einstellungen · Wissen liest, bleibt ebenfalls privat auf deinem PC.",
        "Websites, die „Nein zu KI“ sagen, liest KIplatz nicht, auch nicht für eine einzelne Frage. Was KIplatz von fremden Websites liest und aufhebt, steht unter kiplatz.at/urheberrecht.",
    ],
    "2026-10-07h": [
        "Die Spalte rechts im Programm ist weg: Rückmeldungen stehen wieder unten in einer schmalen Zeile und verschwinden nach ein paar Sekunden von selbst. Liest du unter Einstellungen · Wissen eine Website ein, steht direkt unter dem Feld, was gemerkt wurde. Gelesen wird genau diese eine Seite, nicht die Seiten dahinter.",
        "Am Handy bleibt beim Schreiben eines langen Textes die Zeile, in der du gerade tippst, immer im Bild. Vorher wuchs das Eingabefeld unter die Tastatur, und man schrieb blind weiter.",
        "Schreibst du am Handy mehr als eine Zeile, bekommt dein Text die ganze Breite des Eingabefelds. Die Knöpfe für Dateien, Mikrofon und Senden rücken dann in eine Zeile darunter.",
    ],
    "2026-10-07g": [
        "Im Programm gibt es neben „Neues Gespräch“ jetzt die Lupe wie in der App, sie sucht in den Titeln deiner Gespräche. „Gespräche importieren“ steht in den Einstellungen unter Allgemein und im Menü Programm, nicht mehr in der Seitenleiste. „Meine KI“ zeigt die Fragen als Kacheln zum Antippen wie in der App.",
    ],
    "2026-10-07f": [
        "Das Menü im Programm ist aufgeräumt: Platzl, Skills, Meine KI und Meine Community stehen fest in der Seitenleiste, unten links öffnet dein Konto die Einstellungen. Einstellungen und Meine Community haben Reiter wie bei Claude, jede Karte liegt offen und gibt es genau einmal. Keine Aufklappmenüs mehr.",
    ],
    "2026-10-07e": [
        "Die Einstellungen der App sind aufgeräumt: eine Liste in vier Gruppen (Community, KIplatz anpassen, Geräte und PC, Daten und Konto), Wichtiges oben. Jede Zeile öffnet eine eigene Seite, keine Aufklappmenüs mehr. „Antworten prüfen“ steht jetzt gleich unter Community.",
        "Ein Klick auf „KIplatz“ oben links führt immer zur Startseite mit den Gesprächen, im Programm und in der App.",
    ],
    "2026-10-07d": [
        "Meldest du dich am iPhone vom Home-Bildschirm aus mit Google oder GitHub an, schließt sich das Anmeldefenster danach wieder von selbst. Vorher blieb es nach der Anmeldung stehen.",
    ],
    "2026-10-07c": [
        "Sitzt du am PC, ruht jede Arbeit im Hintergrund, auch bei der Einstellung „Immer“. Fragen der Community beantwortet dein PC trotzdem sofort und mit voller Suche. Bist du eine Weile weg oder schläfst du, läuft wieder alles.",
    ],
    "2026-10-07b": [
        "Wird der Arbeitsspeicher knapp, während du am PC arbeitest, hört KIplatz sofort mit dem Aufbereiten des Wissens auf und macht erst weiter, wenn du eine Weile weg bist. Fragen der Community beantwortet dein PC dabei weiter, genauso gut wie vorher.",
    ],
    "2026-10-07a": [
        "KIplatz braucht beim Aufbereiten des Wissens viel weniger Arbeitsspeicher. Am Laptop waren es nach ein paar Stunden über 12 GB, jetzt bleibt es bei rund 2,5 GB. So bleibt mehr Platz für deine eigenen Programme.",
        "Start für alle: Jedes Gerät beginnt wieder mit 100 Credits, auch die Bestenliste hat neu angefangen.",
    ],
    "2026-10-06f": [
        "Jede Antwort trägt ein unsichtbares Etikett „von KIplatz erzeugt“, so wie es das EU-Gesetz über KI vorsieht. Am Text ändert sich dadurch kein Wort. Prüfen kann es jeder auf kiplatz.at/ki-kennzeichnung.",
    ],
    "2026-10-06e": [
        "Neu unter Einstellungen: „Meine Fragen helfen beim Lernen“. Schaltest du es aus, kommen deine Fragen, „Daumen hoch“ und Berichtigungen nicht mehr in die Lernliste. Das gilt für dein ganzes Konto, am Handy und am PC.",
    ],
    "2026-10-06d": [
        "Auf Geräten mit kleinem Modell schaut KIplatz bei Wissensfragen jetzt zuerst im Internet nach und antwortet mit Quelle. Findet es nichts Verlässliches, sagt es das, statt zu raten.",
        "„Bei wie viel Grad siedet Wasser?“ und ähnliche Fragen hält KIplatz nicht mehr für eine Wetterfrage.",
    ],
    "2026-10-06c": [
        "Ist dein Programm auf Englisch eingestellt, kommen jetzt auch „Neu im Programm“, das Menü am Symbol unten rechts und die Spracherkennung auf Englisch. Mails an dein Konto kommen in der Sprache, in der du dich angemeldet hast.",
    ],
    "2026-10-06b": [
        "Nach dem Start liest KIplatz die Wikipedia einmal kurz an. So ist schon die erste Frage schnell, nicht erst die zweite.",
    ],
    "2026-10-06a": [
        "Stellst du eine Frage, während dein PC nachts seine Prüffragen beantwortet, kommt deine Frage sofort dran. Die Prüffrage wird danach wiederholt.",
        "Ist der Arbeitsspeicher fast voll und du arbeitest am Gerät, macht KIplatz mit der Arbeit für andere Pause, damit nichts ruckelt.",
        "Gibt dein Gerät seine Fragen ohnehin an die Community, gibt KIplatz in der Pause auch den Arbeitsspeicher des Modells frei.",
        "Wechselst du das Laufwerk, beginnt der Umzug der Wikipedia sofort, auch wenn gerade ein langer Arbeitsschritt läuft.",
    ],
    "2026-10-05l": [
        "Wählst du für deinen Speicher ein anderes Laufwerk, zieht die Wikipedia jetzt mit um: Das Programm kopiert sie, prüft jede Datei und löscht erst dann die alte Kopie. Vorher wurde sie gelöscht und neu geholt, das dauerte viele Stunden.",
        "Das Aufbereiten einer neuen Wikipedia-Ausgabe beginnt nach einem Neustart des Programms nicht mehr von vorne.",
    ],
    "2026-10-05k": [
        "Fragen nach Verbindungen, Fahrzeiten, Preisen, Öffnungszeiten oder Terminen sucht KIplatz jetzt gleich im Internet, ohne erst in der Wikipedia nachzuschlagen. Das spart bei solchen Fragen einige Sekunden.",
    ],
    "2026-10-05j": [
        "Was KIplatz gerade schreibt und noch prüft, steht blasser da und heißt „Entwurf, wird geprüft“. Passt die erste Fassung nicht zu den Quellen, steht das unter der Antwort, und KIplatz sucht gleich im Internet, statt zu fragen.",
        "Antworten auf englische Fragen kommen schneller: übersetzt wird nur noch die Antwort selbst.",
    ],
    "2026-10-05i": [
        "Fragt KIplatz „Soll ich live nachprüfen?“, steht direkt darunter der Knopf „Ja, live nachprüfen“. Ein kurzes „ja“ im Eingabefeld geht genauso.",
    ],
    "2026-10-05h": [
        "KIplatz gibt es jetzt auch auf Englisch. Das Programm nimmt die Sprache von Windows, die App die des Handys; umstellen kannst du sie unter Einstellungen, „Sprache“. Fragst du auf Englisch, antwortet KIplatz auf Englisch, geprüft wird die Antwort wie immer gegen die Quellen.",
        "In der App wird kein Text mehr mit „…“ abgeschnitten: passt er nicht in eine Zeile, etwa bei großer Schrift, bekommt er eine zweite.",
    ],
    "2026-10-05g": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-05f": [
        "Anmelden mit dem Handy: Klick unter „Meine Community“ auf „Mit dem Handy anmelden“ und scann den QR-Code mit der KIplatz-App (Einstellungen, „PC anmelden“). Ohne Passwort, in ein paar Sekunden.",
        "Berichtigst du eine Antwort und ein PC der Community bestätigt sie, bekommst du jetzt 2 Credits. Unter „Prüfen“ findest du außerdem einen Text, mit dem du KIplatz an Freunde weiterempfehlen kannst.",
    ],
    "2026-10-05e": [
        "Hinter den Sätzen einer Antwort stehen keine farbigen Punkte mehr. Woher eine Antwort kommt, siehst du weiter unter „Details zur Antwort“.",
    ],
    "2026-10-05d": [
        "Bei „Meine KI“ steht beim freien Feld „Sonst noch etwas?“ jetzt dabei, dass es mit jeder Frage mitgeht. Persönliches gehört dort nicht hinein.",
    ],
    "2026-10-05c": [
        "Die Fragen beim Einrichten gibt es jetzt auch unter Bereiche als „Meine KI“, mit Antwortstil: wofür du KIplatz brauchst (etwa Programmieren, Web, KI am eigenen PC, Linux und Git), wie es antworten soll und was es nie tun soll. Das gilt jetzt auch, wenn ein PC der Community antwortet.",
    ],
    "2026-10-05b": [
        "„Schlüssel kopieren“ unter „Andere Programme dürfen KIplatz fragen“ kopiert jetzt wirklich den ganzen Schlüssel. Angezeigt wird er nur noch verkürzt, „Anzeigen“ zeigt ihn ganz.",
        "Die Kopier-Knöpfe im Programm, etwa bei Antworten und beim Team-Code, funktionieren jetzt zuverlässig.",
    ],
    "2026-10-05a": [
        "Den Tagesbericht liest du jetzt auf einen Blick: oben die Zahlen deines PCs als Kacheln, darunter dein Platz, der Platz deines Teams und die Prüffragen der Nacht, und für das ganze Netz eine kleine Tabelle mit heute und gestern.",
        "Seiten, die KIplatz liest, tragen jetzt ihren richtigen Titel. Vorher hingen bei manchen Seiten Wörter aus Menü und Bildchen dran, etwa „…infoAustriaGroßglockner“.",
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-04c": [
        "Anmelden ohne Passwort: Adresse eintippen, den Code aus der Mail eintippen, fertig. In der App direkt, am PC und im Platzl über den Knopf „Mit E-Mail-Code anmelden“.",
        "In der App kannst du mehrere Konten anmelden und mit einem Tipp wechseln, etwa ein eigenes und eines für die Familie. Jedes Konto hat seine eigenen Gespräche, Projekte und Skills.",
        "Neu in der Bestenliste: Gründe ein Team mit Verein, Firma oder Freunden oder tritt mit einem Code bei. Die Arbeit aller zählt fürs Team, und das Team bekommt einen Platz in der Team-Rangliste.",
        "Läuft Open WebUI oder ein anderes Programm bei dir in Docker, kann es KIplatz jetzt auch fragen. Schalte dafür unter „Einstellungen“ bei „Andere Programme dürfen KIplatz fragen“ den Schalter für Docker ein. Geräte im Heimnetz kommen weiterhin nicht hinein.",
        "Deinen Namen zeigt die Bestenliste nur noch, wenn du „Mit Namen in der Bestenliste“ anhakst. Dein Tagesbericht unter „Meine Community“ sagt dir, was dein PC gestern und heute für andere erarbeitet hat und auf welchem Platz du und dein Team steht.",
    ],
    "2026-10-04b": [
        "Unter jeder Antwort steht jetzt eine ruhige Zeile wie in der App: Kopieren, Daumen hoch und runter, Prüfen und Nochmal. Teilen, Vorlesen und die Details findest du unter den drei Punkten, die Quellen rechts daneben.",
        "Mit „Antwort melden“ sagst du uns direkt, wenn eine Antwort falsch, unvollständig oder anstößig ist. Beim Daumen runter tippst du den Grund einfach an.",
        "Sätze mit „z. B.“, „ca.“ oder „d. h.“ prüft KIplatz jetzt als einen Satz, nicht mehr als zwei.",
    ],
    "2026-10-04a": [
        "In der App meldest du dich jetzt mit einem Tipp an: Konto wählen, bestätigen, und du bist wieder in der App. Der Umweg über die Website fällt weg.",
        "Mehr Datenschutz in der App: Hast du den Standort für Wetterfragen eingeschaltet, schlägt unser Server den Ortsnamen nach, auf etwa 1 km gerundet und ohne ihn zu speichern. Dein Handy fragt dafür keinen fremden Dienst.",
    ],
    "2026-10-03h": [
        "Weiß KIplatz etwas nicht, sucht es im Internet nach, bevor es aufgibt. „Im Internet nichts gefunden“ steht nur noch da, wenn wirklich gesucht wurde.",
    ],
    "2026-10-03g": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-03f": [
        "Fragst du nach einer Dauer, einer Anzahl oder einem Datum, nennt KIplatz genau diese Angabe aus den Quellen. Steht sie nirgends, sagt es das ehrlich, statt eine andere Zahl zu nennen.",
        "Deine Frage geht bevorzugt an einen PC, auf dem das Wissen der Community schon fertig liegt; der findet die Quellen schneller.",
    ],
    "2026-10-03e": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-03d": [
        "Dein PC kann Modelle an neue Mitglieder weitergeben, verschlüsselt und Stück für Stück geprüft. So wächst die Leitung mit der Community, ganz ohne Rechenzentrum. Ein- und ausschalten unter „Rechenkraft teilen“.",
        "Neue Mitglieder holen ihre KI zuerst bei anderen PCs der Community; klappt das nicht, wie bisher von unserem Server in Wien.",
    ],
    "2026-10-03c": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-03b": [
        "Ein neuer PC kann sofort fragen: Solange seine eigene KI noch geladen wird, antwortet ein PC der Community.",
        "Beim Laden der KI wird jedes Stück einzeln geprüft. Kommt eines kaputt an, holt dein PC nur dieses Stück neu, nicht die ganze Datei.",
    ],
    "2026-10-03a": [
        "Die KI holt dein PC nur noch von unserem Server in Wien. Ist er gerade ausgelastet, steht unten „Einen kurzen Moment bitte“, und dein PC ist gleich von selbst an der Reihe.",
        "Gesucht wird nur noch über die Suche der Community auf unserem Server.",
    ],
    "2026-10-02r": [
        "Mehr Datenschutz: Unter einer gespeicherten Antwort steht der Name eines PCs nur, solange er zur Community gehört, und auf die PCs der anderen kommt er gar nicht. Nummern und E-Mail-Adressen in einer Rückmeldung werden unkenntlich gemacht.",
    ],
    "2026-10-02q": [
        "Sagst du KIplatz „merk dir das“, sagt es dir ehrlich, was es behalten kann und wie es etwas dauerhaft richtig weiß: über Daumen runter mit der richtigen Antwort als Vorschlag.",
        "Prüft sich dein PC nachts mit den Prüffragen der Community, siehst du unter „Heute“, wie viele er richtig beantwortet hat.",
    ],
    "2026-10-02p": [
        "Dein PC merkt sich den Anfang einer Antwort wieder, auch wenn er zwischendurch Wissen aufbereitet. Er muss ihn dann nicht jedes Mal neu lesen.",
        "Weiß KIplatz bei der Frage eines Mitglieds etwas nicht, sucht es höchstens einmal nach und sagt dann ehrlich, dass es das noch nicht weiß. Die neue Antwort bekommt die Frage wörtlich mit, damit sie genau das beantwortet, was gefragt war.",
        "Webseiten, die beim Suchen gelesen wurden, verschwinden nach Ablauf wieder von deinem PC.",
    ],
    "2026-10-02o": [
        "Antworten am PC sind wieder schneller: Eine Änderung vom selben Abend hat sie gebremst und ist zurückgenommen.",
    ],
    "2026-10-02n": [
        "Mehr Sicherheit im Heimnetz: Ein fremdes Gerät im selben WLAN kann die Verbindung zwischen deinem PC und deinem Laptop nicht mehr lahmlegen, der Kopplungscode lässt sich nicht mehr erraten, und ein gekoppeltes Gerät kann deinen PC keine Seiten aus deinem Heimnetz lesen lassen, etwa die deines Routers. Koppeln geht nur, wenn beide Geräte diese Fassung haben.",
        "Hat dein PC ein großes Modell und teilt er Rechenkraft, prüft er sich nachts selbst mit den Prüffragen der Community. Antwortet er schlecht, kommen die Fragen der Mitglieder zuerst zu anderen PCs, bis eine Nacht wieder passt. Gesperrt wird er nie.",
        "„Daumen hoch“ unter einer Antwort aus dem Antwort-Speicher zählt jetzt auch bei der Community. „Daumen runter“ zählt je Konto: Erst wenn zwei Mitglieder eine gespeicherte Antwort schlecht finden, wird sie neu erarbeitet.",
    ],
    "2026-10-02m": [
        "Auf einem PC mit genug Grafikspeicher behält KIplatz den Anfang deiner Antwort im Gedächtnis, auch während es nebenbei Wissen aufbereitet. Die nächste Antwort beginnt dadurch schneller.",
    ],
    "2026-10-02l": [
        "Eine Frage, die dein PC für ein Mitglied angenommen hat, geht nie mehr verloren: Kann er sie nicht beantworten, weil er gerade neu startet, das Modell nicht lädt oder du selbst etwas fragst, gibt er sie sofort an die Community zurück, und der nächste PC übernimmt.",
        "Nach einer kurzen Unterbrechung der Verbindung ist dein PC binnen Sekunden wieder für die Community da, nicht erst nach einer Minute.",
        "Fertige Antworten werden öfter gefunden: „Wie viele Einwohner hat Innsbruck?“ und „Einwohner Innsbruck“ gelten als dieselbe Frage.",
    ],
    "2026-10-02k": [
        "Allgemeine Wissensfragen, die die Community schon geprüft beantwortet hat, beantwortet dein PC jetzt sofort selbst, ohne nachzudenken. Die Antworten liegen verschlüsselt auf deinem PC und lassen sich nur mit genau dieser Frage öffnen.",
        "Fragen, für die im Internet nachgeschaut wird, sind schneller fertig: KIplatz wartet nicht mehr auf die langsamste Webseite.",
    ],
    "2026-10-02j": [
        "Neue Versionen kommen jetzt binnen 5 Minuten auf deinen PC, nicht erst zur vollen Stunde.",
        "Fragst du nach anderen KI-Anbietern, beschreibt KIplatz sich selbst richtig: es läuft auf deinem PC und auf den Geräten der Community.",
    ],
    "2026-10-02i": [
        "Meldet sich am PC ein anderer Windows-Benutzer an, etwa zum Spielen, macht KIplatz sofort Pause und gibt die Grafikkarte frei. Ist er wieder weg, arbeitet KIplatz von selbst weiter.",
    ],
    "2026-10-02h": [
        "Hat dein PC gerade eine Frage angenommen, wartet ein Update, bis die Antwort draußen ist. Keine Frage geht mehr durch einen Neustart verloren.",
    ],
    "2026-10-02g": [
        "Neue Versionen kommen jetzt binnen 5 Minuten statt binnen einer Stunde. Dein PC prüft dabei wie immer die Unterschrift.",
    ],
    "2026-10-02f": [
        "Muss KIplatz eine Antwort neu schreiben, weil eine Zahl in keiner Quelle stand, entschuldigt es sich nicht mehr für einen Fehler, den du nie gesehen hast.",
    ],
    "2026-10-02e": [
        "Antworten kommen schneller: Dein PC liest bei den Prüfschritten nicht mehr jedes Mal alles von vorn ein.",
        "Laufen zwei KIplatz auf einem Rechner, macht das eine Pause, während das andere eine Frage beantwortet.",
        "Bei „Jetzt live nachprüfen“ sucht dein PC gleichzeitig in der Wikipedia und im Internet.",
    ],
    "2026-10-02d": [
        "Deine Frage geht jetzt an den PC, der in der Community gerade am schnellsten fertig wird. Gezählt wird die ganze Zeit bis zur fertigen Antwort, mit Suchen und Prüfen.",
        "Nach „Daumen hoch“ oder „Daumen runter“ steht das Danke jetzt direkt unter den Daumen.",
    ],
    "2026-10-02c": [
        "Kommt eine Frage, lässt dein PC jede andere Arbeit sofort liegen und antwortet, auch beim Aufbereiten, beim Vorbereiten am Morgen und in der Nacht.",
        "Fragen kommen schneller bei einem freien PC an: Keine Frage wartet mehr mehrere Sekunden auf einen PC, der gerade nicht zugreift.",
    ],
    "2026-10-02b": [
        "Fragt jemand etwas, das die Community schon geprüft beantwortet hat, kommt die Antwort jetzt sofort aus dem Antwort-Speicher, ohne Wartezeit. Gefällt sie dir nicht, nimmt „Daumen runter“ sie heraus.",
        "Dein PC sagt jetzt mit jeder Antwort, wie lange welcher Schritt gedauert hat. So machen wir KIplatz gezielt schneller.",
    ],
    "2026-10-02a": [
        "Skills können jetzt „Immer an“ sein: einmal anhaken, dann gelten sie in jedem Gespräch, auch in neuen. Das geht unter Skills und mitten im Gespräch über „Immer an …“ neben der Skill-Auswahl.",
        "Beantwortet ein PC der Community deine Frage, bekommt er deine Skills jetzt mit und hält sich daran.",
    ],
    "2026-10-01d": [
        "Teilen sich mehrere Benutzer oder Programme eine Grafikkarte, sieht KIplatz das jetzt und wählt ein Modell, das daneben noch Platz hat.",
        "Hängt ein PC bei einer Frage, springt nach wenigen Sekunden ein anderer ein.",
    ],
    "2026-10-01c": [
        "Dein PC hält jetzt eine Kopie des öffentlichen Wissens der Community und sucht selbst darin. Antworten kommen schneller, auch wenn sehr viele gleichzeitig fragen.",
        "Die Suche am Server ist um ein Vielfaches schneller geworden.",
    ],
    "2026-10-01b": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-10-01a": [
        "Antworten kommen schneller: Kommt eine Frage, legt dein PC die Arbeit im Hintergrund sofort zur Seite und antwortet zuerst.",
        "Auf Grafikkarten mit wenig Speicher bleibt die KI jetzt ganz auf der Karte und schreibt wieder in voller Geschwindigkeit.",
        "Eine normale Frage vom Handy beantwortet der stärkste freie PC der Community. Dein PC daheim kümmert sich um die Fragen zu deinen Dateien.",
    ],
    "2026-09-30k": [
        "KIplatz läuft jetzt auf einer neueren Programm-Grundlage, die noch lange Sicherheitsupdates bekommt. Du hast nichts zu tun.",
    ],
    "2026-09-30j": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-30i": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-30h": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-30g": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-30f": [
        "KIplatz erneuert jetzt auch seine Programm-Grundlage (das Python darunter) von selbst, so wie bisher schon das Programm. Du musst nichts neu installieren und keinen Ordner anfassen.",
    ],
    "2026-09-30e": [
        "Unter „Frag dein Zuhause“ steht bei „Zuletzt geholt“ jetzt immer der Name des Handys, das die Datei geholt hat.",
        "Nach dem Verbinden sagt dir KIplatz gleich, wo du das Suchen in deinen Dateien findest: in der App über das Plus neben dem Eingabefeld, am Laptop mit dem Haken darunter.",
    ],
    "2026-09-30d": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-30c": [
        "Bevor dein PC das Wikipedia-Wissen neu einliest, schaut er nach, ob auf dem Laufwerk genug Platz ist. Wird es knapp, wartet er, statt die Platte vollzuschreiben; die bisherige Kopie bleibt so lange in Gebrauch.",
    ],
    "2026-09-30b": [
        "KIplatz hat jetzt eine eigene Adresse: Dein Programm spricht mit kiplatz.at. Unter „Was verlässt meinen Rechner“ steht deshalb ab jetzt kiplatz.at.",
    ],
    "2026-09-30a": [
        "Große Städte wie Salzburg und Innsbruck fehlten im Wikipedia-Wissen auf deinem PC. Dein PC liest es in freien Stunden einmal neu ein, danach findet KIplatz auch diese Artikel.",
    ],
    "2026-09-29w": [
        "„In meinen Dateien suchen“ steht jetzt unter der Frage, neben „Skill“. Du setzt den Haken selbst, und er bleibt im Gespräch, bis du ihn wieder wegnimmst; ein neues Gespräch beginnt ohne.",
        "Fragst du ohne Haken nach einer Datei, sucht KIplatz nicht auf eigene Faust, sondern sagt dir, wo der Haken ist.",
    ],
    "2026-09-29v": [
        "Fragst du nach dem letzten Bildschirmfoto, findet KIplatz jetzt genau das neueste; Wörter wie „letzte“ oder „neueste“ heißen „das Neueste zuerst“.",
        "Findet KIplatz mehrere Dateien, steht oben ein Satz und darunter die Liste zum Anklicken, nicht mehr alles doppelt.",
        "Das Kästchen „In meinen Dateien suchen“ erscheint nur, wenn dein PC mit einem Handy oder Laptop verbunden ist.",
    ],
    "2026-09-29u": [
        "Unter „Meine Community“ ist „Deine Credits“ jetzt zugeklappt wie die anderen Bereiche; ein Klick zeigt dein Guthaben und wofür.",
        "Verbindest du dein Handy ein zweites Mal mit demselben PC, bleibt es bei einer Verbindung, und die App sagt dir, dass es schon verbunden war.",
    ],
    "2026-09-29t": [
        "Fragst du nach einem Ort, etwa „Einwohnerzahl Wels“, nimmt KIplatz den Wikipedia-Artikel über die Stadt, nicht den gleichnamigen Fisch.",
        "Bei einem Vergleich wie „Einwohner Salzburg und Wien“ kommen die Artikel aller genannten Orte mit, auch wenn KIplatz zusätzlich im Netz nachschaut.",
        "In der App verbindest du dein Handy jetzt auch mit der Kamera: QR-Code am PC scannen, fertig. Dein Handy fragt vorher, ob du die Kamera erlaubst.",
    ],
    "2026-09-29s": [
        "Fragst du nach Zahlen zu mehreren Orten oder Namen, kommt jeder davon in der Antwort vor; fehlt zu einem die sichere Zahl, sagt KIplatz das dazu, statt ihn zu übergehen.",
        "Bei einer Zahlenfrage zu einem Ort zählen nur der Ort selbst und passende Seiten, keine Ortsteile mehr.",
        "Schaltest du „In meinen Dateien suchen“ selbst aus, sucht KIplatz im Netz, auch wenn deine Frage nach einer Datei klingt.",
        "Große Dateien vom PC daheim kommen jetzt auch bei langsamem Internet an; was nicht auf einmal geht, holt KIplatz gleich hinterher.",
    ],
    "2026-09-29r": [
        "Eine Antwort kommt jetzt ganz oder gar nicht: Streicht die Prüfung Unbelegtes, bleibt nie ein halber Satz stehen; KIplatz antwortet dann noch einmal streng oder sagt ehrlich, dass es das nicht sicher weiß.",
        "Nennst du einen Ort oder Namen, steht dessen Wikipedia-Artikel immer vorn in den Quellen, nicht nur Ortsteile oder Nebensachen.",
        "Rückfragen gibt es nur noch bei echten Aufträgen wie „plane mir“ oder „empfiehl mir“. Eine Wissensfrage, auch mit „vergleiche“, wird sofort beantwortet.",
    ],
    "2026-09-29q": [
        "„Frag dein Zuhause“ findet jetzt alle deine Dateien auf dem PC daheim, auch Word, PDF und Fotos, und zeigt sie als Liste mit Ordner und Datum. Findet es nichts Genaues, zeigt es ähnliche Dateien.",
        "Hak in der Liste an, was du brauchst, und hol es dir aufs Handy oder den Laptop. Unterwegs ist die Datei verschlüsselt.",
        "Über dem Eingabefeld siehst du, ob deine Frage in deinen Dateien sucht; das Programm schaltet es bei einer Dateifrage von selbst ein, du kannst es jederzeit umstellen.",
        "Unter „Deine Credits“ stehen gleiche Buchungen jetzt in einer Zeile, mit Anzahl und Summe, statt vieler einzelner Zeilen.",
    ],
    "2026-09-29p": [
        "Fragst du nach einer eigenen Datei, etwa „wo ist meine Bewerbung“, sucht KIplatz nie mehr im Internet, sondern nur in deinen Unterlagen, und sagt ehrlich, wenn es nichts findet.",
        "Sucht KIplatz im Internet, passen die Suchwörter immer zu deiner Frage; gespeicherte Suchergebnisse enthalten deine Frage nicht.",
    ],
    "2026-09-29o": [
        "Neu: „Frag dein Zuhause“. Dein Handy oder Laptop fragt deinen PC daheim, und der antwortet mit deinen Unterlagen. Einmal koppeln unter „Meine Community“ mit einem Code oder QR-Code; deine Unterlagen bleiben am PC.",
        "Unter „Gemeinsamer Speicher“ stehen die Wikipedia-Zahlenreihen für neue Geräte jetzt getrennt vom Wissen der Community.",
    ],
    "2026-09-29n": [
        "Im dunklen Fenster haben „Die KI zum Fragen“ und „Dein Gerät“ wieder dieselbe Farbe wie die anderen Zeilen statt Schwarz.",
    ],
    "2026-09-29m": [
        "In den Bereichen ist jede zweite Zeile leicht getönt, und die Überschriften der Gruppen sind größer, damit man sich schneller zurechtfindet.",
        "Hat schon ein PC der Community die Wikipedia fertig für die Suche nach Bedeutung aufbereitet, übernimmt ein neuer PC diese Zahlenreihen von ihm, statt tagelang selbst zu rechnen. Das geschieht von selbst, nur in freien Minuten und ohne Text, nur Zahlen.",
    ],
    "2026-09-29l": [
        "Fragst du nach mehreren Orten auf einmal, sucht KIplatz neben jedem Ort einzeln auch nach Seiten, die alle zusammen nennen, etwa nach einem Vergleich.",
    ],
    "2026-09-29k": [
        "Ortsnamen aus mehreren Wörtern wie St. Pölten, Bad Ischl oder Klagenfurt am Wörthersee erkennt KIplatz jetzt als einen Ort, wenn du nach mehreren Orten auf einmal fragst.",
        "Während KIplatz eine Antwort prüft, zeigt der Entwurf am Handy keine internen Hinweise mehr.",
    ],
    "2026-09-29j": [
        "Fragst du nach mehreren Orten oder Dingen auf einmal, etwa nach den Einwohnern von Klagenfurt und München, sucht KIplatz jetzt für jedes einzeln, im Internet und in der Wikipedia-Kopie.",
        "Eine gefundene und belegte Zahl bleibt in der Antwort stehen, auch wenn zu einem anderen Teil der Frage noch nichts gefunden wurde.",
    ],
    "2026-09-29i": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-29h": [
        "Die Bereiche sind aufgeräumt: Einstellungen, Meine Community und die anderen zeigen eine übersichtliche Liste in Gruppen. Jeder Punkt ist zugeklappt und öffnet sich mit einem Klick; was du offen hattest, merkt sich das Programm.",
        "Das Menü „Bereiche“ ist in drei Gruppen geteilt: mitmachen, Community und Einstellungen.",
    ],
    "2026-09-29g": [
        "Die KI auf deinem PC startet jetzt auch dort, wo Windows mit „Smart App Control“ nur unterschriebene Programmteile zulässt. Beim ersten Start holt das Programm dafür einmal die neue KI-Laufzeit, rund 28 MB.",
        "Unter Hilfe → Über stehen jetzt alle offenen Bausteine und Daten, die KIplatz verwendet, mit ihren Lizenzen.",
        "Die Wikipedia-Kopie rechnet bei einer neuen Ausgabe nur noch die Abschnitte neu, die sich geändert haben; alles andere übernimmt sie. Die Grafikkarte ist dadurch viel früher wieder frei für Antworten, und die Kopie braucht halb so viel Platz für ihre Bedeutungs-Zahlen.",
    ],
    "2026-09-29f": [
        "Unter der letzten Antwort steht „Nochmal fragen“: dieselbe Frage geht noch einmal an die Community, und wenn einer frei ist, antwortet ein anderer, gleich guter PC.",
        "Mit dem neuen Knopf „Teilen“ unter jeder Antwort schickst du Frage und Antwort als Text weiter, per Nachricht oder Mail. Es entsteht kein Link und nichts am Server.",
        "Unter Suchergebnissen steht jetzt immer richtig, was an die Suche ging: deine Suchwörter oder, wenn keine gebildet wurden, deine Frage selbst.",
        "Fragst du nach Zahlen, prüft KIplatz sie gegen seine Quellen und antwortet bei Zweifel noch einmal, nur mit belegten Zahlen. Eine Antwort aus leeren Überschriften gibt es nicht mehr; weiß KIplatz es nicht, sagt es das und bietet „Live im Netz nachprüfen“ an.",
        "Während KIplatz eine Antwort prüft, siehst du am Handy den ganzen Entwurf und was gerade geschieht, statt eines einzelnen Wortes.",
    ],
    "2026-09-29e": [
        "Lässt Windows die KI auf deinem Gerät einmal nicht starten, sagt das Programm es dir in einem Satz und versucht es erst nach 30 Minuten wieder. Deine Fragen beantworten solange die PCs der Community, und Windows meldet sich nicht mehr jede Minute.",
    ],
    "2026-09-29d": [
        "KIplatz stellt keine Rückfrage mehr vor eine fertige Antwort; unter jeder Antwort steht wieder „Live im Netz nachprüfen“.",
    ],
    "2026-09-29c": [
        "Der Schlüssel, mit dem sich dein PC beim Server ausweist, wird alle 90 Tage von selbst erneuert. Unter „Deine Daten am Server“ kannst du ihn auch selbst erneuern, wenn du glaubst, dass jemand den alten hat.",
    ],
    "2026-09-29b": [
        "Der Leerlauf deines PCs wird auch nach vielen Tagen Laufzeit richtig erkannt.",
    ],
    "2026-09-29a": [
        "Dein PC hält die Verbindung zum Community-Server offen, statt für jede Anfrage neu anzuklopfen. Fragen und Antworten kommen dadurch schneller an, und der Server hat weniger Arbeit.",
    ],
    "2026-09-28b": [
        "Startet eine neue Version auf deinem Gerät zweimal nicht, holt das Programm von selbst die vorige zurück und sagt es dir.",
        "Das Programm prüft jetzt eine unterschriebene Auskunft des Servers, welcher Bau der neueste ist, und sagt dir, wenn sie fehlt, zu alt ist oder nicht stimmt.",
    ],
    "2026-09-28a": [
        "Die Statuszeile unten zeigt nach dem Start der KI nicht mehr „wird gestartet“, wenn sie längst läuft.",
        "Dein PC wartet beim Server auf Arbeit, statt alle paar Sekunden nachzufragen; eine Frage kommt so sofort bei ihm an.",
        "Ein Update, das wegen einer offenen Datei nicht fertig wurde, wird von selbst wiederholt.",
    ],
    "2026-09-27a": [
        "KIplatz bleibt schnell, auch wenn sehr viele Menschen gleichzeitig fragen. Wenn gerade nichts zu tun ist, meldet sich dein PC dafür seltener beim Server.",
        "Die Wörter einer Antwort aus der Community erscheinen, sobald der PC sie geschrieben hat, und „Stopp“ wirkt sofort.",
    ],
    "2026-09-26s": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-26r": [
        "KIplatz kennt jetzt Apotheken, Ärzte, Tankstellen, Gasthäuser, Hütten und Berge in Österreich, Deutschland, der Schweiz und Liechtenstein, samt Adresse und Öffnungszeiten, aus OpenStreetMap.",
        "Ein PC der Community bereitet die Orte auf; dein Gerät lädt dafür nichts herunter.",
    ],
    "2026-09-26q": [
        "Hängst du am Handy ein Foto oder eine Datei an und willst nur den Text daraus, schreibt KIplatz ihn jetzt einfach ab, statt nach Zielgruppe und Ton zu fragen.",
        "Unter einer Rückfrage stehen keine roten Punkte mehr, denn eine Frage behauptet nichts.",
    ],
    "2026-09-26p": [
        "Das Platzl nutzt jetzt das ganze Fenster. Ein Thema öffnet sich groß, „Zurück zur Übersicht“ bringt dich zur Liste.",
    ],
    "2026-09-26o": [
        "„Stopp“ wirkt jetzt sofort, auch wenn die KI gerade kein Wort schreibt.",
        "Bleibt die KI auf der Grafikkarte stehen, etwa nach einem Benutzerwechsel in Windows, gibt das Programm nach 90 Sekunden auf und antwortet über den Prozessor, statt zu hängen.",
    ],
    "2026-09-26n": [
        "Wird das Programm hart beendet, etwa im Task-Manager, endet die KI jetzt mit. Vorher konnte sie im Hintergrund die Grafikkarte belegen, und der nächste Start lud sehr langsam.",
        "Oben steht „KIplatz ist an“ erst, wenn die KI wirklich fertig geladen ist.",
    ],
    "2026-09-26m": [
        "Die Verschlüsselung im Programm ist auf dem neuesten Stand: Die Bibliothek dafür wurde erneuert, bekannte Lücken sind geschlossen.",
    ],
    "2026-09-26l": [
        "Tabellen in Antworten sind jetzt echte Tabellen, etwa wenn du Preise in mehreren Ländern vergleichen lässt. Vorher standen nur Striche da.",
        "Der Punkt für einen Satz ohne Beleg steht am Ende der Tabellenzeile, die er betrifft.",
    ],
    "2026-09-26k": [
        "Was du änderst, während KIplatz noch antwortet (umbenennen, anheften, in ein Projekt schieben, eine Antwort bewerten), bleibt jetzt erhalten.",
        "Credits: Eine Frage und eine Gutschrift im selben Moment werden beide gebucht.",
    ],
    "2026-09-26j": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-26i": [
        "Das Platzl im Programm: unter Bereiche, Platzl einmal verbinden, dann Themen lesen, antworten und neue Themen anlegen. Veröffentlicht wird nur nach deiner Rückfrage.",
        "Unter jeder Antwort eine kleine Fahne: Fehler im Platzl melden, mit Frage und Antwort als Entwurf; oben schreibst du, was falsch war.",
        "Skills aus dem Platzl: unter Skills „Aus dem Platzl“ übernehmen oder neu laden; eigene Skills teilst du mit „Im Platzl teilen“. Für Größeres öffnet „Mitbauen in der Werkstatt“ die Werkstatt.",
    ],
    "2026-09-26h": [
        "Das KIplatz-Symbol in der Taskleiste und am Desktop ist größer und so gut zu erkennen wie die anderen Programme daneben.",
    ],
    "2026-09-26f": [
        "Skills aus dem Platzl gehen jetzt auch am Handy: In der KIplatz-App tippst du bei einem Skill im Platzl auf „Skill verwenden“, und dein PC hält sich beim Antworten daran, wenn er eine solche Frage bekommt.",
        "Im Platzl einen Skill schreiben, am Handy gleich ausprobieren, im Platzl verbessern, mit „Neu aus dem Platzl laden“ die neue Fassung holen. Wer nicht weiterkommt, fragt im selben Thema die Community.",
    ],
    "2026-09-26d": [
        "Gespräche und Projekte bekommen Farben: Rechtsklick in der Liste, „Farbe …“, etwa Blau für Wasserfragen, Grün für Natur. Vor dem Gespräch steht ein Farbstreifen, vor dem Projekt ein farbiger Punkt; die Schrift bleibt.",
        "Farben und Projekte kommen mit „Gespräche auf allen Geräten“ auch aufs Handy, und umgekehrt.",
    ],
    "2026-09-26c": [
        "Ohne KIplatz-Konto beantwortet die Community 5 Fragen am Tag. Mit einem kostenlosen Konto fragst du ohne Grenze: unter „Meine Community“, „Dein KIplatz-Konto“. Was dein PC selbst beantwortet, zählt nicht mit.",
    ],
    "2026-09-26b": [
        "Neu: Gespräche auf allen Geräten. Unter „Dein KIplatz-Konto“ einschalten, dann beginnst du am Handy und schreibst am PC weiter. Ende-zu-Ende-verschlüsselt: Den Schlüssel haben nur deine Geräte, der Server sieht nur Datensalat.",
        "Ein neues Gerät kommt nur dazu, wenn du es auf einem anderen zulässt, erkennbar an derselben Prüfzahl. Dateien und Bilder bleiben am PC.",
    ],
    "2026-09-26a": [
        "Unter „Dein KIplatz-Konto“ siehst du jetzt alle Geräte, auf denen du angemeldet bist, mit „zuletzt aktiv“. Jedes kannst du einzeln abmelden, oder alle anderen auf einmal, etwa wenn ein Handy verloren geht.",
        "Ein Handy oder eine App, die 90 Tage nicht benutzt wurde, meldet sich von selbst ab. Dein PC bleibt dabei in der Community.",
    ],
    "2026-09-25a": [
        "Der Knopf zum Verbinden eines zweiten PCs daheim heißt jetzt „PC im Heimnetz koppeln“. Fürs Handy ist er nicht gedacht: Dort meldest du dich mit deinem KIplatz-Konto an.",
    ],
    "2026-09-24z": [
        "Eine Frage bleibt nicht mehr bei „schlägt in der Wikipedia nach“ hängen: Die Suche in der Wikipedia auf deinem Gerät dauert höchstens 5 Sekunden, und „Stopp“ hält sie sofort an.",
        "Mit der ganzen Wikipedia auf dem Gerät zeigt das Fenster nach dem Start gleich alles an, statt minutenlang nur Punkte.",
        "Am Handy folgt die Liste der Gespräche jetzt beim Aufwischen deinem Finger und gleitet auf oder zu.",
    ],
    "2026-09-24y": [
        "Ein Gerät mit der eigenen Wikipedia bereitet sie jetzt auch dann für die Suche nach Bedeutung auf, wenn es nebenbei für die Community arbeitet. Pause macht es nur für Fragen, beim Laden eines Modells und wenn die Grafikkarte zu heiß wird.",
        "Suchst du über das Menü nach einem Update, während KIplatz gerade selbst nachsieht, kommen sich die beiden nicht mehr in die Quere.",
    ],
    "2026-09-24x": [
        "Fragst du, was etwas anderes kostet, etwa das Klimaticket, bekommst du jetzt den Preis und nicht die Auskunft, dass KIplatz kostenlos ist.",
        "Beim Kilometergeld nennt KIplatz wieder den Betrag des Finanzministeriums, auch wenn dort „seit“ mit einem früheren Datum steht.",
    ],
    "2026-09-24w": [
        "Auf Fragen, was KIplatz kostet, was Credits sind und wofür es die Platzordnung gibt, antwortet KIplatz jetzt immer mit denselben geprüften Sätzen.",
    ],
    "2026-09-24v": [
        "Die Prüfung der Webseiten über Windows wirkt jetzt gleich nach dem Update, nicht erst nach dem nächsten Start von KIplatz.",
    ],
    "2026-09-24u": [
        "KIplatz lässt jetzt Windows prüfen, ob eine Webseite echt ist, so wie dein Browser. Damit liest es auch Seiten, die vorher an einer unvollständigen Kette von Zertifikaten gescheitert sind, etwa das Kilometergeld beim Finanzministerium.",
    ],
    "2026-09-24t": [
        "Stützt sich eine Antwort auf Quellen, muss jede Zahl, jedes Datum und jeder Name darin in einer Quelle stehen. Ein Satz, bei dem das nicht so ist, fliegt raus, bevor du ihn liest.",
        "Bleibt danach nichts übrig, sagt KIplatz ehrlich „Das weiß ich noch nicht.“, statt etwas zu erfinden.",
    ],
    "2026-09-24s": [
        "Bevor KIplatz antwortet, prüft ein zweites kleines Modell jede gefundene Stelle, ob sie wirklich zur Frage passt. Nur passende Stellen kommen in die Antwort.",
        "Passt nichts Gespeichertes wirklich, sucht KIplatz gleich live im Internet, statt aus halb passenden Stellen eine Antwort zu bauen.",
    ],
    "2026-09-24r": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-24q": [
        "Bei Fragen nach dem nächsten Termin zählt eine gemerkte Seite nur, wenn sie höchstens 12 Stunden alt ist; ein Datum vor heute wird nie als „nächstes“ genannt.",
    ],
    "2026-09-24p": [
        "KIplatz entscheidet selbst, ob eine Frage eine Suche im Internet braucht, und schreibt die Suchwörter selbst. Findet es nichts, sucht es bis zu zwei weitere Male mit anderen Wörtern und liest dabei andere Seiten.",
        "Es liest mehrere Seiten gleichzeitig und nimmt zuerst die, deren Auszug schon passt. Bei „nächstes“ und „letztes“ zählt, was zu heute passt, nicht ein Bericht vom Saisonende.",
        "Nennt eine Frage Deutschland, die Schweiz, ein Bundesland, einen Kanton oder eine Stadt, sucht KIplatz dort und rechnet die Feiertage für diese Region aus, etwa den Tag der Deutschen Einheit in Bayern.",
    ],
    "2026-09-24o": [
        "Antwortet eine zuständige Stelle beim ersten Mal nicht, fragt KIplatz gleich ein zweites Mal nach.",
    ],
    "2026-09-24n": [
        "Ein Gerät, das 100 GB oder mehr freigibt, holt sich die ganze deutsche Wikipedia und schlägt bei Wissensfragen zuerst dort nach, ohne ins Internet zu gehen. Unter der Antwort stehen der Artikel und der Stand.",
        "In freien Minuten bereitet das Gerät die Wikipedia für die Suche nach Bedeutung auf, die beliebtesten Artikel zuerst. Wie weit es ist, steht unter „Rechenkraft teilen“ und bei „Gemeinsamer Speicher“.",
    ],
    "2026-09-24m": [
        "Bei Fragen nach dem heutigen Stand liest KIplatz direkt bei der zuständigen Stelle nach, etwa für Fußballtabellen und Spielpläne, Leitzinsen, Ticketpreise und das Kilometergeld.",
        "Nennt eine Antwort ein Datum oder einen Betrag, der in keiner Quelle steht, streicht KIplatz den Satz, statt etwas Erfundenes zu zeigen. Wochentage neben einem Datum rechnet es selbst nach.",
        "Lücken wie „[Name]“ bleiben nie mehr in einem Text stehen.",
    ],
    "2026-09-24l": [
        "Feiertage und Herbstferien rechnet KIplatz selbst aus, mit dem richtigen Wochentag.",
        "Bei Fragen nach dem aktuellen Stand zählt nur, was aktuell ist: Gemerktes von einer früheren Saison oder einem früheren Jahr wird übergangen, und KIplatz sucht neu.",
    ],
    "2026-09-24k": [
        "Folgefragen werden nicht mehr mit der Frage davor vermischt: Auf „LASK Spielplan“ und dann „Rapid Spielplan“ sucht KIplatz nur nach Rapid.",
        "Bei Spielplänen, Tabellen und Terminen sucht KIplatz nach der aktuellen Saison oder dem aktuellen Jahr und sortiert Seiten mit einem älteren Stand aus.",
        "Weiß KIplatz etwas nicht, sucht es von selbst im Internet, statt zu fragen.",
    ],
    "2026-09-24j": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-24i": [
        "Das Programm holt Bausteine nach, die nach deiner Installation dazugekommen sind, zum Beispiel für den QR-Code beim Einladen und zum Lesen von PDF-Dateien.",
        "Am iPhone sagt die Handy-Seite jetzt gleich zu Beginn, dass du sie zuerst zum Home-Bildschirm hinzufügst und dich erst dort anmeldest.",
    ],
    "2026-09-24h": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-24g": [
        "Die Anmeldung bei der Community übersteht jetzt auch eine Neueinrichtung des Programms.",
        "Jedes Gerät hat einen eigenen Namen: Heißt ein neues Gerät wie ein vorhandenes, bekommt es eine Nummer dazu.",
        "In der ZIP-Datei liegt eine Anleitung auf Deutsch und Englisch.",
    ],
    "2026-09-24f": [
        "Rechenkraft, Arbeitsspeicher und Festplatte stellst du jetzt mit Schiebereglern ein, zum Beispiel 10 %, 1,5 GB oder 50 MB. Ein Strich zeigt die Empfehlung.",
        "Du wählst selbst, auf welchem Laufwerk das gemeinsame Wissen liegt, etwa auf einer leeren zweiten Festplatte. KIplatz legt dort nur den eigenen Ordner „KIplatz-Speicher“ an und nimmt Vorhandenes geprüft mit.",
    ],
    "2026-09-24e": [
        "Jede Frage geht jetzt an den PC mit dem stärksten Modell, der rechtzeitig fertig wird. Ein kleineres Modell springt nur ein, wenn die stärkeren beschäftigt sind, und das steht dann unter der Antwort.",
        "Vorbereitete Antworten für die Suche schreiben nur noch starke Modelle. Kleinere PCs helfen beim Aufbereiten der Texte und beim Speichern.",
        "Ist ein Gerät nicht bei der Community angemeldet, steht das jetzt oben im Fenster, mit einem Knopf zum Dazukommen.",
    ],
    "2026-09-24d": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-24c": [
        "Fragen nach Aktionen, Angeboten und Preisen in Geschäften schaut KIplatz jetzt im Internet nach. Es sucht dabei zweimal: einmal genau "
        "mit den Geschäften, die du nennst, und einmal allgemein in den Flugblättern. An die Suche gehen nur die Suchwörter, nicht deine Frage.",
        "Während KIplatz arbeitet, dreht sich das Symbol neben der Antwort. Daneben stehen die Sekunden und was gerade passiert, "
        "zum Beispiel „sucht im Internet nach …“ oder „schreibt die Antwort …“. Am Handy steht dort nicht mehr „rechnet“, sondern "
        "„ein PC aus der Community erarbeitet deine Antwort“.",
        "Lange Antworten mit vielen gefundenen Seiten passen jetzt immer ins Modell. Vorher konnte eine Antwort mitten im Wort abbrechen, "
        "oder das Nachprüfen wartete mehrere Minuten und kam ohne Antwort zurück. Schafft ein PC eine Frage nicht, übernimmt sofort ein anderer.",
        "Wetterangaben aus dem Internet bekommen keinen gelben Ring mehr, wenn die Zahlen stimmen. Eine falsche Zahl bekommt dafür einen roten Punkt.",
        "Am Handy stehen beim neuen Gespräch das Symbol und „Willkommen“ in der Mitte und das Eingabefeld gleich darunter. Die Sätze der Antwort "
        "sind nicht mehr unterstrichen, und nach dem Senden geht die Tastatur weg.",
        "Eine alte Verknüpfung „Community AI“ auf dem Desktop ersetzt das Programm beim Start durch „KIplatz“ mit dem neuen Logo.",
    ],
    "2026-09-24b": [
        "Der Stopp-Knopf neben dem Senden-Knopf erscheint nur noch, während eine Antwort läuft, und die Zeile „Wird gleich gesendet“ nur, "
        "wenn wirklich eine Frage wartet. Bisher waren beide immer zu sehen.",
    ],
    "2026-09-24a": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-23ze": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-23zd": [
        "Die Hausordnung heißt jetzt Platzordnung, passend zum Platzl. Die Regeln selbst bleiben gleich.",
    ],
    "2026-09-23zc": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-23zb": [
        "Fragst du etwas über KIplatz selbst, bekommt die KI zuerst die von Menschen geschriebene Selbstauskunft als Quelle und die Anweisung, nichts dazuzuerfinden: "
        "keine anderen Orte, Personen oder Aufgaben des Servers als dort stehen.",
        "Die dünne rote Linie für „Widerspruch zur Quelle“ erscheint nur noch, wenn ein Satz eine Quelle nennt und kein einziges Wort daraus stammt; "
        "eine freie Umschreibung bekommt nur den Punkt.",
    ],
    "2026-09-23za": [
        "Bildschirmfotos und Bilder kannst du jetzt mit Strg+V einfügen oder mit der Maus ins Fenster ziehen; sie hängen am Gespräch wie ein gewähltes Bild "
        "und bleiben auf deinem Gerät. Anschauen kann sie die KI auf einem Rechner mit Grafikkarte.",
    ],
    "2026-09-23z": [
        "„Live im Netz nachprüfen“ steht wieder unter jeder Antwort, und der Klick heißt jetzt wirklich Netz: Die Community-Suche am Server sucht mit deiner Frage, "
        "die besten Seiten werden gelesen, und die neue Antwort nennt sie als Quellen. Steht eine Adresse wie news.at in der Frage, wird diese Seite live gelesen.",
        "Findet die Suche nichts oder ist sie gerade nicht erreichbar, sagt das Programm das in einem Satz, statt eine neue Antwort ohne Quelle zu schreiben. "
        "Bisher hat eine Sperre kurze Fragen wie „Sag mir was zu KIplatz“ gar nicht erst ins Netz gelassen.",
    ],
    "2026-09-23y": [
        "„Jetzt live nachprüfen“ steht nur noch unter Antworten, bei denen es etwas neu zu lesen gibt (Wetter, Schlagzeilen, eine live gelesene Seite). "
        "Unter Antworten aus dem Wissensspeicher gibt es nichts nachzulesen; dort zeigt „Details zur Antwort“ die Quellen.",
    ],
    "2026-09-23x": [
        "Die Startseite von kiplatz.at zeigt die beantworteten Fragen seit dem Start, nicht mehr nur die von heute.",
        "Der Community-Server zählt dafür Summen mit, die nie gelöscht werden; die Tageszahlen bleiben wie bisher 30 Tage.",
    ],
    "2026-09-23v": [
        "Keine gewellten oder gepunkteten Linien mehr unter ganzen Sätzen. Die Ampel steht als Zeichen hinter dem Satz: ein Ring für unsicher, ein voller Punkt für ohne Beleg.",
        "Rechtsklick auf ein Gespräch in einem Projekt zeigt „Aus dem Projekt nehmen“.",
    ],
    "2026-09-23t": [
        "Projekte in der Seitenleiste lassen sich mit einem Klick auf den Namen ein- und ausklappen; eingeklappt steht die Zahl der Gespräche dahinter, und das Gerät merkt sich, was zu ist.",
        "Das Rechtsklick-Menü eines Gesprächs bleibt immer ganz im Fenster, auch beim letzten Eintrag unten im Archiv.",
        "Ein Projekt hat einen Punkt davor und ein eigenes Rechtsklick-Menü: umbenennen, auflösen (die Gespräche bleiben) oder samt Gesprächen löschen.",
    ],
    "2026-09-23q": [
        "Allgemeine Optimierungen wurden durchgeführt.",
    ],
    "2026-09-23p": [
        "Hitzebremse: Vor jedem Arbeitsschritt für die Community liest dein Gerät die Temperatur der Grafikkarte. Ab 85 °C macht es 60 Sekunden Pause und schaut dann wieder nach; "
        "das Fenster zeigt es an. Wo es keinen Messwert gibt, gibt es auch keine Bremse.",
        "Der Prüfstand-Knopf „Jetzt prüfen“ wartet, bis die laufende Rechenarbeit ihren Auftrag beendet hat, und läuft nie gleichzeitig mit ihr.",
    ],
    "2026-09-23o": [
        "Barrierefreiheit: Jedes Eingabefeld und jeder Knopf im Fenster und am Handy ist für Vorleseprogramme beschriftet, der Tastaturfokus ist sichtbar, "
        "die Ampel unter Antworten zeigt Unsicheres auch als gepunktete Linie, nicht nur als Farbe, und wer in Windows weniger Bewegung eingestellt hat, sieht keine Animationen. "
        "Die Website hat eine Barrierefreiheitserklärung und Nutzungsbedingungen mit Kennzeichnung der KI-Antworten.",
        "Antwortest du auf eine Rückfrage von KIplatz nur mit „Ja“, sucht es jetzt nach deiner eigentlichen Frage statt nach dem Wort „Ja“. "
        "Enthält eine Antwort drei oder mehr Sätze ohne ein einziges Wort aus den Quellen, wird sie verworfen und KIplatz antwortet noch einmal, kurz und ehrlich. "
        "Rückfragen an dich bekommen keinen roten Punkt mehr, und ein Widerspruch zur Quelle ist gewellt unterstrichen statt durchgestrichen.",
        "Fragen, die dein Gerät für dich selbst beantwortet, zählen jetzt auf der Website als beantwortete Fragen mit, nur als Zahl.",
    ],
    "2026-09-23n": [
        "Messwerte auf der Website: Nach jeder Antwort für ein anderes Mitglied misst dein PC, wie ausgelastet er war und, wenn die Grafikkarte es hergibt, "
        "wie warm sie war und wie viel Strom sie gebraucht hat. Nur Zahlen, keine Namen. Die Statistik-Seite zeigt daraus Wartezeit, Tempo, Temperatur und Leistung des Netzes.",
        "Am Community-Server liegen die Wörter und Texte aller Abschnitte jetzt in einem Index auf der Platte statt im Arbeitsspeicher; die Suche bleibt gleich gut und braucht Millisekunden. "
        "Scheiben, die dreifach bei Mitgliedern liegen und geprüft sind, gibt der Server nach einem Tag ab: Der gemeinsame Speicher liegt dann wirklich bei der Community, nicht in einem Rechenzentrum.",
    ],
    "2026-09-23m": [
        "Fragen ohne Prompt-Kunst: Fragst du nach einem Plan, einer Empfehlung oder einer Entscheidung, prüft KIplatz zuerst, ob dir etwas Wichtiges fehlt, "
        "und stellt dann höchstens zwei kurze Fragen; hast du schon alles gesagt, legt es gleich los.",
        "Neben dem Eingabefeld gibt es den Knopf „Frage vervollständigen“: KIplatz schreibt deine Bitte vollständig auf, mit Lücken in eckigen Klammern für alles, was du noch dazusagen musst. "
        "Du füllst aus und schickst ab.",
        "Beim Start stellt KIplatz dir einmal drei Fragen (Name, Ort, was dich beschäftigt) und merkt sie sich auf deinem Gerät. Zu deinen Themen sammelt dein PC in freier Zeit "
        "Wissen aus der Community, privat, nur für dich. Dazu zehn Skill-Vorlagen für den Alltag unter Skills, fertig zum Übernehmen.",
    ],
    "2026-09-23l": [
        "Sicherheit: Die Schlüssel des Programms liegen auf deinem Gerät "
        "nicht mehr im Klartext, sondern von Windows verschlüsselt (nur dein Windows-Benutzer auf diesem Gerät kann sie lesen); die Umstellung passiert von selbst.",
        "Der Anmeldelink fürs Handy trägt nicht mehr das Geheimnis, sondern einen Code, der 10 Minuten und einmal gilt; alte Links gelten nicht mehr.",
        "Die Anmeldung mit dem KIplatz-Konto geht nur noch zu unserer Werkstatt, egal was ein Server antwortet.",
    ],
    "2026-09-23k": [
        "Im Morgenbericht steht der Tag beim Wetter fett, zwischen heute und morgen ist eine Leerzeile, und unter der letzten Schlagzeile ist mehr Abstand zur Zeile „Stimmt das?“.",
    ],
    "2026-09-23j": [
        "Der Morgenbericht zeigt unter jeder Schlagzeile eine Zeile „Zum Beitrag auf …“ mit dem Namen der Nachrichtenseite zum Anklicken statt der langen Adresse; "
        "der Beitrag öffnet sich in deinem Browser, und zwischen den Themen ist eine Leerzeile.",
        "Trägst du unter Einstellungen einen neuen Ort ein, wird der Bericht von heute gleich noch einmal gemacht und geöffnet; vorher blieb der alte ohne Wetter stehen.",
        "Während die KI vorbereitet wird, läuft ein Balken über alle Dateien („1 von 2“), statt für jede Datei neu von vorne zu beginnen.",
    ],
    "2026-09-23i": [
        "Der gemeinsame Speicher liegt jetzt in Scheiben auf den Geräten der Mitglieder: Gibst du in der Freigabe Platz auf der Festplatte frei (Standard 500 MB), "
        "hält dein Gerät gepackte Scheiben des gemeinsamen Wissens, jede dreifach im Netz, mit Prüfsumme; einmal am Tag prüft der Server eine Scheibe nach und holt sie zurück, wenn seine Kopie fehlt. "
        "Unter „Meine Community“ siehst du, was dein Gerät hält; je Scheibe und Stichprobe gibt es einen Credit.",
        "Der Morgenbericht zeigt jede Schlagzeile ganz (vorher war sie am ersten Doppelpunkt abgeschnitten, etwa „Ukraine“ statt „Ukraine: Tote bei Angriffen“), "
        "mit Quelle und einem Link zum Artikel, und mischt mehrere freie Nachrichtenfeeds ohne Bezahlschranke aus deinem Land (Österreich, Deutschland oder Schweiz; "
        "welche, steht in der Datenschutzerklärung). Welches Land, sagt der Ort in den Einstellungen.",
        "Hast du im Morgenbericht noch keinen Ort, steht jetzt dabei, dass du ihn unter Einstellungen einträgst und dort „Jetzt erstellen“ drückst, "
        "statt bis zum nächsten Morgen zu warten.",
    ],
    "2026-09-23h": [
        "Sicherheit und Datenschutz nachgezogen: Ein Update wird nur noch eingespielt, wenn das unterschriebene Paket wirklich neuer ist als dein Programm; "
        "das Protokoll auf deinem Gerät verbirgt auch den Rechnernamen, E-Mail-Adressen und IPv6-Adressen, und „Fehler melden“ schickt keine Adressen gelesener Seiten mit.",
        "Der Vorschlag für deinen Gerätenamen ist neutral („Gerät-1a2b“) statt des Namens deines Computers, und die Protokolldatei des KI-Bausteins wird bei 1 MB gekürzt.",
        "Am Community-Server: Nachrichten aus dem Kontaktformular liegen ohne Internetadresse und höchstens 30 Tage, das Protokoll enthält keine Namen, Adressen oder Titel, "
        "beim Austritt verschwindet dein Gerätename auch aus „Fehler der Woche“ und den Prüfstand-Berichten, und die Datenschutzerklärung des Programms ist auf dem Stand vom 23.09.2026.",
    ],
    "2026-09-23g": [
        "Deine eigene Frage hat jetzt Vorrang: Rechnet dein Gerät gerade für die Community (Abschnitte vertiefen, Beiträge prüfen), "
        "hält es damit inne, sobald du fragst, und macht eine halbe Minute nach der Antwort weiter. Gemessen auf einem Laptop mit Grafikkarte: "
        "eine Antwort kam in 1 bis 3 s statt 12 bis 28 s, wenn nebenbei gerechnet wurde.",
        "Das Bedeutungs-Modell läuft nur noch einmal (vorher zweimal, für Suche und Rechenarbeit getrennt), und der Bild-Zusatz wird erst geladen, "
        "wenn du wirklich ein Bild schickst. Beides zusammen spart rund 2 GB Grafikspeicher; war die Karte voll, kroch jede Antwort.",
        "Der Schlüssel zum KI-Baustein auf deinem Gerät steht nicht mehr in dessen Startbefehl, den jedes Programm am Rechner lesen könnte, "
        "sondern wird ihm still übergeben.",
    ],
    "2026-09-23f": [
        "Die Suche im Wissen der Community ist schneller und treffsicherer: Der Server hält die Wörter aller Abschnitte im Speicher statt sie bei jeder Frage neu zu zerlegen (vorher 2,8 s je Suche), schaut sich doppelt so viele Kandidaten an, bevor er die besten wählt, lässt Literaturlisten und Weblinks aus Artikeln weg und stellt vorbereitete Antworten nur noch vor, wenn die seltenen Wörter der Frage wirklich passen.",
    ],
    "2026-09-23e": [
        "Antworten kommen auf kleinen Laptops schneller: Rechnet die Community für dich, schaut dein Gerät jetzt jede halbe Sekunde nach und die Rechner der Community fragen jede Sekunde nach Arbeit, solange Fragen kommen. Rechnet dein Gerät ohne Grafikkarte selbst, liest das Modell nur noch den halben Vorspann und zwei statt vier Auszüge, merkt sich den festen Teil ab der zweiten Frage, und du siehst jeden fertigen Satz sofort statt alles am Ende.",
    ],
    "2026-09-23d": [
        "Der Prüfstand: Ein PC der Community stellt KIplatz jede Nacht dieselben Prüffragen, darunter jede Berichtigung, die ein Mitglied eingereicht hat, und meldet, wie viele richtig waren. Das Programm prüft nach Wörtern, nicht das Modell selbst.",
    ],
    "2026-09-23c": [
        "Sprechen statt tippen hört jetzt mit einem eigenen Hör-Modell zu, das im selben Baustein läuft wie die KI: einmal rund 1 GB holen, danach versteht es dich auf der Grafikkarte in einer Sekunde, am Prozessor in ein paar Sekunden. Die Windows-Spracherkennung bleibt nur noch als Notweg, wenn der Download nicht klappt.",
    ],
    "2026-09-23b": [
        "Kurze Aufnahmen wie „test, test“ brachten die Windows-Spracherkennung aus dem Tritt (sie meldete das Ende der Aufnahme als Fehler). Behoben; das Programm liest jetzt bis zum Ende und gibt den Text zurück.",
    ],
    "2026-09-23a": [
        "Sprechen statt tippen versteht dich jetzt mit der Spracherkennung, die in Windows steckt: sofort, ohne Download, offline, und Windows lässt sie immer laden. Mikrofon drücken, sprechen, noch einmal drücken, der Text steht im Eingabefeld.",
    ],
    "2026-09-22i": [
        "Blockiert Windows einen Baustein fürs Sprechen (Smart App Control lässt nur signierte Programmteile laden), sagt das Programm das jetzt in einem Satz statt mit einem Windows-Fenster. Tippen geht weiter; Sprechen kommt, sobald die Bausteine signiert sind.",
    ],
    "2026-09-22h": [
        "War eine Antwort falsch, sagst du es mit Daumen runter und schreibst dazu, wie es richtig wäre. Dein Gerät hält sich ab sofort daran, bei derselben Frage kommt deine Fassung. Schickst du die Berichtigung an die Community, prüft sie ein anderes Gerät, danach gilt sie für alle.",
    ],
    "2026-09-22g": [
        "Fragst du KIplatz, was es ist, wer es ist, was es kann oder wie es arbeitet, bekommst du einen festen, von Menschen geschriebenen Text statt einer Antwort des Modells. Der Satz „Ich bin KIplatz aus KIplatz“ ist damit Geschichte.",
    ],
    "2026-09-22f": [
        "Der Credits-Verlauf sagt jetzt, wofür ein Credit war: „Frage eines Mitglieds beantwortet“, „Abschnitt vertieft“, „Vertiefung eines anderen Geräts geprüft“, „Abschnitte in Zahlen gerechnet“. Vorher stand bei jeder Art von Arbeit dieselbe Zeile „0 Abschnitte für die Community gerechnet“.",
    ],
    "2026-09-22e": [
        "Was beim Kontobuch schon galt, gilt jetzt für jede Datei, die das Programm schreibt (Einstellungen, Gespräche, Gedächtnis, Gerätezugang, Wissen): Erst wird auf die Platte gewartet, dann ersetzt die neue Datei die alte. Ein hartes Ausschalten kann so keine leere Datei mehr hinterlassen.",
        "Ist trotzdem einmal eine Datei beschädigt, legt das Programm sie mit Datum daneben, beginnt mit dem Startwert neu und sagt dir das unter „Meine Community“; nichts wird gelöscht.",
    ],
    "2026-09-22d": [
        "Zeigt das Programm „? Credits“ und auf „Meine Community“ den Satz „die Credits-Datei ist beschädigt“, repariert es das jetzt selbst: Die kaputte Datei bleibt daneben liegen, das Kontobuch wird neu angelegt, und der Stand kommt aus der Bestenliste der Community. So eine Datei entsteht, wenn der PC direkt nach dem Speichern hart ausgeht; ab jetzt wird beim Speichern auf die Platte gewartet, damit das nicht wieder passiert.",
    ],
    "2026-09-22c": [
        "Dein KIplatz-Konto gilt jetzt auch im Programm: Unter „Meine Community“ meldest du dich mit einem Klick an, die Anmeldung läuft im Browser auf der Anmeldeseite von KIplatz, mit Passwort oder mit Google. Das Programm bekommt kein Passwort zu sehen und behält keinen Zugang zur Werkstatt.",
        "Credits und Bestenliste zählen dann für dein Konto, über alle Geräte, auf denen du angemeldet bist. „Abmelden“ löst das Gerät wieder vom Konto; ohne Konto geht alles weiter wie bisher.",
    ],
    "2026-09-22b": [
        "Das KIplatz-Symbol sitzt jetzt wirklich in der Mitte: auf der Verknüpfung, in der Taskleiste, bei der Uhr und im Fenster. Die bisherigen Symboldateien waren nach rechts verschoben, darum wirkte das Symbol schief; alle Größen entstehen jetzt aus einer sauberen Vorlage.",
        "Zeigt Windows noch das alte Symbol, hält es das nur im Zwischenspeicher: einmal abmelden und wieder anmelden oder den Rechner neu starten, dann liest Windows das Symbol frisch ein.",
    ],
    "2026-09-21b": [
        "Das Symbol in der Taskleiste, bei der Uhr und auf der Verknüpfung ist jetzt freigestellt, mittig und füllt das Feld aus, so wie bei anderen Programmen. Vorher hatte es einen eigenen dunkelgrünen Hintergrund und Luft rundherum.",
    ],
    "2026-09-21a": [
        "Das Fenster trägt jetzt das KIplatz-Logo: in der Titelleiste, in der Taskleiste und beim Wechseln mit Alt + Tab. Vorher stand dort das Python-Symbol, weil das Programm über das signierte Python von python.org läuft.",
        "Die Programmdatei KIplatz.exe im Programmordner behält das Python-Symbol: Sie ist eine unveränderte, signierte Kopie von pythonw.exe, und ein eigenes Symbol darin würde die Unterschrift zerstören. Zum Anheften an die Taskleiste nimm die Verknüpfung „KIplatz“ vom Desktop (Rechtsklick, „An Taskleiste anheften“); die trägt das Logo.",
    ],
    "2026-09-20g": [
        "Das Programm heißt jetzt KIplatz: der Platz, an dem Menschen ihre eigene KI betreiben, mitrechnen, reden und bauen. Die Verknüpfung auf dem Desktop und im Startmenü und die Startdatei heißen jetzt ebenfalls KIplatz; der Programmordner bleibt, wo er ist.",
        "KIplatz hat ein Logo: das Sechs-Personen-Symbol, links oben im Fenster, bei der Uhr, auf der Verknüpfung und auf der Handy-Seite. Und die KI im Fenster heißt jetzt auch KIplatz statt „Unser Modell“.",
        "Autostart repariert: Auf manchen Rechnern zeigte der Windows-Eintrag noch auf die alte Programmdatei, deshalb startete das Programm nach dem Anmelden nicht. Der Eintrag wird jetzt bei jedem Start geprüft und bei Bedarf erneuert.",
    ],
    "2026-09-20f": [
        "Tagesbilanz: Unter „Meine Community“ steht, was dein Rechner heute getan hat und was das ganze Netz geschafft hat. Beim Öffnen sagt dir das Programm einmal am Tag, was in deiner Abwesenheit passiert ist.",
        "In der Früh holt dein Rechner, wenn er gerade nichts zu tun hat, Wetter und Schlagzeilen für alle Mitglieder vor; abschaltbar unter Einstellungen.",
    ],
    "2026-09-20e": [
        "Vertiefen läuft runder: Bringt KIplatz zu einem Abschnitt zweimal keine saubere Zusammenfassung mit Fragen zustande, gibt dein Rechner ihn an einen anderen weiter, statt es jede Minute neu zu versuchen.",
    ],
    "2026-09-20d": [
        "Der Community-Server holt jetzt von selbst Nachschub: lange, geprüfte Artikel der deutschen Wikipedia und weitere geprüfte Quellen. So haben die Rechner immer etwas zu rechnen und zu vertiefen.",
    ],
    "2026-09-20c": [
        "Dein Rechner arbeitet jetzt auch, wenn niemand fragt: Er vertieft das gemeinsame Wissen. Zu jedem Abschnitt schreibt er eine Zusammenfassung und Fragen mit Antworten, ein zweiter Rechner prüft sie. Geprüfte Antworten stehen bei der nächsten passenden Frage sofort bereit.",
        "Unter „Rechenkraft teilen“ siehst du, wie viele Abschnitte dein Rechner heute vertieft und geprüft hat; jeder zählt einen Credit.",
    ],
    "2026-09-20b": [
        "Gedächtnis mit Zustimmung: Schreib „Merk dir: ich wohne in Gmunden“, und KIplatz weiß es ab jetzt. „Vergiss das mit …“ löscht es, „Was weißt du über mich?“ zeigt alles. Bleibt auf diesem Gerät; ein Rechner der Community bekommt es nie. Liste und Schalter unter Einstellungen.",
        "Morgenbericht: Unter Einstellungen Zeit und Ort eintragen, dann kommt jeden Tag Wetter und Schlagzeilen als neues Gespräch, auf Wunsch vorgelesen.",
        "Strg + Leertaste nimmt markierten Text aus dem Programm davor mit: Der Text steht in Anführungszeichen im Eingabefeld, du schreibst die Frage dazu.",
    ],
    "2026-09-20a": [
        "Fundament: Der Server sichert seine Daten jetzt täglich und wird alle 5 Minuten geprüft; jedes Paket im Programm hat eine feste Prüfsumme.",
        "Muss die Community einmal kurz anhalten, siehst du den Grund, und dein Gerät antwortet selbst.",
    ],
    "2026-09-19p": [
        "Nach einem Update kam manchmal die Meldung, ein Anschluss fürs Heimnetz sei belegt. Behoben: Das alte Programm gibt ihn vor dem Neustart frei, das neue versucht es bei Bedarf von selbst noch einmal.",
    ],
    "2026-09-19o": [
        "Die Knöpfe in der Frageleiste („+“, Mikrofon, Senden, Stopp) sind kleiner und ruhiger.",
    ],
    "2026-09-19n": [
        "Unter dem Eingabefeld gibt es jetzt ein „+“: Datei, Bild, Ordner oder Bildschirm dazugeben, mit Symbol und Wort. Rechts neben Senden das Mikrofon in voller Knopfgröße.",
        "Sprechen statt tippen: Mikrofon drücken, sprechen, noch einmal drücken. Der Text steht dann im Eingabefeld, du liest ihn und schickst ihn ab. Beim ersten Mal holt das Programm die Sprachbausteine (200 MB). Alles bleibt am Gerät.",
        "Vorlesen geht jetzt wirklich; kürzere Texte im ganzen Programm, kein Einladungscode mehr beim ersten Start, „Wissen“ über die volle Breite, kein „Testbetrieb“ mehr im Fenstertitel.",
    ],
    "2026-09-19m": [
        "🎤 neben dem Eingabefeld: drücken, sprechen, noch einmal drücken. Der Text steht dann im Eingabefeld, du liest ihn und schickst ihn ab. Beim ersten Mal holt das Programm die Sprachbausteine (200 MB). Alles bleibt am Gerät.",
        "Vorlesen (🔊) geht jetzt wirklich; die Windows-Stimme wurde vorher nicht gefunden.",
        "Kürzere Texte im ganzen Programm, kein Einladungscode mehr beim ersten Start, „Wissen“ über die volle Breite, „Über“ mit Trennlinien, kein „Testbetrieb“ mehr im Fenstertitel.",
    ],
    "2026-09-19l": [
        "Antwortet ein anderer Rechner der Community für dich, siehst du die Wörter jetzt kommen, während er tippt.",
        "Strg + Leertaste bringt das Fenster von überall nach vorne, gleich mit dem Cursor im Eingabefeld.",
        "🔊 unter jeder Antwort liest sie mit der Windows-Stimme vor. 🖥 neben dem Eingabefeld gibt ein Bild deines Bildschirms ins Gespräch (nur mit Grafikkarte).",
        "Neuer Bereich „Was verlässt meinen Rechner“: jede Verbindung des Programms, wohin und wozu, ohne Inhalte.",
    ],
    "2026-09-19k": [
        "Beim ersten Start fragt das Programm nur noch zwei Dinge: den Gerätenamen und den Einladungscode. Danach kannst du sofort fragen.",
        "Fehler stehen in einfachen Worten da. Unter Hilfe gibt es „Fehler melden“: ein Klick, der Bericht geht an uns, ohne deine Fragen.",
        "Community AI steht jetzt in den Windows-Apps und im Startmenü. Beim Einrichten ist der Autostart an; am Akku rechnet ein Laptop nicht für andere.",
    ],
    "2026-09-19j": [
        "Die Seite „Wissen“ ist kompakt: Summen, die neuesten Einträge, Suche und Filter nach Art.",
        "Ein zweiter Klick auf das Desktop-Symbol öffnet kein zweites Programm mehr, sondern holt das laufende nach vorne.",
    ],
}

ZURUECKGEHALTEN: dict[str, list[str]] = {
    "2026-10-12d": [
        "Neu unter „Meine KI“: ein Frag-Fenster für deinen Betrieb oder Verein. Besucher deiner Website stellen Fragen, und dein PC beantwortet sie aus einem Ordner mit deinen Unterlagen, ohne Cloud.",
    ],
}

KURZ_JE_TAG: dict[str, list[str]] = {
    "2026-10-26": [
        "Fragen auf kiplatz.at kommen jetzt als erste dran, und du siehst, woran der PC gerade arbeitet",
    ],
    "2026-10-25": [
        "Ist dein Flug verspätet oder gestrichen, rechnet KIplatz dir aus, wie viel Entschädigung dir zusteht",
        "In Programm und App fügst du jetzt mehrere PDFs zu einer zusammen, ohne Hochladen",
        "Frag, ob die KI-Verordnung deinen Betrieb betrifft, und KIplatz sagt dir, was jetzt gilt und was später kommt",
    ],
    "2026-10-24": [
        "KIplatz zeigt dir YouTube-Videos jetzt direkt in der Antwort, abgespielt wird erst nach deinem Klick",
        "Frag nach dem günstigsten Anbieter, und KIplatz vergleicht mehrere Shops in einer Tabelle",
        "Ein Foto oder PDF im Anhang sucht KIplatz jetzt gezielt im Internet nach",
    ],
    "2026-10-21": [
        "„Ja, live nachprüfen“ sucht jetzt immer im Internet, auch bei Bergen mit bekanntem Namen",
    ],
    "2026-10-20": [
        "KIplatz läuft jetzt auch auf Linux und am Mac mit Apple-Chip, als Helfer ohne Fenster",
        "Dein PC tritt jetzt mit deinem KIplatz-Konto bei, ganz ohne Code",
        "Unter jeder Antwort steht jetzt, auf welchem PC wirklich nachgeschlagen wurde",
    ],
    "2026-10-19": [
        "Antworten aus dem Lexikon am eigenen PC kommen jetzt auch, während das Gerät im Hintergrund daran arbeitet",
        "Ein großer Download im Hintergrund hält deine eigene Frage nicht mehr auf",
        "Ein Termin mit Jahreszahl kommt gleich aus dem Kalender, auch auf Englisch",
    ],
    "2026-10-18": [
        "KIplatz kennt Feiertage weltweit beim Namen und rechnet Termine wie den ersten Advent selbst aus",
        "Bei Einreise, Visum und Ämtern in jedem Land schaut KIplatz jetzt aktuell bei den Behörden nach",
        "Auf Englisch merkt sich KIplatz jetzt Sätze, liest den Morgenbericht und klingt natürlicher",
    ],
    "2026-10-17": [
        "Fragen wie „Was soll ich tun, wenn …“ bekommen jetzt gleich eine Antwort statt Rückfragen",
        "Auch auf Englisch weiß KIplatz jetzt, was Feber bedeutet",
        "Antworten auf Alltagsfragen kommen jetzt oft schneller, weil weniger neu geschrieben wird",
    ],
    "2026-10-16": [
        "KIplatz weiß jetzt, was Paradeiser, Feber und ein Haberer sind",
        "Fragen zu Filmen, Gewittern und Datumsspannen bekommen jetzt eine richtige Antwort",
        "Fragen wie „Wie funktioniert das Pfand?“ bekommen wieder eine echte Antwort",
    ],
    "2026-10-15": [
        "Umrechnungen, Prozent und Backzeiten bekommen wieder eine richtige Antwort",
        "Fragen nach Regeln und Pflichten sucht KIplatz immer im Internet und nennt keine aus dem Gedächtnis",
        "Mit der rechten Maustaste kannst du im Programm jetzt kopieren und einfügen",
    ],
    "2026-10-14": [
        "Die ersten 100 PCs, die mithelfen, sind Gründungsmitglieder, mit einer Nummer, die bleibt",
        "Die Nummer steht in der Bestenliste, in deiner Geräteliste und als Abzeichen im Platzl",
        "Unter einer belegten Antwort stehen jetzt alle Quellen, aus denen sie stammt",
    ],
    "2026-10-13": [
        "KIplatz hat jetzt einen Liveticker: Spielstände und Livescores aus Fußball, Eishockey, NFL und NBA auf Frage",
        "Frag einfach: Wie steht es bei Sturm Graz, wer spielt heute in der Bundesliga, wann ist das nächste Rennen",
        "Meine KI kennt jetzt Fachgebiete: Programmieren, Web und KI am eigenen PC bringen geprüfte Quellen mit",
    ],
    "2026-10-12": [
        "Im neuen Wiki schlägst du eine bessere Antwort mit Quelle vor, und die Community stimmt darüber ab",
        "Hat ein Vorschlag mindestens 5 Ja, bekommt jeder diese Antwort, mit der Quelle darunter",
        "Findet die Suche zu etwas Unbekanntem wirklich nichts, sagt KIplatz das jetzt ehrlich",
    ],
    "2026-10-11": [
        "Umrechnen und Rechnen klappt jetzt zuverlässig, von Millimetern bis Kilometern, auch mit Brüchen",
        "Euro in Dollar, Tage bis Weihnachten, Zeitzonen und Kreditrate: KIplatz antwortet jetzt sofort und genau",
        "Gleichungen mit x, Rezepte für mehr Personen und Brutto zu Netto in Österreich löst KIplatz mit Rechenweg",
    ],
    "2026-10-10": [
        "Die Antwort verschwindet beim Prüfen nicht mehr kurz, du liest an derselben Stelle weiter",
        "Bremst eine Suchmaschine, fragt KIplatz jetzt von selbst andere, damit deine Frage beantwortet wird",
        "Ein Bild gleich nach dem Start der KI lässt sie nicht mehr ausgehen, der Bild-Zusatz lädt jetzt zuverlässig",
    ],
    "2026-10-09": [
        "Beim Aufbereiten des Wissens bleibt dein PC an sehr langen Abschnitten nicht mehr hängen",
        "Auf Englisch zeigen Programm und App jetzt keine deutschen Reste mehr, auch nicht bei Zahlen und Meldungen",
        "Nach dem Anmelden bleibt die App nicht mehr stehen und fragt beim ersten Mal nur noch nach Name und Wohnort",
    ],
    "2026-10-08": [
        "Fehlt einer Zahl die Quelle, hat KIplatz im Internet schon mitgesucht und sagt nicht, es weiß es nicht",
        "Fragst du nach einer Länge oder einem Preis, findet KIplatz die Stelle mit der Zahl auch auf langen Seiten",
        "Einfache Zahlenfragen beantwortet KIplatz jetzt in wenigen Sekunden, ohne Umweg über eine Suche im Internet",
    ],
    "2026-10-07": [
        "KIplatz braucht beim Aufbereiten des Wissens jetzt viel weniger Arbeitsspeicher",
        "Sitzt du am PC, ruht die Arbeit im Hintergrund und Fragen anderer gehen trotzdem sofort",
        "Start für alle: Jedes Gerät beginnt wieder mit 100 Credits",
    ],
    "2026-10-06": [
        "Mit kleinem Modell schaut KIplatz bei Wissensfragen zuerst im Internet nach, mit Quelle",
        "Findet es nichts Verlässliches, sagt es das, statt zu raten",
        "„Wann siedet Wasser?“ hält KIplatz nicht mehr für eine Wetterfrage",
    ],
    "2026-10-05": [
        "KIplatz gibt es jetzt auch auf Englisch, am PC und am Handy",
        "Am PC anmelden mit dem Handy: QR-Code scannen, ohne Passwort, in ein paar Sekunden",
        "Was KIplatz noch prüft, steht blasser da und heißt „Entwurf, wird geprüft“",
    ],
    "2026-10-04": [
        "Anmelden ohne Passwort: Adresse eintippen, Code aus der Mail eintippen, fertig",
        "In der App mehrere Konten, Wechsel mit einem Tipp, etwa eines für die Familie",
        "Teams in der Bestenliste: mit Verein, Firma oder Freunden sammeln",
    ],
    "2026-10-03": [
        "Die KI kommt nur noch von unserem Server in Wien",
        "Ist der Server voll, bist du gleich von selbst an der Reihe",
        "Einfachere Datenschutzerklärung",
    ],
    "2026-10-02": [
        "Antworten kommen von PCs der Community, in wenigen Sekunden",
        "Weiß KIplatz etwas nicht, sucht es nach und sagt es ehrlich",
        "Mehr Datenschutz und mehr Sicherheit im Heimnetz",
    ],
}


GESCHICHTE_JE_TAG: dict[str, dict[str, str]] = {
    "2026-10-25": {
        "haken": "Frag KIplatz ab heute „Flug Linz nach Antalya 5 Stunden verspätet, was steht mir zu?“, und du bekommst den Betrag nach der EU-Verordnung.",
        "text": "KIplatz misst dafür die Luftlinie zwischen den Flughäfen, so wie es die Verordnung verlangt. Es sagt dir auch, wann die Fluglinie nicht zahlen muss und wo du Hilfe bekommst, wenn sie sich querlegt. Und wer wissen will, ob die KI-Verordnung den eigenen Betrieb betrifft, bekommt nach vier kurzen Angaben eine klare Antwort: was jetzt gilt, was später kommt und was man nicht braucht.",
    },
    "2026-10-24": {
        "haken": "Frag KIplatz ab heute „Zeig mir Gameplay zu Enshrouded“, und das Video steht gleich in der Antwort, mit Vorschaubild.",
        "text": "Und wer „Wo bekomme ich diesen Reifen am günstigsten?“ fragt, bekommt jetzt eine Tabelle mehrerer Shops nach Preis. Jeder Preis wird gegen die Seite des Shops geprüft, bevor er dasteht.",
    },
    "2026-10-21": {
        "haken": "Frag KIplatz ab heute „Wie hoch ist der Traunstein?“, und tippst du auf „Ja, live nachprüfen“, wird wirklich im Internet gesucht.",
        "text": "Bisher hielt ein Treffer auf der Karte die Suche im Internet auf, auch wenn du ausdrücklich nachprüfen wolltest. Das haben wir behoben.",
    },
    "2026-10-20": {
        "haken": "Frag KIplatz ab heute „What is the capital of Australia?“, und auch alles rund um die Antwort kommt auf Englisch.",
        "text": "Wir haben den Helfer für Linux und Macs mit Apple-Chip fertig: drei Befehle im Terminal, und dein Rechner arbeitet ohne Fenster für die Community mit. Dein PC tritt jetzt mit deinem KIplatz-Konto bei, ganz ohne Code. Und unter jeder Antwort steht, auf welchem PC wirklich nachgeschlagen wurde.",
    },
    "2026-10-19": {
        "haken": "Frag KIplatz ab heute „Wann ist Ostern 2027?“, und die Antwort kommt gleich aus dem Kalender.",
        "text": "Wir haben auch dafür gesorgt, dass dein PC aus dem Lexikon antwortet, während er nebenbei für die Community arbeitet. "
                "Und ein großer Download im Hintergrund hält deine eigene Frage nicht mehr auf.",
    },
    "2026-10-18": {
        "haken": "Frag KIplatz ab heute „Wann ist heuer der erste Advent?“, und es rechnet dir das Datum gleich selbst aus, ohne zu raten.",
        "text": "Wir haben KIplatz dazu die Feiertage der ganzen Welt beigebracht. Bei Einreise, Visum und Ämtern schaut es jetzt in jedem "
                "Land aktuell bei den Behörden nach. Auf Englisch merkt es sich Sätze, liest den Morgenbericht und klingt natürlicher.",
    },
    "2026-10-17": {
        "haken": "Frag KIplatz ab heute „Was soll ich tun, wenn der Abfluss verstopft ist?“, und du bekommst gleich eine Antwort statt Gegenfragen.",
        "text": "Wir haben auch die Antworten auf Alltagsfragen schneller gemacht, weil weniger neu geschrieben wird. "
                "Und wer auf Englisch wissen will, was Feber heißt, bekommt jetzt ebenfalls eine Antwort.",
    },
}


_EN: dict | None = None


def englisch(satz: str) -> str:
    global _EN
    if _EN is None:
        import json
        from pathlib import Path
        try:
            _EN = json.loads((Path(__file__).resolve().with_name("neuerungen_en.json")).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _EN = {}
    return _EN.get(satz, satz)


def fuer(bau: str) -> list[str]:
    return list(NEUERUNGEN.get(bau, []))


def seit(gesehen: str | None, aktuell: str, *, hoechstens: int = 8) -> list[str]:
    if gesehen == aktuell:
        return []
    saetze: list[str] = []
    for bau in sorted(NEUERUNGEN, reverse=True):
        if bau > aktuell or (gesehen and bau <= gesehen):
            continue
        saetze.extend(NEUERUNGEN[bau])
        if not gesehen:
            break
    return saetze[:hoechstens]
