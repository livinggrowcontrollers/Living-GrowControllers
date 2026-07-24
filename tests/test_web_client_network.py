from collections import deque
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import decoder
from network import client_discovery, network_worker
from network.registry import DeviceRegistry
from web_client import WebClientThread


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.closed = False

    def json(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True


class _FakeSession:
    def __init__(self, outcomes, request_log):
        self.headers = {}
        self._outcomes = outcomes
        self._request_log = request_log
        self.closed = False

    def mount(self, *_args):
        pass

    def request(self, method, url, **kwargs):
        self._request_log.append((method, url, kwargs))
        outcome = self._outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        self.closed = True


def _transport(outcomes):
    outcomes = deque(outcomes)
    request_log = []
    sessions = []

    def factory():
        session = _FakeSession(outcomes, request_log)
        sessions.append(session)
        return session

    return (
        network_worker.PersistentHTTPTransport(factory),
        sessions,
        request_log,
    )


class PersistentTransportTests(unittest.TestCase):
    def test_reuses_session_and_closes_it_when_device_is_removed(self):
        transport, sessions, request_log = _transport(
            [_FakeResponse(), _FakeResponse()]
        )
        for _ in range(2):
            with transport.request(
                "device-1",
                "poll",
                "GET",
                "https://example.test/data",
            ):
                pass

        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(request_log), 2)
        transport.retain_devices(set())
        self.assertTrue(sessions[0].closed)
        self.assertEqual(transport._handles, {})

    def test_connection_error_discards_stale_session(self):
        transport, sessions, _request_log = _transport(
            [
                requests.exceptions.ConnectionError("network changed"),
                _FakeResponse(),
            ]
        )
        with self.assertRaises(requests.exceptions.ConnectionError):
            with transport.request(
                "device-1", "poll", "GET", "https://example.test/data"
            ):
                pass
        with transport.request(
            "device-1", "poll", "GET", "https://example.test/data"
        ):
            pass

        self.assertEqual(len(sessions), 2)
        self.assertTrue(sessions[0].closed)

    def test_control_payload_is_sent_once_to_exact_endpoint(self):
        transport, _sessions, request_log = _transport(
            [_FakeResponse(status_code=200)]
        )
        payload = {"rev_plant_planner": 3, "plant_planner": {}}

        self.assertTrue(
            network_worker.send_control_request(
                "https://example.test",
                payload,
                None,
                None,
                endpoint="/control/plants",
                mac="device-1",
                transport=transport,
            )
        )
        self.assertEqual(len(request_log), 1)
        self.assertEqual(
            request_log[0][1],
            "https://example.test/control/plants",
        )
        self.assertIs(request_log[0][2]["json"], payload)


class RegistryRecoveryTests(unittest.TestCase):
    def test_cloudflare_url_remains_authoritative(self):
        registry = DeviceRegistry()
        registry.update_device("device-1", ip="192.168.2.20")
        self.assertEqual(
            registry.build_targets(
                "device-1",
                {
                    "ip_address": "https://example.trycloudflare.com",
                    "hostname": "growmaster-d064",
                },
            ),
            ["https://example.trycloudflare.com"],
        )

    def test_successful_discovery_route_is_preferred(self):
        registry = DeviceRegistry()
        registry.update_device("device-1", ip="192.168.2.21")
        device = {
            "ip_address": "192.168.2.20",
            "hostname": "growmaster-d064",
        }
        registry.handle_success("device-1", "http://192.168.2.21")
        self.assertEqual(
            registry.build_targets("device-1", device)[0],
            "http://192.168.2.21",
        )

    def test_breaker_stays_below_stale_timeout(self):
        registry = DeviceRegistry()
        clock = [100.0]
        with patch(
            "network.registry.time.monotonic",
            side_effect=lambda: clock[0],
        ):
            for _ in range(4):
                self.assertEqual(registry.handle_failure("device-1"), 0.0)
            self.assertEqual(registry.handle_failure("device-1"), 1.0)
            clock[0] += 1.0
            self.assertFalse(registry.is_cooldown("device-1"))
            self.assertEqual(registry.handle_failure("device-1"), 2.0)
            clock[0] += 2.0
            self.assertEqual(registry.handle_failure("device-1"), 4.0)
            clock[0] += 4.0
            self.assertEqual(registry.handle_failure("device-1"), 6.0)


class WorkerPipelineTests(unittest.TestCase):
    def test_heavy_fetch_is_scheduled_without_blocking_live_payload(self):
        payload = {"rev_plant_planner": 2, "device_id": "growmaster-d064"}
        transport, _sessions, _request_log = _transport(
            [_FakeResponse(payload=payload)]
        )
        scheduled = []
        with patch.object(
            network_worker.config,
            "get_device_auth",
            return_value=(None, None),
        ), patch.object(network_worker, "_update_config_ip_if_needed"):
            result = network_worker.fetch_single_device(
                "device-1",
                {},
                ["https://example.test"],
                DeviceRegistry(),
                {},
                {"device-1": 1},
                transport=transport,
                heavy_fetch_scheduler=lambda *args: scheduled.append(args),
            )

        self.assertIs(result[1], payload)
        self.assertEqual(len(scheduled), 1)
        self.assertNotIn("plant_planner", payload)

    def test_timestamp_is_assigned_at_receipt(self):
        with patch(
            "web_client.client_storage.load_plants_at_boot",
            return_value=({}, {}),
        ):
            client = WebClientThread(interval=0.1)
        payload = {"value": 42}
        started = time.time()
        try:
            with patch(
                "web_client.config._init",
                return_value={
                    "devices": {
                        "device-1": {"ip_address": "https://example.test"}
                    }
                },
            ), patch(
                "network.network_worker.fetch_single_device",
                return_value=("device-1", payload, False),
            ), patch.object(decoder, "inject_web_data"):
                client.fetch_all_web_data()
        finally:
            client.stop()
        self.assertGreaterEqual(payload["timestamp"], started)

    def test_android_timeouts_and_mdns_ipv4(self):
        with patch.object(network_worker, "is_android", return_value=True):
            self.assertEqual(
                network_worker._request_timeout(
                    "https://example.trycloudflare.com", "poll"
                ),
                (3.0, 4.5),
            )
        self.assertEqual(
            client_discovery._select_ipv4(
                ["fe80::1234", "192.168.2.20"]
            ),
            "192.168.2.20",
        )

    def test_android_build_contract(self):
        build_spec = (PROJECT_ROOT / "buildozer.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("CHANGE_WIFI_MULTICAST_STATE", build_spec)
        self.assertIn("requests", build_spec.split("requirements =", 1)[1])


if __name__ == "__main__":
    unittest.main()
