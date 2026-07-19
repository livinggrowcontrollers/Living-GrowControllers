from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.components.unified_slider import UnifiedSlider


class LabeledSlider(BoxLayout):
    def __init__(self, title, value_text="", slider_kwargs=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp_scaled(50), **kwargs)
        row = BoxLayout(size_hint_y=None, height=dp_scaled(15))
        row.add_widget(Label(text=title, font_size=sp_scaled(20), color=(0.0, 0.85, 0.35, 0.75), halign="left"))
        self.value_label = Label(text=value_text, font_size=sp_scaled(20), color=(1, 1, 1, 1), halign="right")
        row.add_widget(self.value_label)
        self.slider = UnifiedSlider(size_hint_y=None, height=dp_scaled(35), **(slider_kwargs or {}))
        self.add_widget(row)
        self.add_widget(self.slider)
