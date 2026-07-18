"""Reusable compact sensor tile for the grow overview.

The widget owns presentation only.  Its ``source`` configuration selects the
data pipeline and the matching dashboard metric IDs, while all layout, trend
and graph-opening behaviour remains in one place.
"""

import os

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


ASSET_ROOT = os.path.join("dashboard_gui", "assets")
HARDWARE_PICS_DIR = os.path.join(ASSET_ROOT, "hardware_pics")
SHT31_PIC = os.path.join(HARDWARE_PICS_DIR, "sht31.png")
PIC_DEFAULT = os.path.join(HARDWARE_PICS_DIR, "default.png")
PIC_THERMOBEACON = os.path.join(HARDWARE_PICS_DIR, "thermobeacon.png")
PIC_INKBIRD = os.path.join(HARDWARE_PICS_DIR, "inkbird.png")


class SensorSummaryTile(BoxLayout):
    """One display component for an arbitrary temperature/humidity/VPD source."""

    def __init__(self, *, title, metrics, source, device_id="", channel="ch1",
                 image_source=SHT31_PIC, dynamic_ble_image=False, measurements=None, **kwargs):
        super().__init__(orientation="vertical", padding=dp_scaled(6), spacing=0, **kwargs)
        self.title = title
        self.metrics = metrics
        self.source = source
        self.device_id = device_id
        self.channel = channel
        self.dynamic_ble_image = dynamic_ble_image
        self.measurements = measurements or (
            ("Temp", metrics[0], source["temp"], "°C"),
            ("Hum", metrics[1], source["hum"], "%"),
            ("VPD", metrics[2], source["vpd"], "kPa"),
        )

        self.value_box = BoxLayout(
            orientation="vertical", padding=[dp_scaled(12), dp_scaled(10)],
            spacing=dp_scaled(6),
        )
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])
            self.glow_color = Color(0.2, 0.8, 0.2, 0.35)
            self.value_glow = Line(width=5)
            self.border_color = Color(0.2, 0.8, 0.2, 0.85)
            self.value_border = Line(width=1.3)
        self.value_box.bind(pos=self._update_canvas, size=self._update_canvas)

        columns = BoxLayout(orientation="horizontal", spacing=dp_scaled(10))
        labels = BoxLayout(orientation="vertical", size_hint=(0.65, 1), spacing=dp_scaled(2))
        images = BoxLayout(orientation="vertical", size_hint=(0.35, 1))

        self.title_label = self._label(title, bold=True)
        self.value_labels = [self._label("--") for _ in self.measurements]
        for label in (self.title_label, *self.value_labels):
            labels.add_widget(label)

        self.sensor_image = Image(source=image_source, fit_mode="contain")
        images.add_widget(self.sensor_image)
        columns.add_widget(labels)
        columns.add_widget(images)
        self.value_box.add_widget(columns)
        self.add_widget(self.value_box)

    @staticmethod
    def _at(data, path):
        current = data
        for key in path:
            if not isinstance(current, dict):
                return {}
            current = current.get(key, {})
        return current if isinstance(current, dict) else {"value": current}

    @staticmethod
    def _label(text, bold=False):
        label = Label(
            text=text, markup=True, bold=bold, font_size=sp_scaled(20),
            halign="left", valign="middle", size_hint=(1, None), height=dp_scaled(25),
        )
        label.bind(size=lambda instance, *_: setattr(instance, "text_size", instance.size))
        return label

    def _update_canvas(self, widget, *_):
        x, y = widget.pos
        w, h = widget.size
        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)
        rect = (x, y, w, h, dp_scaled(14))
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    def _set_health(self, healthy):
        color = (0.2, 0.8, 0.2) if healthy else (1.0, 0.3, 0.2)
        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)

    def _update_dynamic_image(self, data):
        if not self.dynamic_ble_image:
            return
        name = str(data.get("name", "")).lower()
        source = PIC_INKBIRD if "sps" in name else PIC_THERMOBEACON if "thermobeacon" in name else PIC_DEFAULT
        if self.sensor_image.source != source:
            self.sensor_image.source = source

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        metric = self.measurements[0][1]
        for label, (_, candidate, _, _) in zip(self.value_labels, self.measurements):
            if label.collide_point(*touch.pos):
                metric = candidate
                break
        if not metric:
            return super().on_touch_down(touch)
        full_key = f"{self.device_id}_{self.channel}_{metric}"
        try:
            if hasattr(GLOBAL_STATE, "ggm") and GLOBAL_STATE.ggm.engines["dashboard"].open_fullscreen(full_key):
                return True
        except (KeyError, AttributeError):
            pass
        return super().on_touch_down(touch)

    def update_values(self, data, prefix=""):
        if prefix and "_" in prefix:
            self.device_id, self.channel = prefix.split("_", 1)
        if not data:
            self._set_health(False)
            return

        readings = [self._at(data, path) for _, _, path, _ in self.measurements]
        self._update_dynamic_image(self._at(data, self.source.get("sensor", ())))
        values = [reading.get("value") for reading in readings]
        units = [reading.get("unit", default_unit) for reading, (_, _, _, default_unit) in zip(readings, self.measurements)]
        key_prefix = f"{prefix}_" if prefix else ""

        GLOBAL_STATE.register_tiles(
            [metric for (_, metric, _, _), value in zip(self.measurements, values) if metric and value is not None],
            self.device_id,
            self.channel,
        )
        for label, (name, metric, _, _), value, unit in zip(self.value_labels, self.measurements, values, units):
            label.text = UIFormatter.format_sensor_label(
                name=name, value=value if value is not None else "--", unit=unit,
                trend=GLOBAL_STATE.get_trend_icon(f"{key_prefix}{metric}") if metric else "",
                sz_val=20, sz_name=16, sz_trend=18, sz_unit=16,
            )
        self._set_health(bool(values) and all(value is not None for value in values))
