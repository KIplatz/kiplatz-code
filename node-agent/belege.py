# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONATE = {"jänner": 1, "januar": 1, "jan": 1, "feber": 2, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3, "april": 4, "apr": 4,
          "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10,
          "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12}
_MONAT = "|".join(sorted(MONATE, key=len, reverse=True))
_TAG = "|".join(WOCHENTAGE + KURZ)

_DATUM_ZAHL = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4})(?![\d:])|(?<=\.)(\d{2})(?![\d:]))?")
_DATUM_WORT = re.compile(rf"(?<!\d)(\d{{1,2}})\.\s*({_MONAT})\.?(?:\s+(\d{{4}}))?(?![a-zäöü])", re.I)
_DATUM_ISO = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
_WOCHENTAG_DATUM = re.compile(rf"\b({_TAG})(\.?)(,?\s+(?:den\s+|dem\s+)?)(\d{{1,2}}\.\s?\d{{1,2}}\.(?:\s?\d{{2,4}})?|\d{{1,2}}\.\s*(?:{_MONAT})\.?(?:\s+\d{{4}})?)", re.I)

_BETRAG = re.compile(r"(?:€\s*(\d[\d.,]*\d|\d)|(\d[\d.,]*\d|\d)\s*(?:€|euro\b|eur\b|cent\b|%|prozent\b))", re.I)
_ZAHL = re.compile(r"\d[\d.,]*\d|\d")


def _jahr(j: str | None) -> int | None:
    if not j:
        return None
    n = int(j)
    return n + 2000 if n < 100 else n


