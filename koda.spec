# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

textual_datas, textual_bins, textual_hiddenimports = collect_all("textual")

# Bundle bundled/mpv/ if the directory exists (Windows portable with mpv)
_mpv_dir = Path("bundled/mpv")
_extra_datas = []
if _mpv_dir.is_dir():
    _extra_datas.append(("bundled/mpv", "mpv"))

# Use custom icon if present in assets/ (Windows only — .ico format)
import sys as _sys
_icon_file = Path("assets/koda_icon.ico") if _sys.platform == "win32" else None
_icon = str(_icon_file) if (_icon_file and _icon_file.exists()) else None

a = Analysis(
    ["koda/__main__.py"],
    pathex=["."],
    binaries=textual_bins,
    datas=[
        ("koda/tui/app.tcss", "koda/tui"),
        *textual_datas,
        *_extra_datas,
    ],
    hiddenimports=[
        "tomllib",
        "tomli_w",
        "plyer",
        "plyer.platforms",
        "plyer.platforms.win.notification",
        "plyer.platforms.macosx.notification",
        "plyer.platforms.linux.notification",
        "koda.tui.screens.home",
        "koda.tui.screens.search",
        "koda.tui.screens.detail",
        "koda.tui.screens.library",
        "koda.tui.screens.download",
        "koda.tui.screens.settings",
        "koda.tui.screens.version",
        "koda.tui.screens.folder_pick",
        "koda.tui.screens.keys_help",
        "koda.tui.screens.resume_modal",
        "koda.tui.widgets",
        "koda.tui.widgets.poster",
        "koda.updater",
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
    icon=_icon,
)
