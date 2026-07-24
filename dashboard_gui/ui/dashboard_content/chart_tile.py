# dashboard_content/chart_tile.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy_garden.graph import Graph, LinePlot
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Rectangle, Color, RoundedRectangle, Mesh
from kivy.uix.floatlayout import FloatLayout
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
from dashboard_gui.ui.common.graph_chart_content.graph_mesh import (
    clear_graph_series,
    update_graph_mesh,
)
class ChartTile(ButtonBehavior, BoxLayout):
    def __init__(self, tile_id, **kw):
        ButtonBehavior.__init__(self, **kw)
        BoxLayout.__init__(self, orientation="vertical", spacing=dp_scaled(2), padding=dp_scaled(8))

        # Konfiguration zentral aus der MetricRegistry beziehen
        cfg = MetricRegistry.get(tile_id)

        self.tile_id = tile_id
        self.title = cfg.get("name")
        self.unit = cfg.get("unit")
        self.color = cfg.get("color")
        self._glow_color = cfg.get("glow")
        self.style = cfg.get("style", {})
        self.presentation = MetricRegistry.presentation("tile")
        self._last_val = None
        self._last_avg = None
        self._last_min = None
        self._last_max = None
        self._graph_mode = "live"
        self._history_render_signature = None
        self.window = GLOBAL_STATE.graph_engine.get_window_size()

        # -------------------------------------------------
        # 1. MODERNISIERTER BACKGROUND (Jetzt noch transparenter!)
        # -------------------------------------------------
        with self.canvas.before:
            self.bg_color = Color(*self.presentation.get("background", [0.08, 0.08, 0.10, 0.40]))
        
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp_scaled(2)]
            )
        
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # -------------------------------------------------
        # 2. HEADER & LIVE-WERT (Fokus auf große Typografie)
        # -------------------------------------------------
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled((35)), padding=[dp_scaled(6), 0])
        self.lbl_main_info = Label(
            text=f"[color=#555555]{self.title}[/color]", 
            markup=True, 
            halign="left", 
            valign="middle",
            font_size=sp_scaled((20)),
            bold=True,
            color=self.presentation.get("title_color", [1, 1, 1, 0.9]),
            outline_width=1,
            outline_color=(0,0,0,0.15)
        )
        self.lbl_main_info.bind(size=self.lbl_main_info.setter('text_size'))
        header.add_widget(self.lbl_main_info)
        self.add_widget(header)

        # -------------------------------------------------
        # 3. GRAPH CONTAINER & GRAFIK-ENGINE
        # -------------------------------------------------
        self.graph_container = FloatLayout(size_hint=(1, 1))
        
        self.graph = Graph(
            draw_border=False, 
            background_color=(0,0,0,0),
            padding=dp_scaled(0), 
            xmin=0, xmax=self.window, ymin=0, ymax=1,
            size_hint=(1, 1), 
            pos_hint={'x': 0, 'y': 0}
        )
        
        # Plot-Linie dicker für professionellen Look (Anti-Aliased Style)
        self.plot = LinePlot(color=self.color, line_width=dp_scaled(1.5))
        self.plot_glow = LinePlot(color=self._glow_color, line_width=dp_scaled(2.5))
        self.graph.add_plot(self.plot)
        self.graph.add_plot(self.plot_glow)
        self.graph_container.add_widget(self.graph)

        # -------------------------------------------------
        # 4. TRANSTRANSQUARENTE FILL-FLÄCHE (Unterschwelliges Leuchten)
        # -------------------------------------------------
        with self.graph.canvas.after:
            self.mesh_color = Color(self.color[0], self.color[1], self.color[2], 0.25)
            # WICHTIG: triangle_strip statt triangle_fan
            self.mesh = Mesh(mode='triangle_strip')
            
        self.graph.bind(pos=self._upd_mesh, size=self._upd_mesh)

        # -------------------------------------------------
        # 5. STATS LABELS (Subtil im Hintergrund gedimmt)
        # -------------------------------------------------
        self.lbl_avg = Label(
            text="avg: --", 
            font_size=sp_scaled(20), 
            bold=True,
            color=self.presentation.get("stats_color", [1, 1, 1, 0.7]),
            size_hint=(None, None),
            size=(dp_scaled(140), dp_scaled(20)),
            pos_hint={'right': 0.96, 'top': 0.95}, 
            halign="right"
        )
        self.lbl_avg.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))

        self.minmax_box = BoxLayout(
            orientation="horizontal", 
            size_hint=(1, None),
            height=dp_scaled(20),
            pos_hint={'x': 0.1, 'y': 0.13},
            padding=[dp_scaled(12), 0],
            spacing=dp_scaled(20)
        )
        
        stats_color = self.presentation.get("stats_color", [1, 1, 1, 0.7])
        self.lbl_min = Label(text="min: --", font_size=sp_scaled(18), bold=True, color=stats_color, halign="left")
        self.lbl_max = Label(text="max: --", font_size=sp_scaled(18), bold=True, color=stats_color, halign="left")
        
        for l in [self.lbl_min, self.lbl_max]:
            l.bind(size=lambda s, w: setattr(s, 'text_size', (w[0], None)))
        
        self.minmax_box.add_widget(self.lbl_max)
        self.minmax_box.add_widget(self.lbl_min)
        self.graph_container.add_widget(self.lbl_avg)   
        self.graph_container.add_widget(self.minmax_box)

        # DEZENTE ZEITACHSE UNTER MIN/MAX
        self.x_axis_labels = GridLayout(
            cols=5, size_hint=(1, None), height=dp_scaled(18),
            pos_hint={'x': 0, 'y': 0.026}, padding=[dp_scaled(12), 0]
        )
        self.labels_list = []
        for _ in range(5):
            lbl = Label(text="", font_size=sp_scaled(15), color=self.presentation.get("axis_color", [1, 1, 1, 0.4]), bold=True, halign="center")
            self.labels_list.append(lbl)
            self.x_axis_labels.add_widget(lbl)
        
        self.graph_container.add_widget(self.x_axis_labels)
        self.add_widget(self.graph_container)

    def _upd_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _upd_mesh(self, *args):
        update_graph_mesh(self.graph, self.plot, self.mesh)

    def update(self, value, buf_key, render=False):
        if not render:
            return

        if self._graph_mode != "live":
            self._graph_mode = "live"
            self._history_render_signature = None
            self._last_val = None
    
        history = GLOBAL_STATE.get_graph_data(buf_key)
        unit = GLOBAL_STATE.get_unit(buf_key)
    
        if not history:
            self.lbl_main_info.text = f"[color=#555555]{self.title}: --[/color]"
            self._render_empty_graph()
            return
    
        last_val = history[-1]
        trend_icon = GLOBAL_STATE.get_trend_icon(buf_key)
    
        if last_val != self._last_val:
            self.lbl_main_info.text = UIFormatter.format_sensor_label(
                name=self.title, value=last_val, unit=unit, trend=trend_icon,
                style={**self.presentation.get("formatter", {}), **self.style},
            )
            self._last_val = last_val
    
        self._render_buffer(history, unit, buf_key)
        self._upd_mesh()

    def render_history_snapshot(self, snapshot, unit):
        if snapshot is None:
            self.render_history_status(
                "History",
                "Keine Daten",
            )
            return

        resolved_unit = unit or self.unit or "—"
        signature = (
            snapshot.points,
            snapshot.xmin,
            snapshot.xmax,
            snapshot.ymin,
            snapshot.ymax,
            snapshot.labels,
            snapshot.last_value,
            snapshot.stats,
            resolved_unit,
        )
        if (
            self._graph_mode == "history"
            and signature == self._history_render_signature
        ):
            return

        self._graph_mode = "history"
        self._history_render_signature = signature
        self._last_val = snapshot.last_value

        number_style = {
            **self.presentation.get("formatter", {}),
            **self.style,
        }
        self.lbl_main_info.text = UIFormatter.format_sensor_label(
            name=self.title,
            value=snapshot.last_value,
            unit=resolved_unit,
            trend="",
            style=number_style,
        )

        self.graph.xmin = snapshot.xmin
        self.graph.xmax = snapshot.xmax
        self.graph.ymin = snapshot.ymin
        self.graph.ymax = snapshot.ymax
        points = list(snapshot.points)
        self.plot.points = points
        self.plot_glow.points = points

        for index, label in enumerate(self.labels_list):
            label.text = (
                snapshot.labels[index]
                if index < len(snapshot.labels)
                else ""
            )

        stats = snapshot.stats
        if stats is None:
            self.lbl_avg.text = "avg: ---"
            self.lbl_min.text = "min: ---"
            self.lbl_max.text = "max: ---"
        else:
            self.lbl_avg.text = (
                f"avg: "
                f"{UIFormatter.format_number(stats.average, number_style)} "
                f"{resolved_unit}"
            )
            self.lbl_min.text = (
                f"min: "
                f"{UIFormatter.format_number(stats.minimum, number_style)}"
                f"{resolved_unit}"
            )
            self.lbl_max.text = (
                f"max: "
                f"{UIFormatter.format_number(stats.maximum, number_style)}"
                f"{resolved_unit}"
            )

        self._upd_mesh()

    def render_history_status(self, range_label, message):
        signature = ("status", range_label, message)
        if (
            self._graph_mode == "history"
            and signature == self._history_render_signature
        ):
            return

        self._graph_mode = "history"
        self._history_render_signature = signature
        self._last_val = None
        self.lbl_main_info.text = (
            f"[color=#555555]{self.title}: --[/color]"
        )
        self._render_empty_graph()
        self.lbl_avg.text = range_label
        self.lbl_min.text = message
        self.lbl_max.text = ""

    def refresh_metric_theme(self):
        """Refresh appearance while preserving the tile's graph history."""
        cfg = MetricRegistry.get(self.tile_id)
        self.title = cfg["name"]
        self.unit = cfg["unit"]
        self.color = cfg["color"]
        self._glow_color = cfg["glow"]
        self.style = cfg["style"]
        self.presentation = MetricRegistry.presentation("tile")
        self.plot.color = self.color
        self.plot_glow.color = self._glow_color
        self.mesh_color.rgba = (*self.color[:3], 0.25)
        self.bg_color.rgba = self.presentation.get("background", [0.08, 0.08, 0.10, 0.40])
        self.lbl_main_info.color = self.presentation.get("title_color", [1, 1, 1, 0.9])
        stats_color = self.presentation.get("stats_color", [1, 1, 1, 0.7])
        self.lbl_avg.color = stats_color
        self.lbl_min.color = stats_color
        self.lbl_max.color = stats_color
        for label in self.labels_list:
            label.color = self.presentation.get("axis_color", [1, 1, 1, 0.4])
        self._last_val = None
        self._history_render_signature = None

    def _render_empty_graph(self):
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.lbl_avg.text = "avg: ---"
        self.lbl_min.text = "min: ---"
        self.lbl_max.text = "max: ---"
        self.graph.ymin = 0
        self.graph.ymax = 1
        if hasattr(self, 'labels_list'):
            for lbl in self.labels_list:
                lbl.text = ""

    def _render_buffer(self, buf, unit, buf_key):
        if not buf: 
            self._render_empty_graph()
            return
    
        self.window = GLOBAL_STATE.graph_engine.get_window_size()
        display_buf = list(buf)[-self.window:]
        
        # --- WIEDER REVERTED: Deine originale, dynamische X-Achsen-Stauchung ---
        self.graph.xmin = 0
        self.graph.xmax = max(len(display_buf) - 1, 1)
    
        mn_val = min(display_buf)
        mx_val = max(display_buf)
        
        if mn_val == mx_val:
            self.graph.ymin = mn_val - 1.0
            self.graph.ymax = mx_val + 1.0
        else:
            diff = mx_val - mn_val
            self.graph.ymin = mn_val - (diff * 0.08) 
            self.graph.ymax = mx_val + (diff * 0.08)
    
        # --- DER MINIMALE FIX FÜR KIVY ---
        # Wenn nur 1 Wert existiert, tricksen wir Kivy aus, indem wir einen 
        # zweiten Punkt bei X=1 mit demselben Wert setzen. 
        # Da xmax oben durch max(1-1, 1) ebenfalls auf 1 steht, passt das perfekt!
        if len(display_buf) == 1:
            pts = [(0, display_buf[0]), (1, display_buf[0])]
        else:
            pts = [(i, val) for i, val in enumerate(display_buf)]
        self.plot.points = pts
        self.plot_glow.points = pts
        
        # --- DEINE ORIGINAL-LOGIK (Unverändert für Timeline, Averages & Trends) ---

        labels = GLOBAL_STATE.graph_engine.get_live_time_axis_labels(
            display_len=len(display_buf),
            label_count=len(self.labels_list),
        )

        for lbl, txt in zip(self.labels_list, labels):
            lbl.text = txt


        avg_v, mn_stat, mx_stat = GLOBAL_STATE.graph_engine.get_stats(buf_key)
        if avg_v is not None:
            number_style = {**self.presentation.get("formatter", {}), **self.style}
            self.lbl_avg.text = f"avg: {UIFormatter.format_number(avg_v, number_style)} {unit}"
            self.lbl_min.text = f"min: {UIFormatter.format_number(mn_stat, number_style)}{unit}"
            self.lbl_max.text = f"max: {UIFormatter.format_number(mx_stat, number_style)}{unit}"

    def reset(self):
        self._graph_mode = "live"
        self._history_render_signature = None
        self.lbl_main_info.text = f"[color=#555555]{self.title}[/color]"
        self._render_empty_graph()

    def on_release(self):
        idx = GLOBAL_STATE.get_active_index()
        dev_list = GLOBAL_STATE.get_device_list()
        if not dev_list or idx >= len(dev_list): return
        item = dev_list[idx]
        dev_id = item.get("device_id") if isinstance(item, dict) else item
        channel = GLOBAL_STATE.get_active_channel()
        full_key = f"{dev_id}_{channel}_{self.tile_id}"
        if hasattr(GLOBAL_STATE, "ggm"):
            GLOBAL_STATE.ggm.engines["dashboard"].open_fullscreen(full_key)
