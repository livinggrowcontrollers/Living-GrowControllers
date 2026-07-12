# dasboard_gui/ui/common/icons/light_control.py

from kivy.uix.boxlayout import BoxLayout
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.overlays.light_overlay import LightOverlay
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from kivy.uix.label import Label
from kivy.app import App


class LightControl(BoxLayout):
    def __init__(self, parent_header=None, **kw):
        super().__init__(**kw)
        self.parent_header = parent_header
        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(45)
        self.latest_data = {}
        self.latest_brightness = None

        self.icon_on = "\uf0eb"  
        self.icon_off = "\uf0eb" # Wir nutzen das gleiche Icon, ändern aber das Feeling

        self.icon = IconLabel(text=self.icon_on, font_size=sp_scaled(24))
        self.add_widget(self.icon)

    def set_brightness(self, brightness, data=None):
        if isinstance(data, dict):
            self.latest_data = data
        # store latest brightness for activity checks
        try:
            self.latest_brightness = None if brightness is None else int(brightness)
        except Exception:
            self.latest_brightness = None

        # 1. OFFLINE / SENSOR-FEHLER (Pseudo-Werte < 0)
        # Grau durchscheinend (Alpha 0.5) signalisiert Verbindungsabbruch
        if brightness is None or brightness < 0:
            self.icon.color = (0.5, 0.5, 0.5, 0.5) 
            return
    
        # 2. SAFE CAST
        try:
            val = int(brightness)
        except Exception:
            self.icon.color = (0.5, 0.5, 0.5, 0.5)
            return
    
        color = BoxColorUpdater.get_light_color(brightness)
        self.icon.color = (*color, 1)

    def is_active(self):
        """Return True if light is considered active (brightness > 0)."""
        try:
            return bool(self.latest_brightness and int(self.latest_brightness) > 0)
        except Exception:
            return False
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): return False
        
        ui = GLOBAL_STATE.ui_handler
        
        # Sicherstellen, dass wir nicht beide Overlays gleichzeitig offen haben
        if getattr(ui, "active_fan_overlay", None):
            ui.active_fan_overlay.close()

        if getattr(ui, "active_light_overlay", None):
            ui.active_light_overlay.close()
        else:
            overlay = LightOverlay(parent_header=self)
            ui.active_light_overlay = overlay
            App.get_running_app().root.current_screen.add_widget(overlay)
        return True