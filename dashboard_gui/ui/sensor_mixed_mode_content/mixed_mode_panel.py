# dashboard_gui/ui/sensor_mixed_mode_content/mixed_mode_panel.py

# -*- coding: utf-8 -*-
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Line
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Line
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.sensor_mixed_mode_content.mixed_mode_device_button import DeviceButton

class MixedModePanel(BoxLayout):
    def __init__(self, screen, **kw):
        super().__init__(orientation="horizontal", padding=dp_scaled(15), spacing=dp_scaled(20), **kw)
        self.screen = screen
        
        # --- LINKS: Scroll-Liste ---
        self.left_col = BoxLayout(orientation="vertical", size_hint_x=0.35)
        # ... (dein bisheriger Code für left_col)
        self.left_col.add_widget(Label(text="[b]DEVICES[/b]", markup=True, size_hint_y=None, height=dp_scaled(30), color=(1, 1, 1, 0.6)))
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp_scaled(2))
        self.details_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp_scaled(10))
        self.details_list.bind(minimum_height=self.details_list.setter("height"))
        self.scroll.add_widget(self.details_list)
        self.left_col.add_widget(self.scroll)
        self.add_widget(self.left_col)

        # --- RECHTS: Averages Card ---
        self.right_col = BoxLayout(orientation="vertical", size_hint_x=0.65)
        
        # Card-Container (Höhe auf 380 erhöht, damit die dicke Schrift Platz hat)
        # Erhöhe die Card-Größe etwas für Android-Sicherheit
        self.avg_card = BoxLayout(
            orientation="vertical", 
            padding=dp_scaled(15), 
            spacing=dp_scaled(5), 
            size_hint=(None, None), 
            size=(dp_scaled(420), dp_scaled(340)), # Etwas mehr Puffer
            pos_hint={"center_x": .5, "center_y": .5}
        )
        
        with self.avg_card.canvas.before:
            Color(0, 0, 0, 0.62)
            self.bg_rect = RoundedRectangle(
                pos=self.avg_card.pos,
                size=self.avg_card.size,
                radius=[dp_scaled(20)]
            )
        
            Color(0, 0.8, 1, 0.5)
            self.outline = Line(
                rounded_rectangle=(
                    self.avg_card.x,
                    self.avg_card.y,
                    self.avg_card.width,
                    self.avg_card.height,
                    dp_scaled(20)
                ),
                width=1.2
            )
            
        self.avg_card.bind(pos=self._update_rect, size=self._update_rect)

        # 1. Überschrift
        self.lbl_avg_title = Label(
            text="[b]MIXED AVERAGES[/b]", markup=True, font_size=sp_scaled(22),
            size_hint_y=None, height=dp_scaled(45), color=(1, 1, 1, 0.9),
            halign="center", valign="middle"
        )
        self.lbl_avg_title.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        self.avg_card.add_widget(self.lbl_avg_title)


        # Wir erhöhen die Basis-Schriftgröße der Labels mit sp_scaled
# Wir entfernen font_size aus den Labels, da wir sie oben im Handler 
# Die Labels brauchen eine definierte Höhe, sonst "clippen" sie bei Markup
        self.lbl_temp = Label(text="--", markup=True, color=(1, 0.4, 0.4, 1), size_hint_y=None, height=dp_scaled(60))
        self.lbl_hum  = Label(text="--", markup=True, color=(0.4, 0.7, 1, 1), size_hint_y=None, height=dp_scaled(60))
        self.lbl_vpd  = Label(text="--", markup=True, color=(0.4, 1, 0.7, 1), size_hint_y=None, height=dp_scaled(60))
        self.lbl_dew  = Label(text="--", markup=True, color=(0.8, 0.8, 1, 1), size_hint_y=None, height=dp_scaled(60))
        
        for l in [self.lbl_temp, self.lbl_hum, self.lbl_vpd, self.lbl_dew]:
            self.avg_card.add_widget(l)
        
        self.right_col.add_widget(Widget()) 
        self.right_col.add_widget(self.avg_card)
        self.right_col.add_widget(Widget()) 
        self.add_widget(self.right_col)

    def _update_rect(self, obj, *args):
        self.bg_rect.pos = obj.pos
        self.bg_rect.size = obj.size
    
        self.outline.rounded_rectangle = (
            obj.x,
            obj.y,
            obj.width,
            obj.height,
            dp_scaled(20)
        )

    def set_averages(self, data):
        """Nimmt das Rohdaten-Paket und nutzt den UIFormatter für den Edel-Look."""
        
        # --- DEINE ZENTRALEN STELLHEBEL (JETZT VOLLSTÄNDIG SEPARIERT) ---