def daten(text: str) -> set[tuple[int, int, int | None]]:
    out: set[tuple[int, int, int | None]] = set()
    for m in _DATUM_ZAHL.finditer(text or ""):
        t, mo = int(m.group(1)), int(m.group(2))
        if 1 <= t <= 31 and 1 <= mo <= 12:
            out.add((t, mo, _jahr(m.group(3) or m.group(4))))
    for m in _DATUM_WORT.finditer(text or ""):
        t, mo = int(m.group(1)), MONATE[m.group(2).lower()]
        if 1 <= t <= 31:
            out.add((t, mo, _jahr(m.group(3))))
    for m in _DATUM_ISO.finditer(text or ""):
        out.add((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    return out


def _werte(zahl: str) -> set[float]:
    z = zahl.strip(".,")
    out: set[float] = set()
    if not z:
        return out
    if "," in z and "." in z:
        a, b = (z.replace(".", "").replace(",", "."), z.replace(",", ""))
        for x in (a, b):
            try:
                out.add(round(float(x), 4))
            except ValueError:
                pass
        return out
    kandidaten = [z.replace(",", ".")]
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", z):
        kandidaten.append(z.replace(".", "").replace(",", ""))
    for x in kandidaten:
        try:
            out.add(round(float(x), 4))
        except ValueError:
            pass
    return out


def betraege(text: str) -> list[set[float]]:
    return [_werte(m.group(1) or m.group(2)) for m in _BETRAG.finditer(text or "")]


def zahlenwerte(text: str) -> set[float]:
    out: set[float] = set()
    for m in _ZAHL.finditer(text or ""):
        out |= _werte(m.group(0))
    return out


def _gedeckt_datum(d: tuple[int, int, int | None], belegt: set[tuple[int, int, int | None]]) -> bool:
    t, m, j = d
    for bt, bm, bj in belegt:
        if bt == t and bm == m and (j is None or bj is None or bj == j):
            return True
    return False


def _saetze(absatz: str) -> list[str]:
    import pruefung
    return [s for s in re.split(r"(?<=[.!?])(?<!\d\.)" + pruefung._ABKUERZUNG + r"\s+(?=[A-ZÄÖÜ„\"(–-])", absatz) if s]


_SEIT = re.compile(r"\b(?:seit|ab)\s+(?:(?:dem|\d{1,2}\.|[A-Za-zÄÖÜäöü]+)\s+){0,3}20\d\d\b", re.I)


def seit_belegt(satz: str, gelesen: str) -> bool:
    if not (gelesen or "").strip() or not _SEIT.search(satz or ""):
        return False
    werte = zahlenwerte(gelesen)
    if not all(_werte(m.group(0)) & werte for m in _ZAHL.finditer(satz)):
        return False
    d = daten(gelesen)
    return all(_gedeckt_datum(x, d) for x in daten(satz))


def unbelegte_streichen(antwort: str, belege: str, *, betraege_pruefen: bool = True) -> tuple[str, list[str]]:
    belegt_d = daten(belege)
    belegt_z = zahlenwerte(belege)
    raus: list[str] = []
    absaetze = []
    for absatz in (antwort or "").split("\n"):
        bleiben = []
        for s in _saetze(absatz):
            falsch_d = [d for d in daten(s) if not _gedeckt_datum(d, belegt_d)]
            falsch_b = [b for b in betraege(s) if b and not (b & belegt_z)] if betraege_pruefen else []
            if falsch_d or falsch_b:
                raus.append(s)
            else:
                bleiben.append(s)
        if bleiben or not absatz.strip():
            absaetze.append(" ".join(bleiben))
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(absaetze)).strip()
    if raus and not rest:
        rest = "Das weiß ich noch nicht."
    return rest, raus


KLEINE_ZAHL = 12
_EINHEIT_NACH = re.compile(r"\s*(?:%|‰|€|°|prozent\b|euro\b|eur\b|cent\b|chf\b|fr\.|franken\b|dollar\b|\$|m\b|km\b|cm\b|mm\b|kg\b|g\b|t\b|l\b|ha\b|"
                           r"meter\b|kilometer\b|millionen?\b|mio\b|milliarden?\b|mrd\b|tausend\b|grad\b|uhr\b|jahr\w*|einwohner\w*|stunden?\b|minuten?\b|"
                           r"tage?n?\b|wochen?\b|monate?n?\b|mal\b|stück\b|punkte?n?\b|tore?n?\b|kw\b|kwh\b|ps\b|kmh\b|km/h)", re.I)
_WORT_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß'’-]*")
_KEIN_NAME = set("""der die das den dem des ein eine einer eines einem einen er sie es wir ihr du ich man dies diese dieser dieses jener
sein seine ihre ihr unser euer im in am an auf aus bei mit nach von vor zu zum zur und oder aber doch denn weil wenn als wie so da dort hier
laut ja nein nicht kein keine heute morgen gestern übrigens außerdem zudem allerdings jedoch damit dabei dazu davon insgesamt""".split())
_VERBINDER = {"von", "van", "de", "la", "le", "da", "di", "du", "zu", "del", "ten", "ter"}
_UNGEFAEHR = re.compile(r"(?:rund|etwa|ungefähr|ca\.?|circa|zirka|knapp|fast|beinahe|über|mehr als|weniger als|gut|annähernd)\s+$", re.I)
UNGEFAEHR_ANTEIL = 0.1
_MAL = {"tausend": 1e3, "millionen": 1e6, "million": 1e6, "mio": 1e6, "milliarden": 1e9, "milliarde": 1e9, "mrd": 1e9}
_MAL_NACH = re.compile(r"\s*(tausend|millionen|million|mio|milliarden|milliarde|mrd)\b\.?", re.I)


def _zahl_pruefbar(m: re.Match, satz: str) -> bool:
    roh = m.group(0)
    if _EINHEIT_NACH.match(satz, m.end()):
        return True
    werte = _werte(roh)
    return any(w != int(w) or w > KLEINE_ZAHL for w in werte)


def _ungefaehr_belegt(m: re.Match, satz: str, belegt: set[float]) -> bool:
    if not _UNGEFAEHR.search(satz[:m.start()]):
        return False
    mal = _MAL_NACH.match(satz, m.end())
    faktor = _MAL[mal.group(1).lower()] if mal else 1.0
    for w in _werte(m.group(0)):
        x = w * faktor
        if x and any(abs(v - x) <= abs(x) * UNGEFAEHR_ANTEIL for v in belegt):
            return True
    return False


def unbelegte_zahlen(satz: str, belegt: set[float]) -> list[str]:
    out = []
    for m in _ZAHL.finditer(satz or ""):
        if _zahl_pruefbar(m, satz) and not (_werte(m.group(0)) & belegt) and not _ungefaehr_belegt(m, satz, belegt):
            out.append(m.group(0))
    return out


def _tokens(satz: str) -> list[tuple[str, int]]:
    return [(m.group(0).strip("'’-"), m.start()) for m in _WORT_TOKEN.finditer(satz or "")]


def namen(satz: str) -> tuple[list[str], list[str]]:
    toks = _tokens(satz)
    sicher: list[str] = []
    verdacht: list[str] = []
    lauf: list[str] = []

    def lauf_ende():
        kern = [w for w in lauf if w.lower() not in _VERBINDER and w.lower() != "der"]
        if kern and (len(kern) >= 2 or len(kern[0]) >= 3):
            verdacht.append(" ".join(lauf).strip())
        lauf.clear()

    for i, (w, pos) in enumerate(toks):
        vorher = satz[:pos].rstrip()
        satzanfang = i == 0 or vorher.endswith((":", "–", "-", "•", "(", "„", "\""))
        if w[:1].isupper() and not satzanfang and w.lower() not in _KEIN_NAME:
            if len(w) >= 2 and (w.isupper() or re.search(r"\d", w) or re.search(r"[a-zäöüß][A-ZÄÖÜ]", w)):
                lauf_ende()
                sicher.append(w)
                continue
            lauf.append(w)
        elif lauf and i + 1 < len(toks) and toks[i + 1][0][:1].isupper() and (
                w.lower() in _VERBINDER or (w.lower() == "der" and lauf[-1].lower() == "von")):
            lauf.append(w)
        else:
            lauf_ende()
    lauf_ende()
    return sicher, verdacht


def _wortstaemme(text: str) -> set[str]:
    return {w.lower() for w, _ in _tokens(text)}


def name_belegt(name: str, staemme: set[str]) -> bool:
    for teil in name.split():
        t = teil.lower().strip(".,;:")
        if not t or t in _VERBINDER:
            continue
        if t in staemme:
            continue
        kern = t[:max(4, len(t) - 2)]
        if not any(s.startswith(kern) or (len(s) >= 4 and t.startswith(s) and len(t) - len(s) <= 2) for s in staemme):
            return False
    return True


@dataclass(frozen=True)
class Befund:
    satz: str
    zahlen: tuple[str, ...]
    namen: tuple[str, ...]
    verdacht: tuple[str, ...]

    @property
    def sicher_falsch(self) -> bool:
        return bool(self.zahlen or self.namen)


def streng_pruefen(antwort: str, belege: str, *, zahlen_pruefen: bool = True, namen_pruefen=None) -> list[Befund]:
    belegt_d = daten(belege)
    belegt_z = zahlenwerte(belege)
    staemme = _wortstaemme(belege)
    out: list[Befund] = []
    for absatz in (antwort or "").split("\n"):
        for s in _saetze(absatz):
            if s.rstrip().endswith("?"):
                continue
            z = [f"{d[0]}.{d[1]}." + (str(d[2]) if d[2] else "") for d in daten(s) if not _gedeckt_datum(d, belegt_d)]
            if zahlen_pruefen:
                ohne_daten = _DATUM_ISO.sub(" ", _DATUM_WORT.sub(" ", _DATUM_ZAHL.sub(" ", s)))
                z += unbelegte_zahlen(ohne_daten, belegt_z)
            sicher, lauf = namen(s) if (namen_pruefen is None or namen_pruefen(s)) else ([], [])
            n = [x for x in sicher if not name_belegt(x, staemme)]
            v = [x for x in lauf if not name_belegt(x, staemme)]
            if z or n or v:
                out.append(Befund(s, tuple(z), tuple(n), tuple(v)))
    return out


PRUEFER_SYSTEM = ("Du bist ein strenger Prüfer. Du bekommst Quellen und nummerierte Sätze. Prüfe jeden Satz: Stehen alle Personen, Namen, "
                  "Orte, Firmen und Zahlen darin so in den Quellen, und sagen die Quellen dasselbe? Dann ja. Steht etwas davon nicht in den Quellen, "
                  "auch wenn es stimmen könnte, dann nein. Allgemeinwissen zählt nicht. Antworte nur mit einer Zeile je Satz: die Nummer, dann ja "
                  "oder nein, zum Beispiel „1 ja“. Keine Erklärung.")


def pruefer_auftrag(saetze: list[str]) -> str:
    return "Sätze:\n" + "\n".join(f"{i + 1}. {' '.join(s.split())}" for i, s in enumerate(saetze))


def urteil_lesen(text: str, anzahl: int) -> set[int]:
    nein: set[int] = set()
    for m in re.finditer(r"(?m)^\s*(\d{1,2})\s*[.):]?\s*[-–:]?\s*(ja|nein)\b", text or "", re.I):
        i = int(m.group(1)) - 1
        if 0 <= i < anzahl and m.group(2).lower() == "nein":
            nein.add(i)
    return nein


_TRENNER = re.compile(r"^\s*[-–—*_=]{3,}\s*$")
_ZAHLENFRAGE = re.compile(r"(?i)\b(?:wie ?viel\w*|wie hoch|wie groß|wie lang\w*|wie weit|wie alt|wie schwer|wie schnell|wie oft|wie tief|wann|"
                          r"seit wann|bis wann|was kostet|kostet|einwohner\w*|bevölkerung|preis\w*|höhe|länge|fläche|entfernung|anzahl|prozent|"
                          r"gehalt|lohn|temperatur|umsatz|gewicht)\b")


def zahlenfrage(frage: str) -> bool:
    return bool(_ZAHLENFRAGE.search(frage or ""))


def _inhalt(zeile: str) -> bool:
    z = zeile.strip()
    return bool(z) and not _TRENNER.match(z) and not z.endswith(":") and len(_WORT_TOKEN.findall(z)) >= 2


def geruest_bereinigen(text: str) -> str:
    zeilen = (text or "").split("\n")
    out: list[str] = []
    for i, z in enumerate(zeilen):
        s = z.strip()
        if not s:
            out.append("")
            continue
        if _TRENNER.match(s):
            continue
        if s.endswith(":") and not _inhalt(s):
            folgt = next((w.strip() for w in zeilen[i + 1:] if w.strip() and not _TRENNER.match(w.strip())), "")
            if not folgt or folgt.endswith(":"):
                continue
        out.append(z)
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return rest if any(_inhalt(z) for z in rest.split("\n")) else ""


_ZEILE_ANFANG = re.compile(r"^\s*(?:[-–•*]\s+|\d|[A-ZÄÖÜ„“\"'«»(]|\d+\.\s)")
_ZEILE_FALSCH = re.compile(r"^\s*(?:[),;:.!?]|und\b|oder\b|aber\b|sowie\b|sondern\b|denn\b|weil\b|dass\b|[a-zäöüß])")
_KLAMMERN = (("(", ")"), ("[", "]"), ("„", "“"))
_MD_ANFANG = re.compile(r"^(?:#{1,6}\s+|>\s*)?(?:\*\*|__)?")
_TRENNZEILE = re.compile(r"[-–—_*=:|\s]{3,}")
_KLEIN_NACH_SATZ = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}[.!?]\s+[a-zäöüß]")


