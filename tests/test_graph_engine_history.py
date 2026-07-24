import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dashboard_gui.gsm_engines.data_flow_engine import DataFlowEngine
from dashboard_gui.gsm_engines.graph_engine import GraphEngine
from dashboard_gui.gsm_engines.graph_history_engine import (
    GraphHistoryEngine,
)


class FakeGsm:
    def __init__(self):
        self.active_device_id = "dev-1"

    def get_unit(self, _key):
        return "°C"

    def get_active_device_id(self):
        return self.active_device_id


def history_device(
    device_id,
    revision,
    selection_id,
    start=100,
    end=200,
    points=30,
    range_key="custom",
    mode="history",
    history=None,
    generated_at=None,
):
    selection = {
        "rev_history": revision,
        "selection_id": selection_id,
        "mode": mode,
        "range_key": range_key if mode == "history" else None,
        "range_label": (
            "Benutzerdefiniert"
            if range_key == "custom"
            else f"{range_key}h"
        ) if mode == "history" else "Live",
    }
    if mode == "history":
        selection.update(
            {
                "from": start,
                "to": end,
                "points": points,
            }
        )
    elif mode == "live":
        selection.update(
            {
                "log_range_key": 6,
                "log_range_label": "6h",
                "from": start,
                "to": end,
                "points": points,
            }
        )
    return {
        "device_id": device_id,
        "name": device_id,
        "history_selection": selection,
        "history_generated_at": (
            float(revision)
            if generated_at is None
            else float(generated_at)
        ),
        "total_raw_points": 0,
        "history": history or {},
    }


def history_payload(
    revision,
    devices,
    session="hub-session",
    generated_at=None,
):
    return {
        "history_session": session,
        "rev_history": revision,
        "history_generated_at": (
            float(revision)
            if generated_at is None
            else float(generated_at)
        ),
        "devices": devices,
    }


