# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import heapq
import json
import math
import operator
from array import array
import random
import re
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import hausordnung
import schleifenbremse
import sicher_schreiben
import vermittlung_basis
import wissen

STARK_AB_B = vermittlung_basis.STARK_AB_B
PRUEF_FASSUNG = 2
NACHPRUEFEN_STRENG_ANTEIL = 0.4
NACHPRUEFEN_ANTEIL = 0.5

MODELL_KENNUNG = "qwen3-embedding-0.6b-q8_0"
MODELL_SHA256 = "06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439"
DIMENSION = 1024
BUENDEL = 50
PRUEFANTEIL = 0.2
TOLERANZ = 0.99
FRIST_S = 600
INDEX_PRUEFEN_S = 1.0
GERAETE_SCHWUND_AB = 20
NACHKOMMA = 5
CREDITS_JE_BUENDEL = 1
UNKLAR_PAUSE_S = 24 * 3600
QR_BREMSE_S = 24 * 3600
UNKLAR_ADMIN = 3
STARK_DA_S = 300
PRUEF_ART = "hausordnung"
PRUEF_TEXT = 6000
VERSTOESSE_SPERRE = 2
MAX_GERAETE = 20000
GERAETE_MAX_BYTES = 64 * 1024 * 1024
AUFTRAEGE_SCHREIB_MAX_BYTES = 6 * 1024 * 1024
AUFTRAEGE_KUERZEN_AUF_BYTES = 5 * 1024 * 1024
AUFTRAEGE_LESEN_MAX_BYTES = 32 * 1024 * 1024
GRUENDUNG_MAX = 100
AKTIV_SAMMELN_S = 2.0
DIRNAME = "rechen"
INDEX_DIRNAME = "index"
VERTIEF_ART = "vertiefen"
VERTIEF_PRUEF_ART = "vertiefen_pruefen"
VERTIEF_DIRNAME = "vertieft"
VERTIEF_FRAGEN_MIN = 3
VERTIEF_FRAGEN_MAX = 5
VERTIEF_ZUSAMMENFASSUNG_MAX = 500
VERTIEF_FRAGE_MAX = 200
VERTIEF_ANTWORT_MAX = 700
VERTIEF_FRIST_S = 900
VERTIEF_VERWORFEN_MAX = 3
VERTIEF_STAU_MAX = 500
VERTIEF_PAUSE_S = 30 * 24 * 3600
CREDITS_JE_VERTIEFUNG = 1
CREDITS_JE_VERTIEF_PRUEFUNG = 1
VERTIEF_TREFFER_MIN = 2
VERTIEF_TREFFER = 2
VERTIEF_GEWICHT_MIN = 0.6
TRAININGS_SCHRITT = 5000
VERTIEF_VERZEICHNIS_PRUEFEN_S = 2.0


class VerteilerError(wissen.WissenError):
    pass


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _heute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _schreiben(p: Path, obj) -> None:
    sicher_schreiben.json_datei(p, obj, indent=None)