# Diese Werte werden jetzt AUTOMATISCH skaliert!
        GROESSE_WERT    = 42  # Sieht jetzt auf Desktop und Android gleich groß aus
        GROESSE_NAME    = 18  
        GROESSE_TREND   = 24  
        GROESSE_UNIT    = 18
        # --------------------------------------------------------------

        mapping = [
            ("temp", self.lbl_temp),
            ("hum",  self.lbl_hum),
            ("vpd",  self.lbl_vpd),
            ("dew",  self.lbl_dew)
        ]

        for key, label_widget in mapping:
            d = data.get(key, {})
            
            if d.get("val") is not None:
                # Wir rufen die Engine mit allen VIER Größen auf:
                label_widget.text = UIFormatter.format_sensor_label(
                    name=d["name"],
                    value=d["val"],
                    unit=d["unit"],
                    trend=d["trend"],
                    sz_val=GROESSE_WERT,
                    sz_name=GROESSE_NAME,
                    sz_trend=GROESSE_TREND,
                    sz_unit=GROESSE_UNIT
                )
            else:
                # Fallback für "Keine Daten"
                name = d.get("name", key.upper())
                label_widget.text = f"[color=#666666][size={GROESSE_NAME}]{name}:[/size] [size={GROESSE_WERT}]--[/size][/color]"

    def rebuild_device_list(self):
        self.details_list.clear_widgets()
        snapshot = self.screen.handler.get_device_list_snapshot()
        for dev in snapshot:
            self.details_list.add_widget(self._build_card(dev))

    def update_device_values(self):
        """Aktualisiert nur die Texte der Buttons mit der GLEICHEN Größe wie beim Build."""
        snapshot = self.screen.handler.get_device_list_snapshot()
        
        # --- ZENTRALE STELLSCHRAUBE (Muss identisch mit _build_card sein) ---
        s_name = int(sp_scaled(20))
        s_detail = int(sp_scaled(18)) # Einheitlich auf 18 (oder dein Wunschwert)
        
        for dev_data in snapshot:
            dev_id = dev_data["device_id"]
            for card in self.details_list.children:
                if getattr(card, 'device_id', None) == dev_id:
                    # Suche den Button im Card-Container
                    btn = next((c for c in card.children if isinstance(c, ToggleButton)), None)
                    if btn:
                        is_sel = btn.state == "down"
                        
                        if is_sel:
                            name = f"[b][size={s_name}]{dev_data['label']}[/size][/b]"
                        else:
                            name = f"[size={s_name}]{dev_data['label']}[/size]"
                        
                        btn.text = (
                            f"{name}\n"
                            f"[size={s_detail}][color=#cccccc]{dev_data['values_str']}[/color][/size]"
                        )
                    break

    def _build_card(self, dev):
        is_sel = dev["selected"]
        h = dp_scaled(120) if (is_sel and dev["has_external"]) else dp_scaled(80)
        card = BoxLayout(orientation="vertical", size_hint_y=None, height=h, spacing=dp_scaled(5))
        card.device_id = dev["device_id"]

        # --- GLEICHE STELLSCHRAUBE WIE OBEN ---
        s_name = int(sp_scaled(20))
        s_detail = int(sp_scaled(18)) 

        btn = DeviceButton(
            text="", # Wird gleich gesetzt
            markup=True, 
            halign="center",
            state="down" if is_sel else "normal",
        )
        
        # Hier nutzen wir exakt das gleiche Format
        if is_sel:
            name = f"[b][size={s_name}]{dev['label']}[/size][/b]"
        else:
            name = f"[size={s_name}]{dev['label']}[/size]"
        
        btn.text = (
            f"{name}\n"
            f"[size={s_detail}][color=#cccccc]{dev['values_str']}[/color][/size]"
        )
        
        btn.bind(on_release=lambda x: self.screen._toggle_dev(dev["device_id"]))
        card.add_widget(btn)

        # ... (Modus-Buttons für Internal/External bleiben gleich) ...
        if is_sel and dev["has_external"]:
            # Hier auch sp_scaled nutzen für die Modus-Buttons
            modes = BoxLayout(spacing=dp_scaled(4), size_hint_y=None, height=dp_scaled(35))
            for m in ["internal", "external"]:
                m_active = m in dev["modes"]
                m_btn = DeviceButton(
                    text=m.upper(), 
                    state="down" if m_active else "normal",
                    font_size=sp_scaled(16), bold=True,
                    background_color=(0, 0, 0, 0.4) if m_active else (0, 0, 0, 0.3),
                    color=(1, 1, 1, 1) if m_active else (1, 1, 1, 0.5)
                )
                m_btn.bind(on_release=lambda x, m=m: self.screen._switch_mode(dev["device_id"], m))
                modes.add_widget(m_btn)
            card.add_widget(modes)
            
        return card
    def rebuild_device_list(self):
        """Baut die Liste komplett neu (nur bei Strukturänderungen nötig)."""
        self.details_list.clear_widgets()
        snapshot = self.screen.handler.get_device_list_snapshot()
        for dev in snapshot:
            card = self._build_card(dev)
            card.device_id = dev["device_id"] # WICHTIG: ID an das Widget heften für späteres Update
            self.details_list.add_widget(card)

