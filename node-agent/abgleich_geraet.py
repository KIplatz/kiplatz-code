# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

import abgleich_krypto as ak
import app_core
import geheim
import gespraeche
import sicher_schreiben

DIRNAME = "abgleich"
PROJEKTE_ID = "0" * 32
DATEI = "zustand.json"


def _ms(iso: str) -> int:
    try:
        return int(datetime.strptime(str(iso), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _iso(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def in_gemeinsam(g: gespraeche.Gespraech) -> dict:
    nachrichten = []
    for n in g.nachrichten:
        m = {k: v for k, v in n.items() if k != "zeit"}
        m["zeit"] = _ms(n.get("zeit", ""))
        nachrichten.append(m)
    return {"titel": g.titel, "angeheftet": g.angeheftet, "projekt": g.projekt, "farbe": g.farbe, "geaendert": _ms(g.geaendert), "nachrichten": nachrichten}


def fingerabdruck(g: gespraeche.Gespraech) -> str:
    d = in_gemeinsam(g)
    d.pop("geaendert", None)
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def aus_gemeinsam(d: dict, g: gespraeche.Gespraech) -> gespraeche.Gespraech:
    g.titel = str(d.get("titel") or "Gespräch")[:80]
    g.angeheftet = bool(d.get("angeheftet"))
    g.projekt = str(d.get("projekt") or "")[:gespraeche.MAX_PROJEKT]
    g.farbe = str(d.get("farbe") or "") if str(d.get("farbe") or "") in gespraeche.FARBEN else ""
    neu = []
    for n in (d.get("nachrichten") or [])[:gespraeche.MAX_NACHRICHTEN]:
        if not isinstance(n, dict) or n.get("rolle") not in ("user", "assistant"):
            continue
        m = {k: v for k, v in n.items() if k != "zeit"}
        m["text"] = str(n.get("text", ""))[:gespraeche.MAX_NACHRICHT]
        m["zeit"] = _iso(n.get("zeit"))
        neu.append(m)
    g.nachrichten = neu
    g.geaendert = _iso(d.get("geaendert"))
    return g


class AbgleichFehler(app_core.AppError):
    pass


class AbgleichGeraet:
    def __init__(self, base_dir: Path, community, ablage: gespraeche.Gespraechsablage) -> None:
        self.dir = Path(base_dir) / DIRNAME
        self.c = community
        self.ablage = ablage
        self._sperre = threading.Lock()
        self.zuletzt = ""
        self.zuletzt_fehler = ""


    def _lesen(self) -> dict:
        d = sicher_schreiben.json_laden(self.dir / DATEI, {}, art=dict)
        d.setdefault("an", False)
        d.setdefault("zuordnung", {})
        d.setdefault("bekannt", {})
        d.setdefault("stand", {})
        return d

    def _schreiben(self, d: dict) -> None:
        app_core.ensure_plain_directory(self.dir)
        sicher_schreiben.json_datei(self.dir / DATEI, d)

    @staticmethod
    def _geheim_zu(roh: bytes) -> str:
        return geheim.schuetzen(base64.b64encode(roh).decode("ascii"))

    @staticmethod
    def _geheim_auf(wert: str) -> bytes:
        return base64.b64decode(geheim.lesen(str(wert)))

    def _server(self, tat: str, **felder) -> dict:
        return self.c._anfrage("/abgleich", {"tat": tat, **felder}, als_geraet=True)

    def _kennung(self) -> str:
        g = self.c.geraet() or {}
        return str(g.get("kennung", ""))

    def _privat(self, d: dict):
        if not d.get("privat"):
            p = ak.neues_geraet()
            d["privat"] = self._geheim_zu(ak.privat_speichern(p))
            return p
        return ak.privat_laden(self._geheim_auf(d["privat"]))


    def stand(self) -> dict:
        d = self._lesen()
        if not d["an"]:
            return {"an": False}
        s = self._server("stand")
        return {"an": True, "eingerichtet": s["eingerichtet"], "zugelassen": bool(s.get("mein_fach")), "wartet": bool(s.get("meine_anfrage")) and not s.get("mein_fach"),
                "pruefzahl": ak.pruefzahl(ak.oeffentlich(self._privat(d))) if d.get("privat") else "",
                "anfragen": [{"kennung": q["kennung"], "name": q["name"], "pruefzahl": ak.pruefzahl(q["oeffentlich"])} for q in s["anfragen"]],
                "wechsel_noetig": bool(s.get("wechsel_noetig")) and bool(s.get("mein_fach")), "belegt": s["belegt"], "grenze": s["grenze"],
                "gespraeche": len([b for b in s["bloecke"] if b != PROJEKTE_ID]), "zuletzt": self.zuletzt, "fehler": self.zuletzt_fehler}


    def einschalten(self) -> dict:
        with self._sperre:
            d = self._lesen()
            s = self._server("stand")
            p = self._privat(d)
            oeff, kennung = ak.oeffentlich(p), self._kennung()
            d["an"] = True
            if not s["eingerichtet"]:
                k, r = ak.neuer_kontoschluessel(), ak.neuer_wiederherstellungsschluessel()
                self._server("einrichten", fach=ak.fach_packen(k, oeff), oeffentlich=oeff, siegel=ak.siegel(k, kennung, oeff), wiederherstellung=ak.wiederherstellung_packen(k, r))
                d.update(k=self._geheim_zu(k), version=1)
                self._schreiben(d)
                return {"wiederherstellung": r}
            if s.get("mein_fach"):
                self._schreiben(d)
                return {"schon": True}
            self._server("anfrage", oeffentlich=oeff)
            self._schreiben(d)
            return {"pruefzahl": ak.pruefzahl(oeff)}

    def zulassen(self, kennung: str) -> dict:
        with self._sperre:
            d = self._lesen()
            k = self._kontoschluessel(d)
            s = self._server("stand")
            q = next((q for q in s["anfragen"] if q["kennung"] == kennung), None)
            if q is None:
                raise AbgleichFehler("ABGLEICH_ANFRAGE", "diese Anfrage gibt es nicht mehr; am anderen Gerät noch einmal einschalten")
            return self._server("zulassen", kennung=kennung, fach=ak.fach_packen(k, q["oeffentlich"]), siegel=ak.siegel(k, kennung, q["oeffentlich"]), version=s["version"])

    def ablehnen(self, kennung: str) -> dict:
        return self._server("ablehnen", kennung=str(kennung))

    def wiederherstellen(self, r_text: str) -> dict:
        with self._sperre:
            d = self._lesen()
            w = self._server("wiederherstellung")
            try:
                k = ak.wiederherstellung_oeffnen(w["wiederherstellung"], r_text)
            except ak.KryptoFehler as exc:
                raise AbgleichFehler("ABGLEICH_WIEDER", str(exc)) from None
            p = self._privat(d)
            oeff, kennung = ak.oeffentlich(p), self._kennung()
            self._server("selbst", fach=ak.fach_packen(k, oeff), oeffentlich=oeff, siegel=ak.siegel(k, kennung, oeff), version=w["version"])
            d.update(an=True, k=self._geheim_zu(k), version=w["version"])
            self._schreiben(d)
            return {"ok": True}

    def schluessel_wechseln(self) -> dict:
        with self._sperre:
            d = self._lesen()
            k_alt = self._kontoschluessel(d)
            s = self._server("stand")
            erlaubt = set(s.get("geraete") or [])
            k_neu, r = ak.neuer_kontoschluessel(), ak.neuer_wiederherstellungsschluessel()
            faecher = {}
            for kennung, e in (s.get("schluessel") or {}).items():
                if kennung in erlaubt and ak.siegel_pruefen(k_alt, kennung, e.get("oeffentlich") or {}, e.get("siegel", "")):
                    faecher[kennung] = {"fach": ak.fach_packen(k_neu, e["oeffentlich"]), "siegel": ak.siegel(k_neu, kennung, e["oeffentlich"])}
            if self._kennung() not in faecher:
                raise AbgleichFehler("ABGLEICH_SIEGEL", "der eigene Schlüssel am Server passt nicht; bitte den Abgleich aus- und wieder einschalten")
            ids = list(s["bloecke"])
            alt = {}
            for i in range(0, len(ids), 50):
                alt.update(self._server("holen", ids=ids[i:i + 50])["bloecke"])
            neu_version = s["version"] + 1
            self._server("wechsel", version=neu_version, faecher=faecher, wiederherstellung=ak.wiederherstellung_packen(k_neu, r))
            d.update(k=self._geheim_zu(k_neu), version=neu_version)
            self._schreiben(d)
            for bid, daten in alt.items():
                try:
                    inhalt = ak.block_entschluesseln(k_alt, bid, daten)
                except ak.KryptoFehler:
                    continue
                v = int(s["bloecke"][bid]["v"]) + 1
                self._server("schreiben", id=bid, v=v, schluessel=neu_version, daten=ak.block_verschluesseln(k_neu, bid, inhalt))
                d["bekannt"][bid] = v
            self._schreiben(d)
            return {"wiederherstellung": r, "geraete": len(faecher)}

    def ausschalten(self, *, am_server_loeschen: bool = False) -> dict:
        with self._sperre:
            if am_server_loeschen:
                self._server("aus")
            else:
                try:
                    self._server("verlassen")
                except app_core.AppError:
                    pass
            self._schreiben({"an": False})
            return {"an": False}


    def _kontoschluessel(self, d: dict) -> bytes:
        if not d.get("k"):
            raise AbgleichFehler("ABGLEICH_NICHT_ZUGELASSEN", "dieses Gerät ist für den Abgleich noch nicht zugelassen")
        return self._geheim_auf(d["k"])

    def _projekte_abgleichen(self, d: dict, s: dict, k: bytes, version: int) -> None:
        hier = self.ablage.projekt_farben()
        fp = hashlib.sha256(json.dumps(hier, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        hier_geaendert = fp != d["stand"].get(PROJEKTE_ID)
        e = s["bloecke"].get(PROJEKTE_ID)
        if e and int(e["v"]) > int(d["bekannt"].get(PROJEKTE_ID, 0)) and int(e.get("schluessel", 0)) == version:
            daten = self._server("holen", ids=[PROJEKTE_ID])["bloecke"].get(PROJEKTE_ID)
            try:
                dort = (ak.block_entschluesseln(k, PROJEKTE_ID, daten).get("projekte") or {}) if daten else {}
            except ak.KryptoFehler:
                dort = None
            if isinstance(dort, dict):
                neu = {**dort, **hier} if hier_geaendert else dict(dort)
                self.ablage._projekte_schreiben({str(n)[:gespraeche.MAX_PROJEKT]: (f if f in gespraeche.FARBEN else "") for n, f in neu.items() if str(n).strip()})
                d["bekannt"][PROJEKTE_ID] = int(e["v"])
                hier = self.ablage.projekt_farben()
                fp_neu = hashlib.sha256(json.dumps(hier, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                d["stand"][PROJEKTE_ID] = "" if hier_geaendert else fp_neu
                fp = fp_neu
                hier_geaendert = d["stand"][PROJEKTE_ID] != fp
        if hier_geaendert and (hier or e):
            v = max(int((s["bloecke"].get(PROJEKTE_ID) or {}).get("v", 0)) + 1, int(datetime.now(timezone.utc).timestamp() * 1000))
            self._server("schreiben", id=PROJEKTE_ID, v=v, schluessel=version,
                         daten=ak.block_verschluesseln(k, PROJEKTE_ID, {"projekte": hier, "geaendert": v}))
            d["bekannt"][PROJEKTE_ID] = v
            d["stand"][PROJEKTE_ID] = fp

    def abgleichen(self) -> dict:
        with self._sperre:
            d = self._lesen()
            if not d["an"]:
                return {"an": False}
            s = self._server("stand")
            if not s.get("mein_fach"):
                return {"an": True, "zugelassen": False}
            if not d.get("k") or int(d.get("version", 0)) != int(s["version"]):
                d["k"] = self._geheim_zu(ak.fach_oeffnen(s["mein_fach"], self._privat(d)))
                d["version"] = s["version"]
            k, version = self._kontoschluessel(d), int(s["version"])
            bid_von = {b: kennung for kennung, b in d["zuordnung"].items()}
            geholt = hochgeladen = geloescht = 0
            self._projekte_abgleichen(d, s, k, version)
            fehlt = [b for b, e in s["bloecke"].items() if b != PROJEKTE_ID and int(e["v"]) > int(d["bekannt"].get(b, 0)) and int(e.get("schluessel", 0)) == version]
            for i in range(0, len(fehlt), 50):
                for bid, daten in self._server("holen", ids=fehlt[i:i + 50])["bloecke"].items():
                    try:
                        inhalt = ak.block_entschluesseln(k, bid, daten)
                    except ak.KryptoFehler:
                        continue
                    kennung = bid_von.get(bid)
                    with self.ablage.sperre:
                        try:
                            g = self.ablage.laden(kennung) if kennung else None
                        except app_core.AppError:
                            g = None
                        if g is None:
                            g = self.ablage.neu()
                            d["zuordnung"][g.kennung] = bid
                            bid_von[bid] = g.kennung
                        aus_gemeinsam(inhalt, g)
                        self.ablage.speichern(g)
                    d["bekannt"][bid] = int(s["bloecke"][bid]["v"])
                    d["stand"][bid] = fingerabdruck(g)
                    geholt += 1
            for bid in [b for b in list(d["bekannt"]) if b not in s["bloecke"] and b != PROJEKTE_ID]:
                kennung = bid_von.get(bid)
                with self.ablage.sperre:
                    try:
                        g = self.ablage.laden(kennung) if kennung else None
                    except app_core.AppError:
                        g = None
                    unveraendert = g is not None and fingerabdruck(g) == d["stand"].get(bid)
                    if unveraendert:
                        self.ablage.loeschen(kennung)
                        geloescht += 1
                if kennung and (g is None or unveraendert):
                    d["zuordnung"].pop(kennung, None)
                d["bekannt"].pop(bid, None)
                d["stand"].pop(bid, None)
            vorhanden = {e["kennung"] for e in self.ablage.liste()}
            for kennung, bid in list(d["zuordnung"].items()):
                if kennung not in vorhanden:
                    if bid in s["bloecke"]:
                        self._server("loeschen", id=bid)
                    d["zuordnung"].pop(kennung, None)
                    d["bekannt"].pop(bid, None)
                    d["stand"].pop(bid, None)
            for e in self.ablage.liste():
                if not e["anzahl"]:
                    continue
                bid = d["zuordnung"].get(e["kennung"])
                g = self.ablage.laden(e["kennung"])
                if bid and d["stand"].get(bid) == fingerabdruck(g):
                    continue
                if not bid:
                    bid = secrets.token_hex(16)
                    d["zuordnung"][e["kennung"]] = bid
                v = max(int(s["bloecke"].get(bid, {}).get("v", 0)) + 1, _ms(g.geaendert))
                try:
                    self._server("schreiben", id=bid, v=v, schluessel=version, daten=ak.block_verschluesseln(k, bid, in_gemeinsam(g)))
                except app_core.AppError as exc:
                    if getattr(exc, "code", "") in ("COMMUNITY_ABGLEICH_VOLL", "COMMUNITY_ABGLEICH_GROSS"):
                        self.zuletzt_fehler = exc.detail
                        continue
                    raise
                d["bekannt"][bid] = v
                d["stand"][bid] = fingerabdruck(g)
                hochgeladen += 1
            self._schreiben(d)
            self.zuletzt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {"an": True, "zugelassen": True, "geholt": geholt, "hochgeladen": hochgeladen, "geloescht": geloescht}
