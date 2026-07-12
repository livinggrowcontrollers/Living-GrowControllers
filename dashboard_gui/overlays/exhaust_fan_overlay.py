# dashboard_gui/overlays/exhaust_fan_overlay.py

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
# import config  <-- Vermutlich hier definiert: ASSET_ROOT
import time 
import json 
import os
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.unified_slider import UnifiedSlider
from dashboard_gui.overlays.lock_overlay import LockOverlay
from dashboard_gui.overlays.base_revision_system import BaseRevisionSystem
from kivy.uix.widget import Widget
from kivy.uix.image import Image  # <-- WICHTIGER IMPORT!
from dashboard_gui.ui.common.buttons.button_style_helper import ButtonStyleHelper
from dashboard_gui.ui.common.background_click_handler import BackgroundClickHandler
import config
# --- ASSET PFAD KONFIGURATION (Beispielhaft, anpassen falls nötig) ---
# Da 'config' im Snippet auskommentiert ist, definieren wir es hier lokal.
# In deinem echten Code sollte das aus der 'config.py' kommen.
ASSET_ROOT = os.path.join("dashboard_gui", "assets") 
FAN_PIC_PATH = os.path.join(ASSET_ROOT, "hardware_pics", "vivosun_t6.png")
# -------------------------------------------------------------------


