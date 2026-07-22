# dashboard_gui/overlays/push_message_overlay.py

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Line, RoundedRectangle
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE

class PushMessageOverlay(FloatLayout):
    def __init__(self, parent_icon, **kw):
        super().__init__(**kw)
        self.parent_icon = parent_icon

        # Hintergrund-Button zum Schließen
        bg = Button(
            background_color=(0, 0, 0, 0.2),
            border=(0, 0, 0, 0)
        )
        bg.bind(on_release=lambda *_: self.parent_icon.close_overlay())
        self.add_widget(bg)

        # Das Panel-Layout (Höhe leicht erhöht für mehr Fehlerplatz)
        self.panel = FloatLayout(
            size_hint=(None, None),
            size=(dp_scaled(400), dp_scaled(350)), 
            pos_hint={"right": 0.98, "top": 0.94}
        )

        # --- Jump-Button Pattern ---
        jump_btn = Button(
            text="[font=FA]\uf013[/font]",
            font_size=sp_scaled(24),
            markup=True,
            size_hint=(None, None),
            size=(dp_scaled(50), dp_scaled(50)),
            pos_hint={"right": 0.98, "top": 0.98},
            background_color=(0, 0, 0, 0),
            color=(0, 0.8, 1, 0.8)
        )
        
        with jump_btn.canvas.before:
            Color(0, 0.8, 1, 0.2)
            jump_bg = RoundedRectangle(radius=[dp_scaled(10)])
            Color(0, 0.8, 1, 0.5)
            jump_line = Line(width=1.1)
            
        def update_btn_canvas(obj, *args):
            jump_bg.pos = obj.pos
            jump_bg.size = obj.size
            jump_line.rounded_rectangle = (obj.x, obj.y, obj.width, obj.height, dp_scaled(10))
            
        jump_btn.bind(pos=update_btn_canvas, size=update_btn_canvas)
        
        def jump_to_overview(*_):
            GLOBAL_STATE.ui_handler.goto("grow_overview")
            self.parent_icon.close_overlay()

        jump_btn.bind(on_release=jump_to_overview)
        self.panel.add_widget(jump_btn)

        # --- Panel Canvas (Hintergrund & Outline) ---
        with self.panel.canvas.before:
            self.panel.bg_color = Color(0.05, 0.05, 0.05, 0.85) # Etwas dunkler für bessere Lesbarkeit
            self.panel.bg = RoundedRectangle(
                pos=self.panel.pos,
                size=self.panel.size,
                radius=[dp_scaled(20)]
            )
            Color(*self.parent_icon.accent)
            self.panel.outline = Line(
                rounded_rectangle=(
                    self.panel.x,
                    self.panel.y,
                    self.panel.width,
                    self.panel.height,
                    dp_scaled(20)
                ),
                width=1.2
            )
    
        def update_canvas(obj, *_):
            self.panel.bg.pos = obj.pos
            self.panel.bg.size = obj.size
            self.panel.outline.rounded_rectangle = (
                obj.x,
                obj.y,
                obj.width,
                obj.height,
                dp_scaled(20)
            )
    
        self.panel.bind(pos=update_canvas, size=update_canvas)

        # --- Titel ---
        title = Label(
            text=self.parent_icon.title_text,
            markup=True,
            font_size=sp_scaled(20),
            size_hint=(1, None),
            height=dp_scaled(40),
            pos_hint={"center_x": 0.5, "top": 0.95},
            halign="center",
            valign="middle"
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.panel.add_widget(title)
    
        # --- Scrollbarer Content für mehrere Meldungen ---
        # ScrollView container positionieren
        scroll_container = ScrollView(
            size_hint=(None, None),
            size=(dp_scaled(360), dp_scaled(240)),
            pos_hint={"center_x": 0.5, "top": 0.80},
            do_scroll_x=False,
            do_scroll_y=True
        )

        # BoxLayout im ScrollView hält die einzelnen Labels
        message_list = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp_scaled(8),
            padding=[dp_scaled(10), dp_scaled(5)]
        )
        # Wichtig: BoxLayout muss seine Höhe an den Inhalt anpassen
        message_list.bind(minimum_height=message_list.setter('height'))

        if self.parent_icon.critical_messages:
            # Für jede Nachricht ein eigenes Label erstellen
            for msg in self.parent_icon.critical_messages:
                lbl = Label(
                    text=f"[color=ff6666]• {msg}[/color]",
                    markup=True,
                    font_size=sp_scaled(15),
                    size_hint_y=None,
                    halign="left",
                    valign="top"
                )
                # Text-Wrapping aktivieren, damit lange Einzelfehler umbrechen
                lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
                lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
                message_list.add_widget(lbl)
        else:
            # Keine Fehler
            lbl = Label(
                text="No active critical messages",
                font_size=sp_scaled(15),
                size_hint_y=None,
                height=dp_scaled(30),
                halign="center",
                color=(0.7, 0.7, 0.7, 1)
            )
            message_list.add_widget(lbl)

        scroll_container.add_widget(message_list)
        self.panel.add_widget(scroll_container)
        
        self.add_widget(self.panel)