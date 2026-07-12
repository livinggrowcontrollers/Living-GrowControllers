# dashboard_gui/global_gesture_manager.py

class GlobalGestureManager:
    def __init__(self, gsm):
        self.gsm = gsm

        from dashboard_gui.gesture_engines.dashboard_swipe import DashboardSwipeEngine
        from dashboard_gui.gesture_engines.fullscreen_swipe import FullscreenSwipeEngine
        from dashboard_gui.gesture_engines.vpd_swipe import VPDSwipeEngine

        self.engines = {
            "dashboard": DashboardSwipeEngine(gsm),
            "fullscreen": FullscreenSwipeEngine(gsm),
            "vpd_scatter": VPDSwipeEngine(gsm)
        }

        # 🔥 NEU: GLOBAL STATE
        self._gesture_mode = None   # "swipe" | "scroll"
        self._start_x = 0
        self._start_y = 0

    def handle_touch(self, screen_name, event_type, touch):
        engine = self.engines.get(screen_name)
        if not engine:
            return False
    
        if event_type == "down":
            self._gesture_mode = None
            self._start_x = touch.x
            self._start_y = touch.y
    
            engine.process_touch_down(touch)
            return False
    
        elif event_type == "move":
            dx = touch.x - self._start_x
            dy = touch.y - self._start_y
    
            # 👉 Entscheidung EINMAL treffen
            if self._gesture_mode is None:
                if abs(dx) > 10:
                    self._gesture_mode = "swipe"
                elif abs(dy) > 10:
                    self._gesture_mode = "scroll"
    
            # 👉 SWIPE → Engine bekommt Kontrolle
            if self._gesture_mode == "swipe":
                engine.process_touch_move(touch)
                return True   # ❗ blockiert ScrollView
    
            return False  # ScrollView darf arbeiten
    
        elif event_type == "up":
            if self._gesture_mode == "swipe":
                engine.process_touch_up(touch)
                self._gesture_mode = None
                return True
    
            self._gesture_mode = None
            return False