# dashboard_gui/ui/light_tile.py
# LightTile: Zeigt den Status der Beleuchtung an, inklusive aktueller Helligkeit, Zielhelligkeit, verbleibender Zeit und Phase des Tages.
import os
import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle, Line

from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.light_overlay import LightOverlay
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar
from dashboard_gui.ui.common.logic.light_time import calculate_light_time
ASSET_ROOT = os.path.join("dashboard_gui", "assets")
LIGHT_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "electrogrow.png")


class LightTile(BoxLayout):

    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )
        self.val_box_w = dp_scaled(200)
        self.val_box_h = dp_scaled(140)

        self.padding = dp_scaled(6)
        self.spacing = dp_scaled(0)

        # Titel oben drüber über die ganze Breite
        self.title_label = Label(
            text="ElectroGrow 720W",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )
        self.title_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self._user_active = False
        self._last_user_action = 0
        self._last_sent_rev = 0
        self._ui_lock = False

        # Main Container
        self.content_container = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(2)
        )

        # Value Box (Hintergrund und Rahmen)
        self.value_box = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1), 
            padding=[dp_scaled(12), dp_scaled(10)],
            spacing=dp_scaled(6)
        )
        
# Horizontale Box für die Aufteilung: Links Labels, Rechts Bild
        self.columns_box = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(10)
        )

        # Linke Spalte für die Werte (auf 50% verkleinert, reicht für die Texte völlig)
        self.labels_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.65, 1),
            spacing=dp_scaled(2)
        )
        
        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.35, 1),
        )
        
        self.prog_bar = SegmentedProgressBar()
        self.prog_bar.size_hint = (1, None)
        self.prog_bar.height = dp_scaled(18)                
        
        # Bild füllt nun die vergrößerte 50%-Spalte komplett aus
        self.light_image = Image(
            source=LIGHT_PIC,
            size_hint=(1, 1),
            fit_mode="contain"  # Skaliert das Bild perfekt auf die neue Maximalgröße
        )
        self.image_column.add_widget(self.light_image)
        
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])
        
            self.glow_color = Color(1.0, 0.72, 0.15, 0.35)
            self.value_glow = Line(width=5)
        
            self.border_color = Color(1.0, 0.72, 0.15, 0.85)
            self.value_border = Line(width=1.3)

        self.value_box.bind(pos=self._update_value_box_canvas, size=self._update_value_box_canvas)
        self.labels_column.add_widget(self.title_label)
        # 1. Labels initialisieren
# ================= LABELS (EXAKT WIE IN EXHAUST TILE) =================
        # LIVE und TARGET kombiniert in EINEM Label, mit fester Höhe
        self.lbl_live_target = Label(
            text="LIVE: --% | TARGET: --%", 
            font_size=sp_scaled(18), 
            bold=True,
            halign="left", 
            valign="middle", 
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp_scaled(20)  # Feste Höhe verhindert Platzverschwendung
        )
        
        self.lbl_remaining = Label(
            text="REST: --:--", 
            font_size=sp_scaled(18),
            halign="left", 
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )
        
        self.lbl_status = Label(
            text="STATUS: INIT", 
            font_size=sp_scaled(18),
            halign="left", 
            valign="middle", 
            markup=True,
            size_hint=(1, None),
            height=dp_scaled(20)
        )
        
        self.lbl_phase = Label(
            text="PHASE: --", 
            font_size=sp_scaled(18),
            halign="left", 
            valign="middle", 
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp_scaled(20)
        )

        # Bindung für die Textgröße (wichtig für die linksbündige Ausrichtung)
        for lbl in (self.lbl_live_target, self.lbl_remaining, self.lbl_status, self.lbl_phase):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        # Spalten in die übergeordnete horizontale Box einfügen
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)

        # Zusammenbau der Value Box von oben nach unten
        self.value_box.add_widget(self.columns_box)    # Spalten (Werte & Bild)
        self.value_box.add_widget(self.prog_bar)       # Progressbar unten

        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)


    def _update_box_color(self, brightness):
        color = BoxColorUpdater.get_light_color(brightness)

        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)

    def _update_value_box_canvas(self, obj, *args):
        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(14)
        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)
        rect = (x, y, w, h, r)
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

    # ==================== UPDATE ====================
    def update_values(self, data):
        if not data:
            return

        target = data.get("light_target")

        if target is None:
            target = 0
        else:
            target = int(target)
        current_hw = data.get("light_pct")

        if current_hw is None:
            current_hw = 0
        else:
            current_hw = int(current_hw)
        self.prog_bar.value = current_hw
        self.prog_bar.max = 100
        self._update_box_color(current_hw)
        
        # SO IST ES RECHT (Exakt wie im ExhaustTile):
        self.lbl_live_target.text = f"LIVE: {current_hw}% | TARGET: {target}%"
        self.lbl_remaining.text = calculate_light_time(data)

        self._update_phase(data)
        
        # --- REVISION / ENGINE LOGIK ENTFERNT, DA REIN PASSIV ---

        # Status direkt aus dem 'light_mode' ableiten
        mode = data.get('light_mode', 'man')

        if mode == "manual" or mode == "man":
            self.lbl_status.text = "STATUS: [color=00ff00]MANU[/color]"
        elif mode == "time":
            self.lbl_status.text = "STATUS: [color=00ff00]TIMER[/color]"
        else:
            # Fallback, falls mal 'ok' oder ein anderer Modus kommt
            self.lbl_status.text = f"STATUS: [color=00ff00]{mode.upper()}[/color]"

    # ==================== PHASE ====================

    def _update_phase(self, data):
        # Wir nutzen direkt light_state_reason als führenden Wert
        state = str(data.get("light_state_reason", "UNKNOWN")).upper().strip()
        climate_override = bool(data.get("light_climate_override", False))
        
        # Konfiguration für die Phasen
        phase_config = {
            "SUNRISE": {"text": "SUNRISE", "color": (1.0, 0.72, 0.15, 1)},
            "SUNSET":  {"text": "SUNSET",  "color": (1.0, 0.45, 0.1, 1)},
            "NIGHT":   {"text": "NIGHT",   "color": (0.45, 0.65, 1.0, 1)},
            "DAY":     {"text": "DAY",     "color": (1.0, 1.0, 0.6, 1)},
            "UNKNOWN": {"text": "UNKNOWN", "color": (0.5, 0.5, 0.5, 1)}
        }

        # Fallback auf NIGHT, falls etwas Unerwartetes kommt
        config = phase_config.get(state, phase_config["UNKNOWN"])
        
        text = config["text"]
        color = config["color"]
    
        # Climate Override anhängen, falls aktiv
        if climate_override:
            text += " | CLIM"
    
        self.lbl_phase.text = f"PHASE: {text}"
                # Wenn der Grund sehr lang ist, Schriftgröße verringern
        if len(text) > 10:  # Richtwert, ggf. anpassen
            self.lbl_phase.font_size = sp_scaled(16)
        else:
            self.lbl_phase.font_size = sp_scaled(18)
        self.lbl_phase.color = color
    

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        ui = GLOBAL_STATE.ui_handler
        if getattr(ui, "active_light_overlay", None):
            ui.active_light_overlay.close()

        overlay = LightOverlay(parent_header=self)
        ui.active_light_overlay = overlay
        App.get_running_app().root.current_screen.add_widget(overlay)
        return True