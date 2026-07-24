import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dashboard_gui.gsm_engines.graph_engine import (
    HistorySelectionResult,
    HistoryWindow,
)
from dashboard_gui.gsm_engines.overlay_command_engine import (
    OverlayCommandEngine,
)
from web_client import WebClientThread


class FakeHistoryGraphEngine:
    HISTORY_TARGET_POINTS = 30

    def __init__(self):
        self.selection_calls = []
        self.completions = []

    def get_history_control_state(self):
        return {
            "history_session": "hub-session",
            "rev_history": 7,
        }

    def select_history_window(self, **kwargs):
        self.selection_calls.append(kwargs)
        window = kwargs["history_window"]
        return HistorySelectionResult(
            key=(
                kwargs["device_id"],
                window.start_timestamp,
                window.end_timestamp,
                kwargs["target_points"],
            ),
            status="loading",
            selection_id=kwargs["selection_id"],
            target_revision=8,
        )

    def select_live_mode(self, **kwargs):
        self.selection_calls.append(kwargs)
        return HistorySelectionResult(
            key=(kwargs["device_id"], "live"),
            status="loading",
            selection_id=kwargs["selection_id"],
            target_revision=8,
        )

    def complete_history_command(
        self,
        selection_id,
        error=None,
    ):
        self.completions.append(
            (selection_id, error)
        )
        return True


class HistoryCommandRoutingTests(unittest.TestCase):
    def test_command_engine_owns_history_target_and_exact_device_id(self):
        graph_engine = FakeHistoryGraphEngine()
        gsm = Mock()
        gsm.graph_engine = graph_engine
        engine = OverlayCommandEngine(gsm)
        sent = {}
        completed = []
        window = HistoryWindow(
            start_timestamp=100.0,
            end_timestamp=200.0,
            label="6h",
            range_key=6,
        )

        def capture_send(mac, params, on_done):
            sent.update(
                {
                    "mac": mac,
                    "params": params,
                    "on_done": on_done,
                }
            )

        with patch(
            "dashboard_gui.gsm_engines.overlay_command_engine.config._init",
            return_value={
                "devices": {
                    "dashboard-uuid": {
                        "device_id": "stable-device-id",
                    }
                }
            },
        ), patch(
            "dashboard_gui.gsm_engines.overlay_command_engine.uuid.uuid4",
            return_value="selection-uuid",
        ), patch(
            "dashboard_gui.gsm_engines.overlay_command_engine."
            "web_client.WEB_CLIENT.send_history_command",
            side_effect=capture_send,
        ):
            result = engine.send_history_command(
                mac="dashboard-uuid",
                mode="history",
                history_window=window,
                on_complete=lambda key, error: completed.append(
                    (key, error)
                ),
                force=True,
            )

        self.assertEqual(result.status, "loading")
        self.assertEqual(result.target_revision, 8)
        self.assertEqual(sent["mac"], "dashboard-uuid")
        self.assertEqual(
            sent["params"],
            {
                "mode": "history",
                "from": 100.0,
                "to": 200.0,
                "points": 30,
                "range_key": 6,
                "device_id": "stable-device-id",
                "selection_id": "selection-uuid",
                "base_revision": 7,
                "base_session": "hub-session",
            },
        )
        self.assertEqual(
            graph_engine.selection_calls[0]["device_id"],
            "dashboard-uuid",
        )

        acknowledgement = {
            "status": "selected",
            "history_session": "hub-session",
            "rev_history": 8,
            "selection_id": "selection-uuid",
            "device_id": "stable-device-id",
            "mode": "history",
        }
        sent["on_done"](acknowledgement, None)

        self.assertEqual(
            graph_engine.completions,
            [("selection-uuid", None)],
        )
        self.assertEqual(completed, [(result.key, None)])

    def test_web_client_resolves_route_again_for_every_history_command(self):
        client = object.__new__(WebClientThread)
        client.registry = Mock()
        client.registry.is_cooldown.return_value = False
        client.registry.build_targets.side_effect = (
            lambda _mac, device: [device["route"]]
        )
        current_config = {
            "devices": {
                "dashboard-uuid": {
                    "route": "https://remote.example",
                }
            }
        }
        calls = []

        def send_request(base_url, params, _user, _pw):
            calls.append((base_url, dict(params)))
            return {
                "status": "selected",
                "selection_id": params["selection_id"],
            }, None

        def send_and_wait(selection_id):
            done = threading.Event()
            client.send_history_command(
                "dashboard-uuid",
                {"selection_id": selection_id},
                lambda _payload, _error: done.set(),
            )
            self.assertTrue(done.wait(2))

        with patch(
            "web_client.config._init",
            side_effect=lambda: current_config,
        ), patch(
            "web_client.config.get_device_auth",
            return_value=("", ""),
        ), patch(
            "web_client.network_worker.send_history_request",
            side_effect=send_request,
        ):
            send_and_wait("remote-command")
            current_config["devices"]["dashboard-uuid"] = {
                "route": "http://192.168.2.20",
            }
            send_and_wait("local-command")

        self.assertEqual(
            [base_url for base_url, _params in calls],
            [
                "https://remote.example",
                "http://192.168.2.20",
            ],
        )

    def test_local_config_uuid_is_never_used_as_history_device_id(self):
        graph_engine = FakeHistoryGraphEngine()
        gsm = Mock()
        gsm.graph_engine = graph_engine
        engine = OverlayCommandEngine(gsm)

        with patch(
            "dashboard_gui.gsm_engines.overlay_command_engine.config._init",
            return_value={
                "devices": {
                    "local-config-uuid": {
                        "device_id": "",
                        "hostname": "growmaster-d064",
                    }
                }
            },
        ), patch(
            "dashboard_gui.gsm_engines.overlay_command_engine."
            "web_client.WEB_CLIENT.send_history_command",
        ) as send:
            result = engine.send_history_command(
                mac="local-config-uuid",
                mode="live",
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("device_id", result.error)
        self.assertEqual(graph_engine.selection_calls, [])
        send.assert_not_called()

    def test_only_command_engine_calls_web_client_history_api(self):
        project_root = Path(__file__).resolve().parents[1]
        callers = []
        for source_file in (
            project_root / "dashboard_gui"
        ).rglob("*.py"):
            source = source_file.read_text(encoding="utf-8")
            if "WEB_CLIENT.send_history_command(" in source:
                callers.append(source_file.relative_to(project_root))

        self.assertEqual(
            callers,
            [
                Path(
                    "dashboard_gui/gsm_engines/"
                    "overlay_command_engine.py"
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
