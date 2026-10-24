# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import math
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sicher_schreiben

try:
    import app_core
except ImportError:
    import stat as _stat

    class _AppCore:
        class AppError(Exception):
            def __init__(self, code: str, detail: str) -> None:
                super().__init__(f"{code}: {detail}")
                self.code, self.detail = code, detail

        @staticmethod
        def _is_reparse(p: Path) -> bool:
            try:
                st = p.lstat()
            except OSError:
                return False
            return _stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)

        @staticmethod
        def ensure_plain_directory(p: Path) -> Path:
            if _AppCore._is_reparse(p):
                raise _AppCore.AppError("ORDNER_UNSICHER", f"{p.name} ist eine Verknüpfung")
            p.mkdir(parents=True, exist_ok=True)
            return p

    app_core = _AppCore()

DIRNAME = "wissen"
ARTEN = ("seite", "dokument", "pass", "nachgeschaut", "ortswissen", "berichtigung", "thema", "privatseite", "fenster")
ORTSWISSEN_MAX_TAGE = 366
PRIVATE_ARTEN = ("dokument", "pass", "thema", "nachgeschaut", "privatseite", "fenster")
GEHEIM_ARTEN = ("dokument", "pass", "thema", "fenster")
HAUSHALT = "haushalt"
FENSTER = "fenster"
UNGEPRUEFT = "ungeprueft"
ZURUECKGEHALTEN = "zurueckgehalten"
ENDUNGEN = (".txt", ".md", ".html", ".htm")
MAX_SEITE = 2 * 1024 * 1024
MAX_DATEI = 1024 * 1024
MAX_DATEIEN = 200
ABGLEICH_S = 5.0
MAX_TEXT = 400_000
ABSCHNITT_ZEICHEN = 700
TREFFER = 4
SEITEN_TIMEOUT_S = 15.0
_UA = "KIplatz/1.0 (+https://kiplatz.at/urheberrecht/)"

_STOPP = set("""der die das den dem des ein eine einer eines einem einen und oder aber auch nicht ist sind war waren wird werden
wurde wurden hat haben hatte hatten kann können konnte soll sollen muss müssen darf dürfen ich du er sie es wir ihr sie mich dich
sich uns euch mir dir ihm ihr ihnen mein dein sein unser euer in im an am auf aus bei mit nach von vor zu zum zur über unter für
durch gegen ohne um bis als wie was wer wo wann warum welche welcher welches dass ob wenn weil denn dann noch nur schon sehr
mehr viel viele man hier dort da so also etwas nichts alle alles kein keine keinen keinem keiner jetzt heute morgen gibt gib mir
bitte kurz sag sage erklär erkläre weißt weisst
fuer ueber koennen koennte muessen duerfen waere wuerde wuerden moechte moechten""".split())


class WissenError(app_core.AppError):
    pass


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


MAX_GUELTIG_TAGE = 30


def gueltig_pruefen(gueltig_bis: str, *, hoechstens_tage: int = MAX_GUELTIG_TAGE) -> str:
    g = (gueltig_bis or "").strip()
    if not g:
        return ""
    try:
        t = datetime.strptime(g, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise WissenError("WISSEN_GUELTIG", "die Gültigkeit ist nicht lesbar") from None
    if t > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=hoechstens_tage):
        raise WissenError("WISSEN_GUELTIG", f"länger als {hoechstens_tage} Tage wird das nicht gemerkt")
    return g


_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORT = re.compile(r"[a-z0-9]+")
_BEIWERK = re.compile(r"==\s*(Einzelnachweise|Weblinks|Literatur|Anmerkungen|Siehe auch|Quellen|Belege)\s*==")


def ist_beiwerk(text: str) -> bool:
    m = _BEIWERK.search(text or "")
    return bool(m) and m.start() < 80


def ohne_beiwerk(text: str) -> str:
    m = _BEIWERK.search(text or "")
    return (text[: m.start()].rstrip() if m else text)


def abschnitt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def woerter(text: str) -> list[str]:
    out = []
    for w in _WORT.findall(text.lower().translate(_UMLAUT)):
        if len(w) < 3 or w in _STOPP:
            continue
        for _ in range(3):
            for end in ("ungen", "ung", "en", "er", "es", "em", "e", "s", "n"):
                if len(w) - len(end) >= 4 and w.endswith(end):
                    w = w[: -len(end)]
                    break
        out.append(w)
    return out


_ZAHL = r"\d[\d.,]*\s*"
_MASSE = (
    (r"\bwie\s+lang\b|\bwie\s+weit\b|\bl(?:ä|ae)nge\b|\bentfernung\b|\bdistanz\b|\bstrecke\b",
     _ZAHL + r"(?:km|kilometer\w*|meter\w*|m|cm|mm|meilen)\b", r"l[äa]nge|entfern|strecke|distanz|kilometer"),
    (r"\bwie\s+lange\b|\bdauer(?:t|n)?\b|\bwie\s+viel\s+zeit\b",
     _ZAHL + r"(?:sekunden?|minuten?|min|stunden?|std|h|tage?n?|wochen?|monate?n?|jahre?n?)\b", r"dauer|stunden|minuten|tage\b"),
    (r"\bwie\s+(?:hoch|tief)\b|\bh[öo]he\b|\btiefe\b|\bseeh[öo]he\b",
     _ZAHL + r"(?:m|meter\w*|km|ft|fu(?:ß|ss))\b", r"h[öo]he|tiefe|meter"),
    (r"\bwie\s+gro(?:ß|ss)\b|\bfl[äa]che\b",
     _ZAHL + r"(?:km²|km2|m²|m2|quadratkilometer\w*|quadratmeter\w*|hektar|ha)\b|" + _ZAHL + r"(?:km²|m²)", r"fl[äa]che|quadrat|hektar"),
    (r"\bwie\s+schwer\b|\bgewicht\b|\bwiegt\b",
     _ZAHL + r"(?:kg|kilogramm|g|gramm|t|tonnen?)\b", r"gewicht|wiegt|kilogramm|tonnen"),
    (r"\bwie\s+(?:viel|teuer)\b.{0,40}\b(?:kost|preis|euro|geld)|\bwas\s+kostet\b|\bpreis(?:e|es)?\b|\bkosten\b",
     _ZAHL + r"(?:€|euro\b|eur\b|cent\b|dollar\b|\$|franken\b|chf\b)|(?:€|eur\b|\$)\s*\d", r"preis|kostet|kosten|euro\b"),
    (r"\bwie\s+viele?\b|\banzahl\b|\beinwohner\w*\b",
     r"\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{5,}\b|\b\d+(?:[.,]\d+)?\s*(?:millionen|mio\b|tausend|milliarden)|"
     r"\b\d[\d.,]*\s*(?:einwohner\w*|menschen|personen|mitglieder\w*|stück|prozent|%)", r"anzahl|einwohner|insgesamt"),
    (r"\bwann\b|\bseit\s+wann\b|\bin\s+welchem\s+jahr\b|\bwie\s+alt\b|\bdatum\b",
     r"\b(?:1[0-9]{3}|20[0-9]{2})\b|\b\d{1,2}\.\s*(?:januar|jänner|februar|feber|märz|april|mai|juni|juli|august|september|oktober|november|dezember|\d{1,2}\.)",
     r"gegründet|seit|eröffnet|geboren|jahr"),
)
_MASSE_RE = tuple((re.compile(f, re.I), re.compile(z, re.I), re.compile(w, re.I)) for f, z, w in _MASSE)


