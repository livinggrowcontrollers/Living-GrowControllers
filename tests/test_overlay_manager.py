import unittest

from dashboard_gui.overlays.infrastructure.contracts import OverlayKey
from dashboard_gui.overlays.infrastructure.overlay_manager import OverlayManager


class FakeUIManager:
    pass


class FakeHost:
    def __init__(self):
        self.widgets = []

    def add_widget(self, widget):
        self.widgets.append(widget)


class FakeOverlay:
    def __init__(self, manager):
        self.manager = manager
        self.closed = False

    def close(self):
        self.closed = True
        self.manager.unregister(self)


class OverlayManagerTests(unittest.TestCase):
    def test_only_one_overlay_remains_active(self):
        ui = FakeUIManager()
        manager = OverlayManager(ui)
        host = FakeHost()
        first = manager.open(OverlayKey("light"), lambda: FakeOverlay(manager), host)
        second = manager.open(OverlayKey("exhaust"), lambda: FakeOverlay(manager), host)
        self.assertTrue(first.closed)
        self.assertIs(manager.active_overlay, second)
        self.assertIs(ui.active_exhaust_fan_overlay, second)
        self.assertIsNone(ui.active_light_overlay)

    def test_opening_the_same_instance_toggles_it_closed(self):
        ui = FakeUIManager()
        manager = OverlayManager(ui)
        host = FakeHost()
        overlay = manager.open(OverlayKey("circulation", 2), lambda: FakeOverlay(manager), host)
        result = manager.open(OverlayKey("circulation", 2), lambda: FakeOverlay(manager), host)
        self.assertIsNone(result)
        self.assertTrue(overlay.closed)
        self.assertIsNone(manager.active_overlay)


if __name__ == "__main__":
    unittest.main()
