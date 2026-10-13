# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from datetime import date, timedelta
from fractions import Fraction

import kalender_at
import threading

from rechnen import Ergebnis, zahl_text

_STIL = threading.local()

WOCHENTAGE_DE = kalender_at.WOCHENTAGE
WOCHENTAGE_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONATE_DE = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONATE_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_MONAT_NAMEN = {"januar": 1, "jänner": 1, "jan": 1, "february": 2, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3, "april": 4, "apr": 4, "mai": 5,
                "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10,
                "november": 11, "nov": 11, "dezember": 12, "dez": 12,
                "january": 1, "march": 3, "mar": 3, "may": 5, "june": 6, "july": 7, "august ": 8, "october": 10, "oct": 10, "december": 12, "dec": 12}
_MONAT_NAMEN.pop("august ", None)
_MIN_JAHR, _MAX_JAHR = 1583, 9999

_MONAT_RE = "|".join(sorted(_MONAT_NAMEN, key=len, reverse=True))
_TAGE_FEST = {"weihnachten": (12, 24), "heiligabend": (12, 24), "silvester": (12, 31), "neujahr": (1, 1), "nationalfeiertag": (10, 26),
              "staatsfeiertag": (5, 1), "allerheiligen": (11, 1), "stefanitag": (12, 26), "christtag": (12, 25), "dreikönig": (1, 6)}
_FUELL = r"(?:\s*(?:bitte|eigentlich|denn|mal|eh|please))*"


