# KIplatz helper in a container

English · [Deutsch](#auf-deutsch)

For Linux x64 with Docker. The image is built on your machine from Debian (pinned by checksum) and our helper package from kiplatz.at, whose Ed25519 signature is checked during the build. Nothing secret is in it, and the helper never runs as root.

```bash
git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code/node-agent/container
docker compose run --rm helfer einrichten   # sign in with your KIplatz account (open the address on your phone)
docker compose up -d
```

`docker compose exec helfer kiplatz-helfer status` shows what it is doing. With a graphics card add `-f compose.nvidia.yaml` (NVIDIA, needs the NVIDIA Container Toolkit) or `-f compose.dri.yaml` (AMD, Intel) to both compose commands. Its data stays in the volume `kiplatz_daten`; updates arrive signed, as without a container. `docker compose down` stops it; `docker compose down -v` also removes its data.

## Auf Deutsch

Für Linux x64 mit Docker. Das Abbild entsteht bei dir aus Debian (mit fester Prüfsumme) und unserem Helfer-Paket von kiplatz.at, dessen Ed25519-Unterschrift der Bau prüft. Nichts Geheimes ist darin, und der Helfer läuft nie als root.

```bash
git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code/node-agent/container
docker compose run --rm helfer einrichten   # mit dem KIplatz-Konto anmelden (die Adresse am Handy öffnen)
docker compose up -d
```

`docker compose exec helfer kiplatz-helfer status` zeigt, was er gerade tut. Mit Grafikkarte kommt bei beiden compose-Befehlen `-f compose.nvidia.yaml` (NVIDIA, braucht das NVIDIA Container Toolkit) oder `-f compose.dri.yaml` (AMD, Intel) dazu. Seine Daten bleiben im Volume `kiplatz_daten`; Updates kommen unterschrieben wie ohne Container. `docker compose down` hält ihn an, `docker compose down -v` löscht auch seine Daten.
