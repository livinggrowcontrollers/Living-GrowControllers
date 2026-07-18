# dashboard_gui/config_engine.py
import config
from kivy.clock import Clock

class ConfigEngine:
    def __init__(self, gsm):
        self.gsm = gsm

    def refresh(self):
        """Zentrale Refresh-Methode – wird bei jeder Config-Änderung aufgerufen"""
        print("[ConfigEngine] Full refresh triggered")
        
        # 1. Settings / Graphen / Timing
        self.refresh_settings()
        
        # 2. Device-Liste & Active Index neu validieren
        self._refresh_device_state()
        
        # 3. UI komplett neu aufbauen wo nötig
        self._refresh_ui()

    def refresh_settings(self):
        """Nur die reinen Settings (kann auch separat aufgerufen werden)"""
        new_window = config.get_tile_graph_window()
        new_interval = config.get_refresh_interval()
        
        # 🔥 NEU: Optional den Smoothing-Faktor für das Log-Statement holen
        # (Wenn config.get_graph_smoothing_factor existiert)
        new_smoothing = getattr(config, 'get_graph_smoothing_factor', lambda: "N/A")()

        self.gsm.max_history = new_window
        
        # 🔥 MODIFIZIERT: Statt nur rebuild_buffers rufen wir jetzt refresh_config auf
        if hasattr(self.gsm, "graph_engine"):
            print("[ConfigEngine] Refreshing GraphEngine configs...")
            self.gsm.graph_engine.refresh_config()

        # RSSI History trimmen
        if hasattr(self.gsm, "data_flow") and hasattr(self.gsm.data_flow, "rssi_history"):
            df = self.gsm.data_flow
            for dev_id in list(df.rssi_history.keys()):
                buf = df.rssi_history[dev_id]
                if len(buf) > new_window:
                    df.rssi_history[dev_id] = buf[-new_window:]

        # Clock Intervall neu setzen
        if hasattr(self.gsm, "_main_tick"):
            self.gsm._main_tick.cancel()
            self.gsm._main_tick = Clock.schedule_interval(
                self.gsm._global_update, new_interval
            )

        print(f"[CONFIG] Settings synced: window={new_window}, interval={new_interval}s, smoothing={new_smoothing}")

    def _refresh_device_state(self):
        """Device-spezifischer Teil – wichtig für DevicePicker"""
        if not hasattr(self.gsm, 'active_channel_engine'):
            return
            
        ace = self.gsm.active_channel_engine
        
        # NEU: Vor dem Rebuild die alten angesammelten Tiles der TileEngine nullen!
        if hasattr(self.gsm, 'tile_engine'):
            self.gsm.tile_engine.reset_active_tiles()
        
        # Device-Liste neu aufbauen + Index validieren
        ace._rebuild_device_list()
        
        current_id = self.gsm.get_active_device_id()
        device_list = ace.get_device_list()
        
        # Der Buffer filtert anhand der aktuellen Config.  Ein erneutes Laden
        # entfernt gelöschte Geräte, ohne den Decoder-Fallback auf Platte zu
        # zerstören.
        try:
            from dashboard_gui.data_buffer import BUFFER
            BUFFER.soft_reload()
        except Exception as buf_err:
            print("[ConfigEngine] Could not reload BUFFER:", buf_err)
        
        if not device_list:
            ace.active_index = 0
            return
            
        if current_id not in device_list:
            ace.active_index = 0
            print(f"[ConfigEngine] Active device gone → reset to index 0")
        
        try:
            self.gsm.set_active_channel(self.gsm.get_active_channel())
        except Exception as e:
            print("[ConfigEngine] Channel re-trigger failed:", e)

    def _refresh_ui(self):
        """UI Teile neu laden"""
        if hasattr(self.gsm.ui_handler, 'reset_all_screens'):
            Clock.schedule_once(lambda *_: self.gsm.ui_handler.reset_all_screens(), 0.1)
        
        # Device Picker neu aufbauen falls offen
        if hasattr(self.gsm.ui_handler, 'get_screen'):
            dp_screen = self.gsm.ui_handler.get_screen("device_picker")
            if dp_screen and hasattr(dp_screen, '_build'):
                Clock.schedule_once(lambda *_: dp_screen._build(), 0.2)
