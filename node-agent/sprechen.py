# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import ctypes
import io
import os
import subprocess
import sys
import threading
import time
import wave
import zipfile
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import app_core
import ki_laufzeit
from modell_katalog import HOEREN, SPRACHE_LAUFZEIT, SPRACHE_MODELL
import sprechen_windows

WINDOWS_ERKENNER = sprechen_windows.Erkenner()
HOER_RUHE_S = 300
NOTWEG_S = 600

CLI_EXE = "whisper-cli.exe"
RATE = 16000
PUFFER_MS = 100
MAX_S = 90
ERKENNEN_TIMEOUT_S = 240
_CREATE_NO_WINDOW = 0x08000000


class SprechenError(app_core.AppError):
    pass


class SprachOrdner:

    def __init__(self, ki: ki_laufzeit.KiOrdner) -> None:
        self.ki = ki
        self.laufzeit_dir = ki.ki_dir / "laufzeit" / SPRACHE_LAUFZEIT.kennung
        self.cli = self.laufzeit_dir / CLI_EXE
        self.modell = ki.modelle_dir / SPRACHE_MODELL.datei
        self.arbeit = ki.ki_dir / "sprechen"
        self.marke_blockiert = self.arbeit / "whisper-blockiert.txt"

    def laufzeit_da(self) -> bool:
        return self.cli.is_file()

    def modell_da(self) -> bool:
        try:
            return self.modell.is_file() and self.modell.stat().st_size == SPRACHE_MODELL.groesse
        except OSError:
            return False

    def da(self) -> bool:
        return self.laufzeit_da() and self.modell_da()

    def hoer_da(self) -> bool:
        return self.ki.laufzeit_da() and self.ki.modell_da(HOEREN) and self.ki.bilder_da(HOEREN)

    def blockiert(self) -> bool:
        return self.marke_blockiert.is_file()

    def blockiert_merken(self) -> None:
        try:
            app_core.ensure_plain_directory(self.arbeit)
            self.marke_blockiert.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " Smart App Control hat whisper-cli.exe nicht geladen\n", encoding="utf-8")
        except OSError:
            pass


def entpacken(zip_pfad: Path, ziel_dir: Path) -> Path:
    app_core.ensure_plain_directory(ziel_dir)
    root = ziel_dir.resolve()
    try:
        with zipfile.ZipFile(zip_pfad) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if not name or name.startswith("."):
                    continue
                if not name.lower().endswith((".exe", ".dll")):
                    continue
                target = root / name
                if target.parent != root:
                    raise SprechenError("SPRECHEN_LAUFZEIT", "Archiv enthält einen unerlaubten Pfad")
                with z.open(info) as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(ki_laufzeit.CHUNK)
                        if not chunk:
                            break
                        dst.write(chunk)
    except (zipfile.BadZipFile, OSError) as exc:
        raise SprechenError("SPRECHEN_LAUFZEIT", f"Sprach-Laufzeit konnte nicht entpackt werden ({exc.__class__.__name__})") from None
    exe = root / CLI_EXE
    if not exe.is_file():
        raise SprechenError("SPRECHEN_LAUFZEIT", f"{CLI_EXE} fehlt im Archiv")
    return exe


HOLEN_GESAMT = HOEREN.groesse + HOEREN.bilder.groesse


def holen(ordner: SprachOrdner, *, fortschritt: Callable[[str, int, int], None] | None = None, herunterladen=None) -> None:
    laden = herunterladen or ki_laufzeit.herunterladen
    ordner.ki.anlegen()
    if not ordner.ki.laufzeit_da():
        zip_pfad = ordner.ki.downloads_dir / ki_laufzeit.LAUFZEIT.datei
        if not ki_laufzeit.pruefsumme_ok(zip_pfad, ki_laufzeit.LAUFZEIT):
            laden(ki_laufzeit.LAUFZEIT, zip_pfad, fortschritt=(lambda d, g: fortschritt("KI-Laufzeit", d, g)) if fortschritt else None)
        ki_laufzeit.laufzeit_entpacken(zip_pfad, ordner.ki.laufzeit_dir, schon_da=ordner.ki.laufzeit_da)
    if not ordner.ki.modell_da(HOEREN):
        laden(HOEREN, ordner.ki.modell_pfad(HOEREN), fortschritt=(lambda d, g: fortschritt("Hör-Modell", d, g)) if fortschritt else None)
    if not ordner.ki.bilder_da(HOEREN):
        laden(HOEREN.bilder, ordner.ki.bilder_pfad(HOEREN), fortschritt=(lambda d, g: fortschritt("Hör-Zusatz", d, g)) if fortschritt else None)


