# dashboard_gui/ui/common/icons/exhaust_fan_control.py
from kivy.uix.boxlayout import BoxLayout
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from kivy.uix.label import Label
from kivy.app import App



class ExhaustFanControl(BoxLayout):
    def __init__(self, parent_header=None, **kw):
        super().__init__(**kw)
        self.parent_header = parent_header
        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(45)
        self.latest_data = {}
        self.latest_rpm = None
        # Entweder vom parent_header übernehmen oder direkt vom GLOBAL_STATE
        if parent_header and hasattr(parent_header, 'gsm'):
            self.gsm = parent_header.gsm
        else:
            self.gsm = GLOBAL_STATE.gsm

        self.icon = IconLabel(text="\uf863", font_size=sp_scaled(24))
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
            color = BoxColorUpdater.get_rpm_color(rpm)
            self.icon.color = (*color, 1)

        except Exception:
            self.icon.color = (0.3, 0.3, 0.3, 1)

    def is_active(self):
        """Return True if exhaust fan is active (rpm > 0)."""
        try:
            return bool(self.latest_rpm and float(self.latest_rpm) > 0)
        except Exception:
            return False

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): return False
        ui = GLOBAL_STATE.ui_handler
        
        # Hier importieren wir nun das spezifische Exhaust-Overlay
        # Pfad ggf. anpassen, falls die Datei anders heißt
        from dashboard_gui.overlays.exhaust_fan_overlay import ExhaustFanOverlay
        
        if getattr(ui, "active_exhaust_fan_overlay", None):
            ui.active_exhaust_fan_overlay.close()
        else:
            overlay = ExhaustFanOverlay(parent_header=self)
            ui.active_exhaust_fan_overlay = overlay
            App.get_running_app().root.current_screen.add_widget(overlay)
        return True