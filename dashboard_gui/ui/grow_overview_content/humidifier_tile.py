import os

from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.features.humidifier.overlay import HumidifierOverlay
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
HUMIDIFIER_PIC = os.path.join(
    ASSET_ROOT,
    "hardware_pics",
    "humidifier.png"
)


class HumidifierTile(BoxLayout):

    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )

        self.val_box_w = dp_scaled(200)
        self.val_box_h = dp_scaled(140)

        self.padding = dp_scaled(6)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================
        self.title_label = Label(
            text="Humidifier",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )
        self.title_label.bind(
            size=lambda inst, *_: setattr(inst, "text_size", inst.size)
        )

        # ================= MAIN CONTAINER =================
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
        self.hum_image = Image(
            source=HUMIDIFIER_PIC,
            size_hint=(1, 1),
            fit_mode="contain"
        )

        self.image_column.add_widget(self.hum_image)

        # ================= PROGRESS BAR =================
        self.prog_bar = SegmentedProgressBar()
        self.prog_bar.size_hint = (1, None)
        self.prog_bar.height = dp_scaled(18)

        # ================= CANVAS =================
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(
                radius=[dp_scaled(14)]
            )

            self.glow_color = Color(
                0.1, 0.45, 0.9, 0.35
            )
            self.value_glow = Line(width=5)

            self.border_color = Color(
                0.1, 0.45, 0.9, 0.85
            )
            self.value_border = Line(width=1.3)

        self.value_box.bind(
            pos=self._update_value_box_canvas,
            size=self._update_value_box_canvas
        )

        self.labels_column.add_widget(self.title_label) 

        # ================= LABELS =================
        # Kombiniertes OUTPUT und LIVE Label im einheitlichen Kachel-Format
        self.lbl_output = Label(
            text="OUTPUT: 0% | LIVE: 0%",
            font_size=sp_scaled(18),
            bold=True,
            halign="left",
            valign="middle",
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp_scaled(18)
        )

        self.lbl_status = Label(
            text="STATUS: OFFLINE",
            font_size=sp_scaled(18),
            bold=True,
            halign="left",
            valign="middle",
            color=(0.9, 0.9, 0.9, 1),
            size_hint=(1, None),
            height=dp_scaled(18)
        )

        for lbl in (self.lbl_output, self.lbl_status):
            lbl.bind(
                size=lambda inst, *_: setattr(inst, "text_size", inst.size)
            )
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)

        self.value_box.add_widget(self.columns_box)
        self.value_box.add_widget(self.prog_bar)

        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)
    def _update_box_color(self, output_pct):
        rgb = StatusColors.get_output_color(output_pct)
        self.glow_color.rgba = (*rgb, 0.35)
        self.border_color.rgba = (*rgb, 0.85)

    def _update_value_box_canvas(self, obj, *args):
        self.value_bg.pos = obj.pos
        self.value_bg.size = obj.size

        rect = (
            obj.x,
            obj.y,
            obj.width,
            obj.height,
            dp_scaled(14)
        )

        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    # ---------------- DATA UPDATE ----------------
    def update_values(self, data):
        data = data or {}
        target = data.get("humidifier_pct")
        live = data.get("humidifier_speed_now")
        status = str(data.get("humidifier_status") or "offline")

        if target is None or live is None:
            self.lbl_output.text = "OUTPUT: -- | LIVE: --"
            self.lbl_status.text = f"STATUS: {status.replace('_', ' ').upper()}"
            self.prog_bar.value = 0
            self._update_box_color(None)
            return

        target = int(target)
        live = int(live)
        self.lbl_output.text = f"OUTPUT: {target}% | LIVE: {live}%"
        self.lbl_status.text = f"STATUS: {status.replace('_', ' ').upper()}"
        self.prog_bar.value = live
        self.prog_bar.max = 100
        self._update_box_color(live)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        GLOBAL_STATE.ui_handler.open_overlay(
            "humidifier",
            lambda: HumidifierOverlay(parent_header=self),
        )
        return True
