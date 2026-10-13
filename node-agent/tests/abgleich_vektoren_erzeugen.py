# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric import ec

import abgleich_krypto as ak

ZIEL = Path(__file__).resolve().parents[2] / "app" / "tests" / "abgleich-vektoren.json"


def _jwk(p: ec.EllipticCurvePrivateKey) -> dict:
    n = p.private_numbers()
    f = lambda i: base64.urlsafe_b64encode(i.to_bytes(32, "big")).rstrip(b"=").decode()
    return {"kty": "EC", "crv": "P-256", "d": f(n.private_value), "x": f(n.public_numbers.x), "y": f(n.public_numbers.y), "ext": True}


def vektoren() -> dict:
    k = bytes(range(32))
    geraet = ec.derive_private_key(0x1F6F5B3F9A7E0000000000000000000000000000000000000000000000000001, ec.SECP256R1())
    wegwerf = ec.derive_private_key(0x35594F8FD3BD0000000000000000000000000000000000000000000000000002, ec.SECP256R1())
    iv = bytes(range(100, 112))
    bid = "0123456789abcdef0123456789abcdef"
    gespraech = {"id": bid, "titel": "Probe: Wetter in Gmunden", "angeheftet": False, "geaendert": 1790000000000,
                 "nachrichten": [{"rolle": "user", "text": "Wie wird das Wetter morgen?", "zeit": 1790000000000},
                                 {"rolle": "assistant", "text": "Sonnig, 18 Grad. Ümlaute: äöüß €", "zeit": 1790000001000}]}
    r_text = ak.wiederherstellung_zeigen(bytes(range(200, 215)))
    return {
        "hinweis": "Nur Testschlüssel für die Prüfungen; erzeugt von node-agent/tests/abgleich_vektoren_erzeugen.py",
        "kontoschluessel": ak.b64(k), "iv": ak.b64(iv), "id": bid, "gespraech": gespraech,
        "block": ak.block_verschluesseln(k, bid, gespraech, iv=iv),
        "geraet_jwk": _jwk(geraet), "geraet_oeffentlich": ak.oeffentlich(geraet), "pruefzahl": ak.pruefzahl(ak.oeffentlich(geraet)),
        "wegwerf_jwk": _jwk(wegwerf),
        "fach": ak.fach_packen(k, ak.oeffentlich(geraet), wegwerf=wegwerf, iv=iv),
        "wiederherstellung_text": r_text, "wiederherstellung": ak.wiederherstellung_packen(k, r_text, iv=iv),
        "siegel_kennung": "a1b2c3d4e5f6", "siegel": ak.siegel(k, "a1b2c3d4e5f6", ak.oeffentlich(geraet)),
    }


if __name__ == "__main__":
    ZIEL.write_text(json.dumps(vektoren(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", ZIEL)
