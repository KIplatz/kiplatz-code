# Contributing to KIplatz

Great that you want to join in. This repository is an **export**: we build in our own repository, run the checks there, and publish the result here with every build. What happens with your contribution:

| You want to … | Then go here |
|---|---|
| report a bug, bring in an idea, suggest a source | [Workshop, project KIplatz/mitbauen](https://werkstatt.kiplatz.at/KIplatz/mitbauen?lang=en-US), with a template for every report |
| propose a code change | open a pull request here **or** attach a patch in the workshop. We read it, check it for security and licence, rebuild it in our repository, and it comes back here with the next build. Your name goes into the release notes if you tick "thank me by name" |
| write, share or improve a skill | [Forum (Platzl), category Skills](https://forum.kiplatz.at/?tl=en) |
| ask a question or talk with others | [Forum (Platzl)](https://forum.kiplatz.at/?tl=en) |
| report a security hole | confidentially, see [SECURITY.md](SECURITY.md) |

One account works for the forum, the workshop and the program: [create one for free](https://werkstatt.kiplatz.at/user/sign_up?lang=en-US). Most conversations are in German; English is welcome everywhere.

## What a good code change looks like

- One change per pull request, with a sentence on what it fixes and how you tested it.
- Run the checks before you send it: `python3 node-agent/entwickeln.py check` (on Windows `python` instead of `python3`).
- No new network connections without a word about them: everything the program sends anywhere is listed under "What leaves my computer", and that list has to stay true.
- No third-party code without its licence; see [NOTICE.md](NOTICE.md).
- Sign your commits off with `git commit -s` (Developer Certificate of Origin). That is a one-line statement that you wrote the change or have the right to submit it under the AGPL. No contributor agreement, no paperwork.

## Set up in 10 minutes

On Linux (tested on Ubuntu) and on a Mac:

```bash
git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code
python3 node-agent/entwickeln.py setup
python3 node-agent/entwickeln.py test
```

On Windows the same with `python` instead of `python3`. `setup` creates `.venv` next to `node-agent/`, installs the packages from `node-agent/requirements-dev.txt` and, if Node.js is there, esbuild for the tests (`npm ci --ignore-scripts` in `app/`). Nothing is installed system-wide and nothing needs administrator rights. `build` makes the program zip on Windows without our signature; `check` runs what has to be green before a pull request.

## How we treat each other

The [house rules](https://kiplatz.com/house-rules/) apply here as everywhere at KIplatz: stay friendly, welcome newcomers, stay on topic, stay honest and keep other people's data private.

---

## Auf Deutsch: Mitbauen bei KIplatz

Schön, dass du mitmachen willst. Dieses Repository ist ein **Export**: Wir bauen in unserem eigenen Repository, lassen dort die Prüfungen laufen und veröffentlichen das Ergebnis mit jedem Bau hier. Was mit deinem Beitrag passiert:

| Du willst … | Dann hier |
|---|---|
| einen Fehler melden, eine Idee einbringen, eine Quelle vorschlagen | [Werkstatt, Projekt KIplatz/mitbauen](https://werkstatt.kiplatz.at/KIplatz/mitbauen) mit Vorlagen für jede Meldung |
| eine Code-Änderung vorschlagen | hier einen Pull Request öffnen **oder** einen Patch in der Werkstatt anhängen. Wir lesen ihn, prüfen Sicherheit und Lizenz, bauen ihn in unserem Repository nach, und er kommt mit dem nächsten Bau hierher zurück. Dein Name steht in den Neuerungen, wenn du „Danke mit Namen“ ankreuzt |
| einen Skill schreiben, teilen oder verbessern | [Platzl, Bereich Skills](https://forum.kiplatz.at/) |
| eine Frage stellen oder mitreden | [Platzl](https://forum.kiplatz.at/) |
| eine Sicherheitslücke melden | vertraulich, siehe [SECURITY.md](SECURITY.md) |

Ein Konto gilt für Platzl, Werkstatt und Programm: [kostenlos anlegen](https://werkstatt.kiplatz.at/user/sign_up).

**So sieht eine gute Code-Änderung aus:** eine Änderung je Pull Request mit einem Satz, was sie behebt und wie du sie geprüft hast; vorher `python3 node-agent/entwickeln.py pruefen` (unter Windows `python` statt `python3`); keine neue Internetverbindung ohne ein Wort dazu (die Liste „Was verlässt meinen Rechner“ muss wahr bleiben); kein fremder Code ohne Lizenz; Commits mit `git commit -s` unterschreiben (Developer Certificate of Origin, eine Zeile, kein Vertrag).

**In 10 Minuten startklar** (Linux, getestet auf Ubuntu, und Mac; unter Windows `python` statt `python3`):

```bash
git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code
python3 node-agent/entwickeln.py einrichten
python3 node-agent/entwickeln.py tests
```

`einrichten` legt `.venv` neben `node-agent/` an, holt die Pakete aus `node-agent/requirements-dev.txt` und, wenn Node.js da ist, esbuild für die Tests (`npm ci --ignore-scripts` in `app/`). Nichts wird für das ganze System installiert, nichts braucht Administratorrechte. `bauen` macht unter Windows das Programm-ZIP ohne unsere Unterschrift; `pruefen` lässt laufen, was vor einem Pull Request grün sein muss.

Wie wir miteinander umgehen, steht in der [Platzordnung](https://kiplatz.at/hausordnung/).
