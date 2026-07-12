# © 2025 Dominik Rosenthal (Hackintosh1980)
# Umgebaut für integriertes mDNS-Autofill Mapping
# dashboard_gui/ui/device_picker_content/device_picker.py
import os
import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label    
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import AsyncImage
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox  
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import Clock
import core
import threading

from dashboard_gui.ui.device_picker_content.device_discoverer import PopupDiscoverer
import dashboard_gui.ui.device_picker_content.config_actions as actions
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from kivy.uix.gridlayout import GridLayout 
from kivy.graphics import Color, Line, Rectangle, InstructionGroup
from dashboard_gui.ui.common.icons.led_circle import LEDCircle
from dashboard_gui.ui.device_picker_content.mdns_scanner_popup import open_mdns_scanner_popup
from dashboard_gui.ui.device_picker_content.status_pipeline import DeviceStatusPipeline
# mDNS Importe
ASSET_ROOT = os.path.join("dashboard_gui", "assets")

class DevicePickerScreen(Screen):
    name = "device_picker"

    def __init__(self, **kw):
        super().__init__(**kw)
        GLOBAL_STATE.ui_handler.attach_screen("device_picker", self)
        
        self.device_leds = {}  # <-- NEU: Speicher für die LED-Widgets
        self.device_rows = {}
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(
                source=os.path.join(ASSET_ROOT, "background2.png"),
                pos=root.pos,
                size=root.size
            )

        root.bind(
            pos=lambda *_: setattr(self.bg_rect, "pos", root.pos),
            size=lambda *_: setattr(self.bg_rect, "size", root.size)
        )
        # --- HEADER ---
        self.header = HeaderBar()
        root.add_widget(self.header)

        # -------------------------------------------------
        # FIXE BUTTON LEISTE
        # -------------------------------------------------

        toolbar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(45),
            spacing=dp_scaled(8),
            padding=[dp_scaled(8), dp_scaled(4)]
        )

        btn_delete_all = Button(
            text="[font=FA]\uf1f8[/font] Delete All",
            markup=True,
            font_size=sp_scaled(18),
            background_down="",
            background_color=(0.7, 0.25, 0.25, 1)
        )

        btn_setup = Button(
            text="[font=FA]\uf013[/font] Setup",
            markup=True,
            font_size=sp_scaled(18),
            background_down="",
            background_color=(0.2, 0.5, 0.7, 1)
        )

        btn_delete_all.bind(on_release=lambda *_: actions.delete_all_devices(self._build))
        btn_setup.bind(on_release=lambda *_:
            GLOBAL_STATE.ui_handler.goto("setup")
        )

        toolbar.add_widget(btn_delete_all)
        toolbar.add_widget(btn_setup)


        # --- BODY ---
        self.content_layout = BoxLayout(
            orientation="vertical",
            padding=dp_scaled(10),
            spacing=dp_scaled(10)
        )

        # SINGLE COLUMN: ein zentrales ScrollView mit einem GridLayout cols=1
