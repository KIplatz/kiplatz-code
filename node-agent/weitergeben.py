# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ipaddress
import queue
import socket
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import modell_katalog
import sicher_schreiben
import stueck_zug
import treffpunkt_basis

LEBENSZEICHEN_S = 25.0
EINMAL_ZEITEN = (0.0, 2.0, 4.0)
EINMAL_WARTEN_S = 6.0
FEHLT_HOECHSTENS = 3
HABE_S = 600.0
SITZUNG_ERNEUERN_S = 1800.0
BYTES_JE_S = 4 * 1024 * 1024
MONAT_BYTES = 30 * 1000 ** 3
HOECHSTENS_HALTER = 2
EINSTELLUNG = "weitergeben.json"
GEHT_NICHT = "Weitergeben geht in diesem Netz nicht; Modelle kommen vom Server."


def ziel_erlaubt(ip: str) -> bool:
    try:
        a = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return a.is_global and not a.is_multicast


class Weitergeber:
    def __init__(self, core, community, modelle_dir, *, uhr=time.time, schlafen=time.sleep, log=lambda z: None,
                 sock_fabrik=lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM), adresse_aufloesen=socket.gethostbyname,
                 rechenkraft_laeuft=lambda: False, frage_laeuft=lambda: False) -> None:
        self._core, self._community, self._modelle_dir = core, community, Path(modelle_dir)
        self._uhr, self._schlafen, self._log = uhr, schlafen, log
        self._sock_fabrik, self._aufloesen = sock_fabrik, adresse_aufloesen
        self._rechenkraft_laeuft, self._frage_laeuft = rechenkraft_laeuft, frage_laeuft
        self.zustand = "aus"
        self._sock = None
        self._ziel = None
        self._sitzung: dict = {}
        self._zaehler = 0
        self._spiegel = threading.Event()
        self._fehlt = 0
        self._wege: dict[bytes, tuple["queue.Queue[bytes]", tuple[str, int]]] = {}
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self._aktive_halter = 0
        self._letzte_habe = 0.0
        self.weitergegeben_heute = 0

    def _einstellung(self) -> dict:
        d = sicher_schreiben.json_laden(Path(self._core.base_dir) / EINSTELLUNG, {}, art=dict)
        return d if isinstance(d, dict) else {}

    def an(self) -> bool:
        return self._einstellung().get("an", True) is not False

    def setzen(self, an: bool) -> None:
        sicher_schreiben.json_datei(Path(self._core.base_dir) / EINSTELLUNG, {**self._einstellung(), "an": bool(an)})

    def _monat(self) -> tuple[str, int]:
        e = self._einstellung()
        m = datetime.now().strftime("%Y-%m")
        return m, int(e.get("bytes", 0) or 0) if e.get("monat") == m else 0

    def _monat_dazu(self, n: int) -> None:
        m, b = self._monat()
        sicher_schreiben.json_datei(Path(self._core.base_dir) / EINSTELLUNG, {**self._einstellung(), "monat": m, "bytes": b + int(n)})

    def zeile(self) -> str:
        if self.zustand == "geht_nicht":
            return GEHT_NICHT
        if self.zustand != "bereit":
            return ""
        if not self.an():
            return "Modelle weitergeben: aus."
        _, b = self._monat()
        return f"Modelle weitergeben: bereit; diesen Monat {b / 1000 ** 3:.1f} GB an andere Mitglieder weitergegeben."

    def starten(self) -> None:
        if self.zustand != "aus":
            return
        self.zustand = "pruefe"
        threading.Thread(target=self._lauf, name="weitergeben", daemon=True).start()

    def anhalten(self) -> None:
        self._halt.set()
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass

    def _geht_nicht(self, grund: str) -> None:
        self.zustand = "geht_nicht"
        self._log(f"weitergeben: geht in diesem Netz nicht ({grund}); bis zum nächsten Programmstart kein Versuch mehr")
        self.anhalten()

    def _anmelden(self) -> None:
        r = self._community._anfrage("/weitergeben/anmelden", {}, als_geraet=True)
        self._sitzung = {"sitzung": bytes.fromhex(r["sitzung"]), "ablauf": int(r["ablauf"]), "schluessel": bytes.fromhex(r["schluessel"]),
                         "seit": self._uhr()}
        host = urllib.parse.urlsplit(self._community.adresse).hostname or "kiplatz.at"
        self._ziel = (self._aufloesen(host), int(r.get("udp") or treffpunkt_basis.UDP_PORT))

    def _lebenszeichen(self) -> None:
        self._zaehler = max(self._zaehler + 1, int(time.time()))
        s = self._sitzung
        self._sock.sendto(treffpunkt_basis.lebenszeichen(s["schluessel"], s["sitzung"], s["ablauf"], self._zaehler, jetzt=self._uhr()), self._ziel)

    def _lauf(self) -> None:
        try:
            self._anmelden()
        except Exception as exc:
            self.zustand = "server_nicht"
            self._log(f"weitergeben: der Server bietet es gerade nicht an ({type(exc).__name__}); bis zum nächsten Programmstart kein Versuch mehr")
            self.anhalten()
            return
        try:
            self._sock = self._sock_fabrik()
            self._sock.bind(("0.0.0.0", 0))
            self._sock.settimeout(0.5)
        except Exception as exc:
            self._geht_nicht(type(exc).__name__)
            return
        threading.Thread(target=self._empfangen, name="weitergeben-ein", daemon=True).start()
        anfang = self._uhr()
        for t in EINMAL_ZEITEN:
            while self._uhr() - anfang < t and not self._spiegel.is_set():
                self._schlafen(0.1)
            if self._spiegel.is_set():
                break
            try:
                self._lebenszeichen()
            except OSError:
                break
        while self._uhr() - anfang < EINMAL_WARTEN_S and not self._spiegel.is_set():
            self._schlafen(0.1)
        if not self._spiegel.is_set():
            self._geht_nicht("keine Antwort vom Treffpunkt")
            return
        self.zustand = "bereit"
        self._log("weitergeben: bereit")
        while not self._halt.is_set():
            self._spiegel.clear()
            if self._uhr() - self._sitzung["seit"] > SITZUNG_ERNEUERN_S:
                try:
                    self._anmelden()
                except Exception:
                    pass
            try:
                self._lebenszeichen()
            except OSError:
                self._geht_nicht("Senden geht nicht mehr")
                return
            if self._rechenkraft_laeuft() and self.an() and self._uhr() - self._letzte_habe > HABE_S:
                self._habe_melden()
            if self._halt.wait(LEBENSZEICHEN_S):
                return
            if not self._spiegel.is_set():
                self._fehlt += 1
                if self._fehlt >= FEHLT_HOECHSTENS:
                    self._geht_nicht("Lebenszeichen bleiben unbeantwortet")
                    return
            else:
                self._fehlt = 0

    def _empfangen(self) -> None:
        while not self._halt.is_set() and self._sock is not None:
            try:
                daten, absender = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            if daten[:2] == treffpunkt_basis.MAGIC and absender == self._ziel:
                if treffpunkt_basis.spiegel_lesen(self._sitzung.get("schluessel", b""), self._sitzung.get("sitzung", b""), daten):
                    self._spiegel.set()
                continue
            if daten[:2] == stueck_zug.MAGIC and len(daten) >= stueck_zug.KOPF.size:
                paar = daten[4:12]
                with self._lock:
                    weg = self._wege.get(paar)
                if weg is not None and absender == weg[1]:
                    weg[0].put(daten)

    def _vorhanden(self) -> list[str]:
        out = []
        for p in modell_katalog.ALLE:
            if not p.stuecke_sha256:
                continue
            z = self._modelle_dir / p.datei
            try:
                if z.is_file() and z.stat().st_size == p.groesse:
                    out.append(p.datei)
            except OSError:
                pass
        return out

    def _habe_melden(self) -> None:
        self._letzte_habe = self._uhr()
        _, b = self._monat()
        dateien = self._vorhanden() if b < MONAT_BYTES else []
        try:
            self._community._anfrage("/weitergeben/habe", {"dateien": dateien}, als_geraet=True)
        except Exception:
            pass

    def halter_auftrag(self, a: dict) -> bool:
        if self.zustand != "bereit" or not self.an() or not self._rechenkraft_laeuft() or self._aktive_halter >= stueck_zug.HOECHSTENS_PARTNER:
            return False
        try:
            paar, schluessel = bytes.fromhex(str(a["paar"])), bytes.fromhex(str(a["schluessel"]))
            ip, port = str(a["an"]).rsplit(":", 1)
            datei = modell_katalog.NACH_DATEI[str(a["datei"])].datei
        except (KeyError, ValueError, TypeError):
            return False
        if len(paar) != 8 or len(schluessel) != 32 or not ziel_erlaubt(ip) or datei not in self._vorhanden() or self._monat()[1] >= MONAT_BYTES:
            return False
        ziel = (ip, int(port))
        ein: "queue.Queue[bytes]" = queue.Queue()
        with self._lock:
            self._wege[paar] = (ein, ziel)
            self._aktive_halter += 1

        def lauf():
            h = None
            try:
                h = stueck_zug.Halter(paar, schluessel, self._modelle_dir / datei, lambda b: self._sock.sendto(b, ziel), bytes_je_s=BYTES_JE_S,
                                      pause=self._frage_laeuft)
                h.laufen(ein)
            except (stueck_zug.ZugFehler, OSError):
                pass
            finally:
                if h is not None and h.gesendet:
                    self._monat_dazu(h.gesendet)
                    self.weitergegeben_heute += h.gesendet
                    self._log(f"weitergeben: {h.gesendet // (1024 * 1024)} MB an ein anderes Mitglied")
                with self._lock:
                    self._wege.pop(paar, None)
                    self._aktive_halter -= 1
        threading.Thread(target=lauf, name="weitergeben-halter", daemon=True).start()
        return True

    def quellen(self, paket):
        if self.zustand != "bereit" or not paket.stuecke_sha256:
            return
        for _ in range(HOECHSTENS_HALTER):
            try:
                r = self._community._anfrage("/weitergeben/halter", {"datei": paket.datei}, als_geraet=True)
            except Exception:
                return
            if not r.get("halter"):
                return
            try:
                paar, schluessel = bytes.fromhex(r["paar"]), bytes.fromhex(r["schluessel"])
                ip, port = str(r["von"]).rsplit(":", 1)
            except (KeyError, ValueError, TypeError):
                return
            if not ziel_erlaubt(ip):
                continue
            von = (ip, int(port))
            ein: "queue.Queue[bytes]" = queue.Queue()
            with self._lock:
                self._wege[paar] = (ein, von)
            lader = stueck_zug.Lader(paar, schluessel, lambda b, von=von: self._sock.sendto(b, von), ein, paket.groesse)

            def oeffner(req, timeout, lader=lader):
                if not lader.begruesst:
                    lader.begruessen()
                rng = req.headers.get("Range") or req.get_header("Range") or ""
                ab = int(rng.split("=")[1].rstrip("-")) if rng.startswith("bytes=") else 0
                return stueck_zug.LaderStrom(lader, ab)

            def melden(paar_hex=r["paar"]):
                try:
                    self._community._anfrage("/weitergeben/melden", {"paar": paar_hex}, als_geraet=True)
                except Exception:
                    pass

            def fertig(paar=paar, paar_hex=r["paar"]):
                with self._lock:
                    self._wege.pop(paar, None)
                try:
                    self._community._anfrage("/weitergeben/fertig", {"paar": paar_hex}, als_geraet=True)
                except Exception:
                    pass

            yield oeffner, melden, fertig
