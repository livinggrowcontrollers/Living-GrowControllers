import os
import sys
import time

# --- START DER ZEITMESSUNG ---
START_TIME = time.perf_counter()
print(f"[PERF] ===== STARTUP DIAGNOSTIC INITIALIZED =====")

os.environ["KIVY_NO_ARGS"] = "1"

if getattr(sys, "frozen", False):
    os.chdir(sys._MEIPASS)

# Basis-Verzeichnis ermitteln
BASE_DIR = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(__file__)

# Kivy Basis-Imports (so schlank wie möglich halten für den Start)
t_kivy_start = time.perf_counter()
from kivy.app import App
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.config import Config
print(f"[PERF] Kivy Basis-Core geladen in: {time.perf_counter() - t_kivy_start:.4f}s")

# Grafik-Config setzen
Config.set('graphics', 'multisamples', '0')
Config.set('kivy', 'default_font', 'Roboto')

# Icon setzen
Window.set_icon(os.path.join(BASE_DIR, "assets", "logo.png"))

# FontAwesome laden
FONT_PATH = os.path.join(BASE_DIR, "dashboard_gui", "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FONT_PATH):
    LabelBase.register(name="FA", fn_regular=FONT_PATH)
else:
    print("[PERF] ⚠️ Font fehlt:", FONT_PATH)

# --- SCHWERE IMPORTS MESSEN ---
t_imports_start = time.perf_counter()

# Basis-Module importieren
from dashboard_gui.data_buffer import BUFFER
from dashboard_gui.ui.i18n import I18N
from dashboard_gui.global_state_manager import GLOBAL_STATE
import core

# Die 14 Screens importieren (Hier liegt oft der Flaschenhals!)
print("[PERF] Starte Import der 14 Screens...")
from dashboard_gui.ui.grow_overview_content.grow_overview_screen import GrowOverviewScreen
from dashboard_gui.ui.cam_viewer_content.cam_viewer_screen import CamViewerScreen
from dashboard_gui.dashboard import DashboardScreen
from dashboard_gui.setup_screen import SetupScreen
from dashboard_gui.ui.about_content.about_screen import AboutScreen
from dashboard_gui.settings_screen import SettingsScreen
from dashboard_gui.ui.fullscreen_content.fullscreen_view import FullScreenView
from dashboard_gui.ui.device_picker_content.device_picker import DevicePickerScreen
from dashboard_gui.ui.csv_viewer_content.csv_viewer_screen import CSVViewerScreen
from dashboard_gui.ui.vpd_scatter_screen_content.vpd_scatter_screen import VPDScatterScreen
from dashboard_gui.ui.sensor_mixed_mode_content.sensor_mixed_mode_screen import SensorMixedModeScreen
from dashboard_gui.ui.grow_controller_content.grow_controller_screen import GrowControllerScreen
from dashboard_gui.ui.plant_planner_content.plant_planner_screen import PlantPlannerScreen
from dashboard_gui.ui.debug_content.debug_screen import DebugScreen

print(f"[PERF] Alle Module & Screens importiert in: {time.perf_counter() - t_imports_start:.4f}s")


def init_buffer():
    t_buf = time.perf_counter()
    BUFFER.load()
    if not BUFFER.data or not isinstance(BUFFER.data, list):
        BUFFER.data = []
    BUFFER.file_exists = True
    BUFFER.data_ok = True
    BUFFER.alive_flag = True
    print(f"[PERF] Buffer initialisiert/geladen in: {time.perf_counter() - t_buf:.4f}s")


class DashboardApp(App):

    def build(self):
        print("[PERF] App.build() aufgerufen.")
        
        # 1. I18N und Buffer
        t_i18n = time.perf_counter()
        I18N.init()
        print(f"[PERF] I18N initialisiert in: {time.perf_counter() - t_i18n:.4f}s")
        
        init_buffer()

        # 2. ScreenManager
        self.sm = ScreenManager(transition=FadeTransition())
        GLOBAL_STATE.bind_screen_manager(self.sm)

        # 3. Screens instanziieren (Massiver Performance-Fresser beim Start!)
        t_screens = time.perf_counter()
        
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
        
        print(f"[PERF] Alle 14 Screens instanziiert und hinzugefügt in: {time.perf_counter() - t_screens:.4f}s")
        
        self.sm.current = "dashboard"
        return self.sm

    def on_start(self):
        t_core = time.perf_counter()
        core.start()
        print(f"[PERF] core.start() ausgeführt in: {time.perf_counter() - t_core:.4f}s")
        
        # Gesamte Bootzeit bis zum ersten Frame
        total_time = time.perf_counter() - START_TIME
        print(f"[PERF] 🚀 GESAMTZEIT BIS ZUM START: {total_time:.4f}s 🚀")

    def on_pause(self):
        return True

    def on_resume(self):
        print("[APP] RESUME")
        Clock.schedule_once(self._rebuild_dashboard_graphs, 0.85)
        core.stop()
        core.start()
        core.stop_gatt_bridge()
        core.restart_gatt_bridge()
        return True
    
    def _rebuild_dashboard_graphs(self, dt):
        try:
            dashboard = self.root.get_screen("dashboard")
            for tile in dashboard.content.tile_map.values():
                tile.rebuild_graph()
        except Exception as e:
            print("[RESUME ERROR]", e)


def main():
    DashboardApp().run()


if __name__ == "__main__":
    main()