# SPDX-License-Identifier: AGPL-3.0-or-later
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_web

HTML = (app_web.webapp_dir() / app_web.INDEX_NAME).read_text(encoding="utf-8")


def _gliederung() -> dict[str, list[str]]:
    block = HTML[HTML.index("const GLIEDERUNG = {"):HTML.index("const REITER = {")]
    seiten: dict[str, list[str]] = {}
    for m in re.finditer(r"\n    (\w+): \[(.*?)\n    \],", block, re.S):
        seiten[m.group(1)] = re.findall(r'\["([^"\]]+)", "[^"]*"(?:, "fest")?\]', m.group(2))
    return seiten


def _abschnitt(seite: str) -> str:
    a = HTML.index(f'id="page-{seite}"')
    b = HTML.find('<section class="page"', a + 10)
    return HTML[a:b if b > 0 else len(HTML)]


def test_jede_karte_der_gliederung_gibt_es_auf_ihrer_seite():
    g = _gliederung()
    assert {"einstellungen", "community", "mitrechnen", "wissen", "skills", "admin"} <= set(g)
    for seite, titel in g.items():
        text = _abschnitt(seite)
        h3 = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<h3[^>]*>(.*?)</h3>", text, re.S)]
        for t in titel:
            assert any(x.startswith(t) for x in h3), f"{seite}: keine Karte mit dem Titel „{t}“"


def test_reiter_statt_klapper_und_kontomenue_statt_bereiche():
    assert "function klappbar(" not in HTML and "kiplatz.klappAuf" not in HTML and 'id="bereiche"' not in HTML
    nav = HTML[HTML.index('<ul class="navlist bereiche-fest" id="nav">'):HTML.index("</ul>", HTML.index('id="nav">'))]
    assert re.findall(r'data-page="([a-z]+)"', nav) == ["platzl", "skills", "meineki", "community"]
    assert ".bereiche-fest li { padding: 6px 10px; font-size: 13px; }" in HTML
    menue = HTML[HTML.index('id="konto-menu"'):HTML.index("</div>", HTML.index('id="konto-menu"'))]
    assert re.findall(r'data-(?:page|tun)="([a-z]+)"', menue) == ["einstellungen", "admin", "ueber", "beenden"] and 'id="nav-admin"' in menue
    block = HTML[HTML.index("const REITER = {"):HTML.index("const ELTERN")]
    assert re.findall(r'\["(\w+)", "([^"]+)"\]', block) == [("einstellungen", "Allgemein"), ("einstellungen", "KI und Antworten"), ("mitrechnen", "Rechenkraft teilen"),
        ("wissen", "Wissen"), ("datenfluss", "Datenschutz"), ("einstellungen", "Für Fortgeschrittene"), ("einstellungen", "Hilfe und Wartung"),
        ("community", "Überblick"), ("community", "Konto und Geräte"), ("pruefen", "Antworten prüfen"), ("bestenliste", "Bestenliste"), ("wiki", "Wiki"), ("community", "Rückmeldungen")]
    assert 'id="reiter"' in HTML and "function reiterZeichnen" in HTML and 'querySelectorAll("#nav li[data-page]")' in HTML


def test_jede_karte_genau_einmal():
    assert HTML.count("<h3>Die KI zum Fragen</h3>") == 1 and 'id="ki-kv"' not in HTML and "btn-ki-an3" not in HTML
    d = _abschnitt("datenfluss")
    assert "<h3>Gedächtnis</h3>" in d and "<h3>Lernen</h3>" in d and "<h3>Gedächtnis</h3>" not in _abschnitt("einstellungen")
    g = _gliederung()
    alle = [t for seite in g for t in g[seite]]
    assert len(alle) == len(set(alle)), [t for t in alle if alle.count(t) > 1]


def test_kein_skript_greift_auf_huellen_zu_die_gliedern_wegwirft():
    from html.parser import HTMLParser

    seiten = {f"page-{s}" for s in _gliederung()}

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stapel: list[tuple[str, bool, bool]] = []
            self.verloren: set[str] = set()

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            oben = self.stapel[-1] if self.stapel else ("", False, False)
            klassen = (a.get("class") or "").split()
            in_scroll = oben[1] or ("scroll" in klassen and any(t == "section" for t, *_ in self.stapel) and self._seite)
            in_karte = oben[2] or "card" in klassen
            if in_scroll and not in_karte and a.get("id") and "scroll" not in klassen:
                self.verloren.add(a["id"])
            if tag == "section":
                self._seite = a.get("id") in seiten
            if tag not in ("br", "img", "input", "meta", "link", "hr", "source", "wbr"):
                self.stapel.append((tag, in_scroll, in_karte))

        def handle_endtag(self, tag):
            while self.stapel:
                if self.stapel.pop()[0] == tag:
                    break

        _seite = False

    p = P()
    p.feed(HTML[: HTML.index("<script")])
    skript = HTML[HTML.index("<script"):]
    angesprochen = {i for i in p.verloren if f'"#{i}"' in skript or f"'#{i}'" in skript or f'getElementById("{i}")' in skript}
    assert not angesprochen, f"Skript spricht Hüllen an, die gliedern() entfernt: {sorted(angesprochen)}"


def test_zebra_und_groessere_gruppentitel():
    assert "--zebra:" in HTML and HTML.count("--zebra:") == 2
    assert '.gruppe > .card.zebra { background: var(--zebra); }' in HTML and 'c.classList.toggle("zebra", i % 2 === 1)' in HTML
    assert ".gruppe-titel { font-size: 15px;" in HTML


def test_getoente_karten_sind_in_der_liste_nicht_schwarz():
    a = HTML.index(".gruppe > .card.tint { background: var(--surface); }")
    assert a < HTML.index(".gruppe > .card.zebra { background: var(--zebra); }")
