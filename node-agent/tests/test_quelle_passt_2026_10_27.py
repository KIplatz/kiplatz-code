# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wissen

W = "https://de.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"
FAELLE = [
    ("Was ist die Hauptstadt von Russland?", "Die Hauptstadt von Russland ist Moskau.", W + "Bessarabien", "Bessarabien", False),
    ("Was ist die Hauptstadt von Ägypten?", "Die Hauptstadt von Ägypten ist Kairo.", W + "Alexander_der_Gro%C3%9Fe", "Alexander der Große", False),
    ("Was ist die Hauptstadt von Frankreich?", "Die Hauptstadt von Frankreich ist Paris.", W + "Bordeaux", "Bordeaux", False),
    ("Was ist die Hauptstadt von Japan?", "Die Hauptstadt von Japan ist Tokio.", W + "Bahnhof_Tokio", "Bahnhof Tokio", True),
    ("Was ist die Hauptstadt von Brasilien?", "Die Hauptstadt von Brasilien ist Brasília.", W + "Brasilien", "Brasilien", True),
    ("Was ist die Hauptstadt von Deutschland?", "Die Hauptstadt von Deutschland ist Berlin.", W + "Berlin", "Berlin", True),
    ("Was ist die Hauptstadt von Thailand?", "Die Hauptstadt von Thailand ist Bangkok.", W + "Bangkok", "Bangkok", True),
    ("Was ist die Hauptstadt von Kolumbien?", "Die Hauptstadt von Kolumbien ist Bogotá.", W + "Bogot%C3%A1", "Bogotá", True),
    ("Wer war Ludwig van Beethoven?", "Der Komponist Ludwig van Beethoven lebte von 1770 bis 1827.", W + "Ludwig_van_Beethoven", "Ludwig van Beethoven", True),
    ("What is the capital of Egypt?", "The capital of Egypt is Cairo.", E + "Cairo", "Cairo", True),
    ("What is the capital of Iran?", "The capital of Iran is Tehran.", "https://www.worldatlas.com/articles/what-is-the-capital-city-of-iran.html", "What Is The Capital City Of Iran?", True),
    ("What is the capital of Pakistan?", "The capital of Pakistan is Islamabad.", E + "Islamabad", "Islamabad", True),
    ("What is the capital of Indonesia?", "Jakarta is currently the capital of Indonesia. Indonesia is building a new capital called Nusantara.", E + "Nusantara", "Nusantara", True),
    ("What is the capital of Bangladesh?", "The capital of Bangladesh is Dhaka.", E + "Dhaka", "Dhaka", True),
    ("What is the capital of Mexico?", "The capital of Mexico is Mexico City.", E + "Mexico_City", "Mexico City", True),
    ("What is the capital of Ethiopia?", "The capital of Ethiopia is Addis Ababa.", E + "Addis_Ababa", "Addis Ababa", True),
    ("What is the capital of Philippines?", "The capital of the Philippines is Manila.", E + "Capital_of_the_Philippines", "Capital of the Philippines", True),
    ("Who was Frédéric Chopin?", "Frédéric Chopin was a Polish composer.", E + "Fr%C3%A9d%C3%A9ric_Chopin", "Frédéric Chopin", True),
    ("What is the capital of Italy?", "The capital of Italy is Rome.", "https://www.e-a-a.org/EAA2024/EAA2024/Rome.aspx", "Rome", True),
    ("What is the capital of Kenya?", "The capital of Kenya is Nairobi.", "https://www.youtube.com/watch?v=7OUHWWdGKOY", "Nairobi, the capital of Kenya", True),
    ("What is the capital of Myanmar (Burma)?", "The capital of Myanmar is Naypyidaw.", E + "Naypyidaw", "Naypyidaw", True),
]


def test_die_gemessenen_quellen():
    for frage, antwort, adresse, titel, passt in FAELLE:
        assert wissen.quelle_passt({"adresse": adresse, "titel": titel}, frage, antwort) is passt, (frage, titel)


def test_eigene_dateien_und_rechnungen_bleiben():
    q = [{"nummer": 1, "art": "dokument", "titel": "Mietvertrag.pdf", "adresse": "", "privat": True},
         {"nummer": 2, "art": "berechnet", "titel": "Kalender", "adresse": ""},
         {"nummer": 3, "art": "seite", "titel": "Bessarabien", "adresse": W + "Bessarabien"},
         {"nummer": 4, "art": "seite", "titel": "Moskau", "adresse": W + "Moskau"}]
    assert [x["nummer"] for x in wissen.passende_quellen(q, "Was ist die Hauptstadt von Russland?", "Die Hauptstadt ist Moskau.")] == [1, 2, 4]


def test_ohne_titel_und_adresse_laesst_sich_nichts_sagen():
    assert wissen.quelle_passt({"titel": "", "adresse": ""}, "Wer war Mozart?", "Mozart war ein Komponist.")
