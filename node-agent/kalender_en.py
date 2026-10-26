# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

WOCHENTAGE_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WOCHENTAGE_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONATE_DE = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MONATE_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

NAMEN = {
    "Neujahr": "New Year's Day", "Heilige Drei Könige": "Epiphany", "Internationaler Frauentag": "International Women's Day",
    "Karfreitag": "Good Friday", "Ostersonntag": "Easter Sunday", "Ostermontag": "Easter Monday", "Staatsfeiertag": "Labour Day (Staatsfeiertag)",
    "Tag der Arbeit": "Labour Day", "Christi Himmelfahrt": "Ascension Day", "Auffahrt": "Ascension Day", "Pfingstsonntag": "Whit Sunday",
    "Pfingstmontag": "Whit Monday", "Fronleichnam": "Corpus Christi", "Augsburger Friedensfest": "Augsburg Peace Festival",
    "Mariä Himmelfahrt": "Assumption Day", "Weltkindertag": "World Children's Day", "Tag der Deutschen Einheit": "German Unity Day",
    "Nationalfeiertag": "National Day", "Reformationstag": "Reformation Day", "Allerheiligen": "All Saints' Day",
    "Buß- und Bettag": "Day of Prayer and Repentance", "Mariä Empfängnis": "Immaculate Conception", "Christtag": "Christmas Day",
    "1. Weihnachtsfeiertag": "Christmas Day", "2. Weihnachtsfeiertag": "St. Stephen's Day (Boxing Day)", "Weihnachtstag": "Christmas Day",
    "Stefanitag": "St. Stephen's Day", "Stephanstag": "St. Stephen's Day", "Berchtoldstag": "Berchtold's Day", "Bundesfeiertag": "Swiss National Day",
    "Rosenmontag": "Rose Monday", "Faschingsdienstag (Fastnacht)": "Shrove Tuesday (carnival)",
    "Aschermittwoch, Beginn der Fastenzeit": "Ash Wednesday, start of Lent", "Palmsonntag": "Palm Sunday", "Gründonnerstag": "Maundy Thursday",
    "Karsamstag": "Holy Saturday", "Muttertag (Österreich, Deutschland, Schweiz)": "Mother's Day (Austria, Germany, Switzerland)",
    "Vatertag in Österreich": "Father's Day in Austria",
    "Zeitumstellung auf Sommerzeit (Uhr um 2 Uhr eine Stunde vor)": "Clocks change to summer time (forward one hour at 2 am)",
    "Zeitumstellung auf Winterzeit (Uhr um 3 Uhr eine Stunde zurück)": "Clocks change to winter time (back one hour at 3 am)",
    "Volkstrauertag (Deutschland)": "National Day of Mourning (Germany)", "Totensonntag (Ewigkeitssonntag)": "Sunday of the Dead (Eternity Sunday)",
    "1. Advent, Beginn der Adventszeit und des Kirchenjahres": "First Sunday of Advent, start of Advent and of the church year",
    "1. Advent": "First Sunday of Advent", "2. Advent": "Second Sunday of Advent", "3. Advent": "Third Sunday of Advent",
    "4. Advent": "Fourth Sunday of Advent", "Valentinstag": "Valentine's Day", "Martini": "St. Martin's Day", "Nikolaus": "St. Nicholas' Day",
    "Heiliger Abend": "Christmas Eve", "Silvester": "New Year's Eve",
}

ORTE = {
    "Österreich": "Austria", "Deutschland": "Germany", "Schweiz": "Switzerland", "Wien": "Vienna", "Niederösterreich": "Lower Austria",
    "Oberösterreich": "Upper Austria", "Steiermark": "Styria", "Kärnten": "Carinthia", "Tirol": "Tyrol", "Bayern": "Bavaria", "Hessen": "Hesse",
    "Niedersachsen": "Lower Saxony", "Nordrhein-Westfalen": "North Rhine-Westphalia", "Rheinland-Pfalz": "Rhineland-Palatinate",
    "Sachsen-Anhalt": "Saxony-Anhalt", "Sachsen": "Saxony", "Thüringen": "Thuringia", "Mecklenburg-Vorpommern": "Mecklenburg-Western Pomerania",
    "Zürich": "Zurich", "Luzern": "Lucerne", "Graubünden": "Grisons", "Tessin": "Ticino", "Waadt": "Vaud", "Wallis": "Valais",
    "Neuenburg": "Neuchâtel", "Freiburg": "Fribourg", "Genf": "Geneva", "Basel-Landschaft": "Basel-Country", "Appenzell Ausserrhoden":
    "Appenzell Outer Rhodes", "Appenzell Innerrhoden": "Appenzell Inner Rhodes",
}

_WT = "|".join(WOCHENTAGE_DE)
_MO = "|".join(MONATE_DE + ["Januar"])


def _monat(m: str) -> str:
    return MONATE_EN[0] if m == "Januar" else MONATE_EN[MONATE_DE.index(m)]


def _wochentag(w: str) -> str:
    return WOCHENTAGE_EN[WOCHENTAGE_DE.index(w)]


def _tag_satz(m: re.Match) -> str:
    tag = f"{int(m.group(1))} {_monat(m.group(2))} {m.group(3)} ({_wochentag(m.group(4))})"
    wo, rest = m.group(5), m.group(6)
    if rest.startswith("kein gesetzlicher Feiertag"):
        return f"{tag} is not a public holiday in {wo}."
    t = re.match(r"nur teilweise ein gesetzlicher Feiertag: (.+?) \((.+)\)\.$", rest)
    if t:
        return f"{tag} is a public holiday in only part of {wo}: {t.group(1)} ({t.group(2)})."
    t = re.match(r"ein gesetzlicher Feiertag: (.+)\.$", rest)
    return f"{tag} is a public holiday in {wo}: {t.group(1)}." if t else m.group(0)


