# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import http.client
import json
import re
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import geheim
import sicher_schreiben
import wissen

TLS_KONTEXT = ssl.create_default_context
STANDARD_ADRESSE = "https://kiplatz.at:8444"
ALTE_ADRESSEN: dict[str, str] = {}
DIRNAME = "community"
SCHLUESSEL_DATEI = "schluessel"
GERAET_DATEI = "geraet.json"
TIMEOUT_S = 8.0
WEBSUCHE_TIMEOUT_S = 20.0
SEITE_TIMEOUT_S = 40.0
ERGEBNIS_TIMEOUT_S = 60.0
PRUEFSTAND_ERGEBNIS_TIMEOUT_S = 180.0
MAX_ANTWORT = 4 * 1024 * 1024
_UA = "CommunityAI-Fenster/1"
LEITUNG_RUHE_S = 60.0
SCHLUESSEL_ERNEUERN_TAGE = 90
LEITUNGEN_MAX = 4
_LEITUNG_WEG = (http.client.RemoteDisconnected, http.client.BadStatusLine, ConnectionResetError, ConnectionAbortedError, BrokenPipeError)

_ZWECKE = {
    "platzl-start": "Community-Server: Platzl verbinden (nur eine Zufallsnummer)", "platzl-abholen": "Community-Server: Platzl-Freigabe abholen (verschlüsselt)",
    "wiki-vektoren": "Community-Server: Wikipedia-Vektoren suchen oder anbieten (nur Ausgabe und Modell)", "zuhause-anbieten": "Community-Server: Code für „Frag dein Zuhause“ anmelden (nur eine Kennung, kein Schlüssel)",
    "zuhause-koppeln": "Community-Server: mit dem PC daheim koppeln (nur eine Kennung, kein Schlüssel)", "zuhause-liste": "Community-Server: gekoppelte Geräte ansehen",
    "zuhause-entfernen": "Community-Server: Kopplung lösen", "wiki-vektoren-geholt": "Community-Server: Wikipedia-Vektoren übernommen",
    "fenster-anlegen": "Community-Server: Frag-Fenster anmelden (nur Name und Website, nie die Unterlagen)", "fenster-entfernen": "Community-Server: Frag-Fenster entfernen",
    "cwiki": "Community-Server: Wiki-Vorschläge ansehen, vorschlagen und abstimmen (Frage, Text und Quelle, die du selbst einträgst; nie, wer du bist)", "hallo": "Community-Server: ist er da?", "rechenstand": "Community-Server: wer ist online?", "auftrag": "Community-Server: nach Arbeit fragen",
    "ergebnis": "Community-Server: Ergebnis abgeben", "sammler": "Community-Server: Nachschub verwalten (Admin)", "sammler-setzen": "Community-Server: Nachschub verwalten (Admin)",
    "sammler-jetzt": "Community-Server: Nachschub jetzt holen (Admin)", "frage-stellen": "Community-Server: deine Frage stellen", "antwort": "Community-Server: Antwort holen oder abgeben",
    "antwort-teil": "Community-Server: Antwort tippt", "frage-aufgeben": "Community-Server: Frage zurückziehen", "websuche": "Community-Suche (Suchbegriff geht zum Server)",
    "merken": "Community-Server: Nachgeschautes für alle merken", "seite": "Community-Server: Website für alle merken", "suche": "Community-Server: im Wissen suchen",
    "quellen": "Community-Server: Quellenliste", "meldung-inhalt": "Community-Server: Inhalt einer gemeldeten Quelle (Admin)", "rangliste": "Community-Server: Bestenliste", "teams": "Community-Server: Team-Rangliste", "teams-admin": "Community-Server: Teams verwalten (Admin)", "team-admin": "Community-Server: Team sperren, umbenennen, entfernen (Admin)", "lernen": "Community-Server: Schalter „Meine Fragen helfen beim Lernen“", "mein-team": "Community-Server: dein Team und der Name in der Bestenliste (Konto)", "melden": "Community-Server: Quelle melden", "meldungen": "Community-Server: Meldungen (Admin)",
    "einladung": "Community-Server: Einladungscode", "not-aus": "Community-Server: Not-Aus schalten (Admin)", "admin-ernennen": "Community-Server: Admin ernennen", "geraet-mit-code": "Community-Server: Gerät anmelden", "meine-daten": "Community-Server: was er über dieses Gerät weiß",
    "austreten": "Community-Server: austreten", "fehlerbericht": "Community-Server: Fehlerbericht an den Admin", "fehlerberichte": "Community-Server: Fehlerberichte (Admin)",
    "pruefung-anbieten": "Community-Server: Antwort prüfen lassen", "pruefungen": "Community-Server: offene Prüfungen", "pruefung-abgeben": "Community-Server: Urteil abgeben",
    "pruefung-stand": "Community-Server: Stand der Prüfung", "ortswissen": "Community-Server: Ortswissen eintragen", "rueckmeldung": "Community-Server: Rückmeldung zu einer Antwort",
    "download": "Community-Server: Update holen", "modelle": "Community-Server: Modell holen",
    "konto-anmeldung": "Community-Server: wie die Anmeldung mit dem Konto geht", "konto-anmelden": "Community-Server: Anmeldenachweis des Kontos abgeben",
    "konto-abmelden": "Community-Server: Konto vom Gerät lösen",
    "konto-liste": "Community-Server: Konten, die auf diesem Gerät angemeldet waren", "konto-wechseln": "Community-Server: zu einem anderen deiner Konten wechseln",
    "konto-start": "Community-Server: mit dem Konto beitreten (Beginn)", "konto-ergebnis": "Community-Server: mit dem Konto beitreten (Zugang abholen)",
    "meine-geraete": "Community-Server: deine Geräte (Konto)", "geraet-abmelden": "Community-Server: ein Gerät deines Kontos abmelden",
    "ueberall-abmelden": "Community-Server: auf allen anderen Geräten abmelden",
    "abgleich": "Community-Server: Gespräche abgleichen (Ende-zu-Ende-verschlüsselt, der Server sieht nur Datensalat)",
}

SPRACHE = "de"


class CommunityError(app_core.AppError):
    pass


def _iso_s(wert) -> float:
    try:
        return datetime.strptime(str(wert), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _leitung_schliessen(c) -> None:
    try:
        c.close()
    except Exception:
        pass


class _Leitungen:

    def __init__(self, adresse: str, ctx, *, verbinden=None, uhr=None) -> None:
        self.adresse = adresse
        teile = urllib.parse.urlsplit(adresse)
        self.https = teile.scheme == "https"
        self.host = teile.hostname or ""
        self.port = teile.port or (443 if self.https else 80)
        self._ctx = ctx
        self._verbinden = verbinden or self._neu
        self._uhr = uhr or time.monotonic
        self._frei: list[tuple[object, float]] = []
        self._lock = threading.Lock()

    def _neu(self, timeout: float):
        if self.https:
            return http.client.HTTPSConnection(self.host, self.port, timeout=timeout, context=self._ctx)
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout)

    def holen(self, timeout: float) -> tuple[object, bool]:
        with self._lock:
            while self._frei:
                c, seit = self._frei.pop()
                if self._uhr() - seit > LEITUNG_RUHE_S:
                    _leitung_schliessen(c)
                    continue
                c.timeout = timeout
                setzen = getattr(getattr(c, "sock", None), "settimeout", None)
                if setzen is not None:
                    try:
                        setzen(timeout)
                    except OSError:
                        pass
                return c, True
        return self._verbinden(timeout), False

    def zurueck(self, c) -> None:
        with self._lock:
            if len(self._frei) < LEITUNGEN_MAX:
                self._frei.append((c, self._uhr()))
                return
        _leitung_schliessen(c)

    def alle_schliessen(self) -> None:
        with self._lock:
            frei, self._frei = self._frei, []
        for c, _ in frei:
            _leitung_schliessen(c)

    @property
    def freie(self) -> int:
        with self._lock:
            return len(self._frei)


