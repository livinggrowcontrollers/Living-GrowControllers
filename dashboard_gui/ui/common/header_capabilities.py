"""Canonical capability truth shared by HeaderBar and device-picker rows."""

from dashboard_gui.circulation_fan_registry import MAX_CIRCULATION_FANS, fan_snapshot
from dashboard_gui.overlays.components.status_colors import StatusColors


def build_header_state(frame):
    """Extract exactly the capability-relevant HeaderBar state from a frame."""
    frame = frame or {}
    web = frame.get("webserver", {})
    health = frame.get("health", {})
    climate_target_keys = (
        "target_temp_min", "target_temp_max",
        "target_humidity_min", "target_humidity_max",
        "target_vpd_min", "target_vpd_max",
    )
    climate_hub_active = all(web.get(key) is not None for key in climate_target_keys)
    return {
        "light": web.get("light_pct"),
        "circulation_fans": {fan_id: fan_snapshot(web, fan_id) for fan_id in range(1, MAX_CIRCULATION_FANS + 1)},
        "exhaust_fan_rpm": web.get("exhaust_fan", {}).get("exhaust_fan_rpm"),
        "humidifier_speed_now": web.get("humidifier_speed_now"),
        "battery": health.get("battery", {}).get("voltage") or web.get("battery_voltage"),
        "external": any(frame.get(channel, {}).get("external", {}).get("present", False) for channel in ("adv", "gatt", "webserver")),
        "external2": bool(health.get("external2", {}).get("present") or web.get("external2", {}).get("present", False)),
        "climate_hub": climate_hub_active,
        "climate_hub_color": StatusColors.get_climate_color(web),
        "broadcast_available": False,
    }


def build_header_capabilities(state, push_active=False):
    """Return the ordered Header truth; consumers decide only how to render it."""
    state = state or {}
    battery_voltage = state.get("battery")
    battery_icon, _ = StatusColors.get_battery_state(battery_voltage)
    capabilities = [
        {"id": "light", "label": "Light Control", "icon": "\uf0eb", "enabled": state.get("light") is not None,
         "color": (*StatusColors.get_light_color(state.get("light") or 0), 1), "value": state.get("light"),
         "show_in_picker": True},
    ]
    for fan_id in range(1, MAX_CIRCULATION_FANS + 1):
        fan = state.get("circulation_fans", {}).get(fan_id, {})
        rpm = fan.get("rpm") if fan.get("rpm") is not None else -256
        capabilities.append({
            # Umluft und Abluft intentionally have different Header glyphs.
            "id": f"circulation_fan_{fan_id}", "label": f"Circulation Fan {fan_id}", "icon": "\uf72e",
            "enabled": bool(fan.get("enabled")), "color": (*StatusColors.get_rpm_color(rpm), 1), "value": rpm,
            "show_in_picker": True,
        })
    exhaust_rpm = state.get("exhaust_fan_rpm")
    humidifier_speed_now = state.get("humidifier_speed_now")
    capabilities.extend((
        {"id": "exhaust_fan", "label": "Exhaust Fan", "icon": "\uf863", "enabled": exhaust_rpm is not None,
         "color": (*StatusColors.get_rpm_color(exhaust_rpm if exhaust_rpm is not None else -256), 1), "value": exhaust_rpm,
         "show_in_picker": True},
        {"id": "humidifier", "label": "Humidifier", "icon": "\uf043", "enabled": humidifier_speed_now is not None,
         "color": (*StatusColors.get_output_color(humidifier_speed_now), 1), "value": humidifier_speed_now,
         "show_in_picker": True},
        {"id": "broadcast", "label": "Broadcast", "icon": "\uf09e", "enabled": bool(state.get("broadcast_available")),
         "color": (0.7, 0.7, 0.7, 1), "show_in_picker": False},
        {"id": "battery", "label": "Battery", "icon": battery_icon, "enabled": battery_voltage is not None,
         "color": (*StatusColors.get_battery_color(battery_voltage), 1), "value": battery_voltage, "show_in_picker": True},
        {"id": "external", "label": "External Sensor", "icon": StatusColors.get_external_state(bool(state.get("external")))[0], "enabled": bool(state.get("external")),
         "color": (*StatusColors.get_external_color(), 1), "value": bool(state.get("external")), "show_in_picker": True},
        {"id": "external2", "label": "External Sensor 2", "icon": "\uf2c7", "enabled": bool(state.get("external2")),
         "color": (*StatusColors.get_external_color(), 1), "show_in_picker": False},
        {"id": "climate_hub", "label": "Climate Hub", "icon": "\uf0c2", "enabled": bool(state.get("climate_hub")),
         "color": (*state.get("climate_hub_color", (0.35, 0.35, 0.35)), 1), "show_in_picker": True},
        {"id": "push_message", "label": "Push Messages", "icon": "\uf0f3", "enabled": bool(push_active),
         "color": (0.6, 0.6, 0.6, 1), "show_in_picker": False},
    ))
    return capabilities
