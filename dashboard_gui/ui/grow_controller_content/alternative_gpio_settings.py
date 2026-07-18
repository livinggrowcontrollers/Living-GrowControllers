import os

from kivy.uix.popup import Popup
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Rectangle

from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.grow_controller_content.pin_matrix import REQUIRED_ROLES, get_pin_info
from dashboard_gui.circulation_fan_registry import MAX_CIRCULATION_FANS, fan_gpio_keys

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
PINOUT_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "esp32_pinout.png")
ROLE_NAMES = {
    "p_reset": "Reset-Taster",
    "p_c_fan": "Umluft-Lüfter",
    "p_c_tac": "Umluft-Tacho",

    # entfernen
    # "p_c_tac_pull"

    "p_e_fan": "Abluft-Lüfter",
    "p_e_tac": "Abluft-Tacho",

    # entfernen
    # "p_e_tac_pull"

    "p_light": "Beleuchtung",
    "p_i2c_sda": "I²C SDA",
    "p_i2c_scl": "I²C SCL",
    "p_rtc_sda": "RTC SDA",
    "p_rtc_scl": "RTC SCL",
    "p_bat": "Batterie",

    # entfernen
    # "p_bat_pull"
}
for _fan_id in range(1, MAX_CIRCULATION_FANS + 1):
    _pwm, _tacho, _pull = fan_gpio_keys(_fan_id)
    ROLE_NAMES[_pwm] = f"Umluft-Lüfter {_fan_id}"
    ROLE_NAMES[_tacho] = f"Umluft-Tacho {_fan_id}"
# Deine originalen Pixel-Koordinaten bezogen auf das Bild
GPIO_POSITIONS = {

   
    # linke Seite ESP
    4: (-47, 765),
    5: (-47, 725), 
    6: (-47, 685),
    7: (-47, 645),
    15: (-47, 605), 
    16: (-47, 565), 

    
    17: (-47, 525),
    18: (-47, 488),
    8: (-47, 448), 
    
    3: (-47, 408), 
    46: (-47, 368),
    9: (-47, 328),
    10: (-47, 288), 
    11: (-47, 248), 
    12: (-47, 208),
    13: (-47, 168),
    14: (-47, 128),
   
    # rechte Seite ESP
    
    1: (907, 765),
    2: (907, 725),
    42: (907, 685),
    41: (907, 645),
    40: (907, 605),
    39: (907, 565),
    38: (907, 525),
    37: (907, 488),
    36: (907, 448),
    35: (907, 408),
    0: (907, 368),
    45: (907, 328),
    48: (907, 288),
    47: (907, 248),
    21: (907, 208),  # korrekt!!
    20: (907, 168),  # korrekt!!
    19: (907, 128)




}

IMAGE_SIZE = (900, 961)
POPUP_SIZE = (1350, 700)

# Berechnungen für das rein vertikale Layout:
# Die Breite der Arbeitsfläche entspricht exakt der Breite des Sichtbereichs der ScrollView.
SCROLL_VIEW_WIDTH = POPUP_SIZE[0] - 40
SCROLL_VIEW_HEIGHT = POPUP_SIZE[1] - 100

# Arbeitsfläche: Breite ist starr an den Viewport gekoppelt, Höhe ist massiv vergrößert (z.B. 2000px)
WORKSPACE_SIZE = (SCROLL_VIEW_WIDTH, 1000)

# Horizontal zentrieren wir das Bild auf der fixen Breite, vertikal setzen wir es mittig in das Riesen-Widget
OFFSET_X = (WORKSPACE_SIZE[0] - IMAGE_SIZE[0]) / 2
OFFSET_Y = (WORKSPACE_SIZE[1] - IMAGE_SIZE[1]) / 2


