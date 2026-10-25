# -*- mode: python ; coding: utf-8 -*-
#
# Build (see README.md's build section):
#   onedir (default): uv run pyinstaller "CSV Plot Maker.spec" --noconfirm --clean
#   onefile:          uv run pyinstaller "CSV Plot Maker.spec" --noconfirm --clean -- --onefile
import argparse
import datetime
import re
from pathlib import Path

_parser = argparse.ArgumentParser()
_parser.add_argument("--onefile", action="store_true")
_options = _parser.parse_args()

# Stamp today's date into BUILD_DATE so the built .exe's window title shows
# when it was built. __version__ stays manual.
_version_file = Path(SPECPATH) / "src" / "csv_plot_maker" / "_version.py"
_version_text = _version_file.read_text(encoding="utf-8")
_version_file.write_text(
    re.sub(r'^BUILD_DATE = ".*"$', f'BUILD_DATE = "{datetime.date.today().isoformat()}"', _version_text, flags=re.M),
    encoding="utf-8",
)


a = Analysis(
    ['src/csv_plot_maker/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

_exe_options = dict(
    name='CSV Plot Maker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if _options.onefile:
    # Single packed exe -> dist\CSV Plot Maker.exe
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        upx_exclude=[],
        runtime_tmpdir=None,
        **_exe_options,
    )
else:
    # onedir: exe + dependency folder -> dist\CSV Plot Maker\CSV Plot Maker.exe.
    # Default because it keeps PySide6 (LGPLv3) dynamically linked and
    # replaceable (see README.md).
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **_exe_options,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='CSV Plot Maker',
    )
