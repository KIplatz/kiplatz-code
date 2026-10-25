# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import struct
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import sicher_schreiben
import wissen

FORMAT = 1
DIRNAME = "scheiben"
LANDKARTE = "landkarte.json"
ZIEL_ZEICHEN = 4_000_000
REIFE_S = 24 * 3600
KOPIEN = 3
GESEHEN_S = 7 * 24 * 3600
VERGESSEN_S = 14 * 24 * 3600
STICHPROBE_S = 24 * 3600
AUFTRAG_FRIST_S = 6 * 3600
TAKT_JE_GERAET_S = 300
VERSTOESSE_RAUS = 3
MAX_SCHEIBE_BYTES = 64 * 1024 * 1024
HALTEN_ART = "scheibe_halten"
LIEFERN_ART = "scheibe_liefern"
CREDITS_JE_SCHEIBE = 1
CREDITS_JE_STICHPROBE = 1
ARTEN_IN_SCHEIBEN = ("seite",)
VEKTOR_WARTEN_S = 3 * 24 * 3600
ABGEBEN_WARTEN_S = 24 * 3600
KALT_STICHPROBE_S = 7 * 24 * 3600
HINWEIS = ("Eine Scheibe des gemeinsamen Wissens von KIplatz (kiplatz.at): öffentliche Quellen, jede mit Titel und Adresse; die Lizenz "
           "steht bei der Quelle (Wikipedia: CC BY-SA 4.0). Lesbar mit jedem Packprogramm, Prüfsummen in scheibe.json.")
_ZEIT = (1980, 1, 1, 0, 0, 0)

WIKI_ART = "wiki-vektoren"
WIKI_JE_SCHEIBE = 50_000
WIKI_TRANSIT_BYTES = 1024 ** 3
WIKI_TRANSIT_S = 3 * 24 * 3600
WIKI_GESUCHT_S = 2 * 24 * 3600
WIKI_ZURUECK_HOECHSTENS = 4
WIKI_JE_GERAET_S = 60
WIKI_JE_GERAET_ZUGLEICH = 4
WIKI_ABGELEHNT_SPERRE = 2
WIKI_SPERRE_S = 30 * 24 * 3600
WIKI_HINWEIS = ("Zahlenreihen (Vektoren) zu Abschnitten der deutschen Wikipedia, je Abschnitt nur ein Hash, kein Text (kiplatz.at). "
                "Ein Gerät mit derselben Wikipedia-Kopie übernimmt sie, statt sie selbst zu rechnen.")
_WIKI_SATZ = struct.Struct("<16sH")


def _zip_ablegen(z: zipfile.ZipFile, name: str, daten: bytes) -> str:
    info = zipfile.ZipInfo(name, date_time=_ZEIT)
    info.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(info, daten)
    return hashlib.sha256(daten).hexdigest()


def wiki_packen(paare, *, ausgabe: str, modell: str, nr: int, ordner: Path) -> dict | None:
    teile, von, bis, n, vorher = [], b"", b"", 0, b""
    for h, v in paare:
        h, v = bytes(h), bytes(v)
        if len(h) != 16 or not v or len(v) > 0xFFFF or h < vorher:
            raise ScheibenError("WIKI_FORMAT", "Hash oder Vektor unbrauchbar oder nicht sortiert")
        teile.append(_WIKI_SATZ.pack(h, len(v)) + v)
        von = von or h
        bis, vorher, n = h, h, n + 1
    if not n:
        return None
    daten = b"".join(teile)
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    tmp = ordner / f"wiki-{nr}-{os.getpid()}.zip.teil"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        dateien = {"vektoren.bin": _zip_ablegen(z, "vektoren.bin", daten)}
        manifest = {"format": FORMAT, "art": WIKI_ART, "ausgabe": str(ausgabe), "modell": str(modell), "nr": int(nr), "anzahl": n,
                    "von": von.hex(), "bis": bis.hex(), "hinweis": WIKI_HINWEIS, "dateien": dateien}
        _zip_ablegen(z, "scheibe.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8"))
    sha = pruefsumme(tmp)
    ziel = ordner / f"{sha[:16]}.zip"
    if ziel.exists():
        tmp.unlink()
    else:
        os.replace(tmp, ziel)
    if ziel.stat().st_size > MAX_SCHEIBE_BYTES:
        ziel.unlink()
        raise ScheibenError("WIKI_GROSS", "die Scheibe wäre größer als erlaubt")
    return {"kennung": sha[:16], "sha256": sha, "bytes": ziel.stat().st_size, "anzahl": n, "pfad": ziel}


def wiki_lesen(pfad: Path, *, modell: str | None = None):
    m = scheibe_lesen(pfad)
    if m.get("art") != WIKI_ART or set(m["dateien"]) != {"vektoren.bin"} or not str(m.get("ausgabe", "")).isdigit():
        raise ScheibenError("WIKI_FORMAT", "keine Scheibe mit Wikipedia-Vektoren")
    if modell is not None and str(m.get("modell")) != str(modell):
        raise ScheibenError("WIKI_MODELL", "die Vektoren stammen von einem anderen Bedeutungs-Modell")
    with zipfile.ZipFile(pfad) as z:
        daten = z.read("vektoren.bin")
    paare, i, vorher = [], 0, b""
    while i < len(daten):
        if i + _WIKI_SATZ.size > len(daten):
            raise ScheibenError("WIKI_FORMAT", "abgeschnittener Eintrag")
        h, lang = _WIKI_SATZ.unpack_from(daten, i)
        i += _WIKI_SATZ.size
        if lang == 0 or i + lang > len(daten) or h < vorher:
            raise ScheibenError("WIKI_FORMAT", "Eintrag unbrauchbar oder nicht sortiert")
        paare.append((h, daten[i:i + lang]))
        i += lang
        vorher = h
    if not paare or len(paare) != int(m.get("anzahl", -1)) or paare[0][0].hex() != m.get("von") or paare[-1][0].hex() != m.get("bis"):
        raise ScheibenError("WIKI_FORMAT", "Anzahl oder Bereich passt nicht zum Manifest")
    return m, paare


