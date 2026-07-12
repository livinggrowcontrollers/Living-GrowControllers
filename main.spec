# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

datas = [
    ("assets", "assets"),
    ("dashboard_gui/assets", "dashboard_gui/assets"),
    ("data", "data"),
]
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
    runtime_hooks=["rthook_kivy_path.py"],
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
    console=True,
)

# -------------------------
# COLLECT
# -------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LGS",
)