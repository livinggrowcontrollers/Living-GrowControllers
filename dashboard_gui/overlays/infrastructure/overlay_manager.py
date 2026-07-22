# dashboard_gui/overlays/infrastructure/overlay_manager.py

from .contracts import OverlayKey


class OverlayManager:
    """Own exactly one active control overlay for the application."""

    _LEGACY_ATTRS = {
        "light": "active_light_overlay",
        "circulation": "active_circulation_fan_overlay",
        "exhaust": "active_exhaust_fan_overlay",
        "climate_hub": "active_climate_hub_overlay",
    }

    def __init__(self, ui_manager):
        self.ui_manager = ui_manager
        self.active_key = None
        self.active_overlay = None

    def open(self, key, factory, host):
        if not isinstance(key, OverlayKey):
            key = OverlayKey(*key) if isinstance(key, tuple) else OverlayKey(str(key))

        if self.active_overlay is not None:
            if self.active_key == key:
                self.active_overlay.close()
                return None
            self.active_overlay.close()

        overlay = factory()
        self.active_key = key
        self.active_overlay = overlay
        self._sync_legacy_refs(overlay, key)
        host.add_widget(overlay)
        return overlay

    def close_active(self):
        if self.active_overlay is not None:
            self.active_overlay.close()

    def unregister(self, overlay):
        if overlay is not self.active_overlay:
            return
        self.active_overlay = None
        self.active_key = None
        self._sync_legacy_refs(None, None)

    def _sync_legacy_refs(self, overlay, key):
        for attr in self._LEGACY_ATTRS.values():
            setattr(self.ui_manager, attr, None)
        if overlay is not None and key is not None:
            attr = self._LEGACY_ATTRS.get(key.kind)
            if attr:
                setattr(self.ui_manager, attr, overlay)
