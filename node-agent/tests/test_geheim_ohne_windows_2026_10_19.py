# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import stat

import pytest

import geheim


@pytest.fixture
def eigener_ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(geheim, "ORDNER", tmp_path / "geheim")
    geheim.vergessen()
    yield tmp_path / "geheim"
    geheim.vergessen()


def test_ein_hauptschluessel_nur_fuer_mich_und_nie_ein_zweiter(eigener_ordner):
    w1, w2 = geheim.schuetzen("0f" * 32), geheim.schuetzen("geheim-2")
    assert geheim.lesen(w1) == "0f" * 32 and geheim.lesen(w2) == "geheim-2" and w1 != geheim.schuetzen("0f" * 32)
    assert geheim.geschuetzt(w1) and "0f0f" not in w1
    if os.name != "posix":
        assert w1.startswith("dpapi:") and not eigener_ordner.exists()
        return
    assert w1.startswith("datei:") and w2.startswith("datei:")
    datei = eigener_ordner / geheim.SCHLUESSEL_DATEI
    assert stat.S_IMODE(os.stat(eigener_ordner).st_mode) == 0o700 and stat.S_IMODE(os.stat(datei).st_mode) == 0o600
    assert sorted(p.name for p in eigener_ordner.iterdir()) == [geheim.SCHLUESSEL_DATEI]
    os.chmod(datei, 0o644)
    geheim.vergessen()
    with pytest.raises(geheim.GeheimError) as e:
        geheim.lesen(w1)
    assert e.value.code == "GEHEIM_RECHTE"
    os.chmod(datei, 0o600)
    os.chmod(eigener_ordner, 0o755)
    geheim.vergessen()
    with pytest.raises(geheim.GeheimError):
        geheim.lesen(w1)


def test_ein_fremder_oder_beschaedigter_wert_gibt_nie_klartext(eigener_ordner):
    w = geheim.schuetzen("abc")
    art, _, rest = w.partition(":")
    import base64
    roh = base64.b64decode(rest)
    for stelle in (len(roh) // 2, len(roh) - 1):
        kaputt_roh = bytearray(roh)
        kaputt_roh[stelle] ^= 0x01
        kaputt = art + ":" + base64.b64encode(bytes(kaputt_roh)).decode("ascii")
        with pytest.raises(geheim.GeheimError) as e:
            geheim.lesen(kaputt)
        assert "abc" not in e.value.detail
    if os.name == "posix":
        (eigener_ordner / geheim.SCHLUESSEL_DATEI).unlink()
        geheim.vergessen()
        with pytest.raises(geheim.GeheimError) as e:
            geheim.lesen(w)
        assert e.value.code == "GEHEIM_SCHLUESSEL" and not (eigener_ordner / geheim.SCHLUESSEL_DATEI).exists()


def test_der_schluesselbund_wird_nie_ueberschrieben(eigener_ordner, monkeypatch):
    bund: dict = {}
    geschrieben = []

    def lesen(kennung):
        if bund.get("gesperrt"):
            raise geheim.GeheimError("GEHEIM_GESPERRT", "gesperrt")
        return bund.get(kennung)

    def schreiben(kennung, k):
        assert kennung not in bund
        geschrieben.append(kennung)
        bund[kennung] = k
        return True
    monkeypatch.setattr(geheim, "_bund_lesen", lesen)
    monkeypatch.setattr(geheim, "_bund_schreiben", schreiben)
    w = geheim.schuetzen("im-bund")
    if os.name != "posix":
        assert w.startswith("dpapi:") and geschrieben == []
        return
    kennung = geschrieben[0]
    assert w.startswith(f"bund:{kennung}.") and len(geschrieben) == 1
    assert (eigener_ordner / geheim.ART_DATEI).read_bytes() == f"bund:{kennung}".encode("ascii")
    assert not (eigener_ordner / geheim.SCHLUESSEL_DATEI).exists()
    import shutil
    shutil.rmtree(eigener_ordner)
    geheim.vergessen()
    assert geheim.lesen(w) == "im-bund"
    eigener_ordner.mkdir(mode=0o700)
    (eigener_ordner / geheim.ART_DATEI).write_bytes(f"bund:{kennung}".encode("ascii"))
    os.chmod(eigener_ordner / geheim.ART_DATEI, 0o600)
    bund["gesperrt"] = True
    geheim.vergessen()
    for ruf in (lambda: geheim.schuetzen("neu"), lambda: geheim.lesen(w)):
        with pytest.raises(geheim.GeheimError) as e:
            ruf()
        assert e.value.code == "GEHEIM_GESPERRT"
    assert len(geschrieben) == 1 and not (eigener_ordner / geheim.SCHLUESSEL_DATEI).exists()
    bund["gesperrt"] = False
    geheim.vergessen()
    assert geheim.lesen(w) == "im-bund"


def test_klar_gilt_nur_ohne_jeden_schutz():
    assert geheim.moeglich()
    assert not geheim.geschuetzt("klar:abc") and geheim.lesen("klar:abc") == "abc"
