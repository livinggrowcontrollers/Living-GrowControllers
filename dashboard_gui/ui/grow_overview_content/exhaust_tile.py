#exhaust_tile.py
import os

from kivy.app import App
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.exhaust_fan_overlay import ExhaustFanOverlay
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
ASSET_ROOT = os.path.join("dashboard_gui", "assets")
FAN_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "vivosun_t6.png")

class ExhaustTile(BoxLayout, BoxColorUpdater):

    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )

        self.val_box_w = dp_scaled(200)
        self.val_box_h = dp_scaled(140)

        self.padding = dp_scaled(8)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================
        self.title_label = Label(
            text="Exhaust: Vivosun T6",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )
        self.title_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        # ================= MAIN CONTAINER =================
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
            spacing=dp_scaled(4)
        )

        # ================= COLUMNS =================
        self.columns_box = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(2)
        )

        self.labels_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.6, 1),
            spacing=dp_scaled(2)
        )
        
        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.4, 1)
        )
        # ================= IMAGE =================
        self.fan_image = Image(
            source=FAN_PIC,
            size_hint=(1, 1),
            fit_mode="contain"

        )
        self.image_column.add_widget(self.fan_image)

        # ================= PROGRESS BAR =================
        self.prog_bar = SegmentedProgressBar()
        self.prog_bar.size_hint = (1, None)
        self.prog_bar.height = dp_scaled(18)

        # ================= CANVAS (LIKE LIGHT TILE) =================
        with self.value_box.canvas.before:
            Color(0, 0, 0, 0.62)
            self.value_bg = RoundedRectangle(radius=[dp_scaled(14)])

            self.glow_color = Color(0.1, 0.45, 0.9, 0.35)
            self.value_glow = Line(width=5)

            self.border_color = Color(0.1, 0.45, 0.9, 0.85)
            self.value_border = Line(width=1.3)

        self.value_box.bind(pos=self._update_value_box_canvas,
                            size=self._update_value_box_canvas)

        self.labels_column.add_widget(self.title_label)

        # ================= LABELS =================
        self.lbl_rpm = Label(
            text="RPM: 0 | LIVE: 0%",
            font_size=sp_scaled(18),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(18)
        )

        self.lbl_reason1 = Label(
            text="",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )
        self.lbl_reason2 = Label(
            text="",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 1, 1),
            size_hint=(1, None),
            height=dp_scaled(20)
        )

        self.lbl_mode = Label(
            text="MODE: IDLE",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            color=(0.9, 0.9, 0.9, 1),
            size_hint=(1, None),
            height=dp_scaled(20)
        )
        self.labels_column.add_widget(self.lbl_rpm)
        self.labels_column.add_widget(self.lbl_reason1)
        self.labels_column.add_widget(self.lbl_reason2)
        self.labels_column.add_widget(self.lbl_mode)

        for lbl in (self.lbl_rpm, self.lbl_reason1, self.lbl_reason2, self.lbl_mode):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        
        # ================= BUILD =================
        # ================= BUILD =================
        
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)
        
        self.value_box.add_widget(self.columns_box)
        self.value_box.add_widget(self.prog_bar)
        
        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)



    def _update_value_box_canvas(self, obj, *args):
        self.value_bg.pos = obj.pos
        self.value_bg.size = obj.size
        rect = (obj.x, obj.y, obj.width, obj.height, dp_scaled(14))
        self.value_glow.rounded_rectangle = rect
        self.value_border.rounded_rectangle = rect
    
    def update_values(self, data):
        # Wenn KEINE Daten da sind (Total-Delete oder Offline), setzen wir alles auf Standard zurück
        if not data:
            self.prog_bar.value = 0
            self.lbl_rpm.text = "RPM: 0 | LIVE: 0%"
            self.lbl_reason1.text = "OFFLINE"
            self.lbl_reason2.text = "NO DEVICE"
            self.lbl_mode.text = "MODE: IDLE"
            self._update_box_color(0) # Setzt die Box-Farbe auf den Standard-Ruhezustand
            return

        # ================= AB HIER DIE NORMALE LOGIK =================
        # RPM aus der 'exhaust_fan'-Gruppe holen
        exhaust_fan_group = data.get('exhaust_fan', {})
        rpm = exhaust_fan_group.get("exhaust_fan_rpm")
        if rpm is None:
            rpm = 0
        else:
            rpm = int(rpm)

        speed = data.get("exhaust_fan_speed_now")
        if speed is None:
            speed = 0
        else:
            speed = int(speed)
               
        reason1 = str(data.get("exhaust_fan_state_reason_1", "")).replace('_', ' ').upper()
        reason2 = str(data.get("exhaust_fan_state_reason_2", "")).replace('_', ' ').upper()
        night = bool(data.get("exhaust_fan_night_reduction", False))
        chaos = bool(data.get("exhaust_fan_chaos_active", False))

        night_txt = "ON" if night else "OFF"
        chaos_txt = "ON" if chaos else "OFF"

        self.lbl_mode.text = (
            f"NIGHT: {night_txt} | CHAOS: {chaos_txt}"
        )
        self.prog_bar.value = speed
        self.prog_bar.max = 100
    
        self.lbl_rpm.text = f"RPM: {rpm} | LIVE: {speed}%"
        
        self.lbl_reason1.text = reason1
        self.lbl_reason2.text = reason2

        if "FAILSAFE" in reason1 or "CRIT" in reason1:
            self.lbl_reason1.color = (1, 0.2, 0.2, 1)

        elif "CHAOS" in reason1:
            self.lbl_reason1.color = (1, 0.5, 0, 1)

        elif "VPD" in reason1:
            self.lbl_reason1.color = (0.3, 1, 1, 1)

        elif "REFINED" in reason1:
            self.lbl_reason1.color = (0.4, 1, 0.4, 1)

        elif "NIGHT" in reason1:
            self.lbl_reason1.color = (0.6, 0.6, 1, 1)

        else:
            self.lbl_reason1.color = (1, 1, 1, 0.8)


        self._update_box_color(rpm)


    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
    
        print(f"[DEBUG] ExhaustTile clicked")
    
        overlay = ExhaustFanOverlay(parent_header=self)
        App.get_running_app().root.current_screen.add_widget(overlay)
        return True