# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import struct
import threading
import time
from pathlib import Path

import sicher_schreiben
import verteiler
import wissen
import wortindex

FORMAT = 1
DIRNAME = "gemeinschaft"
STAND_DATEI = "stand.json"
BAU_ABSTAND_S = 300
HOLEN_ABSTAND_S = 600
JE_ANFRAGE = 200
ANFRAGE_MAX_BYTES = 64 * 1024 * 1024
PAKET_MAX_BYTES = 16 * 1024 * 1024
AENDERUNGEN_MERKEN = 2000
ALTE_DATEIEN_S = 3600
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SCHLUESSEL = re.compile(r"^[qva]:[0-9A-Za-z_.-]{1,80}$")
_EIMER = re.compile(r"^[0-9a-f]{2}$")


def _atomar(pfad: Path, daten: bytes) -> None:
    sicher_schreiben.roh(pfad, daten)


def _roh(daten: dict) -> bytes:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pakete_packen(liste: list[tuple[str, bytes]]) -> bytes:
    return b"".join(sha.encode("ascii") + struct.pack(">I", len(b)) + b for sha, b in liste)


def pakete_auspacken(daten: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    i = 0
    while i < len(daten):
        if i + 68 > len(daten):
            raise ValueError("die Pakete kamen unvollständig an")
        sha = daten[i:i + 64].decode("ascii", "replace")
        (n,) = struct.unpack(">I", daten[i + 64:i + 68])
        if not _SHA.match(sha) or n > PAKET_MAX_BYTES or i + 68 + n > len(daten):
            raise ValueError("die Pakete kamen beschädigt an")
        out[sha] = daten[i + 68:i + 68 + n]
        i += 68 + n
    return out


class Pakete:

    def __init__(self, ordner, speicher, vt: verteiler.Verteiler, sperre, antworten=None) -> None:
        self.dir = Path(ordner) / DIRNAME
        self.speicher, self.vt, self.sperre = speicher, vt, sperre
        self.antworten = antworten
        self._lock = threading.Lock()
        self._sig: dict[str, str] = {}
        self._objekte: dict[str, str] = {}
        self.version = 0
        self._aenderungen: list[tuple[int, dict[str, str | None]]] = []
        self._geladen = False

    def _laden(self) -> None:
        if self._geladen:
            return
        self._geladen = True
        d = sicher_schreiben.json_laden(self.dir / STAND_DATEI, {}, art=dict)
        if d.get("format") == FORMAT and isinstance(d.get("objekte"), dict):
            self.version = int(d.get("version", 0))
            self._objekte = {k: v for k, v in d["objekte"].items() if _SCHLUESSEL.match(k) and _SHA.match(str(v)) and self.datei(v) is not None}
            self._sig = {k: v for k, v in (d.get("sig") or {}).items() if k in self._objekte}

    def stand(self, seit: int | None = None) -> dict | None:
        with self._lock:
            self._laden()
            if not self.version:
                return None
            if seit is not None and 0 < seit <= self.version:
                bekannt_ab = self._aenderungen[0][0] - 1 if self._aenderungen else self.version
                if seit >= bekannt_ab:
                    aend: dict[str, str | None] = {}
                    for v, a in self._aenderungen:
                        if v > seit:
                            aend.update(a)
                    return {"format": FORMAT, "version": self.version, "seit": seit, "aenderungen": aend}
            return {"format": FORMAT, "version": self.version, "objekte": dict(self._objekte)}

    def datei(self, sha: str) -> Path | None:
        if not _SHA.match(str(sha)):
            return None
        p = self.dir / f"{sha}.json.gz"
        return p if p.is_file() else None

    def bauen(self) -> int:
        wi = getattr(self.speicher, "wortindex", None)
        if wi is None:
            return 0
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._laden()
        with self.sperre:
            index = self.vt._im_index()
            vertieft = self.vt._alle_vertieft()
            texte = self.vt._texte()
            marken = wi.marken()
            idx_mt = {k: c[0] for k, c in self.vt._index_cache.items()}
            vf_mt = {k: c[0] for k, c in self.vt._vertieft_cache.items()}
        je_quelle_v: dict[str, dict] = {}
        for s, e in index.items():
            je_quelle_v.setdefault(s.rsplit(":", 1)[0], {})[s] = e
        je_quelle_t: dict[str, dict] = {}
        for s, e in vertieft.items():
            je_quelle_t.setdefault(s.rsplit(":", 1)[0], {})[s] = e
        neu: dict[str, str | None] = {}
        gesehen: set[str] = set()
        for k in set(marken) | set(je_quelle_v) | set(je_quelle_t):
            for art, sig in (("q", f"{marken.get(k)}|{idx_mt.get(k)}"), ("v", f"{marken.get(k)}|{vf_mt.get(k)}")):
                schl = f"{art}:{k}"
                if not _SCHLUESSEL.match(schl):
                    continue
                gesehen.add(schl)
                if self._sig.get(schl) == sig and schl in self._objekte:
                    continue
                daten = self._quelle(wi, k, je_quelle_v.get(k, {}), texte) if art == "q" else self._vorbereitet(k, je_quelle_t.get(k, {}), texte)
                self._sig[schl] = sig
                if daten is None:
                    if schl in self._objekte:
                        neu[schl] = None
                    continue
                roh = _roh(daten)
                sha = hashlib.sha256(roh).hexdigest()
                if self._objekte.get(schl) != sha:
                    if self.datei(sha) is None:
                        _atomar(self.dir / f"{sha}.json.gz", gzip.compress(roh, compresslevel=6, mtime=0))
                    neu[schl] = sha
        if self.antworten is not None:
            marken = self.antworten.fuer_pcs_marken()
            geaendert = {e for e, m in marken.items() if _EIMER.match(e) and not (self._sig.get(f"a:{e}") == m and f"a:{e}" in self._objekte)}
            gesehen |= {f"a:{e}" for e in marken if _EIMER.match(e) and e not in geaendert and f"a:{e}" in self._objekte}
            inhalte = self.antworten.fuer_pcs(eimer=geaendert) if geaendert else {}
            for e in geaendert:
                schl, inhalt = f"a:{e}", inhalte.get(e) or {}
                self._sig[schl] = marken[e]
                if not inhalt:
                    continue
                gesehen.add(schl)
                roh = _roh({"format": FORMAT, "art": "a", "kennung": e, "antworten": inhalt})
                sha = hashlib.sha256(roh).hexdigest()
                if self._objekte.get(schl) != sha:
                    if self.datei(sha) is None:
                        _atomar(self.dir / f"{sha}.json.gz", gzip.compress(roh, compresslevel=6, mtime=0))
                    neu[schl] = sha
        for schl in [s for s in self._objekte if s not in gesehen]:
            neu[schl] = None
            self._sig.pop(schl, None)
        if neu or not self.version:
            with self._lock:
                for schl, sha in neu.items():
                    if sha is None:
                        self._objekte.pop(schl, None)
                    else:
                        self._objekte[schl] = sha
                self.version += 1
                self._aenderungen.append((self.version, neu))
                self._aenderungen = self._aenderungen[-AENDERUNGEN_MERKEN:]
                _atomar(self.dir / STAND_DATEI, json.dumps({"format": FORMAT, "version": self.version, "erzeugt": wissen._jetzt(),
                                                           "objekte": self._objekte, "sig": self._sig}, ensure_ascii=False).encode("utf-8"))
                behalten = set(self._objekte.values())
            jetzt = time.time()
            for p in self.dir.glob("*.json.gz"):
                try:
                    if p.name[:64] not in behalten and jetzt - p.stat().st_mtime > ALTE_DATEIEN_S:
                        p.unlink(missing_ok=True)
                except OSError:
                    pass
        return len(neu)

    @staticmethod
    def _quelle(wi, kennung: str, vektoren: dict, texte: dict) -> dict | None:
        roh = [d for d in wi.roh_ausgeben([kennung]) if not d["privat"] and d["freigegeben"]]
        if not roh:
            return None
        vk = {s: {"hash": e.get("hash"), "s": e.get("s", 1.0), "vq": e.get("vq"), "sk": e.get("sk")}
              for s, e in vektoren.items() if (texte.get(s) or (None,))[0] == e.get("hash") and e.get("vq") and e.get("sk")}
        return {"format": FORMAT, "art": "q", "kennung": kennung, "quelle": roh[0], "vektoren": vk}

    @staticmethod
    def _vorbereitet(kennung: str, eintraege: dict, texte: dict) -> dict | None:
        out = {}
        for s, e in eintraege.items():
            if not isinstance(e, dict) or not e.get("geprueft") or (texte.get(s) or (None,))[0] != e.get("hash"):
                continue
            out[s] = {"hash": e.get("hash"), "geprueft": True,
                      "fragen": [{"frage": str(f.get("frage", "")), "antwort": str(f.get("antwort", ""))} for f in (e.get("fragen") or []) if isinstance(f, dict)]}
        return {"format": FORMAT, "art": "v", "kennung": kennung, "vertieft": out} if out else None


class Spiegel:

    def __init__(self, base_dir, gemeinschaft, protokoll=None) -> None:
        self.dir = Path(base_dir) / DIRNAME
        self._gemeinschaft = gemeinschaft if callable(gemeinschaft) else (lambda: gemeinschaft)
        self._log = protokoll or (lambda z: None)
        self._lock = threading.RLock()
        self._holen = threading.Lock()
        self._wi: wortindex.Wortindex | None = None
        self._objekte: dict[str, str] = {}
        self._vektoren: dict[str, dict[str, dict]] = {}
        self._verzeichnisse: dict[str, tuple[dict, dict]] = {}
        self._antworten: dict[str, dict] = {}
        self.version = 0
        self.vollstaendig = False
        self._such: tuple | None = None
        self.letzte_suche = ""
        self._geladen = False

    def bereit(self) -> bool:
        self._laden()
        return self.vollstaendig and self._wi is not None

    def _laden(self) -> None:
        with self._lock:
            if self._geladen:
                return
            self._geladen = True
            d = sicher_schreiben.json_laden(self.dir / STAND_DATEI, {}, art=dict)
            if d.get("format") != FORMAT or not isinstance(d.get("objekte"), dict):
                return
            try:
                self._wi = wortindex.Wortindex(self.dir / wortindex.DATEI)
            except Exception as exc:
                self._log(f"FEHLER gemeinschaftswissen öffnen: {type(exc).__name__}")
                return
            for schl, sha in d["objekte"].items():
                try:
                    roh = gzip.decompress((self.dir / f"{sha}.json.gz").read_bytes())
                    if hashlib.sha256(roh).hexdigest() != sha:
                        continue
                    self._im_speicher(schl, sha, json.loads(roh.decode("utf-8")), wortindex_auch=False)
                except (OSError, ValueError, EOFError):
                    continue
            self.version = int(d.get("version", 0))
            self.vollstaendig = bool(d.get("vollstaendig")) and set(self._objekte) == set(d["objekte"])

    def _im_speicher(self, schl: str, sha: str, daten: dict, *, wortindex_auch: bool) -> None:
        art, k = schl.split(":", 1)
        if daten.get("format") != FORMAT or daten.get("art") != art or daten.get("kennung") != k:
            raise ValueError(f"Paket {schl} passt nicht zur Liste")
        if art == "q":
            q = daten.get("quelle") or {}
            if q.get("privat") or not q.get("freigegeben") or str(q.get("kennung")) != k:
                raise ValueError(f"Paket {schl} enthält, was nicht hinaus darf")
            if wortindex_auch:
                self._wi.roh_aufnehmen([q], [k])
            vk = {}
            for s, e in (daten.get("vektoren") or {}).items():
                if not str(s).startswith(k + ":"):
                    continue
                e = dict(e)
                verteiler._eintrag_laden(e)
                vk[s] = e
            self._vektoren[k] = vk
        elif art == "a":
            if not _EIMER.match(k):
                raise ValueError(f"Paket {schl} passt nicht zur Liste")
            for nr in [n for n in self._antworten if n[:2] == k]:
                del self._antworten[nr]
            for nr, e in (daten.get("antworten") or {}).items():
                if isinstance(nr, str) and re.fullmatch(r"[0-9a-f]{32}", nr) and nr[:2] == k and isinstance(e, dict):
                    self._antworten[nr] = {"c": str(e.get("c", "")), "bis": float(e.get("bis", 0) or 0)}
        else:
            self._verzeichnisse[k] = verteiler.vertief_verzeichnis_bauen({s: e for s, e in (daten.get("vertieft") or {}).items() if str(s).startswith(k + ":")})
        self._objekte[schl] = sha
        self._such = None

    def _weg(self, schl: str) -> None:
        art, k = schl.split(":", 1)
        if art == "q":
            self._wi.roh_aufnehmen([], [k])
            self._vektoren.pop(k, None)
        elif art == "a":
            for nr in [n for n in self._antworten if n[:2] == k]:
                del self._antworten[nr]
        else:
            self._verzeichnisse.pop(k, None)
        alt = self._objekte.pop(schl, None)
        if alt and alt not in self._objekte.values():
            (self.dir / f"{alt}.json.gz").unlink(missing_ok=True)
        self._such = None

    def aktualisieren(self) -> int:
        if not self._holen.acquire(blocking=False):
            return 0
        try:
            self._laden()
            com = self._gemeinschaft()
            stand = com.gemeinschaft_stand(self.version if self.vollstaendig else None)
            if not isinstance(stand, dict) or stand.get("format") != FORMAT:
                self._log(f"INFO gemeinschaftswissen: Format {stand.get('format') if isinstance(stand, dict) else '?'} unbekannt, es sucht der Server")
                return 0
            if isinstance(stand.get("aenderungen"), dict) and stand.get("seit") == self.version and self.vollstaendig:
                ziel = dict(self._objekte)
                for schl, sha in stand["aenderungen"].items():
                    if sha is None:
                        ziel.pop(schl, None)
                    else:
                        ziel[schl] = sha
            elif isinstance(stand.get("objekte"), dict):
                ziel = dict(stand["objekte"])
            else:
                return 0
            ziel = {s: h for s, h in ziel.items() if _SCHLUESSEL.match(str(s)) and _SHA.match(str(h))}
            self.dir.mkdir(parents=True, exist_ok=True)
            n = 0
            with self._lock:
                if self._wi is None:
                    self._wi = wortindex.Wortindex(self.dir / wortindex.DATEI)
                for schl in [s for s in self._objekte if s not in ziel]:
                    self._weg(schl)
                    n += 1
            fehlt = [(s, h) for s, h in sorted(ziel.items()) if self._objekte.get(s) != h]
            for i in range(0, len(fehlt), JE_ANFRAGE):
                stueck = fehlt[i:i + JE_ANFRAGE]
                pakete = pakete_auspacken(com.gemeinschaft_pakete([h for _s, h in stueck], ANFRAGE_MAX_BYTES))
                for schl, sha in stueck:
                    gz = pakete.get(sha)
                    if gz is None:
                        raise ValueError(f"Paket {schl} fehlt in der Antwort")
                    roh = gzip.decompress(gz)
                    if hashlib.sha256(roh).hexdigest() != sha:
                        raise ValueError(f"Paket {schl} kam beschädigt an")
                    daten = json.loads(roh.decode("utf-8"))
                    with self._lock:
                        alt = self._objekte.get(schl)
                        self._im_speicher(schl, sha, daten, wortindex_auch=True)
                        _atomar(self.dir / f"{sha}.json.gz", gz)
                        if alt and alt != sha and alt not in self._objekte.values():
                            (self.dir / f"{alt}.json.gz").unlink(missing_ok=True)
                    n += 1
                self._stand_schreiben()
            with self._lock:
                self.version = int(stand.get("version", 0))
                self.vollstaendig = set(self._objekte) == set(ziel)
                self._stand_schreiben()
            if n:
                self._log(f"OK gemeinschaftswissen: {n} Pakete aufgenommen oder entfernt, Fassung {self.version}, {len(self._vektoren)} Quellen auf diesem Gerät")
            return n
        finally:
            self._holen.release()

    def _stand_schreiben(self) -> None:
        with self._lock:
            _atomar(self.dir / STAND_DATEI, json.dumps({"format": FORMAT, "version": self.version, "vollstaendig": self.vollstaendig,
                                                        "objekte": self._objekte}).encode("utf-8"))

    def antwort(self, nachrichten) -> dict | None:
        import antwortspeicher_basis
        vereinfacht = antwortspeicher_basis.frage_taugt(nachrichten)
        if not vereinfacht:
            return None
        schl = antwortspeicher_basis.schluessel(vereinfacht)
        self._laden()
        with self._lock:
            e = self._antworten.get(antwortspeicher_basis.pc_nummer(schl))
        return antwortspeicher_basis.pc_entpacken(schl, e) if e is not None else None

    def antworten_anzahl(self) -> int:
        self._laden()
        with self._lock:
            return len(self._antworten)


    def _suchlisten(self):
        with self._lock:
            if self._such is None:
                index: dict[str, dict] = {}
                for vk in self._vektoren.values():
                    index.update(vk)
                jetzt = wissen._jetzt()
                texte: dict[str, tuple[str]] = {}
                for q, _teile, hashes in self._wi.alle(mit_hash=True):
                    if q.privat or not q.gueltig(jetzt):
                        continue
                    for nr, h in enumerate(hashes):
                        texte[f"{q.kennung}:{nr}"] = (h,)
                schluessel, skizzen = verteiler.skizzen_liste(index, lambda s: (texte.get(s) or (None,))[0])
                self._such = (schluessel, skizzen, index, texte, list(self._verzeichnisse.values()))
            return self._such

    def _abschnitt(self, s: str):
        try:
            k, nr = s.rsplit(":", 1)
            r = self._wi.abschnitt(k, int(nr))
        except (ValueError, TypeError):
            return None
        return (r[0], r[1]) if r else None

    def _idf(self, w: str) -> float:
        n, d = self._wi.anzahl_abschnitte(), self._wi.df(w)
        return math.log(1 + (n - d + 0.5) / (d + 0.5)) if n else 1.0

    def suchen(self, frage: str, *, n: int = wissen.TREFFER, vektor: list[float] | None = None, fachgebiete=None) -> tuple[list[wissen.Treffer], int]:
        if not self.bereit():
            raise RuntimeError("die Kopie des Gemeinschaftswissens ist noch nicht vollständig")
        fg = wissen.fachgebiete_pruefen(fachgebiete)
        schluessel, skizzen, index, texte, verzeichnisse = self._suchlisten()
        fw = wissen.woerter(frage)
        breite = (wissen.FACH_BREITE if fg else 2) * n
        tr = self._wi.suchen(fw, n=breite, privat_erlaubt=False) if fw else []
        art = "wort"
        v = verteiler.vektor_pruefen(vektor) if isinstance(vektor, list) else None
        if v is not None:
            naehe = verteiler.naechste_vektoren(v, schluessel, skizzen, index, breite)
            gefunden = {s: r for s, _p in naehe if (r := self._abschnitt(s)) is not None and not r[0].privat}
            bedeutung = [wissen.Treffer(gefunden[s][0], gefunden[s][1], a) for s, a in naehe if s in gefunden and not wissen.ist_beiwerk(gefunden[s][1])]
            tr = wissen.treffer_vereinen(tr, bedeutung, n=n, fachgebiete=fg)
            art = "bedeutung+wort" if bedeutung else "wort"
        else:
            tr = wissen.fachgebiet_gewichten(tr, fg, n=n)
        vorbereitet = verteiler.vertief_treffer(frage, verzeichnisse, texte, self._idf, self._abschnitt)
        if vorbereitet:
            tr = (vorbereitet + tr)[:n]
            art += "+vorbereitet"
        if fg:
            art += "+fachgebiet"
        self.letzte_suche = art
        return tr, len(self._vektoren)


__all__ = ["Pakete", "Spiegel", "FORMAT", "BAU_ABSTAND_S", "HOLEN_ABSTAND_S", "pakete_packen", "pakete_auspacken"]
