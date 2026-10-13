# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

API = "https://www.thesportsdb.com/api/v2/json/"
SEITE = "https://www.thesportsdb.com/"
QUELLE = "TheSportsDB"
SCHLUESSEL_DATEI = Path("geheim") / "thesportsdb.schluessel"
LIVE_S = 120
PLAN_S = 3600
SUCHE_S = 24 * 3600
JE_MINUTE = 80
TIMEOUT_S = 10.0
MAX_ANTWORT = 4 * 1024 * 1024
MAX_SPIELE = 15
MAX_SACHE = 60
_UA = "KIplatz/1.0 (+https://kiplatz.at/urheberrecht/)"

LIGEN: dict[str, str] = {
    "bundesliga": "Austrian Bundesliga", "österreichische bundesliga": "Austrian Bundesliga", "oesterreichische bundesliga": "Austrian Bundesliga",
    "admiral bundesliga": "Austrian Bundesliga", "austrian bundesliga": "Austrian Bundesliga", "deutsche bundesliga": "German Bundesliga",
    "german bundesliga": "German Bundesliga", "1. bundesliga": "German Bundesliga", "2. bundesliga": "German 2. Bundesliga", "zweite bundesliga": "German 2. Bundesliga",
    "2. liga": "Austrian 2. Liga", "premier league": "English Premier League", "english premier league": "English Premier League",
    "championship": "English League Championship", "champions league": "UEFA Champions League", "europa league": "UEFA Europa League",
    "conference league": "UEFA Europa Conference League", "serie a": "Italian Serie A", "la liga": "Spanish La Liga", "primera division": "Spanish La Liga",
    "ligue 1": "French Ligue 1", "eredivisie": "Dutch Eredivisie", "primeira liga": "Portuguese Primeira Liga", "süper lig": "Turkish Super Lig",
    "super league": "Swiss Super League", "mls": "American Major League Soccer", "nations league": "UEFA Nations League",
    "öfb cup": "Austrian Cup", "oefb cup": "Austrian Cup", "öfb-cup": "Austrian Cup", "dfb pokal": "DFB-Pokal", "dfb-pokal": "DFB-Pokal", "fa cup": "English FA Cup",
    "formel 1": "Formula 1", "formel1": "Formula 1", "formel-1": "Formula 1", "formel eins": "Formula 1", "f1": "Formula 1", "formula 1": "Formula 1", "formula-1": "Formula 1",
    "formula one": "Formula 1",
    "motogp": "MotoGP", "nba": "NBA", "nfl": "NFL", "nhl": "NHL", "mlb": "MLB", "wnba": "WNBA", "euroleague": "Euroleague Basketball",
    "del": "German DEL", "ice hockey league": "Austrian ICE Hockey League", "ice liga": "Austrian ICE Hockey League", "eishockey liga": "Austrian ICE Hockey League",
    "superliga": "Austrian Basketball Superliga", "basketball superliga": "Austrian Basketball Superliga", "bbl": "German Basketball Bundesliga",
}
_LIGA_RE = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(LIGEN, key=len, reverse=True)) + r")(?![\w])", re.I)

ZUSTAND = {"NS": "noch nicht begonnen", "1H": "1. Halbzeit", "HT": "Halbzeitpause", "2H": "2. Halbzeit", "ET": "Verlängerung", "BT": "Pause vor der Verlängerung",
           "P": "Elfmeterschießen", "PEN": "Elfmeterschießen", "FT": "Spiel beendet", "AET": "beendet nach Verlängerung", "LIVE": "läuft",
           "P1": "1. Drittel", "P2": "2. Drittel", "P3": "3. Drittel", "OT": "Verlängerung", "Q1": "1. Viertel", "Q2": "2. Viertel", "Q3": "3. Viertel", "Q4": "4. Viertel",
           "PST": "verschoben", "CANC": "abgesagt", "ABD": "abgebrochen", "SUSP": "unterbrochen", "INT": "unterbrochen", "AWD": "Entscheidung am grünen Tisch", "WO": "kampflos"}
LAEUFT = {"1H", "HT", "2H", "ET", "BT", "P", "PEN", "LIVE", "P1", "P2", "P3", "OT", "Q1", "Q2", "Q3", "Q4"}
VORBEI = {"FT", "AET", "AWD", "WO", "Final"}


class SportError(Exception):

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code, self.detail = code, detail


