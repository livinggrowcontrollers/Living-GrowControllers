# blebridge_desktop/blebridge_linux.py
import os
import sys
import time
import json
import asyncio
import threading
from datetime import datetime, timezone

from bleak import BleakScanner

# Pfade analog zu macOS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT_FILE = os.path.join(DATA_DIR, "ble_dump.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

WRITE_INTERVAL = 3.0
SCAN_IDLE_SLEEP = 0.2

def ts_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"

def get_target_channel():
    """Liest den aktuellen Empfangskanal aus der config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                return int(cfg.get("lgs_mesh_channel_recv", 17))
    except:
        pass
    return 17

class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.last = {}

    def update(self, ident, name, rssi, msd_dict):
        if not msd_dict:
            return

        # Bleak liefert { vendor_id_int: b'payload' }.
        # Wir bauen daraus den lückenlosen Hex-String (ID + Payload) wie in CoreBluetooth.
        adv_hex = ""

        for v_id, v_bytes in msd_dict.items():
            vendor_hex = bytes([
                v_id & 0xFF,
                (v_id >> 8) & 0xFF
            ]).hex().upper()

            adv_hex += vendor_hex + bytes(v_bytes).hex().upper()

        if not adv_hex:
            return

        # 1. Wenn es unser Vendor ist (7445)
        if adv_hex.startswith("7445"):
            target_ch = get_target_channel()
            lgs_pattern = f"7445A1{target_ch:02X}"
            
            if adv_hex.startswith(lgs_pattern):
                # Unser Kanal -> Identität auf virtuellen Node normalisieren
                effective_ident = "FF-FF-A1-00-00-01"
                effective_name = f"LGS_NODE_{target_ch}"
                with self.lock:
                    # Falls die echte Hardware-ID im Store gelandet ist, entfernen
                    if ident in self.last and ident != effective_ident:
                        del self.last[ident]
                    
                    dev = self.last.get(effective_ident, {"address": effective_ident, "gatt_raw": None})
                    dev.update({
                        "timestamp": ts_iso(), 
                        "name": effective_name, 
                        "rssi": int(rssi) if rssi is not None else 0,
                        "adv_raw": adv_hex, 
                        "log_raw": adv_hex, 
                        "note": f"ch_{target_ch}_active"
                    })
                    self.last[effective_ident] = dev
            else:
                # Falscher Kanal -> Aus dem Store werfen / ignorieren
                with self.lock:
                    if ident in self.last: 
                        del self.last[ident]
                return 
        else:
            # 2. Alle anderen Geräte -> Normal als "raw" speichern
            with self.lock:
                dev = self.last.get(ident, {"address": ident, "gatt_raw": None})
                dev.update({
                    "timestamp": ts_iso(), 
                    "name": name, 
                    "rssi": int(rssi) if rssi is not None else 0,
                    "adv_raw": adv_hex, 
                    "log_raw": adv_hex, 
                    "note": "raw"
                })
                self.last[ident] = dev

    def snapshot(self):
        with self.lock:
            return list(self.last.values())

class WriterThread(threading.Thread):
    def __init__(self, store):
        super().__init__(daemon=True)
        self.store = store
        self.run_flag = True
        os.makedirs(DATA_DIR, exist_ok=True)

    def run(self):
        while self.run_flag:
            try:
                tmp = OUT_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.store.snapshot(), f, ensure_ascii=False, indent=2)
                os.replace(tmp, OUT_FILE)
            except Exception as e:
                print("write err:", e, file=sys.stderr)
            time.sleep(WRITE_INTERVAL)

    def stop(self):
        self.run_flag = False

async def scan_loop(store):
    def detection_callback(device, advertisement_data):
        try:
            name = device.name or "(unknown)"
            rssi = advertisement_data.rssi
            msd = advertisement_data.manufacturer_data  # Reines Dict weitergeben
            ident = device.address
            store.update(ident, name, rssi, msd)
        except Exception as e:
            print("discover err:", e, file=sys.stderr)

    print(f"[SmoothBLE] Running… (Target Channel: {get_target_channel()})")
    scanner = BleakScanner(detection_callback=detection_callback)

    try:
        while True:
            await scanner.start()
            await asyncio.sleep(SCAN_IDLE_SLEEP)
            await scanner.stop()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    except Exception as e:
        print("scan err:", e, file=sys.stderr)

def main():
    print("[SmoothBLE] START")
    store = Store()
    writer = WriterThread(store)
    writer.start()

    try:
        asyncio.run(scan_loop(store))
    finally:
        writer.stop()
        print("[SmoothBLE] STOP")

if __name__ == "__main__":
    main()