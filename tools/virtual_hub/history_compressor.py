# tools/virtual_hub/history_compressor.py

import csv
import os
import time
from typing import Dict, List, Any, Callable, Optional


def _safe_float(val) -> Optional[float]:
    if val is None or val == "":
        return None

    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compress_series(
    timestamps: List[float],
    values: List[float],
    target_points: int = 30,
    is_state_sensor: bool = False
) -> Dict[str, List[Any]]:
    n = len(values)
    if n <= target_points:
        return {"t": timestamps, "v": values}

    res_t: List[float] = []
    res_v: List[float] = []

    # Digital / State Sensors (light, exhaust, circulation)
    if is_state_sensor:
        res_t.append(timestamps[0])
        res_v.append(values[0])

        for i in range(1, n - 1):
            prev_val = values[i - 1]
            curr_val = values[i]
            next_val = values[i + 1]

            if curr_val != prev_val or curr_val != next_val:
                res_t.append(timestamps[i])
                res_v.append(curr_val)

        res_t.append(timestamps[-1])
        res_v.append(values[-1])
        return {"t": res_t, "v": res_v}

    # Continuous Sensor Logic (Bucket Min/Max/First/Last)
    num_buckets = max(1, target_points // 4)
    bucket_size = n / num_buckets

    for b in range(num_buckets):
        start_idx = int(b * bucket_size)
        end_idx = int((b + 1) * bucket_size) if b < num_buckets - 1 else n

        if start_idx >= end_idx:
            continue

        sub_t = timestamps[start_idx:end_idx]
        sub_v = values[start_idx:end_idx]

        idx_min = sub_v.index(min(sub_v))
        idx_max = sub_v.index(max(sub_v))
        idx_first = 0
        idx_last = len(sub_v) - 1

        selected_indices = sorted(list(set([idx_first, idx_min, idx_max, idx_last])))

        for idx in selected_indices:
            res_t.append(sub_t[idx])
            res_v.append(sub_v[idx])

    return {"t": res_t, "v": res_v}


def compress(
    csv_path: Optional[str] = None,
    target_points_per_series: int = 30,  # HARD CUT: Von 500 auf 30 reduziert
    max_age_hours: Optional[float] = 6.0,  # HARD CUT: Nur Daten der letzten X Stunden
    log_cb: Optional[Callable[[str], None]] = None
) -> Dict[str, Dict[str, Any]]:

    def log(msg: str):
        if log_cb:
            log_cb(f"[Compressor] {msg}")

    # 1. Automatische & sichere Pfadermittlung
    if not csv_path or not os.path.exists(csv_path):
        base_dir = os.path.dirname(os.path.abspath(__file__)) # .../tools/virtual_hub
        project_root = os.path.abspath(os.path.join(base_dir, "..", "..")) # Projektverzeichnis
        
        candidates = [
            os.path.join(project_root, "data", "log.csv"),
            os.path.abspath("data/log.csv"),
        ]
        
        for candidate in candidates:
            if os.path.exists(candidate):
                csv_path = candidate
                break

    log(f"Versuche Datei zu laden von: {csv_path}")

    if not csv_path or not os.path.exists(csv_path):
        log(f"FEHLER: Datei nicht gefunden unter '{csv_path}'!")
        return {"error": f"Datei nicht gefunden: {csv_path}"}

    raw_data: Dict[str, Dict[str, Any]] = {}
    state_sensors = {
        "light_pct",
        "exhaust_pct",
        "circulation_pct",
        "battery_voltage"
    }

    field_names = [
        "T_i",
        "H_i",
        "VPD_i",

        "T_e",
        "H_e",
        "VPD_e",

        "BLE_T_i",
        "BLE_H_i",
        "BLE_VPD_i",

        "BLE_T_e",
        "BLE_H_e",
        "BLE_VPD_e",

        "light_pct",
        "exhaust_fan_rpm",
        "circulation_fan_rpm",
        "battery_voltage",
        "rssi"
    ]
    # Zeitfilter berechnen
    current_time = time.time()
    max_age_seconds = (max_age_hours * 3600) if max_age_hours else None

    line_count = 0
    skipped_count = 0

    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = _safe_float(row.get("timestamp"))

                if ts is None or ts <= 0:
                    skipped_count += 1
                    continue

                # Temporal Cut: Zu alte Einträge überspringen
                if max_age_seconds and ts > 0 and (current_time - ts) > max_age_seconds:
                    skipped_count += 1
                    continue

                line_count += 1
                dev_id = row.get("device_id", "unknown").strip()
                dev_name = row.get("device_name", "Unknown Device").strip()

                if dev_id not in raw_data:
                    raw_data[dev_id] = {
                        "name": dev_name,
                        "metrics": {
                            field_name: {
                                "t": [],
                                "v": [],
                            }
                            for field_name in field_names
                        }
                    }

                for field_name in field_names:
                    value = _safe_float(row.get(field_name))

                    if value is None:
                        continue

                    raw_data[dev_id]["metrics"][field_name]["t"].append(ts)
                    raw_data[dev_id]["metrics"][field_name]["v"].append(value)

        log(f"PoC-Cut aktiv: {line_count} Zeilen (letzte {max_age_hours}h) eingelesen ({skipped_count} alte Zeilen verworfen). Geräte: {list(raw_data.keys())}")

    except Exception as e:
        log(f"FEHLER beim Lesen: {str(e)}")
        return {"error": str(e)}

    output: Dict[str, Any] = {}

    for dev_id, dev_content in raw_data.items():
        compressed_history: Dict[str, Any] = {}
        total_raw = 0

        for sensor_name, series in dev_content["metrics"].items():
            timestamps = series["t"]
            values = series["v"]

            total_raw = max(total_raw, len(values))

            is_state = sensor_name in state_sensors

            compressed_series = _compress_series(
                timestamps=timestamps,
                values=values,
                target_points=target_points_per_series,
                is_state_sensor=is_state,
            )

            compressed_history[sensor_name] = compressed_series

            log(
                f"  -> {sensor_name}: "
                f"{len(values)} Pts -> "
                f"{len(compressed_series['t'])} Pts"
            )

        output[dev_id] = {
            "device_id": dev_id,
            "name": dev_content["name"],
            "total_raw_points": total_raw,
            "history": compressed_history
        }

    log("Kompression erfolgreich abgeschlossen!")
    return output


create_history = compress