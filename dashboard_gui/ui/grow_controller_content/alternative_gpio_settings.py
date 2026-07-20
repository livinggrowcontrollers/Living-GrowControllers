

import os

from kivy.uix.popup import Popup
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatter import Scatter
from kivy.uix.stencilview import StencilView
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.graphics.transformation import Matrix
from kivy.uix.scrollview import ScrollView

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
    "p_humidifier": "Luftbefeuchter",

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

# Sichtbereich für die zoombare GPIO-Arbeitsfläche.
SCROLL_VIEW_WIDTH = POPUP_SIZE[0] - 40
SCROLL_VIEW_HEIGHT = POPUP_SIZE[1] - 100

# Bild, GPIO-Buttons und Beschriftungen teilen sich diese feste Koordinatenbasis.
# Sie wird als Ganzes von Scatter skaliert, damit die Buttons immer exakt auf dem Bild bleiben.
WORKSPACE_SIZE = (SCROLL_VIEW_WIDTH, 1000)

# Horizontal zentrieren wir das Bild auf der fixen Breite, vertikal setzen wir es mittig in das Riesen-Widget
OFFSET_X = (WORKSPACE_SIZE[0] - IMAGE_SIZE[0]) / 2
OFFSET_Y = (WORKSPACE_SIZE[1] - IMAGE_SIZE[1]) / 2


class ZoomableGpioCanvas(Scatter):
    """Scatter with the ImageViewer's explicit mouse-wheel zoom behaviour."""

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and touch.is_mouse_scrolling:
            if touch.button == "scrolldown":
                self.zoom(1.1, touch.pos)
            elif touch.button == "scrollup":
                self.zoom(0.9, touch.pos)
            return True
        return super().on_touch_down(touch)

    def zoom(self, factor, anchor_pos):
        """Scale around the cursor/gesture anchor without moving its GPIO target."""
        old_scale = self.scale
        new_scale = max(self.scale_min, min(self.scale_max, old_scale * factor))
        if new_scale == old_scale:
            return
        scale_factor = new_scale / old_scale
        self.apply_transform(
            Matrix().scale(scale_factor, scale_factor, scale_factor),
            anchor=anchor_pos,
        )


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

        # 2. Beschnittener Sichtbereich mit einer frei verschieb- und zoombaren Ebene.
        # Scatter transformiert Bild, Pin-Buttons und Labels gemeinsam.
        self.viewport = StencilView(
            size_hint=(None, None),
            size=(SCROLL_VIEW_WIDTH, SCROLL_VIEW_HEIGHT),
        )
        root.add_widget(self.viewport)

        self.gpio_canvas = ZoomableGpioCanvas(
            size_hint=(None, None),
            size=WORKSPACE_SIZE,
            do_rotation=False,
            do_translation=True,
            do_scale=True,
            scale_min=0.45,
            scale_max=3.5,
        )
        self.viewport.add_widget(self.gpio_canvas)

        # 3. Feste Arbeitsfläche innerhalb der transformierbaren Ebene.
        self.workspace = Widget(size_hint=(None, None), size=WORKSPACE_SIZE)
        self.gpio_canvas.add_widget(self.workspace)

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

        # Nach dem ersten Layout die komplette Matrix passend in den Sichtbereich legen.
        Clock.schedule_once(self._fit_gpio_canvas, 0)

        # Schließen-Button
        close = GlassButton(text="SCHLIESSEN", size_hint=(None, None), size=(180, 50))
        close_container = AnchorLayout(anchor_x='left', anchor_y='bottom', padding=[20, 20, 20, 20])
        close_container.add_widget(close)
        root.add_widget(close_container)

        # Die Buttons sind zusätzlich zum Pinch/Mausrad da, damit Zoom auf
        # jedem Gerät zuverlässig erreichbar bleibt.
        zoom_controls = AnchorLayout(anchor_x="right", anchor_y="bottom", padding=[20, 20, 20, 20])
        zoom_row = FloatLayout(size_hint=(None, None), size=(156, 50))
        zoom_out = GlassButton(text="−", size_hint=(None, None), size=(48, 50), pos=(0, 0))
        zoom_reset = GlassButton(text="FIT", size_hint=(None, None), size=(54, 50), pos=(51, 0))
        zoom_in = GlassButton(text="+", size_hint=(None, None), size=(48, 50), pos=(108, 0))
        zoom_out.bind(on_release=lambda *_: self._zoom_gpio(0.85))
        zoom_reset.bind(on_release=self._fit_gpio_canvas)
        zoom_in.bind(on_release=lambda *_: self._zoom_gpio(1.18))
        for control in (zoom_out, zoom_reset, zoom_in):
            zoom_row.add_widget(control)
        zoom_controls.add_widget(zoom_row)
        root.add_widget(zoom_controls)

        self.content = root
        close.bind(on_release=self.dismiss)

    def _fit_gpio_canvas(self, *_):
        """Show the complete GPIO matrix initially; wheel/pinch can zoom from here."""
        viewport_w, viewport_h = self.viewport.size
        workspace_w, workspace_h = WORKSPACE_SIZE
        if not viewport_w or not viewport_h:
            return

        self.gpio_canvas.scale = min(viewport_w / workspace_w, viewport_h / workspace_h)
        scaled_w = workspace_w * self.gpio_canvas.scale
        scaled_h = workspace_h * self.gpio_canvas.scale
        self.gpio_canvas.pos = (
            self.viewport.x + (viewport_w - scaled_w) / 2,
            self.viewport.y + (viewport_h - scaled_h) / 2,
        )

    def _zoom_gpio(self, factor):
        self.gpio_canvas.zoom(factor, self.viewport.center)

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
        info_roles, info_text = get_pin_info(gpio)
        menu = Popup(
            title=f"GPIO {gpio} – FUNKTION WÄHLEN",
            size_hint=(None, None),
            size=(440, 580),
            background="",
            background_color=(0.04, 0.04, 0.06, 0.98),
        )
        content = BoxLayout(orientation="vertical", spacing=10, padding=[14, 12])
        info_label = Label(
            text=info_text,
            markup=True,
            size_hint_y=None,
            height=58,
            halign="center",
            valign="middle",
            color=(0.75, 0.85, 0.95, 1),
        )
        info_label.bind(size=lambda widget, *_: setattr(widget, "text_size", widget.size))
        content.add_widget(info_label)

        scroll = ScrollView(do_scroll_x=False, bar_width=8)
        choices = GridLayout(cols=1, size_hint_y=None, spacing=7, padding=[2, 2])
        choices.bind(minimum_height=choices.setter("height"))
        scroll.add_widget(choices)
        content.add_widget(scroll)

        def choose(function):
            self.select_function(gpio, function)
            menu.dismiss()

        disable_btn = GlassButton(text="DEAKTIVIERT", size_hint_y=None, height=46)
        disable_btn.bind(on_release=lambda *_: choose(None))
        choices.add_widget(disable_btn)

        for key, required_role in REQUIRED_ROLES.items():
            if required_role not in info_roles:
                continue
            display = ROLE_NAMES.get(key, key)

            btn = GlassButton(
                text=f"{display}   [{required_role}]",
                size_hint_y=None,
                height=46,
                halign="left",
                valign="middle",
                padding=[14, 0],
            )
            btn.bind(size=lambda widget, *_: setattr(widget, "text_size", widget.size))
            btn.bind(on_release=lambda _, k=key: choose(k))
            choices.add_widget(btn)

        menu.content = content
        menu.open()

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
