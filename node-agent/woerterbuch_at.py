# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

QUELLE = {"titel": "Österreichisches Wörterbuch von KIplatz", "adresse": "https://kiplatz.at/", "art": "seite"}

WOERTER: dict[str, tuple[str, str]] = {
    "paradeiser": ("Tomate", "tomato"),
    "paradeismark": ("Tomatenmark", "tomato paste"),
    "erdapfel": ("Kartoffel", "potato"),
    "erdäpfel": ("Kartoffeln", "potatoes"),
    "karfiol": ("Blumenkohl", "cauliflower"),
    "kren": ("Meerrettich", "horseradish"),
    "kohlsprossen": ("Rosenkohl", "Brussels sprouts"),
    "fisolen": ("grüne Bohnen", "green beans"),
    "marille": ("Aprikose", "apricot"),
    "ribisel": ("Johannisbeere (rote oder schwarze)", "currant (red or black)"),
    "zwetschke": ("Zwetschge, eine Pflaumensorte", "a kind of plum"),
    "ringlotte": ("Reneklode, eine kleine Pflaumensorte", "greengage plum"),
    "schwammerl": ("Pilz", "mushroom"),
    "eierschwammerl": ("Pfifferling", "chanterelle mushroom"),
    "häuptelsalat": ("Kopfsalat", "butterhead lettuce"),
    "vogerlsalat": ("Feldsalat", "lamb's lettuce"),
    "kukuruz": ("Mais", "corn, maize"),
    "melanzani": ("Aubergine", "aubergine, eggplant"),
    "topfen": ("Quark", "quark, curd cheese"),
    "schlagobers": ("geschlagene Sahne, Schlagsahne", "whipped cream"),
    "obers": ("Sahne", "cream"),
    "sauerrahm": ("saure Sahne", "sour cream"),
    "faschiertes": ("Hackfleisch", "minced meat"),
    "faschierte laibchen": ("Frikadellen, Fleischlaibchen", "meat patties"),
    "laibchen": ("flache, runde Bratlinge, etwa Fleischlaibchen", "small flat patties"),
    "semmel": ("Brötchen, ein kleines rundes Gebäck", "bread roll"),
    "weckerl": ("kleines, längliches Brötchen", "small bread roll"),
    "kipferl": ("Hörnchen, ein gebogenes Gebäck", "crescent-shaped pastry"),
    "palatschinke": ("dünner Pfannkuchen, ähnlich einer Crêpe", "thin pancake, like a crêpe"),
    "powidl": ("Pflaumenmus", "plum jam"),
    "germ": ("Hefe", "yeast"),
    "staubzucker": ("Puderzucker", "icing sugar"),
    "kletzen": ("getrocknete Birnen", "dried pears"),
    "beiried": ("Roastbeef, ein Stück vom Rinderrücken", "sirloin, roast beef cut"),
    "lungenbraten": ("Rinderfilet oder Schweinsfilet", "tenderloin"),
    "stelze": ("Schweinshaxe", "pork knuckle"),
    "hendl": ("Hähnchen, Brathuhn", "chicken"),
    "eierspeis": ("Rührei", "scrambled eggs"),
    "grammeln": ("Grieben, ausgebratene Speckwürfel", "pork cracklings"),
    "blunzn": ("Blutwurst", "black pudding, blood sausage"),
    "krapfen": ("Berliner, ein gefülltes Hefegebäck", "jam doughnut"),
    "golatsche": ("Plundergebäck mit Füllung, etwa Topfen", "filled puff pastry"),
    "jause": ("Zwischenmahlzeit, Brotzeit", "snack, light meal"),
    "gusto": ("Appetit, Lust auf etwas", "craving, appetite"),
    "kracherl": ("Limonade", "fizzy lemonade"),
    "krügerl": ("halber Liter Bier", "half a litre of beer"),
    "seidl": ("ein Glas Bier mit 0,3 Liter", "a 0.3 litre glass of beer"),
    "spritzer": ("Wein mit Mineralwasser gemischt, Weinschorle", "wine spritzer"),
    "gspritzter": ("Wein oder Saft mit Mineralwasser gemischt, Schorle", "spritzer"),
    "heuriger": ("Weinlokal eines Winzers, in dem er eigenen Wein ausschenkt; auch der junge Wein des Jahres", "wine tavern of a winegrower; also this year's young wine"),
    "beisl": ("einfaches Gasthaus, Kneipe", "simple pub, tavern"),
    "zuckerl": ("Bonbon", "sweet, candy"),
    "sackerl": ("Tüte, kleiner Beutel", "bag"),
    "packerl": ("Päckchen", "small parcel"),
    "kasten": ("Schrank, etwa Kleiderkasten; ein „Kasten Bier“ ist eine Getränkekiste", "wardrobe or cupboard; a “Kasten Bier” is a crate of beer"),
    "sessel": ("Stuhl", "chair"),
    "polster": ("Kissen", "pillow, cushion"),
    "tuchent": ("Bettdecke, Federbett", "duvet"),
    "rauchfang": ("Schornstein", "chimney"),
    "rauchfangkehrer": ("Schornsteinfeger", "chimney sweep"),
    "stiege": ("Treppe", "stairs"),
    "stockerl": ("Hocker", "stool"),
    "mistkübel": ("Mülleimer", "rubbish bin"),
    "kübel": ("Eimer", "bucket"),
    "kluppe": ("Wäscheklammer", "clothes peg"),
    "patschen": ("Hausschuhe; auch ein Reifen ohne Luft", "slippers; also a flat tyre"),
    "leiberl": ("T-Shirt", "T-shirt"),
    "mascherl": ("Fliege, die man zum Hemd trägt", "bow tie"),
    "jänner": ("Januar", "January"),
    "feber": ("Februar", "February"),
    "heuer": ("dieses Jahr", "this year"),
    "matura": ("Abitur, die Reifeprüfung am Ende der höheren Schule", "school-leaving exam"),
    "krankenstand": ("Krankschreibung, die Zeit, in der jemand krank von der Arbeit fernbleibt", "sick leave"),
    "trafik": ("Tabakladen, in dem es auch Zeitungen, Fahrscheine und Lotto gibt", "tobacconist and newsagent"),
    "bim": ("Straßenbahn", "tram"),
    "spital": ("Krankenhaus", "hospital"),
    "ordination": ("Arztpraxis", "doctor's surgery"),
    "gemeindebau": ("Wohnanlage, die einer Gemeinde gehört, Sozialwohnungen", "council housing"),
    "vorrang": ("Vorfahrt", "right of way"),
    "bankomat": ("Geldautomat", "cash machine, ATM"),
    "bankomatkarte": ("Debitkarte, mit der man am Geldautomaten Geld abhebt und bezahlt", "debit card"),
    "erlagschein": ("Zahlschein, Überweisungsvordruck", "payment slip"),
    "kassa": ("Kasse", "checkout, till"),
    "teuerung": ("Preisanstieg, Inflation", "rising prices, inflation"),
    "pickerl": ("Aufkleber; auch die Autobahnvignette und die jährliche Überprüfung des Autos nach § 57a KFG", "sticker; also the motorway vignette and the annual vehicle inspection"),
    "parkpickerl": ("Parkerlaubnis für eine Kurzparkzone, etwa für Bewohner des Viertels", "residents' parking permit"),
    "sackgeld": ("Taschengeld", "pocket money"),
    "haberer": ("Kumpel, guter Freund", "mate, buddy"),
    "oida": ("umgangssprachlicher Ausruf oder Anrede, etwa „Alter“, in Wien sehr verbreitet", "slang exclamation or form of address, like “dude”"),
    "servus": ("Gruß zum Kommen und Gehen, hallo oder tschüss", "hello or goodbye"),
    "baba": ("tschüss", "bye"),
    "leiwand": ("toll, super", "great, cool"),
    "fesch": ("hübsch, schick", "good-looking, smart"),
    "bussi": ("Küsschen", "little kiss"),
    "gspusi": ("Liebschaft, Affäre", "fling, affair"),
    "schmäh": ("Witz, Scherz, auch eine besondere Art von Humor und Charme", "joke, banter, a particular kind of humour"),
    "grant": ("schlechte Laune", "grumpiness"),
    "grantig": ("schlecht gelaunt", "grumpy"),
    "hackn": ("Arbeit", "work, job"),
    "tschick": ("Zigarette", "cigarette"),
    "gatsch": ("Matsch, Schlamm", "mud, slush"),
    "wimmerl": ("Pickel", "pimple"),
    "gelse": ("Stechmücke", "mosquito"),
    "fasching": ("Karneval", "carnival"),
    "krampus": ("Schreckgestalt, die den Nikolaus begleitet", "horned figure that accompanies St Nicholas"),
}

