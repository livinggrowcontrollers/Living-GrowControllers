# dashboard_gui/settings_screen.py
# -*- coding: utf-8 -*-
"""
SettingsScreen – zentrale Einstellungsseite
© 2025-2026 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from dashboard_gui import ui
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.settings_content.settings_main_panel import SettingsMainPanel
import config
from kivy.metrics import dp
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

from dashboard_gui.ui.i18n import I18N

class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        # Root Layout
        root = BoxLayout(orientation="vertical")

        # Attach to global state
        GLOBAL_STATE.ui_handler.attach_screen("settings", self)

        # Header Bar
        self.header = HeaderBar()
 
        root.add_widget(self.header)

        # Settings Panel
        panel = SettingsMainPanel(
            on_save=self._save,
            on_cancel=self._cancel
        )
        # Set current language
        I18N.init()
        panel_inputs = panel.inputs  # Zugriff auf Inputs falls nötig
        root.add_widget(panel)

        self.add_widget(root)


    # -----------------------------
    # Save Handler - FINAL VERSION
    # -----------------------------
    def _save(self, values: dict):
        cfg = config._init()
    
        cfg["refresh_interval"] = float(values.get("refresh_interval", 0.1))
        cfg["graph_refresh_interval"] = float(
            values.get("graph_refresh_interval", 15.0)
        )

        cfg["graph_resolution"] = float(values.get("graph_resolution", 80.0))
        cfg["stale_timeout"] = float(values.get("stale_timeout", 15.0))
        cfg["tile_graph_window"] = int(values.get("tile_graph_window", 400))
        cfg["graph_smoothing_factor"] = float(values.get("graph_smoothing_factor", 1))
        
        cfg["temperature_offset"] = float(values.get("temperature_offset", 0.0))
        cfg["humidity_offset"] = float(values.get("humidity_offset", 0.0))
        cfg["leaf_offset"] = float(values.get("leaf_offset", 0.0))
        cfg["temperature_unit"] = values.get("temperature_unit", "C")
        config.set_theme(values.get("theme", config.get_theme()))
    
        # LGS Mesh
        cfg["lgs_mesh_channel_send"] = int(values.get("lgs_mesh_channel_send", 17))
        cfg["lgs_mesh_channel_recv"] = int(values.get("lgs_mesh_channel_recv", 17))
        config.save(cfg)
        config.reload()

        from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
        MetricRegistry.reload()
        self._refresh_metric_theme()
    
        # ---------------------------------
        # Watchdog Live Update
        # ---------------------------------
        from core import _ble_watchdog
        if _ble_watchdog and hasattr(_ble_watchdog, "set_timeout"):
            _ble_watchdog.set_timeout(cfg["stale_timeout"])
            print(f"[SETTINGS] Watchdog stale_timeout → {cfg['stale_timeout']}")
    
        # ---------------------------------
        # GSM LIVE SYNC (Graph + Interval)
        # ---------------------------------
        GLOBAL_STATE.engine.refresh_settings()
    
        # ---------------------------------
        # Hardware Restart (Mesh)
        # ---------------------------------
        import core
        from platform_utils import is_android

        if is_android():
            print("[SETTINGS] Restart LGS Mesh Bridges")
            core.restart_adv_bridge()
            core.restart_broadcast_bridge()
    
        print("[SETTINGS] Save completed")
        GLOBAL_STATE.ui_handler.go_back() # Geht zurück zum Dashboard (oder vorheriger Screen)

    def _refresh_metric_theme(self):
        """Apply the newly saved metric palette without restarting the app."""
        dashboard = GLOBAL_STATE.ui_handler.get_screen("dashboard")
        if dashboard and hasattr(dashboard, "content"):
            dashboard.content.refresh_metric_theme()

        fullscreen = GLOBAL_STATE.ui_handler.get_screen("fullscreen")
        if fullscreen and getattr(fullscreen, "current_key", None):
            fullscreen.activate_tile(fullscreen.current_key)

        grow_overview = GLOBAL_STATE.ui_handler.get_screen("grow_overview")
        if grow_overview and hasattr(
            grow_overview,
            "refresh_metric_theme",
        ):
            grow_overview.refresh_metric_theme()
        
    # -----------------------------
    # Cancel Handler
    # -----------------------------
    def _cancel(self, *_):
        print("[SETTINGS] Cancel - no changes saved")
        GLOBAL_STATE.ui_handler.go_back() # Geht zurück zum Dashboard (oder vorheriger Screen)  

    # -----------------------------
    # Update UI from global state
    # -----------------------------
    def update_from_global(self, data):
        self.header.update_from_global(data)
        self.header._last_frame = data
