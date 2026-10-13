# SPDX-License-Identifier: AGPL-3.0-or-later
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web
import ki_laufzeit

HIER = Path(__file__).resolve().parent.parent


def test_the_window_names_kiplatz_never_the_maker():
    assert app_web.ki_anzeigename("Ministral 3 14B") == "KIplatz (großes Modell)"
    assert app_web.ki_anzeigename("Ministral 3 8B") == "KIplatz (mittleres Modell)"
    assert app_web.ki_anzeigename("Ministral 3 3B") == "KIplatz (kleines Modell)"
    assert app_web.ki_anzeigename("") == "KIplatz"
    for m in ki_laufzeit.MODELLE.values():
        assert "Ministral" not in app_web.ki_anzeigename(m.name) and "Mistral" not in app_web.ki_anzeigename(m.name)


def test_no_status_line_in_the_switch_on_path_uses_the_raw_model_name():
    quelle = (HIER / "app_web.py").read_text(encoding="utf-8")
    assert not re.search(r"_melden\(f\"\{wahl\.modell\.name\}", quelle)
    assert "plan.append((wahl.modell.name," not in quelle
    assert 'f"{wahl.modell.name} läuft auf' not in quelle
