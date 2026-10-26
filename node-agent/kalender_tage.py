# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta

import kalender_at
import kalender_en
import laender

WOCHENTAGE = kalender_at.WOCHENTAGE

BETRIFFT = re.compile(r"advent|aschermittwoch|fasching|fastnacht|rosenmontag|palmsonntag|gründonnerstag|karfreitag|karsamstag|ostersonntag|"
                      r"\bostern\b|pfingstsonntag|\bpfingsten\b|muttertag|vatertag|zeit-?umstellung|uhren-?umstellung|sommerzeit|winterzeit|uhr(?:en)?\b.{0,25}\bum(?:ge)?stell|"
                      r"umstellung der uhr|totensonntag|ewigkeitssonntag|volkstrauertag|nikolaus|heilige[nr]? abend|heiligabend|silvester|"
                      r"valentinstag|halloween|martini|weihnachten|"
                      r"\beaster\b|good friday|ash wednesday|palm sunday|pentecost|whitsun|shrove tuesday|valentine'?s day|\badvent\b", re.I)
_WANN = re.compile(r"\bwann\b|\bwelche[mnrs]?\b.{0,25}\b(?:tag|datum|sonntag|wochentag|termin)\b|\bdatum\b|\bf[äa]llt\b|\bbeginn\w*\b|\bstartet\b|"
                   r"\bend(?:et|e)\b|\bwie viele tage\b|\bwie lange (?:noch|bis)\b|\bist\b.{0,40}\b(?:19|20)\d\d\b|\bam wievielten\b|"
                   r"\bwhen\b|\bwhat (?:date|day)\b|\bwhich (?:date|day|sunday)\b|\bhow many days\b|\bis\b.{0,40}\b(?:19|20)\d\d\b", re.I)
_DACH = frozenset({"AT", "DE", "CH", "LI"})
_JAHR = re.compile(r"\b(19[5-9]\d|20\d\d|21\d\d)\b")
_JAHR_WORT = re.compile(r"\b(?P<dieses>heuer|heurig\w*|diesjährig\w*|dies(?:es|em) jahr|im laufenden jahr|this year|this year's)\b|"
                        r"\b(?P<naechstes>(?:im )?n[äa]chste[nms]? jahr|kommende[nms]? jahr|next year|next year's)\b|"
                        r"\b(?P<letztes>(?:im )?letzte[nms]? jahr|vorige[nms]? jahr|vergangene[nms]? jahr|last year|last year's)\b", re.I)


def _heute_frager():
    try:
        import ki_laufzeit
        return ki_laufzeit.heute()
    except Exception:
        from datetime import date as _d
        return _d.today()


def _letzter_sonntag(jahr: int, monat: int) -> date:
    ende = date(jahr + (monat == 12), monat % 12 + 1, 1) - timedelta(days=1)
    return ende - timedelta(days=(ende.weekday() + 1) % 7)


def _nter_sonntag(jahr: int, monat: int, n: int) -> date:
    erster = date(jahr, monat, 1)
    return erster + timedelta(days=(6 - erster.weekday()) % 7 + 7 * (n - 1))


def erster_advent(jahr: int) -> date:
    heiligabend = date(jahr, 12, 24)
    return heiligabend - timedelta(days=(heiligabend.weekday() + 1) % 7) - timedelta(days=21)


