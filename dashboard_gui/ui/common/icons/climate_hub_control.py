# dashboard_gui/ui/common/icons/climate_hub_control.py

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class ClimateHubControl(BoxLayout):

    def __init__(self, parent_header=None, **kw):
        super().__init__(**kw)

        self.parent_header = parent_header

        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(45)

        self.icon = IconLabel(
            text="\uf0ac",      # Globe
            font_size=sp_scaled(24)
        )

        self.icon.color = (0.75, 0.75, 0.75, 1)
        self._active = False

        self.add_widget(self.icon)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): 
            return False
            
        ui = GLOBAL_STATE.ui_handler
        from dashboard_gui.overlays.climate_hub_overlay import ClimateHubOverlay
        
        # Falls das Overlay bereits offen ist, schließen – andernfalls neu erzeugen
        if getattr(ui, "active_climate_hub_overlay", None):
            ui.active_climate_hub_overlay.close()
        else:
            overlay = ClimateHubOverlay(parent_header=self)
            ui.active_climate_hub_overlay = overlay
            App.get_running_app().root.current_screen.add_widget(overlay)
        return True

    def set_active(self, active=True):
        self._active = bool(active)
        # Adjust visual subtly
        if self._active:
            self.icon.color = (0.3, 1, 1, 1)
        else:
            self.icon.color = (0.75, 0.75, 0.75, 1)

    def is_active(self):
        return bool(self._active)