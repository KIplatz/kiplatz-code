# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

_GROESSE = re.compile(r"(?<!\d)(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2})(?!\d)", re.I)
_SPEICHER = re.compile(r"(?<![\w.])(\d{1,4})\s*(GB|TB)\b", re.I)
_CODE = re.compile(r"(?<![\w.-])((?:[A-Za-z]{1,8}-?\d[\w-]*)|(?:\d{2,}\.\d{2,}))(?![\w])")
_NAME_ZAHL = re.compile(r"\b([A-Za-zÄÖÜäöüß][A-Za-zäöüß]{2,}|[A-Z]{2,})\s+(\d{1,4})(?![\d.,/]|\s*(?:GB|TB|Zoll|cm|mm|Stück|stk|x|%|€|Euro|Jahre|Uhr))\b")
VARIANTENWORTE = ("pro", "plus", "max", "ultra", "slim", "mini", "lite", "digital", "fe", "se", "air", "neo")
ANSCHLUSS = {"usbc": ("lightning",), "lightning": ("usbc",)}
_INDEX = re.compile(r"^\d{2,3}[A-Za-z]{1,2}$")
_JAHR = re.compile(r"^(?:19|20)\d\d$")
EINKAUF_WOERTER: dict[str, tuple[str, ...]] = {
    "de": ("günstig", "guenstig", "billig", "preiswert", "preis", "kost", "kauf", "bestell", "angebot", "anbieter", "händler", "haendler", "shop",
           "vergleich", "tiefpreis", "sonderangebot", "rabatt"),
    "en": ("cheap", "price", "pricing", "buy", "deal", "offer", "sale", "shop", "store", "compare", "cost", "bargain", "discount", "retailer"),
    "it": ("prezz", "economic", "cost", "compra", "acquist", "offert", "negozi", "sconto", "scontat", "conven", "risparmi"),
    "fr": ("prix", "cher", "achet", "achat", "offre", "promo", "magasin", "boutique", "compar", "coût", "cout", "moins", "remise", "soldes"),
    "es": ("precio", "barat", "compra", "oferta", "tienda", "cuesta", "coste", "económic", "economic", "descuento", "rebaja"),
    "pt": ("preço", "preco", "barat", "compra", "oferta", "loja", "custa", "desconto", "promoç", "promoc"),
    "nl": ("prijs", "goedkoop", "goedkop", "kopen", "koop", "aanbieding", "winkel", "kost", "korting", "voordelig"),
    "pl": ("cena", "cen", "tani", "tanio", "kupi", "kupić", "sklep", "ofert", "promocj"),
    "cs": ("cena", "cen", "levn", "koupit", "kup", "obchod", "nabíd", "sleva"),
    "sk": ("cena", "cen", "lacn", "kúpiť", "kupit", "obchod", "ponuk", "zľava"),
    "hu": ("ár", "olcs", "vásárl", "vesz", "bolt", "ajánlat", "akció"),
    "sl": ("cena", "cen", "poceni", "kupi", "trgovin", "ponudb", "popust"),
    "hr": ("cijen", "jeftin", "kupi", "trgovin", "ponud", "popust"),
    "da": ("pris", "billig", "køb", "kob", "butik", "tilbud", "rabat"),
    "sv": ("pris", "billig", "köp", "kop", "butik", "erbjudande", "rea", "rabatt"),
    "nb": ("pris", "billig", "kjøp", "kjop", "butikk", "tilbud", "rabatt"),
    "fi": ("hinta", "halpa", "halvin", "osta", "kauppa", "tarjous", "alennus"),
    "el": ("τιμή", "τιμη", "φθην", "αγορ", "κατάστημ", "προσφορ"),
    "ro": ("preț", "pret", "ieftin", "cumpăr", "cumpar", "magazin", "ofert", "reducer"),
    "bg": ("цена", "евтин", "купи", "магазин", "оферт", "намален"),
    "ja": ("価格", "値段", "最安", "安い", "購入", "買", "通販", "セール"),
}
FUELLWOERTER: dict[str, tuple[str, ...]] = {
    "de": ("wo", "wie", "was", "wer", "er", "sie", "ihn", "diese*", "welche*", "ist", "sind", "am", "im", "in", "aus", "bei", "für", "fuer", "von", "vom",
           "zum", "zur", "der", "die", "das", "den", "dem", "des", "ein*", "mir", "mich", "ich", "du", "uns", "es", "zeig*", "such*", "find*", "gib", "gibt",
           "bekomm*", "krieg*", "bester", "beste", "besten", "testbewert*", "testbericht*", "test", "tests", "bewert*", "woanders", "sonst", "online", "internet",
           "bitte", "jetzt", "aktuell*", "heute", "und", "oder", "dazu", "davon", "lohnt", "sich", "möchte", "moechte", "will", "brauche", "suche",
           "neu*", "stück", "stueck", "reifen", "nach", "mit"),
    "en": ("where", "which", "what", "how", "best", "is", "are", "the", "a", "an", "for", "in", "to", "me", "find", "get", "online", "can", "i",
           "lowest", "cheapest", "good", "new", "of", "from", "with", "tyres", "tires", "tyre", "tire", "reviews", "review"),
    "it": ("dove", "come", "quale", "qual", "più", "piu", "meno", "il", "la", "lo", "gli", "le", "di", "del", "della", "dei", "in", "a", "per", "con",
           "un", "una", "basso", "bassa", "trovo", "posso", "miglior", "migliore", "è", "pneumatic*", "gomme"),
    "fr": ("où", "ou", "le", "la", "les", "de", "du", "des", "en", "au", "aux", "un", "une", "pour", "plus", "quel", "quelle", "trouver", "est",
           "meilleur", "pas", "pneu", "pneus"),
    "es": ("dónde", "donde", "el", "la", "los", "las", "de", "del", "en", "un", "una", "para", "más", "mas", "menos", "cuál", "cual", "es", "mejor",
           "neumátic*", "neumatic*"),
    "pt": ("onde", "o", "a", "os", "as", "de", "do", "da", "em", "no", "na", "um", "uma", "mais", "menos", "melhor", "pneu"),
    "nl": ("waar", "de", "het", "een", "in", "voor", "van", "beste", "welke", "is"),
}
_GANZ = frozenset({"cher", "cost", "ár", "tani", "rea", "kup", "kop", "kob", "cen", "osta", "vesz", "koop", "kost"})
_STAEMME = tuple(dict.fromkeys(w for ws in EINKAUF_WOERTER.values() for w in ws))
_KEINE_SACHE = re.compile(
    r"(?i)^(?:" + "|".join(re.escape(w) for w in _STAEMME if w not in _GANZ) + r")\w*$"
    r"|^(?:" + "|".join(re.escape(w) for w in _STAEMME if w in _GANZ) + r"|chère|chers|costs?|kostet|kosten|tanio|tanie|taniej|kostar|koster)$"
    r"|^(?:" + "|".join(re.escape(w) for ws in FUELLWOERTER.values() for w in ws if not w.endswith("*")) + r")$"
    r"|^(?:" + "|".join(re.escape(w[:-1]) for ws in FUELLWOERTER.values() for w in ws if w.endswith("*")) + r")\w*$")
