# 
import os
import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.graphics import Rectangle, Color
from kivy.clock import Clock
from kivy.metrics import dp
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.grow_controller_content.controller_wifi_settings import WifiSettingsOverlay
from dashboard_gui.ui.grow_controller_content.controller_user_password_settings import UserPasswordSettingsOverlay
from dashboard_gui.ui.grow_controller_content.controller_bluetooth_settings import BluetoothSettingsOverlay
from dashboard_gui.ui.grow_controller_content.controller_gpio_settings import GpioSettingsPanel
from dashboard_gui.ui.grow_controller_content.controller_ota_settings import OtaSettingsOverlay
from dashboard_gui.ui.grow_controller_content.alternative_gpio_settings import AlternativeGpioSettings
from dashboard_gui.ui.grow_controller_content.controller_command_status_popup import GrowCommandStatusPopup
from dashboard_gui.overlays.infrastructure.revision_session import RevisionSession

ASSET_ROOT = os.path.join("dashboard_gui", "assets")


class GrowControllerScreen(Screen):
    name = "grow_controller"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        GLOBAL_STATE.ui_handler.attach_screen("grow_controller", self)
        
        self.root = BoxLayout(orientation="vertical")
        self.labels = {}  
        self.live_gpios = {}  
        self.engine = RevisionSession()
        
        self._init_done = True
        self._last_sent_rev = 0
        self._last_send_time = 0
        self._retry_count = 0
        self._max_retries = 5
        self._last_grow_payload = None
        self._last_action_context = None
        self._reset_after_ack = False
        self._status_popup_after_ack = False
        self._reset_burst_scheduled = False
        self.gpio_panel = None # Referenz für gezielte Updates
        # Reboot / popup flags
        self.reboot_required = False
        self._reboot_popup_shown = False

        # Hintergrund
        with self.root.canvas.before:
            Color(0, 0, 0, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            Color(1, 1, 1, 0.6) 
            self.bg_image = Rectangle(
                source=os.path.join(ASSET_ROOT, "background2.png"),
                pos=self.pos, size=self.size
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.header = HeaderBar()
        self.root.add_widget(self.header)
        # BLE status flags (will be populated from device status)
        self.ble_bridge_enabled = True
        self.ble_scan_enabled = True

        # Einmalig initialisieren
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.body = BoxLayout(orientation='vertical', size_hint_y=1, padding=dp_scaled(20))
        self.scroll.add_widget(self.body)
        self.root.add_widget(self.scroll)
        self.add_widget(self.root)

        Clock.schedule_once(self.build_ui, 0.1)
        Clock.schedule_interval(self._check_sync_status, 1.0)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.bg_image.pos = self.pos
        self.bg_image.size = self.size

    def build_ui(self, *_):
        # UI nur aufbauen, wenn noch nicht geschehen
        self.body.clear_widgets()

        # Erstelle das Panel einmalig und halte die Referenz
        self.gpio_panel = GpioSettingsPanel(screen=self, embedded=True)
        self.gpio_panel.update_from_live_gpios(self.live_gpios)
        self.body.add_widget(self.gpio_panel)

        if hasattr(self, 'footer_layout') and self.footer_layout in self.root.children:
            self.root.remove_widget(self.footer_layout)

        self.footer_layout = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(130),
            padding=[dp_scaled(20), dp_scaled(10), dp_scaled(20), dp_scaled(20)],
            spacing=dp_scaled(10)
        )

        btn_grid = GridLayout(cols=7, spacing=dp_scaled(12), size_hint_y=1)

        buttons = [
            ("[font=FA]\uf021[/font]\nSOFT RESET", self.soft_reset),
            ("[font=FA]\uf017[/font]\nSYNC CLOCK", self.sync_time),
            ("[font=FA]\uf042[/font]\nBLE SETTINGS", self.open_bluetooth_settings),
            ("[font=FA]\uf041[/font]\nUSER & PASSWORD", self.open_security_settings),
            ("[font=FA]\uf1eb[/font]\nSET WIFI", self.open_wifi_settings),
            ("[font=FA]\uf0c8[/font]\nTEST REV", self.test_rev),
            ("[font=FA]\uf5fd[/font]\nPIN MATRIX", self.open_alternative_gpio_settings),
            ("AP MODE", self.set_ap_mode),
            ("ROUTER MODE", self.set_sta_mode),
            ("[font=FA]\uf019[/font]\nOTA UPDATE", self.open_ota_settings), # NEUER BUTTON

        ]

        for text, callback in buttons:
            btn = GlassButton(text=text, markup=True, on_release=callback, halign="center")
            btn_grid.add_widget(btn)

        # BLE Bridge and Scanner toggles (independent)
        self.bridge_btn_footer = GlassButton(text=f"Bridge: {'ON' if self.ble_bridge_enabled else 'OFF'}", font_size=sp_scaled(14))
        self.bridge_btn_footer.bind(on_release=self.toggle_ble_bridge)
        btn_grid.add_widget(self.bridge_btn_footer)

        self.scan_btn_footer = GlassButton(text=f"Scanner: {'ON' if self.ble_scan_enabled else 'OFF'}", font_size=sp_scaled(14))
        self.scan_btn_footer.bind(on_release=self.toggle_ble_scan)
        btn_grid.add_widget(self.scan_btn_footer)

        f_reset = GlassButton(text="[font=FA]\uf1f8[/font]\nFACTORY", markup=True, on_release=self.factory_reset, halign="center")
        f_reset.color = (1, 0.25, 0.25, 1)
        btn_grid.add_widget(f_reset)

        self.footer_layout.add_widget(btn_grid)
        self.root.add_widget(self.footer_layout)


    def _send_grow_payload(
        self,
        payload,
        is_retry=False,
        context=None,
        reset_after_ack=True,
        show_status=True
    ):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            print("[GrowController] Fehler: Keine MAC-Adresse gefunden!")
            return None

        self._last_grow_payload = dict(payload)
        self._last_action_context = context
        self._reset_after_ack = bool(reset_after_ack)
        self._status_popup_after_ack = bool(show_status)

        new_rev = GLOBAL_STATE.send_overlay_command("grow_controller", **payload)
        if new_rev:
            self.engine.mark_sent(new_rev)
            self._last_sent_rev = new_rev  # backward safe fuer alte Screen-Checks
            self._last_send_time = time.time()
            if not is_retry:
                self.engine.reset_retry()
                self._retry_count = 0
        return new_rev

    def _retry_last_grow_payload(self):
        if not self._last_grow_payload:
            return
        self._send_grow_payload(
            self._last_grow_payload,
            is_retry=True,
            context=self._last_action_context,
            reset_after_ack=self._reset_after_ack,
            show_status=self._status_popup_after_ack
        )

    def _send_command(self, command_name):
        if command_name in ("soft_reset", "factory_reset"):
            self._schedule_reset_burst(command_name)
            return

        self._send_grow_payload(
            {"command": command_name},
            context=f"command:{command_name}",
            reset_after_ack=False,
            show_status=True
        )

    def _schedule_reset_burst(
        self,
        command_name="soft_reset",
        repeats=4,
        interval=0.9,
        show_popup=True,
        popup_title="Reset gesendet"
    ):
        if self._reset_burst_scheduled and command_name == "soft_reset":
            return

        self._reset_burst_scheduled = True
        if show_popup:
            GrowCommandStatusPopup.show(
                reset_sent=True,
                title=popup_title
            )

        def fire_reset(index):
            mac = GLOBAL_STATE.get_active_device_id()
            if not mac:
                return
            try:
                print(f"[GrowController] Fire-and-forget reset {index + 1}/{repeats}: {command_name}")
            except Exception:
                pass
            GLOBAL_STATE.send_overlay_command(
                "grow_controller",
                command=command_name
            )

        def clear_flag(*_):
            self._reset_burst_scheduled = False

        for index in range(repeats):
            Clock.schedule_once(lambda dt, i=index: fire_reset(i), index * interval)

        Clock.schedule_once(clear_flag, repeats * interval + 0.2)

    def _schedule_reset_after_ack(self):
        self._reset_after_ack = False
        self._reboot_popup_shown = True
        try:
            if hasattr(self, 'reboot_action_box') and self.reboot_action_box in self.footer_layout.children:
                self.footer_layout.remove_widget(self.reboot_action_box)
        except Exception:
            pass
        self._schedule_reset_burst("soft_reset", show_popup=False)
        if self._status_popup_after_ack:
            GrowCommandStatusPopup.show(
                reset_sent=True,
                title="Befehl bestätigt"
            )
        self._status_popup_after_ack = False

    def close_gpio_settings(self):
        if hasattr(self, 'gpio_overlay') and self.gpio_overlay in self.children:
            self.remove_widget(self.gpio_overlay)

    def open_wifi_settings(self, *_):
        if hasattr(self, 'wifi_overlay') and self.wifi_overlay in self.children:
            return
        self.wifi_overlay = WifiSettingsOverlay(screen=self)
        self.add_widget(self.wifi_overlay)

    def close_wifi_settings(self):
        if hasattr(self, 'wifi_overlay') and self.wifi_overlay in self.children:
            self.remove_widget(self.wifi_overlay)

    def open_bluetooth_settings(self, *_):
        if hasattr(self, 'bluetooth_overlay') and self.bluetooth_overlay in self.children:
            return
        self.bluetooth_overlay = BluetoothSettingsOverlay(screen=self)
        self.add_widget(self.bluetooth_overlay)

    def close_bluetooth_settings(self):
        if hasattr(self, 'bluetooth_overlay') and self.bluetooth_overlay in self.children:
            if hasattr(self.bluetooth_overlay, 'on_close'):
                self.bluetooth_overlay.on_close()
            self.remove_widget(self.bluetooth_overlay)

    def open_security_settings(self, *_):
        if hasattr(self, 'security_overlay') and self.security_overlay in self.children:
            return
        self.security_overlay = UserPasswordSettingsOverlay(screen=self)
        self.add_widget(self.security_overlay)

    def close_security_settings(self):
        if hasattr(self, 'security_overlay') and self.security_overlay in self.children:
            self.remove_widget(self.security_overlay)

    def test_rev(self, *_):
        self._send_command("test")
    
    def soft_reset(self, *_):
        self._send_command("soft_reset")

    def sync_time(self, *_):
        self._send_command("sync_time")

    def factory_reset(self, *_):
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        content.add_widget(Label(text="Wirklich FACTORY RESET ausführen?\n\nAlle Einstellungen gehen verloren!", color=(1, 0.3, 0.3, 1), halign="center"))
        
        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=15)
        yes = GlassButton(text="JA, JETZT ZURÜCKSETZEN", color=(1, 0.2, 0.2, 1))
        no = GlassButton(text="ABBRECHEN")
        
        yes.bind(on_release=lambda x: (self._send_command("factory_reset"), popup.dismiss()))
        no.bind(on_release=lambda x: popup.dismiss())
        
        btn_box.add_widget(yes)
        btn_box.add_widget(no)
        content.add_widget(btn_box)
        
        popup = Popup(title="⚠️ FACTORY RESET", content=content, size_hint=(0.8, 0.45))
        popup.open()

    def _check_sync_status(self, dt):
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(GLOBAL_STATE.get_active_device_id())
        if not data: return
        server_rev = int(data.get("rev_grow", 0))
        if self.engine.is_pending(server_rev) and self.engine.should_retry():
            if self.engine.retry_allowed():
                self.engine.register_retry()
                self._retry_count = getattr(self.engine, "_retry_count", 0)
                self._retry_last_grow_payload()

    def toggle_ble_bridge(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            print("[GrowController] Fehler: Keine MAC-Adresse gefunden!")
            return
        new_state = not getattr(self, 'ble_bridge_enabled', True)
        new_rev = self._send_grow_payload(
            {"ble_bridge": new_state},
            context="ble_bridge",
            reset_after_ack=False,
            show_status=True
        )
        if new_rev:
            self.ble_bridge_enabled = new_state
            self.bridge_btn_footer.text = f"Bridge: {'ON' if new_state else 'OFF'}"
            self.bridge_btn_footer.color = (0.2, 1, 0.4, 1) if new_state else (1, 1, 1, 1)

    def toggle_ble_scan(self, *_):
        mac = GLOBAL_STATE.get_active_device_id()
        if not mac:
            return
        new_state = not getattr(self, 'ble_scan_enabled', True)
        
        print(f"[UI Toggle] BLE Scan -> {new_state}")
        
        new_rev = self._send_grow_payload(
            {"ble_scan": new_state},
            context="ble_scan",
            reset_after_ack=False,
            show_status=True
        )
        if new_rev:
            self.ble_scan_enabled = new_state
            # Button sofort aktualisieren
            self.scan_btn_footer.text = f"Scanner: {'ON' if new_state else 'OFF'}"
            self.scan_btn_footer.color = (0.2, 1, 0.4, 1) if new_state else (1, 1, 1, 1)
    def set_ap_mode(self, *_):
        self._send_wifi_mode(0)
    
    def set_sta_mode(self, *_):
        self._send_wifi_mode(1)
    
    def open_alternative_gpio_settings(self, *_):

        popup = AlternativeGpioSettings(screen=self)

        popup.open()

    def _send_wifi_mode(self, mode):
        self._send_grow_payload(
            {"wifi_mode": int(mode)},
            context="wifi_mode",
            reset_after_ack=True,
            show_status=True
        )

    def open_ota_settings(self, *_):
        if hasattr(self, 'ota_overlay') and self.ota_overlay in self.children:
            return
        self.ota_overlay = OtaSettingsOverlay(screen=self)
        self.add_widget(self.ota_overlay)

    def close_ota_settings(self):
        if hasattr(self, 'ota_overlay') and self.ota_overlay in self.children:
            self.remove_widget(self.ota_overlay)

    def update_from_global(self, data):
        """Reaktives Update vom GSM - JETZT PERFORMANCE-OPTIMIERT & MIT RESET-SCHUTZ!"""
        self.header.update_from_global(data)
        
        try:
            ws = data.get("webserver", {})
            new_gpios = ws.get("gpios", {})
            
            # Überprüfen, ob das Panel gerade im "Editiermodus" (dirty) ist
            panel_is_editing = (
                self.gpio_panel and
                getattr(self.gpio_panel, 'is_dirty', False)
            )

            # Während der User editiert:
            # KEINE Live-Übernahme!
            if panel_is_editing:
                return

            # Nur echte Änderungen übernehmen
            if new_gpios != self.live_gpios:
                self.live_gpios = dict(new_gpios)
                if self.gpio_panel:
                    self.gpio_panel.update_from_live_gpios(
                        self.live_gpios
                    )

            ble = ws.get("ble_sensors", {})
            self.ble_sensors_raw_data = ble 

            if ble:
                self.discovered_ble_devices = ble.get("discovered_devices", [])
            else:
                self.discovered_ble_devices = []

            # =========================================================================
            # SAUBERE TRENNUNG DER REVISIONEN (Target-Revision-Prinzip)
            # =========================================================================
            # 1. Standard-System-Revision (für GPIOs, WiFi, etc.)
            self.current_rev = int(ws.get("rev_grow", 0))
            
            # 2. Eigene OTA-Revision (isoliert aus dem 'ota'-Unterobjekt)
            ota_data = ws.get("ota", {})
            self.current_ota_rev = int(ota_data.get("ota_rev", ws.get("rev_grow", 0)))
            
            # --- DEINE UNKAPUTTBARE REVISIONS-ÄNDERUNGS-LOGIK (jetzt auf OTA-Rev gemappt) ---
            ota_waiting = getattr(self, '_ota_is_waiting', False)
            rev_before_ota = getattr(self, '_rev_before_ota', -1)
            
            # Sobald der ESP nach dem Booten eine andere OTA-Revision meldet als vorher:
            if ota_waiting and rev_before_ota != -1 and self.current_ota_rev != rev_before_ota:
                print(f"[OTA-Pipeline] ERFOLG! Revision im 'ota' block geändert von {rev_before_ota} auf {self.current_ota_rev}.")
                self._ota_is_waiting = False
                self._rev_before_ota = -1  # Reset
                
                # Schließe das Overlay und zeige dem User den Erfolg
                if hasattr(self, 'ota_overlay') and self.ota_overlay:
                    self.ota_overlay._update_done_ui(True, "Erfolgreich geflasht und neu gestartet!")

            # --- STANDARD ACK-LOGIK (reagiert isoliert auf self.current_rev) ---
            if (
                self._reset_after_ack
                and self._last_sent_rev > 0
                and self.current_rev >= self._last_sent_rev
            ):
                context = self._last_action_context
                self._schedule_reset_after_ack()

                if context == "wifi_settings":
                    self._wifi_is_waiting = False
                    if hasattr(self, 'wifi_overlay') and self.wifi_overlay:
                        self.wifi_overlay.show_success()
                elif context == "security_settings":
                    self.close_security_settings()
                elif context == "gpio_settings":
                    self.close_gpio_settings()
                elif context == "bluetooth_settings":
                    self.close_bluetooth_settings()
            elif (
                self._status_popup_after_ack
                and self._last_sent_rev > 0
                and self.current_rev >= self._last_sent_rev
            ):
                GrowCommandStatusPopup.show(
                    reset_sent=False,
                    title="Befehl bestätigt"
                )
                self._status_popup_after_ack = False
            
            # Basis-Variablen befüllen
            self.wifi_mode = int(ws.get("wifi_mode", 0))
            self.ip = ws.get("ip", "-")
            self.ssid = ws.get("ssid", "-")
            self.dev_name = ws.get("dev_name", "-")
            self.fw_ver = ws.get("fw_ver", "-")
            self.rssi = ws.get("rssi", 0)
            
            # BLE enabled flags from device status
            self.ble_bridge_enabled = bool(ws.get("ble_bridge_enabled", True))
            self.ble_scan_enabled = bool(ws.get("ble_scan_enabled", True))

            # Reboot flag vom ESP lesen
            self.reboot_required = bool(ws.get("reboot_required", False))

            # Wenn das ESP die Revision übernommen hat und ein Reboot erforderlich ist,
            # zeigen wir eine nicht-intrusive manuelle Aktion in der Footer-Leiste
            try:
                last_sent = getattr(self, '_last_sent_rev', 0)
                if self.reboot_required and self.current_rev == last_sent and not self._reboot_popup_shown:
                    # Stelle sicher, dass footer_layout existiert
                    if not hasattr(self, 'footer_layout') or self.footer_layout is None:
                        # Fallback: erstelle ein kleines Footer-Layout
                        self.footer_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp_scaled(60))
                        self.root.add_widget(self.footer_layout)

                    # Aktionselement nur einmal erzeugen
                    if not hasattr(self, 'reboot_action_box'):
                        self.reboot_action_box = BoxLayout(size_hint_y=None, height=dp_scaled(60), spacing=dp_scaled(10), padding=[dp_scaled(10), dp_scaled(6)])
                        lbl = Label(text="Änderungen gespeichert. Neustart erforderlich.", size_hint_x=0.6, halign='left', valign='middle')
                        lbl.bind(size=lbl.setter('text_size'))
                        btn_yes = GlassButton(text="JETZT NEUSTARTEN", color=(1, 0.2, 0.2, 1), size_hint_x=0.2)
                        btn_later = GlassButton(text="SPÄTER", size_hint_x=0.2)

                        def do_restart(*_a):
                            self._send_command("soft_reset")
                            try:
                                if hasattr(self, 'reboot_action_box') and self.reboot_action_box in self.footer_layout.children:
                                    self.footer_layout.remove_widget(self.reboot_action_box)
                            except Exception:
                                pass

                        def do_later(*_a):
                            self._reboot_popup_shown = True
                            try:
                                if hasattr(self, 'reboot_action_box') and self.reboot_action_box in self.footer_layout.children:
                                    self.footer_layout.remove_widget(self.reboot_action_box)
                            except Exception:
                                pass

                        btn_yes.bind(on_release=lambda x: do_restart())
                        btn_later.bind(on_release=lambda x: do_later())

                        self.reboot_action_box.add_widget(lbl)
                        self.reboot_action_box.add_widget(btn_yes)
                        self.reboot_action_box.add_widget(btn_later)

                        # Append to footer
                        self.footer_layout.add_widget(self.reboot_action_box)
                    self._reboot_popup_shown = True
            except Exception:
                pass

            # Retry-Engine für Standard-Acks
            if self.engine.is_pending(self.current_rev) and self.engine.should_retry():
                if self.engine.retry_allowed():
                    self.engine.register_retry()
                    self._retry_last_grow_payload()
                    return
                if getattr(self, '_wifi_is_waiting', False):
                    self._wifi_is_waiting = False
                    print("[GrowControllerScreen] WLAN-Wechsel Timeout! ESP antwortet nicht.")
                    try:
                        if hasattr(self, 'wifi_overlay') and self.wifi_overlay in self.children and hasattr(self.wifi_overlay, 'show_timeout'):
                            self.wifi_overlay.show_timeout()
                    except Exception:
                        pass

        except Exception as e:
            print(f"[GrowControllerScreen] update_from_global ERROR: {e}")
            # Fallback-Zuweisung im Fehlerfall
            ws = data.get("webserver", {}) if isinstance(data, dict) else {}
            self.ip = ws.get("ip", "-")
            self.ssid = ws.get("ssid", "-")
            self.dev_name = ws.get("dev_name", "-")
            self.fw_ver = ws.get("fw_ver", "-")
            self.rssi = ws.get("rssi", 0)
