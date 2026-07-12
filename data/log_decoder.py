# data/log_decoder.py
# Standalone BLE Log Decoder (Desktop)
# © 2026 Dominik Rosenthal

import json
import os
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "ble_log_dump.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "log_decoded.json")


def load_log(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    entries = []
    current = {}

    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            if line.startswith("{"):
                current = {}
                continue
            if line.startswith("}"):
                if current:
                    entries.append(current)
                current = {}
                continue
            if ":" in line:
                try:
                    key, value = line.split(":", 1)
                    key = key.strip().strip('"')
                    value = value.strip().rstrip(",")
                    if value == "null":
                        value = None
                    elif value.startswith('"') and value.endswith('"'):
                        value = value.strip('"')
                    else:
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    current[key] = value
                except Exception as e:
                    print(f"⚠️ parse error line {lineno}: {e}")
    return entries


def group_by_device(log_entries):
    devices = defaultdict(list)
    for entry in log_entries:
        addr = entry.get("address", "UNKNOWN")
        devices[addr].append(entry)
    return devices


def decode_entry(entry):
    """
    History-Log Decoder – nur Timestamp und einfache Werte.
    Kein ADV/GATT, keine Flags.
    """
    decoded = dict(entry)
    raw = entry.get("gatt_raw")
    decoded["raw_len"] = len(raw) // 2 if raw else 0

    ts = entry.get("timestamp")
    if isinstance(ts, (int, float)):
        try:
            decoded["timestamp_iso"] = datetime.fromtimestamp(ts).isoformat()
        except Exception:
            decoded["timestamp_iso"] = None
    elif isinstance(ts, str):
        decoded["timestamp_iso"] = ts
    else:
        decoded["timestamp_iso"] = None

    decoded["temperature_c"] = entry.get("temperature_c", None)
    decoded["humidity_pct"] = entry.get("humidity_pct", None)
    decoded["status"] = entry.get("status", None)
    return decoded


def decode_devices(grouped):
    """
    Entfernt doppelte gatt_raw Einträge pro Gerät, behält aber eins.
    """
    result = {}

    for addr, entries in grouped.items():
        seen_raws = set()
        unique_entries = []
        for e in entries:
            raw = e.get("gatt_raw")
            if raw not in seen_raws:
                seen_raws.add(raw)
                unique_entries.append(decode_entry(e))
        result[addr] = {
            "count": len(unique_entries),
            "entries": unique_entries
        }

    return result


def main():
    print("📥 loading:", INPUT_FILE)
    log = load_log(INPUT_FILE)

    print("🔀 grouping by device")
    grouped = group_by_device(log)

    print("🧠 decoding")
    decoded = decode_devices(grouped)

    print("💾 writing:", OUTPUT_FILE)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(decoded, f, indent=2)

    print("✅ done")
    print("   devices:", len(decoded))


if __name__ == "__main__":
    main()