_KAUFWUNSCH = re.compile(
    r"(?i)(?<!\w)(?:" + "|".join(re.escape(w) for w in _STAEMME if w not in _GANZ and w.isascii()) + r")\w*"
    r"|(?<!\w)(?:" + "|".join(re.escape(w) for w in _STAEMME if w in _GANZ) + r"|chère|chers|costs?|kostet|kosten|tanio|tanie|taniej)(?!\w)"
    r"|(?:" + "|".join(re.escape(w) for w in _STAEMME if not w.isascii() and w not in _GANZ) + r")")


@dataclass(frozen=True)
class Angebot:
    haendler: str
    preis: float
    adresse: str
    herkunft: str
    waehrung: str = "EUR"
    produkt: str = ""


_ZAHL = r"\d{1,3}(?:[.,   '’]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_BETRAG_MUSTER: re.Pattern | None = None


def _betrag_muster() -> re.Pattern:
    global _BETRAG_MUSTER
    if _BETRAG_MUSTER is None:
        import laender
        zeichen = sorted(set(laender.ZEICHEN) | {"€"}, key=len, reverse=True)
        codes = sorted(set(laender.WAEHRUNG.values()))
        z = "|".join([re.escape(x) for x in zeichen] + [rf"\b{c}\b" for c in codes] + [r"\b[Ee]uros?\b"])
        _BETRAG_MUSTER = re.compile(rf"(?<![\w.,])(?:(?P<vz>{z})\s?(?P<v>{_ZAHL})(?:[.,][-–])?|(?P<n>{_ZAHL})(?:[.,][-–])?\s?(?P<nz>{z}))")
    return _BETRAG_MUSTER


