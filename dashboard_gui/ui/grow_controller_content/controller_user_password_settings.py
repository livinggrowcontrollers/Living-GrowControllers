# dashboard_gui/ui/grow_controller_content/controller_user_password_settings.py

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.button import Button
from kivy.graphics import Rectangle, Color, RoundedRectangle

# Wir importieren deinen ausgelagerten GlassButton und die Utils
from .grow_controller_screen import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class UserPasswordSettingsOverlay(RelativeLayout):
    def __init__(self, screen, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.screen = screen  # Referenz auf den Haupt-Screen für Callbacks

        # Hintergrund-Abdunklung + dismiss on click
        self.bg_btn = Button(background_normal="", background_down="", background_color=(0, 0, 0, 0.6))
        self.bg_btn.bind(on_release=lambda *_: self.screen.close_security_settings())
        self.add_widget(self.bg_btn)

        # Content Box
        box = BoxLayout(
            orientation="vertical", 
            padding=[dp_scaled(20), dp_scaled(15)], 
            spacing=dp_scaled(12),
            size_hint=(None, None), 
            size=(dp_scaled(600), dp_scaled(400)), 
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        with box.canvas.before:
            # Translucent rounded panel like circulation overlay
            Color(0, 0, 0, 0.62)
            self.box_bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp_scaled(12)])
        box.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        # Titel
        box.add_widget(Label(text="SECURITY EINSTELLUNGEN", bold=True, font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(30), color=(0.2, 1, 0.4, 1)))
        
        # HTTP Username Input
        box.add_widget(Label(text="Web-Admin Username:", halign="left", size_hint_y=None, height=dp_scaled(20), text_size=(dp_scaled(280), None)))
        self.user_input = TextInput(
            hint_text="Neuer Username (z.B. admin)", multiline=False, font_size=sp_scaled(20),
            size_hint_y=None, height=dp_scaled(45), background_color=(0.1, 0.1, 0.12, 1), foreground_color=(1, 1, 1, 1)
        )
        box.add_widget(self.user_input)
        
        # HTTP Passwort Input
        box.add_widget(Label(text="Web-Admin Passwort:", halign="left", size_hint_y=None, height=dp_scaled(20), text_size=(dp_scaled(280), None)))
        self.pw_input = TextInput(
            hint_text="Neues Passwort", password=True, multiline=False, font_size=sp_scaled(20),
            size_hint_y=None, height=dp_scaled(45), background_color=(0.1, 0.1, 0.12, 1), foreground_color=(1, 1, 1, 1)
        )
        box.add_widget(self.pw_input)
        
        # Buttons
        btn_box = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(10))
        
        save_btn = GlassButton(text="SPEICHERN", font_size=sp_scaled(20))
        save_btn.bind(on_release=lambda x: self._apply_security_settings())
        
        cancel_btn = GlassButton(text="ABBRECHEN", font_size=sp_scaled(20))
        cancel_btn.color = (1, 0.3, 0.3, 1)
        cancel_btn.bind(on_release=lambda x: self.screen.close_security_settings())
        
        btn_box.add_widget(save_btn)
        btn_box.add_widget(cancel_btn)
        box.add_widget(btn_box)
        
        self.add_widget(box)

    def _apply_security_settings(self):
        """Sendet die neuen Credentials atomar an das System"""
        username = self.user_input.text.strip()
        password = self.pw_input.text.strip()

        # Nur senden, wenn Felder nicht komplett leer sind (Sicherheitsnetz)
        if not username or not password:
            print("[SecuritySettings] Fehler: Username oder Passwort dürfen nicht leer sein!")
            return

        # Absenden mit den exakten Keys, die dein ESP32 jetzt erwartet
        print(f"[SecuritySettings] Sende an ESP: {username} / {password}")
        self.screen._send_grow_payload(
            {
                "sec_user": username,
                "sec_pw": password
            },
            context="security_settings",
            reset_after_ack=False,  # Wir wollen keinen Reset nach dem Ack, nur die neuen Daten übernehmen
        )
