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
from permission_fix import (
    ensure_permissions,
    offer_battery_optimization_exemption_once,
    startup_requirements_ready,
)

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


SCREEN_CLASSES = {
    "dashboard": DashboardScreen,
    "fullscreen": FullScreenView,
    "device_picker": DevicePickerScreen,
    "setup": SetupScreen,
    "grow_controller": GrowControllerScreen,
    "grow_overview": GrowOverviewScreen,
    "settings": SettingsScreen,
    "vpd_scatter": VPDScatterScreen,
    "sensor_mixed_mode": SensorMixedModeScreen,
    "plant_planner": PlantPlannerScreen,
    "cam_viewer": CamViewerScreen,
    "csv_viewer": CSVViewerScreen,
    "about": AboutScreen,
    "debug": DebugScreen,
}

STARTUP_PRELOAD_ORDER = (
    "fullscreen",
    "device_picker",
    "setup",
    "grow_controller",
)


def init_buffer():
    t_buf = time.perf_counter()
    BUFFER.load()
    if not BUFFER.data or not isinstance(BUFFER.data, list):
        BUFFER.data = []
    BUFFER.file_exists = True
    BUFFER.data_ok = True
    BUFFER.alive_flag = True
    print(f"[PERF] Buffer initialisiert/geladen in: {time.perf_counter() - t_buf:.4f}s")


def create_profiled_screen(screen_class, name):
    print(f"[PERF][SCREEN] START {name}")
    started_at = time.perf_counter()
    screen = screen_class(name=name)
    duration = time.perf_counter() - started_at
    print(f"[PERF][SCREEN] END {name}: {duration:.4f}s")
    return screen


class DashboardApp(App):

    def build(self):
        print("[PERF] App.build() aufgerufen.")
        self._core_started = False
        
        # 1. I18N und Buffer
        t_i18n = time.perf_counter()
        I18N.init()
        print(f"[PERF] I18N initialisiert in: {time.perf_counter() - t_i18n:.4f}s")
        
        init_buffer()

        # 2. ScreenManager
        self.sm = ScreenManager(transition=FadeTransition())
        GLOBAL_STATE.bind_screen_manager(self.sm)

        # Nur die erste sichtbare Oberfläche blockiert den Start.
        dashboard_started_at = time.perf_counter()
        self.ensure_screen("dashboard")
        self.sm.current = "dashboard"
        self._startup_preload_queue = list(STARTUP_PRELOAD_ORDER)
        print(f"[PERF] Initiales Dashboard bereit in: {time.perf_counter() - dashboard_started_at:.4f}s")
        return self.sm

    def ensure_screen(self, name):
        if self.sm.has_screen(name):
            return self.sm.get_screen(name)

        screen_class = SCREEN_CLASSES.get(name)
        if screen_class is None:
            raise KeyError(f"Unbekannter Screen: {name}")

        screen = create_profiled_screen(screen_class, name)
        self.sm.add_widget(screen)
        return screen

    def _preload_next_screen(self, _dt):
        while self._startup_preload_queue:
            name = self._startup_preload_queue.pop(0)
            if self.sm.has_screen(name):
                continue
            print(f"[PERF][PRELOAD] START {name}")
            self.ensure_screen(name)
            print(f"[PERF][PRELOAD] END {name}")
            break

        if self._startup_preload_queue:
            Clock.schedule_once(self._preload_next_screen, 0.15)

    def on_start(self):
        # Erst die sichtbare UI liefern, dann den Android-Permission-Flow starten.
        Clock.schedule_once(self._ensure_startup_permissions, 0.20)

        # Gesamte Bootzeit bis zur sichtbaren UI
        total_time = time.perf_counter() - START_TIME
        print(f"[PERF] 🚀 GESAMTZEIT BIS ZUM UI-START: {total_time:.4f}s 🚀")
        Clock.schedule_once(self._preload_next_screen, 0.35)

    def _ensure_startup_permissions(self, _dt):
        ensure_permissions(self._start_core_once)

    def _start_core_once(self):
        if self._core_started:
            return

        t_core = time.perf_counter()
        core.start()
        self._core_started = True
        print(f"[PERF] core.start() nach Freigabe in: {time.perf_counter() - t_core:.4f}s")
        offer_battery_optimization_exemption_once()

    def on_pause(self):
        return True

    def on_resume(self):
        print("[APP] RESUME")
        Clock.schedule_once(self._rebuild_dashboard_graphs, 0.85)
        Clock.schedule_once(self._resume_after_permission_check, 0.12)
        return True

    def _resume_after_permission_check(self, _dt):
        if self._core_started and not startup_requirements_ready():
            core.stop()
            self._core_started = False

        ensure_permissions(self._continue_after_resume)

    def _continue_after_resume(self):
        if not self._core_started:
            self._start_core_once()
            return

        # Android kann den BLE-Scan beim Activity-Wechsel pausieren. Ein kleiner
        # ADV-Neustart genuegt; Service und kompletter Core bleiben unangetastet.
        core.restart_adv_bridge()
    
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
