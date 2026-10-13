# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import app_core

MAX_DATEI = 200 * 1024 * 1024
MAX_GESPRAECHE = 2000
MAX_NACHRICHTEN = 400
MAX_TEXT = 40_000


@dataclass
class Importiert:
    titel: str
    nachrichten: list[dict] = field(default_factory=list)
    erstellt: str = ""
    herkunft: str = ""


def _zeit(t) -> str:
    try:
        if isinstance(t, (int, float)) and t > 0:
            return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(t, str) and len(t) >= 10:
            return t[:19].replace(" ", "T") + ("Z" if not t.endswith("Z") and len(t) >= 19 else "")
    except (ValueError, OverflowError, OSError):
        pass
    return ""


def _text_aus_chatgpt(msg: dict) -> str:
    c = msg.get("content") or {}
    if isinstance(c, str):
        return c
    parts = c.get("parts") if isinstance(c, dict) else None
    if isinstance(parts, list):
        return "\n".join(p if isinstance(p, str) else (p.get("text", "") if isinstance(p, dict) else "") for p in parts).strip()
    if isinstance(c, dict) and isinstance(c.get("text"), str):
        return c["text"]
    return ""


def aus_chatgpt(daten: list) -> list[Importiert]:
    out: list[Importiert] = []
    for conv in daten[:MAX_GESPRAECHE]:
        if not isinstance(conv, dict) or not isinstance(conv.get("mapping"), dict):
            continue
        mapping = conv["mapping"]
        kette: list[dict] = []
        node = conv.get("current_node")
        besucht = 0
        while node and node in mapping and besucht < MAX_NACHRICHTEN * 3:
            n = mapping[node]
            msg = n.get("message") if isinstance(n, dict) else None
            if isinstance(msg, dict):
                rolle = ((msg.get("author") or {}).get("role") or "")
                text = _text_aus_chatgpt(msg)
                if rolle in ("user", "assistant") and text.strip():
                    kette.append({"rolle": rolle, "text": text[:MAX_TEXT]})
            node = n.get("parent") if isinstance(n, dict) else None
            besucht += 1
        kette.reverse()
        if kette:
            out.append(Importiert(str(conv.get("title") or "Ohne Titel")[:80], kette[-MAX_NACHRICHTEN:], _zeit(conv.get("create_time")), "ChatGPT"))
    return out


def aus_claude(daten: list) -> list[Importiert]:
    out: list[Importiert] = []
    for conv in daten[:MAX_GESPRAECHE]:
        if not isinstance(conv, dict) or not isinstance(conv.get("chat_messages"), list):
            continue
        kette = []
        for m in conv["chat_messages"]:
            if not isinstance(m, dict):
                continue
            rolle = {"human": "user", "assistant": "assistant"}.get(str(m.get("sender", "")))
            text = m.get("text") or ""
            if not text and isinstance(m.get("content"), list):
                text = "\n".join(str(c.get("text", "")) for c in m["content"] if isinstance(c, dict))
            if rolle and str(text).strip():
                kette.append({"rolle": rolle, "text": str(text)[:MAX_TEXT]})
        if kette:
            out.append(Importiert(str(conv.get("name") or "Ohne Titel")[:80], kette[-MAX_NACHRICHTEN:], _zeit(conv.get("created_at")), "Claude"))
    return out


def aus_openwebui(daten: list) -> list[Importiert]:
    out: list[Importiert] = []
    for e in daten[:MAX_GESPRAECHE]:
        if not isinstance(e, dict):
            continue
        chat = e.get("chat") if isinstance(e.get("chat"), dict) else e
        msgs = chat.get("messages")
        if not isinstance(msgs, list) and isinstance(chat.get("history"), dict):
            h = chat["history"].get("messages")
            msgs = list(h.values()) if isinstance(h, dict) else None
        if not isinstance(msgs, list):
            continue
        kette = [{"rolle": str(m.get("role")), "text": str(m.get("content", ""))[:MAX_TEXT]} for m in msgs
                 if isinstance(m, dict) and m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()]
        if kette:
            out.append(Importiert(str(chat.get("title") or e.get("title") or "Ohne Titel")[:80], kette[-MAX_NACHRICHTEN:], _zeit(e.get("created_at") or chat.get("timestamp")), "Open WebUI"))
    return out


