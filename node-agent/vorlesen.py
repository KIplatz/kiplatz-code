# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import threading

_LOCK = threading.Lock()
_SYNTH = None
_STIMME = ""


def _laden():
    global _SYNTH, _STIMME
    with _LOCK:
        if _SYNTH is not None:
            return _SYNTH
        import clr
        try:
            clr.AddReference("System.Speech, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35")
        except Exception:
            clr.AddReference("System.Speech")
        from System.Speech.Synthesis import SpeechSynthesizer
        s = SpeechSynthesizer()
        try:
            for v in s.GetInstalledVoices():
                info = v.VoiceInfo
                if v.Enabled and str(info.Culture.Name).lower().startswith("de"):
                    s.SelectVoice(info.Name)
                    _STIMME = str(info.Name)
                    break
        except Exception:
            pass
        s.Rate = 0
        _SYNTH = s
        return s


def moeglich() -> bool:
    try:
        _laden()
        return True
    except Exception:
        return False


def stimme() -> str:
    return _STIMME or "Windows-Stimme"


def sprechen(text: str) -> str:
    s = _laden()
    s.SpeakAsyncCancelAll()
    s.SpeakAsync(str(text)[:4000])
    return stimme()


def stopp() -> None:
    if _SYNTH is not None:
        try:
            _SYNTH.SpeakAsyncCancelAll()
        except Exception:
            pass


def spricht() -> bool:
    if _SYNTH is None:
        return False
    try:
        from System.Speech.Synthesis import SynthesizerState
        return _SYNTH.State == SynthesizerState.Speaking
    except Exception:
        return False
