# dashboard_gui/ui/common/inactive_devices_icon.py

from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
from dashboard_gui.ui.common.icons.icon_label import IconLabel
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.inactive_items_overlay import InactiveItemsOverlay

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
        state = header._state
        items = []

        def get_icon_props(widget, default_char=""):
            target = getattr(widget, 'icon', widget)
            return (
                getattr(target, 'text', default_char),
                getattr(target, 'font_name', 'FA'),
                getattr(target, 'color', (0.6, 0.6, 0.6, 1))
            )

        def handle(widget, is_active, name, default_icon, width):
            if not is_active:
                t, f, c = get_icon_props(widget, default_icon)
                items.append((name, t, f, c))
                widget.opacity = 0
                widget.disabled = True
                widget.width = 0
            else:
                widget.opacity = 1
                widget.disabled = False
                widget.width = width

        # --- LOGIK ---
        handle(header.light, state.get("light") is not None, "Light Control", "\uf0eb", dp_scaled(40))

        handle(header.circulation_fan, state.get("circulation_fan_rpm") is not None,
            "Circulation Fan", "\uf863", dp_scaled(40))

        handle(header.exhaust_fan, state.get("exhaust_fan_rpm") is not None,
            "Exhaust Fan", "\uf863", dp_scaled(40))

        handle(header.btn_broadcast, state.get("broadcast_available"),
            "Broadcast", "\uf09e", dp_scaled(40))

        handle(header.battery, state.get("battery") is not None,
            "Battery", "\uf244", dp_scaled(70))

        handle(header.external, state.get("external"),
            "External Sensor", "\uf2c9", dp_scaled(75))

        handle(header.external2, state.get("external2"),
            "External Sensor 2", "\uf2c9", dp_scaled(75))

        handle(header.climate_hub, state.get("climate_hub"),
            "Climate Hub", "\uf0c2", dp_scaled(40))

        # Push separat (weil Methode)
        push_active = getattr(header.push_message, 'is_active', lambda: False)()
        handle(header.push_message, push_active,
            "Push Messages", "\uf0f3", dp_scaled(40))

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