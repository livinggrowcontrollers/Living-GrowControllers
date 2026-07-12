import os

from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter

ASSET_ROOT = os.path.join("dashboard_gui", "assets")

SCD41_PIC = os.path.join(
    ASSET_ROOT,
    "hardware_pics",
    "scd41.png"
)


class SensorSCD41Tile(BoxLayout):

    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )

        self.padding = dp_scaled(6)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================

        self.title_label = Label(
            text="CO2: SCD41",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )

        self.title_label.bind(
            size=lambda inst, *_:
            setattr(inst, "text_size", inst.size)
        )

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
            source=SCD41_PIC,
            size_hint=(1, 1),
            fit_mode="contain"
        )

        self.image_column.add_widget(self.sensor_image)

        # ================= CANVAS =================

        with self.value_box.canvas.before:

            Color(0, 0, 0, 0.62)

            self.value_bg = RoundedRectangle(
                radius=[dp_scaled(14)]
            )

            self.glow_color = Color(
                0.2,
                0.8,
                0.2,
                0.35
            )

            self.value_glow = Line(width=5)

            self.border_color = Color(
                0.2,
                0.8,
                0.2,
                0.85
            )

            self.value_border = Line(width=1.3)

        self.value_box.bind(
            pos=self._update_value_box_canvas,
            size=self._update_value_box_canvas
        )

        # ================= LABELS =================

        self.lbl_co2 = Label(
            text="--",
            markup=True,
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25)
        )

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

        self.labels_column.add_widget(self.title_label)


        for lbl in (
            self.lbl_co2,
            self.lbl_temp,
            self.lbl_hum
        ):
            lbl.bind(
                size=lambda inst, *_:
                setattr(inst, "text_size", inst.size)
            )

            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)
        
        self.value_box.add_widget(self.columns_box)
        
        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

    def _update_box_color(self, has_values):

        if has_values:

            self.glow_color.rgba = (
                0.2,
                0.8,
                0.2,
                0.35
            )

            self.border_color.rgba = (
                0.2,
                0.8,
                0.2,
                0.85
            )

        else:

            self.glow_color.rgba = (
                1.0,
                0.3,
                0.2,
                0.35
            )

            self.border_color.rgba = (
                1.0,
                0.3,
                0.2,
                0.85
            )

    def _update_value_box_canvas(self, obj, *args):

        x, y = obj.pos
        w, h = obj.size

        r = dp_scaled(14)

        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)

        rect = (
            x,
            y,
            w,
            h,
            r
        )

        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    def update_values(self, data, prefix=""):

        #
        # FAKE DATEN
        #

        co2_val = 845
        temp_val = 24.8
        hum_val = 61.2

        key_prefix = f"{prefix}_" if prefix else ""

        trend_co2 = GLOBAL_STATE.get_trend_icon(
            f"{key_prefix}co2_scd41_fake"
        )

        trend_temp = GLOBAL_STATE.get_trend_icon(
            f"{key_prefix}temp_scd41_fake"
        )

        trend_hum = GLOBAL_STATE.get_trend_icon(
            f"{key_prefix}hum_scd41_fake"
        )

        self.lbl_co2.text = UIFormatter.format_sensor_label(
            name="CO2",
            value=co2_val,
            unit="ppm",
            trend=trend_co2,
            sz_val=20,
            sz_name=16,
            sz_trend=18,
            sz_unit=16
        )

        self.lbl_temp.text = UIFormatter.format_sensor_label(
            name="Temp",
            value=temp_val,
            unit="°C",
            trend=trend_temp,
            sz_val=20,
            sz_name=16,
            sz_trend=18,
            sz_unit=16
        )

        self.lbl_hum.text = UIFormatter.format_sensor_label(
            name="Hum",
            value=hum_val,
            unit="%",
            trend=trend_hum,
            sz_val=20,
            sz_name=16,
            sz_trend=18,
            sz_unit=16
        )

        self._update_box_color(True)