def brauchbar(text: str) -> bool:
    zeilen = [z for z in (text or "").split("\n") if z.strip()]
    if not zeilen:
        return False
    worte = []
    for z in zeilen:
        s = z.strip()
        if s.startswith("|") or _TRENNZEILE.fullmatch(s):
            continue
        s = _MD_ANFANG.sub("", s).strip()
        worte.append(s)
        if not s:
            continue
        if _ZEILE_FALSCH.match(s) or not (_ZEILE_ANFANG.match(s) or not re.match(r"[\wÄÖÜäöüß]", s)):
            return False
        for auf, zu in _KLAMMERN:
            if s.count(auf) != s.count(zu):
                return False
        if _KLEIN_NACH_SATZ.search(s):
            return False
        for satz in _saetze(s)[1:]:
            if _ZEILE_FALSCH.match(satz):
                return False
    tabelle = any(z.strip().startswith("|") for z in zeilen)
    return tabelle or any(len(re.sub(r"^\s*[-–•*]\s+", "", z).split()) >= 3 for z in worte)


WOERTLICH_WOERTER = 10
WORTLAUT_FREI = ("seite", "ortswissen", "berichtigung", "dokument", "pass")


def _wortliste(text: str) -> list[str]:
    return [w for w in re.findall(r"[0-9a-zäöüß]+", str(text or "").lower()) if not w.isdigit()]


