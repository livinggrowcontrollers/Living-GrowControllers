#cam_viewer_panel.py
import os, json
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.app import App
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.cam_viewer_content.cam_player_widget import CamPlayerWidget
from dashboard_gui.global_state_manager import GLOBAL_STATE
import config

DEFAULT_RTSP_PORT = 554
DEFAULT_LIVE_PATH = "stream1"
CAM_CFG = os.path.join(config.DATA, "cam_config.json")


def build_rtsp_url(ip, u, p, path):
    return f"rtsp://{u}:{p}@{ip}:{DEFAULT_RTSP_PORT}/{path}"


class CamViewerPanel(BoxLayout):

    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)

        # Player Widget
        self.player = CamPlayerWidget(size_hint_y=0.40)
        self.add_widget(self.player)

        # Stream URL placeholder
        self.stream_url = None

        # Load Config
        cfg = self._load()

        # ------- FORM -------
        form = BoxLayout(orientation="vertical",
                         size_hint_y=None,
                         height=dp_scaled(150),
                         spacing=dp_scaled(8))

        def make_row(label, default):
            row = BoxLayout(size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(8))
            row.add_widget(Label(text=label, size_hint=(0.3,1), font_size=sp_scaled(16)))
            field = TextInput(text=default, multiline=False, font_size=sp_scaled(16))
            row.add_widget(field)
            return row, field

        r1, self.inp_ip = make_row("Camera IP", cfg.get("ip",""))
        r2, self.inp_user = make_row("Username", cfg.get("user",""))
        r3, self.inp_pwd = make_row("Password", cfg.get("pwd",""))
        self.inp_pwd.password = True

        form.add_widget(r1)
        form.add_widget(r2)
        form.add_widget(r3)
        self.add_widget(form)

        # ------- BUTTONS -------
        btns = BoxLayout(size_hint_y=None, height=dp_scaled(50), spacing=dp_scaled(8))

        b_start = Button(
            markup=True,
            text="[font=FA]\uf04b[/font] Start Live",
            background_color=(0.2,0.6,0.2,1),
            font_size=sp_scaled(18)
        )
        b_start.bind(on_release=lambda *_: self.start())

        b_stop = Button(
            markup=True,
            text="[font=FA]\uf04d[/font] Stop",
            background_color=(0.6,0.2,0.2,1),
            font_size=sp_scaled(18)
        )
        b_stop.bind(on_release=lambda *_: self.stop())

        btns.add_widget(b_start)
        btns.add_widget(b_stop)
        self.add_widget(btns)

        # ------- LOG -------
        self.log = Label(text="RTSP idle.",
                         valign="top", halign="left",
                         size_hint_y=1, font_size=sp_scaled(16))
        self.log.bind(size=lambda *_: setattr(self.log, "text_size", self.log.size))

        scroll = ScrollView(size_hint=(1,1))
        scroll.add_widget(self.log)
        self.add_widget(scroll)

    # -----------------------------------------------------
    def _load(self):
        os.makedirs(config.DATA, exist_ok=True)
        if not os.path.exists(CAM_CFG):
            return {}
        try:
            return json.load(open(CAM_CFG))
        except:
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(CAM_CFG), exist_ok=True)
        with open(CAM_CFG, "w", encoding="utf-8") as f:
            json.dump({
                "ip": self.inp_ip.text.strip(),
                "user": self.inp_user.text.strip(),
                "pwd": self.inp_pwd.text.strip(),
            }, f, indent=2, ensure_ascii=False)

    # -----------------------------------------------------
    def _log(self, msg):
        self.log.text += "\n" + msg

    # -----------------------------------------------------
    def start(self):
        
        # Angenommen, dein ScreenManager ist im Root-Widget der App
# ... innerhalb von start() ...
        app = App.get_running_app()
        if app.root:
            app.root.current = "dashboard"    
            self._save()
    
        ip = self.inp_ip.text.strip()
        u  = self.inp_user.text.strip()
        p  = self.inp_pwd.text.strip()
    
        if not ip or not u or not p:
            self._log("❌ IP/User/Pass fehlen.")
            return
    
        self.stream_url = build_rtsp_url(ip,u,p,DEFAULT_LIVE_PATH)
        self.player.show_starting(self.stream_url)
    
        self._log(f"🌐 Browser: {self.stream_url} wird geöffnet.")

        # 🔥 Direkt ins Dashboard springen, immer!
        if GLOBAL_STATE.dashboard_ref and GLOBAL_STATE.dashboard_ref.manager:
            GLOBAL_STATE.dashboard_ref.manager.current = "dashboard"

    def stop(self):
        self.player.show_stopped()
        self._log("■ Stream gestoppt.")
