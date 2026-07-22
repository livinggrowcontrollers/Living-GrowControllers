# config.py
# # -*- coding: utf-8 -*-

import os
import json

from platform_utils import is_android

if is_android():
    app_dir = os.environ.get("ANDROID_ARGUMENT")
    if not app_dir:
        raise RuntimeError("ANDROID_ARGUMENT fehlt: Android-App-Datenpfad ist nicht verfügbar")
    DATA = os.path.join(app_dir, "data")
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    DATA = os.path.join(BASE, "data")

CONFIG_PATH = os.path.join(DATA, "config.json")
METRIC_THEMES = ("standard", "blossom", "aurora")
LEGACY_THEME_ALIASES = {"tiles": "standard", "tiles2": "blossom", "tiles3": "aurora"}

DEFAULTS = {
    "devices": {},
    "user": "admin",
    "pass": "1234",
    "active": True,  # 🔥 Das neue, saubere Flag
    "bridge_profiles": {},
    "refresh_interval": 0.1,
    "stale_timeout": 15.0,
    "graph_resolution": 100.0,
    "graph_smoothing_factor": 1,  # 🔥 Neu: Standard-Smoothing (0.0 = kein Smoothing / 1.0 = hartes Smoothing)
    "tile_graph_window": 400,
    "temperature_unit": "C",
    "temperature_offset": 0.0,
    "humidity_offset": 0.0,
    "leaf_offset": 0.0,
    "developer_mode": False,
    "theme": "standard",
    "lgs_mesh_channel_send": 17,  # Default Kanal 17
    "lgs_mesh_channel_recv": 17,  # Default Kanal 17
    "language": "en",  # "en", "es", "de"
}

# A config UUID remains the key in ``devices``.  This field identifies the
# physical Growmaster behind that entry and is intentionally never derived
# again after a user has renamed the display name.
DEVICE_DEFAULTS = {
    "device_id": "",
}


_config = None


def get_device_id(device):
    """Return the persistent physical-device identity with legacy fallback."""
    if not isinstance(device, dict):
        return ""
    return str(
        device.get("device_id")
        or device.get("hostname")
        or device.get("name")
        or ""
    ).strip()


def validate_device_id(device_id):
    return (
        isinstance(device_id, str)
        and device_id.startswith("growmaster-")
        and len(device_id) > len("growmaster-")
    )


def is_growmaster_device(device):
    return validate_device_id(get_device_id(device))


def _migrate_device_ids(cfg):
    """Add the persistent ID once to legacy device entries.

    Returns whether the in-memory config changed, so callers can persist one
    atomic migration instead of writing during ordinary reads.
    """
    devices = cfg.get("devices", {})
    if not isinstance(devices, dict):
        return False

    changed = False
    for config_uuid, device in devices.items():
        if not isinstance(device, dict):
            continue

        has_device_id = "device_id" in device
        raw_device_id = device.get("device_id", "")
        device_id = str(raw_device_id).strip()
        if raw_device_id != device_id:
            device["device_id"] = device_id
            changed = True
        if not device_id:
            hostname = str(device.get("hostname", "")).strip()
            candidate = hostname or str(device.get("name", "")).strip()
            # An explicit empty value belongs to a copied, not-yet-connected
            # entry.  Old configs have no key at all and are migrated once.
            if not has_device_id or validate_device_id(hostname):
                device_id = candidate
                device["device_id"] = device_id
                changed = True

        if not validate_device_id(device_id) and cfg.get("developer_mode", False):
            print(f"[DEVICE_ID] Invalid or missing device_id for device: {device.get('name') or config_uuid}")

    return changed


def _ensure_device_entry(cfg, mac):
    devices = cfg.setdefault("devices", {})
    entry = devices.setdefault(mac, {})
    if not isinstance(entry, dict):
        entry = devices[mac] = {}
    for key, value in DEVICE_DEFAULTS.items():
        entry.setdefault(key, value)
    return entry


def _init():
    global _config

    if _config is not None:
        return _config

    os.makedirs(DATA, exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        _config = dict(DEFAULTS)
        save(_config)
        return _config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = dict(DEFAULTS)
    except:
        data = dict(DEFAULTS)

    for k, v in DEFAULTS.items():
        data.setdefault(k, v)

    migrated = _migrate_device_ids(data)
    _config = data
    if migrated:
        save(_config)
    return _config


def save(cfg):
    global _config
    _config = cfg

    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)