SAETZE: list[tuple[re.Pattern[str], object]] = [
    (re.compile(rf"^Der (\d{{1,2}})\. ({_MO}) (\d{{4}}) \(({_WT})\) ist in (.+?) ((?:kein|nur teilweise ein|ein) gesetzlicher Feiertag.*)$"), _tag_satz),
    (re.compile(r"^Gesetzliche Feiertage in (.+?), vom Programm aus dem Kalender berechnet \(heute ist ([^)]*)\)"),
     r"Public holidays in \1, computed by the program from the calendar (today is \2)"),
    (re.compile(r"^Gesetzliche Feiertage in (.+?), vom Server bei Nager\.Date abgefragt \(heute ist ([^)]*)\)"),
     r"Public holidays in \1, retrieved by the server from Nager.Date (today is \2)"),
    (re.compile(r"^Feiertage in der Schweiz(.*?), vom Programm aus dem Kalender berechnet \(heute ist ([^)]*)\)\. Einheitlich ist nur der "
                r"Bundesfeiertag; die übrigen Feiertage legt jeder Kanton selbst fest\."),
     r"Public holidays in Switzerland\1, computed by the program from the calendar (today is \2). Only Swiss National Day is the same everywhere; "
     r"each canton sets the other holidays itself."),
    (re.compile(r"^Termine im Kalender(.*?), vom Programm berechnet \(heute ist ([^)]*)\)"), r"Dates in the calendar\1, computed by the program (today is \2)"),
    (re.compile(r"^Welche dieser Feiertage im (.+?) gelten, steht nicht in diesem Kalender, sondern in den gefundenen Seiten\.$"),
     r"Which of these holidays apply in the \1 is not in this calendar but in the pages found."),
    (re.compile(r"^Herbstferien an allen Schulen in Österreich \(alle Bundesländer, seit dem Schuljahr (\d+/\d+)\): (.+?) bis (.+?)\.$"),
     r"Autumn holidays at all schools in Austria (all states, since the school year \1): \2 to \3."),
    (re.compile(r"^Im Jahr (\d{4}) gibt es in (.+?) (\d+) gesetzliche Feiertage im ganzen Land, dazu (\d+), die nur in einem Teil gelten\.$"),
     lambda m: f"In {m.group(1)}, {m.group(2)} has {m.group(3)} public holidays that apply everywhere, plus {m.group(4)} that "
               f"{'applies' if m.group(4) == '1' else 'apply'} in only part of it."),
    (re.compile(r"^Im Jahr (\d{4}) gibt es in (.+?) (\d+) gesetzliche Feiertage\.$"), r"In \1, \2 has \3 public holidays."),
    (re.compile(r"^Feiertage und Herbstferien in (.+?) \(vom Programm berechnet\)$"), r"Public holidays and autumn holidays in \1 (computed by the program)"),
    (re.compile(r"^Feiertage in (.+?) \(vom Programm berechnet\)$"), r"Public holidays in \1 (computed by the program)"),
    (re.compile(r"^Termine im Kalender \(vom Programm berechnet\)$"), "Dates in the calendar (computed by the program)"),
    (re.compile(r"\. Die nächsten:$"), ". The next ones:"),
    (re.compile(r" Die nächsten:$"), " The next ones:"),
    (re.compile(r", für ([\d, ]+):$"), r", for \1:"),
    (re.compile(r" Für ([\d, ]+):$"), r" For \1:"),
]

ZUSAETZE = [
    ("in Bayern nur in Gemeinden mit überwiegend katholischer Bevölkerung", "in Bavaria only in municipalities with a predominantly Catholic population"),
    ("in Sachsen und Thüringen nur in einzelnen Gemeinden", "in Saxony and Thuringia only in some municipalities"),
    ("nur in der Stadt Augsburg", "only in the city of Augsburg"), (", in der ganzen Schweiz", ", throughout Switzerland"),
    (", in allen Kantonen", ", in all cantons"), (", in vielen Kantonen", ", in many cantons"), (", in den meisten Kantonen", ", in most cantons"),
    (", in einigen Kantonen", ", in some cantons"), (", in katholischen Kantonen", ", in Catholic cantons"), (", bundesweit", ", nationwide"),
    ("nur ein Bankfeiertag", "only a bank holiday"), ("nur regional", "only in some regions"), ("nur in ", "only in "),
]

_DATUM = re.compile(rf"\b({_WT}), (\d{{1,2}})\.(\d{{1,2}})\.(\d{{4}})\b")
_KANTON = re.compile(r"\bKanton (\S[^,;:()]*)")


def _ort(text: str) -> str:
    for de in sorted(ORTE, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(de)}(?![\w-])", ORTE[de], text)
    return _KANTON.sub(lambda m: f"Canton of {m.group(1)}", text)


def zeile(z: str) -> str:
    for muster, ersatz in SAETZE:
        z = muster.sub(ersatz, z)
    z = _DATUM.sub(lambda m: f"{_wochentag(m.group(1))}, {int(m.group(2))} {MONATE_EN[int(m.group(3)) - 1]} {m.group(4)}", z)
    for de in sorted(NAMEN, key=len, reverse=True):
        z = re.sub(rf"(?<![\w.]){re.escape(de)}(?![\w])", NAMEN[de], z)
    for de, en in ZUSAETZE:
        z = z.replace(de, en)
    z = re.sub(r"(?<=[a-z')]) und (?=[A-Z])", " and ", z)
    return _ort(z)


def text(t: str) -> str:
    return "\n".join(zeile(z) for z in (t or "").split("\n"))


__all__ = ["text", "zeile", "NAMEN", "ORTE"]
