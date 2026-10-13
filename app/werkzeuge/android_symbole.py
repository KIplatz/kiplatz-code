# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HIER = Path(__file__).resolve().parent
REPO = HIER.parent.parent
QUELLE = REPO / "website" / "marke" / "quelle" / "symbol-transparent.png"
RES = REPO / "app" / "android" / "app" / "src" / "main" / "res"
DICHTEN = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
SYMBOL_DP_VORDERGRUND = 62
SYMBOL_ANTEIL_ALT = 0.78
SYMBOL_ANTEIL_START = 0.28
WEISS = (255, 255, 255, 255)


def _symbol() -> Image.Image:
    t = Image.open(QUELLE).convert("RGBA")
    l, o, r, u = t.getchannel("A").getbbox()
    mx, my, seite = (l + r) / 2, (o + u) / 2, max(r - l, u - o)
    return t.crop((round(mx - seite / 2), round(my - seite / 2), round(mx + seite / 2), round(my + seite / 2)))


def _mittig(flaeche: Image.Image, symbol: Image.Image, groesse: int) -> Image.Image:
    s = symbol.resize((groesse, groesse), Image.LANCZOS)
    flaeche.alpha_composite(s, ((flaeche.width - groesse) // 2, (flaeche.height - groesse) // 2))
    return flaeche


def erzeugen() -> list[Path]:
    sym = _symbol()
    geschrieben: list[Path] = []
    for name, f in DICHTEN.items():
        ordner = RES / f"mipmap-{name}"
        v = round(108 * f)
        vorder = _mittig(Image.new("RGBA", (v, v), (0, 0, 0, 0)), sym, round(SYMBOL_DP_VORDERGRUND * f))
        a = round(48 * f)
        eckig = Image.new("RGBA", (a, a), (0, 0, 0, 0))
        ImageDraw.Draw(eckig).rounded_rectangle((0, 0, a - 1, a - 1), radius=round(a * 0.18), fill=WEISS)
        rund = Image.new("RGBA", (a, a), (0, 0, 0, 0))
        ImageDraw.Draw(rund).ellipse((0, 0, a - 1, a - 1), fill=WEISS)
        for datei, bild in (("ic_launcher_foreground.png", vorder),
                            ("ic_launcher.png", _mittig(eckig, sym, round(a * SYMBOL_ANTEIL_ALT))),
                            ("ic_launcher_round.png", _mittig(rund, sym, round(a * SYMBOL_ANTEIL_ALT)))):
            ziel = ordner / datei
            bild.save(ziel, optimize=True)
            geschrieben.append(ziel)
    for ziel in sorted(RES.glob("drawable*/splash.png")):
        b, h = Image.open(ziel).size
        bild = _mittig(Image.new("RGBA", (b, h), WEISS), sym, round(min(b, h) * SYMBOL_ANTEIL_START))
        bild.convert("RGB").save(ziel, optimize=True)
        geschrieben.append(ziel)
    return geschrieben


if __name__ == "__main__":
    for p in erzeugen():
        print(p.relative_to(REPO))
