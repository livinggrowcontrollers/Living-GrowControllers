# dashboard_gui/overlays/features/light/overlay.py


import os
import time

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.components.unified_slider import UnifiedSlider
from dashboard_gui.overlays.infrastructure.control_overlay import ControlOverlay
from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from .schedule import LightSchedule
from .channel_preview import LightChannelPreview
from .state_adapter import LightStateAdapter
from .timeline_widget import LightTimelineWidget


LIGHT_PICTURE = os.path.join("dashboard_gui", "assets", "hardware_pics", "electrogrow.png")


class LightOverlay(ControlOverlay):
    _PHASES = {
        "SUNRISE": ("SUNRISE", (1.0, 0.72, 0.15, 1)),
        "SUNSET": ("SUNSET", (1.0, 0.45, 0.1, 1)),
        "NIGHT": ("NIGHT", (0.45, 0.65, 1.0, 1)),
        "DAY": ("DAY", (0.0, 1.0, 0.35, 1)),
    }

    def __init__(self, parent_header, **kwargs):
        self._target_mode = "time"
        self._climate_override = False
        super().__init__(
            parent_header,
            overlay_key=OverlayKey("light"),
            command_type="light",
            adapter=LightStateAdapter(),
            title="LIGHT CONTROL PRO",
            panel_spacing=7,
            accent=(0.22, 0.22, 0.22),
            **kwargs,
        )

