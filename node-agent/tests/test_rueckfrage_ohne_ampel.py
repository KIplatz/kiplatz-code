# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ki_laufzeit as kl
import schriftstueck
from test_app_web import _api

ANHANG = ("\n\nDatei „IMG_8635.png“ (Foto, Text erkannt):\nDie Feuerwehren Gmunden und Altmünster wurden am Sonntag zur Mittagszeit "
          "zu einem Verkehrsunfall alarmiert. Die B144 war erschwert passierbar.")


def _mit_modell(tmp_path, antwort):
    api, fake, _ = _api(tmp_path)
    api._ki_bereit_machen()
    gesehen = {}

    def frage(nachrichten, *, zusatz="", **kw):
        gesehen["zusatz"] = zusatz
        return kl.Antwort(antwort, 10, 8, 0.1)
    fake.frage = frage
    return api, gesehen


def test_reading_an_attached_photo_gets_no_question_round(tmp_path):
    api, gesehen = _mit_modell(tmp_path, "Die Feuerwehren Gmunden und Altmünster wurden am Sonntag zur Mittagszeit zu einem Verkehrsunfall alarmiert.")
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": "Lies den Text und schreib ihn mir hin" + ANHANG}], [], "ein Mitglied")
    assert "JETZT NOCH NICHT" not in gesehen["zusatz"] and not text.startswith(schriftstueck.VORSPANN)
    assert ls["gemacht"] != "nachgefragt"


def test_a_real_question_round_carries_no_traffic_light(tmp_path):
    api, gesehen = _mit_modell(tmp_path, "Damit ich das gut machen kann, fehlen mir noch:\n- Für wen der Text ist\n- Wie lang\n- Welcher Ton\n"
                                         "Antworte mir Punkt für Punkt, oder schreib „weiter“.")
    text, ls = api._antwort_fuer_mitglied([{"role": "user", "content": "Schreib mir einen Text über den Gmundner Traunsee"}], [], "ein Mitglied")
    assert "JETZT NOCH NICHT" in gesehen["zusatz"] and text.startswith(schriftstueck.VORSPANN)
    assert ls["gemacht"] == "nachgefragt" and ls["erfunden"] == "nichts, es wurde nur nachgefragt"
    assert ls["pruefung"].get("rot", 0) == 0 and not ls["pruefung"].get("saetze")
