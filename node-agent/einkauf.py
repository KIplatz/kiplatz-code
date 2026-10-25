# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

VERGLEICHS_HOSTS = ("geizhals.", "idealo.", "preisvergleich.", "compiral.", "guenstiger.de", "billiger.de", "check24.", "preis.de", "testberichte.de",
                    "pricerunner.", "shopping.google.", "preissuchmaschine.", "preisrunter.", "reifen-vergleich", "tyre-price", "reifentiefpreis.",
                    "testbericht.de", "idealo.at", "geizkragen.")
KEIN_HAENDLER = ("youtube.", "wikipedia.", "reddit.", "facebook.", "instagram.", "tiktok.", "x.com", "twitter.", "willhaben.", "ebay-kleinanzeigen.",
                 "kleinanzeigen.de", "chip.de", "computerbild.", "heise.de", "krone.at", "bild.de", "test.de", "adac.de", "oeamtc.at", "autobild.",
                 "bussgeldkatalog.", "bpb.de", "urlaubstracker.", "mydealz.", "preisjaeger.", "smarthomeassistent.")
_GROESSE = re.compile(r"(?<!\d)(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2})(?!\d)", re.I)
_SPEICHER = re.compile(r"(?<![\w.])(\d{1,4})\s*(GB|TB)\b", re.I)
_CODE = re.compile(r"(?<![\w.-])((?:[A-Za-z]{1,8}-?\d[\w-]*)|(?:\d{2,}\.\d{2,}))(?![\w])")
_NAME_ZAHL = re.compile(r"\b([A-Za-zÄÖÜäöüß][A-Za-zäöüß]{2,}|[A-Z]{2,})\s+(\d{1,4})(?![\d.,/]|\s*(?:GB|TB|Zoll|cm|mm|Stück|stk|x|%|€|Euro|Jahre|Uhr))\b")
VARIANTENWORTE = ("pro", "plus", "max", "ultra", "slim", "mini", "lite", "digital", "fe", "se", "air", "neo")
ANSCHLUSS = {"usbc": ("lightning",), "lightning": ("usbc",)}
_INDEX = re.compile(r"^\d{2,3}[A-Za-z]{1,2}$")
_JAHR = re.compile(r"^(?:19|20)\d\d$")
_KEINE_SACHE = re.compile(
    r"(?i)^(?:wo|wie|was|wer|er|sie|ihn|diese\w*|welche\w*|ist|sind|am|im|in|aus|bei|für|fuer|von|vom|zum|zur|der|die|das|den|dem|des|ein\w*|mir|mich|ich|du|uns|es|"
    r"zeig\w*|such\w*|find\w*|gib|gibt|bekomm\w*|krieg\w*|kauf\w*|bestell\w*|kost\w*|preis\w*|günstig\w*|guenstig\w*|billig\w*|preiswert\w*|"
    r"anbieter\w*|händler\w*|haendler\w*|shops?|angebot\w*|vergleich\w*|bester?n?|testbewert\w*|testbericht\w*|test\w*|bewert\w*|woanders|"
    r"sonst|online|internet|bitte|jetzt|aktuell\w*|heute|und|oder|dazu|davon|lohnt|sich|möchte|moechte|will|brauche|suche|neu\w*|"
    r"cheap\w*|cheapest|price\w*|buy|where|which|best|deals?|offers?|is|the|a|an|for|in|to|me|find|get|online|shop|store|"
    r"deutschland|österreich|oesterreich|schweiz|germany|austria|switzerland|italien|italy|frankreich|france|spanien|spain|uk|usa|"
    r"stück|stueck|reifen\b)$")


@dataclass(frozen=True)
class Angebot:
    haendler: str
    preis: float
    adresse: str
    herkunft: str


def _norm(t: str) -> str:
    s = str(t).lower().replace("ß", "ss").replace("playstation", "ps")
    s = re.sub(r"\b(?:gq|qe|qn)(?=\d{2}[a-z])", "q", s)
    s = re.sub(r"\b(?:gu|ue|un)(?=\d{2}[a-z])", "u", s)
    return re.sub(r"[^a-z0-9/]", "", s)


def host(adresse: str) -> str:
    return re.sub(r"^www\d?\.", "", re.sub(r"^https?://", "", str(adresse)).split("/")[0].lower())


def ist_vergleichsseite(adresse: str, titel: str = "") -> bool:
    import nachschauen
    h = host(adresse)
    return any(v in h for v in VERGLEICHS_HOSTS) or bool(nachschauen._PREISVERGLEICH_WORT.search(titel or ""))


