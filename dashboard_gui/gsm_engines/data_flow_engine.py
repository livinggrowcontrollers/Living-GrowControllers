# dashboard_gui/gsm_engines/data_flow_engine.py
import time
from dashboard_gui.data_buffer import BUFFER
from datetime import datetime

class DataFlowEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self.rssi_history = {}
        self._last_frame_time = time.time()
        self.current_latency = 0
        self.last_seen_timestamps = {}
        self._last_counter = None
        self._last_raw = None
        self._last_web_ts = None

    def process_cycle(self):
        now = time.time()
        self.current_latency = (now - self._last_frame_time) * 1000 
        self._last_frame_time = now
        
        BUFFER.soft_reload()
        data = BUFFER.get()
        
        if not self.gsm.running or not data:
            if not data: 
                self.gsm.led_engine.offline()
                self.rssi_history.clear()
                self.last_seen_timestamps.clear()
                
                if hasattr(self.gsm, 'ui_handler'):
                    self.gsm.ui_handler.update_active_screen(
                        self.gsm.screen_manager, 
                        {
                            "device_id": None, 
                            "channel": "",      
                            "alive": False
                        }
                    )
            return

        # --- PHASE 1: BACKGROUND UPDATES (Global) ---
# --- PHASE 1: BACKGROUND UPDATES (ALLE KANÄLE) ---

        for device_frame in data:
            dev_id = device_frame.get("device_id")
            if not dev_id:
                continue

            for ch_name in ("adv", "webserver", "gatt"):

                ch = device_frame.get(ch_name)

                if not isinstance(ch, dict):
                    continue

                if not ch.get("alive", False):
                    continue

                self.gsm.metrics_engine.process_metrics(
                    dev_id,
                    ch_name,
                    ch
                )

                self.gsm.metrics_engine.process_vpd_coords(
                    dev_id,
                    ch_name,
                    ch
                )               
        if hasattr(self.gsm, "mixed_engine"):
            self.gsm.mixed_engine.update(data)

        # --- PHASE 2: UI FOKUS ---
        ch_name = self.gsm.get_active_channel()
        active_dev_id = self.gsm.get_active_device_id()
        
        if not active_dev_id:
            return

        d = None
        for frame in data:
            if frame.get("device_id") == active_dev_id:
                d = frame
                break

        if d is None:
            return

        dev_id = d.get("device_id")
        ch = d.get(ch_name, {})
        if not isinstance(ch, dict):
            ch = {}
            
        # ❗ NEU: RSSI-Historie basierend auf Kanal-spezifischem RSSI
        self._update_focused_rssi(dev_id, d, ch_name, ch)

        d["channel"] = ch_name 
        d["latency"] = self.current_latency 

        if hasattr(self.gsm, 'ui_handler'):
            self.gsm.ui_handler.update_active_screen(self.gsm.screen_manager, d)
        
        self._handle_health_and_leds(d, ch, ch_name, dev_id)

    def _update_focused_rssi(self, dev_id, frame, ch_name, ch):
        """Trackt den RSSI Verlauf basierend auf dem aktuell ausgewählten UI-Kanal."""
        try:
            ts_value = frame.get("timestamp") or time.time()
            self.last_seen_timestamps[dev_id] = ts_value

            # NEU: Primär Kanal-spezifisches RSSI verwenden
            rssi = ch.get("rssi")
            
            # Fallback auf alten Health-Block (für Übergangsphase)
            # Fallback auf alten Health-Block (für Übergangsphase)
            if rssi is None:
                rssi = frame.get("health", {}).get("signal", {}).get("rssi")

            if rssi is not None:
                history = self.rssi_history.setdefault(dev_id, [])
                history.append(float(rssi))
                if len(history) > self.gsm.max_history:
                    history.pop(0)
        except Exception as e:
            print(f"[DFE] RSSI History Update Error: {e}")

    def _handle_health_and_leds(self, d, ch, ch_name, dev_id):
        if not ch.get("alive", False):
            self.gsm.led_engine.offline()
            return

        if ch_name == "webserver":
            current_web_ts = ch.get("timestamp")
            if current_web_ts and current_web_ts != self._last_web_ts:
                self.gsm.led_engine.flow()
                self._last_web_ts = current_web_ts
            else:
                self.gsm.led_engine.stale()

        elif ch_name == "adv":
            raw = ch.get("raw")
            if raw and raw != self._last_raw:
                self.gsm.led_engine.flow()
                self._last_raw = raw
            else:
                self.gsm.led_engine.stale()
            
        else: # GATT
            counter = ch.get("packet_counter")
            if counter is not None and counter != self._last_counter:
                self.gsm.led_engine.flow()
                self._last_counter = counter
            else:
                self.gsm.led_engine.stale()