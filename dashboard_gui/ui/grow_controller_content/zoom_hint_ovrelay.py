# dashboard_gui/ui/grow_controller_content/zoom_hint_ovrelay.py


from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class ZoomHintOverlay(BoxLayout):
    """
    Wiederverwendbarer Hinweis-Badge mit Font Awesome Icons.
    Löst beim Klick oder Interaktion eine Fade-Out Animation aus.
    """

    def __init__(
        self,
        text="[font=FA]\uf00e[/font] Scrollen zum Zoomen  •  [font=FA]\uf047[/font] Drücken & Ziehen",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp_scaled(380), dp_scaled(42))
        self.padding = [dp_scaled(12), dp_scaled(6)]
        self.opacity = 0.95

        with self.canvas.before:
            Color(0.1, 0.1, 0.15, 0.88)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp_scaled(8)])
            Color(0.2, 0.8, 1, 0.4)
            self.border = RoundedRectangle(
                pos=(self.x - 1, self.y - 1),
                size=(self.width + 2, self.height + 2),
                radius=[dp_scaled(9)],
            )

        self.bind(pos=self._update_graphics, size=self._update_graphics)

        self.label = Label(
            text=text,
            markup=True,  # FA-Font Rendering aktiviert
            font_size=sp_scaled(14),
            color=(0.9, 0.9, 0.9, 1),
            halign="center",
            valign="middle",
        )
        self.label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.add_widget(self.label)

        self._is_dismissed = False

    def _update_graphics(self, *_):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.border.pos = (self.x - 1, self.y - 1)
        self.border.size = (self.width + 2, self.height + 2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.dismiss()
            return True
        return super().on_touch_down(touch)

    def dismiss(self, *_):
        """Sanfte Ausblend-Animation."""
        if self._is_dismissed:
            return
        self._is_dismissed = True

        anim = Animation(opacity=0, d=0.25, t="out_quad")

        def _remove(*_):
            if self.parent:
                self.parent.remove_widget(self)

        anim.bind(on_complete=_remove)
        anim.start(self)