def _nter_wochentag(j: int, monat: int, wochentag: int, n: int) -> date:
    if n > 0:
        d = date(j, monat, 1)
        d += timedelta(days=(wochentag - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(j + (monat == 12), monat % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - wochentag) % 7)


_FEST_EN = {
    "christmas": lambda j: date(j, 12, 25), "christmas day": lambda j: date(j, 12, 25), "christmas eve": lambda j: date(j, 12, 24), "boxing day": lambda j: date(j, 12, 26),
    "new year": lambda j: date(j, 1, 1), "new years": lambda j: date(j, 1, 1), "new year day": lambda j: date(j, 1, 1), "new years day": lambda j: date(j, 1, 1),
    "new year eve": lambda j: date(j, 12, 31), "new years eve": lambda j: date(j, 12, 31),
    "halloween": lambda j: date(j, 10, 31), "valentines day": lambda j: date(j, 2, 14), "valentine day": lambda j: date(j, 2, 14), "valentines": lambda j: date(j, 2, 14),
    "st patricks day": lambda j: date(j, 3, 17), "saint patricks day": lambda j: date(j, 3, 17),
    "independence day": lambda j: date(j, 7, 4), "fourth of july": lambda j: date(j, 7, 4), "4th of july": lambda j: date(j, 7, 4), "july 4th": lambda j: date(j, 7, 4),
    "thanksgiving": lambda j: _nter_wochentag(j, 11, 3, 4), "thanksgiving day": lambda j: _nter_wochentag(j, 11, 3, 4),
    "memorial day": lambda j: _nter_wochentag(j, 5, 0, -1), "labor day": lambda j: _nter_wochentag(j, 9, 0, 1), "labour day": lambda j: _nter_wochentag(j, 9, 0, 1),
    "mothers day": lambda j: _nter_wochentag(j, 5, 6, 2), "fathers day": lambda j: _nter_wochentag(j, 6, 6, 3),
    "easter": lambda j: kalender_at.ostersonntag(j), "easter sunday": lambda j: kalender_at.ostersonntag(j), "easter monday": lambda j: kalender_at.ostersonntag(j) + timedelta(days=1),
    "good friday": lambda j: kalender_at.ostersonntag(j) - timedelta(days=2), "whit sunday": lambda j: kalender_at.ostersonntag(j) + timedelta(days=49),
    "pentecost": lambda j: kalender_at.ostersonntag(j) + timedelta(days=49), "ascension day": lambda j: kalender_at.ostersonntag(j) + timedelta(days=39),
}
_FEST_US = {"thanksgiving", "thanksgiving day", "independence day", "fourth of july", "4th of july", "july 4th", "memorial day", "labor day", "mothers day", "fathers day"}
_FEST_EN_RE = "|".join(sorted((re.escape(k).replace(r"\ ", r"\s+") for k in _FEST_EN), key=len, reverse=True))


def _fest_name(s: str) -> str:
    return " ".join(re.sub(r"['’.]", "", s.lower()).split())


def heute() -> date:
    return date.today()


def _gueltig(j: int, m: int, t: int) -> bool:
    try:
        date(j, m, t)
        return True
    except ValueError:
        return False


def _en(d: date) -> str:
    return f"{MONATE_EN[d.month - 1]} {d.day}, {d.year}" if getattr(_STIL, "us", False) else f"{d.day} {MONATE_EN[d.month - 1]} {d.year}"


def _ds(d: date, en: bool = False) -> str:
    if en:
        return f"{WOCHENTAGE_EN[d.weekday()]}, {_en(d)}"
    return f"{WOCHENTAGE_DE[d.weekday()]}, {d.day}.{d.month}.{d.year}"


def _jahr(j: int) -> int:
    return 2000 + j if j < 70 else 1900 + j if j < 100 else j


def _tage_im_monat(j: int, m: int) -> int:
    return (date(j + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day


def _ok(d: date) -> date | None:
    return d if _MIN_JAHR <= d.year <= _MAX_JAHR else None


def datum_lesen(s: str, h: date, *, vorwaerts: bool = True) -> date | None:
    s = " ".join(s.lower().replace(",", " ").split()).strip(" .")
    s = re.sub(r"^(?:dem|den|der|das|am|zum|zur|vom|ab|auf|bis|seit|von|on|the)\s+", "", s)
    s = re.sub(r"^(?:dem|den|der|das|the)\s+", "", s)
    fest = _fest_name(s)
    mf = re.fullmatch(rf"({_FEST_EN_RE})(?:\s+(\d{{4}}))?", fest)
    if mf:
        name = _fest_name(mf.group(1))
        if name in _FEST_EN:
            if name in _FEST_US:
                _STIL.us = True
            j = int(mf.group(2)) if mf.group(2) else h.year
            if not _MIN_JAHR <= j <= _MAX_JAHR:
                return None
            d = _FEST_EN[name](j)
            if not mf.group(2) and ((vorwaerts and d < h) or (not vorwaerts and d > h)):
                d = _FEST_EN[name](j + (1 if vorwaerts else -1))
            return _ok(d)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})", s)
    if m:
        a, b, j = int(m.group(1)), int(m.group(2)), _jahr(int(m.group(3)))
        if a > 12 and b <= 12:
            tag, mo = a, b
        elif b > 12 and a <= 12:
            tag, mo = b, a
            _STIL.us = True
        else:
            tag, mo = b, a
            _STIL.us = True
            if a != b and a <= 12 and b <= 12:
                _STIL.mehrdeutig = (s, date(j, a, b) if _gueltig(j, a, b) else None, date(j, b, a) if _gueltig(j, b, a) else None)
        return _mit_jahr(tag, mo, j, h, vorwaerts)
    m = re.fullmatch(rf"({_MONAT_RE})\.?\s+(\d{{1,2}}){_ORD}(?:\s+(\d{{4}}))?", s)
    if m:
        _STIL.us = True
        return _mit_jahr(int(m.group(2)), _MONAT_NAMEN[m.group(1)], int(m.group(3)) if m.group(3) else None, h, vorwaerts)
    m = re.fullmatch(rf"(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MONAT_RE})\.?(?:\s+(\d{{4}}))?", s)
    if m:
        return _mit_jahr(int(m.group(1)), _MONAT_NAMEN[m.group(2)], int(m.group(3)) if m.group(3) else None, h, vorwaerts)
    if s in ("heute", "today"):
        return h
    if s in ("morgen", "tomorrow"):
        return h + timedelta(days=1)
    if s in ("übermorgen", "uebermorgen"):
        return h + timedelta(days=2)
    if s in ("gestern", "yesterday"):
        return h - timedelta(days=1)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return _ok(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            return None
    m = re.fullmatch(rf"(\d{{1,2}})\.\s*(\d{{1,2}})(?:\.\s*(\d{{4}}|\d{{2}}))?|(\d{{1,2}})\.?\s*({_MONAT_RE})\.?\s*(\d{{4}})?", s)
    if m:
        if m.group(1):
            t, mo, j = int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            t, mo, j = int(m.group(4)), _MONAT_NAMEN[m.group(5)], m.group(6)
        return _mit_jahr(t, mo, _jahr(int(j)) if j else None, h, vorwaerts)
    m = re.fullmatch(r"(weihnachten|heiligabend|silvester|neujahr|nationalfeiertag|staatsfeiertag|allerheiligen|stefanitag|christtag|dreikönig)(?:\s+(\d{4}))?", s)
    if m:
        mo, t = _TAGE_FEST[m.group(1)][0], _TAGE_FEST[m.group(1)][1]
        return _mit_jahr(t, mo, int(m.group(2)) if m.group(2) else None, h, vorwaerts)
    m = re.fullmatch(r"(ostern|ostersonntag|ostermontag|pfingsten|pfingstsonntag|pfingstmontag|christi himmelfahrt|fronleichnam)(?:\s+(\d{4}))?", s)
    if m:
        versatz = {"ostern": 0, "ostersonntag": 0, "ostermontag": 1, "pfingsten": 49, "pfingstsonntag": 49, "pfingstmontag": 50, "christi himmelfahrt": 39,
                   "fronleichnam": 60}[m.group(1)]
        j = int(m.group(2)) if m.group(2) else h.year
        if not _MIN_JAHR <= j <= _MAX_JAHR:
            return None
        d = kalender_at.ostersonntag(j) + timedelta(days=versatz)
        if not m.group(2) and ((vorwaerts and d < h) or (not vorwaerts and d > h)):
            d = kalender_at.ostersonntag(j + (1 if vorwaerts else -1)) + timedelta(days=versatz)
        return _ok(d)
    return None


def _mit_jahr(t: int, mo: int, j: int | None, h: date, vorwaerts: bool) -> date | None:
    try:
        if j is not None:
            return _ok(date(j, mo, t))
        d = date(h.year, mo, t)
        if vorwaerts and d < h:
            d = date(h.year + 1, mo, t)
        elif not vorwaerts and d > h:
            d = date(h.year - 1, mo, t)
        return _ok(d)
    except ValueError:
        return None


def _monate_dazu(d: date, n: int) -> date | None:
    m0 = d.year * 12 + d.month - 1 + n
    j, m = divmod(m0, 12)
    if not _MIN_JAHR <= j <= _MAX_JAHR:
        return None
    return date(j, m + 1, min(d.day, _tage_im_monat(j, m + 1)))


def _dauer(tage: int, en: bool = False) -> str:
    a = abs(tage)
    t = f"{zahl_text(a, en)} {'day' if a == 1 else 'days'}" if en else f"{zahl_text(a)} {'Tag' if a == 1 else 'Tage'}"
    if a < 7:
        return t
    w, r = divmod(a, 7)
    wt = (f"{w} {'week' if w == 1 else 'weeks'}" + (f" and {r} {'day' if r == 1 else 'days'}" if r else "")) if en else (
        f"{w} {'Woche' if w == 1 else 'Wochen'}" + (f" und {r} {'Tag' if r == 1 else 'Tage'}" if r else ""))
    return f"{t} ({wt})"


def _kw(d: date) -> int:
    return d.isocalendar()[1]


def _alter(geb: date, h: date) -> tuple[int, int, int]:
    j = h.year - geb.year - ((h.month, h.day) < (geb.month, geb.day))
    ab = _monate_dazu(geb, j * 12) or geb
    m = (h.year - ab.year) * 12 + h.month - ab.month - (h.day < ab.day)
    ab2 = _monate_dazu(ab, m) or ab
    return j, m, (h - ab2).days


def _alle(text: str) -> str:
    t = " ".join(text.lower().split())
    t = re.sub(r"[?!]+\s*$", "", t).strip(" .")
    t = re.sub(r"\b(year|valentine|mother|father|patrick)[’']s\b", r"\1s", t)
    return t


_ORD = r"(?:st|nd|rd|th)?"
D = rf"(?:\d{{1,2}}\.\s*\d{{1,2}}(?:\.(?:\s*(?:\d{{4}}|\d{{2}}))?)?|\d{{1,2}}\.?\s*(?:{_MONAT_RE})\.?(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}}|heute|morgen|übermorgen|gestern|today|tomorrow|yesterday|"
D += rf"\d{{1,2}}/\d{{1,2}}/(?:\d{{4}}|\d{{2}})|(?:{_MONAT_RE})\.?\s+\d{{1,2}}{_ORD}(?:\s*,?\s*\d{{4}})?|\d{{1,2}}{_ORD}\s+(?:of\s+)?(?:{_MONAT_RE})\.?(?:\s*,?\s*\d{{4}})?|(?:the\s+)?(?:{_FEST_EN_RE})(?:\s*,?\s*\d{{4}})?|"
D += r"(?:weihnachten|heiligabend|silvester|neujahr|nationalfeiertag|staatsfeiertag|allerheiligen|stefanitag|christtag|dreikönig|ostern|ostersonntag|ostermontag|pfingsten|"
D += r"pfingstsonntag|pfingstmontag|christi himmelfahrt|fronleichnam)(?:\s+\d{4})?)"
_ART = r"(?:(?:zum|zur|zu|dem|den|der|das)\s+)?"
_VOR = r"(?:(?:am|zum|zur|vom|ab|auf|bis|seit|von)\s+)?" + _ART


def loesen(text: str, h: date | None = None) -> Ergebnis | None:
    h = h or heute()
    t = _alle(text)
    if not t or len(t) > 160:
        return None
    _STIL.us, _STIL.mehrdeutig = False, None
    for stufe in (_heute, _tage, _plus_minus, _wochentag, _alter_frage, _schaltjahr, _kalenderwoche, _ostern):
        r = stufe(t, h)
        if r is not None:
            md = getattr(_STIL, "mehrdeutig", None)
            if md:
                s_, us, uk = md
                if us and uk:
                    r = Ergebnis(r.de + f" (Das Datum {s_} lässt sich zweifach lesen: als Monat/Tag/Jahr, hier {us.day}.{us.month}.{us.year}, oder als Tag/Monat/Jahr, dann {uk.day}.{uk.month}.{uk.year}. Schreib es aus, wenn du das andere meinst.)",
                                 r.en + f" (The date {s_} can be read two ways: as month/day/year, used here ({_en(us)}), or as day/month/year ({_en(uk)}). Write it out if you meant the other one.)")
            return r
    return None


def _heute(t: str, h: date) -> Ergebnis | None:
    if re.fullmatch(rf"(?:(?:welcher|welchen|was\s+(?:für\s+)?(?:ein\s+)?)\s*(?:tag|wochentag|datum)\s+(?:ist|haben\s+wir|ist\s+es)\s+heute|welches\s+datum\s+(?:ist|haben\s+wir)\s+heute|"
                    rf"den\s+wievielten\s+haben\s+wir(?:\s+heute)?|datum\s+heute|heutiges\s+datum|was\s+ist\s+heute\s+für\s+ein\s+(?:tag|datum)|welcher\s+tag\s+ist\s+heute|"
                    rf"what(?:'s|\s+is)\s+(?:the\s+)?(?:date|day)(?:\s+(?:today|now))?|what(?:'s|\s+is)\s+today'?s\s+(?:date|day)|what\s+day\s+is\s+(?:it|today)|today'?s\s+date)\s*{_FUELL}", t):
        return Ergebnis(f"Heute ist {_ds(h)}, Kalenderwoche {_kw(h)}.", f"Today is {_ds(h, True)}, week {_kw(h)}.")
    return None


def _zwei(t: str, h: date, muster: str) -> tuple[date, date] | None:
    m = re.fullmatch(muster, t)
    if not m:
        return None
    a, b = datum_lesen(m.group("a"), h, vorwaerts=False), datum_lesen(m.group("b"), h)
    return (a, b) if a and b else None


def _tage(t: str, h: date) -> Ergebnis | None:
    einheit = r"(?P<e>tage|tagen|wochen|monate|monaten|days|weeks|months)"
    m = re.fullmatch(rf"(?:wie\s*viele?|wieviele?|how\s+many)\s+{einheit}\s+(?:sind\s+es\s+|ist\s+es\s+|dauert\s+es\s+|are\s+there\s+|is\s+it\s+|are\s+left\s+|left\s+|do\s+i\s+have\s+)?(?:noch\s+)?(?:left\s+)?(?:bis|until|till|to|before)\s+{_ART}(?P<d>{D}){_FUELL}", t) \
        or re.fullmatch(rf"(?:how\s+long\s+(?:is\s+it\s+)?(?:until|till|to)|(?P<e>days|weeks|months)\s+(?:left\s+)?(?:until|till|to)|how\s+(?:many\s+)?(?P<e2>days|weeks|months)\s+(?:are\s+)?(?:left\s+)?(?:until|till|to))\s+{_ART}(?P<d>{D}){_FUELL}", t) \
        or re.fullmatch(rf"(?:wie\s+lange\s+(?:noch\s+)?(?:ist\s+es\s+)?(?:dauert\s+es\s+)?(?:noch\s+)?bis)\s+{_ART}(?P<d>{D}){_FUELL}", t) \
        or re.fullmatch(rf"(?P<e>tage)\s+bis\s+{_ART}(?P<d>{D}){_FUELL}", t)
    if m:
        d = datum_lesen(m.group("d"), h)
        if d is None:
            return None
        n = (d - h).days
        e = m.groupdict().get("e") or m.groupdict().get("e2") or "tage"
        return _bis_ergebnis(h, d, n, e)
    m = re.fullmatch(rf"(?:wie\s*viele?|wieviele?|how\s+many)\s+{einheit}\s+(?:ist|sind|is|are)?\s*(?:es\s+)?(?:schon\s+|nun\s+)?(?:her\s+)?(?:seit|since)\s+{_ART}(?P<d>{D}){_FUELL}", t) \
        or re.fullmatch(rf"(?:wie\s+lange\s+ist\s+es\s+her\s+(?:seit|dass)?)\s*{_ART}(?P<d>{D}){_FUELL}", t)
    if m:
        d = datum_lesen(m.group("d"), h, vorwaerts=False)
        if d is None:
            return None
        e = m.groupdict().get("e") or "tage"
        return _bis_ergebnis(d, h, (h - d).days, e, seit=True)
    z = _zwei(t, h, rf"(?:wie\s*viele?|wieviele?|how\s+many)\s+{einheit}\s+(?:sind\s+es\s+|liegen\s+|are\s+there\s+)?(?:zwischen|between)\s+{_ART}(?P<a>{D})\s+(?:und|and)\s+{_ART}(?P<b>{D}){_FUELL}") \
        or _zwei(t, h, rf"(?:wie\s*viele?|wieviele?|how\s+many)\s+{einheit}\s+(?:sind\s+es\s+)?(?:von|vom|from)\s+{_ART}(?P<a>{D})\s+(?:bis|to|until)\s+{_ART}(?P<b>{D}){_FUELL}") \
        or _zwei(t, h, rf"(?:tage|days)\s+(?:zwischen|between)\s+{_ART}(?P<a>{D})\s+(?:und|and)\s+{_ART}(?P<b>{D}){_FUELL}")
    if z:
        m2 = re.search(einheit, t)
        return _bis_ergebnis(z[0], z[1], (z[1] - z[0]).days, m2.group("e") if m2 else "tage")
    return None


def _bis_ergebnis(a: date, b: date, n: int, e: str, seit: bool = False) -> Ergebnis:
    if e in ("monate", "monaten", "months"):
        ganz = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)
        rest = (b - (_monate_dazu(a, ganz) or a)).days
        de_dauer = f"{ganz} {'Monat' if ganz == 1 else 'Monate'}" + (f" und {rest} {'Tag' if rest == 1 else 'Tage'}" if rest else "")
        en_dauer = f"{ganz} {'month' if ganz == 1 else 'months'}" + (f" and {rest} {'day' if rest == 1 else 'days'}" if rest else "")
    elif e in ("wochen", "weeks"):
        w, rest = divmod(abs(n), 7)
        de_dauer = f"{w} {'Woche' if w == 1 else 'Wochen'}" + (f" und {rest} {'Tag' if rest == 1 else 'Tage'}" if rest else "") + f" ({abs(n)} Tage)"
        en_dauer = f"{w} {'week' if w == 1 else 'weeks'}" + (f" and {rest} {'day' if rest == 1 else 'days'}" if rest else "") + f" ({abs(n)} days)"
    else:
        de_dauer, en_dauer = _dauer(n), _dauer(n, True)
    if n < 0:
        de_dauer, en_dauer = de_dauer, en_dauer
    if seit:
        return Ergebnis(f"Seit {_ds(a)} sind es {de_dauer}.", f"Since {_ds(a, True)} it has been {en_dauer}.")
    if n == 0:
        return Ergebnis(f"{_ds(b)} ist heute.", f"{_ds(b, True)} is today.")
    if n < 0:
        return Ergebnis(f"Zwischen {_ds(b)} und {_ds(a)} liegen {de_dauer} (das erste Datum liegt später).",
                        f"Between {_ds(b, True)} and {_ds(a, True)} there are {en_dauer} (the first date is later).")
    return Ergebnis(f"Von {_ds(a)} bis {_ds(b)} sind es {de_dauer}.", f"From {_ds(a, True)} to {_ds(b, True)} it is {en_dauer}.")


def _plus_minus(t: str, h: date) -> Ergebnis | None:
    einh = r"(?P<e>tag|tage|tagen|woche|wochen|monat|monate|monaten|jahr|jahre|jahren|day|days|week|weeks|month|months|year|years)"
    m = re.fullmatch(rf"(?:(?:(?:was|welches\s+datum|welcher\s+tag|welcher\s+wochentag|which\s+date|what\s+(?:date|day))\s+(?:ist|haben\s+wir|wird|war|is|will\s+it\s+be|was)\s+)|(?:das\s+)?datum\s+|the\s+date\s+)?"
                     rf"(?P<r>in|vor|heute\s+in|heute\s+vor)\s+(?P<n>\d{{1,5}})\s+{einh}{_FUELL}", t)
    basis = h
    if m:
        vorzeichen = -1 if m.group("r").endswith("vor") else 1
    else:
        m = re.fullmatch(rf"(?:(?:what\s+(?:is\s+)?(?:the\s+)?date|what\s+day|which\s+date)\s+(?:is\s+(?:it\s+)?|will\s+it\s+be\s+|was\s+(?:it\s+)?)?)?"
                         rf"(?P<n>\d{{1,5}})\s+{einh}\s+(?P<r>from\s+(?:now|today)|ago){_FUELL}", t)
        if m:
            vorzeichen = -1 if m.group("r") == "ago" else 1
        else:
            m = re.fullmatch(rf"(?P<n>\d{{1,5}})\s+{einh}\s+(?P<r>nach|vor|after|before|from)\s+{_ART}(?P<d>{D}){_FUELL}", t)
            if m:
                vorzeichen = -1 if m.group("r") in ("vor", "before") else 1
                basis = datum_lesen(m.group("d"), h)
            else:
                m = re.fullmatch(rf"(?P<d>{D})\s*(?P<r>\+|plus|-|minus)\s*(?P<n>\d{{1,5}})\s*{einh}{_FUELL}", t)
                if not m:
                    return None
                vorzeichen = -1 if m.group("r") in ("-", "minus") else 1
                basis = datum_lesen(m.group("d"), h)
    if basis is None:
        return None
    n = int(m.group("n")) * vorzeichen
    e = m.group("e")
    if e.startswith(("tag", "day")):
        ziel = basis + timedelta(days=n) if abs(n) < 4_000_000 else None
    elif e.startswith(("woche", "week")):
        ziel = basis + timedelta(days=7 * n) if abs(n) < 600_000 else None
    elif e.startswith(("monat", "month")):
        ziel = _monate_dazu(basis, n)
    else:
        ziel = _monate_dazu(basis, 12 * n)
    try:
        if ziel is None or not _ok(ziel):
            return None
    except (OverflowError, ValueError):
        return None
    ab = abs(n)
    erste = e[0]
    de_name = {"t": "Tag" if ab == 1 else "Tagen", "d": "Tag" if ab == 1 else "Tagen", "w": "Woche" if ab == 1 else "Wochen",
               "m": "Monat" if ab == 1 else "Monaten", "j": "Jahr" if ab == 1 else "Jahren", "y": "Jahr" if ab == 1 else "Jahren"}[erste]
    if basis != h:
        de_name = {"Tagen": "Tage", "Monaten": "Monate", "Jahren": "Jahre"}.get(de_name, de_name)
    en_name = {"t": "day", "d": "day", "w": "week", "m": "month", "j": "year", "y": "year"}[erste] + ("" if ab == 1 else "s")
    if basis == h:
        if n >= 0:
            return Ergebnis(f"In {ab} {de_name} ist {_ds(ziel)}.", f"In {ab} {en_name} it will be {_ds(ziel, True)}.")
        return Ergebnis(f"Vor {ab} {de_name} war {_ds(ziel)}.", f"{ab} {en_name} ago it was {_ds(ziel, True)}.")
    return Ergebnis(f"{ab} {de_name} {'nach' if n >= 0 else 'vor'} {_ds(basis)}: {_ds(ziel)}.",
                    f"{ab} {en_name} {'after' if n >= 0 else 'before'} {_ds(basis, True)}: {_ds(ziel, True)}.")


def _wochentag(t: str, h: date) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:which|what)\s+(?:day\s+of\s+the\s+week|weekday|day)\s+(?:is|was|will\s+(?:it\s+be|be)|does)\s+(?:it\s+)?(?:on\s+)?(?:the\s+)?(?P<en>{D})(?:\s+fall\s+on|\s+fall)?{_FUELL}"
                     rf"|on\s+(?:which|what)\s+day\s+(?:of\s+the\s+week\s+)?(?:does|did|will)\s+(?:the\s+)?(?P<en2>{D})\s+fall{_FUELL}"
                     rf"|(?:welcher|welchen|was\s+für\s+ein|auf\s+welchen)\s+(?:wochen)?tag\s+(?:ist|war|wird|fällt|faellt)\s+(?:der\s+|das\s+)?(?P<d>{D})(?:\s+fällt)?{_FUELL}"
                     rf"|auf\s+welchen\s+(?:wochen)?tag\s+(?:fällt|faellt)\s+(?:der\s+|das\s+)?(?P<d2>{D}){_FUELL}"
                     rf"|welcher\s+wochentag\s+(?:ist|war|wird)\s+(?:am\s+|der\s+)?(?P<d3>{D}){_FUELL}"
                     rf"|what\s+(?:day|weekday)\s+(?:is|was|will)\s+(?:it\s+be\s+)?(?:on\s+)?(?P<d4>{D}){_FUELL}|(?:welcher\s+tag|welcher\s+wochentag)\s+ist\s+(?:es\s+)?(?:am\s+)?(?P<d5>{D}){_FUELL}", t)
    if not m:
        return None
    s = next((g for g in m.groups() if g), None)
    d = datum_lesen(s, h) if s else None
    if d is None:
        return None
    vergangen = "war" if d < h else "ist" if d == h else "wird"
    en_v = "was" if d < h else "is" if d == h else "will be"
    return Ergebnis(f"Der {d.day}.{d.month}.{d.year} {vergangen} ein {WOCHENTAGE_DE[d.weekday()]}.", f"{_en(d)} {en_v} a {WOCHENTAGE_EN[d.weekday()]}.")


