import os
import config # Dein config-Modul für den Pfad
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.app import App
import json
from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled
from dashboard_gui.ui.cam_viewer_content.cam_viewer_panel import CAM_CFG, DEFAULT_LIVE_PATH, build_rtsp_url
ASSET_ROOT = os.path.join("dashboard_gui", "assets")

TAPO_PIC = os.path.join(
    ASSET_ROOT,
    "hardware_pics",
    "tapo.png"
)


class TapoTile(BoxLayout):

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
            text="TP-Link Tapo Cam",
            font_size=sp_scaled(20),
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(25),
            color=(1, 1, 1, 1)
        )

        self.title_label.bind(
            size=lambda inst, *_:
            setattr(inst, "text_size", inst.size)
        )

        # ================= MAIN =================

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
            size_hint=(0.6, 1),
            spacing=dp_scaled(2)
        )

        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.4, 1)
        )

        # ================= IMAGE =================

        self.tapo_image = Image(
            source=TAPO_PIC,
            size_hint=(1, 1),
            fit_mode="contain"
        )

        self.image_column.add_widget(self.tapo_image)

        # ================= CANVAS =================

        with self.value_box.canvas.before:

            Color(0, 0, 0, 0.62)

            self.value_bg = RoundedRectangle(
                radius=[dp_scaled(14)]
            )

            self.glow_color = Color(
                0.1,
                0.45,
                0.9,
                0.35
            )

            self.value_glow = Line(width=5)

            self.border_color = Color(
                0.1,
                0.45,
                0.9,
                0.85
            )

            self.value_border = Line(width=1.3)

        self.value_box.bind(
            pos=self._update_value_box_canvas,
            size=self._update_value_box_canvas
        )

        self.labels_column.add_widget(self.title_label)

        # ================= LABELS =================

        self.lbl_camera = Label(
            text="CAM: ONLINE",
            font_size=sp_scaled(20),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20),
            color=(0.2, 1, 0.2, 1)  
        )

        self.lbl_stream = Label(
            text="STREAM: ACTIVE",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20),
            color=(0.2, 1, 0.2, 1)
        )

        self.lbl_status = Label(
            text="STATUS: FAKE",
            font_size=sp_scaled(14),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20),
            color=(1, 0.8, 0.2, 1)
        )

        for lbl in (
            self.lbl_camera,
            self.lbl_stream,
            self.lbl_status
        ):
            lbl.bind(
                size=lambda inst, *_:
                setattr(inst, "text_size", inst.size)
            )

            self.labels_column.add_widget(lbl)

        # ================= BUILD =================

        # ================= BUILD =================
        
        self.columns_box.add_widget(self.labels_column)
        self.columns_box.add_widget(self.image_column)
        
        self.value_box.add_widget(self.columns_box)
        
        self.content_container.add_widget(self.value_box)
        self.add_widget(self.content_container)

    def _update_box_color(self, is_ok):

        if is_ok:

            self.glow_color.rgba = (
                0.1,
                0.45,
                0.9,
                0.35
            )

            self.border_color.rgba = (
                0.1,
                0.45,
                0.9,
                0.85
            )

        else:

            self.glow_color.rgba = (
                1.0,
                0.3,
                0.2,
                0.35
            )

            self.border_color.rgba = (
                1.0,
                0.3,
                0.2,
                0.85
            )

# ... innerhalb der Klasse TapoTile ...

    def on_touch_down(self, touch):
        # Prüfen, ob die Berührung innerhalb des Tiles stattfindet
        if self.collide_point(*touch.pos):
            self.start_cam_stream()
            return True # Event verarbeiten
        return super().on_touch_down(touch)

    def start_cam_stream(self):
        # 1. Daten laden (wie im CamViewerPanel)
        app = App.get_running_app()        
        
        if os.path.exists(CAM_CFG):
            with open(CAM_CFG, 'r') as f:
                cfg = json.load(f)
        else:
            cfg = {}

        ip = cfg.get("ip")
        user = cfg.get("user")
        pwd = cfg.get("pwd")

        if not ip or not user or not pwd:
            print("⚠️ Cam-Konfiguration unvollständig.")
            return

        # 2. Den Screen finden und die Daten übergeben
        cam_screen = app.ensure_screen("cam_viewer")
            
        # Wir suchen das Panel im Screen (normalerweise das 2. Kind von root in CamViewerScreen)
        # Oder besser: Zugriff über den screen.children[0].children[0]
        # Hier ist ein robusterer Weg:
        panel = None
        for child in cam_screen.walk():
            if child.__class__.__name__ == "CamViewerPanel":
                panel = child
                break

        if panel:
            # Setze die Werte ins Panel
            panel.inp_ip.text = ip
            panel.inp_user.text = user
            panel.inp_pwd.text = pwd

            # Starte den Stream
            panel.start()

            # Wechsle den Screen
            app.root.current = "cam_viewer"
    def _update_value_box_canvas(self, obj, *args):

        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(14)

        self.value_bg.pos = (x, y)
        self.value_bg.size = (w, h)

        self.value_glow.rounded_rectangle = (
            x,
            y,
            w,
            h,
            r
        )

        self.value_border.rounded_rectangle = (
            x,
            y,
            w,
            h,
            r
        )

    def update_values(self, data):

        #
        # Fake Placeholder
        #

        camera_online = False
        stream_active = False

        if camera_online:
            self.lbl_camera.text = "CAM: ONLINE"
            self.lbl_camera.color = (0.2, 1, 0.2, 1)
        else:
            self.lbl_camera.text = "CAM: OFFLINE"
            self.lbl_camera.color = (1, 0.3, 0.2, 1)

        if stream_active:
            self.lbl_stream.text = "STREAM: ACTIVE"
            self.lbl_stream.color = (0.2, 1, 0.2, 1)
        else:
            self.lbl_stream.text = "STREAM: INACTIVE"
            self.lbl_stream.color = (1, 0.7, 0.2, 1)

        self.lbl_status.text = "STATUS: PLACEHOLDER"
        self.lbl_status.color = (1, 0.8, 0.2, 1)

        self._update_box_color(True)
