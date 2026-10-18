# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import re
import secrets
import stat
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HOECHSTENS_DATEIEN = 400_000
ZEIT_BUDGET_S = 60.0
FRISCH_S = 15 * 60
TREFFER_HOECHSTENS = 20
KENNUNG_GUELTIG_S = 2 * 3600

_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORT = re.compile(r"[a-z0-9]+")

_BEKANNT = [("Dokumente", "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", "Documents"), ("Bilder", "{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Pictures"),
            ("Desktop", "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop"), ("Downloads", "{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
            ("Musik", "{4BD8D571-6D19-48D3-BE97-422220080E43}", "Music"), ("Videos", "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", "Videos")]

ARTEN = {
    "Word-Datei": {".doc", ".docx", ".odt", ".rtf", ".pages"}, "PDF": {".pdf"}, "Excel-Tabelle": {".xls", ".xlsx", ".ods", ".csv", ".numbers"},
    "Präsentation": {".ppt", ".pptx", ".odp", ".key-folie"}, "Bild": {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".raw", ".cr2", ".nef", ".dng"},
    "Video": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".3gp"}, "Musik": {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"},
    "Textdatei": {".txt", ".md"}, "ZIP-Archiv": {".zip", ".7z", ".rar"}, "E-Mail": {".eml", ".msg"},
}
_ART_VON = {e: a for a, es in ARTEN.items() for e in es}
_ART_WORTE = [(re.compile(r"\b(?:pdfs?|pdf-\w+)\b"), "PDF"), (re.compile(r"\b(?:word\w*|docx?)\b"), "Word-Datei"),
              (re.compile(r"\b(?:excel\w*|tabellen?|xlsx?|spreadsheets?)\b"), "Excel-Tabelle"),
              (re.compile(r"\b(?:fotos?|bilder?|photos?|pictures?|images?)\b"), "Bild"),
              (re.compile(r"\b(?:videos?|filme?|movies?)\b"), "Video"), (re.compile(r"\b(?:powerpoint\w*|praesentation\w*|presentations?|slides)\b"), "Präsentation")]
ART_EN = {"Word-Datei": "Word file", "PDF": "PDF", "Excel-Tabelle": "Excel sheet", "Präsentation": "Presentation", "Bild": "Image", "Video": "Video",
          "Musik": "Music", "Textdatei": "Text file", "ZIP-Archiv": "ZIP archive", "E-Mail": "Email", "Datei": "File"}
WURZEL_EN = {name: englisch for name, _guid, englisch in _BEKANNT}
_ENDUNG_NIE = {".kdbx", ".kdb", ".key", ".pem", ".ppk", ".pfx", ".p12", ".jks", ".keystore", ".ovpn", ".gpg", ".pgp", ".asc", ".wallet", ".crt", ".cer",
               ".lnk", ".url", ".ini", ".tmp", ".crdownload", ".part", ".partial", ".dll", ".exe", ".sys", ".msi", ".bat", ".cmd", ".ps1"}
_NAME_NIE = re.compile(r"(?:passw|kennw|kennwort|zugangsdat|zugangscode|credential|secret|geheim|schluessel|schlussel|id_rsa|id_ed25519|id_ecdsa|"
                       r"wallet|seed|recovery|wiederherstell|tan-?liste|^desktop\.ini$|^thumbs\.db$|^\.|^~\$)", re.I)
_ORDNER_NIE = re.compile(r"^(?:node_modules|__pycache__|\.git|\.ssh|\.gnupg|appdata|\$recycle\.bin|system volume information|venv|\.venv|"
                         r"communityainetwork|communityai-test|communityai|kiplatz|my music|my pictures|my videos)$|passw|kennw|zugangsdat|credential|secret|"
                         r"geheim|schluessel|schlussel|wallet", re.I)

_FUELL = set("""datei dateien dokument dokumente dokumenten file files ordner unterlagen such suche suchen sucht gesucht finde finden findest gefunden wo ist
sind liegt liegen hab habe hast hat ich du mir mich mein meine meinen meinem meiner meines dein deine unser unsere die der das den dem des ein eine einen
einem einer zeig zeige zeigen hol hole holen schick schicke gib bitte von vom im in auf mit und oder aus fuer ueber zu zum zur an am es da dort noch mal
kannst koenntest brauch brauche braeuchte bräuchte welche welcher alle alles pc handy computer rechner laptop daheim zuhause heim gerade irgendwo
irgendwie nochmal mehr pdf pdfs word excel tabelle tabellen foto fotos bild bilder video videos ja nein was wie wann denn doch""".split())
_FUELL |= set("""where wheres whats what which who when is are was were be been you my mine our your yours the a an this that these those there here it its
find finding found show showing get getting fetch send give bring open look looking search searching saved save put kept keep stored located
file files folder folders document documents doc docs paper papers from into onto out off for with and or of at by to me please can could would will
need want got have has had do does did any some all every pc phone computer laptop home house spreadsheet spreadsheets photo photos picture pictures
image images movie movies presentation presentations slides just again more yes now""".split())


def _norm(text: str) -> str:
    return str(text or "").lower().translate(_UMLAUT)


_NEUESTE = {"letzte", "letzten", "letzter", "letztes", "letztem", "neueste", "neuesten", "neuester", "neuestes", "aktuellste", "aktuellsten",
            "aktuellster", "aktuellstes", "juengste", "juengsten", "juengster", "zuletzt", "last", "latest", "newest", "recent", "lately"}
NEUESTE_HOECHSTENS = 5


def nach_neuester(frage: str) -> bool:
    return any(w in _NEUESTE for w in _WORT.findall(_norm(frage)))


def kernwoerter(frage: str) -> list[str]:
    out: list[str] = []
    kurz = {w.lower() for w in re.findall(r"\b[A-ZÄÖÜ]{2}\b", str(frage or ""))}
    for w in _WORT.findall(_norm(frage)):
        if w in _FUELL or w in _NEUESTE or (len(w) < 3 and not w.isdigit() and w not in kurz) or w in out:
            continue
        out.append(w)
    return out


def art_der_frage(frage: str) -> str:
    t = _norm(frage)
    for rx, art in _ART_WORTE:
        if rx.search(t):
            return art
    return ""


def art_der_datei(name: str) -> str:
    return _ART_VON.get(os.path.splitext(name)[1].lower(), "Datei")


@dataclass
class Eintrag:
    pfad: str
    wurzel: str
    ordner: str
    name: str
    groesse: int
    geaendert: float
    name_n: str
    weg_n: str


def _bekannter_ordner(guid: str) -> Path | None:
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]
        g = GUID()
        if ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(g)) != 0:
            return None
        p = ctypes.c_wchar_p()
        ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p))
        try:
            return Path(p.value) if p.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(p)
    except Exception:
        return None