class AlternativeGpioSettings(Popup):
    def __init__(self, screen=None, **kwargs):
        super().__init__(**kwargs)
        self.screen = screen
        self.gpio_panel = getattr(screen, "gpio_panel", None)

        self.title = "VISUAL GPIO EDITOR"
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (None, None)
        self.size = POPUP_SIZE

        # 1. Root-Container
        root = AnchorLayout(anchor_x='center', anchor_y='center')
        self.root_layout = root
        
        with root.canvas.before:
            Color(.05, .05, .05, .97)
            root.bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[12])
        root.bind(pos=lambda s, v: setattr(root.bg, "pos", v), size=lambda s, v: setattr(root.bg, "size", v))

        # 2. ScrollView: do_scroll_x ist jetzt auf FALSE gesetzt
        self.scroll_view = ScrollView(
            size_hint=(None, None), 
            size=(SCROLL_VIEW_WIDTH, SCROLL_VIEW_HEIGHT),
            do_scroll_x=False,  # Seitliches Scrollen komplett deaktiviert
            do_scroll_y=True
        )
        root.add_widget(self.scroll_view)

        # 3. Arbeitsfläche
        self.workspace = Widget(size_hint=(None, None), size=WORKSPACE_SIZE)
        self.scroll_view.add_widget(self.workspace)

        with self.workspace.canvas.before:
            Color(1, 1, 1, 1)
            self.workspace.background = Rectangle(
                source=PINOUT_PIC, 
                pos=(OFFSET_X, OFFSET_Y), 
                size=IMAGE_SIZE
            )

        self.pin_buttons = {}
        self.pin_labels = {}
        self.create_gpio_buttons()

        # Start-Scrollposition vertikal mittig setzen (0.5), horizontal ist egal da do_scroll_x=False
        self.scroll_view.scroll_y = 0.5

        # Schließen-Button
        close = GlassButton(text="SCHLIESSEN", size_hint=(None, None), size=(180, 50))
        close_container = AnchorLayout(anchor_x='left', anchor_y='bottom', padding=[20, 20, 20, 20])
        close_container.add_widget(close)
        root.add_widget(close_container)

        self.content = root
        close.bind(on_release=self.dismiss)

    # ... [Restliche Methoden wie _get_selected_gpios, _apply_button_state, open_gpio_menu, select_function bleiben exakt gleich] ...

    def _get_selected_gpios(self):
        panel = getattr(self, "gpio_panel", None)
        if panel is None:
            return None

        raw = getattr(panel, "selected_gpios", None)
        if raw is None:
            return None

        # 🔥 FILTER: ALLE *_pull RAUS
        clean = {
            k: v for k, v in raw.items()
            if not k.endswith("_pull")
        }

        return clean

    def _refresh_pin_button_states(self):
        for gpio, btn in self.pin_buttons.items():
            self._apply_button_state(btn, gpio)



    def create_gpio_buttons(self):
        for gpio, pos in GPIO_POSITIONS.items():

            shifted_pos = (pos[0] + OFFSET_X, pos[1] + OFFSET_Y)

            btn = Button(
                text=str(gpio),
                size_hint=(None, None),
                size=(40, 40),
                pos=shifted_pos,
                font_size=21,
                background_normal="",
                background_color=(0, .8, 0, .75),
            )

            btn.bind(on_release=lambda x, g=gpio: self.open_gpio_menu(g))

            self.pin_buttons[gpio] = btn
            self.workspace.add_widget(btn)

            # ---------- Beschriftung ----------
            label = Label(
                text="",
                size_hint=(None, None),
                size=(200, 30),
                font_size=21,
                color=(1, 1, 1, 1),
                valign="middle",
            )

            if pos[0] < 100:
                # linke ESP-Seite -> Text links vom Button
                label.text_size = (200, 30)
                label.halign = "right"
                label.pos = (
                    shifted_pos[0] - 205,
                    shifted_pos[1]
                )
            else:
                # rechte ESP-Seite -> Text rechts vom Button
                label.text_size = (200, 30)
                label.halign = "left"
                label.pos = (
                    shifted_pos[0] + 45,
                    shifted_pos[1]
                )

            self.pin_labels[gpio] = label
            self.workspace.add_widget(label)

            self._apply_button_state(btn, gpio)


    def _apply_button_state(self, btn, gpio):
        label = self.pin_labels[gpio]

        selected_gpios = self._get_selected_gpios()

        if not selected_gpios:
            btn.text = str(gpio)
            btn.background_color = (.25, .25, .25, 1)
            label.text = ""
            return

        assigned_role = None

        for role, assigned_pin in selected_gpios.items():
            if int(assigned_pin) == int(gpio):
                assigned_role = role
                break

        if assigned_role is None:
            btn.text = str(gpio)
            btn.background_color = (.25, .25, .25, 1)
            label.text = ""
            return

        btn.text = str(gpio)

        label.text = ROLE_NAMES.get(assigned_role, assigned_role)

        role = REQUIRED_ROLES.get(assigned_role)

        color_map = {
            "INPUT": (0.1, 0.8, 1, 1),
            "PWM": (1, 0.7, 0.1, 1),
            "I2C": (0.8, 0.2, 1, 1),
            "ANALOG": (1, 0.2, 0.2, 1),
        }

        btn.background_color = color_map.get(role, (.9, .9, .9, 1))
    def open_gpio_menu(self, gpio):
        dropdown = DropDown(auto_width=False, width=260)

        info_roles, info_text = get_pin_info(gpio)
        title = Label(
            text=f"[b]GPIO {gpio}[/b]\n[size=14]{info_text}[/size]",
            markup=True,
            size_hint_y=None,
            height=60,
        )
        dropdown.add_widget(title)
        with dropdown.canvas.before:
            Color(0.03, 0.03, 0.03, 0.98)
            dropdown.bg = RoundedRectangle(
                pos=dropdown.pos,
                size=dropdown.size,
                radius=[10]
            )

        dropdown.bind(
            pos=lambda s, v: setattr(dropdown.bg, "pos", v),
            size=lambda s, v: setattr(dropdown.bg, "size", v),
        )
        disable_btn = GlassButton(text="DEAKTIVIERT", size_hint_y=None, height=42)
        disable_btn.bind(on_release=lambda x: (self.select_function(gpio, None), dropdown.dismiss()))
        dropdown.add_widget(disable_btn)

        for key, required_role in REQUIRED_ROLES.items():
            if required_role not in info_roles:
                continue
            display = ROLE_NAMES.get(key, key)

            btn = GlassButton(
                text=f"{display}   [{required_role}]",
                size_hint_y=None,
                height=42
            )            
            
            btn.bind(on_release=lambda x, k=key: (self.select_function(gpio, k), dropdown.dismiss()))
            dropdown.add_widget(btn)

        dropdown.open(self.pin_buttons[gpio])

    def select_function(self, gpio, function):
        panel = getattr(self, "gpio_panel", None)
        if panel is None:
            return

        selected_gpios = getattr(panel, "selected_gpios", None)
        if selected_gpios is None:
            return

        setattr(panel, "is_dirty", True)

        if function is None:
            for role, assigned_pin in list(selected_gpios.items()):
                if int(assigned_pin) == int(gpio):
                    selected_gpios[role] = -1
        else:
            for role, assigned_pin in list(selected_gpios.items()):
                if int(assigned_pin) == int(gpio) and role != function:
                    selected_gpios[role] = -1
            selected_gpios[function] = int(gpio)

        if hasattr(panel, "build_rows"):
            panel.build_rows()

        self._refresh_pin_button_states()