_WAVE_MAPPER = 0xFFFFFFFF
_WAVE_FORMAT_PCM = 1
_WAVE_FORMAT_QUERY = 0x0001
_CALLBACK_NULL = 0
_WHDR_DONE = 0x00000001
_MMSYSERR_NOERROR = 0

if sys.platform == "win32":
    from ctypes import wintypes

    class _WAVEFORMATEX(ctypes.Structure):
        _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                    ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]

    class _WAVEHDR(ctypes.Structure):
        pass

    _WAVEHDR._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD),
                         ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                         ("lpNext", ctypes.POINTER(_WAVEHDR)), ("reserved", ctypes.c_size_t)]

    def _winmm():
        m = ctypes.WinDLL("winmm")
        m.waveInOpen.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.UINT, ctypes.POINTER(_WAVEFORMATEX), ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
        m.waveInOpen.restype = wintypes.UINT
        for name in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
            getattr(m, name).argtypes = [wintypes.HANDLE, ctypes.POINTER(_WAVEHDR), wintypes.UINT]
            getattr(m, name).restype = wintypes.UINT
        for name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
            getattr(m, name).argtypes = [wintypes.HANDLE]
            getattr(m, name).restype = wintypes.UINT
        m.waveInGetNumDevs.restype = wintypes.UINT
        return m

    def _format() -> "_WAVEFORMATEX":
        f = _WAVEFORMATEX()
        f.wFormatTag, f.nChannels, f.nSamplesPerSec, f.wBitsPerSample = _WAVE_FORMAT_PCM, 1, RATE, 16
        f.nBlockAlign = 2
        f.nAvgBytesPerSec = RATE * 2
        f.cbSize = 0
        return f


def mikrofon_da() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return _winmm().waveInGetNumDevs() > 0
    except Exception:
        return False


def format_moeglich() -> bool:
    if sys.platform != "win32":
        return False
    try:
        m = _winmm()
        h = wintypes.HANDLE()
        return m.waveInOpen(ctypes.byref(h), _WAVE_MAPPER, ctypes.byref(_format()), 0, 0, _WAVE_FORMAT_QUERY) == _MMSYSERR_NOERROR
    except Exception:
        return False