def tage(jahr: int) -> list[tuple[date, str]]:
    o = kalender_at.ostersonntag(jahr)
    a1 = erster_advent(jahr)
    liste = [
        (o - timedelta(days=48), "Rosenmontag"), (o - timedelta(days=47), "Faschingsdienstag (Fastnacht)"),
        (o - timedelta(days=46), "Aschermittwoch, Beginn der Fastenzeit"), (o - timedelta(days=7), "Palmsonntag"),
        (o - timedelta(days=3), "Gründonnerstag"), (o - timedelta(days=2), "Karfreitag"), (o - timedelta(days=1), "Karsamstag"),
        (o, "Ostersonntag"), (o + timedelta(days=49), "Pfingstsonntag"),
        (_nter_sonntag(jahr, 5, 2), "Muttertag (Österreich, Deutschland, Schweiz)"), (_nter_sonntag(jahr, 6, 2), "Vatertag in Österreich"),
        (_letzter_sonntag(jahr, 3), "Zeitumstellung auf Sommerzeit (Uhr um 2 Uhr eine Stunde vor)"),
        (_letzter_sonntag(jahr, 10), "Zeitumstellung auf Winterzeit (Uhr um 3 Uhr eine Stunde zurück)"),
        (a1 - timedelta(days=14), "Volkstrauertag (Deutschland)"), (a1 - timedelta(days=7), "Totensonntag (Ewigkeitssonntag)"),
        (a1, "1. Advent, Beginn der Adventszeit und des Kirchenjahres"), (a1 + timedelta(days=7), "2. Advent"),
        (a1 + timedelta(days=14), "3. Advent"), (a1 + timedelta(days=21), "4. Advent"),
        (date(jahr, 2, 14), "Valentinstag"), (date(jahr, 10, 31), "Halloween"), (date(jahr, 11, 11), "Martini"),
        (date(jahr, 12, 6), "Nikolaus"), (date(jahr, 12, 24), "Heiliger Abend"), (date(jahr, 12, 31), "Silvester"),
    ]
    return sorted(liste)


def _tag(d: date) -> str:
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}.{d.month}.{d.year}"


def jahre(frage: str, heute: date | None = None) -> list[int]:
    h = heute or _heute_frager()
    gefunden = []
    for m in re.finditer(_JAHR.pattern + "|" + _JAHR_WORT.pattern, frage or "", re.I):
        if m.group(1):
            gefunden.append(int(m.group(1)))
        else:
            gefunden.append(h.year + (1 if m.group("naechstes") else -1 if m.group("letztes") else 0))
    return list(dict.fromkeys(gefunden))[:3]


def betrifft(frage: str) -> bool:
    return bool(BETRIFFT.search(frage or "")) and bool(_WANN.search(frage or "")) and not (laender.alle(frage) - _DACH)


_GLEICH = {"uhren": "zeitu", "umges": "zeitu", "umste": "zeitu", "somme": "zeitu", "winte": "zeitu", "weihn": "heili", "heili": "heili",
           "fastn": "fasch", "karne": "rosen", "ewigk": "toten", "easte": "oster", "frida": "karfr", "wedne": "asche", "pente": "pfing",
           "whits": "pfing", "shrov": "fasch", "valen": "valen"}


def _gefragt(frage: str, name: str) -> bool:
    kern = re.split(r"[,(]", name, maxsplit=1)[0].lower()
    kern += " " + re.split(r"[,(]", kalender_en.NAMEN.get(name, ""), maxsplit=1)[0].lower()
    stamm = {w[:5] for w in re.findall(r"[a-zäöüß]{5,}", kern)}
    worte = {w[:5] for w in re.findall(r"[a-zäöüß]{5,}", (frage or "").lower())}
    return bool(stamm & (worte | {_GLEICH[w] for w in worte if w in _GLEICH}))


def text(frage: str, heute: date | None = None) -> str:
    h = heute or _heute_frager()
    gefragt = jahre(frage, h)
    if gefragt:
        eintraege = [x for j in gefragt for x in tage(j)]
        kopf = f"Termine im Kalender {', '.join(str(j) for j in gefragt)}, vom Programm berechnet (heute ist {_tag(h)}):"
    else:
        eintraege = [x for j in (h.year, h.year + 1) for x in tage(j) if x[0] >= h]
        kopf = f"Termine im Kalender, vom Programm berechnet (heute ist {_tag(h)}). Die nächsten:"
    passend = [x for x in eintraege if _gefragt(frage, x[1])]
    return "\n".join([kopf] + [f"– {n}: {_tag(d)}" for d, n in (passend or eintraege)])


