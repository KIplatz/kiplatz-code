# SPDX-License-Identifier: AGPL-3.0-or-later
import belege as b


def test_ein_laengerer_name_mit_gleichem_anfang_belegt_den_namen_nicht():
    st = b._wortstaemme
    assert not b.name_genau_belegt("Ambros", st("Ambrosi Chachua ist ein Fußballer aus Georgien"))
    assert not b.name_genau_belegt("Ambros", st("Der heilige Ambrosius war Bischof"))
    assert b.gefragter_name_fehlt("Wer ist Ambros?", "", ["Ambrosi Chachua ist ein Fußballer aus Georgien"]) == "Ambros"


def test_beugungen_bleiben_belegt():
    st = b._wortstaemme
    assert b.name_genau_belegt("Ambros", st("Wolfgang Ambros ist ein Liedermacher"))
    assert b.name_genau_belegt("Goethe", st("Goethes Faust erschien 1808"))
    assert b.name_genau_belegt("Goethes", st("Goethe schrieb den Faust"))
    assert b.name_genau_belegt("Kompany", st("Kompanys Mannschaft gewann"))
    assert b.name_genau_belegt("Müller", st("die Firma der Müllers"))


def test_ein_name_allein_nennt_die_anderen_aus_den_quellen():
    quellen = ["Lukáš Ambros ist ein tschechischer Fußballspieler.", "Wolfgang Ambros ist ein österreichischer Liedermacher."]
    name, weitere = b.namensvettern("Wer ist Ambros?", "Lukáš Ambros ist ein tschechischer Fußballspieler.", quellen)
    assert name == "Ambros" and weitere == ["Wolfgang Ambros"]
    assert b.namensvettern("Who is Ambros?", "", quellen)[1] == ["Lukáš Ambros", "Wolfgang Ambros"]


def test_volle_namen_und_beschreibungen_fragen_nicht_nach():
    quellen = ["Lukáš Ambros ist Fußballer.", "Wolfgang Ambros ist Liedermacher."]
    assert b.namensvettern("Wer ist Wolfgang Ambros?", "", quellen) == ("", [])
    assert b.namensvettern("Wer ist der Bundeskanzler?", "", quellen) == ("", [])
    assert b.namensvettern("Wer ist Ambros?", "Wolfgang Ambros …", ["Der Ambros singt.", "Wolfgang Ambros ist Liedermacher."]) == ("Ambros", [])
