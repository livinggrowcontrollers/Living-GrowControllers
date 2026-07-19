from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from .sync_button import SyncButton


class OverlayHeader(BoxLayout):
    def __init__(self, title, height=35, **kwargs):
        super().__init__(size_hint_y=None, height=dp_scaled(height), spacing=dp_scaled(5), **kwargs)
        self.title_label = Label(
            text=title,
            bold=True,
            color=(0, 1, 0, 1),
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
        )
        self.title_label.bind(size=self.title_label.setter("text_size"))
        self.actions = BoxLayout(size_hint=(None, 1), width=0, spacing=dp_scaled(5))
        self.sync_button = SyncButton()
        self.add_widget(self.title_label)
        self.add_widget(self.actions)
        self.add_widget(self.sync_button)

    def add_action(self, widget, width=None):
        action_width = width if width is not None else getattr(widget, "width", 0)
        self.actions.width += action_width + dp_scaled(5)
        self.actions.add_widget(widget)
