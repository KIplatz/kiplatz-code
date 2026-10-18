# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import queue
import secrets
import struct
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import stueckliste

MAGIC = b"KW"
VERSION = 1
HALLO, WUNSCH, DATEN, FERTIG = 1, 2, 3, 4
NUTZLAST = 1200
BITMAP = 64
KOPF = struct.Struct("!2sBB8s12s")
DATEN_KOPF = struct.Struct("!II")
WUNSCH_KOPF = struct.Struct("!II")
BEGRUESSUNG_S = 5.0
BEGRUESSUNG_ZEITEN = (0.0, 0.3, 0.6, 1.0, 1.5, 2.0, 3.0, 4.0)
STILL_S = 10.0
STUECK_HOECHSTENS_S = 120.0
NACHFORDERN_S = 0.3
FENSTER_START, FENSTER_MIN, FENSTER_MAX = 32, 8, 256
WIEDERHOLUNG_FENSTER = 4096
HOECHSTENS_PARTNER = 2


class ZugFehler(OSError):
    pass


def pakete_je_stueck(stueck_groesse: int) -> int:
    return max(1, -(-stueck_groesse // NUTZLAST))


def _schluessel(paar_schluessel: bytes) -> tuple[bytes, bytes]:
    def hk(info: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(paar_schluessel)
    return hk(b"KIplatz weitergeben halter"), hk(b"KIplatz weitergeben lader")


class Seite:

    def __init__(self, paar: bytes, paar_schluessel: bytes, *, halter: bool) -> None:
        h2l, l2h = _schluessel(paar_schluessel)
        self.paar = paar
        self._aus = AESGCM(h2l if halter else l2h)
        self._ein = AESGCM(l2h if halter else h2l)
        self._praefix = secrets.token_bytes(4)
        self._zaehler = 0
        self._partner_praefix: bytes | None = None
        self._hoechster = 0
        self._gesehen: set[int] = set()

    def bauen(self, typ: int, inhalt: bytes = b"") -> bytes:
        self._zaehler += 1
        nonce = self._praefix + self._zaehler.to_bytes(8, "big")
        kopf = KOPF.pack(MAGIC, VERSION, typ, self.paar, nonce)
        return kopf + self._aus.encrypt(nonce, inhalt, kopf)

    def lesen(self, daten: bytes) -> tuple[int, bytes] | None:
        if len(daten) < KOPF.size + 16 or len(daten) > KOPF.size + DATEN_KOPF.size + NUTZLAST + 16:
            return None
        try:
            magic, ver, typ, paar, nonce = KOPF.unpack(daten[:KOPF.size])
        except struct.error:
            return None
        if magic != MAGIC or ver != VERSION or paar != self.paar:
            return None
        try:
            inhalt = self._ein.decrypt(nonce, daten[KOPF.size:], daten[:KOPF.size])
        except InvalidTag:
            return None
        praefix, z = nonce[:4], int.from_bytes(nonce[4:], "big")
        if self._partner_praefix is None:
            self._partner_praefix = praefix
        elif praefix != self._partner_praefix:
            return None
        if z <= self._hoechster - WIEDERHOLUNG_FENSTER or z in self._gesehen:
            return None
        self._gesehen.add(z)
        if z > self._hoechster:
            self._hoechster = z
            if len(self._gesehen) > 2 * WIEDERHOLUNG_FENSTER:
                self._gesehen = {x for x in self._gesehen if x > self._hoechster - WIEDERHOLUNG_FENSTER}
        return typ, inhalt


def _begruessen(seite: Seite, senden, ein: "queue.Queue[bytes]", uhr=time.monotonic) -> None:
    anfang = uhr()
    zeiten = list(BEGRUESSUNG_ZEITEN)
    while True:
        jetzt = uhr() - anfang
        if zeiten and jetzt >= zeiten[0]:
            zeiten.pop(0)
            senden(seite.bauen(HALLO))
        if jetzt > BEGRUESSUNG_S:
            raise ZugFehler("keine Antwort vom anderen PC")
        try:
            roh = ein.get(timeout=0.1)
        except queue.Empty:
            continue
        p = seite.lesen(roh)
        if p is not None:
            if p[0] == HALLO:
                senden(seite.bauen(HALLO))
            return


class Halter:

    def __init__(self, paar: bytes, paar_schluessel: bytes, datei: Path, senden, *, bytes_je_s: float = 4 * 1024 * 1024,
                 uhr=time.monotonic, schlafen=time.sleep, pause=lambda: False) -> None:
        self.seite = Seite(paar, paar_schluessel, halter=True)
        self.datei, self.senden, self.uhr, self.schlafen = Path(datei), senden, uhr, schlafen
        self.bytes_je_s = bytes_je_s
        self.pause = pause
        self.groesse = self.datei.stat().st_size
        self.gesendet = 0

    def laufen(self, ein: "queue.Queue[bytes]") -> int:
        _begruessen(self.seite, self.senden, ein, self.uhr)
        frei_ab = self.uhr()
        letzte = self.uhr()
        with open(self.datei, "rb") as f:
            while True:
                if self.uhr() - letzte > STILL_S:
                    raise ZugFehler("der Lader meldet sich nicht mehr")
                try:
                    roh = ein.get(timeout=0.5)
                except queue.Empty:
                    continue
                p = self.seite.lesen(roh)
                if p is None:
                    continue
                typ, inhalt = p
                if typ == FERTIG:
                    return self.gesendet
                if typ != WUNSCH or len(inhalt) != WUNSCH_KOPF.size + BITMAP:
                    continue
                letzte = self.uhr()
                nr_stueck, start = WUNSCH_KOPF.unpack(inhalt[:WUNSCH_KOPF.size])
                bitmap = inhalt[WUNSCH_KOPF.size:]
                basis = nr_stueck * stueckliste.STUECK
                ende_stueck = min(self.groesse, basis + stueckliste.STUECK)
                if basis >= self.groesse:
                    continue
                for i in range(BITMAP * 8):
                    if not bitmap[i // 8] >> (i % 8) & 1:
                        continue
                    nr = start + i
                    von = basis + nr * NUTZLAST
                    if von >= ende_stueck:
                        break
                    while self.pause():
                        self.schlafen(0.2)
                    f.seek(von)
                    stueck = f.read(min(NUTZLAST, ende_stueck - von))
                    jetzt = self.uhr()
                    frei_ab = max(frei_ab, jetzt) + len(stueck) / self.bytes_je_s
                    if frei_ab - jetzt > 0.002:
                        self.schlafen(frei_ab - jetzt)
                    self.senden(self.seite.bauen(DATEN, DATEN_KOPF.pack(nr_stueck, nr) + stueck))
                    self.gesendet += len(stueck)


class Lader:

    def __init__(self, paar: bytes, paar_schluessel: bytes, senden, ein: "queue.Queue[bytes]", groesse: int, *,
                 uhr=time.monotonic) -> None:
        self.seite = Seite(paar, paar_schluessel, halter=False)
        self.senden, self.ein, self.uhr = senden, ein, uhr
        self.groesse = groesse
        self.fenster = FENSTER_START
        self.begruesst = False

    def begruessen(self) -> None:
        _begruessen(self.seite, self.senden, self.ein, self.uhr)
        self.begruesst = True

    def stueck(self, nr_stueck: int, ab: int = 0) -> bytes:
        basis = nr_stueck * stueckliste.STUECK
        laenge = min(stueckliste.STUECK, self.groesse - basis)
        if laenge <= 0:
            raise ZugFehler("hinter dem Dateiende")
        n = pakete_je_stueck(laenge)
        erst = ab // NUTZLAST
        da: dict[int, bytes] = {}
        anfang = self.uhr()
        letzte_daten = self.uhr()
        while True:
            fehlend = [i for i in range(erst, n) if i not in da]
            if not fehlend:
                break
            if self.uhr() - anfang > STUECK_HOECHSTENS_S:
                raise ZugFehler("ein Stück hat zu lange gedauert")
            start = fehlend[0]
            wunsch = [i for i in fehlend if i - start < BITMAP * 8][:self.fenster]
            bitmap = bytearray(BITMAP)
            for i in wunsch:
                bitmap[(i - start) // 8] |= 1 << ((i - start) % 8)
            self.senden(self.seite.bauen(WUNSCH, WUNSCH_KOPF.pack(nr_stueck, start) + bytes(bitmap)))
            erwartet, neu = set(wunsch), 0
            frist = self.uhr() + NACHFORDERN_S
            while erwartet and self.uhr() < frist:
                try:
                    roh = self.ein.get(timeout=max(0.01, frist - self.uhr()))
                except queue.Empty:
                    break
                p = self.seite.lesen(roh)
                if p is None or p[0] != DATEN or len(p[1]) < DATEN_KOPF.size:
                    continue
                s, i = DATEN_KOPF.unpack(p[1][:DATEN_KOPF.size])
                if s != nr_stueck or i >= n or i in da:
                    continue
                if len(p[1]) - DATEN_KOPF.size != min(NUTZLAST, laenge - i * NUTZLAST):
                    continue
                da[i] = p[1][DATEN_KOPF.size:]
                letzte_daten = self.uhr()
                if i in erwartet:
                    erwartet.discard(i)
                    neu += 1
                    frist = self.uhr() + NACHFORDERN_S
            if self.uhr() - letzte_daten > STILL_S:
                raise ZugFehler("der andere PC schickt nichts mehr")
            verlust = 1 - neu / max(1, len(wunsch))
            self.fenster = max(FENSTER_MIN, self.fenster // 2) if verlust > 0.1 else min(FENSTER_MAX, self.fenster + 4)
        daten = b"".join(da[i] for i in range(erst, n))
        return daten[ab - erst * NUTZLAST:]

    def fertig(self) -> None:
        try:
            self.senden(self.seite.bauen(FERTIG))
        except OSError:
            pass


class LaderStrom:

    def __init__(self, lader: Lader, ab: int) -> None:
        self.lader, self.pos = lader, ab
        self.status = 206 if ab else 200
        self._puffer = b""

    def read(self, n: int = -1) -> bytes:
        while len(self._puffer) < (n if n > 0 else 1) and self.pos < self.lader.groesse:
            nr = self.pos // stueckliste.STUECK
            stueck = self.lader.stueck(nr, self.pos - nr * stueckliste.STUECK)
            self._puffer += stueck
            self.pos += len(stueck)
        if n is None or n < 0:
            n = len(self._puffer)
        aus, self._puffer = self._puffer[:n], self._puffer[n:]
        return aus

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.lader.fertig()
        return False