def _zahl(s: str) -> float | None:
    s = re.sub(r"[   '’]", "", s)
    if "." in s and "," in s:
        dezimal = "." if s.rfind(".") > s.rfind(",") else ","
        s = s.replace("," if dezimal == "." else ".", "").replace(dezimal, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        teile = s.split(sep)
        if len(teile) > 2 or (len(teile) == 2 and len(teile[1]) == 3):
            s = "".join(teile)
        else:
            s = s.replace(sep, ".")
    try:
        return float(s)
    except ValueError:
        return None


def waehrung_des_markts(markt: str) -> str:
    import laender
    return laender.WAEHRUNG.get(str(markt or "").upper(), "")


def _iso(zeichen: str, markt: str) -> str:
    import laender
    z = zeichen.strip()
    if re.fullmatch(r"[A-Z]{3}", z):
        return z
    if z.lower().startswith("euro") or z == "€":
        return "EUR"
    moeglich = laender.ZEICHEN.get(z, ())
    soll = waehrung_des_markts(markt)
    if soll in moeglich:
        return soll
    return "USD" if z == "$" else (moeglich[0] if len(moeglich) == 1 else "")


def betraege(text: str, markt: str = "") -> list[tuple[int, int, float, str]]:
    out = []
    for m in _betrag_muster().finditer(text or ""):
        zahl, zeichen = (m.group("v"), m.group("vz")) if m.group("v") else (m.group("n"), m.group("nz"))
        wert = _zahl(zahl)
        if wert is not None:
            out.append((m.start(), m.end(), wert, _iso(zeichen, markt)))
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9/]", "", str(t).lower().replace("ß", "ss"))


def _kurz(t: str) -> str:
    return re.sub(r"\b([A-Z])[a-z]+([A-Z])[a-z]+(?=\W|\d|$)", r"\1\2", str(t))


def _norm_name(t: str) -> str:
    return _norm(_kurz(t))


def host(adresse: str) -> str:
    return re.sub(r"^www\d?\.", "", re.sub(r"^https?://", "", str(adresse)).split("/")[0].lower())


VERGLEICH_WORTE = ("preisvergleich", "preise vergleichen", "vergleiche preise", "price comparison", "compare prices", "confronta prezzi",
                   "comparatore", "comparer les prix", "comparateur", "compara precios", "comparador", "comparar preços", "prijsvergelijk",
                   "vergelijk prijzen", "porównaj ceny", "porównywarka", "porovnání cen", "porovnanie cien", "árösszehasonlító", "jämför priser",
                   "sammenlign priser", "hintavertailu", "価格比較")
ANGEBOTE_WORTE = ("angebote", "offers", "offerte", "offres", "ofertas", "aanbiedingen", "ofert", "nabídek", "ponúk", "ajánlat", "erbjudanden", "tilbud",
                  "tarjousta", "件", "shops", "stores", "händler", "negozi", "boutiques", "tiendas", "winkels", "sklepów")
AB_WORTE = ("ab", "from", "a", "da", "à partir de", "dès", "desde", "a partir de", "vanaf", "od", "fra", "från", "alkaen", "tól")
_VERGLEICH_TITEL = re.compile(r"(?i)(?:" + "|".join(re.escape(w) for w in VERGLEICH_WORTE) + r")|(?<![\w])\d{1,5}\s+(?:"
                              + "|".join(re.escape(w) for w in ANGEBOTE_WORTE) + r")(?!\w)")
_AB = re.compile(r"(?i)(?<![\w])(?:" + "|".join(re.escape(w) for w in AB_WORTE) + r")\s+$")
KEIN_HAENDLER = ("youtube.", "wikipedia.", "reddit.", "facebook.", "instagram.", "tiktok.", "x.com", "twitter.", "pinterest.", "linkedin.", "quora.")


def ist_vergleichsseite(adresse: str, titel: str = "", text: str = "") -> bool:
    import nachschauen
    import wissen
    t = titel or ""
    if _VERGLEICH_TITEL.search(f"{t} {str(text or '')[:300]}") or any(_AB.search(t[max(0, a - 14):a]) for a, _e, _w, _i in betraege(t)):
        return True
    return bool(text) and (nachschauen.preisvergleich(text) or ("\n" + wissen.HAENDLER_LISTE_KOPF) in "\n" + text
                           or bool(re.search(re.escape(wissen.ANGEBOTE_KOPF) + r"[^\n]*:\n- " + re.escape(wissen.MEHRERE_HAENDLER), text)))


