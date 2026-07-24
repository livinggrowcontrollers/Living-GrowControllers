import csv
import math
import os
from typing import Any, Callable, Dict, List, Optional, Sequence


FIELD_NAMES = (
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
    "rssi",
)

# Diese Reihen werden als Zustände behandelt. Auch sie halten das Punktbudget ein.
STATE_SENSORS = {
    "light_pct",
}


def _history_device_identity(device_id: str) -> str:
    """Use the logged device_id as the sole device identity."""
    return str(device_id or "").strip() or "unknown"


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _validate_window(
    start_timestamp: Any,
    end_timestamp: Any,
    target_points: Any,
) -> tuple[float, float, int]:
    start = _safe_float(start_timestamp)
    end = _safe_float(end_timestamp)

    if start is None or end is None:
        raise ValueError("start_timestamp und end_timestamp müssen gültige Zahlen sein.")
    if start >= end:
        raise ValueError("start_timestamp muss kleiner als end_timestamp sein.")

    if isinstance(target_points, bool):
        raise ValueError("target_points muss eine positive Ganzzahl sein.")

    try:
        numeric_points = float(target_points)
        points = int(numeric_points)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("target_points muss eine positive Ganzzahl sein.") from exc

    if not math.isfinite(numeric_points) or numeric_points != points:
        raise ValueError("target_points muss eine positive Ganzzahl sein.")
    if points < 1:
        raise ValueError("target_points muss mindestens 1 sein.")

    return start, end, points


def _resolve_csv_file(csv_file: Optional[str]) -> Optional[str]:
    if csv_file and os.path.isfile(csv_file):
        return csv_file

    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    candidates = (
        os.path.join(project_root, "data", "log.csv"),
        os.path.abspath(os.path.join("data", "log.csv")),
    )

    return next((path for path in candidates if os.path.isfile(path)), None)


def _evenly_spaced_indices(indices: Sequence[int], count: int) -> List[int]:
    if count >= len(indices):
        return list(indices)
    if count <= 1:
        return [indices[-1]]

    last_position = len(indices) - 1
    selected = {
        indices[round(position * last_position / (count - 1))]
        for position in range(count)
    }

    # round() kann bei kleinen Listen denselben Index zweimal treffen.
    if len(selected) < count:
        for index in indices:
            selected.add(index)
            if len(selected) == count:
                break

    return sorted(selected)


def _compress_state_series(
    timestamps: Sequence[float],
    values: Sequence[float],
    target_points: int,
) -> Dict[str, List[Any]]:
    if len(values) <= target_points:
        return {"t": list(timestamps), "v": list(values)}

    transition_indices = {0, len(values) - 1}
    for index in range(1, len(values)):
        if values[index] != values[index - 1]:
            # Beide Seiten einer Zustandskante erhalten, soweit das Budget reicht.
            transition_indices.add(index - 1)
            transition_indices.add(index)

    candidates = sorted(transition_indices)
    selected = _evenly_spaced_indices(candidates, target_points)

    return {
        "t": [timestamps[index] for index in selected],
        "v": [values[index] for index in selected],
    }


def _largest_triangle_three_buckets(
    timestamps: Sequence[float],
    values: Sequence[float],
    target_points: int,
) -> Dict[str, List[Any]]:
    """Komprimiert eine kontinuierliche Reihe mit festem Punktbudget."""
    length = len(values)

    if length <= target_points:
        return {"t": list(timestamps), "v": list(values)}
    if target_points == 1:
        return {"t": [timestamps[-1]], "v": [values[-1]]}
    if target_points == 2:
        return {
            "t": [timestamps[0], timestamps[-1]],
            "v": [values[0], values[-1]],
        }

    bucket_width = (length - 2) / (target_points - 2)
    selected_indices = [0]
    anchor_index = 0

    for bucket in range(target_points - 2):
        average_start = int(math.floor((bucket + 1) * bucket_width)) + 1
        average_end = int(math.floor((bucket + 2) * bucket_width)) + 1
        average_end = min(average_end, length)

        if average_start >= average_end:
            average_x = timestamps[-1]
            average_y = values[-1]
        else:
            average_count = average_end - average_start
            average_x = (
                sum(timestamps[average_start:average_end]) / average_count
            )
            average_y = sum(values[average_start:average_end]) / average_count

        range_start = int(math.floor(bucket * bucket_width)) + 1
        range_end = int(math.floor((bucket + 1) * bucket_width)) + 1
        range_end = min(range_end, length - 1)

        anchor_x = timestamps[anchor_index]
        anchor_y = values[anchor_index]
        max_area = -1.0
        next_anchor = range_start

        for index in range(range_start, max(range_start + 1, range_end)):
            area = abs(
                (anchor_x - average_x) * (values[index] - anchor_y)
                - (anchor_x - timestamps[index]) * (average_y - anchor_y)
            )
            if area > max_area:
                max_area = area
                next_anchor = index

        selected_indices.append(next_anchor)
        anchor_index = next_anchor

    selected_indices.append(length - 1)

    return {
        "t": [timestamps[index] for index in selected_indices],
        "v": [values[index] for index in selected_indices],
    }


def _compress_series(
    timestamps: Sequence[float],
    values: Sequence[float],
    target_points: int,
    is_state_sensor: bool = False,
) -> Dict[str, List[Any]]:
    if is_state_sensor:
        return _compress_state_series(timestamps, values, target_points)

    return _largest_triangle_three_buckets(
        timestamps,
        values,
        target_points,
    )