def _alter_frage(t: str, h: date) -> Ergebnis | None:
    m = re.fullmatch(rf"wie\s+alt\s+(?:ist|wird|bin\s+ich|ist\s+man|ist\s+jemand|ist\s+einer)?\s*(?:jemand\s+|man\s+|einer\s+|der\s+|ein\s+mensch\s+|eine\s+person\s+)?(?:der\s+|die\s+|wer\s+|wenn\s+(?:man|ich)\s+)?"
                     rf"(?:am\s+|im\s+jahr\s+)?(?P<d>{D})\s+geboren\s+(?:ist|bin|wurde|wurde)?{_FUELL}"
                     rf"|geboren\s+am\s+(?P<d2>{D})\s*,?\s*wie\s+alt\s*(?:ist\s+das|bin\s+ich|ist\s+man)?{_FUELL}"
                     rf"|how\s+old\s+is\s+(?:someone|a\s+person|somebody|one)\s+(?:who\s+was\s+)?born\s+(?:on\s+)?(?P<d3>{D}){_FUELL}"
                     rf"|how\s+old\s+am\s+i\s*(?:if\s+i\s+was\s+born|when\s+i\s+was\s+born|if\s+i\s+am\s+born|born)\s+(?:on\s+)?(?P<d4>{D}){_FUELL}"
                     rf"|(?:i\s+was\s+born|born)\s+(?:on\s+)?(?P<d5>{D})\s*,?\s*how\s+old\s+am\s+i{_FUELL}", t)
    if not m:
        return None
    s = next((g for g in m.groups() if g), None)
    geb = datum_lesen(s, h, vorwaerts=False) if s else None
    if geb is None or geb > h:
        return None
    j, mo, tg = _alter(geb, h)
    de = f"Wer am {geb.day}.{geb.month}.{geb.year} geboren ist, ist heute {j} Jahre"
    en = f"Someone born on {_en(geb)} is {j} years"
    if mo or tg:
        de += f", {mo} {'Monat' if mo == 1 else 'Monate'} und {tg} {'Tag' if tg == 1 else 'Tage'}"
        en += f", {mo} {'month' if mo == 1 else 'months'} and {tg} {'day' if tg == 1 else 'days'}"
    de += f" alt ({zahl_text(Fraction((h - geb).days))} Tage gelebt)."
    en += f" old ({zahl_text(Fraction((h - geb).days), True)} days lived)."
    return Ergebnis(de, en)


