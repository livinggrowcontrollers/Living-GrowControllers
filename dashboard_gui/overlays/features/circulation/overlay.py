import os
import time

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.components.unified_slider import UnifiedSlider
from dashboard_gui.overlays.infrastructure.control_overlay import ControlOverlay
from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from .state_adapter import CirculationFanStateAdapter


CIRCULATION_PICTURE = os.path.join("dashboard_gui", "assets", "hardware_pics", "mars_gaming.png")


class CirculationFanOverlay(ControlOverlay):
    def __init__(self, parent_header, fan_id=1, **kwargs):
        self.fan_id = int(fan_id)
        self._target_mode = "nat"
        super().__init__(
            parent_header,
            overlay_key=OverlayKey("circulation", self.fan_id),
            command_type="circulation_fan",
            adapter=CirculationFanStateAdapter(self.fan_id),
            title=f"CIRCULATION FAN {self.fan_id} CONTROL",
            panel_spacing=10,
            header_height=40,
            accent=(0.0, 0.7, 1.0),
            **kwargs,
        )

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(180), spacing=dp_scaled(10))
        top.add_widget(Image(source=CIRCULATION_PICTURE, size_hint=(None, 1), width=dp_scaled(180)))

        middle = BoxLayout(orientation="vertical")
        self.lbl_val = Label(text="0% - 0%", font_size=sp_scaled(36), bold=True, halign="left", valign="middle")
        self.lbl_val.bind(size=self.lbl_val.setter("text_size"))
        self.lbl_reason = Label(text="", font_size=sp_scaled(20), halign="left", valign="middle")
        middle.add_widget(self.lbl_val)
        middle.add_widget(self.lbl_reason)
        top.add_widget(middle)

        right = BoxLayout(orientation="vertical")
        self.lbl_rpm = Label(text="RPM: 0", font_size=sp_scaled(22), color=(0.7, 0.7, 1, 0.8), halign="center", valign="middle")
        self.lbl_live_speed = Label(text="LIVE: 0%", font_size=sp_scaled(22), bold=True, color=(0, 1, 1, 0.8), halign="center", valign="middle")
        for label in (self.lbl_rpm, self.lbl_live_speed):
            label.bind(size=label.setter("text_size"))
            right.add_widget(label)
        top.add_widget(right)
        self.panel.add_widget(top)

        self.panel.add_widget(Widget(size_hint_y=None, height=dp_scaled(10)))
        self.panel.add_widget(Label(text="SPEED RANGE (MIN - MAX)", font_size=sp_scaled(20), color=(0, 1, 0, 0.5), size_hint_y=None, height=dp_scaled(15)))
        self.range_slider = UnifiedSlider(min=0, max=100, mode="range", size_hint_y=None, height=dp_scaled(50))
        self.range_slider.bind(
            min_value=self._on_slider_change,
            max_value=self._on_slider_change,
            on_touch_down=self._control_touch_down,
            on_touch_up=self._control_touch_up,
        )
        self.panel.add_widget(self.range_slider)
        self.panel.add_widget(Widget())

        buttons = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_man = self._create_styled_btn("MANUAL")
        self.btn_nat = self._create_styled_btn("NATURAL")
        self.btn_chao = self._create_styled_btn("CHAOTIC")
        for button in (self.btn_man, self.btn_nat, self.btn_chao):
            buttons.add_widget(button)
        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_nat.bind(on_release=lambda *_: self._set_mode("nat"))
        self.btn_chao.bind(on_release=lambda *_: self._set_mode("chao"))
        self.panel.add_widget(buttons)

        self._set_controls_disabled(True)
        self._finish_setup(init_delay=0)

    def _on_slider_change(self, *_):
        if not self._init_done or self._ui_lock:
            return
        self.lbl_val.text = f"{int(self.range_slider.min_value)}% - {int(self.range_slider.max_value)}%"
        self._set_orange()

    def _set_mode(self, mode):
        if self._locked:
            return
        self._target_mode = mode
        self._last_user_action = time.time()
        self._apply_button_styles(mode)
        self._submit_current_state()

    def _render_live_state(self, state):
        self.lbl_live_speed.text = f"LIVE: {state.live_speed}%"
        self.lbl_rpm.text = f"RPM: {state.rpm}"
        self.panel.set_accent(StatusColors.get_rpm_color(state.rpm))

    def _apply_server_state(self, state):
        if self._user_active:
            return
        self.range_slider.min_value = state.target_min
        self.range_slider.max_value = state.target_max
        self.lbl_val.text = f"{state.target_min}% - {state.target_max}%"
        self._target_mode = state.mode
        self._apply_button_styles(state.mode)

    def _build_command_kwargs(self, **overrides):
        return {
            "fan_id": self.fan_id,
            "min": int(self.range_slider.min_value),
            "max": int(self.range_slider.max_value),
            "mode": overrides.get("mode", self._target_mode),
        }

    def _apply_button_styles(self, mode):
        base = (0.15, 0.15, 0.15, 1)
        states = (
            (self.btn_man, mode == "manual", (0, 1, 0, 0.85)),
            (self.btn_nat, mode == "nat", (0, 0.6, 1, 0.85)),
            (self.btn_chao, mode == "chao", (1, 0.5, 0, 0.85)),
        )
        for button, active, color in states:
            button.background_color = color if active else base
            button.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)

    def _set_controls_disabled(self, disabled):
        self.range_slider.disabled = disabled
