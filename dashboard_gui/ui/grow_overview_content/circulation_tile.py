import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle, Line

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.circulation_fan_overlay import CirculationFanOverlay
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.circulation_fan_registry import overlay_snapshot

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
CIRC_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "mars_gaming.png")

class CirculationTile(BoxLayout, BoxColorUpdater):

    def __init__(self, fan_id=1, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )
        self.fan_id = int(fan_id)

        self.val_box_w = dp_scaled(200)
        self.val_box_h = dp_scaled(140)

        self.padding = dp_scaled(8)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================
        self.title_label = Label(
            text=f"Circulation {self.fan_id}: MARS PWMX",
            font_size=sp_scaled(18),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )
        self.title_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        # ================= MAIN BOX =================
        self.content_container = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(2)
        )

        # ================= VALUE BOX =================
        self.value_box = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            padding=[dp_scaled(12), dp_scaled(10)],
            spacing=dp_scaled(6)
        )

        # ================= COLUMNS =================
        self.columns_box = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(2)
        )

        self.labels_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.65, 1),
            spacing=dp_scaled(2)
        )

        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.35, 1)
        )

        # ================= IMAGE =================
        self.fan_image = Image(
            source=CIRC_PIC,
            size_hint=(1, 1),
            fit_mode="contain"
        )
        self.image_column.add_widget(self.fan_image)

        # ================= PROGRESS BAR =================
        self.prog_bar = SegmentedProgressBar()
        self.prog_bar.size_hint = (1, None)
        self.prog_bar.height = dp_scaled(18)

        # ================= CANVAS (LIGHT STYLE) =================
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])

            self.glow_color = Color(0.1, 0.45, 0.9, 0.35)
            self.value_glow = Line(width=5)

            self.border_color = Color(0.1, 0.45, 0.9, 0.85)
            self.value_border = Line(width=1.3)

        self.value_box.bind(
            pos=self._update_value_box_canvas,
            size=self._update_value_box_canvas
        )

        self.labels_column.add_widget(self.title_label)

        # ================= LABELS =================
        # Kombiniertes RPM und LIVE Label exakt im Exhaust-Format
        self.lbl_rpm = Label(
            text="RPM: 0 | LIVE: 0%",
            font_size=sp_scaled(18),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(18)
        )

        self.lbl_status = Label(
            text="STATUS: OFFLINE",
            font_size=sp_scaled(18),
            bold=True, # Optional: Auch bold gemacht für ein einheitliches Schriftbild
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(18) # Auf 18dp angepasst, passend zum neuen Layout
        )

        for lbl in (self.lbl_rpm, self.lbl_status):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)

        self.value_box.add_widget(self.columns_box)
        self.value_box.add_widget(self.prog_bar)

        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

    # ---------------- CANVAS UPDATE ----------------
    def _update_value_box_canvas(self, obj, *args):
        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(14)
        rect = (x, y, w, h, r)

        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect

     # ---------------- DATA UPDATE ----------------
# ---------------- DATA UPDATE ----------------
    def update_values(self, data):
        data = overlay_snapshot(data, self.fan_id)
        # 1. Daten sicher aus dem Dictionary extrahieren
        rpm = data.get("circulation_fan", {}).get("circulation_fan_rpm")

        if rpm is None:
            rpm = 0
        else:
            rpm = int(rpm)
        speed = data.get("circulation_fan_speed_now")

        if speed is None:
            speed = 0
        else:
            speed = int(speed)
        
        # 2. Das neue, kombinierte Label im Exhaust-Format befüllen
        self.lbl_rpm.text = f"RPM: {rpm} | LIVE: {speed}%"      
    
        # 3. Progress Bar aktualisieren (speed ist jetzt oben sauber definiert)
        self.prog_bar.value = speed
        self.prog_bar.max = 100
        
        # 4. Status / Modus bestimmen
        mode = data.get('circulation_fan_mode', 'manual')
        mode_map = {
            "chao": "CHAOS",
            "manual": "MANUAL",
            "nat": "NATURAL",
            "natural": "NATURAL"
        }
    
        self.lbl_status.text = f"MODE: {mode_map.get(mode, 'UNKNOWN')}"

        # 5. Rahmenfarbe basierend auf RPM updaten
        self._update_box_color(rpm)
    # ---------------- TOUCH ----------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
    
        print(f"[DEBUG] CirculationTile clicked")
    
        ui = GLOBAL_STATE.ui_handler
        if getattr(ui, "active_circulation_fan_overlay", None):
            ui.active_circulation_fan_overlay.close()
    
        overlay = CirculationFanOverlay(parent_header=self, fan_id=self.fan_id)
        ui.active_circulation_fan_overlay = overlay
        App.get_running_app().root.current_screen.add_widget(overlay)
        return True
