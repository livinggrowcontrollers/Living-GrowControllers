# dashboard_gui/led_engine.py
import time

class LedEngine:
    def __init__(self, ui_handler):
        self.ui_handler = ui_handler
        self._flow_hold = False
        self.led_state = {"alive": False, "status": "offline"}

    def flow(self):
        self.led_state = {"alive": True, "status": "flow"}
        self._flow_hold = True
        self._last_packet_timestamp = time.time()
        self._push_led()

    def stale(self):
        self.led_state = {"alive": True, "status": "stale"}
        self._push_led()

    def offline(self):
        self.led_state = {"alive": False, "status": "offline"}
        self._push_led()

    def nodata(self):
        self.led_state = {"alive": False, "status": "nodata"}
        self._push_led()

    def release_flow_hold(self):
        self._flow_hold = False

    def _push_led(self):
        if self.ui_handler:
            self.ui_handler.update_leds(self.led_state)