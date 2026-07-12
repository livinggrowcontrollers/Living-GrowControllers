# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# Kivy-Abhängigkeiten für Windows und Linux importieren
try:
    from kivy_deps import sdl2, glew
except ImportError:
    sdl2 = None
    glew = None

block_cipher = None

# Datenverzeichnisse definieren
datas = [
    ("assets", "assets"),
    ("dashboard_gui/assets", "dashboard_gui/assets"),
    ("data", "data"),
]

# Automatisch Kivy-interne Daten sammeln
datas += collect_data_files('kivy')



# -------------------------
# HIDDEN IMPORTS
# -------------------------
hiddenimports = [
    "kivy",
    "kivy.app",
    "kivy.uix.label",
    "kivy.uix.button",
    "kivy.uix.widget",
    "kivy.uix.image",
    "kivy.uix.boxlayout",
    "kivy.uix.screenmanager",
    "kivy.core.window",
    "kivy.core.text",
    "kivy.core.image",
    "kivy.core.image.img_imageio",
    "kivy.graphics",
    "kivy.properties",
    "kivy_garden.graph",
    "kivy_garden.graph.graph",
    "asyncio",
    "threading",
]

# -------------------------
# ANALYSIS
# -------------------------
a = Analysis(
    ["main.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],  # Leer lassen, damit der GitHub-Runner nicht abstürzt
    excludes=[],
    noarchive=False,
    optimize=0,
)

# -------------------------
# PYZ
# -------------------------
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# -------------------------
# EXE
# -------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LGS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

# -------------------------
# COLLECT
# -------------------------
coll_binaries = a.binaries
coll_datas = a.datas

# Wenn wir auf Windows oder Linux bauen, fügen wir die SDL2/GLEW Binaries hinzu
if sdl2 and glew:
    coll_binaries += sdl2.dep_bins + glew.dep_bins

coll = COLLECT(
    exe,
    coll_binaries,
    coll_datas,
    strip=False,
    upx=False,
    name="LGS",
)


# -------------------------
# macOS BUNDLE (INFO.PLIST FOR NATIVE ABOUT)
# -------------------------
app = BUNDLE(
    coll,
    name="LivingGrowControllers.app",
    icon="assets/logo.icns",
    bundle_identifier="com.lgs.dashboard",
    info_plist={
        'CFBundleName': 'LGS',
        'CFBundleDisplayName': 'LivingGrowControllers Dashboard',
        'CFBundleGetInfoString': "LGS Analytics Dashboard",
        'CFBundleIdentifier': "com.lgs.dashboard",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHighResolutionCapable': 'True',
        'NSHumanReadableCopyright': "Copyright © 2026 LGS. Alle Rechte vorbehalten."
    }
)