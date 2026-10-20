# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ZIEL = HIER / "container"
sys.path.insert(0, str(HIER))

BASIS = "debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f"
APT = ("ca-certificates", "curl", "openssl", "libgomp1", "libvulkan1", "mesa-vulkan-drivers", "vulkan-tools")
PAKET = "KIplatz-Helfer-linux-x64.tar.gz"
UID = 10001
KOPF = "# Erzeugt von node-agent/helfer_container.py. Nicht von Hand ändern: Skript ändern, laufen lassen, committen."
_ED25519_DER = bytes.fromhex("302a300506032b6570032100")


def pem(pubkey_b64: str) -> list[str]:
    roh = base64.b64decode(pubkey_b64)
    if len(roh) != 32:
        raise ValueError("ein Ed25519-Schlüssel hat 32 Bytes")
    return ["-----BEGIN PUBLIC KEY-----", base64.b64encode(_ED25519_DER + roh).decode("ascii"), "-----END PUBLIC KEY-----"]


def schluessel() -> list[str]:
    import app_install
    return [app_install.UPDATE_PUBKEY_B64, app_install.UPDATE_PUBKEY_RETTUNG_B64]


def pruef_skript(schluessel_b64: list[str], datei: str, sig: str) -> str:
    zeilen = ["set -eu", f"tr -d '\\r' < {sig} | cut -d' ' -f1 | head -n 1 | base64 -d > /tmp/kiplatz.sig.bin", "ok=0"]
    for i, k in enumerate(schluessel_b64, 1):
        zeilen.append(f"printf '%s\\n' {' '.join(repr(z) for z in pem(k))} > /tmp/kiplatz-{i}.pem")
    namen = " ".join(f"/tmp/kiplatz-{i}.pem" for i in range(1, len(schluessel_b64) + 1))
    zeilen.append(f"for k in {namen}; do if openssl pkeyutl -verify -pubin -inkey $k -rawin -in {datei} -sigfile /tmp/kiplatz.sig.bin >/dev/null 2>&1; "
                  "then ok=1; break; fi; done")
    zeilen.append(f"rm -f /tmp/kiplatz.sig.bin {namen}")
    zeilen.append('if [ "$ok" != 1 ]; then echo "KIplatz: die Unterschrift des Helfer-Pakets stimmt nicht, nichts wird gebaut" >&2; exit 1; fi')
    return "\n".join(zeilen)


