# dashboard_gui/ui/common/icons/external_icon.py

from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.metrics import dp
import time
import os
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

# -------------------------------------------------------
# External Sensor – OPTIMIZED FOR 60DP HEADER
# -------------------------------------------------------
class ExternalIcon(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "horizontal" # Von vertikal auf horizontal gewechselt
        self.spacing = dp_scaled(4)
        self.size_hint = (None, 1)
        self.width = dp_scaled(40)      # Etwas breiter für Icon + Text nebeneinander

        # Icon etwas kleiner, damit es nicht "schreit"
        self.icon = IconLabel(font_size=sp_scaled(22))
        
        # Text-Label zentrieren
        self.text_label = Label(
            font_size=sp_scaled(14), 
            color=(0.8, 0.8, 0.8, 1),
            halign="left",
            valign="middle"
        )
        self.text_label.bind(size=self.text_label.setter('text_size'))

        self.add_widget(self.icon)
        self.add_widget(self.text_label)

        self.set_external(False)
        self._present = False

    def set_external(self, present):
        self._present = bool(present)

        icon, text = BoxColorUpdater.get_external_state(self._present)

        if present is None:
            return color (0.6, 0.6, 0.6, 1),
        else:

            color = (*BoxColorUpdater.get_external_color(), 1)

        self.icon.text = icon
        self.icon.color = color
        self.text_label.text = text
        self.text_label.color = color

    def is_active(self):
        """Return True if external sensor is present."""
        return bool(self._present)


            
