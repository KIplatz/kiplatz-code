# SPDX-License-Identifier: AGPL-3.0-or-later
import argparse
import ast
import importlib
import sys
from pathlib import Path

import pytest

ORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ORDNER))


class _Halt(Exception):
    pass


def _alle_hilfen(parser: argparse.ArgumentParser) -> None:
    parser.format_help()
    parser.format_usage()
    for aktion in parser._actions:
        if isinstance(aktion, argparse._SubParsersAction):
            for unter in aktion.choices.values():
                _alle_hilfen(unter)


def _einstiege() -> list[tuple[str, str]]:
    gefunden = []
    for datei in sorted(ORDNER.glob("*.py")):
        quelle = datei.read_text(encoding="utf-8")
        if "ArgumentParser" not in quelle:
            continue
        for knoten in ast.walk(ast.parse(quelle)):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            ruft = any(
                isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                and k.func.attr in ("parse_args", "parse_known_args")
                for k in ast.walk(knoten)
            )
            if ruft:
                gefunden.append((datei.stem, knoten.name))
    return gefunden


EINSTIEGE = _einstiege()


def test_jede_datei_mit_parser_hat_einen_einstieg():
    mit_parser = {d.stem for d in ORDNER.glob("*.py") if "ArgumentParser(" in d.read_text(encoding="utf-8")}
    assert mit_parser, "keine Parser gefunden: Suche kaputt"
    assert mit_parser <= {m for m, _ in EINSTIEGE}, mit_parser - {m for m, _ in EINSTIEGE}


@pytest.mark.parametrize("modul,funktion", EINSTIEGE, ids=[f"{m}.{f}" for m, f in EINSTIEGE])
def test_hilfetext_laesst_sich_formatieren(modul, funktion, monkeypatch):
    def statt_parsen(self, args=None, namespace=None):
        _alle_hilfen(self)
        raise _Halt

    monkeypatch.setattr(argparse.ArgumentParser, "parse_known_args", statt_parsen)
    einstieg = getattr(importlib.import_module(modul), funktion)
    with pytest.raises(_Halt):
        einstieg([])
