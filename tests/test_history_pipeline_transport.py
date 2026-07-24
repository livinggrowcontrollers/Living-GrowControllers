import csv
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIRTUAL_HUB_DIR = PROJECT_ROOT / "tools" / "virtual_hub"
if str(VIRTUAL_HUB_DIR) not in sys.path:
    sys.path.insert(0, str(VIRTUAL_HUB_DIR))

from history_compressor import FIELD_NAMES, compress
from history_routes import (
    HISTORY_REFRESH_SECONDS,
    LIVE_HISTORY_HOURS,
    HistoryPipelineStore,
    create_history_blueprint,
)


class HistoryPipelineTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.csv_file = Path(self.temp_directory.name) / "history.csv"
        field_names = (
            "timestamp",
            "device_id",
            "device_name",
            *FIELD_NAMES,
        )
        with self.csv_file.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as target:
            writer = csv.DictWriter(target, fieldnames=field_names)
            writer.writeheader()
            for device_id, name, offset in (
                ("device-1", "Dashboard Device 1", 0),
                ("device-2", "Dashboard Device 2", 10),
            ):
                for index in range(12):
                    writer.writerow(
                        {
                            "timestamp": 100 + (index * 10),
                            "device_id": device_id,
                            "device_name": name,
                            "T_i": 20 + offset + index,
                            "H_i": 50 + offset + index,
                        }
                    )

        self.store = HistoryPipelineStore(
            csv_file=str(self.csv_file),
            history_session="test-session",
        )
        app = Flask(__name__)
        app.register_blueprint(
            create_history_blueprint(pipeline_store=self.store)
        )
        self.client = app.test_client()

    def _select(
        self,
        device_id="device-1",
        selection_id="selection-1",
        start=100,
        end=210,
        points=4,
        range_key=24,
    ):
        base = self.store.get_control_state()
        return self.client.get(
            "/history",
            query_string={
                "mode": "history",
                "from": start,
                "to": end,
                "points": points,
                "device_id": device_id,
                "range_key": range_key,
                "selection_id": selection_id,
                "base_revision": base["rev_history"],
                "base_session": base["history_session"],
            },
        )

    def _live_query(self, device_id, selection_id):
        base = self.store.get_control_state()
        return {
            "mode": "live",
            "device_id": device_id,
            "selection_id": selection_id,
            "base_revision": base["rev_history"],
            "base_session": base["history_session"],
        }

    def test_ack_is_control_only_and_header_precedes_device_log(self):
        response = self._select()

        self.assertEqual(response.status_code, 200)
        acknowledgement = response.get_json()
        self.assertEqual(acknowledgement["status"], "selected")
        self.assertEqual(acknowledgement["history_session"], "test-session")
        self.assertEqual(acknowledgement["rev_history"], 1)
        self.assertEqual(acknowledgement["selection_id"], "selection-1")
        self.assertEqual(acknowledgement["device_id"], "device-1")
        self.assertNotIn("devices", acknowledgement)
        self.assertNotIn("history", acknowledgement)

        pipeline = self.store.get_pipeline_payload()
        self.assertEqual(
            list(pipeline)[:2],
            ["history_session", "rev_history"],
        )
        device = pipeline["devices"]["device-1"]
        self.assertLess(
            list(device).index("history_selection"),
            list(device).index("history"),
        )
        selection = device["history_selection"]
        self.assertEqual(selection["range_key"], 24)
        self.assertEqual(selection["range_label"], "24h")
        self.assertEqual(selection["from"], 100.0)
        self.assertEqual(selection["to"], 210.0)
        self.assertEqual(selection["points"], 4)
        self.assertLessEqual(
            len(device["history"]["T_i"]["v"]),
            4,
        )

    def test_virtual_hub_refresh_interval_is_one_minute(self):
        self.assertEqual(HISTORY_REFRESH_SECONDS, 60.0)

    def test_selection_keeps_every_device_and_updates_only_exact_device_id(self):
        self._select(device_id="device-1", selection_id="first")
        before = self.store.get_pipeline_payload()
        device_2_before = deepcopy(before["devices"]["device-2"])

        response = self._select(
            device_id="device-1",
            selection_id="second",
            start=120,
            end=200,
            range_key=6,
        )

        self.assertEqual(response.status_code, 200)
        pipeline = self.store.get_pipeline_payload()
        self.assertEqual(set(pipeline["devices"]), {"device-1", "device-2"})
        self.assertEqual(
            pipeline["devices"]["device-1"]["history_selection"][
                "selection_id"
            ],
            "second",
        )
        self.assertEqual(pipeline["devices"]["device-2"], device_2_before)

    def test_same_selection_id_is_idempotent_and_last_new_click_wins(self):
        first = self._select(selection_id="click-a").get_json()
        second = self._select(
            selection_id="click-b",
            start=120,
            end=200,
            range_key=6,
        ).get_json()
        retry = self._select(selection_id="click-a").get_json()

        self.assertGreater(second["rev_history"], first["rev_history"])
        self.assertEqual(retry["rev_history"], first["rev_history"])
        active = self.store.get_pipeline_payload()["devices"]["device-1"][
            "history_selection"
        ]
        self.assertEqual(active["selection_id"], "click-b")
        self.assertEqual(active["range_key"], 6)

    def test_invalid_selection_does_not_replace_pipeline(self):
        self._select()
        selected = self.store.get_pipeline_payload()

        response = self._select(
            selection_id="invalid",
            start=210,
            end=100,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.get_pipeline_payload(), selected)

    def test_device_name_is_never_used_as_device_identity(self):
        response = self._select(
            device_id="Dashboard Device 1",
            selection_id="wrong-identity",
        )

        self.assertNotEqual(response.status_code, 200)
        self.assertIn("device_id", response.get_json()["error"])

    def test_csv_rows_are_grouped_only_by_exact_device_id(self):
        legacy_csv = (
            Path(self.temp_directory.name) / "strict-device-id.csv"
        )
        field_names = (
            "timestamp",
            "device_id",
            "device_name",
            *FIELD_NAMES,
        )
        with legacy_csv.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as target:
            writer = csv.DictWriter(target, fieldnames=field_names)
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": 100,
                    "device_id": "hub-local-uuid",
                    "device_name": "growmaster-d064",
                    "T_i": 20,
                }
            )
            writer.writerow(
                {
                    "timestamp": 200,
                    "device_id": "growmaster-d064",
                    "device_name": "Same visible name",
                    "T_i": 21,
                }
            )

        devices = compress(
            csv_file=str(legacy_csv),
            start_timestamp=100,
            end_timestamp=200,
            target_points=30,
        )

        self.assertEqual(
            list(devices),
            ["hub-local-uuid", "growmaster-d064"],
        )
        self.assertEqual(
            devices["hub-local-uuid"]["device_id"],
            "hub-local-uuid",
        )

    def test_live_mode_is_confirmed_for_one_device(self):
        self._select()
        with patch("history_routes.time.time", return_value=210):
            response = self.client.get(
                "/history",
                query_string=self._live_query(
                    "device-1",
                    "live-click",
                ),
            )

        self.assertEqual(response.status_code, 200)
        acknowledgement = response.get_json()
        self.assertEqual(acknowledgement["mode"], "live")
        self.assertEqual(acknowledgement["device_id"], "device-1")
        self.assertEqual(
            acknowledgement["log_range_key"],
            LIVE_HISTORY_HOURS,
        )
        pipeline = self.store.get_pipeline_payload()
        live_block = pipeline["devices"]["device-1"]
        live_selection = live_block["history_selection"]
        self.assertEqual(
            live_selection["mode"],
            "live",
        )
        self.assertIsNone(live_selection["range_key"])
        self.assertEqual(
            live_selection["log_range_key"],
            LIVE_HISTORY_HOURS,
        )
        self.assertEqual(live_selection["log_range_label"], "6h")
        self.assertEqual(
            live_selection["from"],
            210.0 - (LIVE_HISTORY_HOURS * 3600),
        )
        self.assertEqual(live_selection["to"], 210.0)
        self.assertEqual(live_selection["points"], 30)
        self.assertLessEqual(
            len(live_block["history"]["T_i"]["v"]),
            30,
        )
        self.assertEqual(
            pipeline["devices"]["device-2"]["history_selection"]["mode"],
            "history",
        )

    def test_minute_refresh_updates_log_without_changing_revision(self):
        self._select(
            device_id="device-1",
            selection_id="six-hour-mode",
            range_key=6,
        )
        before = self.store.get_pipeline_payload()
        before_target = before["devices"]["device-1"][
            "history_selection"
        ]

        with self.csv_file.open(
            "a",
            newline="",
            encoding="utf-8",
        ) as target:
            writer = csv.DictWriter(
                target,
                fieldnames=(
                    "timestamp",
                    "device_id",
                    "device_name",
                    *FIELD_NAMES,
                ),
            )
            writer.writerow(
                {
                    "timestamp": 250,
                    "device_id": "device-1",
                    "device_name": "Dashboard Device 1",
                    "T_i": 99,
                }
            )

        self.assertTrue(
            self.store.refresh_active_windows(now=300)
        )
        refreshed = self.store.get_pipeline_payload()
        refreshed_target = refreshed["devices"]["device-1"][
            "history_selection"
        ]

        self.assertEqual(
            refreshed["rev_history"],
            before["rev_history"],
        )
        self.assertEqual(
            refreshed_target["rev_history"],
            before_target["rev_history"],
        )
        self.assertEqual(
            refreshed_target["selection_id"],
            before_target["selection_id"],
        )
        self.assertEqual(refreshed_target["range_key"], 6)
        self.assertEqual(refreshed_target["to"], 300.0)
        self.assertGreater(
            refreshed["history_generated_at"],
            before["history_generated_at"],
        )
        self.assertEqual(
            refreshed["devices"]["device-1"]["history"]["T_i"]["t"][-1],
            250.0,
        )
        self.assertEqual(
            refreshed["devices"]["device-1"]["history"]["T_i"]["v"][-1],
            99.0,
        )

    def test_custom_window_is_not_moved_by_minute_refresh(self):
        self._select(
            selection_id="fixed-custom",
            range_key="custom",
        )
        before = self.store.get_pipeline_payload()

        self.assertFalse(
            self.store.refresh_active_windows(now=300)
        )
        self.assertEqual(self.store.get_pipeline_payload(), before)

    def test_live_six_hour_log_refreshes_without_changing_revision(self):
        self._select()
        with patch("history_routes.time.time", return_value=210):
            self.client.get(
                "/history",
                query_string=self._live_query(
                    "device-1",
                    "live-click",
                ),
            )
        before = self.store.get_pipeline_payload()
        before_live = before["devices"]["device-1"]
        before_target = before_live["history_selection"]

        with self.csv_file.open(
            "a",
            newline="",
            encoding="utf-8",
        ) as target:
            writer = csv.DictWriter(
                target,
                fieldnames=(
                    "timestamp",
                    "device_id",
                    "device_name",
                    *FIELD_NAMES,
                ),
            )
            writer.writerow(
                {
                    "timestamp": 250,
                    "device_id": "device-1",
                    "device_name": "Dashboard Device 1",
                    "T_i": 99,
                }
            )
        self.assertTrue(
            self.store.refresh_active_windows(now=270)
        )
        refreshed = self.store.get_pipeline_payload()
        refreshed_live = refreshed["devices"]["device-1"]
        refreshed_target = refreshed_live["history_selection"]

        self.assertEqual(
            refreshed["rev_history"],
            before["rev_history"],
        )
        self.assertEqual(
            refreshed_target["rev_history"],
            before_target["rev_history"],
        )
        self.assertEqual(
            refreshed_target["selection_id"],
            before_target["selection_id"],
        )
        self.assertEqual(refreshed_target["mode"], "live")
        self.assertEqual(
            refreshed_target["log_range_key"],
            LIVE_HISTORY_HOURS,
        )
        self.assertEqual(
            refreshed_target["from"] - before_target["from"],
            60.0,
        )
        self.assertEqual(
            refreshed_target["to"] - before_target["to"],
            60.0,
        )
        self.assertGreater(
            refreshed_live["history_generated_at"],
            before_live["history_generated_at"],
        )
        self.assertEqual(
            refreshed_live["history"]["T_i"]["t"][-1],
            250.0,
        )
        self.assertEqual(
            refreshed_live["history"]["T_i"]["v"][-1],
            99.0,
        )

    def test_stale_base_revision_is_rejected_without_replacing_pipeline(self):
        first = self._select(selection_id="first")
        self.assertEqual(first.status_code, 200)
        selected = self.store.get_pipeline_payload()

        response = self.client.get(
            "/history",
            query_string={
                "mode": "history",
                "from": 120,
                "to": 200,
                "points": 4,
                "device_id": "device-1",
                "range_key": 6,
                "selection_id": "stale-dashboard",
                "base_revision": 0,
                "base_session": "test-session",
            },
        )

        self.assertEqual(response.status_code, 409)
        conflict = response.get_json()
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(conflict["rev_history"], 1)
        self.assertEqual(self.store.get_pipeline_payload(), selected)


if __name__ == "__main__":
    unittest.main()
