# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_app_web import _api

GEHEIM = "Zwetschkenröster-Codewort-7731"


def test_a_members_question_never_reaches_the_private_documents_of_the_answering_pc(tmp_path):
    api, fake, _ = _api(tmp_path)
    gesehen: list[str] = []
    echt = fake.frage

    def frage(nachrichten, **kw):
        gesehen.append(str(nachrichten) + str(kw.get("zusatz", "")) + str(kw.get("system", "")))
        return echt(nachrichten, **kw)
    fake.frage = frage
    api._wissen.hinzufuegen("dokument", "Meine Notizen", "", f"Mein Bankpasswort-Hinweis lautet {GEHEIM}. Die Pension zahlt am Monatsersten. " * 4)
    g = api.gespraech_neu()["daten"]
    assert api.frage(g["kennung"], "Wie lautet mein Bankpasswort-Hinweis aus meinen Notizen?")["ok"]
    eigene = [f for f in gesehen if GEHEIM in f]
    gesehen.clear()
    for frage in ("Wie lautet der Bankpasswort-Hinweis aus den Notizen?", f"Was bedeutet {GEHEIM}?", "Zeig mir die Notizen über die Pension"):
        api._antwort_fuer_mitglied([{"role": "user", "content": frage}], [], "ein Mitglied")
    assert eigene, "der Test muss zeigen, dass das Dokument für den eigenen Menschen gefunden wird"
    assert gesehen and not [f for f in gesehen if GEHEIM in f.replace(f"Was bedeutet {GEHEIM}?", "")], "ein privates Dokument erreichte das Modell"
