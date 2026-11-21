# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

DE: dict[str, str] = {
    "V.a.": "Verdacht auf (noch nicht bestätigt)",
    "Z.n.": "Zustand nach (etwas war früher: eine Operation, Verletzung oder Krankheit)",
    "St.p.": "Status post, heißt „Zustand nach“ (etwas war früher)",
    "DD": "Differentialdiagnose: eine andere mögliche Erklärung, die noch abgeklärt wird",
    "Dg.": "Diagnose",
    "o.B.": "ohne Befund, also unauffällig",
    "bds.": "beidseits, auf beiden Seiten",
    "re.": "rechts",
    "li.": "links",
    "Pat.": "Patientin oder Patient",
    "HN": "Hirnnerven (die Nerven, die direkt aus dem Gehirn kommen, etwa für Augen, Gesicht und Schlucken)",
    "MER": "Muskeleigenreflexe (Reflexe, die beim Klopfen auf eine Sehne ausgelöst werden)",
    "BSR": "in Nervenbefunden Bizepssehnenreflex (Reflex am Oberarm), im Labor Blutsenkungsreaktion (mehrdeutig, der Zusammenhang entscheidet)",
    "TSR": "Trizepssehnenreflex (Reflex an der Rückseite des Oberarms)",
    "PSR": "Patellarsehnenreflex (Kniereflex)",
    "ASR": "Achillessehnenreflex (Reflex an der Ferse)",
    "RPR": "Radiusperiostreflex (Reflex am Unterarm)",
    "KM": "meist Kontrastmittel („keine KM-Aufnahme“: die Stelle nimmt kein Kontrastmittel auf), im MRT auch Knochenmark (KM-Ödem); mehrdeutig",
    "LP": "Lumbalpunktion: Entnahme von Nervenwasser aus dem unteren Rücken",
    "VEP": "visuell evozierte Potenziale: Messung, wie schnell das Sehsystem Lichtreize weiterleitet",
    "SEP": "somatosensibel evozierte Potenziale: Messung, wie schnell Nerven Berührungsreize weiterleiten",
    "MS": "in Nervenbefunden Multiple Sklerose, in Herzbefunden Mitralklappenstenose (mehrdeutig, der Zusammenhang entscheidet)",
    "HWI": "Harnwegsinfekt, in Herzbefunden auch Hinterwandinfarkt (mehrdeutig, der Zusammenhang entscheidet)",
    "HWS": "Halswirbelsäule",
    "BWS": "Brustwirbelsäule",
    "LWS": "Lendenwirbelsäule",
    "NSTEMI": "Herzinfarkt ohne ST-Hebung im EKG",
    "STEMI": "Herzinfarkt mit ST-Hebung im EKG",
    "KHK": "koronare Herzkrankheit: Verengung der Herzkranzgefäße; die Zahl dahinter (KHK-3) nennt, wie viele Hauptgefäße betroffen sind",
    "PCI": "Aufdehnen einer verengten Herzkranzarterie mit einem Katheter",
    "DES": "Stent, der ein Medikament abgibt, damit sich das Gefäß nicht wieder verengt",
    "RIVA": "vorderer absteigender Ast der linken Herzkranzarterie",
    "RCX": "umbiegender Ast der linken Herzkranzarterie",
    "RCA": "rechte Herzkranzarterie",
    "LVEF": "Auswurfleistung der linken Herzkammer in Prozent",
    "HT": "Hypertonie, Bluthochdruck; in einem Untersuchungsbefund auch Herztöne (mehrdeutig)",
    "DM": "Diabetes mellitus, Zuckerkrankheit (DM II: Typ 2)",
    "HLP": "Hyperlipidämie, erhöhte Blutfette",
    "py": "Packungsjahre: 1 Packungsjahr heißt ein Jahr lang täglich eine Packung Zigaretten",
    "NAW": "Notarztwagen",
    "FA": "Fachärztin oder Facharzt; als Überschrift auch Familienanamnese, also Krankheiten in der Familie (mehrdeutig)",
    "ASS": "Acetylsalicylsäure (hemmt die Blutplättchen)",
    "VKB": "vorderes Kreuzband",
    "HKB": "hinteres Kreuzband",
    "IM": "Innenmeniskus",
    "AM": "Außenmeniskus",
    "HH": "Hinterhorn (hinterer Teil des Meniskus)",
    "VH": "Vorderhorn (vorderer Teil des Meniskus)",
    "RO": "in Lungenbefunden: rechter Oberlappen",
    "RM": "in Lungenbefunden: rechter Mittellappen",
    "RU": "in Lungenbefunden: rechter Unterlappen",
    "LO": "in Lungenbefunden: linker Oberlappen",
    "LU": "in Lungenbefunden: linker Unterlappen",
    "CT": "Computertomographie (Schichtröntgen)",
    "MRT": "Magnetresonanztomographie (Schichtbild mit Magnetfeld, ohne Röntgenstrahlen)",
    "EKG": "Elektrokardiogramm, Aufzeichnung der Herzströme",
    "EEG": "Elektroenzephalogramm, Aufzeichnung der Hirnströme",
    "CRP": "C-reaktives Protein, ein Entzündungswert im Blut",
    "Hb": "Hämoglobin, der rote Blutfarbstoff, der Sauerstoff trägt",
    "MCV": "mittleres Volumen, also die Größe der roten Blutkörperchen",
    "TSH": "Thyreoidea-stimulierendes Hormon: Hormon der Hirnanhangdrüse, das die Schilddrüse steuert",
    "fT4": "freies Thyroxin, ein Schilddrüsenhormon",
    "TPO-AK": "Antikörper gegen ein Eiweiß der Schilddrüse (Thyreoperoxidase)",
    "HbA1c": "Langzeit-Blutzuckerwert der letzten 2 bis 3 Monate",
    "GOT": "Leberwert (Enzym, heute auch AST genannt)",
    "GPT": "Leberwert (Enzym, heute auch ALT genannt)",
    "SD": "meist Schilddrüse; bei Messwerten auch Standardabweichung (mehrdeutig)",
    "LK": "Lymphknoten",
    "TI-RADS": "Einteilung von Schilddrüsenknoten im Ultraschall nach ihren Merkmalen",
    "LGIEN": "niedriggradige Zellveränderung in der Schleimhaut, eine Vorstufe",
    "HGIEN": "hochgradige Zellveränderung in der Schleimhaut, eine weiter fortgeschrittene Vorstufe",
    "R0": "am Schnittrand wurde kein krankhaftes Gewebe gefunden",
    "Wo.": "Wochen",
}

