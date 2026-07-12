# dashboard_gui/ui/common/signal_inspector/signal_inspector.py

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.clock import Clock
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
import time 
from kivy.app import App

class SignalInspector(FloatLayout):
    def __init__(self, parent_header, **kwargs):
        super().__init__(**kwargs)
        self.parent_header = parent_header
        self.dfe = GLOBAL_STATE.data_flow 
        
        # 1) Hintergrund
        bg = Button(background_color=(0, 0, 0, 0.2), border=(0, 0, 0, 0))
        bg.bind(on_release=lambda *_: self.close())
        self.add_widget(bg)

        # 2) Das Panel (avg_card Style)
        self.panel = FloatLayout(
            size_hint=(None, None),
            size=(dp_scaled(400), dp_scaled(300)), 
            pos_hint={"right": 0.98, "top": 0.94}
        )

        with self.panel.canvas.before:
            self.panel.bg_color = Color(0.05, 0.05, 0.05, 0.85)
            self.panel.bg = RoundedRectangle(pos=self.panel.pos, size=self.panel.size, radius=[dp_scaled(20)])
            self.panel.outline_color = Color(0, 0.8, 1, 0.5)
            self.panel.outline = Line(rounded_rectangle=(self.panel.x, self.panel.y, self.panel.width, self.panel.height, dp_scaled(20)), width=1.2)
        
        self.panel.bind(pos=self._update_panel_canvas, size=self._update_panel_canvas)


        # 5) Jump-Button zum Grow Controller hinzufügen
        # Wir platzieren ihn oben rechts im Panel, direkt über dem Graphen
        self.jump_btn = Button(
            text="[font=FA]\uf013[/font]", # fa-cog / Zahnrad
            font_size=sp_scaled(24),
            markup=True,
            size_hint=(None, None),
            size=(dp_scaled(50), dp_scaled(50)),
            pos_hint={"right": 0.98, "top": 0.98},
            background_color=(0, 0, 0, 0), # Transparent, da wir eigenes Design wollen
            color=(0, 0.8, 1, 0.8) # Neon Blau
        )
        
        # Zeichnen wir einen kleinen Rahmen um den Button für den Glass-Look
        with self.jump_btn.canvas.before:
            Color(0, 0.8, 1, 0.2)
            self.jump_bg = RoundedRectangle(radius=[dp_scaled(10)])
            Color(0, 0.8, 1, 0.5)
            self.jump_line = Line(rounded_rectangle=(0,0,0,0, dp_scaled(10)), width=1.1)
            
        self.jump_btn.bind(pos=self._update_btn_canvas, size=self._update_btn_canvas)
        self.jump_btn.bind(on_release=self.jump_to_controller)
        
        # 4) LAYER 2: Der Text
        # 4) LAYER 2: Der Text
        # WICHTIG: size_hint=(1, 1) sorgt dafür, dass er das Panel ausfüllt!
        content_text = BoxLayout(
            orientation="vertical", 
            padding=dp_scaled(20),
            size_hint=(1, 1),  # <-- Das hat gefehlt!
            pos_hint={"x": 0, "y": 0} # Damit es genau auf dem Panel liegt
        )

        self.lbl = Label(markup=True, halign="left", valign="top", font_size=sp_scaled(18))
        self.lbl.bind(size=lambda *_: setattr(self.lbl, "text_size", self.lbl.size))
        
        self.raw_lbl = Label(markup=True, halign="left", font_name="RobotoMono-Regular", 
                             font_size=sp_scaled(18), size_hint_y=None, height=dp_scaled(20), 
                             color=(0.5, 0.8, 1, 0.5))
        self.raw_lbl.bind(size=lambda *_: setattr(self.raw_lbl, "text_size", self.raw_lbl.size))

        content_text.add_widget(self.lbl)
        content_text.add_widget(Widget(size_hint_y=None, height=dp_scaled(10)))
        content_text.add_widget(self.raw_lbl)

        self.panel.add_widget(content_text)
        self.add_widget(self.panel)
        
        self.panel.add_widget(self.jump_btn)


        self.sync_with_global_state()
        self._update_event = Clock.schedule_interval(self.update_ui, 0.2)

    def _update_panel_canvas(self, obj, *args):
        self.panel.bg.pos = obj.pos
        self.panel.bg.size = obj.size
        self.panel.outline.rounded_rectangle = (obj.x, obj.y, obj.width, obj.height, dp_scaled(20))
    def _update_btn_canvas(self, obj, *args):
        self.jump_bg.pos = obj.pos
        self.jump_bg.size = obj.size
        self.jump_line.rounded_rectangle = (obj.x, obj.y, obj.width, obj.height, dp_scaled(10))

    def jump_to_controller(self, *_):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        # Ruft den Screen auf und merkt sich den alten Screen im Stack
        GLOBAL_STATE.ui_handler.goto("device_picker")     # Geht direkt zum Spezialisten")
        self.close() # Den Inspector zumachen, damit man freie Sicht hat

    def sync_with_global_state(self):
        dev_id = GLOBAL_STATE.get_active_device_id()
        if not dev_id or not self.dfe: return
        self._current_dev_id = dev_id


    def update_ui(self, *_):
        dev_id = GLOBAL_STATE.get_active_device_id()
        if not dev_id: return
        if self._current_dev_id != dev_id: self.sync_with_global_state()

        # Daten aus verschiedenen Quellen extrahieren
        frame = getattr(self.parent_header, "_last_frame", {})
        web = frame.get("webserver", {})  # <--- Hier kommen IP und BootCause her
        health = frame.get("health", {})
        channel = frame.get("channel", "adv")
        ch_data = frame.get(channel, {})

        # 1. RSSI & Graph
        rssi = health.get("signal", {}).get("rssi")
        if rssi is not None and rssi != "--":
            rssi_color = "00FF00" if float(rssi) > -65 else ("FFCC00" if float(rssi) > -85 else "FF4444")
        else:
            rssi_color = "888888"

        # 2. Zeitrechnung (Uptime & Last Seen)
        # Wir nehmen die Uptime vom Webserver (S) oder vom Health-Frame
        uptime_raw = web.get("uptime_esp_s") or health.get("uptime", {}).get("value") or 0
        s = int(uptime_raw)
        uptime_str = f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}" if s < 86400 else f"{s//86400}d { (s%86400)//3600:02d}:{(s%3600)//60:02d}"

        last_seen = "Never"
        if dev_id in self.dfe.last_seen_timestamps:
            diff = time.time() - self.dfe.last_seen_timestamps[dev_id]
            last_seen = f"{int(diff)}s ago" if diff < 60 else time.strftime("%H:%M:%S", time.localtime(self.dfe.last_seen_timestamps[dev_id]))

        # 3. Netzwerk & System
        ip_addr = web.get("ip", "0.0.0.0")
        boot_cause = web.get("boot_cause", "Unknown")
        # Kürzen falls zu lang (z.B. "Software Watchdog" -> "SW Watchdog")
        boot_cause_short = boot_cause.replace("Software", "SW").replace("Power Cut", "Power")

        latency = frame.get("latency", 0) / 1000.0
        lat_color = "00FF00" if latency < 2.0 else "FFCC00"

        # 4. RAW Data
        raw_val = ch_data.get("raw") or ch_data.get("adv_raw") or "--"
        short_raw = (str(raw_val)[:50] + "...") if len(str(raw_val)) > 50 else str(raw_val)

        # UI Text Zusammenbau
        dev_name = GLOBAL_STATE.get_device_label(dev_id)
        
        self.lbl.text = (
            f"[b][color=00CCFF]{dev_name}[/color][/b] [size=11sp][color=888888]{dev_id}[/color][/size]\n\n"
            f"RSSI     : [color={rssi_color}][b]{rssi} dBm[/b][/color]\n"
            f"IP       : [color=FFFFFF]{ip_addr}[/color]\n"
            f"Uptime   : [color=AAFF00]{uptime_str}[/color]\n"
            f"Boot     : [color=FFCC00]{boot_cause_short}[/color]\n"
            f"Latency  : [color={lat_color}]{latency:.2f}s[/color]\n"
            f"Seen     : {last_seen}\n"
        )
        self.raw_lbl.text = f"[color=4488FF]RAW:[/color] {short_raw}"

    def close(self):
        if self._update_event:
            self._update_event.cancel()
        if GLOBAL_STATE.ui_handler.active_inspector == self:
            GLOBAL_STATE.ui_handler.active_inspector = None
        if self.parent:
            self.parent.remove_widget(self)