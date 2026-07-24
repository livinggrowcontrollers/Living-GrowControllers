import math
import threading
import time
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional, Tuple

import config

from dashboard_gui.ui.common.graph_chart_content.chart_time_axis import (
    compute_time_axis_labels,
)


@dataclass(frozen=True)
class GraphStats:
    average: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class GraphPoint:
    graph_x: float
    value: float
    timestamp: Optional[float]
    index: int
    total: int
    role: str = ""
    label: str = ""

    @property
    def coordinates(self):
        return (self.graph_x, self.value)


@dataclass(frozen=True)
class GraphSnapshot:
    mode: str
    points: Tuple[Tuple[float, float], ...]
    timestamps: Tuple[float, ...]
    values: Tuple[float, ...]
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    labels: Tuple[str, ...]
    last_value: float
    stats: Optional[GraphStats]
    trend_icon: str = ""
    range_label: str = ""
    notable_points: Tuple[GraphPoint, ...] = ()


@dataclass(frozen=True)
class HistoryWindow:
    start_timestamp: float
    end_timestamp: float
    label: str
    range_key: object = None


@dataclass(frozen=True)
class HistorySelectionResult:
    key: tuple
    status: str
    error: Optional[str] = None
    selection_id: Optional[str] = None
    target_revision: Optional[int] = None



