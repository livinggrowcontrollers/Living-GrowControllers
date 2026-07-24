"""Reusable compact sensor tile for the grow overview.

The original live values, trends and layout stay untouched.  Only the small
overlay lines read passively from the shared History cache.
"""

import math
import os

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.graph_chart_content.metric_registry import (
    MetricRegistry,
)
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


ASSET_ROOT = os.path.join("dashboard_gui", "assets")
HARDWARE_PICS_DIR = os.path.join(ASSET_ROOT, "hardware_pics")
SHT31_PIC = os.path.join(HARDWARE_PICS_DIR, "sht31.png")
PIC_DEFAULT = os.path.join(HARDWARE_PICS_DIR, "default.png")
PIC_THERMOBEACON = os.path.join(
    HARDWARE_PICS_DIR,
    "thermobeacon.png",
)
PIC_INKBIRD = os.path.join(HARDWARE_PICS_DIR, "inkbird.png")

SPARK_POINT_LIMIT = 8


class SensorSummaryTile(BoxLayout):
    """One live sensor tile with passive History lines."""

    def __init__(
        self,
        *,
        title,
        metrics,
        source,
        device_id="",
        channel="ch1",
        image_source=SHT31_PIC,
        dynamic_ble_image=False,
        measurements=None,
        **kwargs,
    ):
        super().__init__(
            orientation="vertical",
            padding=dp_scaled(6),
            spacing=0,
            **kwargs,
        )
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
        self._history_series = [
            ()
            for _measurement in self.measurements
        ]
        self._history_signature = None
        self.presentation = MetricRegistry.presentation("tile")
        self.metric_configs = self._metric_configs()

        self.value_box = BoxLayout(
            orientation="vertical",
            padding=[dp_scaled(12), dp_scaled(10)],
            spacing=dp_scaled(6),
        )
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])

            self.history_colors = []
            self.history_lines = []
            for metric_config in self.metric_configs:
                metric_color = metric_config["color"]
                self.history_colors.append(Color(*metric_color))
                self.history_lines.append(
                    Line(
                        width=dp_scaled(1.35),
                        joint="round",
                        cap="round",
                    )
                )

            self.glow_color = Color(0.2, 0.8, 0.2, 0.35)
            self.value_glow = Line(width=5)
            self.border_color = Color(0.2, 0.8, 0.2, 0.85)
            self.value_border = Line(width=1.3)
        self.value_box.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
        )

        columns = BoxLayout(
            orientation="horizontal",
            spacing=dp_scaled(10),
        )
        labels = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp_scaled(2),
        )
        images = BoxLayout(
            orientation="vertical",
            size_hint=(0.35, 1),
        )

        self.title_label = self._label(title, bold=True)
        self.title_label.color = self.presentation.get(
            "title_color",
            [1, 1, 1, 0.9],
        )
        self.value_labels = [
            self._label("--")
            for _ in self.measurements
        ]
        for label in (self.title_label, *self.value_labels):
            labels.add_widget(label)
        for label in self.value_labels:
            label.bind(
                pos=self._update_history_geometry,
                size=self._update_history_geometry,
            )

        self.sensor_image = Image(
            source=image_source,
            fit_mode="contain",
            opacity=0.65,
        )
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
        return (
            current
            if isinstance(current, dict)
            else {"value": current}
        )

    @staticmethod
    def _label(text, bold=False):
        label = Label(
            text=text,
            markup=True,
            bold=bold,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
        )
        label.bind(
            size=lambda instance, *_: setattr(
                instance,
                "text_size",
                instance.size,
            )
        )
        return label

    def _metric_configs(self):
        return [
            (
                MetricRegistry.get(metric)
                if metric
                else {
                    "color": [0.58, 0.62, 0.68, 1],
                    "style": {},
                }
            )
            for _name, metric, _path, _unit in self.measurements
        ]

    @staticmethod
    def _hex_color(rgba):
        channels = [
            max(0, min(255, round(float(channel) * 255)))
            for channel in rgba[:3]
        ]
        return "#{:02x}{:02x}{:02x}".format(*channels)

    def _metric_label_style(self, index):
        metric_config = self.metric_configs[index]
        presentation_style = self.presentation.get("formatter", {})
        return {
            "color_name": self._hex_color(metric_config["color"]),
            "color_sub": presentation_style.get(
                "color_sub",
                metric_config.get("style", {}).get(
                    "color_sub",
                    "#bbbbbb",
                ),
            ),
            "decimals": metric_config.get("style", {}).get(
                "decimals",
                2,
            ),
        }

    @staticmethod
    def _reduce_history(values):
        clean_values = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                clean_values.append(number)

        if len(clean_values) <= SPARK_POINT_LIMIT:
            return tuple(clean_values)

        last_index = len(clean_values) - 1
        indices = [
            round(index * last_index / (SPARK_POINT_LIMIT - 1))
            for index in range(SPARK_POINT_LIMIT)
        ]
        return tuple(clean_values[index] for index in indices)

    def _update_canvas(self, widget, *_):
        x, y = widget.pos
        width, height = widget.size
        self.value_bg.pos = (x, y)
        self.value_bg.size = (width, height)
        rectangle = (
            x,
            y,
            width,
            height,
            dp_scaled(14),
        )
        self.value_glow.rounded_rectangle = rectangle
        self.value_border.rounded_rectangle = rectangle
        self._update_history_geometry()

    def _update_history_geometry(self, *_):
        box_x, _box_y = self.value_box.pos
        box_width, _box_height = self.value_box.size
        
        graph_left = box_x + (box_width * 0.42)
        graph_right = box_x + box_width - dp_scaled(10)
        graph_width = max(1.0, graph_right - graph_left)

        for index, values in enumerate(self._history_series):
            line = self.history_lines[index]
            if not values or index >= len(self.value_labels):
                line.points = []
                continue

            label = self.value_labels[index]
            center_y = label.center_y
            
            # Amplitude nutzt JETZT fast die volle Zeilenhöhe (45% nach oben/unten = 90% Nutzung)
            # Vorher lag das bei 28%. Das gibt deutlich mehr "Ausschlag", ohne die Zeile zu verlassen.
            amplitude = label.height * 0.45

            minimum = min(values)
            maximum = max(values)
            count = len(values)
            points = []

            for point_index, value in enumerate(values):
                x_ratio = point_index / (count - 1) if count > 1 else 0.5
                y_ratio = 0.5 if minimum == maximum else (value - minimum) / (maximum - minimum)
                
                points.extend((
                    graph_left + (x_ratio * graph_width),
                    center_y + ((y_ratio - 0.5) * 2 * amplitude),
                ))

            line.points = points

    def _refresh_history_lines(self):
        prepared_series = []
        signature = [self.device_id]

        for _name, metric, _path, _unit in self.measurements:
            snapshot = (
                GLOBAL_STATE.graph_engine.get_cached_history_snapshot(
                    self.device_id,
                    metric,
                )
                if self.device_id and metric
                else None
            )
            values = (
                self._reduce_history(snapshot.values)
                if snapshot is not None
                else ()
            )
            prepared_series.append(values)
            signature.append((metric, values))

        signature = tuple(signature)
        if signature == self._history_signature:
            return

        self._history_signature = signature
        self._history_series = prepared_series
        self._update_history_geometry()

    def reset_history(self, device_id=None, channel=None):
        """Clear visible History immediately when the active device changes."""
        self.device_id = str(device_id) if device_id else ""
        if channel:
            self.channel = str(channel)
        self._history_signature = None
        self._history_series = [
            ()
            for _measurement in self.measurements
        ]
        self._update_history_geometry()

    def refresh_metric_theme(self):
        self.presentation = MetricRegistry.presentation("tile")
        self.metric_configs = self._metric_configs()
        self.title_label.color = self.presentation.get(
            "title_color",
            [1, 1, 1, 0.9],
        )
        for index, metric_config in enumerate(self.metric_configs):
            self.history_colors[index].rgba = metric_config["color"]

    def _set_health(self, healthy):
        color = (
            (0.2, 0.8, 0.2)
            if healthy
            else (1.0, 0.3, 0.2)
        )
        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)

    def _update_dynamic_image(self, data):
        if not self.dynamic_ble_image:
            return
        name = str(data.get("name", "")).lower()
        source = (
            PIC_INKBIRD
            if "sps" in name
            else (
                PIC_THERMOBEACON
                if "thermobeacon" in name
                else PIC_DEFAULT
            )
        )
        if self.sensor_image.source != source:
            self.sensor_image.source = source

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        metric = self.measurements[0][1]
        for label, (
            _name,
            candidate,
            _path,
            _unit,
        ) in zip(self.value_labels, self.measurements):
            if label.collide_point(*touch.pos):
                metric = candidate
                break
        if not metric:
            return super().on_touch_down(touch)
        full_key = f"{self.device_id}_{self.channel}_{metric}"
        try:
            if (
                hasattr(GLOBAL_STATE, "ggm")
                and GLOBAL_STATE.ggm.engines[
                    "dashboard"
                ].open_fullscreen(full_key)
            ):
                return True
        except (KeyError, AttributeError):
            pass
        return super().on_touch_down(touch)

    def update_values(self, data, prefix=""):
        if prefix and "_" in prefix:
            self.device_id, self.channel = prefix.split("_", 1)

        self._refresh_history_lines()
        if not data:
            self._set_health(False)
            return

        readings = [
            self._at(data, path)
            for _name, _metric, path, _unit in self.measurements
        ]
        self._update_dynamic_image(
            self._at(
                data,
                self.source.get("sensor", ()),
            )
        )
        values = [
            reading.get("value")
            for reading in readings
        ]
        units = [
            reading.get("unit", default_unit)
            for reading, (
                _name,
                _metric,
                _path,
                default_unit,
            ) in zip(readings, self.measurements)
        ]
        key_prefix = f"{prefix}_" if prefix else ""

        GLOBAL_STATE.register_tiles(
            [
                metric
                for (
                    _name,
                    metric,
                    _path,
                    _unit,
                ), value in zip(self.measurements, values)
                if metric and value is not None
            ],
            self.device_id,
            self.channel,
        )
        for index, (
            label,
            (
                name,
                metric,
                _path,
                _default_unit,
            ),
            value,
            unit,
        ) in enumerate(
            zip(
                self.value_labels,
                self.measurements,
                values,
                units,
            )
        ):
            label.text = UIFormatter.format_sensor_label(
                name=name,
                value=value if value is not None else "--",
                unit=unit,
                trend=(
                    GLOBAL_STATE.get_trend_icon(
                        f"{key_prefix}{metric}"
                    )
                    if metric
                    else ""
                ),
                sz_val=20,
                sz_name=16,
                sz_trend=18,
                sz_unit=16,
                style=self._metric_label_style(index),
            )
        self._set_health(
            bool(values)
            and all(value is not None for value in values)
        )