_SATZ_ENDE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"(])|\n+")


_MASS_FRAGEWOERTER = frozenset(woerter("lang lange weit hoch tief groß gross schwer viel viele teuer alt wann kostet kosten dauert dauer"))


def mass_punkte(frage: str, pflicht: str | None = None):
    arten = [(z, w) for f, z, w in _MASSE_RE if f.search(str(frage or ""))]
    if not arten:
        return None
    fw = set(woerter(frage)) - _MASS_FRAGEWOERTER
    pf = set(woerter(pflicht)) if pflicht else set()

    def punkte(text: str) -> float:
        best = 0.0
        for satz in _SATZ_ENDE.split(str(text or "")):
            if any(z.search(satz) for z, _w in arten):
                ws = set(woerter(satz))
                best = max(best, 1.0 if pf and not (pf & ws) else 1.0 + len(fw & ws))
            elif best < 0.5 and any(w.search(satz) for _z, w in arten):
                best = 0.5
        return best
    return punkte


_ADRESSE = re.compile(
    r"(?<![\w@])(?:https?://)?(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:at|de|ch|com|org|net|eu|info|io|li|it|fr|nl|uk|us|edu|gov|tv|me|app|dev)(?::\d{2,5})?(?:/[^\s\"'<>()\[\]]*)?",
    re.IGNORECASE,
)
MAX_ADRESSEN_JE_FRAGE = 2


def adressen_in_text(text: str) -> list[str]:
    out: list[str] = []
    for m in _ADRESSE.finditer(text or ""):
        a = m.group(0).rstrip(".,;:!?")
        if "." not in a.split("://")[-1].split("/")[0]:
            continue
        if a.lower() not in [x.lower() for x in out]:
            out.append(a)
        if len(out) >= MAX_ADRESSEN_JE_FRAGE:
            break
    return out


def abschnitte(text: str, *, zeichen: int = ABSCHNITT_ZEICHEN) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    stuecke: list[str] = []
    aktuell = ""
    for absatz in re.split(r"\n\s*\n", text):
        absatz = absatz.strip()
        if not absatz:
            continue
        for satz in re.split(r"(?<=[.!?:])\s+", absatz):
            if aktuell and len(aktuell) + len(satz) + 1 > zeichen:
                stuecke.append(aktuell.strip())
                aktuell = ""
            aktuell += (" " if aktuell else "") + satz
        if aktuell and len(aktuell) > zeichen * 0.6:
            stuecke.append(aktuell.strip())
            aktuell = ""
    if aktuell.strip():
        stuecke.append(aktuell.strip())
    return stuecke


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.teile: list[str] = []
        self.titel = ""
        self.titel_liste: list[str] = []
        self._still = 0
        self._in_titel = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside"):
            self._still += 1
        if tag == "title" and not self._still:
            self._in_titel = True
            self.titel_liste.append("")
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"):
            self.teile.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside") and self._still:
            self._still -= 1
        if tag == "title":
            self._in_titel = False
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"):
            self.teile.append("\n")

    def handle_data(self, data):
        if self._in_titel:
            self.titel_liste[-1] += data
        elif not self._still:
            self.teile.append(data)


def html_zu_text(roh: str) -> tuple[str, str]:
    p = _Text()
    p.feed(roh)
    text = html.unescape("".join(p.teile))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    titel = max((" ".join(t.split()) for t in p.titel_liste), key=len, default="")
    return titel, text


_ROBOTS_NAME = "KIplatz"
_ROBOTS_NAME_ALT = "CommunityAI-Wissen"
_ROBOTS_TTL_S = 3600
_robots: dict[str, tuple[float, object, str, list]] = {}
KI_PROGRAMME = ("GPTBot", "ChatGPT-User", "OAI-SearchBot", "CCBot", "Google-Extended", "GoogleOther", "ClaudeBot", "Claude-Web", "anthropic-ai",
                "Applebot-Extended", "Bytespider", "PerplexityBot", "meta-externalagent", "FacebookBot", "cohere-ai", "Amazonbot", "Diffbot",
                "Timpibot", "AI2Bot", "Omgilibot", "ImagesiftBot", "YouBot", "MistralAI-User", _ROBOTS_NAME, "KIplatzBot", _ROBOTS_NAME_ALT, "*")
LESER_FUER_PERSONEN = (_ROBOTS_NAME, "KIplatzBot", _ROBOTS_NAME_ALT, "*", "ChatGPT-User", "OAI-SearchBot", "Claude-User", "Claude-SearchBot",
                       "Claude-Web", "Perplexity-User", "PerplexityBot", "MistralAI-User")
_NOAI = re.compile(r"\b(noai|noimageai)\b", re.I)