ZEITUMSTELLUNG = re.compile(r"zeit-?umstellung|uhren-?umstellung|uhr(?:en)?\b.{0,25}\bum(?:ge)?stell|umstellung der uhr|daylight[- ]sav\w*|"
                            r"\bDST\b|clocks?\b.{0,30}\b(?:go|change|move|spring|fall|turn)\w*|\b(?:change|turn|move|set)\w* (?:the )?clocks?\b|"
                            r"\b(?:spring|fall) (?:forward|back)\b", re.I)
_ZEITUMSTELLUNG_SCHWACH = re.compile(r"sommerzeit|winterzeit|normalzeit|summer ?time", re.I)
_MEZ = ("2 Uhr", "3 Uhr", "3 Uhr", "2 Uhr")
_EU_REGEL = "Sommerzeit vom letzten Sonntag im März bis zum letzten Sonntag im Oktober, in ganz Europa zugleich um 1 Uhr Weltzeit (UTC)."
_REGELN: dict[str, tuple[tuple[int, int], tuple[int, int], tuple[str, str, str, str], str]] = {
    "US": ((3, 2), (11, 1), ("2 Uhr", "3 Uhr", "2 Uhr", "1 Uhr"), "Sommerzeit vom zweiten Sonntag im März bis zum ersten Sonntag im November, "
          "umgestellt wird um 2 Uhr Ortszeit. Nicht umgestellt wird auf Hawaii, im größten Teil von Arizona und in den Außengebieten wie Puerto Rico."),
    "CA": ((3, 2), (11, 1), ("2 Uhr", "3 Uhr", "2 Uhr", "1 Uhr"), "Sommerzeit vom zweiten Sonntag im März bis zum ersten Sonntag im November, "
          "umgestellt wird um 2 Uhr Ortszeit. Nicht umgestellt wird im größten Teil von Saskatchewan und in Yukon."),
    "AU": ((10, 1), (4, 1), ("2 Uhr", "3 Uhr", "3 Uhr", "2 Uhr"), "Sommerzeit vom ersten Sonntag im Oktober bis zum ersten Sonntag im April, "
          "nur in New South Wales, Victoria, dem Australian Capital Territory, Tasmanien und South Australia; Queensland, Western Australia und "
          "das Northern Territory stellen nicht um."),
    "NZ": ((9, -1), (4, 1), ("2 Uhr", "3 Uhr", "3 Uhr", "2 Uhr"), "Sommerzeit vom letzten Sonntag im September bis zum ersten Sonntag im April."),
}
for _c in ("AT BE HR CZ DK FR DE HU IT LU MT NL PL SK SI ES SE NO CH LI AL AD BA ME MK RS MC SM VA XK").split():
    _REGELN[_c] = ((3, -1), (10, -1), _MEZ, _EU_REGEL)
for _c in ("GB", "IE", "PT"):
    _REGELN[_c] = ((3, -1), (10, -1), ("1 Uhr", "2 Uhr", "2 Uhr", "1 Uhr"), _EU_REGEL)
for _c in ("BG", "CY", "EE", "FI", "GR", "LV", "LT", "RO"):
    _REGELN[_c] = ((3, -1), (10, -1), ("3 Uhr", "4 Uhr", "4 Uhr", "3 Uhr"), _EU_REGEL)
_KEINE = {"JP": "", "CN": "", "IN": "", "KR": "", "HK": "", "TW": "", "SG": "", "MY": "", "TH": "", "VN": "", "ID": "", "PH": "", "AE": "",
          "SA": "", "ZA": "", "IS": "", "BY": "", "AR": "", "BR": " (seit 2019)", "RU": " (seit 2014)", "TR": " (seit 2016)",
          "MX": " (seit Oktober 2022; nur einige Orte an der Grenze zu den USA stellen mit den USA um)"}


def _sonntag(jahr: int, monat: int, n: int) -> date:
    return _letzter_sonntag(jahr, monat) if n < 0 else _nter_sonntag(jahr, monat, n)


