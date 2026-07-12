import kivy
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.togglebutton import ToggleButton
from kivy.metrics import dp
from dashboard_gui.ui.scaling_utils import dp_scaled

class DeviceButton(ToggleButton):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)

        with self.canvas.before:
            # Hintergrund-Farbe (bleibt gleich)
            Color(0, 0, 0, 0.62)
            self.bg = RoundedRectangle(radius=[dp_scaled(12)])

            # Rahmen-Farbe (bleibt gleich)
            Color(0, 0.8, 1, 0.6)
            self.outline = Line(
                width=dp_scaled(1.2), # Start-Dicke
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp_scaled(12))
            )

        # Bindings für Position/Größe UND Status-Wechsel
        self.bind(pos=self._update_canvas, size=self._update_canvas, state=self._update_canvas)

    def _update_canvas(self, *args):
        # 1. Position und Größe des Hintergrunds
        self.bg.pos = self.pos
        self.bg.size = self.size

        # 2. Dynamische Linienstärke basierend auf dem Status
        # Wenn gedrückt (down), zeichnen wir den Rahmen deutlich dicker
        if self.state == 'down':
            self.outline.width = dp_scaled(3.5)  # Schöner fetter Rahmen
        else:
            self.outline.width = dp_scaled(1.2)  # Standard dünner Rahmen

        # 3. Rahmen-Geometrie aktualisieren
        self.outline.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp_scaled(12)
        )