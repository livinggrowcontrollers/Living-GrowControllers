# dashboard_gui/overlays/features/exhaust/state_adapter.py

from dataclasses import dataclass

from dashboard_gui.overlays.features.shared.coercion import as_int


@dataclass(frozen=True)
class ExhaustFanState:
    revision: int
    target_min: int
    target_max: int
    mode: str
    chaos_enabled: bool
    rpm: int
    live_speed: int
    reason_primary: str
    reason_secondary: str


class ExhaustFanStateAdapter:
    @staticmethod
    def decode(raw):
        fan = raw.get("exhaust_fan", {}) if isinstance(raw.get("exhaust_fan"), dict) else {}
        return ExhaustFanState(
            revision=as_int(raw.get("rev_exhaust"), 0),
            target_min=as_int(raw.get("exhaust_fan_min"), 20),
            target_max=as_int(raw.get("exhaust_fan_pct"), 65),
            mode=str(raw.get("exhaust_fan_mode") or "auto"),
            chaos_enabled=bool(raw.get("exhaust_fan_chaos_active", raw.get("exhaust_fan_chaos", False))),
            rpm=as_int(fan.get("exhaust_fan_rpm"), 0),
            live_speed=as_int(raw.get("exhaust_fan_speed_now"), 0),
            reason_primary=str(raw.get("exhaust_fan_state_reason_1", "idle")),
            reason_secondary=str(raw.get("exhaust_fan_state_reason_2", "")),
        )

    @staticmethod
    def revision(state):
        return state.revision
