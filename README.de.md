# KIplatz: das Programm und die App, quelloffen

**KIplatz ist eine kostenlose KI aus Österreich, die auf den PCs ihrer Community läuft statt in einem Rechenzentrum.** In diesem Repository liegt der Quelltext der zwei Dinge, die Mitglieder installieren: das Windows-Programm (`node-agent/`) und die App für Handy und Browser (`app/`). Beides ist freie Software unter der [GNU AGPL 3.0 oder später](LICENSE).

[English](README.md) · Deutsch

[kiplatz.at](https://kiplatz.at/) · [Programm holen](https://kiplatz.at/rechenkraft-teilen/) · [Die App](https://kiplatz.at/app/) · [Platzl (Forum)](https://forum.kiplatz.at/) · [Werkstatt](https://werkstatt.kiplatz.at/KIplatz/mitbauen) · [Was nie passiert](https://kiplatz.at/was-nie-passiert/)

**Ohne Installation ausprobieren:** Stell auf [kiplatz.at](https://kiplatz.at/) eine Frage.

## Windows 11 oder die App im Browser

Das Programm läuft auf Windows 11. Auf dem Mac, unter Linux oder am Handy nimmst du die App im Browser unter [kiplatz.at/app](https://kiplatz.at/app/). Das Programm nimmt das Modell, das zu deinem PC passt. Das ist Ministral 3 mit 14, 8 oder 3 Milliarden Parametern, jeweils das größte, das in den freien Speicher der Grafikkarte passt. Ohne passende Grafikkarte arbeitet der Prozessor (ab 16 GB Arbeitsspeicher das 8B-Modell, sonst das 3B). Ist der PC dafür zu schwach, antwortet ein freier PC der Community.

## Was hier liegt

- Das Windows-Programm (`node-agent/`): das Fenster, die KI-Laufzeit am PC, der Wissensspeicher, das Heimnetz, die Verbindung zu kiplatz.at.
- Die App für Android, iOS und den Browser (`app/`; `app/www/` ist genau das, was unter kiplatz.at/app läuft).
- Die Bau-Skripte, damit du dasselbe Paket bauen kannst, das wir ausliefern, und die Tests, die mit dem Programm allein laufen.

Programm und App verbinden sich mit kiplatz.at. Der Dienst der Community läuft auf einem Server in Wien, in der EU, unter europäischem Datenschutz. Was du mit diesem Code kannst: jede Zeile lesen, die auf deinem Rechner läuft, nachsehen, was ihn verlässt, das Programm selbst bauen und es mit uns verbessern.

## Lies, was auf deinem PC läuft

Alles, was das Programm irgendwohin schickt, steht im Fenster unter „Was verlässt meinen Rechner“, dieselbe Liste unter [kiplatz.at/was-nie-passiert](https://kiplatz.at/was-nie-passiert/). Gute Stellen zum Anfangen:

- `node-agent/app_web.py`: die Programmseite des Fensters; jeder Knopf landet hier.
- `node-agent/ki_laufzeit.py`: wie die KI-Laufzeit am PC (Ollama, llama.cpp) gestartet und überwacht wird.
- `node-agent/wissen.py`: der Wissensspeicher auf deiner Platte und wie Seiten gelesen werden.
- `node-agent/rechenarbeit.py`: was dein PC für die Community tut, wenn er nichts zu tun hat.
- `node-agent/app_install.py`: wie Updates geprüft werden (die öffentlichen Schlüssel stehen in der Datei).
- `app/www/js/start.js`: die App.

## Das Programm selbst bauen

Du brauchst Windows 11, Python 3.12 oder neuer im PATH und eine Internetverbindung (das Skript holt das eingebettete Python von python.org und die Pakete von PyPI, jedes gegen eine feste SHA-256 geprüft).

```powershell
powershell -ExecutionPolicy Bypass -File node-agent\build_app_zip.ps1 -OhneUnterschrift
```

Das Ergebnis ist `node-agent\dist\CommunityAI.zip`. „Ohne Unterschrift“ heißt: dein Paket läuft als eigenes Programm; Updates kommen unterschrieben von kiplatz.at. Die Prüfsummen unserer Pakete stehen neben jedem Download, damit du ein selbst gebautes Paket mit dem von uns vergleichen kannst.

Aus dem Quelltext starten, ohne zu bauen:

```powershell
pip install -r node-agent\requirements-dev.txt
python node-agent\app_web.py
```

Das startet es im Testbetrieb mit eigenem Datenordner. KI-Laufzeit und Modell holt es beim ersten Start von kiplatz.at.

## Die App

`app/www/` ist eine gewöhnliche Web-App ohne Bau-Schritt; öffne `app/www/index.html` über einen lokalen Webserver, oder starte den Schein-Server, der bei der Entwicklung für kiplatz.at einspringt:

```powershell
cd app
npm ci
npm run entwickeln
```

Die Hüllen für Android und iOS kommen von Capacitor (`npm run sync`, dann Android Studio oder Xcode). `app/werkzeuge/android_paket.ps1` liest die Schlüssel für die Stores aus Umgebungsvariablen.

## Tests

```powershell
python -m pytest node-agent\tests -q
```

Die Tests hier laufen mit dem Programm allein, ohne Server. Es sind dieselben Tests, die wir vor jeder Auslieferung laufen lassen.

## Mitbauen

Pull Requests und Ideen sind willkommen. Dieses Repository ist ein Export von dem Ort, an dem wir bauen: Wir lesen jeden Vorschlag, bauen ihn dort nach, und er kommt mit dem nächsten Bau hierher zurück, auf Wunsch mit deinem Namen in den Neuerungen. Wie du einen Fehler meldest, eine Idee einbringst oder den Code verbesserst: [CONTRIBUTING.md](CONTRIBUTING.md). Sicherheitslücken: [SECURITY.md](SECURITY.md), vertraulich. Name und Logo gehören nicht zur Lizenz: [TRADEMARK.md](TRADEMARK.md). Fremde Bausteine: [NOTICE.md](NOTICE.md).

## Neuerungen

Was sich mit jedem Bau geändert hat, steht unter [kiplatz.at/neu](https://kiplatz.at/neu/) und in den Neuerungen des [KIplatz-Schaufensters](https://github.com/KIplatz/kiplatz). Jeder Bau hier trägt seine Bau-Nummer als Tag (zum Beispiel `2026-10-13c`), dieselbe Nummer, die das Programm unter „Über KIplatz“ zeigt.