def _aelteste_weg(obj, zu_viel: int):
    if isinstance(obj, dict):
        reihe = sorted(obj, key=lambda k: str((obj[k] or {}).get("vergeben", "")) if isinstance(obj[k], dict) else "")
        weg, frei = set(), 0
        for k in reihe:
            if frei >= zu_viel:
                break
            weg.add(k)
            frei += len(json.dumps({k: obj[k]}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        return {k: v for k, v in obj.items() if k not in weg}
    liste, frei, i = list(obj), 0, 0
    while i < len(liste) and frei < zu_viel:
        frei += len(json.dumps(liste[i], ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1
        i += 1
    return liste[i:]


def _lesen(p: Path, standard):
    return sicher_schreiben.json_laden(p, standard)


def abschnitt_hash(text: str) -> str:
    return wissen.abschnitt_hash(text)


def pruefsumme(ergebnisse: list[dict]) -> str:
    roh = json.dumps([[str(e.get("schluessel", "")), e.get("vektor")] for e in ergebnisse], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def vektor_pruefen(v) -> list[float] | None:
    if not isinstance(v, list) or len(v) != DIMENSION:
        return None
    out = []
    quadrat = 0.0
    for x in v:
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x) > 1.0:
            return None
        x = round(float(x), NACHKOMMA)
        out.append(x)
        quadrat += x * x
    if abs(math.sqrt(quadrat) - 1.0) > 0.01:
        return None
    return out


def kosinus(a, b) -> float:
    if hasattr(math, "sumprod"):
        return float(math.sumprod(a, b))
    return sum(x * y for x, y in zip(a, b))


VORFILTER = 200


def quantisieren(v) -> tuple[bytes, float]:
    m = max((abs(float(x)) for x in v), default=0.0)
    s = m / 127.0 if m > 0 else 1.0
    return bytes((max(-127, min(127, round(float(x) / s))) & 0xFF) for x in v), s


def dequantisieren(b: bytes, s: float) -> list[float]:
    return [x * s for x in array("b", b)]


def skizze(v) -> int:
    out = 0
    for i, x in enumerate(v):
        if x > 0:
            out |= 1 << i
    return out


def punkt_int8(a: array, b: array) -> int:
    return sum(map(operator.mul, a, b))


def index_eintrag(vektor: list[float], **rest) -> dict:
    b, s = quantisieren(vektor)
    return {"vq": base64.b64encode(b).decode("ascii"), "s": round(s, 9), "sk": format(skizze(vektor), "0256x"), **rest}


def _eintrag_umstellen(e: dict) -> bool:
    if isinstance(e.get("vektor"), (list, array)):
        e.update(index_eintrag(list(e["vektor"])))
        e.pop("vektor", None)
        return True
    return False


def _eintrag_laden(e: dict) -> None:
    try:
        e["_b"] = array("b", base64.b64decode(str(e.get("vq", ""))))
        e["_sk"] = int(str(e.get("sk", "0")), 16)
    except (ValueError, TypeError):
        e.pop("_b", None)
        e.pop("_sk", None)


def _eintrag_speicherform(e: dict) -> dict:
    return {k: v for k, v in e.items() if not k.startswith("_")}


def vertiefung_pruefen_form(v) -> dict:
    if not isinstance(v, dict):
        raise VerteilerError("VERTIEF_FORM", "keine Vertiefung mitgeschickt")
    z = " ".join(str(v.get("zusammenfassung", "")).split())
    if len(z) < 10:
        raise VerteilerError("VERTIEF_FORM", "die Zusammenfassung fehlt oder ist zu kurz")
    fragen = []
    for f in v.get("fragen") if isinstance(v.get("fragen"), list) else []:
        if not isinstance(f, dict):
            continue
        fr = " ".join(str(f.get("frage", "")).split())
        an = " ".join(str(f.get("antwort", "")).split())
        if len(fr) < 8 or len(an) < 5:
            continue
        if not fr.endswith("?"):
            fr = fr.rstrip(".!:") + "?"
        if fr.lower() in [x["frage"].lower() for x in fragen]:
            continue
        fragen.append({"frage": fr[:VERTIEF_FRAGE_MAX], "antwort": an[:VERTIEF_ANTWORT_MAX]})
        if len(fragen) >= VERTIEF_FRAGEN_MAX:
            break
    if len(fragen) < VERTIEF_FRAGEN_MIN:
        raise VerteilerError("VERTIEF_FORM", f"es braucht mindestens {VERTIEF_FRAGEN_MIN} Fragen mit Antwort, es kamen {len(fragen)}")
    return {"zusammenfassung": z[:VERTIEF_ZUSAMMENFASSUNG_MAX], "fragen": fragen}


@dataclass(frozen=True)
class Geraet:
    kennung: str
    name: str
    abschnitte: int
    geprueft: int
    abgelehnt: int
    credits: int

    def kurz(self) -> dict:
        return {"kennung": self.kennung, "name": self.name, "abschnitte": self.abschnitte, "geprueft": self.geprueft, "abgelehnt": self.abgelehnt, "credits": self.credits}


_NAME_RESERVIERT = re.compile(r"admin|kiplatz|moderator|support|community[-\s]?ai|offiziell", re.IGNORECASE)


def _namensschluessel(name: str) -> str:
    return "".join(c for c in str(name).casefold() if c.isalnum())


def geraetename_eindeutig(name: str, vergeben) -> str:
    name = " ".join(str(name or "").split())[:60] or "Gerät"
    name = " ".join(_NAME_RESERVIERT.sub("Gerät", name).split())[:60]
    schon = {_namensschluessel(v) for v in vergeben}
    if _namensschluessel(name) not in schon:
        return name
    for n in range(2, 1000):
        neu = f"{name[:55]} {n}"
        if _namensschluessel(neu) not in schon:
            return neu
    return f"{name[:48]} {secrets.token_hex(3)}"


def _gesperrt(f):
    def innen(self, *a, **k):
        with self._sperre:
            return f(self, *a, **k)
    innen.__name__, innen.__doc__, innen.__wrapped__ = f.__name__, f.__doc__, f
    return innen


class _HashSicht:
    __slots__ = ("_t",)

    def __init__(self, texte: dict[str, tuple[str, str]]) -> None:
        self._t = texte

    def get(self, s: str, standard=None):
        e = self._t.get(s)
        return e[0] if e is not None else standard

    def items(self):
        return ((s, e[0]) for s, e in self._t.items())


def naechste_vektoren(v, schluessel: list[str], skizzen: list[int], index: dict[str, dict], n: int) -> list[tuple[str, float]]:
    qb, qs = quantisieren(v)
    qa, qsk = array("b", qb), skizze(v)
    abstand = [(qsk ^ sk).bit_count() for sk in skizzen]
    treffer = []
    for _abstand, s in heapq.nsmallest(max(VORFILTER, 20 * n), zip(abstand, schluessel)):
        e = index[s]
        b = e.get("_b")
        if isinstance(b, array) and len(b) == DIMENSION:
            treffer.append((s, round(punkt_int8(qa, b) * qs * float(e.get("s", 1.0)), 4)))
    treffer.sort(key=lambda t: t[1], reverse=True)
    return treffer[:n]


def skizzen_liste(index: dict[str, dict], hash_von) -> tuple[list[str], list[int]]:
    schluessel: list[str] = []
    skizzen: list[int] = []
    for s, e in index.items():
        sk = e.get("_sk")
        if sk is None or hash_von(s) != e.get("hash"):
            continue
        schluessel.append(s)
        skizzen.append(sk)
    return schluessel, skizzen


def vertief_verzeichnis_bauen(abschnitte: dict) -> tuple[dict, dict]:
    woerter_: dict[str, list[tuple[str, int]]] = {}
    eintraege: dict[tuple[str, int], tuple[frozenset, str, str, str]] = {}
    for s, e in abschnitte.items():
        if not isinstance(e, dict) or not e.get("geprueft"):
            continue
        for i, f in enumerate(e.get("fragen") or []):
            if not isinstance(f, dict):
                continue
            ft = str(f.get("frage", ""))
            qw = frozenset(wissen.woerter(ft))
            if not qw:
                continue
            eintraege[(s, i)] = (qw, ft, str(f.get("antwort", "")), str(e.get("hash", "")))
            for w in qw:
                woerter_.setdefault(w, []).append((s, i))
    return woerter_, eintraege


def vertief_treffer(frage: str, verzeichnisse, texte, idf, abschnitt, n: int = VERTIEF_TREFFER) -> list[wissen.Treffer]:
    fw = set(wissen.woerter(frage))
    if not fw:
        return []
    idf_cache: dict[str, float] = {}

    def gewicht(w: str) -> float:
        if w not in idf_cache:
            idf_cache[w] = idf(w)
        return idf_cache[w]

    fw_gewicht = {w: gewicht(w) for w in fw}
    kandidaten: list[tuple[float, str, str, str]] = []
    for woerter_, eintraege in verzeichnisse:
        gemeinsam_je: dict[tuple[str, int], list[str]] = {}
        for w in fw:
            for k in woerter_.get(w, ()):
                gemeinsam_je.setdefault(k, []).append(w)
        for k, gemeinsam_w in gemeinsam_je.items():
            qw, ft, antwort, h = eintraege[k]
            s = k[0]
            t_ = texte.get(s)
            if t_ is None or t_[0] != h:
                continue
            gemeinsam = len(gemeinsam_w)
            if gemeinsam < min(VERTIEF_TREFFER_MIN, len(qw)):
                continue
            anteil = sum(fw_gewicht[w] for w in gemeinsam_w) / (sum(gewicht(w) for w in qw) or 1.0)
            if anteil < VERTIEF_GEWICHT_MIN:
                continue
            kandidaten.append((round(anteil * 2 + gemeinsam / len(fw), 3), s, ft, antwort))
    kandidaten.sort(key=lambda x: (-x[0], x[1]))
    out: list[wissen.Treffer] = []
    gesehen: set[str] = set()
    for punkte, s, ft, antwort in kandidaten:
        if s in gesehen:
            continue
        r = abschnitt(s)
        if r is None or r[0].privat:
            continue
        gesehen.add(s)
        text = (f"{antwort}" + chr(10) + f"(Vorbereitete Antwort auf „{ft}“, von einem zweiten Gerät geprüft. "
                f"Aus dem Abschnitt: {r[1][:300].rstrip()}…)")
        out.append(wissen.Treffer(r[0], text, punkte))
        if len(out) >= n:
            break
    return out


class Verteiler:
    def __init__(self, ordner: Path, speicher: wissen.Wissensspeicher, *, jetzt=time.time, zufall: random.Random | None = None) -> None:
        self._sperre = threading.RLock()
        self.dir = Path(ordner) / DIRNAME
        self.index_dir = Path(ordner) / INDEX_DIRNAME
        self.speicher = speicher
        self._jetzt = jetzt
        self._zufall = zufall or random.SystemRandom()
        self._geraete_pfad = self.dir / "geraete.json"
        self._aktiv_offen: dict[str, str] = {}
        self._streng_pruefer: set[str] = set()
        self._aktiv_timer: threading.Timer | None = None
        self._credits_offen: dict[str, dict[str, int]] = {}
        self._gruendung_pfad = self.dir / "gruendung.json"
        self.admin_konten_lesen = lambda: set()
        self._abschnitte_cache: tuple[int, list] | None = None
        self._texte_cache: tuple[list, dict] | None = None
        self._index_sig: tuple | None = None
        self._index_out: dict[str, dict] = {}
        self._index_geprueft = 0.0
        self._offen_cache: tuple[dict, dict, list] | None = None
        self._stand_cache: tuple[list, dict, dict] | None = None
        self._auftraege_pfad = self.dir / "auftraege.json"
        self._pruefliste_pfad = self.dir / "pruefliste.json"
        self._index_cache: dict[str, tuple[int, dict]] = {}
        self.vertieft_dir = Path(ordner) / VERTIEF_DIRNAME
        self._vertieft_cache: dict[str, tuple[int, dict]] = {}
        self._qw_cache: dict[str, set[str]] = {}
        self._vf: dict[str, tuple[int, dict, dict]] = {}
        self._skizzen_cache: tuple | None = None
        self._vf_geprueft = 0.0
        self._unklar: dict[tuple[str, str], float] = {}
        self.bremse = schleifenbremse.Schleifenbremse(jetzt=jetzt, log=self._log)
        self._stufe: dict[str, tuple[float, float]] = {}
        self._stark_arbeit: dict[str, float] = {}
        self.protokoll: list[str] = []
        self.melden = None
        self.begrenzt = 0

    def _log(self, zeile: str) -> None:
        self.protokoll.append(zeile)
        self.protokoll = self.protokoll[-200:]


    def _geraete(self) -> dict:
        d = sicher_schreiben.json_laden(self._geraete_pfad, {}, hoechstens=GERAETE_MAX_BYTES)
        d = d if isinstance(d, dict) else {}
        self._offenes_eintragen(d)
        return d

    def _offenes_eintragen(self, g: dict) -> None:
        for k, tag in list(self._aktiv_offen.items()):
            if isinstance(g.get(k), dict):
                g[k]["zuletzt"] = tag
        for k, plus in list(self._credits_offen.items()):
            if isinstance(g.get(k), dict):
                for feld, v in list(plus.items()):
                    g[k][feld] = int(g[k].get(feld, 0)) + int(v)

    def _wecker(self) -> None:
        if self._aktiv_timer is None:
            self._aktiv_timer = threading.Timer(AKTIV_SAMMELN_S, self._aktiv_spaeter)
            self._aktiv_timer.daemon = True
            self._aktiv_timer.start()

    def _geraete_lesen(self) -> dict:
        d = sicher_schreiben.json_laden_gemerkt(self._geraete_pfad, {}, hoechstens=GERAETE_MAX_BYTES)
        return d if isinstance(d, dict) else {}

    def _geraete_schreiben(self, g: dict) -> None:
        vorher = len(self._geraete_lesen())
        if vorher >= GERAETE_SCHWUND_AB and len(g) < vorher // 2:
            self._log(f"FEHLER geraeteliste: {len(g)} statt {vorher} Geräte, nicht geschrieben")
            raise OSError(f"Geräteliste würde von {vorher} auf {len(g)} schrumpfen; nicht geschrieben")
        _schreiben(self._geraete_pfad, g)
        self._aktiv_offen.clear()
        self._credits_offen.clear()

    def _aktiv_spaeter(self) -> None:
        with self._sperre:
            self._aktiv_timer = None
            if self._aktiv_offen or self._credits_offen:
                try:
                    self._geraete_schreiben(self._geraete())
                except OSError as exc:
                    self._log(f"FEHLER geraeteliste schreiben: {type(exc).__name__}")

    def sichern(self) -> None:
        with self._sperre:
            if self._aktiv_timer is not None:
                self._aktiv_timer.cancel()
                self._aktiv_timer = None
            if self._aktiv_offen or self._credits_offen:
                self._geraete_schreiben(self._geraete())

    @_gesperrt
    def geraet_anlegen(self, name: str, *, art: str = "", herkunft: str = "") -> tuple[str, str]:
        g = self._geraete()
        name = geraetename_eindeutig(name, [e.get("name", "") for e in g.values() if isinstance(e, dict)])
        if len(g) >= MAX_GERAETE:
            raise VerteilerError("RECHEN_GERAETE", "zu viele Geräte")
        kennung = secrets.token_hex(6)
        token = secrets.token_hex(32)
        g[kennung] = {"name": name, "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(), "angelegt": _jetzt(),
                      "abschnitte": 0, "geprueft": 0, "abgelehnt": 0, "credits": 0, "zuletzt": _heute()}
        if art:
            g[kennung]["art"] = str(art)[:30]
        if herkunft in ("konto", "pc-konto"):
            g[kennung]["herkunft"] = herkunft
        self._geraete_schreiben(g)
        self._log(f"GERAET {kennung} {name}")
        return kennung, token

    def geraet_pruefen(self, kennung: str | None, token: str | None) -> Geraet | None:
        if not kennung or not token:
            return None
        e = self._geraete_lesen().get(str(kennung))
        if not isinstance(e, dict):
            return None
        h = hashlib.sha256(str(token).encode("utf-8", "replace")).hexdigest()
        if not secrets.compare_digest(h, str(e.get("token_sha256", ""))):
            neu = str(e.get("token_neu_sha256", ""))
            if not neu or not secrets.compare_digest(h, neu):
                return None
            self._schluessel_uebernehmen(str(kennung), h)
        if e.get("gesperrt"):
            return None
        offen = self._credits_offen.get(str(kennung)) or {}
        return Geraet(str(kennung), str(e.get("name", "")), int(e.get("abschnitte", 0)) + int(offen.get("abschnitte", 0)),
                      int(e.get("geprueft", 0)) + int(offen.get("geprueft", 0)), int(e.get("abgelehnt", 0)) + int(offen.get("abgelehnt", 0)),
                      int(e.get("credits", 0)) + int(offen.get("credits", 0)))

    def geraet_auskunft(self, kennung: str) -> dict | None:
        e = self._geraete().get(str(kennung))
        if not isinstance(e, dict):
            return None
        return {"kennung": str(kennung), **{k: v for k, v in e.items() if k not in ("token_sha256", "token_neu_sha256")}, "schluessel": "nur als Prüfwert gespeichert"}

    ERNEUERN_ABSTAND_S = 60


    @_gesperrt
    def geraet_schluessel_erneuern(self, kennung: str) -> str:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            raise VerteilerError("RECHEN_GERAET", "unbekanntes Gerät")
        if 0 <= time.time() - float(e.get("erneuert_s") or 0) < self.ERNEUERN_ABSTAND_S:
            raise VerteilerError("RECHEN_ZU_OFT", "der Schlüssel wurde eben erst erneuert; bitte in einer Minute noch einmal")
        token = secrets.token_hex(32)
        e["erneuert_s"] = time.time()
        e["token_neu_sha256"] = hashlib.sha256(token.encode("ascii")).hexdigest()
        e["erneuert"] = _jetzt()
        self._geraete_schreiben(g)
        self._log(f"GERAET {kennung} neuer Schlüssel ausgegeben")
        return token

    @_gesperrt
    def _schluessel_uebernehmen(self, kennung: str, h: str) -> None:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict) or not secrets.compare_digest(str(e.get("token_neu_sha256", "")), h):
            return
        e["token_sha256"] = h
        e.pop("token_neu_sha256", None)
        self._geraete_schreiben(g)
        self._log(f"GERAET {kennung} neuer Schlüssel gilt, der alte nicht mehr")

    @_gesperrt
    def konto_sperre_aufheben(self, sub: str) -> bool:
        konten = self.konten_gesperrt()
        if konten.pop(str(sub)[:200], None) is None:
            return False
        sicher_schreiben.json_datei(self._konten_gesperrt_pfad(), konten)
        self._log("SPERRE Konto-Sperre aufgehoben")
        return True

    @_gesperrt
    def geraet_loeschen(self, kennung: str) -> bool:
        g = self._geraete()
        if str(kennung) not in g:
            return False
        del g[str(kennung)]
        self._geraete_schreiben(g)
        self._log(f"GERAET {kennung} gelöscht (ausgetreten)")
        return True


    def _konten_gesperrt_pfad(self) -> Path:
        return self.dir / "konten_gesperrt.json"

    def konten_gesperrt(self) -> dict:
        d = sicher_schreiben.json_laden(self._konten_gesperrt_pfad(), {}, art=dict)
        return d if isinstance(d, dict) else {}

    def gesperrt_ist(self, kennung: str) -> bool:
        e = self._geraete_lesen().get(str(kennung))
        return not isinstance(e, dict) or bool(e.get("gesperrt"))

    def konto_ist_gesperrt(self, sub: str) -> bool:
        return bool(sub) and str(sub)[:200] in self.konten_gesperrt()

    @_gesperrt
    def geraet_lebenslang(self, kennung: str, grund: str = "") -> dict:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            raise VerteilerError("RECHEN_GERAET", "dieses Gerät gibt es nicht")
        grund = " ".join(str(grund or "").split())[:160] or "vom Admin auf Lebenszeit gesperrt"
        sub = str(e.get("konto_sub") or "")
        betroffen = [k for k, x in g.items() if isinstance(x, dict) and (k == str(kennung) or (sub and x.get("konto_sub") == sub))]
        for k in betroffen:
            x = g[k]
            x["gesperrt"], x["sperrgrund"], x["gesperrt_seit"], x["lebenslang"] = True, ("Lebenslang: " + grund)[:200], _jetzt(), True
        self._geraete_schreiben(g)
        if sub:
            konten = self.konten_gesperrt()
            konten[sub[:200]] = {"seit": _jetzt(), "grund": grund}
            sicher_schreiben.json_datei(self._konten_gesperrt_pfad(), konten)
        self._log(f"SPERRE lebenslang {kennung} ({len(betroffen)} Geräte{', Konto gesperrt' if sub else ''}) {grund}")
        return {"kennung": str(kennung), "geraete": len(betroffen), "konto_gesperrt": bool(sub), "grund": grund}

    @_gesperrt
    def konto_sperren(self, sub: str, an: bool, grund: str = "") -> int:
        sub = str(sub or "")[:200]
        if not sub:
            raise VerteilerError("KONTO_ID", "ohne Konto-Kennung geht das nicht")
        grund = " ".join(str(grund or "").split())[:160] or "vom Admin gesperrt"
        g = self._geraete()
        n = 0
        for x in g.values():
            if not isinstance(x, dict) or x.get("konto_sub") != sub:
                continue
            if an and not x.get("gesperrt"):
                x["gesperrt"], x["sperrgrund"], x["gesperrt_seit"], x["konto_sperre"] = True, ("Konto gesperrt: " + grund)[:200], _jetzt(), True
                n += 1
            elif not an and any([x.pop("konto_sperre", None), x.pop("lebenslang", None)]):
                x["gesperrt"] = False
                x.pop("sperrgrund", None)
                x.pop("gesperrt_seit", None)
                n += 1
        self._geraete_schreiben(g)
        konten = self.konten_gesperrt()
        if an:
            konten[sub] = {"seit": _jetzt(), "grund": grund}
        else:
            konten.pop(sub, None)
        sicher_schreiben.json_datei(self._konten_gesperrt_pfad(), konten)
        self._log(f"SPERRE Konto {'gesperrt' if an else 'freigegeben'} ({n} Geräte) {grund if an else ''}".rstrip())
        return n

    @_gesperrt
    def konto_binden(self, kennung: str, sub: str, name: str, benutzer: str = "", weg: str = "") -> dict:
        if self.konto_ist_gesperrt(sub):
            raise VerteilerError("KONTO_GESPERRT", "dieses KIplatz-Konto ist gesperrt, weil es gegen die Platzordnung verstoßen hat")
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            raise VerteilerError("RECHEN_GERAET", "unbekanntes Gerät")
        if e.get("konto_sub") != str(sub)[:200] or not e.get("konto_seit"):
            e["konto_seit"] = _jetzt()
        if e.get("konto_sub") != str(sub)[:200]:
            e.pop("konto_benutzer", None)
        e["konto_sub"] = str(sub)[:200]
        e["konto_name"] = " ".join(str(name or "").split())[:60] or "Mitglied"
        if re.fullmatch(r"[A-Za-z0-9_.\-]{1,60}", str(benutzer or "")):
            e["konto_benutzer"] = str(benutzer)
        if weg == "qr":
            e["konto_qr_seit"] = _jetzt()
        else:
            e.pop("konto_qr_seit", None)
        self._geraete_schreiben(g)
        self._log(f"KONTO {kennung} -> {e['konto_name']}")
        return {"name": e["konto_name"], "sub": e["konto_sub"]}

    def qr_bremse(self, kennung: str) -> bool:
        e = self._geraete_lesen().get(str(kennung))
        seit = str(e.get("konto_qr_seit", "")) if isinstance(e, dict) else ""
        if not seit:
            return False
        try:
            t = datetime.strptime(seit, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        return (datetime.now(timezone.utc) - t).total_seconds() < QR_BREMSE_S

    @_gesperrt
    def konto_loesen(self, kennung: str) -> bool:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict) or not e.get("konto_sub"):
            return False
        e.pop("konto_sub", None)
        e.pop("konto_name", None)
        e.pop("konto_seit", None)
        e.pop("konto_qr_seit", None)
        e.pop("konto_benutzer", None)
        self._geraete_schreiben(g)
        self._log(f"KONTO {kennung} gelöst")
        return True


    def konto_geraete(self, sub: str) -> list[dict]:
        aus = []
        gr = self.gruendung()
        for k, e in self._geraete().items():
            if isinstance(e, dict) and sub and e.get("konto_sub") == str(sub):
                aus.append({"kennung": k, "name": str(e.get("name", "")), "art": str(e.get("art") or ("PC" if e.get("herkunft") != "konto" else "Gerät")),
                            "angemeldet": str(e.get("konto_seit") or e.get("angelegt", "")), "zuletzt": str(e.get("zuletzt", "")),
                            "sitzung": e.get("herkunft") == "konto", "gruendung": gr.get(k, 0)})
        return sorted(aus, key=lambda x: (x["zuletzt"], x["angemeldet"]), reverse=True)

    @_gesperrt
    def geraet_abmelden(self, kennung: str) -> str:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict) or not e.get("konto_sub"):
            return ""
        if e.get("herkunft") == "konto":
            del g[str(kennung)]
            self._geraete_schreiben(g)
            self._log(f"GERAET {kennung} abgemeldet (entfernt)")
            return "entfernt"
        self.konto_loesen(str(kennung))
        return "geloest"

    @_gesperrt
    def aktiv_merken(self, kennung: str, heute: str | None = None) -> str:
        heute = heute or _heute()
        kennung = str(kennung)
        e = self._geraete_lesen().get(kennung)
        if not isinstance(e, dict):
            return ""
        vorher = self._aktiv_offen.get(kennung) or str(e.get("zuletzt", ""))
        if vorher != heute:
            self._aktiv_offen[kennung] = heute
            if self._aktiv_timer is None:
                self._aktiv_timer = threading.Timer(AKTIV_SAMMELN_S, self._aktiv_spaeter)
                self._aktiv_timer.daemon = True
                self._aktiv_timer.start()
        return vorher

    @_gesperrt
    def kontoreste_entfernen(self) -> int:
        g, n = self._geraete(), 0
        for e in g.values():
            if isinstance(e, dict) and not e.get("konto_sub") and "konto_benutzer" in e:
                e.pop("konto_benutzer", None)
                n += 1
        if n:
            self._geraete_schreiben(g)
        return n

    @_gesperrt
    def herkunft_nachtragen(self) -> int:
        import konto_basis as _konto
        g, n = self._geraete(), 0
        arten = "|".join(re.escape(a) for a in _konto.HANDY_ARTEN)
        for e in g.values():
            if not isinstance(e, dict) or e.get("herkunft") or not e.get("konto_sub") or not e.get("konto_name"):
                continue
            m = re.fullmatch(re.escape(str(e["konto_name"])) + rf" ({arten})(?: \d+)?", str(e.get("name", "")))
            if m and not any(int(e.get(z, 0) or 0) for z in ("abschnitte", "geprueft", "credits", "antworten", "vertieft")):
                e["herkunft"], e["art"] = "konto", m.group(1)
                n += 1
        if n:
            self._geraete_schreiben(g)
        return n

    def konto_von(self, kennung: str) -> dict | None:
        e = self._geraete_lesen().get(str(kennung))
        if not isinstance(e, dict) or not e.get("konto_sub"):
            return None
        k = {"name": str(e.get("konto_name", "")), "sub": str(e["konto_sub"])}
        if e.get("konto_benutzer"):
            k["benutzer"] = str(e["konto_benutzer"])
        return k

    @_gesperrt
    def geraet_sperren(self, kennung: str, gesperrt: bool, grund: str = "") -> dict:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            raise VerteilerError("RECHEN_GERAET", "dieses Gerät gibt es nicht")
        if not gesperrt and e.get("lebenslang"):
            sub = str(e.get("konto_sub") or "")
            for x in g.values():
                if isinstance(x, dict) and x.get("lebenslang") and (x is e or (sub and x.get("konto_sub") == sub)):
                    x.pop("lebenslang", None)
                    if x is not e:
                        x["gesperrt"], x["sperrgrund"], x["gesperrt_seit"] = False, "", ""
            konten = self.konten_gesperrt()
            if sub and konten.pop(sub[:200], None) is not None:
                sicher_schreiben.json_datei(self._konten_gesperrt_pfad(), konten)
        e["gesperrt"] = bool(gesperrt)
        e["sperrgrund"] = " ".join(str(grund or "").split())[:200] if gesperrt else ""
        e["gesperrt_seit"] = _jetzt() if gesperrt else ""
        self._geraete_schreiben(g)
        self._log(f"SPERRE {kennung} {'an' if gesperrt else 'aus'} {e['sperrgrund']}")
        return {"kennung": str(kennung), "name": e.get("name", ""), "gesperrt": bool(gesperrt), "sperrgrund": e["sperrgrund"]}

    def antworten_bisher(self, kennung: str) -> int:
        e = self._geraete_lesen().get(str(kennung))
        offen = self._credits_offen.get(str(kennung)) or {}
        return (int(e.get("antworten", 0) or 0) if isinstance(e, dict) else 0) + int(offen.get("antworten", 0) or 0)

    def geraete(self) -> list[dict]:
        return [{"kennung": k, "name": e.get("name", ""), "abschnitte": e.get("abschnitte", 0), "geprueft": e.get("geprueft", 0), "abgelehnt": e.get("abgelehnt", 0), "credits": e.get("credits", 0), "angelegt": e.get("angelegt", ""),
                 "gesperrt": bool(e.get("gesperrt")), "sperrgrund": e.get("sperrgrund", ""), "gesperrt_seit": e.get("gesperrt_seit", ""), "verstoesse": int(e.get("verstoesse", 0)),
                 "lebenslang": bool(e.get("lebenslang")),
                 "antworten": int(e.get("antworten", 0)), "admin": bool(e.get("admin")),
                 "vertieft": int(e.get("vertieft", 0)), "vertieft_geprueft": int(e.get("vertieft_geprueft", 0)),
                 "konto_sub": str(e.get("konto_sub", "") or ""), "konto_name": str(e.get("konto_name", "") or ""),
                 "zuletzt": str(e.get("zuletzt", "") or ""), "art": str(e.get("art", "") or ""),
                 "gruendung": gr.get(k, 0)}
                for gr in [self.gruendung()] for k, e in self._geraete().items() if isinstance(e, dict)]


    def ist_admin(self, kennung: str) -> bool:
        e = self._geraete_lesen().get(str(kennung))
        return isinstance(e, dict) and bool(e.get("admin")) and not e.get("gesperrt")

    @_gesperrt
    def geraet_admin(self, kennung: str, an: bool) -> dict:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            raise VerteilerError("GERAET_UNBEKANNT", "dieses Gerät gibt es nicht")
        e["admin"] = bool(an)
        e["admin_seit"] = _jetzt() if an else ""
        self._geraete_schreiben(g)
        return {"kennung": str(kennung), "name": str(e.get("name", "")), "admin": bool(an)}

    def _geraet_zaehlen(self, g: dict, kennung: str, **plus: int) -> None:
        e = g.get(kennung)
        if isinstance(e, dict):
            for k, v in plus.items():
                e[k] = int(e.get(k, 0)) + v

    @_gesperrt
    def credits_gutschreiben(self, kennung: str, credits: int, **zaehler: int) -> None:
        e = self._credits_offen.setdefault(str(kennung), {})
        for feld, v in {"credits": int(credits), **zaehler}.items():
            if int(v):
                e[feld] = int(e.get(feld, 0)) + int(v)
        if not e:
            self._credits_offen.pop(str(kennung), None)
        self._wecker()
        if int(credits) > 0:
            self._gruendung_vergeben(str(kennung))


    def gruendung(self) -> dict[str, int]:
        d = sicher_schreiben.json_laden_gemerkt(self._gruendung_pfad, {})
        g = d.get("geraete") if isinstance(d, dict) else None
        return {str(k): int(v.get("nr", 0)) for k, v in (g or {}).items() if isinstance(v, dict) and int(v.get("nr", 0)) > 0}

    def gruendung_eintraege(self) -> list[dict]:
        d = sicher_schreiben.json_laden_gemerkt(self._gruendung_pfad, {})
        g = d.get("geraete") if isinstance(d, dict) else None
        geraete = self._geraete_lesen()
        aus = []
        for k, v in sorted((g or {}).items(), key=lambda kv: int((kv[1] or {}).get("nr", 0)) if isinstance(kv[1], dict) else 0):
            e = geraete.get(str(k))
            if not isinstance(v, dict) or not isinstance(e, dict):
                continue
            aus.append({"nr": int(v.get("nr", 0)), "zeit": str(v.get("zeit", "")), "benutzer": str(e.get("konto_benutzer", "") or ""),
                        "konto_name": str(e.get("konto_name", "") or ""), "konto_sub": str(e.get("konto_sub", "") or "")})
        return aus

    def _gruendung_vergeben(self, kennung: str) -> int:
        bekannt = self.gruendung()
        if kennung in bekannt:
            return bekannt[kennung]
        if len(bekannt) >= GRUENDUNG_MAX:
            return 0
        geraete = self._geraete_lesen()
        e = geraete.get(kennung)
        if not isinstance(e, dict) or e.get("admin") or e.get("gesperrt"):
            return 0
        sub = str(e.get("konto_sub", "") or "")
        if sub:
            try:
                admin_konten = set(self.admin_konten_lesen() or ())
            except Exception:
                admin_konten = set()
            if sub in admin_konten or any(isinstance(x, dict) and x.get("admin") and str(x.get("konto_sub", "")) == sub for x in geraete.values()):
                return 0
        nr = max(bekannt.values(), default=0) + 1
        d = sicher_schreiben.json_laden(self._gruendung_pfad, {})
        d = d if isinstance(d, dict) else {}
        g = d.setdefault("geraete", {})
        if not isinstance(g, dict):
            g = d["geraete"] = {}
        g[kennung] = {"nr": nr, "zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._jetzt()))}
        _schreiben(self._gruendung_pfad, d)
        self._log(f"GRUENDUNG Nr. {nr} für {kennung}")
        return nr


    def _index_pfad(self, quelle: str) -> Path:
        return self.index_dir / f"{quelle}.json"

    def _index_lesen(self, quelle: str) -> dict:
        d = _lesen(self._index_pfad(quelle), {})
        if not isinstance(d, dict) or d.get("modell") != MODELL_KENNUNG or not isinstance(d.get("abschnitte"), dict):
            return {"modell": MODELL_KENNUNG, "abschnitte": {}}
        for e in d["abschnitte"].values():
            if isinstance(e, dict):
                _eintrag_umstellen(e)
        return d

    def _index_schreiben(self, quelle: str, d: dict) -> None:
        self._index_cache.pop(quelle, None)
        _schreiben(self._index_pfad(quelle), {**d, "abschnitte": {s: _eintrag_speicherform(e) for s, e in d["abschnitte"].items() if isinstance(e, dict)}})
        self._index_geprueft = 0.0

    @_gesperrt
    def index_umstellen(self) -> int:
        n = 0
        if not self.index_dir.is_dir():
            return 0
        for p in sorted(self.index_dir.glob("*.json")):
            roh = _lesen(p, {})
            if isinstance(roh, dict) and isinstance(roh.get("abschnitte"), dict) and any(isinstance(e, dict) and "vektor" in e for e in roh["abschnitte"].values()):
                self._index_schreiben(p.stem, self._index_lesen(p.stem))
                n += 1
        return n

    def index_von(self, quelle: str) -> dict:
        d = self._index_lesen(quelle)
        return {"modell": MODELL_KENNUNG, "abschnitte": {s: _eintrag_speicherform(e) for s, e in d["abschnitte"].items() if isinstance(e, dict) and e.get("vq")}}

    def alle_abschnitte(self) -> list[tuple[str, str, str]]:
        wi = getattr(self.speicher, "wortindex", None)
        if wi is not None:
            self.speicher._abgleichen_gelegentlich()
            c = self._abschnitte_cache
            if c is not None and c[0] == wi.version:
                return c[1]
        out = []
        for q, teile, hashes in self.speicher.alle_mit_hash():
            if q.privat:
                continue
            for nr, (t, h) in enumerate(zip(teile, hashes)):
                out.append((f"{q.kennung}:{nr}", h, t))
        if wi is not None:
            self._abschnitte_cache = (wi.version, out)
            self._texte_cache = None
        return out

    def _texte(self) -> dict[str, tuple[str, str]]:
        alle = self.alle_abschnitte()
        c = self._texte_cache
        if c is not None and c[0] is alle:
            return c[1]
        texte = {s: (h, t) for s, h, t in alle}
        self._texte_cache = (alle, texte)
        return texte

    def _skizzen(self, index: dict[str, dict]) -> tuple[list[str], list[int]]:
        texte = self._texte()
        c = self._skizzen_cache
        if c is not None and c[0] is index and c[1] is texte:
            return c[2], c[3]
        schluessel, skizzen = skizzen_liste(index, lambda s: (texte.get(s) or (None,))[0])
        self._skizzen_cache = (index, texte, schluessel, skizzen)
        return schluessel, skizzen

    def _im_index(self) -> dict[str, dict]:
        if not self.index_dir.is_dir():
            return {}
        jetzt = time.monotonic()
        if self._index_sig is not None and jetzt - self._index_geprueft < INDEX_PRUEFEN_S:
            return self._index_out
        self._index_geprueft = jetzt
        gesehen: dict[str, int] = {}
        for p in self.index_dir.glob("*.json"):
            try:
                gesehen[p.stem] = p.stat().st_mtime_ns
            except OSError:
                continue
        sig = tuple(sorted(gesehen.items()))
        if self._index_sig == sig:
            return self._index_out
        out: dict[str, dict] = {}
        for stem, mtime in gesehen.items():
            c = self._index_cache.get(stem)
            if c is None or c[0] != mtime:
                d = self._index_lesen(stem)
                for e in d["abschnitte"].values():
                    if isinstance(e, dict):
                        _eintrag_laden(e)
                c = (mtime, d)
                self._index_cache[stem] = c
            for s, e in c[1]["abschnitte"].items():
                if isinstance(e, dict):
                    out[s] = e
        for k in [k for k in self._index_cache if k not in gesehen]:
            self._index_cache.pop(k, None)
        self._index_sig, self._index_out = sig, out
        self._offen_cache = None
        return out

    def _offene(self, texte: dict[str, tuple[str, str]], index: dict[str, dict]) -> list[str]:
        c = self._offen_cache
        if c is not None and c[0] is texte and c[1] is index:
            return c[2]
        offen = [s for s, (h, _t) in texte.items() if not (s in index and index[s].get("hash") == h)]
        self._offen_cache = (texte, index, offen)
        return offen


    def suche_vektor(self, vektor: list[float], *, n: int = 8) -> list[tuple[str, float]]:
        v = vektor_pruefen(vektor)
        if v is None:
            raise VerteilerError("SUCHE_VEKTOR", "der Suchvektor ist unbrauchbar")
        index = self._im_index()
        schluessel, skizzen = self._skizzen(index)
        return naechste_vektoren(v, schluessel, skizzen, index, n)

    def _auftraege(self) -> dict:
        d = sicher_schreiben.json_laden_gemerkt(self._auftraege_pfad, {}, hoechstens=AUFTRAEGE_LESEN_MAX_BYTES)
        return {k: dict(v) if isinstance(v, dict) else v for k, v in d.items()} if isinstance(d, dict) else {}

    def _auftraege_schreiben(self, auftraege: dict) -> None:
        self._begrenzt_schreiben(self._auftraege_pfad, auftraege)

    def _pruefliste_schreiben(self, liste: list) -> None:
        self._begrenzt_schreiben(self._pruefliste_pfad, liste)

    def _begrenzt_schreiben(self, pfad: Path, obj) -> None:
        roh = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(roh) > AUFTRAEGE_SCHREIB_MAX_BYTES:
            vorher = len(obj)
            obj = _aelteste_weg(obj, len(roh) - AUFTRAEGE_KUERZEN_AUF_BYTES)
            weg = vorher - len(obj)
            roh = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.begrenzt += weg
            zeile = f"BEGRENZT {pfad.name}: {weg} ältere Einträge abgeschnitten, {len(obj)} bleiben ({len(roh) // 1024} KB)"
            self._log(zeile)
            if self.melden is not None:
                try:
                    self.melden(zeile)
                except Exception:
                    pass
        sicher_schreiben.roh(pfad, roh + b"\n")

    def _abgelaufene_freigeben(self, auftraege: dict) -> None:
        jetzt = self._jetzt()
        for k in [k for k, a in auftraege.items() if not isinstance(a, dict) or float(a.get("frist", 0)) < jetzt]:
            self._log(f"FRIST {k} abgelaufen")
            auftraege.pop(k, None)

    def _pruefliste(self) -> list[dict]:
        d = sicher_schreiben.json_laden_gemerkt(self._pruefliste_pfad, [], hoechstens=AUFTRAEGE_LESEN_MAX_BYTES)
        return [dict(e) for e in d if isinstance(e, dict)] if isinstance(d, list) else []

    def stand(self, geraet: Geraet | None = None) -> dict:
        alle = self.alle_abschnitte()
        index = self._im_index()
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        vergeben = {s for a in auftraege.values() for s in (a.get("schluessel") or [])}
        texte = self._texte()
        c = self._stand_cache
        if c is None or c[0] is not alle or c[1] is not index:
            fertig = sum(1 for s, h, _ in alle if s in index and index[s].get("hash") == h)
            geprueft = sum(1 for s, h, _ in alle if s in index and index[s].get("hash") == h and index[s].get("geprueft"))
            c = (alle, index, {"fertig": fertig, "geprueft": geprueft})
            self._stand_cache = c
        offen = sum(1 for s in self._offene(texte, index) if s not in vergeben)
        d = {"modell": MODELL_KENNUNG, "abschnitte": len(alle), "im_index": c[2]["fertig"], "geprueft": c[2]["geprueft"], "offen": offen, "vergeben": len(vergeben),
             "quellen": self.speicher.anzahl(), "ungeprueft": len(self.speicher.ungeprueft()), "zeit": _jetzt()}
        vt = self._alle_vertieft()
        aktuell = _HashSicht(texte)
        d["vertieft"] = sum(1 for s, e in vt.items() if aktuell.get(s) == e.get("hash"))
        d["vertieft_geprueft"] = sum(1 for s, e in vt.items() if aktuell.get(s) == e.get("hash") and e.get("geprueft"))
        vert_vergeben = {a.get("schluessel") for a in auftraege.values() if a.get("art") == VERTIEF_ART}
        d["vertiefen_offen"] = sum(1 for s, h in aktuell.items() if not (s in vt and vt[s].get("hash") == h) and s not in vert_vergeben)
        if geraet is not None:
            d["geraet"] = geraet.kurz()
        return d


    def modell_melden(self, kennung: str, modell: str, *, arbeitet: bool) -> float:
        t = self._jetzt()
        stufe = vermittlung_basis.modell_stufe(modell)
        if modell:
            self._stufe[kennung] = (stufe, t)
        else:
            stufe = self.stufe_von(kennung)
        if arbeitet and stufe >= STARK_AB_B:
            self._stark_arbeit[kennung] = t
        if len(self._stufe) > MAX_GERAETE * 2:
            for k in [k for k, (_s, z) in self._stufe.items() if t - z > 24 * 3600]:
                self._stufe.pop(k, None)
                self._stark_arbeit.pop(k, None)
        return stufe

    def stufe_von(self, kennung) -> float:
        e = self._stufe.get(str(kennung or ""))
        return e[0] if e else 0.0

    def stark_da(self, ausser=()) -> bool:
        t = self._jetzt()
        return any(t - z <= STARK_DA_S for k, z in self._stark_arbeit.items() if k not in ausser)

    def _klein_geprueft(self, e: dict) -> bool:
        try:
            return float(e["pruefer_stufe"]) < STARK_AB_B
        except (KeyError, TypeError, ValueError):
            st = self.stufe_von(e.get("pruefer"))
            return 0.0 < st < STARK_AB_B

    def _schreiber_stufe(self, e: dict) -> float:
        try:
            return float(e["modell_stufe"])
        except (KeyError, TypeError, ValueError):
            return self.stufe_von(e.get("geraet"))

    @_gesperrt
    def naechstes_buendel(self, geraet: Geraet, *, herkunft: dict | None = None, pruefen: bool = False, vertiefen: bool = False, modell: str = "") -> dict | None:
        stufe = self.modell_melden(geraet.kennung, modell, arbeitet=pruefen or vertiefen)
        stark = stufe >= STARK_AB_B
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        if any(a.get("geraet") == geraet.kennung for a in auftraege.values()):
            for k in [k for k, a in auftraege.items() if a.get("geraet") == geraet.kennung]:
                auftraege.pop(k, None)
        if pruefen:
            in_pruefung = {a.get("quelle") for a in auftraege.values() if a.get("art") == PRUEF_ART}
            mein_konto = (self.konto_von(geraet.kennung) or {}).get("sub")
            for q, text in self.speicher.ungeprueft():
                if q.kennung in in_pruefung or (herkunft or {}).get(q.kennung) == geraet.kennung or q.status != wissen.UNGEPRUEFT:
                    continue
                von = (herkunft or {}).get(q.kennung)
                if mein_konto and von and von != "admin" and (self.konto_von(von) or {}).get("sub") == mein_konto:
                    continue
                if q.gueltig_bis and not q.gueltig():
                    continue
                if self._jetzt() - self._unklar.get((q.kennung, geraet.kennung), -UNKLAR_PAUSE_S) < UNKLAR_PAUSE_S:
                    continue
                if not stark and self.stark_da(ausser={geraet.kennung, (herkunft or {}).get(q.kennung)}):
                    continue
                if not self.bremse.darf(geraet.kennung, ("pruefen", q.kennung)):
                    continue
                self.bremse.vergeben(geraet.kennung, ("pruefen", q.kennung))
                kennung = secrets.token_hex(8)
                auftraege[kennung] = {"geraet": geraet.kennung, "vergeben": _jetzt(), "frist": self._jetzt() + FRIST_S, "art": PRUEF_ART, "quelle": q.kennung}
                self._auftraege_schreiben(auftraege)
                self._log(f"PRUEFAUFTRAG {kennung} an {geraet.kennung}: {q.kennung}")
                return {"auftrag": kennung, "art": PRUEF_ART, "frist_s": FRIST_S, "hausordnung": hausordnung.HAUSORDNUNG,
                        "quelle": {"kennung": q.kennung, "art": q.art, "titel": q.titel, "adresse": q.adresse, "text": text[:PRUEF_TEXT]}}
        vergeben = {s for a in auftraege.values() for s in (a.get("schluessel") or [])}
        texte = self._texte()
        index = self._im_index()
        gewaehlt: list[str] = []
        pruef: list[str] = []
        for e in self._pruefliste():
            s = str(e.get("schluessel", ""))
            if e.get("geraet") == geraet.kennung or s in vergeben or s not in texte or texte[s][0] != e.get("hash"):
                continue
            if not self.bremse.darf(geraet.kennung, ("abschnitt", s)):
                continue
            if len(pruef) >= max(1, int(BUENDEL * PRUEFANTEIL)):
                break
            pruef.append(s)
        gewaehlt.extend(pruef)
        for s in self._offene(texte, index):
            if len(gewaehlt) >= BUENDEL:
                break
            if s in vergeben or s in gewaehlt:
                continue
            if not self.bremse.darf(geraet.kennung, ("abschnitt", s)):
                continue
            gewaehlt.append(s)
        if not gewaehlt:
            return self._vertief_auftrag(geraet, auftraege, texte, stufe) if vertiefen else None
        for s in gewaehlt:
            self.bremse.vergeben(geraet.kennung, ("abschnitt", s))
        kennung = secrets.token_hex(8)
        frist = self._jetzt() + FRIST_S
        auftraege[kennung] = {"geraet": geraet.kennung, "vergeben": _jetzt(), "frist": frist, "schluessel": gewaehlt,
                              "hash": {s: texte[s][0] for s in gewaehlt}, "pruef": pruef}
        self._auftraege_schreiben(auftraege)
        self._log(f"AUFTRAG {kennung} an {geraet.kennung}: {len(gewaehlt)} Abschnitte, davon {len(pruef)} zur Prüfung")
        return {"auftrag": kennung, "modell": {"kennung": MODELL_KENNUNG, "sha256": MODELL_SHA256, "dimension": DIMENSION},
                "frist_s": FRIST_S, "nachkomma": NACHKOMMA,
                "abschnitte": [{"schluessel": s, "text": texte[s][1]} for s in gewaehlt]}


    def _vertieft_pfad(self, quelle: str) -> Path:
        return self.vertieft_dir / f"{quelle}.json"

    def _vertieft_lesen(self, quelle: str) -> dict:
        d = _lesen(self._vertieft_pfad(quelle), {})
        if not isinstance(d, dict) or not isinstance(d.get("abschnitte"), dict):
            d = {"abschnitte": {}}
        if not isinstance(d.get("verzicht"), dict):
            d["verzicht"] = {}
        if not isinstance(d.get("verworfen"), dict):
            d["verworfen"] = {}
        return d

    def _vertieft_schreiben(self, quelle: str, d: dict) -> None:
        self._vertieft_cache.pop(quelle, None)
        self._vf.pop(quelle, None)
        self._vf_geprueft = 0.0
        if d.get("abschnitte") or d.get("verzicht") or d.get("verworfen"):
            _schreiben(self._vertieft_pfad(quelle), d)
        else:
            try:
                self._vertieft_pfad(quelle).unlink()
            except OSError:
                pass

    def _alle_vertieft(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        if not self.vertieft_dir.is_dir():
            return out
        gesehen = set()
        for p in self.vertieft_dir.glob("*.json"):
            try:
                mtime = p.stat().st_mtime_ns
            except OSError:
                continue
            gesehen.add(p.stem)
            c = self._vertieft_cache.get(p.stem)
            if c is None or c[0] != mtime:
                c = (mtime, self._vertieft_lesen(p.stem))
                self._vertieft_cache[p.stem] = c
            for s, e in c[1]["abschnitte"].items():
                if isinstance(e, dict):
                    out[s] = e
        for k in [k for k in self._vertieft_cache if k not in gesehen]:
            self._vertieft_cache.pop(k, None)
        return out

    def _alle_verzicht(self) -> dict[str, list[str]]:
        self._alle_vertieft()
        out: dict[str, list[str]] = {}
        for _mtime, d in self._vertieft_cache.values():
            for s, wer in (d.get("verzicht") or {}).items():
                if isinstance(wer, list):
                    out[s] = [str(x) for x in wer]
        return out

    def _alle_verworfen(self) -> dict[str, dict]:
        self._alle_vertieft()
        out: dict[str, dict] = {}
        for _mtime, d in self._vertieft_cache.values():
            for s, v in (d.get("verworfen") or {}).items():
                if isinstance(v, dict):
                    out[s] = v
        return out

    def _ruht(self, verworfen: dict, s: str, h: str) -> bool:
        v = verworfen.get(s)
        if not isinstance(v, dict) or v.get("hash") != h:
            return False
        try:
            return int(v.get("n", 0)) >= VERTIEF_VERWORFEN_MAX and self._jetzt() - float(v.get("zeit_s", 0)) < VERTIEF_PAUSE_S
        except (TypeError, ValueError):
            return False

    def _verzicht_merken(self, s: str, kennung: str) -> None:
        quelle = s.split(":", 1)[0]
        d = self._vertieft_lesen(quelle)
        wer = d["verzicht"].setdefault(s, [])
        if kennung not in wer:
            wer.append(kennung)
        self._vertieft_schreiben(quelle, d)

    @_gesperrt
    def vertiefung_verzicht(self, geraet: Geraet, body: dict) -> dict:
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        kennung = str(body.get("auftrag", ""))
        a = auftraege.get(kennung)
        if not isinstance(a, dict) or a.get("geraet") != geraet.kennung or a.get("art") != VERTIEF_ART:
            raise VerteilerError("RECHEN_AUFTRAG", "diesen Auftrag gibt es nicht mehr (Frist abgelaufen oder unbekannt)")
        s = str(a.get("schluessel", ""))
        auftraege.pop(kennung, None)
        self._auftraege_schreiben(auftraege)
        self._verzicht_merken(s, geraet.kennung)
        grund = " ".join(str(body.get("grund", "")).split())[:160]
        self._log(f"VERZICHT {s} von {geraet.kennung}: {grund}")
        return {"schluessel": s, "verzicht": True}

    def _quellen_kurz(self) -> dict[str, dict]:
        return {q.kennung: {"kennung": q.kennung, "titel": q.titel, "adresse": q.adresse, "art": q.art} for q, _ in self.speicher.alle() if not q.privat}

    def _vertief_auftrag(self, geraet: Geraet, auftraege: dict, texte: dict, stufe: float = 0.0) -> dict | None:
        stark = stufe >= STARK_AB_B
        if not stark:
            return None
        vt = self._alle_vertieft()
        quellen = self._quellen_kurz()
        in_arbeit = {(a.get("art"), a.get("schluessel")) for a in auftraege.values() if a.get("art") in (VERTIEF_ART, VERTIEF_PRUEF_ART)}
        for s, e in vt.items():
            if s not in texte or texte[s][0] != e.get("hash") or e.get("geprueft") or e.get("geraet") == geraet.kennung:
                continue
            if geraet.kennung in (e.get("unklar_von") or []) or (VERTIEF_PRUEF_ART, s) in in_arbeit:
                continue
            if self._schreiber_stufe(e) < STARK_AB_B:
                continue
            if not stark and self.stark_da(ausser={geraet.kennung, e.get("geraet")}):
                continue
            if not self.bremse.darf(geraet.kennung, ("vertief_pruefen", s)):
                continue
            self.bremse.vergeben(geraet.kennung, ("vertief_pruefen", s))
            kennung = secrets.token_hex(8)
            auftraege[kennung] = {"geraet": geraet.kennung, "vergeben": _jetzt(), "frist": self._jetzt() + VERTIEF_FRIST_S, "art": VERTIEF_PRUEF_ART, "schluessel": s, "hash": e.get("hash")}
            self._auftraege_schreiben(auftraege)
            self._log(f"VERTIEFPRUEFUNG {kennung} an {geraet.kennung}: {s}")
            return {"auftrag": kennung, "art": VERTIEF_PRUEF_ART, "frist_s": VERTIEF_FRIST_S, "schluessel": s, "quelle": quellen.get(s.split(":", 1)[0], {}),
                    "text": texte[s][1], "vertiefung": {"zusammenfassung": e.get("zusammenfassung", ""), "fragen": list(e.get("fragen") or [])}}
        if stark and random.random() < NACHPRUEFEN_ANTEIL:
            streng_runde = random.random() < NACHPRUEFEN_STRENG_ANTEIL
            for s, e in vt.items():
                if s not in texte or texte[s][0] != e.get("hash") or not e.get("geprueft"):
                    continue
                if geraet.kennung in (e.get("geraet"), e.get("pruefer")) or (VERTIEF_PRUEF_ART, s) in in_arbeit:
                    continue
                if geraet.kennung in (e.get("unklar_von") or []):
                    continue
                streng_fehlt = streng_runde and int(e.get("pruef_fassung") or 1) < PRUEF_FASSUNG and geraet.kennung in self._streng_pruefer
                if not ((self._klein_geprueft(e) and not e.get("nachgeprueft")) or streng_fehlt):
                    continue
                if not self.bremse.darf(geraet.kennung, ("vertief_pruefen", s)):
                    continue
                self.bremse.vergeben(geraet.kennung, ("vertief_pruefen", s))
                kennung = secrets.token_hex(8)
                auftraege[kennung] = {"geraet": geraet.kennung, "vergeben": _jetzt(), "frist": self._jetzt() + VERTIEF_FRIST_S, "art": VERTIEF_PRUEF_ART, "schluessel": s,
                                      "hash": e.get("hash"), "nachpruefen": True}
                self._auftraege_schreiben(auftraege)
                self._log(f"VERTIEFNACHPRUEFUNG {kennung} an {geraet.kennung}: {s}")
                return {"auftrag": kennung, "art": VERTIEF_PRUEF_ART, "frist_s": VERTIEF_FRIST_S, "schluessel": s, "quelle": quellen.get(s.split(":", 1)[0], {}),
                        "text": texte[s][1], "vertiefung": {"zusammenfassung": e.get("zusammenfassung", ""), "fragen": list(e.get("fragen") or [])}}
        if not stark:
            return None
        stau = sum(1 for s, e in vt.items() if e.get("geraet") == geraet.kennung and not e.get("geprueft") and s in texte and texte[s][0] == e.get("hash"))
        if stau >= VERTIEF_STAU_MAX:
            return None
        verzicht = self._alle_verzicht()
        verworfen = self._alle_verworfen()
        for s, (h, text) in texte.items():
            if s in vt and vt[s].get("hash") == h and (vt[s].get("geprueft") or self._schreiber_stufe(vt[s]) >= STARK_AB_B):
                continue
            if self._ruht(verworfen, s, h):
                continue
            if (VERTIEF_ART, s) in in_arbeit or geraet.kennung in verzicht.get(s, []):
                continue
            if not self.bremse.darf(geraet.kennung, ("vertiefen", s)):
                continue
            self.bremse.vergeben(geraet.kennung, ("vertiefen", s))
            kennung = secrets.token_hex(8)
            auftraege[kennung] = {"geraet": geraet.kennung, "vergeben": _jetzt(), "frist": self._jetzt() + VERTIEF_FRIST_S, "art": VERTIEF_ART, "schluessel": s, "hash": h}
            self._auftraege_schreiben(auftraege)
            self._log(f"VERTIEFAUFTRAG {kennung} an {geraet.kennung}: {s}")
            return {"auftrag": kennung, "art": VERTIEF_ART, "frist_s": VERTIEF_FRIST_S, "schluessel": s, "quelle": quellen.get(s.split(":", 1)[0], {}),
                    "text": text, "fragen_min": VERTIEF_FRAGEN_MIN, "fragen_max": VERTIEF_FRAGEN_MAX}
        return None

    @_gesperrt
    def vertiefung_annehmen(self, geraet: Geraet, body: dict) -> dict:
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        kennung = str(body.get("auftrag", ""))
        a = auftraege.get(kennung)
        g = self._geraete()
        try:
            if not isinstance(a, dict) or a.get("geraet") != geraet.kennung or a.get("art") != VERTIEF_ART:
                raise VerteilerError("RECHEN_AUFTRAG", "diesen Auftrag gibt es nicht mehr (Frist abgelaufen oder unbekannt)")
            s = str(a.get("schluessel", ""))
            texte = {k: (h, t) for k, h, t in self.alle_abschnitte()}
            if s not in texte or texte[s][0] != a.get("hash"):
                raise VerteilerError("VERTIEF_VERALTET", "der Abschnitt hat sich inzwischen geändert; er wird neu vergeben")
            v = vertiefung_pruefen_form(body.get("vertiefung"))
            b = hausordnung.pruefen(v["zusammenfassung"] + chr(10) + chr(10).join(f["frage"] + " " + f["antwort"] for f in v["fragen"]))
            if not b.ok:
                raise VerteilerError("VERTIEF_HAUSORDNUNG", "der Text verstößt gegen die Platzordnung und wird nicht gespeichert")
        except VerteilerError as exc:
            auftraege.pop(kennung, None)
            self._auftraege_schreiben(auftraege)
            self._geraet_zaehlen(g, geraet.kennung, abgelehnt=1)
            self._geraete_schreiben(g)
            self._log(f"ABGELEHNT {kennung} von {geraet.kennung}: {exc.code} {exc.detail}")
            if isinstance(a, dict) and exc.code in ("VERTIEF_FORM", "VERTIEF_HAUSORDNUNG"):
                self._verzicht_merken(str(a.get("schluessel", "")), geraet.kennung)
            raise
        quelle = s.split(":", 1)[0]
        d = self._vertieft_lesen(quelle)
        d["abschnitte"][s] = {"hash": a.get("hash"), "zusammenfassung": v["zusammenfassung"], "fragen": v["fragen"], "geraet": geraet.kennung, "zeit": _jetzt(), "geprueft": False,
                              "modell_stufe": self.stufe_von(geraet.kennung)}
        d["verzicht"].pop(s, None)
        self._vertieft_schreiben(quelle, d)
        self.bremse.erledigt(geraet.kennung, ("vertiefen", s))
        auftraege.pop(kennung, None)
        self._auftraege_schreiben(auftraege)
        self._geraet_zaehlen(g, geraet.kennung, vertieft=1, credits=CREDITS_JE_VERTIEFUNG)
        self._geraete_schreiben(g)
        self._log(f"VERTIEFT {s} von {geraet.kennung}: {len(v['fragen'])} Fragen")
        neu = self.geraet_pruefen_ohne_token(geraet.kennung)
        return {"schluessel": s, "fragen": len(v["fragen"]), "credits": CREDITS_JE_VERTIEFUNG, "geraet": neu.kurz() if neu else geraet.kurz()}

    @_gesperrt
    def vertiefung_urteil_annehmen(self, geraet: Geraet, body: dict) -> dict:
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        kennung = str(body.get("auftrag", ""))
        a = auftraege.get(kennung)
        if not isinstance(a, dict) or a.get("geraet") != geraet.kennung or a.get("art") != VERTIEF_PRUEF_ART:
            raise VerteilerError("RECHEN_AUFTRAG", "diesen Prüfauftrag gibt es nicht mehr (Frist abgelaufen oder unbekannt)")
        urteil = str(body.get("urteil", "")).lower()
        grund = " ".join(str(body.get("grund", "")).split())[:200]
        s = str(a.get("schluessel", ""))
        auftraege.pop(kennung, None)
        self._auftraege_schreiben(auftraege)
        if urteil not in ("ok", "falsch", "unklar"):
            raise VerteilerError("RECHEN_URTEIL", "das Urteil muss ok, falsch oder unklar sein")
        quelle = s.split(":", 1)[0]
        d = self._vertieft_lesen(quelle)
        e = d["abschnitte"].get(s)
        r = {"schluessel": s, "urteil": urteil, "grund": grund, "credits": 0}
        nach = bool(a.get("nachpruefen"))
        if not isinstance(e, dict) or e.get("hash") != a.get("hash") or (e.get("geprueft") and not nach):
            self._log(f"VERTIEFURTEIL {s} von {geraet.kennung}: Eintrag inzwischen weg oder geprüft")
            return r
        g = self._geraete()
        stufe = self.stufe_von(geraet.kennung)
        if urteil in ("falsch", "ok") and stufe < STARK_AB_B <= self._schreiber_stufe(e):
            urteil = "unklar"
            r["urteil"] = urteil
        try:
            fassung = int(body.get("fassung") or 1)
        except (TypeError, ValueError):
            fassung = 1
        if fassung >= PRUEF_FASSUNG:
            self._streng_pruefer.add(geraet.kennung)
        if urteil == "unklar":
            e["unklar_von"] = list(e.get("unklar_von") or []) + [geraet.kennung]
            self._vertieft_schreiben(quelle, d)
            self._log(f"VERTIEFURTEIL {s} von {geraet.kennung}: unklar {grund}")
            return r
        raus = sorted({int(x) for x in (body.get("raus") or []) if isinstance(x, int) or str(x).isdigit()}) if isinstance(body.get("raus"), list) else []
        if urteil == "ok" and raus:
            bleiben = [f for i, f in enumerate(e.get("fragen") or [], 1) if i not in raus]
            if 0 in raus or not bleiben:
                urteil, grund = "falsch", grund or "Zusammenfassung oder alle Antworten stehen so nicht im Abschnitt"
            else:
                e["fragen"] = bleiben
                grund = f"ohne Antwort {', '.join(map(str, raus))}"
            r["urteil"], r["grund"] = urteil, grund
        self.bremse.erledigt(geraet.kennung, ("vertief_pruefen", s))
        if urteil == "ok":
            e["geprueft"], e["pruefer"], e["geprueft_zeit"], e["pruefer_stufe"] = True, geraet.kennung, _jetzt(), stufe
            e["pruef_fassung"] = max(fassung, int(e.get("pruef_fassung") or 1)) if nach else fassung
            e.pop("unklar_von", None)
            d["verworfen"].pop(s, None)
            if nach:
                e["nachgeprueft"] = True
        else:
            d["abschnitte"].pop(s, None)
            v = d["verworfen"].get(s)
            n = int(v.get("n", 0)) + 1 if isinstance(v, dict) and v.get("hash") == e.get("hash") else 1
            d["verworfen"][s] = {"hash": e.get("hash"), "n": n, "zeit_s": self._jetzt()}
            self._geraet_zaehlen(g, str(e.get("geraet")), abgelehnt=1)
        self._vertieft_schreiben(quelle, d)
        self._geraet_zaehlen(g, geraet.kennung, vertieft_geprueft=1, credits=CREDITS_JE_VERTIEF_PRUEFUNG)
        self._geraete_schreiben(g)
        r["credits"] = CREDITS_JE_VERTIEF_PRUEFUNG
        self._log(f"VERTIEFURTEIL {s} von {geraet.kennung}: {urteil} {grund}")
        neu = self.geraet_pruefen_ohne_token(geraet.kennung)
        r["geraet"] = neu.kurz() if neu else geraet.kurz()
        return r

    def trainings_paare(self, n: int = 50000, woche: int | None = None) -> list[dict]:
        alle: list[dict] = []
        for s, e in self._alle_vertieft().items():
            if not isinstance(e, dict) or not e.get("geprueft"):
                continue
            quelle = "Wikipedia" if s.lower().startswith("wiki") else "Gemeinschaftswissen"
            for f in e.get("fragen") or []:
                if isinstance(f, dict) and f.get("frage") and f.get("antwort"):
                    alle.append({"frage": str(f["frage"]), "antwort": str(f["antwort"]), "quelle": quelle, "abschnitt": s})
        if len(alle) <= n:
            return alle
        if woche is None:
            woche = int(time.strftime("%G")) * 53 + int(time.strftime("%V"))
        start = (woche * TRAININGS_SCHRITT) % len(alle)
        return (alle[start:] + alle[:start])[:n]

    def _vertief_verzeichnis(self) -> list[tuple[dict, dict]]:
        jetzt = time.monotonic()
        if jetzt - self._vf_geprueft >= VERTIEF_VERZEICHNIS_PRUEFEN_S or not self._vf:
            self._vf_geprueft = jetzt
            self._alle_vertieft()
            for stem, (mtime, daten) in list(self._vertieft_cache.items()):
                c = self._vf.get(stem)
                if c is None or c[0] != mtime:
                    self._vf_bauen(stem, mtime, daten)
            for stem in [k for k in self._vf if k not in self._vertieft_cache]:
                self._vf.pop(stem, None)
        return [(c[1], c[2]) for c in list(self._vf.values())]

    def _vf_bauen(self, stem: str, mtime: int, daten: dict) -> None:
        woerter_, eintraege = vertief_verzeichnis_bauen(daten.get("abschnitte") or {})
        self._vf[stem] = (mtime, woerter_, eintraege)

    def vertief_vorbauen(self, sperre) -> int:
        if not self.vertieft_dir.is_dir():
            return 0
        n = 0
        for p in sorted(self.vertieft_dir.glob("*.json")):
            with sperre:
                try:
                    mtime = p.stat().st_mtime_ns
                except OSError:
                    continue
                c = self._vertieft_cache.get(p.stem)
                if c is None or c[0] != mtime:
                    c = (mtime, self._vertieft_lesen(p.stem))
                    self._vertieft_cache[p.stem] = c
                v = self._vf.get(p.stem)
                if v is None or v[0] != c[0]:
                    self._vf_bauen(p.stem, c[0], c[1])
                    n += 1
        return n

    def vertieft_suche(self, frage: str, *, n: int = VERTIEF_TREFFER) -> list[wissen.Treffer]:
        return vertief_treffer(frage, self._vertief_verzeichnis(), self._texte(), lambda w: self.speicher.idf(w, privat_erlaubt=False),
                               self.speicher.abschnitt, n)


    @_gesperrt
    def ergebnis_annehmen(self, geraet: Geraet, body: dict) -> dict:
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        kennung = str(body.get("auftrag", ""))
        a = auftraege.get(kennung)
        g = self._geraete()
        try:
            if not isinstance(a, dict) or a.get("geraet") != geraet.kennung:
                raise VerteilerError("RECHEN_AUFTRAG", "diesen Auftrag gibt es nicht mehr (Frist abgelaufen oder unbekannt)")
            if str(body.get("modell", "")) != MODELL_KENNUNG:
                raise VerteilerError("RECHEN_MODELL", "das Ergebnis stammt nicht vom festgelegten Modell")
            ergebnisse = body.get("ergebnisse")
            if not isinstance(ergebnisse, list) or not ergebnisse:
                raise VerteilerError("RECHEN_LEER", "kein Ergebnis mitgeschickt")
            if not secrets.compare_digest(str(body.get("pruefsumme", "")), pruefsumme(ergebnisse)):
                raise VerteilerError("RECHEN_PRUEFSUMME", "die Prüfsumme des Ergebnisses stimmt nicht")
            erwartet = list(a.get("schluessel") or [])
            vektoren: dict[str, list[float]] = {}
            for e in ergebnisse:
                s = str(e.get("schluessel", "")) if isinstance(e, dict) else ""
                if s not in erwartet or s in vektoren:
                    raise VerteilerError("RECHEN_FREMD", "das Ergebnis enthält Abschnitte, die nicht zum Auftrag gehören, oder doppelt")
                v = vektor_pruefen(e.get("vektor"))
                if v is None:
                    raise VerteilerError("RECHEN_VEKTOR", "ein Vektor ist unbrauchbar (falsche Länge, keine Zahl oder nicht normiert)")
                vektoren[s] = v
            if set(vektoren) != set(erwartet):
                raise VerteilerError("RECHEN_UNVOLLSTAENDIG", "das Ergebnis ist unvollständig")
        except VerteilerError as exc:
            auftraege.pop(kennung, None)
            self._auftraege_schreiben(auftraege)
            self._geraet_zaehlen(g, geraet.kennung, abgelehnt=1)
            self._geraete_schreiben(g)
            self._log(f"ABGELEHNT {kennung} von {geraet.kennung}: {exc.code}")
            raise
        pruefliste = self._pruefliste()
        pruef_offen = {str(e.get("schluessel")): e for e in pruefliste}
        geprueft_jetzt = 0
        verworfen = 0
        neu_pruef: list[dict] = []
        hashes = a.get("hash") or {}
        for s in erwartet:
            quelle, _nr = s.split(":", 1)
            d = self._index_lesen(quelle)
            if s in (a.get("pruef") or []) and s in pruef_offen:
                erster = pruef_offen.pop(s)
                if kosinus(vektoren[s], list(erster.get("vektor") or [])) >= TOLERANZ:
                    d["abschnitte"][s] = index_eintrag(list(erster["vektor"]), hash=hashes.get(s), geraet=erster.get("geraet"), geprueft=True, zweites=geraet.kennung, zeit=_jetzt())
                    self._geraet_zaehlen(g, str(erster.get("geraet")), geprueft=1)
                    self._geraet_zaehlen(g, geraet.kennung, abschnitte=1, geprueft=1)
                    geprueft_jetzt += 1
                else:
                    d["abschnitte"].pop(s, None)
                    self._geraet_zaehlen(g, str(erster.get("geraet")), abgelehnt=1)
                    self._geraet_zaehlen(g, geraet.kennung, abgelehnt=1)
                    verworfen += 1
                    self._log(f"ABWEICHUNG {s}: {erster.get('geraet')} und {geraet.kennung} verworfen")
            else:
                d["abschnitte"][s] = index_eintrag(vektoren[s], hash=hashes.get(s), geraet=geraet.kennung, geprueft=False, zeit=_jetzt())
                self._geraet_zaehlen(g, geraet.kennung, abschnitte=1)
                if self._zufall.random() < PRUEFANTEIL:
                    neu_pruef.append({"schluessel": s, "hash": hashes.get(s), "geraet": geraet.kennung, "vektor": vektoren[s]})
            self._index_schreiben(quelle, d)
        self._pruefliste_schreiben([e for e in pruefliste if str(e.get("schluessel")) in pruef_offen] + neu_pruef)
        auftraege.pop(kennung, None)
        self._auftraege_schreiben(auftraege)
        self._geraet_zaehlen(g, geraet.kennung, credits=CREDITS_JE_BUENDEL)
        self._geraete_schreiben(g)
        for s in erwartet:
            self.bremse.erledigt(geraet.kennung, ("abschnitt", s))
        self._log(f"OK {kennung} von {geraet.kennung}: {len(erwartet)} Abschnitte, {geprueft_jetzt} geprüft, {verworfen} verworfen")
        neu = self.geraet_pruefen_ohne_token(geraet.kennung)
        return {"angenommen": len(erwartet), "geprueft": geprueft_jetzt, "verworfen": verworfen, "credits": CREDITS_JE_BUENDEL,
                "geraet": neu.kurz() if neu else geraet.kurz()}

    @_gesperrt
    def urteil_annehmen(self, geraet: Geraet, body: dict) -> dict:
        auftraege = self._auftraege()
        self._abgelaufene_freigeben(auftraege)
        kennung = str(body.get("auftrag", ""))
        a = auftraege.get(kennung)
        if not isinstance(a, dict) or a.get("geraet") != geraet.kennung or a.get("art") != PRUEF_ART:
            raise VerteilerError("RECHEN_AUFTRAG", "diesen Prüfauftrag gibt es nicht mehr (Frist abgelaufen oder unbekannt)")
        urteil = str(body.get("urteil", "")).lower()
        grund = " ".join(str(body.get("grund", "")).split())[:200]
        quelle = str(a.get("quelle", ""))
        auftraege.pop(kennung, None)
        self._auftraege_schreiben(auftraege)
        if urteil not in ("ok", "verstoss", "unklar"):
            raise VerteilerError("RECHEN_URTEIL", "das Urteil muss ok, verstoss oder unklar sein")
        sicher = bool(body.get("sicher"))
        r = {"quelle": quelle, "urteil": urteil, "grund": grund, "credits": 0, "sicher": sicher}
        if urteil == "unklar":
            self._unklar[(quelle, geraet.kennung)] = self._jetzt()
            if len(self._unklar) > 5000:
                grenze = self._jetzt() - UNKLAR_PAUSE_S
                self._unklar = {k: v for k, v in self._unklar.items() if v >= grenze}
            self._log(f"UNKLAR {quelle} von {geraet.kennung}")
            if len({g for (q, g) in self._unklar if q == quelle}) >= UNKLAR_ADMIN:
                self.speicher.zurueckhalten(quelle)
                self._log(f"UNKLAR {quelle}: {UNKLAR_ADMIN} Geräte konnten es nicht beurteilen, wartet jetzt auf den Admin")
            return r
        self.bremse.erledigt(geraet.kennung, ("pruefen", quelle))
        g = self._geraete()
        if urteil == "ok":
            self.speicher.freigeben(quelle)
            haken = getattr(self, "freigegeben", None)
            if haken is not None:
                try:
                    haken(quelle)
                except Exception as exc:
                    self._log(f"FEHLER freigabe-haken {quelle}: {type(exc).__name__}")
        elif sicher:
            self.speicher.entfernen(quelle)
        else:
            self.speicher.zurueckhalten(quelle)
        self._geraet_zaehlen(g, geraet.kennung, credits=CREDITS_JE_BUENDEL)
        self._geraete_schreiben(g)
        r["credits"] = CREDITS_JE_BUENDEL
        self._log(f"URTEIL {quelle} von {geraet.kennung}: {urteil} {grund}")
        neu = self.geraet_pruefen_ohne_token(geraet.kennung)
        r["geraet"] = neu.kurz() if neu else geraet.kurz()
        return r

    @_gesperrt
    def geraet_verstoss(self, kennung: str, grund: str) -> bool:
        g = self._geraete()
        e = g.get(str(kennung))
        if not isinstance(e, dict):
            return False
        e["verstoesse"] = int(e.get("verstoesse", 0)) + 1
        if e["verstoesse"] >= VERSTOESSE_SPERRE and not e.get("gesperrt"):
            e["gesperrt"], e["sperrgrund"], e["gesperrt_seit"] = True, f"automatisch nach {e['verstoesse']} Verstößen gegen die Platzordnung: {grund}"[:200], _jetzt()
        self._geraete_schreiben(g)
        self._log(f"VERSTOSS {kennung} ({e['verstoesse']}) {grund}")
        return bool(e.get("gesperrt"))

    def geraet_pruefen_ohne_token(self, kennung: str) -> Geraet | None:
        e = self._geraete_lesen().get(kennung)
        if not isinstance(e, dict):
            return None
        return Geraet(kennung, str(e.get("name", "")), int(e.get("abschnitte", 0)), int(e.get("geprueft", 0)), int(e.get("abgelehnt", 0)), int(e.get("credits", 0)))


    def vektoren(self) -> list[tuple[str, list[float], bool]]:
        texte = {s: h for s, h, _ in self.alle_abschnitte()}
        return [(s, dequantisieren(bytes(e["_b"]), float(e.get("s", 1.0))) if isinstance(e.get("_b"), array) else [], bool(e.get("geprueft")))
                for s, e in self._im_index().items() if texte.get(s) == e.get("hash")]


__all__ = ["Verteiler", "VerteilerError", "Geraet", "MODELL_KENNUNG", "MODELL_SHA256", "DIMENSION", "BUENDEL", "PRUEFANTEIL", "TOLERANZ", "FRIST_S",
           "NACHKOMMA", "CREDITS_JE_BUENDEL", "pruefsumme", "vektor_pruefen", "kosinus", "abschnitt_hash", "quantisieren", "dequantisieren", "skizze", "index_eintrag",
           "VERTIEF_ART", "VERTIEF_PRUEF_ART", "VERTIEF_FRAGEN_MIN", "VERTIEF_FRAGEN_MAX", "vertiefung_pruefen_form"]
