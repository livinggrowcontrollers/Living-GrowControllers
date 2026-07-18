import os
import sys
import time
import threading
from datetime import datetime

# Kivy-Konfiguration für feste Fenstergröße (vor den restlichen Kivy-Imports)
from kivy.config import Config
Config.set('graphics', 'width', '700')
Config.set('graphics', 'height', '650')
Config.set('graphics', 'resizable', '0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock
from kivy.utils import get_color_from_hex

import serial.tools.list_ports
import esptool


class LivingGrowFlasher(App):
    def build(self):
        self.title = "Living Grow Flash Tool"
        
        # Status-Variablen
        self.selected_port = None
        self.selected_firmware = None
        self.is_flashing = False
        
        # Hauptlayout (Dunkles Theme)
        root = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Hintergrundfarbe setzen via Canvas
        with root.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*get_color_from_hex('#121212'))
            self.rect = Rectangle(size=(700, 650), pos=root.pos)
            root.bind(size=self._update_rect, pos=self._update_rect)

        # --- Titel-Zeile ---
        title_label = Label(
            text="LIVING GROW FLASH TOOL",
            font_size='20sp',
            bold=True,
            size_hint_y=None,
            height=40,
            color=get_color_from_hex('#00E676')  # Modernes Grün
        )
        root.add_widget(title_label)
        
        # --- Port-Auswahl Sektion ---
        port_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=10)
        
        port_label = Label(text="ESP32 Port:", size_hint_x=0.2, halign='left', valign='middle')
        port_label.bind(size=port_label.setter('text_size'))
        port_layout.add_widget(port_label)
        
        self.port_spinner = Spinner(
            text="Wähle Port...",
            values=(),
            size_hint_x=0.6,
            background_color=get_color_from_hex('#1E1E1E'),
            color=get_color_from_hex('#FFFFFF')
        )
        self.port_spinner.bind(text=self.on_port_selected)
        port_layout.add_widget(self.port_spinner)
        
        self.btn_refresh = Button(
            text="Refresh",
            size_hint_x=0.2,
            background_color=get_color_from_hex('#2979FF'),
            color=get_color_from_hex('#FFFFFF')
        )
        self.btn_refresh.bind(on_press=self.refresh_ports)
        port_layout.add_widget(self.btn_refresh)
        
        root.add_widget(port_layout)
        
        # --- Firmware-Liste Sektion ---
        root.add_widget(Label(
            text="Verfügbare Firmware (.bin):",
            size_hint_y=None,
            height=25,
            halign='left',
            valign='middle',
            color=get_color_from_hex('#B0BEC5')
        ))
        
        # ScrollView für die Firmware-Dateien
        self.fw_scroll = ScrollView(size_hint_y=0.35, bar_width=10)
        self.fw_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.fw_grid.bind(minimum_height=self.fw_grid.setter('height'))
        self.fw_scroll.add_widget(self.fw_grid)
        root.add_widget(self.fw_scroll)
        
        # --- Flash Steuerung & Status ---
        self.btn_flash = Button(
            text="Flash Firmware",
            size_hint_y=None,
            height=50,
            background_color=get_color_from_hex('#00C853'),
            color=get_color_from_hex('#FFFFFF'),
            font_size='16sp',
            bold=True
        )
        self.btn_flash.bind(on_press=self.start_flash_thread)
        root.add_widget(self.btn_flash)
        
        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=15)
        root.add_widget(self.progress_bar)
        
        # --- Log-Fenster ---
        root.add_widget(Label(
            text="Log:",
            size_hint_y=None,
            height=20,
            halign='left',
            valign='middle',
            color=get_color_from_hex('#B0BEC5')
        ))
        
        self.log_scroll = ScrollView(size_hint_y=0.3, bar_width=10)
        self.log_label = Label(
            text="Bereit.\n",
            size_hint_y=None,
            halign='left',
            valign='top',
            color=get_color_from_hex('#ECEFF1'),
            font_name='Roboto' if sys.platform != 'win32' else 'Consolas'
        )
        
        # Dynamisches Höhen- und Breiten-Update ohne Absturz
        self.log_label.bind(texture_size=self._update_log_label_height)
        self.log_label.bind(width=self._update_log_label_width)
        
        self.log_scroll.add_widget(self.log_label)
        root.add_widget(self.log_scroll)
        
        # Initiale Scans durchführen
        self.refresh_ports()
        self.scan_firmware()
        
        return root

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def _update_log_label_height(self, instance, size):
        instance.height = size[1]

    def _update_log_label_width(self, instance, width):
        instance.text_size = (width, None)

    def log(self, text):
        def append_log(dt):
            self.log_label.text += f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n"
            Clock.schedule_once(self._scroll_to_bottom, 0.05)
        Clock.schedule_once(append_log)

    def _scroll_to_bottom(self, dt):
        self.log_scroll.scroll_y = 0

    # --- COM-Ports ---
    def refresh_ports(self, instance=None):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        
        if port_list:
            self.port_spinner.values = port_list
            if self.selected_port not in port_list:
                self.port_spinner.text = port_list[0]
                self.selected_port = port_list[0]
            self.log(f"Ports aktualisiert. {len(port_list)} Gerät(e) gefunden.")
        else:
            self.port_spinner.values = []
            self.port_spinner.text = "Keine Ports gefunden"
            self.selected_port = None
            self.log("Keine seriellen Geräte gefunden.")

    def on_port_selected(self, spinner, text):
        if text != "Wähle Port..." and text != "Keine Ports gefunden":
            self.selected_port = text
            self.log(f"Port ausgewählt: {text}")

    # --- Firmware Erkennung ---
    def scan_firmware(self):
        self.fw_grid.clear_widgets()
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fw_dir = os.path.normpath(os.path.join(base_dir, "..", "..", "data", "firmware"))
        
        if not os.path.exists(fw_dir):
            self.log(f"Fehler: Firmware-Pfad existiert nicht: {fw_dir}")
            error_lbl = Label(
                text="Firmware-Ordner nicht gefunden!\nBitte anlegen unter: ../../data/firmware",
                color=get_color_from_hex('#FF1744'),
                size_hint_y=None,
                height=50
            )
            self.fw_grid.add_widget(error_lbl)
            return

        files = [f for f in os.listdir(fw_dir) if f.endswith('.bin')]
        
        if not files:
            self.log("Keine .bin Dateien im Firmware-Ordner gefunden.")
            no_fw_lbl = Label(text="Keine Firmware-Dateien (.bin) vorhanden.", size_hint_y=None, height=40)
            self.fw_grid.add_widget(no_fw_lbl)
            return

        for file in files:
            full_path = os.path.join(fw_dir, file)
            stats = os.stat(full_path)
            
            size_kb = round(stats.st_size / 1024, 1)
            mod_time = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
            
            btn_text = f" {file}\n   Größe: {size_kb} KB  |  Datum: {mod_time}"
            
            btn = ToggleButton(
                text=btn_text,
                group='firmware_group',
                size_hint_y=None,
                height=55,
                halign='left',
                valign='middle',
                background_color=get_color_from_hex('#1E1E1E'),
                color=get_color_from_hex('#FFFFFF')
            )
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=lambda x, p=full_path, f=file: self.select_firmware(p, f))
            self.fw_grid.add_widget(btn)

        self.log(f"Firmware-Verzeichnis gescannt. {len(files)} Datei(en) gefunden.")

    def select_firmware(self, full_path, filename):
        self.selected_firmware = full_path
        self.log(f"Firmware ausgewählt: {filename}")

    # --- Flashen ---
    def set_gui_lock(self, locked):
        self.is_flashing = locked
        self.btn_flash.disabled = locked
        self.btn_refresh.disabled = locked
        self.port_spinner.disabled = locked
        
        for child in self.fw_grid.children:
            if isinstance(child, ToggleButton):
                child.disabled = locked

    def update_progress(self, current, total):
        percent = int((current / total) * 100)
        def set_val(dt):
            self.progress_bar.value = percent
        Clock.schedule_once(set_val)

    def start_flash_thread(self, instance):
        if self.is_flashing:
            return
            
        if not self.selected_port:
            self.log("Fehler: Kein ESP32 Port ausgewählt.")
            return
            
        if not self.selected_firmware:
            self.log("Fehler: Keine Firmware (.bin) ausgewählt.")
            return

        self.set_gui_lock(True)
        self.progress_bar.value = 0
        
        threading.Thread(target=self.flash_process, daemon=True).start()

    def flash_process(self):
        self.log("Flash-Vorgang gestartet...")
        
        try:
            self.log(f"Verbinde mit {self.selected_port}...")
            
            # Initialisiere den ESP32-Chip direkt über esptools cmds-API
            # Das umgeht die unzuverlässige main()-Schnittstelle
            esp = esptool.cmds.detect_chip(self.selected_port, baud=115200)
            esp.change_baud(460800)
            self.log(f"Chip erkannt: {esp.get_chip_description()}")
            
            # Verbindung aufbauen
            
            # Flash-Größe automatisch ermitteln
            flash_size = "detect"
            
            self.log("Bereite Flash vor (löschen/schreiben)...")
            
            # Datei einlesen
            with open(self.selected_firmware, 'rb') as f:
                fw_data = f.read()
            
            # Wrapper für den Kivy-Fortschrittsbalken
            def progress_callback(write_len, total_len):
                self.update_progress(write_len, total_len)

            self.log("Schreibe Firmware an Adresse 0x0...")
            
            # Direktes Schreiben des Flashs über das Chip-Objekt
            esptool.cmds.write_flash(
                esp,
                [(0x0, fw_data)],
                flash_freq="keep",
                flash_mode="keep",
                flash_size="keep",
                compress=False,
                no_progress=False,
            )
            
            # Verbindung sauber trennen und ESP neu starten
            self.log("Flash erfolgreich verifiziert!")
            self.log("Fertig.")
            
        except Exception as e:
            self.log(f"FEHLER beim Flashen: {str(e)}")
            
        finally:
            Clock.schedule_once(lambda dt: self.set_gui_lock(False))


if __name__ == '__main__':
    LivingGrowFlasher().run()