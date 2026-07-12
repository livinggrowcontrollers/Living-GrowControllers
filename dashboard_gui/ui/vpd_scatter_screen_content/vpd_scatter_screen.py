from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.graphics import Rectangle, Color, Ellipse
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.anchorlayout import AnchorLayout
from kivy_garden.graph import Graph
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.common.buttons.control_buttons import ControlButtons
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
import math
import time

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class VPDScatterScreen(Screen):


    """
    VPD Scatter – FINAL STABLE VERSION
    - Keine Garden-Plots
    - Punkte via Canvas (Ellipse)
    - Graph nur als Koordinaten-Referenz
    """
    name = "vpd_scatter" # <--- Unverzicht
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.gsm = GLOBAL_STATE


        # -------------------------------------------------
        # ROOT
        # -------------------------------------------------
        self.main = BoxLayout(orientation="vertical")
        self.add_widget(self.main)
        # -------------------------------------------------
        # VPD BACKGROUND MODES
        # -------------------------------------------------
        self._vpd_bgs = {
            "default": "dashboard_gui/assets/vpd_bg.png",
            "seedling": "dashboard_gui/assets/vpd_bg.png",
            "veg": "dashboard_gui/assets/vpd_bg.png",
            "flower": "dashboard_gui/assets/vpd_bg.png",
        }

        self._active_bg = "default"

        # -------------------------------------------------
        # HEADER
        # -------------------------------------------------
        app = App.get_running_app()

        self.header = HeaderBar()

        self.main.add_widget(self.header)

        self.header.enable_back()
        self.gsm.ui_handler.attach_screen("vpd_scatter", self)
        self._reset_active = False

        # -------------------------------------------------
        # CONTENT
        # -------------------------------------------------
        self.content = FloatLayout()

        # -------------------------------------------------
        # BG SWITCH MENU (TOP-LEFT)
        # -------------------------------------------------
        from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
        from kivy.uix.button import Button

        self.bg_menu = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            height=dp_scaled(36),
            spacing=dp_scaled(6),
            pos_hint={"x": 0, "top": 1},
            padding=(dp_scaled(8), dp_scaled(8))
        )

        def mk_bg_btn(txt, key):
            btn = Button(
                text=txt,
                size_hint=(None, None),
                size=(dp_scaled(90), dp_scaled(32)),
                font_size=sp_scaled(16),
                # background_normal leer lassen, damit unsere background_color wirkt
                background_normal='',
                # Standardzustand: 0.45 Alpha
                background_color=(0.05, 0.05, 0.05, 0.45),
                on_release=lambda *_: self._set_vpd_bg(key)
            )
        
            # Feedback-Logik: Beim Drücken wird der Button etwas heller/weniger transparent
            def on_state(instance, value):
                if value == 'down':
                    # Hellerer Zustand beim Drücken (0.7 Alpha)
                    instance.background_color = (0.2, 0.2, 0.2, 0.7)
                else:
                    # Zurück zum HUD-Style (0.45 Alpha)
                    instance.background_color = (0.05, 0.05, 0.05, 0.45)
        
            btn.bind(state=on_state)
            return btn

        self.bg_menu.add_widget(mk_bg_btn("Default", "default"))
        self.bg_menu.add_widget(mk_bg_btn("Seedling", "seedling"))
        self.bg_menu.add_widget(mk_bg_btn("Veg", "veg"))
        self.bg_menu.add_widget(mk_bg_btn("Flower", "flower"))

        self.content.add_widget(self.bg_menu)

        # -------------------------------------------------
        # VALUE MIRROR BOX (RECHTS) - VERGRÖSSERT
        # -------------------------------------------------
        
        self.value_box = AnchorLayout(
            anchor_x="right",
            anchor_y="top",
            size_hint=(1, 1),
            width=dp_scaled(350), # 💡 Leicht erhöht für mehr Spielraum rechts
            padding=(dp_scaled(12), dp_scaled(72), dp_scaled(12), dp_scaled(12))
        )
        
        self.value_label = Label(
            text="",
            size_hint=(0.45, None),   # 💡 Erhöht von 0.25 auf 0.45 (ca. 45% der Breite)
            halign="left",
            valign="middle",
            markup=True,
            font_size=sp_scaled(26),  # 💡 Schriftgröße erhöht von 20 auf 26
            padding=(dp_scaled(15), dp_scaled(15)) # 💡 Innenabstand hinzugefügt, damit der Text nicht am Rand klebt
        )
        
        # 🔑 Auto-Höhe nach Text (beachtet jetzt auch das Padding)
        self.value_label.bind(
            texture_size=lambda instance, value: setattr(instance, 'height', value[1] + instance.padding[1] * 2)  
        )
        
        with self.value_label.canvas.before:
            # Hintergrund – deutlich transparenter
            Color(0.00, 0.00, 0.00, 0.15)
            self._value_bg = RoundedRectangle(radius=[dp_scaled(14)])
        
            # Border – sehr subtil, fast HUD-like
            Color(0.8, 0.8, 0.8, 0.18)
            self._value_border = RoundedRectangle(radius=[dp_scaled(14)], width=1.0)
        
        self.value_label.bind(pos=self._sync_value_box, size=self._sync_value_box)
        
        self.value_box.add_widget(self.value_label)
        self.content.add_widget(self.value_box)
        self.main.add_widget(self.content)
        self._mirror = {
            "in": {"t": None, "h": None, "vpd": None},
            "ex": {"t": None, "h": None, "vpd": None},
        }
        # -------------------------------------------------
        # BACKGROUND (PNG = ACHSEN)
        # -------------------------------------------------
        with self.content.canvas.before:
            self.bg_rect = Rectangle(
                texture=CoreImage(
                    "dashboard_gui/assets/vpd_bg.png"
                ).texture,
                size=self.content.size,
                pos=self.content.pos,
            )
        self.content.bind(size=self._update_bg, pos=self._update_bg)

        # -------------------------------------------------
        # GRAPH (NUR KOORDINATEN!)
        # -------------------------------------------------
        self.graph = Graph(
            xmin=15,   # Humidity %
            xmax=120,
            ymin=0,    # Temperatur °C
            ymax=40,
            draw_border=False,
            background_color=(0, 0, 0, 0),
            tick_color=(0, 0, 0, 0),
            padding=0,
        )
        self.content.add_widget(self.graph)

        self.graph.bind(size=self._sync_graph, pos=self._sync_graph)
        self.content.bind(size=self._sync_graph, pos=self._sync_graph)

        # SCATTER POINTS (CANVAS)
        # -------------------------------------------------
        with self.graph.canvas.after:
            # INTERN (Gelb)
            Color(1.0, 0.85, 0.2, 0.85)
            self.p_in = Ellipse(size=(30, 30), pos=(-1000, -1000))

            # EXTERN (Grün)
            Color(0.3, 1.0, 0.3, 0.85)
            self.p_ex = Ellipse(size=(30, 30), pos=(-1000, -1000))

            # --- NEU: BLE outside (Pink/Magenta) ---
            Color(1.0, 0.2, 0.6, 0.85)
            self.p_outside = Ellipse(size=(30, 30), pos=(-1000, -1000))

            # --- NEU: BLE inside (Cyan/Hellblau) ---
            Color(0.2, 0.8, 1.0, 0.85)
            self.p_inside = Ellipse(size=(30, 30), pos=(-1000, -1000))
        # -------------------------------------------------
        # CONTROL BUTTONS
        # -------------------------------------------------
        self.controls = ControlButtons()
        self.controls.size_hint = (1, None)
        self.controls.height = dp_scaled(40)
        self.controls.pos_hint = {'y': 0}
        self.main.add_widget(self.controls)

        Clock.schedule_interval(self._tick, 1.0)

    # -------------------------------------------------
    # LAYOUT SYNC
    # -------------------------------------------------
    def _update_bg(self, *_):
        header_h = dp(45) # Die Höhe deines Headers
        # Das Bild startet erst unter dem Header
        self.bg_rect.pos = (self.content.pos[0], self.content.pos[1])
        # Das Bild ist genau so groß wie der Content-Bereich
        self.bg_rect.size = (self.content.size[0], self.content.size[1])

    def _sync_graph(self, *_):
        self.graph.size = self.content.size
        self.graph.pos = self.content.pos

    def _sync_value_box(self, *_):
        self._value_bg.size = self.value_label.size
        self._value_bg.pos = self.value_label.pos
        self._value_border.size = self.value_label.size
        self._value_border.pos = self.value_label.pos
    def _last_float(self, buf):
        if not buf:
            return None
        v = buf[-1]
        return float(v) if v is not None else None    
    def _temp_from_vpd_rh(self, vpd, rh):
        if vpd <= 0 or rh <= 0 or rh >= 100:
            return None
    
        es = vpd / (1.0 - rh / 100.0)
        L = math.log(es / 0.6108)
        return (237.3 * L) / (17.27 - L)
    def _set_vpd_bg(self, key):
        path = self._vpd_bgs.get(key)
        if not path:
            return

        self.bg_rect.texture = CoreImage(path).texture
        self._active_bg = key

    # -------------------------------------------------
    # DATA LOAD
    # -------------------------------------------------
    def _load_points(self):
        idx = self.gsm.get_active_index()
        dev_list = self.gsm.get_device_list()
        if not dev_list or idx >= len(dev_list): 
            return
    
        dev_id = dev_list[idx]
        ch = self.gsm.get_active_channel()
        prefix = f"{dev_id}_{ch}"
    
        def get_last(metric):
            buf = self.gsm.get_graph_data(f"{prefix}_{metric}")
            if not buf or buf[-1] is None:
                return None
            val = float(buf[-1])
            # Check auf Pseudo-Werte (Sensor nicht erkannt)
            if val < -250: 
                return None
            return val
    
        # Daten sammeln
        self._box = {
            "in":  {"t": get_last("temp_in"),  "h": get_last("hum_in"),  "vpd": get_last("vpd_in")},
            "ex":  {"t": get_last("temp_ex"),  "h": get_last("hum_ex"),  "vpd": get_last("vpd_ex")},
            "outside": {"t": get_last("ble_temp_outside"), "h": get_last("ble_hum_outside"), "vpd": get_last("ble_vpd_outside")},
            "inside": {"t": get_last("ble_temp_inside"), "h": get_last("ble_hum_inside"), "vpd": get_last("ble_vpd_inside")}
        }
        
        # Koordinaten für Scatter (X=Hum, Y=Temp)
        coords = {
            "in":  (get_last("vpd_x_in"),  get_last("vpd_y_in")),
            "ex":  (get_last("vpd_x_ex"),  get_last("vpd_y_ex")),
            "outside": (get_last("vpd_x_outside"), get_last("vpd_y_outside")),
            "inside": (get_last("vpd_x_inside"), get_last("vpd_y_inside"))
        }

        # Canvas Mapping
        mapping = {"in": self.p_in, "ex": self.p_ex, "outside": self.p_outside, "inside": self.p_inside}

        for key, ellipse in mapping.items():
            hx, ty = coords[key]
            if hx is not None and ty is not None:
                self._place_point(ellipse, ty, hx)
            else:
                ellipse.pos = (-1000, -1000)
    
        self._update_value_box()
   # -------------------------------------------------
    def _place_point(self, ellipse, temp, hum):
        gx, gy = self.graph.pos
        gw, gh = self.graph.size
    
        xr = max(self.graph.xmax - self.graph.xmin, 0.0001)
        yr = max(self.graph.ymax - self.graph.ymin, 0.0001)
    
        # clamp
        hum = min(max(hum, self.graph.xmin), self.graph.xmax)
        temp = min(max(temp, self.graph.ymin), self.graph.ymax)
    
        # X = Humidity → rechts
        x = gx + (hum - self.graph.xmin) / xr * gw
    
        # Y = Temperatur → oben heiß, unten kalt (invertiert)
        y = gy + (1.0 - (temp - self.graph.ymin) / yr) * gh
    
        ellipse.pos = (
            x - ellipse.size[0] / 2,
            y - ellipse.size[1] / 2
        )
    # -------------------------------------------------
    # GSM UPDATE
    # -------------------------------------------------
    def update_from_global(self, d):
        self.header.update_from_global(d)
        self._load_points()

    def _tick(self, *_):
        pass
    def _update_value_box(self):
        def fmt(v, unit="", precision=1):
            """Hilfsfunktion für saubere Formatierung."""
            if v is None or v < -250:  # Pseudo-Werte Check
                return "--"
            return f"{v:.{precision}f}{unit}"

        b = getattr(self, "_box", None)
        if not b: 
            return

        # Farbcodes (RGBA Hex)
        c_in  = "FFD933FF" # Gelb
        c_ex  = "4DFF4DFF" # Grün
        c_outside = "FF3399FF" # Pink
        c_inside = "33CCFFFF" # Cyan
        
        lines = []
        
        # Mapping der Sensoren für die Schleife (Key, Label, Farbe)
        sensors = [
            ("in",  "INTERN", c_in),
            ("ex",  "EXTERN", c_ex),
            ("outside", "BLE-Outside", c_outside),
            ("inside", "BLE-Inside", c_inside)
        ]

        for key, name, color in sensors:
            vpd = fmt(b[key]['vpd'], "k", 2)
            t   = fmt(b[key]['t'], "°")
            h   = fmt(b[key]['h'], "%")
            
            # Die Zeile: Punkt | Name | VPD | T/H
            dot = f"[font=FA][color=#{color}]\uf111[/color][/font]"

            line = (
                f"{dot} [b]{name}:[/b] {vpd} "
                f"[size={int(sp_scaled(15))}]({t}/{h})[/size]"
            )
            lines.append(line)

        # Zusammenfügen mit Zeilenumbruch
        self.value_label.text = "\n".join(lines)

    # -------------------------------------------------
    # RESET
    def reset_from_global(self):
        print("[DASHBOARD] Suche Tiles zum Resetten...")

        # Wir gehen durch ALLE Widgets im Dashboard
        for widget in self.walk():
            # Wenn das Widget eine 'reset' Methode hat (wie deine ChartTiles), ruf sie auf!
            if hasattr(widget, 'reset') and callable(widget.reset):
                widget.reset()

        # Header separat (da dieser meist kein ChartTile ist)
        if hasattr(self, 'header'):
            self.header.set_clock("--:--")
            self.header.set_rssi(None)