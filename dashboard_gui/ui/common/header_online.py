# dashboard_gui/ui/common/header_online.py

import time
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle, Ellipse, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.metrics import dp, sp
import config
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.window_picker import WindowPicker
from dashboard_gui.ui.common.device_picker_menu import DevicePickerMenu
from dashboard_gui.ui.common.signal_inspector.signal_inspector import SignalInspector
from dashboard_gui.ui.common.icons.broadcast_button import BroadcastButton
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.icons.circulation_fan_control import CirculationFanControl
from dashboard_gui.ui.common.icons.exhaust_fan_control import ExhaustFanControl  # <--- NEU
from dashboard_gui.ui.common.icons.light_control import LightControl
from dashboard_gui.ui.common.icons.signal_bars import SignalBars
from dashboard_gui.ui.common.icons.led_circle import LEDCircle
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.common.icons.battery_icon import BatteryIcon
from dashboard_gui.ui.common.icons.external_icon import ExternalIcon
from dashboard_gui.ui.common.icons.external2_icon import External2Icon
from dashboard_gui.ui.common.icons.push_message_icon import PushMessageIcon
from dashboard_gui.ui.common.icons.climate_hub_control import ClimateHubControl
from dashboard_gui.ui.common.icons.inactive_items_icon import InactiveItemsIcon
from dashboard_gui.circulation_fan_registry import fan_snapshot


