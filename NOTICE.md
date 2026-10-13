# Third-party components

KIplatz is licensed under the GNU AGPL 3.0 or later (see `LICENSE`). It is built on and talks to the following components, each under its own licence. Nothing in this list is part of the KIplatz licence; the names and logos of these projects belong to their owners.

## Program (Windows, `node-agent/`)

| Component | Licence | Used for |
|---|---|---|
| Python (embeddable package from python.org) | PSF License | the runtime the program ships with |
| psutil | BSD-3-Clause | memory, CPU and process figures |
| segno | BSD-3-Clause | QR codes for pairing a phone |
| pypdf | BSD-3-Clause | reading PDF attachments |
| cryptography | Apache-2.0 / BSD-3-Clause | signatures, keys, encryption |
| truststore | MIT | the Windows certificate store for HTTPS |
| pywin32 | PSF-style | Windows services and DPAPI |
| pywebview, pythonnet, clr-loader, bottle, proxy-tools | BSD-3-Clause, MIT, MIT, MIT, MIT | the program window |
| cffi, pycparser, typing-extensions | MIT, BSD-3-Clause, PSF | dependencies of the above |
| pytest (development only) | MIT | the test suite |
| Ollama, llama.cpp, whisper.cpp | MIT (`node-agent/lizenzen/OLLAMA_LICENSE`) | running language models locally |

The language models themselves are downloaded from kiplatz.at at first start; each model carries its own licence, shown in the program under "Models".

## App (`app/`)

| Component | Licence | Used for |
|---|---|---|
| Capacitor (core, cli, android, ios, app, haptics, share) | MIT | the native shell for Android and iOS |
| @aparajita/capacitor-secure-storage | MIT | keys in the device's secure storage |
| jsQR (`app/www/js/vendor/jsQR.js`) | Apache-2.0 (`app/www/js/vendor/jsQR-LICENSE.txt`) | reading QR codes with the camera |
| esbuild (development only) | MIT | bundling |
| Atkinson Hyperlegible (font) | SIL Open Font License 1.1 (`app/www/schrift/OFL.txt`) | the app's typeface |
| transformers.js, tesseract.js, pdf.js | Apache-2.0 | voice input, text recognition and PDFs in the browser, fetched from kiplatz.at (`app/ki-helfer.json`) |
| onnxruntime-web | MIT | running small models in the browser |

## Data sources the program reads for answers

Wikipedia (CC BY-SA 4.0), OpenStreetMap (ODbL), Open-Meteo (CC BY 4.0), the Austrian legal information system RIS (CC BY 4.0), the European Central Bank (reference rates), public news feeds and TheSportsDB. Every answer names its sources. The full list of what leaves your computer is in the program under "What leaves my computer" and at kiplatz.com/what-never-happens/.