# SINGLE COLUMN: ein zentrales ScrollView mit einem GridLayout cols=1

        legend = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(15),
            padding=[dp_scaled(12), 0],
            spacing=dp_scaled(8),
        )

        mix_hdr = Label(
            text="MIX",
            font_size=sp_scaled(14),
            size_hint_x=0.1,
            halign="left",
            valign="middle",
            bold=True,
            color=(0.60, 0.62, 0.66, 1),
        )
        mix_hdr.bind(size=lambda i, *_: setattr(i, "text_size", i.size)) 

        device_hdr = Label(
            text="DEVICES",
            font_size=sp_scaled(14),
            size_hint_x=0.4,
            halign="center",
            valign="middle",
            bold=True,
            color=(0.60, 0.62, 0.66, 1),
        )
        device_hdr.bind(size=lambda i, *_: setattr(i, "text_size", i.size))

        channel_hdr = Label(
            text="STATUS / VALUES",
            font_size=sp_scaled(14),
            size_hint=(None, 1),
            width=dp_scaled(500),
            halign="center",
            valign="middle",
            bold=True,
            color=(0.60, 0.62, 0.66, 1),
        )
        channel_hdr.bind(size=lambda i, *_: setattr(i, "text_size", i.size))

        action_hdr = Label(
            text="ACTIONS",
            font_size=sp_scaled(14),
            size_hint=(None, 1),
            width=dp_scaled(260),
            halign="center",
            valign="middle",
            bold=True,
            color=(0.60, 0.62, 0.66, 1),
        )
        action_hdr.bind(size=lambda i, *_: setattr(i, "text_size", i.size))

        edit_hdr = Label(
            text="SETUP",
            font_size=sp_scaled(14),
            size_hint=(None, 1),
            width=dp_scaled(60),
            halign="center",
            valign="middle",
            bold=True,
            color=(0.60, 0.62, 0.66, 1),
        )
        edit_hdr.bind(size=lambda i, *_: setattr(i, "text_size", i.size))


        legend.add_widget(mix_hdr)
        legend.add_widget(device_hdr)
        legend.add_widget(channel_hdr)
        legend.add_widget(action_hdr)
        legend.add_widget(edit_hdr)

        self.content_layout.add_widget(legend)

        scroll_view = ScrollView()
        self.container_devices = GridLayout(
            cols=1,
            spacing=dp_scaled(12),
            size_hint_y=None,
        )
        self.container_devices.bind(
            minimum_height=self.container_devices.setter("height")
        )
        scroll_view.add_widget(self.container_devices)

        self.content_layout.add_widget(scroll_view)

        root.add_widget(self.content_layout)

        # Fixed toolbar at the bottom (Footer)
        root.add_widget(toolbar)

        self.add_widget(root)

        # Status pipeline: verlagert die Global-Update-Logik in ein Modul
        self.status_pipeline = DeviceStatusPipeline(self)

    def on_pre_enter(self, *_):
        self._build()


    def _build(self):
        self.device_leds.clear()  # <-- NEU: Altspeicher löschen      
        self.device_rows.clear()
        if hasattr(self, "device_channel_labels"):
            self.device_channel_labels.clear()        
        
        self.container_devices.clear_widgets()

        import config
        cfg = config._init()
        devices = cfg.get("devices", {})

        if not devices:
            self.container_devices.add_widget(Label(text="No devices configured"))
            return

        # --- MIXED GROUPS BUILD ---
        mixed_devices = [mac for mac, d in devices.items() if d.get("mixed_enabled")]

        self.mixed_groups = []
        visited = set()

        for mac in mixed_devices:
            if mac in visited:
                continue

            group = [mac]
            visited.add(mac)

            # aktuell simpel: alle mixed Geräte sind eine Gruppe
            # (du hast kein mapping → also bewusst so)
            for other in mixed_devices:
                if other not in visited:
                    group.append(other)
                    visited.add(other)

            self.mixed_groups.append(group)

        # SICHERHEIT: list(...) erzeugt eine statische Momentaufnahme. 
        # Selbst wenn sich im Hintergrund was ändert, stürzt Python nicht ab!
        # Lineares Hinzufügen: eine einzige Spalte (kein i%2 Split mehr)
        for mac, dev in list(devices.items()):
            row_widget = self._device_row(mac, dev)

            # Mixed Position bestimmen
            row_widget.mixed_position = None

            for group in getattr(self, "mixed_groups", []):
                if mac in group:
                    if len(group) == 1:
                        row_widget.mixed_position = "single"
                    elif mac == group[0]:
                        row_widget.mixed_position = "top"
                    elif mac == group[-1]:
                        row_widget.mixed_position = "bottom"
                    else:
                        row_widget.mixed_position = "middle"

            self.container_devices.add_widget(row_widget)

    
    
    def _move_device(self, mac, direction):
        actions.move_device(mac, direction, self._build)


    def _notify_global_state(self):
        actions.notify_global_state()


    def _rebuild_active_index(self, deleted_mac=None):
        actions.rebuild_active_index(deleted_mac)
    
    def _delete_device(self, mac):
        actions.delete_device(mac, self._build)


    def _delete_all_devices(self, *_):
        actions.delete_all_devices(self._build)
    def _copy_device(self, mac):
        actions.copy_device(mac, self._build)

    def open(self):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.goto(self.name)

    def _device_row(self, mac, dev):
        from dashboard_gui.ui.device_picker_content.device_row import DeviceRow
        row = DeviceRow(mac, dev, self)
        self.device_rows[mac] = row
        return row
    
    def update_from_global(self, d):
        # Delegate the processing to the status pipeline module
        try:
            self.status_pipeline.process_global_update(d)
        except Exception as e:
            print(f"[DevicePicker] Status pipeline error: {e}")