# 1. Tabs definieren
        tabs = BoxLayout(size_hint_y=None, height=dp_scaled(20), spacing=dp_scaled(8))
        self.btn_tab_main = self._create_styled_btn("MAIN")
        self.btn_tab_uv = self._create_styled_btn("UV")
        self.btn_tab_ir = self._create_styled_btn("IR")
        self.btn_tab_main.bind(on_release=lambda *_: self._select_light_tab("main"))
        self.btn_tab_uv.bind(on_release=lambda *_: self._select_light_tab("uv"))
        self.btn_tab_ir.bind(on_release=lambda *_: self._select_light_tab("ir"))
        for button in (self.btn_tab_main, self.btn_tab_uv, self.btn_tab_ir):
            tabs.add_widget(button)

        # FIX: Alle Widgets im Panel sichern, leeren und Tabs ganz oben als erstes platzieren
        existing_children = list(self.panel.children)
        self.panel.clear_widgets()
        
        # 1. Tabs als allererstes ganz oben ins Panel einfügen
        self.panel.add_widget(tabs)
        
        # 2. Bisherige Basis-Widgets (z. B. aus ControlOverlay) wieder drunter hängen
        for child in reversed(existing_children):
            self.panel.add_widget(child)

        # 3. Nun den Content-Host für die Tabs darunter anlegen
        self.content_host = BoxLayout(orientation="vertical")
        self.main_content = BoxLayout(orientation="vertical", spacing=dp_scaled(7))
        self.uv_preview = LightChannelPreview(
            channel_name="UV",
            description="Independent ultraviolet channel for a future dedicated low-voltage PWM output.",
            accent=(0.65, 0.3, 1.0),
            default_pct=20,
        )
        self.ir_preview = LightChannelPreview(
            channel_name="IR",
            description="Independent infrared channel for a future dedicated low-voltage PWM output.",
            accent=(1.0, 0.24, 0.14),
            default_pct=15,
        )
        
        # Content-Host unter den Tabs und Basis-Header einfügen
        self.panel.add_widget(self.content_host)

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(52), spacing=dp_scaled(10))
        top.add_widget(Image(source=LIGHT_PICTURE, size_hint=(None, 1), width=dp_scaled(180)))
        values = BoxLayout(orientation="horizontal", size_hint_x=0.4, spacing=dp_scaled(5))
        self.lbl_val = Label(text="0%", font_size=sp_scaled(36), bold=True, halign="center", valign="middle")
        self.lbl_slider_target = Label(text="0%", font_size=sp_scaled(36), bold=True, color=(0.0, 0.75, 1, 1), halign="center", valign="middle")
        for label in (self.lbl_val, self.lbl_slider_target):
            label.bind(size=label.setter("text_size"))
            values.add_widget(label)
        top.add_widget(values)
        status = BoxLayout(
            orientation="vertical",
            size_hint_x=0.6,
            spacing=dp_scaled(1),
            padding=[0, 0, 0, dp_scaled(4)],
        )
        self.lbl_status_text = Label(text="STATUS: INIT", font_size=sp_scaled(20), bold=True, color=(0, 1, 0, 0.85), halign="center")
        self.lbl_remaining = Label(text="REMAINING: --", font_size=sp_scaled(20), color=(1, 1, 0, 1), bold=True, halign="center")
        for label in (self.lbl_status_text, self.lbl_remaining):
            label.bind(size=label.setter("text_size"))
            status.add_widget(label)
       
        top.add_widget(status)
        self.main_content.add_widget(top)

        controls = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(230),
            spacing=dp_scaled(2),
        )

        def add_slider_field(label, slider):
            field = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp_scaled(56),
                spacing=dp_scaled(3),
            )
            field.add_widget(label)
            field.add_widget(slider)
            controls.add_widget(field)

        intensity_row = BoxLayout(size_hint_y=None, height=dp_scaled(15), spacing=dp_scaled(4))
        self.lbl_intensity = Label(text="INTENSITY", font_size=sp_scaled(20), color=(1, 1, 1, 0.9), bold=True, halign="right", valign="middle")
        self.lbl_light_state = Label(text="DAY", markup=True, font_size=sp_scaled(20), bold=True, color=(0, 1, 0, 0.95), halign="center", valign="middle")
        for label in (self.lbl_intensity, self.lbl_light_state):
            label.bind(size=label.setter("text_size"))
            intensity_row.add_widget(label)

        self.slider = UnifiedSlider(min=0, max=100, mode="single", size_hint_y=None, height=dp_scaled(38))
        self.slider.bind(value=self._on_intensity_change, on_touch_down=self._control_touch_down, on_touch_up=self._control_touch_up)
        add_slider_field(intensity_row, self.slider)

        self.lbl_sunrise_sunset = Label(text="RAMPEN: --", markup=True, font_size=sp_scaled(20), color=(1, 0.8, 0.2, 0.8), size_hint_y=None, height=dp_scaled(15))
        self.slider_sunrise_sunset = UnifiedSlider(min=1, max=48, range_min=1, range_max=48, mode="range", fill_entire_track=True, size_hint_y=None, height=dp_scaled(38))
        self.slider_sunrise_sunset.bind(min_value=self._on_ramp_change, max_value=self._on_ramp_change, on_touch_down=self._control_touch_down, on_touch_up=self._control_touch_up)
        add_slider_field(self.lbl_sunrise_sunset, self.slider_sunrise_sunset)

        self.lbl_start = Label(text="START: --", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(15))
        self.slider_start = UnifiedSlider(min=0, max=0, range_min=0, range_max=95, mode="single", size_hint_y=None, height=dp_scaled(38))
        self.slider_start.bind(value=self._on_start_change, on_touch_down=self._control_touch_down, on_touch_up=self._control_touch_up)
        add_slider_field(self.lbl_start, self.slider_start)

        self.lbl_dur = Label(text="DURATION: --", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(15))
        self.slider_dur = UnifiedSlider(min=1, max=48, range_min=1, range_max=96, mode="single", size_hint_y=None, height=dp_scaled(38))
        self.slider_dur.bind(value=self._on_duration_change, on_touch_down=self._control_touch_down, on_touch_up=self._control_touch_up)
        add_slider_field(self.lbl_dur, self.slider_dur)
        self.main_content.add_widget(controls)

        self.timeline = LightTimelineWidget()
        self.main_content.add_widget(self.timeline)

        buttons = BoxLayout(size_hint_y=None, height=dp_scaled(30), spacing=dp_scaled(8))
        self.btn_man = self._create_styled_btn("MANUELL")
        self.btn_tim = self._create_styled_btn("TIMER")
        self.btn_climate = self._create_styled_btn("CLIMA OVR")
        self.btn_man.bind(on_release=lambda *_: self._set_mode("manual"))
        self.btn_tim.bind(on_release=lambda *_: self._set_mode("time"))
        self.btn_climate.bind(on_release=lambda *_: self._toggle_climate_override())
        for button in (self.btn_man, self.btn_tim, self.btn_climate):
            buttons.add_widget(button)
        self.main_content.add_widget(buttons)

        self._active_light_tab = None
        self._select_light_tab("main")

        self._set_controls_disabled(True)
        self._finish_setup()

    def _select_light_tab(self, tab_name):
        views = {
            "main": self.main_content,
            "uv": self.uv_preview,
            "ir": self.ir_preview,
        }
        if tab_name not in views or tab_name == self._active_light_tab:
            return

        self.content_host.clear_widgets()
        self.content_host.add_widget(views[tab_name])
        self._active_light_tab = tab_name

        is_operational = tab_name == "main"
        self.sync_icon.disabled = not is_operational
        self.sync_icon.opacity = 1 if is_operational else 0
        if is_operational:
            self.lbl_title.text = "LIGHT CONTROL PRO"
            self.lbl_title.color = (0, 1, 0, 1)
        else:
            self.lbl_title.text = f"LIGHT CONTROL PRO  ·  {tab_name.upper()} PREVIEW"
            self.lbl_title.color = (*self.uv_preview.accent, 1) if tab_name == "uv" else (*self.ir_preview.accent, 1)

        base = (0.15, 0.15, 0.15, 1)
        active_colors = {
            "main": (1.0, 0.72, 0.08, 0.95),
            "uv": (0.65, 0.3, 1.0, 0.95),
            "ir": (1.0, 0.24, 0.14, 0.95),
        }
        for name, button in (
            ("main", self.btn_tab_main),
            ("uv", self.btn_tab_uv),
            ("ir", self.btn_tab_ir),
        ):
            active = name == tab_name
            button.background_color = active_colors[name] if active else base
            button.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)

    def _current_schedule(self):
        duration_steps = max(1, int(self.slider_dur.value))
        return LightSchedule(
            mode=self._target_mode,
            target_pct=int(self.slider.value),
            start_minute=int(self.slider_start.value) * 15,
            duration_minutes=duration_steps * 15,
            sunrise_minutes=int(self.slider_sunrise_sunset.min_value) * 15,
            sunset_minutes=int(duration_steps - self.slider_sunrise_sunset.max_value) * 15,
            climate_override=self._climate_override,
        ).normalized()

    def _refresh_schedule_labels(self):
        schedule = self._current_schedule()
        self.lbl_slider_target.text = f"{schedule.target_pct}%"
        self.lbl_start.text = f"START: {schedule.start_minute // 60:02d}:{schedule.start_minute % 60:02d}"
        self.lbl_dur.text = f"DURATION: {schedule.duration_minutes // 60}h {schedule.duration_minutes % 60:02d}m"
        self.lbl_sunrise_sunset.text = f"[font=FA]\uf185[/font] SUNRISE: {schedule.sunrise_minutes}m | [font=FA]\uf186[/font] SUNSET: {schedule.sunset_minutes}m"
        self.timeline.set_schedule(schedule)

    def _on_intensity_change(self, *_):
        if self._init_done and not self._ui_lock and not self._locked:
            self._refresh_schedule_labels()
            self._set_orange()

    def _on_duration_change(self, _instance, value):
        if not self._init_done or self._ui_lock:
            return
        steps = max(1, min(96, int(value)))
        self.slider_sunrise_sunset.range_max = steps
        self.slider_sunrise_sunset.max_value = min(self.slider_sunrise_sunset.max_value, steps)
        self.slider_sunrise_sunset.min_value = min(self.slider_sunrise_sunset.min_value, self.slider_sunrise_sunset.max_value)
        self._refresh_schedule_labels()
        if not self._locked:
            self._set_orange()

    def _on_start_change(self, *_):
        if self._init_done and not self._ui_lock:
            self._refresh_schedule_labels()
            if not self._locked:
                self._set_orange()

    def _on_ramp_change(self, *_):
        if self._init_done and not self._ui_lock:
            self._refresh_schedule_labels()
            if not self._locked:
                self._set_orange()

    def _set_mode(self, mode):
        if self._locked:
            return
        self._target_mode = mode
        self._last_user_action = time.time()
        self._apply_button_styles()
        self._submit_current_state()

    def _toggle_climate_override(self):
        if self._locked:
            return
        self._climate_override = not self._climate_override
        self._apply_button_styles()
        self._submit_current_state()

    def _render_live_state(self, state):
        self.lbl_remaining.text = state.remaining_text
        self.lbl_val.text = f"{state.current_pct}%"
        self.panel.set_accent(StatusColors.get_light_color(state.current_pct))
        self._render_phase(state.state_reason, state.schedule.climate_override)

    def _render_phase(self, reason, climate_override):
        text, color = self._PHASES.get(reason, self._PHASES["DAY"])
        extensions = []
        if climate_override:
            extensions.append("[color=00ff66]CLIM-OVR[/color]")
        if reason not in self._PHASES and reason not in ("", "MANUAL", "NORMAL", "TIMER"):
            extensions.append(f"[color=ffcc33]{reason}[/color]")
        self.lbl_light_state.text = f"{text}{' | ' + ' | '.join(extensions) if extensions else ''}"
        self.lbl_light_state.color = color

    def _apply_server_state(self, state):
        if self._user_active:
            return
        schedule = state.schedule
        self._target_mode = schedule.mode
        self._climate_override = schedule.climate_override
        duration_steps = schedule.duration_minutes // 15
        self.slider.value = schedule.target_pct
        self.slider_start.value = schedule.start_minute // 15
        self.slider_dur.value = duration_steps
        self.slider_sunrise_sunset.range_max = duration_steps
        self.slider_sunrise_sunset.min_value = max(1, schedule.sunrise_minutes // 15)
        self.slider_sunrise_sunset.max_value = max(self.slider_sunrise_sunset.min_value, duration_steps - schedule.sunset_minutes // 15)
        if schedule.mode == "off":
            self.lbl_status_text.text = "STATUS: AUS"
            self.lbl_status_text.color = (1, 0.2, 0.2, 0.8)
        elif schedule.mode == "manual":
            self.lbl_status_text.text = "STATUS: MANUELL"
            self.lbl_status_text.color = (0, 0.8, 1, 1)
        else:
            self.lbl_status_text.text = "STATUS: TIMER"
            self.lbl_status_text.color = (0, 1, 0, 1)
        self.lbl_val.color = (1, 0.72, 0.05, 1) if schedule.mode == "time" and state.current_pct != schedule.target_pct and state.current_pct > 0 else (1, 1, 1, 1)
        self._refresh_schedule_labels()
        self._apply_button_styles()

    def _build_command_kwargs(self, **overrides):
        schedule = self._current_schedule()
        return {
            "pct": schedule.target_pct,
            "mode": overrides.get("mode", schedule.mode),
            "h": schedule.start_minute // 60,
            "m": schedule.start_minute % 60,
            "dur": schedule.duration_minutes,
            "sunrise": schedule.sunrise_minutes,
            "sunset": schedule.sunset_minutes,
            "climate_override": overrides.get("climate_override", schedule.climate_override),
        }

    def _apply_button_styles(self):
        base = (0.15, 0.15, 0.15, 1)
        states = (
            (self.btn_man, self._target_mode == "manual", (0, 1, 0, 0.85)),
            (self.btn_tim, self._target_mode == "time", (0, 0.7, 1, 0.85)),
            (self.btn_climate, self._climate_override, (1, 0.5, 0, 0.85)),
        )
        for button, active, color in states:
            button.background_color = color if active else base
            button.color = (0, 0, 0, 1) if active else (1, 1, 1, 1)

    def _set_controls_disabled(self, disabled):
        for slider in (self.slider, self.slider_start, self.slider_dur, self.slider_sunrise_sunset):
            slider.disabled = disabled
        self.uv_preview.set_disabled(disabled)
        self.ir_preview.set_disabled(disabled)
