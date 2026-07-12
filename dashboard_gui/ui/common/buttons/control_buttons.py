from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.graphics import Color, Rectangle
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.i18n import I18N
from kivy.graphics import Rectangle, Color, RoundedRectangle, Line

class ControlButtons(BoxLayout):
    on_start = ObjectProperty(None, allownone=True)
    on_stop  = ObjectProperty(None, allownone=True)
    on_reset = ObjectProperty(None, allownone=True)
    running = BooleanProperty(False)

    # --- EDLES INDUSTRIAL DESIGN KONFIGURATION ---
    # Tiefer, edler Anthrazit-Farbton für die Leiste (passend zur Future Vision)
    BG_COLOR = (0.05, 0.05, 0.06, 0.9) 
    
    # Premium Muted Colors (Dezent matt, hohe Transparenz für den Glass-Look)
    COLOR_START = (0.15, 0.45, 0.25, 0.35)  # Soft Transparentes Grün
    COLOR_STOP  = (0.55, 0.18, 0.22, 0.35)  # Soft Transparentes Rot
    COLOR_RESET = (0.20, 0.22, 0.28, 0.40)  # Edles, gedimmtes Slate-Grau/Blau

    TXT_START = "control.start"
    TXT_STOP  = "control.stop"
    TXT_RESET = "control.reset"

    def __init__(self, on_start=None, on_stop=None, on_reset=None, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)

        # Layout-Setup
        self.spacing = dp_scaled(14)  # Abstand zwischen den Buttons erhöhen für Air-Effekt
        self.padding = [dp_scaled(16), dp_scaled(8), dp_scaled(16), dp_scaled(8)]
        self.size_hint_y = None
        self.height = dp_scaled(55)

        # -------------------------------------------------
        # HINTERGRUND & TOP-BORDER (Trennlinie)
        # -------------------------------------------------
        with self.canvas.before:
            Color(*self.BG_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            
            # Subtile obere Trennlinie für maximale UI-Tiefe
            Color(1, 1, 1, 0.05)
            self.top_line = Line(points=[self.x, self.top, self.right, self.top], width=dp_scaled(1))
            
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.on_start = on_start
        self.on_stop  = on_stop
        self.on_reset = on_reset

        # -------------------------------------------------
        # BUTTONS INITIALISIEREN (Mit Canvas-Styling)
        # -------------------------------------------------
        # 1. Start/Stop Button
        self.btn_toggle = Button(
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0), # Native Farbe auf transparent schalten!
            markup=True,
            font_size=sp_scaled(15),
            size_hint=(0.5, 1),
            color=(1, 1, 1, 0.9)
        )

        # 2. Reset Button
        self.btn_reset = Button(
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0), # Native Farbe auf transparent schalten!
            markup=True,
            font_size=sp_scaled(15),
            size_hint=(0.5, 1),
            color=(1, 1, 1, 0.75),
            text=f"[font=FA]\uf021[/font]  {I18N.t(self.TXT_RESET)}"
        )

        # --- EIGENE ABGERUNDETE DESIGN-EBENEN AUF DIE BUTTONS LEGEN ---
        with self.btn_toggle.canvas.before:
            self.toggle_color = Color(1, 1, 1, 1)
            self.toggle_bg = RoundedRectangle(radius=[dp_scaled(8)])
            
        with self.btn_reset.canvas.before:
            Color(*self.COLOR_RESET)
            self.reset_bg = RoundedRectangle(radius=[dp_scaled(8)])

        self.btn_toggle.bind(pos=self._update_btn_shapes, size=self._update_btn_shapes)
        self.btn_reset.bind(pos=self._update_btn_shapes, size=self._update_btn_shapes)

        self.add_widget(self.btn_toggle)
        self.add_widget(self.btn_reset)

        self.btn_toggle.bind(on_release=self._toggle_release)
        self.btn_reset.bind(on_release=self._reset_release)

        self.sync_with_global()

    def _update_rect(self, instance, value):
        """Hält die untere Leiste und die Trennlinie synchron."""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.top_line.points = [self.x, self.top, self.right, self.top]

    def _update_btn_shapes(self, *args):
        """Bringt die abgerundeten Hintergründe exakt auf Button-Position."""
        self.toggle_bg.pos = self.btn_toggle.pos
        self.toggle_bg.size = self.btn_toggle.size
        
        self.reset_bg.pos = self.btn_reset.pos
        self.reset_bg.size = self.btn_reset.size

    def sync_with_global(self):
        """Dynamischer Farb- und Textwechsel im edlen Glass-Stil."""
        self.running = GLOBAL_STATE.graph_control.is_running
        
        if self.running:
            # Wenn das System läuft -> Zeige edles Stop-Rot
            self.toggle_color.rgba = self.COLOR_STOP
            self.btn_toggle.text = f"[color=#ffcccc][font=FA]\uf04c[/font][/color]  {I18N.t(self.TXT_STOP)}"
        else:
            # Wenn das System steht -> Zeige edles Start-Grün
            self.toggle_color.rgba = self.COLOR_START
            self.btn_toggle.text = f"[color=#ccffcc][font=FA]\uf04b[/font][/color]  {I18N.t(self.TXT_START)}"

    def _toggle_release(self, *_):
        if not GLOBAL_STATE.graph_control.is_running:
            GLOBAL_STATE.global_start()
            if self.on_start: self.on_start()
        else:
            GLOBAL_STATE.global_stop()
            if self.on_stop: self.on_stop()
        GLOBAL_STATE.sync_ui_buttons()

    def _reset_release(self, *_):
        GLOBAL_STATE.global_reset()
        GLOBAL_STATE.sync_ui_buttons()

    def refresh_state(self):
        self.sync_with_global()