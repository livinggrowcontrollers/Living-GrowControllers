import os
import time
import urllib.request
import threading
import config
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

from platform_utils import is_android


def get_firmware_root():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base = os.path.abspath(
        os.path.join(current_dir, "..", "..", "..", "data", "firmware")
    )
    return base


class OtaSettingsOverlay(RelativeLayout):
    def __init__(self, screen, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.screen = screen
        
        self.mac = GLOBAL_STATE.get_active_device_id() or "00:00:00:00:00:00"
        self.selected_file_path = None
        self.selected_item_widget = None
        self.firmware_dir = get_firmware_root()

        if not os.path.exists(self.firmware_dir):
            try:
                os.makedirs(self.firmware_dir, exist_ok=True)
            except Exception as e:
                print(f"[OTA] Fehler beim Erstellen des Ordners: {e}")

        # Hintergrund-Abdunklung
        from kivy.uix.widget import Widget

        self.bg_btn = Widget()
        with self.bg_btn.canvas:
            Color(0, 0, 0, 0.6)
            self.bg_rect = RoundedRectangle(pos=self.bg_btn.pos, size=self.bg_btn.size)

        self.bg_btn.bind(pos=lambda s,v: setattr(self.bg_rect, 'pos', v),
                        size=lambda s,v: setattr(self.bg_rect, 'size', v))        
        self.bg_btn.bind(on_release=lambda *_: self.screen.close_ota_settings())
        self.add_widget(self.bg_btn)

        # Hauptfenster (Höhe leicht erhöht für beide Balken)
        self.box = BoxLayout(
            orientation="vertical", 
            padding=[dp_scaled(20), dp_scaled(15)], 
            spacing=dp_scaled(10),
            size_hint=(None, None), 
            size=(dp_scaled(600), dp_scaled(560)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        with self.box.canvas.before:
            Color(0, 0, 0, 0.75)
            self.box_bg = RoundedRectangle(pos=self.box.pos, size=self.box.size, radius=[dp_scaled(12)])
        self.box.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        # 1. Titel
        self.box.add_widget(Label(
            text="OTA FIRMWARE UPDATE", 
            bold=True, 
            font_size=sp_scaled(20), 
            size_hint_y=None, 
            height=dp_scaled(30), 
            color=(0.2, 1, 0.4, 1)
        ))

        self.box.add_widget(Label(
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
        self.box.add_widget(scroll)

        self.refresh_file_list()

        # BAR 1: Download-Fortschritt (Blau)
        self.box.add_widget(Label(text="Download Status", size_hint_y=None, height=dp_scaled(15), font_size=sp_scaled(12), color=(0.2, 0.8, 1, 0.6), halign="left"))
        self.download_progress_bar = SegmentedProgressBar(
            size_hint_y=None, 
            height=dp_scaled(10),
            num_segments=30,
            active_color=(0.2, 0.8, 1.0, 1.0),
            inactive_color=(0.15, 0.15, 0.15, 1.0)
        )
        self.download_progress_bar.value = 0
        self.box.add_widget(self.download_progress_bar)

        # BAR 2: Flash-Fortschritt (Grün/Orange)
        self.box.add_widget(Label(text="Flash Status", size_hint_y=None, height=dp_scaled(15), font_size=sp_scaled(12), color=(0.2, 1.0, 0.4, 0.6), halign="left"))
        self.progress_bar = SegmentedProgressBar(
            size_hint_y=None, 
            height=dp_scaled(10),
            num_segments=30,
            active_color=(0.2, 1.0, 0.4, 1.0),
            inactive_color=(0.15, 0.15, 0.15, 1.0)
        )
        self.progress_bar.value = 0
        self.box.add_widget(self.progress_bar)

        # 3. Action-Buttons
        btn_box = BoxLayout(size_hint_y=None, height=dp_scaled(45), spacing=dp_scaled(10))
        
        self.download_btn = GlassButton(text="[font=FA]\uf019[/font] DOWNLOAD", markup=True, font_size=sp_scaled(15))
        self.download_btn.bind(on_release=self.trigger_download)
        
        self.flash_btn = GlassButton(text="[font=FA]\uf0e7[/font] JETZT FLASHEN", markup=True, font_size=sp_scaled(15))
        self.flash_btn.bind(on_release=self.trigger_flash_alias)
        self.flash_btn.opacity = 0.5
        
        self.cancel_btn = GlassButton(text="SCHLIESSEN", font_size=sp_scaled(15))
        self.cancel_btn.color = (1, 0.3, 0.3, 1)
        self.cancel_btn.bind(on_release=lambda x: self.screen.close_ota_settings())
        
        btn_box.add_widget(self.download_btn)
        btn_box.add_widget(self.flash_btn)
        btn_box.add_widget(self.cancel_btn)
        self.box.add_widget(btn_box)
        
        # Status Label
        self.status_label = Label(text="Bitte wähle eine Firmware-Datei aus der Liste", size_hint_y=None, height=dp_scaled(24), halign='center', markup=True)
        self.box.add_widget(self.status_label)

        self.add_widget(self.box)

    def refresh_file_list(self):
        """Liest das Firmware-Verzeichnis aus und listet alle gefundenen Dateien auf."""
        self.file_list_layout.clear_widgets()

        base = get_firmware_root()

        if os.path.exists(base):
            files = [
                f for f in sorted(os.listdir(base))
                if os.path.isfile(os.path.join(base, f))
            ]
        else:
            files = []
            print(f"[OTA] Firmware-Ordner nicht gefunden: {base}")

        if not files:
            self.file_list_layout.add_widget(Label(
                text=f"Keine Firmware-Dumps gefunden.\n{base}",
                color=(0.6, 0.6, 0.6, 1),
                size_hint_y=None,
                height=dp_scaled(50),
                font_size=sp_scaled(14)
            ))
            return

        for filename in files:
            file_path = os.path.join(base, filename)

            try:
                size_kb = os.path.getsize(file_path) / 1024
                size_str = f"{size_kb:.1f} KB"
            except Exception:
                size_str = "Unbekannte Größe"

            # DIREKTER FIX: Kein verschachteltes Layout mehr. 
            # Wir nutzen direkt einen Button mit Markup für Name und Größe links/rechts ausgerichtet.
            item_btn = Button(
                text=f" [font=FA]\uf15b[/font] {filename}  [color=b3b3b3]{size_str}[/color]",
                markup=True,
                halign="left",
                valign="middle",
                background_normal="",
                background_color=(0.1, 0.1, 0.1, 0.4),
                size_hint_y=None,
                height=dp_scaled(38),
                padding=[dp_scaled(10), 0]
            )
            # Wichtig für halign="left", damit der Text sich an der Button-Breite ausrichtet
            item_btn.bind(size=item_btn.setter('text_size'))

            # Der Klick-Trigger zieht jetzt garantiert direkt auf dem Widget
            item_btn.bind(
                on_release=lambda btn, path=file_path, name=filename:
                    self.select_file(btn, path, name)
            )

            self.file_list_layout.add_widget(item_btn)
    def on_touch_down(self, touch):
        if not self.box.collide_point(*touch.pos):
            self.screen.close_ota_settings()
            return True
        return super().on_touch_down(touch)
    def select_file(self, widget, path, filename):
        if self.selected_item_widget:
            self.selected_item_widget.background_color = (0.1, 0.1, 0.1, 0.4)
        
        self.selected_item_widget = widget
        widget.background_color = (0.2, 1, 0.4, 0.25)

        self.selected_file_path = path
        self.flash_btn.opacity = 1.0
        
        self.status_label.color = (0.2, 1, 0.4, 1)
        self.status_label.text = f"[b]Ausgewählt:[/b] {filename}"

    def trigger_download(self, instance):
        """Startet den echten HTTP-Download in einem Hintergrund-Thread."""
        url = "https://github.com/livinggrowcontrollers/Living-GrowControllers/raw/refs/heads/main/Arduino/testble2/build/esp32.esp32.waveshare_esp32_s3_lcd_147/testble2.ino.bin"
        
        
        filename = "testble2.ino.bin"
        save_path = os.path.join(self.firmware_dir, filename)

        self.download_btn.disabled = True
        self.flash_btn.disabled = True
        self.download_progress_bar.value = 0
        self.status_label.color = (0.2, 0.8, 1, 1)
        self.status_label.text = "[font=FA]\uf019[/font] Verbinde zum Server..."

        threading.Thread(target=self._download_worker, args=(url, save_path), daemon=True).start()

    def _download_worker(self, url, save_path):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                downloaded = 0

                with open(save_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        f.write(buffer)

                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                        else:
                            percent = 50
                        
                        # UI-Update über die Kivy-Clock ausführen
                        Clock.schedule_once(lambda dt, p=percent, d=downloaded, t=total_size: self._update_download_progress(p, d, t))

            Clock.schedule_once(lambda dt: self._download_finished(True, save_path))

        except Exception as e:
            Clock.schedule_once(lambda dt: self._download_finished(False, str(e)))

    def _update_download_progress(self, percent, downloaded, total_size):
        self.download_progress_bar.value = percent
        dl_mb = downloaded / (1024 * 1024)
        t_mb = total_size / (1024 * 1024)
        self.status_label.text = (
            f"[font=FA]\uf019[/font] Download: [b]{percent:.1f}%[/b] ({dl_mb:.2f}/{t_mb:.2f} MB)"
        )

    def _download_finished(self, success, result):
        self.download_btn.disabled = False
        if success:
            self.download_progress_bar.value = 100
            self.status_label.color = (0.2, 1, 0.4, 1)
            self.status_label.text = "[font=FA]\uf00c[/font] Download erfolgreich gelistet!"
            self.refresh_file_list()
        else:
            self.status_label.color = (1, 0.3, 0.3, 1)
            self.status_label.text = f"[font=FA]\uf071[/font] Download-Fehler: {result}"

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
        self.progress_bar.value = 100
        self.status_label.color = (0.2, 1, 0.4, 1)
        self.status_label.text = "[font=FA]\uf00c[/font] [b]Upload abgeschlossen![/b] Schließe Fenster..."
        self.screen._ota_is_waiting = False
        
        Clock.unschedule(self._close_self)
        Clock.schedule_once(self._close_self, 1.0)

    def _close_self(self, *args):
        self.screen.close_ota_settings()

    def reset_ui_after_failure(self):
        self.flash_btn.disabled = False
        self.download_btn.disabled = False
        self.cancel_btn.disabled = False
        self.bg_btn.disabled = False