def _name_sauber(name: str) -> str:
    return " ".join(re.sub(r"[|\[\]()<>`*_\\#!]", " ", str(name or "")).split())[:60]


def im_markt(adresse: str, markt: str) -> str:
    import belege
    m = re.match(r"^(https?://[^/]+\.)([a-z]{2})(/.*)?$", adresse or "", re.I)
    if not m or not markt or len(markt) != 2 or not belege.land_der_adresse(adresse):
        return adresse
    endung = "uk" if markt.upper() == "GB" else markt.lower()
    return m.group(1) + endung + (m.group(3) or "")


def produktseiten(seiten: list, v: Variante, markt: str = "", hoechstens: int = 3) -> list[dict]:
    import wissen
    out: list[dict] = []
    for s in seiten:
        if not (s.text.lstrip().startswith(wissen.PRODUKTSEITEN_KOPF) or ("\n" + wissen.PRODUKTSEITEN_KOPF) in s.text):
            continue
        block = s.text[s.text.index(wissen.PRODUKTSEITEN_KOPF):].split("\n\n")[0]
        passend = []
        for z in block.splitlines()[1:]:
            m = re.match(r"^- (.+?)(?: \((\d+) Angebote\))?: (https?://\S+)$", z.strip())
            if m and host(m.group(3)) == host(s.adresse) and v.passt(m.group(1), m.group(1)):
                passend.append((-int(m.group(2) or 0), m.group(1), im_markt(m.group(3), markt)))
        for _n, titel, adresse in sorted(passend, key=lambda x: x[0])[:hoechstens]:
            if markt_passt(adresse, markt) and all(adresse != t["adresse"] for t in out):
                out.append({"titel": titel, "adresse": adresse, "text": ""})
    return out


KEIN_LADEN_WORTE = ("price history", "price tracker", "price as of", "price drop alert", "preisalarm","preisverlauf", "preisentwicklung", "preishistorie", "storico prezzi", "historique des prix",
                    "historial de precios", "prijsgeschiedenis", "historia cen", "kleinanzeigen", "anzeigen", "classifieds", "annunci", "annonces",
                    "anuncios", "advertenties", "ogłoszenia", "inzeráty", "hirdetés", "annonser", "価格推移")
_KEIN_LADEN = re.compile(r"(?i)" + "|".join(re.escape(w) for w in KEIN_LADEN_WORTE))


def kein_haendler(adresse: str, titel: str = "") -> bool:
    h = host(adresse)
    return any(k in h for k in KEIN_HAENDLER) or bool(_KEIN_LADEN.search(titel or ""))


def _wort_in(wort: str, text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(wort)}(?![a-z0-9])", text.lower()))


@dataclass(frozen=True)
class Variante:
    pflicht: tuple[str, ...]
    eins: tuple[str, ...]
    worte: tuple[str, ...] = ()

    def passt(self, text: str, titel: str = "") -> bool:
        n = _norm(text) + " " + _norm_name(text)
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
        eins.append(_norm_name(name + " " + zahl))
    return Variante(tuple(dict.fromkeys(pflicht)), tuple(dict.fromkeys(e for e in eins if e)), worte)


def sache(frage: str) -> str:
    t = re.sub(r"(?i)\bDOT\b(?:\s*\d{2,4}\b)?|\b3PMSF\b|\bM\s*\+\s*S\b", " ", str(frage or ""))
    import laender
    import nachschauen
    t = laender._MUSTER.sub(lambda m: " " if laender.NAMEN.get(m.group(1)) in nachschauen.MAERKTE else m.group(0), t)
    worte = [w.strip(",.;:!?„“\"'()？。、") for w in t.split()]
    return " ".join(w for w in worte if w and not _KEINE_SACHE.match(w) and not _JAHR.match(w))


def ist_einkauf(frage: str) -> bool:
    import belege
    f = str(frage or "")
    if not (belege.vergleichsfrage(f) or _KAUFWUNSCH.search(f)):
        return False
    v = variante(sache(f))
    return bool(v.pflicht) if ist_alternative(f) else not v.leer()


ALTERNATIV_WORTE = ("alternativ", "ähnlich", "vergleichbar", "anstelle", "stattdessen", "similar", "instead of", "comparable", "simil", "invece di",
                    "similaire", "au lieu", "équivalent", "parecid", "en lugar de", "en vez de", "semelhante", "vergelijkbaar", "in plaats van",
                    "podobn", "zamiast", "hasonló", "liknande", "lignende", "代わり", "代替", "似た")
