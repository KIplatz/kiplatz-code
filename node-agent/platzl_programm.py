# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import html.parser
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import app_core
import geheim
import sicher_schreiben

FORUM = "https://forum.kiplatz.at"
API = "https://kiplatz.at/platzl-api"
RUECK = "https://kiplatz.at/platzl-zurueck"
RECHTE = "read,write,session_info"
DATEI = "platzl.json"
GUELTIG_S = 600
TITEL_MIN, TEXT_MIN, TEXT_MAX = 15, 20, 30000
MAX_ANTWORT = 4 * 1024 * 1024
WEG = re.compile(r"^/(session/current|categories|latest|c/[a-z0-9-]+/\d+/l/latest|t/\d+)\.json(\?page=\d{1,3})?$|^/user-api-key/revoke$|^/posts\.json$")
_SCHLUESSEL = re.compile(r"^[A-Za-z0-9]{16,128}$")


class _ErsterCodeblock(html.parser.HTMLParser):

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tiefe, self.fertig, self.teile = 0, False, []

    def handle_starttag(self, tag, attrs):
        if tag == "pre" and not self.fertig:
            self.tiefe += 1
        elif tag == "br" and self.tiefe:
            self.teile.append("\n")

    def handle_endtag(self, tag):
        if tag == "pre" and self.tiefe:
            self.tiefe -= 1
            if not self.tiefe:
                self.fertig = True

    def handle_data(self, data):
        if self.tiefe and not self.fertig:
            self.teile.append(data)


def skill_im_beitrag(cooked: str) -> str | None:
    p = _ErsterCodeblock()
    p.feed(str(cooked or ""))
    text = "".join(p.teile)
    return text if len(text.strip()) >= 20 else None


