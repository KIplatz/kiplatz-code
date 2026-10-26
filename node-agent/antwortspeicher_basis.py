# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import hashlib
import json
import re
import time
import unicodedata
import zlib


MIN_ANTWORT, MAX_ANTWORT = 20, 4000


FORMAT = "2"


MAX_FRAGE = 200


MAX_WOERTER = 20


AB_STUFE = 8.0


_FUELL = frozenset("""hat haben hatte hatten der die das den dem des ein eine einer eines einen einem ist sind war waren es gibt
bitte mal denn eigentlich ungefaehr zirka circa ca etwa so von in im am kannst koenntest du sag sage sagen weisst
wie wieviel""".split())


_ZEIT = frozenset("""heute morgen gestern uebermorgen jetzt aktuell aktuelle aktuellen derzeit momentan gerade neueste neuesten neuester
letzte letzten letzter naechste naechsten kommende kommenden diese dieses diesen dieser woche wochenende monat jahr wetter news nachrichten
schlagzeilen live preis preise kurs kurse uhr uhrzeit datum spiel spiele tabelle ergebnis ergebnisse stand""".split())


_PERSON = frozenset("""ich mein meine meinen meinem meiner meines mich mir wir unser unsere unseren unserem uns dein deine deinen deinem dich dir""".split())


_NIE = _ZEIT | _PERSON


_WANDEL = ("kost", "preis", "gebuehr", "maut", "vignett", "tarif", "ticket", "eintritt", "pflicht", "erlaubt", "verbot", "straf", "bussgeld",
           "frist", "tempolimit", "hoechstgeschwindigkeit", "vorgeschrieb", "gesetz", "mindestalter", "pickerl")


def wandelt_sich(woerter) -> bool:
    return any((x.startswith(s) if s == "kost" else s in x) for x in woerter for s in _WANDEL)


_GLEICH = {"einwohnerzahl": "einwohner", "bewohner": "einwohner", "einwohnern": "einwohner", "groesse": "gross", "groess": "gross",
          "hoehe": "hoch", "laenge": "lang", "tiefe": "tief", "breite": "breit", "alter": "alt", "gewicht": "schwer"}


_WEISS_NICHT = re.compile(r"wei(ß|ss) ich (noch )?nicht|keine (gesicherten |verlässlichen )?(informationen|angaben)|nicht (sicher )?sagen|kann ich nicht beantworten"
                          r"|\bI (?:do not|don't|don’t) (?:yet )?know\b|\bI (?:can't|can’t|cannot) (?:say|tell|answer)\b|\bnothing reliable\b", re.I)


def _woerter(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", str(text or "")).lower()
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"\bwie\s+viele?\b", "wieviel", t)
    t = re.sub(r"\bwieviele\b", "wieviel", t)
    return re.findall(r"[a-z0-9]+", t)


_VERGLEICH = frozenset(("als", "oder", "vs", "versus"))


def frage_taugt(nachrichten, *, frisch: bool = False, skill=None, zuhause=None) -> str:
    if frisch or skill or zuhause or not isinstance(nachrichten, list) or len(nachrichten) != 1:
        return ""
    n = nachrichten[0]
    if not isinstance(n, dict) or n.get("role") != "user" or not isinstance(n.get("content"), str):
        return ""
    text = n["content"].strip()
    if not text or len(text) > MAX_FRAGE:
        return ""
    w = _woerter(text)
    if not w or len(w) > MAX_WOERTER or any(x in _NIE for x in w) or wandelt_sich(w):
        return ""
    if any(x in _VERGLEICH for x in w):
        return ""
    kern = sorted({_GLEICH.get(x, x) for x in w if x not in _FUELL})
    return " ".join(kern) if len(kern) >= 2 else ""


def schluessel(vereinfacht: str) -> bytes:
    return hashlib.sha256(f"kiplatz-antwortspeicher/{FORMAT}/{vereinfacht}".encode("utf-8")).digest()


