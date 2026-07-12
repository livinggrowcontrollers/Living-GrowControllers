# dashboard_gui/ui/common/icons/battery_icon.py


from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater

#######BATTERY
class BatteryIcon(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "horizontal"
        self.spacing = dp_scaled(4)
        self.size_hint = (None, 1)
        self.width = dp_scaled(75) # Platz für Icon + "4.1V"

        self.icon = IconLabel(font_size=sp_scaled(22))
        self.text_label = Label(
            text="--V",
            font_size=sp_scaled(12),
            color=(0.8, 0.8, 0.8, 1),
            halign="left",
            valign="middle"
        )
        self.text_label.bind(size=self.text_label.setter('text_size'))

        self.add_widget(self.icon)
        self.add_widget(self.text_label)

    def set_voltage(self, voltage):
        icon, text = BoxColorUpdater.get_battery_state(voltage)

        self.icon.text = icon
        self.text_label.text = text
        self.icon.color = (*BoxColorUpdater.get_battery_color(voltage), 1)