_ALTERNATIV = re.compile(r"(?i)" + "|".join(re.escape(w) for w in ALTERNATIV_WORTE)
                         + r"|(?:günstiger|billiger|preiswerter)\w*\s+(?:\S+\s+){0,2}als\b|cheaper\s+(?:\S+\s+){0,2}than\b"
                         + r"|più\s+economic\w*\s+(?:\S+\s+){0,2}(?:di|del|della)\b|moins\s+ch[eè]re?s?\s+(?:\S+\s+){0,2}que\b"
                         + r"|más\s+barat\w*\s+(?:\S+\s+){0,2}que\b|goedkoper\w*\s+(?:\S+\s+){0,2}dan\b")


def ist_alternative(frage: str) -> bool:
    return bool(_ALTERNATIV.search(str(frage or "")))


def suchvariante(frage: str) -> tuple[Variante, tuple[str, ...]]:
    v = variante(sache(frage))
    if ist_alternative(frage):
        return Variante(v.pflicht, (), ()), v.eins
    return v, ()


def anfragen(frage: str, sachen: list[str] | None = None) -> list[str]:
    if ist_alternative(frage):
        groessen = [" ".join(m.group(0).split()) for m in _GROESSE.finditer(" ".join(sachen or []) + " " + frage)]
        if groessen:
            return [groessen[0]]
    if sachen and len(sachen) >= 2:
        return [" ".join(s.split()[:10]) for s in sachen][:4]
    s = sache(frage)
    return [" ".join(s.split()[:10])] if s else []


NICHT_DER_PREIS: dict[str, tuple[str, ...]] = {
    "streich": ("uvp", "statt", "unverbindl", "ehemals", "bisher", "streichpreis", "rrp", "list price", "msrp", "regular price", "compare at",
                "prezzo consigliato", "invece di", "prezzo di listino", "prix conseillé", "au lieu de", "prix barré", "prix de référence",
                "precio recomendado", "antes", "pvpr", "precio anterior", "preço recomendado", "adviesprijs", "cena katalogowa", "doporučená cena",
                "ajánlott ár", "希望小売価格", "参考価格", "通常価格"),
    "rate": ("mtl", "monatl", "pro monat", "im monat", "rate", "raten", "finanzierung", "/mo", "per month", "a month", "/month", "monthly",
             "installment", "al mese", "/mese", "rata", "/mois", "par mois", "mensualit", "/mes", "al mes", "cuota", "plazos", "per maand", "p/m",
             "miesięcznie", "měsíčně", "havonta", "月々", "月額"),
    "versand": ("versand", "shipping", "delivery", "pfand", "zzgl", "spedizione", "livraison", "frais de port", "envío", "envio", "verzend", "porto",
                "dostawa", "doprava", "szállítás", "送料"),
    "grenze": ("bestellung", "bestellwert", "mindestbestell", "einkaufswert", "warenwert", "orders over", "orders from", "order over", "spend over",
               "ordini superiori", "ordini da", "commandes de plus", "dès", "pedidos superiores", "pedidos de más", "bestellingen vanaf",
               "zamówień od", "objednávky nad"),
    "ersparnis": ("save", "spare", "du sparst", "sparen sie", "ersparnis", "risparmi", "économis", "economis", "ahorra", "ahorro", "bespaar",
                  "oszczędź", "ušetř", "spar ", "节约", "お得"),
    "gebraucht": ("refurbished", "generalüberholt", "gebraucht", "b-ware", "wie neu", "renewed", "used", "pre-owned", "preowned", "vorführ",
                  "ricondizionat", "usato", "reconditionn", "occasion", "reacondicionad", "usado", "seminuevo", "gebruikt", "używany", "použit",
                  "használt", "中古", "再生品"),
    "zubehoer": ("hülle", "schutzfolie", "panzerglas", "displayschutz", "ladekabel", "netzteil", "halterung", "tasche", "ventil", "montage", "wuchten",
                 "einlagerung", "reifendruck", "rdks", "ersatzteil", "ersatzbürste", "staubbeutel", "screen protector", "phone case", "charger",
                 "mounting", "fitting", "custodia", "pellicola", "montaggio", "coque", "housse", "étui", "funda", "protector de pantalla", "montaje",
                 "hoesje", "montaż", "pouzdro", "tok", "ケース", "フィルム"),
}
LADEN_WORTE = ("in den warenkorb", "warenkorb", "lieferbar", "auf lager", "sofort verfügbar", "jetzt kaufen", "versandkostenfrei", "lieferzeit",
               "add to cart", "add to basket", "add to bag", "in stock", "out of stock", "buy now", "free delivery", "free shipping", "ships in",
               "aggiungi al carrello", "disponibil", "acquista ora", "spedizione gratuita", "ajouter au panier", "en stock", "acheter maintenant",
               "livraison gratuite", "añadir al carrito", "comprar ahora", "envío gratis", "disponible", "adicionar ao carrinho", "em stock",
               "comprar agora", "in winkelwagen", "op voorraad", "nu kopen", "gratis verzending", "do koszyka", "dostępn", "kup teraz", "do košíku",
               "skladem", "do košíka", "na sklade", "kosárba", "raktáron", "v košarico", "na zalogi", "u košaricu", "na stanju", "læg i kurv",
               "på lager", "lägg i varukorg", "i lager", "köp nu", "legg i handlekurv", "lisää ostoskoriin", "varastossa", "προσθήκη στο καλάθι",
               "διαθέσιμο", "adaugă în coș", "în stoc", "добави в количката", "в наличност", "カートに入れる", "在庫あり", "送料無料", "購入手続き")
