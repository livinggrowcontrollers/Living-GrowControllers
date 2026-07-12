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
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

# -------------------------------------------------------
# External2  Sensor – OPTIMIZED FOR 60DP HEADER
# -------------------------------------------------------
class External2Icon(BoxLayout):
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

        self.set_external2(False)
        self._present = False

    def set_external2(self, present):
        try:
            self._present = bool(present)
        except Exception:
            self._present = False
        if present:
            self.icon.text = "\uf2c7" # Thermometer Icon
            self.icon.color = (1, 0.5, 0, 1) # lachsfarben orange-grün
            self.text_label.text = "EXT2"
            self.text_label.color = (1, 0.5, 0, 1) # hintergrundfarbe des icons undfüllbox
        else:
            self.icon.text = "\uf059" # Fragezeichen
            self.icon.color = (0.4, 0.4, 0.4, 1)
            self.text_label.text = "OFF"
            self.text_label.color = (0.4, 0.4, 0.4, 1)

    def is_active(self):
        """Return True if external2 sensor is present."""
        return bool(self._present)


            
