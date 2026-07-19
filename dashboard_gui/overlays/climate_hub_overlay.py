# dashboard_gui/overlays/climate_hub_overlay.py
import os
import time
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.dropdown import DropDown
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.unified_slider import UnifiedSlider
from dashboard_gui.overlays.lock_overlay import LockOverlay
from dashboard_gui.overlays.base_revision_system import BaseRevisionSystem
from dashboard_gui.ui.common.buttons.button_style_helper import ButtonStyleHelper
from dashboard_gui.ui.common.background_click_handler import BackgroundClickHandler

# --- ASSET CONFIGURATION ---
ASSET_ROOT = os.path.join("dashboard_gui", "assets")
CLIMATE_PIC_PATH = os.path.join(ASSET_ROOT, "hardware_pics", "climate_hub.png") 


class ClimateHubOverlay(FloatLayout, BoxColorUpdater, ButtonStyleHelper, BackgroundClickHandler):
    def __init__(self, parent_header, **kwargs):
        super().__init__(**kwargs)
        
        # ===================================================================
        # STRIKT ZUERST: ALLE INSTANZVARIABLEN INITIALISIEREN
        # ===================================================================
        self.opacity = 0
        self.parent_header = parent_header
        self._user_active = False 
        self._last_user_action = 0 
        self._init_done = False
        self._locked = True
        self._ui_lock = False
        self._stage = "custom"
        self._night_reduction_enabled = True
        
        # REVISION ENGINE INITIALISIERUNG (Gekoppelt an rev_exhaust)
        self.engine = BaseRevisionSystem()
        self._last_sent_rev = 0

        # ===================================================================
        # UI & WIDGET AUFBAU
        # ===================================================================
        # Hintergrund mit Klick-Schließ-Logik
        self.bg_btn = Button(background_color=(0, 0, 0, 0.25))
        self.bg_btn.bind(on_release=self._on_background_click)
        self.add_widget(self.bg_btn)

        # Main Panel
        self.panel = BoxLayout(
            orientation="vertical", 
            spacing=dp_scaled(8),
            size_hint=(None, None), 
            size=(dp_scaled(800), dp_scaled(500)),
            padding=[dp_scaled(25), dp_scaled(15), dp_scaled(25), dp_scaled(25)],
            pos_hint={"right": 0.98, "y": 0.01} 
        )

        # Canvas Setup (Glow & Border)
        with self.panel.canvas.before:
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg_rect = RoundedRectangle(radius=[dp_scaled(20)])
        
            self.glow_color = Color(0.1, 0.45, 0.9, 0.35)
            self.glow_line = Line(width=4)
        
            self.border_color = Color(0.1, 0.45, 0.9, 0.85)
            self.border_line = Line(width=2.5)

        self.panel.bind(pos=self._u, size=self._u)

        # --- HEADER BEREICH ---
        title_row = BoxLayout(size_hint_y=None, height=dp_scaled(35), spacing=dp_scaled(5))
        self.lbl_title = Label(text="CLIMATE HUB", bold=True, color=(0, 1, 0, 1),
                               font_size=sp_scaled(20), halign="left", valign="middle")
        self.lbl_title.bind(size=self.lbl_title.setter('text_size'))
        
        self.sync_icon = Button(text="[font=FA]\uf021[/font]", markup=True,
                                font_size=sp_scaled(30), size_hint=(None, None), 
                                width=dp_scaled(45), height=dp_scaled(45),
                                background_color=(0, 0, 0, 0), color=(1, 1, 1, 1))
        self.sync_icon.bind(on_release=self._force_sync)

        self.btn_phase = Button(
            text="CUSTOM  [font=FA]\uf078[/font]",
            markup=True,
            font_size=sp_scaled(16),
            size_hint=(None, 1),
            width=dp_scaled(190),
            background_normal="",
            background_down="",
            background_color=(0.0, 0.65, 0.35, 0.85),
            color=(0, 0, 0, 1),
        )
        self.btn_phase.bind(on_release=self._open_stage_menu)
        
        title_row.add_widget(self.lbl_title)
        title_row.add_widget(self.btn_phase)
        title_row.add_widget(self.sync_icon)
        self.panel.add_widget(title_row)

        # --- LIVE DATA INFOBEREICH ---
        top_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(80), spacing=dp_scaled(10))
        
        from kivy.uix.image import Image
        img_placeholder = Image(source=CLIMATE_PIC_PATH, size_hint=(None, 1), width=dp_scaled(180))
        top_container.add_widget(img_placeholder)
        
        mid_col = BoxLayout(orientation="vertical", size_hint_x=0.75, spacing=dp_scaled(2))
        self.lbl_live_temp = Label(text="Live Temperature: --", font_size=sp_scaled(18), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        self.lbl_live_hum = Label(text="Live Humidity: --", font_size=sp_scaled(18), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        self.lbl_live_vpd = Label(text="Live VPD: --", font_size=sp_scaled(18), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        
        for lbl in [self.lbl_live_temp, self.lbl_live_hum, self.lbl_live_vpd]:
            lbl.bind(size=lbl.setter('text_size'))
            mid_col.add_widget(lbl)
            
        top_container.add_widget(mid_col)
        
        right_col = BoxLayout(orientation="vertical", size_hint_x=0.25, spacing=dp_scaled(4))
        self.lbl_rating_placeholder = Label(text="", font_size=sp_scaled(22), bold=True, color=(0.7, 0.7, 1, 0.8), halign="center", valign="middle")
        self.lbl_rating_placeholder.bind(size=self.lbl_rating_placeholder.setter('text_size'))
        right_col.add_widget(self.lbl_rating_placeholder)
        
        top_container.add_widget(right_col)
        self.panel.add_widget(top_container)

        # --- THREE RANGE SLIDERS (Analog zu Exhaust) ---
        self.lbl_temp = self._add_slider_label("TEMPERATURE TARGET", "22.0° - 28.0°")
        self.temp_slider = UnifiedSlider(range_min=15, range_max=30, min=22, max=28, mode='range', 
                                       size_hint_y=None, height=dp_scaled(35))
        self.temp_slider.bind(min_value=self._on_env_slider_change, max_value=self._on_env_slider_change,
                              on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.temp_slider)

        self.lbl_hum = self._add_slider_label("HUMIDITY TARGET", "45% - 70%")
        self.hum_slider = UnifiedSlider(
            range_min=30, range_max=70, 
            min=40, max=70, 
            mode='range', 
            size_hint_y=None, height=dp_scaled(35)
        )
        self.hum_slider.bind(min_value=self._on_env_slider_change, max_value=self._on_env_slider_change,
                             on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.hum_slider)

        self.lbl_vpd = self._add_slider_label("VPD TARGET", "0.8 - 1.5")
        self.vpd_slider = UnifiedSlider(min=1, max=15, range_min=1, range_max=26, mode='range', 
                                      size_hint_y=None, height=dp_scaled(35))
        self.vpd_slider.bind(min_value=self._on_vpd_slider_change, max_value=self._on_vpd_slider_change,
                             on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.vpd_slider)

        self.panel.add_widget(Widget())

        # The bottom action belongs to the active climate profile: night
        # reduction is shared with the existing Exhaust target pipeline.
        night_row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_night = self._create_styled_btn("[font=FA]\uf186[/font]  NIGHT MODE")
        self.btn_night.bind(on_release=lambda *_: self._toggle_night_mode())
        night_row.add_widget(self.btn_night)
        self.panel.add_widget(night_row)
        
        # --- LOCK OVERLAY & SCHEDULING ---
        self.lock_overlay = LockOverlay(parent=self, panel=self.panel, unlock_callback=self._on_unlock)
        
        self._update_event = Clock.schedule_interval(self.update_ui, 0.1)
        Clock.schedule_once(self._init_values, 0.1)
        
        self.add_widget(self.panel)

    def _add_slider_label(self, left_text, right_text=""):
        row = BoxLayout(size_hint_y=None, height=dp_scaled(15))
        row.add_widget(Label(text=left_text, font_size=sp_scaled(20), color=(0.0, 0.85, 0.35, 0.75), halign="left"))
        lbl_right = Label(text=right_text, font_size=sp_scaled(20), color=(1, 1, 1, 1), halign="right")
        row.add_widget(lbl_right)
        self.panel.add_widget(row)
        return lbl_right

    # ===================================================================
    # SLIDER & SELECTION EVENTS (Aufgeteilt analog zu Exhaust)
    # ===================================================================
    def _on_env_slider_change(self, *args):
        if not self._init_done or self._ui_lock or self._locked: 
            return
        self._set_custom_from_manual_input()
        self._update_target_labels()
        self._set_orange()

    def _on_vpd_slider_change(self, *args):
        if not self._init_done or self._ui_lock or self._locked: 
            return
        self._set_custom_from_manual_input()
        self._update_target_labels()
        self._set_orange()

    def _open_stage_menu(self, *_):
        dropdown = DropDown(auto_dismiss=True, max_height=dp_scaled(300))
        stages = (
            ("seedling", "SEEDLING"),
            ("vegetative", "VEG"),
            ("flowering", "FLOWERING"),
            ("drying", "DRYING"),
            ("curing", "CURING"),
            ("custom", "CUSTOM"),
        )
        for stage, label in stages:
            button = Button(text=label, size_hint_y=None, height=dp_scaled(42), background_normal="", background_color=(0.12, 0.12, 0.14, 1))
            button.bind(on_release=lambda _button, selected=stage: self._set_stage(selected, dropdown))
            dropdown.add_widget(button)
        dropdown.open(self.btn_phase)

    def _set_stage(self, stage_name, dropdown=None):
        if self._locked:
            return
        self._stage = stage_name
        self._last_user_action = time.time()
        self._user_active = True

        profiles = {
            "seedling": (24.0, 27.0, 60, 70, 0.6, 0.9),
            "vegetative": (24.0, 28.0, 55, 70, 0.8, 1.2),
            "flowering": (22.0, 27.0, 45, 60, 1.2, 1.5),
            "drying": (18.0, 22.0, 50, 60, 0.7, 1.0),
            "curing": (18.0, 21.0, 55, 62, 0.6, 0.9),
        }
        if stage_name in profiles:
            t_min, t_max, h_min, h_max, v_min, v_max = profiles[stage_name]
            self._ui_lock = True
            self.temp_slider.min_value, self.temp_slider.max_value = t_min, t_max
            self.hum_slider.min_value, self.hum_slider.max_value = h_min, h_max
            self.vpd_slider.min_value, self.vpd_slider.max_value = int(v_min * 10), int(v_max * 10)
            self._ui_lock = False
            self._update_target_labels()

        self._apply_stage_controls()
        if dropdown:
            dropdown.dismiss()
        self._set_orange()
        self._send_current_state()
        Clock.schedule_once(lambda dt: setattr(self, "_user_active", False), 0.4)

    def _set_custom_from_manual_input(self):
        if self._stage != "custom":
            self._stage = "custom"
            self._apply_stage_controls()

    def _apply_stage_controls(self):
        label = self._stage.upper() if self._stage != "vegetative" else "VEG"
        self.btn_phase.text = f"{label}  [font=FA]\uf078[/font]"
        self.btn_phase.background_color = (0.0, 0.65, 0.35, 0.85) if self._stage != "custom" else (0.35, 0.35, 0.4, 0.9)
        self.btn_phase.color = (0, 0, 0, 1) if self._stage != "custom" else (1, 1, 1, 1)
        self.btn_night.background_color = (0.35, 0.42, 1.0, 0.9) if self._night_reduction_enabled else (0.15, 0.15, 0.15, 1)
        self.btn_night.color = (0, 0, 0, 1) if self._night_reduction_enabled else (1, 1, 1, 1)

    def _toggle_night_mode(self):
        if self._locked:
            return
        self._night_reduction_enabled = not self._night_reduction_enabled
        self._user_active = True
        self._last_user_action = time.time()
        self._apply_stage_controls()
        self._send_current_state()
        Clock.schedule_once(lambda dt: setattr(self, "_user_active", False), 0.4)

    def _update_target_labels(self):
        self.lbl_temp.text = f"{self.temp_slider.min_value:.1f}° - {self.temp_slider.max_value:.1f}°"
        self.lbl_hum.text = f"{int(self.hum_slider.min_value)}% - {int(self.hum_slider.max_value)}%"
        self.lbl_vpd.text = f"{self.vpd_slider.min_value / 10.0:.1f} - {self.vpd_slider.max_value / 10.0:.1f}"

    def _touch_down(self, instance, touch):
        if self._locked: 
            return False
        if instance.collide_point(*touch.pos):
            self._user_active = True
            return False

    def _touch_up(self, instance, touch):
        if self._user_active:
            self._user_active = False
            self._last_user_action = time.time()
            self._send_current_state()
            return False

    # ===================================================================
    # INTERIMS-BRÜCKE AN REV_EXHAUST PIPELINE
    # ===================================================================
    def _send_current_state(self, is_retry=False, **kwargs):
        if not self._init_done:
            return

        stage = kwargs.get("stage", self._stage)
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            return

        new_rev = GLOBAL_STATE.send_overlay_command(
            "climate_hub",
            t_min=round(float(self.temp_slider.min_value), 1),
            t_max=round(float(self.temp_slider.max_value), 1),
            h_min=int(self.hum_slider.min_value),
            h_max=int(self.hum_slider.max_value),
            vpd_min=round(self.vpd_slider.min_value / 10.0, 1),
            vpd_max=round(self.vpd_slider.max_value / 10.0, 1),
            stage=stage,
            night_reduction=self._night_reduction_enabled,
        )

        if new_rev:
            self.engine.mark_sent(new_rev)
            self._last_sent_rev = new_rev
            self._last_user_action = time.time()
            self._set_orange()
        
            if not is_retry:
                self.engine.reset_retry()

    def _apply_server_snapshot(self, data):
        if self._user_active:
            return   
            
        t_min = float(data.get('target_temp_min', 22.0))
        t_max = float(data.get('target_temp_max', 28.0))
        h_min = int(data.get('target_humidity_min', 45))
        h_max = int(data.get('target_humidity_max', 70))
        v_min = float(data.get('target_vpd_min', 0.8))
        v_max = float(data.get('target_vpd_max', 1.5))

        self._ui_lock = True

        self.temp_slider.min_value = t_min
        self.temp_slider.max_value = t_max
        self.hum_slider.min_value = h_min
        self.hum_slider.max_value = h_max
        self.vpd_slider.min_value = int(v_min * 10)
        self.vpd_slider.max_value = int(v_max * 10)

        self._ui_lock = False

        self._night_reduction_enabled = bool(data.get("exhaust_fan_night_reduction", True))
        self._update_target_labels()
        self._apply_stage_controls()
        self._update_climate_box_color(data)
        
        # Interims-Gekoppelt an die rev_exhaust vom ESP
        self._last_sent_rev = int(data.get('rev_exhaust', 0))
        self.engine.mark_confirmed_snapshot(self._last_sent_rev)

    def _set_orange(self):
        self.sync_icon.text = "[font=FA]\uf021[/font]"
        self.sync_icon.color = (1, 0.5, 0, 1)

    def _force_sync(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac) if mac else None
        if not data:
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)
            return

        self._apply_server_snapshot(data)
        server_rev = int(data.get("rev_exhaust", 0))
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
    
        Clock.schedule_once(lambda dt: self._send_current_state(), 0.05)
        self._set_orange()

    # ===================================================================
    # REVISIONS-GESTEUERTES UPDATE_UI (Über rev_exhaust gesichert)
    # ===================================================================
    def update_ui(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac) if mac else None

        if server_data:
            # ==========================================================
            # LIVE SENSOR VALUES
            # ==========================================================
            internal = server_data.get("internal", {})

            temp_data = internal.get("temperature", {})
            hum_data = internal.get("humidity", {})
            vpd_data = server_data.get("vpd_internal", {})

            temp_val = temp_data.get("value")
            hum_val = hum_data.get("value")
            vpd_val = vpd_data.get("value") if isinstance(vpd_data, dict) else vpd_data

            temp_unit = temp_data.get("unit", "°C")
            hum_unit = hum_data.get("unit", "%")
            vpd_unit = (
                vpd_data.get("unit", "kPa")
                if isinstance(vpd_data, dict)
                else "kPa"
            )

            self.lbl_live_temp.text = (
                f"Live Temperature: {temp_val:.1f} {temp_unit}"
                if temp_val is not None
                else "Live Temperature: --"
            )

            self.lbl_live_hum.text = (
                f"Live Humidity: {hum_val:.1f} {hum_unit}"
                if hum_val is not None
                else "Live Humidity: --"
            )

            self.lbl_live_vpd.text = (
                f"Live VPD: {vpd_val:.2f} {vpd_unit}"
                if vpd_val is not None
                else "Live VPD: --"
            )
            self._update_climate_box_color(server_data)

        else:
            if self._init_done:
                self.sync_icon.text = "[font=FA]\uf071[/font]"
                self.sync_icon.color = (1, 0.3, 0, 1)
            return

        # ==========================================================
        # Target-Revision Überprüfung
        # ==========================================================
        server_rev = int(server_data.get("rev_exhaust", 0))
        pending = self.engine.is_pending(server_rev)

        if pending and self.engine.should_retry():
            if self.engine.retry_allowed():
                self.engine.register_retry()
                self._send_current_state(is_retry=True)
                return

        status = self.engine.get_status(
            server_rev,
            self._user_active,
            self._last_user_action
        )

        self._update_sync_icon(status)

        if status == "green" and not self._user_active:
            self._apply_server_snapshot(server_data)

    def _update_sync_icon(self, status):
        if status == "green":
            self.sync_icon.text = "[font=FA]\uf058[/font]"
            self.sync_icon.color = (0, 1, 0, 1)
        elif status == "orange" or status == "retry":
            self.sync_icon.text = "[font=FA]\uf021[/font]"
            self.sync_icon.color = (1, 0.5, 0, 1)
        elif status == "error":
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)

    def _on_unlock(self):
        self._locked = False
        for s in [self.temp_slider, self.hum_slider, self.vpd_slider]:
            s.disabled = False
        self._apply_stage_controls()

    def _init_values(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac) if mac else None
        if not data:
            Clock.schedule_once(self._init_values, 0.1)
            return
            
        server_rev = int(data.get('rev_exhaust', 0))
        self._apply_server_snapshot(data)
        
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
        self._init_done = True
        
        self.sync_icon.text = "[font=FA]\uf058[/font]"
        self.sync_icon.color = (0, 1, 0, 1)

        if self._locked and self.lock_overlay and not self.lock_overlay.overlay:
            self.lock_overlay.create()
        self.opacity = 1

    def _u(self, *args):
        if not hasattr(self, 'bg_rect'):
            return
    
        pos = self.panel.pos
        size = self.panel.size
    
        self.bg_rect.pos = pos
        self.bg_rect.size = size
    
        rect = (
            self.panel.x,
            self.panel.y,
            self.panel.width,
            self.panel.height,
            dp_scaled(20)
        )
    
        self.glow_line.rounded_rectangle = rect
        self.border_line.rounded_rectangle = rect

    def _update_climate_box_color(self, data):
        color = self.get_climate_color(data)
        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)
    
    def close(self):
        if hasattr(self, '_update_event') and self._update_event:
            self._update_event.cancel()
        if self.parent:
            self.parent.remove_widget(self)
        GLOBAL_STATE.ui_handler.active_climate_hub_overlay = None
