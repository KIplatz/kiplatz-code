# SPDX-License-Identifier: AGPL-3.0-or-later
import selbstauskunft as sa

SELBST = [
    "Wie kann man dich trainieren damit du intelligenter wirst?",
    "Warum lernst du nicht?",
    "Wie intelligent bist du?",
    "… keine kreativen Texte oder Meinungen. warum kannst du das nicht",
    "Lernst du aus meinen Fragen?",
    "Wer hat dich trainiert?",
    "Hast du Gefühle?",
    "Was sind deine Grenzen?",
    "Was ist dein Wissensstand?",
    "How smart are you?",
    "Do you learn from my questions?",
    "Why can't you write poems?",
    "What is your knowledge cutoff?",
]

ANDERES = [
    "Wie lerne ich am besten Vokabeln?",
    "Wie intelligent sind Delfine?",
    "Kannst du mir erklären, wie Machine Learning funktioniert?",
    "Wie trainiere ich meinen Hund?",
    "Was ist der Wissensstand zur Klimaforschung?",
    "Bist du sicher, dass Gemini besser als ChatGPT ist?",
    "How do neural networks learn?",
    "How smart are crows?",
    "Hast du ein Rezept für Kaiserschmarrn?",
]


def test_fragen_ueber_das_eigene_wesen_bekommen_die_selbstauskunft():
    for f in SELBST:
        assert sa.betrifft(f), f


def test_andere_fragen_mit_denselben_woertern_bleiben_beim_modell():
    for f in ANDERES:
        assert not sa.betrifft(f), f


def test_die_quelle_sagt_was_ueber_lernen_und_grenzen_stimmt():
    t = sa.TEXTE["lernen"]
    assert "keine KI trainiert" in t and "ab Werk ist er aus" in t and "keinen festen Wissensstand" not in t
    assert "einen festen Wissensstand, an dem es aufhört, gibt es darum nicht" in t
    assert any(x.text == t for x in sa.treffer())
    assert "nenne keinen Trainingsstand" in sa.ANWEISUNG
