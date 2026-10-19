# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib

import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import belege
import wissen

WETTER_API = "https://api.open-meteo.com/v1/forecast"
ORTE_API = "https://geocoding-api.open-meteo.com/v1/search"
FEEDS: dict[str, list[tuple[str, str]]] = {
    "at": [("ORF", "https://rss.orf.at/news.xml"), ("news.at", "https://www.news.at/rss/home"), ("APA-OTS", "https://www.ots.at/rss/politik")],
    "de": [("tagesschau", "https://www.tagesschau.de/index~rss2.xml"), ("ZDFheute", "https://www.zdfheute.de/rss/zdf/nachrichten"),
           ("Deutschlandfunk", "https://www.deutschlandfunk.de/nachrichten-100.rss"), ("Deutsche Welle", "https://rss.dw.com/rdf/rss-de-all")],
    "ch": [("SRF", "https://www.srf.ch/news/bnf/rss/1646")],
    "gb": [("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"), ("Sky News", "https://feeds.skynews.com/feeds/rss/home.xml")],
    "us": [("NPR", "https://feeds.npr.org/1001/rss.xml")],
}
FEEDS_INTERNATIONAL = {"en": [("DW", "https://rss.dw.com/rdf/rss-en-top")]}
FEED_SPRACHE = {"at": "de", "de": "de", "ch": "de", "gb": "en", "us": "en"}


def land_name(land: str) -> str:
    return LAENDER.get(land) or ("international" if land in FEEDS_INTERNATIONAL else "Österreich")
SCHLAGZEILEN_JE_FEED = 6
SCHLAGZEILEN_MAX = 15
SUCHE_SEITEN = 2
SUCHE_TREFFER = 5
SUCHE_NICHT_DURCH = "Community-Suche (nicht durchgekommen)"
SUCHE_NICHTS = "NACHSCHAU_NICHTS"
TIMEOUT_S = 15.0
MAX_ANTWORT = 1024 * 1024
GUELTIG = {"wetter": timedelta(hours=6), "schlagzeilen": timedelta(hours=3), "suche": timedelta(days=7)}
MAX_GUELTIG_TAGE = 30
MAX_TEXT = 20_000
_UA = wissen._UA
LAENDER = {"at": "Österreich", "de": "Deutschland", "ch": "Schweiz", "gb": "Großbritannien", "us": "USA"}
NAMENSNENNUNG = {"wetter": "Open-Meteo (CC BY 4.0)", "schlagzeilen": "", "suche": ""}

_WETTER_STARK = re.compile(r"\b(wetter|wettervorhersage|wetterbericht|regnet|schneit)\b", re.I)
_WETTER_MESS = re.compile(r"\b(wie warm|wie kalt|wie hei[ßs]|temperatur\w*|grad)\b", re.I)
_WETTER_ZEIT = re.compile(r"\b(heute|morgen|[üu]bermorgen|drau[ßs]en|am wochenende|diese woche|n[äa]chste woche|in der nacht|nachts|tags[üu]ber|hat es|haben wir|jetzt|gerade)\b", re.I)
_WETTER_SCHWACH = re.compile(r"\b(regen|schnee|sonnig|sonne|gewitter|wind|wolk\w*|bew[öo]lkt|nebel|hitze|frost)\b", re.I)
_FRAGEFORM = re.compile(r"\b(wird es|ist es|gibt es|kommt|bleibt es|scheint)\b", re.I)
_KEIN_WETTER = re.compile(r"\b(warum|wieso|weshalb|wie entsteh\w*|wie weit|entfernt|entfernung|sekunden|was ist|was sind|was bedeutet|fahrenheit|in celsius|in grad celsius)\b", re.I)
_SCHREIBEN = re.compile(r"\b(schreib\w*|gedicht|geschichte|erkl[äa]r\w*|was ist ein|was bedeutet|übersetz\w*|uebersetz\w*)\b", re.I)
_SCHLAGZEILEN = re.compile(r"\b(schlagzeil|nachrichten|news\b|neuigkeit|was ist (heute |gerade )?(passiert|los)|was gibt es neues|aktuelle meldung)", re.I)
_RECHNEN = re.compile(r"\b(zu je|je stück|pro stück|stückpreis|zusammen|insgesamt|gesamt|summe|mal\b|prozent|rabatt|umrechn\w*|in meilen|in kilometer|in euro|wie viele tage)\b|[×x*]\s*\d|\d\s*[×x*]|%", re.I)
_SUCHE = re.compile(r"\b(wie ?viel|wie hoch|wie teuer|was kostet|kosten|preis|f[öo]rderung|zuschuss|frist|termin|[öo]ffnungszeit|gesetz|steuer|aktuell|derzeit|neu(?:e|en|es)?\b|20(?:2[4-9]|3\d)|wer ist|wann ist|wo ist|wo gibt|"
                    r"how much|how many|how high|how expensive|costs?\b|price|subsid\w+|grant|deadline|appointment|opening hours|law\b|tax\w*|"
                    r"current\w*|new\b|who is|when is|where is|where can i)", re.I)
_ANGEBOT = re.compile(r"\b(aktion(?:en)?|angebot(?:e|en)?|sonderangebot\w*|flugbl[äa]tt\w*|prospekt\w*|rabattaktion\w*|abverkauf|schn[äa]ppchen|"
                      r"g[üu]nstig\w*|billig\w*|lagernd|verf[üu]gbar\w*|wo (?:bekomm|krieg|kauf|find)\w*|gibt es (?:\w+ )?(?:irgend)?wo|"
                      r"durchsuch\w*|recherchier\w*|such(?:e|st)? (?:im|online|nach)|schau (?:im|online|nach)|im (?:internet|netz)|online)\b", re.I)
_ORT = re.compile(r"\b(?:in|für|fuer|bei|um)\s+([A-ZÄÖÜ][\wäöüß.-]+(?:\s+(?:am|an der|im|bei)\s+[A-ZÄÖÜ][\wäöüß.-]+|\s+[A-ZÄÖÜ][\wäöüß.-]+)?)")
_ORT_NICHT = {"Österreich", "Deutschland", "Schweiz", "Europa", "Zukunft", "Ordnung", "Moment"}
_ORT_OHNE = re.compile(r"\b[Ww]etter(?:vorhersage|bericht)?\s+(?:(?:heute|morgen|übermorgen)\s+)?([A-ZÄÖÜ][\wäöüß.-]+)")


_UNTERWEGS = re.compile(r"\b(zug|z[üu]ge|bahn|[öo]bb|db|westbahn|railjet|ice|bus(?:se)?|flug|fl[üu]ge|flieger|f[äa]hre|schiff|"
                        r"verbindung(?:en)?|umsteig\w*|fahrplan\w*|abfahrt\w*|ankunft|anreise|anfahrt|route|fahrzeit|reisezeit|"
                        r"train|flight|connection|timetable|departure|arrival)\b", re.I)
