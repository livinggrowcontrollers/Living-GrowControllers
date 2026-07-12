#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json

from platform_utils import is_android

if is_android():
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ctx = PythonActivity.mActivity
    DATA = os.path.join(ctx.getFilesDir().getAbsolutePath(), "app", "data")
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    DATA = os.path.join(BASE, "data")

CONFIG_PATH = os.path.join(DATA, "config.json")

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
    "theme": "tiles",   # tiles | tiles2 | tiles3
    "lgs_mesh_channel_send": 17,  # Default Kanal 17
    "lgs_mesh_channel_recv": 17,  # Default Kanal 17
    "language": "en",  # "en", "es", "de"
}


_config = None


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

    _config = data
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
    name = dev_entry.get("name", "").lower()
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
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["image_file"] = image_file.strip()
    save(cfg)
    
def get_device_auth(mac):
    cfg = _init()
    dev = cfg.get("devices", {}).get(mac, {})
    auth = dev.get("auth", {})
    return auth.get("user"), auth.get("pass")

def set_device_auth(mac, user, pw):
    """Speichert user/pass für ein Gerät"""
    cfg = _init()
    devs = cfg.setdefault("devices", {})
    dev_entry = devs.setdefault(mac, {})
    dev_entry["auth"] = {"user": user, "pass": pw}
    save(cfg)

def get_device_ip(mac):
    cfg = _init()
    return cfg.get("devices", {}).get(mac, {}).get("ip_address", "")

def set_device_ip(mac, ip):
    cfg = _init()
    devs = cfg.setdefault("devices", {}) # <-- Garantiert, dass es fest im cfg-Verzeichnis verankert ist
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["ip_address"] = ip.strip()
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
    devs = cfg["devices"]
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["profile"] = profile
    save(cfg)


def set_devices_full(dev_dict):
    cfg = _init()
    cfg["devices"] = dev_dict
    save(cfg)

def get_theme():
    return _init().get("theme", "tiles")

def set_theme(theme: str):
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

    # ❗WICHTIG: Referenz NICHT ersetzen
    _config.clear()
    _config.update(data)

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
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["name"] = name
    save(cfg)

def set_device_hostname(mac, hostname):
    """Speichert den mDNS-Hostname (ohne .local) für ein Gerät"""
    cfg = _init()
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["hostname"] = hostname
    save(cfg)

def set_device_mac(mac, mac_addr):
    """Setzt/normalisiert die MAC-Adresse als Schlüssel/Attribut für ein Gerät"""
    cfg = _init()
    devs = cfg.get("devices", {})
    # Wenn der Eintrag unter einer anderen MAC existiert, wird das nicht verschoben.
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["mac"] = mac_addr
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
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["mixed_enabled"] = bool(state)
    save(cfg)


def get_mixed_external(mac):
    cfg = _init()
    return bool(cfg.get("devices", {}).get(mac, {}).get("mixed_external", False))


def set_mixed_external(mac, state: bool):
    cfg = _init()
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["mixed_external"] = bool(state)
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
    devs = cfg.setdefault("devices", {})
    if mac not in devs:
        devs[mac] = {}
        
    devs[mac]["mixed_internal"] = "internal" in modes_set
    devs[mac]["mixed_external"] = "external" in modes_set
    save(cfg)

def is_device_protected(mac):
    cfg = _init()
    return bool(cfg.get("devices", {}).get(mac, {}).get("protected", False))

def set_device_protected(mac, state: bool):
    cfg = _init()
    devs = cfg.get("devices", {})
    if mac not in devs:
        devs[mac] = {}
    devs[mac]["protected"] = bool(state)
    save(cfg)

# Falls deine config.py Getter-Methoden nutzt, füge diese hinzu:
def get_graph_smoothing_factor():
    cfg = _init()
    return float(cfg.get("graph_smoothing_factor", 0.1))