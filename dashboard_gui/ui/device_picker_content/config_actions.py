import config
from kivy.clock import Clock
from dashboard_gui.global_state_manager import GLOBAL_STATE

def notify_global_state():
    """Config-Änderung → alles neu syncen"""
    try:
        GLOBAL_STATE.refresh_config()
        reloaded_cfg = config._init()
        print(f"[DevicePicker] Config reloaded: {reloaded_cfg}")
        print("[DevicePicker] Global state notified")
    except Exception as e:
        print(f"[DevicePicker] Notify failed: {e}")

def rebuild_active_index(deleted_mac=None):
    """Sichere Neuberechnung des active_index nach Änderungen"""
    ace = GLOBAL_STATE.active_channel_engine
    if not ace:
        return
        
    current_list = ace.get_device_list()
    old_index = ace.get_active_index()
    
    if not current_list:
        ace.active_index = 0
        return

    current_active = GLOBAL_STATE.get_active_device_id()

    if deleted_mac and deleted_mac == current_active:
        ace.active_index = 0
        print("[DevicePicker] Active device deleted -> fallback index 0")
    else:
        ace.active_index = min(old_index, len(current_list) - 1)

    ace._last_counter = None
    GLOBAL_STATE.set_active_index(ace.active_index)

def move_device(mac, direction, rebuild_callback):
    cfg = config._init()
    devices = cfg.get("devices", {})
    keys = list(devices.keys())
    if mac not in keys: return
    idx = keys.index(mac)

    if direction == "up" and idx > 0: swap_idx = idx - 1
    elif direction == "down" and idx < len(keys) - 1: swap_idx = idx + 1
    else: return

    keys[idx], keys[swap_idx] = keys[swap_idx], keys[idx]
    new_devices = {k: devices[k] for k in keys}
    cfg["devices"] = new_devices
    config.save(cfg)
    
    rebuild_callback()
    notify_global_state()
    rebuild_active_index()

def delete_device(mac, rebuild_callback):
    import core
    cfg = config._init()
    devices = cfg.get("devices", {})

    if mac not in devices:
        return

    active_before = GLOBAL_STATE.get_active_device_id()
    del devices[mac]
    config.save(cfg)

    print(f"[DevicePicker] Deleted device {mac}")
    notify_global_state()

    ace = GLOBAL_STATE.active_channel_engine
    current_list = ace.get_device_list() if ace else []

    if not current_list and ace:
        ace.active_index = 0
        ace._last_counter = None
        if hasattr(ace, "_rebuild_device_list"):
            ace._rebuild_device_list()
    elif ace:
        if mac == active_before:
            ace.active_index = 0
        else:
            ace.active_index = min(ace.active_index, len(current_list) - 1)
        ace._last_counter = None
        GLOBAL_STATE.set_active_index(ace.active_index)



    Clock.schedule_once(lambda dt: rebuild_callback(), 0.05)

def delete_all_devices(rebuild_callback):
    import core
    cfg = config._init()
    devices = cfg.get("devices", {})

    if len(devices) <= 1:
        print("[DevicePicker] Abgebrochen: Das letzte Gerät ist schreibgeschützt.")
        return

    first_key = list(devices.keys())[0]
    protected_device = {first_key: devices[first_key]}
    cfg["devices"] = protected_device
    config.save(cfg)

    notify_global_state()

    ace = GLOBAL_STATE.active_channel_engine
    if ace:
        ace.active_index = 0
        ace._last_counter = None
        if hasattr(ace, "_rebuild_device_list"):
            ace._rebuild_device_list()


    Clock.schedule_once(lambda dt: rebuild_callback(), 0.05)

def copy_device(mac, rebuild_callback):
    import uuid
    import copy
    cfg = config._init()
    devices = cfg.get("devices", {})

    if mac not in devices:
        return

    new_dev = copy.deepcopy(devices[mac])

    # 🔥 HARD RESET IDENTITY
    new_id = str(uuid.uuid4())
    new_dev["mac"] = None
    new_dev["name"] = f"{new_dev.get('name','')} (Copy)"

    devices[new_id] = new_dev
    config.save(cfg)
    
    # Callback nutzen statt self._build()
    rebuild_callback()

def toggle_mixed_mode(mac, screen):
    """Mixed-Mode eines Geräts umschalten."""

    if mac in GLOBAL_STATE.mixed_selected_buffers:
        GLOBAL_STATE.mixed_selected_buffers.remove(mac)
        config.set_mixed_enabled(mac, False)

    else:
        GLOBAL_STATE.mixed_selected_buffers.add(mac)
        config.set_mixed_enabled(mac, True)

        if mac not in GLOBAL_STATE.mixed_device_modes:
            GLOBAL_STATE.mixed_device_modes[mac] = {"internal"}
            config.set_mixed_external(mac, False)

    if hasattr(screen, "_build"):
        screen._build()