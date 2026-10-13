# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import html
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

import region as region_mod
import wissen

TIMEOUT_S = 15.0
MAX_SEITE = 3 * 1024 * 1024
MERKEN_S = 15 * 60
MAX_TEXT = 4000
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class StelleError(wissen.WissenError):
    pass


@dataclass(frozen=True)
class Fund:
    stelle: str
    titel: str
    adresse: str
    text: str


def _tag(d: date) -> str:
    return f"{WOCHENTAGE[d.weekday()]}, {d.day:02d}.{d.month:02d}.{d.year}"


def _datum(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def seitentext(roh: str, *, nur_hauptteil: bool = True) -> str:
    s = roh or ""
    if nur_hauptteil:
        m = re.search(r"<main\b.*?</main>", s, flags=re.S | re.I)
        if m:
            s = m.group(0)
    s = re.sub(r"<(script|style|nav|noscript)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


class Leser:

    def __init__(self, *, oeffner=None, uhr=time.time) -> None:
        self._oeffner = oeffner
        self._uhr = uhr
        self._merk: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def __call__(self, adresse: str) -> str:
        if not adresse.startswith("https://"):
            raise StelleError("STELLE_ADRESSE", "nur verschlüsselte Adressen")
        with self._lock:
            m = self._merk.get(adresse)
            if m and self._uhr() - m[0] < MERKEN_S:
                return m[1]
        oeffner = self._oeffner or __import__("datenfluss").oeffner("Zuständige Stelle lesen (Bundesliga, EZB, Klimaticket, Finanzministerium)")
        vorbehalt = wissen.vorbehalt(adresse, oeffner=oeffner)
        if vorbehalt:
            raise StelleError("STELLE_VORBEHALT", f"{urllib.parse.urlsplit(adresse).hostname} sagt Nein zu KI ({vorbehalt})")
        req = urllib.request.Request(adresse, headers={"User-Agent": wissen._UA, "Accept": "text/html,*/*"})
        roh, kopf = b"", {}
        for versuch in (1, 2):
            try:
                with oeffner(req, timeout=TIMEOUT_S) as r:
                    kopf = getattr(r, "headers", {}) or {}
                    roh = r.read(MAX_SEITE + 1)
                break
            except Exception as exc:
                grund = str(getattr(exc, "reason", "") or exc)[:80]
                if versuch == 2:
                    raise StelleError("STELLE_HOLEN", f"{urllib.parse.urlsplit(adresse).hostname} antwortet nicht ({type(exc).__name__}: {grund})") from None
                time.sleep(2)
        if len(roh) > MAX_SEITE:
            raise StelleError("STELLE_GROSS", "die Seite ist zu groß")
        text = roh.decode("utf-8", errors="replace")
        vorbehalt = wissen.vorbehalt_in_seite(kopf, text)
        if vorbehalt:
            raise StelleError("STELLE_VORBEHALT", f"{urllib.parse.urlsplit(adresse).hostname} sagt Nein zu KI ({vorbehalt})")
        with self._lock:
            self._merk[adresse] = (self._uhr(), text)
        return text


BL = "https://www.bundesliga.at/de"
VEREIN_WORTE = {
    "rapid": "SCR", "salzburg": "RBS", "red bull": "RBS", "lask": "ASK", "linzer ask": "ASK", "sturm": "STU", "austria wien": "FAK",
    "violette": "FAK", "wac": "WAC", "wolfsberg": "WAC", "hartberg": "HTB", "ried": "SVR", "altach": "ALT", "gak": "GAK",
    "grazer ak": "GAK", "wsg": "WSG", "tirol": "WSG", "wattens": "WSG", "lustenau": "ALU", "blau-weiß": "BWL", "blau weiß": "BWL",
    "blau-weiss": "BWL", "klagenfurt": "AKL",
}
_FUSSBALL = re.compile(r"\b(spiel\w*|spielt|gegner|gegen wen|tabelle\w*|tabellenf[üu]hr\w*|f[üu]hrt|f[üu]hrend|spitze|platz|punkte|ergebnis\w*|"
                       r"runde|spieltag|match|heimspiel|ausw[äa]rts\w*|derby|gewonnen|verloren|unentschieden|anpfiff|meister\w*|bundesliga)\b", re.I)
_BUNDESLIGA = re.compile(r"\bbundesliga\b", re.I)
_ANDERE_LIGA = re.compile(r"\b(deutsch\w*|2\.\s*liga|zweite liga|champions|europa ?league|conference|premier|serie a|la liga|frauen|basketball|eishockey|handball)\b", re.I)


def _vereine_in(frage: str) -> list[str]:
    f = " " + (frage or "").lower() + " "
    out = []
    for wort, ab in VEREIN_WORTE.items():
        if re.search(r"(?<![\wäöü])" + re.escape(wort) + r"(?![\wäöü])", f) and ab not in out:
            if wort == "tirol" and "wsg" not in f and "wattens" not in f and "fußball" not in f and "fussball" not in f:
                continue
            out.append(ab)
    if "austria" in f and not any(a in out for a in ("FAK", "ALU")):
        out.append("FAK")
    return out


def bundesliga_betrifft(frage: str) -> bool:
    f = frage or ""
    if _ANDERE_LIGA.search(f):
        return False
    if _BUNDESLIGA.search(f) and re.search(r"(?i)österreich|tabelle|f[üu]hr|spitze|platz|spieltag|runde|spielplan|meister|punkte|ergebnis", f):
        return True
    return bool(_vereine_in(f)) and bool(_FUSSBALL.search(f))


_TABELLE_SAISON = re.compile(r"Tabelle\s+(20\d\d)\s*/\s*(20\d\d)")


def tabelle_lesen(text: str) -> tuple[str, list[dict]]:
    m = _TABELLE_SAISON.search(text)
    saison = f"{m.group(1)}/{m.group(2)[2:]}" if m else ""
    start = text.find("Punkte", m.end() if m else 0)
    zeilen: list[dict] = []
    if start < 0:
        return saison, zeilen
    zeile = re.compile(r"(\d{1,2}) (?:[-–▲▼↑↓] )?([A-Z]{3}) (.+?) (\d{1,2}) (\d{1,2}) (\d{1,2}) (\d{1,2}) (\d{1,3}) (\d{1,3}) (-?\d{1,3}) (\d{1,3})(?= |$)")
    pos = start + len("Punkte")
    for _ in range(24):
        z = zeile.match(text, pos + 1) if pos < len(text) else None
        if not z:
            break
        platz = int(z.group(1))
        if zeilen and platz != zeilen[-1]["platz"] + 1:
            break
        zeilen.append({"platz": platz, "kurz": z.group(2), "name": z.group(3), "spiele": int(z.group(4)), "siege": int(z.group(5)),
                       "remis": int(z.group(6)), "niederlagen": int(z.group(7)), "tore": int(z.group(8)), "gegentore": int(z.group(9)),
                       "punkte": int(z.group(11))})
        pos = z.end()
    return saison, zeilen


def spiele_lesen(text: str, vereine: dict[str, str]) -> list[dict]:
    if not vereine:
        return []
    team = "|".join(re.escape(f"{k} {n}") for k, n in sorted(vereine.items(), key=lambda kv: -len(kv[1])))
    muster = re.compile(rf"(\d{{1,2}}) (\d\d\.\d\d\.\d{{4}}) (\d\d:\d\d )?({team}) ({team}) (\d+ : \d+(?: \(\d+:\d+\))?|-:-|-\s*:\s*-)")
    spiele, gesehen = [], set()
    for m in muster.finditer(text):
        d = _datum(m.group(2))
        if d is None:
            continue
        heim, gast = m.group(4).split(" ", 1), m.group(5).split(" ", 1)
        stand = m.group(6).replace(" ", "")
        schluessel = (m.group(2), heim[0], gast[0])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        spiele.append({"runde": int(m.group(1)), "datum": d, "zeit": (m.group(3) or "").strip(), "heim": heim[0], "heim_name": heim[1],
                       "gast": gast[0], "gast_name": gast[1], "ergebnis": "" if "-:-" in stand or stand.startswith("-") else re.sub(r"\(.*\)", "", stand)})
    return spiele


def _spiel_zeile(s: dict) -> str:
    zeit = f", {s['zeit']} Uhr" if s["zeit"] else ""
    erg = f", Ergebnis {s['ergebnis']}" if s["ergebnis"] else ""
    return f"{_tag(s['datum'])}{zeit}: {s['heim_name']} gegen {s['gast_name']}{erg}"


def bundesliga(frage: str, heute: date, lesen) -> list[Fund]:
    tab_roh = lesen(f"{BL}/tabelle")
    saison, tabelle = tabelle_lesen(seitentext(tab_roh, nur_hauptteil=False))
    if len(tabelle) < 6:
        raise StelleError("STELLE_FORM", "die Tabelle der Bundesliga ließ sich nicht lesen")
    namen = {z["kurz"]: z["name"] for z in tabelle}
    gefragt = [k for k in _vereine_in(frage) if k in namen]
    runden: dict[int, list[dict]] = {}
    aktuell = spiele_lesen(seitentext(lesen(f"{BL}/spielplan"), nur_hauptteil=False), namen)
    for s in aktuell:
        runden.setdefault(s["runde"], []).append(s)
    if not runden:
        raise StelleError("STELLE_FORM", "der Spielplan der Bundesliga ließ sich nicht lesen")
    naechste = max(runden) + 1
    plan = bool(re.search(r"(?i)spielplan|termine|n[äa]chsten spiele|restprogramm", frage))
    for _ in range(3):
        offen = [s for r in runden.values() for s in r if not s["ergebnis"] and s["datum"] >= heute]
        def kommend(k: str) -> int:
            return sum(1 for s in offen if k in (s["heim"], s["gast"]))
        genug = all(kommend(k) >= (3 if plan else 1) for k in gefragt) if gefragt else bool(offen)
        if genug:
            break
        try:
            neu = spiele_lesen(seitentext(lesen(f"{BL}/spielplan?spieltag={naechste}"), nur_hauptteil=False), namen)
        except StelleError:
            break
        if not neu:
            break
        for s in neu:
            runden.setdefault(s["runde"], []).append(s)
        naechste += 1
    alle = sorted((s for r in runden.values() for s in r), key=lambda s: (s["datum"], s["zeit"], s["runde"]))
    gespielt = max(z["spiele"] for z in tabelle)
    teile = [f"ADMIRAL Bundesliga (Österreich), Saison {saison}, gelesen am {heute.strftime('%d.%m.%Y')} auf bundesliga.at, vom Programm aufbereitet "
             f"(Wochentage und nächste Spiele sind ausgerechnet; Daten, Uhrzeiten und Gegner genau so übernehmen)."]
    for k in gefragt:
        n = namen[k]
        vorbei = [s for s in alle if k in (s["heim"], s["gast"]) and s["ergebnis"]]
        kommend = [s for s in alle if k in (s["heim"], s["gast"]) and not s["ergebnis"] and s["datum"] >= heute]
        platz = next(z for z in tabelle if z["kurz"] == k)
        satz = [f"{n}: Platz {platz['platz']} mit {platz['punkte']} Punkten."]
        if vorbei:
            satz.append(f"Letztes Bundesliga-Spiel: {_spiel_zeile(vorbei[-1])}.")
        if kommend:
            s = kommend[0]
            satz.append(f"Nächstes Bundesliga-Spiel von {n}: {_spiel_zeile(s)} ({s['runde']}. Runde, "
                        + ("Heimspiel" if s["heim"] == k else "Auswärtsspiel") + ").")
            if len(kommend) > 1:
                satz.append("Danach: " + "; ".join(f"{_spiel_zeile(x)} ({x['runde']}. Runde)" for x in kommend[1:4]) + ".")
        else:
            satz.append(f"Ein kommendes Bundesliga-Spiel von {n} steht im gelesenen Spielplan noch nicht.")
        teile.append(" ".join(satz))
    teile.append(f"Tabellenführer nach {gespielt} Runden ist {tabelle[0]['name']} mit {tabelle[0]['punkte']} Punkten.")
    teile.append(f"Tabelle nach {gespielt} Runden: "
                 + "; ".join(f"{z['platz']}. {z['name']} {z['punkte']} Punkte ({z['spiele']} Spiele, {z['siege']} Siege, {z['remis']} Unentschieden, "
                             f"{z['niederlagen']} Niederlagen, Tore {z['tore']}:{z['gegentore']})" for z in tabelle) + ".")
    for r in sorted(runden):
        teile.append(f"{r}. Runde: " + "; ".join(_spiel_zeile(s) for s in sorted(runden[r], key=lambda s: (s["datum"], s["zeit"]))) + ".")
    teile.append("Das ist nur die Meisterschaft (Bundesliga). Spiele im ÖFB-Cup oder im Europacup stehen hier nicht.")
    return [Fund("bundesliga", f"Bundesliga Tabelle und Spielplan {saison}", f"{BL}/spielplan", " ".join(teile)[:MAX_TEXT * 2])]


EZB = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html"
_EZB_BETRIFFT = re.compile(r"\b(leitzins\w*|ezb|europ[äa]ische[n]? zentralbank|einlagen(?:satz|zins)|hauptrefinanzierung\w*|spitzenrefinanzierung\w*)\b", re.I)
_MONATE_EN = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def ezb_betrifft(frage: str) -> bool:
    f = frage or ""
    if re.search(r"(?i)\b(fed|federal reserve|usa|snb|schweizer nationalbank|bank of england)\b", f):
        return False
    return bool(_EZB_BETRIFFT.search(f))


def _prozent(x: str) -> str:
    return f"{float(x):.2f}".replace(".", ",") + " %"


def ezb_lesen(roh: str) -> list[dict]:
    body = re.search(r"<tbody.*?</tbody>", roh or "", flags=re.S)
    text = " ".join(re.sub(r"<[^>]+>", " ", body.group(0) if body else "").split())
    reihen = []
    for m in re.finditer(r"(20\d\d)\s+(\d{1,2})\s+([A-Z][a-z]{2})\.?\s+(-?\d+\.\d+)\s+(-?\d+\.\d+|-)\s+(-?\d+\.\d+|-)\s+(-?\d+\.\d+)", text):
        monat = _MONATE_EN.get(m.group(3))
        if not monat:
            continue
        haupt = m.group(5) if m.group(5) != "-" else m.group(6)
        if haupt == "-":
            continue
        reihen.append({"ab": date(int(m.group(1)), monat, int(m.group(2))), "einlage": float(m.group(4)), "haupt": float(haupt), "spitze": float(m.group(7))})
    return reihen


def ezb(frage: str, heute: date, lesen) -> list[Fund]:
    reihen = [r for r in ezb_lesen(lesen(EZB)) if r["ab"] <= heute] or ezb_lesen(lesen(EZB))
    if not reihen:
        raise StelleError("STELLE_FORM", "die Zinstabelle der EZB ließ sich nicht lesen")
    jetzt, vorher = reihen[0], (reihen[1] if len(reihen) > 1 else None)
    t = (f"Leitzinsen der Europäischen Zentralbank (EZB), laut ihrer eigenen Tabelle, gelesen am {heute.strftime('%d.%m.%Y')}. "
         f"Seit {jetzt['ab'].strftime('%d.%m.%Y')} gilt: Hauptrefinanzierungssatz {_prozent(jetzt['haupt'])}, Einlagensatz {_prozent(jetzt['einlage'])}, "
         f"Spitzenrefinanzierungssatz {_prozent(jetzt['spitze'])}. Der Hauptrefinanzierungssatz ist der klassische Leitzins; über den Einlagensatz "
         f"steuert die EZB seit 2024 vor allem.")
    if vorher:
        diff = round(jetzt["haupt"] - vorher["haupt"], 2)
        richtung = ("angehoben" if diff > 0 else "gesenkt") if diff else "gleich gelassen"
        t += (f" Davor, ab {vorher['ab'].strftime('%d.%m.%Y')}: Hauptrefinanzierungssatz {_prozent(vorher['haupt'])}, Einlagensatz {_prozent(vorher['einlage'])}. "
              f"Am {jetzt['ab'].strftime('%d.%m.%Y')} wurden die Zinsen damit " + (f"um {abs(diff):.2f}".replace(".", ",") + " Prozentpunkte " if diff else "") + f"{richtung}.")
    return [Fund("ezb", "Leitzinsen der EZB", EZB, t)]


KLIMATICKET = "https://www.klimaticket.at/agb/klimaticket-oe/"
_KT_BETRIFFT = re.compile(r"\bklima[\s-]?ticket\w*", re.I)
_KT_REGION = re.compile(r"\b(o[öo]|ober[öo]sterreich|nieder[öo]sterreich|n[öo]|wien|steiermark|salzburg|tirol|vorarlberg|k[äa]rnten|burgenland|region\w*)\b", re.I)


def klimaticket_betrifft(frage: str) -> bool:
    f = frage or ""
    return bool(_KT_BETRIFFT.search(f)) and (not _KT_REGION.search(f) or bool(re.search(r"(?i)klima[\s-]?ticket\s*(ö|österreich)\b", f)))


def klimaticket(frage: str, heute: date, lesen) -> list[Fund]:
    text = seitentext(lesen(KLIMATICKET), nur_hauptteil=False)
    gueltig = re.search(r"Gültig ab (\d\d\.\d\d\.\d{4})", text)
    i = text.rfind("Anhang 3 Ticketpreise")
    j = text.find("Anhang 4", i + 1) if i >= 0 else -1
    block = text[i:j if j > i else i + 1200] if i >= 0 else ""
    k = text.find("monatlicher Teilbetrag", j) if j >= 0 else -1
    raten_block = text[k:k + 600] if k >= 0 else ""
    muster = re.compile(r"KlimaTicket Ö ((?:[A-ZÄÖÜ][\wäöüß]+)(?:,? (?:[A-ZÄÖÜ][\wäöüß]+))*) € ([\d.]+,\d\d)")
    preise = muster.findall(block)
    raten = muster.findall(raten_block)
    if not preise:
        raise StelleError("STELLE_FORM", "die Preise des KlimaTicket Ö ließen sich nicht lesen")
    ust = " (inkl. 10 % USt)" if "10 % USt" in block else ""
    t = (f"KlimaTicket Ö (ganz Österreich), Jahrespreise laut den Geschäftsbedingungen"
         + (f", gültig ab {gueltig.group(1)}" if gueltig else "") + f"{ust}, gelesen am {heute.strftime('%d.%m.%Y')}: "
         + "; ".join(f"{art} {betrag} €" for art, betrag in preise) + ". Es ist ein Jahresticket.")
    if raten:
        t += (" Wer per SEPA-Lastschrift monatlich zahlt, zahlt Monatsraten; ein monatlicher Teilbetrag ist: "
              + "; ".join(f"{art} {betrag} €" for art, betrag in raten) + ".")
    t += " Die regionalen Klimatickets der Bundesländer kosten anders und stehen hier nicht."
    return [Fund("klimaticket", "KlimaTicket Ö Preise", KLIMATICKET, t)]


@dataclass(frozen=True)
class Seite:
    kennung: str
    titel: str
    adresse: str
    betrifft: re.Pattern


SEITEN = [
    Seite("kilometergeld", "Amtliches Kilometergeld (Finanzministerium)", "https://www.bmf.gv.at/themen/steuern/kraftfahrzeuge/kilometergeld.html",
          re.compile(r"\bkilometergeld\w*|\bkilometersatz\b|\bkilometerpauschale\b", re.I)),
    Seite("pendlerpauschale", "Pendlerpauschale und Pendlereuro (Finanzministerium)", "https://www.bmf.gv.at/themen/steuern/arbeitnehmerveranlagung/pendlerfoerderung-das-pendlerpauschale/allgemeines-zum-pendlerpauschale.html",
          re.compile(r"\bpendler(?:pauschale|euro|förderung|foerderung)\w*", re.I)),
]


def seite(s: Seite, heute: date, lesen) -> list[Fund]:
    text = seitentext(lesen(s.adresse))
    if len(text) < 200:
        raise StelleError("STELLE_FORM", f"die Seite „{s.titel}“ ließ sich nicht lesen")
    return [Fund(s.kennung, s.titel, s.adresse, f"{s.titel}, gelesen am {heute.strftime('%d.%m.%Y')}: {text[:MAX_TEXT]}")]


def passend(frage: str, vorher: str = "") -> list[str]:
    out = []
    if bundesliga_betrifft(frage) or (_vereine_in(frage) and bundesliga_betrifft(vorher) and len((frage or "").split()) <= 6):
        out.append("bundesliga")
    if ezb_betrifft(frage):
        out.append("ezb")
    if klimaticket_betrifft(frage):
        out.append("klimaticket")
    out += [s.kennung for s in SEITEN if s.betrifft.search(frage or "")]
    r = region_mod.erkennen(frage)
    if r is not None and r.land != "at":
        out = [k for k in out if k == "ezb" and r.land == "de"]
    return out


NAMEN = {"bundesliga": "bundesliga.at", "ezb": "ecb.europa.eu", "klimaticket": "klimaticket.at", "kilometergeld": "bmf.gv.at", "pendlerpauschale": "bmf.gv.at"}


def lesen_fuer(frage: str, *, vorher: str = "", heute: date | None = None, lesen=None) -> tuple[list[Fund], list[str]]:
    heute = heute or date.today()
    lesen = lesen or _LESER
    funde, fehler = [], []
    for k in passend(frage, vorher):
        try:
            if k == "bundesliga":
                funde += bundesliga(frage, heute, lesen)
            elif k == "ezb":
                funde += ezb(frage, heute, lesen)
            elif k == "klimaticket":
                funde += klimaticket(frage, heute, lesen)
            else:
                funde += seite(next(s for s in SEITEN if s.kennung == k), heute, lesen)
        except wissen.WissenError as exc:
            fehler.append(f"{NAMEN.get(k, k)}: {exc.detail}")
        except Exception as exc:
            fehler.append(f"{NAMEN.get(k, k)}: nicht lesbar ({type(exc).__name__})")
    return funde, fehler


_LESER = Leser()

__all__ = ["Fund", "Leser", "StelleError", "passend", "lesen_fuer", "seitentext", "tabelle_lesen", "spiele_lesen", "ezb_lesen", "bundesliga_betrifft",
           "ezb_betrifft", "klimaticket_betrifft", "NAMEN"]