_VERGLEICH_PRODUKT = re.compile(r"^https?://(?:www\.)?geizhals\.(?:at|de|eu)/[^?#]*-a\d+\.html", re.I)


def ist_vergleich_produktseite(adresse: str) -> bool:
    return bool(_VERGLEICH_PRODUKT.match(adresse or ""))


def _name_sauber(name: str) -> str:
    return " ".join(re.sub(r"[|\[\]()<>`*_\\#!]", " ", str(name or "")).split())[:60]


def von_geizhals(adresse: str) -> bool:
    return bool(re.match(r"^https?://(?:www\.)?geizhals\.(?:at|de|eu)/", adresse or "", re.I))


def im_markt(adresse: str, markt: str) -> str:
    m = re.match(r"^(https?://(?:www\.)?geizhals\.)(at|de|eu)(/.*)$", adresse or "", re.I)
    if m and (markt or "").upper() in ("AT", "DE"):
        return m.group(1) + markt.lower() + m.group(3)
    return adresse


def produktseiten(seiten: list, v: Variante, markt: str = "", hoechstens: int = 3) -> list[dict]:
    import wissen
    out: list[dict] = []
    for s in seiten:
        if wissen.PRODUKTSEITEN_KOPF not in s.text or not von_geizhals(s.adresse):
            continue
        block = s.text[s.text.index(wissen.PRODUKTSEITEN_KOPF):].split("\n\n")[0]
        passend = []
        for z in block.splitlines()[1:]:
            m = re.match(r"^- (.+?)(?: \((\d+) Angebote\))?: (https?://\S+)$", z.strip())
            if m and ist_vergleich_produktseite(m.group(3)) and v.passt(m.group(1), m.group(1)):
                passend.append((-int(m.group(2) or 0), m.group(1), im_markt(m.group(3), markt)))
        for _n, titel, adresse in sorted(passend, key=lambda x: x[0])[:hoechstens]:
            if markt_passt(adresse, markt) and all(adresse != t["adresse"] for t in out):
                out.append({"titel": titel, "adresse": adresse, "text": ""})
    return out


def kein_haendler(adresse: str) -> bool:
    h = host(adresse)
    return any(k in h for k in KEIN_HAENDLER)


def _wort_in(wort: str, text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(wort)}(?![a-z0-9])", text.lower()))


@dataclass(frozen=True)
class Variante:
    pflicht: tuple[str, ...]
    eins: tuple[str, ...]
    worte: tuple[str, ...] = ()

    def passt(self, text: str, titel: str = "") -> bool:
        n = _norm(text)
        if not (all(p in n for p in self.pflicht) and (not self.eins or any(e in n for e in self.eins))):
            return False
        if not all(_wort_in(w, text) for w in self.worte):
            return False
        t = titel or ""
        if any(_wort_in(w, t) for w in VARIANTENWORTE if w not in self.worte):
            return False
        if any(p in ANSCHLUSS and any(a in _norm(t) for a in ANSCHLUSS[p]) for p in self.pflicht):
            return False
        return not (self.eins and any(re.search(rf"(?i){re.escape(e)}\s*\+", _norm_plus(t)) for e in self.eins) and "plus" not in self.worte)

    def leer(self) -> bool:
        return not self.pflicht and not self.eins


def _norm_plus(t: str) -> str:
    return re.sub(r"[^a-z0-9/+]", "", str(t).lower())


def variante(sache: str) -> Variante:
    t = str(sache or "")
    worte = tuple(w for w in VARIANTENWORTE if _wort_in(w, t))
    pflicht = [f"{a}/{b}" for a, b, _c in _GROESSE.findall(t)] + [f"r{c}" for _a, _b, c in _GROESSE.findall(t)]
    pflicht += [f"{z}{e.lower()}" for z, e in _SPEICHER.findall(t)]
    pflicht += [a for a in ANSCHLUSS if a in _norm(t)]
    ohne_groesse = _GROESSE.sub(" ", _SPEICHER.sub(" ", t))
    eins = []
    for c in _CODE.findall(ohne_groesse):
        if _INDEX.match(c) or _JAHR.match(c) or c.upper() in {"DOT", "XL", "SUV"} or len(_norm(c)) < 2:
            continue
        eins.append(_norm(c))
    for name, zahl in _NAME_ZAHL.findall(ohne_groesse):
        if _KEINE_SACHE.match(name) or _JAHR.match(zahl):
            continue
        eins.append(_norm(name + zahl))
    return Variante(tuple(dict.fromkeys(pflicht)), tuple(dict.fromkeys(e for e in eins if e)), worte)


