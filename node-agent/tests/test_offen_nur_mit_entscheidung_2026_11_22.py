# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_core

README = Path(__file__).resolve().parents[1] / "README.md"
VERMERK = "Betreiber entscheidet"
_OFFEN = re.compile(r"\bOffen\b\s*[:,(]|\*\*Offen\b", re.I)


def abschnitt(text: str, bau: str) -> str:
    m = re.search(rf"^## Bau {re.escape(bau)}\b.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def offene_ohne_entscheidung(text: str) -> list[str]:
    return [z.strip() for z in text.splitlines() if _OFFEN.search(z) and VERMERK not in z]


def test_laufender_bau_hat_nur_offenes_mit_entscheidung():
    if not README.exists():
        return
    text = README.read_text(encoding="utf-8")
    teil = abschnitt(text, app_core.APP_BUILD)
    funde = offene_ohne_entscheidung(teil)
    assert not funde, ("Im Abschnitt des laufenden Baus steht Offenes ohne Entscheidung des Betreibers. Selbst lösen, bevor fertig gemeldet wird, "
                       f"oder als „{VERMERK}: …“ mit Optionen markieren:\n" + "\n".join(funde))


def test_gegenprobe_findet_offenes():
    probe = ("## Bau 2099-01-01a: Probe\n\n- **Offen:** die Ausgehzeit liest das Modell falsch.\n"
             "- **Offen (Betreiber entscheidet: Geld für ein größeres Modell):** A oder B.\n- Erledigt: alles andere.\n## Bau 2098-12-31a: alt\n"
             "- **Offen:** steht in einem alten Abschnitt.\n")
    teil = abschnitt(probe, "2099-01-01a")
    assert offene_ohne_entscheidung(teil) == ["- **Offen:** die Ausgehzeit liest das Modell falsch."]
    assert "alten Abschnitt" not in teil
    assert offene_ohne_entscheidung("- Offenheit und offene Fragen sind kein Befund.") == []
