from kivy.uix.button import Button
from kivy.graphics import Line, Color
from kivy.metrics import dp
from dashboard_gui.ui.scaling_utils import sp_scaled   



class GlassButton(Button):
    def __init__(self, **kwargs):

        kwargs.setdefault("markup", True)

        super().__init__(**kwargs)

        self.background_normal = ''
        self.background_color = (0.1, 0.1, 0.2, 0.4)
        self.color = (1, 1, 1, 1)
        self.font_size = sp_scaled(14)

        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0, 1, 0.4, 0.5) 
            Line(rectangle=(self.x, self.y, self.width, self.height), width=dp(1.1))
