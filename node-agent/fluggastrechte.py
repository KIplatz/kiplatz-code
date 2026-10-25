# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import math
import re
from pathlib import Path

GEMACHT = "gerechnet, ohne Modell"
WOHER = ("EU-Verordnung 261/2004 über Fluggastrechte, Entfernung als Luftlinie zwischen den Flughäfen (OurAirports, Public Domain), "
         "vom Programm gerechnet, ohne Modell.")
DATEI = Path(__file__).with_name("flughaefen.tsv")
EU_RAUM = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS NO LI CH".split())
_ORTE = {"wien": "VIE", "vienna": "VIE", "münchen": "MUC", "muenchen": "MUC", "mailand": "MXP", "milano": "MXP", "rom": "FCO", "roma": "FCO",
         "venedig": "VCE", "neapel": "NAP", "florenz": "FLR", "lissabon": "LIS", "kopenhagen": "CPH", "brüssel": "BRU", "bruessel": "BRU",
         "prag": "PRG", "warschau": "WAW", "athen": "ATH", "kairo": "CAI", "köln": "CGN", "koeln": "CGN", "nürnberg": "NUE", "genf": "GVA",
         "zürich": "ZRH", "zuerich": "ZRH", "london": "LHR", "paris": "CDG", "new york": "JFK", "istanbul": "IST", "teneriffa": "TFS",
         "mallorca": "PMI", "palma": "PMI", "kreta": "HER", "heraklion": "HER", "rhodos": "RHO", "korfu": "CFU", "zypern": "LCA",
         "larnaka": "LCA", "antalya": "AYT", "hurghada": "HRG", "dubai": "DXB", "bukarest": "OTP", "belgrad": "BEG", "sofia": "SOF",
         "krakau": "KRK", "danzig": "GDN", "stockholm": "ARN", "oslo": "OSL", "helsinki": "HEL", "dublin": "DUB", "edinburgh": "EDI",
         "amsterdam": "AMS", "frankfurt": "FRA", "düsseldorf": "DUS", "duesseldorf": "DUS", "hamburg": "HAM", "berlin": "BER",
         "stuttgart": "STR", "graz": "GRZ", "linz": "LNZ", "salzburg": "SZG", "innsbruck": "INN", "klagenfurt": "KLU", "bratislava": "BTS",
         "pressburg": "BTS", "budapest": "BUD", "zagreb": "ZAG", "split": "SPU", "barcelona": "BCN", "madrid": "MAD", "malaga": "AGP",
         "sevilla": "SVQ", "valencia": "VLC", "nizza": "NCE", "marseille": "MRS", "lyon": "LYS", "porto": "OPO", "faro": "FAO",
         "tokio": "HND", "peking": "PEK", "bangkok": "BKK", "los angeles": "LAX", "chicago": "ORD", "miami": "MIA", "toronto": "YYZ",
         "kapstadt": "CPT", "marrakesch": "RAK", "agadir": "AGA", "tunis": "TUN", "djerba": "DJE", "malta": "MLA", "gran canaria": "LPA",
         "fuerteventura": "FUE", "lanzarote": "ACE", "ibiza": "IBZ", "sharm el-sheikh": "SSH", "marsa alam": "RMF", "doha": "DOH",
         "abu dhabi": "AUH", "malediven": "MLE", "phuket": "HKT", "singapur": "SIN", "hongkong": "HKG", "memmingen": "FMM",
         "friedrichshafen": "FDH", "basel": "BSL", "luxemburg": "LUX", "manchester": "MAN", "glasgow": "GLA", "bologna": "BLQ",
         "pisa": "PSA", "catania": "CTA", "palermo": "PMO", "bari": "BRI", "thessaloniki": "SKG", "kos": "KGS", "zadar": "ZAD",
         "dubrovnik": "DBV", "burgas": "BOJ", "varna": "VAR", "riga": "RIG", "tallinn": "TLL", "vilnius": "VNO", "reykjavik": "KEF"}
_FALL = re.compile(r"(?i)\b(?:verspät\w*|verspaet\w*|verzöger\w*|annull\w*|gestrichen\w*|storniert\w*|abgesagt\w*|ausgefallen\w*|überbuch\w*|"
                   r"nichtbeförderung|nicht\s+mitgenommen|delay\w*|late|cancel\w*|overbook\w*|denied\s+boarding)")
