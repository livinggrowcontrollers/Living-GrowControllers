# dashboard_gui/overlays/features/climate_hub/state_adapter.py


from dataclasses import dataclass

from dashboard_gui.overlays.components.status_colors import StatusColors
from dashboard_gui.overlays.features.shared.coercion import as_float, as_int
from .targets import ClimateTargets


@dataclass(frozen=True)
class ClimateHubState:
    revision: int
    climate: ClimateTargets
    night_reduction_enabled: bool
    plant_phase: int
    live_temperature: object
    temperature_unit: str
    live_humidity: object
    humidity_unit: str
    live_vpd: object
    vpd_unit: str
    accent: tuple


class ClimateHubStateAdapter:
    @staticmethod
    def decode(raw):
        internal = raw.get("internal", {}) if isinstance(raw.get("internal"), dict) else {}
        temperature = internal.get("temperature", {}) if isinstance(internal.get("temperature"), dict) else {}
        humidity = internal.get("humidity", {}) if isinstance(internal.get("humidity"), dict) else {}
        vpd_node = raw.get("vpd_internal", {})
        live_vpd = vpd_node.get("value") if isinstance(vpd_node, dict) else vpd_node
        vpd_unit = vpd_node.get("unit", "kPa") if isinstance(vpd_node, dict) else "kPa"
        return ClimateHubState(
            revision=as_int(raw.get("rev_exhaust"), 0),
            climate=ClimateTargets(
                temp_min=as_float(raw.get("target_temp_min"), 22.0),
                temp_max=as_float(raw.get("target_temp_max"), 28.0),
                humidity_min=as_int(raw.get("target_humidity_min"), 45),
                humidity_max=as_int(raw.get("target_humidity_max"), 70),
                vpd_min=as_float(raw.get("target_vpd_min"), 0.8),
                vpd_max=as_float(raw.get("target_vpd_max"), 1.5),
            ),
            night_reduction_enabled=bool(raw.get("exhaust_fan_night_reduction", True)),
            plant_phase=as_int(raw.get("plant_phase"), 0),
            live_temperature=None if temperature.get("value") is None else as_float(temperature.get("value")),
            temperature_unit=str(temperature.get("unit", "°C")),
            live_humidity=None if humidity.get("value") is None else as_float(humidity.get("value")),
            humidity_unit=str(humidity.get("unit", "%")),
            live_vpd=None if live_vpd is None else as_float(live_vpd),
            vpd_unit=str(vpd_unit),
            accent=StatusColors.get_climate_color(raw),
        )

    @staticmethod
    def revision(state):
        return state.revision
