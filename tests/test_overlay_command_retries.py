import unittest

from dashboard_gui.gsm_engines import overlay_command_engine as command_module


class FakeWebClient:
    def __init__(self):
        self.sent = []

    def send_control(self, mac, payload):
        self.sent.append((mac, dict(payload)))


class OverlayCommandRetryTests(unittest.TestCase):
    def setUp(self):
        self.original_client = command_module.web_client.WEB_CLIENT
        self.client = FakeWebClient()
        command_module.web_client.WEB_CLIENT = self.client
        self.engine = command_module.OverlayCommandEngine(None)
        self.snapshot = {
            "rev_light": 0,
            "rev_exhaust": 10,
            "exhaust_fan_min": 20,
            "exhaust_fan_pct": 65,
            "exhaust_fan_mode": "auto",
            "target_temp_min": 22.0,
            "target_temp_max": 28.0,
            "target_humidity_min": 40,
            "target_humidity_max": 70,
            "target_vpd_min": 0.8,
            "target_vpd_max": 1.5,
        }
        self.engine.get_latest_device_data = lambda _mac: dict(self.snapshot)

    def tearDown(self):
        command_module.web_client.WEB_CLIENT = self.original_client

    def test_rapid_light_changes_receive_strictly_increasing_revisions(self):
        first = self.engine.send_light_command("device", pct=40)
        second = self.engine.send_light_command("device", pct=50)
        self.assertEqual((first, second), (1, 2))
        self.assertEqual(self.client.sent[-1][1]["light_pct"], 50)

    def test_retry_reuses_identical_revision_and_payload(self):
        revision = self.engine.send_light_command("device", pct=55)
        original_payload = self.client.sent[-1][1]
        retried_revision = self.engine.retry_command("device", "light")
        self.assertEqual(retried_revision, revision)
        self.assertEqual(self.client.sent[-1][1], original_payload)

    def test_climate_mirror_preserves_pending_exhaust_targets(self):
        exhaust_revision = self.engine.send_exhaust_command("device", min=33, max=81)
        climate_revision = self.engine.send_climate_hub_command("device", t_min=24.0, t_max=27.0)
        payload = self.client.sent[-1][1]
        self.assertEqual((exhaust_revision, climate_revision), (11, 12))
        self.assertEqual((payload["exhaust_fan_min"], payload["exhaust_fan_pct"]), (33, 81))
        self.assertEqual((payload["target_temp_min"], payload["target_temp_max"]), (24.0, 27.0))

    def test_circulation_instances_keep_separate_revision_channels(self):
        self.snapshot.update({"rev_circfan": 4, "rev_circfan2": 8})
        fan_one = self.engine.send_fan_command("device", fan_id=1, min=20, max=60, mode="nat")
        fan_two = self.engine.send_fan_command("device", fan_id=2, min=30, max=70, mode="chao")
        retried_fan_one = self.engine.retry_command("device", "circulation_fan", instance_id=1)
        self.assertEqual((fan_one, fan_two, retried_fan_one), (5, 9, 5))
        self.assertEqual(self.client.sent[-1][1]["rev_circfan"], 5)


if __name__ == "__main__":
    unittest.main()
