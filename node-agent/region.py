# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

LAENDER = {"de": "Deutschland", "at": "Österreich", "ch": "Schweiz"}
SPRACHE = {"de": "de-DE", "at": "de-AT", "ch": "de-CH"}


@dataclass(frozen=True)
class Region:
    land: str
    gebiet: str = ""
    name: str = ""

    @property
    def land_name(self) -> str:
        return LAENDER[self.land]

    @property
    def sprache(self) -> str:
        return SPRACHE[self.land]

    def text(self) -> str:
        return f"{self.land_name} ({self.name})" if self.name else self.land_name


GEBIETE: tuple[tuple[str, str, str, str], ...] = (
    ("de", "BW", "Baden-Württemberg", r"baden[\s-]?württemberg|baden[\s-]?wuerttemberg"),
    ("de", "BY", "Bayern", r"bayern|bayerisch\w*|freistaat bayern"),
    ("de", "BE", "Berlin", r"berlin\w*"),
    ("de", "BB", "Brandenburg", r"brandenburg"),
    ("de", "HB", "Bremen", r"bremen|bremerhaven"),
    ("de", "HH", "Hamburg", r"hamburg\w*"),
    ("de", "HE", "Hessen", r"hessen|hessisch\w*"),
    ("de", "MV", "Mecklenburg-Vorpommern", r"mecklenburg[\s-]?vorpommern|mecklenburg|vorpommern"),
    ("de", "NI", "Niedersachsen", r"niedersachsen|niedersächsisch\w*"),
    ("de", "NW", "Nordrhein-Westfalen", r"nordrhein[\s-]?westfalen|\bnrw\b"),
    ("de", "RP", "Rheinland-Pfalz", r"rheinland[\s-]?pfalz"),
    ("de", "SL", "Saarland", r"saarland"),
    ("de", "SN", "Sachsen", r"(?<![-\w])sachsen(?![-\w])|sächsisch\w*"),
    ("de", "ST", "Sachsen-Anhalt", r"sachsen[\s-]anhalt"),
    ("de", "SH", "Schleswig-Holstein", r"schleswig[\s-]?holstein"),
    ("de", "TH", "Thüringen", r"thüringen|thueringen|thüringisch\w*"),
    ("at", "W", "Wien", r"wien(?![\wäöü])"),
    ("at", "NÖ", "Niederösterreich", r"niederösterreich|niederoesterreich"),
    ("at", "OÖ", "Oberösterreich", r"oberösterreich|oberoesterreich"),
    ("at", "S", "Salzburg", r"salzburg\w*"),
    ("at", "ST", "Steiermark", r"steiermark|steirisch\w*"),
    ("at", "K", "Kärnten", r"kärnten|kaernten"),
    ("at", "T", "Tirol", r"(?<!süd)(?<!sued)tirol"),
    ("at", "V", "Vorarlberg", r"vorarlberg"),
    ("at", "B", "Burgenland", r"burgenland"),
    ("ch", "ZH", "Kanton Zürich", r"zürich|zuerich"),
    ("ch", "BE", "Kanton Bern", r"(?<![-\w])bern(?![-\w])"),
    ("ch", "LU", "Kanton Luzern", r"luzern"),
    ("ch", "UR", "Kanton Uri", r"kanton uri"),
    ("ch", "SZ", "Kanton Schwyz", r"schwyz"),
    ("ch", "OW", "Kanton Obwalden", r"obwalden"),
    ("ch", "NW", "Kanton Nidwalden", r"nidwalden"),
    ("ch", "GL", "Kanton Glarus", r"glarus"),
    ("ch", "ZG", "Kanton Zug", r"kanton zug|stadt zug|in zug\b"),
    ("ch", "FR", "Kanton Freiburg", r"fribourg|freiburg im üechtland|kanton freiburg"),
    ("ch", "SO", "Kanton Solothurn", r"solothurn"),
    ("ch", "BS", "Kanton Basel-Stadt", r"basel[\s-]?stadt|(?<![-\w])basel(?![-\w])"),
    ("ch", "BL", "Kanton Basel-Landschaft", r"basel[\s-]?land\w*|baselbiet"),
    ("ch", "SH", "Kanton Schaffhausen", r"schaffhausen"),
    ("ch", "AR", "Kanton Appenzell Ausserrhoden", r"appenzell ausserrhoden"),
    ("ch", "AI", "Kanton Appenzell Innerrhoden", r"appenzell innerrhoden|(?<![-\w])appenzell(?![-\w])(?! ausserrhoden)"),
    ("ch", "SG", "Kanton St. Gallen", r"st\.?\s?gallen|sankt gallen"),
    ("ch", "GR", "Kanton Graubünden", r"graubünden|graubuenden|chur\b|davos|st\.?\s?moritz"),
    ("ch", "AG", "Kanton Aargau", r"aargau|aarau"),
    ("ch", "TG", "Kanton Thurgau", r"thurgau|frauenfeld"),
    ("ch", "TI", "Kanton Tessin", r"tessin|ticino|lugano|bellinzona|locarno"),
    ("ch", "VD", "Kanton Waadt", r"waadt|vaud|lausanne|montreux"),
    ("ch", "VS", "Kanton Wallis", r"wallis|valais|sion|zermatt|visp|brig\b"),
    ("ch", "NE", "Kanton Neuenburg", r"neuenburg|neuchâtel|neuchatel"),
    ("ch", "GE", "Kanton Genf", r"genf|genève|geneve"),
    ("ch", "JU", "Kanton Jura", r"kanton jura|delémont|delemont"),
)

