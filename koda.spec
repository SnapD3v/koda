# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

textual_datas, textual_bins, textual_hiddenimports = collect_all("textual")

a = Analysis(
    ["koda/__main__.py"],
    pathex=["."],
    binaries=textual_bins,
    datas=[
        ("koda/tui/app.tcss", "koda/tui"),
        *textual_datas,
    ],
    hiddenimports=[
        "tomllib",
        "tomli_w",
        "koda.tui.screens.home",
        "koda.tui.screens.search",
        "koda.tui.screens.detail",
        "koda.tui.screens.library",
        "koda.tui.screens.download",
        "koda.tui.screens.settings",
        "koda.tui.screens.version",
        "koda.tui.screens.folder_pick",
        *textual_hiddenimports,
    ],
    hookspath=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="koda",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
