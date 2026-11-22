# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_web
import belege

EURO = ("As of 2026, the euro is used by 21 European Union countries as their official currency.\n\n"
        "Outside the EU, the euro is also used by several non-member states, such as Andorra and Monaco.\n"
        "– Microstates like Liechtenstein, Malta’s dependencies, and others.")


def test_kandidaten_vom_ende_her_mit_name_oder_zahl():
    k = belege.anhang_kandidaten(EURO, "Which countries use the euro?")
    assert k[0].startswith("– Microstates like Liechtenstein")
    assert len(k) == 2 and not any(s.startswith("As of 2026") for s in k)
    assert belege.anhang_kandidaten("South Africa has twelve official languages. These languages come from South Africa and Namibia.",
                                    "How many official languages does South Africa have?") == ["These languages come from South Africa and Namibia."]


def test_kein_kandidat_ohne_name_und_zahl_oder_nur_aus_der_frage():
    assert belege.anhang_kandidaten("Canberra is the capital. It was a compromise.", "What is the capital of Australia?") == []
    assert belege.anhang_kandidaten("Ja. Wien ist schön.", "Ist Wien schön?") == []
    assert belege.anhang_kandidaten("Antwort.\n\nStand: nachgeschaut am 22.11.2026.", "x") == []


def test_notiz_form_und_auswertung_passen_zusammen():
    n = app_web.anhang_notiz([("Microstates like Liechtenstein, Malta dependencies.", 0.0), ("Andorra uses it; really.", 0.5), ("x 1", 1.0)])
    assert n.startswith("Anhang: „Microstates like Liechtenstein, Malta depende…“ R0; „Andorra uses it, really,…“ R0,5. ")
    for danach in ("Gestrichen: x. ", "keine Antwort: y. ", "1 Satz z. ", ""):
        notiz = "Vermischt: a. " + n + danach
        treffer = re.findall(r"„([^“]*)“ R(\d+(?:,\d+)?)(?=[;.])", notiz[notiz.find("Anhang: "):])
        assert [r for _s, r in treffer] == ["0", "0,5"], danach
    assert app_web.anhang_notiz([]) == ""


def test_nur_in_der_pruefrunde():
    quelle = Path(app_web.__file__).read_text(encoding="utf-8")
    assert 'if getattr(_PRUEFRUNDE, "an", False) and isinstance(getattr(_ANHANG, "liste", None), list) and richter is not None' in quelle
    assert "_ANHANG.liste, _ANHANG.zeit = [], 0.0" in quelle and "_ANHANG.liste[:] = []" in quelle and "anhang_liste, _ANHANG.liste = list(getattr(_ANHANG, \"liste\", None) or []), None" in quelle