def dockerfile() -> str:
    pruefen = pruef_skript(schluessel(), PAKET, PAKET + ".sig").split("\n")
    return "\n".join([
        KOPF,
        "# Der KIplatz-Helfer im Container (Linux x64). Das Abbild entsteht bei dir: Debian mit fester Prüfsumme, dazu das Helfer-Paket",
        "# von kiplatz.at, im Bau mit unserer Unterschrift (Ed25519) geprüft. Kein Geheimnis im Abbild, der Helfer läuft nie als root.",
        f"FROM {BASIS}",
        "ARG HELFER_QUELLE=https://kiplatz.at/download",
        "RUN apt-get update \\",
        f" && apt-get install -y --no-install-recommends {' '.join(APT)} \\",
        " && rm -rf /var/lib/apt/lists/* \\",
        f" && useradd --create-home --uid {UID} --user-group --shell /usr/sbin/nologin kiplatz \\",
        " && mkdir -p /home/kiplatz/helfer /daten && chown kiplatz:kiplatz /home/kiplatz/helfer /daten",
        "# die kleine Prüfsummen-Datei ändert sich mit jedem Bau; so holt `docker compose build` ein neues Paket, sobald es eines gibt",
        f"ADD ${{HELFER_QUELLE}}/{PAKET}.sha256 /tmp/helfer/{PAKET}.sha256",
        "# Holen, Prüfen (Prüfsumme und Unterschrift) und Auspacken in einem Schritt: das Paket bleibt nicht als Schicht im Abbild liegen",
        "RUN set -eu; cd /tmp/helfer; \\",
        f"    curl -fsSL --proto '=https' --tlsv1.2 -o {PAKET} \"${{HELFER_QUELLE}}/{PAKET}\"; \\",
        f"    curl -fsSL --proto '=https' --tlsv1.2 -o {PAKET}.sig \"${{HELFER_QUELLE}}/{PAKET}.sig\"; \\",
        f"    tr -d '\\r' < {PAKET}.sha256 | sha256sum -c -; \\",
        "    " + "; \\\n    ".join(z for z in pruefen) + "; \\",
        f"    tar -xzf {PAKET} -C /home/kiplatz/helfer --no-same-owner; \\",
        "    chown -R kiplatz:kiplatz /home/kiplatz/helfer; \\",
        "    cd /; rm -rf /tmp/helfer",
        "ENV KIPLATZ_CONTAINER=1 \\",
        "    HOME=/home/kiplatz \\",
        "    XDG_DATA_HOME=/daten/data \\",
        "    XDG_STATE_HOME=/daten/state \\",
        "    XDG_CONFIG_HOME=/daten/config \\",
        "    PATH=/home/kiplatz/helfer/kiplatz-helfer:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        f"USER {UID}:{UID}",
        "WORKDIR /home/kiplatz",
        "VOLUME /daten",
        "# gesund, solange der laufende Helfer jede Minute seinen Stand schreibt (kiplatz-helfer status liest ihn)",
        "HEALTHCHECK --interval=2m --timeout=10s --start-period=10m CMD find /daten/data/kiplatz/daten/helfer-stand.json -mmin -3 | grep -q .",
        'ENTRYPOINT ["/home/kiplatz/helfer/kiplatz-helfer/kiplatz-helfer"]',
        'CMD ["start"]',
        "",
    ])


def compose() -> str:
    return "\n".join([
        KOPF,
        "# Der KIplatz-Helfer mit Docker Compose (Linux x64):",
        "#   docker compose build                       das Abbild bei dir bauen (prüft unsere Unterschrift)",
        "#   docker compose run --rm helfer einrichten  mit dem KIplatz-Konto beitreten (die Adresse am Handy öffnen)",
        "#   docker compose up -d                       starten; startet nach jedem Neustart des Rechners von selbst",
        "#   docker compose exec helfer kiplatz-helfer status",
        "# Mit Grafikkarte: zusätzlich -f compose.nvidia.yaml (NVIDIA) oder -f compose.dri.yaml (AMD, Intel).",
        "name: kiplatz",
        "services:",
        "  helfer:",
        "    build: .",
        "    image: kiplatz-helfer:lokal",
        "    platform: linux/amd64",
        "    restart: unless-stopped",
        "    init: true",
        "    environment:",
        "      LANG: ${LANG:-C.UTF-8}   # Deutsch, wenn dein System Deutsch spricht",
        "    volumes:",
        "      - daten:/daten",
        "      # wie ohne Container: Hintergrundarbeit ruht, solange jemand an diesem Rechner angemeldet ist. Gelesen wird nur, ob eine",
        "      # Sitzung aktiv ist (logind), nie ein Name. Ohne systemd bleibt der Ordner leer, und der Helfer arbeitet wie auf einem Server.",
        "      - /run/systemd/sessions:/run/systemd/sessions:ro",
        "    cap_drop: [ALL]",
        "    security_opt: [\"no-new-privileges:true\"]",
        "    stop_grace_period: 30s",
        "volumes:",
        "  daten:",
        "",
    ])


def compose_nvidia() -> str:
    return "\n".join([
        KOPF,
        "# NVIDIA: braucht das NVIDIA Container Toolkit am Rechner. docker compose -f compose.yaml -f compose.nvidia.yaml up -d",
        "services:",
        "  helfer:",
        "    environment:",
        "      NVIDIA_DRIVER_CAPABILITIES: compute,utility,graphics   # graphics: llama.cpp rechnet über Vulkan",
        "    deploy:",
        "      resources:",
        "        reservations:",
        "          devices:",
        "            - driver: nvidia",
        "              count: all",
        "              capabilities: [gpu]",
        "",
    ])