_FLUG = re.compile(r"(?i)\b(?:flug\w*|flüge|flight\w*|maschine|flieger|airline|fluglinie|fluggesellschaft|abflug|landung)")
_ANSPRUCH = re.compile(r"(?i)\b(?:entschädig\w*|zusteh\w*|zustand|steht\s+mir|geld|anspruch\w*|erstatt\w*|ausgleich\w*|rechte|bekomme\s+ich|kriege\s+ich|"
                       r"compensation|claim|entitled|refund|rights|owed|get\s+back)")
_RECHTE = re.compile(r"(?i)\b(?:fluggastrecht\w*|261/2004|eu\s?261|uk\s?261|passagierrecht\w*|air\s+passenger\s+rights)\b")
_STUNDEN = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*(?:stunden|stunde|std\.?|h\b|hours?|hrs?)")
_MINUTEN = re.compile(r"(?i)(\d+)\s*(?:minuten|min\.?|minutes?)")
RUECKFRAGE_ANFANG = "Damit ich ausrechnen kann, was dir zusteht, brauche ich noch"
RUECKFRAGE_ANFANG_EN = "So I can work out what you're owed, I still need"
_flughaefen: dict[str, tuple] | None = None


def _laden() -> dict[str, tuple]:
    global _flughaefen
    if _flughaefen is None:
        daten = {}
        try:
            for z in DATEI.read_text(encoding="utf-8").splitlines():
                if not z or z.startswith("#"):
                    continue
                t = z.split("\t")
                if len(t) >= 7:
                    daten[t[0]] = (t[0], t[1], t[2], t[3], t[4], float(t[5]), float(t[6]), t[7] if len(t) > 7 else "")
        except (OSError, ValueError):
            daten = {}
        _flughaefen = daten
    return _flughaefen


_FUELL = {"flug", "flight", "mein", "meine", "my", "der", "die", "das", "the", "ab", "von", "from", "nach", "to", "mit", "with", "war", "was"}


def flughafen(text: str, streng: bool = False):
    t = " ".join(str(text or "").split()).strip(" ,.;:!?„“\"'()")
    daten = _laden()
    if not t or not daten:
        return None
    if re.fullmatch(r"[A-Z]{3}", t) and t in daten:
        return daten[t]
    klein = t.lower()
    if klein in _FUELL:
        return None
    if klein in _ORTE and _ORTE[klein] in daten:
        return daten[_ORTE[klein]]
    passend = [f for f in daten.values() if f[2].lower().split(",")[0].strip() == klein or klein == f[1].lower()]
    if not passend and not streng:
        passend = [f for f in daten.values() if len(klein) >= 4 and (klein in f[1].lower().split() or klein in f[1].lower() or klein in f[7].lower())]
    return sorted(passend, key=lambda f: (f[4] != "l", len(f[1])))[0] if passend else None


def name_de(f) -> str:
    for k, v in _ORTE.items():
        if v == f[0]:
            return " ".join(w[:1].upper() + w[1:] for w in k.split())
    return (f[2] or f[1]).split(" (")[0]


def _strecke(text: str):
    t = " ".join(str(text or "").split())

    def nach_wort(muster: str):
        for m in re.finditer(muster + r"\s+([^,;:!?()]{2,40})", t):
            f = _finden(re.split(r"(?i)\s+(?:nach|to|von|ab|from|und|and|mit|with|war|was)\s+", m.group(1))[0])
            if f:
                return f
        return None
    von, nach = nach_wort(r"(?i)\b(?:von|ab|from)"), nach_wort(r"(?i)\b(?:nach|to)")
    if von and nach and von[0] != nach[0]:
        return von, nach
    reihe = [f for f in _der_reihe_nach(t) if f]
    if von and not nach:
        nach = next((f for f in reihe if f[0] != von[0]), None)
    elif nach and not von:
        von = next((f for f in reihe if f[0] != nach[0]), None)
    elif not (von and nach and von[0] != nach[0]):
        von, nach = (reihe + [None, None])[:2]
    return von, nach


def _finden(ort: str):
    w = [x.strip(" .„“\"'") for x in ort.split()]
    for n in range(min(len(w), 4), 0, -1):
        f = flughafen(" ".join(w[:n]), streng=True)
        if f:
            return f
    return flughafen(" ".join(w[:3])) if len(w) <= 3 else None


