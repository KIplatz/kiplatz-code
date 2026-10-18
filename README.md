# KIplatz: the program and the app, open source

**KIplatz is a free AI from Austria that runs on its community's PCs instead of in a data centre.** This repository holds the source code of the two things members install: the Windows program (`node-agent/`) and the app for phones and browsers (`app/`). Both are free software under the [GNU AGPL 3.0 or later](LICENSE).

English · [Deutsch](README.de.md)

[kiplatz.com](https://kiplatz.com/) · [Get the program](https://kiplatz.com/share-computing/) · [The app](https://kiplatz.at/app/) · [Forum (Platzl)](https://forum.kiplatz.at/?tl=en) · [Workshop](https://werkstatt.kiplatz.at/KIplatz/mitbauen?lang=en-US) · [What never happens](https://kiplatz.com/what-never-happens/)

**Try it without installing anything:** ask a question on [kiplatz.com](https://kiplatz.com/).

## Windows 11, or the app in the browser

The program runs on Windows 11. On a Mac, on Linux or on a phone you use the app in the browser at [kiplatz.at/app](https://kiplatz.at/app/). The program picks the model that fits your PC: Ministral 3 with 14B, 8B or 3B parameters, the biggest one that fits into the free memory of your graphics card. Without a suitable graphics card the processor does the work (the 8B model from 16 GB of memory, otherwise the 3B), and if your PC is too weak for that, a free PC of the community answers.

## What is in here

- The Windows program (`node-agent/`): the window, the local AI runtime, the knowledge store, the home network, the connection to kiplatz.at.
- The app for Android, iOS and the browser (`app/`; `app/www/` is exactly what runs at kiplatz.at/app).
- The build scripts, so that you can build the same package we ship, and the tests that run on the program alone.

The program and the app connect to kiplatz.at. The community's service runs on a server in Vienna, in the EU, under European data protection law. What you can do with this code: read every line that runs on your computer, check what leaves it, build the program yourself, and improve it with us.

## Read what runs on your PC

Everything the program sends anywhere is listed in the window under "What leaves my computer", and the same list is at [kiplatz.com/what-never-happens](https://kiplatz.com/what-never-happens/). Good places to start reading:

- `node-agent/app_web.py`: the program's side of the window; every button ends up here.
- `node-agent/ki_laufzeit.py`: how the local AI runtime (Ollama, llama.cpp) is started and watched.
- `node-agent/wissen.py`: the knowledge store on your disk and how pages are read.
- `node-agent/rechenarbeit.py`: what your PC does for the community when it is idle.
- `node-agent/app_install.py`: how updates are verified (the public keys are in the file).
- `app/www/js/start.js`: the app.

## Build the program yourself

You need Windows 11, Python 3.12 or newer on your PATH, and an internet connection (the script downloads the embeddable Python from python.org and the packages from PyPI, each checked against a fixed SHA-256).

```powershell
powershell -ExecutionPolicy Bypass -File node-agent\build_app_zip.ps1 -OhneUnterschrift
```

The result is `node-agent\dist\CommunityAI.zip`. `-OhneUnterschrift` means "without signature": your package runs as a program of its own; updates come signed from kiplatz.at. The checksums of our packages are published next to every download, so you can compare a package you built with the one we ship.

To run from source instead of building:

```powershell
pip install -r node-agent\requirements-dev.txt
python node-agent\app_web.py
```

This starts the program in test mode with its own data folder. The AI runtime and a model are fetched from kiplatz.at at first start.

## The app

`app/www/` is a plain web app without a build step; open `app/www/index.html` through any local web server, or run the mock server that stands in for kiplatz.at during development:

```powershell
cd app
npm ci
npm run entwickeln
```

The native shells for Android and iOS use Capacitor (`npm run sync`, then Android Studio or Xcode). `app/werkzeuge/android_paket.ps1` reads the store signing keys from environment variables.

## Tests

```powershell
python -m pytest node-agent\tests -q
```

The tests in this repository run on the program alone, without the server. They are the same tests we run before every release.

## Contributing

Pull requests and ideas are welcome. This repository is an export from the place where we build: we read every suggestion, rebuild it there, and it comes back here with the next build, with your name in the release notes if you like. How to report a bug, bring in an idea or improve the code: [CONTRIBUTING.md](CONTRIBUTING.md). Security holes: [SECURITY.md](SECURITY.md), confidentially. The name and the logo are not part of the licence: [TRADEMARK.md](TRADEMARK.md). Third-party components: [NOTICE.md](NOTICE.md).

## Release notes

What changed in each build is at [kiplatz.com/new](https://kiplatz.com/new/) and in the release notes of the [KIplatz showcase repository](https://github.com/KIplatz/kiplatz). Each build here is tagged with its build number (for example `2026-10-13c`), the same number the program shows under "About KIplatz".
