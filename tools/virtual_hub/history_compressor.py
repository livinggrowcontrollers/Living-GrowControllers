from collections import OrderedDict
import csv
from dataclasses import dataclass
import io
import math
import os
import threading
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

INDEX_BLOCK_ROWS = 256
MAX_CACHED_INDEXES = 8
INDEX_SIGNATURE_BYTES = 128


def _history_device_identity(device_id: str) -> str:
    """Use the logged device_id as the sole device identity."""
    return str(device_id or "").strip() or "unknown"


@dataclass
class _CsvBlock:
    start_offset: int
    end_offset: int
    row_count: int = 0
    min_timestamp: Optional[float] = None
    max_timestamp: Optional[float] = None


class _HistoryCsvIndex:
    """Inkrementeller Blockindex für eine wachsende History-CSV."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._file_identity: Optional[tuple[int, int]] = None
        self._mtime_ns = 0
        self._indexed_offset = 0
        self._field_names: tuple[str, ...] = ()
        self._timestamp_column = -1
        self._tail_signature = b""
        self._ended_with_newline = True
        self._blocks: List[_CsvBlock] = []

    def _must_rebuild(self, source, file_stat: os.stat_result) -> bool:
        identity = (file_stat.st_dev, file_stat.st_ino)
        if identity != self._file_identity:
            return True
        if file_stat.st_size < self._indexed_offset:
            return True
        if file_stat.st_size > self._indexed_offset and not self._ended_with_newline:
            return True
        if (
            file_stat.st_size == self._indexed_offset
            and file_stat.st_mtime_ns != self._mtime_ns
        ):
            return True
        if file_stat.st_mtime_ns != self._mtime_ns and self._tail_signature:
            signature_start = self._indexed_offset - len(self._tail_signature)
            source.seek(signature_start)
            if source.read(len(self._tail_signature)) != self._tail_signature:
                return True
        return False

    def _reset(self, source, file_stat: os.stat_result) -> None:
        source.seek(0)
        header = source.readline()
        try:
            decoded_header = header.decode("utf-8-sig").rstrip("\r\n")
            self._field_names = tuple(next(csv.reader([decoded_header])))
            self._timestamp_column = self._field_names.index("timestamp")
        except (StopIteration, UnicodeError, csv.Error, ValueError):
            self._field_names = ()
            self._timestamp_column = -1

        self._file_identity = (file_stat.st_dev, file_stat.st_ino)
        self._indexed_offset = source.tell()
        self._tail_signature = b""
        self._ended_with_newline = header.endswith(b"\n")
        self._blocks = []

    def refresh(self) -> None:
        with self._lock:
            with open(self.path, "rb") as source:
                file_stat = os.fstat(source.fileno())
                if self._must_rebuild(source, file_stat):
                    self._reset(source, file_stat)
                else:
                    source.seek(self._indexed_offset)

                snapshot_size = file_stat.st_size
                while source.tell() < snapshot_size:
                    line_start = source.tell()
                    line = source.readline(snapshot_size - line_start)
                    if not line:
                        break

                    while line.count(b'"') % 2 and source.tell() < snapshot_size:
                        continuation_start = source.tell()
                        continuation = source.readline(
                            snapshot_size - continuation_start
                        )
                        if not continuation:
                            break
                        line += continuation

                    line_end = source.tell()
                    if line.count(b'"') % 2:
                        source.seek(line_start)
                        break

                    if self._timestamp_column == 0:
                        timestamp = _safe_float(line.partition(b",")[0])
                    else:
                        try:
                            cells = next(csv.reader([line.decode("utf-8")]))
                            timestamp = _safe_float(cells[self._timestamp_column])
                        except (
                            IndexError,
                            StopIteration,
                            UnicodeError,
                            csv.Error,
                        ):
                            timestamp = None

                    if (
                        not self._blocks
                        or self._blocks[-1].row_count >= INDEX_BLOCK_ROWS
                    ):
                        self._blocks.append(
                            _CsvBlock(
                                start_offset=line_start,
                                end_offset=line_end,
                            )
                        )

                    block = self._blocks[-1]
                    block.end_offset = line_end
                    block.row_count += 1
                    if timestamp is not None:
                        if block.min_timestamp is None or timestamp < block.min_timestamp:
                            block.min_timestamp = timestamp
                        if block.max_timestamp is None or timestamp > block.max_timestamp:
                            block.max_timestamp = timestamp

                    self._indexed_offset = line_end

                signature_length = min(
                    INDEX_SIGNATURE_BYTES,
                    self._indexed_offset,
                )
                source.seek(self._indexed_offset - signature_length)
                self._tail_signature = source.read(signature_length)
                self._ended_with_newline = (
                    not self._tail_signature
                    or self._tail_signature.endswith(b"\n")
                )
                self._mtime_ns = file_stat.st_mtime_ns

    def scan_plan(
        self,
        start_timestamp: float,
        end_timestamp: float,
    ) -> tuple[tuple[str, ...], int, List[tuple[int, int]]]:
        self.refresh()
        with self._lock:
            field_names = self._field_names
            total_rows = sum(block.row_count for block in self._blocks)
            matching_blocks = [
                (block.start_offset, block.end_offset)
                for block in self._blocks
                if (
                    block.min_timestamp is None
                    or block.max_timestamp is None
                    or (
                        block.max_timestamp >= start_timestamp
                        and block.min_timestamp <= end_timestamp
                    )
                )
            ]
        return field_names, total_rows, matching_blocks


_INDEXES: "OrderedDict[str, _HistoryCsvIndex]" = OrderedDict()
_INDEXES_LOCK = threading.Lock()


def _get_history_index(path: str) -> _HistoryCsvIndex:
    canonical_path = os.path.realpath(path)
    with _INDEXES_LOCK:
        index = _INDEXES.get(canonical_path)
        if index is None:
            index = _HistoryCsvIndex(canonical_path)
            _INDEXES[canonical_path] = index
        else:
            _INDEXES.move_to_end(canonical_path)
        while len(_INDEXES) > MAX_CACHED_INDEXES:
            _INDEXES.popitem(last=False)
        return index


def _iter_indexed_rows(
    path: str,
    field_names: Sequence[str],
    byte_ranges: Sequence[tuple[int, int]],
):
    if not field_names:
        return

    with open(path, "rb") as source:
        for start_offset, end_offset in byte_ranges:
            source.seek(start_offset)
            raw_rows = source.read(end_offset - start_offset)
            decoded_rows = raw_rows.decode("utf-8")
            yield from csv.DictReader(
                io.StringIO(decoded_rows),
                fieldnames=field_names,
            )


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
    total_rows = 0

    try:
        history_index = _get_history_index(resolved_csv_file)
        field_names, total_rows, byte_ranges = history_index.scan_plan(
            start,
            end,
        )

        for row in _iter_indexed_rows(
            resolved_csv_file,
            field_names,
            byte_ranges,
        ):
            timestamp = _safe_float(row.get("timestamp"))
            if timestamp is None or timestamp < start or timestamp > end:
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
        f"{total_rows} Zeilen indexiert."
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
