# dashboard_gui/gesture_engines/vpd_swipe.py
from kivy.metrics import dp

class VPDSwipeEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self._swipe_threshold = dp(60)
        self._touch_start_x = None
        self._touch_active = False

    def process_touch_down(self, touch):
        self._touch_start_x = touch.x
        self._touch_active = True

    def process_touch_move(self, touch):
        if not self._touch_active or self._touch_start_x is None:
            return
        dx = touch.x - self._touch_start_x
        if abs(dx) < self._swipe_threshold:
            return

        direction = -1 if dx < 0 else 1
        self._handle_swipe(direction)
        self._touch_active = False

    def process_touch_up(self, touch):
        self._touch_active = False
        self._touch_start_x = None

    def _handle_swipe(self, direction):
        if direction < 0:
            self.gsm.next_device()
        else:
            self.gsm.previous_device()