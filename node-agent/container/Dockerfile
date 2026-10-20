# Erzeugt von node-agent/helfer_container.py. Nicht von Hand ändern: Skript ändern, laufen lassen, committen.
# Der KIplatz-Helfer im Container (Linux x64). Das Abbild entsteht bei dir: Debian mit fester Prüfsumme, dazu das Helfer-Paket
# von kiplatz.at, im Bau mit unserer Unterschrift (Ed25519) geprüft. Kein Geheimnis im Abbild, der Helfer läuft nie als root.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
ARG HELFER_QUELLE=https://kiplatz.at/download
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl openssl libgomp1 libvulkan1 mesa-vulkan-drivers vulkan-tools \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 --user-group --shell /usr/sbin/nologin kiplatz \
 && mkdir -p /home/kiplatz/helfer /daten && chown kiplatz:kiplatz /home/kiplatz/helfer /daten
# die kleine Prüfsummen-Datei ändert sich mit jedem Bau; so holt `docker compose build` ein neues Paket, sobald es eines gibt
ADD ${HELFER_QUELLE}/KIplatz-Helfer-linux-x64.tar.gz.sha256 /tmp/helfer/KIplatz-Helfer-linux-x64.tar.gz.sha256
# Holen, Prüfen (Prüfsumme und Unterschrift) und Auspacken in einem Schritt: das Paket bleibt nicht als Schicht im Abbild liegen
RUN set -eu; cd /tmp/helfer; \
    curl -fsSL --proto '=https' --tlsv1.2 -o KIplatz-Helfer-linux-x64.tar.gz "${HELFER_QUELLE}/KIplatz-Helfer-linux-x64.tar.gz"; \
    curl -fsSL --proto '=https' --tlsv1.2 -o KIplatz-Helfer-linux-x64.tar.gz.sig "${HELFER_QUELLE}/KIplatz-Helfer-linux-x64.tar.gz.sig"; \
    tr -d '\r' < KIplatz-Helfer-linux-x64.tar.gz.sha256 | sha256sum -c -; \
    set -eu; \
    tr -d '\r' < KIplatz-Helfer-linux-x64.tar.gz.sig | cut -d' ' -f1 | head -n 1 | base64 -d > /tmp/kiplatz.sig.bin; \
    ok=0; \
    printf '%s\n' '-----BEGIN PUBLIC KEY-----' 'MCowBQYDK2VwAyEAMq0a5sAEHp9ba/kUL/F69I67SooKawCBS7p1mtmKWNw=' '-----END PUBLIC KEY-----' > /tmp/kiplatz-1.pem; \
    printf '%s\n' '-----BEGIN PUBLIC KEY-----' 'MCowBQYDK2VwAyEAOF758lOi5oKh6rttdYLB5Vb5oIU1KYES9pz+06YKXIw=' '-----END PUBLIC KEY-----' > /tmp/kiplatz-2.pem; \
    for k in /tmp/kiplatz-1.pem /tmp/kiplatz-2.pem; do if openssl pkeyutl -verify -pubin -inkey $k -rawin -in KIplatz-Helfer-linux-x64.tar.gz -sigfile /tmp/kiplatz.sig.bin >/dev/null 2>&1; then ok=1; break; fi; done; \
    rm -f /tmp/kiplatz.sig.bin /tmp/kiplatz-1.pem /tmp/kiplatz-2.pem; \
    if [ "$ok" != 1 ]; then echo "KIplatz: die Unterschrift des Helfer-Pakets stimmt nicht, nichts wird gebaut" >&2; exit 1; fi; \
    tar -xzf KIplatz-Helfer-linux-x64.tar.gz -C /home/kiplatz/helfer --no-same-owner; \
    chown -R kiplatz:kiplatz /home/kiplatz/helfer; \
    cd /; rm -rf /tmp/helfer
ENV KIPLATZ_CONTAINER=1 \
    HOME=/home/kiplatz \
    XDG_DATA_HOME=/daten/data \
    XDG_STATE_HOME=/daten/state \
    XDG_CONFIG_HOME=/daten/config \
    PATH=/home/kiplatz/helfer/kiplatz-helfer:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
USER 10001:10001
WORKDIR /home/kiplatz
VOLUME /daten
# gesund, solange der laufende Helfer jede Minute seinen Stand schreibt (kiplatz-helfer status liest ihn)
HEALTHCHECK --interval=2m --timeout=10s --start-period=10m CMD find /daten/data/kiplatz/daten/helfer-stand.json -mmin -3 | grep -q .
ENTRYPOINT ["/home/kiplatz/helfer/kiplatz-helfer/kiplatz-helfer"]
CMD ["start"]
