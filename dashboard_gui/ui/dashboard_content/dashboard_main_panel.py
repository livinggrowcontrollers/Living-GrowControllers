# dashboard_gui/ui/dashboard_content/dashboard_main_panel.py


import os
import math
import time
from kivy.uix.gridlayout import GridLayout
from dashboard_gui.ui.dashboard_content.chart_tile import ChartTile
from dashboard_gui.ui.scaling_utils import dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
from kivy.uix.scrollview import ScrollView

class DashboardMainPanel(GridLayout):
    def __init__(self, **kw):
        profile_started_at = time.perf_counter()
        super().__init__(**kw)
        self.cols = 3
        self.spacing = dp_scaled(2) # minimal vergrößert für mehr Cleanliness
        self.padding = dp_scaled(2)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        self._history_pipeline_key = None
        self._graph_range_revision = -1
        
        # Kacheln dynamisch aus der zentralen MetricRegistry erzeugen
        tile_ids = [
            "temp_in", "hum_in", "vpd_in",
            "temp_ex", "hum_ex", "vpd_ex",
            "ble_temp_outside", "ble_hum_outside", "ble_vpd_outside",
            "ble_temp_inside", "ble_hum_inside", "ble_vpd_inside",
            "leaf_temp", "vpd_leaf",
            "v_bat", "rssi" 
        ]

        self.tile_map = {}
        for key in tile_ids:
            tile_started_at = time.perf_counter()
            tile = ChartTile(key)
            self.tile_map[key] = tile
            setattr(self, f"tile_{key}", tile)
            print(f"[PERF][DASHBOARD][TILE] {key}: {time.perf_counter() - tile_started_at:.4f}s")

        print(f"[PERF][DASHBOARD][TILES] TOTAL: {time.perf_counter() - profile_started_at:.4f}s")

    def refresh_metric_theme(self):
        for tile in self.tile_map.values():
            tile.refresh_metric_theme()
        



    def update_from_data(self, d):  
        from dashboard_gui.data_buffer import BUFFER
        data = BUFFER.get()
        # 🔥 NEU: Wenn keine Geräte in der ActiveChannelEngine existieren, 
        # Dashboard komplett leeren und abbrechen!
        if hasattr(GLOBAL_STATE, "active_channel_engine"):
            lst = GLOBAL_STATE.active_channel_engine.get_device_list()
            if not lst:
                self.clear_widgets()
                return

        if not data: 
            self.clear_widgets()
            return
        
        active_idx = GLOBAL_STATE.get_active_index()
        active_channel = GLOBAL_STATE.get_active_channel()
        active_device_id = data[active_idx].get("device_id") if active_idx < len(data) else None
        history_window, range_revision = (
            GLOBAL_STATE.graph_history_engine.get_graph_range_state()
        )
        if range_revision != self._graph_range_revision:
            self._graph_range_revision = range_revision
            self._history_pipeline_key = None

        # Helper-Update Funktion (JETZT GANZ OBEN DEFINIERT)
        # So ist sie in der ganzen Methode verfügbar.
        def u(tile, val_dict, key, prefix, is_active):
            val = val_dict.get("value") if (val_dict and isinstance(val_dict, dict)) else None
            if val is not None:
                tile.update(val, f"{prefix}_{key}", render=is_active)

        # ---------------------------------------------------
        # 2. SICHTBARKEIT (NUR FÜR DAS AKTIVE GERÄT)
        # ---------------------------------------------------
        active_keys = []
        if active_idx < len(data):
            stream = data[active_idx].get(active_channel, {})
            internal = stream.get("internal", {})
            external = stream.get("external", {})
            ext2     = stream.get("external2", {})
            ble      = stream.get("ble_sensors", {})
            # Check Internal
            if internal.get("temperature", {}).get("value") is not None: active_keys.append("temp_in")
            if internal.get("humidity", {}).get("value") is not None:    active_keys.append("hum_in")
            if stream.get("vpd_internal", {}).get("value") is not None:  active_keys.append("vpd_in")
            
            # Check External 1
            if external.get("present"):
                if external.get("temperature", {}).get("value") is not None: active_keys.append("temp_ex")
                if external.get("humidity", {}).get("value") is not None:    active_keys.append("hum_ex")
                if stream.get("vpd_external", {}).get("value") is not None:  active_keys.append("vpd_ex")

            # Check External 2 (Leaf)
            if ext2.get("present"):
                if ext2.get("leaf_temp", {}).get("value") is not None:       active_keys.append("leaf_temp")
                if ext2.get("vpd_leaf", {}).get("value") is not None:        active_keys.append("vpd_leaf")

            # Check BLE Sensors
            outside_data = ble.get("outside", {})
            if outside_data.get("online"):
                if outside_data.get("temperature", {}).get("value") is not None: active_keys.append("ble_temp_outside")
                if outside_data.get("humidity", {}).get("value") is not None:    active_keys.append("ble_hum_outside")
                if outside_data.get("vpd", {}).get("value") is not None:         active_keys.append("ble_vpd_outside") # NEU


            inside_data = ble.get("inside", {})
            if inside_data.get("online"):
                if inside_data.get("temperature", {}).get("value") is not None: active_keys.append("ble_temp_inside")
                if inside_data.get("humidity", {}).get("value") is not None:    active_keys.append("ble_hum_inside")
                if inside_data.get("vpd", {}).get("value") is not None:         active_keys.append("ble_vpd_inside") # NEU
            # Check Fans & Battery

            # Check Fans & Battery
            if stream.get("battery_voltage") is not None:                               active_keys.append("v_bat")
            
            # RSSI nur einblenden, wenn vorhanden UND das Signal gültig ist
            if stream.get("rssi") is not None:
                active_keys.append("rssi")

            self._apply_tile_visibility(active_keys)

        if history_window is not None:
            self._update_history_tiles(
                device_id=active_device_id,
                active_channel=active_channel,
                active_keys=active_keys,
                history_window=history_window,
            )
            return

        # ---------------------------------------------------
        # 3. WERTE-UPDATE (BUFFER FÜR ALLE GERÄTE)
        # ---------------------------------------------------
        for frame in data:
            device_id = frame.get("device_id")
            stream = frame.get(active_channel)
            if not device_id or not stream or not stream.get("alive"): continue

            prefix = f"{device_id}_{active_channel}"
            is_active = (device_id == active_device_id)
            ble = stream.get("ble_sensors", {})

            # Internal
            u(self.tile_temp_in, stream.get("internal", {}).get("temperature"), "temp_in", prefix, is_active)
            u(self.tile_hum_in,  stream.get("internal", {}).get("humidity"), "hum_in", prefix, is_active)
            u(self.tile_vpd_in,  stream.get("vpd_internal"), "vpd_in", prefix, is_active)

            # External 1
            ext = stream.get("external", {})
            if ext.get("present"):
                u(self.tile_temp_ex, ext.get("temperature"), "temp_ex", prefix, is_active)
                u(self.tile_hum_ex,  ext.get("humidity"), "hum_ex", prefix, is_active)
                u(self.tile_vpd_ex,  stream.get("vpd_external"), "vpd_ex", prefix, is_active)

            # External 2
            ext2 = stream.get("external2", {})
            if ext2.get("present"):
                u(self.tile_leaf_temp, ext2.get("leaf_temp"), "leaf_temp", prefix, is_active)
                u(self.tile_vpd_leaf,  ext2.get("vpd_leaf"), "vpd_leaf", prefix, is_active)

            # BLE outside
            outside = ble.get("outside", {})
            u(self.tile_ble_temp_outside, outside.get("temperature"), "ble_temp_outside", prefix, is_active)
            u(self.tile_ble_hum_outside,  outside.get("humidity"), "ble_hum_outside", prefix, is_active)
            u(self.tile_ble_vpd_outside,  outside.get("vpd"), "ble_vpd_outside", prefix, is_active) # NEU
            
            # BLE inside
            inside = ble.get("inside", {})
            u(self.tile_ble_temp_inside, inside.get("temperature"), "ble_temp_inside", prefix, is_active)
            u(self.tile_ble_hum_inside,  inside.get("humidity"), "ble_hum_inside", prefix, is_active)
            u(self.tile_ble_vpd_inside,  inside.get("vpd"), "ble_vpd_inside", prefix, is_active) # NEU
            
            
            # Fans & Battery
            bat_v = stream.get("battery_voltage")
            if bat_v is not None:
                self.tile_v_bat.update(bat_v, f"{prefix}_v_bat", render=is_active)

            # RSSI Wert sauber filtern und updaten
            # REPARIERT: Das UI schreibt den Wert direkt, ohne den Marker zu kennen.
            rssi_val = stream.get("rssi")
            if rssi_val is not None:
                self.tile_rssi.update(rssi_val, f"{prefix}_rssi", render=is_active)

    def _update_history_tiles(
        self,
        device_id,
        active_channel,
        active_keys,
        history_window,
    ):
        if not device_id:
            self._render_history_status(
                active_keys,
                history_window.label,
                "Kein Gerät",
            )
            return

        pipeline_key = (
            GLOBAL_STATE.graph_history_engine.get_history_pipeline_key(
                str(device_id)
            )
        )
        expected_window = (
            float(history_window.start_timestamp),
            float(history_window.end_timestamp),
        )
        if (
            pipeline_key is None
            or pipeline_key[1:3] != expected_window
        ):
            self._render_history_status(
                active_keys,
                history_window.label,
                "Warte auf Pipeline …",
            )
            return

        self._history_pipeline_key = pipeline_key

        for tile_id in active_keys:
            tile = self.tile_map.get(tile_id)
            if tile is None:
                continue

            snapshot = GLOBAL_STATE.graph_history_engine.get_history_snapshot(
                pipeline_key=self._history_pipeline_key,
                tile_id=tile_id,
                label_count=len(tile.labels_list),
                range_label=history_window.label,
            )
            if snapshot is None:
                tile.render_history_status(
                    history_window.label,
                    "Keine History",
                )
                continue

            full_key = f"{device_id}_{active_channel}_{tile_id}"
            tile.render_history_snapshot(
                snapshot,
                GLOBAL_STATE.get_unit(full_key),
            )

    def _render_history_status(
        self,
        active_keys,
        range_label,
        message,
    ):
        for tile_id in active_keys:
            tile = self.tile_map.get(tile_id)
            if tile is not None:
                tile.render_history_status(range_label, message)

    def _apply_tile_visibility(self, active_keys):
        self.clear_widgets()
    
        from kivy.core.window import Window
    
        offset = dp_scaled(100)
        padding = dp_scaled(0   ) # Minimal, da die Tiles selbst schon gepaddet sind
        spacing = dp_scaled(0)
    
        available_height = max(0, Window.height - offset)
    
        num_tiles = len(active_keys)
    
        self.padding = [padding] * 4
        self.spacing = spacing
    
        self.cols = self._get_balanced_cols(num_tiles)
    
        # Maximal zwei sichtbare Reihen; weitere Tiles laufen über den ScrollView-Kontext.
        rows = min(2, max(1, math.ceil(num_tiles / self.cols))) if self.cols else 1
    
        usable_height = available_height - (padding * 2) - (spacing * (rows - 1))
        row_height = max(10, usable_height / rows)
    
        order = [
            "temp_in", "hum_in", "vpd_in",
            "temp_ex", "hum_ex", "vpd_ex",
            "ble_temp_outside", "ble_hum_outside", "ble_vpd_outside",
            "ble_temp_inside", "ble_hum_inside", "ble_vpd_inside",
            "leaf_temp", "vpd_leaf",

            "v_bat", "rssi",
        ]
    
        for key in order:
            if key not in active_keys:
                continue
    
            tile = self.tile_map.get(key)
            if not tile:
                continue
    
            tile.size_hint_y = None
            tile.height = row_height
    
            self.add_widget(tile)

    def _get_balanced_cols(self, num_tiles):
        """Maximal drei Spalten, aber vier Tiles werden sauber als 2x2 gelegt."""
        if num_tiles <= 0:
            return 1
        if num_tiles == 4:
            return 2
        return min(3, num_tiles)