EN: dict[str, str] = {
    "s/p": "status post: something happened earlier (an operation, injury or illness)",
    "r/o": "rule out: still to be excluded",
    "CAD": "coronary artery disease, narrowing of the heart's arteries",
    "LAD": "in heart reports the left anterior descending artery; elsewhere also lymphadenopathy (enlarged lymph nodes) or left axis deviation on the ECG",
    "LVEF": "left ventricular ejection fraction, how much blood the left heart chamber pumps out, in percent",
    "NSTEMI": "heart attack without ST elevation on the ECG",
    "STEMI": "heart attack with ST elevation on the ECG",
    "PCI": "opening a narrowed heart artery with a catheter",
    "DES": "drug-eluting stent, a stent that releases a medicine",
    "HTN": "hypertension, high blood pressure",
    "SOB": "shortness of breath",
    "bid": "twice a day",
    "tid": "three times a day",
    "qd": "once a day",
    "prn": "as needed",
    "CT": "computed tomography (cross-section X-ray)",
    "MRI": "magnetic resonance imaging (scan with a magnetic field, no X-rays)",
    "ECG": "electrocardiogram, recording of the heart's electrical activity",
    "CRP": "C-reactive protein, a marker of inflammation in the blood",
    "TSH": "thyroid-stimulating hormone, which controls the thyroid",
    "HbA1c": "long-term blood sugar over the last 2 to 3 months",
}

DOSIS = re.compile(r"(?<!\d)[0-2](?:[.,]5)?-[0-2](?:[.,]5)?-[0-2](?:[.,]5)?(?:-[0-2](?:[.,]5)?)?(?![\d-])")
DOSIS_DE = "Zahlen wie 1-0-1 nennen, wie oft ein Medikament genommen wird: morgens, mittags, abends (und nachts)"
DOSIS_EN = "Numbers like 1-0-1 say how often a medicine is taken: morning, midday, evening (and night)"


def _muster(schluessel: str) -> re.Pattern:
    gross = any(z.isupper() for z in schluessel)
    kern = re.escape(schluessel).replace(r"\.", r"\.\s?")
    return re.compile(r"(?<!\w)" + kern + (r"(?![\w])" if schluessel[-1].isalnum() else ""), 0 if gross else re.I)


_KNIE = re.compile(r"(?i)knie|menisk")
_LUNGE = re.compile(r"(?i)lunge|lappen|thorax|rundherd|pulmo")
GEBIET = {"IM": _KNIE, "AM": _KNIE, "HH": _KNIE, "VH": _KNIE, "VKB": _KNIE, "HKB": _KNIE,
          "RO": _LUNGE, "RM": _LUNGE, "RU": _LUNGE, "LO": _LUNGE, "LU": _LUNGE}
_DE = [(k, _muster(k), v) for k, v in DE.items()]
_EN = [(k, _muster(k), v) for k, v in EN.items()]


def gefunden(text: str, *, englisch: bool = False) -> list[tuple[str, str]]:
    t = text or ""
    aus = [(k, v) for k, m, v in (_EN if englisch else _DE) if m.search(t) and (k not in GEBIET or GEBIET[k].search(t))]
    if DOSIS.search(t):
        aus.append(("1-0-1", DOSIS_EN if englisch else DOSIS_DE))
    return aus


def zusatz(text: str, *, englisch: bool = False) -> str:
    treffer = gefunden(text, englisch=englisch)
    if not treffer:
        return ""
    liste = "; ".join(f"{k} = {v}" for k, v in treffer)
    if englisch:
        return ("Abbreviations in this text, from a checked list (use these meanings, not your own): " + liste + ". An abbreviation that is "
                "not on this list and that you don't know for sure: write that its meaning is not certain here.")
    return ("Abkürzungen in diesem Text, aus einer geprüften Liste (nimm diese Bedeutungen, nicht dein eigenes Wissen): " + liste + ". Eine "
            "Abkürzung, die nicht in dieser Liste steht und die du nicht sicher kennst: schreib dazu, dass die Bedeutung hier nicht sicher ist.")
