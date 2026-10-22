# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sicher_schreiben
import wissen

DATEI = "pruefstand.json"
DECKUNG_AB = 0.5
MAX_FRAGEN = 200
MAX_BERICHTE = 30
MITGLIEDER_NAECHTE = 3
MITGLIEDER_MAX = 5000
SCHWACH_UNTER = 0.8
MAX_ANTWORT = 600
BERICHTIGUNG_MAX = 60
SIEBEN = 7

START_FRAGEN: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("Was ist KIplatz?", "KIplatz ist eine kostenlose KI aus Österreich, die eine Community gemeinsam baut; die Antworten kommen von den Computern der Mitglieder, nicht aus einem Rechenzentrum.", ("Österreich", "Community"), "selbstauskunft"),
    ("Wer bist du?", "Ich bin KIplatz, die KI der gleichnamigen Community aus Österreich; ich laufe auf deinem PC oder auf dem Gerät eines anderen Mitglieds.", ("KIplatz",), "selbstauskunft"),
    ("Was kannst du?", "Ich beantworte Fragen, schreibe und fasse Texte zusammen, rechne, schaue Wetter und Schlagzeilen nach und suche im Wissen der Community.", ("Fragen",), "selbstauskunft"),
    ("Wie funktioniert KIplatz?", "Deine Frage geht zuerst an die KI auf deinem eigenen PC; hat dein Gerät keine passende Grafikkarte, schickt das Programm die Frage an ein anderes Gerät der Community, der Server vermittelt nur.", ("PC",), "selbstauskunft"),
    ("Was kostet KIplatz?", "KIplatz ist kostenlos; es gibt keine Werbung, keinen Datenhandel und kein Abo.", ("kostenlos",), "kiplatz.at"),
    ("Was sind Credits bei KIplatz?", "Credits sind Anerkennung für Arbeit, die ein Gerät für die Community erledigt hat; sie sind kein Geld und keine Kryptowährung.", ("Geld",), "kiplatz.at"),
    ("Wofür gibt es bei KIplatz eine Platzordnung?", "Die Platzordnung sind die Regeln für Mitreden, Mitbauen und das Programm: respektvoll miteinander, keine Pornografie, keine Gewalt, keine Hetze; sie gilt überall gleich.", ("Regeln",), "kiplatz.at"),
    ("Wo werden meine Fragen an KIplatz gespeichert?", "Deine Gespräche bleiben auf deinem eigenen Gerät; der Server vermittelt und bewahrt nur allgemeine Wissensfragen und ihre Antworten verschlüsselt und ohne Absender auf.", ("Gerät",), "kiplatz.at"),
    ("Wie hoch ist das Allalinhorn?", "Das Allalinhorn ist ein 4027 Meter hoher Berg in den Walliser Alpen in der Schweiz.", ("4027",), "Wikipedia"),
    ("Was war Aquincum?", "Aquincum war eine römische Stadt und ein Legionslager an der Donau auf dem Gebiet des heutigen Budapest, Hauptstadt der Provinz Pannonia inferior.", ("Budapest",), "Wikipedia"),
    ("Wann fand die Armory Show statt?", "Die Armory Show war eine Kunstausstellung im Jahr 1913 in New York, die die europäische Moderne in den USA bekannt machte.", ("1913",), "Wikipedia"),
    ("Was ist die Asiatische Tigermücke?", "Die Asiatische Tigermücke ist eine ursprünglich aus Südostasien stammende Stechmücke, die Krankheiten wie Dengue-Fieber übertragen kann und sich auch in Europa ausbreitet.", ("Mücke",), "Wikipedia"),
    ("Was ist Alizarin?", "Alizarin ist ein roter Farbstoff, der ursprünglich aus der Wurzel des Färberkrapps gewonnen und ab 1868 synthetisch hergestellt wurde.", ("Farbstoff",), "Wikipedia"),
    ("Was ist die Alpha-Beta-Suche?", "Die Alpha-Beta-Suche ist ein Verfahren der Informatik, das den Minimax-Algorithmus bei Spielen wie Schach beschleunigt, indem es Zweige des Suchbaums abschneidet, die das Ergebnis nicht mehr ändern können.", ("Minimax",), "Wikipedia"),
    ("Was war die Argentinien-Krise?", "Die Argentinien-Krise war eine schwere Wirtschaftskrise Argentiniens um die Jahrtausendwende mit dem Staatsbankrott Ende 2001, dem Ende der Bindung des Peso an den Dollar und großen Protesten.", ("2001",), "Wikipedia"),
    ("Welche Schiffsklasse ist die Arleigh-Burke-Klasse?", "Die Arleigh-Burke-Klasse ist eine Klasse von Zerstörern der United States Navy mit dem Aegis-Kampfsystem; das Typschiff ist die USS Arleigh Burke.", ("Zerstörer",), "Wikipedia"),
    ("Was ist 3 mal 9,90 Euro?", "3 mal 9,90 Euro sind 29,70 Euro.", ("29,70",), "Rechnen"),
    ("Wie viele Tage hat ein Schaltjahr?", "Ein Schaltjahr hat 366 Tage.", ("366",), "Rechnen"),
    ("Wie heißt die Hauptstadt von Österreich?", "Die Hauptstadt von Österreich ist Wien.", ("Wien",), "Alltag"),
    ("Wie hoch ist der Normalsatz der Umsatzsteuer in Österreich?", "Der Normalsatz der Umsatzsteuer in Österreich beträgt 20 Prozent.", ("20",), "Alltag"),
)


class PruefstandError(wissen.WissenError):
    pass


def _jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tag(jetzt: datetime | None = None) -> str:
    return (jetzt or datetime.now(timezone.utc)).strftime("%Y-%m-%d")


def _norm(s: str) -> str:
    return " ".join(str(s or "").split())


def _ohne_tausender(s: str) -> str:
    return re.sub(r"(?<=\d)[.  '’ ](?=\d{3}(?!\d))", "", s or "")


def bewerten(antwort: str, erwartet: str, pflicht) -> tuple[bool, float, list[str]]:
    import zufallsfragen
    a = _norm(antwort)
    a_klein = _ohne_tausender(a).lower()
    pflicht = [str(w).strip() for w in (pflicht or []) if str(w).strip()]
    fehlt = [w for w in pflicht if _ohne_tausender(w).lower() not in a_klein]
    soll = set(wissen.woerter(_norm(erwartet)))
    if soll:
        ist = set(wissen.woerter(a))
        deckung = len(soll & ist) / len(soll)
    else:
        deckung = 1.0 if a else 0.0
    if pflicht:
        richtig = bool(a) and not fehlt and not zufallsfragen._WEISS_NICHT.search(a)
    else:
        richtig = bool(a) and deckung >= DECKUNG_AB
    return richtig, round(deckung, 2), fehlt


