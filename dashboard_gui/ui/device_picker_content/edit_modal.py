# dashboard_gui/ui/device_picker_content/edit_modal.py

from concurrent.futures import ThreadPoolExecutor

import config
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from web_client import WEB_CLIENT
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.device_picker_content.mdns_scanner_popup import open_mdns_scanner_popup
from dashboard_gui.ui.device_picker_content.config_actions import notify_global_state

class DeviceEditModal(ModalView):
    def __init__(self, mac, dev, displayed_mac, rebuild_callback, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.9, 0.85)
        self.auto_dismiss = True
        self.background = ""
        self.background_color = (0, 0, 0, 0.72)
        
        self.mac = mac
        self.dev = dev
        self.displayed_mac = displayed_mac
        self.rebuild_callback = rebuild_callback

        popup_layout = BoxLayout(
            orientation="vertical",
            padding=dp_scaled(15),
            spacing=dp_scaled(10)
        )

        with popup_layout.canvas.before:
            Color(0, 0, 0, 0.6)
            self.bg_rect = RoundedRectangle(
                pos=popup_layout.pos,
                size=popup_layout.size,
                radius=[dp_scaled(18)]
            )
        popup_layout.bind(
            pos=lambda *_: setattr(self.bg_rect, "pos", popup_layout.pos),
            size=lambda *_: setattr(self.bg_rect, "size", popup_layout.size)
        )

        self.name_input = TextInput(text=dev.get("name", ""), multiline=False, font_size=sp_scaled(27), size_hint_y=None, height=dp_scaled(50))
        self.ip_input = TextInput(text=dev.get("ip_address", ""), hint_text="Webserver IP (Auto-Fill)", multiline=False, font_size=sp_scaled(27),  size_hint_y=None, height=dp_scaled(50))
        self.hostname_input = TextInput(text=dev.get("hostname", ""), hint_text="mDNS Hostname", multiline=False, font_size=sp_scaled(27), size_hint_y=None, height=dp_scaled(50))
        self.user_input = TextInput(text=dev.get("auth", {}).get("user", ""), hint_text="Username", multiline=False, font_size=sp_scaled(27), size_hint_y=None, height=dp_scaled(50))
        self.pass_input = TextInput(text=dev.get("auth", {}).get("pass", ""), hint_text="Password", password=True, multiline=False, font_size=sp_scaled(27), size_hint_y=None, height=dp_scaled(50))

        self.protected_cb = CheckBox(active=bool(dev.get("protected", False)))
        prot_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(40))
        prot_row.add_widget(Label(text="Schreibschutz:", size_hint_x=0.8, halign="left"))
        prot_row.add_widget(self.protected_cb)

        mdns_btn = Button(text="[font=FA]\uf002[/font]  Scan mDNS", markup=True, size_hint_y=None, height=dp_scaled(50), background_down="", background_color=(0.2, 0.5, 0.9, 1))

        popup_layout.add_widget(self.name_input)
        popup_layout.add_widget(mdns_btn)
        popup_layout.add_widget(self.ip_input)
        popup_layout.add_widget(self.hostname_input)
        popup_layout.add_widget(self.user_input)
        popup_layout.add_widget(self.pass_input)
        popup_layout.add_widget(prot_row)

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(44), spacing=dp_scaled(8))
        save_btn = Button(text="Save", background_down="", background_color=(0.15, 0.6, 0.4, 1))
        cancel_btn = Button(text="Cancel", background_down="", background_color=(0.5, 0.5, 0.5, 1))
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)
        popup_layout.add_widget(btn_row)

        save_btn.bind(on_release=lambda *_: self.save_device_data_modal())
        cancel_btn.bind(on_release=lambda *_: self.dismiss())

        mdns_btn.bind(
            on_release=lambda *_: open_mdns_scanner_popup(
                self.mac,
                self.ip_input,        # Übergibt das Input-Objekt des Modals
                self.hostname_input,  # Übergibt das Input-Objekt des Modals
                self.save_device_data_modal
            )
        )
        self.add_widget(popup_layout)
        # Vorbereitung für periodisches Refresh der angezeigten Config (Debugging)
        self._refresh_ev = None
        self.bind(on_open=lambda *_: self._start_refresh())
        self.bind(on_dismiss=lambda *_: self._stop_refresh())

    def _start_refresh(self, *a):
        return

    def _stop_refresh(self, *a):
        try:
            if self._refresh_ev is not None:
                self._refresh_ev.cancel()
                self._refresh_ev = None
        except Exception:
            self._refresh_ev = None

    def save_device_data_modal(self, direct_ip=None, direct_host=None, *args):
        import core  # Importiere dein bestehendes Core-Modul
        import time
        
        # 1. Den Webserver sofort über deine Core-Brücke stoppen


        cfg = config._init()
        devices = cfg.setdefault("devices", {})

        current_mac = self.displayed_mac or self.mac
        new_mac_value = str(current_mac).strip().upper() if current_mac else ""

        for existing_id, data in list(devices.items()):
            if existing_id != self.mac:
                existing_mac = str(data.get("mac") or existing_id).strip().upper()
                if existing_mac == new_mac_value and new_mac_value:
                    print(f"[DevicePicker] Duplicate MAC blocked: {new_mac_value}")
                    # Wenn abgebrochen wird, den Server sicherheitshalber wieder starten
                    return

        # Normalize direct_ip/direct_host only if they're strings
        if isinstance(direct_ip, str) and direct_ip:
            final_ip = direct_ip.strip()
        else:
            final_ip = self.ip_input.text.strip()

        if isinstance(direct_host, str) and direct_host:
            final_host = direct_host.strip()
        else:
            final_host = self.hostname_input.text.strip()

        device_entry = devices.setdefault(self.mac, {})
        existing_device_id = str(device_entry.get("device_id", "")).strip()
        device_entry["name"] = self.name_input.text.strip()
        device_entry["ip_address"] = final_ip
        device_entry["hostname"] = final_host
        device_entry["mac"] = new_mac_value or self.mac
        device_entry["protected"] = bool(self.protected_cb.active)
        device_entry["auth"] = {"user": self.user_input.text.strip(), "pass": self.pass_input.text.strip()}
        # The editable label never changes the physical identity.  A copied
        # placeholder receives an ID only when it is linked to a real
        # Growmaster hostname for the first time.
        if existing_device_id:
            device_entry["device_id"] = existing_device_id
        elif config.validate_device_id(final_host):
            device_entry["device_id"] = final_host
        else:
            device_entry["device_id"] = ""
        # Markiere diese Änderung als manuell vorgenommen, damit Hintergrund-Discovery
        # sie kurzzeitig nicht überschreibt.
        device_entry["_manual_update_ts"] = time.time()
        
        try:
            if hasattr(self, "_discovery") and self._discovery:
                self._discovery.stop()
        except Exception as e:
            print(f"[DeviceEditModal] Discovery stop failed: {e}")

        # 2. Config auf die Festplatte schreiben, während der Server schläft
        config.save(cfg)

        # Notify global state manager to reload config and refresh engines
        try:
            from dashboard_gui.global_state_manager import GLOBAL_STATE
            GLOBAL_STATE.refresh_config()
        except Exception as e:
            print(f"[DeviceEditModal] Failed to notify GLOBAL_STATE: {e}")
        # Trigger UI rebuild callback (if provided) and close modal
        try:
            if callable(self.rebuild_callback):
                Clock.schedule_once(lambda dt: self.rebuild_callback(), 0.05)
        except Exception as e:
            print(f"[DeviceEditModal] Rebuild callback failed: {e}")

        try:
            self.dismiss()
        except Exception as e:
            print(f"[DeviceEditModal] Dismiss failed: {e}")



    def _refresh_fields(self, dt):
        try:
            cfg = config._init()
            dev = cfg.get("devices", {}).get(self.mac, {})

            # Felder nur aktualisieren, wenn der Nutzer nicht gerade darin tippt
            if not getattr(self.name_input, "focus", False):
                self.name_input.text = dev.get("name", "")
            if not getattr(self.ip_input, "focus", False):
                self.ip_input.text = dev.get("ip_address", "")
            if not getattr(self.hostname_input, "focus", False):
                self.hostname_input.text = dev.get("hostname", "")
            if not getattr(self.user_input, "focus", False):
                self.user_input.text = dev.get("auth", {}).get("user", "")
            if not getattr(self.pass_input, "focus", False):
                self.pass_input.text = dev.get("auth", {}).get("pass", "")

            # CheckBox hat kein Focus-Flag; wir setzen sie trotzdem, da sie selten
            # während Debugging gleichzeitig verändert wird.
            self.protected_cb.active = bool(dev.get("protected", False))
        except Exception as e:
            print(f"[DeviceEditModal] Fehler beim Refresh der Felder: {e}")
