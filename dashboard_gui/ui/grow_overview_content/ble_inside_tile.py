import os
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.app import App  

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter

# ================= IMAGE ASSETS =================
ASSET_ROOT = os.path.join("dashboard_gui", "assets")
HARDWARE_PICS_DIR = os.path.join(ASSET_ROOT, "hardware_pics")

# Definition der verfügbaren Hardware-Bilder
PIC_THERMOBEACON = os.path.join(HARDWARE_PICS_DIR, "thermobeacon.png")
PIC_INKBIRD = os.path.join(HARDWARE_PICS_DIR, "inkbird.png")
# Optional: Ein Standardbild (z. B. ein Bluetooth-Icon oder Fragezeichen), wenn nichts aktiv ist
PIC_DEFAULT = os.path.join(HARDWARE_PICS_DIR, "default.png") 


class SensorBLE_InsideTile(BoxLayout):
    def __init__(self, device_id, channel, tile_id, **kwargs):
        super().__init__(**kwargs)
        
        # Hier geben wir dem Tile sein Gedächtnis:
        self.device_id = device_id
        self.channel = channel
        self.tile_id = tile_id
        self.padding = dp_scaled(6)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================
        self.title_label = Label(
            text="BLE: Inside Sensor",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )
        self.title_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        # ================= MAIN =================
        self.content_container = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(2)
        )

        # ================= VALUE BOX =================
        self.value_box = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            padding=[dp_scaled(12), dp_scaled(10)],
            spacing=dp_scaled(6)
        )

        # ================= COLUMNS =================
        self.columns_box = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(10)
        )
        self.labels_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.65, 1),
            spacing=dp_scaled(2)
        )
        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.35, 1)
        )

        # ================= IMAGE =================
        # Startet standardmäßig mit dem Default-Bild
        self.sensor_image = Image(
            source=PIC_DEFAULT,
            size_hint=(1, 1),
            fit_mode="contain"
        )
        self.image_column.add_widget(self.sensor_image)

        # ================= CANVAS (GREEN SENSOR STYLE) =================
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])
            self.glow_color = Color(0.2, 0.8, 0.2, 0.35)
            self.value_glow = Line(width=5)
            self.border_color = Color(0.2, 0.8, 0.2, 0.85)
            self.value_border = Line(width=1.3)

        self.value_box.bind(
            pos=self._update_value_box_canvas,
            size=self._update_value_box_canvas
        )

        # ================= LABELS =================
        self.lbl_temp = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )
        self.lbl_hum = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )
        self.lbl_vpd = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )
        self.labels_column.add_widget(self.title_label)

        for lbl in (self.lbl_temp, self.lbl_hum, self.lbl_vpd):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)
        
        self.value_box.add_widget(self.columns_box)
        
        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): 
            return False
        
        GLOBAL_STATE.ui_handler.goto("grow_controller")
        scr = GLOBAL_STATE.ui_handler.screens.get("grow_controller")
        if scr and hasattr(scr, 'open_bluetooth_settings'):
            scr.open_bluetooth_settings()
            if hasattr(scr.bluetooth_overlay, '_set_target_sensor'):
                scr.bluetooth_overlay._set_target_sensor("inside") 
            
        return True

    def _update_value_box_canvas(self, obj, *args):
        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(14)
        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)
        rect = (x, y, w, h, r)
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    def _update_box_color(self, is_ok):
        if is_ok:
            self.glow_color.rgba = (0.2, 0.8, 0.2, 0.35)    
            self.border_color.rgba = (0.2, 0.8, 0.2, 0.85)  
        else:
            self.glow_color.rgba = (1.0, 0.3, 0.2, 0.35)
            self.border_color.rgba = (1.0, 0.3, 0.2, 0.85)

    def update_values(self, data, prefix=""):
        if not data:
            self._update_box_color(False)
            return 
        
        ble = data.get("ble_sensors", {})
        inside = ble.get("inside", {})
        
        # ================= ABSOLUT FIXER BILD-TAUSCH =================
        # Der Name kommt jetzt direkt und flackerfrei aus dem Werteblock!
        device_name = inside.get("name", "") 
        
        new_source = PIC_DEFAULT
        if device_name:
            # Wir wandeln den Namen in Kleinbuchstaben um...
            cleaned_name = device_name.lower()
            
            if "sps" in cleaned_name:
                new_source = PIC_INKBIRD
            # ...und vergleichen hier AUCH nur mit Kleinbuchstaben!
            elif "thermobeacon" in cleaned_name:
                new_source = PIC_THERMOBEACON

        # Nur das Widget aktualisieren, wenn sich der Pfad geändert hat
        if self.sensor_image.source != new_source:
            self.sensor_image.source = new_source

        # ================= SENSOR WERTE UPDATE =================
        temp_data = inside.get("temperature", {})
        hum_data = inside.get("humidity", {})
        vpd_data = inside.get("vpd", {})

        temp_val = temp_data.get("value")
        hum_val = hum_data.get("value")
        vpd_val = vpd_data.get("value")

        temp_unit = temp_data.get("unit", "°C")
        hum_unit = hum_data.get("unit", "%")
        vpd_unit = vpd_data.get("unit", "kPa")

        key_prefix = f"{prefix}_" if prefix else ""

        trend_temp = GLOBAL_STATE.get_trend_icon(f"{key_prefix}ble_temp_inside")
        trend_hum = GLOBAL_STATE.get_trend_icon(f"{key_prefix}ble_hum_inside")
        trend_vpd = GLOBAL_STATE.get_trend_icon(f"{key_prefix}ble_vpd_inside")

        self.lbl_temp.text = UIFormatter.format_sensor_label(
            name="Temp", value=temp_val if temp_val is not None else "--",
            unit=temp_unit, trend=trend_temp, sz_val=20, sz_name=16, sz_trend=18, sz_unit=16        )

        self.lbl_hum.text = UIFormatter.format_sensor_label(
            name="Hum", value=hum_val if hum_val is not None else "--",
            unit=hum_unit, trend=trend_hum, sz_val=20, sz_name=16, sz_trend=18, sz_unit=16        )

        self.lbl_vpd.text = UIFormatter.format_sensor_label(
            name="VPD", value=vpd_val if vpd_val is not None else "--",
            unit=vpd_unit, trend=trend_vpd, sz_val=20, sz_name=16, sz_trend=18, sz_unit=16        )
        
        has_valid_values = (temp_val is not None) and (hum_val is not None)
        self._update_box_color(has_valid_values)