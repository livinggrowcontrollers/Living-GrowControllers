# dashboard_gui/gesture_engines/dashboard_swipe.py
from kivy.metrics import dp
from kivy.app import App
import dashboard_gui.global_state_manager as gsm

class DashboardSwipeEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        # Konfiguration
        self._swipe_threshold = dp(60)  # Wie weit muss man wischen?
        self._touch_start_x = None      # Wo ging der Finger runter?
        self._touch_active = False      # Läuft gerade ein Swipe?

    def open_fullscreen(self, full_key):
        """Wird von ChartTile aufgerufen (Klick auf Kachel)"""
        sm = getattr(self.gsm, "screen_manager", None)
        fs = App.get_running_app().ensure_screen("fullscreen")

        if fs:
            if not fs.activate_tile(full_key):
                print(f"[DashboardSwipe] Fullscreen blocked for: {full_key}")
                return False
            if sm:
                sm.transition.direction = "up"
            gsm.GLOBAL_STATE.ui_handler.goto("fullscreen")
            return True
        return False
    # --- TOUCH-LOGIK (Wird vom GGM gefüttert) ---

    def process_touch_down(self, touch):
        """Finger berührt das Dashboard"""
        self._touch_start_x = touch.x
        self._touch_active = True

    def process_touch_move(self, touch):
        """Finger bewegt sich auf dem Dashboard"""
        if not self._touch_active or self._touch_start_x is None:
            return

        # Differenz berechnen
        dx = touch.x - self._touch_start_x

        # Prüfen, ob weit genug gewischt wurde
        if abs(dx) < self._swipe_threshold:
            return

        # Swipe erkannt! Richtung bestimmen
        # Finger nach links (dx negativ) -> nächstes Gerät (-1)
        # Finger nach rechts (dx positiv) -> vorheriges Gerät (1)
        direction = -1 if dx < 0 else 1
        self._handle_swipe(direction)

        # WICHTIG: Swipe sperren, bis der Finger wieder losgelassen wird
        self._touch_active = False

    def process_touch_up(self, touch):
        """Finger verlässt das Dashboard"""
        self._touch_active = False
        self._touch_start_x = None

    # --- AKTION ---

    def _handle_swipe(self, direction):
        """Führt den Gerätewechsel im GSM aus"""
        if direction < 0:
            print("[DASHBOARD-SWIPE] Nächstes Gerät")
            self.gsm.next_device()
        else:
            print("[DASHBOARD-SWIPE] Vorheriges Gerät")
            self.gsm.previous_device()
