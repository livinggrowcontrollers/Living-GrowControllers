import time

from kivy.graphics import Color, Line, Mesh
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from .schedule import LightSchedule


class LightTimelineWidget(FloatLayout):
    """Own the complete 24-hour light-curve rendering."""

    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=dp_scaled(48), **kwargs)
        self._schedule = LightSchedule()
        with self.canvas.before:
            Color(1, 0.72, 0.05, 0.15)
            self.graph_fill = Mesh(mode="triangle_strip")
            Color(1, 0.72, 0.05, 0.08)
            self.graph_glow = Line(width=dp_scaled(3), joint="round")
            Color(1, 0.72, 0.15, 1)
            self.graph_line = Line(width=dp_scaled(1.5), joint="round")
            Color(1, 0.2, 0.2, 0.85)
            self.time_indicator = Line(width=dp_scaled(1.5))

        self.time_labels = []
        for text in ("00:00", "06:00", "12:00", "18:00"):
            label = Label(
                text=text,
                font_size=sp_scaled(11),
                color=(0.82, 0.82, 0.82, 0.92),
                size_hint=(None, None),
                size=(dp_scaled(40), dp_scaled(15)),
            )
            self.time_labels.append(label)
            self.add_widget(label)
        self.bind(pos=self._redraw, size=self._redraw)

    def set_schedule(self, schedule):
        self._schedule = schedule.normalized()
        self._redraw()

    def _redraw(self, *_):
        x_base = self.x + dp_scaled(20)
        y_base = self.y + dp_scaled(17)
        width = max(1, self.width - dp_scaled(40))
        height = dp_scaled(26)
        points = []
        for progress, intensity in self._schedule.curve():
            points.extend((x_base + progress * width, y_base + intensity / 100.0 * height))
        self.graph_line.points = points
        self.graph_glow.points = points

        vertices = []
        for index in range(0, len(points), 2):
            x_pos, y_pos = points[index], points[index + 1]
            vertices.extend((x_pos, y_base, 0, 0, x_pos, y_pos, 0, 0))
        self.graph_fill.indices = list(range(len(vertices) // 4))
        self.graph_fill.vertices = vertices

        now = time.localtime()
        current_minute = now.tm_hour * 60 + now.tm_min
        indicator_x = x_base + current_minute / 1440.0 * width
        self.time_indicator.points = (indicator_x, y_base, indicator_x, y_base + height + dp_scaled(4))

        for index, label in enumerate(self.time_labels):
            label.pos = (x_base + index * 0.25 * width - label.width / 2, self.y)
