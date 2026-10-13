# SPDX-License-Identifier: AGPL-3.0-or-later
import re
from pathlib import Path

WWW = Path(__file__).resolve().parents[2] / "app" / "www"


def _weg_muster() -> re.Pattern:
    text = (WWW / "js" / "schnittstelle.js").read_text(encoding="utf-8")
    m = re.search(r"^const WEG = /(.+)/i;", text, re.M)
    assert m, "WEG fehlt in schnittstelle.js"
    return re.compile(m.group(1), re.I)


def test_die_abholadresse_der_antwort_besteht_die_eigene_wegepruefung():
    weg = _weg_muster()
    start = (WWW / "js" / "start.js").read_text(encoding="utf-8")
    assert '"/antwort/" + encodeURIComponent(z.laufend.kennung) + "?warten=15"' in start
    for gut in ("/antwort/a9f67bccafd86a54?warten=15", "/antwort/a9f67bccafd86a54?warten=15&seit=genommen%3A3",
                "/frage-stellen", "/hallo", "/zuhause-ablage/0123abcd"):
        assert weg.match(gut), gut
    for schlecht in ("https://fremd.example/x", "//fremd.example/x", "/antwort/x?warten=<script>", "antwort/x", "/antwort/x#a",
                     "/antwort/x?a=b c"):
        assert not weg.match(schlecht), schlecht
