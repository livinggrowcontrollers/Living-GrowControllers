"""Single protocol adapter for the up-to-three generated circulation fans."""

MAX_CIRCULATION_FANS = 3


def fan_prefix(fan_id):
    fan_id = int(fan_id)
    if not 1 <= fan_id <= MAX_CIRCULATION_FANS:
        raise ValueError("fan_id must be between 1 and 3")
    return "circulation_fan" if fan_id == 1 else f"circulation_fan{fan_id}"


def fan_revision_key(fan_id):
    return "rev_circfan" if int(fan_id) == 1 else f"rev_circfan{int(fan_id)}"


def fan_gpio_keys(fan_id):
    """ESP GPIO field names for one generated circulation-fan module."""
    suffix = "" if int(fan_id) == 1 else str(int(fan_id))
    return (f"p_c_fan{suffix}", f"p_c_tac{suffix}", f"p_c_tac{suffix}_pull")


def fan_snapshot(data, fan_id):
    """Expose every ESP fan in the original Fan-1 shape for reusable UI."""
    data = data or {}
    prefix = fan_prefix(fan_id)
    rpm = data.get(f"{prefix}_rpm")
    if int(fan_id) == 1:
        rpm = data.get("circulation_fan", {}).get("circulation_fan_rpm", rpm)
    present = any(key in data for key in (f"{prefix}_rpm", f"{prefix}_pct", fan_revision_key(fan_id)))
    return {
        "fan_id": int(fan_id),
        "present": present,
        "enabled": present and rpm is not None and rpm > -250,
        "rpm": rpm,
        "live": data.get(f"{prefix}_speed_now"),
        "min": data.get(f"{prefix}_min"),
        "max": data.get(f"{prefix}_pct"),
        "mode": data.get(f"{prefix}_mode", "off"),
        "rev": data.get(fan_revision_key(fan_id), 0),
    }


def overlay_snapshot(data, fan_id):
    """Compatibility view so existing Fan-1 overlay labels stay generic."""
    fan = fan_snapshot(data, fan_id)
    return {
        "rev_circfan": fan["rev"],
        # The overlay may be opened for a configured-but-disabled fan.  Keep
        # its controls numeric instead of leaking None into Kivy's int().
        "circulation_fan_min": 20 if fan["min"] is None else fan["min"],
        "circulation_fan_pct": 65 if fan["max"] is None else fan["max"],
        "circulation_fan_mode": fan["mode"],
        "circulation_fan_speed_now": 0 if fan["live"] is None else fan["live"],
        "circulation_fan": {"circulation_fan_rpm": 0 if fan["rpm"] is None else fan["rpm"]},
    }


def add_normalized_fans(raw, decoded):
    decoded["circulation_fans"] = {
        str(fan_id): fan_snapshot(raw, fan_id)
        for fan_id in range(1, MAX_CIRCULATION_FANS + 1)
        if fan_snapshot(raw, fan_id)["present"]
    }
