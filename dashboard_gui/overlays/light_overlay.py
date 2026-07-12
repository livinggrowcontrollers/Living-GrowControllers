# dashboard_gui/overlays/light_overlay.py
###############################################################################
# !!! REPARIERTES & BEGRADIGTES OVERLAY: HIGH-TECH DESIGN MIT BACKGROUND-GRAPH !!!
# INKLUSIVE ROTEM ZEITINDIKATOR & X-ACHSEN-ZEITLEGENDE
###############################################################################

import os
import json
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
import time 
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.common.logic.light_time import calculate_light_time
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.unified_slider import UnifiedSlider
from dashboard_gui.overlays.lock_overlay import LockOverlay
from dashboard_gui.overlays.base_revision_system import BaseRevisionSystem
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from dashboard_gui.ui.common.buttons.button_style_helper import ButtonStyleHelper
from dashboard_gui.ui.common.background_click_handler import BackgroundClickHandler

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
LIGHT_PIC_PATH = os.path.join(ASSET_ROOT, "hardware_pics", "electrogrow.png")

class LightOverlay(FloatLayout, ButtonStyleHelper, BackgroundClickHandler):
    def __init__(self, parent_header, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0
        self.parent_header = parent_header
        self._user_active = False 
        self._last_user_action = 0 
        self._init_done = False
        self._locked = True
        self._target_mode = "time"
        self._last_sent_rev = 0
        self._last_send_time = 0
        self._retry_count = 0
        self._max_retries = 5
        self._ui_lock = False
        self._pending_updates = {}
        self.sync_path = os.path.join("data", "settings_sync.json")
        self.engine = BaseRevisionSystem()
        
        # Hintergrund
        # Hintergrund mit smarter Schließ-Logik bei Missclicks
# Hintergrund mit smarter Schließ-Logik bei Missclicks
        self.bg_btn = Button(background_color=(0, 0, 0, 0.25))
        
        def bg_touch_down(instance, touch):
            if self._locked:
                return False  # Lässt den Touch direkt zum LockOverlay durchwandern
            return Button.on_touch_down(instance, touch)
            
        self.bg_btn.on_touch_down = bg_touch_down.__get__(self.bg_btn, Button)
        self.bg_btn.bind(on_release=self._on_background_click)
        self.add_widget(self.bg_btn)

        # Panel (Abmessungen exakt beibehalten)
        self.panel = BoxLayout(
            orientation="vertical", 
            spacing=dp_scaled(7),
            size_hint=(None, None), 
            size=(dp_scaled(800), dp_scaled(500)), 
            padding=[dp_scaled(25), dp_scaled(15), dp_scaled(25), dp_scaled(25)],
            pos_hint={"right": 0.98, "y": 0.01} 
        )

# Leinwand für Hintergrund-Styling und Tageskurve
        with self.panel.canvas.before:
            # 1. Background
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg_rect = RoundedRectangle(radius=[dp_scaled(20)])
            
            # 2. Dynamische Farben (Intensitäts-Glow & Rahmen)
            self.glow_color = Color(0.12, 0.12, 0.12, 0.0)
            self.value_glow = Line(width=4)
            
            self.border_color = Color(0.22, 0.22, 0.22, 0.55)
            self.value_border = Line(width=2.5)
            
            # 3. Graph Elemente
            from kivy.graphics import Mesh
            Color(1, 0.72, 0.05, 0.15)
            self.graph_fill = Mesh(mode='triangle_strip')
            
            Color(1, 0.72, 0.05, 0.08)
            self.graph_glow = Line(width=dp_scaled(3), joint='round')
            
            Color(1, 0.72, 0.15, 1.25)
            self.graph_line = Line(width=dp_scaled(1.5), joint='round')

            # 4. Zeit-Indikator
            Color(1, 0.2, 0.2, 0.85) 
            self.time_indicator = Line(width=dp_scaled(1.5))

        self.panel.bind(pos=self._u, size=self._u)

        # Header

        title_row = BoxLayout(size_hint_y=None, height=dp_scaled(28), spacing=dp_scaled(0))
        
        self.lbl_title = Label(text="LIGHT CONTROL PRO", bold=True, color=(0, 1, 0, 1),
                               font_size=sp_scaled(20), halign="left", valign="middle")
        self.lbl_title.bind(size=self.lbl_title.setter('text_size'))
        
        self.sync_icon = Button(text="[font=FA]\uf021[/font]", markup=True, font_size=sp_scaled(30),
                                background_color=(0, 0, 0, 0), color=(1, 1, 1, 1), 
                                size_hint_x=None, width=dp_scaled(45))
        self.sync_icon.bind(on_release=self._force_sync)
        
        title_row.add_widget(self.lbl_title)
        title_row.add_widget(self.sync_icon)
        self.panel.add_widget(title_row)

        # === STATUS BEREICH (nur aktueller Wert + Status + Restzeit) ===

        top_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(68), spacing=dp_scaled(2))
        
        # 1. Das Bild
        img_light = Image(source=LIGHT_PIC_PATH, size_hint=(None, 1), width=dp_scaled(180))
        top_container.add_widget(img_light)
        
        # 2. Hauptwert + Zielwert links (horizontal nebeneinander)
        values_left = BoxLayout(orientation='horizontal', size_hint_x=0.4, spacing=dp_scaled(5))
        self.lbl_val = Label(text="0%", font_size=sp_scaled(36), bold=True, halign='center', valign='middle')
        self.lbl_val.bind(size=self.lbl_val.setter('text_size'))
        self.lbl_slider_target = Label(text="0%", font_size=sp_scaled(36), bold=True, color=(0.0, 0.75, 1, 1), halign='center', valign='middle')
        self.lbl_slider_target.bind(size=self.lbl_slider_target.setter('text_size'))
        values_left.add_widget(self.lbl_val)
        values_left.add_widget(self.lbl_slider_target)
        top_container.add_widget(values_left)
        
        # 3. Status rechts
        status_right = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=dp_scaled(1))
        self.lbl_status_text = Label(text="STATUS: INIT", font_size=sp_scaled(20), bold=True, color=(0, 1, 0, 0.85), halign='center')
        self.lbl_remaining = Label(text="REMAINING: --", font_size=sp_scaled(20), color=(1, 1, 0, 1), bold=True, halign='center')
        self.lbl_status_text.bind(size=self.lbl_status_text.setter('text_size'))
        self.lbl_remaining.bind(size=self.lbl_remaining.setter('text_size'))
        status_right.add_widget(self.lbl_status_text)
        status_right.add_widget(self.lbl_remaining)
        top_container.add_widget(status_right)
        
        self.panel.add_widget(top_container)
    
        # === INTENSITÄT LABEL (MITTIG ÜBER DEM SLIDER) ===
        intensity_label_row = BoxLayout(size_hint_y=None, height=dp_scaled(15), spacing=dp_scaled(4))
        self.lbl_intensity = Label(
            text="INTENSITY",
            font_size=sp_scaled(20),
            color=(1, 1, 1, 0.9),
            bold=True,
            halign='right',
            valign='middle'
        )
        self.lbl_intensity.bind(
            size=self.lbl_intensity.setter('text_size')
        )
        
        # LIGHT STATE LABEL
        self.lbl_light_state = Label(
            text="DAY",
            font_size=sp_scaled(20),
            bold=True,
            color=(0, 1, 0, 0.95),
            halign='center',
            valign='middle'
        )
        self.lbl_light_state.bind(
            size=self.lbl_light_state.setter('text_size')
        )
        
        intensity_label_row.add_widget(self.lbl_intensity)
        intensity_label_row.add_widget(self.lbl_light_state)
        self.panel.add_widget(intensity_label_row)

        # Haupt-Slider
        self.slider = UnifiedSlider(min=0, max=100, mode='single', size_hint_y=None, height=dp_scaled(38))
        self.slider.bind(value=self._on_slider_change, on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.slider)



        # Sunrise/Sunset
        self.lbl_sunrise_sunset = Label(text="RAMPEN: --", markup=True, font_size=sp_scaled(20), color=(1, 0.8, 0.2, 0.8), size_hint_y=None, height=dp_scaled(15))
        self.panel.add_widget(self.lbl_sunrise_sunset)
        self.slider_sunrise_sunset = UnifiedSlider(min=1, max=96, mode='range', fill_entire_track=True)        
        self.slider_sunrise_sunset.bind(min_value=self._on_sunrise_sunset_change, max_value=self._on_sunrise_sunset_change, on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.slider_sunrise_sunset)

        # Startzeit
        self.lbl_start = Label(text="START: --", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(15))
        self.panel.add_widget(self.lbl_start)
        self.slider_start = UnifiedSlider(min=0, max=95, mode='single', size_hint_y=None, height=dp_scaled(38))
        self.slider_start.bind(value=self._on_start_change, on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.slider_start)

        # Dauer
        self.lbl_dur = Label(text="DURATION: --", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(15))
        self.panel.add_widget(self.lbl_dur)
        self.slider_dur = UnifiedSlider(min=1, max=96, mode='single', size_hint_y=None, height=dp_scaled(38))
        self.slider_dur.bind(value=self._on_dur_change, on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.slider_dur)

        # Etwas weniger Platz vor dem Graphen (da Restzeit jetzt oben ist)
        self.panel.add_widget(Widget(size_hint_y=None, height=dp_scaled(4)))

        # Timeline (X-Achse)
        self.timeline_layout = FloatLayout(size_hint_y=None, height=dp_scaled(15))
        self.lbl_time_00 = Label(text="00:00", font_size=sp_scaled(11), color=(0.82, 0.82, 0.82, 0.92), size_hint=(None, None), size=(dp_scaled(40), dp_scaled(15)))
        self.lbl_time_06 = Label(text="06:00", font_size=sp_scaled(11), color=(0.82, 0.82, 0.82, 0.92), size_hint=(None, None), size=(dp_scaled(40), dp_scaled(15)))
        self.lbl_time_12 = Label(text="12:00", font_size=sp_scaled(11), color=(0.82, 0.82, 0.82, 0.92), size_hint=(None, None), size=(dp_scaled(40), dp_scaled(15)))
        self.lbl_time_18 = Label(text="18:00", font_size=sp_scaled(11), color=(0.82, 0.82, 0.82, 0.92), size_hint=(None, None), size=(dp_scaled(40), dp_scaled(15)))
        
        self.timeline_layout.add_widget(self.lbl_time_00)
        self.timeline_layout.add_widget(self.lbl_time_06)
        self.timeline_layout.add_widget(self.lbl_time_12)
        self.timeline_layout.add_widget(self.lbl_time_18)
        self.panel.add_widget(self.timeline_layout)

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp_scaled(30), spacing=dp_scaled(8))
        self.btn_man = self._create_styled_btn("MANUELL")
        self.btn_tim = self._create_styled_btn("TIMER")
        self.btn_climate = self._create_styled_btn("CLIMA OVR")
        btn_row.add_widget(self.btn_man)
        btn_row.add_widget(self.btn_tim)
        btn_row.add_widget(self.btn_climate)
        self.panel.add_widget(btn_row)


        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_tim.bind(on_release=lambda *_: self._set_mode("time"))
        self.btn_climate.bind(on_release=lambda *_: self._toggle_climate_override()) # <- Eigene Toggle-Funktion

        self.add_widget(self.panel)

        self.lock_overlay = LockOverlay(parent=self, panel=self.panel, unlock_callback=self._on_unlock)
        Clock.schedule_once(self._init_values, 0.1)
        
        self._update_event = Clock.schedule_interval(self.update_ui, 0.1)
    

    def _update_overlay_colors(self, brightness):
        glow_alpha = 0.35
        border_alpha = 0.85

        color = BoxColorUpdater.get_light_color(brightness)

        self.glow_color.rgba = (*color, glow_alpha)
        self.border_color.rgba = (*color, border_alpha)


        
    def _init_values(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        if not data: Clock.schedule_once(self._init_values, 0.1); return
        server_rev = int(data.get('rev_light', 0))
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
        self._ui_lock = True
        self._apply_server_snapshot(data)
        self._ui_lock = False
        self._init_done = True
        self._update_graph()
        self._user_active = False
        self._last_user_action = 0
        self.sync_icon.text = "[font=FA]\uf058[/font]"
        self.sync_icon.color = (0, 1, 0, 1)

        if self._locked and self.lock_overlay and not self.lock_overlay.overlay:
            self.lock_overlay.create()
        self.opacity = 1

    def _apply_server_snapshot(self, data):
        if not data:
            return
    
        # 1. Daten holen
        mode = data.get('light_mode', 'man')
        self._target_mode = mode
        current_hw = data.get("light_pct")

        if current_hw is None:
            current_hw = 0
        else:
            current_hw = int(current_hw)
        target = data.get("light_target")

        if target is None:
            target = 0
        else:
            target = int(target)
        state_reason = str(data.get('light_state_reason', 'DAY')).upper().strip()
        climate_override = bool(data.get('light_climate_override', False))
        
        # 2. UI Updates (Farben & Basiswerte)
        self._update_overlay_colors(current_hw)
        self.lbl_val.text = f"{current_hw}%"
        self.lbl_slider_target.text = f"{target}%"
        
        # Status Text
        if mode == "off":
            self.lbl_status_text.text = "STATUS: AUS"
            self.lbl_status_text.color = (1, 0.2, 0.2, 0.8)
        elif mode == "manual":
            self.lbl_status_text.text = "STATUS: MANUELL"
            self.lbl_status_text.color = (0, 0.8, 1, 1)
        else:
            self.lbl_status_text.text = "STATUS: TIMER"
            self.lbl_status_text.color = (0, 1, 0, 1)

        # 3. Phase Logik (Mapping statt if/else Kaskade)
        phase_config = {
            "SUNRISE": {"text": "SUNRISE", "color": (1.0, 0.72, 0.15, 1)},
            "SUNSET":  {"text": "SUNSET",  "color": (1.0, 0.45, 0.1, 1)},
            "NIGHT":   {"text": "NIGHT",   "color": (0.45, 0.65, 1.0, 1)},
            "DAY":     {"text": "DAY",     "color": (0.0, 1.0, 0.35, 1)}
        }
        
        config = phase_config.get(state_reason, phase_config["DAY"])
        base_text = config["text"]
        base_color = config["color"]
    
        # Extensions (Climate + Reason)
        extensions = []
        if climate_override:
            extensions.append("[color=00ff66]CLIM-OVR[/color]")
            
        # Nur zusätzliche Reason, wenn kein Standard-Phasenname
        if state_reason not in phase_config and state_reason not in ["", "MANUAL", "NORMAL", "TIMER"]:
            extensions.append(f"[color=ffcc33]{state_reason}[/color]")
    
        self.lbl_light_state.markup = True
        self.lbl_light_state.text = f"{base_text}{' | ' + ' | '.join(extensions) if extensions else ''}"
        self.lbl_light_state.color = base_color
    
        # 4. Slider & Zeit-Daten
        h = int(data.get('l_start_h', 8))
        m = int(data.get('l_start_m', 0))
        dur = int(data.get('l_dur', 720))
        srise = int(data.get('l_sunrise', 60))
        sset = int(data.get('l_sunset', 60))
    
        dur_steps = dur // 15
        self.slider.value = target
        self.slider_start.value = (h * 60 + m) // 15
        self.slider_dur.value = dur_steps
        # Ersetzen durch mathematische Absicherung (Clamping):
        self.slider_sunrise_sunset.range_max = dur_steps

        # ABSICHERUNG: Werte werden fest zwischen 1 und dur_steps geklammert, damit sie nicht ins Nirvana rutschen
        calc_min = max(1, min(dur_steps, srise // 15))
        calc_max = max(calc_min, min(dur_steps, dur_steps - (sset // 15)))

        self.slider_sunrise_sunset.min_value = calc_min
        self.slider_sunrise_sunset.max_value = calc_max
    
        # 5. Label Texte & Abschluss
        self.lbl_start.text = f"START: {h:02d}:{m:02d}"
        self.lbl_dur.text = f"DURATION: {dur//60}h {dur%60:02d}m"
        
        if mode == "time" and current_hw != target and current_hw > 0:
            self.lbl_val.color = (1, 0.72, 0.05, 1)
        else:
            self.lbl_val.color = (1, 1, 1, 1)
    
        self._update_ramp_label(srise, sset)
        self._apply_button_styles(mode, target)
        self._update_graph()
    def _update_graph(self, *args):
        if not self._init_done: return
        try:
            target = int(self.slider.value)
            start_min = int(self.slider_start.value) * 15
            dur_min = int(self.slider_dur.value) * 15
            srise_min = int(self.slider_sunrise_sunset.min_value) * 15
            sset_min = int(self.slider_sunrise_sunset.range_max - self.slider_sunrise_sunset.max_value) * 15
        except Exception:
            return

        # Koordinaten-Mapping auf Basis der festen Panel-Größe
        x_base = self.panel.x + dp_scaled(25)
        y_base = self.panel.y + dp_scaled(75) 
        w_graph = self.panel.width - dp_scaled(50)
        h_graph = dp_scaled(30) 

        points = []
        end_min = start_min + dur_min

        for step in range(97):
            t = (step * 15) % 1440
            if step == 96: t = 1440
            
            is_active = False
            t_rel = 0

            if end_min <= 1440:
                if start_min <= t <= end_min:
                    is_active = True
                    t_rel = t - start_min
            else:
                if t >= start_min:
                    is_active = True
                    t_rel = t - start_min
                elif t <= (end_min % 1440):
                    is_active = True
                    t_rel = t + 1440 - start_min

            pct = 0
            if is_active and dur_min > 0:
                if t_rel < srise_min and srise_min > 0:
                    pct = target * (t_rel / srise_min)
                elif t_rel > (dur_min - sset_min) and sset_min > 0:
                    pct = target * ((dur_min - t_rel) / sset_min)
                else:
                    pct = target

            x_p = x_base + (step / 96.0) * w_graph
            y_p = y_base + (pct / 100.0) * h_graph
            points.extend([x_p, y_p])

        self.graph_line.points = points
        self.graph_glow.points = points

        vertices = []
        for i in range(0, len(points), 2):
            x_p = points[i]
            y_p = points[i+1]
            vertices.extend([x_p, y_base, 0, 0])
            vertices.extend([x_p, y_p, 0, 0])

        self.graph_fill.indices = list(range(len(vertices) // 4))
        self.graph_fill.vertices = vertices

        # --- POSITION DER ROTEN TIME-LINE ---
        now = time.localtime()
        current_total_minutes = now.tm_hour * 60 + now.tm_min
        day_progress = current_total_minutes / 1440.0
        indicator_x = x_base + (day_progress * w_graph)
        
        self.time_indicator.points = [
            indicator_x, y_base, 
            indicator_x, y_base + h_graph + dp_scaled(5)
        ]

        # --- NEU: DYNAMISCHE POSITIONIERUNG DER ZEIT-LABEL (LEGENDE) ---
        # Wir platzieren die Label relativ zur X-Achse des Graphen um Verschiebungen zu verhindern
        self.lbl_time_00.pos = (x_base - self.lbl_time_00.width / 2, y_base - dp_scaled(16))
        self.lbl_time_06.pos = (x_base + (0.25 * w_graph) - self.lbl_time_06.width / 2, y_base - dp_scaled(16))
        self.lbl_time_12.pos = (x_base + (0.50 * w_graph) - self.lbl_time_12.width / 2, y_base - dp_scaled(16))
        self.lbl_time_18.pos = (x_base + (0.75 * w_graph) - self.lbl_time_18.width / 2, y_base - dp_scaled(16))


    def _on_slider_change(self, *args):
        if self._init_done and not self._ui_lock and not self._locked:
            value = int(self.slider.value)
            self.lbl_slider_target.text = f"{value}%"      # nur noch hier
            self.sync_icon.color = (1, 0.5, 0, 1)
            self._update_graph()

    # Ersetzen durch additive Absicherung am Ende der Funktion:
    def _on_dur_change(self, instance, value):
        if self._init_done and not self._ui_lock:
            steps = max(1, min(96, int(value)))
            self.slider_dur.value = steps
            self.lbl_dur.text = f"DURATION: {(steps*15)//60}h {(steps*15)%60:02d}m"
            self.slider_sunrise_sunset.range_max = steps
            
            # ADD: Verhindert das Ausbrechen des Sunset-Buttons bei Verkürzung der Dauer
            if self.slider_sunrise_sunset.max_value > steps:
                self.slider_sunrise_sunset.max_value = steps
            if self.slider_sunrise_sunset.min_value > self.slider_sunrise_sunset.max_value:
                self.slider_sunrise_sunset.min_value = self.slider_sunrise_sunset.max_value
                
            self._update_graph()

    def _on_start_change(self, instance, value):
        if self._init_done and not self._ui_lock:
            value = max(0, min(95, int(value)))
            m = value * 15
            self.lbl_start.text = f"START: {m//60:02d}:{m%60:02d}"
            self._update_graph()

    def _update_ramp_label(self, sr, ss):
        self.lbl_sunrise_sunset.text = f"[font=FA]\uf185[/font] SUNRISE: {sr}m | [font=FA]\uf186[/font] SUNSET: {ss}m"

    def _on_sunrise_sunset_change(self, *args):
        if self._init_done and not self._ui_lock:
            sr, ss = int(self.slider_sunrise_sunset.min_value) * 15, int(self.slider_sunrise_sunset.range_max - self.slider_sunrise_sunset.max_value) * 15
            self._update_ramp_label(sr, ss)
            self._update_graph()

    def _touch_down(self, slider, touch):
        if not self._locked and slider.collide_point(*touch.pos): self._user_active = True

    def _touch_up(self, slider, touch):
        if self._user_active:
            self._user_active = False; self._last_user_action = time.time(); self._send_command()

    def _set_mode(self, mode):
        if not self._locked: self._target_mode = mode; self._send_command(mode=mode)

    def _on_unlock(self):
        self._locked = False
        for s in [self.slider, self.slider_start, self.slider_dur, self.slider_sunrise_sunset]: s.disabled = False

    def _force_sync(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            return

        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)

        if not data:
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)
            return

        server_rev = int(data.get('rev_light', 0))
        srv_target = data.get("light_target")

        if target is None:
            target = 0
        else:
            target = int(target)
        srv_mode = data.get('light_mode', self._target_mode)

        # Übernehme UI Snapshot (minimale Übernahme, so wie Circulation does)
        self._ui_lock = True
        try:
            try:
                self.slider.value = srv_target
            except Exception:
                pass
            try:
                h = int(data.get('l_start_h', 8))
                m = int(data.get('l_start_m', 0))
                dur = int(data.get('l_dur', 720))
                dur_steps = dur // 15
                self.slider_start.value = (h * 60 + m) // 15
                self.slider_dur.value = dur_steps
                self.slider_sunrise_sunset.range_max = dur_steps
                self.slider_sunrise_sunset.min_value = int(data.get('l_sunrise', 60)) // 15
                self.slider_sunrise_sunset.max_value = dur_steps - (int(data.get('l_sunset', 60)) // 15)
            except Exception:
                pass
        finally:
            self._ui_lock = False

        self._target_mode = srv_mode
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)

        # Plane das Senden kurz verzögert (gleiches Verhalten wie Circulation)
        Clock.schedule_once(lambda dt: self._send_command(), 0.05)

        # Visuelles Feedback: orange (pending)
        self.sync_icon.text = "[font=FA]\uf021[/font]"
        self.sync_icon.color = (1, 0.5, 0, 1)

    def update_ui(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        if not server_data:
            if self._init_done:
                self.sync_icon.text, self.sync_icon.color = "[font=FA]\uf071[/font]", (1, 0.3, 0, 1)
            return

        self.lbl_remaining.text = calculate_light_time(server_data)
        server_rev = int(server_data.get('rev_light', 0))
        pending = self.engine.is_pending(server_rev)
        
        if pending and self.engine.should_retry():
            if self.engine.retry_allowed():
                self.engine.register_retry()
                self._send_command(is_retry=True)
                return
        
        status = self.engine.get_status(
            server_rev,
            self._user_active,
            self._last_user_action
        )
        
        if status == "green":
            self.sync_icon.text, self.sync_icon.color = "[font=FA]\uf058[/font]", (0, 1, 0, 1)
        elif status == "retry":
            self.sync_icon.text, self.sync_icon.color = "[font=FA]\uf021[/font]", (1, 0.5, 0, 1)
        elif status == "error":
            self.sync_icon.text, self.sync_icon.color = "[font=FA]\uf071[/font]", (1, 0.3, 0, 1)
        else:
            self.sync_icon.text, self.sync_icon.color = "[font=FA]\uf021[/font]", (1, 0.5, 0, 1)
        
        self._update_graph()

        if status != "green": return
        if not self._user_active:
            self._ui_lock = True; self._apply_server_snapshot(server_data); self._ui_lock = False

    def _toggle_climate_override(self):
        if not self._locked:
            mac = GLOBAL_STATE.get_active_device_id()
            server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
            # Aktuellen Zustand invertieren
            current_override = server_data.get('light_climate_override', False)
            new_override = not current_override
            
            # Befehl mit neuem Override-Zustand absenden
            self._send_command(climate_override=new_override)

    def _send_command(self, is_retry=False, **kwargs):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac or not self._init_done: return
        send_mode = kwargs.get("mode", self._target_mode)
        start_min = max(0, min(95, int(self.slider_start.value))) * 15
        
        # Hol den Klima-Zustand: Entweder aus den kwargs (frischer Klick) oder aus dem UI-Buffer-Zustand
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        climate_state = kwargs.get("climate_override", server_data.get('light_climate_override', False))

        rev = GLOBAL_STATE.send_overlay_command(
            "light", 
            pct=int(self.slider.value), 
            mode=send_mode,                    # immer explizit senden
            h=start_min // 60, 
            m=start_min % 60, 
            dur=int(self.slider_dur.value) * 15,
            sunrise=int(self.slider_sunrise_sunset.min_value) * 15, 
            sunset=int(self.slider_sunrise_sunset.range_max - self.slider_sunrise_sunset.max_value) * 15,
            climate_override=climate_state # <- Wird an die Engine übergeben
        )
        if rev:
            self.engine.mark_sent(rev)
            self._last_sent_rev = rev
            self._last_send_time = time.time()
            if not is_retry: self.engine.reset_retry()

    def _apply_button_styles(self, mode, target=0):
    
        base = (0.15, 0.15, 0.15, 1)
    
        # MANUAL
        self.btn_man.background_color = (0, 1, 0, 0.85) if mode == "manual" else base
    
        # TIMER
        self.btn_tim.background_color = (0, 0.7, 1, 0.85) if mode == "time" else base
    
        # CLIMATE (ESP LIVE STATUS)
        mac = GLOBAL_STATE.get_active_device_id()
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        climate_active = server_data.get('light_climate_override', False)
    
        self.btn_climate.background_color = (1, 0.5, 0, 0.85) if climate_active else base
    
        # 🔥 TEXT KONTRAST FIX (EXHAUST 1:1 übernommen)
        def fix(btn, active):
            btn.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)
    
        fix(self.btn_man, mode == "manual")
        fix(self.btn_tim, mode == "time")
        fix(self.btn_climate, climate_active)
        
    def _u(self, *args):
        # Sicherheitsprüfung: Existieren die Canvas-Objekte schon?
        if not hasattr(self, 'bg_rect') or not hasattr(self, 'value_border'):
            return

        # Position und Dimensionen
        pos = self.panel.pos
        size = self.panel.size
        r = dp_scaled(20)
        rect = (pos[0], pos[1], size[0], size[1], r)

        # Update Background
        self.bg_rect.pos = pos
        self.bg_rect.size = size
        
        # Update Rahmen (anstatt 'outline' verwenden wir 'value_border')
        self.value_border.rounded_rectangle = rect
        self.value_glow.rounded_rectangle = rect
        
        # Nur Graph updaten, wenn Initialisierung fertig
        if self._init_done:
            self._update_graph()

    def close(self):
        if self._update_event: self._update_event.cancel()
        if self.parent: self.parent.remove_widget(self)
        GLOBAL_STATE.ui_handler.active_light_overlay = None
