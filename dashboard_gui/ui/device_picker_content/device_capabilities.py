from dashboard_gui.ui.scaling_utils import dp_scaled

def extract_capabilities(frame):
    if not isinstance(frame, dict):
        return []

    web = frame.get("webserver", {})
    health = frame.get("health", {})

    caps = []

    # LIGHT
    if web.get("light_pct") is not None:
        caps.append(("light", "\uf0eb"))

    # FANS
    if web.get("circulation_fan", {}).get("circulation_fan_rpm") is not None:
        caps.append(("fan", "\uf863"))

    if web.get("exhaust_fan", {}).get("exhaust_fan_rpm") is not None:
        caps.append(("fan", "\uf863"))

    # BATTERY
    if health.get("battery", {}).get("voltage") or web.get("battery_voltage"):
        caps.append(("battery", "\uf244"))

    # EXTERNAL
    if any(
        frame.get(ch, {}).get("external", {}).get("present")
        for ch in ("adv", "gatt", "webserver")
    ):
        caps.append(("external", "\uf2c9"))

    # CLIMATE HUB
    if frame.get("climate_hub") or web.get("climate_hub"):
        caps.append(("climate", "\uf0c2"))

    return caps