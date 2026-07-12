###############################################################################
# !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP !!!
# -----------------------------------------------------------------------------
# 1. KEINE DIREKTEN SCHALTVORGÄNGE...
###############################################################################

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.uix.image import Image
import config 
import time 
import json 
import os
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.unified_slider import UnifiedSlider
from dashboard_gui.overlays.lock_overlay import LockOverlay
from dashboard_gui.overlays.base_revision_system import BaseRevisionSystem
from dashboard_gui.ui.common.buttons.button_style_helper import ButtonStyleHelper
from dashboard_gui.ui.common.background_click_handler import BackgroundClickHandler
from kivy.uix.widget import Widget

ASSET_ROOT = os.path.join("dashboard_gui", "assets") 
CIRC_PIC_PATH = os.path.join(ASSET_ROOT, "hardware_pics", "mars_gaming.png")
class CirculationFanOverlay(FloatLayout, BoxColorUpdater, ButtonStyleHelper, BackgroundClickHandler):
    def __init__(self, parent_header, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0
        self.parent_header = parent_header
        self._pending_updates = {} 
        self._user_active = False 
        self._last_user_action = 0 
        self._init_done = False
        self.sync_path = os.path.join(config.DATA, "settings_sync.json")
        
        # === AUTO-RETRY MECHANISMUS ===
        self._last_sent_rev = 0
        self._last_send_time = 0
        self._retry_count = 0
        self._max_retries = 5

        self._update_event = Clock.schedule_interval(self.update_ui, 0.1)
        self.engine = BaseRevisionSystem()
        self._locked = True
        self._target_mode = "nat"
        self._ui_lock = False
        
        self._target_state = {"min": 20, "max": 65, "mode": "nat"}
        self.is_circulation = True
        
        # Hintergrund
        self.bg_btn = Button(background_color=(0, 0, 0, 0.25))
        self.bg_btn.bind(on_release=self._on_background_click)
        self.add_widget(self.bg_btn)

        # Panel
        self.panel = BoxLayout(
            orientation="vertical", 
            spacing=dp_scaled(10),
            size_hint=(None, None), 
            size=(dp_scaled(800), dp_scaled(500)), # <--- HÖHE BLEIBT 500
            padding=[dp_scaled(25), dp_scaled(15), dp_scaled(25), dp_scaled(25)], 
            # 'right': 0.98 hält es rechts.
            # 'y': 0.02 platziert es knapp über dem unteren Bildschirmrand,
            # wodurch es automatisch unter dem 45dp hohen Header rutscht.
            pos_hint={"right": 0.98, "y": 0.01} 
        )

        with self.panel.canvas.before:
        
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg_rect = RoundedRectangle(
                radius=[dp_scaled(20)]
            )
        
            self.glow_color = Color(
                0.0, 0.7, 1.0, 0.35
            )
            self.value_glow = Line(width=4)
        
            self.border_color = Color(
                0.0, 0.7, 1.0, 0.85
            )
            self.value_border = Line(width=2.5)

        self.panel.bind(pos=self._u, size=self._u)

        # 1. Titel + Sync Icon (Header)
        title_row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(5))
        self.lbl_title = Label(text="CIRCULATION FAN CONTROL", bold=True, color=(0, 1, 0, 1),
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

        # 2. KOMPAKTES BILD & DATEN LAYOUT
        top_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(180), spacing=dp_scaled(10))
        
        img_circ = Image(source=CIRC_PIC_PATH, 
                         size_hint=(None, 1), width=dp_scaled(180))
        top_container.add_widget(img_circ)
        
        mid_col = BoxLayout(orientation="vertical")
        self.lbl_val = Label(text="0% - 0%", font_size=sp_scaled(36), bold=True, halign="left", valign="middle")
        self.lbl_val.bind(size=self.lbl_val.setter('text_size'))
        self.lbl_reason = Label(text="", font_size=sp_scaled(20), halign="left", valign="middle")
        mid_col.add_widget(self.lbl_val)
        mid_col.add_widget(self.lbl_reason)
        top_container.add_widget(mid_col)
        
        right_col = BoxLayout(orientation="vertical")
        self.lbl_rpm = Label(text="RPM: 0", font_size=sp_scaled(22), color=(0.7, 0.7, 1, 0.8), halign="center", valign="middle")
        self.lbl_rpm.bind(size=self.lbl_rpm.setter('text_size'))
        self.lbl_live_speed = Label(text="LIVE: 0%", font_size=sp_scaled(22), bold=True, color=(0, 1, 1, 0.8), halign="center", valign="middle")
        self.lbl_live_speed.bind(size=self.lbl_live_speed.setter('text_size'))
        right_col.add_widget(self.lbl_rpm)
        right_col.add_widget(self.lbl_live_speed)
        top_container.add_widget(right_col)
        
        self.panel.add_widget(top_container)

        # 3. Slider Bereich
        self.panel.add_widget(Widget(size_hint_y=None, height=dp_scaled(10)))
        self.panel.add_widget(Label(text="SPEED RANGE (MIN - MAX)", font_size=sp_scaled(20), color=(0,1,0,0.5), 
                                  size_hint_y=None, height=dp_scaled(15)))
        
        self.range_slider = UnifiedSlider(min=0, max=100, mode='range', size_hint_y=None, height=dp_scaled(50))
        self.range_slider.bind(min_value=self._on_slider_change, max_value=self._on_slider_change,
                             on_touch_down=self._touch_down, on_touch_up=self._touch_up)
        self.panel.add_widget(self.range_slider)

        self.panel.add_widget(Widget())

        # 4. Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_man = self._create_styled_btn("MANUAL")
        self.btn_nat = self._create_styled_btn("NATURAL")
        self.btn_chao = self._create_styled_btn("CHAOTIC")
        btn_row.add_widget(self.btn_man)
        btn_row.add_widget(self.btn_nat)
        btn_row.add_widget(self.btn_chao)
        self.panel.add_widget(btn_row)

        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_nat.bind(on_release=lambda *_: self._set_mode("nat"))
        self.btn_chao.bind(on_release=lambda *_: self._set_mode("chao"))

        self.lock_overlay = LockOverlay(parent=self, panel=self.panel, unlock_callback=self._on_unlock)
        
        self.add_widget(self.panel)
        Clock.schedule_once(self._init_values, 0)

    # =========================================================================
    # AUTO-RETRY SEND LOGIK (zentralisiert)
    # =========================================================================
    def _send_current_state(self, is_retry=False, **kwargs):
        """Einheitliche Sende-Methode mit Retry-Unterstützung"""
        if not self._init_done:
            return

        mode = kwargs.get("mode", self._target_state["mode"])

        new_rev = GLOBAL_STATE.send_overlay_command(
            "circulation_fan",
            min=int(self.range_slider.min_value),
            max=int(self.range_slider.max_value),
            mode=mode
        )

        if new_rev:
            self.engine.mark_sent(new_rev)
            self._last_sent_rev = new_rev   # BACKWARD SAFE (noch behalten!)
            self._last_send_time = time.time()
        
            self._set_orange()
        
            if not is_retry:
                self.engine.reset_retry()


    # =========================================================================
    # UPDATE_UI mit starkem Auto-Retry
    # =========================================================================
    def update_ui(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
        if not server_data:
            if self._init_done:
                self.sync_icon.text = "[font=FA]\uf071[/font]"
                self.sync_icon.color = (1, 0.3, 0, 1)
            return
        
        # === 1. REVISION & PASSIVE SESSION SNAPSHOT ===
        server_rev = int(server_data.get('rev_circfan', 0))

        # === 2. STATUS ANALYSE ===
        pending = self.engine.is_pending(server_rev)
        
        if pending and self.engine.should_retry():
            if self.engine.retry_allowed():
                self.engine.register_retry()
                self._send_current_state(is_retry=True)
                return
        
        # Live-Werte immer anzeigen

        self.lbl_live_speed.text = f"LIVE: {server_data.get('circulation_fan_speed_now', 0)}%"
        self.lbl_rpm.text = f"RPM: {server_data.get('circulation_fan', {}).get('circulation_fan_rpm', 0)}"      
        rpm = int(server_data.get('circulation_fan', {}).get('circulation_fan_rpm', 0))
        self._update_box_color(rpm)     

        # === 4. ICON LOGIK (Der ehrliche Status) ===
        status = self.engine.get_status(
            server_rev,
            self._user_active,
            self._last_user_action
        )
                
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
            self.sync_icon.text = "[font=FA]\uf021[/font]"
            self.sync_icon.color = (1, 0.5, 0, 1)
        
        if status != "green":
            return

        # UI-Werte vom ESP übernehmen (nur wenn User gerade nicht schiebt)
        if not self._user_active:
            self._ui_lock = True
            self.range_slider.min_value = int(server_data.get('circulation_fan_min', 20))
            self.range_slider.max_value = int(server_data.get('circulation_fan_pct', 65))
            self._ui_lock = False
            self.lbl_val.text = f"{int(self.range_slider.min_value)}% - {int(self.range_slider.max_value)}%"
            self._target_state["mode"] = server_data.get(
                'circulation_fan_mode',
                'nat'
            )
            self._apply_button_styles(server_data.get('circulation_fan_mode', 'nat'))

    def _on_slider_change(self, instance, value):
        if not self._init_done or self._ui_lock: 
            return
        min_v = int(self.range_slider.min_value)
        max_v = int(self.range_slider.max_value)
        self.lbl_val.text = f"{min_v}% - {max_v}%"
        self._target_state["min"] = min_v
        self._target_state["max"] = max_v
        self._set_orange()

    def _set_mode(self, mode):
        if self._locked: 
            return
        self._target_state["mode"] = mode
        self._send_current_state()          # User-Aktion → is_retry=False

    def _touch_up(self, instance, touch):
        if self._locked or not self._user_active:
            return False
        self._user_active = False
        self._last_user_action = time.time()
        self._send_current_state()          # User-Aktion
        return False

    def _touch_down(self, instance, touch):
        if self._locked:
            return False
        if instance.collide_point(*touch.pos):
            self._user_active = True
            return False

    def _force_sync(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            return
    
        # =========================================================
        # 1. FRISCHEN SERVER SNAPSHOT HOLEN
        # =========================================================
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)

        if not data:
            self.sync_icon.text = "[font=FA]\uf071[/font]"
            self.sync_icon.color = (1, 0.3, 0, 1)
            return
    
        server_rev = int(data.get("rev_circfan", 0))
        srv_min = data.get("circulation_fan_min", 20)
        srv_max = data.get("circulation_fan_pct", 65)
        srv_mode = data.get("circulation_fan_mode", "nat")
    
        self._ui_lock = True
        self.range_slider.min_value = srv_min
        self.range_slider.max_value = srv_max
        self._ui_lock = False
    
        self._target_state["mode"] = srv_mode
    
        self.lbl_val.text = f"{int(srv_min)}% - {int(srv_max)}%"
    
        self._apply_button_styles(srv_mode)
    
        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)
    
        # =========================================================
        # 2. STATE ERNEUT PUSHEN
        # =========================================================
        Clock.schedule_once(
            lambda dt: self._send_current_state(),
            0.05
        )
    
        # =========================================================
        # 3. FEEDBACK
        # =========================================================
        self._set_orange()

    def _set_orange(self):
        self.sync_icon.text = "[font=FA]\uf021[/font]"
        self.sync_icon.color = (1, 0.5, 0, 1)

    # Rest bleibt fast unverändert (nur kleine Cleanups)


    def _apply_button_styles(self, mode):
    
        base = (0.15, 0.15, 0.15, 1)
    
        # MANUAL
        self.btn_man.background_color = (0, 1, 0, 0.85) if mode == "manual" else base
    
        # NATURAL
        self.btn_nat.background_color = (0, 0.6, 1, 0.85) if mode == "nat" else base
    
        # CHAOS
        self.btn_chao.background_color = (1, 0.5, 0, 0.85) if mode == "chao" else base
    
        # 🔥 KONTRAST FIX (wie Exhaust)
        def fix(btn, active):
            btn.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)
    
        fix(self.btn_man, mode == "manual")
        fix(self.btn_nat, mode == "nat")
        fix(self.btn_chao, mode == "chao")


    def _init_values(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)

        if not data:
            Clock.schedule_once(self._init_values, 0.1)
            return

        # =========================
        # 🔥 1. SERVER STATE ÜBERNEHMEN (OHNE HANDSHAKE)
        # =========================
        server_rev = int(data.get('rev_circfan', 0))

        self._last_sent_rev = server_rev
        self.engine.mark_confirmed_snapshot(server_rev)

        # 🔥 GANZ WICHTIG: Session einfach übernehmen

        # =========================
        # 🔥 2. UI SAUBER SETZEN (LOCKED)
        # =========================
        srv_min = int(data.get("circulation_fan_min", 20))
        srv_max = int(data.get("circulation_fan_pct", 65))
        srv_mode = data.get("circulation_fan_mode", "nat")
        rpm = data.get("circulation_fan", {}).get("circulation_fan_rpm")

        if rpm is None:
            rpm = 0
        else:
            rpm = int(rpm)

        self._ui_lock = True
        self.range_slider.min_value = srv_min
        self.range_slider.max_value = srv_max
        self._ui_lock = False

        self.lbl_val.text = f"{srv_min}% - {srv_max}%"
        self._target_state["mode"] = srv_mode

        self._apply_button_styles(srv_mode)
        self._update_box_color(rpm)

        # =========================
        # 🔥 3. STATE RESET (WICHTIG)
        # =========================
        self._retry_count = 0
        self._last_send_time = 0
        self._user_active = False
        self._last_user_action = 0
        self.sync_icon.text = "[font=FA]\uf058[/font]"
        self.sync_icon.color = (0, 1, 0, 1)

        # =========================
        # 🔥 4. SYSTEM FREIGEBEN
        # =========================
        self._init_done = True
        self.range_slider.disabled = False

        if self._locked and self.lock_overlay and not self.lock_overlay.overlay:
            self.lock_overlay.create()
        self.opacity = 1

    def _on_unlock(self):
        self._locked = False
        self.range_slider.disabled = False

    def _u(self, *_):
    
        if not hasattr(self, "bg_rect"):
            return
    
        pos = self.panel.pos
        size = self.panel.size
    
        self.bg_rect.pos = pos
        self.bg_rect.size = size
    
        rect = (
            pos[0],
            pos[1],
            size[0],
            size[1],
            dp_scaled(20)
        )
    
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    def close(self):
        if self._update_event: self._update_event.cancel()
        if self.parent: self.parent.remove_widget(self)
        GLOBAL_STATE.ui_handler.active_circulation_fan_overlay = None