def spiel_kurz(e: dict) -> dict:
    def s(k: str, n: int = 80) -> str:
        v = e.get(k)
        return "" if v is None else " ".join(str(v).split())[:n]
    zeit = s("strEventTime") or s("strTime")
    return {"sport": s("strSport"), "liga": s("strLeague"), "liga_id": s("idLeague", 12), "heim": s("strHomeTeam"), "gast": s("strAwayTeam"),
            "heim_id": s("idHomeTeam", 12), "gast_id": s("idAwayTeam", 12), "heim_tore": s("intHomeScore", 6), "gast_tore": s("intAwayScore", 6),
            "zustand": s("strStatus", 12), "fortschritt": s("strProgress", 12), "datum": s("dateEvent", 10), "zeit": zeit[:5], "name": s("strEvent", 120),
            "runde": s("intRound", 6), "land": s("strCountry", 40), "ort": s("strVenue", 80), "verschoben": s("strPostponed", 6) == "yes", "aktualisiert": s("updated", 19)}


class Sport:

    def __init__(self, ordner: Path, *, oeffner=None, jetzt=time.time) -> None:
        self.ordner = Path(ordner)
        self._oeffner = oeffner or urllib.request.urlopen
        self._jetzt = jetzt
        self._sperre = threading.Lock()
        self._speicher: dict[str, tuple[float, object]] = {}
        self._anfragen: deque[float] = deque()
        self.anfragen_gesamt = 0
        self._gemeldet = False


    def eingerichtet(self) -> bool:
        try:
            return bool(self._schluessel())
        except SportError:
            return False

    def _schluessel(self) -> str:
        p = self.ordner / SCHLUESSEL_DATEI
        try:
            k = p.read_text(encoding="utf-8").strip()
        except OSError:
            raise SportError("SPORT_AUS", "Spielstände sind am Server nicht eingerichtet") from None
        if not re.fullmatch(r"[A-Za-z0-9]{3,64}", k):
            raise SportError("SPORT_AUS", "Spielstände sind am Server nicht eingerichtet")
        return k


    def _holen(self, weg: str, gueltig_s: float) -> object:
        with self._sperre:
            t = self._jetzt()
            alt = self._speicher.get(weg)
            if alt is not None and alt[0] > t:
                return alt[1]
            while self._anfragen and self._anfragen[0] <= t - 60.0:
                self._anfragen.popleft()
            if len(self._anfragen) >= JE_MINUTE:
                if alt is not None:
                    return alt[1]
                raise SportError("SPORT_GEBREMST", "gerade fragen zu viele nach Spielständen, bitte in einer Minute noch einmal")
            self._anfragen.append(t)
            self.anfragen_gesamt += 1
            schluessel = self._schluessel()
        req = urllib.request.Request(API + weg, headers={"X-API-KEY": schluessel, "User-Agent": _UA, "Accept": "application/json"})
        try:
            with self._oeffner(req, timeout=TIMEOUT_S) as r:
                roh = r.read(MAX_ANTWORT)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise SportError("SPORT_GEBREMST", "TheSportsDB bremst gerade, bitte in einer Minute noch einmal") from None
            raise SportError("SPORT_NETZ", f"TheSportsDB antwortet mit Fehler {exc.code}") from None
        except Exception as exc:
            raise SportError("SPORT_NETZ", f"TheSportsDB ist gerade nicht erreichbar ({type(exc).__name__})") from None
        try:
            d = json.loads(roh.decode("utf-8", "replace"))
        except ValueError:
            raise SportError("SPORT_ANTWORT", "die Antwort von TheSportsDB ist nicht lesbar") from None
        if not isinstance(d, dict):
            raise SportError("SPORT_ANTWORT", "die Antwort von TheSportsDB ist nicht lesbar")
        wert: object = next((v for v in d.values() if isinstance(v, list)), [])
        with self._sperre:
            self._speicher[weg] = (self._jetzt() + gueltig_s, wert)
            if len(self._speicher) > 500:
                self._speicher.pop(next(iter(self._speicher)))
        return wert

    def live(self, sport: str = "") -> list[dict]:
        liste = [spiel_kurz(e) for e in self._holen("livescore/all", LIVE_S) if isinstance(e, dict)]
        if sport:
            liste = [s for s in liste if s["sport"].lower() == sport.lower()]
        return liste

    def plan(self, *, liga_id: str = "", verein_id: str = "", richtung: str = "next") -> list[dict]:
        richtung = "previous" if richtung in ("previous", "letzte") else "next"
        if verein_id:
            weg = f"schedule/{richtung}/team/{_nummer(verein_id)}"
        elif liga_id:
            weg = f"schedule/{richtung}/league/{_nummer(liga_id)}"
        else:
            raise SportError("SPORT_SACHE", "für einen Spielplan braucht es eine Liga oder einen Verein")
        return [spiel_kurz(e) for e in self._holen(weg, PLAN_S) if isinstance(e, dict)]

    def liga_finden(self, name: str) -> dict | None:
        n = " ".join(str(name or "").split())[:MAX_SACHE]
        if not n:
            return None
        suchtext = LIGEN.get(n.lower(), n)
        for e in self._holen("search/league/" + _suchwort(suchtext), SUCHE_S):
            if isinstance(e, dict) and e.get("idLeague"):
                return {"id": str(e["idLeague"]), "name": str(e.get("strLeague") or suchtext)[:80], "sport": str(e.get("strSport") or "")[:40], "land": str(e.get("strCountry") or "")[:40]}
        return None

    def verein_finden(self, name: str, *, sport: str = "") -> dict | None:
        n = " ".join(str(name or "").split())[:MAX_SACHE]
        if not n:
            return None
        treffer = [e for e in self._holen("search/team/" + _suchwort(n), SUCHE_S) if isinstance(e, dict) and e.get("idTeam")]
        if sport:
            treffer = [e for e in treffer if str(e.get("strSport") or "").lower() == sport.lower()] or treffer
        if not treffer:
            return None
        e = treffer[0]
        return {"id": str(e["idTeam"]), "name": str(e.get("strTeam") or n)[:80], "liga": str(e.get("strLeague") or "")[:80], "liga_id": str(e.get("idLeague") or "")[:12],
                "sport": str(e.get("strSport") or "")[:40], "land": str(e.get("strCountry") or "")[:40]}


    def anfrage(self, body: dict) -> dict:
        was = str(body.get("was") or "live")
        if was not in ("live", "naechste", "letzte"):
            was = "live"
        sache = " ".join(str(body.get("sache") or "").split())[:MAX_SACHE]
        sport = " ".join(str(body.get("sport") or "").split())[:30]
        land = str(body.get("land") or "at")[:2].lower()
        if sache.lower() == "bundesliga" and land == "de":
            sache = "deutsche Bundesliga"
        liga = verein = None
        hinweis = ""
        if sache:
            m = _LIGA_RE.fullmatch(sache)
            liga = self.liga_finden(sache) if (m or not _klingt_nach_verein(sache)) else None
            if liga is None:
                verein = self.verein_finden(sache, sport=sport)
            if liga is None and verein is None and not m:
                liga = self.liga_finden(sache)
            if liga is None and verein is None:
                raise SportError("SPORT_SACHE", f"zu „{sache}“ habe ich keine Liga und keinen Verein gefunden")
        stand = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._jetzt()))
        if was == "live":
            spiele = self.live(sport or (liga or verein or {}).get("sport", ""))
            if liga is not None:
                spiele = [s for s in spiele if s["liga_id"] == liga["id"]]
            elif verein is not None:
                spiele = [s for s in spiele if verein["id"] in (s["heim_id"], s["gast_id"]) or _passt(verein["name"], s)]
            if not spiele and (liga is not None or verein is not None):
                was, hinweis = "naechste", "Gerade läuft kein Spiel; das sind die nächsten Termine."
        if was in ("naechste", "letzte"):
            if liga is None and verein is None:
                raise SportError("SPORT_SACHE", "für Spielplan oder Ergebnisse braucht es eine Liga oder einen Verein")
            spiele = self.plan(liga_id=liga["id"] if liga else "", verein_id=verein["id"] if verein else "", richtung="previous" if was == "letzte" else "next")
            spiele.sort(key=lambda s: (s["datum"], s["zeit"]), reverse=(was == "letzte"))
        return {"was": was, "spiele": spiele[:MAX_SPIELE], "liga": liga, "verein": verein, "quelle": QUELLE, "stand": stand, "hinweis": hinweis}


def _nummer(s: str) -> str:
    n = re.sub(r"\D", "", str(s))[:12]
    if not n:
        raise SportError("SPORT_SACHE", "keine gültige Nummer")
    return n


def _suchwort(s: str) -> str:
    return urllib.parse.quote(re.sub(r"\s+", "_", s.strip()), safe="_-")


def _klingt_nach_verein(sache: str) -> bool:
    return not re.search(r"\b(liga|league|cup|pokal|serie|division|championship|formula|formel|nba|nfl|nhl|mlb|del|bbl|mls)\b", sache, re.I)


def _passt(name: str, spiel: dict) -> bool:
    n = name.lower()
    return n in spiel["heim"].lower() or n in spiel["gast"].lower()


def liga_alias(text: str) -> str:
    m = _LIGA_RE.search(str(text or ""))
    return m.group(1) if m else ""


__all__ = ["Sport", "SportError", "spiel_kurz", "liga_alias", "LIGEN", "ZUSTAND", "LAEUFT", "VORBEI", "QUELLE", "SEITE", "SCHLUESSEL_DATEI", "LIVE_S", "PLAN_S", "JE_MINUTE"]
