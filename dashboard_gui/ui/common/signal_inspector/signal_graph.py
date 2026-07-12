from kivy.uix.widget import Widget
from kivy.graphics import Line, Color
from kivy.clock import Clock
from dashboard_gui.ui.scaling_utils import dp_scaled
class SignalGraph(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.max_points = 60
        # Trigger erstellen
        self._redraw_trigger = Clock.create_trigger(self._do_redraw, -1)

        with self.canvas.after:
            Color(0, 0.8, 1, 0.15)
            self._glow = Line(width=dp_scaled(6), joint='round')
            Color(0, 0.9, 1, 0.7)
            self._line = Line(width=dp_scaled(2.5), joint='round')

        # Hier war der Fehler: Die Methode muss existieren!
        self.bind(pos=self._trigger_redraw, size=self._trigger_redraw)

    def _trigger_redraw(self, *args):
        """Wird aufgerufen, wenn sich Position oder Größe ändern."""
        self._redraw_trigger()

    def add_value(self, val):
        try:
            v = float(val)
            # VIVID SCALE: -90 bis -40 dBm auf 0.0 bis 1.0 spreizen
            normalized = (v + 90) / 50 
            normalized = max(0.05, min(0.95, normalized))
            self.points.append(normalized)
        except: return

        if len(self.points) > self.max_points:
            self.points.pop(0)
        self._redraw_trigger()

    def _do_redraw(self, *args):
        if not self.points or self.width <= 0: return
        w_step = self.width / (self.max_points - 1)
        line_points = []
        for i, p in enumerate(self.points):
            line_points.extend((self.x + (i * w_step), self.y + (p * self.height)))
        
        self._line.points = line_points
        self._glow.points = line_points

    def reset(self):
        self.points = []
        self._line.points = []
        self._glow.points = []