_DAUER_WEG = re.compile(r"\b(wie lange (?:brauch|dauer|f[äa]hr|geh)\w*|wie (?:komme?|kommt) (?:ich|man)|how long (?:does|will|is)|how do i get)\b", re.I)
_WANN_FAEHRT = re.compile(r"\b(wann (?:f[äa]hrt|geht|kommt|startet|landet|fliegt)|n[äa]chste[nrs]?|letzte[nrs]?|when (?:does|is) the)\b", re.I)
_VON_NACH = re.compile(r"\bvon\s+\S+.*\bnach\s+\S+|\bfrom\s+\S+.*\bto\s+\S+", re.I)
_JETZT_PRAKTISCH = re.compile(r"\b(preis(?:e)?|kostet|kosten|tarif\w*|ticket\w*|eintritt\w*|[öo]ffnungszeit\w*|ge[öo]ffnet|hat (?:\w+ )*offen|"
                              r"termin\w*|heute|morgen|[üu]bermorgen|aktuell\w*|derzeit|gerade jetzt|diese woche|n[äa]chste woche|am wochenende|"
                              r"price|costs?|opening hours|open today|today|tomorrow|currently|right now|deadline\w*|this year|dieses jahr|heuer)\b", re.I)


_AMT_WER = re.compile(r"(?i)\b(?:wer (?:ist|sind)|who (?:is|are|'s))\b|\bwho's\b")
_AMT_DIREKT = re.compile(r"(?i)\b(?:wer regiert|wer führt|who (?:governs|rules|runs|leads))\b")
_AMT_ROLLE = re.compile(r"(?i)\b(?:\w*präsident\w*|\w*kanzler\w*|premier\w*|\w*minister\w*|regierungschef\w*|staatsoberhaupt|\w*bürgermeister\w*|"
                        r"landeshauptm[äa]nn\w*|landeshauptfrau|gouverneur\w*|könig\w*|kaiser\w*|papst|vorsitzende\w*|parteichef\w*|ceo|"
                        r"trainer\w*|kapitän\w*|president|chancellor|head of (?:state|government)|mayor|governor|king|queen|emperor|pope|"
                        r"chair(?:man|woman|person)?|party leader|coach|manager|captain)\b")
_AMT_FRUEHER = re.compile(r"(?i)\b(?:erste[nmrs]?|ehemalig\w*|damalig\w*|frühere[nmrs]?|first|former|previous)\b")


def amtsfrage(frage: str) -> bool:
    f = frage or ""
    if _AMT_FRUEHER.search(f):
        return False
    return bool(_AMT_DIREKT.search(f) or (_AMT_WER.search(f) and _AMT_ROLLE.search(f)))


def nicht_im_lexikon(frage: str) -> bool:
    f = " ".join(str(frage or "").split())
    if not f:
        return False
    if _UNTERWEGS.search(f) and (_VON_NACH.search(f) or _DAUER_WEG.search(f) or _WANN_FAEHRT.search(f)):
        return True
    if _DAUER_WEG.search(f) and _VON_NACH.search(f):
        return True
    if _SCHLAGZEILEN.search(f) and belege.gefragtes_land(f) not in ("", *LAENDER):
        return True
    return bool(_JETZT_PRAKTISCH.search(f)) or belege.regelfrage(f) or amtsfrage(f)


def erkennen_im_gespraech(nachrichten: list[dict]) -> "Auftrag | None":
    if not nachrichten or nachrichten[-1].get("role") != "user":
        return None
    a = erkennen(str(nachrichten[-1].get("content", "")))
    if a is None or a.art != "wetter" or a.ort:
        return a
    for n in reversed(nachrichten[:-1]):
        if n.get("role") != "user":
            continue
        frueher = erkennen(str(n.get("content", "")))
        if frueher is not None and frueher.art == "wetter" and frueher.ort:
            return Auftrag("wetter", a.frage, ort=frueher.ort, tag=a.tag)
    return a

