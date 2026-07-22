# dashboard_gui/overlays/features/climate_hub/overlay.py


import os
import time

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.infrastructure.control_overlay import ControlOverlay
from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from .profiles import PROFILES, PROFILE_LABELS, match_profile
from .state_adapter import ClimateHubStateAdapter
from .target_editor import ClimateTargetsEditor
from .targets import ClimateTargets


CLIMATE_HUB_PICTURE = os.path.join("dashboard_gui", "assets", "hardware_pics", "climate_hub.png")


class ClimateHubOverlay(ControlOverlay):
    """Primary UI for climate targets and the global Night Reduction policy."""

    _PHASE_NAMES = {0: "DAY", 1: "SUNSET", 2: "NIGHT", 3: "SUNRISE"}

    def __init__(self, parent_header, **kwargs):
        self._stage = "custom"
        self._night_reduction_enabled = True
        super().__init__(
            parent_header,
            overlay_key=OverlayKey("climate_hub"),
            command_type="climate_hub",
            adapter=ClimateHubStateAdapter(),
            title="CLIMATE HUB",
            panel_spacing=7,
            **kwargs,
        )

        self.btn_phase = Button(
            text="CUSTOM  [font=FA]\uf078[/font]",
            markup=True,
            font_size=sp_scaled(16),
            size_hint=(None, 1),
            width=dp_scaled(190),
            background_normal="",
            background_down="",
            background_color=(0.35, 0.35, 0.4, 0.9),
            color=(1, 1, 1, 1),
        )
        self.btn_phase.bind(on_release=self._open_stage_menu)
        self.header.add_action(self.btn_phase, dp_scaled(190))

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(90), spacing=dp_scaled(10))
        top.add_widget(Image(source=CLIMATE_HUB_PICTURE, size_hint=(None, 1), width=dp_scaled(180)))
        middle = BoxLayout(orientation="vertical", size_hint_x=0.75, spacing=dp_scaled(2))
        self.lbl_live_temp = Label(text="Live Temperature: --", font_size=sp_scaled(21), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        self.lbl_live_hum = Label(text="Live Humidity: --", font_size=sp_scaled(21), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        self.lbl_live_vpd = Label(text="Live VPD: --", font_size=sp_scaled(21), bold=True, color=(1, 1, 1, 0.9), halign="left", valign="middle")
        for label in (self.lbl_live_temp, self.lbl_live_hum, self.lbl_live_vpd):
            label.bind(size=label.setter("text_size"))
            middle.add_widget(label)
        top.add_widget(middle)
        top.add_widget(Widget(size_hint_x=0.25))
        self.panel.add_widget(top)

        self.climate_editor = ClimateTargetsEditor(
            defaults=ClimateTargets(humidity_min=45),
            on_change=self._on_climate_change,
            on_touch_down=self._control_touch_down,
            on_touch_up=self._control_touch_up,
        )
        self.temp_slider, self.hum_slider, self.vpd_slider = self.climate_editor.sliders
        self.lbl_temp = self.climate_editor.temp.value_label
        self.lbl_hum = self.climate_editor.humidity.value_label
        self.lbl_vpd = self.climate_editor.vpd.value_label
        self.panel.add_widget(self.climate_editor)
        self.panel.add_widget(Widget())

        night_row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(10))
        self.btn_night_reduction = self._create_styled_btn("[font=FA]\uf186[/font]  NIGHT REDUCTION")
        self.btn_night_reduction.bind(on_release=lambda *_: self._toggle_night_reduction())
        night_row.add_widget(self.btn_night_reduction)
        self.panel.add_widget(night_row)

        self._set_controls_disabled(True)
        self._apply_stage_controls()
        self._finish_setup()

    def _on_climate_change(self, _targets):
        if not self._init_done or self._ui_lock or self._locked:
            return
        self._stage = "custom"
        self._apply_stage_controls()
        self._set_orange()

    def _open_stage_menu(self, *_):
        if self._locked:
            return
        dropdown = DropDown(auto_dismiss=True, max_height=dp_scaled(300))
        for stage in (*PROFILES.keys(), "custom"):
            button = Button(text=PROFILE_LABELS[stage], size_hint_y=None, height=dp_scaled(42), background_normal="", background_color=(0.12, 0.12, 0.14, 1))
            button.bind(on_release=lambda _button, selected=stage: self._set_stage(selected, dropdown))
            dropdown.add_widget(button)
        dropdown.open(self.btn_phase)

    def _set_stage(self, stage, dropdown=None):
        if self._locked:
            return
        self._stage = stage
        self._user_active = True
        self._last_user_action = time.time()
        if stage in PROFILES:
            self.climate_editor.apply(PROFILES[stage])
        self._apply_stage_controls()
        if dropdown:
            dropdown.dismiss()
        self._submit_current_state()
        event = Clock.schedule_once(lambda _dt: setattr(self, "_user_active", False), 0.4)
        self._deferred_events.append(event)

    def _toggle_night_reduction(self):
        if self._locked:
            return
        self._night_reduction_enabled = not self._night_reduction_enabled
        self._user_active = True
        self._last_user_action = time.time()
        self._apply_stage_controls()
        self._submit_current_state()
        event = Clock.schedule_once(lambda _dt: setattr(self, "_user_active", False), 0.4)
        self._deferred_events.append(event)

    def _render_live_state(self, state):
        self.lbl_live_temp.text = f"Live Temperature: {state.live_temperature:.1f} {state.temperature_unit}" if state.live_temperature is not None else "Live Temperature: --"
        self.lbl_live_hum.text = f"Live Humidity: {state.live_humidity:.1f} {state.humidity_unit}" if state.live_humidity is not None else "Live Humidity: --"
        self.lbl_live_vpd.text = f"Live VPD: {state.live_vpd:.2f} {state.vpd_unit}" if state.live_vpd is not None else "Live VPD: --"
        self.panel.set_accent(state.accent)
        phase = self._PHASE_NAMES.get(state.plant_phase, "UNKNOWN")
        self.header.title_label.text = f"CLIMATE HUB • {phase}"

    def _apply_server_state(self, state):
        if self._user_active:
            return
        self.climate_editor.apply(state.climate)
        self._night_reduction_enabled = state.night_reduction_enabled
        self._stage = match_profile(state.climate)
        self._apply_stage_controls()

    def _build_command_kwargs(self, **overrides):
        climate = self.climate_editor.values()
        return {
            "t_min": climate.temp_min,
            "t_max": climate.temp_max,
            "h_min": climate.humidity_min,
            "h_max": climate.humidity_max,
            "vpd_min": climate.vpd_min,
            "vpd_max": climate.vpd_max,
            "night_reduction": self._night_reduction_enabled,
        }

    def _apply_stage_controls(self):
        label = PROFILE_LABELS.get(self._stage, "CUSTOM")
        self.btn_phase.text = f"{label}  [font=FA]\uf078[/font]"
        preset = self._stage != "custom"
        self.btn_phase.background_color = (0.0, 0.65, 0.35, 0.85) if preset else (0.35, 0.35, 0.4, 0.9)
        self.btn_phase.color = (0, 0, 0, 1) if preset else (1, 1, 1, 1)
        self.btn_night_reduction.background_color = (0.35, 0.42, 1.0, 0.9) if self._night_reduction_enabled else (0.15, 0.15, 0.15, 1)
        self.btn_night_reduction.color = (0, 0, 0, 1) if self._night_reduction_enabled else (1, 1, 1, 1)

    def _set_controls_disabled(self, disabled):
        self.climate_editor.set_disabled(disabled)
