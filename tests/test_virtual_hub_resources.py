import csv
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUB_ROOT = PROJECT_ROOT / "tools" / "virtual_hub"
for path in (str(PROJECT_ROOT), str(HUB_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from bounded_log import BoundedLogBuffer
import history_compressor
import history_routes


class VirtualHubResourceTests(unittest.TestCase):
    def test_log_buffer_never_exceeds_limit(self):
        buffer = BoundedLogBuffer(3, initial_lines=("initial",))
        for index in range(10):
            buffer.append(str(index))

        text = buffer.drain_text()
        self.assertEqual(text.splitlines(), ["7", "8", "9"])
        self.assertEqual(buffer.snapshot(), ("7", "8", "9"))

    def test_history_index_is_incremental_and_preserves_device_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "log.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(
                    target,
                    fieldnames=("timestamp", "device_id", "device_name", "T_i"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "timestamp": 100.0,
                        "device_id": "dashboard-uuid",
                        "device_name": "growmaster-d064",
                        "T_i": 21.0,
                    }
                )

            first = history_compressor.compress(
                str(csv_path), 90.0, 110.0, 30
            )
            with csv_path.open("a", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(
                    target,
                    fieldnames=("timestamp", "device_id", "device_name", "T_i"),
                )
                writer.writerow(
                    {
                        "timestamp": 120.0,
                        "device_id": "dashboard-uuid",
                        "device_name": "growmaster-d064",
                        "T_i": 22.0,
                    }
                )
            second = history_compressor.compress(
                str(csv_path), 90.0, 130.0, 30
            )

        self.assertIn("dashboard-uuid", first)
        self.assertNotIn("growmaster-d064", first)
        self.assertEqual(
            second["dashboard-uuid"]["history"]["T_i"]["v"],
            [21.0, 22.0],
        )

    def test_pipeline_read_is_not_blocked_by_periodic_compression(self):
        store = history_routes.HistoryPipelineStore(
            history_session="test-session"
        )
        store._rev_history = 1
        store._payload = {
            "history_session": "test-session",
            "rev_history": 1,
            "history_generated_at": 100.0,
            "devices": {
                "device-1": {
                    "name": "Device",
                    "history_selection": {
                        "rev_history": 1,
                        "selection_id": "selection-1",
                        "mode": "history",
                        "range_key": 1,
                        "points": 30,
                    },
                    "history": {},
                }
            },
        }
        original_payload = store._payload
        entered = threading.Event()
        release = threading.Event()

        def slow_compress(**_kwargs):
            entered.set()
            release.wait(2.0)
            return {
                "device-1": {
                    "name": "Device",
                    "total_raw_points": 0,
                    "history": {},
                }
            }

        with patch.object(history_routes, "compress", side_effect=slow_compress):
            worker = threading.Thread(
                target=store.refresh_active_windows,
                kwargs={"now": 200.0},
            )
            worker.start()
            self.assertTrue(entered.wait(1.0))
            started = time.monotonic()
            payload = store.get_pipeline_payload(copy_payload=False)
            elapsed = time.monotonic() - started
            release.set()
            worker.join(2.0)

        self.assertIs(payload, original_payload)
        self.assertLess(elapsed, 0.2)
        self.assertFalse(worker.is_alive())

    def test_selection_replay_cache_is_bounded(self):
        store = history_routes.HistoryPipelineStore(
            history_session="test-session"
        )
        result = {
            "history_session": "test-session",
            "device_id": "device-1",
        }
        for index in range(history_routes.MAX_SELECTION_CACHE + 50):
            store._remember_selection(f"selection-{index}", result)

        self.assertEqual(
            len(store._selections),
            history_routes.MAX_SELECTION_CACHE,
        )


if __name__ == "__main__":
    unittest.main()
