# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass

SERVER = "https://kiplatz.at:8444"
MODELLE_WEG = "/modelle/"
ORDNER = "modelle"


@dataclass(frozen=True)
class Paket:

    kennung: str
    name: str
    datei: str
    url: str
    sha256: str
    groesse: int
    herkunft: str = ""
    unterschrift: str = ""

    @property
    def stuecke_sha256(self) -> str:
        return STUECKLISTEN.get(self.datei, "")

    @property
    def quellen(self) -> tuple[str, ...]:
        return (self.url,) if self.url else ()


@dataclass(frozen=True)
class Modell(Paket):
    braucht_mib: int = 0
    kontext: int = 0
    kv_mib: int = 0
    bilder: "Paket | None" = None


def _unser(datei: str) -> str:
    return SERVER + MODELLE_WEG + datei


_HF = "https://huggingface.co/{konto}/{repo}/resolve/main/{datei}"


def _mmproj(kennung: str, groesse: int, sha256: str) -> Paket:
    datei = f"Ministral-3-{kennung}-Instruct-2512-BF16-mmproj.gguf"
    return Paket(kennung=f"{kennung}-bilder", name=f"Bild-Zusatz {kennung}", datei=datei, url=_unser(datei),
                 herkunft=_HF.format(konto="mistralai", repo=f"Ministral-3-{kennung}-Instruct-2512-GGUF", datei=datei), sha256=sha256, groesse=groesse)


LAUFZEIT = Paket(
    kennung="ollama-0.34.4-vulkan",
    name="KI-Laufzeit (llama.cpp aus Ollama 0.34.4, Vulkan, unterschrieben)",
    datei="kiplatz-laufzeit-ollama-0.34.4-vulkan-x64.zip",
    url=_unser("kiplatz-laufzeit-ollama-0.34.4-vulkan-x64.zip"),
    sha256="af10be9c6799c87ab6990c8bbd621fa9176f7657fd770e52727c3e9cf977d576",
    groesse=28047755,
    unterschrift="Ollama Inc.",
)

LAUFZEIT_ALT = Paket(
    kennung="b11003",
    name="llama.cpp b11003 (Vulkan)",
    datei="llama-b11003-bin-win-vulkan-x64.zip",
    url=_unser("llama-b11003-bin-win-vulkan-x64.zip"),
    herkunft="https://github.com/ggml-org/llama.cpp/releases/download/b11003/llama-b11003-bin-win-vulkan-x64.zip",
    sha256="017f589071d26385304b6426b1426e45efce3e1cba66b25d3d5de9d4f56dd8fa",
    groesse=31708851,
)

_LLAMA = "https://github.com/ggml-org/llama.cpp/releases/download/b11003/"


def _llama(plattform: str, datei: str, sha256: str, groesse: int, name: str) -> Paket:
    return Paket(kennung=f"b11003-{plattform}", name=f"llama.cpp b11003 ({name})", datei=datei, url=_unser(datei), herkunft=_LLAMA + datei,
                 sha256=sha256, groesse=groesse)