MESSREIHE_DATEI = "messreihe.json"
MESSREIHE_MAX = 1500
MESSREIHE_BERICHTE = 60
RUNDE_FRAGEN = 100
PROBELAUF_FRAGEN = 24
DURCHGANG_RUNDEN = 3
RUNDEN_DATEI = "pruefrunden.json"
SUCHE_AUS_MERKMAL = "Suche im Internet ist gerade nicht durchgekommen"
NOTIZ_MAX = 600
_NOTIZ = re.compile(r"[^.]*(?:neu geantwortet|gestrichen|nicht ausgegeben|ausgelassen|nachübersetzt|Zeit je Schritt)[^.]*\.(?:[^.]*\d s[^.]*\.)?")


def notiz_aus(quellen) -> str:
    t = " ".join(str(quellen or "").split())
    return " ".join(m.group(0).strip() for m in _NOTIZ.finditer(t))[:NOTIZ_MAX]


SUCHE_AUS_EN = re.compile(r"internet search (is ?n.t|is not|did ?n.t|did not|has ?n.t|has not|could ?n.t|could not) (working|work|get through|gotten through|come through|go through)", re.I)


def suche_aus(antwort) -> bool:
    t = str(antwort or "")
    return SUCHE_AUS_MERKMAL in t or bool(SUCHE_AUS_EN.search(t))


PROBE_UNSICHER_AB = 15
PROBE_UNSICHER_ANTEIL = 0.10
PROBE_UNSICHER_ART = 0.15


def ohne_suche_raus(probe: list, vorher: list) -> set:
    def aus(liste):
        return {str(x.get("kennung")): BEWERTET_WIE.get(str(x.get("art", "")), str(x.get("art", ""))) for x in liste
                if isinstance(x, dict) and suche_aus(x.get("antwort"))}
    pa, va = aus(probe), aus(vorher)
    return {k for k, art in pa.items() if art == "erfunden"} | {k for k, art in va.items() if art != "erfunden"}


def _median_s(fragen: list) -> float | None:
    werte = sorted(float(x.get("dauer_s", 0) or 0) for x in fragen if isinstance(x, dict))
    if not werte:
        return None
    m = len(werte) // 2
    return round(werte[m] if len(werte) % 2 else (werte[m - 1] + werte[m]) / 2, 1)


def unsicher(fragen: list, raus: set) -> bool:
    je_art: dict = {}
    for x in fragen:
        if isinstance(x, dict) and "art" in x:
            a = je_art.setdefault(str(x["art"]), [0, 0])
            a[0] += 1
            a[1] += 1 if x.get("kennung") in raus else 0
    gesamt = sum(a[0] for a in je_art.values())
    return bool(gesamt) and (sum(a[1] for a in je_art.values()) > PROBE_UNSICHER_ANTEIL * gesamt
                             or any(a[1] > PROBE_UNSICHER_ART * a[0] for a in je_art.values()))
_NICHT_WISSEN = re.compile(r"wei(?:ß|ss) ich (?:\w+ )*nicht|kenne ich (?:\w+ )*nicht|(?:nichts|keine \w+) (?:\w+ ){0,3}gefunden|finde (?:\w+ ){0,3}(?:nichts|keine)"
                           r"|keine (?:gesicherten |verlässlichen |genauen )?(?:informationen|angaben|treffer|quellen?|daten)|nicht bekannt|gibt es (?:\w+ )?nicht"
                           r"|existiert (?:\w+ )?nicht|nicht (?:sicher )?sagen|nichts (?:verlässliches|bekannt)", re.I)
_VERNEINT = re.compile(r"\b(?:hat|besitzt|gibt es)\s+(?:gar\s+)?(?:keinen?|keine)\b|\bist\s+kein(?:e|en)?\s+(?:Bundesland|Land|Staat|Hauptstadt)\b")
_NICHT_WISSEN_EN = re.compile(r"I (?:don't|do not|can't|cannot|couldn't|could not|am unable to|'m unable to) (?:know|say|tell|find|confirm|verify|answer)"
                              r"|not (?:entirely |completely |quite |really )?sure|no (?:reliable |verified |specific |further |such )?(?:information|data|details|answer|record)"
                              r"|(?:doesn't|does not|didn't|did not) (?:seem to )?exist|(?:nothing|no results?) (?:reliable )?(?:was |were )?found"
                              r"|unknown to me|I have no (?:information|idea|data|knowledge)|not (?:known|aware)", re.I)