def zeitumstellung_welt(frage: str, heute: date | None = None) -> tuple[str, str, bool] | None:
    gemeint = ZEITUMSTELLUNG.search(frage or "") or (_ZEITUMSTELLUNG_SCHWACH.search(frage or "") and _WANN.search(frage or ""))
    if not gemeint or betrifft(frage):
        return None
    code = laender.erkennen(frage)
    if code not in _REGELN and code not in _KEINE:
        return None
    h = heute or _heute_frager()
    name = laender.DEUTSCH.get(code, code)
    if code in _KEINE:
        return (f"Zeitumstellung in {name} (vom Programm)", f"In {name} gibt es keine Zeitumstellung{_KEINE[code]}; die Uhrzeit bleibt das "
                f"ganze Jahr gleich (heute ist {_tag(h)}).", True)
    (m1, n1), (m2, n2), (v1, z1, v2, z2), regel = _REGELN[code]
    gefragt = jahre(frage, h)
    eintraege = sorted((d, n) for j in (gefragt or (h.year, h.year + 1)) for d, n in (
        (_sonntag(j, m1, n1), f"Beginn der Sommerzeit (die Uhr springt um {v1} eine Stunde vor auf {z1})"),
        (_sonntag(j, m2, n2), f"Ende der Sommerzeit (die Uhr springt um {v2} eine Stunde zurück auf {z2})")) if gefragt or d >= h)
    kopf = (f"Zeitumstellung in {name}, vom Programm nach der dort geltenden Regel berechnet (heute ist {_tag(h)}). {regel}"
            + (f" Für {', '.join(str(j) for j in gefragt)}:" if gefragt else " Die nächsten:"))
    return f"Zeitumstellung in {name} (vom Programm berechnet)", "\n".join([kopf] + [f"– {n}: {_tag(d)}" for d, n in eintraege]), True


MONATE = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def feiertag_saetze(wo: str, tage_je_jahr: dict[int, list[tuple[date, str, str]]], frage: str, h: date, jahre: list[int]) -> list[str]:
    import belege
    zeilen = []

    def je_tag(j: int) -> dict[date, tuple[list[str], str]]:
        out: dict[date, tuple[list[str], str]] = {}
        for d, n, w in sorted(tage_je_jahr.get(j) or [], key=lambda x: (x[0], bool(x[2]))):
            namen, wo_nur = out.get(d, ([], w))
            out[d] = (namen + [n] if n not in namen else namen, "" if not w or not wo_nur else wo_nur)
        return out
    for j in sorted(tage_je_jahr):
        tage = je_tag(j)
        teil = sum(1 for _namen, w in tage.values() if w)
        zeilen.append(f"Im Jahr {j} gibt es in {wo} {len(tage) - teil} gesetzliche Feiertage" + (f" im ganzen Land, dazu {teil}, die nur in einem Teil "
                                                                                                f"gelten" if teil else "") + ".")
    for tag, monat, jahr in sorted(belege.daten(frage)):
        for j in ([jahr] if jahr else (jahre or [belege._jahr_fuer(tag, monat, h)])):
            try:
                d = date(j, monat, tag)
            except ValueError:
                continue
            if j not in tage_je_jahr:
                continue
            tag_text = f"{d.day}. {MONATE[d.month - 1]} {d.year} ({kalender_at.WOCHENTAGE[d.weekday()]})"
            treffer = je_tag(j).get(d)
            if treffer is None:
                zeilen.append(f"Der {tag_text} ist in {wo} kein gesetzlicher Feiertag.")
            elif treffer[1]:
                zeilen.append(f"Der {tag_text} ist in {wo} nur teilweise ein gesetzlicher Feiertag: {' und '.join(treffer[0])} ({treffer[1]}).")
            else:
                zeilen.append(f"Der {tag_text} ist in {wo} ein gesetzlicher Feiertag: {' und '.join(treffer[0])}.")
    return zeilen


__all__ = ["erster_advent", "tage", "jahre", "betrifft", "text", "zeitumstellung_welt", "feiertag_saetze"]
