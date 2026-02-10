# ProductAddsManager.spec
# PyInstaller spec file — run with: pyinstaller ProductAddsManager.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['MAIN.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include the templates folder if it exists at build time
        ('app/templates', 'app/templates'),
    ],
    hiddenimports=[
        # FreeSimpleGUI
        'FreeSimpleGUI',
        # pandas internals commonly missed by the hook
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.timestamps',
        'pandas._libs.tslibs.offsets',
        'pandas._libs.skiplist',
        'pandas._libs.hashtable',
        'pandas._libs.index',
        'pandas._libs.lib',
        'pandas._libs.missing',
        'pandas._libs.reduction',
        'pandas._libs.writers',
        # openpyxl
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.styles.fonts',
        'openpyxl.styles.fills',
        'openpyxl.cell._writer',
        'openpyxl.workbook',
        'openpyxl.reader.excel',
        # numpy (pulled by pandas)
        'numpy',
        'numpy.core._dtype_ctypes',
        # stdlib — sqlite3 sometimes needs explicit inclusion
        'sqlite3',
        '_sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim things we definitely don't use
        'matplotlib',
        'scipy',
        'PIL',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProductAddsManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # compress binaries if UPX is on PATH; set False if it causes AV flags
    console=False,      # no console window — GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='app/icon.ico',  # uncomment and point to a .ico file if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ProductAddsManager',   # output folder name under dist/
)
