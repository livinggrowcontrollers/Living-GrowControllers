from datetime import datetime, timedelta

from kivy.graphics import Color, Mesh, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy_garden.graph import Graph, LinePlot

import config
from dashboard_gui.ui.common.buttons.control_buttons import ControlButtons
from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class FullScreenMainPanel(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.presentation = MetricRegistry.presentation("fullscreen")

        with self.canvas.before:
            self.bg_color = Color(0.08, 0.08, 0.1, 0.40)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size, source="")
        self.bind(pos=self._update_bg, size=self._update_bg)

        win_seconds = config.get_tile_graph_window()
        self.graph = Graph(
            xmin=0,
            xmax=win_seconds,
            ymin=0,
            ymax=1,
            draw_border=False,
            background_color=(0, 0, 0, 0),
            y_grid_label=True,
            x_grid_label=False,
            padding=dp_scaled(10),
            label_options={
                "color": self.presentation.get(
                    "graph_label_color",
                    [1, 1, 1, 0.4],
                ),
                "bold": True,
            },
            size_hint=(1, 0.96),
            pos_hint={"x": 0, "y": 0},
        )
        self.plot = LinePlot(line_width=dp_scaled(2.5))
        self.plot_glow = LinePlot(line_width=dp_scaled(3))
        self.graph.add_plot(self.plot_glow)
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)

        with self.graph.canvas.after:
            self.mesh_color = Color(1, 1, 1, 0.25)
            self.mesh = Mesh(mode="triangle_strip")

        self.x_axis_labels = GridLayout(
            cols=5,
            size_hint=(1, None),
            height=dp_scaled(40),
            pos_hint={"x": 0, "y": 0.08},
        )
        self.labels_list = []
        for _ in range(5):
            label = Label(
                text="",
                font_size=sp_scaled(24),
                color=self.presentation.get(
                    "axis_color",
                    [1, 1, 1, 0.5],
                ),
                bold=True,
                outline_width=1,
                outline_color=(0, 0, 0, 1),
            )
            self.labels_list.append(label)
            self.x_axis_labels.add_widget(label)
        self.add_widget(self.x_axis_labels)

        self.hud = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            height=dp_scaled(280),
            pos_hint={"center_x": 0.5, "top": 0.85},
            spacing=dp_scaled(-10),
        )
        self.lbl_title = Label(
            text="--",
            font_size=sp_scaled(45),
            bold=True,
            color=self.presentation.get(
                "title_color",
                [1, 1, 1, 0.9],
            ),
            outline_width=1,
            outline_color=(0, 0, 0, 1),
        )
        self.lbl_value = Label(
            text="--",
            font_size=sp_scaled(70),
            bold=True,
            markup=True,
            outline_width=3,
            outline_color=(0, 0, 0, 1),
        )
        self.lbl_sub = Label(
            text="avg: -- | min: -- | max: --",
            font_size=sp_scaled(24),
            bold=True,
            color=self.presentation.get(
                "stats_color",
                [0.8, 0.8, 0.8, 0.8],
            ),
            outline_width=1,
            outline_color=(0, 0, 0, 1),
        )
        self.hud.add_widget(self.lbl_title)
        self.hud.add_widget(self.lbl_value)
        self.hud.add_widget(self.lbl_sub)
        self.add_widget(self.hud)

        self.header = HeaderBar()
        self.header.pos_hint = {"top": 1}
        self.add_widget(self.header)

        button_size = dp_scaled(45)
        self.btn_left = Button(
            text="[font=FA]\uf060[/font]",
            markup=True,
            font_size=sp_scaled(20),
            size_hint=(None, None),
            size=(button_size, button_size),
            pos_hint={"x": 0.02, "center_y": 0.5},
            background_color=(0, 0, 0, 0.4),
        )
        self.btn_right = Button(
            text="[font=FA]\uf061[/font]",
            markup=True,
            font_size=sp_scaled(20),
            size_hint=(None, None),
            size=(button_size, button_size),
            pos_hint={"right": 0.98, "center_y": 0.5},
            background_color=(0, 0, 0, 0.4),
        )
        self.add_widget(self.btn_left)
        self.add_widget(self.btn_right)

        self.on_range_selected = None
        self.on_custom_range_selected = None
        self.range_buttons = {}
        self.range_bar = BoxLayout(
            orientation="horizontal",
            spacing=dp_scaled(3),
            padding=(dp_scaled(5), 0),
            size_hint=(0.98, None),
            height=dp_scaled(38),
            pos_hint={"center_x": 0.5, "top": 0.93},
        )

        range_items = (
            ("LIVE", None),

            ("1H", 1),
            ("2H", 2),
            ("3H", 3),
            ("6H", 6),
            ("12H", 12),
            ("24H", 24),
            ("48H", 48),
            ("7D", 7 * 24),
            ("30D", 30 * 24),
            ("365D", 365 * 24),
            ("ZEIT", "custom"),
        )

        for text, hours in range_items:
            button = Button(
                text=text,
                bold=True,
                font_size=sp_scaled(20),
                background_normal="",
                background_down="",
                background_color=(0.08, 0.08, 0.10, 0.72),
                color=(0.75, 0.75, 0.78, 1),
            )
            button.bind(
                on_release=lambda _button, selected_hours=hours: (
                    self._emit_range_selected(selected_hours)
                )
            )
            self.range_buttons[hours] = button
            self.range_bar.add_widget(button)

        self.add_widget(self.range_bar)
        self.set_active_range(None)

        self.controls = ControlButtons()
        self.controls.size_hint = (1, None)
        self.controls.height = dp_scaled(40)
        self.controls.pos_hint = {"y": 0}
        self.add_widget(self.controls)

    def configure_metric_plots(self, main_color, glow_color):
        # Wie bei den Live-Tiles bleiben die Plot-Instanzen dauerhaft in der
        # Graph-FBO. Entfernen/Neu-Anlegen leert den gemeinsamen Zeichenpuffer
        # und verursacht sichtbares Flackern oder kurzzeitig fehlende Linien.
        self.plot.color = main_color
        self.plot_glow.color = glow_color
        self.plot._gcolor.rgba = main_color
        self.plot_glow._gcolor.rgba = glow_color
        return self.plot, self.plot_glow

    def apply_metric_theme(self, presentation=None):
        self.presentation = presentation or MetricRegistry.presentation(
            "fullscreen"
        )
        self.lbl_title.color = self.presentation.get(
            "title_color",
            [1, 1, 1, 0.9],
        )
        self.lbl_sub.color = self.presentation.get(
            "stats_color",
            [0.8, 0.8, 0.8, 0.8],
        )
        self.graph.label_options["color"] = self.presentation.get(
            "graph_label_color",
            [1, 1, 1, 0.4],
        )
        for label in self.labels_list:
            label.color = self.presentation.get(
                "axis_color",
                [1, 1, 1, 0.5],
            )

    def _emit_range_selected(self, hours):
        if hours == "custom":
            self._open_custom_range_popup()
            return

        if callable(self.on_range_selected):
            self.on_range_selected(hours)

    def _open_custom_range_popup(self):
        now = datetime.now().astimezone()
        start_default = now - timedelta(days=1)
        date_format = "%Y-%m-%d %H:%M"

        content = BoxLayout(
            orientation="vertical",
            spacing=dp_scaled(8),
            padding=dp_scaled(12),
        )
        content.add_widget(
            Label(
                text="Lokale Zeit (JJJJ-MM-TT HH:MM)",
                size_hint_y=None,
                height=dp_scaled(28),
            )
        )
        start_input = TextInput(
            text=start_default.strftime(date_format),
            multiline=False,
            hint_text="Von",
            size_hint_y=None,
            height=dp_scaled(42),
        )
        end_input = TextInput(
            text=now.strftime(date_format),
            multiline=False,
            hint_text="Bis",
            size_hint_y=None,
            height=dp_scaled(42),
        )
        error_label = Label(
            text="",
            color=(1, 0.35, 0.35, 1),
            size_hint_y=None,
            height=dp_scaled(30),
        )
        content.add_widget(start_input)
        content.add_widget(end_input)
        content.add_widget(error_label)

        actions = BoxLayout(
            orientation="horizontal",
            spacing=dp_scaled(8),
            size_hint_y=None,
            height=dp_scaled(42),
        )
        cancel_button = Button(text="Abbrechen")
        load_button = Button(text="Laden")
        actions.add_widget(cancel_button)
        actions.add_widget(load_button)
        content.add_widget(actions)

        popup = Popup(
            title="Benutzerdefiniertes Zeitfenster",
            content=content,
            size_hint=(0.86, 0.62),
            auto_dismiss=False,
        )

        def submit(*_):
            try:
                start_datetime = datetime.strptime(
                    start_input.text.strip(),
                    date_format,
                ).astimezone()
                end_datetime = datetime.strptime(
                    end_input.text.strip(),
                    date_format,
                ).astimezone()
            except ValueError:
                error_label.text = "Bitte beide Zeiten im angegebenen Format eingeben."
                return

            start_timestamp = start_datetime.timestamp()
            end_timestamp = end_datetime.timestamp()
            if start_timestamp >= end_timestamp:
                error_label.text = "'Von' muss vor 'Bis' liegen."
                return

            popup.dismiss()
            if callable(self.on_custom_range_selected):
                self.on_custom_range_selected(
                    start_timestamp,
                    end_timestamp,
                )

        cancel_button.bind(on_release=lambda *_: popup.dismiss())
        load_button.bind(on_release=submit)
        popup.open()

    def set_active_range(self, active_hours):
        for hours, button in self.range_buttons.items():
            if hours == active_hours:
                button.background_color = (0.12, 0.55, 0.30, 0.90)
                button.color = (1, 1, 1, 1)
            else:
                button.background_color = (0.08, 0.08, 0.10, 0.72)
                button.color = (0.75, 0.75, 0.78, 1)

    def _update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
