# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from pathlib import Path

QUELLEN = ("wikipedia", "orte", "woerterbuch", "kalender", "modell", "bedeutung", "suche")
NAMEN_DE = {"wikipedia": "Wikipedia-Kopie", "orte": "Orte (OpenStreetMap)", "woerterbuch": "Österreichisches Wörterbuch", "kalender": "Kalender",
            "modell": "Chat-Modell", "bedeutung": "Bedeutungs-Modell", "suche": "Suchmaschinen"}
MELDEN_ABSTAND_S = 300
STILL_AB_S = 3600
FRISCH_S = 20 * 60
GERAETE_MAX = 5000
TEXT_MAX = 160
STAND_MAX = 40
FEHLT_MAX = 10
WOERTERBUCH_MINDESTENS = 100
FEIERTAGE_MINDESTENS = 10


def _jetzt_iso(t: float | None = None) -> str:
    return datetime.fromtimestamp(t if t is not None else time.time(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_zu_s(iso: str) -> float:
    try:
        return datetime.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0


def _eintrag(ok: bool, text: str, *, gilt: bool = True, stand: str = "", zahl: int = 0, fehlt: list[str] | None = None) -> dict:
    e = {"ok": bool(ok), "gilt": bool(gilt), "stand": str(stand or "")[:STAND_MAX], "zahl": int(zahl or 0), "text": " ".join(str(text or "").split())[:TEXT_MAX]}
    if fehlt:
        e["fehlt"] = [str(x)[:STAND_MAX] for x in fehlt][:FEHLT_MAX]
    return e


def _datum(ausgabe: str) -> str:
    return f"{ausgabe[6:8]}.{ausgabe[4:6]}.{ausgabe[:4]}" if len(ausgabe or "") == 8 else ""


def _wikipedia(wiki) -> dict:
    if wiki is None:
        return _eintrag(False, "Wikipedia: nicht eingerichtet.", gilt=False)
    try:
        if not wiki.darf_halten():
            return _eintrag(False, "Wikipedia: dieses Gerät hält keine Kopie (unter 100 GB Freigabe).", gilt=False)
        z = wiki.zustand()
        ausgabe, artikel, phase = str(z.get("ausgabe") or ""), int(z.get("artikel") or 0), str(z.get("phase") or "")
        if not wiki.bereit():
            return _eintrag(False, f"Wikipedia: noch keine fertige Kopie ({phase or 'aus'}).", stand=ausgabe, zahl=artikel)
        if wiki.belegt():
            return _eintrag(False, f"Wikipedia: die Kopie ist gerade belegt ({phase}); Einleitungen und Namensprüfung fallen aus, bis sie frei ist.", stand=ausgabe, zahl=artikel)
        if phase == "fehler":
            return _eintrag(False, f"Wikipedia: gerade geht es nicht ({z.get('meldung') or ''}).", stand=ausgabe, zahl=artikel)
        zahl = f"{artikel:,}".replace(",", ".")
        return _eintrag(True, f"Wikipedia: {zahl} Artikel, Stand {_datum(ausgabe)}.", stand=ausgabe, zahl=artikel)
    except Exception as exc:
        return _eintrag(False, f"Wikipedia: Zustand nicht lesbar ({type(exc).__name__}).")


def _orte(osm) -> dict:
    if osm is None:
        return _eintrag(False, "Orte: nicht eingerichtet.", gilt=False)
    try:
        if not osm.darf_halten():
            return _eintrag(False, "Orte: dieses Gerät bereitet die Orte nicht auf.", gilt=False)
        st = osm._stand()
        offen = [k for k, _, _ in osm._laender]
        da = {kurz: bool(st.get(f"fertig_{kurz}") and kurz in osm._dateien) for kurz, _, _ in osm._laender}
        fertig = [kurz.upper() for kurz, _, _ in osm._laender if da[kurz]]
        fehlt = [deutsch for kurz, _, deutsch in osm._laender if not da[kurz]]
        fehlt_kurz = [kurz.upper() for kurz, _, _ in osm._laender if not da[kurz]]
        tage = sorted(str(st.get(f"fertig_{k}", "")) for k in offen if st.get(f"fertig_{k}"))
        stand = tage[0] if tage else ""
        n = sum(int(st.get(f"eintraege_{k}", 0) or 0) for k in offen if st.get(f"fertig_{k}"))
        if fehlt:
            grund = osm.meldung if osm.phase == "fehler" and osm.meldung else osm.phase
            laender = ", ".join(fehlt_kurz)
            if len(fehlt_kurz) == 1:
                text = f"Orte: {laender} fehlt ({grund})." if grund else f"Orte: {laender} fehlt."
            else:
                text = f"Orte: {laender} fehlen ({grund})." if grund else f"Orte: {laender} fehlen."
            return _eintrag(False, text, stand=stand, zahl=n, fehlt=fehlt)
        return _eintrag(True, f"Orte: {', '.join(fertig)} bereit, ältester Stand {_datum(stand)}.", stand=stand, zahl=n)
    except Exception as exc:
        return _eintrag(False, f"Orte: Zustand nicht lesbar ({type(exc).__name__}).")


def _woerterbuch() -> dict:
    try:
        import woerterbuch_at
        n = len(woerterbuch_at.WOERTER)
        probe = woerterbuch_at.treffer("Was sind Paradeiser?")
        ok = n >= WOERTERBUCH_MINDESTENS and bool(probe)
        text = f"Wörterbuch: {n} österreichische Wörter." if ok else f"Wörterbuch: {n} österreichische Wörter, die Probe „Paradeiser“ fand nichts."
        return _eintrag(ok, text, zahl=n)
    except Exception as exc:
        return _eintrag(False, f"Wörterbuch: nicht ladbar ({type(exc).__name__}).")


def _kalender(heute: date | None = None) -> dict:
    try:
        import kalender_at
        import kalender_dach
        import kalender_tage
        jahr = (heute or date.today()).year
        at, de, ch, tage = kalender_at.feiertage(jahr), kalender_dach.feiertage_de(jahr), kalender_dach.feiertage_ch(jahr), kalender_tage.tage(jahr)
        n = len(at) + len(de) + len(ch) + len(tage)
        ok = len(at) >= FEIERTAGE_MINDESTENS and len(de) >= FEIERTAGE_MINDESTENS and len(ch) >= 1 and len(tage) >= 5
        return _eintrag(ok, f"Kalender: {len(at)} Feiertage AT, {len(de)} DE, {len(ch)} CH und {len(tage)} Termine für {jahr} gerechnet.", stand=str(jahr), zahl=n)
    except Exception as exc:
        return _eintrag(False, f"Kalender: rechnet nicht ({type(exc).__name__}).")


MODELL_TEXTE = {
    "modell": {"nicht": "Chat-Modell: nicht eingerichtet.", "aus": "Chat-Modell: ausgeschaltet.", "laeuft": "Chat-Modell: läuft ({wo}).",
               "laeuft_ohne": "Chat-Modell: läuft.", "laden": "Chat-Modell: wird gerade geholt oder geladen.",
               "fremd": "Chat-Modell: läuft in einer anderen Fassung als im Katalog ({ist} statt {soll}).",
               "ohne_fassung": "Chat-Modell: läuft, das Programm meldet keine Fassung (Bau vor 2026-10-20d).",
               "starten": "Chat-Modell: startet gerade.", "fehler": "Chat-Modell: läuft nicht ({wie}).",
               "nicht_bereit": "Chat-Modell: läuft gerade nicht.", "unlesbar": "Chat-Modell: Zustand nicht lesbar ({fehler})."},
    "bedeutung": {"nicht": "Bedeutungs-Modell: nicht eingerichtet.", "aus": "Bedeutungs-Modell: ausgeschaltet.",
                  "laeuft": "Bedeutungs-Modell: läuft ({wo}).", "laeuft_ohne": "Bedeutungs-Modell: läuft.",
                  "laden": "Bedeutungs-Modell: wird gerade geholt oder geladen.", "starten": "Bedeutungs-Modell: startet gerade.",
                  "fehler": "Bedeutungs-Modell: läuft nicht ({wie}).", "nicht_bereit": "Bedeutungs-Modell: läuft gerade nicht.",
                  "unlesbar": "Bedeutungs-Modell: Zustand nicht lesbar ({fehler})."},
}


def _katalog_fassung(name: str) -> str | None:
    try:
        import modell_katalog
        for m in modell_katalog.MODELLE.values():
            if m.name == name:
                return modell_katalog.fassung(m.datei)
    except Exception:
        return None
    return None


def _modell(ki, art: str = "modell") -> dict:
    t = MODELL_TEXTE[art]
    if ki is None:
        return _eintrag(False, t["nicht"], gilt=False)
    try:
        z = ki.zustand()
        phase, laeuft, modell = str(z.get("phase") or ""), bool(z.get("laeuft")), str(z.get("modell") or z.get("geraet") or "")
        if phase == "aus":
            return _eintrag(False, t["aus"], gilt=False)
        if laeuft:
            e = _eintrag(True, t["laeuft"].format(wo=modell) if modell else t["laeuft_ohne"], stand=modell)
            if art == "modell" and isinstance(z.get("fassung"), str):
                e["fassung"], e["probe"] = z["fassung"][:STAND_MAX], bool(z.get("probe"))
            return e
        meldung = str(z.get("meldung") or "")
        if phase in ("laden", "starten"):
            return _eintrag(False, t[phase], stand=modell)
        if phase == "fehler" and meldung:
            return _eintrag(False, t["fehler"].format(wie=meldung), stand=modell)
        return _eintrag(False, t["nicht_bereit"], stand=modell)
    except Exception as exc:
        return _eintrag(False, t["unlesbar"].format(fehler=type(exc).__name__))


def _suche(suche: dict | None) -> dict:
    if not isinstance(suche, dict):
        return _eintrag(False, "Suchmaschinen: der Server hat es noch nicht gesagt.", gilt=False)
    try:
        frei, gesamt = int(suche.get("frei") or 0), int(suche.get("gesamt") or 0)
    except (TypeError, ValueError):
        return _eintrag(False, "Suchmaschinen: unlesbare Angabe vom Server.", gilt=False)
    if gesamt <= 0:
        return _eintrag(False, "Suchmaschinen: der Server kennt keine.", gilt=False)
    return _eintrag(frei >= 1, f"Suchmaschinen: {frei} von {gesamt} frei laut Server.", zahl=frei)


def sammeln(*, wiki=None, osm=None, ki=None, bedeutung=None, suche: dict | None = None, heute: date | None = None) -> dict:
    return {"wikipedia": _wikipedia(wiki), "orte": _orte(osm), "woerterbuch": _woerterbuch(), "kalender": _kalender(heute),
            "modell": _modell(ki), "bedeutung": _modell(bedeutung, "bedeutung"), "suche": _suche(suche)}


def zeilen(quellen: dict) -> list[str]:
    out = []
    for name in QUELLEN:
        e = quellen.get(name) if isinstance(quellen, dict) else None
        if not isinstance(e, dict):
            continue
        vorne = "OK" if e.get("ok") else ("nicht vorgesehen" if not e.get("gilt") else "FEHLT")
        out.append(f"{vorne}: {e.get('text') or NAMEN_DE.get(name, name)}")
    return out


def kurz(quellen: dict) -> str:
    schlecht = [NAMEN_DE.get(n, n) for n in QUELLEN if isinstance(quellen.get(n), dict) and quellen[n].get("gilt") and not quellen[n].get("ok")]
    return ("Quellen in Ordnung" if not schlecht else "Quelle fehlt: " + ", ".join(schlecht)) if quellen else ""


def pruefen(quellen) -> dict | None:
    if not isinstance(quellen, dict):
        return None
    out = {}
    for name in QUELLEN:
        e = quellen.get(name)
        if not isinstance(e, dict):
            continue
        fehlt = e.get("fehlt")
        out[name] = _eintrag(bool(e.get("ok")), str(e.get("text") or "")[:TEXT_MAX], gilt=bool(e.get("gilt", True)), stand=str(e.get("stand") or "")[:STAND_MAX],
                             zahl=int(e.get("zahl") or 0) if isinstance(e.get("zahl"), (int, float)) and not isinstance(e.get("zahl"), bool) else 0,
                             fehlt=[str(x) for x in fehlt if isinstance(x, str)] if isinstance(fehlt, list) else None)
    if "modell" in out:
        fassung_pruefen(out["modell"], quellen.get("modell"))
    return out or None


def fassung_pruefen(eintrag: dict, roh) -> None:
    soll = _katalog_fassung(eintrag.get("stand") or "") if eintrag.get("ok") else None
    if soll is None:
        return
    roh = roh if isinstance(roh, dict) else {}
    ist = roh.get("fassung")
    t = MODELL_TEXTE["modell"]
    if not isinstance(ist, str):
        if soll:
            eintrag.update(ok=False, text=t["ohne_fassung"])
        return
    ist = ist[:STAND_MAX]
    eintrag["fassung"] = ist
    if ist != soll and not roh.get("probe"):
        eintrag.update(ok=False, text=t["fremd"].format(ist=ist or "Grundfassung", soll=soll or "Grundfassung"))


class Sammlung:

    def __init__(self, pfad: Path, *, jetzt=time.time, schreiben=None, lesen=None) -> None:
        self.pfad = Path(pfad)
        self._jetzt = jetzt
        self._schreiben = schreiben
        self._lesen = lesen
        self._geraete: dict[str, dict] = {}
        import threading
        self._lock = threading.Lock()
        self._datei_geladen = False

    def _datei_lesen(self) -> dict:
        if self._lesen is not None:
            d = self._lesen()
        else:
            import sicher_schreiben
            d = sicher_schreiben.json_laden(self.pfad, {})
        g = d.get("geraete") if isinstance(d, dict) else None
        return {k: v for k, v in g.items() if isinstance(v, dict)} if isinstance(g, dict) else {}

    def _datei_schreiben(self, admins: dict) -> None:
        d = {"geraete": admins, "zeit": _jetzt_iso(self._jetzt())}
        if self._schreiben is not None:
            self._schreiben(d)
            return
        import sicher_schreiben
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        sicher_schreiben.json_datei(self.pfad, d, indent=1)

    def melden(self, kennung: str, name: str, *, admin: bool, quellen: dict) -> dict:
        kennung = str(kennung)[:40]
        t = self._jetzt()
        with self._lock:
            if not self._datei_geladen:
                for k, v in self._datei_lesen().items():
                    self._geraete.setdefault(k, v)
                self._datei_geladen = True
            alt = self._geraete.get(kennung) or {}
            zuletzt_ok = dict(alt.get("zuletzt_ok") or {})
            nicht_ok_seit = dict(alt.get("nicht_ok_seit") or {})
            for q, e in quellen.items():
                if not e.get("gilt"):
                    nicht_ok_seit.pop(q, None)
                    continue
                if e.get("ok"):
                    zuletzt_ok[q] = _jetzt_iso(t)
                    nicht_ok_seit.pop(q, None)
                else:
                    nicht_ok_seit.setdefault(q, _jetzt_iso(t))
            e = {"name": " ".join(str(name or "").split())[:60], "admin": bool(admin), "zeit": _jetzt_iso(t), "quellen": quellen,
                 "zuletzt_ok": zuletzt_ok, "nicht_ok_seit": nicht_ok_seit}
            self._geraete[kennung] = e
            while len(self._geraete) > GERAETE_MAX:
                self._geraete.pop(next(iter(self._geraete)))
            if admin:
                self._datei_schreiben({k: v for k, v in self._geraete.items() if v.get("admin")})
            return dict(e)

    def alle(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._geraete.items()}

    def kurz(self, kennung: str) -> str:
        with self._lock:
            e = self._geraete.get(str(kennung)[:40])
        return kurz(e.get("quellen") or {}) if e else ""

    def vergessen(self, kennung: str) -> None:
        with self._lock:
            e = self._geraete.pop(str(kennung)[:40], None)
            if e and e.get("admin"):
                self._datei_schreiben({k: v for k, v in self._geraete.items() if v.get("admin")})


def still(geraete: dict, jetzt: float, *, still_ab_s: float = STILL_AB_S, frisch_s: float = FRISCH_S) -> list[dict]:
    out = []
    for kennung, e in (geraete or {}).items():
        if not isinstance(e, dict) or not e.get("admin"):
            continue
        if jetzt - iso_zu_s(e.get("zeit", "")) > frisch_s:
            continue
        for q, seit in (e.get("nicht_ok_seit") or {}).items():
            s = jetzt - iso_zu_s(seit)
            if s >= still_ab_s:
                text = str(((e.get("quellen") or {}).get(q) or {}).get("text") or NAMEN_DE.get(q, q))
                out.append({"geraet": str(kennung), "name": str(e.get("name") or ""), "quelle": str(q), "seit_s": s, "text": text})
    return out


__all__ = ["sammeln", "zeilen", "kurz", "pruefen", "Sammlung", "still", "QUELLEN", "NAMEN_DE", "MELDEN_ABSTAND_S", "STILL_AB_S", "FRISCH_S"]
