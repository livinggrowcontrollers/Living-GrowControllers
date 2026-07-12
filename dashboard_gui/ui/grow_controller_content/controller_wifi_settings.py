from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.button import Button
from kivy.graphics import Rectangle, Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock  # Wichtig für das asynchrone Timing!

# Hier importieren wir die GlassButton-Klasse aus deiner Hauptdatei
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class WifiSettingsOverlay(RelativeLayout):
    def __init__(self, screen, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.screen = screen  # Referenz auf den Haupt-Screen für Callbacks und Variablen
        self._closing_trigger = None  # Speichert das Clock-Event, falls nötig

        # Hintergrund-Abdunklung + dismiss on click
        self.bg_btn = Button(background_normal="", background_down="", background_color=(0, 0, 0, 0.6))
        # Dismiss nur erlauben, wenn wir nicht im Wartemodus sind
        self.bg_btn.bind(
            on_release=lambda *_:
            self.screen.close_wifi_settings()
        )
       
        self.add_widget(self.bg_btn)

        # Content Box
        box = BoxLayout(
            orientation="vertical", 
            padding=[dp_scaled(20), dp_scaled(15)], 
            spacing=dp_scaled(12),
            size_hint=(None, None), 
            size=(dp_scaled(600), dp_scaled(420)), # Leicht erhöht, damit alles Platz hat
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        with box.canvas.before:
            # Translucent rounded panel like circulation overlay
            Color(0, 0, 0, 0.62)
            self.box_bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp_scaled(12)])
        box.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        # Titel & SSID
        box.add_widget(Label(text="WLAN KONFIGURATION", bold=True, font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(30), color=(0.2, 1, 0.4, 1)))
        box.add_widget(Label(text="Netzwerk Name (SSID):", halign="left", size_hint_y=None, height=dp_scaled(20), text_size=(dp_scaled(280), None)))
        
        # SSID Fallback-Logik aus dem Screen ziehen
        current_ssid = "---"
        if "ssid" in self.screen.labels and self.screen.labels["ssid"] is not None:
            current_ssid = self.screen.labels["ssid"].text
            
        self.ssid_input = TextInput(
            text=current_ssid if current_ssid != "---" else "",
            hint_text="SSID (Netzwerk Name)", multiline=False, font_size=sp_scaled(20),
            size_hint_y=None, height=dp_scaled(45), background_color=(0.1, 0.1, 0.12, 1), foreground_color=(1, 1, 1, 1)
        )
        box.add_widget(self.ssid_input)
        
        # Passwort Label
        box.add_widget(Label(text="Passwort:", halign="left", size_hint_y=None, height=dp_scaled(20), text_size=(dp_scaled(280), None)))
        
        # --- NEU: Passwort-Container (Input + Auge nebeneinander) ---
        pw_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(5))
        
        self.pw_input = TextInput(
            hint_text="Passwort eingeben", password=True, multiline=False, font_size=sp_scaled(20),
            size_hint_x=0.85, background_color=(0.1, 0.1, 0.12, 1), foreground_color=(1, 1, 1, 1)
        )
        
        # Auge Button mit Font Awesome initialisieren (\uf070 = durchgestrichenes Auge / versteckt)
        self.eye_btn = Button(
            text="[font=FA]\uf070[/font]", 
            markup=True,
            font_size=sp_scaled(20),
            size_hint_x=0.15,
            background_normal="", 
            background_color=(0.15, 0.15, 0.18, 1),
            color=(1, 1, 1, 1)  # <-- HIER: 'color' statt 'foreground_color'
        )
        self.eye_btn.bind(on_release=self.toggle_password_visibility)
        
        pw_container.add_widget(self.pw_input)
        pw_container.add_widget(self.eye_btn)
        box.add_widget(pw_container)
        # -------------------------------------------------------------
        
        # Buttons
        btn_box = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(10))
        
        # Make the send button accessible later and bind
        self.save_btn = GlassButton(text="SENDEN", font_size=sp_scaled(20))
        self.save_btn.bind(on_release=lambda x: self._apply_wifi_settings())
        
        self.cancel_btn = GlassButton(text="ABBRECHEN", font_size=sp_scaled(20))
        self.cancel_btn.color = (1, 0.3, 0.3, 1)
        self.cancel_btn.bind(on_release=lambda x: self.screen.close_wifi_settings())
        
        btn_box.add_widget(self.save_btn)
        btn_box.add_widget(self.cancel_btn)
        box.add_widget(btn_box)
        
        # Status label for waiting / error messages
        self.status_label = Label(text="", size_hint_y=None, height=dp_scaled(24), halign='center', markup=True)
        box.add_widget(self.status_label)

        self.add_widget(box)

    # --- NEU: Funktion zum Umschalten der Sichtbarkeit ---
    def toggle_password_visibility(self, instance):
        if self.pw_input.password:
            self.pw_input.password = False
            self.eye_btn.text = "[font=FA]\uf06e[/font]"  # Offenes Auge
        else:
            self.pw_input.password = True
            self.eye_btn.text = "[font=FA]\uf070[/font]"  # Durchgestrichenes Auge

    def _apply_wifi_settings(self):
        self.screen._wifi_is_waiting = True

        new_rev = self.screen._send_grow_payload(
            {
                "wifi_ssid": self.ssid_input.text.strip(),
                "wifi_pw": self.pw_input.text.strip(),
                "wifi_mode": 1
            },
            context="wifi_settings",
            reset_after_ack=True
        )

        if new_rev:
            try:
                self.set_waiting_state()
            except Exception:
                self.ssid_input.disabled = True
                self.pw_input.disabled = True
                self.eye_btn.disabled = True # Auge mit deaktivieren
                self.save_btn.disabled = True
                self.status_label.text = "Warte auf ESP..."
        else:
            self.screen._wifi_is_waiting = False

    def set_waiting_state(self):
        self.ssid_input.disabled = True
        self.pw_input.disabled = True
        self.eye_btn.disabled = True # Auge deaktivieren
        self.save_btn.disabled = True
        self.status_label.color = (1, 1, 1, 1)
        self.status_label.text = "Warte auf ESP..."

    def clear_waiting_state(self):
        self.ssid_input.disabled = False
        self.pw_input.disabled = False
        self.eye_btn.disabled = False # Auge wieder aktivieren
        self.save_btn.disabled = False
        self.status_label.text = ""

    def show_success(self):
        self.status_label.color = (0.2, 1, 0.4, 1)
        self.status_label.text = "[font=FA]\uf00c[/font] [b]Erfolgreich gesendet! thx @HagenZ <3[/b]"
        
        if self._closing_trigger:
            Clock.unschedule(self._closing_trigger)
            
        self._closing_trigger = Clock.schedule_once(self._delayed_close, 1.5)

    def _delayed_close(self, dt):
        self.screen._wifi_is_waiting = False
        self.screen.close_wifi_settings()

    def show_timeout(self, msg="Timeout: ESP antwortet nicht"):
        try:
            self.clear_waiting_state()
            self.status_label.color = (1, 0.3, 0.3, 1)
            self.status_label.text = msg
        except Exception:
            pass
