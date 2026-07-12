import os
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
MLX90614_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "mlx90614.png")


class SensorExternalMLX90614Tile(BoxLayout):
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
            text="MLX90614",
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
            size_hint=(0.6, 1),
            spacing=dp_scaled(2)
        )
        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.4, 1)
        )

        # ================= IMAGE =================
        self.sensor_image = Image(
            source=MLX90614_PIC,
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
        self.labels_column.add_widget(self.title_label)

        # ================= LABELS =================
        self.lbl_leaf_temp = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )
        self.lbl_vpd_leaf = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )

        for lbl in (self.lbl_leaf_temp, self.lbl_vpd_leaf):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)
        self.value_box.add_widget(self.columns_box)
        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

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
        """Schaltet die UI-Glow und Border-Farbe basierend auf dem Zustand um."""
        if is_ok:
            # HIER DEINE STANDARD-FARBE FÜR "ALLES OK" EINTRAGEN
            self.glow_color.rgba = (0.2, 0.8, 0.2, 0.35)    # RGBA für das Leuchten
            self.border_color.rgba = (0.2, 0.8, 0.2, 0.85)  # RGBA für den Rahmen
        else:
            # ALARM-ROT (Bleibt für alle Kacheln gleich)
            self.glow_color.rgba = (1.0, 0.3, 0.2, 0.35)
            self.border_color.rgba = (1.0, 0.3, 0.2, 0.85)

    def on_touch_down(self, touch):
        # 1. Prüfen, ob der Touch überhaupt innerhalb DIESER Kachel gelandet ist
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        # 2. Welches Tile-ID (welcher Graph) soll geöffnet werden?
        # Standard-Fallback, falls man irgendwo anders auf die Kachel klickt
        target_tile_id = "leaf_temp" 

        # Bestimmen, welches Label getroffen wurde (hit_test)
        if self.lbl_leaf_temp.collide_point(*touch.pos):
            target_tile_id = "leaf_temp"
        elif self.lbl_vpd_leaf.collide_point(*touch.pos):
            target_tile_id = "vpd_leaf"

        # 3. Den magischen Full-Key zusammenbauen
        # Wir nutzen die Variablen, die du im __init__ via self.device_id etc. bereitstellst
        full_key = f"{self.device_id}_{self.channel}_{target_tile_id}"

        # 4. Den Fullscreen-Wechsel über das Dashboard-Modul triggern
        if hasattr(GLOBAL_STATE, "ggm"):
            try:
                print(f"[MLX90614-Tile] Klick erkannt! Öffne Graph für: {full_key}")
                if GLOBAL_STATE.ggm.engines["dashboard"].open_fullscreen(full_key):
                    return True # Event erfolgreich abgefangen und verarbeitet!
            except Exception as e:
                print(f"[MLX90614-Tile] Fehler beim Öffnen des Fullscreens: {e}")
        else:
            print("[MLX90614-Tile] Fehler: GLOBAL_STATE.ggm existiert nicht.")

        return super().on_touch_down(touch)

    def update_values(self, data, prefix=""):
        if not data:
            self._update_box_color(False)
            return

        if prefix and "_" in prefix:
            self.device_id, self.channel = prefix.split("_", 1)

        external2 = data.get("external2", {})
    
        leaf_temp_data = external2.get("leaf_temp", {})
        vpd_leaf_data  = external2.get("vpd_leaf", {})

        leaf_temp_val = leaf_temp_data.get("value")
        vpd_leaf_val  = vpd_leaf_data.get("value") if isinstance(vpd_leaf_data, dict) else vpd_leaf_data

        leaf_temp_unit = leaf_temp_data.get("unit", "°C")
        vpd_leaf_unit  = vpd_leaf_data.get("unit", "kPa") if isinstance(vpd_leaf_data, dict) else "kPa"

        active_tiles = []
        if leaf_temp_val is not None:
            active_tiles.append("leaf_temp")
        if vpd_leaf_val is not None:
            active_tiles.append("vpd_leaf")
        GLOBAL_STATE.register_tiles(active_tiles, self.device_id, self.channel)

        # Trend Icons
        key_prefix = f"{prefix}_" if prefix else ""
        
        trend_temp = GLOBAL_STATE.get_trend_icon(f"{key_prefix}leaf_temp")
        trend_vpd  = GLOBAL_STATE.get_trend_icon(f"{key_prefix}vpd_leaf")

        self.lbl_leaf_temp.text = UIFormatter.format_sensor_label(
            name="Leaf",
            value=leaf_temp_val if leaf_temp_val is not None else "--",
            unit=leaf_temp_unit,
            trend=trend_temp,
            sz_val=20, sz_name=16, sz_trend=18, sz_unit=16        )

        self.lbl_vpd_leaf.text = UIFormatter.format_sensor_label(
            name="VPD Leaf",
            value=vpd_leaf_val if vpd_leaf_val is not None else "--",
            unit=vpd_leaf_unit,
            trend=trend_vpd,
            sz_val=20, sz_name=16, sz_trend=18, sz_unit=16        )
        has_valid_values = (leaf_temp_val is not None) and (vpd_leaf_val is not None)
        self._update_box_color(has_valid_values)