def fremde_texte(quellen) -> list[str]:
    return [str(q.get("text") or "") for q in (quellen or []) if isinstance(q, dict) and q.get("art") not in WORTLAUT_FREI and q.get("text")]


def woertliche_saetze(antwort: str, fremd: list[str], n: int = WOERTLICH_WOERTER) -> list[str]:
    stuecke: set[tuple[str, ...]] = set()
    for t in fremd:
        w = _wortliste(t)
        stuecke.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    if not stuecke:
        return []
    saetze = [s for absatz in (antwort or "").split("\n") for s in _saetze(absatz)]
    woerter: list[str] = []
    satz_von: list[int] = []
    for k, s in enumerate(saetze):
        w = _wortliste(s)
        woerter += w
        satz_von += [k] * len(w)
    laenge = [satz_von.count(k) for k in range(len(saetze))]
    treffer: set[int] = set()
    for i in range(len(woerter) - n + 1):
        if tuple(woerter[i:i + n]) in stuecke:
            for k in set(satz_von[i:i + n]):
                drin = satz_von[i:i + n].count(k)
                if drin >= 5 or drin == laenge[k]:
                    treffer.add(k)
    return [saetze[k] for k in sorted(treffer)]


def saetze_streichen(antwort: str, weg) -> tuple[str, list[str]]:
    raus: list[str] = []
    absaetze = []
    for absatz in (antwort or "").split("\n"):
        bleiben = []
        for s in _saetze(absatz):
            (raus if weg(s) else bleiben).append(s)
        if bleiben or not absatz.strip():
            absaetze.append(" ".join(bleiben))
    rest = re.sub(r"\n{3,}", "\n\n", "\n".join(absaetze)).strip()
    if raus:
        rest = geruest_bereinigen(rest)
    if raus and not rest:
        rest = "Das weiß ich noch nicht."
    return rest, raus


