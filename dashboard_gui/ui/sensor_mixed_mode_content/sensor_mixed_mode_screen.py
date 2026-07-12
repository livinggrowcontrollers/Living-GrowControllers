# dashboard_gui/ui/sensor_mixed_mode_content/sensor_mixed_mode_screen.py

# -*- coding: utf-8 -*-
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Rectangle, Color, Line
from kivy.uix.widget import Widget
import os
import config
from kivy.uix.boxlayout import BoxLayout  # <-- DIESER HAT GEFEHLT
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.common.buttons.control_buttons import ControlButtons
from dashboard_gui.ui.sensor_mixed_mode_content.mixed_mode_data_handler import MixedModeDataHandler
from dashboard_gui.ui.sensor_mixed_mode_content.mixed_mode_panel import MixedModePanel
from kivy.metrics import dp
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.graph_chart_content.chart_time_axis import compute_time_axis_labels
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout

class SensorMixedModeScreen(Screen):
    name = "sensor_mixed_mode"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.GS = GLOBAL_STATE
        self.GS.ui_handler.attach_screen(self.name, self)
        
        root = FloatLayout()
        self.add_widget(root)

        # Hintergrund
        with root.canvas.before:
            self.bg_rect = Rectangle(source=os.path.join("dashboard_gui", "assets", "background_mixed.png"))
        root.bind(size=self._update_bg)

        # Graph Widget (Hintergrund)
        self.graph_widget = Widget()
        
        # --- Zeitachse (unten) ---
        self.time_axis = GridLayout(
            cols=5,
            size_hint=(1, None),
            height=dp_scaled(18),
            pos=(0, dp_scaled(50))  # 👈 exakt über Buttons
        )

        self.time_labels = []
        for _ in range(5):
            lbl = Label(
                text="",
                font_size=sp_scaled(21),
                markup=True,
                color=(1, 1, 1, 0.4),
                bold=True,
                halign="center"
            )
            lbl.bind(size=lambda s, w: setattr(s, "text_size", (w[0], None)))
            self.time_axis.add_widget(lbl)
            self.time_labels.append(lbl)

        root.add_widget(self.time_axis)   
        
        root.add_widget(self.graph_widget, index=0)

        # UI Layout
        layout = BoxLayout(orientation="vertical")
        self.header = HeaderBar()
        layout.add_widget(self.header)
        self.panel = MixedModePanel(self)
        layout.add_widget(self.panel)

        self.controls = ControlButtons()
        self.controls.size_hint = (1,None)
        self.controls.height = dp_scaled(40)
        self.controls.pos_hint = {'y':0}
        layout.add_widget(self.controls)
        root.add_widget(layout)

        self.handler = MixedModeDataHandler(self)

    def _update_bg(self, *args):
        self.bg_rect.size = self.size

    def on_pre_enter(self):
        self.GS.mixed_mode_active = True
        self.handler.refresh()

    def _toggle_dev(self, dev_id):
        # 1. RAM Update
        if dev_id in self.GS.mixed_selected_buffers:
            self.GS.mixed_selected_buffers.remove(dev_id)
            # NEU: Speichern in config.json
            config.set_mixed_enabled(dev_id, False) 
        else:
            self.GS.mixed_selected_buffers.add(dev_id)
            config.set_mixed_enabled(dev_id, True)
            # Nutzen des neuen Setters
            if dev_id not in self.GS.mixed_device_modes:
                self.GS.mixed_device_modes[dev_id] = {"internal"}
            config.set_mixed_modes(dev_id, self.GS.mixed_device_modes[dev_id])

        self.handler.refresh()

    def _switch_mode(self, dev_id, mode):
        # Beim Laden das Set aus der Config als Fallback holen, falls RAM leer
        if dev_id not in self.GS.mixed_device_modes:
            self.GS.mixed_device_modes[dev_id] = config.get_mixed_modes(dev_id)
            
        modes = self.GS.mixed_device_modes[dev_id].copy()
        
        # Mode Toggle Logik
        if mode in modes:
            if len(modes) > 1: 
                modes.remove(mode)
        else:
            modes.add(mode)
        
        # 1. RAM Update
        self.GS.mixed_device_modes[dev_id] = modes
        
        # 2. Speichert jetzt sauber beide Flags (internal und external) gleichzeitig
        config.set_mixed_modes(dev_id, modes)
        
        self.handler.refresh()

    def update_from_global(self, d):
        self.header.update_from_global(d)
        # HIER DIE ARCHITEKTUR-ÄNDERUNG:
        self.handler.update_live_data() # Nur Werte schieben, nicht Liste killen
        self.draw_graph()

    def draw_graph(self):
        # Definition der Kurven
        curves = [
            ("mixed_avg_temp", (1, 0.4, 0.4, 0.9)), 
            ("mixed_avg_hum", (0.4, 0.7, 1, 0.8)), 
            ("mixed_avg_vpd", (0.4, 1, 0.7, 0.7))
        ]
        
        self.graph_widget.canvas.clear()
        
        with self.graph_widget.canvas:
            # Wir teilen die verfügbare Höhe durch die Anzahl der Kurven
            # Damit jede Kurve ihren eigenen "Platz" zum Atmen hat
            num_curves = len(curves)
            w, h = self.graph_widget.width, self.graph_widget.height
            x_off, y_off = self.graph_widget.x, self.graph_widget.y
            
            # Padding für den gesamten Widget-Bereich
            base_padding = h * 0.1
            available_h = h - (2 * base_padding)
            
            # Höhe pro Korridor
            section_h = available_h / num_curves

            for idx, (key, color) in enumerate(curves):
                points = self.GS.graph_engine.get_buffer(key)
                if not points or len(points) < 2: 
                    continue
                
                Color(*color)
                
                min_v, max_v = min(points), max(points)
                v_range = (max_v - min_v) if max_v > min_v else 1
                
                # Berechnung des vertikalen Offsets für diesen spezifischen Graphen
                # idx 0 (Temp) ist oben, idx 2 (VPD) ist unten
                # Wir lassen innerhalb der Sektion nochmal 10% Platz (inner_pad)
                inner_pad = section_h * 0.1
                current_section_y = y_off + base_padding + (num_curves - 1 - idx) * section_h
                
                line_pts = []
                for i, val in enumerate(points):
                    # X bleibt linear
                    px = x_off + (i / (len(points) - 1)) * w
                    
                    # Y wird innerhalb SEINER Sektion skaliert
                    normalized_val = (val - min_v) / v_range
                    py = current_section_y + inner_pad + (normalized_val * (section_h - 2 * inner_pad))
                    
                    line_pts.extend([px, py])
                
                # Zeichnen der Linie mit schönem Glow-Effekt (optional 2. Linie darunter)
                Line(points=line_pts, width=dp_scaled(2.2), joint='round', cap='round')
                
                # Optional: Ein ganz schwacher Schatten/Glow für die Tiefe
                Color(color[0], color[1], color[2], 0.15)
                Line(points=line_pts, width=dp_scaled(5), joint='round', cap='round')
                self.update_time_axis()

    def update_time_axis(self):
        buffer = self.GS.graph_engine.get_buffer("mixed_avg_temp")
        if not buffer:
            return

        display_buf = list(buffer)

        refresh_rate = config.get_refresh_interval()
        raw_res = float(config.get_graph_resolution())

        labels = compute_time_axis_labels(
            display_len=len(display_buf),
            refresh_rate=refresh_rate,
            raw_res=raw_res
        )

        for lbl, txt in zip(self.time_labels, labels):
            lbl.text = txt