def _schaltjahr_ist(j: int) -> bool:
    return j % 4 == 0 and (j % 100 != 0 or j % 400 == 0)


def _schaltjahr(t: str, h: date) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:ist|war|wird|is|was)\s+(?:das\s+jahr\s+)?(?P<j>\d{{4}})\s+(?:ein\s+|a\s+)?(?:schaltjahr|leap\s+year){_FUELL}", t)
    if m:
        j = int(m.group("j"))
        if not _MIN_JAHR <= j <= _MAX_JAHR:
            return None
        ja = _schaltjahr_ist(j)
        grund = ("Es ist durch 4 teilbar" + (", aber nicht durch 100" if j % 100 else "") + ("." if j % 100 else ", durch 400 aber schon." if j % 400 == 0 else ", aber auch durch 100 und nicht durch 400.")) if j % 4 == 0 \
            else "Es ist nicht durch 4 teilbar."
        return Ergebnis(f"{j} {'ist' if ja else 'ist kein'} {'ein ' if ja else ''}Schaltjahr. {grund} Das Jahr hat {366 if ja else 365} Tage.",
                        f"{j} {'is' if ja else 'is not'} a leap year. The year has {366 if ja else 365} days.")
    m = re.fullmatch(rf"wie\s*viele?\s+tage\s+hat\s+(?:der\s+|das\s+)?(?:(?:monat\s+)?(?P<mo>{_MONAT_RE})(?:\s+(?P<j>\d{{4}}))?|(?:jahr\s+)?(?P<jj>\d{{4}})|dieses\s+jahr|das\s+jahr){_FUELL}", t)
    if m:
        if m.group("mo"):
            mo = _MONAT_NAMEN[m.group("mo")]
            j = int(m.group("j")) if m.group("j") else h.year
            if not _MIN_JAHR <= j <= _MAX_JAHR:
                return None
            n = _tage_im_monat(j, mo)
            return Ergebnis(f"{MONATE_DE[mo - 1]} {j} hat {n} Tage.", f"{MONATE_EN[mo - 1]} {j} has {n} days.")
        j = int(m.group("jj")) if m.group("jj") else h.year
        if not _MIN_JAHR <= j <= _MAX_JAHR:
            return None
        n = 366 if _schaltjahr_ist(j) else 365
        return Ergebnis(f"{j} hat {n} Tage.", f"{j} has {n} days.")
    return None