def sache(frage: str) -> str:
    t = re.sub(r"(?i)\bDOT\s*\d{2,4}\b|\b3PMSF\b|\bM\s*\+\s*S\b", " ", str(frage or ""))
    worte = [w.strip(",.;:!?„“\"'()") for w in t.split()]
    return " ".join(w for w in worte if w and not _KEINE_SACHE.match(w) and not _JAHR.match(w))


_KAUFWUNSCH = re.compile(r"(?i)\b(?:günstig\w*|guenstig\w*|billig\w*|preiswert\w*|preis\w*|kost\w*|kauf\w*|bestell\w*|angebot\w*|anbieter\w*|händler\w*|"
                         r"haendler\w*|shops?|cheap\w*|price\w*|buy\w*|deals?|offers?|sale)\b")


def ist_einkauf(frage: str) -> bool:
    import belege
    f = str(frage or "")
    if not (belege.vergleichsfrage(f) or _KAUFWUNSCH.search(f)):
        return False
    return not variante(sache(f)).leer()


def anfragen(frage: str, sachen: list[str] | None = None) -> list[str]:
    if sachen and len(sachen) >= 2:
        return [" ".join(s.split()[:10]) for s in sachen][:4]
    s = sache(frage)
    return [" ".join(s.split()[:10])] if s else []


_ZUBEHOER = re.compile(r"(?i)\b(?:\w*hülle\w*|schutzfolie\w*|panzerglas\w*|displayschutz\w*|ladekabel\w*|netzteil\w*|halterung\w*|tasche\w*|ventil\w*|"
                       r"montage\w*|wuchten|einlagerung\w*|reifendruck\w*|rdks|ersatzteil\w*|ersatzbürste\w*|staubbeutel\w*|screen\s+protector|"
                       r"phone\s+case|sleeve)\b")


def _naechster_preis(text: str, v: Variante, titel: str = "") -> float | None:
    import nachschauen
    text = re.sub(r"(?m)^(?:Gefunden über .*|Fragekennung: .*)$", "", text)
    if not v.passt(text, titel):
        return None
    name = v.eins or v.pflicht[:1]
    if not name:
        return None
    beste: tuple[int, float] | None = None
    for m in nachschauen._GELDBETRAG.finditer(text):
        vorher = _norm(text[max(0, m.start() - 400):m.start()])
        stelle = max(vorher.rfind(e) for e in name)
        if stelle >= 0:
            dazwischen = vorher[stelle:]
            if v.pflicht and dazwischen.count(v.pflicht[0]) >= 2:
                continue
            abstand = len(dazwischen)
        elif any(e in _norm(text[m.end():m.end() + 120]) for e in name):
            abstand = 400
        else:
            continue
        danach, davor = text[m.end():m.end() + 14].lower(), text[max(0, m.start() - 14):m.start()].lower()
        if re.search(r"^\s*(?:/\s*mo|mtl|monatl|pro\s+monat|im\s+monat|per\s+month|a\s+month|/\s*month|x\b)", danach) or \
                re.search(r"(?:versand\w*|shipping|pfand|zzgl\.?|mtl\.?|monatlich|rate|raten)\s*:?\s*(?:ab\s+|von\s+|nur\s+)?$", davor):
            continue
        if re.search(r"(?<![a-z])(?:uvp|statt|unverbindl\w*|ehemals|bisher|streichpreis|rrp|list\s+price)(?![a-z])", davor):
            continue
        gebraucht = r"(?i)refurbished|generalüberholt|gebraucht|b-ware|wie neu|renewed|\bused\b|vorführ"
        if re.search(gebraucht, text[max(0, m.start() - 120):m.start()]) or re.search(gebraucht, text[m.end():m.end() + 90]):
            continue
        if _ZUBEHOER.search(text[max(0, m.start() - 80):m.start()]):
            continue
        if re.search(r"(?i)(?:bestellung\w*|bestellwert\w*|mindestbestell\w*|einkaufswert\w*|warenwert\w*|orders?)\s+(?:ab|von|über|over|from)\s*(?:einem\s+)?$",
                     text[max(0, m.start() - 45):m.start()]):
            continue
        ganz, cent = (m.group(1), m.group(2)) if m.group(1) is not None else (m.group(3), m.group(4))
        wert = float(re.sub(r"[.  ]", "", ganz) + "." + cent)
        if wert <= 0:
            continue
        if beste is None or abstand < beste[0]:
            beste = (abstand, wert)
    return beste[1] if beste else None


UEBER_DIE_GRENZE = {"AT": ("amazon.de",)}