_LADEN = re.compile(r"(?i)" + "|".join(re.escape(w) for w in LADEN_WORTE))


def verkauft(text: str) -> bool:
    import wissen
    t = str(text or "")
    return bool(_LADEN.search(t)) or bool(re.search(re.escape(wissen.ANGEBOTE_KOPF) + r"[^\n]*:\n- diese Seite:", t))


_MUSTER_NICHT = {k: re.compile(r"(?i)(?<![^\W\d_])(?:" + "|".join(re.escape(w) for w in ws) + ")") for k, ws in NICHT_DER_PREIS.items()}


def _steht(art: str, text: str) -> bool:
    return bool(_MUSTER_NICHT[art].search(text))


def _naechster_preis(text: str, v: Variante, titel: str = "", markt: str = "") -> tuple[float, str] | None:
    text = re.sub(r"(?m)^(?:Gefunden über .*|Fragekennung: .*)$", "", text)
    if not v.passt(text, titel):
        return None
    name = v.eins or v.pflicht[:1]
    if not name:
        return None
    beste: tuple[int, float, str] | None = None
    for anfang, ende, wert, iso in betraege(text, markt):
        vorher = _norm_name(text[max(0, anfang - 400):anfang])
        stelle = max(vorher.rfind(e) for e in name)
        if stelle >= 0:
            dazwischen = vorher[stelle:]
            if v.pflicht and dazwischen.count(v.pflicht[0]) >= 2:
                continue
            abstand = len(dazwischen)
        elif any(e in _norm_name(text[ende:ende + 120]) for e in name):
            abstand = 400
        else:
            continue
        davor, danach = text[max(0, anfang - 24):anfang], text[ende:ende + 24]
        streich = list(_MUSTER_NICHT["streich"].finditer(davor))
        if streich and all(abs(b[2] - wert) < 0.01 for b in betraege(davor[streich[-1].end():])):
            continue
        if _steht("versand", text[max(0, anfang - 16):anfang]) or _steht("grenze", text[max(0, anfang - 32):anfang]):
            continue
        if _steht("rate", text[max(0, anfang - 16):anfang]) or re.match(r"\s*(?:/|x\b)", danach) or _steht("rate", danach[:14]):
            continue
        if _steht("gebraucht", text[max(0, anfang - 120):anfang]) or _steht("gebraucht", text[ende:ende + 90]):
            continue
        if _steht("zubehoer", text[max(0, anfang - 80):anfang]) or _steht("ersparnis", text[max(0, anfang - 24):anfang]) or wert <= 0:
            continue
        if beste is None or abstand < beste[0]:
            beste = (abstand, wert, iso)
    return (beste[1], beste[2]) if beste else None


def markt_passt(adresse: str, markt: str) -> bool:
    import belege
    if not markt:
        return True
    land = belege.land_der_adresse(adresse).upper()
    return not land or land == markt.upper()


