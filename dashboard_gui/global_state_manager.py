# dashboard_gui/global_state_manager.py
# HEARTBEAT + MULTI-DEVICE – CLEAN VERSION
from kivy.clock import Clock
import time
import config
from dashboard_gui.gsm_engines.graph_engine import GraphEngine
from dashboard_gui.gsm_engines.ui_screen_button_engine import UIManager # oben importieren
from dashboard_gui.gsm_engines.config_engine import ConfigEngine# oben importieren
from dashboard_gui.gsm_engines.led_engine import LedEngine
from dashboard_gui.gsm_engines.mixed_engine import MixedEngine
from dashboard_gui.gsm_engines.metrics_engine import MetricsEngine
from dashboard_gui.gsm_engines.gatt_config_engine import GattConfigEngine
from dashboard_gui.gsm_engines.active_channel_engine import ActiveChannelEngine
from dashboard_gui.gsm_engines.unit_engine import UnitEngine
from dashboard_gui.gsm_engines.multi_active_key_engine import MultiActiveKeyEngine
from dashboard_gui.gsm_engines.tile_engine import TileEngine
# In deiner global_state_manager.py
from dashboard_gui.global_gesture_manager import GlobalGestureManager
from dashboard_gui.gsm_engines.data_flow_engine import DataFlowEngine
from dashboard_gui.gsm_engines.broadcast_engine import BroadcastEngine
from dashboard_gui.gsm_engines.overlay_command_engine import OverlayCommandEngine
from dashboard_gui.gsm_engines.graph_control_engine import GraphControlEngine