STAEDTE: tuple[tuple[str, str, str], ...] = (
    ("de", "BY", r"münchen|muenchen|nürnberg|nuernberg|augsburg|regensburg|würzburg|wuerzburg|ingolstadt|passau|rosenheim|erlangen|fürth|bamberg|bayreuth|landshut|kempten"),
    ("de", "BW", r"stuttgart|karlsruhe|mannheim|freiburg(?! im üechtland)|heidelberg|(?<![-\w])ulm(?![-\w])|konstanz|heilbronn|pforzheim|reutlingen|tübingen"),
    ("de", "BB", r"potsdam|cottbus|frankfurt \(oder\)|frankfurt an der oder"),
    ("de", "HE", r"frankfurt(?! \(oder\))(?! an der oder)|wiesbaden|kassel|darmstadt|offenbach|marburg"),
    ("de", "MV", r"rostock|schwerin|greifswald|stralsund"),
    ("de", "NI", r"hannover|braunschweig|osnabrück|oldenburg|göttingen|wolfsburg|hildesheim|salzgitter|lüneburg"),
    ("de", "NW", r"köln|koeln|düsseldorf|duesseldorf|dortmund|duisburg|bochum|wuppertal|bielefeld|(?<![-\w])bonn(?![-\w])|münster|aachen|gelsenkirchen|"
                 r"mönchengladbach|krefeld|oberhausen|hagen\b|hamm\b|leverkusen|paderborn|(?:in|aus) essen\b"),
    ("de", "RP", r"mainz|koblenz|trier|kaiserslautern|ludwigshafen|worms"),
    ("de", "SL", r"saarbrücken|saarbruecken"),
    ("de", "SN", r"dresden|leipzig|chemnitz|zwickau"),
    ("de", "ST", r"magdeburg|dessau|(?:in|aus) halle\b|halle \(saale\)|halle an der saale"),
    ("de", "SH", r"(?<![-\w])kiel(?![-\w])|lübeck|luebeck|flensburg|neumünster"),
    ("de", "TH", r"erfurt|(?<![-\w])jena(?![-\w])|weimar|(?<![-\w])gera(?![-\w])|gotha|eisenach"),
    ("at", "OÖ", r"(?<![-\w])linz(?![-\w])|(?<![-\w])wels(?![-\w])|(?<![-\w])steyr(?![-\w])|gmunden|vöcklabruck|voecklabruck|traun\b|laakirchen|bad ischl|braunau|ried im innkreis|freistadt|leonding"),
    ("at", "ST", r"(?<![-\w])graz(?![-\w])|leoben|kapfenberg|bruck an der mur|schladming"),
    ("at", "T", r"innsbruck|kufstein|kitzbühel|kitzbuehel|lienz|schwaz|ischgl|sölden"),
    ("at", "K", r"klagenfurt|villach|wolfsberg|spittal"),
    ("at", "NÖ", r"st\.?\s?pölten|sankt pölten|wiener neustadt|krems|baden bei wien|mödling|amstetten|tulln"),
    ("at", "V", r"dornbirn|bregenz|feldkirch|bludenz"),
    ("at", "B", r"eisenstadt|neusiedl|oberwart"),
    ("ch", "ZH", r"winterthur|uster"),
    ("ch", "BE", r"(?<![-\w])biel(?![-\w])|(?<![-\w])thun(?![-\w])|interlaken|burgdorf"),
)