def messreihe_laden(ordner: Path | None = None) -> list[dict]:
    import json
    ordner = ordner or (_HERE / "pruefsammlung")
    out: list[dict] = []
    if not ordner.is_dir():
        return out
    for p in sorted(ordner.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for f in d.get("fragen", []) if isinstance(d, dict) else []:
            if isinstance(f, dict) and str(f.get("kennung", "")).startswith("m-") and f.get("frage") and f.get("art"):
                out.append(f)
    return out[:MESSREIHE_MAX]


MESSREIHE_ANTWORT = 4000
_WEG_IM_NETZ = (True, False, "nicht_erreicht")
BEWERTET_WIE = {"klasse_a": "wissen", "klasse_b": "wissen", "klasse_c": "wissen", "klasse_d": "erfunden"}
BEKANNT = ("wissen", "alltag", "alltag_en", "klasse_a", "klasse_b", "klasse_c")
ARTEN_NAMEN = (("wissen", "Wissen"), ("alltag", "Alltag und Praxis"), ("alltag_en", "Alltag und Praxis auf Englisch"),
               ("erfunden", "Erfundenes erkennen"), ("rueckfrage", "Nachfragen"), ("grenze", "Formatvorgaben"))
KLASSEN_NAMEN = (("A", "Klasse A, echte Namen in den Formen der Weiß-nicht-Übungen"), ("B", "Klasse B, Grundwissen deutschsprachiger Raum"),
                 ("C", "Klasse C, Weltwissen in anderen Formen"), ("D", "Klasse D, Erfundenes in denselben Formen"))


def weiss_nicht(antwort) -> bool:
    a = _norm(antwort)
    return bool(_NICHT_WISSEN.search(a) or _NICHT_WISSEN_EN.search(a))


def _weg(w) -> dict:
    w = w if isinstance(w, dict) else {}

    def zahl(k):
        try:
            return max(0, min(int(w.get(k, 0) or 0), 99))
        except (TypeError, ValueError):
            return 0
    netz = w.get("im_netz")
    schritte = {}
    for s, n in list((w.get("schritte") if isinstance(w.get("schritte"), dict) else {}).items())[:8]:
        try:
            schritte[_norm(s)[:40]] = max(0, min(int(n or 0), 3600))
        except (TypeError, ValueError):
            continue
    return {"gemacht": _norm(w.get("gemacht"))[:60], "stellen": zahl("stellen"),
            "arten": [_norm(a)[:30] for a in (w.get("arten") if isinstance(w.get("arten"), list) else [])][:8],
            "suchanfragen": zahl("suchanfragen"), "suchrunden": zahl("suchrunden"), "im_netz": netz if netz in _WEG_IM_NETZ else False,
            **({"schritte": schritte} if schritte else {})}


def mess_frage(mf: dict, a: dict) -> dict:
    roh = a.get("antwort", "")
    text = _norm(roh)
    try:
        ms = round(max(0.0, min(float(a.get("dauer_s", 0) or 0), 3600.0)), 1)
    except (TypeError, ValueError):
        ms = 0.0
    e = {"kennung": mf["kennung"], "art": mf["art"], "frage": mf["frage"], "richtig": messreihe_bewerten(mf, roh),
         "antwort": text[:MESSREIHE_ANTWORT], "laenge": len(text), "weiss_nicht": weiss_nicht(text), "ohne_suche": suche_aus(text),
         "dauer_s": ms, "weg": _weg(a.get("weg"))}
    if mf.get("klasse"):
        e["klasse"] = str(mf["klasse"])[:2]
    if a.get("notiz"):
        e["notiz"] = str(a.get("notiz"))[:NOTIZ_MAX]
    return e


def _pflicht_ok(text: str, pflicht) -> bool:
    for gruppe in pflicht or []:
        teile = [w for w in str(gruppe).split("|") if w]
        if not any((w in text) if (w.isupper() and len(w) > 1) else (_ohne_tausender(w).lower() in _ohne_tausender(text).lower()) for w in teile):
            return False
    return True


OHNE_ANTWORT_ANTEIL = 0.02


def ohne_antwort(antwort) -> bool:
    t = str(antwort or "").strip()
    return not t or t.startswith("(keine Antwort")


def vollstaendig(bericht: dict) -> bool:
    try:
        return int(bericht.get("ohne_antwort", 0) or 0) <= max(5, OHNE_ANTWORT_ANTEIL * int(bericht.get("gesamt", 0) or 0))
    except (TypeError, ValueError):
        return True


def messreihe_bewerten(f: dict, antwort: str) -> bool:
    a = _norm(antwort)
    if not a or a.startswith("(keine Antwort"):
        return False
    art = BEWERTET_WIE.get(f.get("art"), f.get("art"))
    if art == "wissen":
        return _pflicht_ok(a, f.get("pflicht")) and not _NICHT_WISSEN.search(a) and not _VERNEINT.search(a)
    if art == "alltag":
        return _pflicht_ok(a, f.get("pflicht")) and not _NICHT_WISSEN.search(a)
    if art == "alltag_en":
        return _pflicht_ok(a, f.get("pflicht")) and not _NICHT_WISSEN.search(a) and not _NICHT_WISSEN_EN.search(a)
    if art == "erfunden":
        return bool(_NICHT_WISSEN.search(a))
    if art == "rueckfrage":
        return "?" in a and len(a) <= 400
    if art == "grenze":
        regel = f.get("regel") if isinstance(f.get("regel"), dict) else {}
        art_r, n = regel.get("regel"), int(regel.get("n", 0) or 0)
        roh = str(antwort or "").strip()
        if art_r == "nur_zahl":
            ok = bool(re.fullmatch(r"[\d.,\s]+\.?", a))
        elif art_r == "ja_nein":
            ok = a.lower().rstrip(".!") in ("ja", "nein")
        elif art_r == "zeilen":
            zeilen = [z.strip() for z in roh.splitlines() if z.strip()]
            ok = len(zeilen) == n and all(z[:1] in "-–•" for z in zeilen)
        elif art_r == "saetze":
            ok = len(re.findall(r"[.!?](?:\s|$)", a)) == n and not any(w in a.lower() for w in regel.get("ohne", []))
        elif art_r == "woerter_max":
            ok = len(re.findall(r"[\wäöüÄÖÜß-]+", a)) <= n
        else:
            ok = False
        return ok and _pflicht_ok(a, f.get("pflicht"))
    return False


def faellig(zuletzt: str, jetzt: datetime) -> bool:
    return zuletzt != jetzt.strftime("%Y-%m-%d")


def runden_reihe(mess: list[dict], rotation: int) -> list[str]:
    gruppen: dict[str, list[str]] = {}
    for f in mess:
        if isinstance(f, dict) and f.get("kennung"):
            gruppen.setdefault(str(f.get("klasse") or f.get("art") or ""), []).append(str(f["kennung"]))
    stellen = []
    for name, ks in gruppen.items():
        ks.sort(key=lambda k: hashlib.sha256(f"{rotation}:{k}".encode("utf-8")).hexdigest())
        stellen += [((i + 0.5) / len(ks), name, k) for i, k in enumerate(ks)]
    return [k for _p, _n, k in sorted(stellen)]


class Pruefstand:
    def __init__(self, ordner: Path, *, jetzt=None, zeit_lesen=None) -> None:
        self.datei = Path(ordner) / DATEI
        self._jetzt = jetzt or (lambda: datetime.now(timezone.utc))
        self._zeit_lesen = zeit_lesen


    def _laden(self) -> dict:
        d = sicher_schreiben.json_laden(self.datei, {})
        neu = False
        if not isinstance(d.get("fragen"), list):
            d["fragen"] = [self._frage(f, e, list(p), q) for f, e, p, q in START_FRAGEN]
            neu = True
        if not isinstance(d.get("berichte"), list):
            d["berichte"] = []
        if not isinstance(d.get("mitglieder"), dict):
            d["mitglieder"] = {}
        for f in d["fragen"]:
            if f.get("art") == "start" and "Hausordnung" in f.get("frage", "") + f.get("erwartet", ""):
                f["frage"] = f.get("frage", "").replace("Hausordnung", "Platzordnung")
                f["erwartet"] = f.get("erwartet", "").replace("Hausordnung", "Platzordnung")
                neu = True
        wahr = {f: e for f, e, _p, _q in START_FRAGEN}
        for f in d["fragen"]:
            if f.get("art") == "start" and "speichert keine Frage" in f.get("erwartet", "") and f.get("frage") in wahr:
                f["erwartet"] = wahr[f["frage"]]
                neu = True
        import zeitfragen
        da = {f.get("schluessel") for f in d["fragen"] if f.get("art") == "zeit"}
        for schluessel, frage in zeitfragen.FRAGEN:
            if schluessel not in da and not any(_norm(f.get("frage", "")).lower() == _norm(frage).lower() for f in d["fragen"]):
                f = self._frage(frage, "", [], "zuständige Stelle, jede Nacht neu gelesen", art="zeit")
                f["schluessel"] = schluessel
                d["fragen"].append(f)
                neu = True
        if neu:
            self._speichern(d)
        return d

    def _speichern(self, d: dict) -> None:
        d["berichte"] = d["berichte"][-MAX_BERICHTE:]
        sicher_schreiben.json_datei(self.datei, d, indent=None)

    @staticmethod
    def _frage(frage: str, erwartet: str, pflicht: list[str], quelle: str, *, art: str = "start") -> dict:
        return {"kennung": "f" + secrets.token_hex(4), "frage": _norm(frage)[:300], "erwartet": _norm(erwartet)[:1000],
                "pflicht": [_norm(w)[:60] for w in pflicht if _norm(w)][:8], "quelle": _norm(quelle)[:80], "art": art, "seit": _jetzt()}


    def fragen(self) -> list[dict]:
        return [dict(f) for f in self._laden()["fragen"]]

    def fragen_fuer_geraet(self) -> list[dict]:
        import zufallsfragen
        heute = self._jetzt().astimezone().date()
        return ([{"kennung": f["kennung"], "frage": f["frage"]} for f in self._laden()["fragen"]]
                + [{"kennung": f["kennung"], "frage": f["frage"]} for f in zufallsfragen.ziehen(heute)])

    def hinzufuegen(self, frage: str, erwartet: str, pflicht, quelle: str = "", *, art: str = "admin") -> dict:
        frage, erwartet = _norm(frage), _norm(erwartet)
        if len(frage) < 5:
            raise PruefstandError("PRUEFSTAND_FRAGE", "die Prüffrage ist zu kurz")
        if len(erwartet) < 2 and not [w for w in (pflicht or []) if _norm(w)]:
            raise PruefstandError("PRUEFSTAND_ERWARTET", "bitte die erwartete Antwort oder ein Pflichtwort angeben")
        d = self._laden()
        if any(_norm(f.get("frage", "")).lower() == frage.lower() for f in d["fragen"]):
            raise PruefstandError("PRUEFSTAND_DOPPELT", "diese Prüffrage gibt es schon")
        if len(d["fragen"]) >= MAX_FRAGEN:
            raise PruefstandError("PRUEFSTAND_VOLL", f"höchstens {MAX_FRAGEN} Prüffragen")
        f = self._frage(frage, erwartet, list(pflicht or []), quelle, art=art)
        d["fragen"].append(f)
        self._speichern(d)
        return f

    def entfernen(self, kennung: str) -> bool:
        d = self._laden()
        vorher = len(d["fragen"])
        d["fragen"] = [f for f in d["fragen"] if f.get("kennung") != kennung]
        if len(d["fragen"]) == vorher:
            return False
        self._speichern(d)
        return True

    def aus_berichtigung(self, frage: str, richtig: str, *, lernen: bool = True) -> dict | None:
        frage, richtig = _norm(frage), _norm(richtig)
        if len(frage) < 5 or len(richtig) < 5:
            return None
        d = self._laden()
        if any(_norm(f.get("frage", "")).lower() == frage.lower() for f in d["fragen"]):
            return None
        alte = [f for f in d["fragen"] if f.get("art") == "berichtigung"]
        if len(alte) >= BERICHTIGUNG_MAX:
            d["fragen"].remove(alte[0])
        f = self._frage(frage, richtig, [], "Berichtigung eines Mitglieds", art="berichtigung")
        if not lernen:
            f["lernen"] = False
        d["fragen"].append(f)
        self._speichern(d)
        return f


    def geraet_vergessen(self, geraet: str) -> None:
        d = self._laden()
        if d["mitglieder"].pop(str(geraet)[:40], None) is not None:
            self._speichern(d)
        if any(isinstance(b, dict) and b.get("geraet") == geraet for b in d["berichte"]):
            for b in d["berichte"]:
                if isinstance(b, dict) and b.get("geraet") == geraet:
                    b["geraet"], b["geraet_name"] = "ausgetreten", "ein ausgetretenes Mitglied"
            self._speichern(d)

    def bericht_annehmen(self, geraet: str, geraet_name: str, antworten, wege=None, *, admin: bool = True, runde: str = "") -> dict:
        if not isinstance(antworten, list) or not antworten:
            raise PruefstandError("PRUEFSTAND_LEER", "keine Antworten im Bericht")
        r = self.runde_annehmen(geraet, geraet_name, runde, antworten) if (runde and admin) else None
        if r is not None and r.get("wiederholt"):
            return {"tag": r["tag"], "richtig": r["richtig"], "gesamt": r["gesamt"], "wege_ok": 0, "wege_gesamt": 0, "dauer_s": r["dauer_s"], "runde": r}
        d = self._laden()
        nach_kennung = {f["kennung"]: f for f in d["fragen"]}
        ergebnisse = []
        nicht_bewertet = []
        dauer = 0.0
        heute = self._jetzt().astimezone().date()
        zufall: list[dict] = []
        import zufallsfragen
        for a in antworten[:MAX_FRAGEN + MESSREIHE_MAX]:
            if not isinstance(a, dict) or str(a.get("kennung", "")).startswith("m-"):
                continue
            f = nach_kennung.get(str(a.get("kennung", "")))
            zf = zufallsfragen.aus_kennung(str(a.get("kennung", ""))) if f is None else None
            if f is None and zf is None:
                continue
            text = _norm(a.get("antwort", ""))[:4000]
            try:
                s = float(a.get("dauer_s", 0) or 0)
            except (TypeError, ValueError):
                s = 0.0
            dauer += max(0.0, min(s, 3600.0))
            if zf is not None:
                pr = a.get("pruefung") if isinstance(a.get("pruefung"), dict) else {}
                pr = {k: int(pr.get(k, 0) or 0) for k in ("gruen", "gelb", "rot") if isinstance(pr.get(k, 0), (int, float))}
                notizen = [str(x)[:200] for x in a.get("belege", [])[:5]] if isinstance(a.get("belege"), list) else []
                u = zufallsfragen.bewerten(zf, text, heute=heute, pruefung=pr, belege_notizen=notizen, quellen=_norm(str(a.get("quellen", "")))[:600])
                zufall.append({"kennung": zf["kennung"], "frage": zf["frage"], **u, "antwort": text[:MAX_ANTWORT], "dauer_s": round(max(0.0, min(s, 3600.0)), 1)})
                continue
            if f.get("art") == "zeit":
                import zeitfragen
                try:
                    erw = zeitfragen.erwartung(str(f.get("schluessel", "")), heute, self._zeit_lesen)
                except Exception as exc:
                    nicht_bewertet.append({"frage": f["frage"], "grund": str(getattr(exc, "detail", type(exc).__name__))[:120]})
                    continue
                richtig, fehlt = zeitfragen.bewerten(text, erw)
                deckung = 1.0 if richtig else 0.0
                ergebnisse.append({"kennung": f["kennung"], "frage": f["frage"], "richtig": richtig, "deckung": deckung, "fehlt": fehlt,
                                   "antwort": text[:MAX_ANTWORT], "dauer_s": round(max(0.0, min(s, 3600.0)), 1), "quelle": f.get("quelle", ""),
                                   "erwartet_heute": erw["text"]})
                continue
            richtig, deckung, fehlt = bewerten(text, f["erwartet"], f["pflicht"])
            ergebnisse.append({"kennung": f["kennung"], "frage": f["frage"], "richtig": richtig, "deckung": deckung, "fehlt": fehlt,
                               "antwort": text[:MAX_ANTWORT], "dauer_s": round(max(0.0, min(s, 3600.0)), 1), "quelle": f.get("quelle", "")})
        if not ergebnisse:
            if r is not None:
                return {"tag": r["tag"], "richtig": r["richtig"], "gesamt": r["gesamt"], "wege_ok": 0, "wege_gesamt": 0, "dauer_s": r["dauer_s"], "runde": r}
            raise PruefstandError("PRUEFSTAND_UNBEKANNT", "keine der Antworten gehört zu einer bekannten Prüffrage")
        w = {}
        if isinstance(wege, dict):
            for k, v in list(wege.items())[:20]:
                w[_norm(str(k))[:40]] = bool(v)
        b = {"zeit": _jetzt(), "tag": _tag(self._jetzt()), "geraet": str(geraet)[:40], "geraet_name": _norm(geraet_name)[:60],
             "richtig": sum(1 for e in ergebnisse if e["richtig"]), "gesamt": len(ergebnisse), "dauer_s": round(dauer, 1),
             "wege_ok": sum(1 for v in w.values() if v), "wege_gesamt": len(w), "wege": w, "fragen": ergebnisse, "nicht_bewertet": nicht_bewertet,
             "zufall": {"fragen": zufall, **{k: sum(1 for x in zufall if x["urteil"] == k) for k in ("richtig", "falsch", "belegt", "offen", "fraglich")}}}
        if not admin:
            n = {"tag": b["tag"], "richtig": b["richtig"], "gesamt": b["gesamt"], "zufall_richtig": b["zufall"]["richtig"],
                 "zufall_falsch": b["zufall"]["falsch"], "dauer_s": b["dauer_s"]}
            alt = [x for x in d["mitglieder"].get(str(geraet)[:40], []) if isinstance(x, dict) and x.get("tag") != n["tag"]]
            d["mitglieder"][str(geraet)[:40]] = (alt + [n])[-MITGLIEDER_NAECHTE:]
            if len(d["mitglieder"]) > MITGLIEDER_MAX:
                for k in sorted(d["mitglieder"], key=lambda k: d["mitglieder"][k][-1].get("tag", ""))[:len(d["mitglieder"]) - MITGLIEDER_MAX]:
                    d["mitglieder"].pop(k, None)
            self._speichern(d)
            return {**n, "wege_ok": b["wege_ok"], "wege_gesamt": b["wege_gesamt"], "schwach": self._schwach(d["mitglieder"][str(geraet)[:40]])}
        d["berichte"].append(b)
        self._speichern(d)
        if r is not None:
            b["runde"] = r
        return b

    def _messreihe_ablegen(self, b: dict, gemessen: list[dict], *, modell: str = "", runde: dict | None = None) -> dict:
        datei = self.datei.parent / MESSREIHE_DATEI
        alt = sicher_schreiben.json_laden(datei, {"berichte": []}, art=dict)
        berichte = alt.get("berichte") if isinstance(alt.get("berichte"), list) else []
        je_art = self._je_art(gemessen, set())
        je_klasse = self._je_art(gemessen, set(), feld="klasse")
        neu = {"zeit": b["zeit"], "tag": b["tag"], "geraet": b["geraet"], "geraet_name": b["geraet_name"], "je_art": je_art,
               **({"je_klasse": je_klasse} if je_klasse else {}),
               "richtig": sum(1 for x in gemessen if x["richtig"]), "gesamt": len(gemessen),
               "dauer_s": round(sum(x["dauer_s"] for x in gemessen), 1), "fragen": gemessen, **({"modell": modell} if modell else {}),
               "ohne_antwort": sum(1 for x in gemessen if ohne_antwort(x.get("antwort"))), **(runde or {})}
        if modell:
            berichte = [x for x in berichte if not (isinstance(x, dict) and x.get("modell") == modell and x.get("geraet") == neu["geraet"]
                                                    and x.get("tag") == neu["tag"])]
        berichte.append(neu)
        sicher_schreiben.json_datei(datei, {"berichte": berichte[-MESSREIHE_BERICHTE:]}, indent=None)
        return neu


    def _runden_laden(self) -> dict:
        d = sicher_schreiben.json_laden(self.datei.parent / RUNDEN_DATEI, {"geraete": {}}, art=dict)
        if not isinstance(d.get("geraete"), dict):
            d["geraete"] = {}
        return d

    def _runden_speichern(self, d: dict) -> None:
        sicher_schreiben.json_datei(self.datei.parent / RUNDEN_DATEI, d, indent=None)

    @staticmethod
    def _neue_rotation(g: dict, mess: list[dict], sammlung: str) -> None:
        g["rotation"] = int(g.get("rotation", 0) or 0) + 1
        g["reihe"], g["pos"], g["sammlung"] = runden_reihe(mess, g["rotation"]), 0, sammlung

    def runde_holen(self, geraet: str, bau: str, fassung: str = "", *, probelauf: bool = False) -> dict:
        geraet, bau, fassung = str(geraet)[:40], _norm(bau)[:40], _norm(fassung)[:120]
        mess = messreihe_laden()
        nach = {f["kennung"]: f for f in mess}
        sammlung = hashlib.sha256("\n".join(sorted(nach)).encode("utf-8")).hexdigest()[:16]
        d = self._runden_laden()
        g = d["geraete"].get(geraet) if isinstance(d["geraete"].get(geraet), dict) else {}
        if g.get("sammlung") != sammlung or not isinstance(g.get("reihe"), list):
            self._neue_rotation(g, mess, sammlung)
            alt = g.get("offen") if isinstance(g.get("offen"), dict) else None
            if alt is not None and set(alt.get("kennungen") or []) <= set(nach):
                alt["pos_vorher"] = 0
            else:
                g["durchgang"], g["offen"] = None, None
        offen = g.get("offen") if isinstance(g.get("offen"), dict) else None
        if offen is not None and offen.get("bau") == bau and offen.get("fassung") == fassung:
            return self._runde_fragen(offen, nach)
        if offen is not None:
            g["pos"], g["offen"] = int(offen.get("pos_vorher", g.get("pos", 0)) or 0), None
            if offen.get("tagesfragen"):
                g["tagesfragen_tag"] = ""
        dg = g.get("durchgang") if isinstance(g.get("durchgang"), dict) else None
        if dg is None or dg.get("bau") != bau or dg.get("fassung") != fassung or len(dg.get("runden") or []) >= DURCHGANG_RUNDEN:
            dg = {"id": "d" + secrets.token_hex(4), "bau": bau, "fassung": fassung, "runden": [], "seit": _jetzt()}
            g["durchgang"] = dg
        if int(g.get("pos", 0) or 0) >= len(g["reihe"]):
            self._neue_rotation(g, mess, sammlung)
        pos = int(g.get("pos", 0) or 0)
        n = PROBELAUF_FRAGEN if probelauf else RUNDE_FRAGEN
        teil = [k for k in g["reihe"][pos:pos + n] if k in nach]
        heute = _tag(self._jetzt())
        tagesfragen = not probelauf and g.get("tagesfragen_tag") != heute
        if tagesfragen:
            g["tagesfragen_tag"] = heute
        offen = {"id": "r" + secrets.token_hex(4), "kennungen": teil, "bau": bau, "fassung": fassung, "durchgang": dg["id"],
                 "nummer": len(dg["runden"]) + 1, "rotation": g["rotation"], "pos_vorher": pos,
                 "pos_bis": min(len(g["reihe"]), pos + n), "von_gesamt": len(g["reihe"]),
                 "letzte": pos + n >= len(g["reihe"]), "tagesfragen": tagesfragen, "probelauf": probelauf, "seit": _jetzt()}
        g["pos"], g["offen"] = pos + n, offen
        d["geraete"][geraet] = g
        self._runden_speichern(d)
        return self._runde_fragen(offen, nach)

    def _runde_fragen(self, offen: dict, nach: dict) -> dict:
        fragen = [{"kennung": k, "frage": nach[k]["frage"]} for k in offen.get("kennungen") or [] if k in nach]
        if offen.get("tagesfragen"):
            fragen = self.fragen_fuer_geraet() + fragen
        info = {k: offen.get(k) for k in ("id", "durchgang", "nummer", "rotation", "pos_bis", "von_gesamt", "letzte", "probelauf")}
        return {"runde": {**info, "von": DURCHGANG_RUNDEN, "messfragen": len(offen.get("kennungen") or [])}, "fragen": fragen}

    def runde_annehmen(self, geraet: str, geraet_name: str, runde_id: str, antworten: list) -> dict:
        geraet = str(geraet)[:40]
        d = self._runden_laden()
        g = d["geraete"].get(geraet) if isinstance(d["geraete"].get(geraet), dict) else {}
        offen = g.get("offen") if isinstance(g.get("offen"), dict) else None
        zuletzt = g.get("zuletzt") if isinstance(g.get("zuletzt"), dict) else {}
        if zuletzt.get("runde") == str(runde_id)[:20]:
            return {**zuletzt, "mails": [], "wiederholt": True}
        if offen is None or offen.get("id") != str(runde_id)[:20]:
            raise PruefstandError("RUNDE_UNBEKANNT", "diese Prüfrunde ist am Server nicht offen (schon gemeldet oder durch einen neuen Bau ersetzt)")
        mess = {f["kennung"]: f for f in messreihe_laden()}
        dabei = set(offen.get("kennungen") or [])
        gemessen, gesehen = [], set()
        for a in antworten[:MAX_FRAGEN + MESSREIHE_MAX]:
            k = str(a.get("kennung", "")) if isinstance(a, dict) else ""
            if k in dabei and k in mess and k not in gesehen:
                gesehen.add(k)
                gemessen.append(mess_frage(mess[k], a))
        if not gemessen:
            raise PruefstandError("RUNDE_LEER", "keine der Antworten gehört zu dieser Prüfrunde")
        meta = {"runde": offen["id"], "durchgang": offen.get("durchgang"), "nummer": offen.get("nummer"), "rotation": offen.get("rotation"),
                "bau": offen.get("bau", ""), "fassung": offen.get("fassung", ""), "fehlen": len(dabei - gesehen)}
        b = {"zeit": _jetzt(), "tag": _tag(self._jetzt()), "geraet": geraet, "geraet_name": _norm(geraet_name)[:60]}
        neu = self._messreihe_ablegen(b, gemessen, runde=meta)
        dg = g.get("durchgang") if isinstance(g.get("durchgang"), dict) else {}
        voll = False
        if dg.get("id") == offen.get("durchgang"):
            dg["runden"] = list(dg.get("runden") or []) + [offen["id"]]
            voll = len(dg["runden"]) >= DURCHGANG_RUNDEN
        g["offen"] = None
        g["zuletzt"] = {k: v for k, v in neu.items() if k != "fragen"}
        if offen.get("letzte"):
            g["durchgang"] = None
        d["geraete"][geraet] = g
        self._runden_speichern(d)
        mails = []
        if offen.get("letzte"):
            mails.append(self.runden_mail(self.runden_stand(geraet, rotation=offen.get("rotation")), "rotation"))
        elif voll:
            mails.append(self.runden_mail(self.runden_stand(geraet, durchgang=dg["id"]), "durchgang"))
        return {**{k: v for k, v in neu.items() if k != "fragen"}, "mails": mails}

    def runden_stand(self, geraet: str, *, durchgang: str | None = None, rotation: int | None = None) -> dict:
        je: dict[str, dict] = {}
        runden, bauten, name, zeit = 0, [], "", ""
        for x in self._messreihe_berichte():
            if x.get("geraet") != geraet or not x.get("runde") or x.get("modell"):
                continue
            if (durchgang is not None and x.get("durchgang") != durchgang) or (rotation is not None and x.get("rotation") != rotation):
                continue
            runden += 1
            name, zeit = x.get("geraet_name") or name, x.get("zeit") or zeit
            if x.get("bau") and x["bau"] not in bauten:
                bauten.append(x["bau"])
            for f in x.get("fragen") or []:
                if isinstance(f, dict) and f.get("kennung"):
                    je[str(f["kennung"])] = f
        fragen = list(je.values())
        return {"geraet": geraet, "geraet_name": name, "zeit": zeit, "tag": str(zeit)[:10], "runden": runden, "bauten": bauten,
                "rotation": rotation, "durchgang": durchgang, "fragen": fragen, "je_art": self._je_art(fragen, set()),
                "je_klasse": self._je_art(fragen, set(), feld="klasse"), "richtig": sum(1 for f in fragen if f.get("richtig")),
                "gesamt": len(fragen), "ohne_antwort": sum(1 for f in fragen if ohne_antwort(f.get("antwort")))}


    def messreihe_probe_annehmen(self, geraet: str, geraet_name: str, antworten, modell: str) -> dict:
        if not isinstance(antworten, list) or not antworten:
            raise PruefstandError("MESSREIHE_LEER", "keine Antworten")
        modell = re.sub(r"[^A-Za-z0-9._-]", "", str(modell or ""))[:120]
        if not modell:
            raise PruefstandError("MESSREIHE_MODELL", "der Name der Fassung fehlt")
        mess = {f["kennung"]: f for f in messreihe_laden()}
        gemessen = []
        for a in antworten[:MESSREIHE_MAX]:
            mf = mess.get(str(a.get("kennung", ""))) if isinstance(a, dict) else None
            if mf is None:
                continue
            gemessen.append(mess_frage(mf, a))
        if not gemessen:
            raise PruefstandError("PRUEFSTAND_UNBEKANNT", "keine der Antworten gehört zur Messreihe")
        b = {"zeit": _jetzt(), "tag": _tag(self._jetzt()), "geraet": str(geraet)[:40], "geraet_name": _norm(geraet_name)[:60]}
        neu = self._messreihe_ablegen(b, gemessen, modell=modell)
        berichte = self._messreihe_berichte()
        vorher = next((x for x in reversed(berichte[:-1]) if x.get("geraet") == neu["geraet"] and not x.get("modell") and x.get("tag") == neu["tag"]
                       and vollstaendig(x)), None)
        e = {"probe": {k: v for k, v in neu.items() if k != "fragen"}, "vorher": {k: v for k, v in vorher.items() if k != "fragen"} if vorher else None}
        if vorher:
            raus = ohne_suche_raus(neu["fragen"], list(vorher.get("fragen") or []))
            e["median"] = {"probe": _median_s(neu["fragen"]), "vorher": _median_s(vorher.get("fragen") or [])}
            e["ohne_suche"] = {"raus": len(raus), "probe": self._je_art(neu["fragen"], raus), "vorher": self._je_art(vorher.get("fragen") or [], raus),
                               "probe_klasse": self._je_art(neu["fragen"], raus, feld="klasse"),
                               "vorher_klasse": self._je_art(vorher.get("fragen") or [], raus, feld="klasse")}
            e["ohne_suche"]["unsicher"] = unsicher(neu["fragen"], raus)
        return e

    @staticmethod
    def _je_art(fragen: list, raus: set, *, feld: str = "art") -> dict:
        je_art: dict = {}
        for x in fragen:
            if not isinstance(x, dict) or x.get("kennung") in raus or not x.get(feld):
                continue
            a = je_art.setdefault(str(x[feld]), {"richtig": 0, "gesamt": 0})
            a["gesamt"] += 1
            a["richtig"] += 1 if x.get("richtig") else 0
        return je_art

    @staticmethod
    def runden_mail(neu: dict, art: str) -> tuple[str, str]:
        import statistics
        fr = neu.get("fragen") or []
        rotation = art == "rotation"
        wer = neu.get("geraet_name") or "dem Admin-PC"
        bauten = ", ".join(neu.get("bauten") or []) or "unbekannt"
        if rotation:
            betreff = f"KIplatz Prüfung: alle {neu.get('gesamt')} Fragen durch, {neu.get('richtig')} richtig"
            zeilen = [f"Alle Fragen der Prüfsammlung sind einmal beantwortet ({neu.get('runden')} Runden auf {wer}, Bau {bauten}): "
                      f"{neu.get('richtig')} von {neu.get('gesamt')} richtig.", ""]
            if len(neu.get("bauten") or []) > 1:
                zeilen += ["Achtung: die Runden liefen mit verschiedenen Bauten, die Zahlen mischen sie.", ""]
        else:
            betreff = f"KIplatz Prüfung: Zwischenstand nach {neu.get('runden')} Runden, {neu.get('richtig')} von {neu.get('gesamt')} richtig"
            zeilen = [f"Zwischenstand von {wer} (Bau {bauten}) nach {neu.get('runden')} Runden: {neu.get('richtig')} von {neu.get('gesamt')} Fragen richtig. "
                      "Die Grenzen „gut genug“ gelten erst, wenn alle Fragen einmal dran waren.", ""]
        aussage = ("wissen", "alltag", "alltag_en", "erfunden")
        for a, name, feld in [(a, n, "je_art") for a, n in ARTEN_NAMEN] + [(k, n, "je_klasse") for k, n in KLASSEN_NAMEN]:
            x = (neu.get(feld) or {}).get(a)
            if not x:
                continue
            klein = not rotation and (feld == "je_klasse" or a not in aussage)
            zeilen.append(f"{name}: {x.get('richtig')} von {x.get('gesamt')}" + (" (zu wenige Fragen für ein Urteil)" if klein else ""))
        ohne = sum(1 for f in fr if suche_aus(f.get("antwort")))
        neu_geschrieben = sum(1 for f in fr if "neu geantwortet" in str(f.get("notiz") or ""))
        mit_notiz = sum(1 for f in fr if f.get("notiz"))
        d = sorted(float(f.get("dauer_s") or 0) for f in fr)
        leer = sum(1 for f in fr if ohne_antwort(f.get("antwort")))
        if leer > max(5, OHNE_ANTWORT_ANTEIL * len(fr)):
            betreff = betreff.replace("Prüfung", "Prüfung UNVOLLSTÄNDIG", 1)
            zeilen.insert(0, f"Achtung: {leer} von {len(fr)} Fragen blieben ohne Antwort (die KI war aus oder der Lauf brach ab). "
                             "Diese Zahlen messen nicht die KI und zählen nie als Vergleich.")
            zeilen.insert(1, "")
        zeilen += ["", f"Ohne Suche beantwortet: {ohne}"]
        if any("laenge" in f for f in fr):
            bekannt = [f for f in fr if f.get("art") in BEKANNT]
            zeilen.append(f"„Weiß nicht“ bei Bekanntem: {sum(1 for f in bekannt if f.get('weiss_nicht'))} von {len(bekannt)}")
            laengen = sorted(int(f.get("laenge") or 0) for f in fr if f.get("art") in ("alltag", "alltag_en"))
            if laengen:
                zeilen.append(f"Länge der Alltagsantworten: Mitte {laengen[len(laengen) // 2]} Zeichen")
        if mit_notiz:
            zeilen.append(f"Neu geschrieben: {neu_geschrieben} von {mit_notiz} Antworten mit Notiz")
        if d:
            zeilen.append(f"Antwortzeit: die Hälfte unter {statistics.median(d):.1f} s, 9 von 10 unter {d[int(len(d) * 0.9)]:.1f} s".replace(".", ","))
        schritte: dict[str, int] = {}
        for f in fr:
            for s, n in ((f.get("weg") or {}).get("schritte") or {}).items():
                schritte[s] = schritte.get(s, 0) + int(n or 0)
        if schritte:
            zeilen.append("Zeit je Schritt, zusammen: " + ", ".join(f"{s} {n // 60} min" for s, n in sorted(schritte.items(), key=lambda x: -x[1])[:6]))
        zeilen += ["", "Ausgerollt wird damit nichts." + (" Die genaue Auswertung: werkzeuge/messnacht_vergleich.py." if rotation else "")]
        return betreff, "\n".join(zeilen)

    @staticmethod
    def probe_mail(e: dict) -> tuple[str, str]:
        p, v = e["probe"], e.get("vorher")
        namen = ARTEN_NAMEN
        os_ = e.get("ohne_suche") or {}
        raus = int(os_.get("raus", 0) or 0)

        def zahl(b, art, feld="je_art"):
            x = (b or {}).get(feld, {}).get(art, {})
            return int(x.get("richtig", 0)), int(x.get("gesamt", 0))

        if v and raus:
            gesamt_p, gesamt_v = dict(p), dict(v)
            p = {**p, "je_art": os_["probe"], "je_klasse": os_.get("probe_klasse") or {}, "richtig": sum(x["richtig"] for x in os_["probe"].values()),
                 "gesamt": sum(x["gesamt"] for x in os_["probe"].values())}
            v = {**v, "je_art": os_["vorher"], "je_klasse": os_.get("vorher_klasse") or {}, "richtig": sum(x["richtig"] for x in os_["vorher"].values()),
                 "gesamt": sum(x["gesamt"] for x in os_["vorher"].values())}
            p["_alle"], v["_alle"] = gesamt_p, gesamt_v

        def mittel(b):
            m = (e.get("median") or {}).get("probe" if b is p else "vorher")
            if m is not None:
                return float(m)
            b = (b or {}).get("_alle", b)
            return round(float(b.get("dauer_s", 0)) / max(1, int(b.get("gesamt", 0))), 1) if b else 0.0

        zeilen = [f"heute Nacht hat {p.get('geraet_name') or 'der Admin-PC'} die Messreihe mit der nachtrainierten Fassung {p['modell']} beantwortet, "
                  "im echten Programm mit Gemeinschaftswissen und Suche. Ausgerollt ist nichts.", ""]
        schlechter = []
        reihen = [(art, name, "je_art") for art, name in namen]
        reihen += [(k, name, "je_klasse") for k, name in KLASSEN_NAMEN if k in (p.get("je_klasse") or {}) or k in ((v or {}).get("je_klasse") or {})]
        for art, name, feld in reihen:
            r, g = zahl(p, art, feld)
            if v:
                rv, gv = zahl(v, art, feld)
                zeilen.append(f"{name}: vorher {rv} von {gv}, mit der Fassung {r} von {g}")
                if gv and g and r / g < rv / gv:
                    schlechter.append(name)
            else:
                zeilen.append(f"{name}: {r} von {g}")
        if v:
            zeilen.append(f"Gesamt: vorher {v.get('richtig')} von {v.get('gesamt')}, mit der Fassung {p.get('richtig')} von {p.get('gesamt')}")
            zeilen.append(f"Zeit je Antwort (Median): vorher {mittel(v)} s, mit der Fassung {mittel(p)} s")
            besser = not schlechter and p.get("richtig", 0) / max(1, p.get("gesamt", 1)) > v.get("richtig", 0) / max(1, v.get("gesamt", 1))
            langsamer = mittel(p) > mittel(v) * 1.15 + 0.5
            zeilen += ["", ("Die Fassung ist besser und nirgends schlechter." if besser else
                            "Schlechter bei: " + ", ".join(schlechter) + "." if schlechter else "Die Fassung ist nicht besser.")
                       + (" Sie antwortet aber spürbar langsamer." if langsamer else "")]
            if raus:
                a, b_ = p["_alle"], v["_alle"]
                zeilen.append(f"Bei {raus} Frage{'n' if raus != 1 else ''} hätte ein Ausfall der Internetsuche die Fassung besser aussehen lassen. Sie sind oben nicht "
                              f"mitgezählt; Ausfälle, die nur gegen die Fassung sprechen, bleiben drin. Mit allen: vorher {b_.get('richtig')} von {b_.get('gesamt')}, "
                              f"mit der Fassung {a.get('richtig')} von {a.get('gesamt')}.")
            if os_.get("unsicher", raus > PROBE_UNSICHER_AB):
                zeilen.append("Das sind zu viele für ein sicheres Urteil. Von selbst misst der PC die Fassung nicht noch einmal; bitte im Chat sagen, "
                              "wie es weitergeht.")
                betreff = f"KIplatz-Training: Messung unsicher, die Suche fiel {raus}-mal aus"
            else:
                betreff = ("KIplatz-Training: Fassung " + ("besser" if besser and not langsamer else "nicht freigabereif")
                           + f" ({p.get('richtig')} statt {v.get('richtig')}" + (f", ohne {raus} Frage{'n' if raus != 1 else ''} ohne Suche" if raus else "") + ")")
        else:
            zeilen.append(f"Gesamt: {p.get('richtig')} von {p.get('gesamt')}. Einen Lauf mit dem Modell aus dem Katalog in derselben Nacht "
                          "gab es nicht; mit einer anderen Nacht wird nicht verglichen, weil die Suche dort anders lief.")
            betreff = "KIplatz-Training: Fassung gemessen, ohne Vergleich derselben Nacht"
        zeilen += ["", "Soll die Fassung zu allen PCs, sag es im Chat. Von selbst geht sie nirgends hin.", "", "KIplatz"]
        return betreff, "Hallo,\n\n" + "\n".join(zeilen) + "\n"

    @staticmethod
    def probe_fehler_mail(modell, fehler) -> tuple[str, str]:
        m = re.sub(r"[^A-Za-z0-9._-]", "", str(modell or ""))[:120] or "(ohne Namen)"
        f = re.sub(r"[\r\n]+", " ", str(fehler or ""))[:200]
        return ("KIplatz-Training: Probe-Nacht nicht gelaufen",
                f"Hallo,\n\nheute Nacht sollte der Admin-PC die nachtrainierte Fassung {m} messen. Das ging nicht: {f}\n\n"
                "Das Programm läuft normal mit dem Modell von heute weiter. Ausgerollt ist nichts.\n\nKIplatz\n")

    def _messreihe_berichte(self) -> list[dict]:
        d = sicher_schreiben.json_laden(self.datei.parent / MESSREIHE_DATEI, {"berichte": []}, art=dict)
        return [x for x in d.get("berichte", []) if isinstance(x, dict)]

    def messreihe_stand(self) -> list[dict]:
        d = sicher_schreiben.json_laden(self.datei.parent / MESSREIHE_DATEI, {"berichte": []}, art=dict)
        return [{**{k: v for k, v in x.items() if k != "fragen"},
                 "ohne_antwort": x.get("ohne_antwort", sum(1 for f in x.get("fragen") or [] if ohne_antwort(f.get("antwort"))))}
                for x in d.get("berichte", []) if isinstance(x, dict)]

    @staticmethod
    def _schwach(naechte: list) -> bool:
        letzte = [x for x in naechte if int(x.get("gesamt", 0) or 0) > 0][-2:]
        return len(letzte) == 2 and all(x["richtig"] / x["gesamt"] < SCHWACH_UNTER for x in letzte)

    def schwache(self) -> list[str]:
        return [g for g, n in self._laden()["mitglieder"].items() if self._schwach(n)]

    def mitglieder_stand(self) -> list[dict]:
        out = []
        for g, n in self._laden()["mitglieder"].items():
            if n:
                out.append({"geraet": g, **n[-1], "naechte": len(n), "hinten": self._schwach(n)})
        return sorted(out, key=lambda x: x.get("tag", ""), reverse=True)[:200]

    def letzter(self) -> dict | None:
        b = self._laden()["berichte"]
        return dict(b[-1]) if b else None

    def _je_tag(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for b in self._laden()["berichte"]:
            out[b.get("tag", "")] = b
        return out

    def oeffentlich(self) -> dict:
        tage = self._je_tag()
        gestern = _tag(self._jetzt() - timedelta(days=1))
        heute = _tag(self._jetzt())
        letzte = tage.get(heute) or tage.get(gestern)
        grenze = _tag(self._jetzt() - timedelta(days=SIEBEN))
        sieben = [b for t, b in tage.items() if t >= grenze]
        return {"letzte": {"tag": letzte["tag"], "richtig": letzte["richtig"], "gesamt": letzte["gesamt"]} if letzte else None,
                "naechte": len(sieben), "richtig": sum(b["richtig"] for b in sieben), "gesamt": sum(b["gesamt"] for b in sieben),
                "fragen": len(self._laden()["fragen"]), "zeigen": len(sieben) >= SIEBEN}

    def stand(self) -> dict:
        return {**self.oeffentlich(), "fragen": self.fragen(), "letzter": self.letzter(), "mitglieder": self.mitglieder_stand()}


__all__ = ["Pruefstand", "PruefstandError", "bewerten", "faellig", "runden_reihe", "START_FRAGEN", "DECKUNG_AB", "SIEBEN", "DATEI"]