class GlobalStateManager:
    def __init__(self):
        self.running = True
        self.screen_manager = None

        # Mixed Mode
        self.mixed_selected_buffers = set()
        self.mixed_device_modes = {}

        self.max_history = config.get_tile_graph_window()

        # Engines
        self.graph_engine = GraphEngine(self)
        self.ui_handler = UIManager(self)
        self.engine = ConfigEngine(self)
        self.led_engine = LedEngine(self.ui_handler)
        self.mixed_engine = MixedEngine(self)
        self.mixed_engine.init_file()
        self.metrics_engine = MetricsEngine(self)
        self.gatt_engine = GattConfigEngine(self)
        self.unit_engine = UnitEngine(self)
        self.multi_key_engine = MultiActiveKeyEngine(self)
        self.tile_engine = TileEngine(self)
        self.ggm = GlobalGestureManager(self)
        self.broadcast_engine = BroadcastEngine(self)
        self.graph_control = GraphControlEngine(self)
        self.overlay_engine = OverlayCommandEngine(self)
        
        self.active_channel_engine = ActiveChannelEngine(self.gatt_engine)
        
        # ✅ ERST DANACH DataFlow!
        self.data_flow = DataFlowEngine(self)

        # Der Tick darf erst starten, wenn alle von ihm verwendeten Engines
        # vollständig aufgebaut sind.
        self._main_tick = Clock.schedule_interval(
            self._global_update, config.get_refresh_interval()
        )
    def sync_ui_buttons(self):
        """Triggert den Sync-Vorgang im UI Manager an."""
        self.ui_handler._refresh_all_buttons()

    def get_active_device_mac(self):
        """Alias für get_active_device_id, da diese die MAC zurückgibt."""
        return self.get_active_device_id()
    def get_active_device_id(self):
        """Gibt die ID des aktuell angewählten Geräts zurück."""
        try:
            # Jetzt existiert self.active_channel_engine!
            idx = self.active_channel_engine.get_active_index()
            dev_list = self.active_channel_engine.get_device_list()
            
            if dev_list and idx < len(dev_list):
                return dev_list[idx]
        except Exception as e:
            print(f"[GSM] Error getting active device id: {e}")
        return None

    def get_active_device_ip(self):
        """Gibt die IP des aktuell aktiven Geräts zurück."""
        dev_id = self.get_active_device_id()
        if not dev_id:
            return None  # Kein aktives Gerät
        try:
            cfg = config._init()
            devices = cfg.get("devices", {})
            return devices.get(dev_id, {}).get("ip_address")
        except Exception as e:
            print(f"[GSM] Error getting active device IP: {e}")
            return None
         
    # In global_state_manager.py
    def get_active_channel(self):
        return self.active_channel_engine.get_active_channel()
    
    def set_active_channel(self, channel):
        self.active_channel_engine.set_active_channel(channel)
        self.data_flow.process_cycle()

    def get_active_index(self):
        return self.active_channel_engine.get_active_index()

    def set_active_index(self, idx):
        self.active_channel_engine.set_active_index(idx)

    def next_device(self):
        self.active_channel_engine.next_device()

    def previous_device(self):
        self.active_channel_engine.previous_device()

    def get_device_list(self):
        return self.active_channel_engine.get_device_list()

    def get_last_seen_text(self, dev_id):
        """Gibt einen menschlich lesbaren String zurück."""
        last_ts = self.data_flow.last_seen_timestamps.get(dev_id)
        if not last_ts:
            return "Nie gesehen"
        
        diff = time.time() - last_ts
        if diff < 2:
            return "Jetzt"
        if diff < 60:
            return f"vor {int(diff)}s"
        return f"vor {int(diff/60)}m"

    # --- BROADCAST DELEGATION ---
    def get_broadcast_active(self):
        return self.broadcast_engine.active    

    def set_broadcast_active(self, state):
        # Ruft die neue Engine-Logik auf (inkl. core start/stop)
        self.broadcast_engine.set_active(state)

    def set_broadcast_available(self, state: bool):
        self.broadcast_engine.set_available(state)

    def set_broadcast_user_disabled(self, state: bool):
        self.broadcast_engine.set_user_disabled(state)

    def send_overlay_command(self, cmd_type, **kwargs):
        """Der GSM routet nur noch – keine Logik mehr hier drin!"""
        mac = self.get_active_device_id()
        if not mac: 
            return None
        
        # Der GSM sagt nur: "OCE, kümmere dich drum!"
        return self.overlay_engine.process_command(mac, cmd_type, **kwargs)

    def retry_overlay_command(self, cmd_type, instance_id=None):
        """Resend the last pending target with its original revision."""
        mac = self.get_active_device_id()
        if not mac:
            return None
        return self.overlay_engine.retry_command(mac, cmd_type, instance_id=instance_id)
    
    
    # ---------------------------------------------------------
    # TILE ENGINE – Delegation
    # ---------------------------------------------------------

    def register_tiles(self, tiles, device_id=None, channel=None):
        self.tile_engine.register_tiles(tiles, device_id, channel)

    def get_active_tiles(self, device_id=None, channel=None):
        return self.tile_engine.get_active_tiles(device_id, channel)

    def build_tile_key(self, device_id, channel, tile_id):
        return self.tile_engine.build_full_key(device_id, channel, tile_id)

    def next_tile(self, tile_id, direction):
        return self.tile_engine.get_next_tile(tile_id, direction)

    def next_tile_key(self, full_key, direction):
        return self.tile_engine.get_next_full_key(full_key, direction)

    # ---------------------------------------------------------
    # PUBLIC API – Device Switch
    # ---------------------------------------------------------
    def get_device_label(self, device_id):
        try:
            cfg = config._init()
            devices = cfg.get("devices", {})
            dev = devices.get(device_id, {})
            return dev.get("name") or device_id
        except:
            return device_id

    # ---------------------------------------------------------
    # ZENTRALE GRAPHEN, SMOOTHING & TREND-FABRIK 
    # ---------------------------------------------------------

    def get_graph_data(self, key):
        return self.graph_engine.get_buffer(key)

    def get_trend_icon(self, key):
    # Einfach an die Engine durchreichen
        return self.graph_engine.get_trend_icon(key)


    # ---------------------------------------------------------
    # UNIT ENGINE – Delegation
    # ---------------------------------------------------------
    
    def get_unit(self, key):
        return self.unit_engine.get_unit(key)
    
    def set_unit(self, key, unit):
        self.unit_engine.set_unit(key, unit)
    
    def toggle_temp_unit(self):
        self.unit_engine.toggle_temp_unit()
    
    def get_temp_unit(self):
        return self.unit_engine.get_temp_unit()

    def get_unit_for_metric(self, dev_id, metric):
        """Resolve the UI unit for a given device metric using full graph keys.

        Priority order is webserver, gatt, adv, matching FullScreenView behavior.
        Temperature metrics fallback to GLOBAL_STATE.get_temp_unit().
        """
        for channel in ("webserver", "gatt", "adv"):
            full_key = f"{dev_id}_{channel}_{metric}"
            unit = self.get_unit(full_key)
            if unit:
                return unit

        if metric.startswith("temp"):
            return self.get_temp_unit()

        return ""

    def global_start(self): self.graph_control.start()
    def global_stop(self): self.graph_control.stop()
    def global_reset(self): self.graph_control.reset()

    def bind_screen_manager(self, sm):
        self.screen_manager = sm


    # ---------------------------------------------------------
    # GLOBAL UPDATE TICK!!!
    # ---------------------------------------------------------
    # Der neue, saubere Tick:
    def _global_update(self, dt):
        self.data_flow.process_cycle()

    # ---------------------------------------------------------
    # Active Keys – MULTI-CHANNEL (adv + gatt, ohne Vorrang) MIXED MODE
    # ---------------------------------------------------------
    def extract_active_keys(self, d):
        return self.multi_key_engine.extract_active_keys(d)

    def refresh_all_headers(self):
        self.ui_handler.refresh_broadcast_buttons()


    # ---------------------------------------------------------
    # PUBLIC: Config Refresh
    # ---------------------------------------------------------
    def refresh_config(self):
        """Einfaches Interface für GSM, alles andere erledigt die Engine"""
        config.reload()  # 1. ZUERST das globale Modul für alle Threads frisch laden!
        print("[GSM] Config reloaded, now refreshing engines...")
        self.engine.refresh()  # 2. DANACH die UI-Strukturen mit den neuen Werten füttern
        print("[GSM] Config refresh complete.")
GLOBAL_STATE = GlobalStateManager()
