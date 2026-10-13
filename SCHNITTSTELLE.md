# Andere Programme dürfen Unser Modell fragen

Stand 18.09.2026 (Paket 6b). Für Bastler und Programmierer, die Unser Modell aus ihren eigenen Werkzeugen heraus benutzen wollen.

## Was das ist

Das Programm kann auf Wunsch eine kleine Tür öffnen, nur auf dem eigenen Gerät. Andere Programme auf demselben Rechner reden durch diese Tür mit Unser Modell, und zwar im Format von OpenAI. Das ist das Format, das Open WebUI, Jan, Continue (VS Code), LibreChat, das Python-Paket `openai` und die meisten anderen Werkzeuge ohnehin sprechen. Man trägt Adresse und Schlüssel einmal ein, fertig.

Die Tür ist standardmäßig zu. Einschalten geht im Programm unter „Einstellungen“, Karte „Andere Programme dürfen Unser Modell fragen“. Dort stehen dann Adresse, Modellname und Schlüssel.

## Was gilt

- Adresse: `http://127.0.0.1:8470/v1`. Nur dieses Gerät kommt hin; aus dem Netz ist die Tür nicht erreichbar, auch nicht aus dem Heimnetz. Anfragen mit einem fremden Host-Kopf werden abgewiesen (Schutz vor Tricks über den Browser).
- Schlüssel: steht im Programm, beginnt mit `cai-`. Er muss in jeder Anfrage als `Authorization: Bearer <Schlüssel>` mitkommen. „Neuen Schlüssel machen“ macht den alten sofort ungültig.
- Modellname: `unser-modell`. Was dahinter läuft (3B, 8B oder 14B, am Gerät oder im Heimnetz), entscheidet das Programm wie bei einer Frage im Fenster.
- Jede Frage geht durch die Hausordnung der Community, so wie im Fenster. Was die Wortliste erwischt, kommt nie beim Modell an.
- Jede Frage bekommt dasselbe wie im Fenster: das Wissen der Community und das eigene Wissen am Gerät, bei Bedarf Wetter, Schlagzeilen oder eine Suche. Die Anweisung des aufrufenden Programms (`role: system`) wird als Zusatz mitgegeben, gilt aber nur, soweit sie der Hausordnung nicht widerspricht.
- Credits: eine Anfrage zählt wie eine Frage im Fenster (Admin: unbegrenzt). Die Community wird über diese Tür nie gefragt; es antwortet immer das eigene Gerät oder das gekoppelte Gerät im Heimnetz.
- Ist die KI aus, schaltet die erste Anfrage sie ein; das dauert beim ersten Mal einige Sekunden, das aufrufende Programm wartet solange.
- Es wird eine Anfrage nach der anderen beantwortet. Ein zweites Programm wartet, bis das erste fertig ist.
- Grenzen je Anfrage: 40 Nachrichten, zusammen 60 000 Zeichen, 256 kB, höchstens 1500 Wortstücke Antwort. Bilder werden über diese Tür nicht angenommen (dafür gibt es 🖼 im Fenster).
- Was durch die Tür geht, wird nicht im Programm als Gespräch gespeichert. Das Protokoll am Gerät vermerkt nur, dass geantwortet wurde und wie lange es gedauert hat, nie den Text.

## Die zwei Wege

`GET /v1/models` gibt genau ein Modell zurück (`unser-modell`).

`POST /v1/chat/completions` nimmt eine Anfrage wie diese:

```json
{
  "model": "unser-modell",
  "messages": [
    {"role": "system", "content": "Antworte in einem Satz."},
    {"role": "user", "content": "Wie wird das Wetter morgen in Linz?"}
  ],
  "stream": false,
  "max_tokens": 300,
  "temperature": 0.3
}
```

Die Antwort hat die gewohnte Form (`choices[0].message.content`, `usage`). Mit `"stream": true` kommen die Wortstücke einzeln als Server-Sent Events (`data: {...}`, am Ende `data: [DONE]`), genau wie bei OpenAI.

Fehler kommen als `{"error": {"message": "...", "type": "..."}}`: 401 ohne oder mit falschem Schlüssel, 403 bei fremdem Host, 400 bei einer Anfrage, die nicht passt (auch bei einem Verstoß gegen die Hausordnung), 503, wenn Unser Modell gerade nicht antworten kann.

## Beispiele

Mit curl:

