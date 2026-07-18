# dashboard_gui/led_engine.py
import time

class LedEngine:
    def __init__(self, ui_handler):
        self.ui_handler = ui_handler
        self._flow_hold = False
        self.led_state = {"alive": False, "status": "offline"}
        self._states_by_channel = {}
        self._last_pushed_channel = None

    def flow(self, channel=None):
        self._set_state({"alive": True, "status": "flow"}, channel)
        self._flow_hold = True
        self._last_packet_timestamp = time.time()

    def stale(self, channel=None):
        self._set_state({"alive": True, "status": "stale"}, channel)

    def offline(self, channel=None):
        self._set_state({"alive": False, "status": "offline"}, channel)

    def nodata(self, channel=None):
        self._set_state({"alive": False, "status": "nodata"}, channel)

    def release_flow_hold(self):
        self._flow_hold = False

    def _set_state(self, state, channel=None):
        """Keep LED state per data channel while publishing the active one."""
        previous = self._states_by_channel.get(channel)
        self._states_by_channel[channel] = state

        # A channel switch is significant even when both channels currently
        # share the same colour/status: the header must receive that channel's
        # own state (and a new flow pulse, if applicable).
        if state == previous and channel == self._last_pushed_channel:
            return

        self.led_state = state
        self._last_pushed_channel = channel
        self._push_led()

    def _push_led(self):
        if self.ui_handler:
            self.ui_handler.update_leds(self.led_state)