class ScheibenError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code, self.detail = code, detail


def _jetzt_iso(t: float | None = None) -> str:
    return datetime.fromtimestamp(t if t is not None else time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_zu_s(iso: str) -> float:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


def pruefsumme(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for stueck in iter(lambda: f.read(1024 * 1024), b""):
            h.update(stueck)
    return h.hexdigest()


def scheibe_lesen(pfad: Path) -> dict:
    with zipfile.ZipFile(pfad) as z:
        m = json.loads(z.read("scheibe.json").decode("utf-8"))
        if m.get("format") != FORMAT or not isinstance(m.get("dateien"), dict):
            raise ScheibenError("SCHEIBE_FORMAT", "unbekanntes Scheiben-Format")
        for name, soll in m["dateien"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != soll:
                raise ScheibenError("SCHEIBE_INHALT", f"Datei {name} passt nicht zur Prüfsumme")
    return m


SPEICHER_ABSTAND_S = 2.0


def _weg(pfad: Path) -> None:
    for versuch in range(25):
        try:
            pfad.unlink(missing_ok=True)
            return
        except PermissionError:
            if versuch == 24:
                raise
            time.sleep(0.005 * (versuch + 1))


def _gesperrt(f):
    @functools.wraps(f)
    def w(self, *a, **kw):
        with self._sperre:
            return f(self, *a, **kw)
    return w


class Scheiben:
    def __init__(self, ordner: Path, speicher: wissen.Wissensspeicher, verteiler, *, jetzt=time.time, log=None) -> None:
        self.dir = Path(ordner) / DIRNAME
        self.speicher = speicher
        self.verteiler = verteiler
        self._jetzt = jetzt
        self._log = log or (lambda zeile: None)
        self.bremse = None
        self._karte_pfad = self.dir / LANDKARTE
        self._zuletzt_geprueft = 0.0
        self._sperre = threading.RLock()
        self._k: dict | None = None
        self._stempel = None
        self._offen = False
        self._geschrieben = 0.0
        self._timer: threading.Timer | None = None
        self.speicher_abstand_s = SPEICHER_ABSTAND_S


    def _stempel_jetzt(self):
        try:
            st = self._karte_pfad.stat()
            return (st.st_ino, st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _karte(self) -> dict:
        if self._k is not None and (self._offen or self._stempel_jetzt() == self._stempel):
            k = self._k
        else:
            k = sicher_schreiben.json_laden(self._karte_pfad, {}, art=dict)
            self._k, self._stempel = k, self._stempel_jetzt()
        k.setdefault("format", FORMAT)
        for name in ("scheiben", "geraete", "quellen"):
            if not isinstance(k.get(name), dict):
                k[name] = {}
        if not isinstance(k.get("gesperrt"), list):
            k["gesperrt"] = []
        return k

    def _schreiben(self, k: dict, *, spaeter: bool = False) -> None:
        self._k, self._offen = k, True
        warten = self.speicher_abstand_s - (time.monotonic() - self._geschrieben)
        if spaeter and warten > 0:
            if self._timer is None:
                self._timer = threading.Timer(warten, self._spaeter)
                self._timer.daemon = True
                self._timer.start()
            return
        self._jetzt_schreiben()

    def _jetzt_schreiben(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.dir.mkdir(parents=True, exist_ok=True)
        sicher_schreiben.json_datei(self._karte_pfad, self._k, indent=None)
        self._stempel = self._stempel_jetzt()
        self._offen = False
        self._geschrieben = time.monotonic()

    def _spaeter(self) -> None:
        with self._sperre:
            self._timer = None
            if self._offen:
                try:
                    self._jetzt_schreiben()
                except OSError as exc:
                    self._log(f"FEHLER landkarte schreiben: {type(exc).__name__}")

    def sichern(self) -> None:
        with self._sperre:
            if self._offen:
                self._jetzt_schreiben()

    def pfad(self, kennung: str) -> Path:
        return self.dir / f"{kennung}.zip"


    def _kandidaten(self, k: dict) -> list[tuple[wissen.Quelle, str]]:
        aus = []
        index = self.verteiler._im_index() if self.verteiler is not None else {}
        jetzt = self._jetzt()
        for q, _teile, hashes in self.speicher.alle_mit_hash():
            if q.art not in ARTEN_IN_SCHEIBEN or q.privat or not q.freigegeben or not q.gueltig() or q.kennung in k["quellen"]:
                continue
            if not self.speicher._pfad(q.kennung).is_file():
                continue
            fertig = self.verteiler is None or all(index.get(f"{q.kennung}:{i}", {}).get("hash") == h for i, h in enumerate(hashes))
            if not fertig and jetzt - _iso_zu_s(q.datum) < VEKTOR_WARTEN_S:
                continue
            aus.append(q)
        aus.sort(key=lambda q: q.datum)
        return [(q, q.kennung) for q in aus]

    @_gesperrt
    def schreiben_wenn_reif(self) -> str | None:
        k = self._karte()
        kandidaten = self._kandidaten(k)
        if not kandidaten:
            return None
        gewaehlt, zeichen = [], 0
        for q, _ in kandidaten:
            gewaehlt.append(q)
            zeichen += q.zeichen
            if zeichen >= ZIEL_ZEICHEN:
                break
        reif = zeichen >= ZIEL_ZEICHEN or self._jetzt() - _iso_zu_s(kandidaten[0][0].datum) >= REIFE_S
        if not reif:
            return None
        return self.schreiben(gewaehlt)

    @_gesperrt
    def schreiben(self, quellen: list[wissen.Quelle]) -> str:
        if not quellen:
            raise ScheibenError("SCHEIBE_LEER", "keine Quellen für eine Scheibe")
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"neu-{os.getpid()}-{int(self._jetzt() * 1000)}.zip.teil"
        dateien: dict[str, str] = {}
        eintraege = []
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            def ablegen(name: str, daten: bytes) -> str:
                info = zipfile.ZipInfo(name, date_time=_ZEIT)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, daten)
                dateien[name] = hashlib.sha256(daten).hexdigest()
                return dateien[name]
            for q in sorted(quellen, key=lambda q: q.kennung):
                roh = self.speicher._pfad(q.kennung).read_bytes()
                name = f"quellen/{q.kennung}.json"
                sha = ablegen(name, roh)
                eintraege.append({"kennung": q.kennung, "art": q.art, "titel": q.titel, "adresse": q.adresse, "datum": q.datum, "zeichen": q.zeichen, "datei": name, "sha256": sha})
                v = self._vertieft(q.kennung)
                if v:
                    ablegen(f"vertieft/{q.kennung}.json", json.dumps(v, ensure_ascii=False, sort_keys=True).encode("utf-8"))
                vk = self._vektoren(q.kennung)
                if vk:
                    ablegen(f"vektoren/{q.kennung}.json", json.dumps(vk, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            manifest = {"format": FORMAT, "erstellt": _jetzt_iso(self._jetzt()), "hinweis": HINWEIS, "quellen": eintraege, "dateien": dateien}
            info = zipfile.ZipInfo("scheibe.json", date_time=_ZEIT)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8"))
        sha = pruefsumme(tmp)
        kennung = sha[:16]
        ziel = self.pfad(kennung)
        if ziel.exists():
            tmp.unlink()
        else:
            os.replace(tmp, ziel)
        k = self._karte()
        if kennung not in k["scheiben"]:
            k["scheiben"][kennung] = {"bytes": ziel.stat().st_size, "sha256": sha, "quellen": [q.kennung for q in quellen], "erstellt": _jetzt_iso(self._jetzt()),
                                       "halter": {}, "offen": {}, "stichprobe": ""}
        for q in quellen:
            k["quellen"][q.kennung] = kennung
        self._schreiben(k)
        self._log(f"SCHEIBE {kennung} geschrieben: {len(quellen)} Quellen, {ziel.stat().st_size} Bytes")
        return kennung

    def _vertieft(self, quelle: str) -> dict:
        try:
            v = self.verteiler._vertieft_lesen(quelle) if self.verteiler is not None else {}
        except Exception:
            v = {}
        return v if isinstance(v, dict) and v.get("abschnitte") else {}

    def _vektoren(self, quelle: str) -> dict:
        try:
            v = self.verteiler.index_von(quelle) if self.verteiler is not None and hasattr(self.verteiler, "index_von") else {}
        except Exception:
            v = {}
        return v if isinstance(v, dict) and v.get("abschnitte") else {}


    @_gesperrt
    def kalt_machen(self) -> int:
        k = self._karte()
        jetzt = self._jetzt()
        n = 0
        for kennung, s in k["scheiben"].items():
            if s.get("veraltet") or len(self._halter_aktiv(k, s)) < KOPIEN or jetzt - _iso_zu_s(s.get("stichprobe", "")) >= KALT_STICHPROBE_S:
                continue
            ziel = self.pfad(kennung)
            if not ziel.is_file() or ziel.stat().st_size != s["bytes"]:
                continue
            try:
                if pruefsumme(ziel) != s["sha256"]:
                    continue
                m = scheibe_lesen(ziel)
            except (OSError, ScheibenError, ValueError, KeyError):
                continue
            soll = {str(e.get("kennung")): str(e.get("sha256")) for e in m.get("quellen", []) if isinstance(e, dict)}
            for q in s.get("quellen", []):
                p = self.speicher._pfad(q)
                if not p.is_file() or q not in soll:
                    continue
                try:
                    if hashlib.sha256(p.read_bytes()).hexdigest() != soll[q]:
                        continue
                    p.unlink()
                except OSError:
                    continue
                self.speicher._cache.pop(q, None)
                n += 1
            if not s.get("kalt"):
                s["kalt"] = _jetzt_iso(jetzt)
        abgegeben = self._abgeben(k, jetzt)
        if n or abgegeben:
            self._schreiben(k)
            if n:
                self._log(f"SCHEIBE kalt: {n} Quellen-Dateien aus dem Speicher genommen, sie liegen in den Scheiben")
            if abgegeben:
                self._log(f"SCHEIBE abgegeben: {abgegeben} gepackte Scheiben liegen nur noch bei den Haltern; Wörter und Texte stehen im Wortindex")
        elif any(s.get("kalt") for s in k["scheiben"].values()):
            self._schreiben(k)
        return n

    def _abgeben(self, k: dict, jetzt: float) -> int:
        wi = getattr(self.speicher, "wortindex", None)
        if wi is None:
            return 0
        n = 0
        for kennung, s in k["scheiben"].items():
            if not s.get("kalt") or s.get("veraltet") or s.get("abgegeben"):
                continue
            if jetzt - _iso_zu_s(s.get("kalt", "")) < ABGEBEN_WARTEN_S:
                continue
            frisch = [g for g, h in s.get("halter", {}).items() if isinstance(h, dict) and jetzt - _iso_zu_s(h.get("stichprobe", "")) < KALT_STICHPROBE_S
                      and g in self._halter_aktiv(k, s)]
            if len(frisch) < KOPIEN:
                continue
            quellen = [str(q) for q in s.get("quellen", [])]
            if any(self.speicher._pfad(q).is_file() for q in quellen) or not all(wi.hat(q) for q in quellen):
                continue
            ziel = self.pfad(kennung)
            try:
                if ziel.is_file():
                    ziel.unlink()
            except OSError:
                continue
            s["abgegeben"] = _jetzt_iso(jetzt)
            n += 1
        return n

    @_gesperrt
    def kalt_liste(self) -> dict[str, str]:
        k = self._karte()
        gesperrt = set(k.get("gesperrt", []))
        return {q: kennung for kennung, s in k["scheiben"].items() if s.get("kalt") and not s.get("veraltet") for q in s.get("quellen", []) if q not in gesperrt}

    @_gesperrt
    def kalt_lesen(self, quelle: str) -> bytes | None:
        k = self._karte()
        kennung = k["quellen"].get(str(quelle))
        if not kennung or quelle in k.get("gesperrt", []):
            return None
        try:
            with zipfile.ZipFile(self.pfad(kennung)) as z:
                return z.read(f"quellen/{quelle}.json")
        except (OSError, KeyError, zipfile.BadZipFile):
            return None

    @_gesperrt
    def sperren(self, quelle: str) -> bool:
        k = self._karte()
        if str(quelle) not in k["quellen"]:
            return False
        if quelle not in k["gesperrt"]:
            k["gesperrt"].append(str(quelle))
            self._schreiben(k)
            self._log(f"SCHEIBE Quelle {quelle} gesperrt")
        return True

    @_gesperrt
    def auspacken(self, kennung: str) -> int:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        if s is None:
            raise ScheibenError("SCHEIBE_UNBEKANNT", "diese Scheibe gibt es nicht")
        if not self.pfad(kennung).is_file():
            s["zurueck"] = True
            self._schreiben(k)
            raise ScheibenError("SCHEIBE_BEI_HALTERN", "diese Scheibe liegt gerade nur bei den Haltern; sie ist angefordert und kommt mit der nächsten Stichprobe zurück")
        m = scheibe_lesen(self.pfad(kennung))
        n = 0
        with zipfile.ZipFile(self.pfad(kennung)) as z:
            for e in m.get("quellen", []):
                p = self.speicher._pfad(str(e.get("kennung")))
                if not p.is_file():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(z.read(str(e.get("datei"))))
                    n += 1
        s.pop("kalt", None)
        s.pop("zurueck", None)
        self._schreiben(k)
        if hasattr(self.speicher, "abgleichen"):
            self.speicher.abgleichen()
        return n


    @_gesperrt
    def geraet_melden(self, kennung: str, limit_mb: int | None, frei_mb: int | None) -> None:
        if limit_mb is None and frei_mb is None:
            return
        k = self._karte()
        e = k["geraete"].setdefault(str(kennung), {})
        if limit_mb is not None:
            e["limit_mb"] = max(0, int(limit_mb))
        if frei_mb is not None:
            e["frei_mb"] = max(0, int(frei_mb))
        e["zuletzt"] = _jetzt_iso(self._jetzt())
        self._schreiben(k, spaeter=True)

    def _gesehen(self, k: dict, geraet: str) -> bool:
        return self._jetzt() - _iso_zu_s(k["geraete"].get(geraet, {}).get("zuletzt", "")) < GESEHEN_S

    def _halter_aktiv(self, k: dict, s: dict) -> list[str]:
        return [g for g in s.get("halter", {}) if self._gesehen(k, g)]

    def _abgelaufene(self, k: dict) -> None:
        jetzt = self._jetzt()
        for kennung, s in k["scheiben"].items():
            for g, o in list(s.get("offen", {}).items()):
                if jetzt - _iso_zu_s(o.get("seit", "")) < AUFTRAG_FRIST_S:
                    continue
                s["offen"].pop(g, None)
                if o.get("art") == LIEFERN_ART:
                    self._verstoss(k, kennung, g, "nicht geliefert")

    def _verstoss(self, k: dict, kennung: str, geraet: str, grund: str) -> None:
        e = k["geraete"].setdefault(geraet, {})
        e["verstoesse"] = int(e.get("verstoesse", 0)) + 1
        self._log(f"SCHEIBE {kennung}: {geraet} {grund} ({e['verstoesse']}. Mal)")
        if e["verstoesse"] >= VERSTOESSE_RAUS:
            for s in k["scheiben"].values():
                s.get("halter", {}).pop(geraet, None)
            e["verstoesse"] = 0
            self._log(f"SCHEIBE {geraet} als Halter gestrichen; Scheiben werden nachkopiert")

    @_gesperrt
    def naechster_auftrag(self, geraet: str, frei_mb: int | None = None) -> dict | None:
        k = self._karte()
        self._abgelaufene(k)
        jetzt = self._jetzt()
        e = k["geraete"].setdefault(str(geraet), {})
        if frei_mb is not None:
            e["frei_mb"] = max(0, int(frei_mb))
        e["zuletzt"] = _jetzt_iso(jetzt)
        if jetzt - _iso_zu_s(e.get("auftrag_zuletzt", "")) < TAKT_JE_GERAET_S:
            self._schreiben(k, spaeter=True)
            return None
        antwort = None
        def _faellig(s: dict) -> bool:
            if s.get("art") == WIKI_ART:
                return bool(s.get("zurueck"))
            if s.get("abgegeben") and (len(self._halter_aktiv(k, s)) < KOPIEN or s.get("zurueck")):
                return True
            return jetzt - _iso_zu_s(s.get("stichprobe", "")) >= STICHPROBE_S
        darf = (lambda z: True) if self.bremse is None else (lambda z: self.bremse.darf(geraet, z))
        faellig = sorted((s for kennung, s in k["scheiben"].items() if geraet in s.get("halter", {}) and not s.get("veraltet")
                          and _faellig(s) and not any(o.get("art") == LIEFERN_ART for o in s.get("offen", {}).values()) and darf(("liefern", kennung))),
                         key=lambda s: (0 if s.get("abgegeben") else 1, s.get("stichprobe", "")))
        for s in faellig:
            kennung = next(kk for kk, ss in k["scheiben"].items() if ss is s)
            s.setdefault("offen", {})[geraet] = {"art": LIEFERN_ART, "seit": _jetzt_iso(jetzt)}
            antwort = {"auftrag": f"liefern-{kennung}", "art": LIEFERN_ART, "scheibe": kennung, "bytes": s["bytes"], "sha256": s["sha256"], "frist_s": AUFTRAG_FRIST_S}
            break
        if antwort is None:
            frei = int(e.get("frei_mb", 0) or 0) * 1024 * 1024
            offen_fuer_geraet = any(g == geraet for s in k["scheiben"].values() for g in s.get("offen", {}))
            if not offen_fuer_geraet:
                kandidaten = [(len(self._halter_aktiv(k, s)) + len(s.get("offen", {})), kennung, s) for kennung, s in k["scheiben"].items()
                              if not s.get("veraltet") and s.get("art") != WIKI_ART and geraet not in s.get("halter", {}) and geraet not in s.get("offen", {}) and s["bytes"] <= frei
                              and self.pfad(kennung).is_file() and darf(("halten", kennung))]
                kandidaten = [c for c in kandidaten if c[0] < KOPIEN]
                if kandidaten:
                    kandidaten.sort(key=lambda c: (c[0], c[1]))
                    _, kennung, s = kandidaten[0]
                    s.setdefault("offen", {})[geraet] = {"art": HALTEN_ART, "seit": _jetzt_iso(jetzt)}
                    antwort = {"auftrag": f"halten-{kennung}", "art": HALTEN_ART, "scheibe": kennung, "bytes": s["bytes"], "sha256": s["sha256"], "frist_s": AUFTRAG_FRIST_S}
        if antwort is not None:
            e["auftrag_zuletzt"] = _jetzt_iso(jetzt)
            if self.bremse is not None:
                self.bremse.vergeben(geraet, ("liefern" if antwort["art"] == LIEFERN_ART else "halten", antwort["scheibe"]))
        self._schreiben(k, spaeter=antwort is None)
        return antwort

    @_gesperrt
    def bestaetigen(self, geraet: str, kennung: str, sha256: str) -> dict:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        if s is None:
            raise ScheibenError("SCHEIBE_UNBEKANNT", "diese Scheibe gibt es nicht")
        if str(sha256).lower() != s["sha256"]:
            s.get("offen", {}).pop(geraet, None)
            self._schreiben(k)
            raise ScheibenError("SCHEIBE_PRUEFSUMME", "die Prüfsumme passt nicht; die Scheibe wird nicht gezählt")
        s.get("offen", {}).pop(geraet, None)
        if self.bremse is not None:
            self.bremse.erledigt(geraet, ("halten", str(kennung)))
        neu = geraet not in s["halter"]
        s["halter"][geraet] = {"seit": _jetzt_iso(self._jetzt()), "stichprobe": ""}
        self._schreiben(k)
        credits = CREDITS_JE_SCHEIBE if neu else 0
        if credits and self.verteiler is not None:
            self.verteiler.credits_gutschreiben(geraet, credits, scheiben=1)
        self._log(f"SCHEIBE {kennung} bestätigt von {geraet} ({len(s['halter'])} Halter)")
        return {"scheibe": kennung, "halter": len(s["halter"]), "credits": credits}

    @_gesperrt
    def abgegeben(self, geraet: str, kennung: str) -> dict:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        if s is not None:
            s.get("halter", {}).pop(geraet, None)
            s.get("offen", {}).pop(geraet, None)
            self._schreiben(k)
        return {"scheibe": kennung, "halter": len(s["halter"]) if s else 0}

    @_gesperrt
    def geliefert(self, geraet: str, kennung: str, datei: Path) -> dict:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        try:
            if s is None:
                raise ScheibenError("SCHEIBE_UNBEKANNT", "diese Scheibe gibt es nicht")
            if geraet not in s.get("halter", {}):
                raise ScheibenError("SCHEIBE_KEIN_HALTER", "dieses Gerät hält diese Scheibe nicht")
            s.get("offen", {}).pop(geraet, None)
            sha = pruefsumme(datei)
            if sha != s["sha256"]:
                s["halter"].pop(geraet, None)
                self._verstoss(k, kennung, geraet, "falsche Bytes geliefert")
                self._schreiben(k)
                raise ScheibenError("SCHEIBE_PRUEFSUMME", "die gelieferte Scheibe passt nicht zur Prüfsumme; das Gerät gilt nicht mehr als Halter")
            zurueckgeholt = False
            ziel = self.pfad(kennung)
            if not ziel.exists() or pruefsumme(ziel) != s["sha256"]:
                os.replace(datei, ziel)
                zurueckgeholt = True
                s.pop("abgegeben", None)
                s.pop("zurueck", None)
                if s.get("art") == WIKI_ART:
                    s["am_server_seit"] = _jetzt_iso(self._jetzt())
                self._log(f"SCHEIBE {kennung} vom Gerät {geraet} zurückgeholt (Kopie am Server fehlte, war abgegeben oder beschädigt)")
            if self.bremse is not None:
                self.bremse.erledigt(geraet, ("liefern", str(kennung)))
            jetzt = _jetzt_iso(self._jetzt())
            s["stichprobe"] = jetzt
            s["halter"][geraet]["stichprobe"] = jetzt
            self._schreiben(k)
            if self.verteiler is not None:
                self.verteiler.credits_gutschreiben(geraet, CREDITS_JE_STICHPROBE, stichproben=1)
            self._log(f"SCHEIBE {kennung} Stichprobe von {geraet} in Ordnung")
            return {"scheibe": kennung, "zurueckgeholt": zurueckgeholt, "credits": CREDITS_JE_STICHPROBE}
        finally:
            try:
                if datei.exists():
                    datei.unlink()
            except OSError:
                pass

    @_gesperrt
    def geraet_vergessen(self, geraet: str) -> None:
        k = self._karte()
        for s in k["scheiben"].values():
            s.get("halter", {}).pop(geraet, None)
            s.get("offen", {}).pop(geraet, None)
        k["geraete"].pop(geraet, None)
        self._schreiben(k)

    @_gesperrt
    def veraltet_pruefen(self) -> int:
        k = self._karte()
        vorhanden = {q.kennung for q, _ in self.speicher.alle(auch_ungeprueft=True)}
        n = 0
        for s in k["scheiben"].values():
            weg = sum(1 for q in s.get("quellen", []) if q not in vorhanden)
            if s.get("quellen") and weg * 2 > len(s["quellen"]) and not s.get("veraltet"):
                s["veraltet"] = True
                n += 1
        if n:
            self._schreiben(k)
        return n

    @_gesperrt
    def zurueckziehen(self, kennung: str) -> list[str]:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        if s is None:
            return []
        if s.get("kalt"):
            self.auspacken(str(kennung))
            k = self._karte()
            s = k["scheiben"][str(kennung)]
        s["veraltet"] = True
        quellen = [str(q) for q in s.get("quellen", [])]
        for q in quellen:
            if k["quellen"].get(q) == str(kennung):
                k["quellen"].pop(q, None)
        self._schreiben(k)
        self._log(f"SCHEIBE {kennung} zurückgezogen ({len(quellen)} Quellen), die Halter löschen sie")
        return quellen

    @_gesperrt
    def veraltet_bei(self, geraet: str) -> list[str]:
        k = self._karte()
        return sorted(kennung for kennung, s in k["scheiben"].items() if s.get("veraltet") and geraet in s.get("halter", {}))

    @_gesperrt
    def verschwundene_streichen(self) -> int:
        k = self._karte()
        jetzt = self._jetzt()
        weg = {g for g, e in k["geraete"].items() if jetzt - _iso_zu_s(e.get("zuletzt", "")) >= VERGESSEN_S}
        n = 0
        for kennung, s in k["scheiben"].items():
            if not (s.get("veraltet") or self.pfad(kennung).is_file()):
                continue
            for g in [g for g in s.get("halter", {}) if g in weg]:
                s["halter"].pop(g, None)
                s.get("offen", {}).pop(g, None)
                n += 1
        if n:
            self._schreiben(k)
            self._log(f"SCHEIBE {n} Halter-Einträge von Geräten gestrichen, die {VERGESSEN_S // 86400} Tage nicht gesehen wurden")
        return n

    @_gesperrt
    def veraltet_entsorgen(self) -> int:
        k = self._karte()
        weg = [kennung for kennung, s in k["scheiben"].items() if s.get("veraltet") and not s.get("halter") and not s.get("offen")]
        for kennung in weg:
            try:
                self.pfad(kennung).unlink(missing_ok=True)
            except OSError:
                continue
            k["scheiben"].pop(kennung, None)
            for q in [q for q, s in k["quellen"].items() if s == kennung]:
                k["quellen"].pop(q, None)
        if weg:
            self._schreiben(k)
            self._log(f"SCHEIBE {len(weg)} veraltete Scheiben ohne Halter gelöscht")
        return len(weg)

    @_gesperrt
    def geraet_scheiben(self, geraet: str) -> list[str]:
        k = self._karte()
        return sorted(kennung for kennung, s in k["scheiben"].items() if geraet in s.get("halter", {}) and not s.get("veraltet"))


    def _wiki_am_server(self, k: dict) -> int:
        return sum(s["bytes"] for kk, s in k["scheiben"].items() if s.get("art") == WIKI_ART and self.pfad(kk).is_file())

    def _wiki_brauchen(self, k: dict, modell: str, ausser: str = "") -> list[str]:
        jetzt = self._jetzt()
        return [g for g, e in k.get("wiki_gesucht", {}).items()
                if g != ausser and isinstance(e, dict) and e.get("modell") == modell and jetzt - _iso_zu_s(e.get("zeit", "")) < WIKI_GESUCHT_S]

    @_gesperrt
    def wiki_stand(self, geraet: str, *, ausgabe: str, modell: str, brauche: bool = False, biete: bool = False) -> dict:
        k = self._karte()
        if not isinstance(k.get("wiki_gesucht"), dict):
            k["wiki_gesucht"] = {}
        modell, ausgabe = str(modell)[:64], str(ausgabe)[:8]
        geaendert = False
        if brauche:
            k["wiki_gesucht"][str(geraet)] = {"modell": modell, "ausgabe": ausgabe, "zeit": _jetzt_iso(self._jetzt())}
            geaendert = True
        liste = []
        for kk, s in sorted(k["scheiben"].items(), key=lambda x: (x[1].get("wiki", {}).get("ausgabe", ""), x[1].get("wiki", {}).get("nr", 0))):
            w = s.get("wiki") or {}
            if s.get("art") != WIKI_ART or w.get("modell") != modell:
                continue
            am = self.pfad(kk).is_file()
            geholt = str(geraet) in s.get("geholt", {})
            liste.append({"kennung": kk, "bytes": s["bytes"], "sha256": s["sha256"], "ausgabe": w.get("ausgabe", ""), "nr": w.get("nr", 0),
                          "anzahl": w.get("anzahl", 0), "am_server": am, "geholt": geholt})
        if brauche:
            platz = WIKI_TRANSIT_BYTES - self._wiki_am_server(k)
            unterwegs = sum(1 for e in liste if not e["am_server"] and k["scheiben"][e["kennung"]].get("zurueck"))
            for e in liste:
                s = k["scheiben"][e["kennung"]]
                if e["am_server"] or e["geholt"] or s.get("zurueck") or not s.get("halter"):
                    continue
                if unterwegs >= WIKI_ZURUECK_HOECHSTENS or s["bytes"] > platz:
                    break
                s["zurueck"] = True
                unterwegs += 1
                platz -= s["bytes"]
                geaendert = True
        if geaendert:
            self._schreiben(k)
        return {"scheiben": liste, "gesucht": bool(self._wiki_brauchen(k, modell, ausser=str(geraet))),
                "platz": max(0, WIKI_TRANSIT_BYTES - self._wiki_am_server(k)), "je_scheibe": WIKI_JE_SCHEIBE,
                "nr_da": sorted(e["nr"] for e in liste if e["ausgabe"] == ausgabe)}

    def wiki_annehmen(self, geraet: str, datei: Path) -> dict:
        try:
            m, _paare = wiki_lesen(datei)
            del _paare
        except BaseException:
            try:
                datei.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return self._wiki_eintragen(geraet, datei, m)

    @_gesperrt
    def _wiki_eintragen(self, geraet: str, datei: Path, m: dict) -> dict:
        try:
            k = self._karte()
            modell, ausgabe, nr = str(m.get("modell", ""))[:64], str(m.get("ausgabe", ""))[:8], int(m.get("nr", -1))
            if nr < 0 or not modell or len(ausgabe) != 8:
                raise ScheibenError("WIKI_FORMAT", "Ausgabe, Modell oder Nummer fehlt")
            if not self._wiki_brauchen(k, modell, ausser=str(geraet)):
                raise ScheibenError("WIKI_NICHT_GESUCHT", "gerade braucht kein anderes Gerät diese Vektoren")
            if any((s.get("wiki") or {}).get("modell") == modell and (s.get("wiki") or {}).get("ausgabe") == ausgabe and (s.get("wiki") or {}).get("nr") == nr
                   for s in k["scheiben"].values() if s.get("art") == WIKI_ART):
                raise ScheibenError("WIKI_DA", "diese Scheibe gibt es schon")
            groesse = datei.stat().st_size
            if self._wiki_am_server(k) + groesse > WIKI_TRANSIT_BYTES:
                raise ScheibenError("WIKI_VOLL", "die Durchreiche am Server ist gerade voll; später wieder")
            self._wiki_bremse(k, str(geraet))
            sha = pruefsumme(datei)
            kennung = sha[:16]
            if kennung in k["scheiben"]:
                raise ScheibenError("WIKI_DA", "diese Scheibe gibt es schon")
            self.dir.mkdir(parents=True, exist_ok=True)
            os.replace(datei, self.pfad(kennung))
            jetzt = _jetzt_iso(self._jetzt())
            k["scheiben"][kennung] = {"art": WIKI_ART, "bytes": groesse, "sha256": sha, "quellen": [], "erstellt": jetzt, "stichprobe": jetzt,
                                      "wiki": {"modell": modell, "ausgabe": ausgabe, "nr": nr, "anzahl": int(m["anzahl"]), "von": m["von"], "bis": m["bis"]},
                                      "halter": {str(geraet): {"seit": jetzt, "stichprobe": jetzt}}, "offen": {}, "geholt": {}, "am_server_seit": jetzt,
                                      "anbieter": str(geraet)}
            if not isinstance(k.get("wiki_zuletzt"), dict):
                k["wiki_zuletzt"] = {}
            k["wiki_zuletzt"][str(geraet)] = jetzt
            self._schreiben(k)
        finally:
            try:
                if datei.exists():
                    datei.unlink()
            except OSError:
                pass
        if self.verteiler is not None:
            self.verteiler.credits_gutschreiben(str(geraet), CREDITS_JE_SCHEIBE, scheiben=1)
        self._log(f"SCHEIBE {kennung} Wikipedia-Vektoren {ausgabe} Nr. {nr} von {geraet} angenommen ({m['anzahl']} Vektoren, {groesse} Bytes)")
        return {"scheibe": kennung, "credits": CREDITS_JE_SCHEIBE}

    def _wiki_bremse(self, k: dict, geraet: str) -> None:
        jetzt = self._jetzt()
        e = (k.get("wiki_abgelehnt") or {}).get(geraet) or {}
        if _iso_zu_s(e.get("gesperrt_bis", "")) > jetzt:
            raise ScheibenError("WIKI_GESPERRT", "von diesem Gerät nimmt der Server gerade keine Vektoren an")
        if jetzt - _iso_zu_s((k.get("wiki_zuletzt") or {}).get(geraet, "")) < WIKI_JE_GERAET_S:
            raise ScheibenError("WIKI_BREMSE", "höchstens eine Scheibe je Minute; gleich wieder")
        if sum(1 for kk, s in k["scheiben"].items() if s.get("art") == WIKI_ART and s.get("anbieter") == geraet and self.pfad(kk).is_file()) >= WIKI_JE_GERAET_ZUGLEICH:
            raise ScheibenError("WIKI_BREMSE", "von diesem Gerät liegen schon genug Scheiben in der Durchreiche; später wieder")

    @_gesperrt
    def wiki_geholt(self, geraet: str, kennung: str, *, ok: bool = True, grund: str = "") -> dict:
        k = self._karte()
        s = k["scheiben"].get(str(kennung))
        if s is None or s.get("art") != WIKI_ART:
            raise ScheibenError("SCHEIBE_UNBEKANNT", "diese Scheibe gibt es nicht")
        geraet = str(geraet)
        if ok:
            s.setdefault("geholt", {})[geraet] = _jetzt_iso(self._jetzt())
            self._schreiben(k)
            self._log(f"SCHEIBE {kennung} Wikipedia-Vektoren von {geraet} übernommen")
            return {"scheibe": kennung}
        anbieter = str(s.get("anbieter") or next(iter(s.get("halter") or {}), ""))
        if anbieter == geraet or geraet in s.get("halter", {}):
            raise ScheibenError("WIKI_EIGENE", "die eigene Scheibe kann ein Gerät nicht ablehnen")
        if not any(g == geraet for g in self._wiki_brauchen(k, (s.get("wiki") or {}).get("modell", ""))):
            raise ScheibenError("WIKI_NICHT_GESUCHT", "nur ein Gerät, das diese Vektoren gesucht hat, kann eine Scheibe ablehnen")
        k["scheiben"].pop(str(kennung), None)
        try:
            _weg(self.pfad(kennung))
        except OSError as exc:
            self._log(f"FEHLER scheibe {kennung} nach Ablehnen nicht gelöscht: {type(exc).__name__}")
        jetzt = _jetzt_iso(self._jetzt())
        if not isinstance(k.get("wiki_abgelehnt"), dict):
            k["wiki_abgelehnt"] = {}
        e = k["wiki_abgelehnt"].setdefault(anbieter, {})
        e["anzahl"] = int(e.get("anzahl", 0)) + 1
        e["zuletzt"] = jetzt
        gesperrt = False
        if e["anzahl"] >= WIKI_ABGELEHNT_SPERRE:
            e["gesperrt_bis"] = _jetzt_iso(self._jetzt() + WIKI_SPERRE_S)
            e["anzahl"] = 0
            gesperrt = True
        self._schreiben(k)
        if anbieter and self.verteiler is not None:
            self.verteiler.credits_gutschreiben(anbieter, -CREDITS_JE_SCHEIBE, scheiben=-1)
        grund = re.sub(r"[^0-9A-Za-z_]", "", str(grund))[:32]
        self._log(f"SCHEIBE {kennung} Wikipedia-Vektoren von {geraet} abgelehnt ({grund or 'ohne Grund'}); Anbieter {anbieter} verliert den Credit"
                  + ("; 30 Tage keine Vektoren mehr von ihm" if gesperrt else ""))
        return {"scheibe": kennung, "entfernt": True}

    @_gesperrt
    def wiki_aufraeumen(self) -> int:
        k = self._karte()
        jetzt = self._jetzt()
        n = 0
        for kk, s in k["scheiben"].items():
            if s.get("art") != WIKI_ART or not self.pfad(kk).is_file():
                continue
            modell = (s.get("wiki") or {}).get("modell", "")
            offen = [g for g in self._wiki_brauchen(k, modell) if g not in s.get("geholt", {}) and g not in s.get("halter", {})]
            seit = _iso_zu_s(s.get("am_server_seit") or s.get("erstellt", ""))
            if offen and jetzt - seit < WIKI_TRANSIT_S:
                continue
            if not s.get("halter"):
                continue
            try:
                _weg(self.pfad(kk))
            except OSError:
                continue
            s["abgegeben"] = _jetzt_iso(jetzt)
            s.pop("zurueck", None)
            n += 1
        gesucht = k.get("wiki_gesucht") if isinstance(k.get("wiki_gesucht"), dict) else {}
        alt = [g for g, e in gesucht.items() if not isinstance(e, dict) or jetzt - _iso_zu_s(e.get("zeit", "")) >= WIKI_GESUCHT_S]
        for g in alt:
            gesucht.pop(g, None)
        if n or alt:
            self._schreiben(k)
            if n:
                self._log(f"SCHEIBE Durchreiche: {n} Scheiben mit Wikipedia-Vektoren vom Server genommen, sie liegen bei ihren Haltern")
        return n


    @_gesperrt
    def stand(self) -> dict:
        k = self._karte()
        scheiben = [s for s in k["scheiben"].values() if not s.get("veraltet") and s.get("art") != WIKI_ART]
        wiki = [s for s in k["scheiben"].values() if s.get("art") == WIKI_ART]
        kopien = [len(self._halter_aktiv(k, s)) for s in scheiben]
        return {"anzahl": len(scheiben), "mb": round(sum(s["bytes"] for s in scheiben) / (1024 * 1024), 1), "quellen": sum(len(s.get("quellen", [])) for s in scheiben),
                "dreifach": sum(1 for n in kopien if n >= KOPIEN), "ohne_halter": sum(1 for n in kopien if n == 0), "kopien_ziel": KOPIEN,
                "halter": len({g for s in scheiben for g in self._halter_aktiv(k, s)}), "stichproben_heute": sum(1 for s in scheiben if s.get("stichprobe", "")[:10] == _jetzt_iso(self._jetzt())[:10]),
                "kalt": sum(1 for s in scheiben if s.get("kalt")), "kalte_quellen": sum(len(s.get("quellen", [])) for s in scheiben if s.get("kalt")),
                "abgegeben": sum(1 for s in scheiben if s.get("abgegeben")),
                "wiki_vektoren": len(wiki), "wiki_vektoren_am_server": sum(1 for kk, s in k["scheiben"].items() if s.get("art") == WIKI_ART and self.pfad(kk).is_file())}

    @_gesperrt
    def landkarte(self) -> dict:
        k = self._karte()
        namen = {g["kennung"]: g["name"] for g in (self.verteiler.geraete() if self.verteiler is not None else [])}
        return {"scheiben": [{"kennung": kennung, "art": s.get("art", "wissen"), "bytes": s["bytes"], "quellen": len(s.get("quellen", [])), "erstellt": s.get("erstellt", ""), "stichprobe": s.get("stichprobe", ""),
                              "veraltet": bool(s.get("veraltet")), "halter": [{"kennung": g, "name": namen.get(g, g), "seit": h.get("seit", ""), "stichprobe": h.get("stichprobe", ""),
                                                                            "aktiv": self._gesehen(k, g)} for g, h in s.get("halter", {}).items()],
                              "offen": list(s.get("offen", {}).keys())} for kennung, s in sorted(k["scheiben"].items())],
                "geraete": [{"kennung": g, "name": namen.get(g, g), **{kk: vv for kk, vv in e.items()}} for g, e in sorted(k["geraete"].items())], **self.stand()}


def stand_leer() -> dict:
    return {"anzahl": 0, "mb": 0.0, "quellen": 0, "dreifach": 0, "ohne_halter": 0, "kopien_ziel": KOPIEN, "halter": 0, "stichproben_heute": 0, "kalt": 0, "kalte_quellen": 0, "abgegeben": 0, "wiki_vektoren": 0, "wiki_vektoren_am_server": 0}


__all__ = ["Scheiben", "ScheibenError", "scheibe_lesen", "pruefsumme", "HALTEN_ART", "LIEFERN_ART", "KOPIEN", "FORMAT", "DIRNAME", "MAX_SCHEIBE_BYTES", "stand_leer",
           "WIKI_ART", "WIKI_JE_SCHEIBE", "WIKI_TRANSIT_BYTES", "wiki_packen", "wiki_lesen"]
