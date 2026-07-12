# dashboard_gui/ui/grow_overview_content/segmented_progress_bar.py

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import NumericProperty
from kivy.metrics import dp


class SegmentedProgressBar(Widget):
    """
    Generischer segmentierter Progressbar (UI-unabhängig)
    - nutzbar für Licht, Klima, Sensoren, Ventilatoren etc.
    """

    value = NumericProperty(0)
    max = NumericProperty(100)
    num_segments = NumericProperty(30)

    active_color = (1.0, 0.72, 0.15, 1)
    inactive_color = (0.2, 0.2, 0.2, 1)

    segment_spacing = NumericProperty(dp(2))
    corner_radius = NumericProperty(dp(2))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            value=self._update_canvas,
            max=self._update_canvas,
            num_segments=self._update_canvas
        )

    def _update_canvas(self, *args):
        self.canvas.clear()

        w, h = self.size
        if self.num_segments <= 0:
            return

        spacing = self.segment_spacing
        segment_w = (w - (self.num_segments - 1) * spacing) / self.num_segments
        segment_h = h

        ratio = 0 if self.max == 0 else self.value / self.max
        filled_count = max(
            1 if self.value > 0 else 0,
            int(ratio * self.num_segments)
        )
        with self.canvas:
            for i in range(self.num_segments):
                if i < filled_count:
                    Color(*self.active_color)
                else:
                    Color(*self.inactive_color)

                x_pos = self.x + i * (segment_w + spacing)
                RoundedRectangle(
                    pos=(x_pos, self.y),
                    size=(segment_w, segment_h),
                    radius=[self.corner_radius]
                )


class SegmentedProgressBarView(BoxLayout):
    """
    Optional Wrapper-Widget (UI Layer)
    - wenn du Labels / Layout später willst
    """

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.bar = SegmentedProgressBar()
        self.add_widget(self.bar)