#--------------------------------------------------------
# HEADER BAR
# -------------------------------------------------------
class HeaderBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        self.gsm = GLOBAL_STATE
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp_scaled(45)   # Etwas höher für besseres Layout
        self.spacing = dp_scaled(10)   # Kleineres Spacing für kompaktere Icons
        # Minimal Padding, Icon-Heavy Design
        self.padding = [dp_scaled(6), dp_scaled(2), dp_scaled(6), dp_scaled(2)]
        self._signal_overlay = None
        self._signal_update_event = None
        with self.canvas.before:
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._u_bg, size=self._u_bg)
        self._last_frame = {}
        
        
        ########### STATE DICT FÜR ALLE WICHTIGEN DATEN, DIE DER HEADER DARSTELLT ALLES Hier REIN, keine Eigenwege
        self._state = {
            "rssi": None,
            "battery": None,
            "light": None,
            "external": False,
            "external2": False,
            "led_alive": False,
            "led_status": "offline",
            "circulation_fan_rpm": None,
            "circulation_fans": {},
            "exhaust_fan_rpm": None,
            "climate_hub": False,
            "broadcast": False
        }        
        
        # BACK BUTTON (stabil, bleibt rechts)
        self.btn_back = Button(
            text="\uf060",
            font_name="FA",
            size_hint=(None, 1),
            width=dp_scaled(70),
            background_color=(0.22, 0.25, 0.30, 0.9),
            color=(0.95, 0.95, 0.98, 1),
            font_size=sp_scaled(22),
            opacity=0.7,
            disabled=True,
        )
        self.btn_back.bind(on_release=lambda *_: self._go_back())

        self.btn_forward = Button(
            text="\uf061",  # FontAwesome arrow-right
            font_name="FA",
            size_hint=(None, 1),
            width=dp_scaled(70),
            background_color=(0.22, 0.25, 0.30, 0.9),
            color=(0.95, 0.95, 0.98, 1),
            font_size=sp_scaled(22),
            opacity=0.7,
            disabled=True,
        )

        self.btn_forward.bind(
            on_release=lambda *_: self._go_forward()
)
        
        # LOGO - Fixed Width, nicht proportional
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png")
        self.device_icon = Image(
            source=logo_path,
            size_hint=(None, 1),
            width=dp_scaled(50),  # Fixed, nicht fluid
            fit_mode="contain",
            keep_ratio=True,
            pos_hint={'center_y': 0.5}
        )
        
        # NEU: Touch-Event abfangen für Home-Button Funktion
        self.device_icon.bind(on_touch_down=self._on_logo_click)
        

        # DEVICE NAME - Klickbar, Flexible Breite (SPACER)
        self.lbl_dev = Button(
            text="---",
            markup=True,
            font_size=sp_scaled(16),
            size_hint=(1, 1),      # Flexible Mitte
            width=dp_scaled(170),  # Anfangsbreite für Device Name mit Channel
            background_color=(0, 0, 0, 0),
            color=(0.95, 0.95, 0.98, 1),
            halign="left",
            valign="middle",
            padding=(dp_scaled(3), 0),
            shorten=True,
            shorten_from='right',
            text_size=(dp_scaled(170), None),  # Text passt in feste Breite, nicht zweizeilig
        )
        self.lbl_dev.bind(size=lambda instance, _: setattr(instance, 'text_size', (instance.width, instance.height)))
        self.lbl_dev.bind(on_release=lambda *_: self._open_device_menu())
        
        # --- ICONS SECTION (Rechts, alle Fixed Width) ---
        # Signalstärke
        self.signal = SignalBars(size_hint=(None, 1))
        self.signal.width = dp_scaled(40)  # Gleichmäßige Breite
        self.signal.bind(on_touch_down=self._signal_click)
        
        # Externer Sensor
        self.external = ExternalIcon(size_hint=(None, 1))
        self.external.width = dp_scaled(75)  # Gleichmäßige Breite

        # Externer2 Sensor
        self.external2 = External2Icon(size_hint=(None, 1))
        self.external2.width = dp_scaled(75)  # Gleichmäßige Breite

        # Circulation Fan
        self.circulation_fans = {
            fan_id: CirculationFanControl(parent_header=self, fan_id=fan_id, size_hint=(None, 1), width=dp_scaled(40))
            for fan_id in (1, 2, 3)
        }
        self.circulation_fan = self.circulation_fans[1]  # Rückwärtskompatibilität
        
        # Exhaust Fan
        self.exhaust_fan = ExhaustFanControl(
            parent_header=self,
            size_hint=(None, 1),
            width=dp_scaled(40)  # Gleichmäßige Breite
        )
        
        # Light Control
        self.light = LightControl(
            parent_header=self,
            size_hint=(None, 1),
            width=dp_scaled(40)  # Gleichmäßige Breite
        )
        # Push Message Icon
        self.push_message = PushMessageIcon(
            size_hint=(None, 1),
            width=dp_scaled(40)
        )

        # Climate Hub Icon
        self.climate_hub = ClimateHubControl(
            parent_header=self,
            size_hint=(None, 1),
            width=dp_scaled(40)
        )

        # Inactive Devices Icon
        self.inactive_devices = InactiveItemsIcon(size_hint=(None, 1))
        self.inactive_devices.width = dp_scaled(40)


        # Battery
        self.battery = BatteryIcon(size_hint=(None, 1))
        self.battery.width = dp_scaled(70)  # Gleichmäßige Breite
        
        # LED Status
        self.led = LEDCircle(size_hint=(None, 1))
        self.led.width = dp_scaled(40)  # Gleichmäßige Breite
        
        # Broadcast Button
        self.btn_broadcast = BroadcastButton(
            text="\uf09e",
            font_name="FA",
            size_hint=(None, 1),
            width=dp_scaled(40),  # Gleichmäßige Breite
            background_color=(0, 0, 0, 0),
            color=(0.7, 0.7, 0.7, 1),
            font_size=sp_scaled(18)
        )
        self.capability_widgets = {
            "light": self.light, "exhaust_fan": self.exhaust_fan, "broadcast": self.btn_broadcast,
            "battery": self.battery, "external": self.external, "external2": self.external2,
            "climate_hub": self.climate_hub, "push_message": self.push_message,
            **{f"circulation_fan_{fan_id}": widget for fan_id, widget in self.circulation_fans.items()},
        }
        
        # Clock
        self.lbl_clock = Label(
            text="--:--",
            font_size=sp_scaled(16),
            size_hint=(None, 1),
            width=dp_scaled(40)  # Gleichmäßige Breite
        )
        Clock.schedule_interval(self._update_clock, 1)

        # MENU BUTTON (Links neben Back)
        self.btn_menu = Button(
            text="\uf0c9",
            font_name="FA",
            size_hint=(None, 1),
            width=dp_scaled(40),  # Gleichmäßige Breite
            background_color=(0.22, 0.25, 0.30, 0.9),
            color=(0.95, 0.95, 0.98, 1),
            font_size=sp_scaled(22)
        )
        self.btn_menu.bind(on_release=lambda *_: self._open_menu())

        # ASSEMBLY - EDGE-LOCK + FLEX-CENTER SYSTEM
        # --- ASSEMBLY (DYNAMISCH NACH PLATTFORM) ---
        from platform_utils import is_android

        if is_android():
            # Perfekt für den linken Daumen: Zurück-Button ganz links
            self.add_widget(self.btn_back)
            self.add_widget(self.device_icon)
        else:
            self.add_widget(self.device_icon)

        # Mitte bleibt flexibel
        self.center_zone = BoxLayout(size_hint=(1, 1), spacing=dp_scaled(6))
        self.lbl_dev.size_hint = (1, 1)
        self.lbl_dev.width = dp_scaled(170)
        self.center_zone.add_widget(self.lbl_dev)
        self.add_widget(self.center_zone)

        # Status Icons rechts
        self.add_widget(self.signal)
        self.add_widget(self.push_message)
        
        self.add_widget(self.climate_hub)
        self.add_widget(self.light)
        for fan in self.circulation_fans.values():
            self.add_widget(fan)
        self.add_widget(self.exhaust_fan)
        self.add_widget(self.btn_broadcast)
        self.add_widget(self.led)
        self.add_widget(self.external)
        self.add_widget(self.external2)
        self.add_widget(self.battery)
        self.add_widget(self.lbl_clock)
        self.add_widget(self.inactive_devices)


        if is_android():
            # Perfekt für den rechten Daumen: Menü und Vorwärts ganz rechts außen
            self.add_widget(self.btn_menu)
            self.add_widget(self.btn_forward)
        else:
            # Desktop bleibt klassisch kompakt
            self.add_widget(self.btn_back)
            self.add_widget(self.btn_menu)
            self.add_widget(self.btn_forward)

        self._responsive_items = [
            (self.lbl_clock, 4),
            (self.btn_broadcast, 4),
            (self.battery, 3),
            (self.light, 3),
            (self.exhaust_fan, 3),
            (self.circulation_fan, 3),
            (self.external, 2),
            (self.external2, 2),
            (self.inactive_devices, 2),
            (self.push_message, 2),
            (self.climate_hub, 2)
        ]
        self._responsive_defaults = {}
        for widget, _ in self._responsive_items:
            self._responsive_defaults[widget] = {
                'width': widget.width,
                'size_hint_x': widget.size_hint_x,
            }

        self.bind(width=self._on_width)
        self._on_width()

        self._menu_overlay = None
        self.device_menu = None




    def _apply_state(self):
        s = self._state
    
        self.signal.set_rssi(s["rssi"])
        self.battery.set_voltage(s["battery"])
        self.light.set_brightness(s["light"])
    
        self.external.set_external(s["external"])
        self.external2.set_external2(s["external2"])
        self.led.set_state(s["led_alive"], s["led_status"])
            # 🔥 FANS FIX
        for fan_id, widget in self.circulation_fans.items():
            widget.set_rpm(s["circulation_fans"].get(fan_id, {}).get("rpm"))
        self.exhaust_fan.set_rpm(s["exhaust_fan_rpm"])
    
    
    # ---------------------------------------------------
    # Back Button Control
    # ---------------------------------------------------
    def update_navigation_buttons(self):

        ui = self.gsm.ui_handler

        # BACK
        if ui.can_go_back():
            self.btn_back.disabled = False
            self.btn_back.opacity = 1
        else:
            self.btn_back.disabled = True
            self.btn_back.opacity = 0.7

        # FORWARD
        if ui.can_go_forward():
            self.btn_forward.disabled = False
            self.btn_forward.opacity = 1
        else:
            self.btn_forward.disabled = True
            self.btn_forward.opacity = 0.7

    def _go_forward(self, *_):
        self.gsm.ui_handler.go_forward()

    def _go_back(self, *_):
        # REIN ÜBER DEN UIMANAGER – Kein hartcodiertes "_back_target" mehr!
        self.gsm.ui_handler.go_back()


    def _on_logo_click(self, widget, touch):
        if widget.collide_point(*touch.pos):
            # Nutzt die bestehende Engine, die bei "dashboard" 
            # automatisch die Stacks säubert und Schleifen verhindert.
            self.gsm.ui_handler.goto("dashboard")
            return True
        return False

    def _set_responsive_widget(self, widget, visible):
        defaults = self._responsive_defaults.get(widget, {})
        if visible:
            widget.opacity = 1
            widget.disabled = False
            widget.size_hint_x = defaults.get('size_hint_x', None)
            if defaults.get('width') is not None:
                widget.width = defaults['width']
        else:
            widget.opacity = 0
            widget.disabled = True
            widget.size_hint_x = None
            widget.width = 0

    def _on_width(self, *_):
        width = self.width or Window.width
        hide_priority4 = width < dp_scaled(520)
        hide_priority3 = width < dp_scaled(470)
        hide_priority2 = width < dp_scaled(400)

        for widget, priority in self._responsive_items:
            if priority == 4:
                self._set_responsive_widget(widget, not hide_priority4)
            elif priority == 3:
                self._set_responsive_widget(widget, not hide_priority3)
            elif priority == 2:
                self._set_responsive_widget(widget, not hide_priority2)
            else:
                self._set_responsive_widget(widget, True)



    def enable_back(self, target="dashboard"):
        self.btn_back.opacity = 1
        self.btn_back.disabled = False
        self.btn_back.width = dp_scaled(70)
        self._back_target = target

    def _signal_click(self, widget, touch):
        if not widget.collide_point(*touch.pos):
            return False
    
        # Wir fragen den globalen UI-Manager
        ui = self.gsm.ui_handler
        
        if ui.active_inspector:
            ui.close_signal_inspector()
        else:
            ui.open_signal_inspector(parent_header=self)
    
        return True




    def _close_signal_overlay(self):
        """Falls extern geschlossen werden muss"""
        if self._signal_overlay:
            self._signal_overlay.close()


    # ---------------------------------------------------
    # Menu overlay
    # ---------------------------------------------------
    def _open_device_menu(self):
        if getattr(self, "_device_menu", None):
            self._device_menu.close()
            return
    
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        from dashboard_gui.ui.common.device_picker_menu import DevicePickerMenu
    
        device_list = GLOBAL_STATE.get_device_list()
    
        menu = DevicePickerMenu(
            parent_header=self,
            device_list=device_list,
            on_select_device=lambda idx: GLOBAL_STATE.set_active_index(idx)
        )
    
        self._device_menu = menu
    
        # nur EIN add_widget, NICHT zweimal!
        App.get_running_app().root.current_screen.add_widget(menu)

    # Window Picker Menü ----------------
    def _open_menu(self):
        # Falls Menü schon offen ist, nichts tun
        if getattr(self, "_menu_overlay", None):
            return
    
        # WindowPicker erzeugen, HeaderBar als Referenz optional übergeben
        picker = WindowPicker(parent_header=self)
    
        # Overlay speichern, damit wir später schließen können
        self._menu_overlay = picker
    
        # Picker zum Screen hinzufügen
        screen = self.parent.parent
        screen.add_widget(picker)


    # ---------------------------------------------------
    # ONE ENTRY-POINT FOR ALL SCREENS
    # ---------------------------------------------------
    def update_from_global(self, frame):
    
        if not isinstance(frame, dict) or not frame:
            return
    
        web_ch = frame.get("webserver", {})
        
        
        fan_states = {fan_id: fan_snapshot(web_ch, fan_id) for fan_id in (1, 2, 3)}
        circ_data = web_ch.get("circulation_fan", {})
        exh_data = web_ch.get("exhaust_fan", {})

        self._state["circulation_fan_rpm"] = circ_data.get("circulation_fan_rpm")
        self._state["circulation_fans"] = fan_states
        self._state["exhaust_fan_rpm"] = exh_data.get("exhaust_fan_rpm")

        
        health = frame.get("health", {})
        ch_name = frame.get("channel", "adv")
        selected_channel = frame.get(ch_name, {})
    
        # DEVICE LABEL bleibt wie es ist
        mac = frame.get("device_id")
        label = GLOBAL_STATE.get_device_label(mac) if mac else "---"
        tag = "WEB" if ch_name == "webserver" else ch_name.upper()
        self.lbl_dev.text = f"[font=FA]\uf2c7[/font]  {label} [color=777777]· {tag}[/color]"
    
        # ----------------------------
        # STATE ONLY (KEIN UI LOGIK MEHR)
        # ----------------------------
        self._state["rssi"] = health.get("signal", {}).get("rssi")
    
        self._state["battery"] = (
            health.get("battery", {}).get("voltage")
            or web_ch.get("battery_voltage")
        )
    
        self._state["light"] = web_ch.get("light_pct")
    
        ext_present = False

        for ch in ("adv", "gatt", "webserver"):
            ch_data = frame.get(ch, {})
            ext_present |= bool(
                ch_data.get("external", {}).get("present", False)
            )

        self._state["external"] = ext_present
  
        self._state["external2"] = bool(
            health.get("external2", {}).get("present")
            or web_ch.get("external2", {}).get("present", False)
        )
        # The root frame describes whether *any* transport is alive.  The
        # header LED, however, represents the currently selected channel.
        # Using the root state made a disconnected GATT channel appear green
        # whenever ADV or Webserver was online.
        self._state["led_alive"] = bool(selected_channel.get("alive", False))
        self._state["led_status"] = selected_channel.get("status", "offline")
    
        # EIN EINZIGER APPLY
        self._apply_state()
        # Climate hub presence
        self._state["climate_hub"] = bool(frame.get("climate_hub") or web_ch.get("climate_hub", False))
        try:
            self.climate_hub.set_active(self._state["climate_hub"])
        except Exception:
            pass
        self._last_frame = frame.copy()          # <--- WICHTIG

        status = GLOBAL_STATE.broadcast_engine.get_status()
        self._state["broadcast_available"] = status.get("available")

    # === Channel korrekt setzen ===
        active_channel = GLOBAL_STATE.get_active_channel() or "webserver"  # Default sinnvoll
        frame_with_channel = self._last_frame.copy()
        frame_with_channel["channel"] = active_channel
        self._last_frame = frame_with_channel
        self.push_message.update_from_frame(frame)
        # Update inactive items icon
        self.inactive_devices.update_from_header(self)
        self._update_clock()



    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------
    def _u_bg(self, *_):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def _update_clock(self, *_):
        self.lbl_clock.text = time.strftime("%H:%M")

    def _short_dev(self, dev):
        if not dev: return "---"
        p = dev.split(":")
        return f"{p[0]}:{p[1]} … {p[-1]}" if len(p) == 6 else dev

 
    def set_led(self, d):
        self.led.set_state(d.get("alive", False), d.get("status", "offline"))



    def set_external(self, present):
        self.external.set_external(bool(present))

    def set_rssi(self, rssi):
        self.signal.set_rssi(rssi)



    def set_clock(self, hhmmss):
        self.lbl_clock.text = hhmmss
