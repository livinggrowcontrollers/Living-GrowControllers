#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from platform_utils import is_android
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


def get_data_root():
    """
    Pfad-Logik UNVERÄNDERT lassen!
    Desktop:  <project_root>/data
    Android:  <files>/app/data
    """
    if is_android():
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        files = ctx.getFilesDir().getAbsolutePath()
        return os.path.join(files, "app", "data")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(base, "..", "..", "..", "data"))


class CSVViewerFileBrowser(FloatLayout):
    """
    Dark-Pro Popup-Filebrowser für CSV/JSON:
    - halbtransparentes Overlay
    - zentrierte Card
    - Dark-Pro-Buttons
    - Pfade & Logik wie vorher
    """

    def __init__(self, on_select, **kw):
        super().__init__(**kw)
        self.on_select = on_select

        # ----------------------------------------------------
        # HINTERGRUND: dunkles Overlay
        # ----------------------------------------------------
        with self.canvas.before:
            Color(0, 0, 0, 0.62) # halbtransparentes Schwarz
            self._bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_bg, pos=self._update_bg)

        # ----------------------------------------------------
        # ZENTRIERTE CARD
        # ----------------------------------------------------
        root = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp_scaled(360), dp_scaled(440)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            spacing=dp_scaled(10),
            padding=dp_scaled(10),
        )

        with root.canvas.before:
            Color(0.08, 0.08, 0.12, 1)  # Card-Hintergrund
            card_bg = RoundedRectangle(
                radius=[dp_scaled(8)] * 4,
                size=root.size,
                pos=root.pos,
            )
        root._card_bg = card_bg
        root.bind(size=self._update_card_bg, pos=self._update_card_bg)

        self.add_widget(root)

        # ----------------------------------------------------
        # TITLE / HEADER
        # ----------------------------------------------------
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(32),
            spacing=dp_scaled(8),
        )

        btn_title = Button(
            text="CSV / JSON auswählen",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=(0.95, 0.95, 0.98, 1),
            font_size=sp_scaled(16),
            halign="left",
        )
        header.add_widget(btn_title)
        root.add_widget(header)

        # ----------------------------------------------------
        # SCROLLBEREICH MIT DATEIEN
        # ----------------------------------------------------
        scroll = ScrollView(size_hint=(1, 1))
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp_scaled(5),
            padding=[0, 0, 0, dp_scaled(4)],
        )
        box.bind(minimum_height=lambda inst, h: setattr(box, "height", h))
        scroll.add_widget(box)
        root.add_widget(scroll)

        # Liste der Dateien im data/ Ordner
        base = get_data_root()

        if os.path.exists(base):
            for name in sorted(os.listdir(base)):
                if name.endswith(".csv") or name.endswith(".json"):
                    btn = Button(
                        text=name,
                        size_hint_y=None,
                        height=dp_scaled(40),
                        background_down="",
                        background_color=(0.16, 0.16, 0.22, 1),  # Dark-Pro List-Item
                        color=(0.95, 0.95, 0.98, 1),
                        font_size=sp_scaled(16),
                    )
                    btn.bind(on_release=lambda _, n=name: self._choose(base, n))
                    box.add_widget(btn)
        else:
            # Falls data/-Ordner fehlt
            btn = Button(
                text=f"data/ Ordner nicht gefunden:\n{base}",
                size_hint_y=None,
                height=dp_scaled(80),
                background_down="",
                background_color=(0.25, 0.16, 0.16, 1),
                color=(0.98, 0.90, 0.90, 1),
                font_size=sp_scaled(16),
            )
            box.add_widget(btn)

        # ----------------------------------------------------
        # CANCEL BUTTON
        # ----------------------------------------------------
        btn_close = Button(
            text="Abbrechen",
            size_hint_y=None,
            height=dp_scaled(40),
            background_down="",
            background_color=(0.45, 0.15, 0.15, 1),  # Dark-Pro Stop-Farbe
            color=(0.98, 0.95, 0.95, 1),
            font_size=sp_scaled(16),
        )
        btn_close.bind(on_release=lambda *_: self._close())
        root.add_widget(btn_close)

    # --------------------------------------------------------
    #  HINTERGRUND-ANPASSUNG
    # --------------------------------------------------------
    def _update_bg(self, *_):
        if self._bg_rect is not None:
            self._bg_rect.size = self.size
            self._bg_rect.pos = self.pos

    def _update_card_bg(self, inst, *_):
        if hasattr(inst, "_card_bg") and inst._card_bg is not None:
            inst._card_bg.size = inst.size
            inst._card_bg.pos = inst.pos

    # --------------------------------------------------------
    #  DATEI AUSWÄHLEN
    # --------------------------------------------------------
    def _choose(self, base, name):
        self.on_select(os.path.join(base, name))
        self._close()

    # --------------------------------------------------------
    #  POPUP SCHLIESSEN
    # --------------------------------------------------------
    def _close(self):
        if self.parent:
            self.parent.remove_widget(self)
