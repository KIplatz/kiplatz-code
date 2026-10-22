# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import random
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import community
import credits
import hausordnung
import kartenteiler as karten
import ki_laufzeit
import messwerte
import node_idle_detector
import node_local_state
import sicher_schreiben
import scheiben
import schleifenbremse
import vermittlung_basis
import verteiler

DIRNAME = "rechen"
STAND_DATEI = "stand.json"
LEERLAUF_S = 120
WARTEN_LEER_S = 60
WARTEN_FEHLER_S = 60
FEHLER_ERST_S = 3
WARTEN_LEERLAUF_S = 15
BATCH = 4
HITZE_C = 85.0
HITZE_PAUSE_S = 60
RAM_GRENZE_PROZENT = 90
TEXTE = {
    "aus": "Gestoppt. Nichts läuft.",
    "startet": "Fragt beim Community-Server nach Arbeit …",
    "nicht_angemeldet": "Dieses Gerät ist noch nicht angemeldet (Einladungscode unter „Meine Community“).",
    "akku": "Am Akku rechnet dein Laptop nicht für andere. Am Strom geht es von selbst weiter.",
    "leerlauf": "Wartet, bis du den Rechner {s} Sekunden nicht benutzt.",
    "am_geraet": "Du arbeitest gerade am Gerät. Fragen der Community beantwortet dein PC sofort, alles andere wartet, bis du 2 Minuten weg bist.",
    "hitze": "Hitzebremse: Die Grafikkarte hat {t} °C. Pause, bis sie unter {max} °C ist.",
    "arbeitsspeicher": "Der Arbeitsspeicher ist zu {p} % belegt und du arbeitest am Gerät. Wikipedia und die Arbeit im Hintergrund ruhen, bis du eine Weile weg bist.",
    "laden": "Bedeutungs-Modell wird geholt und gestartet …",
    "wartet": "Bereit. Gerade fragt niemand und es gibt nichts zu rechnen.",
    "rechnet": "Rechnet einen Auftrag ({n} Abschnitte).",
    "prueft": "Prüft einen neuen Eintrag gegen die Platzordnung.",
    "vertieft": "Vertieft einen Abschnitt aus „{titel}“: Zusammenfassung und Fragen mit Antworten.",
    "vertieft_prueft": "Prüft, ob ein anderer Rechner einen Abschnitt aus „{titel}“ richtig vertieft hat.",
    "speicher": "Hält eine Scheibe des gemeinsamen Wissens auf der Festplatte (Paket 6).",
    "themen": "Sammelt Wissen zu deinen eigenen Themen, privat, nur auf diesem Gerät (Paket 7).",
    "vorwaermt": "Holt Wetter und Schlagzeilen für alle Mitglieder vor (einmal am Morgen).",
    "prueft_selbst": "Prüfstand: stellt KIplatz eine Prüfrunde, solange die Grafikkarte sonst frei ist.",
    "trainiert": "Trainiert KIplatz. Fragen beantworten so lange andere PCs.",
    "antwortet": "Beantwortet eine Frage von {fuer}.",
    "bereit": "Bereit, KIplatz ist geladen. Gerade fragt niemand.",
    "fehler": "Gerade geht es nicht: {text} Nächster Versuch in einer Minute.",
}
WARTEN_FRAGEN_S = 3
WARTEN_ARBEIT_S = 25
NACH_WARTEN_S = 0.5
STAND_ABSTAND_S = 300
VORRANG_NACHLAUF_S = 30
VORRANG_WARTEN_MAX_S = 180
WACHE_WARTEN_S = 20
MITGLIED_NACHLAUF_S = 10
KARTE_NACHLAUF_S = 2
TIPPEN_HALTEN_S = 60
HINTERGRUND_ARTEN = (verteiler.PRUEF_ART, verteiler.VERTIEF_ART, verteiler.VERTIEF_PRUEF_ART)


def fehler_warten_s(code: str, n: int) -> float:
    grenze = WARTEN_FEHLER_S if "VOLL" in str(code or "") else min(WARTEN_FEHLER_S, FEHLER_ERST_S * (2 ** max(0, min(int(n), 10))))
    return grenze * random.uniform(0.5, 1.5)


def hintergrund(auftrag: dict | None) -> bool:
    if not isinstance(auftrag, dict):
        return False
    return auftrag.get("art") in HINTERGRUND_ARTEN or (auftrag.get("art") is None and isinstance(auftrag.get("abschnitte"), list))


def _heute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def wach_halten(an: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED if an else ES_CONTINUOUS))
    except (OSError, AttributeError):
        return False


def am_strom_windows() -> bool:
    try:
        import psutil
        b = psutil.sensors_battery()
    except Exception:
        return True
    if b is None:
        return True
    return bool(b.power_plugged)