class GraphEngine:
    HISTORY_TARGET_POINTS = 30
    HISTORY_KEY_MAP = {
        "temp_in": "T_i",
        "hum_in": "H_i",
        "vpd_in": "VPD_i",
        "temp_ex": "T_e",
        "hum_ex": "H_e",
        "vpd_ex": "VPD_e",
        "ble_temp_inside": "BLE_T_i",
        "ble_hum_inside": "BLE_H_i",
        "ble_vpd_inside": "BLE_VPD_i",
        "ble_temp_outside": "BLE_T_e",
        "ble_hum_outside": "BLE_H_e",
        "ble_vpd_outside": "BLE_VPD_e",
        "v_bat": "battery_voltage",
        "rssi": "rssi",
        "light_pct": "light_pct",
        "exhaust_fan_rpm": "exhaust_fan_rpm",
        "circulation_fan_rpm": "circulation_fan_rpm",
    }
    HISTORY_RANGE_LABELS = {
        1: "1h",
        2: "2h",
        3: "3h",
        6: "6h",
        12: "12h",
        24: "24h",
        48: "48h",
        7 * 24: "7d",
        30 * 24: "30d",
        365 * 24: "365d",
    }

    def __init__(self, gsm):
        self.gsm = gsm
        self.running = True

        # Buffers
        self.window = config.get_tile_graph_window()
        self.graph_buffers = defaultdict(self._new_buffer)
        self._trend_buffers = defaultdict(self._new_buffer)
        self._last_smoothed_values = {}
        self._last_units = {}

        # Counter für das Downsampling (Graph Resolution)
        self._update_counters = defaultdict(int)

        # Separater Graph-Takt
        self.graph_refresh_interval = config.get_graph_refresh_interval()
        self.base_refresh_interval = config.get_refresh_interval()
        self._graph_refresh_tick_interval = 1
        self.graph_resolution = 100.0
        self._resolution_skip_interval = 1
        self._graph_refresh_counters = defaultdict(int)

        # Trends
        self.global_trends = {}

        # History besitzt genau einen zentralen Pipeline-Zustand. Nur der
        # Fullscreen darf ein Zeitfenster beim Virtual Hub auswählen; die
        # Messdaten selbst werden ausschließlich über /data eingespeist.
        self._history_lock = threading.RLock()
        self._history_pipeline_payload = None
        self._history_session = None
        self._history_revision = -1
        self._history_generated_at = -1.0
        self._history_retired_sessions = set()
        self._history_selection_key = None
        self._history_selection_id = None
        self._history_selection_base_revision = -1
        self._history_selection_base_session = None
        self._history_selection_failed_key = None
        self._history_selection_error = None
        self._history_confirmed_selection_id = None
        self._history_confirmed_mode = None
        self._active_history_window = None
        self._graph_range_revision = 0

        # Alle dynamischen Settings zentral laden
        self.refresh_config()

    def _new_buffer(self):
        return deque(maxlen=self.window)

    # ---------------------------------------------------------
    # UNIFIED GRAPH SNAPSHOTS
    # ---------------------------------------------------------
    @staticmethod
    def _axis_bounds(values):
        minimum = min(values)
        maximum = max(values)
        if minimum == maximum:
            return minimum - 1.0, maximum + 1.0

        difference = maximum - minimum
        return (
            minimum - (difference * 0.08),
            maximum + (difference * 0.08),
        )

    def get_live_snapshot(self, key, label_count=5):
        buffer = self.get_buffer(key)
        if not buffer:
            return None

        display_values = tuple(buffer[-self.window:])
        if len(display_values) == 1:
            points = (
                (0.0, display_values[0]),
                (1.0, display_values[0]),
            )
        else:
            points = tuple(
                (float(index), value)
                for index, value in enumerate(display_values)
            )

        ymin, ymax = self._axis_bounds(display_values)
        stats_values = self.get_stats(key)
        stats = (
            GraphStats(*stats_values)
            if stats_values[0] is not None
            else None
        )

        return GraphSnapshot(
            mode="live",
            points=points,
            timestamps=(),
            values=display_values,
            xmin=0.0,
            xmax=max(float(len(display_values) - 1), 1.0),
            ymin=ymin,
            ymax=ymax,
            labels=tuple(
                self.get_live_time_axis_labels(
                    display_len=len(display_values),
                    label_count=label_count,
                )
            ),
            last_value=display_values[-1],
            stats=stats,
            trend_icon=self.get_trend_icon(key) or "",
        )

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------
    def create_history_window(
        self,
        hours,
        start_timestamp=None,
        end_timestamp=None,
        now=None,
    ):
        if hours == "custom":
            start = float(start_timestamp)
            end = float(end_timestamp)
            label = "Benutzerdefiniert"
        else:
            numeric_hours = float(hours)
            if not math.isfinite(numeric_hours) or numeric_hours <= 0:
                raise ValueError("History-Zeitfenster muss positiv sein.")

            end = float(time.time() if now is None else now)
            start = end - (numeric_hours * 3600.0)
            label = self.HISTORY_RANGE_LABELS.get(
                hours,
                f"{numeric_hours:g}h",
            )

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start >= end
        ):
            raise ValueError("Ungültiges History-Zeitfenster.")

        return HistoryWindow(
            start_timestamp=start,
            end_timestamp=end,
            label=label,
            range_key=hours,
        )

    def set_active_history_window(self, history_window):
        if (
            history_window is not None
            and not isinstance(history_window, HistoryWindow)
        ):
            raise TypeError(
                "Aktiver Graph-Zeitraum muss ein HistoryWindow sein."
            )

        with self._history_lock:
            if history_window == self._active_history_window:
                return self._graph_range_revision

            self._history_selection_key = None
            self._active_history_window = history_window
            self._graph_range_revision += 1
            return self._graph_range_revision

    def get_graph_range_state(self):
        with self._history_lock:
            self._adopt_pipeline_target_for_device(
                self._active_dashboard_device_id()
            )
            return (
                self._active_history_window,
                self._graph_range_revision,
            )

    def get_history_control_state(self):
        """Return the latest Hub-confirmed base revision for commands."""
        with self._history_lock:
            if (
                not self._history_session
                or self._history_revision < 0
            ):
                return None
            return {
                "history_session": self._history_session,
                "rev_history": self._history_revision,
            }

    def _history_pipeline_key_for(
        self,
        device_id,
        history_window,
        target_points,
    ):
        return (
            str(device_id),
            float(history_window.start_timestamp),
            float(history_window.end_timestamp),
            int(target_points),
        )

    @staticmethod
    def _normalize_device_identifier(value):
        return str(value or "").strip()

    def _history_source_device_id(self, device_id):
        try:
            cfg = config._init()
            device = cfg.get("devices", {}).get(str(device_id), {})
            source_device_id = str(
                device.get("device_id") or ""
            ).strip()
        except (AttributeError, TypeError):
            source_device_id = ""
        return source_device_id

    def _history_device_key(self, payload, device_id):
        if not isinstance(payload, dict):
            return None

        devices = payload.get("devices", {})
        if not isinstance(devices, dict):
            return None

        identifier = self._normalize_device_identifier(
            self._history_source_device_id(device_id)
        )
        if not identifier:
            return None

        device = devices.get(identifier)
        if not isinstance(device, dict):
            return None
        block_device_id = self._normalize_device_identifier(
            device.get("device_id")
        )
        if block_device_id == identifier:
            return identifier
        return None

    def _history_selection_for_device(self, payload, device_id):
        history_device_id = self._history_device_key(payload, device_id)
        if history_device_id is None:
            return None
        device = payload.get("devices", {}).get(history_device_id)
        if not isinstance(device, dict):
            return None
        selection = device.get("history_selection")
        return selection if isinstance(selection, dict) else None

    @staticmethod
    def _history_control_signature(payload):
        devices = payload.get("devices", {})
        if not isinstance(devices, dict):
            return None

        signature = []
        for device_key in sorted(devices):
            device = devices.get(device_key)
            if not isinstance(device, dict):
                return None
            selection = device.get("history_selection")
            if not isinstance(selection, dict):
                return None
            mode = selection.get("mode")
            try:
                selection_revision = int(
                    selection["rev_history"]
                )
            except (KeyError, TypeError, ValueError):
                return None
            points = None
            log_range_key = None
            fixed_start = None
            fixed_end = None
            if mode == "history":
                try:
                    points = int(selection["points"])
                except (KeyError, TypeError, ValueError):
                    return None
                if selection.get("range_key") == "custom":
                    try:
                        fixed_start = float(selection["from"])
                        fixed_end = float(selection["to"])
                    except (KeyError, TypeError, ValueError):
                        return None
            elif mode == "live":
                try:
                    points = int(selection["points"])
                    log_range_key = int(
                        selection["log_range_key"]
                    )
                except (KeyError, TypeError, ValueError):
                    return None
                if log_range_key != 6:
                    return None
            signature.append(
                (
                    str(device_key),
                    str(device.get("device_id") or ""),
                    selection_revision,
                    str(selection.get("selection_id") or ""),
                    mode,
                    selection.get("range_key"),
                    log_range_key,
                    points,
                    fixed_start,
                    fixed_end,
                )
            )
        return tuple(signature)

    def _active_dashboard_device_id(self):
        getter = getattr(self.gsm, "get_active_device_id", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

    def _history_window_from_selection(self, selection):
        if not isinstance(selection, dict):
            return None
        if selection.get("mode") != "history":
            return None
        try:
            start_timestamp = float(selection["from"])
            end_timestamp = float(selection["to"])
            points = int(selection["points"])
        except (KeyError, TypeError, ValueError):
            return None
        if (
            not math.isfinite(start_timestamp)
            or not math.isfinite(end_timestamp)
            or start_timestamp >= end_timestamp
            or points < 1
        ):
            return None
        range_key = selection.get("range_key")
        label = str(
            selection.get("range_label")
            or self.HISTORY_RANGE_LABELS.get(
                range_key,
                "Benutzerdefiniert",
            )
        )
        return HistoryWindow(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            label=label,
            range_key=range_key,
        )

    def _adopt_pipeline_target_for_device(self, device_id):
        payload = self._history_pipeline_payload
        if not isinstance(payload, dict) or not device_id:
            return False
        selection = self._history_selection_for_device(
            payload,
            device_id,
        )
        if not isinstance(selection, dict):
            return False
        try:
            target_revision = int(selection["rev_history"])
        except (KeyError, TypeError, ValueError):
            return False

        if (
            self._history_selection_id is not None
            and selection.get("selection_id")
            != self._history_selection_id
            and target_revision <= self._history_selection_base_revision
        ):
            return False

        history_window = self._history_window_from_selection(selection)
        if selection.get("mode") == "live":
            history_window = None
        elif history_window is None:
            return False

        changed = history_window != self._active_history_window
        if changed:
            self._active_history_window = history_window
            self._graph_range_revision += 1

        if target_revision > self._history_selection_base_revision:
            if (
                self._history_selection_id is not None
                and selection.get("selection_id")
                == self._history_selection_id
                and self._history_session
                == self._history_selection_base_session
            ):
                self._history_confirmed_selection_id = (
                    self._history_selection_id
                )
                self._history_confirmed_mode = selection.get("mode")
            self._history_selection_key = None
            self._history_selection_id = None
            self._history_selection_base_revision = target_revision
            self._history_selection_base_session = None
        return changed

    def select_history_window(
        self,
        device_id,
        history_window,
        selection_id,
        base_revision,
        base_session,
        force=False,
        target_points=None,
    ):
        """Register one command-engine-owned History target locally."""
        points = (
            self.HISTORY_TARGET_POINTS
            if target_points is None
            else int(target_points)
        )
        if points < 1:
            raise ValueError("History-Punktbudget muss positiv sein.")
        selection_key = self._history_pipeline_key_for(
            device_id,
            history_window,
            points,
        )
        normalized_selection_id = str(selection_id or "").strip()
        normalized_base_session = str(base_session or "").strip()
        if not normalized_selection_id:
            return HistorySelectionResult(
                selection_key,
                "failed",
                "History-Auswahlkennung fehlt.",
            )

        with self._history_lock:
            if (
                normalized_base_session != self._history_session
                or int(base_revision) != self._history_revision
            ):
                return HistorySelectionResult(
                    selection_key,
                    "failed",
                    "History-Basisrevision ist nicht mehr aktuell.",
                    normalized_selection_id,
                    int(base_revision) + 1,
                )
            pipeline_key = self._history_pipeline_key_for_device(
                device_id
            )
            if not force and pipeline_key == selection_key:
                return HistorySelectionResult(
                    selection_key,
                    "loaded",
                    selection_id=normalized_selection_id,
                    target_revision=int(base_revision),
                )
            if not force and self._history_selection_key == selection_key:
                return HistorySelectionResult(
                    selection_key,
                    "loading",
                    selection_id=normalized_selection_id,
                    target_revision=int(base_revision) + 1,
                )
            self._history_selection_key = selection_key
            self._history_selection_id = normalized_selection_id
            self._history_selection_base_revision = int(base_revision)
            self._history_selection_base_session = (
                normalized_base_session
            )
            self._history_selection_failed_key = None
            self._history_selection_error = None
        return HistorySelectionResult(
            selection_key,
            "loading",
            selection_id=normalized_selection_id,
            target_revision=int(base_revision) + 1,
        )

    def select_live_mode(
        self,
        device_id,
        selection_id,
        base_revision,
        base_session,
    ):
        """Register one command-engine-owned Live target locally."""
        selection_key = (str(device_id), "live")
        normalized_selection_id = str(selection_id or "").strip()
        normalized_base_session = str(base_session or "").strip()
        with self._history_lock:
            if (
                not normalized_selection_id
                or normalized_base_session != self._history_session
                or int(base_revision) != self._history_revision
            ):
                return HistorySelectionResult(
                    selection_key,
                    "failed",
                    "History-Basisrevision ist nicht mehr aktuell.",
                    normalized_selection_id or None,
                    int(base_revision) + 1,
                )
            self._history_selection_key = None
            self._history_selection_id = normalized_selection_id
            self._history_selection_base_revision = int(base_revision)
            self._history_selection_base_session = (
                normalized_base_session
            )
            self._history_selection_failed_key = None
            self._history_selection_error = None
        return HistorySelectionResult(
            selection_key,
            "loading",
            selection_id=normalized_selection_id,
            target_revision=int(base_revision) + 1,
        )

    def complete_history_command(
        self,
        selection_id,
        error=None,
    ):
        """Record only transport failure; success still waits for /data."""
        with self._history_lock:
            if selection_id != self._history_selection_id:
                return False
            if error:
                failed_key = self._history_selection_key
                if failed_key is None:
                    failed_key = (
                        self._active_dashboard_device_id(),
                        "live",
                    )
                self._history_selection_failed_key = failed_key
                self._history_selection_id = None
                self._history_selection_base_revision = (
                    self._history_revision
                )
                self._history_selection_base_session = None
                self._history_selection_error = str(error)
            return True

    def consume_history_confirmation(self, selection_id):
        """Consume one Hub-pipeline confirmation for popup feedback."""
        with self._history_lock:
            if (
                not selection_id
                or selection_id
                != self._history_confirmed_selection_id
            ):
                return None
            result = {
                "selection_id": self._history_confirmed_selection_id,
                "mode": self._history_confirmed_mode,
                "rev_history": self._history_revision,
            }
            self._history_confirmed_selection_id = None
            self._history_confirmed_mode = None
            return result

    def _extract_history(self, payload, device_id):
        if not isinstance(payload, dict):
            raise ValueError("History-Pipeline ist kein JSON-Objekt.")

        devices = payload.get("devices", {})
        if not isinstance(devices, dict):
            raise ValueError(
                "History-Pipeline enthält keinen gültigen Geräteblock."
            )

        history_device_id = self._history_device_key(
            payload,
            device_id,
        )
        device = devices.get(history_device_id)

        if not isinstance(device, dict):
            return {}

        history = device.get("history", {})
        return history if isinstance(history, dict) else {}

    def _history_pipeline_key_for_device(self, device_id):
        selection = self._history_selection_for_device(
            self._history_pipeline_payload,
            device_id,
        )
        if (
            not isinstance(selection, dict)
            or selection.get("mode") != "history"
        ):
            return None
        return self._history_data_key_for_device(device_id)

    def _history_data_key_for_device(self, device_id):
        payload = self._history_pipeline_payload
        if not isinstance(payload, dict) or not device_id:
            return None

        normalized_device_id = str(device_id)
        devices = payload.get("devices", {})
        if not isinstance(devices, dict):
            return None

        history_device_id = self._history_device_key(
            payload,
            normalized_device_id,
        )
        if history_device_id is None:
            return None

        selection = self._history_selection_for_device(
            payload,
            normalized_device_id,
        )
        if not isinstance(selection, dict):
            return None
        mode = selection.get("mode")
        if mode == "history":
            pass
        elif mode == "live":
            try:
                if int(selection["log_range_key"]) != 6:
                    return None
            except (KeyError, TypeError, ValueError):
                return None
        else:
            return None
        try:
            start_timestamp = float(selection["from"])
            end_timestamp = float(selection["to"])
            points = int(selection["points"])
        except (KeyError, TypeError, ValueError):
            return None
        if (
            not math.isfinite(start_timestamp)
            or not math.isfinite(end_timestamp)
            or start_timestamp >= end_timestamp
            or points < 1
        ):
            return None
        return (
            normalized_device_id,
            start_timestamp,
            end_timestamp,
            points,
        )

    def ingest_history_pipeline(self, payload):
        """Accept only the newest Hub-confirmed /data History revision."""
        if not isinstance(payload, dict):
            return False

        try:
            history_session = str(payload["history_session"]).strip()
            history_revision = int(payload["rev_history"])
            history_generated_at = float(
                payload["history_generated_at"]
            )
            devices = payload["devices"]
        except (KeyError, TypeError, ValueError):
            return False

        if (
            not history_session
            or history_revision < 1
            or not math.isfinite(history_generated_at)
            or not isinstance(devices, dict)
        ):
            return False

        normalized_payload = deepcopy(payload)
        normalized_payload["history_session"] = history_session
        normalized_payload["rev_history"] = history_revision
        normalized_payload[
            "history_generated_at"
        ] = history_generated_at

        with self._history_lock:
            content_refresh = False
            if history_session in self._history_retired_sessions:
                return False
            if history_session == self._history_session:
                if history_revision < self._history_revision:
                    return False
                if history_revision == self._history_revision:
                    if (
                        history_generated_at
                        <= self._history_generated_at
                    ):
                        return False
                    if self._history_control_signature(
                        normalized_payload
                    ) != self._history_control_signature(
                        self._history_pipeline_payload
                    ):
                        return False
                    content_refresh = True
            elif self._history_session is not None:
                self._history_retired_sessions.add(
                    self._history_session
                )

            previous_session = self._history_session
            active_device_id = self._active_dashboard_device_id()
            previous_active_block = None
            if (
                active_device_id
                and isinstance(self._history_pipeline_payload, dict)
            ):
                previous_key = self._history_device_key(
                    self._history_pipeline_payload,
                    active_device_id,
                )
                previous_active_block = deepcopy(
                    self._history_pipeline_payload.get(
                        "devices",
                        {},
                    ).get(previous_key)
                )
            self._history_session = history_session
            self._history_revision = history_revision
            self._history_generated_at = history_generated_at
            if self._history_pipeline_payload == normalized_payload:
                return False

            self._history_pipeline_payload = normalized_payload
            if previous_session not in (None, history_session):
                self._history_selection_key = None
                self._history_selection_id = None
                self._history_selection_base_revision = history_revision
                self._history_selection_base_session = None
                self._history_selection_failed_key = None
                self._history_selection_error = None

            range_changed = self._adopt_pipeline_target_for_device(
                active_device_id
            )
            if content_refresh and not range_changed and active_device_id:
                active_key = self._history_device_key(
                    normalized_payload,
                    active_device_id,
                )
                active_block = normalized_payload.get(
                    "devices",
                    {},
                ).get(active_key)
                if active_block != previous_active_block:
                    self._graph_range_revision += 1
            selected_key = self._history_selection_key
            if (
                selected_key is not None
                and self._history_pipeline_key_for_device(
                    selected_key[0]
                ) == selected_key
            ):
                self._history_selection_key = None
            if (
                self._history_selection_failed_key is not None
                and self._history_pipeline_key_for_device(
                    self._history_selection_failed_key[0]
                ) == self._history_selection_failed_key
            ):
                self._history_selection_failed_key = None
                self._history_selection_error = None
        return True

    def get_history_selection_state(self, selection_key):
        if selection_key is None:
            return "idle", None

        with self._history_lock:
            if (
                self._history_pipeline_key_for_device(selection_key[0])
                == selection_key
            ):
                return "loaded", None
            if selection_key == self._history_selection_key:
                return "loading", None
            if selection_key == self._history_selection_failed_key:
                return "failed", self._history_selection_error
        return "idle", None

    def get_history_pipeline_key(self, device_id=None):
        """Return the key of the History block received through /data."""
        with self._history_lock:
            if device_id is None:
                return None
            pipeline_key = self._history_pipeline_key_for_device(
                device_id
            )
            if (
                self._history_selection_key is not None
                and self._history_selection_key[0] == str(device_id)
                and pipeline_key != self._history_selection_key
            ):
                return None
            return pipeline_key

    def get_cached_history_snapshot(
        self,
        device_id,
        tile_id,
        label_count=2,
    ):
        """Read passively from the History block carried by /data."""
        with self._history_lock:
            pipeline_key = self._history_data_key_for_device(
                device_id
            )
            if pipeline_key is None:
                return None

        return self.get_history_snapshot(
            pipeline_key=pipeline_key,
            tile_id=tile_id,
            label_count=label_count,
            _allow_live_cache=True,
        )

    def cancel_history_selection(self):
        with self._history_lock:
            self._history_selection_key = None
            self._history_selection_id = None
            self._history_selection_base_revision = self._history_revision
            self._history_selection_base_session = None
            self._history_confirmed_selection_id = None
            self._history_confirmed_mode = None

    @staticmethod
    def _history_axis_labels(source_timestamps, label_count):
        label_count = max(2, int(label_count))
        start_timestamp = source_timestamps[0]
        end_timestamp = source_timestamps[-1]
        span = end_timestamp - start_timestamp
        timestamps = [
            start_timestamp + (span * index / (label_count - 1))
            for index in range(label_count)
        ]

        if span <= 12 * 3600:
            date_format = "%H:%M"
        elif span <= 7 * 24 * 3600:
            date_format = "%d.%m\n%H:%M"
        else:
            date_format = "%d.%m.%y"

        return tuple(
            time.strftime(date_format, time.localtime(timestamp))
            for timestamp in timestamps
        )

    @staticmethod
    def _history_point_label(timestamp):
        return time.strftime(
            "%d.%m.%Y %H:%M:%S",
            time.localtime(timestamp),
        )

    @staticmethod
    def _normalize_history_series(series):
        if not isinstance(series, dict):
            return ()

        timestamps = series.get("t", [])
        values = series.get("v", [])
        if not isinstance(timestamps, list) or not isinstance(values, list):
            return ()

        normalized = []
        for timestamp, value in zip(timestamps, values):
            try:
                parsed_timestamp = float(timestamp)
                parsed_value = float(value)
            except (TypeError, ValueError):
                continue
            if (
                math.isfinite(parsed_timestamp)
                and math.isfinite(parsed_value)
            ):
                normalized.append((parsed_timestamp, parsed_value))

        return tuple(sorted(normalized, key=lambda point: point[0]))

    def get_history_snapshot(
        self,
        pipeline_key,
        tile_id,
        label_count=5,
        range_label="",
        _allow_live_cache=False,
    ):
        with self._history_lock:
            device_id = pipeline_key[0]
            current_key = (
                self._history_data_key_for_device(device_id)
                if _allow_live_cache
                else self._history_pipeline_key_for_device(device_id)
            )
            if (
                pipeline_key
                != current_key
            ):
                return None
            try:
                history = self._extract_history(
                    self._history_pipeline_payload,
                    device_id,
                )
            except ValueError:
                return None

        history_key = self.HISTORY_KEY_MAP.get(tile_id)
        if not history_key:
            return None

        source_points = self._normalize_history_series(
            history.get(history_key)
        )
        if not source_points:
            return None

        (
            _device_id,
            _requested_start,
            _requested_end,
            _points,
        ) = pipeline_key
        timestamps = tuple(point[0] for point in source_points)
        values = tuple(point[1] for point in source_points)
        graph_points = tuple(
            (float(index), value)
            for index, value in enumerate(values)
        )
        graph_span = max(float(len(graph_points) - 1), 1.0)

        if len(graph_points) == 1:
            value = graph_points[0][1]
            line_points = (
                (0.0, value),
                (1.0, value),
            )
        else:
            line_points = graph_points

        stats = GraphStats(
            average=sum(values) / len(values),
            minimum=min(values),
            maximum=max(values),
        )
        ymin, ymax = self._axis_bounds(values)

        notable_points = []
        for role, target_value in (
            ("minimum", stats.minimum),
            ("maximum", stats.maximum),
        ):
            index = values.index(target_value)
            point = GraphPoint(
                graph_x=graph_points[index][0],
                value=target_value,
                timestamp=timestamps[index],
                index=index,
                total=len(values),
                role=role,
                label=self._history_point_label(timestamps[index]),
            )
            if point.coordinates not in {
                marker.coordinates
                for marker in notable_points
            }:
                notable_points.append(point)

        return GraphSnapshot(
            mode="history",
            points=line_points,
            timestamps=timestamps,
            values=values,
            xmin=0.0,
            xmax=graph_span,
            ymin=ymin,
            ymax=ymax,
            labels=self._history_axis_labels(
                timestamps,
                label_count,
            ),
            last_value=values[-1],
            stats=stats,
            trend_icon="",
            range_label=range_label,
            notable_points=tuple(notable_points),
        )

    def inspect_history_point(self, pipeline_key, tile_id, graph_x):
        snapshot = self.get_history_snapshot(
            pipeline_key=pipeline_key,
            tile_id=tile_id,
        )
        if snapshot is None:
            return None

        graph_positions = tuple(
            float(index)
            for index in range(len(snapshot.timestamps))
        )
        index = min(
            range(len(graph_positions)),
            key=lambda item: abs(graph_positions[item] - graph_x),
        )
        timestamp = snapshot.timestamps[index]
        return GraphPoint(
            graph_x=graph_positions[index],
            value=snapshot.values[index],
            timestamp=timestamp,
            index=index,
            total=len(snapshot.values),
            role="selected",
            label=self._history_point_label(timestamp),
        )

    # ---------------------------------------------------------
    # DATA ACCESS (Wichtig für Mixed Mode & Tiles)
    # ---------------------------------------------------------
    def get_last_value(self, key):
        buf = self.graph_buffers.get(key)
        if buf and len(buf) > 0:
            return buf[-1]
        return None

    def get_buffer(self, key):
        buf = self.graph_buffers.get(key)
        return list(buf) if buf else []

    def get_stats(self, key):
        buf = self.graph_buffers.get(key)
        if not buf or len(buf) < 2:
            return None, None, None
    
        data = list(buf)
        avg = sum(data) / len(data)
        mn = min(data)
        mx = max(data)
    
        if mn == mx:
            mn -= 0.1
            mx += 0.1
    
        return avg, mn, mx

    def get_trend_icon(self, key):
        val = self.global_trends.get(key, 0)
        icons = {-1: "\uf063", 1: "\uf062", 0: "\uf061"}
        return icons.get(val, "\uf061")

    def get_all_keys(self):
        return list(self.graph_buffers.keys())

    def get_graph_refresh_interval(self):
        return self.graph_refresh_interval


    def get_graph_refresh_tick_interval(self):
        return self._graph_refresh_tick_interval



    def get_window_size(self):
        return self.window

    def get_effective_point_interval(self):
        return (
            self.graph_refresh_interval
            * self._resolution_skip_interval
        )

    def get_live_time_axis_labels(self, display_len, label_count=5):
        return compute_time_axis_labels(
            display_len=int(display_len),
            refresh_rate=self.graph_refresh_interval,
            raw_res=self.graph_resolution,
        )

    # ---------------------------------------------------------
    # PROCESS VALUE
    # ---------------------------------------------------------
    def process_new_value(self, key, value):
        if not self.running or value is None:
            return

        # ---------------------------------------------------------
        # SEPARATER GRAPH-TAKT
        # ---------------------------------------------------------
        # Der erste Wert jedes Keys wird sofort verarbeitet.
        # Danach wird nur noch im konfigurierten Graph-Intervall verarbeitet.
        has_no_graph_data = (
            key not in self.graph_buffers
            or len(self.graph_buffers[key]) == 0
        )

        if has_no_graph_data:
            self._graph_refresh_counters[key] = 0
        else:
            self._graph_refresh_counters[key] += 1

            if (
                self._graph_refresh_counters[key]
                < self._graph_refresh_tick_interval
            ):
                return

            self._graph_refresh_counters[key] = 0

        try:
            val_float = float(value)
            current_unit = self.gsm.get_unit(key)
            
            # --- UNIT SWITCH LOGIK ---
            if key in self._last_units and self._last_units[key] != current_unit:
                print(f"[GraphEngine] Unit switch... Resetting buffer for {key}")
                self.graph_buffers[key] = deque([val_float, val_float], maxlen=self.window)
                self._trend_buffers[key] = deque([val_float, val_float], maxlen=self.window)
                self._last_smoothed_values[key] = val_float
                self._last_units[key] = current_unit
                self._update_counters[key] = 0
                self._graph_refresh_counters[key] = 0
                return
            
            # --- 1. SMOOTHING LOGIK ---
            # Intuitive Logik: 
            # Wenn Config-Faktor = 0.9 -> Sehr träge/glatt (0.1 Altwert + 0.9 Neuwert? Nein, genau andersrum!)
            # Mathematisch: Je kleiner der Faktor für den *neuen* Wert, desto stärker die Glättung.
            # Daher: f_new = 1.0 - smoothing_factor
            
            if "mixed" in key:
                f_new = 0.2  # Beibehaltenes Hardcoded-Smoothing für Mixed Mode (entspricht 0.8 Smoothing)
            else:
                # Clamp zwischen 0.0 und 0.99, um Divisionen durch 0 oder starre Graphen zu vermeiden
                cfg_factor = max(0.0, min(0.99, self.smoothing_factor))
                f_new = 1.0 - cfg_factor 
            
            if key not in self._last_smoothed_values:
                smoothed = val_float
            else:
                last = self._last_smoothed_values[key]
                # Schwellenwert-Breakout (bei harten Sprüngen nicht glätten)
                if abs(val_float - last) > 5.0:
                    smoothed = val_float
                else:
                    # Exponentieller gleitender Mittelwert
                    smoothed = (last * (1.0 - f_new)) + (val_float * f_new)
            
            self._last_smoothed_values[key] = smoothed
            
            # --- 2. GRAPH RESOLUTION LOGIK (Slider: 1-100) ---
            skip_interval = self._resolution_skip_interval
                        
            # --- DER FIX: Explizite Prüfung vor dem Counter-Inkrement ---
            # Wir prüfen, ob für diesen Key überhaupt schon Werte im Buffer existieren.
            # Da es ein defaultdict ist, müssen wir schauen, ob der Key existiert UND Werte hat.
            has_no_data = key not in self.graph_buffers or len(self.graph_buffers[key]) == 0
            
            if has_no_data:
                # Absolut erster Frame für diesen Key: Sofort durchlassen!
                # Wir setzen den Counter direkt auf 0, damit der NÄCHSTE Frame das Intervall startet.
                self._update_counters[key] = 0
                force_update = True
            else:
                # Normaler Modus: Counter hochzählen
                self._update_counters[key] += 1
                force_update = self._update_counters[key] >= skip_interval

            # Nur schreiben, wenn das Intervall erreicht ist ODER wir den ersten Frame erzwingen
            if force_update:
                self._update_counters[key] = 0  
                
                # Puffer befüllen
                g_buf = self.graph_buffers[key]
                g_buf.append(smoothed)
                if len(g_buf) > self.window:
                    g_buf.popleft()
                
                t_buf = self._trend_buffers[key]
                t_buf.append(smoothed)
                if len(t_buf) > self.window:
                    t_buf.popleft()
                    
                self.global_trends[key] = self._calculate_trend_logic(list(t_buf))            
        except Exception as e:
            print(f"[GraphEngine] Error in process_new_value: {e}")

    def _calculate_trend_logic(self, buf):
        if len(buf) < 5: return 0
        start, end = buf[0], buf[-1]
        diff = end - start
        threshold = max(0.01, abs(start) * 0.002)
        
        if diff > threshold: return 1
        if diff < -threshold: return -1
        return 0

    def reset(self):
        print("[GraphEngine] RESET")
        self.graph_buffers.clear()
        self._trend_buffers.clear()
        self._last_smoothed_values.clear()
        self.global_trends.clear()
        self._update_counters.clear()
        self._graph_refresh_counters.clear()
        with self._history_lock:
            self._history_pipeline_payload = None
            self._history_session = None
            self._history_revision = -1
            self._history_generated_at = -1.0
            self._history_retired_sessions.clear()
            self._history_selection_key = None
            self._history_selection_id = None
            self._history_selection_base_revision = -1
            self._history_selection_base_session = None
            self._history_selection_failed_key = None
            self._history_selection_error = None
            self._history_confirmed_selection_id = None
            self._history_confirmed_mode = None

    def rebuild_buffers(self):
        self.window = config.get_tile_graph_window()
        for key in list(self.graph_buffers.keys()):
            old_buf = list(self.graph_buffers[key])[-self.window:]
            self.graph_buffers[key] = deque(old_buf, maxlen=self.window)
        for key in list(self._trend_buffers.keys()):
            old_buf = list(self._trend_buffers[key])[-self.window:]
            self._trend_buffers[key] = deque(old_buf, maxlen=self.window)

    def refresh_config(
        self,
        graph_refresh_interval=None,
        base_refresh_interval=None,
    ):
        self.rebuild_buffers()

        self.smoothing_factor = float(
            config.get_graph_smoothing_factor()
        )

        raw_resolution = float(config.get_graph_resolution())

        if raw_resolution <= 1.0:
            self.graph_resolution = max(
                1.0,
                raw_resolution * 100.0,
            )
        else:
            self.graph_resolution = raw_resolution

        self.graph_resolution = max(
            1.0,
            min(100.0, self.graph_resolution),
        )

        self._resolution_skip_interval = max(
            1,
            int(100.0 / self.graph_resolution),
        )

        if graph_refresh_interval is None:
            graph_refresh_interval = config.get_graph_refresh_interval()

        if base_refresh_interval is None:
            base_refresh_interval = config.get_refresh_interval()

        self.graph_refresh_interval = max(
            0.1,
            float(graph_refresh_interval),
        )

        self.base_refresh_interval = max(
            0.001,
            float(base_refresh_interval),
        )

        self._graph_refresh_tick_interval = max(
            1,
            round(
                self.graph_refresh_interval
                / self.base_refresh_interval
            ),
        )

        # Den tatsächlich erreichbaren Zeitabstand festhalten.
        self.graph_refresh_interval = (
            self._graph_refresh_tick_interval
            * self.base_refresh_interval
        )

        self._graph_refresh_counters.clear()

        if config.is_developer_mode():
            print(
                "[GraphEngine] Config refreshed: "
                f"graph_interval={self.graph_refresh_interval:.3f}s, "
                f"base_interval={self.base_refresh_interval:.3f}s, "
                f"ticks={self._graph_refresh_tick_interval}"
            )
