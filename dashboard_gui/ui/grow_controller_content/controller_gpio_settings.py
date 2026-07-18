# dashboard_gui/ui/grow_controller_content/controller_gpio_settings.py

import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.image import Image
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from dashboard_gui.ui.common.image_viewer import ZoomableImagePopup
ASSET_ROOT = os.path.join("dashboard_gui", "assets")
from dashboard_gui.circulation_fan_registry import MAX_CIRCULATION_FANS, fan_gpio_keys

PINOUT_PIC = os.path.join(
    ASSET_ROOT,
    "hardware_pics",
    "esp32_pinout_full.png"
)
try:
    from dashboard_gui.ui.grow_controller_content.pin_matrix import validate_and_build_pins, get_pin_info, REQUIRED_ROLES
except Exception:
    # Fallbacks for non-UI contexts/tests
    def validate_and_build_pins(current, new_kwargs):
        current_gpios = current.get("gpios", {}) if current else {}
        merged = {}
        keys = [
            "p_reset", "p_c_fan", "p_c_tac", "p_e_fan", "p_e_tac",
            "p_light", "p_i2c_sda", "p_i2c_scl", "p_rtc_sda", "p_rtc_scl", "p_bat"
        ]
        for k in keys:
            if k in new_kwargs:
                try:
                    merged[k] = int(new_kwargs[k])
                except Exception:
                    merged[k] = -1
            else:
                merged[k] = int(current_gpios.get(k, -1))
        return True, merged

    def get_pin_info(pin):
        return ([], "Unbekannter Pin")

    REQUIRED_ROLES = {
        "p_reset":   "INPUT",
        "p_c_fan":   "PWM",
        "p_c_tac":   "INPUT",
        "p_e_fan":   "PWM",
        "p_e_tac":   "INPUT",
        "p_light":   "PWM",
        "p_i2c_sda": "I2C",
        "p_i2c_scl": "I2C",
        "p_rtc_sda": "I2C",
        "p_rtc_scl": "I2C",
        "p_bat":     "ANALOG"
    }


