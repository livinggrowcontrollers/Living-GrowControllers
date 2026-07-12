# FONT VISUALIZER – VISUELLES ICON BROWSING FÜR FONT AWESOME
# Lege diese Datei in denselben Ordner wie deine TTF (fa-solid-900.ttf)
# dann einfach python3 font_viewer.py starten.

import os
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.clipboard import Clipboard
from fontTools.ttLib import TTFont

# HIER: Name der Font-Datei im gleichen Ordner
FONT_FILE = "fa-solid-900.ttf"

class FontViewer(App):
    def build(self):

        # ---------------------------------------------
        # FONT REGISTRIEREN (WICHTIG!)
        # ---------------------------------------------
        font_path = os.path.join(os.path.dirname(__file__), FONT_FILE)
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")

        # Font für Kivy registrieren
        LabelBase.register(
            name="FA",
            fn_regular=font_path
        )

        # ---------------------------------------------
        # FONT LADEN + CMAP EXTRAHIEREN
        # ---------------------------------------------
        font = TTFont(font_path)
        cmap = font["cmap"].getBestCmap()   # unicode → glyphname

        # ---------------------------------------------
        # UI SETUP
        # ---------------------------------------------
        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(
            cols=6, spacing=12, padding=12,
            size_hint_y=None
        )
        grid.bind(minimum_height=grid.setter("height"))

        # ---------------------------------------------
        # ALLE ICONS ANZEIGEN
        # ---------------------------------------------
        for unicode_val, glyph_name in cmap.items():

            # echtes Unicode Zeichen
            char = chr(unicode_val)

            box = BoxLayout(orientation="vertical", size_hint_y=None, height=140)

            icon = Label(
                text=f"[font=FA]{char}[/font]",
                markup=True,
                font_size=46,
                size_hint=(1, 0.75),
                halign="center",
                valign="middle",
                color=(1, 1, 1, 1)
            )

            lbl_code = Label(
                text=f"U+{unicode_val:04X}",
                font_size=14,
                color=(0.7, 0.7, 0.7, 1),
                size_hint=(1, 0.25)
            )

            # erlaubt: Tippen → Unicode kopieren
            def bind_copy(label, text_to_copy):
                def callback(instance, touch):
                    if instance.collide_point(*touch.pos):
                        Clipboard.copy(text_to_copy)
                        print("COPIED:", text_to_copy)
                label.bind(on_touch_down=callback)

            bind_copy(icon, char)

            box.add_widget(icon)
            box.add_widget(lbl_code)
            grid.add_widget(box)

        scroll.add_widget(grid)
        return scroll


if __name__ == "__main__":
    FontViewer().run()