class Aufnahme:

    def __init__(self, *, max_s: float = MAX_S) -> None:
        self.max_s = float(max_s)
        self._daten = bytearray()
        self._lock = threading.Lock()
        self._stopp = threading.Event()
        self._thread: threading.Thread | None = None
        self._h = None
        self._koepfe: list = []
        self._puffer: list = []
        self._m = None
        self.pegel = 0.0
        self.seit = 0.0
        self.voll = False

    def start(self) -> None:
        if sys.platform != "win32":
            raise SprechenError("SPRECHEN_MIKROFON", "Aufnahme geht nur unter Windows")
        m = _winmm()
        h = wintypes.HANDLE()
        rc = m.waveInOpen(ctypes.byref(h), _WAVE_MAPPER, ctypes.byref(_format()), 0, 0, _CALLBACK_NULL)
        if rc != _MMSYSERR_NOERROR:
            raise SprechenError("SPRECHEN_MIKROFON", f"Windows gibt das Mikrofon nicht her (Code {rc})")
        self._m, self._h = m, h
        groesse = RATE * 2 * PUFFER_MS // 1000
        for _ in range(8):
            puffer = ctypes.create_string_buffer(groesse)
            kopf = _WAVEHDR()
            kopf.lpData = ctypes.cast(puffer, ctypes.c_void_p)
            kopf.dwBufferLength = groesse
            kopf.dwFlags = 0
            m.waveInPrepareHeader(h, ctypes.byref(kopf), ctypes.sizeof(kopf))
            m.waveInAddBuffer(h, ctypes.byref(kopf), ctypes.sizeof(kopf))
            self._puffer.append(puffer)
            self._koepfe.append(kopf)
        rc = m.waveInStart(h)
        if rc != _MMSYSERR_NOERROR:
            self._schliessen()
            raise SprechenError("SPRECHEN_MIKROFON", f"Aufnahme startet nicht (Code {rc})")
        self.seit = time.monotonic()
        self._thread = threading.Thread(target=self._lauf, name="mikrofon", daemon=True)
        self._thread.start()

    def sekunden(self) -> int:
        return int(time.monotonic() - self.seit) if self.seit else 0

    def _einsammeln(self) -> None:
        m, h = self._m, self._h
        for kopf, puffer in zip(self._koepfe, self._puffer):
            if kopf.dwFlags & _WHDR_DONE:
                n = int(kopf.dwBytesRecorded)
                if n:
                    stueck = puffer.raw[:n]
                    with self._lock:
                        self._daten += stueck
                    self.pegel = _pegel(stueck)
                if not self._stopp.is_set():
                    kopf.dwBytesRecorded = 0
                    kopf.dwFlags &= ~_WHDR_DONE
                    m.waveInAddBuffer(h, ctypes.byref(kopf), ctypes.sizeof(kopf))

    def _lauf(self) -> None:
        while not self._stopp.is_set():
            self._einsammeln()
            if time.monotonic() - self.seit >= self.max_s:
                self.voll = True
                break
            time.sleep(PUFFER_MS / 2000)

    def laeuft(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stopp(self) -> bytes:
        if self._h is None:
            return bytes(self._daten)
        self._stopp.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        m, h = self._m, self._h
        try:
            m.waveInStop(h)
            m.waveInReset(h)
            time.sleep(0.02)
            self._einsammeln()
        finally:
            self._schliessen()
        return bytes(self._daten)

    def _schliessen(self) -> None:
        m, h = self._m, self._h
        if h is None:
            return
        for kopf in self._koepfe:
            try:
                m.waveInUnprepareHeader(h, ctypes.byref(kopf), ctypes.sizeof(kopf))
            except Exception:
                pass
        try:
            m.waveInClose(h)
        except Exception:
            pass
        self._h = None


def _pegel(pcm: bytes) -> float:
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    import array
    a = array.array("h")
    a.frombytes(pcm[:n * 2])
    s = 0
    for v in a:
        s += v * v
    return min(1.0, (s / n) ** 0.5 / 8000.0)


def wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def threads_wahl(kerne: int | None) -> int:
    k = int(kerne or os.cpu_count() or 2)
    return max(1, min(4, k - 1))


def text_saeubern(roh: str) -> str:
    import re
    t = re.sub(r"[\[(][^\])]{0,40}[\])]", " ", roh or "")
    t = " ".join(t.split())
    return t.strip()


BLOCKIERT_CODES = {0xC0E90002, 0xC0000428, 0xC000007B, 0xC0000135}
BLOCKIERT_TEXT = ("Windows hat einen Baustein fürs Sprechen blockiert (Smart App Control lässt nur signierte Programmteile laden). Tippen geht "
                  "weiter wie gewohnt; Sprechen kommt, sobald die Bausteine signiert sind.")
_SEM_FAILCRITICALERRORS, _SEM_NOOPENFILEERRORBOX = 0x0001, 0x8000


def blockiert(returncode: int | None) -> bool:
    if returncode is None:
        return False
    return (int(returncode) & 0xFFFFFFFF) in BLOCKIERT_CODES


def _ohne_windows_fenster() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetErrorMode(k32.SetErrorMode(0) | _SEM_FAILCRITICALERRORS | _SEM_NOOPENFILEERRORBOX)
    except Exception:
        pass


def erkennen(ordner: SprachOrdner, pcm: bytes, *, threads: int = 4, sprache: str = "de", laufen=subprocess.run, windows=None, hoerer=None) -> str:
    w = WINDOWS_ERKENNER if windows is None else windows
    if len(pcm) < RATE * 2 // 2:
        raise SprechenError("SPRECHEN_LEER", "die Aufnahme war zu kurz")
    hoer_da = hoerer is not None and ordner.hoer_da()
    whisper_da = ordner.da() and not ordner.blockiert()
    if not hoer_da and not whisper_da and not w.verfuegbar(sprache):
        if ordner.da():
            raise SprechenError("SPRECHEN_BLOCKIERT", BLOCKIERT_TEXT)
        raise SprechenError("SPRECHEN_FEHLT", "das Hör-Modell fehlt noch")
    app_core.ensure_plain_directory(ordner.arbeit)
    basis = ordner.arbeit / f"aufnahme-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    wav = basis.with_suffix(".wav")
    txt = basis.with_suffix(".txt")
    try:
        daten = wav_bytes(pcm)
        wav.write_bytes(daten)
        roh = ""
        if hoer_da:
            try:
                roh = hoerer(daten)
            except app_core.AppError as exc:
                if not whisper_da and not w.verfuegbar(sprache):
                    raise SprechenError("SPRECHEN_ERKENNUNG", exc.detail) from None
                roh = ""
        if roh:
            pass
        elif whisper_da:
            try:
                roh = _whisper(ordner, wav, basis, txt, threads=threads, sprache=sprache, laufen=laufen)
            except SprechenError as exc:
                if exc.code != "SPRECHEN_BLOCKIERT":
                    raise
                ordner.blockiert_merken()
                if not w.verfuegbar(sprache):
                    raise
                roh = w.erkennen(wav, sprache)
        else:
            roh = w.erkennen(wav, sprache)
        text = text_saeubern(roh)
        if not text:
            raise SprechenError("SPRECHEN_LEER", "da war nichts zu verstehen")
        return text
    finally:
        for p in (wav, txt):
            try:
                p.unlink()
            except OSError:
                pass


def _whisper(ordner: SprachOrdner, wav: Path, basis: Path, txt: Path, *, threads: int, sprache: str, laufen) -> str:
    cmd = [str(ordner.cli), "-m", str(ordner.modell), "-f", str(wav), "-l", sprache, "-t", str(int(threads)), "-nt", "-np", "-otxt", "-of", str(basis)]
    _ohne_windows_fenster()
    try:
        r = laufen(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ERKENNEN_TIMEOUT_S,
                   creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0, cwd=str(ordner.laufzeit_dir))
    except subprocess.TimeoutExpired:
        raise SprechenError("SPRECHEN_ERKENNUNG", "das Verstehen hat zu lange gedauert") from None
    except OSError as exc:
        raise SprechenError("SPRECHEN_ERKENNUNG", f"whisper-cli startet nicht ({exc.__class__.__name__})") from None
    if blockiert(getattr(r, "returncode", 0)):
        raise SprechenError("SPRECHEN_BLOCKIERT", BLOCKIERT_TEXT)
    if getattr(r, "returncode", 1) != 0:
        rest = (getattr(r, "stderr", "") or "")[-300:].strip().replace("\n", " ")
        raise SprechenError("SPRECHEN_ERKENNUNG", f"whisper-cli meldet Code {r.returncode}: {rest}")
    try:
        return txt.read_text(encoding="utf-8")
    except OSError:
        return getattr(r, "stdout", "") or ""


class Steuerung:

    def __init__(self, ordner: SprachOrdner, *, threads: int = 4, log: Callable[[str], None] = lambda s: None,
                 aufnahme_klasse=Aufnahme, erkenner=None, holer=None, windows=None, server=None, geraete_ermitteln=ki_laufzeit.geraete_ermitteln) -> None:
        self.ordner = ordner
        self.threads = threads
        self.log = log
        self._aufnahme_klasse = aufnahme_klasse
        self._windows = windows
        self.server = server or ki_laufzeit.KiServer(ordner.ki)
        self._geraete_ermitteln = geraete_ermitteln
        self._ruhe: threading.Timer | None = None
        self._server_lock = threading.Lock()
        self._notweg_bis = 0.0
        self.sprache = "de"
        self._erkenner = erkenner or (lambda pcm: erkennen(ordner, pcm, threads=threads, sprache=self.sprache, windows=self._w(), hoerer=self._hoeren))
        self._holer = holer or (lambda fortschritt: holen(ordner, fortschritt=fortschritt))
        self._lock = threading.Lock()
        self.phase = "aus"
        self.meldung = ""
        self.text = ""
        self.fortschritt = {"was": "", "done": 0, "gesamt": 0}
        self._aufnahme: Aufnahme | None = None
        self._thread: threading.Thread | None = None

    def _w(self):
        return WINDOWS_ERKENNER if self._windows is None else self._windows

    def bereit_ohne_download(self) -> bool:
        return self.ordner.hoer_da() or (self.ordner.da() and not self.ordner.blockiert()) or self._w().verfuegbar()

    def _gut_bereit(self) -> bool:
        return self.ordner.hoer_da() or (self.ordner.da() and not self.ordner.blockiert())

    def _hoeren(self, wav: bytes) -> str:
        with self._server_lock:
            if self._ruhe is not None:
                self._ruhe.cancel()
                self._ruhe = None
            if not self.server.laeuft():
                wahl = ki_laufzeit.waehlen_hoeren(self._geraete_ermitteln(self.ordner.ki.server_exe))
                self.server.start(wahl, hoeren=True, threads=self.threads if wahl.geraet is None else None)
                self.log(f"OK sprechen hörmodell {wahl.geraet.kennung if wahl.geraet else 'cpu'}")
            try:
                return self.server.hoeren(wav)
            finally:
                self._ruhe = threading.Timer(HOER_RUHE_S, self._hoer_server_stoppen)
                self._ruhe.daemon = True
                self._ruhe.start()

    def _hoer_server_stoppen(self) -> None:
        with self._server_lock:
            self._ruhe = None
            if self.server.laeuft():
                self.server.stop()
                self.log("OK sprechen hörmodell entladen (Ruhe)")

    def beenden(self) -> None:
        self.abbrechen()
        with self._server_lock:
            if self._ruhe is not None:
                self._ruhe.cancel()
                self._ruhe = None
        self.server.stop()

    def stand(self) -> dict:
        with self._lock:
            if self.phase == "aufnahme" and self._aufnahme is not None and self._aufnahme.voll and not self._aufnahme.laeuft():
                self._erkennen_starten()
            return self._schnappschuss()

    def start(self) -> dict:
        with self._lock:
            if self.phase in ("holen", "erkennen", "aufnahme"):
                return self._schnappschuss()
            if not self._gut_bereit() and time.monotonic() >= self._notweg_bis:
                self.phase, self.meldung = "holen", ""
                self.fortschritt = {"was": "Hör-Modell", "done": 0, "gesamt": HOLEN_GESAMT}
                self._thread = threading.Thread(target=self._holen_lauf, name="sprache-holen", daemon=True)
                self._thread.start()
                return self._schnappschuss()
            if not mikrofon_da():
                self.phase, self.meldung = "fehler", "Windows findet kein Mikrofon. Ist eines angeschlossen und unter Einstellungen → Datenschutz → Mikrofon für Apps erlaubt?"
                return self._schnappschuss()
            a = self._aufnahme_klasse()
            try:
                a.start()
            except app_core.AppError as exc:
                self.phase, self.meldung = "fehler", f"{exc.detail}. Unter Windows-Einstellungen → Datenschutz → Mikrofon muss der Zugriff für Apps erlaubt sein."
                return self._schnappschuss()
            self._aufnahme = a
            self.phase, self.meldung, self.text = "aufnahme", "", ""
            self.log("OK sprechen aufnahme start")
            return self._schnappschuss()

    def stopp(self) -> dict:
        with self._lock:
            if self.phase == "aufnahme":
                self._erkennen_starten()
            return self._schnappschuss()

    def abbrechen(self) -> dict:
        with self._lock:
            if self._aufnahme is not None:
                try:
                    self._aufnahme.stopp()
                except Exception:
                    pass
                self._aufnahme = None
            if self.phase in ("aufnahme", "fertig", "fehler", "bereit"):
                self.phase, self.text, self.meldung = "aus", "", ""
            return self._schnappschuss()

    def _schnappschuss(self) -> dict:
        d = {"phase": self.phase, "meldung": self.meldung, "text": "", "fortschritt": dict(self.fortschritt),
             "sekunden": self._aufnahme.sekunden() if self._aufnahme else 0, "pegel": round(self._aufnahme.pegel, 2) if self._aufnahme else 0.0,
             "da": self.bereit_ohne_download(), "mikrofon": mikrofon_da()}
        if self.phase == "fertig":
            d["text"], self.text, self.phase = self.text, "", "aus"
        elif self.phase == "fehler":
            self.phase = "aus"
        return d


    def _erkennen_starten(self) -> None:
        a = self._aufnahme
        self.phase = "erkennen"
        self._thread = threading.Thread(target=self._erkennen_lauf, args=(a,), name="sprache-erkennen", daemon=True)
        self._thread.start()

    def _erkennen_lauf(self, a) -> None:
        t0 = time.monotonic()
        try:
            pcm = a.stopp() if a is not None else b""
            text = self._erkenner(pcm)
            with self._lock:
                if self.phase == "erkennen":
                    self.phase, self.text = "fertig", text
            self.log(f"OK sprechen erkannt {len(pcm) // (RATE * 2)} s Ton in {time.monotonic() - t0:.1f} s, {len(text)} Zeichen")
        except app_core.AppError as exc:
            with self._lock:
                self.phase, self.meldung = "fehler", _menschlich(exc)
            self.log(f"INFO sprechen {exc.code}: {exc.detail}")
        except Exception as exc:
            with self._lock:
                self.phase, self.meldung = "fehler", "Das Verstehen ist schiefgegangen; das Programm hat es notiert."
            self.log(f"FEHLER sprechen {type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self._aufnahme = None

    def _holen_lauf(self) -> None:
        def fortschritt(was: str, done: int, gesamt: int) -> None:
            with self._lock:
                self.fortschritt = {"was": was, "done": done, "gesamt": gesamt}
        try:
            self._holer(fortschritt)
            with self._lock:
                self.phase, self.meldung = "bereit", ""
            self.log("OK sprechen laufzeit und modell da")
        except app_core.AppError as exc:
            with self._lock:
                if self._w().verfuegbar():
                    self._notweg_bis = time.monotonic() + NOTWEG_S
                    self.phase, self.meldung = "bereit", ""
                else:
                    self.phase, self.meldung = "fehler", "Das Hör-Modell ist noch nicht da; bitte gleich noch einmal auf das Mikrofon drücken." if exc.code == "KI_DOWNLOAD" else _menschlich(exc)
            self.log(f"INFO sprechen holen {exc.code}: {exc.detail}")
        except Exception as exc:
            with self._lock:
                self.phase, self.meldung = "fehler", "Das Hör-Modell konnte nicht geholt werden; das Programm hat es notiert."
            self.log(f"FEHLER sprechen holen {type(exc).__name__}: {exc}")


def _menschlich(exc: app_core.AppError) -> str:
    if exc.code == "SPRECHEN_LEER":
        return "Da war nichts zu verstehen. Mikrofon drücken, sprechen, noch einmal drücken."
    if exc.code == "SPRECHEN_MIKROFON":
        return f"{exc.detail}."
    return f"Verstehen hat nicht geklappt: {exc.detail}."
