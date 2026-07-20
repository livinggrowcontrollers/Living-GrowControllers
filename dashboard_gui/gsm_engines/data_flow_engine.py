# dashboard_gui/gsm_engines/data_flow_engine.py
import time
from dashboard_gui.data_buffer import BUFFER
from decoders.channel_decoder import channel_signal

class DataFlowEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self.rssi_history = {}
        self._last_frame_time = time.time()
        self.current_latency = 0
        self.last_seen_timestamps = {}
        self._last_channel_signals = {}
        self._last_metric_signals = {}

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
                
                self.gsm.ui_handler.update_active_screen(
                    self.gsm.screen_manager,
                    {"device_id": None, "channel": "", "alive": False},
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

                if self._is_new_metric_frame(dev_id, ch_name, ch):
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

        # UI-only metadata must not leak back into the decoded RAM frame.
        ui_packet = dict(d)
        ui_packet["channel"] = ch_name
        ui_packet["latency"] = self.current_latency

        self.gsm.ui_handler.update_active_screen(self.gsm.screen_manager, ui_packet)
        
        self._handle_health_and_leds(d, ch, ch_name, dev_id)

    def _is_new_metric_frame(self, dev_id, ch_name, channel):
        """Allow each source packet into the graph pipeline exactly once."""
        if ch_name == "webserver":
            signal = channel.get("timestamp")
        else:
            signal = channel_signal(
                channel,
                "raw",
                is_gatt=ch_name == "gatt",
            )

        if signal is None:
            return False

        key = (dev_id, ch_name)
        if self._last_metric_signals.get(key) == signal:
            return False
        self._last_metric_signals[key] = signal
        return True

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
            self.gsm.led_engine.offline(ch_name)
            return

        signal_key = (dev_id, ch_name)
        if ch_name == "webserver":
            signal = ch.get("timestamp")
            if signal and signal != self._last_channel_signals.get(signal_key):
                self.gsm.led_engine.flow(ch_name)
                self._last_channel_signals[signal_key] = signal
            else:
                self.gsm.led_engine.stale(ch_name)

        elif ch_name == "adv":
            signal = ch.get("raw")
            if signal and signal != self._last_channel_signals.get(signal_key):
                self.gsm.led_engine.flow(ch_name)
                self._last_channel_signals[signal_key] = signal
            else:
                self.gsm.led_engine.stale(ch_name)
            
        else: # GATT
            # A raw payload is a legitimate fallback when a bridge does not
            # expose or temporarily loses packet_counter metadata.
            signal = ch.get("packet_counter")
            if signal is None:
                signal = ch.get("raw")
            if signal is not None and signal != self._last_channel_signals.get(signal_key):
                self.gsm.led_engine.flow(ch_name)
                self._last_channel_signals[signal_key] = signal
            else:
                self.gsm.led_engine.stale(ch_name)
