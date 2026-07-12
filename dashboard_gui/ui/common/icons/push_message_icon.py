from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.icons.icon_label import IconLabel

# Temporärer relativer/lokaler Import (da im selben Ordner)
from dashboard_gui.overlays.push_message_overlay import PushMessageOverlay

class PushMessageIcon(BoxLayout):

    def __init__(self, **kw):
        super().__init__(**kw)

        self.orientation = "horizontal"
        self.size_hint = (None, 1)
        self.width = dp_scaled(50)

        self.icon = IconLabel(
            text="\uf0f3",  # Bell
            font_size=sp_scaled(24),
            height=dp_scaled(50),
        )

        self.icon.color = (0.6, 0.6, 0.6, 1)
        self.critical_messages = []
        self._overlay = None
        self._active = False
        
        # DEFAULTS
        self.title_text = "[font=FA]\uf00c[/font] [b]System Healthy[/b]"
        self.accent = (0, 0.8, 1, 0.4)        
        self.add_widget(self.icon)

    def update_from_frame(self, frame):
        self.critical_messages = self._find_critical_states(frame)
    
        if self.critical_messages:
            self.icon.color = (1, 0.2, 0.2, 1)
            self.title_text = "[font=FA]\uf057[/font] [b]Critical Messages[/b]"
            self.accent = (1, 0.25, 0.25, 0.6)
            self._active = True
        else:
            self.icon.color = (0.6, 0.6, 0.6, 1)
            self.title_text = "[font=FA]\uf00c[/font] [b]System Healthy[/b]"
            self.accent = (0, 0.8, 1, 0.4)
            self._active = False

    def _find_critical_states(self, data):
        found = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, str):
                    key_lower = key.lower()
                    if key_lower.endswith("_reason_1") or key_lower.endswith("_reason_2"):
                        val_lower = value.lower()
                        if (
                            val_lower.startswith("crit")
                            or val_lower.startswith("failsafe")
                            or "offline" in val_lower
                            or "error" in val_lower
                            or val_lower.startswith("fail")
                        ):
                            found.append(value)
                found.extend(self._find_critical_states(value))
        elif isinstance(data, list):
            for item in data:
                found.extend(self._find_critical_states(item))
        return found

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self._overlay:
            self.close_overlay()
        else:
            self.open_overlay()
        return True

    def open_overlay(self):
        # Instanziierung des ausgelagerten Overlays
        self._overlay = PushMessageOverlay(parent_icon=self)
        
        # Auf dem aktuellen Screen platzieren
        App.get_running_app().root.current_screen.add_widget(self._overlay)
    
    def close_overlay(self):
        if self._overlay and self._overlay.parent:
            self._overlay.parent.remove_widget(self._overlay)
        self._overlay = None

    def is_active(self):
        """Return True if there are critical messages (treated as active)."""
        return bool(self._active)