def compose_dri() -> str:
    return "\n".join([
        KOPF,
        "# AMD und Intel über Vulkan: docker compose -f compose.yaml -f compose.dri.yaml up -d",
        "# RENDER_GID ist die Nummer der Gruppe render am Rechner: getent group render | cut -d: -f3",
        "services:",
        "  helfer:",
        "    devices:",
        "      - /dev/dri:/dev/dri",
        "    group_add:",
        "      - \"${RENDER_GID:?RENDER_GID fehlt: getent group render | cut -d: -f3}\"",
        "",
    ])


def readme() -> str:
    return "\n".join([
        "# KIplatz helper in a container",
        "",
        "English · [Deutsch](#auf-deutsch)",
        "",
        "For Linux x64 with Docker. The image is built on your machine from Debian (pinned by checksum) and our helper package from kiplatz.at,"
        " whose Ed25519 signature is checked during the build. Nothing secret is in it, and the helper never runs as root.",
        "",
        "```bash",
        "git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code/node-agent/container",
        "docker compose run --rm helfer einrichten   # sign in with your KIplatz account (open the address on your phone)",
        "docker compose up -d",
        "```",
        "",
        "`docker compose exec helfer kiplatz-helfer status` shows what it is doing. With a graphics card add `-f compose.nvidia.yaml` (NVIDIA,"
        " needs the NVIDIA Container Toolkit) or `-f compose.dri.yaml` (AMD, Intel) to both compose commands. Its data stays in the volume"
        " `kiplatz_daten`; updates arrive signed, as without a container. `docker compose down` stops it; `docker compose down -v` also removes its data.",
        "",
        "## Auf Deutsch",
        "",
        "Für Linux x64 mit Docker. Das Abbild entsteht bei dir aus Debian (mit fester Prüfsumme) und unserem Helfer-Paket von kiplatz.at, dessen"
        " Ed25519-Unterschrift der Bau prüft. Nichts Geheimes ist darin, und der Helfer läuft nie als root.",
        "",
        "```bash",
        "git clone https://github.com/KIplatz/kiplatz-code && cd kiplatz-code/node-agent/container",
        "docker compose run --rm helfer einrichten   # mit dem KIplatz-Konto anmelden (die Adresse am Handy öffnen)",
        "docker compose up -d",
        "```",
        "",
        "`docker compose exec helfer kiplatz-helfer status` zeigt, was er gerade tut. Mit Grafikkarte kommt bei beiden compose-Befehlen"
        " `-f compose.nvidia.yaml` (NVIDIA, braucht das NVIDIA Container Toolkit) oder `-f compose.dri.yaml` (AMD, Intel) dazu. Seine Daten"
        " bleiben im Volume `kiplatz_daten`; Updates kommen unterschrieben wie ohne Container. `docker compose down` hält ihn an,"
        " `docker compose down -v` löscht auch seine Daten.",
        "",
    ])


def dateien() -> dict[str, str]:
    return {"Dockerfile": dockerfile(), "compose.yaml": compose(), "compose.nvidia.yaml": compose_nvidia(), "compose.dri.yaml": compose_dri(),
            "README.md": readme()}


def abweichungen(ordner: Path = ZIEL) -> list[str]:
    return [n for n, inhalt in dateien().items()
            if not (ordner / n).is_file() or (ordner / n).read_bytes().replace(b"\r\n", b"\n").decode("utf-8") != inhalt]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 3 and args[0] == "--pruef-skript":
        print(pruef_skript(schluessel(), args[1], args[2]))
        return 0
    if args == ["--pruefen"]:
        falsch = abweichungen()
        for n in falsch:
            print(f"{ZIEL / n}: anders als erzeugt; python node-agent/helfer_container.py")
        return 1 if falsch else 0
    ZIEL.mkdir(exist_ok=True)
    for n, inhalt in dateien().items():
        with open(ZIEL / n, "w", encoding="utf-8", newline="\n") as f:
            f.write(inhalt)
    print(f"{len(dateien())} Dateien in {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