class Rechenarbeit:
    _gpu_werkzeug: str | None = ""
    def __init__(self, core: app_core.AppCore, gemeinschaft, kontobuch: credits.Kontobuch, *, geraet_name: str = "dieses Gerät",
                 server: ki_laufzeit.KiServer | None = None, herunterladen=ki_laufzeit.herunterladen, geraete_ermitteln=ki_laufzeit.geraete_ermitteln,
                 leerlauf_s=None, schlafen=None, protokoll=None, urteil=None, urteil_bereit=None,
                 antworten=None, ki_starten=None, ki_stoppen=None, antworten_moeglich=None, fragen_immer=None, am_strom=None,
                 vertiefen=None, vertiefen_pruefen=None, vorwaermen=None, pruefstand=None, server_geteilt=None, jetzt=None, halter=None, themen=None, hitze_messen=None, ram_messen=None,
                 modell_name=None, stand=None, kartenteiler=None, kopie=None, speicher_freigeben=None, karte_vergeben=None) -> None:
        self._core = core
        self._gemeinschaft = gemeinschaft if callable(gemeinschaft) else (lambda: gemeinschaft)
        self._urteil = urteil
        self._empfang = schleifenbremse.Schleifenbremse(hoechstens=EMPFANG_HOECHSTENS, fenster_s=EMPFANG_FENSTER_S, pause_s=EMPFANG_PAUSE_S, log=lambda z: self._log(z))
        self._ergebnis_ok = True
        self._urteil_bereit = urteil_bereit or (lambda: False)
        self._antworten = antworten
        self._ki_starten = ki_starten
        self._ki_stoppen = ki_stoppen
        self._antworten_moeglich = antworten_moeglich or (lambda: True)
        self._fragen_immer = fragen_immer or (lambda: False)
        self._am_strom = am_strom or am_strom_windows
        self._vertiefen = vertiefen
        self._vertiefen_pruefen = vertiefen_pruefen
        self._vorwaermen = vorwaermen
        self._pruefstand = pruefstand
        self._karte_vergeben = karte_vergeben
        self._server_geteilt = server_geteilt or (lambda: False)
        self._jetzt = jetzt or time.time
        self._halter = halter
        def _kopie_sicher() -> bool:
            try:
                return bool(kopie()) if kopie is not None else False
            except Exception:
                return False
        self._kopie = _kopie_sicher
        self._stand = stand
        self._themen = themen
        self.vorrang = threading.Event()
        self._vorrang_bis = 0.0
        self._vorrang_wer: set[str] = set()
        self._vorrang_lock = threading.Lock()
        self._tippen_bis = 0.0
        self._karte = kartenteiler if kartenteiler is not None else karten.Kartenteiler()
        self._karten_wache: threading.Thread | None = None
        self._mitglied_frage: dict | None = None
        self._mitglied_laeuft = False
        self._wache: threading.Thread | None = None
        self._wache_an = threading.Event()
        self._ki_von_uns = False
        self._modell_name = ""
        self._modell_fn = modell_name
        self.geprueft_n = 0
        self.antwort_seit = 0.0
        self._kontobuch = kontobuch
        self._geraet_name = geraet_name
        self.ordner = ki_laufzeit.KiOrdner(core.base_dir)
        self.server = server or ki_laufzeit.KiServer(self.ordner)
        self._herunterladen = herunterladen
        self._geraete_ermitteln = geraete_ermitteln
        self._leerlauf_s = leerlauf_s or self._leerlauf_windows
        self._schlafen = schlafen or self._warten
        self._log = protokoll or (lambda line: None)
        self._stand_pfad = core.base_dir / DIRNAME / STAND_DATEI
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self._hitze_messen = hitze_messen
        self._ram_messen = ram_messen
        self._speicher_freigeben = speicher_freigeben
        self.wiki_ruht = False
        self._runde_lock = threading.Lock()
        self.phase = "aus"
        self.meldung = ""
        self.wahl: ki_laufzeit.Wahl | None = None
        self.auftrag_n = 0
        self.server_stand: dict | None = None
        self._stand_geholt = 0.0

    @property
    def _community(self) -> community.Community:
        return self._gemeinschaft()


    def _stand_laden(self) -> dict:
        d = sicher_schreiben.json_laden(self._stand_pfad, {})
        if d.get("tag") != _heute():
            alt_tag = {k: int(d.get(k, 0) or 0) for k in ("abschnitte", "geprueft", "credits", "antworten", "vertieft", "vertieft_geprueft")}
            vorher = {"tag": str(d.get("tag", "")), **alt_tag} if d.get("tag") and any(alt_tag.values()) else d.get("vorher")
            d = {"tag": _heute(), "vorher": vorher if isinstance(vorher, dict) else None, "abschnitte": 0, "geprueft": 0, "credits": 0, "auftraege": 0, "antworten": 0, "fuer": {},
                 "gesamt_abschnitte": int(d.get("gesamt_abschnitte", 0) or 0), "gesamt_credits": int(d.get("gesamt_credits", 0) or 0),
                 "gesamt_antworten": int(d.get("gesamt_antworten", 0) or 0), "letzter": d.get("letzter"), "tempo": d.get("tempo", 0.0),
                 "gesamt_vertieft": int(d.get("gesamt_vertieft", 0) or 0), "gesamt_vertieft_geprueft": int(d.get("gesamt_vertieft_geprueft", 0) or 0),
                 "credits_neustart": d.get("credits_neustart")}
        if d.get("credits_neustart") != credits.NEUSTART:
            d["credits"], d["gesamt_credits"], d["credits_neustart"] = 0, 0, credits.NEUSTART
            if isinstance(d.get("vorher"), dict):
                d["vorher"]["credits"] = 0
        d.setdefault("antworten", 0)
        d.setdefault("fuer", {})
        d.setdefault("gesamt_antworten", 0)
        for k in ("vertieft", "vertieft_geprueft", "gesamt_vertieft", "gesamt_vertieft_geprueft"):
            d.setdefault(k, 0)
        return d

    def _vertieft_zaehlen(self, *, vertieft: int = 0, geprueft: int = 0, credits_: int = 0) -> dict:
        d = self._stand_laden()
        d["vertieft"] += vertieft
        d["vertieft_geprueft"] += geprueft
        d["gesamt_vertieft"] += vertieft
        d["gesamt_vertieft_geprueft"] += geprueft
        d["credits"] += credits_
        d["gesamt_credits"] += credits_
        d["auftraege"] += 1
        d["letzter"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._stand_schreiben(d)
        return d

    def _antwort_zaehlen(self, fuer: str, credits_: int) -> dict:
        d = self._stand_laden()
        d["antworten"] += 1
        d["gesamt_antworten"] += 1
        d["credits"] += credits_
        d["gesamt_credits"] += credits_
        d["auftraege"] += 1
        fuer = (fuer or "jemanden")[:60]
        d["fuer"][fuer] = int(d["fuer"].get(fuer, 0)) + 1
        d["letzter"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._stand_schreiben(d)
        return d

    def _stand_schreiben(self, d: dict) -> None:
        app_core.ensure_plain_directory(self._stand_pfad.parent)
        sicher_schreiben.json_datei(self._stand_pfad, d)

    def _zaehlen(self, *, abschnitte: int, geprueft: int, credits_: int) -> dict:
        d = self._stand_laden()
        d["abschnitte"] += abschnitte
        d["geprueft"] += geprueft
        d["credits"] += credits_
        d["auftraege"] += 1
        d["gesamt_abschnitte"] += abschnitte
        d["gesamt_credits"] += credits_
        d["letzter"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._stand_schreiben(d)
        return d


    def text_de(self) -> str:
        d = self._stand_laden()
        if self.phase == "rechnet":
            kopf = TEXTE["rechnet"].format(n=self.auftrag_n)
        elif self.phase == "fehler":
            kopf = TEXTE["fehler"].format(text=self.meldung)
        elif self.phase == "leerlauf":
            kopf = TEXTE["leerlauf"].format(s=LEERLAUF_S)
        elif self.phase == "hitze":
            kopf = TEXTE["hitze"].format(t=self.meldung or "?", max=int(HITZE_C))
        elif self.phase == "arbeitsspeicher":
            kopf = TEXTE["arbeitsspeicher"].format(p=self.meldung or "?")
        elif self.phase == "antwortet":
            kopf = TEXTE["antwortet"].format(fuer=self.meldung or "einem Mitglied")
        elif self.phase in ("vertieft", "vertieft_prueft"):
            kopf = TEXTE[self.phase].format(titel=self.meldung or "einer Quelle")
        else:
            kopf = TEXTE.get(self.phase, "")
        teile = []
        if d["antworten"]:
            fuer = ", ".join(f"{n} für {wer}" for wer, n in sorted(d["fuer"].items(), key=lambda kv: -kv[1])[:3])
            teile.append(f"{d['antworten']} Fragen beantwortet" + (f" ({fuer})" if fuer else ""))
        if d["abschnitte"]:
            teile.append(f"{d['abschnitte']} Abschnitte berechnet ({d['geprueft']} bestätigt)")
        if d["vertieft"] or d["vertieft_geprueft"]:
            teile.append(f"{d['vertieft']} Abschnitte vertieft, {d['vertieft_geprueft']} von anderen geprüft")
        if teile:
            kopf += f"\nHeute: {' · '.join(teile)} · Credits +{d['credits']}"
        elif self.phase not in ("aus", "nicht_angemeldet"):
            kopf += "\nHeute: noch nichts für andere erarbeitet."
        return kopf

    def zustand(self) -> dict:
        d = self._stand_laden()
        return {"phase": self.phase, "meldung": self.meldung, "text": self.text_de(), "laeuft": self._thread is not None and self._thread.is_alive(),
                "angemeldet": self._community.geraet() is not None, "modell_da": self.ordner.modell_da(ki_laufzeit.EMBEDDING),
                "modell_laeuft": self.server.laeuft(), "geraet": self.wahl.geraet_name_de() if (self.wahl and self.server.laeuft()) else None,
                "heute": {"abschnitte": d["abschnitte"], "geprueft": d["geprueft"], "credits": d["credits"], "auftraege": d["auftraege"], "antworten": d["antworten"], "fuer": d["fuer"],
                          "vertieft": d["vertieft"], "vertieft_geprueft": d["vertieft_geprueft"]},
                "vorher": d.get("vorher") if isinstance(d.get("vorher"), dict) else None,
                "gesamt": {"abschnitte": d["gesamt_abschnitte"], "credits": d["gesamt_credits"], "antworten": d["gesamt_antworten"], "letzter": d.get("letzter"),
                           "vertieft": d["gesamt_vertieft"], "vertieft_geprueft": d["gesamt_vertieft_geprueft"]},
                "server": self.server_stand}


    warten_arbeit_s: float = WARTEN_ARBEIT_S

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._halt.clear()
            self.phase, self.meldung = "startet", ""
            self._thread = threading.Thread(target=self._schleife, name="rechenarbeit", daemon=True)
            self._thread.start()
            if self._karten_wache is None or not self._karten_wache.is_alive():
                self._karten_wache = threading.Thread(target=self._karte_beobachten, name="karten-wache", daemon=True)
                self._karten_wache.start()
            return True

    def stop(self, *, timeout_s: float = 10.0) -> None:
        self._halt.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=timeout_s)
        offen = self._frage_nehmen()
        if offen is not None:
            self._frage_zurueck(offen, "das Gerät wurde gerade angehalten")
        self._server_stoppen()
        self.phase, self.meldung, self.auftrag_n = "aus", "", 0


    def vorrang_beginn(self, wer: str = "person") -> None:
        with self._vorrang_lock:
            neu = wer not in self._vorrang_wer
            self._vorrang_wer.add(wer)
            if wer == "person":
                self._vorrang_wer.discard("tippen")
                self._tippen_bis = 0.0
            self.vorrang.set()
        if wer == "person" and neu:
            self._karte.beginnen()

    def vorrang_ende(self, wer: str = "person") -> None:
        with self._vorrang_lock:
            war = wer in self._vorrang_wer
            self._vorrang_wer.discard(wer)
            nachlauf = {"person": VORRANG_NACHLAUF_S, "karte": KARTE_NACHLAUF_S, "tippen": 0.0}.get(wer, MITGLIED_NACHLAUF_S)
            self._vorrang_bis = max(self._vorrang_bis, self._jetzt() + nachlauf)
            if not self._vorrang_wer:
                self.vorrang.clear()
        if wer == "person" and war:
            self._karte.ende()

    def tippen(self) -> None:
        with self._vorrang_lock:
            if "person" in self._vorrang_wer:
                return
            self._tippen_bis = self._jetzt() + TIPPEN_HALTEN_S
        self.vorrang_beginn("tippen")

    def _tippen_ablaufen(self) -> None:
        with self._vorrang_lock:
            if "tippen" in self._vorrang_wer and self._jetzt() >= self._tippen_bis:
                self._vorrang_wer.discard("tippen")
                if not self._vorrang_wer:
                    self.vorrang.clear()

    def frage_wartet(self) -> bool:
        self._tippen_ablaufen()
        return self.vorrang.is_set() or self._mitglied_frage is not None

    def _karte_beobachten(self) -> None:
        while not self._halt.wait(karten.NACHSEHEN_S):
            try:
                self._tippen_ablaufen()
                self._karte.da_melden()
                self._karte.erneuern()
                andere = self._karte.anderer_antwortet() or self._karte.ruhen()
                with self._vorrang_lock:
                    hat = "karte" in self._vorrang_wer
                if andere and not hat:
                    self.vorrang_beginn("karte")
                    self._log("OK rechenarbeit karte: ein anderes KIplatz auf diesem Rechner antwortet, die Hintergrundarbeit macht Pause")
                elif hat and not andere:
                    self.vorrang_ende("karte")
            except Exception as exc:
                self._log(f"FEHLER karten-wache: {type(exc).__name__}")
                self._halt.wait(5)
        self._karte.da_ende()
        with self._vorrang_lock:
            hat = "karte" in self._vorrang_wer
        if hat:
            self.vorrang_ende("karte")


    def _wache_starten(self) -> bool:
        if self._antworten is None or not bool(self._antworten_moeglich()) or not (bool(self._urteil_bereit()) or self._ki_starten is not None):
            return False
        self._wache_an.set()
        t = self._wache
        if t is not None and t.is_alive():
            return True

        def wachen() -> None:
            while self._wache_an.is_set() and not self._halt.is_set():
                if self._mitglied_frage is not None or self._mitglied_laeuft:
                    self._halt.wait(0.2)
                    continue
                try:
                    a = self._community.auftrag_holen(antworten=True, leistung=self._leistung(), warten_s=WACHE_WARTEN_S, nur_fragen=True)
                except Exception as exc:
                    self._log(f"INFO frage-wache: {type(exc).__name__}")
                    self._halt.wait(5)
                    continue
                if a is not None and a.get("art") != vermittlung_basis.ART:
                    self._log(f"INFO frage-wache: der Server gab statt einer Frage {str(a.get('art') or 'einen Rechenauftrag')[:30]} (älterer Dienst); er vergibt ihn nach der Frist neu")
                if a is not None and a.get("art") == vermittlung_basis.ART:
                    if self._halt.is_set():
                        self._frage_zurueck(a, "das Gerät wurde gerade angehalten")
                        return
                    with self._vorrang_lock:
                        self._mitglied_frage = a
                    self.vorrang_beginn("mitglied")
                    self._log(f"OK rechenarbeit frage-wache: Frage {a.get('auftrag')} angenommen, die Hintergrundarbeit macht Pause")
                    continue
                if a is None and not getattr(self._community, "gewartet", False):
                    self._halt.wait(WARTEN_FRAGEN_S)

        self._wache = threading.Thread(target=wachen, name="frage-wache", daemon=True)
        self._wache.start()
        return True

    def _wache_ende(self) -> None:
        self._wache_an.clear()

    def _frage_zurueck(self, auftrag: dict, grund: str) -> None:
        try:
            if hasattr(self._community, "antwort_verzicht"):
                self._community.antwort_verzicht(str(auftrag.get("auftrag", "")), grund)
        except Exception as exc:
            self._log(f"FEHLER frage zurück: {type(exc).__name__}")

    def fragen_abgeben(self, grund: str) -> None:
        self._wache_ende()
        t = self._wache
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(WACHE_WARTEN_S + 5)
        a = self._frage_nehmen()
        if a is not None:
            self._frage_zurueck(a, grund)
            self.vorrang_ende("mitglied")

    def mitglied_jetzt(self) -> bool:
        return self._mitglied_beantworten()

    def _frage_nehmen(self, *, beantworten: bool = False) -> dict | None:
        with self._vorrang_lock:
            a, self._mitglied_frage = self._mitglied_frage, None
            if a is not None and beantworten:
                self._mitglied_laeuft = True
            return a

    def _mitglied_beantworten(self) -> bool:
        a = self._frage_nehmen(beantworten=True)
        if a is None:
            return False
        try:
            self._antwort_geben(a)
        finally:
            self.vorrang_ende("mitglied")
            with self._vorrang_lock:
                self._mitglied_laeuft = False
        return True

    def vorrang_aktiv(self) -> bool:
        self._tippen_ablaufen()
        return self.vorrang.is_set() or self._jetzt() < self._vorrang_bis

    def _vorrang_abwarten(self) -> None:
        bis = self._jetzt() + VORRANG_WARTEN_MAX_S
        while self.vorrang_aktiv() and self._darf() and self._jetzt() < bis and self._mitglied_frage is None:
            self._halt.wait(0.5)


    def _server_stoppen(self) -> None:
        if not self._server_geteilt():
            self.server.stop()

    def _leerlauf_windows(self) -> float | None:
        try:
            return node_idle_detector.get_idle_seconds()
        except node_idle_detector.IdleDetectionError:
            return None

    def _warten(self, sekunden: float) -> None:
        self._halt.wait(sekunden)


    def _hitze_c(self) -> float | None:
        if self._hitze_messen is not None:
            return self._hitze_messen()
        if self._gpu_werkzeug == "":
            self._gpu_werkzeug = messwerte.gpu_werkzeug()
        if not self._gpu_werkzeug:
            return None
        return messwerte.gpu_messen(self._gpu_werkzeug, timeout_s=2.0).get("gpu_temperatur_c")

    _ram_standard = staticmethod(messwerte.ram_messen)

    def _speicherbremse(self) -> bool:
        p = (self._ram_messen or type(self)._ram_standard)()
        voll = p is not None and p >= RAM_GRENZE_PROZENT
        leer = self._leerlauf_s() if (voll or self.wiki_ruht) else None
        weg = leer is not None and leer >= LEERLAUF_S
        if self.wiki_ruht and weg:
            self.wiki_ruht = False
            self._log("OK rechenarbeit wikipedia geht weiter: niemand am Gerät")
        if not voll or weg:
            if self.phase == "arbeitsspeicher":
                self._log(f"OK rechenarbeit speicherbremse gelöst: {'?' if p is None else p} % belegt")
                self.phase = "wartet"
            return False
        if self.phase != "arbeitsspeicher":
            self.wiki_ruht = True
            self._server_stoppen()
            if self._speicher_freigeben is not None:
                try:
                    self._speicher_freigeben()
                except Exception as exc:
                    self._log(f"FEHLER rechenarbeit speicher freigeben: {type(exc).__name__}")
            self._log(f"OK rechenarbeit speicherbremse: Arbeitsspeicher {p} % belegt, jemand arbeitet am Gerät; Wikipedia und Hintergrundarbeit ruhen, Fragen weiter")
        self.phase, self.meldung, self.auftrag_n = "arbeitsspeicher", str(p), 0
        return True

    def _fragen_moeglich(self) -> bool:
        return self._antworten is not None and bool(self._antworten_moeglich()) and (bool(self._urteil_bereit()) or self._ki_starten is not None)

    def _nur_fragen(self, phase: str) -> None:
        leistung = self._leistung()
        auftrag = self._community.auftrag_holen(pruefen=False, antworten=True, leistung=leistung, warten_s=self.warten_arbeit_s)
        if self._halt.is_set():
            if auftrag is not None and auftrag.get("art") == vermittlung_basis.ART:
                self._frage_zurueck(auftrag, "das Gerät wurde gerade angehalten")
            return
        if auftrag is not None and auftrag.get("art") == vermittlung_basis.ART:
            meldung = self.meldung
            self._antwort_geben(auftrag)
            self.phase = phase
            if phase == "arbeitsspeicher":
                self.meldung = meldung
            return
        self._schlafen(NACH_WARTEN_S if getattr(self._community, "gewartet", False) else WARTEN_FRAGEN_S)

    def _hitzebremse(self) -> bool:
        t = self._hitze_c()
        if t is None or t < HITZE_C:
            if self.phase == "hitze":
                self._log(f"OK rechenarbeit hitzebremse gelöst: {'?' if t is None else round(t)} °C")
                self.phase = "wartet"
            return False
        if self.phase != "hitze":
            self._log(f"OK rechenarbeit hitzebremse: Grafikkarte {round(t)} °C, Pause {HITZE_PAUSE_S} s, bis unter {int(HITZE_C)} °C")
        self.phase, self.meldung, self.auftrag_n = "hitze", str(round(t)), 0
        self._schlafen(HITZE_PAUSE_S)
        return True

    def anhalten(self, *, hoechstens_s: float = 600.0) -> bool:
        return self._runde_lock.acquire(timeout=hoechstens_s)

    def weiter(self) -> None:
        try:
            self._runde_lock.release()
        except RuntimeError:
            pass

    def _darf(self) -> bool:
        return not self._halt.is_set() and self._core.run_state() is node_local_state.RunState.ACTIVE

    def _threads(self) -> int | None:
        first = self._core.load_first_start()
        cores = int(first.cpu_cores or 0) if first else 0
        if not cores:
            return None
        return max(1, cores * int(self._core.load_freigabe().cpu_prozent) // 100)

    def _modell_bereit(self) -> None:
        if self.server.laeuft():
            return
        self.phase = "laden"
        self.ordner.anlegen()
        if not self.ordner.laufzeit_da():
            zip_pfad = self.ordner.downloads_dir / ki_laufzeit.LAUFZEIT.datei
            if not ki_laufzeit.pruefsumme_ok(zip_pfad, ki_laufzeit.LAUFZEIT):
                self._herunterladen(ki_laufzeit.LAUFZEIT, zip_pfad)
            ki_laufzeit.laufzeit_entpacken(zip_pfad, self.ordner.laufzeit_dir, schon_da=self.ordner.laufzeit_da)
        if not self.ordner.modell_da(ki_laufzeit.EMBEDDING):
            self._herunterladen(ki_laufzeit.EMBEDDING, self.ordner.modell_pfad(ki_laufzeit.EMBEDDING))
        wahl = ki_laufzeit.waehlen_rechen(self._geraete_ermitteln(self.ordner.server_exe))
        self.wahl = wahl
        self.server.start(wahl, embedding=True, threads=self._threads() if wahl.geraet is None else None)
        self._log(f"OK rechenarbeit modell {wahl.geraet.kennung if wahl.geraet else 'cpu'}")

    def _anmelden(self) -> bool:
        if self._community.geraet() is not None:
            return True
        if not self._community.ist_admin():
            return False
        d = self._community.geraet_anmelden(self._geraet_name)
        self._log(f"OK rechenarbeit angemeldet {d['kennung']}")
        return True


    def _schleife(self) -> None:
        wach_halten(True)
        fehler_n = 0
        while self._darf():
            try:
                with self._runde_lock:
                    self._eine_runde()
                fehler_n = 0
            except app_core.AppError as exc:
                if exc.code == "VORRANG":
                    if self._mitglied_frage is not None:
                        self._log("OK rechenarbeit zurückgestellt (eine Frage eines Mitglieds hat Vorrang)")
                        continue
                    with self._vorrang_lock:
                        karte = self._vorrang_wer == {"karte"}
                    self._log("OK rechenarbeit zurückgestellt (ein anderes KIplatz auf diesem Rechner antwortet gerade)" if karte
                              else f"OK rechenarbeit zurückgestellt (die eigene Frage hat Vorrang): {exc.detail}")
                    self.phase, self.auftrag_n = "wartet", 0
                    self._schlafen(1)
                    continue
                self.phase, self.meldung = "fehler", exc.detail
                self._log(f"ABGELEHNT rechenarbeit: {exc.code}: {exc.detail}")
                self._schlafen(fehler_warten_s(exc.code, fehler_n))
                fehler_n += 1
            except Exception as exc:
                self.phase, self.meldung = "fehler", f"Unerwarteter Fehler: {type(exc).__name__}"
                self._log(f"FEHLER rechenarbeit: {type(exc).__name__}: {exc}")
                self._schlafen(WARTEN_FEHLER_S)
        self._server_stoppen()
        self._ki_freigeben()
        wach_halten(False)
        if self.phase != "aus":
            self.phase, self.auftrag_n = "aus", 0

    def _eine_runde(self) -> None:
        if not self._anmelden():
            self.phase = "nicht_angemeldet"
            self._schlafen(WARTEN_LEER_S)
            return
        try:
            vergeben = str(self._karte_vergeben() or "") if self._karte_vergeben is not None else ""
        except Exception:
            vergeben = ""
        if vergeben:
            if self.phase != "trainiert":
                self._log("OK rechenarbeit ruht: die Grafikkarte ist gerade für einen Test oder das Training vergeben")
            self.phase, self.meldung = "trainiert", vergeben
            self._schlafen(WARTEN_LEERLAUF_S)
            return
        if self._mitglied_beantworten():
            return
        try:
            ruhen = self._karte.ruhen()
        except Exception:
            ruhen = False
        if ruhen:
            if self.phase != "ruht":
                self._server_stoppen()
                self._ki_freigeben()
                self._log("OK rechenarbeit ruht: auf diesem Rechner arbeitet das KIplatz des Benutzers, der gerade angemeldet ist")
            self.phase, self.meldung = "ruht", "Auf diesem PC arbeitet gerade das KIplatz eines anderen Windows-Benutzers. Dieses hier ruht so lange."
            self._schlafen(WARTEN_LEERLAUF_S)
            return
        if not self._am_strom():
            if self.phase != "akku":
                self._server_stoppen()
                self._ki_freigeben()
                self._log("OK rechenarbeit akku: pausiert, bis der Rechner wieder am Strom ist")
            self.phase, self.meldung = "akku", "Am Akku rechnet dein Laptop nicht für andere. Am Strom geht es von selbst weiter."
            self._schlafen(WARTEN_LEERLAUF_S)
            return
        if self._hitzebremse():
            return
        nur_leerlauf = self._core.load_freigabe().nur_im_leerlauf
        if self._speicherbremse():
            if (not nur_leerlauf or self._fragen_immer()) and self._fragen_moeglich():
                self._nur_fragen("arbeitsspeicher")
            else:
                self._schlafen(WARTEN_LEERLAUF_S)
            return
        leer = self._leerlauf_s()
        if not nur_leerlauf and (leer is None or leer < LEERLAUF_S):
            if self.phase != "am_geraet":
                self.wiki_ruht = True
                self._server_stoppen()
                if self._speicher_freigeben is not None:
                    try:
                        self._speicher_freigeben()
                    except Exception as exc:
                        self._log(f"FEHLER rechenarbeit speicher freigeben: {type(exc).__name__}")
                self._log("OK rechenarbeit am gerät: jemand arbeitet, Hintergrundarbeit ruht, Fragen weiter")
            self.phase = "am_geraet"
            if self._fragen_moeglich():
                self._nur_fragen("am_geraet")
            else:
                self._schlafen(WARTEN_LEERLAUF_S)
            return
        if nur_leerlauf:
            if leer is None or leer < LEERLAUF_S:
                if self.phase != "leerlauf":
                    self._server_stoppen()
                    if not self._fragen_immer():
                        self._ki_freigeben()
                self.phase = "leerlauf"
                if self._fragen_immer() and self._fragen_moeglich():
                    self._nur_fragen("leerlauf")
                    return
                self._schlafen(WARTEN_LEERLAUF_S)
                return
        vorrang = self.vorrang_aktiv()
        kann_pruefen = self._urteil is not None and bool(self._urteil_bereit()) and not vorrang
        kann_antworten = self._antworten is not None and (bool(self._urteil_bereit()) or self._ki_starten is not None) and bool(self._antworten_moeglich())
        kann_vertiefen = self._vertiefen is not None and (bool(self._urteil_bereit()) or self._ki_starten is not None) and bool(self._antworten_moeglich()) and not vorrang
        leistung = self._leistung() if (kann_antworten or kann_pruefen or kann_vertiefen) else None
        if leistung is not None:
            try:
                gleich, andere = self._karte.geschwister_genau()
                leistung["geschwister"], leistung["andere_benutzer"] = gleich + andere, andere
            except Exception:
                pass
        speicher = None
        if self._halter is not None:
            try:
                self._halter.aufraeumen()
                if time.monotonic() - getattr(self, "_veraltet_zuletzt", -1e9) >= 1800:
                    self._veraltet_zuletzt = time.monotonic()
                    self._halter.veraltete_loeschen()
                speicher = self._halter.speicher()
            except Exception as exc:
                self._log(f"FEHLER scheiben speicher: {type(exc).__name__}")
        stand = ""
        if self._stand is not None:
            try:
                stand = str(self._stand() or "")
            except Exception as exc:
                self._log(f"FEHLER stand: {type(exc).__name__}")
        auftrag = self._community.auftrag_holen(pruefen=kann_pruefen, antworten=kann_antworten, leistung=leistung, vertiefen=kann_vertiefen, speicher=speicher,
                                                warten_s=self.warten_arbeit_s if kann_antworten else 0.0, **({"stand": stand} if stand else {}))
        if self._halt.is_set():
            if auftrag is not None and auftrag.get("art") == vermittlung_basis.ART:
                self._frage_zurueck(auftrag, "das Gerät wurde gerade angehalten")
            return
        ziel = auftrag_ziel(auftrag)
        if ziel is not None:
            if not self._empfang.darf("dieses", ziel):
                self._schleife_erkannt(ziel)
                return
            self._empfang.vergeben("dieses", ziel)
            self._ergebnis_ok = True
            self._auftrag_ausfuehren(auftrag, vorrang=vorrang, kann_antworten=kann_antworten)
            if self._ergebnis_ok:
                self._empfang.erledigt("dieses", ziel)
            return
        self._auftrag_ausfuehren(auftrag, vorrang=vorrang, kann_antworten=kann_antworten)

    def _klein_arbeiten(self) -> None:
        if self._vorwaermen is not None:
            vorher = self.phase
            self.phase, self.meldung = "vorwaermt", ""
            try:
                n = self._vorwaermen()
            except Exception as exc:
                n = None
                self._log(f"FEHLER rechenarbeit vorwaermen: {type(exc).__name__}: {str(exc)[:100]}")
            if n is not None:
                self._log(f"OK rechenarbeit vorgewaermt: {n} Nachschauen privat auf diesem PC gemerkt")
            self.phase = vorher
        if self._pruefstand is not None and self._mitglied_frage is None:
            vorher = self.phase
            self.phase, self.meldung = "prueft_selbst", ""
            try:
                b = self._pruefstand()
            except Exception as exc:
                b = None
                self._log(f"FEHLER rechenarbeit pruefstand: {type(exc).__name__}: {str(exc)[:100]}")
            if b is not None:
                self._log(f"OK rechenarbeit pruefstand: {b.get('richtig')} von {b.get('gesamt')} Prüffragen richtig")
            self.phase = vorher

    def _schleife_erkannt(self, ziel: tuple) -> None:
        self.phase, self.auftrag_n = "wartet", 0
        self._schlafen(5)

    def _auftrag_ausfuehren(self, auftrag: dict | None, *, vorrang: bool, kann_antworten: bool) -> None:
        if auftrag is not None and auftrag.get("art") == vermittlung_basis.ART:
            self._antwort_geben(auftrag)
            return
        if kann_antworten and hintergrund(auftrag):
            self._wache_starten()
            try:
                self._auftrag_ausfuehren_hintergrund(auftrag, vorrang=vorrang, kann_antworten=kann_antworten)
            finally:
                self._wache_ende()
            return
        self._auftrag_ausfuehren_hintergrund(auftrag, vorrang=vorrang, kann_antworten=kann_antworten)

    def _auftrag_ausfuehren_hintergrund(self, auftrag: dict | None, *, vorrang: bool, kann_antworten: bool) -> None:
        if auftrag is not None and auftrag.get("art") == verteiler.PRUEF_ART:
            self._pruefen(auftrag)
            return
        if auftrag is not None and auftrag.get("art") in (verteiler.VERTIEF_ART, verteiler.VERTIEF_PRUEF_ART):
            self._vertiefen_auftrag(auftrag)
            return
        if auftrag is not None and auftrag.get("art") in (scheiben.HALTEN_ART, scheiben.LIEFERN_ART):
            if self._halter is not None:
                self.phase, self.meldung = "speicher", ""
                (self._halter.halten if auftrag["art"] == scheiben.HALTEN_ART else self._halter.liefern)(auftrag)
            return
        if auftrag is None and vorrang:
            self.phase, self.meldung = ("bereit" if kann_antworten and bool(self._urteil_bereit()) else "wartet"), ""
            self._schlafen(getattr(self._community, "takt_s", 0) or WARTEN_FRAGEN_S)
            return
        if auftrag is None and self._themen is not None and self._themen.faellig():
            self.phase, self.meldung = "themen", ""
            wache = kann_antworten and self._wache_starten()
            try:
                self._themen.sammeln(weiter=lambda: self._darf() and not self.frage_wartet())
            except Exception as exc:
                self._log(f"FEHLER themen: {type(exc).__name__}")
            finally:
                if wache:
                    self._wache_ende()
            return
        if auftrag is None:
            self._server_stoppen()
            if time.monotonic() - self._stand_geholt >= STAND_ABSTAND_S:
                self._stand_geholt = time.monotonic()
                try:
                    self.server_stand = self._community.rechenstand()
                except app_core.AppError:
                    pass
            wache = kann_antworten and (self._vorwaermen is not None or self._pruefstand is not None) and self._wache_starten()
            try:
                self._klein_arbeiten()
            finally:
                if wache:
                    self._wache_ende()
            if self._mitglied_frage is not None:
                return
            takt = getattr(self._community, "takt_s", 0) or WARTEN_FRAGEN_S
            if kann_antworten and getattr(self._community, "gewartet", False):
                takt = NACH_WARTEN_S
            if kann_antworten and bool(self._urteil_bereit()):
                self.phase, self.meldung = "bereit", ""
                self._schlafen(takt)
                return
            self.phase, self.meldung = "wartet", ""
            self._schlafen(takt if kann_antworten else WARTEN_LEER_S)
            return
        abschnitte = [a for a in auftrag.get("abschnitte", []) if isinstance(a, dict) and a.get("schluessel") and isinstance(a.get("text"), str)]
        modell = auftrag.get("modell") or {}
        if str(modell.get("kennung")) != verteiler.MODELL_KENNUNG or str(modell.get("sha256")) != ki_laufzeit.EMBEDDING.sha256:
            raise app_core.AppError("RECHEN_MODELL", "der Server verlangt ein anderes Modell als dieses Programm kennt; bitte das Programm aktualisieren")
        if not abschnitte:
            raise app_core.AppError("RECHEN_LEER", "der Auftrag enthält keine Abschnitte")
        self._modell_bereit()
        self.phase, self.auftrag_n = "rechnet", len(abschnitte)
        nachkomma = int(auftrag.get("nachkomma", verteiler.NACHKOMMA))
        t0 = time.time()
        ergebnisse: list[dict] = []
        for i in range(0, len(abschnitte), BATCH):
            if self._mitglied_frage is not None:
                raise app_core.AppError("VORRANG", "eine Frage eines Mitglieds hat Vorrang; der Auftrag geht an den Server zurück")
            self._vorrang_abwarten()
            if not self._darf():
                self._log("OK rechenarbeit abgebrochen (Stopp/Pause); der Server vergibt den Auftrag neu")
                self._ergebnis_ok = False
                return
            teil = abschnitte[i:i + BATCH]
            for a, v in zip(teil, self.server.vektoren([a["text"] for a in teil])):
                ergebnisse.append({"schluessel": str(a["schluessel"]), "vektor": [round(x, nachkomma) for x in v]})
        dauer = time.time() - t0
        r = self._community.ergebnis_senden(str(auftrag["auftrag"]), verteiler.MODELL_KENNUNG, ergebnisse, verteiler.pruefsumme(ergebnisse))
        n, g, c = int(r.get("angenommen", 0)), int(r.get("geprueft", 0)), int(r.get("credits", 0))
        self._zaehlen(abschnitte=n, geprueft=g, credits_=c)
        if c:
            self._kontobuch.rechenarbeit(c, abschnitte=n, geraet=self._geraet_name)
        self.server_stand = {"geraet": r.get("geraet")} if r.get("geraet") else self.server_stand
        self._log(f"OK rechenarbeit auftrag {auftrag['auftrag']}: {n} Abschnitte in {dauer:.1f} s, {g} geprüft, +{c} Credits")
        self.auftrag_n = 0

    def _ki_freigeben(self) -> None:
        if self._ki_von_uns and self._ki_stoppen is not None:
            try:
                self._ki_stoppen()
                self._log("OK rechenarbeit modell entladen")
            except Exception as exc:
                self._log(f"FEHLER rechenarbeit entladen: {type(exc).__name__}")
        self._ki_von_uns = False

    def _antwort_geben(self, auftrag: dict) -> None:
        self._karte.beginnen()
        self._frage_erledigt = False
        vorher = self.phase
        self.antwort_seit = time.monotonic()
        try:
            self._antwort_geben_innen(auftrag)
        except BaseException as exc:
            if not self._frage_erledigt:
                self._frage_erledigt = True
                self._frage_zurueck(auftrag, f"auf diesem Gerät ging es nicht weiter ({getattr(exc, 'code', '') or type(exc).__name__})")
            raise
        finally:
            self.antwort_seit = 0.0
            if self.phase in ("antwortet", "laden"):
                self.phase = vorher
            self._karte.ende()

    def _antwort_geben_innen(self, auftrag: dict) -> None:
        fuer = str(auftrag.get("fuer", "") or "einem Mitglied")[:60]
        self.phase, self.meldung, self.auftrag_n = "antwortet", fuer, 1
        t0 = time.time()
        laden_s = 0.0
        if not self._urteil_bereit():
            if self._ki_starten is None:
                raise app_core.AppError("ANTWORT_KI", "KIplatz läuft nicht")
            self.phase = "laden"
            self._ki_starten()
            self._ki_von_uns = True
            self.phase = "antwortet"
            laden_s = time.time() - t0
        nachrichten = [n for n in auftrag.get("nachrichten", []) if isinstance(n, dict)]
        auszuege = [a for a in auftrag.get("auszuege", []) if isinstance(a, dict)]
        extra = {"frisch": True} if auftrag.get("frisch") else {}
        kennung = str(auftrag["auftrag"])
        if isinstance(auftrag.get("skill"), dict):
            extra["skill"] = auftrag["skill"]
        zuhause = auftrag.get("zuhause") if isinstance(auftrag.get("zuhause"), dict) else None
        melder = Melder(lambda t: self._community.antwort_teil(kennung, t),
                        (lambda t: self._community.antwort_schritt(kennung, t)) if hasattr(self._community, "antwort_schritt") else None)
        try:
            import inspect
            parameter = inspect.signature(self._antworten).parameters
            if "teil_melden" in parameter:
                extra["teil_melden"] = melder.teil
            if zuhause is not None and "zuhause" in parameter:
                extra["zuhause"] = zuhause
            if isinstance(auftrag.get("fenster"), dict) and "fenster" in parameter:
                extra["fenster"] = auftrag["fenster"]
            if "schritt_melden" in parameter and hasattr(self._community, "antwort_schritt"):
                extra["schritt_melden"] = melder.schritt
            if isinstance(auftrag.get("fachgebiete"), list) and "fachgebiete" in parameter:
                extra["fachgebiete"] = [f for f in auftrag["fachgebiete"] if isinstance(f, str)]
        except (TypeError, ValueError):
            pass
        fehler_vorher = getattr(self._community, "teil_fehler", 0)
        ki_laufzeit.messung_beginnen()
        try:
            text, lieferschein = self._antworten(nachrichten, auszuege, fuer, **extra)
        except app_core.AppError as exc:
            if hasattr(self._community, "antwort_verzicht"):
                self._frage_erledigt = True
                try:
                    wie = self._community.antwort_verzicht(kennung, exc.detail)
                    self._log(f"OK rechenarbeit antwort {kennung} abgegeben ({wie or 'ohne Rückmeldung'}): {exc.code}")
                except Exception as exc2:
                    self._log(f"FEHLER frage zurück: {type(exc2).__name__}")
            raise
        finally:
            aufrufe = ki_laufzeit.messung_ende()
            t_ende = time.monotonic()
            melder.ende()
            ende_s = time.monotonic() - t_ende
        ablauf = melder.ablauf_zeile()
        dauer = time.time() - t0
        self._tempo_merken(lieferschein)
        self._modell_name = str(lieferschein.get("modell") or self._modell_name)[:60]
        try:
            messung = messwerte.messen()
        except Exception:
            messung = {}
        zeiten = {"laden_s": round(laden_s, 2), "ende_s": round(ende_s, 2), "schritte": [[round(z, 2), schritt_kurz(w)] for z, w in melder.ablauf][:30], "aufrufe": aufrufe}
        if isinstance(lieferschein, dict) and (zs := zeit_je_schritt(melder.ablauf, dauer)):
            lieferschein["quellen"] = (str(lieferschein.get("quellen") or "") + " " + zs).strip()
        try:
            mit_ablauf = "ablauf" in inspect.signature(self._community.antwort_senden).parameters
        except (TypeError, ValueError):
            mit_ablauf = False
        for versuch in (1, 2):
            try:
                r = self._community.antwort_senden(str(auftrag["auftrag"]), text, lieferschein, dauer, messung, **({"ablauf": zeiten} if mit_ablauf else {}))
                break
            except app_core.AppError as exc:
                if versuch == 2:
                    raise
                self._log(f"INFO rechenarbeit antwort {auftrag['auftrag']} noch einmal senden: {exc.code}")
                self._halt.wait(1.0)
        self._frage_erledigt = True
        c = int(r.get("credits", 0))
        self._antwort_zaehlen(fuer, c)
        if c:
            self._kontobuch.rechenarbeit(c, abschnitte=0, geraet=self._geraet_name, was="Frage eines Mitglieds beantwortet")
        nicht_angekommen = getattr(self._community, "teil_fehler", 0) - fehler_vorher
        self._log(f"OK rechenarbeit antwort {auftrag['auftrag']} für {fuer} in {dauer:.1f} s, +{c} Credits"
                  + ("" if r.get("verwendet", True) else " (ein anderer Rechner war schneller; die Arbeit zählt trotzdem)")
                  + (f"; {nicht_angekommen} Teilstücke oder Schritte kamen nicht zum Server" if nicht_angekommen else "")
                  + (f"; Ablauf: {ablauf}" if melder.ablauf else "")
                  + (f"; Modell: {aufrufe_zeile(aufrufe)}" if aufrufe else ""))
        self.auftrag_n = 0

    def _ki_sicherstellen(self) -> None:
        if self._urteil_bereit():
            return
        if self._ki_starten is None:
            raise app_core.AppError("ANTWORT_KI", "KIplatz läuft nicht")
        self._ki_starten()
        self._ki_von_uns = True

    def _vertiefen_auftrag(self, auftrag: dict) -> None:
        art = str(auftrag.get("art"))
        q = auftrag.get("quelle") or {}
        titel = str(q.get("titel") or "einer Quelle")[:80]
        text = str(auftrag.get("text") or "")
        if not text.strip():
            raise app_core.AppError("VERTIEF_LEER", "der Auftrag enthält keinen Text")
        self.phase, self.meldung, self.auftrag_n = ("vertieft" if art == verteiler.VERTIEF_ART else "vertieft_prueft"), titel, 1
        t0 = time.time()
        vorher = self.phase
        self._ki_sicherstellen()
        self.phase = vorher
        if art == verteiler.VERTIEF_ART:
            try:
                v = self._vertiefen(titel, text, int(auftrag.get("fragen_min", verteiler.VERTIEF_FRAGEN_MIN)), int(auftrag.get("fragen_max", verteiler.VERTIEF_FRAGEN_MAX)))
            except app_core.AppError as exc:
                if exc.code != "VERTIEF_FORM":
                    raise
                self._ergebnis_ok = False
                self._community.vertiefung_verzicht(str(auftrag["auftrag"]), exc.detail)
                self._log(f"OK rechenarbeit vertiefen verzichtet {auftrag['auftrag']}: {exc.detail[:100]}")
                self.auftrag_n = 0
                return
            r = self._community.vertiefung_senden(str(auftrag["auftrag"]), str(v.get("zusammenfassung", "")), list(v.get("fragen") or []))
            c = int(r.get("credits", 0))
            self._vertieft_zaehlen(vertieft=1, credits_=c)
            self._log(f"OK rechenarbeit vertieft {auftrag['auftrag']}: {r.get('fragen', 0)} Fragen in {time.time() - t0:.1f} s, +{c} Credits")
        else:
            try:
                ergebnis = self._vertiefen_pruefen(text, auftrag.get("vertiefung") or {})
                urteil, grund, raus = ergebnis[0], ergebnis[1], (list(ergebnis[2]) if len(ergebnis) > 2 else [])
            except app_core.AppError as exc:
                urteil, grund, raus = "unklar", exc.detail, []
            urteil = urteil if urteil in ("ok", "falsch") else "unklar"
            self._ergebnis_ok = urteil != "unklar"
            r = self._community.vertiefung_urteil_senden(str(auftrag["auftrag"]), urteil, grund, raus=raus, fassung=PRUEF_FASSUNG)
            c = int(r.get("credits", 0))
            self._vertieft_zaehlen(geprueft=1 if urteil != "unklar" else 0, credits_=c)
            self._log(f"OK rechenarbeit vertiefpruefung {auftrag['auftrag']}: {urteil}{' ohne ' + str(raus) if raus else ''} ({grund[:60]}) in {time.time() - t0:.1f} s, +{c} Credits")
        if c:
            self._kontobuch.rechenarbeit(c, abschnitte=0, geraet=self._geraet_name,
                                         was="Abschnitt vertieft: Zusammenfassung und Fragen geschrieben" if art == verteiler.VERTIEF_ART else "Vertiefung eines anderen Geräts geprüft")
        self.server_stand = {"geraet": r.get("geraet")} if r.get("geraet") else self.server_stand
        self.auftrag_n = 0

    def _leistung(self) -> dict:
        return {"warm": bool(self._urteil_bereit()), "tempo": self._tempo(), "modell": self._modell(), "kopie": bool(self._kopie())}

    def _tempo(self) -> float:
        try:
            return float(self._stand_laden().get("tempo", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _modell(self) -> str:
        try:
            jetzt = str(self._modell_fn() or "") if self._modell_fn else ""
        except Exception:
            jetzt = ""
        return (jetzt or self._modell_name)[:60]

    def _tempo_merken(self, lieferschein: dict) -> None:
        try:
            stuecke, s = float(lieferschein.get("wortstuecke") or 0), float(lieferschein.get("dauer_s") or 0)
        except (TypeError, ValueError):
            return
        if stuecke < 5 or s <= 0:
            return
        d = self._stand_laden()
        alt = float(d.get("tempo", 0.0) or 0.0)
        d["tempo"] = round(stuecke / s if not alt else 0.7 * alt + 0.3 * stuecke / s, 2)
        self._stand_schreiben(d)

    def _pruefen(self, auftrag: dict) -> None:
        q = auftrag.get("quelle") or {}
        text = str(q.get("text", ""))
        self.phase, self.auftrag_n = "prueft", 1
        t0 = time.time()
        try:
            urteil, grund = self._urteil(f"{q.get('titel', '')}\n{text}")
        except app_core.AppError as exc:
            urteil, grund = "unklar", exc.detail
        sicher = urteil == "verstoss" and not hausordnung.pruefen(f"{q.get('titel', '')}\n{text}").ok
        urteil = urteil if urteil in ("ok", "verstoss") else "unklar"
        self._ergebnis_ok = urteil != "unklar"
        r = self._community.urteil_senden(str(auftrag["auftrag"]), urteil, grund, str(q.get("titel", ""))[:160], sicher=sicher)
        c = int(r.get("credits", 0))
        if c:
            self._kontobuch.rechenarbeit(c, abschnitte=0, geraet=self._geraet_name, was="Beitrag zum Wissen auf die Platzordnung geprüft")
            d = self._stand_laden()
            d["credits"] += c
            d["gesamt_credits"] += c
            d["auftraege"] += 1
            d["letzter"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._stand_schreiben(d)
        self.geprueft_n += 1
        self._log(f"OK rechenarbeit pruefauftrag {auftrag['auftrag']}: {urteil} ({grund[:60]}) in {time.time() - t0:.1f} s, +{c} Credits")
        self.auftrag_n = 0


_ZITAT = re.compile(r"[„\"“”‚‘'][^„\"“”‚‘']*[“”\"‘']?")


def schritt_kurz(text: str) -> str:
    return " ".join(_ZITAT.sub(" ", str(text or "")).replace("…", " ").split()[:4])


ZEIT_SATZ = "Zeit je Schritt: {0}."
_SCHRITT_ENDE = {"nach", "und", "gegen", "die", "der", "für", "mit", "von"}


def zeit_je_schritt(ablauf: list[tuple[float, str]], gesamt_s: float, *, ab_s: float = 1.0) -> str:
    gezeigt = [f"{n} {round(s):.0f} s" for n, s in schritt_teile(ablauf, gesamt_s) if s >= ab_s]
    return ZEIT_SATZ.format(", ".join(gezeigt)) if gezeigt else ""


def schritt_teile(ablauf: list[tuple[float, str]], gesamt_s: float) -> list[list]:
    teile: list[list] = []
    for i, (t, text) in enumerate(ablauf):
        ende = ablauf[i + 1][0] if i + 1 < len(ablauf) else gesamt_s
        vorn = re.split(r"[„\"“‚']", str(text or ""), maxsplit=1)[0]
        worte = vorn.replace("…", " ").replace("...", " ").split()[:7]
        while worte and worte[-1].strip(",").lower() in _SCHRITT_ENDE:
            worte.pop()
        name = " ".join(worte).strip(" ,")
        if not name:
            continue
        if teile and teile[-1][0] == name:
            teile[-1][1] += max(0.0, ende - t)
        else:
            teile.append([name, max(0.0, ende - t)])
    return teile


def aufrufe_zeile(aufrufe: list[dict]) -> str:
    teile = []
    for a in aufrufe:
        z = f"{a.get('art', '?')} {a.get('s', 0):.1f} s"
        if "ein" in a or "aus" in a:
            z += f" (ein {int(a.get('ein', 0))}/cache {int(a.get('cache', 0))} in {a.get('ein_ms', 0):.0f} ms, aus {int(a.get('aus', 0))} in {a.get('aus_ms', 0):.0f} ms)"
        elif "n" in a:
            z += f" ({a['n']})"
        teile.append(z)
    return " | ".join(teile)


class Melder:

    ENDE_S = 2.0

    def __init__(self, teil_senden, schritt_senden=None) -> None:
        self._teil_senden, self._schritt_senden = teil_senden, schritt_senden
        self._cond = threading.Condition()
        self._teil: str | None = None
        self._schritt: str | None = None
        self._aus = False
        self._t0 = time.monotonic()
        self.ablauf: list[tuple[float, str]] = []
        self._faden = threading.Thread(target=self._lauf, name="antwort-melder", daemon=True)
        self._faden.start()

    def teil(self, text: str) -> None:
        with self._cond:
            self._teil = text
            self._cond.notify()

    def schritt(self, text: str) -> None:
        self.ablauf.append((time.monotonic() - self._t0, " ".join(str(text).split())[:48]))
        with self._cond:
            self._schritt = text
            self._cond.notify()

    def _lauf(self) -> None:
        while True:
            with self._cond:
                while self._teil is None and self._schritt is None and not self._aus:
                    self._cond.wait()
                teil, schritt, self._teil, self._schritt = self._teil, self._schritt, None, None
                if teil is None and schritt is None and self._aus:
                    return
            for senden, wert in ((self._schritt_senden, schritt), (self._teil_senden, teil)):
                if senden is not None and wert is not None:
                    try:
                        senden(wert)
                    except Exception:
                        pass

    def ablauf_zeile(self) -> str:
        return " | ".join(f"{s:.1f} s {w}" for s, w in self.ablauf + [(time.monotonic() - self._t0, "fertig")])

    def ende(self) -> None:
        with self._cond:
            self._aus = True
            self._cond.notify()
        self._faden.join(self.ENDE_S)


EMPFANG_HOECHSTENS = 5
EMPFANG_FENSTER_S = 600.0
EMPFANG_PAUSE_S = 1800.0


def auftrag_ziel(auftrag: dict | None) -> tuple | None:
    if not isinstance(auftrag, dict) or auftrag.get("art") == vermittlung_basis.ART:
        return None
    art = auftrag.get("art")
    if art == verteiler.PRUEF_ART:
        return ("pruefen", str((auftrag.get("quelle") or {}).get("kennung", "")))
    if art in (verteiler.VERTIEF_ART, verteiler.VERTIEF_PRUEF_ART):
        return (str(art), str(auftrag.get("schluessel", "")))
    if art in (scheiben.HALTEN_ART, scheiben.LIEFERN_ART):
        return (str(art), str(auftrag.get("scheibe", "")))
    if auftrag.get("abschnitte"):
        return ("abschnitte", tuple(sorted(str(a.get("schluessel", "")) for a in auftrag["abschnitte"] if isinstance(a, dict))))
    return None


PRUEF_ZUSATZ = (
    "Prüfauftrag der Community. "
    "Unten steht ein Text, den ein Mitglied in den gemeinsamen Wissensspeicher legen will. Deine einzige Frage: TUT der Text selbst eines dieser fünf Dinge? "
    "(1) Er verherrlicht den Nationalsozialismus oder leugnet oder verharmlost den Holocaust. (2) Er beschreibt Sexuelles mit Kindern oder ist selbst Pornographie "
    "(ausführliche Beschreibung sexueller Handlungen). (3) Er ruft zu Gewalt gegen Menschen auf. (4) Er leitet zum Bau von Waffen oder Sprengstoff an. "
    "(5) Er beschimpft Menschen wegen Herkunft, Religion, Geschlecht oder Behinderung. "
    "Alles andere ist OK: Nachrichten und Berichte über solche Themen, Gerichtsurteile, Geschichte, Gedenken, Aufklärung, Meinung, Ärger, Werbung, Firmenseiten, Anleitungen zu Software, "
    "schlechte oder langweilige Texte. Ein Bericht, der sagt, dass jemand wegen Wiederbetätigung verurteilt wurde, ist OK. Im Zweifel OK. "
    "Antworte mit genau einer Zeile und sonst nichts: OK oder VERSTOSS: Nummer und die Textstelle, die es tut, in höchstens 12 Wörtern."
)


VERTIEF_ZUSATZ = (
    "Vertiefungsauftrag der Community. "
    "Unten steht ein Abschnitt aus einer Quelle des gemeinsamen Wissensspeichers. Schreibe dazu (1) eine Zusammenfassung in höchstens zwei Sätzen "
    "und (2) {min} bis {max} Fragen, die jemand stellen könnte und die genau dieser Abschnitt beantwortet, jede mit einer Antwort in ein bis drei Sätzen. "
    "Alles nur aus dem Abschnitt, nichts dazuerfinden, keine Meinung, keine Einleitung, kein Schluss. "
    "Keine Erklärung, Deutung, Folge oder Bewertung, die der Abschnitt nicht selbst nennt, und keine Namen, Orte oder Zahlen, die nicht darin stehen. "
    "Ohne Sternchen und ohne Aufzählungszeichen. Deutsch. Genau dieses Format, jede Angabe in einer eigenen Zeile:"
    + chr(10) + "ZUSAMMENFASSUNG: …" + chr(10) + "FRAGE: …" + chr(10) + "ANTWORT: …" + chr(10) + "FRAGE: …" + chr(10) + "ANTWORT: …"
)
VERTIEF_PRUEF_ZUSATZ = (
    "Prüfauftrag der Community. "
    "Unten steht ein Abschnitt und danach, was ein anderer Rechner dazu geschrieben hat: eine Zusammenfassung und Fragen mit Antworten. "
    "Prüfe nur eines: Steht das, was die Zusammenfassung und jede Antwort behaupten, so im Abschnitt, ohne Erfindung und ohne Widerspruch? "
    "Kleinere Kürzungen und Umformulierungen sind in Ordnung. Du gibst EIN Urteil für den ganzen Text, keine Liste und keine Nummern je Zeile. "
    "Antworte mit genau einer Zeile und sonst nichts: OK, wenn alles stimmt; oder FALSCH: Nummer der Frage (0 für die Zusammenfassung) und was nicht "
    "stimmt, in höchstens 15 Wörtern; oder UNKLAR, wenn du es nicht beurteilen kannst."
)
VERTIEF_EINZEL_ZUSATZ = (
    "Prüfauftrag der Community. Unten steht ein Abschnitt und danach eine Aussage, die ein anderer Rechner dazu geschrieben hat. "
    "Kürzen und anders formulieren ist erlaubt. Antworte nein, wenn die Aussage etwas behauptet, das nicht im Abschnitt steht (eine Erklärung, Deutung, "
    "Folge, einen Namen, einen Ort, eine Zahl) oder ihm widerspricht, oder wenn sie mitten im Satz aufhört. Sonst ja. Antworte nur mit ja oder nein."
)
PRUEF_FASSUNG = verteiler.PRUEF_FASSUNG
VERTIEF_MAX_TOKENS = 520
VERTIEF_PRUEF_MAX_TOKENS = 60


def vertiefung_aus_antwort(antwort: str) -> dict:
    import re
    z = ""
    fragen: list[dict] = []
    frage = ""
    letzte = None
    vorspann: list[str] = []
    for zeile in (antwort or "").splitlines():
        s = zeile.strip().strip("*").strip()
        if not s:
            continue
        m = re.match(r"^(?:\d+[.)]\s*)?\**\s*(zusammenfassung|frage|antwort)\s*(?:\d+)?\s*\**\s*[:：]\s*(.*)$", s, re.I)
        if not m:
            if letzte == "antwort" and fragen:
                fragen[-1]["antwort"] += " " + s
            elif letzte == "zusammenfassung":
                z += " " + s
            elif letzte == "frage":
                frage += " " + s
            elif letzte is None and not fragen:
                vorspann.append(s)
            continue
        art, inhalt = m.group(1).lower(), m.group(2).strip().lstrip("*").strip()
        if art == "zusammenfassung":
            z, letzte = inhalt, "zusammenfassung"
        elif art == "frage":
            frage, letzte = inhalt, "frage"
        elif frage:
            fragen.append({"frage": frage, "antwort": inhalt})
            frage, letzte = "", "antwort"
        else:
            letzte = None
    if not z.strip() and vorspann:
        kandidat = max(vorspann, key=len)
        if len(kandidat) >= 20 and not kandidat.endswith((":", "!")):
            z = kandidat
    return {"zusammenfassung": " ".join(z.split()), "fragen": [{"frage": " ".join(f["frage"].split()), "antwort": " ".join(f["antwort"].split())} for f in fragen]}


def ja_nein(antwort: str) -> bool | None:
    w = re.sub(r"[^a-zäöü]", "", (str(antwort or "").strip().split() or [""])[0].lower())
    return True if w == "ja" else (False if w == "nein" else None)


def vertief_urteil_aus_antwort(antwort: str) -> tuple[str, str]:
    zeilen = [re.sub(r"^[\s*_#>-]*(?:\d+\s*[:.)]\s*)?[*_]*", "", z).strip() for z in (antwort or "").splitlines() if z.strip()]
    if len(zeilen) > 1:
        koepfe = [z[:10].upper() for z in zeilen]
        falsch = next((z for z, k in zip(zeilen, koepfe) if k.startswith("FALSCH")), None)
        if falsch is not None:
            return "falsch", (falsch.split(":", 1)[1].strip(" *") if ":" in falsch else "stimmt nicht mit dem Abschnitt überein")[:200]
        if all(k.startswith("OK") for k in koepfe):
            return "ok", ""
        return "unklar", " ".join(zeilen)[:80]
    a = " ".join((antwort or "").split()).strip(" .„“\"'*")
    kopf = a[:10].upper()
    if kopf.startswith("OK"):
        return "ok", ""
    if kopf.startswith("FALSCH"):
        return "falsch", a.split(":", 1)[1].strip()[:200] if ":" in a else "stimmt nicht mit dem Abschnitt überein"
    return "unklar", a[:80]


def urteil_aus_antwort(antwort: str) -> tuple[str, str]:
    a = " ".join((antwort or "").split()).strip(" .„“\"'*")
    kopf = a[:12].upper()
    if kopf.startswith("OK"):
        return "ok", ""
    if kopf.startswith("VERSTOSS") or kopf.startswith("VERSTOß"):
        return "verstoss", a.split(":", 1)[1].strip() if ":" in a else "gegen die Platzordnung"
    return "unklar", a[:80]


__all__ = ["Rechenarbeit", "LEERLAUF_S", "WARTEN_LEER_S", "BATCH", "TEXTE", "PRUEF_ZUSATZ", "urteil_aus_antwort",
           "VERTIEF_ZUSATZ", "VERTIEF_PRUEF_ZUSATZ", "vertiefung_aus_antwort", "vertief_urteil_aus_antwort"]