def _http_status(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    return int(code) if isinstance(code, int) else None


def _host_regeln(host: str, oeffner) -> tuple[object, str, list]:
    import urllib.robotparser
    jetzt = time.time()
    eintrag = _robots.get(host)
    if eintrag is not None and jetzt - eintrag[0] <= _ROBOTS_TTL_S:
        return eintrag[1], eintrag[2], eintrag[3]
    parser, aus, tdm = None, "", []
    try:
        req = urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": _UA, "Accept": "text/plain"})
        with oeffner(req, timeout=5) as r:
            art = (r.headers.get("Content-Type") or "").lower()
            roh = r.read(500_000)
        if art.startswith("text/plain") or not art:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(roh.decode("utf-8", "replace").splitlines())
    except WissenError as exc:
        aus = f"robots.txt nicht lesbar ({exc.detail})"
    except Exception as exc:
        st = _http_status(exc)
        if st is None or st >= 500:
            aus = "robots.txt nicht erreichbar" if st is None else f"robots.txt meldet Fehler {st}"
    if not aus:
        try:
            req = urllib.request.Request(f"https://{host}/.well-known/tdmrep.json", headers={"User-Agent": _UA, "Accept": "application/json"})
            with oeffner(req, timeout=4) as r:
                regeln = json.loads(r.read(200_000).decode("utf-8", "replace"))
            tdm = [x for x in (regeln if isinstance(regeln, list) else [regeln]) if isinstance(x, dict)]
        except Exception:
            tdm = []
    _robots[host] = (jetzt - (_ROBOTS_TTL_S - 300) if aus else jetzt, parser, aus, tdm)
    return parser, aus, tdm


def _tdm_passt(ort: str, pfad: str) -> bool:
    ort = str(ort or "").strip() or "/"
    if ort in ("/", "*", "/*"):
        return True
    muster = "^" + ".*".join(re.escape(t) for t in ort.split("*"))
    return bool(re.match(muster, pfad or "/"))


def vorbehalt(adresse: str, *, oeffner=None, fuer_frage: bool = False) -> str:
    oeffner = oeffner or __import__("datenfluss").oeffner("Website lesen")
    teile = urllib.parse.urlsplit(adresse)
    host = teile.netloc.lower()
    if not host:
        return ""
    parser, aus, tdm = _host_regeln(host, oeffner)
    if aus:
        return aus
    if parser is not None:
        for name in (LESER_FUER_PERSONEN if fuer_frage else KI_PROGRAMME):
            try:
                if not parser.can_fetch(name, adresse):
                    return f"robots.txt sperrt {name}"
            except Exception:
                return "robots.txt nicht lesbar"
    for r in tdm:
        if str(r.get("tdm-reservation", "0")).strip() == "1" and _tdm_passt(r.get("location", ""), teile.path):
            return "Vorbehalt in tdmrep.json"
    return ""


def vorbehalt_in_seite(kopf, roh: str) -> str:
    def k(name: str) -> str:
        try:
            return str(kopf.get(name) or "")
        except Exception:
            return ""
    if _NOAI.search(k("X-Robots-Tag")) or k("tdm-reservation").strip() == "1":
        return "Vorbehalt im Kopf der Seite"
    for m in re.finditer(r"<meta\b[^>]*>", (roh or "")[:300_000], re.I):
        tag = m.group(0)
        name = re.search(r"name\s*=\s*[\"']?([\w-]+)", tag, re.I)
        if not name:
            continue
        n = name.group(1).lower()
        inhalt = re.search(r"content\s*=\s*[\"']?([^\"'>]*)", tag, re.I)
        c = inhalt.group(1) if inhalt else ""
        if n == "tdm-reservation" and c.strip() == "1":
            return "Vorbehalt in der Seite"
        if (n == "robots" or n.endswith("bot") or n in ("googlebot-news",)) and _NOAI.search(c):
            return "Vorbehalt in der Seite"
    return ""


def robots_erlaubt(adresse: str, *, oeffner=None) -> bool:
    return not vorbehalt(adresse, oeffner=oeffner)


class _UmleitungPruefen(urllib.request.HTTPRedirectHandler):

    def __init__(self, pruefer) -> None:
        super().__init__()
        self._pruefer = pruefer

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not str(newurl).lower().startswith("https://"):
            raise WissenError("WISSEN_ADRESSE", "die Seite leitet auf eine unverschlüsselte Adresse um")
        self._pruefer(str(newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def nur_oeffentlich(adresse: str) -> None:
    try:
        teile = urllib.parse.urlsplit(adresse if "://" in adresse else "https://" + adresse)
        host = teile.hostname or ""
        infos = socket.getaddrinfo(host, teile.port or 443, proto=socket.IPPROTO_TCP)
    except (ValueError, OSError):
        raise WissenError("WISSEN_ADRESSE", f"„{adresse.strip()[:80]}“ gibt es nicht (die Adresse lässt sich nicht auflösen); Tippfehler? Meist heißt es zum Beispiel firma.at oder firma.com") from None
    if not host or host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        raise WissenError("WISSEN_ADRESSE", "nur öffentliche Websites")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            raise WissenError("WISSEN_ADRESSE", "nur öffentliche Websites, keine internen Adressen")


def seite_holen(adresse: str, *, oeffner=None, pruefer=None, fuer_frage: bool = False) -> tuple[str, str, str]:
    if oeffner is None and pruefer is not None:
        opener = urllib.request.build_opener(_UmleitungPruefen(pruefer))
        oeffner = lambda req, timeout=None: opener.open(req, timeout=timeout)
    oeffner = oeffner or __import__("datenfluss").oeffner("Website lesen")
    adresse = adresse.strip()
    if not adresse.lower().startswith("https://"):
        if adresse.lower().startswith("http://"):
            raise WissenError("WISSEN_ADRESSE", "nur verschlüsselte Adressen (https://) werden gelesen")
        adresse = "https://" + adresse
    if any(ch in adresse for ch in " \n\t\"'<>"):
        raise WissenError("WISSEN_ADRESSE", "das sieht nicht wie eine Adresse aus")
    grund = vorbehalt(adresse, oeffner=oeffner, fuer_frage=fuer_frage)
    if grund:
        raise WissenError("WISSEN_ROBOTS", f"diese Website sagt Nein zu KI ({grund}), darum liest KIplatz sie nicht; bitte selbst dort nachlesen")
    req = urllib.request.Request(adresse, headers={"User-Agent": _UA, "Accept": "text/html, text/plain;q=0.9"})
    try:
        with oeffner(req, timeout=SEITEN_TIMEOUT_S) as r:
            kopf = r.headers
            art = (r.headers.get("Content-Type") or "").lower()
            if not (art.startswith("text/html") or art.startswith("text/plain")):
                raise WissenError("WISSEN_ART", f"die Seite ist kein Text ({art.split(';')[0] or 'unbekannt'})")
            endgueltig = str(getattr(r, "url", adresse) or adresse)
            if not endgueltig.lower().startswith("https://"):
                raise WissenError("WISSEN_ADRESSE", "die Seite leitet auf eine unverschlüsselte Adresse um")
            roh = r.read(MAX_SEITE + 1)
    except WissenError:
        raise
    except Exception as exc:
        raise WissenError("WISSEN_HOLEN", f"die Seite ließ sich nicht lesen ({type(exc).__name__})") from None
    if len(roh) > MAX_SEITE:
        raise WissenError("WISSEN_GROSS", "die Seite ist größer als 2 MB")
    text_roh = roh.decode("utf-8", "replace")
    grund = vorbehalt_in_seite(kopf, text_roh if art.startswith("text/html") else "")
    if grund:
        raise WissenError("WISSEN_ROBOTS", f"diese Website sagt Nein zu KI ({grund}), darum liest KIplatz sie nicht; bitte selbst dort nachlesen")
    if art.startswith("text/html"):
        titel, text = html_zu_text(text_roh)
        angebote = angebote_aus_seite(text_roh) if fuer_frage else ""
        if angebote:
            text = angebote + "\n\n" + text
    else:
        titel, text = "", text_roh.strip()
    if len(text) < 40:
        raise WissenError("WISSEN_LEER", "auf der Seite steht fast kein lesbarer Text")
    return endgueltig, titel or endgueltig, text[:MAX_TEXT]


ANGEBOTE_KOPF = "Angebote laut den Produktdaten dieser Seite"
ANGEBOTE_MAX = 25
MEHRERE_HAENDLER = "mehrere Händler zusammen"
ANGEBOTE_KNOTEN = 2000


def _ld_bloecke(roh: str) -> list[str]:
    klein, aus, p = roh.lower(), [], 0
    while len(aus) < 20:
        a = klein.find("<script", p)
        if a < 0:
            break
        e = klein.find(">", a)
        if e < 0:
            break
        z = klein.find("</script", e)
        if z < 0:
            break
        if "application/ld+json" in klein[a:e]:
            aus.append(roh[e + 1:z])
        p = z + 8
    return aus


def _betrag(wert) -> str:
    s = str(wert or "").strip().replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d+,\d{1,2}", s):
        s = s.replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        return ""
    return f"{x:.2f}".replace(".", ",") if 0 < x < 10_000_000 else ""


def angebote_aus_seite(roh: str) -> str:
    roh = (roh or "")[:MAX_SEITE]
    zeilen: list[str] = []
    name = ""

    def knoten(d):
        offen, n = [d], 0
        while offen and n < ANGEBOTE_KNOTEN:
            x = offen.pop(0)
            n += 1
            if isinstance(x, list):
                offen[:0] = x
            elif isinstance(x, dict):
                yield x
                g = x.get("@graph")
                if isinstance(g, (list, dict)):
                    offen.insert(0, g)

    for block in _ld_bloecke(roh):
        try:
            daten = json.loads(block.strip())
        except (ValueError, RecursionError):
            continue
        for k in knoten(daten):
            typ = k.get("@type")
            if "Product" not in (typ if isinstance(typ, list) else [typ]) or not k.get("offers"):
                continue
            name = " ".join(str(k.get("name") or "").split())[:120]
            angebote = k["offers"] if isinstance(k["offers"], list) else [k["offers"]]
            for o in angebote:
                if not isinstance(o, dict):
                    continue
                einzeln = o.get("offers") if isinstance(o.get("offers"), list) else []
                if einzeln:
                    angebote += einzeln
                    continue
                preis = _betrag(o.get("price") or o.get("lowPrice"))
                if not preis:
                    continue
                waehrung = str(o.get("priceCurrency") or "").strip()[:3]
                verkaeufer = o.get("seller") if isinstance(o.get("seller"), dict) else {}
                wer = " ".join(str(verkaeufer.get("name") or "").split())[:60] or (
                    MEHRERE_HAENDLER if "AggregateOffer" in str(o.get("@type")) else "diese Seite")
                da = "lieferbar" if "InStock" in str(o.get("availability") or "") else ""
                bis = _betrag(o.get("highPrice"))
                betrag = f"{preis} bis {bis}" if bis and bis != preis else preis
                zeilen.append(f"- {wer}: {betrag} {waehrung}".rstrip() + (f", {da}" if da else ""))
            if zeilen:
                break
        if zeilen:
            break
    if not zeilen:
        def mikro(feld: str, wert: str = r"[\d.,]+") -> list[str]:
            out = []
            for m in re.finditer(r"<[^<>]*\bitemprop\s*=\s*[\"']?" + feld + r"\b[^<>]*>", roh, re.I):
                c = re.search(r"\bcontent\s*=\s*[\"']?(" + wert + ")", m.group(0), re.I)
                if c:
                    out.append(c.group(1))
            return out
        preise = [p for p in map(_betrag, mikro("price")) if p]
        waehrung = next(iter(mikro("priceCurrency", r"[A-Za-z]{3}")), "").upper()
        tief, hoch = [p for p in map(_betrag, mikro("lowPrice")) if p][:1], [p for p in map(_betrag, mikro("highPrice")) if p][:1]
        anzahl = next(iter(mikro("offerCount", r"\d+")), "")
        werte = sorted({float(p.replace(",", ".")) for p in preise + tief + hoch})
        if (tief or anzahl) and werte:
            von, bis = (tief or [f"{werte[0]:.2f}".replace(".", ",")])[0], (hoch or [f"{werte[-1]:.2f}".replace(".", ",")])[0]
            zeilen.append(f"- {MEHRERE_HAENDLER}: {von} bis {bis} {waehrung}".rstrip() + (f", {anzahl} Angebote" if anzahl else ""))
        elif preise:
            zeilen.append(f"- diese Seite: {preise[0]} {waehrung}".rstrip())
    if not zeilen:
        return ""
    zeilen = list(dict.fromkeys(zeilen))[:ANGEBOTE_MAX]
    return f"{ANGEBOTE_KOPF}" + (f" (Produkt „{name}“)" if name else "") + ":\n" + "\n".join(zeilen)


@dataclass(frozen=True)
class Quelle:
    kennung: str
    art: str
    titel: str
    adresse: str
    datum: str
    zeichen: int
    gueltig_bis: str = ""
    status: str = ""
    fachgebiet: str = ""

    @property
    def privat(self) -> bool:
        return self.art in PRIVATE_ARTEN

    @property
    def freigegeben(self) -> bool:
        return self.status not in (UNGEPRUEFT, ZURUECKGEHALTEN)

    def gueltig(self, jetzt: str | None = None) -> bool:
        return not self.gueltig_bis or self.gueltig_bis > (jetzt or _jetzt())

    def kurz(self) -> dict:
        d = {"kennung": self.kennung, "art": self.art, "titel": self.titel, "adresse": self.adresse, "datum": self.datum, "zeichen": self.zeichen, "privat": self.art in GEHEIM_ARTEN}
        if self.gueltig_bis:
            d["gueltig_bis"] = self.gueltig_bis
        if self.status:
            d["status"] = self.status
        if self.fachgebiet:
            d["fachgebiet"] = self.fachgebiet
        return d


def kennung_fuer(art: str, adresse_oder_titel: str) -> str:
    return hashlib.sha256((art + "|" + adresse_oder_titel).encode("utf-8")).hexdigest()[:12]


def quelle_aus(d: dict) -> Quelle:
    return Quelle(str(d["kennung"]), str(d["art"]), str(d["titel"]), str(d.get("adresse", "")), str(d["datum"]), int(d["zeichen"]), str(d.get("gueltig_bis") or ""), str(d.get("status") or ""),
                  str(d.get("fachgebiet") or "") if str(d.get("fachgebiet") or "") in FACHGEBIETE else "")


FACHGEBIETE = ("programmieren", "web", "ki", "linux", "schule", "aemter", "geld", "kochen", "garten")
FACH_FAKTOR = 1.5
FACH_BREITE = 4


def fachgebiete_pruefen(roh) -> list[str]:
    if not isinstance(roh, (list, tuple)):
        return []
    da = {x for x in roh if isinstance(x, str)}
    return [f for f in FACHGEBIETE if f in da]


def fachgebiet_gewichten(tr: "list[Treffer]", fachgebiete, *, n: int | None = None, faktor: float = FACH_FAKTOR) -> "list[Treffer]":
    fg = set(fachgebiete or ())
    out = list(tr)
    if fg:
        out = [Treffer(t.quelle, t.text, round(t.punkte * faktor, 3)) if t.quelle.fachgebiet in fg else t for t in out]
        out.sort(key=lambda t: (t.punkte, t.quelle.fachgebiet in fg), reverse=True)
    return out if n is None else out[:n]


@dataclass(frozen=True)
class Treffer:
    quelle: Quelle
    text: str
    punkte: float


class Wissensspeicher:

    def __init__(self, base_dir: Path) -> None:
        self.dir = Path(base_dir) / DIRNAME
        self.quellen_dir = self.dir / "quellen"
        self._cache: dict[str, tuple[float | str, Quelle, list[str], list[list[str]], list[str]]] = {}
        self._gewichte: tuple[tuple, dict[str, int], float, int] | None = None
        self.kalt = None
        self.wortindex = None
        self._abgleichen = 0.0


    def _pfad(self, kennung: str) -> Path:
        return self.quellen_dir / f"{kennung}.json"

    def hinzufuegen(self, art: str, titel: str, adresse: str, text: str, *, gueltig_bis: str = "", status: str = "", fachgebiet: str = "") -> Quelle:
        if art not in ARTEN:
            raise WissenError("WISSEN_ART", "unbekannte Quellenart")
        text = (text or "").strip()[:MAX_TEXT]
        if len(text) < 20:
            raise WissenError("WISSEN_LEER", "zu wenig Text, um es zu merken")
        titel = " ".join((titel or adresse or "ohne Titel").split())[:160]
        adresse = (adresse or "").strip()[:500]
        gueltig_bis = gueltig_pruefen(gueltig_bis, hoechstens_tage=ORTSWISSEN_MAX_TAGE if art == "ortswissen" else MAX_GUELTIG_TAGE)
        q = Quelle(kennung_fuer(art, adresse or titel), art, titel, adresse, _jetzt(), len(text), gueltig_bis, UNGEPRUEFT if status == UNGEPRUEFT else "",
                   str(fachgebiet or "") if str(fachgebiet or "") in FACHGEBIETE else "")
        app_core.ensure_plain_directory(self.quellen_dir)
        sicher_schreiben.json_datei(self._pfad(q.kennung), {**q.kurz(), "text": text}, indent=1)
        self._cache.pop(q.kennung, None)
        self._index_datei(q.kennung)
        return q

    def verlaengern(self, kennung: str, gueltig_bis: str) -> Quelle | None:
        p = self._pfad(re.sub(r"[^0-9a-f]", "", str(kennung))[:12])
        if not p.is_file():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if d.get("art") != "ortswissen":
            return None
        d["gueltig_bis"] = gueltig_pruefen(gueltig_bis, hoechstens_tage=ORTSWISSEN_MAX_TAGE)
        sicher_schreiben.json_datei(p, d, indent=1)
        self._cache.pop(d.get("kennung", ""), None)
        self._index_datei(p.stem)
        return quelle_aus(d)

    def entfernen(self, kennung: str) -> bool:
        kennung = re.sub(r"[^0-9a-f]", "", str(kennung))[:12]
        p = self._pfad(kennung)
        if not p.is_file():
            if self.kalt is not None and kennung in self.kalt.kalt_liste():
                self._cache.pop(kennung, None)
                self._index_weg(kennung)
                return bool(self.kalt.sperren(kennung))
            return False
        p.unlink()
        self._cache.pop(kennung, None)
        self._index_weg(kennung)
        return True


    def _index_datei(self, kennung: str) -> None:
        if self.wortindex is None:
            return
        p = self._pfad(kennung)
        if not p.is_file():
            self._index_weg(kennung)
            return
        if self._lesen(p) is not None:
            c = self._cache.pop(kennung, None)
            if c is not None:
                self.wortindex.aufnehmen(c[1], c[2], c[3], c[4], str(c[0]))

    def _index_weg(self, kennung: str) -> None:
        if self.wortindex is not None:
            self.wortindex.entfernen(kennung)

    def _abgleichen_gelegentlich(self) -> None:
        if time.time() - self._abgleichen >= ABGLEICH_S:
            self.abgleichen()

    def abgleichen(self) -> dict:
        if self.wortindex is None:
            return {}
        self._abgleichen = time.time()
        marken = self.wortindex.marken()
        soll: dict[str, str] = {}
        neu = weg = 0
        if self.quellen_dir.is_dir():
            for p in sorted(self.quellen_dir.glob("*.json")):
                try:
                    soll[p.stem] = str(p.stat().st_mtime)
                except OSError:
                    continue
        kalt: dict[str, str] = {}
        if self.kalt is not None:
            try:
                kalt = self.kalt.kalt_liste()
            except Exception:
                kalt = {}
        for kennung, scheibe in kalt.items():
            soll.setdefault(kennung, f"kalt:{scheibe}")
        for kennung, marke in soll.items():
            if marken.get(kennung) == marke:
                continue
            if marke.startswith("kalt:"):
                if kennung in marken:
                    self.wortindex.marke_setzen(kennung, marke)
                    continue
                r = self._lesen_kalt(kennung, marke[5:])
            else:
                r = self._lesen(self._pfad(kennung))
            if r is None:
                continue
            c = self._cache.pop(kennung, None)
            if c is not None:
                self.wortindex.aufnehmen(c[1], c[2], c[3], c[4], marke)
                neu += 1
        for kennung in set(marken) - set(soll):
            self.wortindex.entfernen(kennung)
            weg += 1
        return {"neu": neu, "weg": weg, **self.wortindex.stand()}

    def abschnitt(self, schluessel: str) -> tuple[Quelle, str] | None:
        try:
            kennung, nr = str(schluessel).rsplit(":", 1)
            nr = int(nr)
        except ValueError:
            return None
        if self.wortindex is not None:
            r = self.wortindex.abschnitt(kennung, nr)
            return (r[0], r[1]) if r else None
        for q, teile in self.alle():
            if q.kennung == kennung:
                return (q, teile[nr]) if 0 <= nr < len(teile) else None
        return None

    def _lesen_kalt(self, kennung: str, scheibe: str) -> tuple[Quelle, list[str]] | None:
        c = self._cache.get(kennung)
        marke = f"kalt:{scheibe}"
        if c and c[0] == marke:
            return c[1], c[2]
        try:
            roh = self.kalt.kalt_lesen(kennung) if self.kalt is not None else None
            if roh is None:
                return None
            d = json.loads(roh.decode("utf-8"))
            q = quelle_aus(d)
            teile = abschnitte(str(d.get("text", "")))
            kopf = woerter(q.titel + " " + q.adresse)
            self._cache[kennung] = (marke, q, teile, [kopf + woerter(t) for t in teile], [abschnitt_hash(t) for t in teile])
            return q, teile
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            return None

    def _lesen(self, p: Path) -> tuple[Quelle, list[str]] | None:
        try:
            mtime = p.stat().st_mtime
            c = self._cache.get(p.stem)
            if c and c[0] == mtime:
                return c[1], c[2]
            d = json.loads(p.read_text(encoding="utf-8"))
            q = quelle_aus(d)
            teile = abschnitte(str(d.get("text", "")))
            kopf = woerter(q.titel + " " + q.adresse)
            toks = [kopf + woerter(t) for t in teile]
            hashes = [abschnitt_hash(t) for t in teile]
            self._cache[p.stem] = (mtime, q, teile, toks, hashes)
            return q, teile
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def alle(self, *, auch_ungeprueft: bool = False) -> list[tuple[Quelle, list[str]]]:
        if self.wortindex is not None:
            self._abgleichen_gelegentlich()
            return self.wortindex.alle(auch_ungeprueft=auch_ungeprueft)
        return [(c[1], c[2]) for _s, c in self._alle_eintraege(auch_ungeprueft=auch_ungeprueft)]

    def _alle_eintraege(self, *, auch_ungeprueft: bool = False) -> list[tuple[str, tuple]]:
        out = []
        jetzt = _jetzt()
        heiss: set[str] = set()
        if self.quellen_dir.is_dir():
            for p in sorted(self.quellen_dir.glob("*.json")):
                heiss.add(p.stem)
                r = self._lesen(p)
                if r and r[0].gueltig(jetzt) and (auch_ungeprueft or r[0].freigegeben):
                    out.append((p.stem, self._cache[p.stem]))
        if self.kalt is not None:
            try:
                kalt = self.kalt.kalt_liste()
            except Exception:
                kalt = {}
            for kennung, scheibe in sorted(kalt.items()):
                if kennung in heiss:
                    continue
                r = self._lesen_kalt(kennung, scheibe)
                if r and r[0].gueltig(jetzt) and (auch_ungeprueft or r[0].freigegeben):
                    out.append((kennung, self._cache[kennung]))
        return out

    def alle_mit_woertern(self, *, auch_ungeprueft: bool = False) -> tuple[list[tuple[Quelle, list[str], list[list[str]]]], tuple]:
        e = self._alle_eintraege(auch_ungeprueft=auch_ungeprueft)
        return [(c[1], c[2], c[3]) for _s, c in e], tuple((s, c[0]) for s, c in e)

    def alle_mit_hash(self) -> list[tuple[Quelle, list[str], list[str]]]:
        if self.wortindex is not None:
            self._abgleichen_gelegentlich()
            return self.wortindex.alle(mit_hash=True)
        return [(c[1], c[2], c[4]) for _s, c in self._alle_eintraege()]

    def wort_gewichte(self, *, privat_erlaubt: bool = True) -> tuple[dict[str, int], float, int]:
        liste, sig = self.alle_mit_woertern()
        sig = sig + (bool(privat_erlaubt),)
        if self._gewichte is not None and self._gewichte[0] == sig:
            return self._gewichte[1], self._gewichte[2], self._gewichte[3]
        df: dict[str, int] = {}
        n = 0
        laenge = 0
        for q, teile, toks in liste:
            if not privat_erlaubt and q.privat:
                continue
            for t, w in zip(teile, toks):
                if ist_beiwerk(t):
                    continue
                n += 1
                laenge += len(w)
                for x in set(w):
                    df[x] = df.get(x, 0) + 1
        avg = laenge / n if n else 1.0
        self._gewichte = (sig, df, avg, n)
        return df, avg, n

    def idf(self, wort: str, *, privat_erlaubt: bool = True) -> float:
        if self.wortindex is not None:
            n, d = self.wortindex.anzahl_abschnitte(), self.wortindex.df(wort)
            return math.log(1 + (n - d + 0.5) / (d + 0.5)) if n else 1.0
        df, _avg, n = self.wort_gewichte(privat_erlaubt=privat_erlaubt)
        d = df.get(wort, 0)
        return math.log(1 + (n - d + 0.5) / (d + 0.5)) if n else 1.0

    def ungeprueft(self) -> list[tuple[Quelle, str]]:
        out = []
        for q, _teile in self.alle(auch_ungeprueft=True):
            if not q.freigegeben:
                try:
                    out.append((q, str(json.loads(self._pfad(q.kennung).read_text(encoding="utf-8")).get("text", ""))))
                except (OSError, ValueError):
                    continue
        return out

    def _status_setzen(self, kennung: str, status: str) -> bool:
        p = self._pfad(re.sub(r"[^0-9a-f]", "", str(kennung))[:12])
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if status:
            d["status"] = status
        else:
            d.pop("status", None)
        sicher_schreiben.json_datei(p, d, indent=1)
        self._cache.pop(p.stem, None)
        self._index_datei(p.stem)
        return True

    def art_von(self, kennung: str) -> str:
        try:
            d = json.loads(self._pfad(re.sub(r"[^0-9a-f]", "", str(kennung))[:12]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        return str(d.get("art", "")) if isinstance(d, dict) else ""

    def freigeben(self, kennung: str) -> bool:
        return self._status_setzen(kennung, "")

    def zurueckhalten(self, kennung: str) -> bool:
        return self._status_setzen(kennung, ZURUECKGEHALTEN)

    def aufraeumen(self) -> int:
        n = 0
        if not self.quellen_dir.is_dir():
            return 0
        jetzt = _jetzt()
        for p in list(self.quellen_dir.glob("*.json")):
            r = self._lesen(p)
            if r and r[0].gueltig_bis and not r[0].gueltig(jetzt):
                try:
                    p.unlink()
                    self._cache.pop(p.stem, None)
                    self._index_weg(p.stem)
                    n += 1
                except OSError:
                    pass
        return n

    def seiten_privat_machen(self) -> int:
        if self.wortindex is not None or not self.quellen_dir.is_dir():
            return 0
        n = 0
        for p in list(self.quellen_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if d.get("art") != "seite":
                continue
            d["art"], d["privat"] = "privatseite", False
            try:
                sicher_schreiben.json_datei(p, d, indent=1)
            except OSError:
                continue
            self._cache.pop(p.stem, None)
            n += 1
        return n

    def liste(self, *, privat: bool | None = None, auch_ungeprueft: bool = True) -> list[dict]:
        return [q.kurz() for q, _ in sorted(self.alle(auch_ungeprueft=auch_ungeprueft), key=lambda t: t[0].datum, reverse=True) if privat is None or q.privat == privat]

    def anzahl(self) -> int:
        if self.wortindex is not None:
            self._abgleichen_gelegentlich()
            return self.wortindex.anzahl_quellen()
        return len(self.liste(auch_ungeprueft=False))


    def seite_lesen(self, adresse: str, *, oeffner=None, namensnennung: str = "") -> Quelle:
        endgueltig, titel, text = seite_holen(adresse, oeffner=oeffner)
        zusatz = " ".join((namensnennung or "").split())[:120]
        return self.hinzufuegen("seite", f"{titel} ({zusatz})" if zusatz else titel, endgueltig, text)

    def ordner_lesen(self, ordner: Path, *, art: str = "dokument") -> list[Quelle]:
        ordner = Path(ordner)
        if app_core._is_reparse(ordner) or not ordner.is_dir():
            raise WissenError("WISSEN_ORDNER", "das ist kein gewöhnlicher Ordner")
        gelesen: list[Quelle] = []
        dateien = []
        for wurzel, unter, namen in os.walk(ordner):
            unter[:] = [u for u in sorted(unter) if not u.startswith(".") and not app_core._is_reparse(Path(wurzel) / u)]
            for n in sorted(namen):
                p = Path(wurzel) / n
                if p.suffix.lower() in ENDUNGEN and not app_core._is_reparse(p):
                    dateien.append(p)
            if len(dateien) > MAX_DATEIEN:
                raise WissenError("WISSEN_VIELE", f"mehr als {MAX_DATEIEN} Dateien; bitte einen kleineren Ordner wählen")
        for p in dateien:
            try:
                if p.stat().st_size > MAX_DATEI:
                    continue
                roh = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if p.suffix.lower() in (".html", ".htm"):
                titel, text = html_zu_text(roh)
                titel = titel or p.name
            else:
                titel, text = p.name, roh
            try:
                gelesen.append(self.hinzufuegen(art, titel, f"{ordner.name}/{p.relative_to(ordner).as_posix()}", text))
            except WissenError:
                continue
        return gelesen


    def suchen(self, frage: str, *, n: int = TREFFER, privat_erlaubt: bool | str = True) -> list[Treffer]:
        if privat_erlaubt == HAUSHALT:
            return [t for t in self.suchen(frage, n=n + 8, privat_erlaubt=True) if t.quelle.art != "pass"][:n]
        nur_art = "fenster" if privat_erlaubt == FENSTER else ""
        fw = woerter(frage)
        if not fw:
            return []
        if self.wortindex is not None and not nur_art:
            return self.wortindex.suchen(fw, n=n, privat_erlaubt=privat_erlaubt)
        liste, _sig = self.alle_mit_woertern()
        df, avg, N = self.wort_gewichte(privat_erlaubt=True if nur_art else privat_erlaubt)
        if not N:
            return []
        k1, b = 1.5, 0.75
        treffer = []
        for q, teile, toks in liste:
            if nur_art:
                if q.art != nur_art:
                    continue
            elif not privat_erlaubt and q.privat:
                continue
            for t, w in zip(teile, toks):
                if not w or ist_beiwerk(t):
                    continue
                self._bm25(q, t, w, fw, df, avg, N, k1, b, treffer)
        treffer.sort(key=lambda tr: tr.punkte, reverse=True)
        return treffer[:n]

    @staticmethod
    def _bm25(q, t, w, fw, df, avg, N, k1, b, treffer) -> None:
        tf: dict[str, int] = {}
        for x in w:
            tf[x] = tf.get(x, 0) + 1
        punkte = 0.0
        for x in set(fw):
            if x not in tf or x not in df:
                continue
            idf = math.log(1 + (N - df[x] + 0.5) / (df[x] + 0.5))
            punkte += idf * tf[x] * (k1 + 1) / (tf[x] + k1 * (1 - b + b * len(w) / avg))
        if punkte > 0:
            treffer.append(Treffer(q, t, round(punkte, 3)))

    def kontext(self, frage: str, *, n: int = TREFFER, privat_erlaubt: bool = True) -> tuple[str, list[dict]]:
        return kontext_bauen(self.suchen(frage, n=n, privat_erlaubt=privat_erlaubt))


def live_lesen(adresse: str, frage: str, *, n: int = TREFFER, oeffner=None, extra=None, fuer_frage: bool = False) -> tuple[Quelle, str, list[Treffer]]:
    endgueltig, titel, text = seite_holen(adresse, oeffner=oeffner, fuer_frage=fuer_frage)
    q = Quelle(hashlib.sha256(("seite|" + endgueltig).encode("utf-8")).hexdigest()[:12], "seite", titel, endgueltig, _jetzt(), len(text))
    if text.startswith(ANGEBOTE_KOPF):
        block, _, rest = text.partition("\n\n")
        teile = [block] + abschnitte(rest)
    else:
        teile = abschnitte(text)
    fw = set(woerter(frage))
    mass = mass_punkte(frage) if extra is None else None
    zusatz = [(float(extra(t)) if extra is not None else 0.0) + (mass(t) if mass is not None else 0.0) for t in teile]
    nach_wort = sorted(range(len(teile)), key=lambda i: -(len(fw & set(woerter(teile[i]))) + 2.0 * zusatz[i]))
    gewaehlt: list[int] = []
    vorn_frei = any(zusatz) if mass is None else any(z >= 1.0 for z in zusatz)
    for i in (list(range(min(2, len(teile)))) if not vorn_frei else []) + nach_wort:
        if i not in gewaehlt:
            gewaehlt.append(i)
        if len(gewaehlt) >= n:
            break
    return q, text, [Treffer(q, teile[i], round(float(len(fw & set(woerter(teile[i])))), 3)) for i in gewaehlt]


def treffer_mischen(*listen: list[Treffer], n: int = TREFFER) -> list[Treffer]:
    alle = sorted((t for liste in listen for t in liste), key=lambda t: t.punkte, reverse=True)
    out: list[Treffer] = []
    gesehen: set[tuple[str, str]] = set()
    for t in alle:
        k = (t.quelle.kennung, t.text[:80])
        if k in gesehen:
            continue
        gesehen.add(k)
        out.append(t)
        if len(out) >= n:
            break
    return out


def treffer_vereinen(wort: list[Treffer], bedeutung: list[Treffer], *, n: int = TREFFER, fachgebiete=None) -> list[Treffer]:
    fg = set(fachgebiete or ())
    punkte: dict[tuple[str, str], float] = {}
    obj: dict[tuple[str, str], Treffer] = {}
    for liste in (wort, bedeutung):
        for rang, t in enumerate(liste, 1):
            k = (t.quelle.kennung, t.text[:80])
            punkte[k] = punkte.get(k, 0.0) + (FACH_FAKTOR if t.quelle.fachgebiet in fg else 1.0) / (60 + rang)
            obj.setdefault(k, t)
    beste = sorted(punkte, key=lambda k: punkte[k], reverse=True)[:n]
    return [Treffer(obj[k].quelle, obj[k].text, round(punkte[k] * 100, 3)) for k in beste]


BERICHTIGUNG_TITEL = "Berichtigung eines Mitglieds"


def berichtigung_text(frage: str, alte_antwort: str, grund: str, vorschlag: str, *, datum: str = "") -> tuple[str, str]:
    frage = " ".join((frage or "").split())[:300]
    vorschlag = " ".join((vorschlag or "").split())[:1200]
    grund = " ".join((grund or "").split())[:600]
    alt = " ".join((alte_antwort or "").split())[:400]
    titel = f"{BERICHTIGUNG_TITEL}: {frage[:90]}"
    zeilen = [f"Frage: {frage}", f"So ist es richtig: {vorschlag}"]
    if grund:
        zeilen.append(f"Was an der alten Antwort nicht gepasst hat: {grund}")
    if alt:
        zeilen.append(f"Alte Antwort (gilt nicht mehr): {alt}")
    zeilen.append(f"Stand: {(datum or _jetzt())[:10]}")
    return titel, "\n".join(zeilen)


def kontext_bauen(tr: list[Treffer], *, live: set[str] | None = None) -> tuple[str, list[dict]]:
    if not tr:
        return "", []
    live = live or set()
    if True:
        zeilen = ["Auszüge aus dem Wissensspeicher der Community. Steht die Antwort darin, gib sie in eigenen Worten wieder "
                  "(nie ganze Sätze aus einem Auszug übernehmen; Zahlen, Namen und Daten genau so wie dort), "
                  "auch wenn es um Websites, Firmen, Personen oder Orte geht, die du sonst nicht kennst, und schreib hinter den Satz in Klammern "
                  "die Nummer, zum Beispiel (Quelle 2). Nie den Buchstaben N, immer die echte Nummer. "
                  "Einen Rat oder eine Angabe aus einem Auszug übernimmst du nur, wenn der Auszug von derselben Sache handelt wie die Frage; "
                  "was dort über etwas anderes steht (ein anderes Gerät, Industrieanlagen, ein anderes Land), gilt für die Antwort nicht. "
                  "Ist die Frage allgemein (ein Begriff, Fachwissen, Schulwissen, Alltagswissen, wie etwas funktioniert) und passen die Auszüge nicht dazu, "
                  "dann antworte aus deinem eigenen Wissen, in ganzen Sätzen, ohne Quellennummer, und erwähne die Auszüge dabei gar nicht "
                  "(nicht „das steht nicht in den Auszügen, aber“). Dasselbe gilt für Rechenaufgaben mit Zahlen aus der Frage: rechnen, nicht nachschlagen. "
                  "Nur bei Angaben, die sich ändern oder die nur eine bestimmte Quelle sicher weiß (Ergebnisse und Ereignisse von heute oder den letzten Tagen, "
                  "Preise, Termine, Öffnungszeiten, Gesetze, Fristen, eine bestimmte Firma, Website, ein bestimmtes Produkt, eine Person, die nicht in jedem "
                  "Lexikon steht, ein kleiner Ort), die nicht in den Auszügen stehen, schreib genau: „Das weiß ich noch nicht.“ "
                  "Lexikon- und Weltwissen (Einwohner großer Städte, Höhen, Jahreszahlen der Geschichte, bekannte Personen) sagst du auch ohne Auszug. "
                  "Erfinde nichts dazu, keine Namen, keine Produkte, keine Jahreszahlen, auch nicht, wenn ein Auszug ein ähnliches Wort enthält. "
                  "Passt ein Auszug nur im Namen, aber nicht im Ort, in der Zeit oder im Zusammenhang der Frage (eine andere Person, Firma oder Sache gleichen Namens), "
                  "dann ist das keine Antwort: Sag in einem Satz, dass du nur jemand oder etwas gleichen Namens von anderswo gefunden hast und nicht weißt, ob es dasselbe ist. Achte auf das Datum oben: Zeigt ein Auszug einen älteren Stand (eine frühere Saison, ein früheres Jahr, Termine, die schon vorbei sind), gib ihn nie als aktuell aus. Nimm den Auszug mit dem neuesten Stand; hat keiner den aktuellen Stand, sag in einem Satz, dass du nur einen älteren Stand gefunden hast, und von wann er ist. Schreib in der Antwort nie „Auszüge“ oder „Wissensspeicher“; die Person sieht keine Auszüge."]
        if any(t.quelle.kennung in live for t in tr):
            zeilen.append("Die mit „gerade live gelesen“ markierten Quellen kommen von der Website, die die Person genannt hat, und wurden soeben abgerufen. "
                          "Fragt die Person, was dort steht, was es dort Neues gibt oder was oben steht, dann fasse diese Auszüge kurz zusammen "
                          "(Überschriften und Themen genügen, in ganzen Sätzen, mit Quellennummer). Das ist dann keine Erfindung, sondern der Inhalt der Seite.")
        if any(t.quelle.art == "nachgeschaut" for t in tr):
            zeilen.append("Die mit „nachgeschaut“ markierten Quellen hat das Programm für genau diese Frage im Internet nachgeschaut (Wetterdienst, Nachrichtenfeed, Spielstände oder Suche). "
                          "Antworte daraus in ganzen Sätzen mit Quellennummer; bei Wetter nenne Tag, Ort, Höchst- und Tiefsttemperatur und ob es regnet; bei Schlagzeilen "
                          "die wichtigsten Überschriften; bei Spielständen und Spielplänen beide Mannschaften, Stand oder Uhrzeit und von wann der Stand ist, nur die Spiele, "
                          "nach denen gefragt wurde. Rechne nichts um und ergänze nichts, was dort nicht steht. Bei einer Ja-Nein-Frage („Regnet es morgen?“) "
                          "beginnt die Antwort mit Ja oder Nein, und zwar so, wie es zum Inhalt passt (kein Regen heißt Nein).")
        if any(t.quelle.art == "ortswissen" for t in tr):
            zeilen.append("Die mit „Ortswissen“ markierten Quellen hat ein Mitglied der Community über seinen Ort eingetragen (Öffnungszeiten, Gemeinde, Vereine, Ärzte, Bäder). "
                          "Sie sind für Fragen zu diesem Ort die beste Quelle: Antworte daraus in ganzen Sätzen mit Quellennummer und nenne den Stand, der dort steht. "
                          "Was dort nicht steht, weißt du nicht; erfinde keine Zeiten und keine Preise dazu.")
        if any(t.quelle.art == "berichtigung" for t in tr):
            zeilen.append("Die mit „Berichtigung“ markierten Quellen hat ein Mitglied geschrieben, nachdem eine frühere Antwort falsch war. "
                          "Passt die Berichtigung zur Frage, gilt sie vor allen anderen Auszügen und vor deinem eigenen Wissen: Antworte so, wie unter "
                          "„So ist es richtig“ steht, mit Quellennummer. Die alte Antwort darin wiederholst du nicht.")
        quellen = []
        for k, t in enumerate(tr, 1):
            marke = " – gerade live gelesen" if t.quelle.kennung in live else (" – nachgeschaut" if t.quelle.art == "nachgeschaut" else (" – Ortswissen" if t.quelle.art == "ortswissen" else (" – Berichtigung" if t.quelle.art == "berichtigung" else "")))
            stand = _stand_de(t.quelle)
            zeilen.append(f"\nQuelle {k}: {t.quelle.titel}" + (f" ({t.quelle.adresse})" if t.quelle.adresse and t.quelle.art not in GEHEIM_ARTEN else "") + marke + stand + f"\n{t.text}")
            quellen.append({"nummer": k, **t.quelle.kurz(), "punkte": t.punkte, "text": t.text})
        return "\n".join(zeilen), quellen


def _stand_de(q: "Quelle") -> str:
    d = (q.datum or "")[:10]
    if len(d) != 10:
        return ""
    wann = f"{d[8:10]}.{d[5:7]}.{d[:4]}"
    return (f", abgerufen am {wann}" if q.art in ("nachgeschaut", "live") else f", Stand {wann}")


WOCHENTAGE_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _jetzt_frager() -> datetime:
    try:
        import ki_laufzeit
        return ki_laufzeit.jetzt()
    except Exception:
        return datetime.now(timezone.utc).astimezone()


def _ortszeit_wort() -> str:
    try:
        import ki_laufzeit
        return "Ortszeit der fragenden Person" if ki_laufzeit.zone() is not None else "Ortszeit des Geräts"
    except Exception:
        return "Ortszeit des Geräts"


def zeit_zeile(jetzt: datetime | None = None) -> str:
    t = jetzt.astimezone() if jetzt else _jetzt_frager()
    return f"Heute ist {WOCHENTAGE_DE[t.weekday()]}, der {t.strftime('%d.%m.%Y')}, es ist {t.strftime('%H:%M')} Uhr ({_ortszeit_wort()}). Daraus ergeben sich Fragen nach Datum, Wochentag, Uhrzeit, Jahr oder Alter; rechne damit, nicht mit deinem Trainingsstand."


def datum_zeile(jetzt: datetime | None = None) -> str:
    t = jetzt.astimezone() if jetzt else _jetzt_frager()
    return f"Heute ist {WOCHENTAGE_DE[t.weekday()]}, der {t.strftime('%d.%m.%Y')}."


def uhrzeit_zeile(jetzt: datetime | None = None) -> str:
    t = jetzt.astimezone() if jetzt else _jetzt_frager()
    return (f"Es ist {t.strftime('%H:%M')} Uhr ({_ortszeit_wort()}). Aus Datum und Uhrzeit ergeben sich Fragen nach Datum, Wochentag, Uhrzeit, "
            "Jahr oder Alter; rechne damit, nicht mit deinem Trainingsstand.")


def ohne_doppelte(quellen: list[dict]) -> list[dict]:
    gesehen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for q in quellen:
        k = (str(q.get("titel", "")), str(q.get("adresse", "")))
        if k in gesehen:
            continue
        gesehen.add(k)
        out.append(q)
    return out


def benutzte_quellen(antwort: str, quellen: list[dict], auch_nummern: set[int] | None = None) -> list[dict]:
    nummern: set[int] = set(auch_nummern or ())
    for gruppe in re.findall(r"Quellen?\s*((?:\d+\s*(?:,|und|bis|&|\+)?\s*)+)", antwort or ""):
        nummern.update(int(n) for n in re.findall(r"\d+", gruppe))
    return ohne_doppelte([q for q in quellen if q["nummer"] in nummern])


def quellen_text_de(antwort: str, quellen: list[dict], anzahl_im_speicher: int, *, auch_nummern: set[int] | None = None) -> str:
    if not quellen:
        if anzahl_im_speicher == 0:
            return "aus dem Wissen des Modells, ohne Quelle. Der Wissensspeicher ist noch leer (Bereich „Wissen“)."
        return f"aus dem Wissen des Modells, ohne Quelle. Im Wissensspeicher ({anzahl_im_speicher} Quellen) passte nichts zur Frage."
    benutzt = benutzte_quellen(antwort, quellen, auch_nummern)
    if not benutzt:
        return "aus dem Wissen des Modells. Der Wissensspeicher hatte " + ", ".join(f"{q['titel']}" for q in ohne_doppelte(quellen)) + ", das Modell hat sie nicht benutzt."
    def gelesen(datum: str) -> str:
        d = str(datum or "")[:10]
        return f", gelesen am {d[8:10]}.{d[5:7]}.{d[:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else ""
    return " ".join(f"{q['titel']}" + (f" ({q['adresse']})" if q["adresse"] else "") + gelesen(q["datum"]) + "." for q in benutzt)


__all__ = ["DIRNAME", "Wissensspeicher", "Quelle", "Treffer", "WissenError", "woerter", "abschnitte", "html_zu_text", "seite_holen",
           "benutzte_quellen", "ohne_doppelte", "quellen_text_de", "treffer_mischen", "treffer_vereinen", "kontext_bauen", "adressen_in_text", "live_lesen",
           "kennung_fuer", "quelle_aus", "gueltig_pruefen", "UNGEPRUEFT", "ZURUECKGEHALTEN", "robots_erlaubt", "FACHGEBIETE", "FACH_FAKTOR", "FACH_BREITE", "fachgebiete_pruefen", "fachgebiet_gewichten"]