def get_reboot_after_save():
    """Gibt zurück, ob nach dem Speichern der Config ein Reboot erfolgen soll.
    Dies ist z.B. bei Änderungen an den LGS-Kanälen der Fall.
    """
    cfg = _init()
    return bool(cfg.get("reboot_after_save", False))
def get_device_image(mac):
    """Holt den Dateinamen des Bildes für ein Gerät. 
    Falls keins gesetzt ist, wird anhand des Namens geraten.
    """
    cfg = _init()
    dev_entry = cfg.get("devices", {}).get(mac, {})
    
    # 1. Wenn explizit ein Bild in der Config hinterlegt ist
    if "image_file" in dev_entry and dev_entry["image_file"]:
        return dev_entry["image_file"]
    
    # 2. Fallback / Automatisches Erraten anhand des Namens (wie im Setup)
    name = get_device_id(dev_entry).lower() or dev_entry.get("name", "").lower()
    if "sps" in name:
        return "inkbird.png"
    elif "thermobeacon" in name:
        return "thermobeacon.png"
    elif "tp35" in name or "thermopro" in name:
        return "thermopro.png"
    elif "growmaster" in name:
        return "esp32_s3.png"
    
    return "unknown_device.png"  # Kein Bild gefunden

def set_device_image(mac, image_file):
    """Speichert den Dateinamen des Bildes für ein bestimmtes Gerät"""
    cfg = _init()
    _ensure_device_entry(cfg, mac)["image_file"] = image_file.strip()
    save(cfg)
    
def get_device_auth(mac):
    cfg = _init()
    dev = cfg.get("devices", {}).get(mac, {})
    auth = dev.get("auth", {})
    return auth.get("user"), auth.get("pass")

def set_device_auth(mac, user, pw):
    """Speichert user/pass für ein Gerät"""
    cfg = _init()
    dev_entry = _ensure_device_entry(cfg, mac)
    dev_entry["auth"] = {"user": user, "pass": pw}
    save(cfg)

def get_device_ip(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("ip_address", "")

def set_device_ip(mac, ip):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["ip_address"] = ip.strip()
    save(cfg)

def get_devices():
    cfg = _init()
    devs = cfg.get("devices", {})
    return list(devs.keys()) if isinstance(devs, dict) else []


def get_device_profile(mac):
    d = _init().get("devices", {}).get(mac)
    if not d:
        return "unknown"
    return d.get("profile", "unknown")


def set_device_profile(mac, profile):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["profile"] = profile
    save(cfg)


def set_devices_full(dev_dict):
    cfg = _init()
    cfg["devices"] = dev_dict
    _migrate_device_ids(cfg)
    save(cfg)

def get_theme():
    theme = LEGACY_THEME_ALIASES.get(_init().get("theme", "standard"), _init().get("theme", "standard"))
    return theme if theme in METRIC_THEMES else "standard"

def set_theme(theme: str):
    theme = LEGACY_THEME_ALIASES.get(theme, theme)
    if theme not in METRIC_THEMES:
        raise ValueError(f"Unknown metric theme: {theme}")
    cfg = _init()
    cfg["theme"] = theme
    save(cfg)

def get_refresh_interval():
    return float(_init().get("refresh_interval"))


def get_stale_timeout():
    return float(_init().get("stale_timeout"))


def get_graph_resolution():
    return float(_init().get("graph_resolution"))


def get_temperature_unit():
    return _init().get("temperature_unit", "C").upper()


def get_temperature_offset():
    return float(_init().get("temperature_offset"))


def get_humidity_offset():
    return float(_init().get("humidity_offset"))


def get_leaf_offset():
    return float(_init().get("leaf_offset"))

def reload():
    global _config

    if _config is None:
        _init()
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Defaults sicherstellen
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)

    migrated = _migrate_device_ids(data)

    # ❗WICHTIG: Referenz NICHT ersetzen
    _config.clear()
    _config.update(data)

    if migrated:
        save(_config)

    print("[config] reload OK (in-place)")

def get_bridge_profiles():
    return _init().get("bridge_profiles", {})

