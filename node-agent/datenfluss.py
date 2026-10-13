# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import threading
import time
import urllib.request
from collections import deque
from urllib.parse import urlsplit

_EINTRAEGE: deque = deque(maxlen=300)
_SUMME: dict[str, dict] = {}
_LOCK = threading.Lock()


def host_von(adresse: str) -> str:
    try:
        return urlsplit(str(adresse)).hostname or str(adresse)[:60]
    except ValueError:
        return str(adresse)[:60]


def melden(adresse: str, zweck: str, raus: int = 0, rein: int = 0) -> None:
    host = host_von(adresse)
    with _LOCK:
        _EINTRAEGE.append({"zeit": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": host, "zweck": str(zweck)[:80], "raus": int(raus or 0), "rein": int(rein or 0)})
        s = _SUMME.setdefault(host, {"host": host, "anfragen": 0, "raus": 0, "rein": 0, "zwecke": [], "zuletzt": ""})
        s["anfragen"] += 1
        s["raus"] += int(raus or 0)
        s["rein"] += int(rein or 0)
        s["zuletzt"] = _EINTRAEGE[-1]["zeit"]
        if zweck and zweck not in s["zwecke"]:
            s["zwecke"] = (s["zwecke"] + [str(zweck)[:80]])[-6:]


def stand() -> dict:
    with _LOCK:
        hosts = sorted((dict(s) for s in _SUMME.values()), key=lambda s: s["anfragen"], reverse=True)
        return {"hosts": hosts, "eintraege": list(reversed(_EINTRAEGE))[:100], "gesamt": sum(s["anfragen"] for s in hosts)}


def leeren() -> None:
    with _LOCK:
        _EINTRAEGE.clear()
        _SUMME.clear()


class _Antwort:

    def __init__(self, r, adresse: str, zweck: str, raus: int) -> None:
        self._r, self._adresse, self._zweck, self._raus, self._rein, self._gemeldet = r, adresse, zweck, raus, 0, False

    def read(self, n: int = -1) -> bytes:
        b = self._r.read(n)
        self._rein += len(b)
        return b

    def __iter__(self):
        for zeile in self._r:
            self._rein += len(zeile)
            yield zeile

    def __getattr__(self, name):
        return getattr(self._r, name)

    def _melden(self) -> None:
        if not self._gemeldet:
            self._gemeldet = True
            melden(self._adresse, self._zweck, self._raus, self._rein)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._melden()
        try:
            return self._r.__exit__(*a)
        except AttributeError:
            return False

    def close(self) -> None:
        self._melden()
        try:
            self._r.close()
        except Exception:
            pass


def oeffner(zweck: str, *, basis=None):
    echt = basis or urllib.request.urlopen

    def _oeffnen(req, timeout=None, **kw):
        adresse = req.full_url if hasattr(req, "full_url") else str(req)
        raus = len(getattr(req, "data", None) or b"")
        try:
            r = echt(req, timeout=timeout, **kw) if timeout is not None else echt(req, **kw)
        except Exception:
            melden(adresse, zweck + " (fehlgeschlagen)", raus, 0)
            raise
        return _Antwort(r, adresse, zweck, raus)

    return _oeffnen
