# main.py – EINZIG gültiger Startpunkt (basierend auf main_ui + core)
import os

os.environ["KIVY_NO_ARGS"] = "1"


import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(sys._MEIPASS)

    
import os
import sys
from kivy.app import App
from kivy.core.window import Window

# Icon -----
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(__file__)

Window.set_icon(
    os.path.join(BASE_DIR, "assets", "logo.png")
)

from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.metrics import dp, sp
from kivy.clock import Clock
# -------------------------------------------------------
# Screens & Logik-Module
# -------------------------------------------------------
from dashboard_gui.dashboard import DashboardScreen
from dashboard_gui.setup_screen import SetupScreen
from dashboard_gui.ui.debug_content.debug_screen import DebugScreen
from dashboard_gui.data_buffer import BUFFER
from dashboard_gui.ui.fullscreen_content.fullscreen_view import FullScreenView
from dashboard_gui.ui.device_picker_content.device_picker import DevicePickerScreen
from dashboard_gui.ui.csv_viewer_content.csv_viewer_screen import CSVViewerScreen
from dashboard_gui.settings_screen import SettingsScreen
from dashboard_gui.ui.cam_viewer_content.cam_viewer_screen import CamViewerScreen
from dashboard_gui.ui.about_content.about_screen import AboutScreen
from dashboard_gui.ui.vpd_scatter_screen_content.vpd_scatter_screen import VPDScatterScreen
from dashboard_gui.ui.sensor_mixed_mode_content.sensor_mixed_mode_screen import SensorMixedModeScreen
from dashboard_gui.ui.grow_controller_content.grow_controller_screen import GrowControllerScreen
from dashboard_gui.ui.i18n import I18N
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.plant_planner_content.plant_planner_screen import PlantPlannerScreen
from dashboard_gui.ui.grow_overview_content.grow_overview_screen import GrowOverviewScreen

import core


from dashboard_gui.global_state_manager import GLOBAL_STATE
from kivy.config import Config
Config.set('graphics', 'multisamples', '0')      # Weniger GPU-Last
Config.set('kivy', 'default_font', 'Roboto')     # Falls möglich

# -------------------------------------------------------
# FontAwesome sicher laden
# -------------------------------------------------------
FONT_PATH = os.path.join(
    os.path.dirname(__file__),
    "dashboard_gui", "assets", "fonts", "fa-solid-900.ttf"
)

if os.path.exists(FONT_PATH):
    LabelBase.register(name="FA", fn_regular=FONT_PATH)
else:
    print("⚠️ Font fehlt:", FONT_PATH)


# -------------------------------------------------------
# Buffer vor UI initialisieren
# -------------------------------------------------------
def init_buffer():
    BUFFER.load()
    if not BUFFER.data or not isinstance(BUFFER.data, list):
        BUFFER.data = []
    BUFFER.file_exists = True
    BUFFER.data_ok = True
    BUFFER.alive_flag = True


# -------------------------------------------------------
# Haupt-App (UI + Core)
# -------------------------------------------------------
class DashboardApp(App):

    def build(self):
        I18N.init()
        init_buffer()

        self.sm = ScreenManager(transition=FadeTransition())
        GLOBAL_STATE.bind_screen_manager(self.sm)

        # Alle Screens sofort hinzufügen
        screens = [
            GrowOverviewScreen(name="grow_overview"),
            CamViewerScreen(name="cam_viewer"),
            DashboardScreen(name="dashboard"),
            SetupScreen(name="setup"),
            AboutScreen(name="about"),
            SettingsScreen(name="settings"),
            FullScreenView(name="fullscreen"),
            DevicePickerScreen(name="device_picker"),
            CSVViewerScreen(name="csv_viewer"),
            VPDScatterScreen(name="vpd_scatter"),
            SensorMixedModeScreen(name="sensor_mixed_mode"),
            GrowControllerScreen(name="grow_controller"),
            PlantPlannerScreen(name="plant_planner"),
            DebugScreen(name="debug")
        ]

        for screen in screens:
            self.sm.add_widget(screen)
        
        self.sm.current = "dashboard"  # Start-Screen (für Entwicklung)
        
        return self.sm
    def on_start(self):
        core.start()
        # Kein Clock.schedule_once mehr für Screens nötig

    def on_pause(self):
        # nichts tun, nur resident bleiben
        return True

    def on_resume(self):
        print("[APP] RESUME")
    
        Clock.schedule_once(self._rebuild_dashboard_graphs, 0.85)
        core.stop()
        core.start()  # Immer ADV neu starten, damit die Verbindung wiederhergestellt wird
        core.stop_gatt_bridge()
        core.restart_gatt_bridge()
        # LOG
        return True
    
    def _rebuild_dashboard_graphs(self, dt):
        try:
            dashboard = self.root.get_screen("dashboard")
    
            for tile in dashboard.content.tile_map.values():
                tile.rebuild_graph()
    
        except Exception as e:
            print("[RESUME ERROR]", e)

# -------------------------------------------------------
# Offizieller Einstiegspunkt
# -------------------------------------------------------
def main():
    DashboardApp().run()


if __name__ == "__main__":
    main()
