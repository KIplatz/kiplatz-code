import os

_NODE_AGENT_DIR = os.path.dirname(os.path.abspath(SPEC))
_REPO_ROOT = os.path.dirname(_NODE_AGENT_DIR)
_PROTOCOL_DIR = os.path.join(_REPO_ROOT, "protocol")
_UPDATE_DIR = os.path.join(_REPO_ROOT, "update")

_datas = [
    (os.path.join(_NODE_AGENT_DIR, "registration.py"), "node-agent"),
    (os.path.join(_PROTOCOL_DIR, "registration.py"), "protocol"),
]

_hiddenimports = ["secrets"]

a = Analysis(
    ['setup_app.py'],
    pathex=[_PROTOCOL_DIR, _UPDATE_DIR],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CommunityAINetwork-NodeSetup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