@dataclass(frozen=True)
class Stand:
    erreichbar: bool
    anzahl: int
    name: str
    text: str


class Community:
    def __init__(self, base_dir: Path, *, adresse: str | None = None, oeffner=None, sicherung: Path | None = None, verbinden=None, uhr=None) -> None:
        self.dir = Path(base_dir) / DIRNAME
        self._sicherung = Path(sicherung) if sicherung else None
        self.wiederhergestellt = False
        self._einstellung = self.dir / "einstellung.json"
        self.adresse = (adresse or self._gelesene_adresse() or STANDARD_ADRESSE).rstrip("/")
        self.bei_weitergeben = None
        self._oeffner = oeffner
        self.teil_fehler = 0
        self._ctx = TLS_KONTEXT()
        self._leitungen = _Leitungen(self.adresse, self._ctx, verbinden=verbinden, uhr=uhr)
        self._leitung_extras = {"verbinden": verbinden, "uhr": uhr}
        self.letzte_suche = "wort"
        self.takt_s = 0


    def _gelesene_adresse(self) -> str | None:
        try:
            d = json.loads(self._einstellung.read_text(encoding="utf-8")) if self._einstellung.exists() else {}
            a = d.get("adresse") if isinstance(d, dict) else None
            a = str(a).rstrip("/") if a else ""
            if not a.lower().startswith("https://"):
                return None
            neu = ALTE_ADRESSEN.get(a.lower())
            if neu:
                try:
                    sicher_schreiben.json_datei(self._einstellung, {**d, "adresse": neu})
                except OSError:
                    pass
                return neu
            return a
        except (OSError, ValueError):
            return None

    def schluessel(self) -> str | None:
        p = self.dir / SCHLUESSEL_DATEI
        try:
            roh = p.read_text(encoding="ascii").strip() if p.exists() else ""
            s = geheim.lesen(roh).strip()
        except (OSError, UnicodeDecodeError, geheim.GeheimError):
            return None
        if not (len(s) == 64 and all(c in "0123456789abcdef" for c in s)):
            return None
        if not geheim.geschuetzt(roh):
            try:
                sicher_schreiben.text(p, geheim.schuetzen(s))
            except OSError:
                pass
        return s

    def ist_admin(self) -> bool:
        return self.schluessel() is not None or self.admin_laut_server()

    def admin_laut_server(self) -> bool:
        try:
            d = json.loads(self._einstellung.read_text(encoding="utf-8")) if self._einstellung.exists() else {}
            return bool(isinstance(d, dict) and d.get("admin_laut_server")) and self.geraet() is not None
        except (OSError, ValueError):
            return False

    def _admin_merken(self, an: bool) -> None:
        try:
            d = json.loads(self._einstellung.read_text(encoding="utf-8")) if self._einstellung.exists() else {}
            d = d if isinstance(d, dict) else {}
            if bool(d.get("admin_laut_server")) == bool(an):
                return
            d["admin_laut_server"] = bool(an)
            self.dir.mkdir(parents=True, exist_ok=True)
            sicher_schreiben.json_datei(self._einstellung, d, indent=1)
        except (OSError, ValueError):
            pass

    def geraet(self) -> dict | None:
        d = sicher_schreiben.json_laden(self.dir / GERAET_DATEI, None, art=dict)
        if not isinstance(d, dict) or not d.get("kennung") or not d.get("schluessel"):
            d = self._aus_sicherung()
            if d is None:
                return None
        roh = str(d["schluessel"])
        try:
            d = {**d, "schluessel": geheim.lesen(roh)}
        except geheim.GeheimError:
            return None
        if not geheim.geschuetzt(roh):
            self._geraet_speichern(d)
        return d

    def _geraet_speichern(self, d: dict) -> None:
        app_core.ensure_plain_directory(self.dir)
        inhalt = {**d, "schluessel": geheim.schuetzen(str(d.get("schluessel", "")))}
        sicher_schreiben.json_datei(self.dir / GERAET_DATEI, inhalt)
        self._sicherung_schreiben(inhalt)


    def schluessel_faellig(self, *, rueckweg_s: float = 0.0, jetzt: float | None = None) -> bool:
        g = self.geraet()
        if g is None:
            return False
        zuletzt = _iso_s(g.get("erneuert") or g.get("seit"))
        jetzt = time.time() if jetzt is None else jetzt
        return zuletzt <= 0 or jetzt - zuletzt >= SCHLUESSEL_ERNEUERN_TAGE * 86400 or float(rueckweg_s or 0) > zuletzt

    def schluessel_erneuern(self) -> None:
        g = self.geraet()
        if g is None:
            raise CommunityError("COMMUNITY_GERAET", "dieses Gerät ist bei der Community noch nicht angemeldet")
        a = self._anfrage("/geraet-schluessel-erneuern", {}, als_geraet=True)
        neu = str(a.get("schluessel") or "")
        if len(neu) != 64 or any(c not in "0123456789abcdef" for c in neu):
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keinen brauchbaren neuen Schlüssel geschickt; der alte gilt weiter")
        self._geraet_speichern({**g, "schluessel": neu, "erneuert": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        if (self.geraet() or {}).get("schluessel") != neu:
            raise CommunityError("COMMUNITY_SPEICHERN", "der neue Schlüssel ließ sich auf diesem Gerät nicht speichern; der alte gilt weiter")
        self._anfrage("/geraet-schluessel-bestaetigen", {}, als_geraet=True)

    def _sicherung_datei(self) -> Path | None:
        if self._sicherung is None:
            return None
        return self._sicherung / f"geraet-{hashlib.sha256(self.adresse.encode('utf-8')).hexdigest()[:12]}.json"

    def _sicherung_schreiben(self, inhalt: dict) -> None:
        p = self._sicherung_datei()
        if p is None:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if sicher_schreiben.json_laden(p, None, art=dict) != inhalt:
                sicher_schreiben.json_datei(p, inhalt)
        except OSError:
            pass

    def _aus_sicherung(self) -> dict | None:
        p = self._sicherung_datei()
        if p is None:
            return None
        d = sicher_schreiben.json_laden(p, None, art=dict)
        if not isinstance(d, dict) or not d.get("kennung") or not d.get("schluessel"):
            return None
        try:
            geheim.lesen(str(d["schluessel"]))
            app_core.ensure_plain_directory(self.dir)
            sicher_schreiben.json_datei(self.dir / GERAET_DATEI, d)
        except (geheim.GeheimError, OSError, app_core.AppError):
            return None
        self.wiederhergestellt = True
        return d

    def sicherung_pruefen(self) -> None:
        if self._sicherung is None:
            return
        d = sicher_schreiben.json_laden(self.dir / GERAET_DATEI, None, art=dict)
        if isinstance(d, dict) and d.get("kennung") and d.get("schluessel") and geheim.geschuetzt(str(d["schluessel"])):
            self._sicherung_schreiben(d)


    def _anfrage(self, weg: str, body: dict | None = None, *, mit_schluessel: bool = False, als_geraet: bool = False, timeout: float = TIMEOUT_S) -> dict:
        kopf = {"User-Agent": _UA, "Accept": "application/json", "Accept-Language": SPRACHE}
        daten = None
        if body is not None:
            daten = json.dumps(body, ensure_ascii=False).encode("utf-8")
            kopf["Content-Type"] = "application/json"
        if mit_schluessel:
            s = self.schluessel()
            if s is None and self.admin_laut_server():
                als_geraet = True
            elif s is None:
                raise CommunityError("COMMUNITY_SCHLUESSEL", "dafür braucht es den Community-Schlüssel; den hat nur der Admin")
            else:
                kopf["X-Schluessel"] = s
        if als_geraet:
            g = self.geraet()
            if g is None:
                raise CommunityError("COMMUNITY_GERAET", "dieses Gerät ist bei der Community noch nicht angemeldet; der Admin meldet es an")
            kopf["X-Geraet"] = str(g["kennung"])
            kopf["X-Geraet-Schluessel"] = str(g["schluessel"])
        methode = "POST" if daten is not None else "GET"
        if self._oeffner is not None or self._hinter_proxy():
            req = urllib.request.Request(self.adresse + weg, data=daten, headers=kopf, method=methode)
            oeffner = self._oeffner or (lambda r, timeout: urllib.request.urlopen(r, timeout=timeout, context=self._ctx))
            try:
                with oeffner(req, timeout=timeout) as r:
                    roh = r.read(MAX_ANTWORT)
                    antwort = json.loads(roh.decode("utf-8") or "{}")
            except urllib.error.HTTPError as exc:
                try:
                    fehler = json.loads(exc.read(MAX_ANTWORT).decode("utf-8") or "{}")
                except ValueError:
                    fehler = {}
                raise CommunityError("COMMUNITY_" + str(fehler.get("fehler") or exc.code), str(fehler.get("text") or f"der Server antwortet mit {exc.code}")) from None
            except CommunityError:
                raise
            except Exception as exc:
                raise CommunityError("COMMUNITY_UNERREICHBAR", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
        else:
            status, roh = self._ueber_leitung(methode, weg, daten, kopf, timeout)
            try:
                antwort = json.loads(roh.decode("utf-8") or "{}")
            except ValueError as exc:
                if status < 400:
                    raise CommunityError("COMMUNITY_UNERREICHBAR", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None
                antwort = {}
            if status >= 400:
                fehler = antwort if isinstance(antwort, dict) else {}
                raise CommunityError("COMMUNITY_" + str(fehler.get("fehler") or status), str(fehler.get("text") or f"der Server antwortet mit {status}"))
        import datenfluss
        datenfluss.melden(self.adresse, _ZWECKE.get(weg.split("?")[0].split("/")[1] if "/" in weg else weg, "Community-Server: " + weg.split("?")[0]), len(daten or b""), len(roh))
        if not isinstance(antwort, dict):
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat etwas Unlesbares geschickt")
        return antwort

    def _hinter_proxy(self) -> bool:
        try:
            teile = urllib.parse.urlsplit(self.adresse)
            return bool(urllib.request.getproxies().get(teile.scheme)) and not urllib.request.proxy_bypass(teile.hostname or "")
        except Exception:
            return False

    def _ueber_leitung(self, methode: str, weg: str, daten: bytes | None, kopf: dict, timeout: float) -> tuple[int, bytes]:
        if self._leitungen.adresse != self.adresse:
            self._leitungen.alle_schliessen()
            self._leitungen = _Leitungen(self.adresse, self._ctx, **self._leitung_extras)
        versuch = 0
        while True:
            c, wieder = self._leitungen.holen(timeout)
            try:
                c.request(methode, weg, body=daten, headers=kopf)
                r = c.getresponse()
                roh = r.read(MAX_ANTWORT + 1)
                if len(roh) > MAX_ANTWORT:
                    _leitung_schliessen(c)
                    raise CommunityError("COMMUNITY_ANTWORT", "der Server hat zu viel auf einmal geschickt")
                if getattr(r, "will_close", False):
                    _leitung_schliessen(c)
                else:
                    self._leitungen.zurueck(c)
                return r.status, roh
            except CommunityError:
                raise
            except Exception as exc:
                _leitung_schliessen(c)
                if wieder and versuch == 0 and methode == "GET" and isinstance(exc, _LEITUNG_WEG):
                    versuch += 1
                    continue
                raise CommunityError("COMMUNITY_UNERREICHBAR", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None


    def stand(self) -> Stand:
        try:
            h = self._anfrage("/hallo")
            n = int(h.get("anzahl", 0) or 0)
            return Stand(True, n, str(h.get("name") or "Community"), f"{n} Quellen am Community-Server")
        except app_core.AppError as exc:
            return Stand(False, 0, "Community", exc.detail)

    def pruefen_pausiert(self, *, frisch: bool = False) -> bool:
        jetzt = time.monotonic()
        merk = getattr(self, "_pausiert_merk", None)
        if merk is not None and jetzt - merk[0] < 600 and not frisch:
            return merk[1]
        try:
            wert = bool(self._anfrage("/hallo").get("pruefen_pausiert"))
        except app_core.AppError:
            wert = merk[1] if merk is not None else False
        self._pausiert_merk = (jetzt, wert)
        return wert

    def suche_stand(self) -> dict | None:
        jetzt = time.monotonic()
        merk = getattr(self, "_suche_merk", None)
        if merk is not None and jetzt - merk[0] < 600:
            return merk[1]
        try:
            h = self._anfrage("/hallo")
            wert = {"frei": int(h["suche_frei"]), "gesamt": int(h["suche_gesamt"])} if "suche_frei" in h else None
        except (app_core.AppError, KeyError, TypeError, ValueError):
            wert = merk[1] if merk is not None else None
        self._suche_merk = (jetzt, wert)
        return wert

    def quellen_melden(self, quellen: dict) -> None:
        self._anfrage("/quellen-stand", {"quellen": quellen}, als_geraet=True)

    def fenster_frei(self) -> bool:
        try:
            return bool(self._anfrage("/hallo").get("fenster"))
        except app_core.AppError:
            return False

    def quellen(self) -> list[dict]:
        return [q for q in self._anfrage("/quellen").get("quellen", []) if isinstance(q, dict)]

    def suchen(self, frage: str, *, n: int = wissen.TREFFER, vektor: list[float] | None = None, fachgebiete=None) -> tuple[list[wissen.Treffer], int]:
        body = {"frage": frage, "n": n}
        if vektor:
            body["vektor"] = vektor
        fg = wissen.fachgebiete_pruefen(fachgebiete)
        if fg:
            body["fachgebiete"] = fg
        a = self._anfrage("/suche", body)
        self.letzte_suche = str(a.get("suche") or "wort")
        treffer = []
        for t in a.get("treffer", []):
            q = t.get("quelle") or {}
            try:
                quelle = wissen.quelle_aus(q)
                treffer.append(wissen.Treffer(quelle, str(t.get("text", "")), float(t.get("punkte", 0.0))))
            except (KeyError, ValueError, TypeError):
                continue
        return treffer, int(a.get("im_speicher", 0) or 0)

    def kann_merken(self) -> bool:
        return self.ist_admin() or self.geraet() is not None

    def seite_lesen(self, adresse: str, *, grund: str, notiz: str = "", namensnennung: str = "") -> dict:
        body = {"adresse": adresse, "grund": grund, "notiz": notiz}
        if namensnennung:
            body["namensnennung"] = namensnennung
        a = self._anfrage("/seite", body, mit_schluessel=True, timeout=SEITE_TIMEOUT_S)
        return a.get("quelle") or {}


    def hausordnung(self) -> str:
        return str(self._anfrage("/hausordnung").get("text") or "")

    def melden(self, kennung: str, grund: str) -> str:
        a = self._anfrage("/melden", {"kennung": kennung, "grund": grund}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())
        return str(a.get("text") or "Gemeldet.")

    def meldungen(self) -> tuple[list[dict], dict]:
        a = self._anfrage("/meldungen", mit_schluessel=True)
        return [m for m in a.get("meldungen", []) if isinstance(m, dict)], {str(k): str(v) for k, v in (a.get("herkunft") or {}).items()}

    def fehlerbericht(self, bau: str, text: str, windows: str = "") -> str:
        a = self._anfrage("/fehlerbericht", {"bau": bau, "text": text, "windows": windows}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())
        return str(a.get("text") or "Danke. Der Bericht liegt beim Admin.")

    def fehlerberichte(self) -> list[dict]:
        a = self._anfrage("/fehlerberichte", mit_schluessel=True)
        return [f for f in a.get("fehlerberichte", []) if isinstance(f, dict)]

    def meldung_inhalt(self, kennung: str) -> dict:
        return self._anfrage("/meldung-inhalt", {"kennung": kennung}, mit_schluessel=True)

    def meldung_erledigt(self, kennung: str) -> None:
        self._anfrage("/meldung-erledigt", {"kennung": kennung}, mit_schluessel=True)

    def geraet_sperren(self, kennung: str, gesperrt: bool, grund: str = "") -> dict:
        return self._anfrage("/geraet-sperren", {"kennung": kennung, "gesperrt": bool(gesperrt), "grund": grund}, mit_schluessel=True)

    def geraet_lebenslang(self, kennung: str, grund: str = "") -> dict:
        return self._anfrage("/geraet-lebenslang", {"kennung": kennung, "grund": grund}, mit_schluessel=True)

    def konto_suchen(self, q: str, alle: bool = False) -> dict:
        return self._anfrage("/konto-suchen", {"alle": True} if alle else {"q": q}, mit_schluessel=True, timeout=30 if alle else 20)

    def konto_ueberall(self, kid: str, aktion: str, grund: str = "") -> dict:
        return self._anfrage("/konto-ueberall", {"id": kid, "aktion": aktion, "grund": grund}, mit_schluessel=True, timeout=90)

    def geraet_entfernen(self, kennung: str) -> dict:
        return self._anfrage("/geraet-entfernen", {"kennung": kennung}, mit_schluessel=True)

    def entfernen(self, kennung: str) -> None:
        self._anfrage("/entfernen", {"kennung": kennung}, mit_schluessel=True)


    def geraet_anmelden(self, name: str) -> dict:
        a = self._anfrage("/geraet", {"name": name}, mit_schluessel=True)
        d = {"kennung": str(a.get("kennung", "")), "schluessel": str(a.get("schluessel", "")), "name": name, "seit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if not d["kennung"] or not d["schluessel"]:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keine Gerätekennung geschickt")
        self._geraet_speichern(d)
        return d

    def geraete(self) -> list[dict]:
        return [g for g in self._anfrage("/geraete", {}, mit_schluessel=True).get("geraete", []) if isinstance(g, dict)]

    def vorschaubild(self, nummer: str) -> bytes | None:
        nummer = str(nummer or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", nummer):
            return None
        req = urllib.request.Request(f"{self.adresse}/vorschau?v={nummer}", headers={"User-Agent": _UA, "Accept": "image/jpeg"})
        try:
            if self._oeffner is not None:
                antwort = self._oeffner(req, timeout=TIMEOUT_S)
            else:
                antwort = urllib.request.urlopen(req, timeout=TIMEOUT_S, context=self._ctx)
            with antwort as r:
                daten = r.read(150_001)
        except Exception:
            return None
        return daten if len(daten) <= 150_000 and daten.startswith(b"\xff\xd8\xff") else None

    def video_rahmen_adresse(self, nummer: str) -> str | None:
        nummer = str(nummer or "")
        return f"{self.adresse}/video-rahmen?v={nummer}" if re.fullmatch(r"[A-Za-z0-9_-]{11}", nummer) else None

    def rechenstand(self) -> dict:
        st = self._anfrage("/rechenstand", als_geraet=self.geraet() is not None)
        g = st.get("geraet")
        if isinstance(g, dict) and "admin" in g:
            self._admin_merken(bool(g["admin"]))
        return st


    def not_aus_setzen(self, an: bool, grund: str = "") -> dict:
        return self._anfrage("/not-aus", {"an": bool(an), "grund": str(grund or "")}, mit_schluessel=True)


    def sammler_stand(self) -> dict:
        return self._anfrage("/sammler", mit_schluessel=True)

    def sammler_setzen(self, daten: dict) -> dict:
        return self._anfrage("/sammler-setzen", dict(daten), mit_schluessel=True)

    def sammler_jetzt(self) -> dict:
        return self._anfrage("/sammler-jetzt", {}, mit_schluessel=True, timeout=90)


    def pruefstand_stand(self) -> dict:
        return self._anfrage("/pruefstand?ansicht=admin", mit_schluessel=True)

    def pruefstand_setzen(self, daten: dict) -> dict:
        return self._anfrage("/pruefstand-setzen", dict(daten), mit_schluessel=True)

    def trainingsliste_zahl(self) -> dict:
        return self._anfrage("/trainingsliste?zahl=1", mit_schluessel=True)

    def pruefstand_holen(self) -> list[dict]:
        return [f for f in self._anfrage("/pruefstand", als_geraet=True).get("fragen", []) if isinstance(f, dict)]

    def pruefrunde_holen(self, bau: str, fassung: str = "", *, probelauf: bool = False) -> tuple[list[dict], dict]:
        weg = "/pruefstand?" + urllib.parse.urlencode({"runde": "1", "bau": str(bau)[:40], "fassung": str(fassung or "")[:120], **({"probelauf": "1"} if probelauf else {})})
        a = self._anfrage(weg, als_geraet=True)
        return [f for f in a.get("fragen", []) if isinstance(f, dict)], (a.get("runde") if isinstance(a.get("runde"), dict) else {})

    def pruefstand_ergebnis(self, antworten: list[dict], wege: dict, *, runde: str = "") -> dict:
        return self._anfrage("/pruefstand-ergebnis", {"antworten": antworten, "wege": wege, **({"runde": str(runde)[:20]} if runde else {})},
                             als_geraet=True, timeout=PRUEFSTAND_ERGEBNIS_TIMEOUT_S)

    def messreihe_ergebnis(self, antworten: list[dict], *, modell: str, fehler: str = "") -> dict:
        return self._anfrage("/messreihe-ergebnis", {"antworten": antworten, "modell": str(modell)[:120], "fehler": str(fehler)[:200]},
                             als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def platzl_start(self, ticket: str) -> dict:
        return self._anfrage("/platzl-start", {"ticket": str(ticket)}, als_geraet=True)

    def platzl_abholen(self, ticket: str) -> dict:
        return self._anfrage("/platzl-abholen", {"ticket": str(ticket)}, als_geraet=True)

    def admin_ernennen(self, kennung: str, an: bool = True) -> dict:
        return self._anfrage("/admin-ernennen", {"kennung": str(kennung), "an": bool(an)}, mit_schluessel=True)

    def schluessel_wechseln(self) -> None:
        alt = self.schluessel()
        if alt is None:
            raise CommunityError("COMMUNITY_SCHLUESSEL", "dieses Gerät hat den Community-Schlüssel nicht; wechseln kann ihn nur ein Gerät, das ihn hat")
        a = self._anfrage("/admin-schluessel-erneuern", {}, mit_schluessel=True)
        neu = str(a.get("schluessel") or "")
        if len(neu) != 64 or any(c not in "0123456789abcdef" for c in neu):
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keinen brauchbaren neuen Schlüssel geschickt; der alte gilt weiter")
        p = self.dir / SCHLUESSEL_DATEI
        sicher_schreiben.text(p, geheim.schuetzen(neu))
        if self.schluessel() != neu:
            try:
                sicher_schreiben.text(p, geheim.schuetzen(alt))
            except OSError:
                pass
            raise CommunityError("COMMUNITY_SPEICHERN", "der neue Schlüssel ließ sich auf diesem Gerät nicht speichern; der alte gilt weiter")
        self._anfrage("/admin-schluessel-bestaetigen", {}, mit_schluessel=True)

    def auftrag_holen(self, *, pruefen: bool = False, antworten: bool = False, leistung: dict | None = None, vertiefen: bool = False, speicher: dict | None = None, stand: str = "",
                      warten_s: float = 0.0, nur_fragen: bool = False, vorab: bool = False) -> dict | None:
        flags = [f for f, an in (("pruefen=1", pruefen), ("antworten=1", antworten), ("vertiefen=1", vertiefen), ("nur_fragen=1", nur_fragen),
                                 ("vorab=1", vorab and not nur_fragen)) if an]
        if leistung:
            werte = {"modell": str(leistung.get("modell") or "")[:60]}
            if leistung.get("geschwister"):
                werte["geschwister"] = str(min(int(leistung.get("geschwister") or 0), 9))
                werte["andere_benutzer"] = str(min(int(leistung.get("andere_benutzer") or 0), 9))
            if antworten:
                werte = {"warm": "1" if leistung.get("warm") else "0", "tempo": f"{float(leistung.get('tempo') or 0):.2f}", "skills": "1", **werte}
                if leistung.get("kopie"):
                    werte["kopie"] = "1"
            flags.append(urllib.parse.urlencode(werte))
        if speicher:
            flags.append(urllib.parse.urlencode({"speicher_mb": int(speicher.get("limit_mb", 0) or 0), "frei_mb": int(speicher.get("frei_mb", 0) or 0)}))
        if stand:
            flags.append(urllib.parse.urlencode({"stand": " ".join(str(stand).split())[:200]}))
        if antworten and warten_s > 0:
            flags.append(urllib.parse.urlencode({"warten": f"{float(warten_s):.0f}"}))
        a = self._anfrage("/auftrag" + ("?" + "&".join(flags) if flags else ""), als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)
        try:
            self.takt_s = max(0, min(30, int(a.get("takt_s", 0) or 0)))
        except (TypeError, ValueError):
            self.takt_s = 0
        self.gewartet = bool(a.get("gewartet"))
        if isinstance(a.get("weitergeben"), dict):
            self.gewartet = True
            if self.bei_weitergeben is not None:
                try:
                    self.bei_weitergeben(a["weitergeben"])
                except Exception:
                    pass
            return None
        return a if a.get("auftrag") else None


    def _geraet_kopf(self) -> dict:
        g = self.geraet()
        if g is None:
            raise CommunityError("COMMUNITY_GERAET", "dieses Gerät ist bei der Community noch nicht angemeldet; der Admin meldet es an")
        return {"User-Agent": _UA, "X-Geraet": str(g["kennung"]), "X-Geraet-Schluessel": str(g["schluessel"])}

    def _roh(self, req: urllib.request.Request, timeout: float):
        oeffner = self._oeffner or (lambda r, timeout: urllib.request.urlopen(r, timeout=timeout, context=self._ctx))
        try:
            return oeffner(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            try:
                fehler = json.loads(exc.read(MAX_ANTWORT).decode("utf-8") or "{}")
            except ValueError:
                fehler = {}
            raise CommunityError("COMMUNITY_" + str(fehler.get("fehler") or exc.code), str(fehler.get("text") or f"der Server antwortet mit {exc.code}")) from None
        except Exception as exc:
            raise CommunityError("COMMUNITY_UNERREICHBAR", f"der Community-Server ist gerade nicht erreichbar ({type(exc).__name__})") from None

    def scheibe_holen(self, kennung: str, ziel: Path, sha256: str) -> Path:
        import hashlib
        import datenfluss
        req = urllib.request.Request(f"{self.adresse}/scheibe/{kennung}", headers=self._geraet_kopf(), method="GET")
        teil = ziel.with_suffix(ziel.suffix + ".teil")
        h = hashlib.sha256()
        n = 0
        try:
            with self._roh(req, SEITE_TIMEOUT_S) as r, open(teil, "wb") as f:
                for stueck in iter(lambda: r.read(1024 * 1024), b""):
                    h.update(stueck)
                    f.write(stueck)
                    n += len(stueck)
                    if n > 64 * 1024 * 1024:
                        raise CommunityError("COMMUNITY_SCHEIBE_GROSS", "die Scheibe ist größer als erlaubt")
        except CommunityError:
            teil.unlink(missing_ok=True)
            raise
        except OSError as exc:
            teil.unlink(missing_ok=True)
            raise CommunityError("COMMUNITY_SCHEIBE_SCHREIBEN", f"die Scheibe konnte nicht gespeichert werden ({exc.strerror or type(exc).__name__})") from None
        datenfluss.melden(self.adresse, "Community-Server: Scheibe des gemeinsamen Wissens holen", 0, n)
        if h.hexdigest() != str(sha256).lower():
            teil.unlink(missing_ok=True)
            raise CommunityError("COMMUNITY_SCHEIBE_PRUEFSUMME", "die Scheibe kam beschädigt an")
        import os
        os.replace(teil, ziel)
        return ziel

    def gemeinschaft_stand(self, seit: int | None = None) -> dict:
        return self._anfrage("/gemeinschaft-stand" + (f"?seit={int(seit)}" if seit else ""), als_geraet=True)

    def gemeinschaft_pakete(self, shas: list[str], hoechstens: int) -> bytes:
        import datenfluss
        daten = json.dumps({"sha256": list(shas)}).encode("utf-8")
        kopf = {**self._geraet_kopf(), "Content-Type": "application/json"}
        req = urllib.request.Request(f"{self.adresse}/gemeinschaft-pakete", data=daten, headers=kopf, method="POST")
        teile: list[bytes] = []
        n = 0
        with self._roh(req, SEITE_TIMEOUT_S) as r:
            for stueck in iter(lambda: r.read(1024 * 1024), b""):
                n += len(stueck)
                if n > hoechstens:
                    raise CommunityError("COMMUNITY_PAKETE_GROSS", "die Pakete des Gemeinschaftswissens sind größer als erlaubt")
                teile.append(stueck)
        datenfluss.melden(self.adresse, "Community-Server: Pakete des Gemeinschaftswissens holen", len(daten), n)
        return b"".join(teile)

    def scheibe_bestaetigen(self, kennung: str, sha256: str) -> dict:
        return self._anfrage("/scheibe-bestaetigt", {"scheibe": kennung, "sha256": sha256}, als_geraet=True)

    def scheibe_abgegeben(self, kennung: str) -> dict:
        return self._anfrage("/scheibe-abgegeben", {"scheibe": kennung}, als_geraet=True)

    def scheiben_weg(self) -> list[str]:
        return [str(k) for k in (self._anfrage("/scheiben-weg", {}, als_geraet=True).get("weg") or []) if isinstance(k, str)][:200]

    def scheibe_liefern(self, kennung: str, pfad: Path) -> dict:
        import datenfluss
        daten = Path(pfad).read_bytes()
        kopf = {**self._geraet_kopf(), "Content-Type": "application/zip", "X-Scheibe": str(kennung)}
        req = urllib.request.Request(f"{self.adresse}/scheibe-liefern", data=daten, headers=kopf, method="POST")
        with self._roh(req, ERGEBNIS_TIMEOUT_S) as r:
            roh = r.read(MAX_ANTWORT)
        datenfluss.melden(self.adresse, "Community-Server: Scheibe für die Stichprobe liefern", len(daten), len(roh))
        try:
            antwort = json.loads(roh.decode("utf-8") or "{}")
        except ValueError:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat etwas Unlesbares geschickt") from None
        return antwort if isinstance(antwort, dict) else {}

    def wiki_vektoren_stand(self, *, ausgabe: str, modell: str, brauche: bool = False, biete: bool = False) -> dict:
        if self.geraet() is None:
            raise CommunityError("COMMUNITY_GERAET", "dieses Gerät ist nicht angemeldet")
        return self._anfrage("/wiki-vektoren", {"ausgabe": str(ausgabe)[:8], "modell": str(modell)[:64], "brauche": bool(brauche), "biete": bool(biete)}, als_geraet=True)

    def wiki_vektoren_geholt(self, kennung: str, *, ok: bool = True, grund: str = "") -> dict:
        body = {"scheibe": str(kennung)[:32]}
        if not ok:
            body.update(ok=False, grund=str(grund)[:32])
        return self._anfrage("/wiki-vektoren-geholt", body, als_geraet=True)


    def feiertage(self, land: str, jahr: int) -> list[dict] | None:
        d = self._anfrage("/feiertage", {"land": str(land)[:2].upper(), "jahr": int(jahr)}, als_geraet=True, timeout=8)
        tage = d.get("tage") if isinstance(d, dict) else None
        if not isinstance(tage, list) or not d.get("erreicht", True):
            return None
        return [t for t in tage if isinstance(t, dict)]

    def zuhause_anbieten(self, kid: str) -> dict:
        return self._anfrage("/zuhause-anbieten", {"kid": str(kid)[:32]}, als_geraet=True)

    def zuhause_koppeln(self, kid: str) -> dict:
        return self._anfrage("/zuhause-koppeln", {"kid": str(kid)[:32]}, als_geraet=True)

    def zuhause_liste(self) -> dict:
        return self._anfrage("/zuhause-liste", {}, als_geraet=True)

    def zuhause_entfernen(self, kid: str) -> dict:
        return self._anfrage("/zuhause-entfernen", {"kid": str(kid)[:32]}, als_geraet=True)


    def fenster_anlegen(self, name: str, websites: list[str]) -> dict:
        return self._anfrage("/fenster-anlegen", {"name": str(name)[:60], "websites": [str(w)[:200] for w in websites][:5]}, als_geraet=True)

    def fenster_entfernen(self) -> dict:
        return self._anfrage("/fenster-entfernen", {}, als_geraet=True)

    def zuhause_ablegen(self, kid: str, daten: bytes) -> str:
        import datenfluss
        kopf = {**self._geraet_kopf(), "Content-Type": "application/octet-stream", "X-Zuhause-Kid": str(kid)[:32]}
        req = urllib.request.Request(f"{self.adresse}/zuhause-ablage", data=bytes(daten), headers=kopf, method="POST")
        with self._roh(req, ERGEBNIS_TIMEOUT_S) as r:
            roh = r.read(MAX_ANTWORT)
        datenfluss.melden(self.adresse, "Community-Server: verschlüsselte Datei für dein Handy ablegen (Frag dein Zuhause)", len(daten), len(roh))
        token = str(json.loads(roh.decode("utf-8")).get("token", ""))
        if not re.fullmatch(r"[0-9a-f]{32}", token):
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keine Abholkennung geschickt")
        return token

    def zuhause_abholen(self, token: str) -> bytes:
        import datenfluss
        req = urllib.request.Request(f"{self.adresse}/zuhause-ablage/{str(token)[:32]}", headers=self._geraet_kopf(), method="GET")
        with self._roh(req, ERGEBNIS_TIMEOUT_S) as r:
            daten = r.read(80 * 1024 * 1024)
        datenfluss.melden(self.adresse, "Community-Server: Datei vom PC daheim abholen (verschlüsselt)", 0, len(daten))
        return daten

    def wiki_vektoren_anbieten(self, pfad: Path) -> dict:
        import datenfluss
        daten = Path(pfad).read_bytes()
        kopf = {**self._geraet_kopf(), "Content-Type": "application/zip"}
        req = urllib.request.Request(f"{self.adresse}/wiki-vektoren-anbieten", data=daten, headers=kopf, method="POST")
        with self._roh(req, ERGEBNIS_TIMEOUT_S) as r:
            roh = r.read(MAX_ANTWORT)
        datenfluss.melden(self.adresse, "Community-Server: Wikipedia-Vektoren für ein anderes Gerät (nur Zahlen, kein Text)", len(daten), len(roh))
        try:
            antwort = json.loads(roh.decode("utf-8") or "{}")
        except ValueError:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat etwas Unlesbares geschickt") from None
        return antwort if isinstance(antwort, dict) else {}

    def scheiben_landkarte(self) -> dict:
        return self._anfrage("/scheiben", mit_schluessel=True)


    def rueckmeldung(self, frage: str, antwort: str, grund: str, vorschlag: str, an: str) -> dict:
        body = {"frage": frage, "antwort": antwort, "grund": grund, "vorschlag": vorschlag, "an": an}
        return self._anfrage("/rueckmeldung", body, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())

    def rueckmeldungen(self) -> dict:
        return self._anfrage("/rueckmeldungen", {}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())

    def speicher_gut(self, kennung: str) -> dict:
        return self._anfrage("/speicher-gut", {"id": str(kennung)[:20]}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())

    def speicher_schlecht(self, kennung: str) -> dict:
        return self._anfrage("/speicher-schlecht", {"id": str(kennung)[:20]}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())

    def zaehlen(self, wert: str) -> dict:
        return self._anfrage("/zaehlen", {"wert": wert}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())


    def ortswissen_eintragen(self, ort: str, titel: str, text: str, adresse: str = "", monate: int = 6) -> dict:
        body = {"ort": ort, "titel": titel, "text": text, "adresse": adresse, "monate": int(monate)}
        a = self._anfrage("/ortswissen", body, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())
        return a.get("quelle") or {}

    def ortswissen_bestaetigen(self, kennung: str) -> dict:
        a = self._anfrage("/ortswissen-bestaetigen", {"kennung": kennung}, mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())
        return a.get("quelle") or {}


    def pruefung_anbieten(self, frage: str, antwort: str, quellen: list[str]) -> dict:
        return self._anfrage("/pruefung-anbieten", {"frage": frage, "antwort": antwort, "quellen": quellen}, als_geraet=True)

    def pruefungen(self) -> list[dict]:
        return [e for e in self._anfrage("/pruefungen", {}, als_geraet=True).get("pruefungen", []) if isinstance(e, dict)]

    def pruefung_abgeben(self, kennung: str, urteil: str, kommentar: str = "") -> dict:
        return self._anfrage("/pruefung-abgeben", {"kennung": kennung, "urteil": urteil, "kommentar": kommentar}, als_geraet=True)

    def pruefung_stand(self, kennungen: list[str]) -> dict:
        d = self._anfrage("/pruefung-stand", {"kennungen": kennungen}, als_geraet=True).get("stand", {})
        return d if isinstance(d, dict) else {}

    def meine_daten(self) -> dict:
        return self._anfrage("/meine-daten", {}, als_geraet=True)

    def austreten(self) -> dict:
        a = self._anfrage("/austreten", {}, als_geraet=True)
        s = self._sicherung_datei()
        if s is not None:
            try:
                s.unlink(missing_ok=True)
            except OSError:
                pass
        p = self.dir / GERAET_DATEI
        try:
            p.unlink()
        except OSError:
            pass
        return a


    def konto_anmeldung(self) -> dict:
        return self._anfrage("/konto-anmeldung")

    def konto_anmelden(self, id_token: str) -> dict:
        return self._anfrage("/konto-anmelden", {"id_token": str(id_token)}, als_geraet=True)

    def konto_abmelden(self) -> dict:
        return self._anfrage("/konto-abmelden", {}, als_geraet=True)

    def konto_liste(self) -> dict:
        return self._anfrage("/konto-liste", {}, als_geraet=True)

    def konto_wechseln(self, sub: str) -> dict:
        return self._anfrage("/konto-wechseln", {"sub": str(sub)[:200]}, als_geraet=True)

    def pc_qr_start(self) -> dict:
        return self._anfrage("/pc-qr-start", {}, als_geraet=True)

    def pc_qr_stand(self, code: str) -> dict:
        return self._anfrage("/pc-qr-stand", {"code": str(code)[:64]}, als_geraet=True)


    def meine_geraete(self) -> dict:
        return self._anfrage("/meine-geraete", {}, als_geraet=True)

    def geraet_abmelden(self, kennung: str) -> dict:
        return self._anfrage("/geraet-abmelden", {"kennung": str(kennung)[:40]}, als_geraet=True)

    def ueberall_abmelden(self) -> dict:
        return self._anfrage("/ueberall-abmelden", {}, als_geraet=True)

    def mein_konto_loeschen(self, bestaetigung: str) -> dict:
        return self._anfrage("/mein-konto-loeschen", {"bestaetigung": str(bestaetigung)[:20]}, als_geraet=True, timeout=90)

    def websuche(self, frage: str, n: int = 5, *, sprache: str = "", zeit: str = "", pruef: bool = False,
                 nur_gemerkt: bool = False) -> list[dict] | None:
        if self.geraet() is None and not self.ist_admin():
            raise CommunityError("COMMUNITY_GERAET", "dieses Gerät ist nicht angemeldet")
        body = {"frage": str(frage)[:300], "n": int(n)}
        if sprache:
            body["sprache"] = str(sprache)[:8]
        if zeit:
            body["zeit"] = str(zeit)[:8]
        if pruef:
            body["pruef"] = True
            if nur_gemerkt:
                body["nur_gemerkt"] = True
        a = self._anfrage("/websuche", body, mit_schluessel=self.ist_admin(), als_geraet=self.geraet() is not None, timeout=WEBSUCHE_TIMEOUT_S)
        if nur_gemerkt and a.get("gemerkt") is False:
            return None
        return [t for t in (a.get("treffer") or []) if isinstance(t, dict) and str(t.get("adresse", "")).startswith("https://")]

    def frage_stellen(self, nachrichten: list[dict], *, auszuege: list | None = None, frisch: bool = False, vorige: str = "", zuhause: dict | None = None,
                      skill: dict | None = None, fachgebiete=None) -> str:
        fg = wissen.fachgebiete_pruefen(fachgebiete)
        a = self._anfrage("/frage-stellen", {"nachrichten": nachrichten, "auszuege": auszuege or [], "frisch": bool(frisch),
                                             **({"vorige": str(vorige)[:32]} if vorige else {}), **({"zuhause": zuhause} if zuhause else {}),
                                             **({"skill": skill} if skill else {}), **({"fachgebiete": fg} if fg else {})},
                           als_geraet=True)
        k = str(a.get("kennung", ""))
        if not k:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keine Kennung für die Frage geschickt")
        return k

    def antwort_abholen(self, kennung: str, *, seit: str = "", warten_s: float = 0.0) -> dict:
        if not warten_s:
            return self._anfrage("/antwort/" + kennung, als_geraet=True)
        weg = "/antwort/" + kennung + "?" + urllib.parse.urlencode({"seit": seit, "warten": f"{float(warten_s):.0f}"})
        return self._anfrage(weg, als_geraet=True, timeout=TIMEOUT_S + float(warten_s))

    def frage_aufgeben(self, kennung: str) -> None:
        try:
            self._anfrage("/frage-aufgeben", {"kennung": kennung}, als_geraet=True)
        except CommunityError:
            pass

    def antwort_schritt(self, auftrag: str, schritt: str) -> None:
        try:
            self._anfrage("/antwort-teil", {"auftrag": auftrag, "schritt": schritt}, als_geraet=True, timeout=5.0)
        except app_core.AppError:
            self.teil_fehler += 1

    def antwort_verzicht(self, auftrag: str, grund: str) -> str:
        try:
            return str(self._anfrage("/antwort-verzicht", {"auftrag": auftrag, "grund": str(grund)[:200]}, als_geraet=True, timeout=10.0).get("wie", ""))
        except app_core.AppError:
            return ""

    def antwort_teil(self, auftrag: str, text: str) -> None:
        try:
            self._anfrage("/antwort-teil", {"auftrag": auftrag, "text": text}, als_geraet=True, timeout=5.0)
        except CommunityError:
            self.teil_fehler += 1

    def antwort_gezaehlt(self, dauer_s: float, wortstuecke: int, messung: dict | None = None) -> dict:
        body: dict = {"dauer_s": dauer_s, "wortstuecke": wortstuecke}
        if messung:
            body["messung"] = messung
        return self._anfrage("/antwort-gezaehlt", body, als_geraet=True)

    def antwort_senden(self, auftrag: str, text: str, lieferschein: dict, dauer_s: float, messung: dict | None = None, *, ablauf: dict | None = None) -> dict:
        body = {"auftrag": auftrag, "text": text, "lieferschein": lieferschein, "dauer_s": dauer_s}
        if messung:
            body["messung"] = messung
        if ablauf:
            body["ablauf"] = ablauf
        return self._anfrage("/antwort", body, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)


    def rangliste(self) -> dict:
        return self._anfrage("/rangliste", als_geraet=self.geraet() is not None)

    def team_rangliste(self) -> dict:
        return self._anfrage("/teams", als_geraet=self.geraet() is not None)

    def mein_team(self) -> dict:
        return self._anfrage("/mein-team", als_geraet=True)

    def teams_admin(self) -> list[dict]:
        return list(self._anfrage("/teams-admin", mit_schluessel=True).get("teams") or [])

    def team_admin(self, tid: str, aktion: str, grund: str = "", name: str = "") -> dict:
        return self._anfrage("/team-admin", {"id": tid, "aktion": aktion, "grund": grund, "name": name}, mit_schluessel=True)

    def lernen(self, an: bool | None = None) -> dict:
        return self._anfrage("/lernen", {} if an is None else {"an": bool(an)}, als_geraet=True)

    def team_aktion(self, aktion: str, **felder) -> dict:
        return self._anfrage("/mein-team", {"aktion": aktion, **felder}, als_geraet=True)

    def wiki_aktion(self, aktion: str, **felder) -> dict:
        return self._anfrage("/cwiki", {"aktion": aktion, **felder}, als_geraet=True)

    def fehler_liste(self) -> dict:
        a = self._anfrage("/fehler")
        return {"fehler": [e for e in a.get("fehler", []) if isinstance(e, dict)], "wer": [str(w) for w in a.get("wer", [])]}

    def fehler_melden(self, frage: str, wer: str, falsch: str, richtig: str, quelle: str = "") -> str:
        a = self._anfrage("/fehler", {"frage": frage, "wer": wer, "falsch": falsch, "richtig": richtig, "quelle": quelle},
                          mit_schluessel=self.ist_admin(), als_geraet=not self.ist_admin())
        return str(a.get("text") or "Gemerkt.")

    def fehler_woche(self, kennung: str) -> list[dict]:
        return [e for e in self._anfrage("/fehler-woche", {"kennung": kennung}, mit_schluessel=True).get("fehler", []) if isinstance(e, dict)]

    def fehler_entfernen(self, kennung: str) -> list[dict]:
        return [e for e in self._anfrage("/fehler-entfernen", {"kennung": kennung}, mit_schluessel=True).get("fehler", []) if isinstance(e, dict)]

    def einladung_erzeugen(self) -> dict:
        return self._anfrage("/einladung", {}, mit_schluessel=True)

    def geraet_mit_code(self, code: str, name: str) -> dict:
        a = self._anfrage("/geraet-mit-code", {"code": code, "name": name})
        d = {"kennung": str(a.get("kennung", "")), "schluessel": str(a.get("schluessel", "")), "name": str(a.get("name") or name)[:60], "seit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if not d["kennung"] or not d["schluessel"]:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keine Gerätekennung geschickt")
        self._geraet_speichern(d)
        return d


    def konto_beitritt_start(self, art: str, name: str = "") -> dict:
        ticket = secrets.token_urlsafe(32)
        basis = "https://kiplatz.at" if self.adresse.rstrip("/") == STANDARD_ADRESSE else self.adresse.rstrip("/")
        a = self._anfrage("/konto-start", {"ticket": ticket, "rueckkehr": f"{basis}/app/", "geraet": str(art), "name": str(name)[:60]})
        return {"ticket": ticket, "adresse": str(a.get("adresse", ""))}

    def konto_beitritt_abholen(self, ticket: str) -> dict | None:
        a = self._anfrage("/konto-ergebnis", {"ticket": str(ticket)})
        if a.get("status") != "fertig":
            return None
        d = {"kennung": str(a.get("kennung", "")), "schluessel": str(a.get("schluessel", "")), "name": str(a.get("name") or "")[:60],
             "seit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if not d["kennung"] or not d["schluessel"]:
            raise CommunityError("COMMUNITY_ANTWORT", "der Server hat keine Gerätekennung geschickt")
        self._geraet_speichern(d)
        return {**d, "konto": str(a.get("konto") or "")[:60]}

    def urteil_senden(self, auftrag: str, urteil: str, grund: str, titel: str = "", *, sicher: bool = False) -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "urteil": urteil, "grund": grund, "titel": titel, "sicher": bool(sicher)}, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def freigeben(self, kennung: str) -> None:
        self._anfrage("/freigeben", {"kennung": kennung}, mit_schluessel=True)

    def vertiefung_senden(self, auftrag: str, zusammenfassung: str, fragen: list[dict]) -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "vertiefung": {"zusammenfassung": zusammenfassung, "fragen": fragen}}, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def vertiefung_verzicht(self, auftrag: str, grund: str = "") -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "vertiefung_verzicht": True, "grund": grund}, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def vertiefung_urteil_senden(self, auftrag: str, urteil: str, grund: str = "", *, raus: list[int] | None = None, fassung: int = 1) -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "vertiefung_urteil": urteil, "grund": grund, "raus": list(raus or []), "fassung": int(fassung)},
                             als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def vorab_senden(self, auftrag: str, text: str = "", lieferschein: dict | None = None, *, verzicht: str = "") -> dict:
        inhalt = {"verzicht": str(verzicht)[:120]} if verzicht else {"text": str(text), "lieferschein": dict(lieferschein or {})}
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "vorab": inhalt}, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def vorab_urteil_senden(self, auftrag: str, urteil: str) -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "vorab_urteil": urteil}, als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)

    def ergebnis_senden(self, auftrag: str, modell: str, ergebnisse: list[dict], pruefsumme: str) -> dict:
        return self._anfrage("/ergebnis", {"auftrag": auftrag, "modell": modell, "ergebnisse": ergebnisse, "pruefsumme": pruefsumme},
                             als_geraet=True, timeout=ERGEBNIS_TIMEOUT_S)


__all__ = ["Community", "CommunityError", "Stand", "STANDARD_ADRESSE", "DIRNAME", "SCHLUESSEL_DATEI", "GERAET_DATEI"]