def _kalenderwoche(t: str, h: date) -> Ergebnis | None:
    m = re.fullmatch(rf"(?:in\s+)?welche[rm]?\s+(?:kalenderwoche|kw)\s+(?:ist|liegt|fällt|haben\s+wir|sind\s+wir)\s*(?:der\s+|das\s+|am\s+)?(?P<d>{D}|es|jetzt|gerade)?(?:\s+(?:liegt|fällt))?{_FUELL}"
                     rf"|(?:in\s+)?welche[rm]?\s+(?:kalenderwoche|kw)\s+(?:liegt|fällt)\s+(?:der\s+|das\s+|am\s+)?(?P<d2>{D}){_FUELL}"
                     rf"|which\s+(?:calendar\s+)?week\s+is\s+(?:it|(?P<d3>{D})){_FUELL}", t)
    if not m:
        return None
    s = next((g for g in m.groups() if g), "heute")
    d = h if s in ("es", "jetzt", "gerade", "heute") else datum_lesen(s, h)
    if d is None:
        return None
    return Ergebnis(f"Der {d.day}.{d.month}.{d.year} liegt in der Kalenderwoche {_kw(d)} (nach ISO 8601, Woche beginnt am Montag).",
                    f"{_en(d)} is in calendar week {_kw(d)} (ISO 8601, weeks start on Monday).")


