# dashboard_gui/gesture_engines/fullscreen_swipe.py
from kivy.metrics import dp

class FullscreenSwipeEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self._swipe_threshold = dp(60) # Ab wieviel Pixeln gilt es als Swipe?
        self._touch_start_x = None
        self._touch_active = False

    @property
    def fs_view(self):
        """Holt sich den aktuellen Screen direkt vom UI-Handler"""
        return self.gsm.ui_handler.screens.get("fullscreen")

    # --- DIE METHODEN, DIE DER GGM BRAUCHT ---

    def process_touch_down(self, touch):
        self._touch_start_x = touch.x
        self._touch_active = True

    def process_touch_move(self, touch):
        if not self._touch_active or self._touch_start_x is None:
            return

        dx = touch.x - self._touch_start_x

        if abs(dx) < self._swipe_threshold:
            return

        # Swipe erkannt!
        direction = -1 if dx < 0 else 1
        self._handle_swipe(direction)

        # Lock, damit pro Wisch nur ein Wechsel passiert
        self._touch_active = False
        self._touch_start_x = None

    def process_touch_up(self, touch):
        self._touch_active = False
        self._touch_start_x = None

    # --- LOGIK ---

    def _handle_swipe(self, direction):
        view = self.fs_view
        if not view:
            return

        # direction < 0: Finger nach links -> Nächste Kachel (1)
        # direction > 0: Finger nach rechts -> Vorherige Kachel (-1)
        if direction < 0:
            view._switch(1)
        else:
            view._switch(-1)