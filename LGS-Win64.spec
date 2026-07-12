# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# -------------------------------------------------
# DATEN
# -------------------------------------------------

datas = [
    ("assets", "assets"),
    ("dashboard_gui/assets", "dashboard_gui/assets"),
    ("data", "data"),
]

# Kivy-Daten (Fonts, Shader usw.)
datas += collect_data_files("kivy")

# -------------------------------------------------
# HIDDEN IMPORTS
# -------------------------------------------------

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
    "kivy.core.window.window_sdl2",

    "kivy.core.text",
    "kivy.core.text.text_sdl2",

    "kivy.core.image",
    "kivy.core.image.img_imageio",

    "kivy.graphics",
    "kivy.properties",

    "kivy_garden.graph",
    "kivy_garden.graph.graph",
    "bleak",
    "asyncio",
    "threading",

    # Zeroconf / mDNS
    "zeroconf",
    "zeroconf._services",
    "zeroconf._dns",
    "zeroconf._cache",
    "zeroconf._listener",
    "zeroconf._protocol",
]

# -------------------------------------------------
# EXCLUDES
# -------------------------------------------------

excludes = [
    "tkinter",
    "lib2to3",
]

# -------------------------------------------------
# ANALYSIS
# -------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=["rthook_kivy_path.py"],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# -------------------------------------------------
# PYZ
# -------------------------------------------------

pyz = PYZ(
    a.pure,
    a.zipped_data,
)

# -------------------------------------------------
# EXE
# -------------------------------------------------

# -------------------------------------------------
# EXE (Windows)
# -------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],                 # Keine Binaries/Datas direkt in die EXE stopfen!
    exclude_binaries=True, # Zwingt PyInstaller zu einer stabilen Ordnerstruktur
    name="LivingGrowControllers_x64_win",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/logo.ico",
)

# -------------------------------------------------
# COLLECT (Sorgt dafür, dass "./data" persistent bleibt)
# -------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="LivingGrowControllers_x64_win",
)