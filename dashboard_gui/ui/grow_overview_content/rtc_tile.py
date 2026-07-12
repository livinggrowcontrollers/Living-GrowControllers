import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line

from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
RTC_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "rtc.png")


class RTCTile(BoxLayout):

    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint=(1, 1),
            **kw
        )

        self.padding = dp_scaled(6)
        self.spacing = dp_scaled(0)

        # ================= TITLE =================
        self.title_label = Label(
            text="RTC DS3231",
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
            spacing=dp_scaled(6)
        )

        # ================= COLUMNS =================
        self.columns_box = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            spacing=dp_scaled(10)
        )

        self.labels_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.5, 1),
            spacing=dp_scaled(2)
        )

        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.5, 1)
        )

        # ================= IMAGE =================
        self.rtc_image = Image(
            source=RTC_PIC,
            size_hint=(1, 1),
            fit_mode="contain"
        )
        self.image_column.add_widget(self.rtc_image)

        # ================= CANVAS =================
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
        self.lbl_time = Label(
            text="TIME: --:--:--",
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )

        self.lbl_found = Label(
            text="RTC: ---",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )

        self.lbl_status = Label(
            text="STATUS: OFFLINE",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )

        for lbl in (self.lbl_time, self.lbl_found, self.lbl_status):
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            self.labels_column.add_widget(lbl)

        # ================= BUILD =================
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)

        self.value_box.add_widget(self.columns_box)

        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

    # ---------------------------------------------------
    # CANVAS
    # ---------------------------------------------------

    def _update_box_color(self, is_ok):
        """Schaltet das UI-Glow und Border-Farbe basierend auf dem Status um."""
        if is_ok:
            # Dein Standard-Blau
            self.glow_color.rgba = (0.1, 0.45, 0.9, 0.35)
            self.border_color.rgba = (0.1, 0.45, 0.9, 0.85)
        else:
            # Alarm-Rot bei Fehlern
            self.glow_color.rgba = (1.0, 0.3, 0.2, 0.35)
            self.border_color.rgba = (1.0, 0.3, 0.2, 0.85)

    def _update_value_box_canvas(self, obj, *args):
        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(14)

        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)

        self.value_glow.rounded_rectangle = (x, y, w, h, r)
        self.value_border.rounded_rectangle = (x, y, w, h, r)


    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
    
            from kivy.app import App
            from dashboard_gui.global_state_manager import GLOBAL_STATE
    
            app = App.get_running_app()
            ui = GLOBAL_STATE.ui_handler
    
            current_screen = app.root.current_screen
    
            if not hasattr(current_screen, "header"):
                return super().on_touch_down(touch)
    
            header = current_screen.header
    
            if ui.active_inspector:
                ui.close_signal_inspector()
            else:
                ui.open_signal_inspector(parent_header=header)
    
            return True
    
        return super().on_touch_down(touch)

    # ---------------------------------------------------
    # UPDATE
    def update_values(self, data):
        if not data:
            return

        web = data.get("webserver", data)

        rtc_time = web.get("rtc_time", "--:--:--")
        rtc_found = web.get("rtc_found", False)
        status = str(web.get("status", "offline")).upper()

        self.lbl_time.text = f"TIME: {rtc_time}"

        # Status für RTC bestimmen
        if rtc_found:
            self.lbl_found.text = "RTC: OK"
            self.lbl_found.color = (0.2, 1, 0.2, 1)
        else:
            self.lbl_found.text = "RTC: NOT FOUND"
            self.lbl_found.color = (1, 0.3, 0.2, 1)

        self.lbl_status.text = status

        # Status für Webserver bestimmen
        if status in ("ACTIVE", "OK"):
            self.lbl_status.color = (0.2, 1, 0.2, 1)
        else:
            self.lbl_status.color = (1, 0.7, 0.2, 1)

        # Gesamtzustand prüfen: Box wird NUR grün/blau, wenn BEIDES (RTC & Status) passt
        is_everything_ok = rtc_found and (status in ("ACTIVE", "OK"))
        self._update_box_color(is_everything_ok)