def vergangene_streichen(antwort: str, heute: date) -> tuple[str, list[str]]:
    def vorbei(s: str) -> bool:
        tage = []
        for t, m, j in daten(s):
            try:
                tage.append(date(j or _jahr_fuer(t, m, heute), m, t))
            except ValueError:
                continue
        return bool(tage) and all(d < heute for d in tage)
    return saetze_streichen(antwort, vorbei)


def _jahr_fuer(tag: int, monat: int, heute: date) -> int:
    best = heute.year
    for j in (heute.year - 1, heute.year, heute.year + 1):
        try:
            if abs((date(j, monat, tag) - heute).days) < abs((date(best, monat, tag) - heute).days):
                best = j
        except ValueError:
            continue
    return best


def wochentage_berichtigen(text: str, heute: date) -> tuple[str, int]:
    n = 0

    def ersetzen(m: re.Match) -> str:
        nonlocal n
        wort, punkt, zwischen, datum_text = m.group(1), m.group(2), m.group(3), m.group(4)
        ds = daten(datum_text)
        if len(ds) != 1:
            return m.group(0)
        t, mo, j = next(iter(ds))
        try:
            d = date(j or _jahr_fuer(t, mo, heute), mo, t)
        except ValueError:
            return m.group(0)
        kurz = wort[:2].capitalize() in KURZ and len(wort) <= 2
        richtig = KURZ[d.weekday()] if kurz else WOCHENTAGE[d.weekday()]
        if richtig.lower() == wort.lower():
            return m.group(0)
        n += 1
        return richtig + punkt + zwischen + datum_text

    return _WOCHENTAG_DATUM.sub(ersetzen, text or ""), n