def _bucket_index(
    timestamp: float,
    start_timestamp: float,
    end_timestamp: float,
    target_points: int,
) -> int:
    window_position = (
        (timestamp - start_timestamp)
        / (end_timestamp - start_timestamp)
    )
    return min(
        target_points - 1,
        max(0, int(window_position * target_points)),
    )


def _add_to_metric_bucket(
    metric: Dict[str, Any],
    bucket_index: int,
    timestamp: float,
    value: float,
    target_points: int,
) -> None:
    metric["count"] += 1
    point = (timestamp, value)

    samples = metric["samples"]
    samples.append(point)
    if len(samples) > (target_points * 2):
        sample_indices = _evenly_spaced_indices(
            list(range(len(samples))),
            target_points,
        )
        metric["samples"] = [
            samples[index]
            for index in sample_indices
        ]

    bucket = metric["buckets"].get(bucket_index)
    if bucket is None:
        metric["buckets"][bucket_index] = {
            "first": point,
            "minimum": point,
            "maximum": point,
            "last": point,
        }
        return

    if timestamp < bucket["first"][0]:
        bucket["first"] = point
    if timestamp >= bucket["last"][0]:
        bucket["last"] = point
    if value < bucket["minimum"][1]:
        bucket["minimum"] = point
    if value > bucket["maximum"][1]:
        bucket["maximum"] = point


def _metric_candidates(metric: Dict[str, Any]) -> tuple[List[float], List[float]]:
    candidates = list(metric["samples"])

    for bucket_index in sorted(metric["buckets"]):
        bucket = metric["buckets"][bucket_index]
        candidates.extend(
            (
                bucket["first"],
                bucket["minimum"],
                bucket["maximum"],
                bucket["last"],
            )
        )

    # Samples und First/Min/Max/Last können auf denselben Rohpunkt zeigen.
    unique_candidates = sorted(set(candidates), key=lambda point: point[0])
    return (
        [point[0] for point in unique_candidates],
        [point[1] for point in unique_candidates],
    )


def compress(
    csv_file: Optional[str],
    start_timestamp: float,
    end_timestamp: float,
    target_points: int,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Liest genau ein Zeitfenster aus der CSV und komprimiert jede Messreihe.

    Die Rückgabeform bleibt die bestehende Geräte-/History-Struktur. Für jede
    Reihe werden während des CSV-Scans nur zeitbasierte First/Min/Max/Last-
    Kandidaten und eine begrenzte Stichprobe gehalten. Ausgeliefert werden
    höchstens ``target_points`` Werte.
    """
    start, end, points = _validate_window(
        start_timestamp,
        end_timestamp,
        target_points,
    )

    def log(message: str) -> None:
        if log_cb:
            log_cb(f"[Compressor] {message}")

    resolved_csv_file = _resolve_csv_file(csv_file)
    log(f"Lade Zeitfenster {start:.3f} bis {end:.3f}.")

    if not resolved_csv_file:
        requested_path = csv_file or "data/log.csv"
        message = f"Datei nicht gefunden: {requested_path}"
        log(f"FEHLER: {message}")
        return {"error": message}

    raw_data: Dict[str, Dict[str, Any]] = {}
    selected_rows = 0
    skipped_rows = 0

    try:
        with open(
            resolved_csv_file,
            mode="r",
            encoding="utf-8",
            newline="",
        ) as source:
            reader = csv.DictReader(source)

            for row in reader:
                timestamp = _safe_float(row.get("timestamp"))
                if timestamp is None or timestamp < start or timestamp > end:
                    skipped_rows += 1
                    continue

                selected_rows += 1
                csv_device_id = str(
                    row.get("device_id") or "unknown"
                ).strip()
                device_name = str(
                    row.get("device_name") or "Unknown Device"
                ).strip()
                device_id = _history_device_identity(csv_device_id)

                device = raw_data.setdefault(
                    device_id,
                    {
                        "name": device_name,
                        "metrics": {
                            field_name: {
                                "count": 0,
                                "buckets": {},
                                "samples": [],
                            }
                            for field_name in FIELD_NAMES
                        },
                    },
                )

                bucket_index = _bucket_index(
                    timestamp,
                    start,
                    end,
                    points,
                )

                for field_name in FIELD_NAMES:
                    value = _safe_float(row.get(field_name))
                    if value is None:
                        continue

                    _add_to_metric_bucket(
                        device["metrics"][field_name],
                        bucket_index,
                        timestamp,
                        value,
                        points,
                    )

    except (OSError, csv.Error) as exc:
        message = str(exc)
        log(f"FEHLER beim Lesen: {message}")
        return {"error": message}

    log(
        f"{selected_rows} Zeilen im Zeitfenster ausgewählt; "
        f"{skipped_rows} Zeilen verworfen."
    )

    output: Dict[str, Dict[str, Any]] = {}

    for device_id, device_content in raw_data.items():
        compressed_history: Dict[str, Any] = {}
        total_raw_points = 0

        for sensor_name, metric in device_content["metrics"].items():
            timestamps, values = _metric_candidates(metric)
            total_raw_points = max(total_raw_points, metric["count"])

            compressed_series = _compress_series(
                timestamps=timestamps,
                values=values,
                target_points=points,
                is_state_sensor=sensor_name in STATE_SENSORS,
            )
            compressed_history[sensor_name] = compressed_series

            log(
                f"{device_id}/{sensor_name}: {metric['count']} -> "
                f"{len(compressed_series['t'])} Punkte"
            )

        output[device_id] = {
            "device_id": device_id,
            "name": device_content["name"],
            "total_raw_points": total_raw_points,
            "history": compressed_history,
        }

    log("Kompression erfolgreich abgeschlossen.")
    return output
