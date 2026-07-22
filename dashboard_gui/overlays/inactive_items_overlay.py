# dashboard_gui/ui/common/inactive_devices_overlay.py


from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView  # Neu importiert
from kivy.graphics import Color, Line, RoundedRectangle
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.global_state_manager import GLOBAL_STATE

class InactiveItemsOverlay(FloatLayout):
    def __init__(self, parent_icon, inactive_items, **kw):
        super().__init__(**kw)
        self.parent_icon = parent_icon
        self.inactive_items = inactive_items or []

        bg = Button(background_color=(0, 0, 0, 0.2), border=(0, 0, 0, 0))
        bg.bind(on_release=lambda *_: self.close())
        self.add_widget(bg)

        self.panel = FloatLayout(
            size_hint=(None, None),
            size=(dp_scaled(400), dp_scaled(320)),
            pos_hint={"right": 0.98, "top": 0.94}
        )
        

        # --- Jump-Button ---
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
            jump_line.rounded_rectangle = (
                obj.x, obj.y, obj.width, obj.height, dp_scaled(10)
            )

        jump_btn.bind(pos=update_btn_canvas, size=update_btn_canvas)

        def jump_to_overview(*_):
            GLOBAL_STATE.ui_handler.goto("setup")
            self.close()

        jump_btn.bind(on_release=jump_to_overview)

        self.panel.add_widget(jump_btn)
        with self.panel.canvas.before:
            self.panel.bg_color = Color(0.05, 0.05, 0.05, 0.95)
            self.panel.bg = RoundedRectangle(pos=self.panel.pos, size=self.panel.size, radius=[dp_scaled(16)])
            Color(0, 0.8, 1, 0.5)
            self.panel.outline = Line(rounded_rectangle=(self.panel.x, self.panel.y, self.panel.width, self.panel.height, dp_scaled(16)), width=1.2)

        self.panel.bind(pos=self._update_canvas, size=self._update_canvas)

        title = Label(text="Inaktive Funktionen", font_size=sp_scaled(18), size_hint=(1, None), height=dp_scaled(36), pos_hint={"center_x": 0.5, "top": 0.98})
        self.panel.add_widget(title)

        # 1. ScrollView erstellen und positionieren
        scroll_view = ScrollView(
            size_hint=(None, None),
            size=(dp_scaled(360), dp_scaled(240)),
            pos_hint={"center_x": 0.5, "top": 0.84},  # Minimal nach unten verschoben, um Platz für den Titel zu lassen
            bar_width=dp_scaled(4),                    # Schön dezenter Scrollbalken
            scroll_type=['content', 'bars']            # Scrollen per Touch/Mausrad und Balken erlauben
        )

        # 2. Das Content-BoxLayout anpassen (wichtig: size_hint_y=None!)
        content = BoxLayout(
            orientation="vertical", 
            padding=dp_scaled(4), 
            spacing=dp_scaled(8), 
            size_hint_y=None
        )
        # Automatische Höhenberechnung aktivieren
        content.bind(minimum_height=content.setter('height'))
        
        # Durchsuche die vom Header übergebenen Infos
        for name_str, icon_text, font_name, current_color in self.inactive_items:
            row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp_scaled(36))
            
            # Name der Funktion links
            lbl = Label(text=name_str, font_size=sp_scaled(18), halign="left", valign="middle", size_hint=(1, 1), color=(0.9, 0.9, 0.9, 1))
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            row.add_widget(lbl)
            
            # Erzeuge ein IconLabel, das exakt die Form aus dem Header kopiert
            visual_icon = IconLabel(text=icon_text, font_size=sp_scaled(24))
            if font_name:
                visual_icon.font_name = font_name
                
            visual_icon.size_hint = (None, 1)
            visual_icon.width = dp_scaled(60)
            
            # Zustand: Inaktiv -> keine Daten -> ausgegraut und nicht klickbar
            visual_icon.disabled = False
            visual_icon.color = (current_color[0], current_color[1], current_color[2], 0.4) # leicht transparent
            
            row.add_widget(visual_icon)
            content.add_widget(row)

        # 3. Content in die ScrollView packen, und ScrollView ins Panel setzen
        scroll_view.add_widget(content)
        self.panel.add_widget(scroll_view)
        
        self.add_widget(self.panel)

    def _update_canvas(self, obj, *args):
        self.panel.bg.pos = obj.pos
        self.panel.bg.size = obj.size
        self.panel.outline.rounded_rectangle = (obj.x, obj.y, obj.width, obj.height, dp_scaled(16))

    def open(self):
        pass

    def close(self):
        if self.parent and self.parent.parent:
            try:
                self.parent.remove_widget(self)
            except Exception:
                pass
        if self.parent_icon:
            self.parent_icon._overlay = None