```bash
curl http://127.0.0.1:8470/v1/chat/completions -H "Authorization: Bearer cai-DEIN-SCHLUESSEL" -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Was ist das Community AI Network?\"}]}"
```

Mit Python und dem Paket `openai`:

```python
from openai import OpenAI
ki = OpenAI(base_url="http://127.0.0.1:8470/v1", api_key="cai-DEIN-SCHLUESSEL")
antwort = ki.chat.completions.create(model="unser-modell", messages=[{"role": "user", "content": "Was ist das Community AI Network?"}])
print(antwort.choices[0].message.content)
```

Open WebUI: Einstellungen → Verbindungen → OpenAI-API: Adresse `http://127.0.0.1:8470/v1`, Schlüssel aus dem Programm. Danach erscheint `unser-modell` in der Modellwahl.

Jan: Settings → Model Providers → OpenAI-kompatibel, dieselben zwei Angaben.

Continue (VS Code): in `config.yaml` einen Eintrag mit `provider: openai`, `apiBase: http://127.0.0.1:8470/v1`, `model: unser-modell` und dem Schlüssel.

LibreChat: einen eigenen Endpunkt mit `baseURL: http://127.0.0.1:8470/v1` in der `librechat.yaml`.

## Programme in Docker auf demselben PC

Seit Bau 2026-10-04c. Ein Programm in Docker Desktop (zum Beispiel Open WebUI) erreicht den PC über den Namen `host.docker.internal`. Dafür gibt es unter „Einstellungen“ in derselben Karte einen eigenen Schalter: „Auch Programme in Docker auf diesem PC dürfen fragen“. Er ist aus, bis man ihn einschaltet.

- Adresse im Programm in Docker: `http://host.docker.internal:8470/v1`, Schlüssel und Modellname wie oben.
- Open WebUI so starten, wie es seine Anleitung vorschlägt (`docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --name open-webui ghcr.io/open-webui/open-webui:main`), dann unter Einstellungen → Verbindungen → OpenAI-API die Adresse oben und den Schlüssel eintragen.
- Open WebUI schickt zu jeder Frage 3 Nebenaufträge mit (Titel, Folgefragen, Schlagworte), und jeder zählt wie eine Frage. Wer das nicht will, startet Open WebUI zusätzlich mit `-e ENABLE_TITLE_GENERATION=False -e ENABLE_FOLLOW_UP_GENERATION=False -e ENABLE_TAGS_GENERATION=False` oder schaltet die drei unter Admin → Einstellungen → Oberfläche aus (gemessen am 04.10.2026 mit Open WebUI 0.11.4: 4 Anfragen je Frage, mit den drei Schaltern 1).
- Ist der Schalter aus, antwortet die Tür mit 403 und sagt, welcher Schalter fehlt.
- Die Tür lauscht weiter nur auf 127.0.0.1. Docker Desktop reicht den Aufruf aus dem Container selbst an diese Adresse weiter (gemessen am 04.10.2026 mit Docker Desktop 4.93 unter Windows 11 und WSL 2). Geräte im Heimnetz und andere Rechner kommen auch mit eingeschaltetem Schalter nicht hinein, und jede Anfrage, die nicht vom Gerät selbst kommt, wird abgewiesen.
- Docker ohne Docker Desktop (etwa Docker direkt in einer WSL-Linux-Umgebung) ist nicht geprüft. Vermutlich kommt die Anfrage dort über das Netz von WSL an und erreicht die Tür nicht, weil sie nur auf 127.0.0.1 lauscht.

Ob eine Anfrage angekommen ist, sieht man im Programm unter „Einstellungen“: Dort steht, wie viele Anfragen in dieser Sitzung durch die Tür gegangen sind.

## Was nicht geht, und warum

- Die Tür ist nicht aus dem Netz erreichbar, auch nicht mit Absicht. Wer ein zweites Gerät versorgen will, nimmt „Unser Modell im Heimnetz“ (verschlüsselt, mit Kopplungscode).
- Kein CORS: Eine Website im Browser bekommt hier keine Antwort. Das ist Absicht; sonst könnte jede besuchte Seite das Modell am Gerät befragen.
- Kein `/v1/embeddings`, kein `/v1/completions` (die alte Form). Wenn ein Werkzeug das braucht, bitte als Wunsch melden.

Quelltext: `node-agent/schnittstelle.py`, Anbindung in `node-agent/app_web.py` (`_schnittstelle_antwort`), Tests in `node-agent/tests/test_schnittstelle.py`.