LAUFZEITEN_HELFER: dict[str, Paket] = {
    "linux-x64-vulkan": _llama("linux-x64-vulkan", "llama-b11003-bin-ubuntu-vulkan-x64.tar.gz",
                               "856325d6e5a2f5fa54179065f3682d896c5720edda7c75fd941ff75b71fe3734", 30218750, "Linux x64, Vulkan"),
    "linux-x64": _llama("linux-x64", "llama-b11003-bin-ubuntu-x64.tar.gz",
                        "5a9558b3aa1add278d82fbebb9dd2f56448c29221e46cd8b1d93723c5b4435ef", 16855523, "Linux x64, Prozessor"),
    "linux-arm64-vulkan": _llama("linux-arm64-vulkan", "llama-b11003-bin-ubuntu-vulkan-arm64.tar.gz",
                                 "6f29395af963bdcfc86cf8cececa73305ca479922882998cb1b02e9fccaafb93", 24247006, "Linux arm64, Vulkan"),
    "linux-arm64": _llama("linux-arm64", "llama-b11003-bin-ubuntu-arm64.tar.gz",
                          "2630c0f5815a81766653c889ee6e70af166f63326f1f8a10167b8d9b6fd1de24", 13476945, "Linux arm64, Prozessor"),
    "macos-arm64": _llama("macos-arm64", "llama-b11003-bin-macos-arm64.tar.gz",
                          "b30339f4186a5a79654fbee087bd7f62964aa727c15f26481b2cc56610b3f768", 11155963, "macOS Apple-Chip, Metal"),
    "macos-x64": _llama("macos-x64", "llama-b11003-bin-macos-x64.tar.gz",
                        "7f44154b08f7b229368db76df57c8dd3f30d6f9d8856cf5f3de8a6fbc20d4f60", 11201898, "macOS Intel"),
}


def laufzeit_hier(system: str | None = None, cpu: str | None = None, vulkan: bool | None = None) -> Paket:
    import platform as _pf
    system = (system or _pf.system()).lower()
    if system == "windows":
        return LAUFZEIT
    cpu = cpu or ("arm64" if _pf.machine().lower() in ("arm64", "aarch64") else "x64")
    if system == "darwin":
        return LAUFZEITEN_HELFER[f"macos-{cpu}"]
    if vulkan is None:
        import ctypes.util
        vulkan = bool(ctypes.util.find_library("vulkan"))
    return LAUFZEITEN_HELFER[f"linux-{cpu}" + ("-vulkan" if vulkan else "")]


MODELLE: dict[str, Modell] = {
    "3B": Modell(
        kennung="3B", name="Ministral 3 3B", datei="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf",
        url=_unser("Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"),
        herkunft=_HF.format(konto="mistralai", repo="Ministral-3-3B-Instruct-2512-GGUF", datei="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"),
        sha256="9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8", groesse=2147023008,
        braucht_mib=2800, kontext=4096, kv_mib=450,
        bilder=_mmproj("3B", 841501856, "70ca26e41ecea9da997e2887462ad68b848fbf64da011ff4107bbe7353519ee0"),
    ),
    "8B": Modell(
        kennung="8B", name="Ministral 3 8B", datei="Ministral-3-8B-Instruct-2512-Q4_K_M.gguf",
        url=_unser("Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"),
        herkunft=_HF.format(konto="mistralai", repo="Ministral-3-8B-Instruct-2512-GGUF", datei="Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"),
        sha256="33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761", groesse=5198911904,
        braucht_mib=5900, kontext=4096, kv_mib=600,
        bilder=_mmproj("8B", 858283168, "e799380f596d152ff4026a72d409ecc89c96cd437676804bc3f2ab3bd6b486ec"),
    ),
    "14B": Modell(
        kennung="14B", name="Ministral 3 14B", datei="Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
        url=_unser("Ministral-3-14B-Instruct-2512-Q4_K_M.gguf"),
        herkunft=_HF.format(konto="mistralai", repo="Ministral-3-14B-Instruct-2512-GGUF", datei="Ministral-3-14B-Instruct-2512-Q4_K_M.gguf"),
        sha256="824e0f3373e69b84f2cae46fdcb9bd1ebc6ab3bfc7acc125d818b7b8178cc613", groesse=8239593024,
        braucht_mib=9000, kontext=8192, kv_mib=1350,
        bilder=_mmproj("14B", 879258784, "ab7616148b7081030fd38e410c9213ce8346a8b0588291c8ca279058e78cfae7"),
    ),
}
MODELL_REIHENFOLGE = ("14B", "8B", "3B")

