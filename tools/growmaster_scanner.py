import json
import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from zeroconf import ServiceBrowser, Zeroconf

# Pfad zur Config-Datei (wird im gleichen Ordner wie das Tool erstellt)
CONFIG_PATH = "devices_config.json"

class GrowmasterDiscoverer:
    def __init__(self, callback):
        self.callback = callback
        self.found_devices = {}

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            # Hostname extrahieren (z.B. growmaster-d064.local.)
            hostname = info.server.rstrip('.').lower()
            
            # Nur unsere Growmaster filtern
            if "growmaster-" in hostname:
                # IP-Adressen auslesen
                addresses = [str(ip) for ip in info.parsed_addresses()]
                ip_address = addresses[0] if addresses else ""
                
                # MAC-Adresse oder ID aus dem Hostnamen extrahieren (z.B. d064)
                # Wir nutzen die ID hier direkt als Key für deine Config
                mac_id = hostname.split("growmaster-")[-1].replace(".local", "")
                
                device_data = {
                    "hostname": hostname.replace(".local", ""),
                    "ip_address": ip_address
                }
                
                if mac_id not in self.found_devices:
                    self.found_devices[mac_id] = device_data
                    # GUI-Thread informieren
                    Clock.schedule_once(lambda dt: self.callback(mac_id, device_data))

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.update_service(zc, type_, name)


class ScannerWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=15, **kwargs)
        
        self.devices = {}
        self.zeroconf = None
        self.browser = None

        # Header
        self.add_widget(Label(
            text="[b]Growmaster mDNS Network Scanner[/b]", 
            markup=True, 
            font_size='20sp', 
            size_hint_y=None, 
            height=40
        ))
        
        # Status Label
        self.status_label = Label(
            text="Bereit zum Scannen...", 
            size_hint_y=None, 
            height=30,
            color=(0.8, 0.8, 0.8, 1)
        )
        self.add_widget(self.status_label)

        # Scrollbare Liste für gefundene Geräte
        scroll = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll.add_widget(self.grid)
        self.add_widget(scroll)

        # Buttons am unteren Rand
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        self.scan_btn = Button(text="Netzwerk scannen", on_press=self.start_scan, background_color=(0.2, 0.6, 1, 1))
        self.save_btn = Button(text="In JSON speichern", on_press=self.save_to_json, disabled=True, background_color=(0.2, 0.8, 0.2, 1))
        
        btn_layout.add_widget(self.scan_btn)
        btn_layout.add_widget(self.save_btn)
        self.add_widget(btn_layout)

    def start_scan(self, instance):
        self.scan_btn.disabled = True
        self.save_btn.disabled = True
        self.grid.clear_widgets()
        self.devices.clear()
        self.status_label.text = "Scanne Netzwerk nach Growmaster-Geräten (5s)..."
        
        # Scan in separatem Thread starten, um Kivy-UI nicht einzufrieren
        threading.Thread(target=self._run_mdns_scan, daemon=True).start()

    def _run_mdns_scan(self):
        self.zeroconf = Zeroconf()
        discoverer = GrowmasterDiscoverer(self.on_device_found)
        # Wir suchen gezielt nach HTTP-Diensten im LAN
        self.browser = ServiceBrowser(self.zeroconf, "_http._tcp.local.", discoverer)
        
        # 5 Sekunden suchen lassen
        import time
        time.sleep(5.0)
        
        # Aufräumen
        self.zeroconf.close()
        Clock.schedule_once(self.on_scan_complete)

    def on_device_found(self, mac_id, data):
        self.devices[mac_id] = data
        
        # Eintrag zur GUI hinzufügen
        row = Label(
            text=f"ID: [b]{mac_id}[/b]  |  mDNS: {data['hostname']}.local  |  IP: {data['ip_address']}",
            markup=True,
            size_hint_y=None,
            height=40,
            color=(0.9, 0.9, 0.9, 1)
        )
        self.grid.add_widget(row)

    def on_scan_complete(self, dt):
        self.scan_btn.disabled = False
        if self.devices:
            self.status_label.text = f"Scan beendet. {len(self.devices)} Gerät(e) gefunden!"
            self.save_btn.disabled = False
        else:
            self.status_label.text = "Keine Growmaster-Geräte gefunden. Erneut versuchen?"

    def save_to_json(self, instance):
        # Struktur exakt so aufbauen, wie es dein web_client.py erwartet:
        config_data = {"devices": {}}
        
        for mac_id, info in self.devices.items():
            hostname = info["hostname"]
            config_data["devices"][mac_id] = {
                "device_id": hostname,
                "name": hostname,
                "hostname": hostname,
                "ip_address": info["ip_address"],
            }
        
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            self.status_label.text = f"Erfolgreich in '{CONFIG_PATH}' gespeichert!"
        except Exception as e:
            self.status_label.text = f"Fehler beim Speichern: {e}"


class GrowmasterScannerApp(App):
    def build(self):
        self.title = "Growmaster Network Discovery"
        return ScannerWidget()


if __name__ == "__main__":
    GrowmasterScannerApp().run()
