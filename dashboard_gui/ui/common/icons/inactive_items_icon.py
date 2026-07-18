# dashboard_gui/ui/common/inactive_devices_icon.py

from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.inactive_items_overlay import InactiveItemsOverlay
from dashboard_gui.ui.common.header_capabilities import build_header_capabilities

class InactiveItemsIcon(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint = (None, 1)
        self.width = dp_scaled(50)
        self.icon = IconLabel(text="\uf142", font_size=sp_scaled(20))
        self.icon.color = (0.6, 0.6, 0.6, 1)
        self.add_widget(self.icon)
        self._overlay = None
        self.inactive_items = []

    def update_items(self, items):
        self.inactive_items = items or []
        if self.inactive_items:
            self.icon.color = (0.2, 0.6, 1, 1)
        else:
            self.icon.color = (0.6, 0.6, 0.6, 1)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self._overlay:
            self.close_overlay()
        else:
            self.open_overlay()
        return True

    def open_overlay(self):
        if not self.inactive_items:
            return
        
        self._overlay = InactiveItemsOverlay(parent_icon=self, inactive_items=self.inactive_items)
        App.get_running_app().root.current_screen.add_widget(self._overlay)

    def close_overlay(self):
        if self._overlay and self._overlay.parent:
            self._overlay.parent.remove_widget(self._overlay)
        self._overlay = None

    def is_active(self):
        return bool(self.inactive_items)
    

    def update_from_header(self, header):
        items = []
        widgets = header.capability_widgets
        for capability in build_header_capabilities(header._state, header.push_message.is_active()):
            widget = widgets[capability["id"]]
            if not capability["enabled"]:
                items.append((capability["label"], capability["icon"], "FA", capability["color"]))
                widget.opacity = 0
                widget.disabled = True
                widget.width = 0
            else:
                widget.opacity = 1
                widget.disabled = False
                widget.width = dp_scaled(70) if capability["id"] == "battery" else dp_scaled(75) if capability["id"] in {"external", "external2"} else dp_scaled(40)

        # --- ICON SELBST ---
        self.update_items(items)

        if items:
            self.opacity = 1
            self.disabled = False
            self.width = dp_scaled(40)
        else:
            self.opacity = 0
            self.disabled = True
            self.width = 0