def set_bridge_profile(mac, profile):
    cfg = _init()
    bp = cfg.get("bridge_profiles", {})
    bp[mac] = profile
    cfg["bridge_profiles"] = bp
    save(cfg)
def get_adv_decoder(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("adv_decoder", "")

def get_gatt_decoder(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("gatt_decoder", "")

def get_bridge_profile(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("bridge_profile", "")

def get_device_name(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("name", "")


def set_device_name(mac, name):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["name"] = name
    save(cfg)

def set_device_hostname(mac, hostname):
    """Speichert den mDNS-Hostname (ohne .local) für ein Gerät"""
    cfg = _init()
    entry = _ensure_device_entry(cfg, mac)
    hostname = str(hostname or "").strip()
    entry["hostname"] = hostname
    if not entry.get("device_id") and validate_device_id(hostname):
        entry["device_id"] = hostname
    save(cfg)

def set_device_mac(mac, mac_addr):
    """Setzt/normalisiert die MAC-Adresse als Schlüssel/Attribut für ein Gerät"""
    cfg = _init()
    # Wenn der Eintrag unter einer anderen MAC existiert, wird das nicht verschoben.
    _ensure_device_entry(cfg, mac)["mac"] = mac_addr
    save(cfg)
def is_developer_mode():
    return bool(_init().get("developer_mode", False))


def set_developer_mode(state: bool):
    cfg = _init()
    cfg["developer_mode"] = bool(state)
    save(cfg)

def get_tile_graph_window():
    return int(_init().get("tile_graph_window", 120))

def get_lgs_channels():
    cfg = _init()
    return int(cfg.get("lgs_mesh_channel_send", 17)), int(cfg.get("lgs_mesh_channel_recv", 17))

def set_lgs_channels(send, recv):
    cfg = _init()
    cfg["lgs_mesh_channel_send"] = int(send)
    cfg["lgs_mesh_channel_recv"] = int(recv)
    save(cfg)

def get_mixed_enabled(mac):
    cfg = _init()
    return bool(cfg.get("devices", {}).get(mac, {}).get("mixed_enabled", False))


def set_mixed_enabled(mac, state: bool):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["mixed_enabled"] = bool(state)
    save(cfg)


def get_mixed_external(mac):
    cfg = _init()
    return bool(cfg.get("devices", {}).get(mac, {}).get("mixed_external", False))


def set_mixed_external(mac, state: bool):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["mixed_external"] = bool(state)
    save(cfg)


def get_mixed_modes(mac):
    """Holt die aktiven Modi für ein Gerät als Set (z.B. {"internal"}, {"external"} oder {"internal", "external"})."""
    cfg = _init()
    dev_entry = cfg.get("devices", {}).get(mac, {})
    
    modes = set()
    # Wenn "mixed_external" True ist, fügen wir external hinzu
    if bool(dev_entry.get("mixed_external", False)):
        modes.add("external")
    
    # NEU: Wir prüfen ein explizites internal Flag. Wenn nichts gesetzt ist, 
    # nehmen wir "internal" als Standard-Fallback an, damit alte Configs nicht brechen.
    if dev_entry.get("mixed_internal", True):
        modes.add("internal")
        
    # Sicherheitsnetz: Falls jemals ein leerer Zustand entsteht, erzwinge internal
    if not modes:
        modes.add("internal")
        
    return modes


def set_mixed_modes(mac, modes_set):
    """Speichert die aktiven Modi (Set) präzise als zwei getrennte Flags in die Config."""
    cfg = _init()
    dev_entry = _ensure_device_entry(cfg, mac)
    dev_entry["mixed_internal"] = "internal" in modes_set
    dev_entry["mixed_external"] = "external" in modes_set
    save(cfg)

def is_device_protected(mac):
    cfg = _init()
    return bool(cfg.get("devices", {}).get(mac, {}).get("protected", False))

def set_device_protected(mac, state: bool):
    cfg = _init()
    _ensure_device_entry(cfg, mac)["protected"] = bool(state)
    save(cfg)

# Falls deine config.py Getter-Methoden nutzt, füge diese hinzu:
def get_graph_smoothing_factor():
    cfg = _init()
    return float(cfg.get("graph_smoothing_factor", 0.1))