class GraphEngineHistoryTests(unittest.TestCase):
    def setUp(self):
        self.config_patch = patch.multiple(
            "dashboard_gui.gsm_engines.graph_engine.config",
            get_tile_graph_window=Mock(return_value=100),
            get_graph_refresh_interval=Mock(return_value=1.0),
            get_refresh_interval=Mock(return_value=0.1),
            get_graph_smoothing_factor=Mock(return_value=0.0),
            get_graph_resolution=Mock(return_value=100.0),
            is_developer_mode=Mock(return_value=False),
            _init=Mock(
                return_value={
                    "devices": {
                        "dev-1": {"device_id": "dev-1"},
                        "dev-2": {"device_id": "dev-2"},
                        "growmaster-d064": {
                            "device_id": "growmaster-d064"
                        },
                    }
                }
            ),
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.gsm = FakeGsm()
        self.live_engine = GraphEngine(self.gsm)
        self.engine = GraphHistoryEngine(self.gsm)

    def test_live_snapshot_keeps_live_trend(self):
        key = "dev_webserver_temp_in"
        self.live_engine.graph_buffers[key].extend([20.0, 21.0, 22.0])
        self.live_engine.global_trends[key] = 1

        snapshot = self.live_engine.get_live_snapshot(key)

        self.assertEqual(snapshot.mode, "live")
        self.assertEqual(snapshot.trend_icon, "\uf062")
        self.assertEqual(snapshot.last_value, 22.0)
        self.assertEqual(len(snapshot.points), 3)

    def test_live_processing_pipeline_still_builds_snapshot(self):
        key = "dev_webserver_temp_in"
        self.live_engine.refresh_config(
            graph_refresh_interval=0.1,
            base_refresh_interval=0.1,
        )

        for value in (20, 21, 22, 23, 24, 25):
            self.live_engine.process_new_value(key, value)

        snapshot = self.live_engine.get_live_snapshot(key)
        self.assertEqual(snapshot.values, (20.0, 21.0, 22.0, 23.0, 24.0, 25.0))
        self.assertEqual(snapshot.last_value, 25.0)
        self.assertEqual(snapshot.trend_icon, "\uf062")

    def test_all_history_presets_keep_exact_request_duration(self):
        now = 2_000_000_000
        presets = {
            6: "6h",
            24: "24h",
            48: "48h",
            7 * 24: "7d",
            30 * 24: "30d",
            365 * 24: "365d",
        }

        for hours, label in presets.items():
            with self.subTest(label=label):
                history_window = self.engine.create_history_window(
                    hours,
                    now=now,
                )
                self.assertEqual(history_window.label, label)
                self.assertEqual(history_window.end_timestamp, now)
                self.assertEqual(
                    history_window.end_timestamp
                    - history_window.start_timestamp,
                    hours * 3600,
                )

    def test_graph_range_is_shared_and_defaults_to_live(self):
        history_window, revision = self.engine.get_graph_range_state()
        self.assertIsNone(history_window)

        selected = self.engine.create_history_window(24, now=10_000)
        selected_revision = self.engine.set_active_history_window(selected)
        self.assertGreater(selected_revision, revision)
        self.assertEqual(
            self.engine.get_graph_range_state(),
            (selected, selected_revision),
        )
        self.assertEqual(selected.range_key, 24)

        unchanged_revision = self.engine.set_active_history_window(selected)
        self.assertEqual(unchanged_revision, selected_revision)

        live_revision = self.engine.set_active_history_window(None)
        self.assertGreater(live_revision, selected_revision)
        self.assertEqual(
            self.engine.get_graph_range_state(),
            (None, live_revision),
        )

    def test_fullscreen_selection_waits_for_central_pipeline_block(self):
        self.assertTrue(
            self.engine.ingest_history_pipeline(
                history_payload(
                    1,
                    {
                        "dev-1": history_device(
                            "dev-1",
                            1,
                            "hub-default",
                            start=0,
                            end=50,
                        )
                    },
                )
            )
        )
        history_window = self.engine.create_history_window(
            "custom",
            start_timestamp=100,
            end_timestamp=200,
        )
        pipeline_payload = history_payload(
            2,
            {
                "dev-1": history_device(
                    "dev-1",
                    2,
                    "filled-after-request",
                    history={
                        "T_i": {
                            "t": [100, 150, 200],
                            "v": [5, 1, 9],
                        },
                        "H_i": {
                            "t": [100, 150, 200],
                            "v": [50, 55, 60],
                        }
                    },
                )
            },
        )
        result = self.engine.select_history_window(
            device_id="dev-1",
            history_window=history_window,
            selection_id="filled-after-request",
            base_revision=1,
            base_session="hub-session",
        )

        self.assertEqual(result.status, "loading")
        self.assertEqual(result.target_revision, 2)
        self.assertEqual(
            self.engine.get_history_selection_state(result.key),
            ("loading", None),
        )
        self.assertTrue(
            self.engine.complete_history_command(
                "filled-after-request",
            )
        )

        self.assertTrue(
            self.engine.ingest_history_pipeline(pipeline_payload)
        )
        self.assertEqual(
            self.engine.get_history_selection_state(result.key),
            ("loaded", None),
        )

        snapshot = self.engine.get_history_snapshot(
            pipeline_key=result.key,
            tile_id="temp_in",
            range_label="Benutzerdefiniert",
        )
        self.assertEqual(snapshot.mode, "history")
        self.assertEqual(snapshot.trend_icon, "")
        self.assertEqual(
            snapshot.points,
            ((0.0, 5.0), (1.0, 1.0), (2.0, 9.0)),
        )
        self.assertEqual(snapshot.xmax, 2.0)
        self.assertEqual(snapshot.stats.minimum, 1.0)
        self.assertEqual(snapshot.stats.maximum, 9.0)
        self.assertEqual(
            {point.role for point in snapshot.notable_points},
            {"minimum", "maximum"},
        )

        humidity_snapshot = self.engine.get_history_snapshot(
            pipeline_key=result.key,
            tile_id="hum_in",
            range_label="Benutzerdefiniert",
        )
        self.assertEqual(humidity_snapshot.values, (50.0, 55.0, 60.0))
        self.assertEqual(humidity_snapshot.points[-1], (2.0, 60.0))
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-1",
                "temp_in",
            ).values,
            (5.0, 1.0, 9.0),
        )
        self.assertEqual(
            self.engine.get_history_pipeline_key("dev-1"),
            result.key,
        )
        self.assertIsNone(
            self.engine.get_history_pipeline_key(
                "another-device"
            )
        )
        self.assertIsNone(
            self.engine.get_cached_history_snapshot(
                "another-device",
                "temp_in",
            )
        )

        selected = self.engine.inspect_history_point(
            pipeline_key=result.key,
            tile_id="temp_in",
            graph_x=1.1,
        )
        self.assertEqual(selected.value, 1.0)
        self.assertEqual(selected.timestamp, 150.0)
        self.assertEqual(selected.role, "selected")
        self.assertEqual(
            self.engine.consume_history_confirmation(
                "filled-after-request"
            ),
            {
                "selection_id": "filled-after-request",
                "mode": "history",
                "rev_history": 2,
            },
        )
        self.assertIsNone(
            self.engine.consume_history_confirmation(
                "filled-after-request"
            )
        )

    def test_history_axis_uses_actual_log_coverage(self):
        requested_start = 100
        requested_end = requested_start + (6 * 3600)
        actual_start = requested_start + (2 * 3600)
        actual_end = requested_start + (4 * 3600)
        payload = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "six-hour-request",
                    start=requested_start,
                    end=requested_end,
                    range_key=6,
                    history={
                        "T_i": {
                            "t": [actual_start, actual_end],
                            "v": [20, 21],
                        }
                    },
                )
            },
        )

        self.assertTrue(self.engine.ingest_history_pipeline(payload))
        snapshot = self.engine.get_history_snapshot(
            pipeline_key=self.engine.get_history_pipeline_key("dev-1"),
            tile_id="temp_in",
            label_count=5,
            range_label="6h",
        )

        self.assertEqual(
            snapshot.labels[0],
            time.strftime(
                "%H:%M",
                time.localtime(actual_start),
            ),
        )
        self.assertEqual(
            snapshot.labels[-1],
            time.strftime(
                "%H:%M",
                time.localtime(actual_end),
            ),
        )
        self.assertNotEqual(
            snapshot.labels[0],
            time.strftime(
                "%H:%M",
                time.localtime(requested_start),
            ),
        )

    def test_missing_hub_base_is_a_failed_fullscreen_selection(self):
        history_window = self.engine.create_history_window(
            6,
            now=10_000,
        )

        result = self.engine.select_history_window(
            device_id="dev-1",
            history_window=history_window,
            selection_id="no-base",
            base_revision=-1,
            base_session="",
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("Basisrevision", result.error)

    def test_late_response_cannot_replace_newer_window(self):
        self.assertTrue(
            self.engine.ingest_history_pipeline(
                history_payload(
                    1,
                    {
                        "dev-1": history_device(
                            "dev-1",
                            1,
                            "hub-default",
                        )
                    },
                )
            )
        )
        old_window = self.engine.create_history_window(
            "custom",
            start_timestamp=100,
            end_timestamp=200,
        )
        new_window = self.engine.create_history_window(
            "custom",
            start_timestamp=300,
            end_timestamp=400,
        )
        old_result = self.engine.select_history_window(
            "dev-1",
            old_window,
            selection_id="old-selection",
            base_revision=1,
            base_session="hub-session",
        )
        new_result = self.engine.select_history_window(
            "dev-1",
            new_window,
            selection_id="new-selection",
            base_revision=1,
            base_session="hub-session",
        )
        self.assertFalse(
            self.engine.complete_history_command(
                "old-selection",
            )
        )
        self.assertTrue(
            self.engine.complete_history_command(
                "new-selection",
            )
        )

        self.assertEqual(
            self.engine.get_history_selection_state(new_result.key),
            ("loading", None),
        )
        self.engine.ingest_history_pipeline(
            history_payload(
                2,
                {
                    "dev-1": history_device(
                        "dev-1",
                        2,
                        "new-selection",
                        start=300,
                        end=400,
                        history={
                            "T_i": {
                                "t": [300, 400],
                                "v": [3, 4],
                            }
                        },
                    )
                },
            )
        )
        self.assertEqual(
            self.engine.get_history_selection_state(new_result.key),
            ("loaded", None),
        )
        self.assertEqual(
            self.engine.get_history_selection_state(old_result.key),
            ("idle", None),
        )

    def test_one_pipeline_block_can_serve_multiple_devices(self):
        payload = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "initial-dev-1",
                    history={
                        "T_i": {"t": [100, 200], "v": [20, 21]}
                    },
                ),
                "dev-2": history_device(
                    "dev-2",
                    1,
                    "initial-dev-2",
                    history={
                        "T_i": {"t": [100, 200], "v": [25, 26]}
                    },
                ),
            },
        )

        self.assertTrue(self.engine.ingest_history_pipeline(payload))
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-1",
                "temp_in",
            ).values,
            (20.0, 21.0),
        )
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-2",
                "temp_in",
            ).values,
            (25.0, 26.0),
        )

    def test_two_dashboards_follow_latest_hub_target_for_same_device(self):
        second_gsm = FakeGsm()
        second_engine = GraphHistoryEngine(second_gsm)
        first_target = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "dashboard-1-click",
                    start=100,
                    end=200,
                    range_key=6,
                )
            },
        )
        second_target = history_payload(
            2,
            {
                "dev-1": history_device(
                    "dev-1",
                    2,
                    "dashboard-2-click",
                    start=300,
                    end=400,
                    range_key=24,
                )
            },
        )

        for engine in (self.engine, second_engine):
            self.assertTrue(engine.ingest_history_pipeline(first_target))
            window, _revision = engine.get_graph_range_state()
            self.assertEqual(window.range_key, 6)

        for engine in (self.engine, second_engine):
            self.assertTrue(engine.ingest_history_pipeline(second_target))
            window, _revision = engine.get_graph_range_state()
            self.assertEqual(window.range_key, 24)
            self.assertEqual(window.start_timestamp, 300)
            self.assertEqual(window.end_timestamp, 400)

        for engine in (self.engine, second_engine):
            self.assertFalse(engine.ingest_history_pipeline(first_target))
            window, _revision = engine.get_graph_range_state()
            self.assertEqual(window.range_key, 24)

    def test_same_revision_accepts_newer_log_generation_only(self):
        first = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "six-hour-mode",
                    start=100,
                    end=200,
                    range_key=6,
                    generated_at=100,
                    history={
                        "T_i": {
                            "t": [100, 200],
                            "v": [20, 21],
                        }
                    },
                )
            },
            generated_at=100,
        )
        refreshed = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "six-hour-mode",
                    start=160,
                    end=260,
                    range_key=6,
                    generated_at=160,
                    history={
                        "T_i": {
                            "t": [160, 260],
                            "v": [21, 22],
                        }
                    },
                )
            },
            generated_at=160,
        )
        collision = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "different-selection",
                    start=200,
                    end=300,
                    range_key=24,
                    generated_at=200,
                )
            },
            generated_at=200,
        )

        self.assertTrue(self.engine.ingest_history_pipeline(first))
        first_range_revision = self.engine.get_graph_range_state()[1]
        self.assertTrue(self.engine.ingest_history_pipeline(refreshed))
        window, refreshed_range_revision = (
            self.engine.get_graph_range_state()
        )
        self.assertEqual(window.range_key, 6)
        self.assertEqual(window.start_timestamp, 160)
        self.assertEqual(window.end_timestamp, 260)
        self.assertGreater(
            refreshed_range_revision,
            first_range_revision,
        )
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-1",
                "temp_in",
            ).values,
            (21.0, 22.0),
        )
        self.assertFalse(self.engine.ingest_history_pipeline(first))
        self.assertFalse(self.engine.ingest_history_pipeline(collision))

    def test_new_hub_session_accepts_revision_one_and_rejects_old_session(self):
        old_session = history_payload(
            99,
            {
                "dev-1": history_device(
                    "dev-1",
                    99,
                    "old-session",
                    range_key=6,
                )
            },
            session="old-hub-session",
        )
        restarted_hub = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "new-session",
                    start=300,
                    end=400,
                    range_key=24,
                )
            },
            session="new-hub-session",
        )

        self.assertTrue(self.engine.ingest_history_pipeline(old_session))
        self.assertTrue(self.engine.ingest_history_pipeline(restarted_hub))
        self.assertFalse(self.engine.ingest_history_pipeline(old_session))
        window, _revision = self.engine.get_graph_range_state()
        self.assertEqual(window.range_key, 24)

    def test_hub_confirmed_live_mode_switches_following_dashboard_to_live(self):
        selected = history_payload(
            1,
            {
                "dev-1": history_device(
                    "dev-1",
                    1,
                    "history-click",
                    range_key=6,
                )
            },
        )
        live = history_payload(
            2,
            {
                "dev-1": history_device(
                    "dev-1",
                    2,
                    "live-click",
                    mode="live",
                    history={
                        "T_i": {
                            "t": [100, 150, 200],
                            "v": [20, 21, 22],
                        }
                    },
                )
            },
        )

        self.assertTrue(self.engine.ingest_history_pipeline(selected))
        self.assertIsNotNone(self.engine.get_graph_range_state()[0])
        self.assertTrue(self.engine.ingest_history_pipeline(live))
        self.assertIsNone(self.engine.get_graph_range_state()[0])
        self.assertIsNone(
            self.engine.get_history_pipeline_key("dev-1")
        )
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-1",
                "temp_in",
            ).values,
            (20.0, 21.0, 22.0),
        )

    def test_live_log_refresh_keeps_mode_revision_and_selection(self):
        first = history_payload(
            2,
            {
                "dev-1": history_device(
                    "dev-1",
                    2,
                    "live-click",
                    start=100,
                    end=200,
                    mode="live",
                    generated_at=100,
                    history={
                        "T_i": {
                            "t": [100, 200],
                            "v": [20, 21],
                        }
                    },
                )
            },
            generated_at=100,
        )
        refreshed = history_payload(
            2,
            {
                "dev-1": history_device(
                    "dev-1",
                    2,
                    "live-click",
                    start=160,
                    end=260,
                    mode="live",
                    generated_at=160,
                    history={
                        "T_i": {
                            "t": [160, 260],
                            "v": [21, 22],
                        }
                    },
                )
            },
            generated_at=160,
        )

        self.assertTrue(self.engine.ingest_history_pipeline(first))
        self.assertIsNone(self.engine.get_graph_range_state()[0])
        self.assertTrue(self.engine.ingest_history_pipeline(refreshed))
        self.assertIsNone(self.engine.get_graph_range_state()[0])
        self.assertEqual(self.engine._history_revision, 2)
        self.assertEqual(
            self.engine.get_cached_history_snapshot(
                "dev-1",
                "temp_in",
            ).values,
            (21.0, 22.0),
        )
        self.assertFalse(self.engine.ingest_history_pipeline(first))

    def test_pipeline_device_key_must_equal_exact_device_id(self):
        malformed = history_payload(
            1,
            {
                "hub-local-uuid": history_device(
                    "growmaster-d064",
                    1,
                    "malformed",
                )
            },
        )

        self.assertTrue(self.engine.ingest_history_pipeline(malformed))
        self.assertIsNone(
            self.engine.get_history_pipeline_key("growmaster-d064")
        )

    def test_explicit_device_id_wins_over_local_config_uuid_log_block(self):
        local_uuid = "android-local-uuid"
        source_device_id = "growmaster-d064"
        self.gsm.active_device_id = local_uuid
        payload = history_payload(
            2,
            {
                local_uuid: history_device(
                    local_uuid,
                    1,
                    "legacy-local-uuid",
                    range_key=6,
                ),
                source_device_id: history_device(
                    source_device_id,
                    2,
                    "confirmed-device-id",
                    start=300,
                    end=400,
                    range_key=24,
                ),
            },
        )
        android_config = {
            "devices": {
                local_uuid: {
                    "device_id": source_device_id,
                    "name": source_device_id,
                }
            }
        }

        with patch(
            "dashboard_gui.gsm_engines.graph_history_engine.config._init",
            return_value=android_config,
        ):
            self.assertTrue(self.engine.ingest_history_pipeline(payload))
            window, _revision = self.engine.get_graph_range_state()
            self.assertEqual(window.range_key, 24)
            self.assertEqual(
                self.engine.get_history_pipeline_key(local_uuid),
                (local_uuid, 300.0, 400.0, 30),
            )

    def test_android_uuid_resolves_to_stable_pipeline_device(self):
        android_device_id = "android-local-uuid"
        source_device_id = "growmaster-d064"
        history_window = self.engine.create_history_window(
            "custom",
            start_timestamp=100,
            end_timestamp=200,
        )
        android_config = {
            "devices": {
                android_device_id: {
                    "device_id": source_device_id,
                    "hostname": source_device_id,
                }
            }
        }

        with patch(
            "dashboard_gui.gsm_engines.graph_history_engine.config._init",
            return_value=android_config,
        ):
            self.assertTrue(
                self.engine.ingest_history_pipeline(
                    history_payload(
                        1,
                        {
                            source_device_id: history_device(
                                source_device_id,
                                1,
                                "hub-default",
                                start=0,
                                end=50,
                            )
                        },
                    )
                )
            )
            result = self.engine.select_history_window(
                device_id=android_device_id,
                history_window=history_window,
                selection_id="android-selection",
                base_revision=1,
                base_session="hub-session",
            )
            self.assertTrue(
                self.engine.complete_history_command(
                    "android-selection",
                )
            )

            self.engine.ingest_history_pipeline(
                history_payload(
                    2,
                    {
                        source_device_id: history_device(
                            source_device_id,
                            2,
                            "android-selection",
                            history={
                                "T_i": {
                                    "t": [100, 200],
                                    "v": [20, 21],
                                }
                            },
                        )
                    },
                )
            )

            self.assertEqual(
                self.engine.get_history_selection_state(result.key),
                ("loaded", None),
            )
            self.assertEqual(
                self.engine.get_cached_history_snapshot(
                    android_device_id,
                    "temp_in",
                ).values,
                (20.0, 21.0),
            )

    def test_missing_android_device_block_is_not_reported_as_loaded(self):
        android_device_id = "android-local-uuid"
        source_device_id = "growmaster-d064"
        android_config = {
            "devices": {
                android_device_id: {
                    "device_id": source_device_id,
                    "hostname": source_device_id,
                }
            }
        }
        payload = history_payload(1, {})

        with patch(
            "dashboard_gui.gsm_engines.graph_history_engine.config._init",
            return_value=android_config,
        ):
            self.assertTrue(self.engine.ingest_history_pipeline(payload))
            self.assertIsNone(
                self.engine.get_history_pipeline_key(android_device_id)
            )

    def test_data_flow_ingests_history_even_if_live_web_is_stale(self):
        history = {
            "from": 100,
            "to": 200,
            "points": 30,
            "devices": {},
        }
        gsm = Mock()
        gsm.running = True
        gsm.get_active_device_id.return_value = None
        engine = DataFlowEngine(gsm)

        with patch(
            "dashboard_gui.gsm_engines.data_flow_engine.BUFFER"
        ) as buffer:
            buffer.get.return_value = [
                {
                    "device_id": "android-local-uuid",
                    "webserver": {
                        "alive": False,
                        "history": history,
                    },
                }
            ]
            engine.process_cycle()

        gsm.graph_history_engine.ingest_history_pipeline.assert_called_once_with(
            history
        )
        gsm.metrics_engine.process_metrics.assert_not_called()

    def test_fullscreen_contains_no_history_transport_engine(self):
        project_root = Path(__file__).resolve().parents[1]
        fullscreen_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "fullscreen_content"
            / "fullscreen_view.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "import requests",
            "import threading",
            "HISTORY_KEY_MAP",
            "HISTORY_SELECTION_TIMEOUT",
            "self._history_data",
            "_normalize_history_endpoint",
        ):
            self.assertNotIn(forbidden, fullscreen_source)

        self.assertNotIn("self._history_window =", fullscreen_source)
        self.assertIn("get_graph_range_state()", fullscreen_source)
        self.assertIn("set_active_history_window(", fullscreen_source)
        self.assertIn(
            "GLOBAL_STATE.send_history_command(",
            fullscreen_source,
        )
        self.assertNotIn("select_history_window(", fullscreen_source)
        self.assertNotIn("select_live_mode(", fullscreen_source)
        self.assertNotIn("remember_history_endpoint(", fullscreen_source)
        self.assertIn("RevisionSession()", fullscreen_source)
        self.assertIn(
            "consume_history_confirmation(",
            fullscreen_source,
        )
        self.assertIn(
            "GrowCommandStatusPopup.show(",
            fullscreen_source,
        )
        self.assertEqual(
            fullscreen_source.count(
                "_select_history_pipeline(\n"
                "            history_window=history_window,\n"
                "            force=True,\n"
                "        )"
            ),
            2,
        )
        passive_loader = fullscreen_source.split(
            "    def _load_history_data(self):",
            1,
        )[1].split(
            "    def _current_device_id(self):",
            1,
        )[0]
        self.assertNotIn(
            "select_history_window(",
            passive_loader,
        )
        self.assertNotIn(
            "_select_history_pipeline(",
            passive_loader,
        )

    def test_fullscreen_command_overlay_has_priority_over_history_touch(self):
        project_root = Path(__file__).resolve().parents[1]
        fullscreen_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "fullscreen_content"
            / "fullscreen_view.py"
        ).read_text(encoding="utf-8")
        history_touch_source = fullscreen_source.split(
            "    def _is_history_plot_touch(self, touch):",
            1,
        )[1].split(
            "    def _command_overlay_is_active(self):",
            1,
        )[0]
        overlay_guard_source = fullscreen_source.split(
            "    def _command_overlay_is_active(self):",
            1,
        )[1].split(
            "    def _inspect_history_touch(self, touch):",
            1,
        )[0]

        self.assertIn(
            "if self._command_overlay_is_active():",
            history_touch_source,
        )
        self.assertIn(
            "return False",
            history_touch_source,
        )
        self.assertIn(
            '"overlay_manager"',
            overlay_guard_source,
        )
        self.assertIn(
            '"active_overlay"',
            overlay_guard_source,
        )
        self.assertIn(
            "overlay.parent is self",
            overlay_guard_source,
        )

    def test_fullscreen_keeps_stable_line_plot_instances(self):
        project_root = Path(__file__).resolve().parents[1]
        panel_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "fullscreen_content"
            / "fullscreen_main_panel.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("PointPlot", panel_source)
        self.assertNotIn("remove_plot", panel_source)
        self.assertEqual(panel_source.count("self.graph.add_plot("), 2)

    def test_dashboard_consumes_shared_history_snapshots(self):
        project_root = Path(__file__).resolve().parents[1]
        dashboard_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "dashboard_content"
            / "dashboard_main_panel.py"
        ).read_text(encoding="utf-8")
        tile_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "dashboard_content"
            / "chart_tile.py"
        ).read_text(encoding="utf-8")

        self.assertIn("get_graph_range_state()", dashboard_source)
        self.assertIn("get_history_snapshot(", dashboard_source)
        self.assertIn("render_history_snapshot(", dashboard_source)
        self.assertIn("get_history_pipeline_key(", dashboard_source)
        for forbidden in (
            "select_history_window(",
            "request_history(",
            "remember_history_endpoint(",
        ):
            self.assertNotIn(forbidden, dashboard_source)
        self.assertIn('trend=""', tile_source)

    def test_grow_overview_sensor_tile_keeps_live_values_and_trends(self):
        project_root = Path(__file__).resolve().parents[1]
        sensor_tile_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "grow_overview_content"
            / "sensor_summary_tile.py"
        ).read_text(encoding="utf-8")

        self.assertIn("SPARK_POINT_LIMIT = 8", sensor_tile_source)
        self.assertIn("MetricRegistry.get(", sensor_tile_source)
        self.assertIn(
            'MetricRegistry.presentation("tile")',
            sensor_tile_source,
        )
        self.assertIn(
            '"color_name": self._hex_color(',
            sensor_tile_source,
        )
        formatter_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "formatters.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'color_name = style.get("color_name", color_sub)',
            formatter_source,
        )
        self.assertIn(
            "get_cached_history_snapshot(",
            sensor_tile_source,
        )
        self.assertIn(
            "GLOBAL_STATE.get_trend_icon(",
            sensor_tile_source,
        )
        self.assertIn(
            'reading.get("value")',
            sensor_tile_source,
        )
        self.assertIn(
            "value=value if value is not None else",
            sensor_tile_source,
        )
        self.assertNotIn(
            "snapshot.last_value",
            sensor_tile_source,
        )
        self.assertIn(
            'orientation="vertical",',
            sensor_tile_source,
        )
        self.assertIn(
            "padding=dp_scaled(6)",
            sensor_tile_source,
        )
        self.assertIn(
            "size_hint=(1, 1)",
            sensor_tile_source,
        )
        self.assertIn(
            "size_hint=(0.35, 1)",
            sensor_tile_source,
        )
        self.assertNotIn("requests.", sensor_tile_source)
        self.assertNotIn("request_history(", sensor_tile_source)
        self.assertNotIn("Mesh(", sensor_tile_source)
        self.assertNotIn("Ellipse(", sensor_tile_source)
        self.assertNotIn("kivy_garden.graph", sensor_tile_source)
        self.assertIn(
            "def reset_history(self, device_id=None, channel=None):",
            sensor_tile_source,
        )

        overview_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "grow_overview_content"
            / "grow_overview_screen.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "select_history_window(",
            "request_history(",
            "remember_history_endpoint(",
            "SUMMARY_HISTORY_POINTS",
            "SUMMARY_HISTORY_HOURS",
            "_ensure_summary_history",
        ):
            self.assertNotIn(forbidden, overview_source)
        self.assertIn(
            "if mac != self._active_summary_device_id:",
            overview_source,
        )
        self.assertIn("tile.reset_history(", overview_source)

    def test_history_data_uses_existing_web_pipeline(self):
        project_root = Path(__file__).resolve().parents[1]
        virtual_hub_source = (
            project_root
            / "tools"
            / "virtual_hub"
            / "esp_virtual_hub.py"
        ).read_text(encoding="utf-8")
        decoder_source = (
            project_root
            / "decoder.py"
        ).read_text(encoding="utf-8")
        data_flow_source = (
            project_root
            / "dashboard_gui"
            / "gsm_engines"
            / "data_flow_engine.py"
        ).read_text(encoding="utf-8")
        graph_history_engine_source = (
            project_root
            / "dashboard_gui"
            / "gsm_engines"
            / "graph_history_engine.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'esp_payload["history"] =',
            virtual_hub_source,
        )
        self.assertIn(
            "history_pipeline_store.start_auto_refresh()",
            virtual_hub_source,
        )
        self.assertIn(
            "history_pipeline_store.stop_auto_refresh()",
            virtual_hub_source,
        )
        self.assertNotIn(
            'esp_payload.pop("history"',
            virtual_hub_source,
        )
        self.assertIn(
            '"history": current_web.get("history")',
            decoder_source,
        )
        self.assertIn(
            "ingest_history_pipeline(",
            data_flow_source,
        )
        self.assertNotIn("response.json()", graph_history_engine_source)
        self.assertNotIn("requests.", graph_history_engine_source)
        self.assertNotIn("history_endpoint", graph_history_engine_source)
        self.assertNotIn("history_endpoint", virtual_hub_source)
        self.assertNotIn("history_endpoint", decoder_source)
        self.assertNotIn(
            'acknowledgement.get("devices")',
            graph_history_engine_source,
        )

    def test_shared_mesh_keeps_chart_tile_geometry(self):
        project_root = Path(__file__).resolve().parents[1]
        mesh_source = (
            project_root
            / "dashboard_gui"
            / "ui"
            / "common"
            / "graph_chart_content"
            / "graph_mesh.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "graph.pos[0] + graph.view_pos[0]",
            mesh_source,
        )
        self.assertIn(
            "graph.pos[1] + graph.view_pos[1]",
            mesh_source,
        )
        self.assertIn("g_size = graph.view_size", mesh_source)
        self.assertNotIn("round(", mesh_source)
        self.assertNotIn("dp_scaled", mesh_source)


if __name__ == "__main__":
    unittest.main()
