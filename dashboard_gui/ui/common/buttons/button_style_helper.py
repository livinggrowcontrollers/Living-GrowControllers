# dashboard_gui/ui/common/button_style_helper.py

from dashboard_gui.ui.scaling_utils import sp_scaled
from kivy.uix.button import Button

class ButtonStyleHelper:

    def _create_styled_btn(self, text):
        return Button(
            text=text,
            markup=True,
            background_normal="",
            background_down="",
            background_color=(0.15, 0.15, 0.15, 1),
            color=(1, 1, 1, 1),  # gleiche Basis wie Exhaust (lesbar default)
            font_size=sp_scaled(20))