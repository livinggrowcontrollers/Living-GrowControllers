from dataclasses import dataclass

from dashboard_gui.ui.common.logic.light_time import calculate_light_time
from dashboard_gui.overlays.features.shared.coercion import as_int
from .schedule import LightSchedule


@dataclass(frozen=True)
class LightState:
    revision: int
    schedule: LightSchedule
    current_pct: int
    state_reason: str
    remaining_text: str


class LightStateAdapter:
    @staticmethod
    def decode(raw):
        schedule = LightSchedule(
            mode=str(raw.get("light_mode") or "time"),
            target_pct=as_int(raw.get("light_target", raw.get("light_pct")), 0),
            start_minute=as_int(raw.get("l_start_h"), 8) * 60 + as_int(raw.get("l_start_m"), 0),
            duration_minutes=as_int(raw.get("l_dur"), 720),
            sunrise_minutes=as_int(raw.get("l_sunrise"), 60),
            sunset_minutes=as_int(raw.get("l_sunset"), 60),
            climate_override=bool(raw.get("light_climate_override", False)),
        ).normalized()
        try:
            remaining_text = calculate_light_time(raw)
        except (TypeError, ValueError):
            remaining_text = "REMAINING: --"
        return LightState(
            revision=as_int(raw.get("rev_light"), 0),
            schedule=schedule,
            current_pct=as_int(raw.get("light_pct"), 0),
            state_reason=str(raw.get("light_state_reason", "DAY")).upper().strip(),
            remaining_text=remaining_text,
        )

    @staticmethod
    def revision(state):
        return state.revision