class ExhaustFanOverlay(FloatLayout, BoxColorUpdater, ButtonStyleHelper, BackgroundClickHandler):
    def __init__(self, parent_header, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0
        self.parent_header = parent_header
        self._user_active = False 
        self._last_user_action = 0 
        self._init_done = False
        self._locked = True
        self._target_mode = "auto"
        self._chaos_enabled = False
        self._night_reduction_enabled = True
        # === AUTO-RETRY VARIABLEN ===
        self._last_sent_rev = 0
        self._last_send_time = 0
        self._retry_count = 0
        self._max_retries = 5

        self._ui_lock = False
        # self.sync_path = os.path.join(config.DATA, "settings_sync.json") # config auskommentiert
        self._pending_updates = {}
        self.engine = BaseRevisionSystem()
        # Nach den anderen self._xxx Variablen
        # Hintergrund
        # Hintergrund mit smarter Schließ-Logik bei Missclicks
        self.bg_btn = Button(background_color=(0, 0, 0, 0.25))
        self.bg_btn.bind(on_release=self._on_background_click)
        self.add_widget(self.bg_btn)

        # Panel
        self.panel = BoxLayout(
            orientation="vertical", 
            spacing=dp_scaled(8),
            size_hint=(None, None), 
            size=(dp_scaled(800), dp_scaled(500)),
            padding=[dp_scaled(25), dp_scaled(15), dp_scaled(25), dp_scaled(25)],
            pos_hint={"right": 0.98, "y": 0.01} 
        )

        # Suche diesen Block in deiner __init__:
        with self.panel.canvas.before:
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg_rect = RoundedRectangle(radius=[dp_scaled(20)])
        
            self.glow_color = Color(0.1, 0.45, 0.9, 0.35)
            self.glow_line = Line(width=4)
        
            self.border_color = Color(0.1, 0.45, 0.9, 0.85)
            self.border_line = Line(width=2.5)

        # WICHTIG: Bindung an Panel-Größe für konsistentes Verhalten
        self.panel.bind(pos=self._u, size=self._u)

        # Header
        title_row = BoxLayout(size_hint_y=None, height=dp_scaled(35), spacing=dp_scaled(5))
        self.lbl_title = Label(text="EXHAUST FAN CONTROL", bold=True, color=(0, 1, 0, 1),
                               font_size=sp_scaled(20), halign="left", valign="middle")
        self.lbl_title.bind(size=self.lbl_title.setter('text_size'))
        
        self.sync_icon = Button(text="[font=FA]\uf021[/font]", markup=True,
                                font_size=sp_scaled(30), size_hint=(None, None), 
                                width=dp_scaled(45), height=dp_scaled(45),
                                background_color=(0, 0, 0, 0), color=(1, 1, 1, 1))
        self.sync_icon.bind(on_release=self._force_sync)
        
        title_row.add_widget(self.lbl_title)
        title_row.add_widget(self.sync_icon)
        self.panel.add_widget(title_row)

        # ===================================================================
        # NEU: BILD + DATEN ZEILE (Vivosun + RPM + Live)
        # ===================================================================

        top_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(80), spacing=dp_scaled(10))
        
        # 1. Bild links
        img_fan = Image(source=FAN_PIC_PATH, size_hint=(None, 1), width=dp_scaled(180))
        top_container.add_widget(img_fan)
        
        # 2. Mitte: Speed-Bereich & Live-Status
        mid_col = BoxLayout(orientation="vertical", size_hint_x=0.75)
        self.lbl_val = Label(text="0% - 0%", font_size=sp_scaled(30), bold=True, halign="left", valign="middle")
        self.lbl_val.bind(size=self.lbl_val.setter('text_size'))
        self.lbl_reason1 = Label(
            text="AUTO IDLE",
            font_size=sp_scaled(18),
            bold=True,
            color=(0, 1, 1, 0.9),
            halign="left",
            valign="middle",
            size_hint=(0.5, None),
            height=dp_scaled(28)
        )
       
        self.lbl_reason1.bind(size=lambda inst, *_: setattr(inst, 'text_size', (inst.width, inst.height)))
        
        self.lbl_reason2 = Label(
            text="",
            font_size=sp_scaled(20),
            bold=True,
            color=(0.8, 0.8, 1, 0.9),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(28)
        )
        
        self.lbl_reason2.bind(size=lambda inst, *_: setattr(inst, 'text_size', (inst.width, inst.height)))
        self.lbl_live_speed = Label(text="LIVE: 0%", font_size=sp_scaled(20), bold=True, color=(0, 1, 1, 0.8), halign="right", valign="middle", size_hint=(None, None), width=dp_scaled(80), height=dp_scaled(28))
        
        
        
        self.reason_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp_scaled(28), spacing=dp_scaled(10))
        self.reason_row.add_widget(self.lbl_reason1)
        self.reason_row.add_widget(self.lbl_reason2)
        mid_col.add_widget(self.lbl_val)
        mid_col.add_widget(self.reason_row)
        top_container.add_widget(mid_col)
        
        # 3. Rechts: RPM & Live-Speed
        right_col = BoxLayout(
            orientation="vertical",
            size_hint_x=0.25,
            spacing=dp_scaled(4)
        )
        
        self.lbl_rpm = Label(
            text="RPM: 0",
            font_size=sp_scaled(22),
            bold=True,
            color=(0.7, 0.7, 1, 0.8),
            halign="center",
            valign="middle"
        )
        self.lbl_rpm.bind(size=self.lbl_rpm.setter('text_size'))
        
        self.lbl_live_speed = Label(
            text="LIVE: 0%",
            font_size=sp_scaled(22),
            bold=True,
            color=(0, 1, 1, 0.8),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp_scaled(24)
        )
        self.lbl_live_speed.bind(size=self.lbl_live_speed.setter('text_size'))
        
        right_col.add_widget(self.lbl_rpm)
        right_col.add_widget(self.lbl_live_speed)
        
        top_container.add_widget(right_col)
        
        self.panel.add_widget(top_container)

        # Sliders
        self._add_slider_label("FAN SPEED RANGE")
        self.range_slider = UnifiedSlider(min=0, max=100, mode='range', size_hint_y=None, height=dp_scaled(35))
        self.range_slider.bind(min_value=self._on_slider_change, max_value=self._on_slider_change,
                               on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.range_slider)

        self.lbl_temp = self._add_slider_label("TEMP TARGET", "22° - 28°")
        self.temp_slider = UnifiedSlider(range_min=15, range_max=30, min=22, max=28, mode='range', 
                                       size_hint_y=None, height=dp_scaled(35))
        self.temp_slider.bind(min_value=self._on_env_slider_change, max_value=self._on_env_slider_change,
                              on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.temp_slider)

        self.lbl_hum = self._add_slider_label("HUMIDITY TARGET", "40% - 70%")
        # UnifiedSlider muss die Grenzen kennen, damit das Mapping stimmt
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

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_man = self._create_styled_btn("MANUAL")
        self.btn_auto = self._create_styled_btn("AUTOMATIC")
        self.btn_chao = self._create_styled_btn("CHAOTIC")
        self.btn_night =self._create_styled_btn("NIGHT")
        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_auto.bind(on_release=lambda *_: self._set_mode("auto"))
        self.btn_chao.bind(on_release=lambda *_: self._set_mode("chao"))
        self.btn_night.bind(on_release=lambda *_: self._set_mode("night"))
        
        btn_row.add_widget(self.btn_man)
        btn_row.add_widget(self.btn_auto)
        btn_row.add_widget(self.btn_chao)
        btn_row.add_widget(self.btn_night)

        self.panel.add_widget(btn_row)
        
        self._phase_map = {
            0: "DAY",
            1: "SUNSET",
            2: "NIGHT",
            3: "SUNRISE"
        }
        self._last_phase = -1
        # Lock & Events
        self.lock_overlay = LockOverlay(parent=self, panel=self.panel, unlock_callback=self._on_unlock)
        
        self._update_event = Clock.schedule_interval(self.update_ui, 0.1)
        
        Clock.schedule_once(self._init_values, 0.1)
        self.add_widget(self.panel)

    # ===================================================================
    # ZENTRALE SEND-METHODE MIT AUTO-RETRY
    # ===================================================================
    # ===================================================================
    def _send_current_state(self, is_retry=False, **kwargs):
        """Einheitliche Sende-Methode mit Retry-Unterstützung"""
        if not self._init_done:
            return

        mode = kwargs.get("mode", self._target_mode)

        # Alle aktuellen UI-Werte sammeln
        new_rev = GLOBAL_STATE.send_overlay_command(
            "exhaust_fan",
            min=int(self.range_slider.min_value),
            max=int(self.range_slider.max_value),
            t_min=round(float(self.temp_slider.min_value), 1),
            t_max=round(float(self.temp_slider.max_value), 1),
            h_min=int(self.hum_slider.min_value),
            h_max=int(self.hum_slider.max_value),
            vpd_min=round(self.vpd_slider.min_value / 10.0, 1),
            vpd_max=round(self.vpd_slider.max_value / 10.0, 1),
            mode=mode,
            chaos=self._chaos_enabled,
            night_reduction=self._night_reduction_enabled)

        if new_rev:
            self.engine.mark_sent(new_rev)
            self._last_sent_rev = new_rev
            self._last_send_time = time.time()
            self._set_orange()
        
            if not is_retry:
                self.engine.reset_retry()


    def _apply_server_snapshot(self, data):
        if self._user_active:
            return   # 🔥 KRITISCHER FIX
        s_min = int(data.get('exhaust_fan_min', 20))
        s_max = int(data.get('exhaust_fan_pct', 65))
        s_mode = data.get('exhaust_fan_mode', 'auto')

        t_min = float(data.get('target_temp_min', 22))
        t_max = float(data.get('target_temp_max', 28))
        h_min = int(data.get('target_humidity_min', 40))
        h_max = int(data.get('target_humidity_max', 70))

        v_min = float(data.get('target_vpd_min', 0.8))
        v_max = float(data.get('target_vpd_max', 1.5))

        # --- SNAPSHOT BLOCK ---
        self._ui_lock = True

        self.range_slider.max_value = s_max
        self.range_slider.min_value = s_min
        self.temp_slider.max_value = t_max
        self.temp_slider.min_value = t_min

        # HIER WIRD DER HUMIDITY SLIDER AUF 30-80 GENAGELT:
        self.hum_slider.range_min = 30
        self.hum_slider.range_max = 70
        self.hum_slider.max_value = h_max
        self.hum_slider.min_value = h_min

        self.vpd_slider.max_value = int(v_max * 10)
        self.vpd_slider.min_value = int(v_min * 10)

        self._ui_lock = False

        self.lbl_val.text = f"{s_min}% - {s_max}%"
        
        # _apply_server_snapshot()

        if config.get_temperature_unit().upper() == "F":
            self.lbl_temp.text = f"{t_min * 9 / 5 + 32:.1f} °F - {t_max * 9 / 5 + 32:.1f} °F"
        else:
            self.lbl_temp.text = f"{t_min:.1f} °C - {t_max:.1f} °C"

        self.lbl_hum.text = f"{h_min}% - {h_max}%"
        self.lbl_vpd.text = f"{v_min:.1f} kPa - {v_max:.1f} kPa"

        # Wir holen uns den Chaos-Status aus den Daten (0 oder 1 vom ESP)
        s_chaos = bool(data.get('exhaust_fan_chaos_active', 0))
        
        # KRITISCHER FIX:
        # Snapshot muss den lokalen Send-State synchronisieren
        self._chaos_enabled = s_chaos
        self._night_reduction_enabled = bool(data.get( "exhaust_fan_night_reduction",True))
        # Hauptmodus synchronisieren
        self._target_mode = s_mode
        
        # Buttons aktualisieren
        self._apply_button_styles(s_mode, s_chaos)
        self._last_sent_rev = int(data.get('rev_exhaust', 0))
        self.engine.mark_confirmed_snapshot(self._last_sent_rev)
        phase_idx = int(data.get("plant_phase", 0))
        phase_name = self._phase_map.get(phase_idx, "OFF")
        
        # Update Header
        self.lbl_title.text = f"EXHAUST FAN CONTROL • {phase_name}"
        
        exhaust_fan_group = data.get('exhaust_fan', {})
        rpm = int(exhaust_fan_group.get('exhaust_fan_rpm', 0))
        self._update_box_color(rpm)

    # ===================================================================
    # Weitere Methoden
    # ===================================================================
    def _add_slider_label(self, left_text, right_text=""):
        row = BoxLayout(size_hint_y=None, height=dp_scaled(15))
        row.add_widget(Label(text=left_text, font_size=sp_scaled(20), color=(0.0, 0.85, 0.35, 0.75), halign="left"))
        lbl_right = Label(text=right_text, font_size=sp_scaled(20), color=(1,1,1,1), halign="right")
        row.add_widget(lbl_right)
        self.panel.add_widget(row)
        return lbl_right


    def _set_mode(self, mode):
        if self._locked:
            return
    
        # CHAOS = TOGGLE
        if mode == "chao":
            self._chaos_enabled = not self._chaos_enabled
        if mode == "night":
            self._night_reduction_enabled = not self._night_reduction_enabled
        # NUR echte Hauptmodi setzen
        elif mode in ("auto", "manual"):
            self._target_mode = mode

        self._last_user_action = time.time()
        self._user_active = True
    
        self._send_current_state()
    
        Clock.schedule_once(
            lambda dt: setattr(self, "_user_active", False),
            0.4
        )

    def _apply_button_styles(self, mode, chaos_active):
        base = (0.15, 0.15, 0.15, 1)
    
        # MANUAL
        self.btn_man.background_color = (0, 1, 0, 0.85) if mode == "manual" else base
    
        # AUTO
        self.btn_auto.background_color = (0, 0.7, 1, 0.85) if mode == "auto" else base
    
        # CHAOS
        self.btn_chao.background_color = (1, 0.5, 0, 0.85) if chaos_active else base
        self.btn_night.background_color = (0.4, 0.4, 1, 0.85) if self._night_reduction_enabled else base
        # 🔥 TEXT KONTRAST FIX (WICHTIG!)
        def fix(btn, active):
            btn.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)
    
        fix(self.btn_man, mode == "manual")
        fix(self.btn_auto, mode == "auto")
        fix(self.btn_chao, chaos_active)
        fix(self.btn_night, self._night_reduction_enabled)

    def _on_slider_change(self, *args):
        if not self._init_done or self._ui_lock or self._locked: 
            return
        self.lbl_val.text = f"{int(self.range_slider.min_value)}% - {int(self.range_slider.max_value)}%"
        self.sync_icon.color = (1, 0.5, 0, 1)

    def _on_env_slider_change(self, *args):
        if not self._init_done or self._ui_lock or self._locked: 
            return
        # .1f sorgt für die Anzeige einer Nachkommastelle
        # _on_env_slider_change()

        if config.get_temperature_unit().upper() == "F":
            t1 = self.temp_slider.min_value * 9 / 5 + 32
            t2 = self.temp_slider.max_value * 9 / 5 + 32
            self.lbl_temp.text = f"{t1:.1f} °F - {t2:.1f} °F"
        else:
            self.lbl_temp.text = f"{self.temp_slider.min_value:.1f} °C - {self.temp_slider.max_value:.1f} °C"

        self.lbl_hum.text = f"{int(self.hum_slider.min_value)}% - {int(self.hum_slider.max_value)}%"
        self.sync_icon.color = (1, 0.5, 0, 1)

    def _on_vpd_slider_change(self, *args):
        if not self._init_done or self._ui_lock or self._locked: 
            return

        self.lbl_vpd.text = (
            f"{self.vpd_slider.min_value / 10.0:.1f} kPa - "
            f"{self.vpd_slider.max_value / 10.0:.1f} kPa"
        )
        
        
        self.sync_icon.color = (1, 0.5, 0, 1)

    def _touch_down(self, instance, touch):
        if self._locked: return False
        if instance.collide_point(*touch.pos):
            self._user_active = True
            return False

    def _touch_up(self, instance, touch):
        if self._user_active:
            self._user_active = False
            self._last_user_action = time.time()
            self._send_current_state()          # User-Aktion → Retry-Zähler zurück
            return False



    # ===================================================================
    # UPDATE_UI (Idiotensicher & Target-Revision-Konform)
    # ===================================================================
    def update_ui(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        if not server_data:
            if self._init_done:
                self.sync_icon.text = "[font=FA]\uf071[/font]"
                self.sync_icon.color = (1, 0.3, 0, 1)
            return

        # === 1. REVISION & PASSIVE SESSION SNAPSHOT ===
        server_rev = int(server_data.get('rev_exhaust', 0))
        
        # === 2. AUTO-RETRY LOGIK ===
        pending = self.engine.is_pending(server_rev)
        
        if pending and self.engine.should_retry():
            if self.engine.retry_allowed():
                self.engine.register_retry()
                self._send_current_state(is_retry=True)
                return

        # === 3. LIVE-WERTE (immer aktuell) ===
        exhaust_fan_group = server_data.get('exhaust_fan', {})
        rpm = int(exhaust_fan_group.get('exhaust_fan_rpm', 0))
        
        self.lbl_rpm.text = f"RPM: {rpm}"
        self._update_box_color(rpm)
        self.lbl_live_speed.text = f"LIVE: {server_data.get('exhaust_fan_speed_now', 0)}%"    
        # ==========================================================
        # LIVE STATE REASON
        # ==========================================================
        reason = server_data.get("exhaust_fan_state_reason_1", "idle")
        reason2 = server_data.get("exhaust_fan_state_reason_2", "")
        
        pretty_reason = (
            reason
            .replace("_", " ")
            .upper()
        )
        
        self.lbl_reason1.text = pretty_reason
        self.lbl_reason2.text = "" if not reason2 else reason2.replace("_", " ").upper()
        # STATUS FARBEN
        if "FAILSAFE" in pretty_reason or "CRIT" in pretty_reason:
            self.lbl_reason1.color = (1, 0.2, 0.2, 1)
        
        elif "CHAOS" in pretty_reason:
            self.lbl_reason1.color = (1, 0.5, 0, 1)
        
        elif "VPD" in pretty_reason:
            self.lbl_reason1.color = (0.3, 1, 1, 1)
        
        elif "REFINED" in pretty_reason:
            self.lbl_reason1.color = (0.4, 1, 0.4, 1)
        
        elif "NIGHT" in pretty_reason:
            self.lbl_reason1.color = (0.6, 0.6, 1, 1)
        
        else:
            self.lbl_reason1.color = (1, 1, 1, 0.8)
        # === 4. ICON LOGIK (Status-Feedback) ===
        status = self.engine.get_status(
            server_rev,
            self._user_active,
            self._last_user_action
        )
        
        self._update_sync_icon(status)

        # === 5. UI-SYNC (Nur wenn nicht aktiv bedient) ===
        if status == "green" and not self._user_active:
            self._apply_server_snapshot(server_data)

    def _update_sync_icon(self, status):
        if status == "green":
            self.sync_icon.text = "[font=FA]\uf058[/font]"
            self.sync_icon.color = (0, 1, 0, 1)
        elif status == "retry":
            self.sync_icon.text = "[font=FA]\uf021[/font]"
            self.sync_icon.color = (1, 0.5, 0, 1)
        elif status == "error":
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)
        else:
            self._set_orange()

    def _set_orange(self):
        self.sync_icon.text = "[font=FA]\uf021[/font]"
        self.sync_icon.color = (1, 0.5, 0, 1)

    def _force_sync(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            return
    
        # =========================================================
        # 1. AKTUELLEN SERVER SNAPSHOT HOLEN
        # =========================================================
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)

        if not data:
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)
            return

        self._apply_server_snapshot(data)
    
        server_rev = int(data.get("rev_exhaust", 0))

        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
    
        # =========================================================
        # 2. AKTUELLEN UI STATE NOCHMAL PUSHEN
        # =========================================================
        Clock.schedule_once(
            lambda dt: self._send_current_state(),
            0.05
        )
    
        # =========================================================
        # 3. VISUELLES FEEDBACK
        # =========================================================
        self._set_orange()

    def _init_values(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        if not data:
            Clock.schedule_once(self._init_values, 0.1)
            return
        rpm = int(data.get('exhaust_fan', {}).get('exhaust_fan_rpm', 0))
        self._update_box_color(rpm)
        phase_idx = int(data.get("plant_phase", 0))
        phase_name = self._phase_map.get(phase_idx, "OFF")  
        server_rev = int(data.get('rev_exhaust', 0))
        
        # Werte einmalig laden
        self._apply_server_snapshot(data)
        
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
        self._init_done = True
        self.range_slider.disabled = False
        self._user_active = False
        self._last_user_action = 0
        self.sync_icon.text = "[font=FA]\uf058[/font]"
        self.sync_icon.color = (0, 1, 0, 1)

        if self._locked and self.lock_overlay and not self.lock_overlay.overlay:
            self.lock_overlay.create()
        self.opacity = 1
    


    def _on_unlock(self):
        self._locked = False
        for s in [self.range_slider, self.temp_slider, self.hum_slider, self.vpd_slider]:
            s.disabled = False
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
    
    def close(self):
        if hasattr(self, '_update_event') and self._update_event:
            self._update_event.cancel()
        if hasattr(self, '_sync_event') and self._sync_event:
            self._sync_event.cancel()
        if self.parent:
            self.parent.remove_widget(self)
        GLOBAL_STATE.ui_handler.active_exhaust_fan_overlay = None
