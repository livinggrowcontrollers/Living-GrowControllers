# dashboard_gui/ui/common/icons/circulation_fan_control.py
from kivy.uix.boxlayout import BoxLayout
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.overlays.components.status_colors import StatusColors



class CirculationFanControl(BoxLayout):
    def __init__(self, parent_header=None, fan_id=1, **kw):
        super().__init__(**kw)
        self.parent_header = parent_header
        self.fan_id = int(fan_id)
        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(45)
        self.latest_data = {}
        self.latest_rpm = None

        # Icon für den Lüfter (\uf72e)
        self.icon = IconLabel(text="\uf72e", font_size=sp_scaled(24))
        self.add_widget(self.icon)

    def set_rpm(self, rpm, data=None):
        if isinstance(data, dict):
            self.latest_data = data
        try:
            self.latest_rpm = None if rpm is None else float(rpm)
        except Exception:
            self.latest_rpm = None
            
        # 1. OFFLINE / PSEUDO-WERTE (z.B. -0.5, -256)
        if rpm is None or rpm < 0:
            self.icon.color = (0.4, 0.4, 0.4, 1)  # Grau
            return
    
        try:
            color = StatusColors.get_rpm_color(rpm)
            self.icon.color = (*color, 1)

        except Exception:
            self.icon.color = (0.3, 0.3, 0.3, 1)

    def is_active(self):
        """Return True if circulation fan is active (rpm > 0)."""
        try:
            return bool(self.latest_rpm and float(self.latest_rpm) > 0)
        except Exception:
            return False

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): 
            return False
        
        # Lokaler Import verhindert Verzögerungen beim App-Start
        from dashboard_gui.overlays.features.circulation.overlay import CirculationFanOverlay
        ui = GLOBAL_STATE.ui_handler
        
        ui.open_overlay(
            "circulation",
            lambda: CirculationFanOverlay(parent_header=self, fan_id=self.fan_id),
            instance_id=self.fan_id,
        )
            
        return True