_ENDUNGEN = ("n", "en", "s", "e", "er", "ern")
_FRAGE = re.compile(r"\b(was (ist|sind|bedeute[tn]|hei(ß|ss)(t|en)|meint man( mit)?)|was versteht man unter|wof[üu]r steht|"
                    r"what (is|are|does|do)|what's|meaning of|definition of)\b", re.I)


def _stichwort(wort: str) -> str | None:
    w = wort.lower().strip(" „“\"'‚‘?!.,;:()")
    if w in WOERTER:
        return w
    for e in _ENDUNGEN:
        if w.endswith(e) and len(w) - len(e) >= 4 and w[: -len(e)] in WOERTER:
            return w[: -len(e)]
    return None


_DANACH_OK = {"in", "österreich", "oesterreich", "auf", "deutsch", "hochdeutsch", "englisch", "genau", "eigentlich", "bei", "uns", "im", "dialekt",
              "wienerisch", "auf", "bayrisch", "überhaupt", "ueberhaupt", "denn", "bitte", "so", "heißt", "heisst", "das", "der", "die", "es", "ist", "noch",
              "mal", "einfach", "erklärt", "erklaert", "gemeint", "means", "mean", "in", "austrian", "german", "deutschland", "schweiz", "austria",
              "an", "a", "the", "recipe", "rezept", "einem", "einer", "österreichischen", "oesterreichischen", "österreichisch", "wort", "word",
              "dialect", "slang", "germany", "vienna", "wien", "wiener"}


