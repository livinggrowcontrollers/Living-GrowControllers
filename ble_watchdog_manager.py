# ble_watchdog_manager.py

import os
import time
import json
import config
from decoders.channel_decoder import channel_signal

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RAW_PATH = os.path.join(DATA, "ble_dump.json")


class BleDumpWatchdog:
    CHANNELS = ["adv", "gatt"]

    def __init__(self, timeout, interval, callback):
        self.timeout = float(timeout)
        self.interval = float(interval)
        self.callback = callback
        self._moved = {}
        self._last_signal = {}
        self._last_ts = {}

        self.running = False

    def check_status(self):
        now = time.time()
        devices = config.get_devices()
        ble_dump = self._load() or []

        per_dev = {}
        any_ok = False
        last_seen_values = []

        for mac in devices:
            ble_entry = self._find(ble_dump, mac)

            dev_result = {}
            for channel in self.CHANNELS:
                ch = self._check_channel(mac, channel, ble_entry, now)
                dev_result[channel] = ch

                if ch["status"] == "OK":
                    any_ok = True
                if ch["last_seen"] is not None:
                    last_seen_values.append(ch["last_seen"])

            per_dev[mac] = dev_result

        return {
            "alive": any_ok,
            "status": "OK" if any_ok else "OFFLINE",
            "last_seen": min(last_seen_values) if last_seen_values else None,
            "devices": per_dev
        }

    def _load(self):
        if not os.path.exists(RAW_PATH):
            return None
        try:
            with open(RAW_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, list) else None
        except Exception:
            return None

    def _find(self, dump, mac):
        for e in dump:
            if isinstance(e, dict) and e.get("address") == mac:
                return e
        return None

    def _check_channel(self, mac, channel, entry, now):
        signal = channel_signal(entry, "gatt_raw" if channel == "gatt" else "adv_raw", is_gatt=channel == "gatt")

        if signal is None:
            return {"alive": False, "last_seen": None, "status": "OFFLINE"}

        if mac not in self._last_signal:
            self._last_signal[mac] = {}
            self._last_ts[mac] = {}
            self._moved[mac] = {}

        last_signal = self._last_signal[mac].get(channel)
        last_ts = self._last_ts[mac].get(channel)
        moved = self._moved[mac].get(channel, False)

        if last_signal is None:
            self._last_signal[mac][channel] = signal
            self._last_ts[mac][channel] = now
            self._moved[mac][channel] = False
            return {"alive": False, "last_seen": None, "status": "INIT"}

        if signal != last_signal:
            self._last_signal[mac][channel] = signal
            self._last_ts[mac][channel] = now
            self._moved[mac][channel] = True
            return {"alive": True, "last_seen": 0.0, "status": "OK"}

        if not moved:
            return {"alive": False, "last_seen": None, "status": "INIT"}

        delta = now - (last_ts or now)

        if delta < self.timeout:
            return {"alive": True, "last_seen": delta, "status": "OK"}

        return {"alive": False, "last_seen": delta, "status": "STALE"}

    def start(self):
        import threading

        if self.running:
            return
        self.running = True

        def loop():
            while self.running:
                try:
                    self.callback(self.check_status())
                except Exception:
                    pass
                time.sleep(self.interval)

        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self.running = False