class GpioSettingsPanel(BoxLayout):
    def __init__(self, screen, embedded=True, **kwargs):
        size_hint = (1, 1) if embedded else (None, None)
        size = kwargs.pop('size', (dp_scaled(600), dp_scaled(600))) if not embedded else None
        super().__init__(orientation='vertical', padding=[dp_scaled(20), dp_scaled(15)], spacing=dp_scaled(12), size_hint=size_hint, **kwargs)
        self.screen = screen

        if not embedded:
            self.size = size
            self.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

        with self.canvas.before:
            Color(0, 0, 0, 0.62)
            self.box_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp_scaled(12)])
        self.bind(pos=lambda s, v: setattr(self.box_bg, 'pos', v), size=lambda s, v: setattr(self.box_bg, 'size', v))

        self.add_widget(Label(
            text="[font=FA]\uf0e7[/font] HAL - HARDWARE ROUTING CONFIG",
            font_size=sp_scaled(21),
            bold=True,
            color=(0.2, 1, 0.4, 1),
            size_hint_y=None,
            height=dp_scaled(25),
            markup=True
        ))

        cols_container = BoxLayout(orientation='horizontal', spacing=dp_scaled(10))

        self.left_scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.right_scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))

        self.left_grid = GridLayout(cols=2, size_hint_y=None, spacing=dp_scaled(10), padding=dp_scaled(5))
        self.left_grid.bind(minimum_height=self.left_grid.setter('height'))

        self.right_grid = GridLayout(cols=2, size_hint_y=None, spacing=dp_scaled(10), padding=dp_scaled(5))
        self.right_grid.bind(minimum_height=self.right_grid.setter('height'))

        self.left_scroll.add_widget(self.left_grid)
        self.right_scroll.add_widget(self.right_grid)

        cols_container.add_widget(self.left_scroll)
        cols_container.add_widget(self.right_scroll)
        self.add_widget(cols_container)

        self.current_gpios = getattr(self.screen, 'live_gpios', {})
        circulation_definitions = []
        for fan_id in range(1, MAX_CIRCULATION_FANS + 1):
            pwm, tacho, pull = fan_gpio_keys(fan_id)
            circulation_definitions.extend((
                (f"Circulation Fan {fan_id} (PWM)", pwm),
                (f"Circulation Fan {fan_id} Tacho", tacho),
                (f"Circulation Fan {fan_id} Pull", pull),
            ))

        self.gpio_definitions = [
            ("Reset Button", "p_reset"),
            *circulation_definitions,

            ("Exhaust Fan (Abluft)", "p_e_fan"),
            ("Exhaust Tacho", "p_e_tac"),
            ("Exhaust Pull", "p_e_tac_pull"),

            ("Main Light (PWM)", "p_light"),

            ("I2C Bus SDA", "p_i2c_sda"),
            ("I2C Bus SCL", "p_i2c_scl"),

            ("RTC SDA", "p_rtc_sda"),
            ("RTC SCL", "p_rtc_scl"),

            ("Battery Analogsensor", "p_bat"),
            ("Battery Pull", "p_bat_pull"),
        ]

        self.selected_gpios = {}
        self.is_dirty = False  # Verhindert ungewollte Live-Updates nach Reset/Änderung
        self.build_rows()
        btn_box = BoxLayout(
            size_hint_y=None,
            height=dp_scaled(40),
            spacing=dp_scaled(2)
        )

        pinout_btn = GlassButton(
            text="ESP32 PINOUT",
            font_size=sp_scaled(20),
            color=(0.3, 0.8, 1, 1)
        )
        pinout_btn.bind(on_release=self.show_pinout)

        save_btn = GlassButton(
            text="SPEICHERN & REBOOT",
            font_size=sp_scaled(20),
            color=(0.2, 1, 0.3, 1),
            markup=True
        )
        save_btn.bind(on_release=self.save_and_reboot)

        cancel_btn = GlassButton(
            text="STANDARD EINSTELLUNGEN",
            font_size=sp_scaled(20),
            color=(0.9, 0.5, 0.1, 1),
            markup=True
        )
        cancel_btn.bind(on_release=self.reset_to_defaults)

        btn_box.add_widget(pinout_btn)
        btn_box.add_widget(save_btn)
        btn_box.add_widget(cancel_btn)

        self.add_widget(btn_box)

    def build_rows(self):

        PULL_KEYS = {
            "p_e_tac_pull",
            "p_bat_pull",
        }
        PULL_KEYS.update(fan_gpio_keys(fan_id)[2] for fan_id in range(1, MAX_CIRCULATION_FANS + 1))
        available_gpios = [-1] + list(range(0, 34)) + list(range(34, 49))
        self.left_grid.clear_widgets()
        self.right_grid.clear_widgets()

        half = (len(self.gpio_definitions) + 1) // 2
        left_defs = self.gpio_definitions[:half]
        right_defs = self.gpio_definitions[half:]

        def add_rows(defs, grid):
            for label_text, key in defs:
                # Nur initialisieren, wenn noch nicht manuell editiert oder zurückgesetzt
                if not self.is_dirty or key not in self.selected_gpios:
                    current_val = self.current_gpios.get(key, -1)
                    self.selected_gpios[key] = current_val
                else:
                    current_val = self.selected_gpios[key]

                lbl = Label(text=label_text, font_size=sp_scaled(20), halign="left", size_hint_y=None, height=dp_scaled(40))
                lbl.bind(size=lambda s, v, l=lbl: setattr(l, 'text_size', v))
                grid.add_widget(lbl)

                if key in PULL_KEYS:

                    pull_names = {
                        0: "NONE",
                        1: "PULL-UP",
                        2: "PULL-DOWN",
                    }

                    btn = GlassButton(
                        text=f"{pull_names.get(current_val, 'NONE')}  [font=FA]\uf078[/font]",
                        markup=True,
                        size_hint_y=None,
                        height=dp_scaled(40),
                        size_hint_x=0.45
                    )

                    btn.bind(
                        on_release=lambda x, k=key, b=btn:
                        self.open_pull_picker(k, b)
                    )

                else:

                    btn_text = (
                        "DEAKTIVIERT (-1)"
                        if current_val == -1
                        else f"GPIO {current_val}"
                    )

                    btn = GlassButton(
                        text=f"{btn_text}  [font=FA]\uf078[/font]",
                        markup=True,
                        size_hint_y=None,
                        height=dp_scaled(40),
                        size_hint_x=0.45
                    )

                    btn.bind(
                        on_release=lambda x, k=key, b=btn:
                        self.open_pin_picker(k, b, available_gpios)
                    )
                grid.add_widget(btn)

        add_rows(left_defs, self.left_grid)
        add_rows(right_defs, self.right_grid)



    def open_pull_picker(self, key, target_button):

        popup = Popup(
            title=f"{key.upper()}",
            size_hint=(0.6, 0.4),
            background='',
            background_color=(0, 0, 0, 0)
        )

        content = BoxLayout(
            orientation='vertical',
            spacing=dp_scaled(10),
            padding=dp_scaled(15)
        )

        options = {
            0: "NONE",
            1: "PULL-UP",
            2: "PULL-DOWN",
        }

        for value, text in options.items():

            btn = GlassButton(
                text=text,
                size_hint_y=None,
                height=dp_scaled(50)
            )

            def choose(_, v=value, t=text):
                self.is_dirty = True
                self.selected_gpios[key] = v

                target_button.text = (
                    f"{t}  [font=FA]\uf078[/font]"
                )

                popup.dismiss()

            btn.bind(on_release=choose)

            content.add_widget(btn)

        popup.content = content
        popup.open()

    def reset_to_defaults(self, *_):
        """Setzt die UI-Auswahl auf Standardwerte und sperrt Live-Überschreibungen."""
        defaults = {
            "p_reset": 7,

            "p_e_fan": 47,
            "p_e_tac": 1,
            "p_e_tac_pull": 1,

            "p_light": 21,

            "p_i2c_sda": 4,
            "p_i2c_scl": 5,

            "p_rtc_sda": 13,
            "p_rtc_scl": 14,

            "p_bat": 6,
            "p_bat_pull": 0,
        
        }
        for fan_id in range(1, MAX_CIRCULATION_FANS + 1):
            pwm, tacho, pull = fan_gpio_keys(fan_id)
            defaults.update({pwm: 45 if fan_id == 1 else -1, tacho: 2 if fan_id == 1 else -1, pull: 1})
        self.is_dirty = True
        for key, val in defaults.items():
            self.selected_gpios[key] = int(val)
        self.build_rows()
    
    def get_role_style(self, role: str, is_forbidden: bool = False) -> tuple:
        if is_forbidden:
            return "\uf05e", "[color=FF3333]", (1, 0.2, 0.2, 1)
        styles = {
            "INPUT":   ("\uf0a1", "[color=00F0FF]", (0, 0.94, 1, 1)),
            "PWM":     ("\uf0e7", "[color=FFAA00]", (1, 0.66, 0, 1)),
            "I2C":     ("\uf2db", "[color=D400FF]", (0.83, 0, 1, 1)),
            "ANALOG":  ("\uf1dd", "[color=00E5FF]", (0, 0.9, 1, 1)),
            "Deaktiviert": ("\uf057", "[color=888888]", (0.5, 0.5, 0.5, 1))
        }
        return styles.get(role, ("\uf111", "[color=FFFFFF]", (1, 1, 1, 1)))

    def _build_picker_button(self, display_text, pin, key, target_button, popup, compatible):
        """Isolierter Scope für jeden einzelnen Picker-Button, um UnboundLocalError komplett zu eliminieren."""
        p_btn = GlassButton(
            text=display_text, 
            size_hint_y=None, 
            height=dp_scaled(48), 
            markup=True,
            halign="left"
        )
        p_btn.bind(size=lambda s, v, b=p_btn: setattr(b, 'text_size', (v[0] - dp_scaled(20), None)))

        if not compatible:
            p_btn.disabled = True
        
        if self.selected_gpios.get(key) == pin:
            p_btn.color = (0.2, 1, 0.4, 1)
            with p_btn.canvas.after:
                Color(0.2, 1, 0.4, 0.3)
                from kivy.graphics import Line
                Line(rounded_rectangle=[p_btn.x, p_btn.y, p_btn.width, p_btn.height, dp_scaled(6)], width=dp_scaled(1.5))

        # Klick setzt den State dirty und wählt den Pin
        p_btn.bind(on_release=lambda x: (setattr(self, 'is_dirty', True), self.select_pin(pin, key, target_button, popup)))
        return p_btn

    def open_pin_picker(self, key, target_button, pin_list):
        content = BoxLayout(orientation='vertical', padding=dp_scaled(12), spacing=dp_scaled(10))
        
        with content.canvas.before:
            # Hintergrundfarbe auf sattes Schwarz mit leichter Transparenz gesetzt
            Color(0.05, 0.05, 0.05, 0.95)
            content.bg_rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp_scaled(14)])

        content.bind(
            pos=lambda s, v: setattr(content.bg_rect, 'pos', v),
            size=lambda s, v: setattr(content.bg_rect, 'size', v)
        )

        legend_text = (
            "[font=FA][color=00F0FF]\uf0a1[/color][/font] IN   "
            "[font=FA][color=00FF66]\uf0a0[/color][/font] OUT   "
            "[font=FA][color=FFAA00]\uf0e7[/color][/font] PWM   "
            "[font=FA][color=D400FF]\uf2db[/color][/font] I2C   "
            "[font=FA][color=00E5FF]\uf1dd[/color][/font] ADC"
        )
        content.add_widget(Label(text=legend_text, markup=True, size_hint_y=None, height=dp_scaled(30), font_size=sp_scaled(21)))

        picker_scroll = ScrollView(do_scroll_x=False, bar_width=dp(6))
        
        # HIER: cols=2 für die zweispaltige Matrix-Ansicht
        picker_grid = GridLayout(cols=2, size_hint_y=None, spacing=dp_scaled(8), padding=dp_scaled(5))
        picker_grid.bind(minimum_height=picker_grid.setter('height'))
        
        popup = Popup(
            title=f"PIN ROUTING FÜR: {key.upper()}", 
            content=content, 
            size_hint=(0.95, 0.85),
            title_align="center",
            title_size=sp_scaled(18),
            # HIER: Macht die Standard-Kivy-Box unsichtbar!
            background='',
            background_color=(0, 0, 0, 0)
        )
        
        required_role = REQUIRED_ROLES.get(key)
        
        for pin in pin_list:
            allowed_roles, info_text = get_pin_info(pin)
            
            if not allowed_roles and pin != -1:
                compatible = False
                is_forbidden = True
            else:
                compatible = (required_role in allowed_roles) if allowed_roles else True
                is_forbidden = False

            icon, color_tag, _ = self.get_role_style(required_role if compatible else "Deaktiviert", is_forbidden)

            if pin == -1:
                display_text = f"[font=FA]\uf057[/font]  [b]PIN DEAKTIVIEREN[/b]"
            elif is_forbidden:
                display_text = f"[font=FA][color=FF3333]\uf05e[/color][/font]  [b]GPIO {pin:02d}[/b]\n[size=14][color=FF0000]LOCK: {info_text}[/color][/size]"
            elif not compatible:
                display_text = f"[font=FA][color=666666]\uf054[/color][/font]  GPIO {pin:02d}\n[size=14][color=888888](Inkompatibel)[/color][/size]"
            else:
                available_badges = " ".join([
                    f"[font=FA]{self.get_role_style(r)[1]}{self.get_role_style(r)[0]}[/color][/font]" 
                    for r in allowed_roles if r != "Deaktiviert"
                ])
                display_text = f"[font=FA]{color_tag}{icon}[/color][/font]  [b]GPIO {pin:02d}[/b] [color=00FF66]OK[/color]\n[size=13]Caps: {available_badges}[/size]"

            # Aufruf der isolierten Scope-Methode
            p_btn = self._build_picker_button(display_text, pin, key, target_button, popup, compatible)
            if is_forbidden:
                p_btn.color = (1, 0.15, 0.15, 1)    
            # Da die Buttons jetzt schmaler sind (2 Spalten), erhöhen wir leicht die 
            # Höhe und erlauben mehrzeiligen Text für Fehlermeldungen / Caps
            p_btn.height = dp_scaled(54)
            
            picker_grid.add_widget(p_btn)
            
        picker_scroll.add_widget(picker_grid)
        content.add_widget(picker_scroll)
        popup.open()

    def select_pin(self, pin, key, target_button, popup):
        self.selected_gpios[key] = pin
        required_role = REQUIRED_ROLES.get(key)
        icon, color_tag, _ = self.get_role_style(required_role if pin != -1 else "Deaktiviert")
        
        if pin == -1:
            target_button.text = f"[font=FA][color=888888]\uf057[/color][/font]  DEAKTIVIERT  [font=FA]\uf078[/font]"
        else:
            target_button.text = f"[font=FA]{color_tag}{icon}[/color][/font]  GPIO {pin}  [font=FA]\uf078[/font]"
            
        popup.dismiss()

    def save_and_reboot(self, *_):
        try:
            valid, result = validate_and_build_pins({"gpios": self.current_gpios}, self.selected_gpios)
        except Exception:
            valid, result = True, self.selected_gpios

        if not valid:
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(text=str(result), halign='center'))
            btn = GlassButton(text="OK", size_hint_y=None, height=dp_scaled(40))
            popup = Popup(title="Ungültige GPIO Auswahl", content=content, size_hint=(0.8, 0.4))
            btn.bind(on_release=popup.dismiss)
            content.add_widget(btn)
            popup.open()
            return

        merged = result if isinstance(result, dict) else self.selected_gpios

        payload = {"command": "none"}

        # NORMALE GPIOS
        for key, val in merged.items():
            payload[key] = int(val)

        # PULL-FELDER EXPLIZIT ÜBERNEHMEN
        PULL_KEYS = {
            "p_e_tac_pull",
            "p_bat_pull",
        }
        PULL_KEYS.update(fan_gpio_keys(fan_id)[2] for fan_id in range(1, MAX_CIRCULATION_FANS + 1))

        for key in PULL_KEYS:

            val = self.selected_gpios.get(key, 0)

            try:
                val = int(val)
            except Exception:
                val = 0

            # Sicherheitsclamp
            if val not in (0, 1, 2):
                val = 0

            payload[key] = val

        # Erst nach dem Speichern lassen wir wieder Aktualisierungen durch
        self.is_dirty = False

        self.screen._send_grow_payload(
            payload,
            context="gpio_settings",
            reset_after_ack=True,
        )



    def show_pinout(self, *_):
        """Öffnet das Pinout-Bild über das neue ausgelagerte Modul."""
        popup = ZoomableImagePopup(title="ESP32-S3 PINOUT", image_source=PINOUT_PIC)
        popup.open()

    def update_from_live_gpios(self, live_gpios: dict):
        """Aktualisiert die Daten vom ESP nur, wenn die UI nicht im Editier/Reset-Modus ist."""
        if self.is_dirty:
            return

        live_gpios = live_gpios or {}
        has_changed = False
        for _, key in self.gpio_definitions:
            if self.current_gpios.get(key, -1) != live_gpios.get(key, -1):
                has_changed = True
                break
        
        if has_changed or not self.selected_gpios:
            self.current_gpios = live_gpios
            for _, key in self.gpio_definitions:
                self.selected_gpios[key] = self.current_gpios.get(key, -1)
            self.build_rows()
