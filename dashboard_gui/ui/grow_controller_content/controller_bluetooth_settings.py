import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Rectangle, Color, RoundedRectangle
from kivy.clock import Clock

# Wiederverwendung deiner Komponenten & Skalierungen
from .grow_controller_screen import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class BluetoothSettingsOverlay(RelativeLayout):
    def __init__(self, screen, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.screen = screen  # Referenz zum Hauptscreen
        
        # Cache um das "Springen" der flinken Liste zu beruhigen
        # Struktur: { mac: {"name": name, "last_seen": timestamp} }
        self._device_cache = {}
        self.CACHE_TIMEOUT = 12.0  # Geräte bleiben 12 Sek im UI, auch wenn der ESP-Scan sie kurz löscht

        # Hintergrund abdunkeln + dismiss on click (wie Circulation overlay)
        self.bg_btn = Button(background_normal="", background_down="", background_color=(0, 0, 0, 0.6))
        self.bg_btn.bind(on_release=lambda *_: self.screen.close_bluetooth_settings())
        self.add_widget(self.bg_btn)

        # Haupt-Content-Box (Höhe leicht erhöht für den Unpair-Button)
        self.box = BoxLayout(
            orientation="vertical", 
            padding=[dp_scaled(15), dp_scaled(15)], 
            spacing=dp_scaled(10),
            size_hint=(None, None), 
            size=(dp_scaled(600), dp_scaled(400)), 
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        with self.box.canvas.before:
            # Translucent rounded panel like circulation overlay
            Color(0, 0, 0, 0.62)
            self.box_bg = RoundedRectangle(pos=self.box.pos, size=self.box.size, radius=[dp_scaled(12)])
        # Update the rounded rectangle when the box moves/resizes
        self.box.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        # Titel
        self.box.add_widget(Label(
            text="BLE SENSOR GATEWAY", bold=True, font_size=sp_scaled(20), 
            size_hint_y=None, height=dp_scaled(30), color=(0.2, 1, 0.4, 1)
        ))

        # Info-Label, welcher Sensor gerade zugewiesen wird
        self.target_sensor = "outside"  # Standardmäßig fangen wir mit outside an
        self.info_lbl = Label(
            text="Wähle ein Gerät für den Slot [b]outside[/b]:", markup=True,
            size_hint_y=None, height=dp_scaled(25), font_size=sp_scaled(23), color=(0.8, 0.8, 0.8, 1)
        )
        self.box.add_widget(self.info_lbl)

        # Umschalter für den Ziel-Sensor (outside vs inside)
        target_selector = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(8))
        self.btn_outside = GlassButton(text="Slot: OUTSIDE", font_size=sp_scaled(30))
        self.btn_outside.color = (0.2, 1, 0.4, 1) # Aktiv-Farbe
        self.btn_outside.bind(on_release=lambda x: self._set_target_sensor("outside"))
        
        self.btn_inside = GlassButton(text="Slot: INSIDE", font_size=sp_scaled(30))
        self.btn_inside.bind(on_release=lambda x: self._set_target_sensor("inside"))
        
        target_selector.add_widget(self.btn_outside)
        target_selector.add_widget(self.btn_inside)
        self.box.add_widget(target_selector)

        # NEU: Button zum Abwählen / Zurücksetzen auf Werkseinstellung (00:00:00:00:00:00)
        self.unpair_btn = GlassButton(text="AKTUELLEN SLOT LEEREN", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(35))
        self.unpair_btn.color = (1.0, 0.6, 0.2, 1) # Orange Warnfarbe
        self.unpair_btn.bind(on_release=lambda x: self._pair_selected("00:00:00:00:00:00"))
        self.box.add_widget(self.unpair_btn)


        # ScrollView für die dynamisch reinfliegenden ADV-Geräte
        self.scroll = ScrollView(size_hint=(1, 1), bar_width=dp_scaled(4))
        self.list_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp_scaled(5))
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll.add_widget(self.list_layout)
        self.box.add_widget(self.scroll)

        # Schließen-Button unten
        close_btn = GlassButton(text="SCHLIESSEN", font_size=sp_scaled(20), size_hint_y=None, height=dp_scaled(40))
        close_btn.color = (1, 0.3, 0.3, 1)
        close_btn.bind(on_release=lambda x: self.screen.close_bluetooth_settings())
        self.box.add_widget(close_btn)


        self.add_widget(self.box)

        # Reaktiv-Clock starten, um die Liste alle 1 Sekunden live aus dem Stream zu aktualisieren
        self.update_event = Clock.schedule_interval(self._populate_discovered_devices, 1.0)

    def _set_target_sensor(self, sensor_type):
        """Schaltet um, für welchen Slot wir gerade eine MAC suchen"""
        self.target_sensor = sensor_type
        if sensor_type == "outside":
            self.info_lbl.text = "Wähle ein Gerät für den Slot [b]OUTSIDE[/b]:"
            self.btn_outside.color = (0.2, 1, 0.4, 1)
            self.btn_inside.color = (1, 1, 1, 1)
        else:
            self.info_lbl.text = "Wähle ein Gerät für den Slot [b]INSIDE[/b]:"
            self.btn_outside.color = (1, 1, 1, 1)
            self.btn_inside.color = (0.2, 1, 0.4, 1)
        self._populate_discovered_devices()

    def _populate_discovered_devices(self, *_):
        """Liest die permanent vom ESP gefischten Geräte aus, dämpft das Springen via Cache und baut die Zeilen"""
        self.list_layout.clear_widgets()
        now = time.time()

        # 1. Aktuell zugewiesene MACs aus den Rohdaten des Hauptscreens extrahieren
        current_outside_mac = ""
        current_inside_mac = ""
        
        ble_data = getattr(self.screen, 'ble_sensors_raw_data', {})
        if ble_data:
            current_outside_mac = ble_data.get("outside", {}).get("mac", "").lower()
            current_inside_mac = ble_data.get("inside", {}).get("mac", "").lower()

        # 2. Neue Geräte vom Hauptscreen in den lokalen Cache schaufeln
        devices = getattr(self.screen, 'discovered_ble_devices', [])
        for dev in devices:
            mac = dev.get("mac", "00:00:00:00:00:00").lower()
            name = dev.get("name", "Unknown")
            if mac != "00:00:00:00:00:00":
                self._device_cache[mac] = {
                    "name": name,
                    "last_seen": now
                }

        # 3. Alte Cache-Einträge entfernen
        dead_macs = [mac for mac, data in self._device_cache.items() if now - data["last_seen"] > self.CACHE_TIMEOUT]
        for mac in dead_macs:
            del self._device_cache[mac]

        # 4. UI aufbauen basierend auf dem beruhigten Cache
        if not self._device_cache:
            self.list_layout.add_widget(Label(
                text="Suche nach ADV-Paketen...", font_size=sp_scaled(20), 
                color=(0.6, 0.6, 0.6, 1), size_hint_y=None, height=dp_scaled(30)
            ))
            return

        # Sortiert nach Name, damit die Zeilen fest stehen bleiben
        for mac, data in sorted(self._device_cache.items(), key=lambda item: item[1]["name"]):
            name = data["name"]
            normalized_mac = mac.lower()
            
            row = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(5))
            
            # Status-Ermittlung für das visuelle Feedback
            is_active_here = False
            is_active_other = False
            status_tag = ""

            if self.target_sensor == "outside":
                if normalized_mac == current_outside_mac:
                    is_active_here = True
                elif normalized_mac == current_inside_mac:
                    is_active_other = True
                    status_tag = " [color=ffaa33](In Inside Slot)[/color]"
            else: # target_sensor == "inside"
                if normalized_mac == current_inside_mac:
                    is_active_here = True
                elif normalized_mac == current_outside_mac:
                    is_active_other = True
                    status_tag = " [color=ffaa33](In Outside Slot)[/color]"

            # Label mit optionalem Status-Tag
            lbl_text = f"{name}{status_tag}\n[color=888888]{mac.upper()}[/color]"
            lbl = Label(text=lbl_text, markup=True, font_size=sp_scaled(20), halign="left", size_hint_x=0.6)
            lbl.bind(size=lambda s,v: setattr(lbl, 'text_size', v))
            row.add_widget(lbl)
            
            # Button dynamisch einfärben und beschriften
            pair_btn = GlassButton(size_hint_x=0.4, font_size=sp_scaled(20))
            
            if is_active_here:
                pair_btn.text = "AKTIV"
                pair_btn.color = (0.2, 1.0, 0.4, 1) # Sattes Grün für das verbundene Gerät im aktuellen Slot
                # Klick trennt die Verbindung (sendet Null-MAC)
                pair_btn.bind(on_release=lambda x: self._pair_selected("00:00:00:00:00:00"))
            elif is_active_other:
                pair_btn.text = "WECHSELN"
                pair_btn.color = (1.0, 0.6, 0.2, 0.6) # Orange/Abgedunkelt: Gerät blockiert, kann aber "rübergeholt" werden
                pair_btn.bind(on_release=lambda x, m=mac: self._pair_selected(m))
            else:
                pair_btn.text = "PAIR"
                pair_btn.color = (1, 1, 1, 1) # Standard-Zustand
                pair_btn.bind(on_release=lambda x, m=mac: self._pair_selected(m))
                
            row.add_widget(pair_btn)
            self.list_layout.add_widget(row)

    def _pair_selected(self, mac):
        """Feuert die ausgewählte MAC (oder 00:00:00:00:00:00) über die Engine zum ESP32"""
        kwargs = {}
        if self.target_sensor == "outside":
            kwargs["pair_outside"] = mac
        else:
            kwargs["pair_inside"] = mac

        self.screen._send_grow_payload(
            kwargs,
            context="bluetooth_settings",
            reset_after_ack=False,
            show_status=True
        )

        # BLE toggles moved to main footer; overlay remains for pairing only.

    def on_close(self):
        """Stoppt den reaktiven Timer, damit im Hintergrund keine Ressourcen fressen"""
        Clock.unschedule(self.update_event)