def angebote(treffer: list[dict], seiten: list, v: Variante, markt: str = "", ohne: tuple[str, ...] = (), alternativen: bool = False) -> list[Angebot]:
    def fremd(name: str) -> bool:
        return bool(ohne) and any(e in _norm_name(name) or e in _norm(name) for e in ohne)
    import wissen
    if v.leer():
        return []
    gefunden: list[Angebot] = []
    for s in seiten:
        if s.text.lstrip().startswith(wissen.HAENDLER_LISTE_KOPF) or ("\n" + wissen.HAENDLER_LISTE_KOPF) in s.text:
            if not markt_passt(s.adresse, markt):
                continue
            block = s.text[s.text.index(wissen.HAENDLER_LISTE_KOPF):].split("\n\n")[0]
            for z in block.splitlines()[1:]:
                m = re.match(r"^- (.{1,60}): (\d+(?:,\d{1,2})?) ([A-Z]{3})? ?\| (.+)$", z.strip())
                wer = _name_sauber(m.group(1)) if m else ""
                domain = re.search(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,3}\b", wer)
                if domain and not markt_passt("https://" + domain.group(0).lower(), markt):
                    continue
                if wer and v.passt(m.group(4), m.group(4)) and not kein_haendler(wer) and not ist_vergleichsseite(wer) and not fremd(m.group(4)):
                    gefunden.append(Angebot(wer, float(m.group(2).replace(",", ".")), s.adresse, "vergleich:" + host(s.adresse),
                                            m.group(3) or waehrung_des_markts(_land(s.adresse)),
                                            _produkt(m.group(4)) if alternativen else ""))
            continue
        if ist_vergleichsseite(s.adresse, s.titel, s.text) or kein_haendler(s.adresse, s.titel) or s.titel.startswith("Suchergebnisse") \
                or not markt_passt(s.adresse, markt):
            continue
        text = s.text
        if (wissen.ANGEBOTE_KOPF not in text and _liste(s.adresse, s.titel)) or not verkauft(text):
            continue
        name = _produkt_der_seite(s.titel, text)
        if fremd(name):
            continue
        preis = None
        if wissen.ANGEBOTE_KOPF in text:
            block = text[text.index(wissen.ANGEBOTE_KOPF):].split("\n\n")[0]
            if wissen.MEHRERE_HAENDLER not in block:
                preis = _naechster_preis(s.titel + "\n" + block, v, s.titel, markt)
        if preis is None:
            preis = _naechster_preis(s.titel + "\n" + text[:6000], v, s.titel, markt)
        if preis:
            gefunden.append(Angebot(host(s.adresse), preis[0], s.adresse, "seite", preis[1], name if alternativen else ""))
    for t in treffer:
        a = str(t.get("adresse", ""))
        if not a or ist_vergleichsseite(a, str(t.get("titel", "")), str(t.get("text", ""))) or kein_haendler(a, f"{t.get('titel', '')} {t.get('text', '')}") \
                or not markt_passt(a, markt):
            continue
        if not verkauft(f"{t.get('titel', '')} {t.get('text', '')}") or fremd(str(t.get("titel", ""))):
            continue
        preis = _naechster_preis(f"{t.get('titel', '')} {t.get('text', '')}", v, str(t.get("titel", "")), markt)
        if preis:
            gefunden.append(Angebot(host(a), preis[0], a, "treffer", preis[1], _produkt(str(t.get("titel", ""))) if alternativen else ""))
    soll = waehrung_des_markts(markt)
    if not soll and gefunden:
        soll = max({g.waehrung for g in gefunden}, key=lambda w: sum(1 for g in gefunden if g.waehrung == w))
    gefunden = [g for g in gefunden if g.waehrung == soll]
    return zusammenfassen(gefunden, anker(treffer, v, soll))


def _produkt(titel: str) -> str:
    t = re.sub(r"^Nachgeschaut:\s*", "", str(titel or ""))
    return _name_sauber(re.split(r"\s+[|–—-]\s+|\s+[|]", t)[0])[:60]


def _produkt_der_seite(titel: str, text: str) -> str:
    import wissen
    m = re.search(re.escape(wissen.ANGEBOTE_KOPF) + r" \(Produkt „([^“\n]{2,160})“\)", text or "")
    return _name_sauber(m.group(1))[:60] if m else _produkt(titel)


def _land(adresse: str) -> str:
    import belege
    return belege.land_der_adresse(adresse).upper()


_LISTE_ADRESSE = re.compile(r"(?i)/(?:list|lists|brand|brands|category|categories|kategorie|c|s|search|suche|ricerca|recherche|buscar|zoeken|"
                            r"szukaj|hledat|keres|catalog|catalogue|catalogo)/|[?&](?:q|k|query|search|s)=")
_LISTE_TITEL = re.compile(r"(?i)\bonline kaufen\b|\bgünstig kaufen\b|\bbuy online\b|\bshop all\b|\bacquista online\b|\bacheter en ligne\b|"
                          r"\bcomprar online\b|\bonline kopen\b|\bkup online\b|\b通販\b")


