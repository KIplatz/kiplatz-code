# SPDX-License-Identifier: AGPL-3.0-or-later
import ast
import re
from pathlib import Path

import app_web
from test_app_web import _api

HIER = Path(__file__).resolve().parents[1]


def _quelle(datei: str) -> tuple[str, ast.Module]:
    text = (HIER / datei).read_text(encoding="utf-8")
    return text, ast.parse(text)


def _api_methoden() -> dict[str, str]:
    text, baum = _quelle("app_web.py")
    for k in baum.body:
        if isinstance(k, ast.ClassDef) and k.name == "Api":
            return {f.name: ast.get_source_segment(text, f) for f in k.body if isinstance(f, ast.FunctionDef) and not f.name.startswith("_")}
    raise AssertionError("class Api fehlt")


def test_jeder_admin_aufruf_steht_in_der_liste_und_prueft_unter_seinem_namen():
    text, baum = _quelle("community.py")
    mit_schluessel = {f.name for f in ast.walk(baum) if isinstance(f, ast.FunctionDef) and "mit_schluessel=True" in ast.get_source_segment(text, f)}
    methoden = _api_methoden()
    beide = {"speicher_stand", "wissen_seite_lesen", "wissen_entfernen"}
    noetig = {n for n, q in methoden.items() if set(re.findall(r"self\._community\.(\w+)\(", q)) & mit_schluessel} - beide
    assert noetig <= app_web.ADMIN_FENSTER, sorted(noetig - app_web.ADMIN_FENSTER)
    for name in app_web.ADMIN_FENSTER:
        assert name in methoden, name
        assert f'_guarded("{name}"' in methoden[name], f"{name} ruft _guarded nicht unter seinem eigenen Namen"
    for name in beide:
        assert name not in app_web.ADMIN_FENSTER and "self._admin_fenster()" in methoden[name], name


def test_jede_geraete_admin_stelle_ist_bewusst_eingeordnet():
    am_geraet = {"__init__", "_pruefstand_lauf", "_neuer_bau_faellig", "_vorab_frei", "_schnittstelle_antwort", "frage", "_admin_fenster"}
    text, baum = _quelle("app_web.py")
    gefunden = set()
    for k in baum.body:
        if isinstance(k, ast.ClassDef) and k.name == "Api":
            for f in k.body:
                if isinstance(f, ast.FunctionDef) and "self._community.ist_admin()" in ast.get_source_segment(text, f):
                    gefunden.add(f.name)
    assert gefunden <= am_geraet, sorted(gefunden - am_geraet)
    methoden = {f.name: ast.get_source_segment(text, f) for k in baum.body if isinstance(k, ast.ClassDef) and k.name == "Api"
                for f in k.body if isinstance(f, ast.FunctionDef)}
    assert "admin = self._admin_fenster()" in methoden["_credits_dict"] and "admin = self._admin_fenster()" in methoden["_wissen_dict"]


def test_ohne_konto_kein_admin_im_fenster_mit_konto_schon(tmp_path, monkeypatch):
    api, _fake, _dl = _api(tmp_path)
    monkeypatch.setattr(api._community, "ist_admin", lambda: True)
    monkeypatch.setattr(api._community, "not_aus_setzen", lambda an, grund="": {"an": an, "grund": grund}, raising=False)
    api._ki.einstellung_setzen(konto=None)
    z = api.zustand()["daten"]
    assert z["admin"] is False and z["konto"] is None and z["credits"]["admin"] is False
    r = api.not_aus_setzen(True, "Probe")
    assert not r["ok"] and r["code"] == "NUR_ADMIN"
    api._ki.einstellung_setzen(konto={"name": "Huber", "sub": "7"})
    z = api.zustand()["daten"]
    assert z["admin"] is True and z["konto"] == {"name": "Huber", "sub": "7"}
    api._ki.einstellung_setzen(konto=None)
    assert api._community.ist_admin() is True and api._admin_fenster() is False


def test_ein_mitglied_ohne_admin_bleibt_auch_mit_konto_ohne_admin(tmp_path, monkeypatch):
    api, _fake, _dl = _api(tmp_path)
    monkeypatch.setattr(api._community, "ist_admin", lambda: False)
    api._ki.einstellung_setzen(konto={"name": "Anna", "sub": "8"})
    assert api.zustand()["daten"]["admin"] is False
    assert api.community_geraete()["code"] == "NUR_ADMIN"


def test_das_fenster_verlaesst_die_admin_seite_und_fragt_beim_abmelden_ehrlich():
    html = (HIER / "webapp" / "index.html").read_text(encoding="utf-8")
    block = html[html.index("function adminZeigen(an)"):html.index("adminBereit = true;", html.index("function adminZeigen(an)"))]
    assert 'if (!an && $("#page-admin").classList.contains("active")) zeige("gespraeche");' in block
    assert "der Browser meldet dich auch auf der Website, im Platzl und in der Werkstatt ab" in html