WETTERCODE = {0: "klar", 1: "meist klar", 2: "teils bewölkt", 3: "bedeckt", 45: "Nebel", 48: "Reifnebel", 51: "leichter Nieselregen", 53: "Nieselregen", 55: "starker Nieselregen",
              56: "gefrierender Nieselregen", 57: "gefrierender Nieselregen", 61: "leichter Regen", 63: "Regen", 65: "starker Regen", 66: "gefrierender Regen", 67: "gefrierender Regen",
              71: "leichter Schneefall", 73: "Schneefall", 75: "starker Schneefall", 77: "Schneegriesel", 80: "leichte Regenschauer", 81: "Regenschauer", 82: "heftige Regenschauer",
              85: "Schneeschauer", 86: "starke Schneeschauer", 95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit starkem Hagel"}
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class NachschauError(wissen.WissenError):
    pass


@dataclass(frozen=True)
class Auftrag:
    art: str
    frage: str
    ort: str = ""
    tag: int = 0
    land: str = "at"

    @property
    def rueckfrage(self) -> str:
        if self.art == "wetter" and not self.ort:
            return "Für welchen Ort soll ich das Wetter nachschauen? Schreib zum Beispiel: Wie wird das Wetter morgen in Linz?"
        return ""

    @property
    def titel(self) -> str:
        if self.art == "wetter":
            return f"Wetter {['heute', 'morgen', 'übermorgen'][self.tag]} in {self.ort}"
        if self.art == "schlagzeilen":
            return f"Schlagzeilen {land_name(self.land)}"
        return ""


@dataclass(frozen=True)
class Ergebnis:
    art: str
    titel: str
    adresse: str
    text: str
    gueltig_bis: str
    woher: str


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def gueltig_bis(art: str, jetzt: datetime | None = None) -> str:
    return ((jetzt or _jetzt()) + GUELTIG.get(art, GUELTIG["suche"])).strftime("%Y-%m-%dT%H:%M:%SZ")


_DATEI_WORT = r"(?:datei|dateien|dokument|dokumente|dokumenten|ordner|unterlagen|pdfs?|pdf-datei|word-?datei|word-?dokument|docx?|excel-?datei|excel-?tabelle|xlsx?|scans?)"
_DATEI_ART_BESITZ = r"(?:meine?[nmrs]?|unsere?[nmrs]?)\s+(?:\w+\s+){0,2}?\w*(?:datei|dateien|dokument\w*|ordner|unterlagen|pdfs?|word\w*|excel\w*|fotos?|bilder|scans?|bewerbung\w*|rechnung\w*|vertr(?:a|ä)g\w*|lebenslauf|zeugnis\w*|bescheid\w*|befund\w*)\b"
_DATEI_TUN = r"(?:such|find|wo\s+(?:ist|sind|liegt|liegen|hab|habe|finde)|zeig|hol|schick|brauch|gib\s+mir|öffne|oeffne|hast\s+du|gibt\s+es)"
_WIE_FRAGE = re.compile(r"\s*(?:wie|warum|wieso|weshalb|was\s+(?:ist|sind|bedeutet|heißt|heisst|macht)|kann\s+man|welches?\s+programm)\b", re.I)
DATEI_WORT_EN = r"(?:files?|documents?|folders?|paperwork|pdfs?|spreadsheets?|scans?)"
DATEI_BESITZ_EN = (r"(?:my|our)\s+(?:\S+\s+){0,2}?(?:files?|documents?|folders?|paperwork|pdfs?|spreadsheets?|photos?|pictures?|scans?|"
                   r"applications?|invoices?|bills?|contracts?|cv|resume|certificates?|payslips?|tax\s+returns?|receipts?|letters?)")
DATEI_TUN_EN = r"(?:find|search|look\s+for|where\s+(?:is|are|did\s+i\s+(?:put|save))|where's|show\s+me|fetch|get\s+me|send\s+me|i\s+need|open|do\s+you\s+have|is\s+there)"
DATEI_WIE_EN = r"\s*(?:how|why|what|which|should|explain|write|can\s+you\s+(?:explain|write|tell))"


SUCHERGEBNISSE_TITEL = "Suchergebnisse"


def ohne_wortlaut(titel: str, text: str) -> tuple[str, str]:
    if not str(titel).startswith("Suchergebnisse") or ("zur Frage „" not in str(text) and not str(titel).startswith("Suchergebnisse: ")):
        return titel, text
    text = re.sub(r"(Suchergebnisse \([^)\n]*\)) zur Frage „[^“]*“(, gelesen am [0-9]{2}\.[0-9]{2}\.[0-9]{4})(?:; gesucht nach: [^\n]*)?[.:]?", r"\1\2:", str(text), count=1)
    return SUCHERGEBNISSE_TITEL, text


def ist_dateifrage(text: str) -> bool:
    t = " ".join(str(text or "").lower().split())
    if not t or _WIE_FRAGE.match(t) or re.match(DATEI_WIE_EN + r"\b", t):
        return False
    if re.search(r"\b" + _DATEI_WORT + r"\b", t) and re.search(_DATEI_TUN, t):
        return True
    if re.search(r"\b" + _DATEI_ART_BESITZ, t) and re.search(_DATEI_TUN, t):
        return True
    tun_en = re.search(r"\b" + DATEI_TUN_EN + r"\b", t)
    return bool(tun_en and (re.search(r"\b" + DATEI_WORT_EN + r"\b", t) or re.search(r"\b" + DATEI_BESITZ_EN + r"\b", t)))


def frage_kennung(frage: str) -> str:
    norm = " ".join((frage or "").lower().split())
    return "Fragekennung: " + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def erkennen(frage: str) -> Auftrag | None:
    f = " ".join((frage or "").split())
    if not f or wissen.adressen_in_text(f):
        return None
    unten = f.lower()
    if _SCHREIBEN.search(f):
        return None
    if _RECHNEN.search(f) and re.search(r"\d", f):
        return None
    mess_wetter =bool(_WETTER_MESS.search(f)) and bool(_FRAGEFORM.search(f) or _WETTER_ZEIT.search(f) or _ORT_OHNE.search(f)
                                                         or any(m.group(1).strip(" .,;:!?") not in _ORT_NICHT for m in _ORT.finditer(f)))
    if (_WETTER_STARK.search(f) or mess_wetter or (_WETTER_SCHWACH.search(f) and _FRAGEFORM.search(f))) and not _SCHLAGZEILEN.search(f) \
            and not (_KEIN_WETTER.search(f) and not re.search(r"\b(wetter|wettervorhersage|wetterbericht)\b", f, re.I)
                     and not re.search(r"\b(heute|morgen|[üu]bermorgen|am wochenende|diese woche|n[äa]chste woche|in der nacht)\b", f, re.I)):
        tag = 2 if "übermorgen" in unten or "uebermorgen" in unten else (1 if re.search(r"\bmorgen\b", unten) else 0)
        ort = ""
        for m in _ORT.finditer(f):
            kandidat = m.group(1).strip(" .,;:!?")
            if kandidat not in _ORT_NICHT:
                ort = kandidat
                break
        if not ort:
            m = _ORT_OHNE.search(f)
            if m and m.group(1) not in _ORT_NICHT and m.group(1).lower() not in ("heute", "morgen", "übermorgen", "in", "für", "aktuell"):
                ort = m.group(1)
        return Auftrag("wetter", f, ort=ort, tag=tag)
    if _SCHLAGZEILEN.search(f):
        genannt = belege.gefragtes_land(f)
        if genannt and genannt not in LAENDER:
            return Auftrag("suche", f) if len(wissen.woerter(f)) >= 2 else None
        land = genannt or ("de" if re.search(r"deutschland|tagesschau", unten) else ("ch" if re.search(r"schweiz|\bsrf\b", unten) else "at"))
        return Auftrag("schlagzeilen", f, land=land)
    if (_SUCHE.search(f) or _ANGEBOT.search(f)) and len(wissen.woerter(f)) >= 2:
        return Auftrag("suche", f)
    return None


_NICHT_SUCHEN = set("""ich du er sie wir ihr mir mich dir dich uns euch mein meine dein deine will willst möchte möchtest moechte bitte kannst könntest
koenntest sag sage sagst sagen schau schaust such suche suchst durchsuch durchsuche durchsuchst durchsuchen recherchier recherchiere finde findest
rede redest eh halt ja nein nicht kein keine ob wo was wie wer wann gibt gibts gibt's es ein eine einer einen einem eines der die das den dem des
und oder aber auch dass daß mal noch schon gerade jetzt heute bitte danke gesamten gesamte ganzen ganze alle allen handel irgendwo irgendwie
mir nach im in am an auf bei für fuer von vom zu zum zur mit über ueber live nachprüfen nachpruefen internet netz online bitte
ist sind war hat haben wird werden kann soll sollte gibt's""".split())
_NICHT_SUCHEN |= set("""brauche brauchst braucht brauchen benötige benötigst benötigt benötigen muss musst müssen darf darfst dürfen als
do does did i you we he she it they a an the to of for is are was were be can could should would will must need needs my your our their
what how when where who which why there please tell me""".split())


def suchbegriffe_regel(text: str, frueher: str = "") -> str:
    def worte(t: str) -> list[str]:
        weg = {m.lower() for m in re.findall(r"\b(?:nicht|kein\w*)\s+(?:(?:von|um|über|nach|mit)\s+)?(?:(?:einer|einem|einen|eine|der|die|das|den|dem)\s+)?([\wäöüÄÖÜß-]+)", t or "", re.I)}
        out = []
        for w in re.findall(r"[\wäöüÄÖÜß-]+", t or ""):
            if len(w) < 2 or w.lower() in _NICHT_SUCHEN or w.lower() in weg or w.lower() in out:
                continue
            out.append(w)
        return out
    eigen = worte(text)
    if len(eigen) < 3 and frueher:
        eigen = [w for w in worte(frueher) if w.lower() not in {e.lower() for e in eigen}][:4] + eigen
    return " ".join(eigen[:8])


_AUFZ_TRENNER = {"und", "oder", "sowie", ",", "bzw", "bzw."}
_AUFZ_NICHT = {"wie", "was", "wer", "wo", "wann", "welche", "welcher", "welches", "warum", "wieso", "gibt", "ist", "sind", "hat", "haben", "kann",
               "können", "bitte", "sag", "vergleich", "vergleiche", "unterschied"}


_NAME_VORWORT = {"bad", "sankt", "st.", "st", "neu", "markt", "maria", "klein", "groß", "gross", "deutsch", "windisch", "hohe", "hoch", "unter", "ober", "alt"}
_NAME_BINDE = [("am",), ("im",), ("ob",), ("bei",), ("an", "der"), ("in", "der"), ("an", "den"), ("vor", "der")]


def aufzaehlung(frage: str) -> list[str]:
    t = re.findall(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß.-]*|,", frage or "")
    gross = lambda w: w[:1].isupper() and w.lower() not in _AUFZ_NICHT

    def name(i: int) -> tuple[str, int] | None:
        if i >= len(t) or not gross(t[i]):
            return None
        teile, j = [t[i]], i + 1
        if t[i].lower() in _NAME_VORWORT and j < len(t) and gross(t[j]):
            teile.append(t[j])
            j += 1
        for b in _NAME_BINDE:
            k = j + len(b)
            if k < len(t) and tuple(x.lower() for x in t[j:k]) == b and gross(t[k]):
                teile += t[j:k] + [t[k]]
                j = k + 1
                break
        wort = " ".join(teile)
        return (wort if teile[-1].lower() in ("st.",) else wort.rstrip("."), j)

    beste: list[str] = []
    i = 1
    while i < len(t):
        n = name(i)
        if not n:
            i += 1
            continue
        kette, j = [n[0]], n[1]
        while j + 1 < len(t) and t[j].lower() in _AUFZ_TRENNER:
            m = name(j + 1)
            if not m:
                break
            kette.append(m[0])
            j = m[1]
        verbindung = i >= 1 and t[i - 1].lower() == "zwischen"
        if len(kette) >= 2 and len(kette) > len(beste) and not verbindung:
            beste = kette
        i = j if len(kette) >= 2 else n[1]
    out: list[str] = []
    for w in beste:
        if w.lower() not in {o.lower() for o in out}:
            out.append(w)
    return out[:4] if len(out) >= 2 else []


def _ohne(text: str, dinge: list[str]) -> str:
    verb = r"(?:,|und|oder|sowie|bzw\.?)"
    for d in dinge:
        e = re.escape(d)
        neu = re.sub(rf"(?i)\b{e}\b\s*{verb}\s+", "", text, count=1)
        if neu == text:
            neu = re.sub(rf"(?i)\s*{verb}\s*\b{e}\b", "", text, count=1)
        if neu == text:
            neu = re.sub(rf"(?i)\b{e}\b", "", text, count=1)
        text = neu
    return " ".join(text.split()).replace(" ?", "?").replace(" ,", ",").replace(" .", ".")


def teilfragen(frage: str) -> list[tuple[str, str]]:
    dinge = aufzaehlung(frage)
    return [(d, _ohne(frage, [x for x in dinge if x != d])) for d in dinge]


def anfragen_aufteilen(anfragen: list[str], frage: str, *, hoechstens: int = 3) -> list[str]:
    dinge = aufzaehlung(frage)
    if not dinge:
        return anfragen
    out: list[str] = []
    gemeinsam: list[str] = []
    for q in anfragen:
        drin = [d for d in dinge if re.search(rf"(?i)\b{re.escape(d)}\b", q)]
        if len(drin) >= 2:
            grund = _ohne(q, drin)
            out += [f"{grund} {d}".strip() for d in drin]
            gemeinsam.append(q)
        else:
            out.append(q)
    grund = _ohne(anfragen[0], dinge) if anfragen else ""
    for d in dinge:
        if not any(re.search(rf"(?i)\b{re.escape(d)}\b", q) for q in out):
            out.append(f"{grund} {d}".strip())
    gesehen: set[str] = set()
    eigen = [q for q in out if not (q.lower() in gesehen or gesehen.add(q.lower()))]
    erst = [next(q for q in eigen if re.search(rf"(?i)\b{re.escape(d)}\b", q)) for d in dinge]
    rest = [q for q in gemeinsam[:1] if q.lower() not in gesehen] + [q for q in eigen if q not in erst] + [q for q in gemeinsam[1:] if q.lower() not in gesehen]
    return (erst + rest)[:max(hoechstens, len(erst))]


def _holen(adresse: str, *, oeffner=None, daten: bytes | None = None, akzeptiert: str = "*/*") -> bytes:
    oeffner = oeffner or __import__("datenfluss").oeffner("Nachschauen im Internet (Wetter, Schlagzeilen, Suche, Seite)")
    if not adresse.lower().startswith("https://"):
        raise NachschauError("NACHSCHAU_ADRESSE", "nur verschlüsselte Adressen")
    kopf = {"User-Agent": _UA, "Accept": akzeptiert}
    if daten is not None:
        kopf["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(adresse, data=daten, headers=kopf, method="POST" if daten is not None else "GET")
    try:
        with oeffner(req, timeout=TIMEOUT_S) as r:
            roh = r.read(MAX_ANTWORT + 1)
    except Exception as exc:
        raise NachschauError("NACHSCHAU_HOLEN", f"{urllib.parse.urlsplit(adresse).hostname} antwortet nicht ({type(exc).__name__})") from None
    if len(roh) > MAX_ANTWORT:
        raise NachschauError("NACHSCHAU_GROSS", "die Antwort ist zu groß")
    return roh


def _json(adresse: str, *, oeffner=None) -> dict:
    try:
        d = json.loads(_holen(adresse, oeffner=oeffner, akzeptiert="application/json").decode("utf-8"))
    except ValueError:
        raise NachschauError("NACHSCHAU_ANTWORT", "die Antwort ist nicht lesbar") from None
    if not isinstance(d, dict):
        raise NachschauError("NACHSCHAU_ANTWORT", "die Antwort ist nicht lesbar")
    return d


class Nachschauer:

    def __init__(self, *, oeffner=None, schlafen=time.sleep, jetzt=_jetzt, seiten_oeffner=None, suche_fn=None) -> None:
        self._suche_fn = suche_fn
        self._oeffner = oeffner
        self._seiten_oeffner = seiten_oeffner or oeffner
        self._schlafen = schlafen
        self._jetzt = jetzt

    def ausfuehren(self, a: Auftrag) -> list[Ergebnis]:
        if a.art == "wetter":
            return [self.wetter(a)]
        if a.art == "schlagzeilen":
            return [self.schlagzeilen(a)]
        return self.suche(a)


    def wetter(self, a: Auftrag) -> Ergebnis:
        if not a.ort:
            raise NachschauError("NACHSCHAU_ORT", a.rueckfrage)
        o = _json(ORTE_API + "?" + urllib.parse.urlencode({"name": a.ort, "count": 1, "language": "de", "format": "json"}), oeffner=self._oeffner)
        treffer = o.get("results") or []
        if not treffer:
            raise NachschauError("NACHSCHAU_ORT", f"den Ort „{a.ort}“ kenne ich nicht; bitte anders schreiben")
        ort = treffer[0]
        name = str(ort.get("name") or a.ort)
        land = str(ort.get("country") or "")
        zone = str(ort.get("timezone") or "Europe/Vienna")
        adresse = WETTER_API + "?" + urllib.parse.urlencode({
            "latitude": ort.get("latitude"), "longitude": ort.get("longitude"), "timezone": zone, "forecast_days": 3,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max"})
        w = _json(adresse, oeffner=self._oeffner)
        d = w.get("daily") or {}
        try:
            tage = list(d["time"])
            zeilen = [frage_kennung(a.frage), f"Wettervorhersage für {name}" + (f" ({land})" if land else "") + ", nachgeschaut bei Open-Meteo am " + self._jetzt().strftime("%d.%m.%Y um %H:%M UTC") + ":"]
            for i, tag in enumerate(tage):
                dt = datetime.strptime(tag, "%Y-%m-%d")
                wann = ["Heute", "Morgen", "Übermorgen"][i] if i < 3 else tag
                code = int(d["weather_code"][i]) if d["weather_code"][i] is not None else -1
                mm = round(float(d["precipitation_sum"][i] or 0), 1)
                regen = "kein Regen" if mm == 0 else f"Regen {str(mm).replace('.', ',')} mm"
                zeilen.append(f"{wann}, {WOCHENTAGE[dt.weekday()]} {dt.strftime('%d.%m.%Y')}: {WETTERCODE.get(code, 'wechselnd')}, "
                              f"Höchsttemperatur {round(float(d['temperature_2m_max'][i]))} °C, Tiefsttemperatur {round(float(d['temperature_2m_min'][i]))} °C, {regen}"
                              + (f" (Regenwahrscheinlichkeit {int(d['precipitation_probability_max'][i])} %)" if d.get("precipitation_probability_max") and d["precipitation_probability_max"][i] is not None else "")
                              + f", Wind bis {round(float(d['wind_speed_10m_max'][i]))} km/h.")
        except (KeyError, IndexError, TypeError, ValueError):
            raise NachschauError("NACHSCHAU_ANTWORT", "die Wetterdaten sind unvollständig") from None
        titel = f"Wetter {['heute', 'morgen', 'übermorgen'][a.tag]} in {name}"
        return Ergebnis("wetter", titel, adresse, "\n".join(zeilen), gueltig_bis("wetter", self._jetzt()), "Wetter bei Open-Meteo nachgeschaut")


    def schlagzeilen(self, a: Auftrag) -> Ergebnis:
        feeds = FEEDS.get(a.land) or FEEDS_INTERNATIONAL.get(a.land) or FEEDS["at"]
        je_feed: list[list[tuple[str, str, str, str]]] = []
        fehler = []
        for name, adresse in feeds:
            try:
                nein = wissen.vorbehalt(adresse, oeffner=self._oeffner)
                if nein:
                    fehler.append(f"{name}: sagt Nein zu KI")
                    continue
                roh = _holen(adresse, oeffner=self._oeffner, akzeptiert="application/rss+xml, application/xml, text/xml").decode("utf-8", "replace")
            except Exception as exc:
                fehler.append(f"{name}: {getattr(exc, 'detail', None) or type(exc).__name__}")
                continue
            liste = []
            for item in re.findall(r"<item\b.*?</item>", roh, re.S)[:SCHLAGZEILEN_JE_FEED]:
                t = re.search(r"<title>(.*?)</title>", item, re.S)
                l = re.search(r"<link>(.*?)</link>", item, re.S)
                b = re.search(r"<description>(.*?)</description>", item, re.S)
                titel = _rein(t.group(1)) if t else ""
                link = html.unescape(l.group(1)).strip() if l else ""
                if titel and link.startswith("https://"):
                    liste.append((titel, link, _rein(b.group(1))[:300] if b else "", name))
            if liste:
                je_feed.append(liste)
        eintraege: list[tuple[str, str, str, str]] = []
        gesehen: set[str] = set()
        for runde in range(SCHLAGZEILEN_JE_FEED):
            for liste in je_feed:
                if runde < len(liste) and liste[runde][0].lower() not in gesehen and len(eintraege) < SCHLAGZEILEN_MAX:
                    eintraege.append(liste[runde])
                    gesehen.add(liste[runde][0].lower())
        if not eintraege:
            raise NachschauError("NACHSCHAU_LEER", "kein Nachrichtenfeed hat gerade etwas geliefert" + (f" ({'; '.join(fehler)})" if fehler else ""))
        namen = [n for n, _ in feeds if any(e[3] == n for e in eintraege)]
        zeilen = [f"{i}. {titel} ({quelle})\n{link}" + (f"\n{teaser}" if teaser else "") for i, (titel, link, teaser, quelle) in enumerate(eintraege, 1)]
        text = frage_kennung(a.frage) + f"\nSchlagzeilen {land_name(a.land)} von{', '.join(namen)}, nachgeschaut am " + self._jetzt().strftime("%d.%m.%Y um %H:%M UTC") + ":\n\n" + "\n\n".join(zeilen)
        return Ergebnis("schlagzeilen", a.titel, feeds[0][1], text[:MAX_TEXT], gueltig_bis("schlagzeilen", self._jetzt()), f"Schlagzeilen in den Nachrichtenfeeds von {', '.join(namen)} nachgeschaut")

    def land_fuer_ort(self, ort: str) -> str:
        if not ort:
            return ""
        o = _json(ORTE_API + "?" + urllib.parse.urlencode({"name": ort, "count": 1, "language": "de", "format": "json"}), oeffner=self._oeffner)
        treffer = o.get("results") or []
        return str((treffer[0] if treffer else {}).get("country_code") or "").lower()[:2]


    def _suche_gemeinsam(self, frage: str) -> tuple[list[str], list[str], str] | None:
        if self._suche_fn is None:
            return None
        try:
            treffer = self._suche_fn(frage[:300])
        except Exception:
            return None
        sicher = ohne_vorbehalt([t for t in treffer if str(t.get("adresse", "")).lower().startswith("https://")], oeffner=self._seiten_oeffner)
        links = [str(t.get("adresse")) for t in sicher]
        return (links, [str(t.get("text", "")) for t in sicher], "Community-Suche") if links else None

    def suche(self, a: Auftrag) -> list[Ergebnis]:
        gemeinsam = self._suche_gemeinsam(a.frage)
        if gemeinsam is None:
            raise NachschauError("NACHSCHAU_LEER", "die Suche der Community ist gerade nicht erreichbar oder hat nichts gefunden")
        links, schnipsel, woher = gemeinsam
        if not links:
            raise NachschauError("NACHSCHAU_LEER", "die Suche hat nichts gefunden oder wurde gebremst")
        out: list[Ergebnis] = []
        gueltig = gueltig_bis("suche", self._jetzt())
        zeilen = [(f"{i + 1}. {urllib.parse.urlsplit(l).hostname or l}: {schnipsel[i]}" if not vermittler(schnipsel[i], l)
                   else f"{i + 1}. {urllib.parse.urlsplit(l).hostname or l} ({VERMITTLER_ZEILE})")
                  if i < len(schnipsel) and schnipsel[i] else f"{i + 1}. {l}" for i, l in enumerate(links[:8])]
        if sum(1 for z in zeilen if ": " in z) >= 2:
            out.append(Ergebnis("suche", SUCHERGEBNISSE_TITEL, links[0], "\n\n".join([frage_kennung(a.frage), f"Suchergebnisse ({woher}), gelesen am " + self._jetzt().strftime("%d.%m.%Y") + ":"] + zeilen)[:MAX_TEXT], gueltig, f"im Internet gesucht ({woher}) und die Seiten gelesen"))
        uebersicht = len(out)
        for i, adresse in enumerate(links[:SUCHE_TREFFER]):
            if len(out) - uebersicht >= SUCHE_SEITEN:
                break
            try:
                q, text, tr = wissen.live_lesen(adresse, a.frage, n=3, oeffner=self._seiten_oeffner)
            except wissen.WissenError:
                continue
            teile = [frage_kennung(a.frage), gefunden_zeile(q.titel, q.adresse, self._jetzt().strftime("%d.%m.%Y"), text)]
            if i < len(schnipsel) and schnipsel[i]:
                teile.append(schnipsel[i])
            teile += [t.text for t in tr]
            out.append(Ergebnis("suche", f"Nachgeschaut: {q.titel}"[:160], q.adresse, "\n\n".join(teile)[:MAX_TEXT], gueltig, f"im Internet gesucht ({woher}) und die Seiten gelesen"))
        if len(out) == uebersicht and not uebersicht:
            raise NachschauError("NACHSCHAU_LEER", "die gefundenen Seiten ließen sich nicht lesen")
        return out

    def _treffer_fuer(self, q: str, sprache: str, zeit: str) -> tuple[list[dict], str]:
        if self._suche_fn is not None:
            opts = {k: v for k, v in (("sprache", sprache), ("zeit", zeit)) if v}
            try:
                tr = self._suche_fn(q[:300], **opts)
                return [t for t in tr if str(t.get("adresse", "")).lower().startswith("https://")], "Community-Suche"
            except Exception:
                return [], SUCHE_NICHT_DURCH
        return [], SUCHE_NICHT_DURCH

    def suche_runde(self, anfragen: list[str], frage: str, *, sprache: str = "", zeit: str = "", ausser=frozenset(), heute=None,
                    ziel: tuple = (None, None)) -> tuple[list[Ergebnis], list[str], str]:
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
        from datetime import date as _date
        heute = heute or _date.today()
        r = richtung(frage)
        anfragen = anfragen_aufteilen([q for q in anfragen if q and q.strip()], frage)[:4] or [frage]
        auftraege = [(q, zeit) for q in anfragen if zeit] + [(q, "") for q in anfragen]
        pool = ThreadPoolExecutor(max_workers=max(1, min(6, len(auftraege))), thread_name_prefix="suche")
        try:
            listen = list(pool.map(lambda x: self._treffer_fuer(x[0], sprache, x[1]), auftraege))
        finally:
            pool.shutdown(wait=False)
        nicht_durch = any(w == SUCHE_NICHT_DURCH for _tr, w in listen)
        woher = next((w for tr, w in listen if tr), "Community-Suche")
        gemischt: list[dict] = []
        for i in range(max((len(tr) for tr, _ in listen), default=0)):
            gemischt += [tr[i] for tr, _ in listen if i < len(tr)]
        reihe = treffer_reihen(gemischt, frage, heute=heute, r=r, ziel=ziel, ausser=ausser)
        reihe = ohne_vorbehalt(reihe, oeffner=self._seiten_oeffner)
        if not reihe:
            if not nicht_durch:
                raise NachschauError(SUCHE_NICHTS, "die Suche hat nichts gefunden")
            raise NachschauError("NACHSCHAU_LEER", "die Suche ist gerade nicht durchgekommen (gebremst oder nicht erreichbar)")
        out: list[Ergebnis] = []
        gueltig = gueltig_bis("suche", self._jetzt())
        tag = self._jetzt().strftime("%d.%m.%Y")
        auszuege = sum(1 for t in reihe[:RUNDE_UEBERSICHT] if t.get("text"))

        def eine(t: dict):
            try:
                return t, wissen.live_lesen(t["adresse"], frage, n=4, oeffner=self._seiten_oeffner, extra=(lambda s: zeit_punkte(s, heute, r)) if r else None)
            except wissen.WissenError:
                sperren(t["adresse"])
                return t, None

        fertig: list = []
        versucht: set[str] = set()
        ende = time.monotonic() + RUNDE_WARTEN_S * 1.5
        for _ in range(2):
            hosts: set[str] = set()
            lesen = []
            for t in reihe:
                if t["adresse"] in versucht or gesperrt(t["adresse"]) or _host(t["adresse"]) in hosts:
                    continue
                hosts.add(_host(t["adresse"]))
                lesen.append(t)
                if len(lesen) >= RUNDE_LESEN:
                    break
            if not lesen or time.monotonic() >= ende:
                break
            versucht |= {t["adresse"] for t in lesen}
            pool = ThreadPoolExecutor(max_workers=len(lesen), thread_name_prefix="lesen")
            try:
                futures = [pool.submit(eine, t) for t in lesen]
                bis = time.monotonic() + max(1.0, min(RUNDE_WARTEN_S, ende - time.monotonic()))
                offen, genug_seit = set(futures), None
                while offen:
                    rest = bis - time.monotonic()
                    if genug_seit is not None:
                        rest = min(rest, genug_seit + RUNDE_NACHLAUF_S - time.monotonic())
                    if rest <= 0:
                        break
                    _fertig, offen = wait(offen, timeout=rest, return_when=FIRST_COMPLETED)
                    lesbar = sum(1 for f in futures if f.done() and not f.exception() and f.result()[1] is not None)
                    if lesbar >= RUNDE_SEITEN:
                        break
                    if lesbar >= 2 and genug_seit is None:
                        genug_seit = time.monotonic()
                fertig += [f.result() for f in futures if f.done() and not f.exception()]
            finally:
                pool.shutdown(wait=False)
            if sum(1 for _, e in fertig if e is not None) >= 2:
                break
        gelesen: list[str] = []
        seiten = 0
        vermittler_hosts = {_host(t["adresse"]) for t, e in fertig if e is not None and vermittler(e[1], t["adresse"])}
        for t, ergebnis in fertig:
            if ergebnis is None or seiten >= RUNDE_SEITEN:
                continue
            q, text, tr = ergebnis
            gelesen.append(t["adresse"])
            inhalt = " ".join(x.text for x in tr)
            if zeitlich_vorbei(inhalt, heute, r) or veraltet_text(q.titel + " " + q.adresse + " " + inhalt, *ziel):
                continue
            teile = [frage_kennung(frage), gefunden_zeile(q.titel, q.adresse, tag, text)]
            if t.get("text"):
                teile.append(" ".join(str(t["text"]).split())[:500])
            teile += [x.text for x in tr]
            out.append(Ergebnis("suche", f"Nachgeschaut: {q.titel}"[:160], q.adresse, "\n\n".join(teile)[:MAX_TEXT], gueltig, f"im Internet gesucht ({woher}) und die Seiten gelesen"))
            seiten += 1
        zeilen = [trefferzeile(i + 1, _host(t["adresse"]), " ".join(str(t.get("titel", "")).split())[:160], " ".join(str(t.get("text", "")).split())[:500],
                               vermittler_hosts) for i, t in enumerate(reihe[:RUNDE_UEBERSICHT])]
        uebersicht = Ergebnis("suche", SUCHERGEBNISSE_TITEL, reihe[0]["adresse"], "\n\n".join(
            [frage_kennung(frage), f"Suchergebnisse ({woher}), gelesen am {tag}."] + zeilen)[:MAX_TEXT],
            gueltig, f"im Internet gesucht ({woher}) und die Seiten gelesen")
        if auszuege >= 2 or (not out and auszuege):
            out.insert(0, uebersicht)
        if not out:
            raise NachschauError("NACHSCHAU_LEER", "die gefundenen Seiten ließen sich nicht lesen oder waren veraltet")
        return out, gelesen, woher


_SAISON_ALT = re.compile(r"\b(20\d\d)\s*[/-]\s*(?:20)?(\d\d)\b")


def _staende(text: str) -> tuple[set[int], set[int]]:
    saisons = {int(m.group(1)) for m in _SAISON_ALT.finditer(text) if (int(m.group(1)) + 1) % 100 == int(m.group(2))}
    jahre = {int(j) for j in re.findall(r"\b(20\d\d)\b", text)}
    return saisons, jahre


def veraltet_text(text: str, ziel_saison: int | None = None, ziel_jahr: int | None = None) -> bool:
    saisons, jahre = _staende(text or "")
    if ziel_saison is not None:
        if saisons:
            return max(saisons) < ziel_saison
        return bool(jahre) and max(jahre) < ziel_saison
    if ziel_jahr is not None:
        return bool(jahre) and max(jahre) < ziel_jahr
    return False


def nur_aktuelle(suchen: list[str], ergebnisse: list["Ergebnis"]) -> tuple[list["Ergebnis"], int]:
    ziel_saison, ziel_jahr = None, None
    for q in suchen:
        s, j = _staende(q)
        if s:
            ziel_saison = max(s)
        elif j:
            ziel_jahr = max(j)
    if ziel_saison is None and ziel_jahr is None:
        return ergebnisse, 0

    def veraltet(e: "Ergebnis") -> bool:
        if e.titel.startswith("Suchergebnisse"):
            return False
        saisons, jahre = _staende(e.adresse + " " + e.titel + " " + e.text)
        if ziel_saison is not None:
            return bool(saisons) and max(saisons) < ziel_saison or (not saisons and bool(jahre) and max(jahre) < ziel_saison)
        return bool(jahre) and max(jahre) < ziel_jahr

    frisch = [e for e in ergebnisse if not veraltet(e)]
    if not [e for e in frisch if not e.titel.startswith("Suchergebnisse")]:
        return ergebnisse, 0
    return frisch, len(ergebnisse) - len(frisch)


RUNDE_LESEN = 5
RUNDE_SEITEN = 4
RUNDE_UEBERSICHT = 8
RUNDE_WARTEN_S = 10.0
RUNDE_NACHLAUF_S = 1.5
GESPERRT_S = 1800.0
_GESPERRT: dict[str, float] = {}

_NAECHST = re.compile(r"n[äa]chste[nrms]?\b|als n[äa]chstes|kommende[nrms]?\b|demn[äa]chst|\bwann (?:spielt|ist|findet|kommt|beginnt|startet|öffnet|oeffnet)\b|"
                      r"spielplan|\btermine?\b|\bbald\b|übermorgen|\bmorgen\b|am wochenende|diese woche|ab wann", re.I)
_LETZT = re.compile(r"\bletzte[nrms]?\b|\bzuletzt\b|\bgestern\b|\bvorige[nrms]?\b|\bvergangene[nrms]?\b|ergebnis(?:se)?\b|\bendstand\b|"
                    r"wie (?:hat|haben) .{1,40} gespielt|wie ist .{1,40} ausgegangen|wer hat .{1,40} gewonnen", re.I)


def richtung(frage: str) -> str:
    f = frage or ""
    if _LETZT.search(f):
        return "letzt"
    if _NAECHST.search(f):
        import kalender_tage
        if kalender_tage.jahre(f) and not re.search(r"n[äa]chste|kommende|als n[äa]chstes|demn[äa]chst", f, re.I):
            return ""
        return "naechst"
    return ""


def _tage(text: str, heute) -> list:
    import belege
    from datetime import date as _date
    out = []
    for t, m, j in belege.daten(text or ""):
        try:
            out.append(_date(j or belege._jahr_fuer(t, m, heute), m, t))
        except ValueError:
            continue
    return out


def zeit_punkte(text: str, heute, r: str) -> float:
    if not r:
        return 0.0
    n = 0
    for d in _tage(text, heute):
        tage = (d - heute).days
        if (r == "naechst" and 0 <= tage <= 120) or (r == "letzt" and -45 <= tage <= 0):
            n += 1
    return float(min(n, 4))


def zeitlich_vorbei(text: str, heute, r: str) -> bool:
    if not r:
        return False
    tage = _tage(text, heute)
    if len(tage) < 2:
        return False
    return zeit_punkte(text, heute, r) == 0


def _host(adresse: str) -> str:
    return (urllib.parse.urlsplit(adresse).hostname or "").lower()


VORBEHALT_WARTEN_S = 2.5
VORBEHALT_HOSTS = 16


def ohne_vorbehalt(treffer: list[dict], *, oeffner=None, warten_s: float = VORBEHALT_WARTEN_S) -> list[dict]:
    import threading
    erste: dict[str, str] = {}
    for t in treffer:
        erste.setdefault(_host(str(t.get("adresse", ""))), str(t.get("adresse", "")))
    erste.pop("", None)
    if not erste:
        return []
    ergebnis: dict[str, str] = {}

    def pruefen(h: str, a: str) -> None:
        try:
            ergebnis[h] = wissen.vorbehalt(a, oeffner=oeffner)
        except Exception:
            ergebnis[h] = "nicht prüfbar"
    faeden = [threading.Thread(target=pruefen, args=(h, a), name="vorbehalt", daemon=True) for h, a in list(erste.items())[:VORBEHALT_HOSTS]]
    for f in faeden:
        f.start()
    bis = time.monotonic() + warten_s
    for f in faeden:
        f.join(max(0.0, bis - time.monotonic()))
    frei = {h for h, grund in list(ergebnis.items()) if not grund}
    def frei_auch_hier(adresse: str) -> bool:
        try:
            return not wissen.vorbehalt(adresse, oeffner=oeffner)
        except Exception:
            return False
    return [t for t in treffer if _host(str(t.get("adresse", ""))) in frei and frei_auch_hier(str(t["adresse"]))]


def gesperrt(adresse: str, jetzt_s: float | None = None) -> bool:
    bis = _GESPERRT.get(_host(adresse), 0.0)
    return bis > (jetzt_s if jetzt_s is not None else time.monotonic())


def sperren(adresse: str, jetzt_s: float | None = None) -> None:
    h = _host(adresse)
    if h:
        _GESPERRT[h] = (jetzt_s if jetzt_s is not None else time.monotonic()) + GESPERRT_S


_AMTLICH = ("gv.at", "oeamtc.at", "arboe.at", "wko.at", "arbeiterkammer.at", "bund.de", "gesetze-im-internet.de", "bundesregierung.de", "adac.de",
            "verbraucherzentrale.de", "admin.ch", "ch.ch", "tcs.ch", "gov", "gov.uk", "europa.eu", "canada.ca", "service-public.fr")
_AMTLICH_ENDUNG = re.compile(r"\.(?:gov|gob|gouv|govt|go|gc|gv)\.[a-z]{2}$")
AMTLICH_PUNKTE = 2.0


def amtlich(adresse: str) -> bool:
    host = re.sub(r"^[a-z]+://", "", str(adresse or "").lower()).split("/", 1)[0].split(":", 1)[0]
    return any(host == d or host.endswith("." + d) for d in _AMTLICH) or bool(_AMTLICH_ENDUNG.search(host))


_VERMITTLER = re.compile(
    r"(?i)\b(?:we are|we're|this (?:web)?site is|our (?:company|service|website|site) is)\s+(?:not|in no way|neither)\s+(?:an?\s+)?"
    r"(?:official|government|governmental|affiliated|associated|connected|linked|endorsed|part of)\b"
    r"|\bnot\s+(?:affiliated|associated|connected|linked|endorsed)\s+(?:with|to|by)\s+(?:any|the)\s+(?:[\w.-]+\s+){0,3}(?:government|authorit\w+|agenc\w+|embass\w+)"
    r"|\bhas no (?:link|connection|affiliation) (?:with|to) (?:any|the)\s+(?:[\w.-]+\s+){0,3}government"
    r"|\b(?:we are|we're)\s+an?\s+(?:private|independent|commercial|third[- ]party)\s+(?:[\w-]+\s+){0,2}(?:company|agency|service|provider|business)"
    r"|\bour\s+(?:service|processing|handling|support|agency|consulting)\s+fees?\b"
    r"|\b(?:wir sind|diese (?:web)?seite ist|diese website ist|dieses angebot ist)\s+(?:kein\w*\s+(?:offizielle\w*\s+|staatliche\w*\s+)?"
    r"(?:behörde|amt|regierungs\w*|offizielle\w*|staatliche\w*)|nicht\s+(?:mit|teil|offiziell|staatlich)|ein\w*\s+private\w*|ein\w*\s+unabhängige\w*)"
    r"|\bnicht mit (?:der|einer|irgendeiner)\s+(?:\w+\s+){0,2}(?:regierung|behörde|botschaft)\w*\s+(?:verbunden|assoziiert|verknüpft)"
    r"|\bunsere\w*\s+(?:service|bearbeitungs|vermittlungs|dienstleistungs)gebühr\w*"
    r"|\bnous ne sommes pas (?:affilié|lié|associé|une agence|un site officiel)|\bce site n['’]est pas (?:un site officiel|affilié)"
    r"|\bno (?:somos|estamos) (?:afiliados|una agencia gubernamental|un sitio oficial)|\beste sitio (?:web )?no es (?:oficial|un sitio oficial)"
    r"|\bnon siamo (?:affiliati|collegati|un sito ufficiale|un ente)|\bquesto sito non è (?:ufficiale|un sito ufficiale)")
VERMITTLER_SATZ = ("Diese Seite sagt selbst, dass sie ein privater Vermittler ist und keine Behörde: nimm von ihr keine Preise, Gebühren, "
                   "Adressen und keinen Antragsweg, und nenne sie nicht als Weg zum Antrag.")
VERMITTLER_ZEILE = "privater Vermittler, keine Behörde"


def vermittler(text: str, adresse: str = "") -> bool:
    return not amtlich(adresse) and bool(_VERMITTLER.search(" ".join((text or "").split())))


def vermittler_adressen(quellen: list[dict]) -> set[str]:
    return {str(q.get("adresse") or "") for q in quellen or [] if VERMITTLER_SATZ in str(q.get("text") or "") and q.get("adresse")}


def gefunden_zeile(titel: str, adresse: str, tag: str, seitentext: str) -> str:
    zeile = f"Gefunden über die Suche, Seite „{titel}“ ({adresse}), gelesen am {tag}."
    return zeile + " " + VERMITTLER_SATZ if vermittler(seitentext, adresse) else zeile


def trefferzeile(i: int, host: str, kopf: str, auszug: str, vermittler_hosts: set[str]) -> str:
    if host in vermittler_hosts or (auszug and vermittler(auszug, "https://" + host)):
        return f"{i}. {host}" + (f" – {kopf}" if kopf else "") + f" ({VERMITTLER_ZEILE})"
    return f"{i}. {host}" + (f" – {kopf}" if kopf else "") + (f": {auszug}" if auszug else "")


def treffer_reihen(treffer: list[dict], frage: str, *, heute, r: str = "", ziel: tuple = (None, None), ausser=frozenset()) -> list[dict]:
    fw = set(wissen.woerter(frage))
    gesehen: set[str] = set()
    bewertet = []
    regel = belege.regelfrage(frage)
    for rang, t in enumerate(treffer):
        adresse = str(t.get("adresse", ""))
        if not adresse.lower().startswith("https://") or adresse in gesehen or adresse in ausser:
            continue
        gesehen.add(adresse)
        kopf = f"{t.get('titel', '')} {t.get('text', '')}"
        tw = set(wissen.woerter(kopf + " " + adresse.replace("-", " ").replace("/", " ")))
        p = (len(fw & tw) / max(1, len(fw))) * 3.0 + zeit_punkte(kopf, heute, r) * 0.75 + 1.0 / (1 + rang)
        if veraltet_text(kopf + " " + adresse, *ziel) or zeitlich_vorbei(kopf, heute, r):
            p -= 3.0
        if regel and amtlich(adresse):
            p += AMTLICH_PUNKTE
        if gesperrt(adresse):
            p -= 10.0
        bewertet.append((p, rang, t))
    bewertet.sort(key=lambda x: (-x[0], x[1]))
    return [t for p, _, t in bewertet if p > -5.0]


def _rein(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def als_quelle(e: Ergebnis) -> tuple[wissen.Quelle, list[wissen.Treffer]]:
    q = wissen.Quelle(wissen.kennung_fuer("nachgeschaut", e.adresse), "nachgeschaut", e.titel, e.adresse, _jetzt().strftime("%Y-%m-%dT%H:%M:%SZ"), len(e.text), e.gueltig_bis)
    return q, [wissen.Treffer(q, t, 1.0) for t in wissen.abschnitte(e.text)[:4]]


__all__ = ["Auftrag", "Ergebnis", "Nachschauer", "NachschauError", "erkennen", "gueltig_bis", "als_quelle", "FEEDS", "WETTER_API", "ORTE_API"]