def kennung(schl: bytes) -> str:
    return hashlib.sha256(b"kiplatz-antwortspeicher-id/" + schl).hexdigest()[:20]


def _stufe(name) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*b\b", str(name or "").lower())
    return float(m.group(1).replace(",", ".")) if m else 0.0


WOERTLICH_WOERTER = 10


FREI_ARTEN = ("seite", "ortswissen", "berichtigung", "dokument", "pass", "berechnet", "abgefragt")


def _fremd(q) -> bool:
    return isinstance(q, dict) and (q.get("art") not in FREI_ARTEN or bool(q.get("privat")))


def wortliste(text: str) -> list[str]:
    return [w for w in re.findall(r"[0-9a-zäöüß]+", str(text or "").lower()) if not w.isdigit()]


def woertlich(antwort: str, quelle: str, n: int = WOERTLICH_WOERTER) -> bool:
    a = wortliste(antwort)
    q = wortliste(quelle)
    if len(a) < n or len(q) < n:
        return False
    stuecke = {tuple(q[i:i + n]) for i in range(len(q) - n + 1)}
    return any(tuple(a[i:i + n]) in stuecke for i in range(len(a) - n + 1))


_NACHGEBESSERT = re.compile(r"gestrichen|neu geantwortet|nicht ausgegeben|kein Rest|fehlte der Anfang|von jemand anderem", re.I)


def nachgebessert(lieferschein) -> bool:
    ls = lieferschein if isinstance(lieferschein, dict) else {}
    notizen = ls.get("belege") if isinstance(ls.get("belege"), list) else []
    return any(_NACHGEBESSERT.search(str(n)) for n in notizen)


MINDEST_BAU = "2026-10-26g"


def vor_mindest_bau(lieferschein) -> bool:
    ls = lieferschein if isinstance(lieferschein, dict) else {}
    return str(ls.get("bau") or "") < MINDEST_BAU


_SCHLUSS_ANGEBOT = re.compile(
    r"^(?:"
    r"(?:gibt es|hast du|haben sie)\b[^?]*\b(?:noch|sonst|weitere)\b[^?]*\?"
    r"|(?:möchtest|willst|brauchst) du\b[^?]*\b(?:noch|mehr|weitere|genauer|details?)\b[^?]*\?"
    r"|(?:kann|darf) ich (?:dir |ihnen )?(?:noch|sonst|weiter)\b[^?]*\?"
    r"|(?:lass mich wissen|sag (?:mir )?bescheid|frag (?:gern|ruhig))\b[^.!?]*[.!?]"
    r"|(?:is there|do you have|have you got)\b[^?]*\b(?:else|other|more|further)\b[^?]*\?"
    r"|(?:would|do) you (?:like|want)\b[^?]*\b(?:more|else|further|details?)\b[^?]*\?"
    r"|(?:can|may) i (?:help|assist)\b[^?]*\belse\b[^?]*\?"
    r"|anything else\b[^?]*\?"
    r"|(?:let me know|feel free to ask)\b[^.!?]*[.!?]"
    r")$", re.I)
_SATZ_GRENZE = re.compile(r"(?<=[.!?])\s+")


def ohne_schlussangebot(text: str) -> str:
    if not isinstance(text, str):
        return text
    absaetze = text.rstrip().split("\n")
    saetze = _SATZ_GRENZE.split(absaetze[-1].strip())
    if not _SCHLUSS_ANGEBOT.match(saetze[-1].strip()):
        return text
    rest = " ".join(saetze[:-1]).strip()
    neu = "\n".join(absaetze[:-1] + ([rest] if rest else [])).rstrip()
    return neu if neu.strip() else text


def _fassungen() -> dict[str, str]:
    from modell_katalog import MODELLE, fassung
    return {m.name: fassung(m.datei) for m in MODELLE.values()}


