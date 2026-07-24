from copy import deepcopy
import math
import threading
import time
from typing import Callable, Optional
import uuid

from flask import Blueprint, jsonify, request

from history_compressor import compress


DEFAULT_TARGET_POINTS = 30
MAX_TARGET_POINTS = 500
DEFAULT_HISTORY_HOURS = 48
LIVE_HISTORY_HOURS = 6
HISTORY_REFRESH_SECONDS = 60.0


class HistoryPipelineStore:
    """Hub-owned per-device History targets carried by the /data pipeline."""

    def __init__(
        self,
        csv_file: Optional[str] = None,
        log_cb: Optional[Callable[[str], None]] = None,
        history_session: Optional[str] = None,
    ):
        self.csv_file = csv_file
        self.log_cb = log_cb
        self._lock = threading.RLock()
        self._history_session = (
            str(history_session).strip()
            if history_session
            else str(uuid.uuid4())
        )
        self._rev_history = 0
        self._history_generated_at = 0.0
        self._selections = {}
        self._payload = None
        self._refresh_stop = threading.Event()
        self._refresh_thread = None

    @staticmethod
    def _range_label(range_key) -> str:
        labels = {

            1: "1h",
            2: "2h",
            3: "3h",
            6: "6h",
            24: "24h",
            48: "48h",
            7 * 24: "7d",
            30 * 24: "30d",
            365 * 24: "365d",
            "custom": "Benutzerdefiniert",
        }
        return labels.get(range_key, str(range_key))

    def _selection_id(self, selection_id: Optional[str]) -> str:
        normalized = str(selection_id or "").strip()
        return normalized or str(uuid.uuid4())

    @staticmethod
    def _device_id(device_id) -> str:
        return str(device_id or "").strip()

    def _selection(
        self,
        revision: int,
        selection_id: str,
        mode: str,
        range_key=None,
        start_timestamp=None,
        end_timestamp=None,
        target_points=None,
        log_range_key=None,
    ):
        selection = {
            "rev_history": revision,
            "selection_id": selection_id,
            "mode": mode,
            "range_key": range_key,
            "range_label": (
                "Live"
                if mode == "live"
                else self._range_label(range_key)
            ),
        }
        if mode == "history" or (
            mode == "live"
            and log_range_key is not None
        ):
            selection.update(
                {
                    "from": float(start_timestamp),
                    "to": float(end_timestamp),
                    "points": int(target_points),
                }
            )
        if mode == "live" and log_range_key is not None:
            selection.update(
                {
                    "log_range_key": log_range_key,
                    "log_range_label": self._range_label(
                        log_range_key
                    ),
                }
            )
        return selection

    @staticmethod
    def _device_block(
        device_id: str,
        compressed: dict,
        selection: dict,
        generated_at: float,
    ):
        return {
            "device_id": device_id,
            "name": compressed.get("name", ""),
            # Die bestätigte Auswahl steht absichtlich vor dem eigentlichen
            # Log. Dashboards lesen zuerst diesen Header und danach History.
            "history_selection": deepcopy(selection),
            "history_generated_at": float(generated_at),
            "total_raw_points": compressed.get("total_raw_points", 0),
            "history": deepcopy(compressed.get("history", {})),
        }

    def _selection_result(
        self,
        device_id: str,
        selection: dict,
    ):
        return {
            "history_session": self._history_session,
            "device_id": device_id,
            **deepcopy(selection),
        }

    def get_control_state(self):
        """Return the current command base without exposing log contents."""
        with self._lock:
            return {
                "history_session": self._history_session,
                "rev_history": self._rev_history,
            }

    def _base_conflict(self, base_revision, base_session):
        try:
            normalized_revision = int(base_revision)
        except (TypeError, ValueError):
            normalized_revision = None
        normalized_session = str(base_session or "").strip()
        if (
            normalized_revision == self._rev_history
            and normalized_session == self._history_session
        ):
            return None
        return {
            "status": "conflict",
            "error": (
                "History-Basisrevision ist nicht mehr aktuell. "
                "Die aktuelle Hub-Bestätigung muss zuerst über /data "
                "übernommen werden."
            ),
            "history_session": self._history_session,
            "rev_history": self._rev_history,
        }

    def _next_generated_at(self, value=None):
        generated_at = float(
            time.time()
            if value is None
            else value
        )
        if generated_at <= self._history_generated_at:
            generated_at = self._history_generated_at + 0.000001
        self._history_generated_at = generated_at
        return generated_at

    def _commit_pipeline(self, devices: dict, generated_at: float):
        self._payload = {
            "history_session": self._history_session,
            "rev_history": self._rev_history,
            "history_generated_at": float(generated_at),
            "devices": devices,
        }

    def select_window(
        self,
        start_timestamp: float,
        end_timestamp: float,
        target_points: int,
        device_id,
        range_key=None,
        selection_id: Optional[str] = None,
        base_revision=None,
        base_session=None,
    ):
        """Commit one target for one exact device_id without dropping peers."""
        with self._lock:
            normalized_device_id = self._device_id(device_id)
            if not normalized_device_id:
                return {"error": "Query-Parameter 'device_id' fehlt."}

            normalized_selection_id = self._selection_id(selection_id)
            previous = self._selections.get(normalized_selection_id)
            if previous is not None:
                return deepcopy(previous)
            conflict = self._base_conflict(
                base_revision,
                base_session,
            )
            if conflict is not None:
                return conflict

            devices = compress(
                csv_file=self.csv_file,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                target_points=target_points,
                log_cb=self.log_cb,
            )
            if "error" in devices:
                return {"error": devices["error"]}
            if normalized_device_id not in devices:
                return {
                    "error": (
                        "Keine Log-Daten für device_id "
                        f"'{normalized_device_id}' gefunden."
                    )
                }

            normalized_range_key = (
                range_key
                if range_key is not None
                else "custom"
            )
            self._rev_history += 1
            generated_at = self._next_generated_at()
            selection = self._selection(
                revision=self._rev_history,
                selection_id=normalized_selection_id,
                mode="history",
                range_key=normalized_range_key,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                target_points=target_points,
            )

            pipeline_devices = (
                deepcopy(self._payload["devices"])
                if self._payload is not None
                else {}
            )
            for compressed_device_id, compressed in devices.items():
                if (
                    compressed_device_id != normalized_device_id
                    and compressed_device_id in pipeline_devices
                ):
                    continue
                initial_selection = (
                    selection
                    if compressed_device_id == normalized_device_id
                    else self._selection(
                        revision=self._rev_history,
                        selection_id=(
                            f"hub-initial:{self._history_session}:"
                            f"{compressed_device_id}"
                        ),
                        mode="history",
                        range_key=normalized_range_key,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        target_points=target_points,
                    )
                )
                pipeline_devices[compressed_device_id] = (
                    self._device_block(
                        compressed_device_id,
                        compressed,
                        initial_selection,
                        generated_at,
                    )
                )

            self._commit_pipeline(pipeline_devices, generated_at)
            result = self._selection_result(
                normalized_device_id,
                selection,
            )
            self._selections[normalized_selection_id] = deepcopy(result)
            return result

    def select_live(
        self,
        device_id,
        selection_id: Optional[str] = None,
        base_revision=None,
        base_session=None,
    ):
        """Commit live mode plus a passive 6h log for one device_id."""
        with self._lock:
            normalized_device_id = self._device_id(device_id)
            if not normalized_device_id:
                return {"error": "Query-Parameter 'device_id' fehlt."}

            normalized_selection_id = self._selection_id(selection_id)
            previous = self._selections.get(normalized_selection_id)
            if previous is not None:
                return deepcopy(previous)
            conflict = self._base_conflict(
                base_revision,
                base_session,
            )
            if conflict is not None:
                return conflict

            end_timestamp = time.time()
            start_timestamp = (
                end_timestamp - (LIVE_HISTORY_HOURS * 3600)
            )
            compressed_devices = compress(
                csv_file=self.csv_file,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                target_points=DEFAULT_TARGET_POINTS,
                log_cb=self.log_cb,
            )
            if "error" in compressed_devices:
                return {"error": compressed_devices["error"]}

            devices = (
                deepcopy(self._payload["devices"])
                if self._payload is not None
                else {}
            )

            self._rev_history += 1
            generated_at = self._next_generated_at()
            selection = self._selection(
                revision=self._rev_history,
                selection_id=normalized_selection_id,
                mode="live",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                target_points=DEFAULT_TARGET_POINTS,
                log_range_key=LIVE_HISTORY_HOURS,
            )
            previous_block = devices.get(normalized_device_id, {})
            compressed = compressed_devices.get(
                normalized_device_id,
                {
                    "name": (
                        previous_block.get("name", "")
                        if isinstance(previous_block, dict)
                        else ""
                    ),
                    "total_raw_points": 0,
                    "history": {},
                },
            )
            devices[normalized_device_id] = self._device_block(
                normalized_device_id,
                compressed,
                selection,
                generated_at,
            )
            self._commit_pipeline(devices, generated_at)
            result = self._selection_result(
                normalized_device_id,
                selection,
            )
            self._selections[normalized_selection_id] = deepcopy(result)
            return result

    @staticmethod
    def acknowledgement(payload):
        """Return control metadata only; series stay on the /data path."""
        keys = (
            "history_session",
            "rev_history",
            "selection_id",
            "device_id",
            "mode",
            "range_key",
            "range_label",
            "log_range_key",
            "log_range_label",
            "from",
            "to",
            "points",
        )
        return {
            "status": "selected",
            **{
                key: payload[key]
                for key in keys
                if key in payload
            },
        }

    def get_pipeline_payload(self):
        """Return all device targets, creating the 48h default once."""
        with self._lock:
            if self._payload is None:
                end_timestamp = time.time()
                start_timestamp = (
                    end_timestamp
                    - (DEFAULT_HISTORY_HOURS * 3600)
                )
                devices = compress(
                    csv_file=self.csv_file,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    target_points=DEFAULT_TARGET_POINTS,
                    log_cb=self.log_cb,
                )
                if "error" in devices:
                    return {"error": devices["error"]}

                self._rev_history += 1
                generated_at = self._next_generated_at()
                pipeline_devices = {}
                for device_id, compressed in devices.items():
                    selection = self._selection(
                        revision=self._rev_history,
                        selection_id=(
                            f"hub-default:{self._history_session}:"
                            f"{device_id}"
                        ),
                        mode="history",
                        range_key=DEFAULT_HISTORY_HOURS,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        target_points=DEFAULT_TARGET_POINTS,
                    )
                    pipeline_devices[device_id] = self._device_block(
                        device_id,
                        compressed,
                        selection,
                        generated_at,
                    )
                self._commit_pipeline(
                    pipeline_devices,
                    generated_at,
                )
            return deepcopy(self._payload)

    @staticmethod
    def _relative_range_hours(range_key):
        if range_key == "custom":
            return None
        try:
            hours = float(range_key)
        except (TypeError, ValueError):
            return None
        return hours if math.isfinite(hours) and hours > 0 else None

    def refresh_active_windows(self, now=None):
        """Refresh relative logs without changing their control revision."""
        with self._lock:
            if self._payload is None:
                return False

            end_timestamp = float(
                time.time()
                if now is None
                else now
            )
            if not math.isfinite(end_timestamp):
                raise ValueError(
                    "History-Aktualisierungszeit ist ungültig."
                )

            pipeline_devices = deepcopy(self._payload["devices"])
            compressed_by_window = {}
            refreshed_device_ids = []
            generated_at = None

            for device_id, current_block in list(
                pipeline_devices.items()
            ):
                if not isinstance(current_block, dict):
                    continue
                selection = current_block.get("history_selection")
                if not isinstance(selection, dict):
                    continue
                mode = selection.get("mode")
                if mode == "history":
                    range_key = selection.get("range_key")
                    log_range_key = None
                elif mode == "live":
                    range_key = None
                    log_range_key = selection.get("log_range_key")
                else:
                    continue

                hours = self._relative_range_hours(
                    (
                        range_key
                        if mode == "history"
                        else log_range_key
                    )
                )
                if hours is None:
                    continue

                try:
                    target_points = int(selection["points"])
                except (KeyError, TypeError, ValueError):
                    continue

                start_timestamp = (
                    end_timestamp - (hours * 3600.0)
                )
                cache_key = (
                    start_timestamp,
                    end_timestamp,
                    target_points,
                )
                compressed_devices = compressed_by_window.get(cache_key)
                if compressed_devices is None:
                    compressed_devices = compress(
                        csv_file=self.csv_file,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        target_points=target_points,
                        log_cb=self.log_cb,
                    )
                    compressed_by_window[cache_key] = compressed_devices
                if "error" in compressed_devices:
                    continue

                if generated_at is None:
                    generated_at = self._next_generated_at(
                        end_timestamp
                    )

                refreshed_selection = self._selection(
                    revision=int(selection["rev_history"]),
                    selection_id=str(selection["selection_id"]),
                    mode=mode,
                    range_key=range_key,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    target_points=target_points,
                    log_range_key=log_range_key,
                )
                compressed = compressed_devices.get(
                    device_id,
                    {
                        "name": current_block.get("name", ""),
                        "total_raw_points": 0,
                        "history": {},
                    },
                )
                pipeline_devices[device_id] = self._device_block(
                    device_id,
                    compressed,
                    refreshed_selection,
                    generated_at,
                )
                refreshed_device_ids.append(device_id)

            if not refreshed_device_ids:
                return False

            # rev_history bleibt absichtlich unverändert. Diese Commit-Marke
            # versioniert ausschließlich den neu erzeugten Loginhalt.
            self._commit_pipeline(pipeline_devices, generated_at)
            if self.log_cb:
                self.log_cb(
                    "[History Pipeline] Automatisch aktualisiert: "
                    f"{len(refreshed_device_ids)} Geräte, "
                    f"Revision {self._rev_history} unverändert"
                )
            return True

    def start_auto_refresh(
        self,
        refresh_seconds=HISTORY_REFRESH_SECONDS,
    ):
        interval = float(refresh_seconds)
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError(
                "History-Aktualisierungsintervall muss positiv sein."
            )
        with self._lock:
            if (
                self._refresh_thread is not None
                and self._refresh_thread.is_alive()
            ):
                return False
            self._refresh_stop.clear()
            self._refresh_thread = threading.Thread(
                target=self._auto_refresh_loop,
                args=(interval,),
                daemon=True,
                name="history-pipeline-refresh",
            )
            self._refresh_thread.start()
            return True

    def _auto_refresh_loop(self, interval):
        while not self._refresh_stop.wait(interval):
            try:
                self.refresh_active_windows()
            except Exception as exc:
                if self.log_cb:
                    self.log_cb(
                        "[History Pipeline] Automatische "
                        f"Aktualisierung fehlgeschlagen: {exc}"
                    )

    def stop_auto_refresh(self):
        self._refresh_stop.set()


