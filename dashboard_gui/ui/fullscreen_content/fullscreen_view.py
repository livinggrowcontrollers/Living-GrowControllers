# dashboard_gui/ui/fullscreen_content/fullscreen_view.py
import os
from kivy.uix.screenmanager import Screen
import config 
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.scaling_utils import dp_scaled
from kivy_garden.graph import LinePlot
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.common.graph_chart_content.chart_time_axis import compute_time_axis_labels
from dashboard_gui.ui.fullscreen_content.fullscreen_main_panel import FullScreenMainPanel
from dashboard_gui.ui.common.graph_chart_content.metric_registry import MetricRegistry
from dashboard_gui.ui.common.graph_chart_content.graph_mesh import clear_graph_series, update_graph_mesh
class FullScreenView(Screen):
    name = "fullscreen"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.tile_id = None
        self.current_key = None
        self._active_unit = ""

        # Instanziierung des ausgelagerten Hauptpanels
        self.layout = FullScreenMainPanel()
        self.add_widget(self.layout)
        
        self.xmax = config.get_tile_graph_window()



        # Shortcuts/Aliase auf die Widgets des Panels für 1:1 Kompatibilität im Code
        self.graph = self.layout.graph
        self.plot = self.layout.plot
        self.plot_glow = self.layout.plot_glow
        self.mesh = self.layout.mesh
        self.mesh_color = self.layout.mesh_color
        self.labels_list = self.layout.labels_list
        self.lbl_title = self.layout.lbl_title
        self.lbl_value = self.layout.lbl_value
        self.lbl_sub = self.layout.lbl_sub
        self.header = self.layout.header
        self.controls = self.layout.controls
        self.graph.bind(pos=self._upd_mesh, size=self._upd_mesh)

        # Binden der Navigation & Controls direkt an diesen Screen
        self.layout.btn_left.bind(on_release=lambda *_: self._switch(-1))
        self.layout.btn_right.bind(on_release=lambda *_: self._switch(1))
        self.layout.controls.on_reset = self.reset_from_global

        self.active_tile = None  
        GLOBAL_STATE.ui_handler.attach_screen("fullscreen", self)

    def _update_bg(self, *args):
        # Reicht das Event an das Panel weiter
        self.layout._update_bg(*args)

    def _upd_mesh(self, *args):
        update_graph_mesh(self.graph, self.plot, self.mesh)

    def activate_tile(self, full_key):
        print(f"[FS] Aktiviere: {full_key}")

        dev_id, channel, tile_id = GLOBAL_STATE.tile_engine.parse_full_key(full_key)
        if not dev_id or not channel or not tile_id:
            print(f"[FS] INVALID KEY FORMAT: {full_key}")
            return False

        allowed = GLOBAL_STATE.get_active_tiles(dev_id, channel)
        if tile_id not in allowed:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(dev_id, channel)
            print(f"[FS] BLOCKED INVALID TILE: {full_key}")
            if fallback_key and fallback_key != full_key:
                print(f"[FS] FALLBACK -> {fallback_key}")
                return self.activate_tile(fallback_key)
            self._clear_active_tile()
            return False

        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.current_key = full_key
        self.tile_id = tile_id
        
        # RSSI Spezialbehandlung
        is_rssi = self.tile_id == "rssi"
        
        if hasattr(GLOBAL_STATE, 'tile_engine'):
            if self.tile_id in GLOBAL_STATE.tile_engine.active_tiles or is_rssi:
                readable_name = "RSSI" if is_rssi else self.tile_id.upper() if "vpd" in self.tile_id else self.tile_id.title()
            else:
                readable_name = self.tile_id.replace("_", " ").title()

        cfg = MetricRegistry.get(self.tile_id)

        main_col = cfg["color"]
        glow_col = cfg["glow"]
        clean_title = cfg.get("name", readable_name)
        
        # Unit für RSSI fix
        if is_rssi:
            unit = "dBm"
        elif "temp" in self.tile_id:
            unit = GLOBAL_STATE.unit_engine.get_temp_unit()
        else:
            unit = GLOBAL_STATE.get_unit(full_key) or cfg.get("unit", "")
            
        self._active_unit = unit
        self.lbl_title.text = clean_title

        # Background & Farben
        bg_path = os.path.join("dashboard_gui", "assets", "background2.png")
        if os.path.exists(bg_path):
            self.layout.bg_rect.source = bg_path
            self.layout.bg_color.rgba = (1, 1, 1, 0.40)
        else:
            self.layout.bg_rect.source = ""
            self.layout.bg_color.rgba = (0.08, 0.08, 0.1, 1)
        
        self.mesh_color.rgba = (main_col[0], main_col[1], main_col[2], 0.25)
        
        # Graph zurücksetzen
        for p in list(self.graph.plots):
            self.graph.remove_plot(p)
            
        self.plot = LinePlot(color=main_col, line_width=dp_scaled(2.5))
        self.plot_glow = LinePlot(color=glow_col, line_width=dp_scaled(3))
        self.graph.add_plot(self.plot_glow)
        self.graph.add_plot(self.plot)
        
        self._load_data()
        return True

    def _clear_active_tile(self):
        self.current_key = None
        self.tile_id = None
        self.active_tile = None
        self.lbl_title.text = ""
        self.lbl_value.text = "---"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.graph.ymin = 0
        self.graph.ymax = 1

    def _load_data(self):
        if not self.current_key:
            return

        buf = GLOBAL_STATE.get_graph_data(self.current_key)
        if not buf or len(buf) < 1:
            buf = GLOBAL_STATE.graph_engine.get_buffer(self.current_key)

        if not buf or len(buf) < 1:
            self._render_empty_graph()
            return

        unit = GLOBAL_STATE.get_unit(self.current_key)
        if not unit and "temp" in self.tile_id:
            unit = GLOBAL_STATE.unit_engine.get_temp_unit()
            
        self._active_unit = unit or "—"

        win_size = config.get_tile_graph_window()
        display_buf = list(buf)[-win_size:]

        self.graph.xmin = 0
        self.graph.xmax = max(len(display_buf) - 1, 1)   


        refresh_rate = config.get_refresh_interval()
        raw_res = float(config.get_graph_resolution())

        labels = compute_time_axis_labels(
            display_len=len(display_buf),
            refresh_rate=refresh_rate,
            raw_res=raw_res
        )

        for lbl, txt in zip(self.labels_list, labels):
            lbl.text = txt


        if len(display_buf) == 1:
            pts = [(0, display_buf[0]), (1, display_buf[0])]
        else:
            pts = list(enumerate(display_buf))
            
        self.plot.points = pts
        self.plot_glow.points = pts

        mn_val = min(display_buf)
        mx_val = max(display_buf)
        if mn_val == mx_val:
            self.graph.ymin = mn_val - 1.0
            self.graph.ymax = mx_val + 1.0
        else:
            diff = mx_val - mn_val
            self.graph.ymin = mn_val - (diff * 0.08)
            self.graph.ymax = mx_val + (diff * 0.08)
        
        
        self._upd_mesh()   

        last_val = display_buf[-1]
        trend_icon = GLOBAL_STATE.get_trend_icon(self.current_key) or ""
        
        # NEU: Nutzung des zentralen Formatters für das große HUD-Value-Label
        self.lbl_value.text = UIFormatter.format_sensor_label(
            name="",                 # Name ist im Fullscreen schon in lbl_title, daher leer
            value=last_val, 
            unit=self._active_unit, 
            trend=trend_icon,
            sz_val=70,               # Entspricht deinem alten font_size=sp_scaled(70)
            sz_unit=30,              # Entspricht deinem alten [size=int(dp_scaled(30))]
            sz_trend=45              # Gleiche Größe für das Trend-Icon wie die Einheit
        )

        avg_v, mn_stat, mx_stat = GLOBAL_STATE.graph_engine.get_stats(self.current_key)
        if avg_v is not None:
            self.lbl_sub.text = f"avg: {avg_v:.2f} {self._active_unit} | min: {mn_stat:.2f} {self._active_unit} | max: {mx_stat:.2f} {self._active_unit}"
    
    
    def update_from_global(self, data):
        self.header.update_from_global(data)

        active_dev = GLOBAL_STATE.get_active_device_id()
        active_ch = GLOBAL_STATE.get_active_channel()
        if not active_dev or not active_ch:
            self._clear_active_tile()
            return

        allowed = GLOBAL_STATE.get_active_tiles(active_dev, active_ch)
        if not allowed:
            self._clear_active_tile()
            return

        if not self.tile_id:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(active_dev, active_ch)
            if fallback_key:
                self.activate_tile(fallback_key)
            return
        
        expected_full_key = f"{active_dev}_{active_ch}_{self.tile_id}"
        
        if self.tile_id not in allowed:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(active_dev, active_ch)
            print(f"[FS] Schutzfunktion! Tile {self.tile_id} nicht erlaubt für neues Gerät. Springe zu: {fallback_key}")
            if fallback_key:
                self.activate_tile(fallback_key)
            else:
                self._clear_active_tile()
            return
            
        if self.current_key != expected_full_key:
            if not self.activate_tile(expected_full_key):
                return

        self._load_data()

    def _switch(self, direction):
        if not self.current_key:
            return

        # 1. Nächsten Key von der gesicherten Engine berechnen lassen
        next_key = GLOBAL_STATE.tile_engine.get_next_full_key(self.current_key, direction)
        
        # 2. Extrahiere das geplante Tile-ID aus dem neuen Key
        next_dev, next_ch, next_tile_id = GLOBAL_STATE.tile_engine.parse_full_key(next_key)

        # 3. Das finale Sicherheits-Gate
        allowed = GLOBAL_STATE.get_active_tiles(next_dev, next_ch)
        
        if next_tile_id in allowed:
            if next_key != self.current_key:
                self.activate_tile(next_key)
        else:
            print(f"[FS UI-Gate] Blockiert: Tile '{next_tile_id}' ist für dieses Gerät inaktiv!")
            
            # Falls wir in einer Sackgasse stecken, erzwinge das erste aktive Tile
            active_dev = GLOBAL_STATE.get_active_device_id()
            active_ch = GLOBAL_STATE.get_active_channel()
            fallback = GLOBAL_STATE.tile_engine.get_first_tile_key(active_dev, active_ch)
            if fallback and fallback != self.current_key:
                self.activate_tile(fallback)
    def reset_from_global(self):
        print("[FS] Resetting Fullscreen UI...")
        unit = GLOBAL_STATE.get_unit(self.current_key) if self.current_key else ""
        self.lbl_value.text = f"--- {unit}"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"
        
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.graph.ymin = 0
        self.graph.ymax = 1
        
        if hasattr(self, 'header'):
            self.header.set_rssi(None)   # Header RSSI zurücksetzen
            
        # Extra: RSSI Tile zurücksetzen
        if self.tile_id == "rssi":
            self.lbl_value.text = "--- dBm"
            self.lbl_sub.text = "Signalstärke nicht verfügbar"
        
        for widget in self.walk():
            if widget != self and hasattr(widget, 'reset') and callable(widget.reset):
                widget.reset()

    def _render_empty_graph(self):
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.lbl_value.text = f"--- {self._active_unit}"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"
        self.graph.ymin = 0
        self.graph.ymax = 1
        for lbl in self.labels_list:
            lbl.text = ""

    def on_touch_down(self, touch):
        if hasattr(GLOBAL_STATE, "ggm"):
            GLOBAL_STATE.ggm.handle_touch("fullscreen", "down", touch)
        return super().on_touch_down(touch)
    
    def on_touch_move(self, touch):
        if hasattr(GLOBAL_STATE, "ggm"):
            GLOBAL_STATE.ggm.handle_touch("fullscreen", "move", touch)
        return super().on_touch_move(touch)
    
    def on_touch_up(self, touch):
        if hasattr(GLOBAL_STATE, "ggm"):
            GLOBAL_STATE.ggm.handle_touch("fullscreen", "up", touch)
        return super().on_touch_up(touch)