def _ostern(t: str, h: date) -> Ergebnis | None:
    m = re.fullmatch(rf"wann\s+(?:ist|war|wird|fällt)\s+(?:dieses\s+jahr\s+|nächstes\s+jahr\s+)?(?P<w>ostern|ostersonntag|ostermontag|pfingsten|pfingstsonntag|pfingstmontag|christi\s+himmelfahrt|fronleichnam)(?:\s+(?P<j>\d{{4}}))?{_FUELL}"
                     rf"|when\s+is\s+(?P<w2>easter)(?:\s+(?P<j2>\d{{4}}))?{_FUELL}", t)
    if not m:
        return None
    wort = m.group("w") or "ostern"
    jahr = m.group("j") or m.group("j2")
    j = int(jahr) if jahr else h.year
    if "nächstes jahr" in t:
        j = h.year + 1
    if not _MIN_JAHR <= j <= _MAX_JAHR:
        return None
    wort = " ".join(wort.split())
    versatz = {"ostern": 0, "ostersonntag": 0, "ostermontag": 1, "pfingsten": 49, "pfingstsonntag": 49, "pfingstmontag": 50, "christi himmelfahrt": 39, "fronleichnam": 60}[wort]
    d = kalender_at.ostersonntag(j) + timedelta(days=versatz)
    if not jahr and "nächstes" not in t and d < h:
        j += 1
        d = kalender_at.ostersonntag(j) + timedelta(days=versatz)
    name = {"ostern": "Ostersonntag", "pfingsten": "Pfingstsonntag"}.get(wort, wort.replace("christi himmelfahrt", "Christi Himmelfahrt").capitalize())
    en_name = {"Ostersonntag": "Easter Sunday", "Ostermontag": "Easter Monday", "Pfingstsonntag": "Whit Sunday", "Pfingstmontag": "Whit Monday", "Christi Himmelfahrt": "Ascension Day",
               "Fronleichnam": "Corpus Christi"}.get(name, name)
    return Ergebnis(f"{name} {d.year} ist am {_ds(d)}.", f"{en_name} {d.year} is on {_ds(d, True)}.")