def markt_passt(adresse: str, markt: str) -> bool:
    import belege
    if not markt:
        return True
    land = belege.land_der_adresse(adresse).upper()
    return not land or land == markt.upper() or host(adresse) in UEBER_DIE_GRENZE.get(markt.upper(), ())


def angebote(treffer: list[dict], seiten: list, v: Variante, markt: str = "") -> list[Angebot]:
    import wissen
    if v.leer():
        return []
    gefunden: list[Angebot] = []
    for s in seiten:
        if wissen.HAENDLER_LISTE_KOPF in s.text and von_geizhals(s.adresse):
            if not markt_passt(s.adresse, markt) or (markt and host(s.adresse).endswith(".eu")):
                continue
            block = s.text[s.text.index(wissen.HAENDLER_LISTE_KOPF):].split("\n\n")[0]
            for z in block.splitlines()[1:]:
                m = re.match(r"^- (.{1,60}): (\d+,\d{2}) EUR \| (.+)$", z.strip())
                wer = _name_sauber(m.group(1)) if m else ""
                if wer and v.passt(m.group(3), m.group(3)) and not kein_haendler(wer) and not ist_vergleichsseite(wer):
                    gefunden.append(Angebot(wer, float(m.group(2).replace(",", ".")), s.adresse, "vergleich:" + host(s.adresse)))
            continue
        if ist_vergleichsseite(s.adresse, s.titel) or kein_haendler(s.adresse) or s.titel.startswith("Suchergebnisse") or not markt_passt(s.adresse, markt):
            continue
        text = s.text
        if wissen.ANGEBOTE_KOPF not in text and (re.search(r"(?i)/(?:list|brand|category|kategorie|c|s|search|suche)/|[?&](?:q|k|query|search)=", s.adresse)
                                                 or re.search(r"(?i)\bonline kaufen\b|\bgünstig kaufen\b", s.titel)):
            continue
        preis = None
        if wissen.ANGEBOTE_KOPF in text:
            block = text[text.index(wissen.ANGEBOTE_KOPF):].split("\n\n")[0]
            if wissen.MEHRERE_HAENDLER not in block:
                preis = _naechster_preis(s.titel + "\n" + block, v, s.titel)
        if preis is None:
            preis = _naechster_preis(s.titel + "\n" + text[:6000], v, s.titel)
        if preis:
            gefunden.append(Angebot(host(s.adresse), preis, s.adresse, "seite"))
    for t in treffer:
        a = str(t.get("adresse", ""))
        if not a or ist_vergleichsseite(a, str(t.get("titel", ""))) or kein_haendler(a) or not markt_passt(a, markt):
            continue
        preis = _naechster_preis(f"{t.get('titel', '')} {t.get('text', '')}", v, str(t.get("titel", "")))
        if preis:
            gefunden.append(Angebot(host(a), preis, a, "treffer"))
    return zusammenfassen(gefunden, anker(treffer, v))


_RANG = {"seite": 0, "vergleich": 1, "treffer": 2}


def _schluessel(haendler: str) -> str:
    return re.sub(r"[^a-z0-9]", "", haendler.lower())


def _ohne_endung(haendler: str) -> str:
    return _schluessel(re.sub(r"\.(?:at|de|com|eu|ch|net)$", "", haendler.lower().strip()))


def anker(treffer: list[dict], v: Variante) -> float | None:
    import nachschauen
    werte = []
    for t in treffer:
        a, titel = str(t.get("adresse", "")), str(t.get("titel", ""))
        if not ist_vergleichsseite(a, titel) or not v.passt(titel, titel):
            continue
        m = re.search(r"(?i)\bab\s+(?:€\s*)?(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+)\s*(?:€|EUR)?", titel)
        if m and nachschauen.geldbetraege(m.group(0) + (" €" if "€" not in m.group(0) else "")):
            werte.append(float(re.sub(r"[.\s]", "", m.group(1)).replace(",", ".")))
    return min(werte) if werte else None


