# FONT VISUALIZER – FINDE JEDES ICON VISUELL
# Läuft standalone. Öffnet ein Grid mit ALLEN Icons aus der TTF.
# Tippe auf ein Icon → Unicode wird angezeigt + in Zwischenablage kopiert.

import os
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.clipboard import Clipboard
from fontTools.ttLib import TTFont

FONT_PATH = "fa-solid-900.ttf"   # <-- hier dein Font eintragen

class FontViewer(App):
    def build(self):
        LabelBase.register(name="FA", fn_regular=FONT_PATH)

        font = TTFont(FONT_PATH)
        cmap = font["cmap"].getBestCmap()

        root = ScrollView()
        grid = GridLayout(cols=6, padding=10, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for code, glyph in cmap.items():
            u = f"\\u{code:04x}"

            box = BoxLayout(orientation="vertical", size_hint_y=None, height=140)

            lbl = Label(
                text=f"[font=FA]{u}[/font]",
                markup=True,
                font_size=48,
                size_hint=(1, 0.8),
                color=(1,1,1,1),
                halign="center",
                valign="middle",
            )

            lbl_unicode = Label(
                text=u,
                font_size=14,
                size_hint=(1, 0.2),
                color=(0.7,0.7,0.7,1),
            )

            def make_callback(u_copy):
                def cb(*_):
                    Clipboard.copy(u_copy)
                    print("COPIED:", u_copy)
                return cb

            lbl.bind(on_touch_down=lambda inst, t, u=u: inst.collide_point(*t.pos) and Clipboard.copy(u))
            box.add_widget(lbl)
            box.add_widget(lbl_unicode)
            grid.add_widget(box)

        root.add_widget(grid)
        return root

if __name__ == "__main__":
    FontViewer().run()