_MD_KOPF = re.compile(r"^##\s+(Ich|Du|User|Nutzer|Frage|KIplatz|Unser Modell|Assistant|Assistent|KI|Antwort)\s*$", re.I | re.M)
_ZEILE = re.compile(r"^(User|Nutzer|Ich|Frage|Assistant|Assistent|KI|Antwort|ChatGPT|Claude)\s*:\s*", re.I)


def aus_markdown(text: str, titel: str = "") -> list[Importiert]:
    text = text.replace("\r\n", "\n")
    t = titel
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        t = m.group(1).strip()
    kette: list[dict] = []
    teile = _MD_KOPF.split(text)
    if len(teile) >= 3:
        for i in range(1, len(teile) - 1, 2):
            rolle = "user" if teile[i].lower() in ("ich", "du", "user", "nutzer", "frage") else "assistant"
            body = teile[i + 1].strip()
            body = re.sub(r"\n\*Woher:.*?\*\s*$", "", body, flags=re.S).strip()
            if body:
                kette.append({"rolle": rolle, "text": body[:MAX_TEXT]})
    else:
        akt = None
        for zeile in text.split("\n"):
            mm = _ZEILE.match(zeile)
            if mm:
                rolle = "user" if mm.group(1).lower() in ("user", "nutzer", "ich", "frage") else "assistant"
                akt = {"rolle": rolle, "text": zeile[mm.end():].strip()}
                kette.append(akt)
            elif akt is not None:
                akt["text"] = (akt["text"] + "\n" + zeile).strip()[:MAX_TEXT]
    kette = [k for k in kette if k["text"]]
    return [Importiert((t or "Importiertes Gespräch")[:80], kette[-MAX_NACHRICHTEN:], "", "Textdatei")] if kette else []


def erkennen(pfad: Path) -> list[Importiert]:
    p = Path(pfad)
    try:
        if p.stat().st_size > MAX_DATEI:
            raise app_core.AppError("IMPORT_GROSS", "die Datei ist größer als 200 MB")
        roh = p.read_bytes()
    except OSError as exc:
        raise app_core.AppError("IMPORT_DATEI", f"die Datei ließ sich nicht lesen ({exc.strerror})") from None
    if p.suffix.lower() == ".zip":
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(roh)) as z:
                name = next((n for n in z.namelist() if n.split("/")[-1] == "conversations.json"), None)
                if not name:
                    raise app_core.AppError("IMPORT_FORM", "in der ZIP-Datei ist keine conversations.json")
                roh = z.read(name)
        except zipfile.BadZipFile:
            raise app_core.AppError("IMPORT_DATEI", "das ist keine ZIP-Datei") from None
    text = roh.decode("utf-8", "replace")
    if text.lstrip().startswith(("[", "{")):
        try:
            daten = json.loads(text)
        except ValueError:
            raise app_core.AppError("IMPORT_FORM", "die Datei sieht aus wie JSON, ist aber nicht lesbar") from None
        if isinstance(daten, dict):
            daten = [daten]
        if not isinstance(daten, list):
            raise app_core.AppError("IMPORT_FORM", "unbekanntes Format")
        for leser in (aus_chatgpt, aus_claude, aus_openwebui):
            out = leser(daten)
            if out:
                return out
        raise app_core.AppError("IMPORT_FORM", "in dieser Datei wurden keine Gespräche von ChatGPT, Claude oder Open WebUI erkannt")
    out = aus_markdown(text, p.stem)
    if not out:
        raise app_core.AppError("IMPORT_FORM", "in dieser Textdatei wurde kein Gespräch erkannt (erwartet: „## Ich“ / „## KIplatz“ oder „User:“ / „Assistant:“)")
    return out


__all__ = ["Importiert", "erkennen", "aus_chatgpt", "aus_claude", "aus_openwebui", "aus_markdown"]