_PLATZHALTER = re.compile(r"\[(?!\d)(?!Quelle)[^\[\]\n]{1,40}\]")
_GRUSS_LUECKE = re.compile(r"(?:(?<=\s)|^)(?:dein|deine|ihr|ihre|euer|eure|von)\s*,?\s*\[[^\[\]\n]{1,40}\]\s*[!.,]?", re.I | re.M)
_ANREDE_LUECKE = re.compile(r"\b(Liebe|Lieber|Hallo|Hi|Servus|Sehr geehrte[r]?)\s*\[[^\[\]\n]{1,40}\]", re.I)
_NUR_GRUSSWORT = re.compile(r"^\s*(?:dein|deine|ihr|ihre|euer|eure|von)\s*[,!.]?\s*$", re.I)


_SELBSTBEZUG = re.compile(r"falsche[nr]? Angabe von mir|ich korrigiere|korrigiere ich|berichtige ich|meine[nr]? (vorige|vorherige|erste|frühere)[nr]? "
                          r"(Antwort|Angabe|Fassung)|(vorige|vorherige)[nr]? Antwort|erste[nr]? Fassung|Entschuldigung|entschuldige|mein Fehler|"
                          r"ich habe mich (geirrt|vertan)|Korrektur:", re.I)
_KLAMMER_SELBST = re.compile(r"\(\s*[^()]{0,200}?\)")


def ohne_selbstbezug(text: str) -> tuple[str, int]:
    n = 0

    def klammer(m: "re.Match[str]") -> str:
        nonlocal n
        if _SELBSTBEZUG.search(m.group(0)):
            n += 1
            return ""
        return m.group(0)
    t = _KLAMMER_SELBST.sub(klammer, text or "")
    t, raus = saetze_streichen(t, lambda s: bool(_SELBSTBEZUG.search(s)))
    n += len(raus)
    if not n:
        return text or "", 0
    return re.sub(r"[ \t]{2,}", " ", t).strip() or "Das weiß ich noch nicht.", n


def ohne_platzhalter(text: str) -> tuple[str, int]:
    t = text or ""
    n = len(_PLATZHALTER.findall(t))
    if not n:
        return t, 0
    t = _GRUSS_LUECKE.sub("", t)
    t = _ANREDE_LUECKE.sub(lambda m: "Guten Tag" if m.group(1).lower().startswith("sehr") else "Hallo", t)
    t = _PLATZHALTER.sub("", t)
    zeilen = [z for z in t.split("\n") if not _NUR_GRUSSWORT.match(z)]
    t = "\n".join(re.sub(r"[ \t]{2,}", " ", re.sub(r"\s+([,.!?])", r"\1", z)).rstrip() for z in zeilen)
    return re.sub(r"\n{3,}", "\n\n", t).strip(), n


_PRUEFEN_FRAGE = re.compile(r"\bwann\b|\bkoste\w*|\bpreis\w*|\bwie (?:viel|hoch|teuer)\b|\bgebühr\w*|\btarif\w*|\bzins\w*|\bspiel\w*|\btermin\w*|"
                            r"\bdatum\b|\bab wann\b|\bbis wann\b|\bgeöffnet\b|\bgeoeffnet\b|\böffnungszeit\w*", re.I)


def pruefen_noetig(frage: str, zeitgebunden: bool) -> bool:
    return zeitgebunden or bool(_PRUEFEN_FRAGE.search(frage or ""))


def rechnet(frage: str) -> bool:
    return bool(re.search(r"\d", frage or "")) and bool(re.search(r"(?i)\bzu je\b|\bje\b|\bmal\b|[×x*+/−-]\s*\d|\bzusammen\b|\binsgesamt\b|\bsumme\b|\bprozent von\b|%\s*von|\brabatt\b|was kostet das", frage or ""))


__all__ = ["daten", "betraege", "unbelegte_streichen", "wochentage_berichtigen", "ohne_platzhalter", "pruefen_noetig", "rechnet", "zahlenfrage", "geruest_bereinigen", "brauchbar",
           "streng_pruefen", "Befund", "namen", "name_belegt", "unbelegte_zahlen", "KLEINE_ZAHL", "PRUEFER_SYSTEM", "pruefer_auftrag", "urteil_lesen"]