def eigene_ordner() -> list[tuple[str, Path]]:
    home = Path.home()
    kandidaten: list[tuple[str, Path]] = []
    for name, guid, englisch in _BEKANNT:
        p = _bekannter_ordner(guid) or home / englisch
        kandidaten.append((name, p))
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(var):
            kandidaten.append(("OneDrive", Path(os.environ[var])))
    out: list[tuple[str, Path]] = []
    for name, p in kandidaten:
        try:
            r = p.resolve()
        except OSError:
            continue
        if r.is_dir() and not any(r == q for _, q in out):
            out.append((name, r))
    return out


def _versteckt(e: os.DirEntry) -> bool:
    try:
        a = getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(a & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM)) if hasattr(stat, "FILE_ATTRIBUTE_HIDDEN") else False


def _verknuepft(e: os.DirEntry) -> bool:
    try:
        if e.is_symlink():
            return True
        a = getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(a & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return True


def verzeichnis(wurzeln: list[tuple[str, Path]], *, budget_s: float = ZEIT_BUDGET_S, hoechstens: int = HOECHSTENS_DATEIEN) -> list[Eintrag]:
    ende = time.monotonic() + budget_s
    out: list[Eintrag] = []
    alle = {os.path.normcase(str(w)) for _, w in wurzeln}
    for wname, wurzel in wurzeln:
        stapel: list[tuple[Path, str]] = [(wurzel, "")]
        while stapel and len(out) < hoechstens and time.monotonic() < ende:
            ordner, rel = stapel.pop()
            try:
                it = list(os.scandir(ordner))
            except OSError:
                continue
            for e in it:
                if _versteckt(e):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        if _verknuepft(e) or _ORDNER_NIE.search(e.name) or os.path.normcase(e.path) in alle:
                            continue
                        stapel.append((Path(e.path), f"{rel}\\{e.name}" if rel else e.name))
                        continue
                    if not e.is_file(follow_symlinks=False):
                        continue
                    endung = os.path.splitext(e.name)[1].lower()
                    if endung in _ENDUNG_NIE or _NAME_NIE.search(e.name):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                out.append(Eintrag(e.path, wname, rel, e.name, int(st.st_size), float(st.st_mtime), _norm(os.path.splitext(e.name)[0]),
                                   _norm(f"{wname} {rel}")))
    return out


def _trifft(wort: str, text: str) -> bool:
    if len(wort) >= 4:
        return wort in text
    return any(w.startswith(wort) for w in _WORT.findall(text))


def suchen(eintraege: list[Eintrag], frage: str, *, hoechstens: int = TREFFER_HOECHSTENS) -> tuple[str, list[Eintrag]]:
    kern = kernwoerter(frage)
    art = art_der_frage(frage)
    if nach_neuester(frage):
        runde, tr = suchen(eintraege, " ".join(kern) + (" " + art if art and not kern else ""), hoechstens=len(eintraege) or 1) if (kern or art) else ("", [])
        if runde == "genau":
            return "neueste", sorted(tr, key=lambda e: -e.geaendert)[:NEUESTE_HOECHSTENS]
        return runde, sorted(tr, key=lambda e: -e.geaendert)[:hoechstens]
    kandidaten = [e for e in eintraege if not art or art_der_datei(e.name) == art]
    if not kern:
        if not art:
            return "", []
        return "genau", sorted(kandidaten, key=lambda e: -e.geaendert)[:hoechstens]
    genau = [e for e in kandidaten if all(_trifft(w, e.name_n) or _trifft(w, e.weg_n) for w in kern)]
    if genau:
        return "genau", sorted(genau, key=lambda e: (-sum(_trifft(w, e.name_n) for w in kern), -e.geaendert))[:hoechstens]
    aehnlich = [(sum(_trifft(w, e.name_n) for w in kern), e) for e in kandidaten]
    aehnlich = [(n, e) for n, e in aehnlich if n >= 1]
    return ("aehnlich" if aehnlich else ""), [e for _, e in sorted(aehnlich, key=lambda x: (-x[0], -x[1].geaendert))][:hoechstens]


def _datum(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%d.%m.%Y")


def _ort(e: Eintrag) -> str:
    return f"im Ordner „{e.ordner.split(chr(92))[-1]}“ ({e.wurzel})" if e.ordner else f"direkt in „{e.wurzel}“"


def _art_satz(e: Eintrag) -> str:
    a = art_der_datei(e.name)
    return {"Datei": "eine Datei", "Bild": "ein Bild", "Video": "ein Video", "PDF": "ein PDF", "ZIP-Archiv": "ein ZIP-Archiv", "E-Mail": "eine E-Mail",
            "Musik": "ein Musikstück"}.get(a, "eine " + a)


def _ort_en(e: Eintrag) -> str:
    wurzel = WURZEL_EN.get(e.wurzel, e.wurzel)
    return f"in the folder “{e.ordner.split(chr(92))[-1]}” ({wurzel})" if e.ordner else f"directly in “{wurzel}”"


def _art_satz_en(e: Eintrag) -> str:
    return {"Word-Datei": "a Word file", "PDF": "a PDF", "Excel-Tabelle": "an Excel sheet", "Präsentation": "a presentation", "Bild": "an image",
            "Video": "a video", "Musik": "a piece of music", "Textdatei": "a text file", "ZIP-Archiv": "a ZIP archive", "E-Mail": "an email"}.get(
        art_der_datei(e.name), "a file")


def antwort_en(frage: str, runde: str, treffer: list[Eintrag], pc_name: str = "") -> str:
    kern = kernwoerter(frage)
    gesucht = " ".join(w.capitalize() for w in kern) or ART_EN.get(art_der_frage(frage), "") or "your question"
    wo = f"on “{pc_name}”" if pc_name else "on your PC at home"
    datum = lambda t: datetime.fromtimestamp(t).strftime("%d/%m/%Y")
    if not treffer:
        return (f"I couldn't find a file {wo} whose name matches “{gesucht}”. I looked in Documents, Pictures, Desktop, Downloads, Music, "
                "Videos and OneDrive. Maybe it's named a little differently; try another word from the name.")
    if runde == "neueste":
        e = treffer[0]
        satz = f"The newest is “{e.name}”, {_art_satz_en(e)} {_ort_en(e)}, from {datum(e.geaendert)}."
        return satz + (" Below you can see the ones before it." if len(treffer) > 1 else "")
    if len(treffer) == 1 and runde == "genau":
        e = treffer[0]
        return f"I found {_art_satz_en(e)} {_ort_en(e)}: “{e.name}”, last changed on {datum(e.geaendert)}."
    if runde == "genau":
        return f"I found {len(treffer)} matching files {wo}. You can see them below, best first."
    return (f"I couldn't find a file with “{gesucht}” in its name {wo}. Below you can see {len(treffer)} similar files "
            "that have part of it in their name.")


def antwort(frage: str, runde: str, treffer: list[Eintrag], pc_name: str = "") -> str:
    kern = kernwoerter(frage)
    gesucht = " ".join(w.capitalize() for w in kern) or art_der_frage(frage) or "deiner Frage"
    wo = f" auf „{pc_name}“" if pc_name else " auf deinem PC daheim"
    if not treffer:
        return (f"Ich habe{wo} keine Datei gefunden, deren Name zu „{gesucht}“ passt. Geschaut habe ich in Dokumente, Bilder, Desktop, Downloads, "
                "Musik, Videos und OneDrive. Vielleicht heißt sie ein bisschen anders; probier es mit einem anderen Wort aus dem Namen.")
    if runde == "neueste":
        e = treffer[0]
        satz = f"Am neuesten ist „{e.name}“, {_art_satz(e)} {_ort(e)}, vom {_datum(e.geaendert)}."
        return satz + (" Darunter siehst du die nächsten davor." if len(treffer) > 1 else "")
    if len(treffer) == 1 and runde == "genau":
        e = treffer[0]
        return f"{_ort(e)[0].upper()}{_ort(e)[1:]} habe ich {_art_satz(e)} gefunden: „{e.name}“, zuletzt geändert am {_datum(e.geaendert)}."
    if runde == "genau":
        return f"Ich habe{wo} {len(treffer)} passende Dateien gefunden. Darunter siehst du sie, die besten zuerst."
    return (f"Eine Datei mit „{gesucht}“ im Namen habe ich{wo} nicht gefunden. Darunter siehst du {len(treffer)} ähnliche Dateien, "
            "in deren Namen ein Teil davon steht.")


class Dateiliste:

    def __init__(self, wurzeln=None, *, jetzt=time.time) -> None:
        self._wurzeln_fn = wurzeln or eigene_ordner
        self._jetzt = jetzt
        self._lock = threading.Lock()
        self._eintraege: list[Eintrag] | None = None
        self._stand = 0.0
        self._baut = False
        self._erstes = threading.Lock()
        self._kennungen: dict[str, tuple[Eintrag, float]] = {}

    def _bauen(self) -> None:
        try:
            e = verzeichnis(self._wurzeln_fn())
        except Exception:
            with self._lock:
                self._baut = False
            raise
        with self._lock:
            self._eintraege, self._stand, self._baut = e, self._jetzt(), False

    def vorbereiten(self) -> None:
        def los():
            try:
                self.eintraege()
            except Exception:
                pass
        threading.Thread(target=los, name="dateiliste-vorab", daemon=True).start()

    def eintraege(self) -> list[Eintrag]:
        with self._lock:
            leer = self._eintraege is None
        if leer:
            with self._erstes:
                with self._lock:
                    noch_leer = self._eintraege is None
                if noch_leer:
                    self._bauen()
        with self._lock:
            alt = self._jetzt() - self._stand > FRISCH_S and not self._baut
            if alt:
                self._baut = True
        if alt:
            threading.Thread(target=self._bauen, name="dateiliste", daemon=True).start()
        with self._lock:
            return list(self._eintraege or [])

    def suchen(self, frage: str, pc_name: str = "", *, englisch: bool = False) -> tuple[str, list[dict]]:
        runde, treffer = suchen(self.eintraege(), frage)
        out = []
        with self._lock:
            t = self._jetzt()
            self._kennungen = {k: v for k, v in self._kennungen.items() if t - v[1] < KENNUNG_GUELTIG_S}
            if len(self._kennungen) > 5000:
                self._kennungen.clear()
            for e in treffer:
                k = secrets.token_hex(8)
                self._kennungen[k] = (e, t)
                art = art_der_datei(e.name)
                out.append({"id": k, "name": e.name, "ordner": e.ordner, "wurzel": WURZEL_EN.get(e.wurzel, e.wurzel) if englisch else e.wurzel,
                            "art": ART_EN.get(art, art) if englisch else art, "groesse": e.groesse,
                            "geaendert": datetime.fromtimestamp(e.geaendert).strftime("%Y-%m-%dT%H:%M:%S"), "runde": runde, **({"pc": pc_name} if pc_name else {})})
        return (antwort_en if englisch else antwort)(frage, runde, treffer, pc_name), out

    def datei(self, kennung: str) -> Eintrag | None:
        with self._lock:
            v = self._kennungen.get(str(kennung))
            return v[0] if v and self._jetzt() - v[1] < KENNUNG_GUELTIG_S else None


__all__ = ["Dateiliste", "Eintrag", "eigene_ordner", "verzeichnis", "suchen", "kernwoerter", "art_der_frage", "art_der_datei", "antwort", "ARTEN"]
