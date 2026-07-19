from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout

from dashboard_gui.ui.scaling_utils import dp_scaled


class ControlPanel(BoxLayout):
    """Shared fixed-size panel with an accent glow and border."""

    def __init__(self, accent=(0.1, 0.45, 0.9), radius=20, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            self.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.bg_rect = RoundedRectangle(radius=[dp_scaled(radius)])
            self.glow_color = Color(*accent, 0.35)
            self.glow_line = Line(width=4)
            self.border_color = Color(*accent, 0.85)
            self.border_line = Line(width=2.5)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def set_accent(self, color, glow_alpha=0.35, border_alpha=0.85):
        self.glow_color.rgba = (*color, glow_alpha)
        self.border_color.rgba = (*color, border_alpha)

    def _update_canvas(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        rect = (self.x, self.y, self.width, self.height, dp_scaled(self._radius))
        self.glow_line.rounded_rectangle = rect
        self.border_line.rounded_rectangle = rect
