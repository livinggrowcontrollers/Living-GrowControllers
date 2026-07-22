# dashboard_gui/overlays/features/exhaust/overlay.py


import os
import time

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.components.unified_slider import UnifiedSlider
from dashboard_gui.overlays.infrastructure.control_overlay import ControlOverlay
from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from .state_adapter import ExhaustFanStateAdapter


EXHAUST_PICTURE = os.path.join("dashboard_gui", "assets", "hardware_pics", "vivosun_t6.png")


class ExhaustFanOverlay(ControlOverlay):
    def __init__(self, parent_header, **kwargs):
        self._target_mode = "auto"
        self._chaos_enabled = False
        super().__init__(
            parent_header,
            overlay_key=OverlayKey("exhaust"),
            command_type="exhaust_fan",
            adapter=ExhaustFanStateAdapter(),
            title="EXHAUST FAN CONTROL",
            panel_spacing=10,
            header_height=40,
            **kwargs,
        )

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(180), spacing=dp_scaled(10))
        top.add_widget(Image(source=EXHAUST_PICTURE, size_hint=(None, 1), width=dp_scaled(180)))

        middle = BoxLayout(orientation="vertical", size_hint_x=0.75)
        self.lbl_val = Label(text="0% - 0%", font_size=sp_scaled(30), bold=True, halign="left", valign="middle")
        self.lbl_val.bind(size=self.lbl_val.setter("text_size"))
        reasons = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp_scaled(28), spacing=dp_scaled(10))
        self.lbl_reason1 = Label(text="AUTO IDLE", font_size=sp_scaled(18), bold=True, color=(0, 1, 1, 0.9), halign="left", valign="middle", size_hint=(0.5, None), height=dp_scaled(28))
        self.lbl_reason2 = Label(text="", font_size=sp_scaled(20), bold=True, color=(0.8, 0.8, 1, 0.9), halign="left", valign="middle", size_hint=(1, None), height=dp_scaled(28))
        for label in (self.lbl_reason1, self.lbl_reason2):
            label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            reasons.add_widget(label)
        middle.add_widget(self.lbl_val)
        middle.add_widget(reasons)
        top.add_widget(middle)

        right = BoxLayout(orientation="vertical", size_hint_x=0.25, spacing=dp_scaled(4))
        self.lbl_rpm = Label(text="RPM: 0", font_size=sp_scaled(22), bold=True, color=(0.7, 0.7, 1, 0.8), halign="center", valign="middle")
        self.lbl_live_speed = Label(text="LIVE: 0%", font_size=sp_scaled(22), bold=True, color=(0, 1, 1, 0.8), halign="center", valign="middle", size_hint_y=None, height=dp_scaled(24))
        for label in (self.lbl_rpm, self.lbl_live_speed):
            label.bind(size=label.setter("text_size"))
            right.add_widget(label)
        top.add_widget(right)
        self.panel.add_widget(top)

        self.panel.add_widget(Widget(size_hint_y=None, height=dp_scaled(10)))
        self.panel.add_widget(Label(text="SPEED RANGE (MIN - MAX)", font_size=sp_scaled(20), color=(0, 1, 0, 0.5), size_hint_y=None, height=dp_scaled(15)))
        self.range_slider = UnifiedSlider(
            min=20,
            max=65,
            range_min=0,
            range_max=100,
            mode="range",
            size_hint_y=None,
            height=dp_scaled(50),
        )
        self.range_slider.bind(
            min_value=self._on_speed_change,
            max_value=self._on_speed_change,
            on_touch_down=self._control_touch_down,
            on_touch_up=self._control_touch_up,
        )
        self.panel.add_widget(self.range_slider)
        self.panel.add_widget(Widget())

        buttons = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_man = self._create_styled_btn("MANUAL")
        self.btn_auto = self._create_styled_btn("AUTOMATIC")
        self.btn_chao = self._create_styled_btn("CHAOTIC")
        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_auto.bind(on_release=lambda *_: self._set_mode("auto"))
        self.btn_chao.bind(on_release=lambda *_: self._set_mode("chao"))
        for button in (self.btn_man, self.btn_auto, self.btn_chao):
            buttons.add_widget(button)
        self.panel.add_widget(buttons)

        self._set_controls_disabled(True)
        self._finish_setup()

    def _on_speed_change(self, *_):
        if not self._init_done or self._ui_lock or self._locked:
            return
        text = f"{int(self.range_slider.min_value)}% - {int(self.range_slider.max_value)}%"
        self.lbl_val.text = text
        self._set_orange()

    def _set_mode(self, mode):
        if self._locked:
            return
        if mode == "chao":
            self._chaos_enabled = not self._chaos_enabled
        elif mode in ("auto", "manual"):
            self._target_mode = mode

        self._user_active = True
        self._last_user_action = time.time()
        self._apply_button_styles()
        self._submit_current_state()
        event = Clock.schedule_once(lambda _dt: setattr(self, "_user_active", False), 0.4)
        self._deferred_events.append(event)

    def _render_live_state(self, state):
        self.lbl_rpm.text = f"RPM: {state.rpm}"
        self.lbl_live_speed.text = f"LIVE: {state.live_speed}%"
        self.panel.set_accent(StatusColors.get_rpm_color(state.rpm))
        reason = state.reason_primary.replace("_", " ").upper()
        self.lbl_reason1.text = reason
        self.lbl_reason2.text = state.reason_secondary.replace("_", " ").upper()
        if "FAILSAFE" in reason or "CRIT" in reason:
            self.lbl_reason1.color = (1, 0.2, 0.2, 1)
        elif "CHAOS" in reason:
            self.lbl_reason1.color = (1, 0.5, 0, 1)
        elif "VPD" in reason:
            self.lbl_reason1.color = (0.3, 1, 1, 1)
        elif "REFINED" in reason:
            self.lbl_reason1.color = (0.4, 1, 0.4, 1)
        elif "NIGHT" in reason:
            self.lbl_reason1.color = (0.6, 0.6, 1, 1)
        else:
            self.lbl_reason1.color = (1, 1, 1, 0.8)

    def _apply_server_state(self, state):
        if self._user_active:
            return
        self.range_slider.min_value = state.target_min
        self.range_slider.max_value = state.target_max
        text = f"{state.target_min}% - {state.target_max}%"
        self.lbl_val.text = text
        self._target_mode = state.mode
        self._chaos_enabled = state.chaos_enabled
        self._apply_button_styles()

    def _build_command_kwargs(self, **overrides):
        return {
            "min": int(self.range_slider.min_value),
            "max": int(self.range_slider.max_value),
            "mode": overrides.get("mode", self._target_mode),
            "chaos": self._chaos_enabled,
        }

    def _apply_button_styles(self):
        base = (0.15, 0.15, 0.15, 1)
        states = (
            (self.btn_man, self._target_mode == "manual", (0, 1, 0, 0.85)),
            (self.btn_auto, self._target_mode == "auto", (0, 0.7, 1, 0.85)),
            (self.btn_chao, self._chaos_enabled, (1, 0.5, 0, 0.85)),
        )
        for button, active, color in states:
            button.background_color = color if active else base
            button.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)

    def _set_controls_disabled(self, disabled):
        self.range_slider.disabled = disabled