def begriffe(frage: str) -> list[str]:
    f = " ".join(str(frage or "").split())
    if not f or len(f) > 120 or not _FRAGE.search(f):
        return []
    out: list[str] = []
    woerter = re.findall(r"[\wäöüßÄÖÜ]+", f)
    for i in range(len(woerter)):
        for n in (2, 1):
            if i + n <= len(woerter):
                s = _stichwort(" ".join(woerter[i:i + n]))
                if s and any(x.lower() not in _DANACH_OK for x in woerter[i + n:]) and not re.search(r"\b(und|oder|bzw|and|or)\b", " ".join(woerter[i + n:]), re.I):
                    continue
                if s and s not in out and not any(s in o for o in out):
                    out.append(s)
    return out[:3]


def text(stichwort: str, *, englisch: bool = False) -> str:
    de, en = WOERTER[stichwort]
    klein = ("heuer", "leiwand", "fesch", "grantig", "baba", "oida", "servus")
    wort = stichwort if stichwort in klein else stichwort[:1].upper() + stichwort[1:]
    if englisch:
        return f"“{wort}” is an Austrian German word. It means: {en}."
    return f"„{wort}“ ist ein österreichisches Wort und bedeutet: {de}."


def englisch(frage: str) -> bool:
    return bool(re.search(r"^\s*(what|what's)\b|\b(meaning|definition) of\b", str(frage or ""), re.I))


def treffer(frage: str):
    b = begriffe(frage)
    if not b or englisch(frage):
        return []
    import wissen
    en = englisch(frage)
    texte = [text(s, englisch=en) for s in b]
    q = wissen.Quelle("woerterbuch-at", QUELLE["art"], QUELLE["titel"], QUELLE["adresse"], wissen._jetzt(), sum(len(t) for t in texte))
    return [wissen.Treffer(q, t, 9.5 - i * 0.1) for i, t in enumerate(texte)]


__all__ = ["WOERTER", "begriffe", "text", "treffer", "QUELLE"]
