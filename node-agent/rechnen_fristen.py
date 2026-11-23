# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re

from rechnen import Ergebnis

STAND = "23.11.2026"
_STUFEN = ((25, "5 Monate"), (15, "4 Monate"), (5, "3 Monate"), (2, "2 Monate"), (0, "6 Wochen"))


_ARBEIT = re.compile(r"(?i)\b(?:angestellt\w*|arbeiter\w*|arbeitgeber\w*|arbeitnehmer\w*|dienstgeber\w*|dienstnehmer\w*|dienstverhältnis\w*|"
                     r"dienstjahr\w*|arbeitsjahr\w*|arbeitsverhältnis\w*|job\w*|firma|betrieb|beschäftigt\w*|chef\w*)\b")
_NICHT_ARBEIT = re.compile(r"(?i)\b(?:miet\w*|wohnung\w*|vermiet\w*|versicherung\w*|handy\w*|mobilfunk\w*|kredit\w*|abo\w*|strom\w*|"
                           r"gas\w*|internet\w*|fitness\w*|zeitung\w*)\b")
_EIGENE_REGELN = re.compile(r"(?i)\b(?:deutschland|schweiz|lehrling\w*|probezeit|befristet\w*|beamt\w*|kollektivvertrag\w*|saison\w*|"
                            r"gastgewerbe|gastronomie|tourismus|baugewerbe|freie[rn]?\s+dienstnehmer\w*|vertragsbedienstet\w*|hausbesorger\w*|"
                            r"hausgehilf\w*|landarbeit\w*|leiharbeit\w*|arbeitskräfteüberlass\w*|karenz\w*|schwanger\w*|mutterschutz|"
                            r"elternteilzeit|behindert\w*|betriebsrat\w*|präsenzdienst|zivildienst)\b")


def loesen(text: str) -> Ergebnis | None:
    t = " ".join(str(text or "").split())
    if not re.search(r"(?i)\bkündigungsfrist\w*\b", t) or not re.search(r"(?i)\b(?:österreich\w*|austria\w*)\b", t):
        return None
    if not _ARBEIT.search(t) or _NICHT_ARBEIT.search(t):
        return None
    if _EIGENE_REGELN.search(t):
        return None
    m = (re.search(r"(?i)\b(?:nach|seit)\s+(\d{1,2})\s+(?:dienst|arbeits|beschäftigungs)?jahren\b", t)
         or re.search(r"(?i)\b(\d{1,2})\s+jahre?\s+(?:lang\s+)?(?:beschäftigt|angestellt|im\s+betrieb|in\s+der\s+firma|dabei)\b", t))
    im = re.search(r"(?i)\bim\s+(\d{1,2})\.\s+(?:dienst|arbeits)?jahr\b", t)
    if m:
        vollendet = int(m.group(1))
    elif im:
        vollendet = int(im.group(1)) - 1
    else:
        return None
    if not 0 <= vollendet <= 60:
        return None
    frist = next(f for ab, f in _STUFEN if vollendet >= ab)
    stufe = next(ab for ab, _f in _STUFEN if vollendet >= ab)
    grund = ("bis zum vollendeten 2. Dienstjahr" if stufe == 0 else f"ab dem vollendeten {stufe}. Dienstjahr")
    jahre = "vollendeten Dienstjahr" if vollendet == 1 else "vollendeten Dienstjahren"
    arbeitgeber = (f"Kündigt der Arbeitgeber, beträgt die Kündigungsfrist nach {vollendet} {jahre} {frist} ({grund}, § 20 Abs. 2 "
                   f"Angestelltengesetz), zum Quartalsende, außer der 15. oder der Monatsletzte ist vereinbart.")
    selbst = ("Kündigst du selbst, gilt 1 Monat zum Monatsletzten, wenn dein Vertrag nichts anderes sagt; vereinbart werden dürfen bis zu "
              "6 Monate, nie aber eine kürzere Frist als die des Arbeitgebers.")
    zuerst_selbst = bool(re.search(r"(?i)\b(?:ich\s+(?:will\s+|möchte\s+)?kündige\w*|selbst\s+kündig\w*|wenn\s+ich\s+kündige|"
                                   r"arbeitnehmerkündigung|ich\s+will\s+(?:gehen|aufhören))\b", t))
    erst, dann = (selbst, arbeitgeber) if zuerst_selbst else (arbeitgeber, selbst)
    de = (f"{erst} {dann}\n\n"
          f"Die Stufen: bis 2 Jahre 6 Wochen, ab 2 Jahren 2 Monate, ab 5 Jahren 3 Monate, ab 15 Jahren 4 Monate, ab 25 Jahren 5 Monate. "
          f"Seit 1.10.2021 gilt das grundsätzlich auch für Arbeiter; in Branchen mit überwiegend Saisonbetrieben (etwa Bau, Tourismus) darf "
          f"der Kollektivvertrag abweichen. Der Kollektivvertrag oder dein Dienstvertrag kann auch sonst längere Fristen vorsehen; "
          f"Stand der Tabelle {STAND}.")
    en = (f"If the employer gives notice, the notice period after {vollendet} completed years of service is "
          f"{frist.replace('Monate', 'months').replace('Wochen', 'weeks')} (section 20(2) Austrian Salaried Employees Act). "
          f"If you resign yourself, it is 1 month.")
    return Ergebnis(de, en)
