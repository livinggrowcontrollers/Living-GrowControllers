from kivy.uix.boxlayout import BoxLayout

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.features.humidifier.overlay import HumidifierOverlay
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class HumidifierControl(BoxLayout):
    def __init__(self, parent_header=None, **kwargs):
        super().__init__(**kwargs)
        self.parent_header = parent_header
        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(45)
        self.latest_output = None
        self.icon = IconLabel(text="\uf043", font_size=sp_scaled(24))
        self.add_widget(self.icon)

    def set_output(self, percent):
        try:
            self.latest_output = None if percent is None else float(percent)
        except (TypeError, ValueError):
            self.latest_output = None
        self.icon.color = (*StatusColors.get_output_color(self.latest_output), 1)

    def is_active(self):
        return self.latest_output is not None and self.latest_output > 0

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        GLOBAL_STATE.ui_handler.open_overlay(
            "humidifier",
            lambda: HumidifierOverlay(parent_header=self),
        )
        return True