EMBEDDING = Modell(
    kennung="qwen3-embedding-0.6b-q8_0", name="Bedeutungs-Modell (0,6B)", datei="Qwen3-Embedding-0.6B-Q8_0.gguf",
    url=_unser("Qwen3-Embedding-0.6B-Q8_0.gguf"),
    herkunft=_HF.format(konto="Qwen", repo="Qwen3-Embedding-0.6B-GGUF", datei="Qwen3-Embedding-0.6B-Q8_0.gguf"),
    sha256="06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439", groesse=639150592,
    braucht_mib=2400, kontext=2048,
)
EMBEDDING_DIMENSION = 1024

BEWERTUNG = Modell(
    kennung="qwen3-reranker-0.6b-q8_0", name="Bewertungs-Modell (0,6B)", datei="qwen3-reranker-0.6b-q8_0.gguf",
    url=_unser("qwen3-reranker-0.6b-q8_0.gguf"),
    herkunft=_HF.format(konto="ggml-org", repo="Qwen3-Reranker-0.6B-Q8_0-GGUF", datei="qwen3-reranker-0.6b-q8_0.gguf"),
    sha256="22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48", groesse=639153184,
    braucht_mib=1900, kontext=4096,
)

SPRACHE_LAUFZEIT = Paket(
    kennung="whisper-b5130",
    name="whisper.cpp b5130 (Prozessor)",
    datei="whisper-b5130-bin-x64.zip",
    url=_unser("whisper-b5130-bin-x64.zip"),
    herkunft="https://github.com/ggml-org/whisper.cpp/releases/download/b5130/whisper-bin-x64.zip",
    sha256="f9ec6c52a2e949b62ab51fa21d0d497958f9e41c3010c157c4e42932d5316f3c",
    groesse=8573270,
)
SPRACHE_MODELL = Paket(
    kennung="whisper-small-q5_1",
    name="Sprach-Modell (whisper small)",
    datei="ggml-small-q5_1.bin",
    url=_unser("ggml-small-q5_1.bin"),
    herkunft=_HF.format(konto="ggerganov", repo="whisper.cpp", datei="ggml-small-q5_1.bin"),
    sha256="ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
    groesse=190085487,
)

HOEREN = Modell(
    kennung="qwen3-asr-0.6b-q8_0", name="Hör-Modell (0,6B)", datei="Qwen3-ASR-0.6B-Q8_0.gguf",
    url=_unser("Qwen3-ASR-0.6B-Q8_0.gguf"),
    herkunft=_HF.format(konto="ggml-org", repo="Qwen3-ASR-0.6B-GGUF", datei="Qwen3-ASR-0.6B-Q8_0.gguf"),
    sha256="bca259818b50ca7c4c05e9bdb35a5dc04fa039653a6d6f3f0f331f96f6aa1971", groesse=804749248,
    braucht_mib=1500, kontext=4096,
    bilder=Paket(kennung="qwen3-asr-0.6b-mmproj", name="Hör-Zusatz (0,6B)", datei="mmproj-Qwen3-ASR-0.6B-Q8_0.gguf",
                 url=_unser("mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"),
                 herkunft=_HF.format(konto="ggml-org", repo="Qwen3-ASR-0.6B-GGUF", datei="mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"),
                 sha256="41a342b5e4c514e968cb756de6cd1b7be39eff43c44c57a2ef5fc6522e36603d", groesse=214392480),
)

WORTLISTE_DE = Paket(kennung="wortliste-de-20261018", name="Wortliste Deutsch", datei="wortliste-de-20261018.sqlite.gz",
                     url=_unser("wortliste-de-20261018.sqlite.gz"),
                     sha256="0f5906e1f14f6bb718245f928bb6c5e7b263554c7be1c5cfb424076cc31fb9c0", groesse=57279696)
WORTLISTE_EN = Paket(kennung="wortliste-en-20261018", name="Wortliste Englisch", datei="wortliste-en-20261018.sqlite.gz",
                     url=_unser("wortliste-en-20261018.sqlite.gz"),
                     sha256="6e08dfb006f42cf9fecc6fd72443b90f9f9343be36f66e6f6a0932a82db990d0", groesse=5478322)
