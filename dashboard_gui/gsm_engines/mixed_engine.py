# dashboard_gui/mixed_engine.py
import os
import json
from datetime import datetime
from kivy.clock import Clock
import config

class MixedEngine:

    def __init__(self, gsm):
        self.gsm = gsm
        self._config_loaded = False
        self.load_from_config()

    def update(self, all_data):
        if not self.gsm.mixed_selected_buffers:
            return
        
        if not hasattr(self, "_initialized"):
            self._initialized = True
            if not all_data:
                return

        selected = self.gsm.mixed_selected_buffers
    
        if not selected or not all_data:
            for key in ("temp", "hum", "vpd", "dew"):
                gk = f"mixed_avg_{key}"
                self.gsm.graph_engine.graph_buffers.pop(gk, None)
                self.gsm.graph_engine._trend_buffers.pop(gk, None)
                self.gsm.graph_engine._last_smoothed_values.pop(gk, None)
                self.gsm.graph_engine.global_trends.pop(gk, None)
    
            if hasattr(self, "_initialized") and self._initialized:
                self.write_json([])
            return
    
        averaging_map = {"temp": [], "hum": [], "vpd": [], "dew": []}
        unit_map = {"temp": None, "hum": None, "vpd": None, "dew": None}
        active_device_ids = []
    
        for frame in all_data:
            dev_id = str(frame.get("device_id"))
            if dev_id not in selected:
                continue
    
            active_modes = self.gsm.mixed_device_modes.get(dev_id, {"internal"})
    
            # Jetzt inklusive webserver für external Support
            for ch_name in ("adv", "gatt", "webserver"):
                ch = frame.get(ch_name)
                if not isinstance(ch, dict):
                    continue
                
                for mode in active_modes:
                    vals = ch.get(mode, {})
                    if not isinstance(vals, dict):
                        continue
            
                    # Temperatur
                    t = vals.get("temperature", {}).get("value")
                    if t is not None:
                        averaging_map["temp"].append(float(t))
                        if unit_map["temp"] is None:
                            unit_map["temp"] = vals.get("temperature", {}).get("unit")
            
                    # Luftfeuchte
                    h = vals.get("humidity", {}).get("value")
                    if h is not None:
                        averaging_map["hum"].append(float(h))
                        if unit_map["hum"] is None:
                            unit_map["hum"] = vals.get("humidity", {}).get("unit")
            
                    # VPD (wird meist pro Mode im Channel-Root berechnet)
                    v = ch.get(f"vpd_{mode}", {}).get("value")
                    if v is not None:
                        averaging_map["vpd"].append(float(v))
                        if unit_map["vpd"] is None:
                            unit_map["vpd"] = ch.get(f"vpd_{mode}", {}).get("unit")
            
                    # Taupunkt
                    d = ch.get(f"dew_point_{mode}", {}).get("value")
                    if d is not None:
                        averaging_map["dew"].append(float(d))
                        if unit_map["dew"] is None:
                            unit_map["dew"] = ch.get(f"dew_point_{mode}", {}).get("unit")
        
            if dev_id not in active_device_ids:
                active_device_ids.append(dev_id)

        results = {}
        has_real_data = False
    
        for key, vals in averaging_map.items():
            if not vals:
                results[key] = None
                continue
    
            avg = sum(vals) / len(vals)
            graph_key = f"mixed_avg_{key}"
    
            results[key] = avg
            self.gsm.graph_engine.process_new_value(graph_key, avg)
    
            unit = unit_map.get(key)
            if unit:
                self.gsm.set_unit(graph_key, unit)
    
            has_real_data = True
    
        if not has_real_data:
            self.write_json([])
            return
    
        self.write_json(results, active_device_ids)

    def write_json(self, results, device_ids=None):
        path = os.path.join(config.DATA, "mixed.json")

        if not results:
            try:
                with open(path, "w") as f:
                    json.dump([], f)
                self.gsm.broadcast_engine.set_available(False)
            except Exception as e:
                print(f"[MixedEngine] Write empty failed: {e}")
            return

        try:
            temp_avg = results.get("temp")
            
            # Interner Standard ist Celsius für JSON/Broadcast
            if temp_avg is not None and config.get_temperature_unit() == "F":
                temp_avg = (temp_avg - 32.0) * 5.0 / 9.0            

            json_data = [{
                "timestamp": datetime.now().isoformat(),
                "avg_temp": temp_avg,
                "avg_hum": results.get("hum"),
                "avg_vpd": results.get("vpd"),
                "avg_dew": results.get("dew"),
                "devices": device_ids or []
            }]

            with open(path, "w") as f:
                json.dump(json_data, f, indent=2)

            self.gsm.broadcast_engine.set_available(True)

            be = self.gsm.broadcast_engine
            if not be.active and not be.user_disabled:
                be.set_active(True)

        except Exception as e:
            print(f"[MixedEngine] write_json failed: {e}")

    def load_from_config(self):
        devices = config.get_devices()
        for dev in devices:
            if config.get_mixed_enabled(dev):
                self.gsm.mixed_selected_buffers.add(dev)
                # Setze Modus basierend auf Config (Internal/External)
                if config.get_mixed_external(dev):
                    self.gsm.mixed_device_modes[dev] = {"external"}
                else:
                    self.gsm.mixed_device_modes[dev] = {"internal"}
        
        self._config_loaded = True
        # "Idiotensicherer" Sync: UI & Realität vereinen
        Clock.schedule_once(self.init_broadcast_on_startup, 3.0)

    def init_broadcast_on_startup(self, dt):
        if self.check_file():
            self.gsm.broadcast_engine.set_available(True)
            be = self.gsm.broadcast_engine
            if not be.active and not be.user_disabled:
                be.set_active(True)

    def check_file(self):
        path = os.path.join(config.DATA, "mixed.json")
        if not os.path.exists(path): return False
        try:
            with open(path, "r") as f:
                return bool(json.load(f))
        except: return False

    def init_file(self):
        """
        Initialisiert die mixed.json Datei beim ersten Start der Engine.
        Wird vom GlobalStateManager in __init__ aufgerufen.
        """
        path = os.path.join(config.DATA, "mixed.json")
        try:
            # Ordner erstellen, falls er nicht existiert
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)
    
            self.gsm.broadcast_data_available = False
            print(f"[MixedEngine] mixed.json initialisiert: {path}")
    
        except Exception as e:
            print(f"[MixedEngine] mixed.json init failed: {e}")