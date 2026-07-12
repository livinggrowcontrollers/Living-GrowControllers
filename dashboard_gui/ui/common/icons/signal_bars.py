from kivy.uix.boxlayout import BoxLayout
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from kivy.uix.label import Label
from kivy.graphics import Rectangle, Color

from kivy.app import App
import os
from kivy.uix.image import Image
ASSET_ROOT = os.path.join("dashboard_gui", "assets")

# -------------------------------------------------------
# Signal Bars (PNG Version)
# -------------------------------------------------------
# --- NACHHER (OPTIMIERT) ---
class SignalBars(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint = (None, 1)
        self.width = dp_scaled(40)  # Fixed breite
        self.padding = [0, dp_scaled(2)]  # Oben/Unten Padding für bessere Proportion
        self.img = Image(
            fit_mode="contain",
            keep_ratio=True,
            size_hint=(1, 1),
            pos_hint={'center_y': 0.5}
        )
        self.add_widget(self.img)

        # absoluter Pfad zu /dashboard_gui/assets/icons/signal
        # Nutzt den Projektordner als Basis (unabhängig davon, wo diese Datei liegt)
        self._icon_dir = os.path.abspath(
            os.path.join("dashboard_gui", "assets", "icons", "signal")
        )

        # Default: kein Signal
        self.set_rssi(None)

    def _panel_bg(self, panel):
        panel.canvas.before.clear()
        with panel.canvas.before:
            Color(0.05,0.05,0.08,0.95)
            Rectangle(pos=panel.pos,size=panel.size)
    def _close_signal_overlay(self):
        if self._signal_overlay and self._signal_overlay.parent:
            self._signal_overlay.parent.remove_widget(self._signal_overlay)
        self._signal_overlay = None

    def _pick_icon(self, level):
        """level = 0..5"""
        fn = f"signal{level}.png"
        p = os.path.join(self._icon_dir, fn)
        return p if os.path.exists(p) else ""

    def set_rssi(self, rssi):
        """RSSI → 0..5 Balken"""
        try:
            rssi = float(rssi)
        except:
            level = 0
            self.img.source = self._pick_icon(level)
            return

        # Abstufungen (anpassbar)
        if rssi >= -55:
            level = 5
        elif rssi >= -65:
            level = 4
        elif rssi >= -75:
            level = 3
        elif rssi >= -85:
            level = 2
        elif rssi >= -95:
            level = 1
        else:
            level = 0

        self.img.source = self._pick_icon(level)
        self.img.reload()

