"""Canonical capability truth shared by HeaderBar and device-picker rows."""

from dashboard_gui.circulation_fan_registry import MAX_CIRCULATION_FANS, fan_snapshot
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater


def build_header_state(frame):
    """Extract exactly the capability-relevant HeaderBar state from a frame."""
    frame = frame or {}
    web = frame.get("webserver", {})
    health = frame.get("health", {})
    return {
        "light": web.get("light_pct"),
        "circulation_fans": {fan_id: fan_snapshot(web, fan_id) for fan_id in range(1, MAX_CIRCULATION_FANS + 1)},
        "exhaust_fan_rpm": web.get("exhaust_fan", {}).get("exhaust_fan_rpm"),
        "battery": health.get("battery", {}).get("voltage") or web.get("battery_voltage"),
        "external": any(frame.get(channel, {}).get("external", {}).get("present", False) for channel in ("adv", "gatt", "webserver")),
        "external2": bool(health.get("external2", {}).get("present") or web.get("external2", {}).get("present", False)),
        "climate_hub": bool(frame.get("climate_hub") or web.get("climate_hub", False)),
        "broadcast_available": False,
    }


def build_header_capabilities(state, push_active=False):
    """Return the ordered Header truth; consumers decide only how to render it."""
    state = state or {}
    capabilities = [
        {"id": "light", "label": "Light Control", "icon": "\uf0eb", "enabled": state.get("light") is not None,
         "color": (*BoxColorUpdater.get_light_color(state.get("light") or 0), 1), "show_in_picker": True},
    ]
    for fan_id in range(1, MAX_CIRCULATION_FANS + 1):
        fan = state.get("circulation_fans", {}).get(fan_id, {})
        rpm = fan.get("rpm") if fan.get("rpm") is not None else -256
        capabilities.append({
            "id": f"circulation_fan_{fan_id}", "label": f"Circulation Fan {fan_id}", "icon": "\uf863",
            "enabled": bool(fan.get("enabled")), "color": (*BoxColorUpdater.get_rpm_color(rpm), 1), "show_in_picker": True,
        })
    exhaust_rpm = state.get("exhaust_fan_rpm")
    capabilities.extend((
        {"id": "exhaust_fan", "label": "Exhaust Fan", "icon": "\uf863", "enabled": exhaust_rpm is not None,
         "color": (*BoxColorUpdater.get_rpm_color(exhaust_rpm if exhaust_rpm is not None else -256), 1), "show_in_picker": True},
        {"id": "broadcast", "label": "Broadcast", "icon": "\uf09e", "enabled": bool(state.get("broadcast_available")),
         "color": (0.7, 0.7, 0.7, 1), "show_in_picker": False},
        {"id": "battery", "label": "Battery", "icon": "\uf244", "enabled": state.get("battery") is not None,
         "color": (*BoxColorUpdater.get_battery_color(state.get("battery") or 0), 1), "show_in_picker": True},
        {"id": "external", "label": "External Sensor", "icon": "\uf2c9", "enabled": bool(state.get("external")),
         "color": (*BoxColorUpdater.get_external_color(), 1), "show_in_picker": True},
        {"id": "external2", "label": "External Sensor 2", "icon": "\uf2c9", "enabled": bool(state.get("external2")),
         "color": (*BoxColorUpdater.get_external_color(), 1), "show_in_picker": False},
        {"id": "climate_hub", "label": "Climate Hub", "icon": "\uf0c2", "enabled": bool(state.get("climate_hub")),
         "color": (*BoxColorUpdater.get_external_color(), 1), "show_in_picker": True},
        {"id": "push_message", "label": "Push Messages", "icon": "\uf0f3", "enabled": bool(push_active),
         "color": (0.6, 0.6, 0.6, 1), "show_in_picker": False},
    ))
    return capabilities
