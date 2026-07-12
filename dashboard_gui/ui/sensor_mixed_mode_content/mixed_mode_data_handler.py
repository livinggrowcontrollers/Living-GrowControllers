# dashboard_gui/ui/sensor_mixed_mode_content/mixed_mode_data_handler.py

# -*- coding: utf-8 -*-
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.data_buffer import BUFFER

class MixedModeDataHandler:
    def __init__(self, screen):
        self.screen = screen
        self.GS = GLOBAL_STATE

    def refresh(self):
        """Komplettes UI-Refresh (Averages aktualisieren und Liste komplett neu aufbauen)."""
        self.update_averages()
        if self.screen.panel:
            self.screen.panel.rebuild_device_list()

    def update_live_data(self):
        """Nur die Werte aktualisieren (wichtig für den schnellen Timer/Live-Loop)."""
        self.update_averages()
        if self.screen.panel:
            self.screen.panel.update_device_values()

    def update_averages(self):
        """Holt die aktuellsten gemittelten Systemwerte aus der GraphEngine."""
        display_names = {"temp": "TEMP", "hum": "HUM", "vpd": "VPD", "dew": "DEW"}
        
        result = {}
        for key in ["temp", "hum", "vpd", "dew"]:
            full_key = f"mixed_avg_{key}"
            
            # Dank des Engine-Fixes liefert get_last_value hier ab Sekunde 1 
            # sofort valide Daten, anstatt auf das Skip-Intervall zu warten!
            result[key] = {
                "name": display_names[key],
                "val": self.GS.graph_engine.get_last_value(full_key),
                "unit": self.GS.get_unit(full_key) or "",
                "trend": self.GS.get_trend_icon(full_key) or ""
            }
        
        # Paket ans Panel übergeben
        if self.screen.panel:
            self.screen.panel.set_averages(result)

    def get_device_list_snapshot(self):
        """Erstellt eine Liste aller Geräte mit aktuellen Sensordetails für die UI."""
        device_list = self.GS.get_device_list()
        data = BUFFER.get() or []
        snapshot = []

        for dev_id in device_list:
            # Den passenden Datensatz (Frame) aus dem Rohdaten-Buffer suchen
            frame = next((f for f in data if str(f.get("device_id")) == str(dev_id)), None)
            
            snapshot.append({
                "device_id": dev_id,
                "label": self.GS.ui_handler.get_device_label(dev_id),
                "frame": frame,
                "selected": dev_id in self.GS.mixed_selected_buffers,
                "has_external": frame and self._has_external(frame),
                "modes": self.GS.mixed_device_modes.get(dev_id, {"internal"}),
                "values_str": self._get_values_string(frame, dev_id) if frame else "Keine Daten"
            })
        return snapshot

    def _get_values_string(self, frame, dev_id):
        """Berechnet T, H, V, D für die Inline-Anzeige in der Geräteliste."""
        active_modes = self.GS.mixed_device_modes.get(dev_id, {"internal"})
        
        # Listen für die Rohwerte zum Mitteln
        t_vals, h_vals, v_vals, d_vals = [], [], [], []
        
        # Daten-Extraktion über alle verfügbaren Empfangskanäle
        for ch_name in ("adv", "gatt", "webserver"):
            ch = frame.get(ch_name, {})
            for mode in active_modes:
                m_data = ch.get(mode, {})
            
                t = m_data.get("temperature", {}).get("value")
                h = m_data.get("humidity", {}).get("value")
                v = ch.get(f"vpd_{mode}", {}).get("value")
                d = ch.get(f"dew_{mode}", {}).get("value")
            
                if t is not None: t_vals.append(float(t))
                if h is not None: h_vals.append(float(h))
                if v is not None: v_vals.append(float(v))
                if d is not None: d_vals.append(float(d))
        
        if not any([t_vals, h_vals, v_vals, d_vals]):
            return "Warte auf Daten..."

        # Einheiten zentral abfragen
        u_t = self.GS.get_unit("mixed_avg_temp") or "°C"
        u_v = self.GS.get_unit("mixed_avg_vpd") or "kPa"

        parts = []
        if t_vals:
            parts.append(f"T: {sum(t_vals)/len(t_vals):.2f}{u_t}")
        if h_vals:
            parts.append(f"H: {sum(h_vals)/len(h_vals):.2f}%")
        if v_vals:
            parts.append(f"V: {sum(v_vals)/len(v_vals):.2f}{u_v}")
        if d_vals:
            parts.append(f"D: {sum(d_vals)/len(d_vals):.2f}{u_t}")

        return " | ".join(parts)
    
    def _has_external(self, frame):
        """Prüft, ob das Gerät Hardware für externe Sensoren besitzt."""
        if not frame: return False
        for ch_name in ("adv", "gatt", "webserver"):
            ch = frame.get(ch_name, {})
            if ch.get("external", {}).get("present"): 
                return True
        return False