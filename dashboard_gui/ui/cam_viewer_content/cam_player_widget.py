#cam_viewer_widget.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
import webbrowser
import sys
import os

class CamPlayerWidget(BoxLayout):
    """
    Player-Widget für Kamera:
    - Öffnet immer den Link im Browser
    - macOS: explizit Safari/Chrome statt VLC
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"

        self.label = Label(
            text="[font=FA]\uf04b[/font] Start Live",
            halign="center",
            valign="middle",
            font_size="20sp"
        )
        self.add_widget(self.label)

    def show_starting(self, url):
        # 1) Label aktualisieren
        self.label.text = f"🌐 Öffne Kamera im Browser:\n{url}"
    
        # 2) Header-Back aktivieren UND sofort auslösen
        if hasattr(self, "header") and self.header:
            self.header.enable_back("dashboard")  # Button sichtbar, Ziel gesetzt
            self.header._go_back()                 # → springt direkt zurück
    
        # 3) Browser öffnen
        try:
            import sys, webbrowser
            if sys.platform == "darwin":  # macOS
                for browser_name in ["safari", "chrome"]:
                    try:
                        b = webbrowser.get(browser_name)
                        b.open(url)
                        return
                    except:
                        continue
                webbrowser.open(url)
            else:
                webbrowser.open(url)
        except Exception as e:
            self.label.text = f"❌ Fehler beim Öffnen im Browser:\n{e}"

    def show_stopped(self):
        self.label.text = "📷 Kein Live-Stream aktiv."
