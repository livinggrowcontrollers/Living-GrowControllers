# dashboard_gui/overlays/features/humidifier/overlay.py


import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.components.unified_slider import UnifiedSlider
from dashboard_gui.overlays.infrastructure.control_overlay import ControlOverlay
from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from .state_adapter import HumidifierStateAdapter


HUMIDIFIER_PICTURE = os.path.join(
    "dashboard_gui",
    "assets",
    "hardware_pics",
    "humidifier.png",
)


class HumidifierOverlay(ControlOverlay):
    def __init__(self, parent_header, **kwargs):
        super().__init__(
            parent_header,
            overlay_key=OverlayKey("humidifier"),
            command_type="humidifier",
            adapter=HumidifierStateAdapter(),
            title="HUMIDIFIER CONTROL",
            panel_spacing=10,
            header_height=40,
            accent=(0.25, 0.75, 1.0),
            **kwargs,
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(180),
            spacing=dp_scaled(12),
        )
        top.add_widget(
            Image(
                source=HUMIDIFIER_PICTURE,
                size_hint=(None, 1),
                width=dp_scaled(180),
            )
        )

        target_column = BoxLayout(orientation="vertical")
        self.lbl_target = Label(
            text="TARGET: 0%",
            font_size=sp_scaled(34),
            bold=True,
            halign="left",
            valign="middle",
        )
        self.lbl_status = Label(
            text="STATUS: INIT",
            font_size=sp_scaled(20),
            bold=True,
            color=(0.3, 0.85, 1.0, 0.9),
            halign="left",
            valign="middle",
        )
        for label in (self.lbl_target, self.lbl_status):
            label.bind(size=label.setter("text_size"))
            target_column.add_widget(label)
        top.add_widget(target_column)

        self.lbl_live = Label(
            text="LIVE: 0%",
            font_size=sp_scaled(28),
            bold=True,
            color=(0.25, 0.9, 1.0, 0.9),
            halign="center",
            valign="middle",
            size_hint_x=0.35,
        )
        self.lbl_live.bind(size=self.lbl_live.setter("text_size"))
        top.add_widget(self.lbl_live)
        self.panel.add_widget(top)

        self.panel.add_widget(Widget(size_hint_y=None, height=dp_scaled(16)))
        self.slider_label = Label(
            text="MAXIMUM OUTPUT: 60%",
            font_size=sp_scaled(20),
            bold=True,
            color=(0.55, 0.9, 1.0, 0.95),
            size_hint_y=None,
            height=dp_scaled(22),
        )
        self.panel.add_widget(self.slider_label)

        self.slider = UnifiedSlider(
            min=0,
            max=60,
            range_min=0,
            range_max=100,
            mode="single",
            size_hint_y=None,
            height=dp_scaled(50),
        )
        self.slider.bind(
            value=self._on_output_change,
            on_touch_down=self._control_touch_down,
            on_touch_up=self._control_touch_up,
        )
        self.panel.add_widget(self.slider)
        self.panel.add_widget(Widget())

        self._set_controls_disabled(True)
        self._finish_setup()

    def _on_output_change(self, *_):
        if not self._init_done or self._ui_lock or self._locked:
            return
        value = int(self.slider.value)
        self.slider_label.text = f"MAXIMUM OUTPUT: {value}%"
        self.lbl_target.text = f"TARGET: {value}%"
        self._set_orange()

    def _render_live_state(self, state):
        self.lbl_live.text = f"LIVE: {state.live_pct}%"
        status = state.status.replace("_", " ").upper()
        self.lbl_status.text = f"STATUS: {status}"
        if "FAIL" in status:
            self.lbl_status.color = (1.0, 0.25, 0.25, 1)
        elif "NIGHT" in status:
            self.lbl_status.color = (0.55, 0.65, 1.0, 1)
        elif status == "DISABLED":
            self.lbl_status.color = (0.55, 0.55, 0.55, 1)
        else:
            self.lbl_status.color = (0.3, 0.9, 1.0, 1)
        self.panel.set_accent(StatusColors.get_output_color(state.live_pct if state.enabled else None))

    def _apply_server_state(self, state):
        if self._user_active:
            return
        self.slider.value = state.target_pct
        self.slider_label.text = f"MAXIMUM OUTPUT: {state.target_pct}%"
        self.lbl_target.text = f"TARGET: {state.target_pct}%"

    def _build_command_kwargs(self, **overrides):
        return {"pct": int(overrides.get("pct", self.slider.value))}

    def _set_controls_disabled(self, disabled):
        self.slider.disabled = disabled
