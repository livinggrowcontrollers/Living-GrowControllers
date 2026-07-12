# dashboard_gui/gsm_engines/metrics_engine.py
class MetricsEngine:

    def __init__(self, gsm):
        self.gsm = gsm

    # ---------------------------------------------------------
    # PROCESS SENSOR METRICS
    # ---------------------------------------------------------
    def process_metrics(self, dev_id, ch_name, ch):
        active_metrics_this_run = []
        ble = ch.get("ble_sensors", {})
        outside = ble.get("outside", {})
        inside = ble.get("inside", {})
        
        # --- NEU: Kanal-spezifischer RSSI (direkt im Kanal) ---
        channel_rssi = ch.get("rssi")

        metrics_to_process = {
            "temp_in": ch.get("internal", {}).get("temperature"),
            "hum_in":  ch.get("internal", {}).get("humidity"),
            "vpd_in":  ch.get("vpd_internal"),
            "temp_ex": ch.get("external", {}).get("temperature"),
            "hum_ex":  ch.get("external", {}).get("humidity"),
            "vpd_ex":  ch.get("vpd_external"),
            "leaf_temp": ch.get("external2", {}).get("leaf_temp"),
            "vpd_leaf":  ch.get("external2", {}).get("vpd_leaf"),
            
            "circulation_fan_rpm": ch.get("circulation_fan", {}).get("circulation_fan_rpm"),
            "exhaust_fan_rpm": ch.get("exhaust_fan", {}).get("exhaust_fan_rpm"),

            # --- BLE SENSORS ---
            "ble_temp_outside": outside.get("temperature"),
            "ble_hum_outside":  outside.get("humidity"),
            "ble_vpd_outside":  outside.get("vpd"),
            
            "ble_temp_inside": inside.get("temperature"),
            "ble_hum_inside":  inside.get("humidity"),
            "ble_vpd_inside":  inside.get("vpd"),

            "v_bat": {"value": ch.get("battery_voltage"), "unit": "V"} if ch.get("battery_voltage") is not None else None,

    # --- KANALBEZOGENE METRIKEN (RSSI & QUALITÄT) ---
            # Streng isoliert: Nur wenn der Key direkt im Kanal-Wurzelverzeichnis existiert!
            "rssi": {"value": ch.get("rssi"), "unit": "dBm"} if ch.get("rssi") is not None else None,
            
            # Qualität NUR auswerten, wenn es ein echtes ch -> signal -> quality gibt, nicht global!
            "signal_quality": {"value": ch.get("signal", {}).get("quality"), "unit": "%"} 
                            if (isinstance(ch.get("signal"), dict) and ch.get("signal", {}).get("quality") is not None) else None
        
        }

        # --- 1. Daten-Verarbeitung ---
        for m_name, value_node in metrics_to_process.items():
            val = None
            unit = ""

            if isinstance(value_node, dict):
                if "value" in value_node:
                    val = value_node.get("value")
                else:
                    val = value_node.get(m_name)
                unit = value_node.get("unit", "")
                
            elif isinstance(value_node, (int, float)):
                val = value_node
                # Unit automatisch setzen
                if "fan_rpm" in m_name:
                    unit = "RPM"
                elif m_name.startswith("vpd"):
                    unit = "kPa"
                elif m_name.startswith("temp") or m_name == "leaf_temp":
                    unit = "°C"
                elif m_name.startswith("hum") or m_name == "signal_quality":
                    unit = "%"
                elif m_name == "rssi":
                    unit = "dBm"

            if val is not None:
                key = f"{dev_id}_{ch_name}_{m_name}"
                self.gsm.graph_engine.process_new_value(key, val)
                self.gsm.set_unit(key, unit)
                active_metrics_this_run.append(m_name)

        # --- 2. Tile-Registrierung pro Gerät/Kanal ---
        if hasattr(self.gsm, "tile_engine"):
            self.gsm.tile_engine.register_tiles(active_metrics_this_run, dev_id, ch_name)
                
                
    # ---------------------------------------------------------
    # PROCESS VPD COORDINATES (FIXED)
    # ---------------------------------------------------------
    def process_vpd_coords(self, dev_id, ch_name, ch):
        coord = ch.get("coord", {})
        coord_internal = coord.get("internal", {})
        coord_external = coord.get("external", {})
        
        all_coords = {
            "vpd_x_in": coord_internal.get("x"),
            "vpd_y_in": coord_internal.get("y"),
            "vpd_x_ex": coord_external.get("x"),
            "vpd_y_ex": coord_external.get("y"),
        }

        # BLE COORDS
        ble = ch.get("ble_sensors", {})
        outside = ble.get("outside", {})
        inside = ble.get("inside", {})
        
        all_coords.update({
            "vpd_x_outside": outside.get("coord", {}).get("x"),
            "vpd_y_outside": outside.get("coord", {}).get("y"),
            "vpd_x_inside": inside.get("coord", {}).get("x"),
            "vpd_y_inside": inside.get("coord", {}).get("y"),
        })

        for m_name, val in all_coords.items():
            if val is not None:
                key = f"{dev_id}_{ch_name}_{m_name}"
                self.gsm.graph_engine.process_new_value(key, val)
                self.gsm.set_unit(key, "")

    # ---------------------------------------------------------
    # NEU: Webserver-Support für Fullscreen & Graphs
    # ---------------------------------------------------------
    def process_webserver_metrics(self, dev_id, ch):
        print("WEBSERVER METRICS CALLED")
        print("RSSI =", ch.get("rssi"))
        self.process_metrics(dev_id, "webserver", ch)
        self.process_vpd_coords(dev_id, "webserver", ch)