class Platzl:
    def __init__(self, base_dir: Path, community, *, oeffner=None) -> None:
        self.datei = Path(base_dir) / DATEI
        self._c = community
        self._oeffner = oeffner
        self._offen: dict | None = None
        self._lock = threading.Lock()


    def _laden(self) -> dict:
        return sicher_schreiben.json_laden(self.datei, {}, art=dict) or {}

    def verbunden(self) -> dict | None:
        d = self._laden()
        if not d.get("schluessel"):
            return None
        try:
            k = geheim.lesen(d["schluessel"])
        except geheim.GeheimError:
            return None
        return {"schluessel": k, "client": str(d.get("client", "")), "name": str(d.get("name", "")), "seit": str(d.get("seit", ""))} if _SCHLUESSEL.match(k) else None

    def stand(self) -> dict:
        v = self.verbunden()
        return {"verbunden": bool(v), "name": v["name"] if v else "", "wartet": self.wartet()}

    def _ablegen(self, schluessel: str, client: str, name: str = "") -> None:
        app_core.ensure_plain_directory(self.datei.parent)
        sicher_schreiben.json_datei(self.datei, {"schluessel": geheim.schuetzen(schluessel, "KIplatz Platzl"), "client": client, "name": name[:60],
                                                 "seit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    def wartet(self) -> bool:
        with self._lock:
            return bool(self._offen) and time.time() - self._offen["zeit"] < GUELTIG_S


    def verbinden_start(self) -> str:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        privat = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = privat.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
        ticket, nonce = secrets.token_hex(16), secrets.token_hex(16)
        alt = self._laden()
        client = str(alt.get("client") or "") or secrets.token_hex(16)
        self._c.platzl_start(ticket)
        with self._lock:
            self._offen = {"privat": privat, "ticket": ticket, "nonce": nonce, "client": client, "zeit": time.time()}
        q = urllib.parse.urlencode({"application_name": "KIplatz-Programm", "client_id": client, "scopes": RECHTE, "public_key": pem, "nonce": nonce,
                                    "auth_redirect": f"{RUECK}?t={ticket}", "padding": "oaep"})
        return f"{FORUM}/user-api-key/new?{q}"

    def abholen(self) -> str:
        with self._lock:
            o = dict(self._offen) if self._offen and time.time() - self._offen["zeit"] < GUELTIG_S else None
        if o is None:
            self._offen = None
            return ""
        r = self._c.platzl_abholen(o["ticket"])
        if r.get("status") != "fertig":
            return "wartet"
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        with self._lock:
            self._offen = None
        try:
            klar = o["privat"].decrypt(base64.b64decode(re.sub(r"\s", "", str(r.get("payload", "")))),
                                       padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
            d = json.loads(klar.decode("utf-8"))
        except Exception:
            raise app_core.AppError("PLATZL", "die Antwort des Platzl ließ sich nicht öffnen; bitte noch einmal verbinden") from None
        if not isinstance(d, dict) or d.get("nonce") != o["nonce"] or not _SCHLUESSEL.match(str(d.get("key", ""))):
            raise app_core.AppError("PLATZL", "die Antwort des Platzl gehört nicht zu dieser Verbindung; bitte noch einmal verbinden")
        self._ablegen(str(d["key"]), o["client"])
        try:
            name = str(((self.api("/session/current.json") or {}).get("current_user") or {}).get("username") or "")
            if name:
                self._ablegen(str(d["key"]), o["client"], name)
        except app_core.AppError:
            pass
        return "fertig"

    def trennen(self) -> None:
        try:
            self.api("/user-api-key/revoke", {})
        except app_core.AppError:
            pass
        try:
            self.datei.unlink()
        except FileNotFoundError:
            pass


    def api(self, weg: str, body: dict | None = None):
        if not WEG.match(weg):
            raise app_core.AppError("PLATZL", "ungültiger Weg")
        v = self.verbunden()
        if v is None:
            raise app_core.AppError("PLATZL_AUS", "das Platzl ist mit diesem PC nicht verbunden")
        daten = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        kopf = {"Accept": "application/json", "User-Api-Key": v["schluessel"], "User-Api-Client-Id": v["client"], "User-Agent": "KIplatz-Programm"}
        if daten is not None:
            kopf["Content-Type"] = "application/json"
        req = urllib.request.Request(API + weg, data=daten, headers=kopf, method="POST" if daten is not None else "GET")
        oeffner = self._oeffner or (lambda r, timeout: urllib.request.urlopen(r, timeout=timeout, context=getattr(self._c, "_ctx", None)))
        roh = b""
        try:
            with oeffner(req, timeout=20) as r:
                roh = r.read(MAX_ANTWORT)
        except urllib.error.HTTPError as exc:
            inhalt = {}
            try:
                inhalt = json.loads(exc.read(64 * 1024).decode("utf-8") or "{}")
            except ValueError:
                pass
            if exc.code == 403 and weg != "/user-api-key/revoke":
                if weg == "/session/current.json" or not self._lebt():
                    try:
                        self.datei.unlink()
                    except FileNotFoundError:
                        pass
                    raise app_core.AppError("PLATZL_AUS", "die Verbindung zum Platzl wurde beendet; verbinde dich bitte neu") from None
                raise app_core.AppError("PLATZL", "dafür fehlen dir im Platzl die Rechte") from None
            if exc.code == 404:
                raise app_core.AppError("PLATZL", "das gibt es im Platzl nicht (mehr)") from None
            if exc.code == 429:
                raise app_core.AppError("PLATZL", "das Platzl bremst gerade; bitte in einer Minute noch einmal") from None
            if exc.code == 422:
                grund = inhalt.get("errors", [""])[0] if isinstance(inhalt.get("errors"), list) and inhalt["errors"] else ""
                raise app_core.AppError("PLATZL", f"das Platzl sagt: {str(grund)[:300]}" if grund else "das Platzl hat den Beitrag nicht angenommen") from None
            raise app_core.AppError("PLATZL", f"das Platzl antwortet mit {exc.code}") from None
        except app_core.AppError:
            raise
        except Exception as exc:
            raise app_core.AppError("PLATZL", f"das Platzl ist gerade nicht erreichbar ({type(exc).__name__})") from None
        finally:
            try:
                import datenfluss
                datenfluss.melden(API, "Platzl: " + ("schreiben" if weg == "/posts.json" else "Verbindung beenden" if "revoke" in weg else "lesen"), len(daten or b""), len(roh))
            except Exception:
                pass
        try:
            return json.loads(roh.decode("utf-8") or "{}")
        except ValueError:
            return {}

    def _lebt(self) -> bool:
        try:
            return bool((self.api("/session/current.json") or {}).get("current_user"))
        except app_core.AppError:
            return False


    def kategorien(self) -> list[dict]:
        d = self.api("/categories.json")
        out = []
        for c in (d.get("category_list") or {}).get("categories") or []:
            slug = str(c.get("slug", "")).lower()
            if isinstance(c.get("id"), int) and re.fullmatch(r"[a-z0-9-]+", slug):
                farbe = str(c.get("color") or "")
                out.append({"id": c["id"], "name": str(c.get("name", ""))[:60], "slug": slug,
                            "farbe": "#" + farbe if re.fullmatch(r"[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", farbe) else "#8a949c",
                            "darf": c.get("permission") in (None, 1)})
        return out

    def themen(self, slug: str = "", kat: int = 0) -> list[dict]:
        weg = f"/c/{slug}/{int(kat)}/l/latest.json" if slug and kat else "/latest.json"
        d = self.api(weg)
        return [{"id": t["id"], "titel": str(t.get("title", ""))[:200], "kategorie": t.get("category_id"), "antworten": max(0, int(t.get("posts_count") or 1) - 1),
                 "zuletzt": str(t.get("last_posted_at") or t.get("created_at") or "")}
                for t in ((d.get("topic_list") or {}).get("topics") or [])[:40] if isinstance(t.get("id"), int)]

    def thema(self, thema: int) -> dict:
        d = self.api(f"/t/{int(thema)}.json")
        slug = str(d.get("slug") or "")
        return {"id": int(thema), "titel": str(d.get("title", ""))[:200], "slug": slug if re.fullmatch(r"[a-z0-9-]+", slug) else "thema",
                "kategorie": d.get("category_id"),
                "beitraege": [{"name": str(p.get("username", ""))[:60], "zeit": str(p.get("created_at", "")), "html": str(p.get("cooked", ""))[:200000]}
                              for p in ((d.get("post_stream") or {}).get("posts") or [])[:50]]}

    def schreiben(self, *, titel: str = "", text: str, kategorie: int | None = None, thema: int | None = None) -> dict:
        raw = str(text or "").strip()
        if len(raw) < TEXT_MIN:
            raise app_core.AppError("PLATZL", f"der Text braucht mindestens {TEXT_MIN} Zeichen")
        if len(raw) > TEXT_MAX:
            raise app_core.AppError("PLATZL", f"der Text ist zu lang (höchstens {TEXT_MAX} Zeichen)")
        if thema:
            body = {"topic_id": int(thema), "raw": raw}
        else:
            t = " ".join(str(titel or "").split())
            if len(t) < TITEL_MIN:
                raise app_core.AppError("PLATZL", f"der Titel braucht mindestens {TITEL_MIN} Zeichen")
            if not isinstance(kategorie, int):
                raise app_core.AppError("PLATZL", "bitte eine Kategorie wählen")
            body = {"title": t[:250], "raw": raw, "category": kategorie}
        d = self.api("/posts.json", body)
        return {"thema": int(d.get("topic_id") or thema or 0), "nummer": int(d.get("post_number") or 0)}

    def skill_text(self, thema: int) -> tuple[str, str]:
        t = self.thema(int(thema))
        roh = skill_im_beitrag(t["beitraege"][0]["html"]) if t["beitraege"] else None
        if not roh:
            raise app_core.AppError("PLATZL", "in diesem Thema steht kein Skill (kein Codeblock im ersten Beitrag)")
        return roh, re.sub(r"^Skill:\s*", "", t["titel"], flags=re.I)[:80]
