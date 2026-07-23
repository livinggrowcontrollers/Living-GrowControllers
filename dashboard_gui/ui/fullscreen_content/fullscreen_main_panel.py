# dashboard_gui/ui/fullscreen_content/fullscreen_main_panel.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy_garden.graph import Graph, LinePlot
from kivy.graphics import Rectangle, Color, Mesh
from kivy.uix.label import Label
from kivy.uix.button import Button
import config 
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.common.buttons.control_buttons import ControlButtons
from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class FullScreenMainPanel(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self.presentation = MetricRegistry.presentation("fullscreen")

        # -------------------------------------------------
        # 1. HINTERGRUND INITIALISIERUNG
        # -------------------------------------------------
        with self.canvas.before:
            self.bg_color = Color(0.08, 0.08, 0.1, 0.40)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size, source="")
        self.bind(pos=self._update_bg, size=self._update_bg)

        # -------------------------------------------------
        # 2. GRAPH & PLOTS
        # -------------------------------------------------
        win_seconds = config.get_tile_graph_window()
        self.graph = Graph(
            xmin=0, xmax=win_seconds,
            ymin=0, ymax=1,
            draw_border=False,
            background_color=(0, 0, 0, 0),
            y_grid_label=True,
            x_grid_label=False,
            padding=dp_scaled(10),
            label_options={'color': self.presentation.get("graph_label_color", [1, 1, 1, 0.4]), 'bold': True},
            size_hint=(1, 0.96),
            pos_hint={'x': 0, 'y': 0}
        )
        self.plot = LinePlot(line_width=dp_scaled(2.5))  
        self.plot_glow = LinePlot(line_width=dp_scaled(3))
        self.graph.add_plot(self.plot_glow)
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)

        # -------------------------------------------------
        # 3. TRANSPARENTE FILL-FLÄCHE (Mesh)
        # -------------------------------------------------
        with self.graph.canvas.after:
            self.mesh_color = Color(1, 1, 1, 0.25)  
            self.mesh = Mesh(mode='triangle_strip')

        # X-ACHSE LABELS
        self.x_axis_labels = GridLayout(
            cols=5, size_hint=(1, None), height=dp_scaled(40),
            pos_hint={'x': 0, 'y': 0.08}
        )
        self.labels_list = []
        for _ in range(5):
            lbl = Label(text="", font_size=sp_scaled(24), color=self.presentation.get("axis_color", [1, 1, 1, 0.5]), bold=True, outline_width=1, outline_color=(0, 0, 0, 1))
            self.labels_list.append(lbl)
            self.x_axis_labels.add_widget(lbl)
        self.add_widget(self.x_axis_labels)

        # VALUE HUD
        self.hud = BoxLayout(
            orientation="vertical", size_hint=(1, None), height=dp_scaled(280),
            pos_hint={'center_x': 0.5, 'top': 0.85}, spacing=dp_scaled(-10)
        )
        
        self.lbl_title = Label(text="--", font_size=sp_scaled(45), bold=True, color=self.presentation.get("title_color", [1, 1, 1, 0.9]), outline_width=1, outline_color=(0, 0, 0, 1))
        self.lbl_value = Label(
            text="--", font_size=sp_scaled(70), bold=True, markup=True,
            outline_width=3, outline_color=(0, 0, 0, 1)
        )
        self.lbl_sub = Label(
            text="avg: -- | min: -- | max: --", font_size=sp_scaled(24), bold=True,
            color=self.presentation.get("stats_color", [0.8, 0.8, 0.8, 0.8]), outline_width=1, outline_color=(0, 0, 0, 1)
        )
        self.hud.add_widget(self.lbl_title)
        self.hud.add_widget(self.lbl_value)
        self.hud.add_widget(self.lbl_sub)
        self.add_widget(self.hud)

        # HEADER
        self.header = HeaderBar()
        self.header.pos_hint = {'top': 1}
        self.add_widget(self.header)

        # NAV BUTTONS
        btn_size = dp_scaled(45)
        self.btn_left = Button(
            text="[font=FA]\uf060[/font]", markup=True, font_size=sp_scaled(20),
            size_hint=(None, None), size=(btn_size, btn_size),
            pos_hint={"x": 0.02, "center_y": 0.5}, background_color=(0, 0, 0, 0.4)
        )
        self.btn_right = Button(
            text="[font=FA]\uf061[/font]", markup=True, font_size=sp_scaled(20),
            size_hint=(None, None), size=(btn_size, btn_size),
            pos_hint={"right": 0.98, "center_y": 0.5}, background_color=(0, 0, 0, 0.4)
        )
        self.add_widget(self.btn_left)
        self.add_widget(self.btn_right)




        # -------------------------------------------------
        # HISTORY RANGE BUTTONS
        # -------------------------------------------------
        self.on_range_selected = None
        self.range_buttons = {}

        self.range_bar = BoxLayout(
            orientation="horizontal",
            spacing=dp_scaled(6),
            padding=(dp_scaled(8), 0),
            size_hint=(0.72, None),
            height=dp_scaled(38),
            pos_hint={
                "center_x": 0.5,
                "top": 0.93,
            },
        )

        range_items = [
            ("LIVE", None),
            ("12H", 12),
            ("24H", 24),
            ("36H", 36),
            ("48H", 48),
        ]

        for text, hours in range_items:
            button = Button(
                text=text,
                bold=True,
                font_size=sp_scaled(15),
                background_normal="",
                background_down="",
                background_color=(0.08, 0.08, 0.10, 0.72),
                color=(0.75, 0.75, 0.78, 1),
            )

            button.bind(
                on_release=lambda _button, selected_hours=hours:
                    self._emit_range_selected(selected_hours)
            )

            self.range_buttons[hours] = button
            self.range_bar.add_widget(button)

        self.add_widget(self.range_bar)
        self.set_active_range(None)

        # CONTROL BUTTONS
        self.controls = ControlButtons()
        self.controls.size_hint = (1, None)
        self.controls.height = dp_scaled(40)
        self.controls.pos_hint = {'y': 0}
        self.add_widget(self.controls)

    def apply_metric_theme(self, presentation=None):
        self.presentation = presentation or MetricRegistry.presentation("fullscreen")
        self.lbl_title.color = self.presentation.get("title_color", [1, 1, 1, 0.9])
        self.lbl_sub.color = self.presentation.get("stats_color", [0.8, 0.8, 0.8, 0.8])
        self.graph.label_options["color"] = self.presentation.get("graph_label_color", [1, 1, 1, 0.4])
        for label in self.labels_list:
            label.color = self.presentation.get("axis_color", [1, 1, 1, 0.5])



    def _emit_range_selected(self, hours):
        if callable(self.on_range_selected):
            self.on_range_selected(hours)

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