def _liste(adresse: str, titel: str) -> bool:
    return bool(_LISTE_ADRESSE.search(adresse or "") or _LISTE_TITEL.search(titel or ""))


_RANG = {"seite": 0, "vergleich": 1, "treffer": 2}


def _schluessel(haendler: str) -> str:
    return re.sub(r"[^a-z0-9]", "", haendler.lower())


def _ohne_endung(haendler: str) -> str:
    return _schluessel(re.sub(r"\.[a-z]{2,3}(?:\.[a-z]{2})?$", "", haendler.lower().strip()))


def anker(treffer: list[dict], v: Variante, waehrung: str = "") -> float | None:
    werte = []
    for t in treffer:
        a, titel = str(t.get("adresse", "")), str(t.get("titel", ""))
        if not ist_vergleichsseite(a, titel) or not v.passt(titel, titel):
            continue
        werte += [w for _a, _e, w, iso in betraege(titel) if w > 0 and (not waehrung or iso == waehrung)]
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
    for t in list(treffer) + [{"adresse": s.adresse, "titel": s.titel, "text": s.text} for s in seiten]:
        a = str(t.get("adresse", ""))
        if a and re.match(r"^https?://[^\s|<>()\[\]`]+$", a) and ist_vergleichsseite(a, str(t.get("titel", "")), str(t.get("text", ""))) \
                and host(a) not in out:
            out[host(a)] = a
    return list(out.items())[:3]


_ZEICHEN_TABELLE = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CNY": "¥", "INR": "₹", "KRW": "₩"}
_OHNE_CENT = frozenset({"JPY", "KRW", "HUF", "ISK", "CLP", "VND", "IDR", "TWD"})


def _geld(x: float, englisch: bool, waehrung: str = "EUR") -> str:
    stellen = 0 if waehrung in _OHNE_CENT else 2
    s = f"{x:,.{stellen}f}"
    zeichen = _ZEICHEN_TABELLE.get(waehrung, "")
    if englisch:
        return f"{zeichen}{s}" if zeichen else f"{waehrung} {s}"
    s = s.replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{s} {zeichen or waehrung}"


TABELLE_MAX = 8


def tabelle(gefunden: list[Angebot], portale: list[tuple[str, str]], *, englisch: bool = False, stand: str = "") -> str:
    if not gefunden:
        if englisch:
            satz = "I couldn't find a shop page that shows a price for exactly this model."
            return satz + (f" You can compare prices at {', '.join(a for _h, a in portale)}." if portale else "")
        satz = "Bei den Händlern, die ich lesen konnte, stand kein Preis für genau dieses Modell."
        return satz + (f" Preise vergleichen kannst du hier: {', '.join(a for _h, a in portale)}." if portale else "")
    mit_produkt = any(g.produkt for g in gefunden)
    kopf = "| Shop | Price | Checked |" if englisch else "| Händler | Preis | Geprüft |"
    if mit_produkt:
        kopf = ("| Product " if englisch else "| Produkt ") + kopf
    zeilen = [kopf, "|---|---|---|---|" if mit_produkt else "|---|---|---|"]
    for g in gefunden[:TABELLE_MAX]:
        quelle = g.herkunft.split(":", 1)[1] if g.herkunft.startswith("vergleich:") else ""
        if englisch:
            wo = "on the shop's page" if g.herkunft == "seite" else f"listed on {quelle}" if quelle else "in the search result"
        else:
            wo = "auf der Seite des Händlers" if g.herkunft == "seite" else f"laut {quelle}" if quelle else "im Suchtreffer"
        zeilen.append((f"| {g.produkt or '–'} " if mit_produkt else "") + f"| {g.haendler} | {_geld(g.preis, englisch, g.waehrung)} | {wo} |")
    g0 = gefunden[0]
    wer = f"{g0.produkt} ({'at' if englisch else 'bei'} {g0.haendler})" if g0.produkt else g0.haendler
    satz = (f"The cheapest is {wer} at {_geld(g0.preis, englisch, g0.waehrung)}." if englisch else
            f"Am günstigsten ist {wer} mit {_geld(g0.preis, englisch, g0.waehrung)}.")
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
        if betraege(z) or nachschauen.geldbetraege(z):
            continue
        behalten.append(z)
    vorne = re.sub(r"\n{3,}", "\n\n", "\n".join(behalten)).strip()
    return "\n\n".join(t for t in (vorne, tabelle(gefunden, portale, englisch=englisch, stand=stand)) if t)
