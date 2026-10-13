# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sqlite3
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import wissen

DATEI = "wortindex.sqlite"
KANDIDATEN = 4


def moeglich() -> bool:
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        c.close()
        return True
    except sqlite3.Error:
        return False


class Wortindex:
    def __init__(self, pfad: Path) -> None:
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._c = sqlite3.connect(str(self.pfad), check_same_thread=False, isolation_level=None)
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA synchronous=NORMAL")
        self._c.execute("CREATE TABLE IF NOT EXISTS quellen (kennung TEXT PRIMARY KEY, marke TEXT NOT NULL, kurz TEXT NOT NULL, "
                        "privat INTEGER NOT NULL, freigegeben INTEGER NOT NULL, gueltig_bis TEXT NOT NULL DEFAULT '')")
        self._c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS abschnitte USING fts5(woerter, kennung UNINDEXED, nr UNINDEXED, hash UNINDEXED, "
                        "text UNINDEXED, beiwerk UNINDEXED, tokenize='unicode61 remove_diacritics 0')")
        self._c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS wortschatz USING fts5vocab(abschnitte, 'row')")
        self._c.execute("CREATE TABLE IF NOT EXISTS stelle (kennung TEXT NOT NULL, nr INTEGER NOT NULL, zeile INTEGER NOT NULL, PRIMARY KEY (kennung, nr))")
        self._stellen_pruefen()
        self._n: int | None = None
        self.version = 0

    def _stellen_pruefen(self) -> None:
        with self._lock:
            n_a = int(self._c.execute("SELECT count(*) FROM abschnitte").fetchone()[0])
            n_s = int(self._c.execute("SELECT count(*) FROM stelle").fetchone()[0])
            if n_a == n_s:
                return
            self._c.execute("BEGIN")
            try:
                self._c.execute("DELETE FROM stelle")
                self._c.execute("INSERT OR REPLACE INTO stelle (kennung, nr, zeile) SELECT kennung, nr, rowid FROM abschnitte")
                self._c.execute("COMMIT")
            except sqlite3.Error:
                self._c.execute("ROLLBACK")
                raise

    def _loeschen(self, kennung: str) -> None:
        self._c.execute("DELETE FROM abschnitte WHERE rowid IN (SELECT zeile FROM stelle WHERE kennung = ?)", (kennung,))
        self._c.execute("DELETE FROM stelle WHERE kennung = ?", (kennung,))

    def schliessen(self) -> None:
        with self._lock:
            self._c.close()


    def aufnehmen(self, q: wissen.Quelle, teile: list[str], toks: list[list[str]], hashes: list[str], marke: str) -> None:
        with self._lock:
            self._c.execute("BEGIN")
            try:
                self._loeschen(q.kennung)
                self._c.execute("INSERT OR REPLACE INTO quellen VALUES (?, ?, ?, ?, ?, ?)",
                                (q.kennung, str(marke), json.dumps(q.kurz(), ensure_ascii=False), int(q.privat), int(q.freigegeben), q.gueltig_bis or ""))
                for nr, (t, w, h) in enumerate(zip(teile, toks, hashes)):
                    zeile = self._c.execute("INSERT INTO abschnitte (woerter, kennung, nr, hash, text, beiwerk) VALUES (?, ?, ?, ?, ?, ?)",
                                            (" ".join(w), q.kennung, nr, h, t, int(wissen.ist_beiwerk(t)))).lastrowid
                    self._c.execute("INSERT OR REPLACE INTO stelle (kennung, nr, zeile) VALUES (?, ?, ?)", (q.kennung, nr, zeile))
                self._c.execute("COMMIT")
            except sqlite3.Error:
                self._c.execute("ROLLBACK")
                raise
            self._n = None
            self.version += 1

    def entfernen(self, kennung: str) -> bool:
        with self._lock:
            self._c.execute("BEGIN")
            self._loeschen(kennung)
            n = self._c.execute("DELETE FROM quellen WHERE kennung = ?", (kennung,)).rowcount
            self._c.execute("COMMIT")
            self._n = None
            self.version += 1
            return n > 0


    def roh_ausgeben(self, kennungen) -> list[dict]:
        ks = sorted(set(kennungen))
        out = []
        with self._lock:
            for k in ks:
                q = self._c.execute("SELECT marke, kurz, privat, freigegeben, gueltig_bis FROM quellen WHERE kennung = ?", (k,)).fetchone()
                if q is None:
                    continue
                zeilen = self._c.execute("SELECT s.nr, a.woerter, a.hash, a.text, a.beiwerk FROM stelle s JOIN abschnitte a ON a.rowid = s.zeile "
                                         "WHERE s.kennung = ? ORDER BY s.nr", (k,)).fetchall()
                out.append({"kennung": k, "marke": q[0], "kurz": q[1], "privat": int(q[2]), "freigegeben": int(q[3]), "gueltig_bis": q[4],
                            "abschnitte": [[int(nr), w, h, tx, int(bw)] for nr, w, h, tx, bw in zeilen]})
        return out

    def roh_aufnehmen(self, quellen: list[dict], weg) -> None:
        with self._lock:
            self._c.execute("BEGIN")
            try:
                for k in set(weg) | {str(d["kennung"]) for d in quellen}:
                    self._loeschen(k)
                    self._c.execute("DELETE FROM quellen WHERE kennung = ?", (k,))
                for d in quellen:
                    k = str(d["kennung"])
                    self._c.execute("INSERT INTO quellen VALUES (?, ?, ?, ?, ?, ?)",
                                    (k, str(d["marke"]), str(d["kurz"]), int(d["privat"]), int(d["freigegeben"]), str(d.get("gueltig_bis") or "")))
                    for nr, w, h, tx, bw in d["abschnitte"]:
                        zeile = self._c.execute("INSERT INTO abschnitte (woerter, kennung, nr, hash, text, beiwerk) VALUES (?, ?, ?, ?, ?, ?)",
                                                (str(w), k, int(nr), str(h), str(tx), int(bw))).lastrowid
                        self._c.execute("INSERT OR REPLACE INTO stelle (kennung, nr, zeile) VALUES (?, ?, ?)", (k, int(nr), zeile))
                self._c.execute("COMMIT")
            except (sqlite3.Error, KeyError, TypeError, ValueError):
                self._c.execute("ROLLBACK")
                raise
            self._n = None
            self.version += 1

    def kennungen(self) -> list[str]:
        with self._lock:
            return [k for (k,) in self._c.execute("SELECT kennung FROM quellen")]

    def marken(self) -> dict[str, str]:
        with self._lock:
            return {k: m for k, m in self._c.execute("SELECT kennung, marke FROM quellen")}

    def marke_setzen(self, kennung: str, marke: str) -> None:
        with self._lock:
            self._c.execute("UPDATE quellen SET marke = ? WHERE kennung = ?", (str(marke), kennung))
            self.version += 1

    def anzahl_quellen(self, *, jetzt: str | None = None) -> int:
        jetzt = jetzt or wissen._jetzt()
        with self._lock:
            r = self._c.execute("SELECT count(*) FROM quellen WHERE freigegeben = 1 AND (gueltig_bis = '' OR gueltig_bis > ?)", (jetzt,)).fetchone()
        return int(r[0]) if r else 0

    def hat(self, kennung: str) -> bool:
        with self._lock:
            return self._c.execute("SELECT 1 FROM quellen WHERE kennung = ?", (kennung,)).fetchone() is not None


    @staticmethod
    def _quelle(kurz: str) -> wissen.Quelle:
        return wissen.quelle_aus(json.loads(kurz))

    def quellen(self, *, auch_ungeprueft: bool = False, jetzt: str | None = None) -> list[wissen.Quelle]:
        jetzt = jetzt or wissen._jetzt()
        with self._lock:
            rows = self._c.execute("SELECT kurz, freigegeben, gueltig_bis FROM quellen").fetchall()
        return [self._quelle(k) for k, f, g in rows if (auch_ungeprueft or f) and (not g or g > jetzt)]

    def abschnitte_von(self, kennung: str) -> tuple[list[str], list[str]]:
        with self._lock:
            rows = self._c.execute("SELECT a.text, a.hash FROM stelle s JOIN abschnitte a ON a.rowid = s.zeile WHERE s.kennung = ? ORDER BY s.nr", (kennung,)).fetchall()
        return [t for t, _ in rows], [h for _, h in rows]

    def alle(self, *, auch_ungeprueft: bool = False, mit_hash: bool = False) -> list[tuple]:
        jetzt = wissen._jetzt()
        with self._lock:
            qs = {k: self._quelle(kurz) for k, kurz, f, g in self._c.execute("SELECT kennung, kurz, freigegeben, gueltig_bis FROM quellen")
                  if (auch_ungeprueft or f) and (not g or g > jetzt)}
            rows = self._c.execute("SELECT kennung, nr, text, hash FROM abschnitte ORDER BY kennung, nr").fetchall()
        teile: dict[str, list[str]] = {k: [] for k in qs}
        hashes: dict[str, list[str]] = {k: [] for k in qs}
        for k, _nr, t, h in rows:
            if k in teile:
                teile[k].append(t)
                hashes[k].append(h)
        return [(q, teile[k], hashes[k]) if mit_hash else (q, teile[k]) for k, q in sorted(qs.items())]

    def abschnitt(self, kennung: str, nr: int) -> tuple[wissen.Quelle, str, str] | None:
        with self._lock:
            z = self._c.execute("SELECT zeile FROM stelle WHERE kennung = ? AND nr = ?", (kennung, int(nr))).fetchone()
            r = None
            if z is not None:
                r = self._c.execute("SELECT q.kurz, a.text, a.hash FROM abschnitte a JOIN quellen q ON q.kennung = ? WHERE a.rowid = ?", (kennung, z[0])).fetchone()
        return (self._quelle(r[0]), r[1], r[2]) if r else None

    def anzahl_abschnitte(self) -> int:
        with self._lock:
            if self._n is None:
                self._n = int(self._c.execute("SELECT count(*) FROM abschnitte WHERE beiwerk = 0").fetchone()[0])
            return self._n

    def df(self, wort: str) -> int:
        with self._lock:
            r = self._c.execute("SELECT doc FROM wortschatz WHERE term = ?", (wort,)).fetchone()
        return int(r[0]) if r else 0

    def suchen(self, fw: list[str], *, n: int, privat_erlaubt: bool = True, jetzt: str | None = None) -> list[wissen.Treffer]:
        worte = sorted({w for w in fw if w.replace("_", "").isalnum()})
        if not worte or n <= 0:
            return []
        abfrage = " OR ".join(f'"{w}"' for w in worte)
        jetzt = jetzt or wissen._jetzt()
        with self._lock:
            rows = self._c.execute(
                "SELECT q.kurz, a.text, bm25(abschnitte) AS p FROM abschnitte a JOIN quellen q ON q.kennung = a.kennung "
                "WHERE abschnitte MATCH ? AND a.beiwerk = 0 AND q.freigegeben = 1 AND (q.privat = 0 OR ?) "
                "ORDER BY p, a.kennung, a.nr LIMIT ?", (abfrage, int(bool(privat_erlaubt)), KANDIDATEN * n)).fetchall()
        out = []
        for kurz, text, p in rows:
            q = self._quelle(kurz)
            if not q.gueltig(jetzt):
                continue
            out.append(wissen.Treffer(q, text, round(-float(p), 3)))
            if len(out) >= n:
                break
        return out

    def stand(self) -> dict:
        with self._lock:
            q = int(self._c.execute("SELECT count(*) FROM quellen").fetchone()[0])
        try:
            bytes_ = self.pfad.stat().st_size
        except OSError:
            bytes_ = 0
        return {"quellen": q, "abschnitte": self.anzahl_abschnitte(), "bytes": bytes_}


__all__ = ["Wortindex", "DATEI", "moeglich"]
