# blebridge_desktop/blebridge_desktop_smooth.py
import json, time, threading, os, sys
from datetime import datetime, timezone
from Foundation import NSObject, NSRunLoop, NSDate
import CoreBluetooth as CB

# Pfade
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT_FILE = os.path.join(DATA_DIR, "ble_dump.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

WRITE_INTERVAL = 3.0
SCAN_IDLE_SLEEP = 0.20

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

    def update(self, ident, name, rssi, msd):
        if not msd: return
        adv_hex = msd.hex().upper()
        
        # 1. Wenn es unser Vendor ist
        if adv_hex.startswith("7445"):
            target_ch = get_target_channel()
            lgs_pattern = f"7445A1{target_ch:02X}"
            
            if adv_hex.startswith(lgs_pattern):
                # Unser Kanal -> Normalisieren
                effective_ident = "FF-FF-A1-00-00-01"
                effective_name = f"LGS_NODE_{target_ch}"
                with self.lock:
                    if ident in self.last and ident != effective_ident:
                        del self.last[ident]
                    dev = self.last.get(effective_ident, {"address": effective_ident, "gatt_raw": None})
                    dev.update({
                        "timestamp": ts_iso(), "name": effective_name, "rssi": int(rssi),
                        "adv_raw": adv_hex, "log_raw": adv_hex, "note": f"ch_{target_ch}_active"
                    })
                    self.last[effective_ident] = dev
            else:
                # Falscher Kanal -> Wegwerfen
                with self.lock:
                    if ident in self.last: del self.last[ident]
                return 
        else:
            # 2. Alle anderen Geräte -> Normal speichern
            with self.lock:
                dev = self.last.get(ident, {"address": ident, "gatt_raw": None})
                dev.update({
                    "timestamp": ts_iso(), "name": name, "rssi": int(rssi),
                    "adv_raw": adv_hex, "log_raw": adv_hex, "note": "raw"
                })
                self.last[ident] = dev

    def snapshot(self):
        with self.lock:
            return list(self.last.values())

class CentralDelegate(NSObject):
    def initWithStore_(self, store):
        self = self.init()
        if self is None: return None
        self.store = store
        return self

    def centralManagerDidUpdateState_(self, manager):
        if manager.state() == CB.CBManagerStatePoweredOn:
            # allow_duplicates=True ist wichtig, um Live-Updates der Sensordaten zu kriegen
            manager.scanForPeripheralsWithServices_options_(
                None, {"kCBScanOptionAllowDuplicatesKey": True}
            )
        else:
            print(f"Bluetooth Status: {manager.state()}")

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, m, p, adv, rssi):
        try:
            name = adv.get(CB.CBAdvertisementDataLocalNameKey) or p.name() or "(unknown)"
            msd = adv.get(CB.CBAdvertisementDataManufacturerDataKey)
            ident = str(p.identifier())
            self.store.update(ident, name, rssi, bytes(msd) if msd else None)
        except Exception as e:
            pass

class WriterThread(threading.Thread):
    def __init__(self, store):
        super().__init__(daemon=True)
        self.store = store
        self.run_flag = True

    def run(self):
        while self.run_flag:
            try:
                data = self.store.snapshot()
                tmp = OUT_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, OUT_FILE)
            except Exception as e:
                print(f"Write Error: {e}")
            time.sleep(WRITE_INTERVAL)

    def stop(self):
        self.run_flag = False

def main():
    print(f"[LGS-Scanner] START (Target Channel: {get_target_channel()})")
    store = Store()
    writer = WriterThread(store)
    writer.start()

    delegate = CentralDelegate.alloc().initWithStore_(store)
    central = CB.CBCentralManager.alloc().initWithDelegate_queue_options_(
        delegate, None, None
    )

    rl = NSRunLoop.currentRunLoop()
    try:
        while True:
            rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            time.sleep(SCAN_IDLE_SLEEP)
    except KeyboardInterrupt:
        pass
    finally:
        writer.stop()
        print("[LGS-Scanner] STOP")

if __name__ == "__main__":
    main()