def _der_reihe_nach(t: str):
    w = [x.strip(" ,.;:!?„“\"'()") for x in re.split(r"[\s\-–—→/>]+", t)]
    gefunden, i = [], 0
    while i < len(w) and len(gefunden) < 2:
        for n in (3, 2, 1):
            s = " ".join(w[i:i + n])
            f = flughafen(s, streng=True) if s[:1].isupper() and len(w[i:i + n]) == n else None
            if f and (not gefunden or f[0] != gefunden[-1][0]):
                gefunden.append(f)
                i += n
                break
        else:
            i += 1
    return (gefunden[0] if gefunden else None, gefunden[1] if len(gefunden) > 1 else None)


def entfernung_km(a, b) -> int:
    la1, lo1, la2, lo2 = map(math.radians, (a[5], a[6], b[5], b[6]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(2 * 6371.0 * math.asin(math.sqrt(h)))


def _art(text: str) -> str:
    if re.search(r"(?i)\b(?:annull\w*|gestrichen\w*|storniert\w*|abgesagt\w*|ausgefallen\w*|cancel\w*)", text):
        return "annullierung"
    if re.search(r"(?i)\b(?:überbuch\w*|nichtbeförderung|nicht\s+mitgenommen|overbook\w*|denied\s+boarding)", text):
        return "nichtbefoerderung"
    return "verspaetung"


def _stunden(text: str) -> float | None:
    h, m = _STUNDEN.search(text), _MINUTEN.search(text)
    if not h and not m:
        return None
    return (float(h.group(1).replace(",", ".")) if h else 0.0) + (int(m.group(1)) / 60 if m else 0.0)


def gewuenscht(text: str) -> bool:
    t = str(text or "")
    return bool((_FALL.search(t) and (_FLUG.search(t) or _RECHTE.search(t)) and (_ANSPRUCH.search(t) or _RECHTE.search(t))))


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


_EN = {"VIE": "Vienna", "MUC": "Munich", "MXP": "Milan", "FCO": "Rome", "VCE": "Venice", "NAP": "Naples", "FLR": "Florence", "LIS": "Lisbon",
       "CPH": "Copenhagen", "BRU": "Brussels", "PRG": "Prague", "WAW": "Warsaw", "ATH": "Athens", "CAI": "Cairo", "CGN": "Cologne", "NUE": "Nuremberg",
       "GVA": "Geneva", "ZRH": "Zurich", "TFS": "Tenerife", "HER": "Heraklion", "RHO": "Rhodes", "CFU": "Corfu", "LCA": "Larnaca", "OTP": "Bucharest",
       "BEG": "Belgrade", "KRK": "Krakow", "GDN": "Gdansk", "HND": "Tokyo", "PEK": "Beijing", "CPT": "Cape Town", "RAK": "Marrakesh",
       "MLE": "Maldives", "SIN": "Singapore", "HKG": "Hong Kong", "LUX": "Luxembourg", "DUS": "Dusseldorf", "BTS": "Bratislava", "KEF": "Reykjavik", "NCE": "Nice"}


def name_en(f) -> str:
    return _EN.get(f[0]) or name_de(f)


def antwort(nachrichten: list[dict]) -> tuple[str, str] | None:
    if not nachrichten or nachrichten[-1].get("role") != "user":
        return None
    letzte = str(nachrichten[-1].get("content", ""))
    vorige = next((str(n.get("content", "")) for n in reversed(nachrichten[:-1]) if n.get("role") == "assistant"), "")
    nach_rueckfrage = vorige.startswith(RUECKFRAGE_ANFANG) or vorige.startswith(RUECKFRAGE_ANFANG_EN)
    if nach_rueckfrage:
        frueher = [str(n.get("content", "")) for n in nachrichten[:-1] if n.get("role") == "user"]
        text = " ".join(frueher[-1:] + [letzte])
    else:
        text = letzte
    if not gewuenscht(text):
        return None
    art = _art(text)
    von, nach = _strecke(text)
    std = _stunden(text)
    fehlt = []
    if von is None or nach is None:
        fehlt.append(("von welchem Flughafen nach welchem du geflogen bist, etwa „von Wien nach London“",
                      "which airport you flew from and to, for example “from Vienna to London”"))
    if art == "verspaetung" and std is None:
        fehlt.append(("wie viele Stunden du am Ziel zu spät angekommen bist", "how many hours late you arrived at your destination"))
    if fehlt and not nach_rueckfrage:
        de = RUECKFRAGE_ANFANG + (": " + fehlt[0][0] + "." if len(fehlt) == 1 else ":\n" + "\n".join(f"- {f[0][0].upper()}{f[0][1:]}" for f in fehlt))
        en = RUECKFRAGE_ANFANG_EN + (": " + fehlt[0][1] + "." if len(fehlt) == 1 else ":\n" + "\n".join(f"- {f[1][0].upper()}{f[1][1:]}" for f in fehlt))
        return de, en
    if von is None or nach is None:
        return ("Ich habe die Flughäfen nicht sicher gefunden. Schreib sie mit Stadt oder dem dreistelligen Code, etwa „von VIE nach LHR“, dann rechne "
                "ich aus, was dir nach der EU-Verordnung 261/2004 zusteht: 250, 400 oder 600 € je nach Entfernung.",
                "I couldn't identify the airports for certain. Write them as cities or three-letter codes, for example “from VIE to LHR”, and I'll work "
                "out what you're owed under EU Regulation 261/2004: €250, €400 or €600 depending on distance.")
    return _berechnen(von, nach, art, std)


def _berechnen(von, nach, art: str, std: float | None) -> tuple[str, str]:
    km = entfernung_km(von, nach)
    ab_eu, an_eu = von[3] in EU_RAUM, nach[3] in EU_RAUM
    uk = von[3] == "GB" or (nach[3] == "GB" and not ab_eu)
    strecke_de = f"{name_de(von)} ({von[0]}) nach {name_de(nach)} ({nach[0]}), rund {_zahl(km)} km Luftlinie,"
    strecke_en = f"{name_en(von)} ({von[0]}) to {name_en(nach)} ({nach[0]}), about {km:,} km as the crow flies"
    if not (ab_eu or uk or an_eu or nach[3] == "GB"):
        return (f"Dein Flug von {strecke_de} beginnt und endet außerhalb der EU. Die EU-Verordnung 261/2004 gilt dafür nicht; was dir zusteht, regeln "
                "dann das Recht des Abfluglands und die Bedingungen der Fluglinie.",
                f"Your flight from {strecke_en} starts and ends outside the EU. EU Regulation 261/2004 doesn't apply; what you're owed then depends "
                "on the law of the departure country and the airline's terms.")
    innereu = ab_eu and an_eu
    if km <= 1500:
        betrag = 250
    elif innereu or km <= 3500:
        betrag = 400
    else:
        betrag = 600
    halb = False
    if art == "verspaetung" and std is not None and 3 <= std < 4 and betrag == 600:
        betrag, halb = 300, True
    if uk:
        betrag = {250: 220, 400: 350, 600: 520, 300: 260}[betrag]
    geld_de, geld_en = (f"{betrag} Pfund", f"£{betrag}") if uk else (f"{betrag} €", f"€{betrag}")
    regel_de = "der britischen Fassung der Verordnung (UK261)" if uk else "der EU-Verordnung 261/2004"
    regel_en = "the UK version of the regulation (UK261)" if uk else "EU Regulation 261/2004"
    de, en = [], []
    if art == "verspaetung" and std is not None and std < 3:
        de.append(f"Für deinen Flug von {strecke_de} gibt es bei {_zahl_std(std)} Verspätung am Ziel noch keine Entschädigung: nach {regel_de} "
                  f"steht sie erst ab drei Stunden zu. Ab drei Stunden wären es {geld_de}.")
        en.append(f"For your flight from {strecke_en}, arriving {_zahl_std_en(std)} late isn't enough for compensation: under {regel_en} "
                  f"it starts at three hours. From three hours it would be {geld_en}.")
        de.append("Wartest du am Flughafen lange, muss die Fluglinie aber für Essen und Getränke sorgen, bei Kurzstrecken ab zwei Stunden, bei längeren "
                  "Flügen ab drei bis vier Stunden, und über Nacht für ein Hotel.")
        en.append("If you wait a long time at the airport, the airline still has to provide food and drink, from two hours on short flights and from "
                  "three to four hours on longer ones, and a hotel overnight.")
    else:
        was = {"verspaetung": (f"du {_zahl_std(std)} zu spät angekommen bist", f"you arrived {_zahl_std_en(std)} late"),
               "annullierung": ("der Flug annulliert wurde", "the flight was cancelled"),
               "nichtbefoerderung": ("du gegen deinen Willen nicht mitgenommen wurdest", "you were denied boarding against your will")}[art]
        de.append(f"Für deinen Flug von {strecke_de} stehen dir nach {regel_de} {geld_de} je Person zu, weil {was[0]}.")
        en.append(f"For your flight from {strecke_en}, you're owed {geld_en} per person under {regel_en}, because {was[1]}.")
        if halb:
            voll_de, voll_en = ("520 Pfund", "£520") if uk else ("600 €", "€600")
            de.append(f"Bei mehr als 3.500 km und 3 bis 4 Stunden Verspätung darf die Fluglinie die {voll_de} halbieren; ab 4 Stunden sind es {voll_de}.")
            en.append(f"On flights over 3,500 km with a delay of 3 to 4 hours the airline may halve the {voll_en}; from 4 hours it's {voll_en}.")
        if art == "annullierung":
            de.append("Kein Anspruch besteht, wenn du mindestens 14 Tage vorher informiert wurdest; bei kürzerer Frist und einem Ersatzflug, der nur wenig "
                      "früher geht oder später ankommt, darf die Fluglinie den Betrag halbieren. Dazu hast du die Wahl zwischen Ersatzflug und Geld zurück.")
            en.append("You're not entitled if you were told at least 14 days in advance; with shorter notice and a replacement flight that leaves only "
                      "slightly earlier or arrives slightly later, the airline may halve the amount. You can also choose between a replacement flight "
                      "and a refund.")
    if not ab_eu and von[3] != "GB":
        if uk:
            de.append("Weil der Flug außerhalb Großbritanniens beginnt, gilt das nur, wenn die Fluglinie aus Großbritannien oder der EU kommt.")
            en.append("Because the flight starts outside the UK, this only applies if the airline is based in the UK or the EU.")
        else:
            de.append("Weil der Flug außerhalb der EU beginnt, gilt das nur, wenn die Fluglinie aus der EU, Island, Norwegen oder der Schweiz kommt.")
            en.append("Because the flight starts outside the EU, this only applies if the airline is based in the EU, Iceland, Norway or Switzerland.")
    de.append("Keinen Anspruch gibt es bei außergewöhnlichen Umständen, etwa Unwetter, Streik der Fluglotsen oder Sicherheitsrisiken; ein Streik des eigenen "
              "Personals der Fluglinie zählt laut Europäischem Gerichtshof in der Regel nicht dazu.")
    en.append("There's no entitlement in extraordinary circumstances such as severe weather, an air traffic control strike or security risks; according "
              "to the European Court of Justice, a strike by the airline's own staff usually doesn't count.")
    de.append("So gehst du vor: schriftlich bei der Fluglinie, mit Buchungsnummer, Flugnummer, Datum und dem Betrag. Zahlt sie nicht, helfen kostenlos in "
              "Österreich die Agentur für Passagier- und Fahrgastrechte (apf), in Deutschland die Schlichtungsstelle söp. Die Entfernung ist die Luftlinie zwischen den Flughäfen, so wie die "
              "Verordnung rechnet.")
    en.append("What to do: write to the airline with your booking number, flight number, date and the amount. If it doesn't pay, the national "
              "enforcement body or a free arbitration service in your country can help. The distance is the straight line between the airports, as "
              "the regulation counts it.")
    return "\n\n".join(de), "\n\n".join(en)


def _zahl_std(std: float | None) -> str:
    if std is None:
        return "mehr als 3 Stunden"
    h, m = divmod(round(std * 60), 60)
    teile = ([f"{h} Stunde" + ("" if h == 1 else "n")] if h else []) + ([f"{m} Minute" + ("" if m == 1 else "n")] if m else [])
    return " ".join(teile) or "0 Minuten"


def _zahl_std_en(std: float | None) -> str:
    if std is None:
        return "more than 3 hours"
    h, m = divmod(round(std * 60), 60)
    teile = ([f"{h} hour" + ("" if h == 1 else "s")] if h else []) + ([f"{m} minute" + ("" if m == 1 else "s")] if m else [])
    return " and ".join(teile) or "0 minutes"
