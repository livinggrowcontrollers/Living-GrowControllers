# dashboard_gui/overlays/features/light/channel_preview.py

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dashboard_gui.overlays.components.unified_slider import UnifiedSlider
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class LightChannelPreview(BoxLayout):
    """Interactive local preview for a future supplemental PWM light channel."""

    def __init__(self, channel_name, description, accent, default_pct=0, **kwargs):
        super().__init__(
            orientation="vertical",
            spacing=dp_scaled(12),
            padding=[dp_scaled(20), dp_scaled(18)],
            **kwargs,
        )
        self.channel_name = str(channel_name).upper()
        self.accent = tuple(accent)

        with self.canvas.before:
            Color(0.02, 0.02, 0.025, 0.72)
            self.background = RoundedRectangle(radius=[dp_scaled(16)])
            self.border_color = Color(*self.accent, 0.8)
            self.border = Line(width=1.4)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

        hero = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(110),
            spacing=dp_scaled(16),
        )
        glyph = Label(
            text=self.channel_name,
            font_size=sp_scaled(50),
            bold=True,
            color=(*self.accent, 1),
            size_hint_x=0.35,
        )
        explanation = BoxLayout(orientation="vertical", spacing=dp_scaled(4))
        title = Label(
            text=f"{self.channel_name} SUPPLEMENT",
            font_size=sp_scaled(24),
            bold=True,
            color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
        )
        info = Label(
            text=description,
            font_size=sp_scaled(18),
            color=(0.82, 0.82, 0.88, 1),
            halign="left",
            valign="middle",
        )
        for label in (title, info):
            label.bind(size=label.setter("text_size"))
            explanation.add_widget(label)
        hero.add_widget(glyph)
        hero.add_widget(explanation)
        self.add_widget(hero)

        self.preview_status = Label(
            text="CONCEPT PREVIEW  •  NO GPIO  •  NO ESP COMMAND",
            font_size=sp_scaled(17),
            bold=True,
            color=(1.0, 0.62, 0.18, 1),
            size_hint_y=None,
            height=dp_scaled(28),
        )
        self.add_widget(self.preview_status)

        self.output_label = Label(
            text=f"LOCAL OUTPUT PREVIEW: {int(default_pct)}%",
            font_size=sp_scaled(24),
            bold=True,
            color=(*self.accent, 1),
            size_hint_y=None,
            height=dp_scaled(30),
        )
        self.add_widget(self.output_label)

        self.output_slider = UnifiedSlider(
            min=0,
            max=int(default_pct),
            range_min=0,
            range_max=100,
            mode="single",
            size_hint_y=None,
            height=dp_scaled(52),
        )
        self.output_slider.bind(value=self._update_output_label)
        self.add_widget(self.output_slider)

        self.add_widget(Widget())
        self.add_widget(
            Label(
                text="Future contract: own low-voltage PWM output, own revision channel, coordinated by Light Control.",
                font_size=sp_scaled(17),
                color=(0.65, 0.7, 0.78, 1),
                size_hint_y=None,
                height=dp_scaled(28),
            )
        )

    def set_disabled(self, disabled):
        self.output_slider.disabled = bool(disabled)

    def _update_output_label(self, _slider, value):
        self.output_label.text = f"LOCAL OUTPUT PREVIEW: {int(value)}%"

    def _update_canvas(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size
        self.border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp_scaled(16),
        )