def zusammenfassen(gefunden: list[Angebot], anker: float | None = None) -> list[Angebot]:
    beste: dict[str, Angebot] = {}
    for g in gefunden:
        if g.preis < 1:
            continue
        k = _schluessel(g.haendler)
        b = beste.get(k)
        rang_g, rang_b = _RANG[g.herkunft.split(":")[0]], _RANG[b.herkunft.split(":")[0]] if b else 9
        if b is None or rang_g < rang_b or (rang_g == rang_b and g.preis < b.preis):
            beste[k] = g
    eigene = {_ohne_endung(g.haendler) for g in beste.values() if g.herkunft != "treffer" and "." in g.haendler}
    beste = {k: g for k, g in beste.items() if "." in g.haendler or not g.herkunft.startswith("vergleich") or _schluessel(g.haendler) not in eigene}
    if anker:
        beste = {k: g for k, g in beste.items() if g.preis >= anker * 0.6}
    werte = sorted(g.preis for g in beste.values())
    if len(werte) >= 3:
        mitte = werte[len(werte) // 2]
        beste = {k: g for k, g in beste.items() if g.preis >= mitte / 2}
    elif len(werte) == 2 and werte[0] < werte[1] / 3:
        beste = {k: g for k, g in beste.items() if g.preis >= werte[1] / 3}
    return sorted(beste.values(), key=lambda g: g.preis)


def vergleichsseiten(treffer: list[dict], seiten: list) -> list[tuple[str, str]]:
    out: dict[str, str] = {}
    for t in list(treffer) + [{"adresse": s.adresse, "titel": s.titel} for s in seiten]:
        a = str(t.get("adresse", ""))
        if a and re.match(r"^https?://[^\s|<>()\[\]`]+$", a) and ist_vergleichsseite(a, str(t.get("titel", ""))) and host(a) not in out:
            out[host(a)] = a
    return list(out.items())[:3]


def _euro(x: float, englisch: bool) -> str:
    s = f"{x:,.2f}"
    return f"€{s}" if englisch else s.replace(",", " ").replace(".", ",").replace(" ", ".") + " €"


TABELLE_MAX = 8


def tabelle(gefunden: list[Angebot], portale: list[tuple[str, str]], *, englisch: bool = False, stand: str = "") -> str:
    if not gefunden:
        if englisch:
            satz = "I couldn't find a shop page that shows a price for exactly this model."
            return satz + (f" You can compare prices at {', '.join(a for _h, a in portale)}." if portale else "")
        satz = "Bei den Händlern, die ich lesen konnte, stand kein Preis für genau dieses Modell."
        return satz + (f" Preise vergleichen kannst du hier: {', '.join(a for _h, a in portale)}." if portale else "")
    kopf = "| Shop | Price | Checked |" if englisch else "| Händler | Preis | Geprüft |"
    zeilen = [kopf, "|---|---|---|"]
    for g in gefunden[:TABELLE_MAX]:
        quelle = g.herkunft.split(":", 1)[1] if g.herkunft.startswith("vergleich:") else ""
        if englisch:
            wo = "on the shop's page" if g.herkunft == "seite" else f"listed on {quelle}" if quelle else "in the search result"
        else:
            wo = "auf der Seite des Händlers" if g.herkunft == "seite" else f"laut {quelle}" if quelle else "im Suchtreffer"
        zeilen.append(f"| {g.haendler} | {_euro(g.preis, englisch)} | {wo} |")
    g0 = gefunden[0]
    satz = (f"The cheapest is {g0.haendler} at {_euro(g0.preis, englisch)}." if englisch else
            f"Am günstigsten ist {g0.haendler} mit {_euro(g0.preis, englisch)}.")
    hinweis = ("Prices as found, without shipping; check the final price at the shop." if englisch else
               "Preise wie gefunden, ohne Versand; den Endpreis zeigt der Händler.")
    if stand:
        hinweis = hinweis[:-1] + (f", as of {stand}." if englisch else f", Stand {stand}.")
    teile = ["\n".join(zeilen), satz + " " + hinweis]
    if portale:
        namen = ", ".join(h for h, _a in portale)
        teile.append(f"More shops are listed by the price comparison {namen}." if englisch else f"Weitere Händler listet der Preisvergleich {namen}.")
    return "\n\n".join(teile)


_TABELLENZEILE = re.compile(r"^\s*\|.*\|\s*$|^[^|\n]*\|[^|\n]*\|[^\n]*$")


def einsetzen(antwort: str, gefunden: list[Angebot], portale: list[tuple[str, str]], *, englisch: bool = False, stand: str = "") -> str:
    import nachschauen
    behalten = []
    for z in str(antwort or "").split("\n"):
        if "|" in z and _TABELLENZEILE.match(z):
            continue
        if nachschauen.geldbetraege(z) or re.search(r"\d\s*(?:€|EUR|Euro)\b", z):
            continue
        behalten.append(z)
    vorne = re.sub(r"\n{3,}", "\n\n", "\n".join(behalten)).strip()
    return "\n\n".join(t for t in (vorne, tabelle(gefunden, portale, englisch=englisch, stand=stand)) if t)
