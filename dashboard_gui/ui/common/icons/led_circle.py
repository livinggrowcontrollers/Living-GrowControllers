# dashboard_gui/ui/common/icons/led_circle.py

import os
from kivy.uix.widget import Widget
from kivy.graphics import Ellipse, Color
from kivy.clock import Clock
from kivy.metrics import dp
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled 
# -------------------------------------------------------
# LED Circle – MODERN UI (NO LOGIC CHANGE)
# -------------------------------------------------------
class LEDCircle(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)

        self._pulse_event = None
        self._base_status = "offline"

        with self.canvas:
            # --- Outer Glow ---
            self.glow_color = Color(0, 1, 0, 0.25)
            self.glow = Ellipse()

            # --- Ring ---
            self.ring_color = Color(0, 1, 0, 0.9)
            self.ring = Ellipse()

            # --- Core ---
            self.core_color = Color(0, 1, 0, 1)
            self.core = Ellipse()

        self.bind(pos=self._u, size=self._u)
        self._u()

    def _u(self, *_):
        size = dp_scaled(16)
        glow = size * 1.6
        ring = size * 1.15

        cx = self.x + self.width / 2
        cy = self.y + self.height / 2

        self.glow.size = (glow, glow)
        self.glow.pos = (cx - glow / 2, cy - glow / 2)

        self.ring.size = (ring, ring)
        self.ring.pos = (cx - ring / 2, cy - ring / 2)

        self.core.size = (size, size)
        self.core.pos = (cx - size / 2, cy - size / 2)

    # -------------------------------
    # LOGIC – UNCHANGED
    # -------------------------------
    def set_state(self, alive, status):
        base = "stale" if status == "flow" else status
        self._base_status = base

        if base in ("offline", "error") and self._pulse_event:
            self._pulse_event.cancel()
            self._pulse_event = None

        if not self._pulse_event:
            self._apply(base)

        if status == "flow":
            self._pulse()

    def _apply(self, s):
        if s == "stale":
            self._set_color(0, 0.6, 0) 
            return
        if s == "nodata":
            self._set_color(1, 0.8, 0); return
        if s == "error":
            self._set_color(1, 0, 0); return
        if s == "offline":
            self._set_color(0.4, 0.1, 0.1); return # Dunkles Rot
            
        # HIER: Wenn das Gerät online ist (Status 'online' oder 'alive'), sattes Grün zeigen!
        if s in ("online", "active") or self._base_status not in ("offline", "error"):
            self._set_color(0, 0.8, 0)
            return

        self._set_color(0.5, 0.5, 0.5)

    def _set_color(self, r, g, b):
        self.core_color.rgba = (r, g, b, 1)
        self.ring_color.rgba = (r * 0.8, g * 0.8, b * 0.8, 0.9)
        self.glow_color.rgba = (r, g, b, 0.25)

    def _pulse(self):
        if self._pulse_event:
            self._pulse_event.cancel()

        self._set_color(0.3, 1, 0.3)
        self.glow_color.a = 0.45

        self._pulse_event = Clock.schedule_once(
            lambda *_: self._end(), 0.15
        )

    def _end(self, *_):
        self._pulse_event = None
        self._apply(self._base_status)