WORTLISTEN: dict[str, Paket] = {"de": WORTLISTE_DE, "en": WORTLISTE_EN}

ALLE: tuple[Paket, ...] = (LAUFZEIT, LAUFZEIT_ALT, *LAUFZEITEN_HELFER.values(), *MODELLE.values(), *(m.bilder for m in MODELLE.values() if m.bilder), EMBEDDING, BEWERTUNG, SPRACHE_LAUFZEIT,
                           SPRACHE_MODELL, HOEREN, HOEREN.bilder, *WORTLISTEN.values())
NACH_DATEI: dict[str, Paket] = {p.datei: p for p in ALLE}

STUECKLISTEN: dict[str, str] = {
    "kiplatz-laufzeit-ollama-0.34.4-vulkan-x64.zip": "f5978134366bc52ed14cc36758694eee0bd624b2c65beb62c0cebbf95dd539d2",
    "llama-b11003-bin-win-vulkan-x64.zip": "8062dfa011f3839198408dc06b6e3ac0ba1ade7b18ea08df9445bc3c56b3bac3",
    "Ministral-3-3B-Instruct-2512-Q4_K_M.gguf": "085d8f9a6b6e668fe70de8d43c5835e43751579bc7122eca0831e269f93df5bc",
    "Ministral-3-8B-Instruct-2512-Q4_K_M.gguf": "51aa6fc1d0dca8a5ac3bc63be3b74813d84dda845948233a74fbee676d0f4ef5",
    "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf": "524313f44e07ff20637cd406395b18251edd099fb0fade7bc59e92d2e0252539",
    "Ministral-3-3B-Instruct-2512-BF16-mmproj.gguf": "ce28671291d59d508fbfab64195d6c2077c9264228d2211c36d29c938210bd4f",
    "Ministral-3-8B-Instruct-2512-BF16-mmproj.gguf": "2f67e4225545252127dd07d6b663da02f3668807e22ae12e716520fd0d2a095e",
    "Ministral-3-14B-Instruct-2512-BF16-mmproj.gguf": "dee4e85a74ca843b8f90dddbd4652398e26f40961e59f95a28360d9a80fe440e",
    "Qwen3-Embedding-0.6B-Q8_0.gguf": "43a4064ca25c11bcce8257ef316e902fcccbc9d2406cbfa6de491351a3b028ae",
    "qwen3-reranker-0.6b-q8_0.gguf": "5dc84fb145f4641297f1b26e16d5137437860387a0ad38296f5a3faddff9f008",
    "whisper-b5130-bin-x64.zip": "2e89bedc2cba75a3264f253837694547ba039ce30f9534b3ae4fc9396b31b6f4",
    "ggml-small-q5_1.bin": "39c6d5335faaa4114229d7c690d2b1193eae88be5a1f21f6fbd34dec5001bfb5",
    "Qwen3-ASR-0.6B-Q8_0.gguf": "bba09999268c3ed78c70d545f117695a4b09f338ae74cbe33bd35c710b349363",
    "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf": "f542db65c955965a2fc83ddd1785f95c82d7fd284dbfda1a4d974f1983aefc62",
}

_FASSUNG = re.compile(r"-kiplatz-(\d{4}-\d{2}-\d{2})(?:-(\d+))?-", re.I)


def fassung(datei: str) -> str:
    m = _FASSUNG.search(str(datei or ""))
    if not m:
        return ""
    return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")


__all__ = ["SERVER", "MODELLE_WEG", "ORDNER", "Paket", "Modell", "LAUFZEIT", "LAUFZEIT_ALT", "MODELLE", "MODELL_REIHENFOLGE", "EMBEDDING", "EMBEDDING_DIMENSION",
           "BEWERTUNG", "SPRACHE_LAUFZEIT", "SPRACHE_MODELL", "HOEREN", "WORTLISTEN", "ALLE", "NACH_DATEI", "fassung"]