def fremde_fassung(lieferschein) -> bool:
    ls = lieferschein if isinstance(lieferschein, dict) else {}
    jetzt = _fassungen().get(str(ls.get("modell") or ""))
    return jetzt is not None and str(ls.get("fassung") or "") != jetzt


AUSLIEFERN_STAND = (f"2026-10-20 schlussangebot, 2026-10-26 weiss-nicht-en, {MINDEST_BAU}, fassung "
                    + ",".join(f"{n}={f or 'grund'}" for n, f in sorted(_fassungen().items())))


def schlussangebot(text) -> bool:
    return isinstance(text, str) and ohne_schlussangebot(text) != text


def ausliefern_ok(lieferschein, text=None) -> bool:
    return (not nachgebessert(lieferschein) and not vor_mindest_bau(lieferschein) and not fremde_fassung(lieferschein)
            and not schlussangebot(text) and not (isinstance(text, str) and _WEISS_NICHT.search(text)))


def antwort_taugt(text: str, lieferschein) -> bool:
    ls = lieferschein if isinstance(lieferschein, dict) else {}
    if not isinstance(text, str) or not MIN_ANTWORT <= len(text.strip()) <= MAX_ANTWORT or _WEISS_NICHT.search(text):
        return False
    if not ausliefern_ok(ls, text):
        return False
    if ls.get("gemacht") not in ("geantwortet", "nachgeschaut und geantwortet") or ls.get("skill") or ls.get("kleineres_modell") or ls.get("aus_speicher"):
        return False
    if ls.get("woertlich") or any(_fremd(q) and woertlich(text, str(q.get("text") or "")) for q in (ls.get("quellen_liste") or [])):
        return False
    if ls.get("stand") and stand_bis(ls) is None:
        return False
    if _stufe(ls.get("modell")) < AB_STUFE:
        return False
    pr = ls.get("pruefung") if isinstance(ls.get("pruefung"), dict) else {}
    try:
        if int(pr.get("rot", 1)) != 0 or int(pr.get("widersprueche", 1)) != 0 or int(pr.get("gruen", 0)) < 1:
            return False
    except (TypeError, ValueError):
        return False
    return isinstance(ls.get("quellen_liste"), list) and len(ls["quellen_liste"]) > 0


def stand_bis(lieferschein) -> float | None:
    from datetime import datetime, timezone
    st = (lieferschein or {}).get("stand") if isinstance(lieferschein, dict) else None
    if not isinstance(st, dict) or st.get("art") != "suche":
        return None
    try:
        bis = datetime.strptime(str(st.get("gilt_bis", "")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None
    return bis if bis > time.time() else None


PC_FORMAT = 1


def pc_nummer(schl: bytes) -> str:
    return hashlib.sha256(b"kiplatz-antwort-pc-finden/" + schl).hexdigest()[:32]


def _pc_schluessel(schl: bytes) -> bytes:
    return hashlib.sha256(b"kiplatz-antwort-pc-schluessel/" + schl).digest()


def pc_entpacken(schl: bytes, paket_eintrag, jetzt: float | None = None) -> dict | None:
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not isinstance(paket_eintrag, dict):
        return None
    try:
        if float(paket_eintrag.get("bis", 0)) < (time.time() if jetzt is None else jetzt):
            return None
        roh = base64.b64decode(str(paket_eintrag.get("c", "")), validate=True)
        d = json.loads(zlib.decompress(AESGCM(_pc_schluessel(schl)).decrypt(roh[:12], roh[12:], pc_nummer(schl).encode("ascii"))).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("f") != PC_FORMAT or not isinstance(d.get("text"), str) or not d["text"].strip():
        return None
    return {"text": d["text"], "lieferschein": d.get("lieferschein") if isinstance(d.get("lieferschein"), dict) else {}, "von": str(d.get("von", ""))[:80],
            "angelegt": float(d.get("angelegt") or 0), "kennung": kennung(schl)}
