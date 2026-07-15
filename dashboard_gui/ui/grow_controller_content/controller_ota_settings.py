import os
import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock

# Deine bestehenden GUI-System-Importe
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE

# Deine SegmentedProgressBar importieren
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar

class OtaSettingsOverlay(RelativeLayout):
    def __init__(self, screen, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.screen = screen
        
        # MAC-Adresse direkt über das globale GLOBAL_STATE abrufen
        self.mac = GLOBAL_STATE.get_active_device_id() or "00:00:00:00:00:00"
        
        # Aktuell ausgewählte Datei für das Flashen
        self.selected_file_path = None
        self.selected_item_widget = None

        # Pfad zur Sandbox-Firmware definieren
        self.firmware_dir = os.path.join("data", "firmware")
        if not os.path.exists(self.firmware_dir):
            try:
                os.makedirs(self.firmware_dir, exist_ok=True)
            except Exception as e:
                print(f"[OTA] Fehler beim Erstellen des Ordners: {e}")

        # Hintergrund-Abdunklung + Schließen bei Klick ins Leere
        self.bg_btn = Button(background_normal="", background_down="", background_color=(0, 0, 0, 0.6))
        self.bg_btn.bind(on_release=lambda *_: self.screen.close_ota_settings())
        self.add_widget(self.bg_btn)

        # Hauptfenster (Content Box)
        box = BoxLayout(
            orientation="vertical", 
            padding=[dp_scaled(20), dp_scaled(15)], 
            spacing=dp_scaled(12),
            size_hint=(None, None), 
            size=(dp_scaled(600), dp_scaled(500)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        with box.canvas.before:
            Color(0, 0, 0, 0.75)
            self.box_bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp_scaled(12)])
        box.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        # 1. Titel
        box.add_widget(Label(
            text="OTA FIRMWARE UPDATE", 
            bold=True, 
            font_size=sp_scaled(20), 
            size_hint_y=None, 
            height=dp_scaled(30), 
            color=(0.2, 1, 0.4, 1)
        ))

        # Sub-Header für lokale Files
        box.add_widget(Label(
            text="Lokale Firmware-Dumps in der Sandbox (/data/firmware/):",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp_scaled(25),
            font_size=sp_scaled(14),
            text_size=(dp_scaled(560), None)
        ))

        # 2. Dateiliste mit ScrollView
        self.file_list_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp_scaled(5))
        self.file_list_layout.bind(minimum_height=self.file_list_layout.setter('height'))
        
        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(4))
        scroll.add_widget(self.file_list_layout)
        box.add_widget(scroll)

        # Liste befüllen
        self.refresh_file_list()

        # Segmentierte Progressbar für die Flash-Visualisierung
        self.progress_bar = SegmentedProgressBar(
            size_hint_y=None, 
            height=dp_scaled(12),
            num_segments=30,
            active_color=(0.2, 1.0, 0.4, 1.0),
            inactive_color=(0.15, 0.15, 0.15, 1.0)
        )
        self.progress_bar.value = 0
        box.add_widget(self.progress_bar)

        # 3. Action-Buttons (Unter der Liste)
        btn_box = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(10))
        
        # Download-Button
        self.download_btn = GlassButton(text="[font=FA]\uf019[/font] DOWNLOAD", markup=True, font_size=sp_scaled(15))
        self.download_btn.bind(on_release=self.trigger_download_alias)
        
        # Flash-Button (Deaktiviert bis File ausgewählt ist)
        self.flash_btn = GlassButton(text="[font=FA]\uf0e7[/font] JETZT FLASHEN", markup=True, font_size=sp_scaled(15))
        self.flash_btn.bind(on_release=self.trigger_flash_alias)
        self.flash_btn.opacity = 0.5
        
        # Abbrechen
        self.cancel_btn = GlassButton(text="SCHLIESSEN", font_size=sp_scaled(15))
        self.cancel_btn.color = (1, 0.3, 0.3, 1)
        self.cancel_btn.bind(on_release=lambda x: self.screen.close_ota_settings())
        
        btn_box.add_widget(self.download_btn)
        btn_box.add_widget(self.flash_btn)
        btn_box.add_widget(self.cancel_btn)
        box.add_widget(btn_box)
        
        # Status Label
        self.status_label = Label(text="Bitte wähle eine Firmware-Datei aus der Liste", size_hint_y=None, height=dp_scaled(24), halign='center', markup=True)
        box.add_widget(self.status_label)

        self.add_widget(box)

    def refresh_file_list(self):
        """Liest das Verzeichnis aus und listet alle gefundenen Dateien auf."""
        self.file_list_layout.clear_widgets()
        
        try:
            files = [f for f in os.listdir(self.firmware_dir) if os.path.isfile(os.path.join(self.firmware_dir, f))]
        except Exception as e:
            files = []
            print(f"[OTA] Fehler beim Lesen des Verzeichnisses: {e}")

        if not files:
            self.file_list_layout.add_widget(Label(
                text="Keine Firmware-Dumps gefunden.",
                color=(0.6, 0.6, 0.6, 1),
                size_hint_y=None,
                height=dp_scaled(30),
                font_size=sp_scaled(14)
            ))
            return

        for filename in files:
            file_path = os.path.join(self.firmware_dir, filename)
            try:
                size_kb = os.path.getsize(file_path) / 1024
                size_str = f"{size_kb:.1f} KB"
            except Exception:
                size_str = "Unbekannte Größe"

            item_btn = Button(
                background_normal="",
                background_color=(0.1, 0.1, 0.1, 0.4),
                size_hint_y=None,
                height=dp_scaled(38)
            )
            
            item_layout = BoxLayout(orientation="horizontal", size_hint=(1, 1), padding=[dp_scaled(10), 0])
            
            lbl_name = Label(
                text=f"[font=FA]\uf15b[/font] {filename}", 
                markup=True,
                halign="left", 
                size_hint_x=0.7,
                text_size=(dp_scaled(350), None)
            )
            lbl_size = Label(
                text=size_str, 
                halign="right", 
                size_hint_x=0.3,
                color=(0.7, 0.7, 0.7, 1)
            )
            
            item_layout.add_widget(lbl_name)
            item_layout.add_widget(lbl_size)
            item_btn.add_widget(item_layout)
            
            item_btn.bind(on_release=lambda btn, path=file_path, name=filename: self.select_file(btn, path, name))
            self.file_list_layout.add_widget(item_btn)

    def select_file(self, widget, path, filename):
        """Markiert ein ausgewähltes File visuell und schaltet den Flash-Button frei."""
        if self.selected_item_widget:
            self.selected_item_widget.background_color = (0.1, 0.1, 0.1, 0.4)
        
        self.selected_item_widget = widget
        widget.background_color = (0.2, 1, 0.4, 0.25)

        self.selected_file_path = path
        self.flash_btn.opacity = 1.0
        
        self.status_label.color = (0.2, 1, 0.4, 1)
        self.status_label.text = f"[b]Ausgewählt:[/b] {filename}"

    def trigger_download_alias(self, instance):
        """Dummy Download-Träger."""
        self.status_label.color = (0.2, 0.8, 1, 1)
        self.status_label.text = "[font=FA]\uf019[/font] Download gestartet (Simuliert)..."

    def trigger_flash_alias(self, instance):
        if not self.selected_file_path:
            self.status_label.color = (1, 0.3, 0.3, 1)
            self.status_label.text = "Bitte wähle zuerst eine Firmware aus!"
            return

        self.flash_btn.disabled = True
        self.download_btn.disabled = True
        self.cancel_btn.disabled = True
        self.bg_btn.disabled = True

        self.status_label.color = (1, 0.72, 0.15, 1)
        self.status_label.text = "[font=FA]\uf0e7[/font] Flash-Vorgang gestartet... Bereite ESP32 vor."
        self.progress_bar.value = 0

        try:
            target_rev = int(time.time() % 100000)

            # Signalisiere dem Screen, dass wir updaten
            self.screen._last_sent_ota_rev = target_rev
            self.screen._ota_is_waiting = True

            GLOBAL_STATE.send_overlay_command(
                "ota_update",
                file_path=self.selected_file_path,
                new_ota_rev=target_rev,
                on_progress=self.update_progress_from_thread,
                on_done=self.update_done_from_thread
            )
        except Exception as e:
            self.status_label.color = (1, 0.3, 0.3, 1)
            self.status_label.text = f"Fehler beim Starten des Flashs: {e}"
            self.reset_ui_after_failure()

    def update_progress_from_thread(self, sent, total):
        percent = (sent / total) * 100
        Clock.schedule_once(lambda dt: self._update_progress_ui(sent, total, percent))

    def _update_progress_ui(self, sent, total, percent):
        self.progress_bar.value = percent
        sent_mb = sent / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.status_label.text = (
            f"[font=FA]\uf0ee[/font] Übertrage: [b]{percent:.1f}%[/b] "
            f"({sent_mb:.2f}MB / {total_mb:.2f}MB)"
        )
        
        # SOFORT-SCHLIESSEN BEI 100% UPLOAD:
        if percent >= 100.0:
            self._trigger_instant_success()

    def update_done_from_thread(self, success, message):
        Clock.schedule_once(lambda dt: self._update_done_ui(success, message))

    def _update_done_ui(self, success, message):
        if success:
            self._trigger_instant_success()
        else:
            self.status_label.color = (1, 0.3, 0.3, 1)
            self.status_label.text = f"[font=FA]\uf071[/font] Fehler: {message}"
            self.reset_ui_after_failure()

    def _trigger_instant_success(self):
        """Beendet den Upload im UI sofort ohne auf die veränderte Revision zu warten."""
        self.progress_bar.value = 100
        self.status_label.color = (0.2, 1, 0.4, 1)
        self.status_label.text = "[font=FA]\uf00c[/font] [b]Upload abgeschlossen![/b] Schließe Fenster..."
        
        # Reset des globalen Wartestatus, da wir fertig sind
        self.screen._ota_is_waiting = False
        
        # Schließe das Overlay nach 1 Sekunde Verzögerung
        Clock.unschedule(self._close_self)
        Clock.schedule_once(self._close_self, 1.0)

    def _close_self(self, *args):
        self.screen.close_ota_settings()

    def reset_ui_after_failure(self):
        self.flash_btn.disabled = False
        self.download_btn.disabled = False
        self.cancel_btn.disabled = False
        self.bg_btn.disabled = False