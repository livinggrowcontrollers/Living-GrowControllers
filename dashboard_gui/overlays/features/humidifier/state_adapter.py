from dataclasses import dataclass

from dashboard_gui.overlays.features.shared.coercion import as_int


@dataclass(frozen=True)
class HumidifierState:
    revision: int
    target_pct: int
    live_pct: int
    status: str
    present: bool
    enabled: bool


class HumidifierStateAdapter:
    @staticmethod
    def decode(raw):
        raw = raw or {}
        target = raw.get("humidifier_pct")
        live = raw.get("humidifier_speed_now")
        status = str(raw.get("humidifier_status") or "disabled")
        return HumidifierState(
            revision=as_int(raw.get("rev_humidifier"), 0),
            target_pct=as_int(target, 60),
            live_pct=as_int(live, 0),
            status=status,
            present="rev_humidifier" in raw,
            enabled=target is not None and live is not None and status != "disabled",
        )

    @staticmethod
    def revision(state):
        return state.revision