MARKEN: tuple[tuple[str, str], ...] = (
    ("de", r"deutschland|deutsche[nrs]?\b(?! sprache)|bundesrepublik|deutsche bahn|\bdb\b|\bice\b|bahncard|deutschlandticket|49[-\s]?euro[-\s]?ticket|\brewe\b|\bedeka\b|kaufland|"
           r"\bdfb\b|\bdfl\b|2\. bundesliga|bundestag|bundeskanzler(?:in)? von deutschland|elterngeld|bürgergeld"),
    ("at", r"österreich\w*|oesterreich\w*|\böbb\b|\boebb\b|klimaticket|\bbilla\b|\bhofer\b|lagerhaus|\bams\b|finanzonline|nationalrat"),
    ("ch", r"schweiz\w*|\bsbb\b|halbtax|generalabonnement|\bmigros\b|eidgenoss\w*|bundesrat der schweiz|\bchf\b"),
)

_GEBIETE_RE = [(land, kurz, name, re.compile(rf"(?<![\wäöü]){muster}", re.I)) for land, kurz, name, muster in GEBIETE]
_STAEDTE_RE = [(land, kurz, re.compile(rf"(?<![\wäöü])(?:{muster})", re.I)) for land, kurz, muster in STAEDTE]
_MARKEN_RE = [(land, re.compile(rf"(?<![\wäöü])(?:{muster})", re.I)) for land, muster in MARKEN]
_NAME = {(land, kurz): name for land, kurz, name, _ in GEBIETE}


def erkennen(text: str) -> Region | None:
    t = text or ""
    funde: list[tuple[int, str, str]] = []
    for land, kurz, _name, rx in _GEBIETE_RE:
        for m in rx.finditer(t):
            funde.append((m.start(), land, kurz))
    for land, kurz, rx in _STAEDTE_RE:
        for m in rx.finditer(t):
            funde.append((m.start(), land, kurz))
    for land, rx in _MARKEN_RE:
        for m in rx.finditer(t):
            funde.append((m.start(), land, ""))
    if not funde:
        return None
    funde.sort()
    zahl: dict[str, int] = {}
    for _, land, _ in funde:
        zahl[land] = zahl.get(land, 0) + 1
    erster = {}
    for pos, land, _ in funde:
        erster.setdefault(land, pos)
    land = max(zahl, key=lambda x: (zahl[x], -erster[x]))
    gebiet = next((kurz for _, l, kurz in funde if l == land and kurz), "")
    return Region(land, gebiet, _NAME.get((land, gebiet), ""))


__all__ = ["Region", "erkennen", "LAENDER", "SPRACHE", "GEBIETE"]
