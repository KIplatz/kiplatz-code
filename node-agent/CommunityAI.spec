import os

_NODE_AGENT_DIR = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['app_web.py'],
    pathex=[_NODE_AGENT_DIR],
    binaries=[],
    datas=[(os.path.join(_NODE_AGENT_DIR, 'webapp', 'index.html'), 'webapp')],
    hiddenimports=["app_core", "app_install", "hardware_detect", "node_local_state", "ki_laufzeit", "credits", "gespraeche", "heimnetz", "wissen", "community", "pruefung",
                   "verteiler", "rechenarbeit", "bedeutung", "nachschauen", "hausordnung", "modell_katalog", "vermittlung", "win32crypt", "webview", "webview.menu", "clr"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CommunityAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