def _parse_timestamp(name: str) -> float:
    raw_value = request.args.get(name)
    if raw_value is None:
        raise ValueError(f"Query-Parameter '{name}' fehlt.")

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Query-Parameter '{name}' ist kein gültiger Timestamp."
        ) from exc

    if not math.isfinite(value):
        raise ValueError(
            f"Query-Parameter '{name}' ist kein gültiger Timestamp."
        )

    return value


def _parse_target_points() -> int:
    raw_value = request.args.get("points", str(DEFAULT_TARGET_POINTS))

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Query-Parameter 'points' muss eine Ganzzahl sein."
        ) from exc

    if value < 1 or value > MAX_TARGET_POINTS:
        raise ValueError(
            f"Query-Parameter 'points' muss zwischen 1 und "
            f"{MAX_TARGET_POINTS} liegen."
        )

    return value


def _parse_range_key():
    raw_value = request.args.get("range_key", "custom").strip()
    if raw_value == "custom":
        return raw_value
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return raw_value


def create_history_blueprint(
    csv_file: Optional[str] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    pipeline_store: Optional[HistoryPipelineStore] = None,
) -> Blueprint:
    history_api = Blueprint("history_api", __name__)
    store = pipeline_store or HistoryPipelineStore(
        csv_file=csv_file,
        log_cb=log_cb,
    )

    @history_api.get("/history")
    def get_history():
        mode = request.args.get("mode", "history").strip().casefold()
        selection_id = request.args.get("selection_id")
        device_id = request.args.get("device_id")
        base_revision = request.args.get("base_revision")
        base_session = request.args.get("base_session")

        if mode == "live":
            payload = store.select_live(
                device_id=device_id,
                selection_id=selection_id,
                base_revision=base_revision,
                base_session=base_session,
            )
            if payload.get("status") == "conflict":
                return jsonify(payload), 409
            if "error" in payload:
                return jsonify({"error": payload["error"]}), 400
            return jsonify(store.acknowledgement(payload))
        if mode != "history":
            return jsonify({"error": "Ungültiger History-Modus."}), 400

        try:
            start_timestamp = _parse_timestamp("from")
            end_timestamp = _parse_timestamp("to")
            target_points = _parse_target_points()
            range_key = _parse_range_key()

            if start_timestamp >= end_timestamp:
                raise ValueError(
                    "Query-Parameter 'from' muss kleiner als 'to' sein."
                )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        payload = store.select_window(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            target_points=target_points,
            device_id=device_id,
            range_key=range_key,
            selection_id=selection_id,
            base_revision=base_revision,
            base_session=base_session,
        )

        if payload.get("status") == "conflict":
            return jsonify(payload), 409
        if "error" in payload:
            return jsonify({"error": payload["error"]}), 500

        if log_cb:
            log_cb(
                "[History Pipeline] "
                f"{start_timestamp:.3f} bis {end_timestamp:.3f}, "
                f"{target_points} Punkte, Revision "
                f"{payload['rev_history']} für device_id "
                f"{payload['device_id']} ausgewählt"
            )

        return jsonify(store.acknowledgement(payload))

    return history_api
