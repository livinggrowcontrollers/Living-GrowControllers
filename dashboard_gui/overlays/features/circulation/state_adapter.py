# dashboard_gui/overlays/features/circulation/state_adapter.py

from dataclasses import dataclass

from dashboard_gui.circulation_fan_registry import fan_snapshot


@dataclass(frozen=True)
class CirculationFanState:
    fan_id: int
    revision: int
    target_min: int
    target_max: int
    mode: str
    live_speed: int
    rpm: int
    present: bool
    enabled: bool


class CirculationFanStateAdapter:
    def __init__(self, fan_id):
        self.fan_id = int(fan_id)

    def decode(self, raw):
        fan = fan_snapshot(raw, self.fan_id)
        return CirculationFanState(
            fan_id=self.fan_id,
            revision=int(fan.get("rev") or 0),
            target_min=int(20 if fan.get("min") is None else fan["min"]),
            target_max=int(65 if fan.get("max") is None else fan["max"]),
            mode=str(fan.get("mode") or "nat"),
            live_speed=int(fan.get("live") or 0),
            rpm=int(fan.get("rpm") or 0),
            present=bool(fan.get("present")),
            enabled=bool(fan.get("enabled")),
        )

    @staticmethod
    def revision(state):
        return state.revision
