from collections import defaultdict, deque

import config

from dashboard_gui.gsm_engines.graph_models import (
    GraphSnapshot,
    GraphStats,
    axis_bounds,
)
from dashboard_gui.ui.common.graph_chart_content.chart_time_axis import (
    compute_time_axis_labels,
)


class GraphEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self.running = True

        # Buffers
        self.window = config.get_tile_graph_window()
        self.graph_buffers = defaultdict(self._new_buffer)
        self._trend_buffers = defaultdict(self._new_buffer)
        self._last_smoothed_values = {}
        self._last_units = {}

        # Counter für das Downsampling (Graph Resolution)
        self._update_counters = defaultdict(int)

        # Separater Graph-Takt
        self.graph_refresh_interval = config.get_graph_refresh_interval()
        self.base_refresh_interval = config.get_refresh_interval()
        self._graph_refresh_tick_interval = 1
        self.graph_resolution = 100.0
        self._resolution_skip_interval = 1
        self._graph_refresh_counters = defaultdict(int)

        # Trends
        self.global_trends = {}

        # Alle dynamischen Settings zentral laden
        self.refresh_config()

    def _new_buffer(self):
        return deque(maxlen=self.window)

    # ---------------------------------------------------------
    # UNIFIED GRAPH SNAPSHOTS
    # ---------------------------------------------------------
    def get_live_snapshot(self, key, label_count=5):
        buffer = self.get_buffer(key)
        if not buffer:
            return None

        display_values = tuple(buffer[-self.window:])
        if len(display_values) == 1:
            points = (
                (0.0, display_values[0]),
                (1.0, display_values[0]),
            )
        else:
            points = tuple(
                (float(index), value)
                for index, value in enumerate(display_values)
            )

        ymin, ymax = axis_bounds(display_values)
        stats_values = self.get_stats(key)
        stats = (
            GraphStats(*stats_values)
            if stats_values[0] is not None
            else None
        )

        return GraphSnapshot(
            mode="live",
            points=points,
            timestamps=(),
            values=display_values,
            xmin=0.0,
            xmax=max(float(len(display_values) - 1), 1.0),
            ymin=ymin,
            ymax=ymax,
            labels=tuple(
                self.get_live_time_axis_labels(
                    display_len=len(display_values),
                    label_count=label_count,
                )
            ),
            last_value=display_values[-1],
            stats=stats,
            trend_icon=self.get_trend_icon(key) or "",
        )

    # ---------------------------------------------------------
    # DATA ACCESS (Wichtig für Mixed Mode & Tiles)
    # ---------------------------------------------------------
    def get_last_value(self, key):
        buf = self.graph_buffers.get(key)
        if buf and len(buf) > 0:
            return buf[-1]
        return None

    def get_buffer(self, key):
        buf = self.graph_buffers.get(key)
        return list(buf) if buf else []

    def get_stats(self, key):
        buf = self.graph_buffers.get(key)
        if not buf or len(buf) < 2:
            return None, None, None
    
        data = list(buf)
        avg = sum(data) / len(data)
        mn = min(data)
        mx = max(data)
    
        if mn == mx:
            mn -= 0.1
            mx += 0.1
    
        return avg, mn, mx

    def get_trend_icon(self, key):
        val = self.global_trends.get(key, 0)
        icons = {-1: "\uf063", 1: "\uf062", 0: "\uf061"}
        return icons.get(val, "\uf061")

    def get_all_keys(self):
        return list(self.graph_buffers.keys())

    def get_graph_refresh_interval(self):
        return self.graph_refresh_interval


    def get_graph_refresh_tick_interval(self):
        return self._graph_refresh_tick_interval



    def get_window_size(self):
        return self.window

    def get_effective_point_interval(self):
        return (
            self.graph_refresh_interval
            * self._resolution_skip_interval
        )

    def get_live_time_axis_labels(self, display_len, label_count=5):
        return compute_time_axis_labels(
            display_len=int(display_len),
            refresh_rate=self.graph_refresh_interval,
            raw_res=self.graph_resolution,
        )

    # ---------------------------------------------------------
    # PROCESS VALUE
    # ---------------------------------------------------------
    def process_new_value(self, key, value):
        if not self.running or value is None:
            return

        # ---------------------------------------------------------
        # SEPARATER GRAPH-TAKT
        # ---------------------------------------------------------
        # Der erste Wert jedes Keys wird sofort verarbeitet.
        # Danach wird nur noch im konfigurierten Graph-Intervall verarbeitet.
        has_no_graph_data = (
            key not in self.graph_buffers
            or len(self.graph_buffers[key]) == 0
        )

        if has_no_graph_data:
            self._graph_refresh_counters[key] = 0
        else:
            self._graph_refresh_counters[key] += 1

            if (
                self._graph_refresh_counters[key]
                < self._graph_refresh_tick_interval
            ):
                return

            self._graph_refresh_counters[key] = 0

        try:
            val_float = float(value)
            current_unit = self.gsm.get_unit(key)
            
            # --- UNIT SWITCH LOGIK ---
            if key in self._last_units and self._last_units[key] != current_unit:
                print(f"[GraphEngine] Unit switch... Resetting buffer for {key}")
                self.graph_buffers[key] = deque([val_float, val_float], maxlen=self.window)
                self._trend_buffers[key] = deque([val_float, val_float], maxlen=self.window)
                self._last_smoothed_values[key] = val_float
                self._last_units[key] = current_unit
                self._update_counters[key] = 0
                self._graph_refresh_counters[key] = 0
                return
            
            # --- 1. SMOOTHING LOGIK ---
            # Intuitive Logik: 
            # Wenn Config-Faktor = 0.9 -> Sehr träge/glatt (0.1 Altwert + 0.9 Neuwert? Nein, genau andersrum!)
            # Mathematisch: Je kleiner der Faktor für den *neuen* Wert, desto stärker die Glättung.
            # Daher: f_new = 1.0 - smoothing_factor
            
            if "mixed" in key:
                f_new = 0.2  # Beibehaltenes Hardcoded-Smoothing für Mixed Mode (entspricht 0.8 Smoothing)
            else:
                # Clamp zwischen 0.0 und 0.99, um Divisionen durch 0 oder starre Graphen zu vermeiden
                cfg_factor = max(0.0, min(0.99, self.smoothing_factor))
                f_new = 1.0 - cfg_factor 
            
            if key not in self._last_smoothed_values:
                smoothed = val_float
            else:
                last = self._last_smoothed_values[key]
                # Schwellenwert-Breakout (bei harten Sprüngen nicht glätten)
                if abs(val_float - last) > 5.0:
                    smoothed = val_float
                else:
                    # Exponentieller gleitender Mittelwert
                    smoothed = (last * (1.0 - f_new)) + (val_float * f_new)
            
            self._last_smoothed_values[key] = smoothed
            
            # --- 2. GRAPH RESOLUTION LOGIK (Slider: 1-100) ---
            skip_interval = self._resolution_skip_interval
                        
            # --- DER FIX: Explizite Prüfung vor dem Counter-Inkrement ---
            # Wir prüfen, ob für diesen Key überhaupt schon Werte im Buffer existieren.
            # Da es ein defaultdict ist, müssen wir schauen, ob der Key existiert UND Werte hat.
            has_no_data = key not in self.graph_buffers or len(self.graph_buffers[key]) == 0
            
            if has_no_data:
                # Absolut erster Frame für diesen Key: Sofort durchlassen!
                # Wir setzen den Counter direkt auf 0, damit der NÄCHSTE Frame das Intervall startet.
                self._update_counters[key] = 0
                force_update = True
            else:
                # Normaler Modus: Counter hochzählen
                self._update_counters[key] += 1
                force_update = self._update_counters[key] >= skip_interval

            # Nur schreiben, wenn das Intervall erreicht ist ODER wir den ersten Frame erzwingen
            if force_update:
                self._update_counters[key] = 0  
                
                # Puffer befüllen
                g_buf = self.graph_buffers[key]
                g_buf.append(smoothed)
                if len(g_buf) > self.window:
                    g_buf.popleft()
                
                t_buf = self._trend_buffers[key]
                t_buf.append(smoothed)
                if len(t_buf) > self.window:
                    t_buf.popleft()
                    
                self.global_trends[key] = self._calculate_trend_logic(list(t_buf))            
        except Exception as e:
            print(f"[GraphEngine] Error in process_new_value: {e}")

    def _calculate_trend_logic(self, buf):
        if len(buf) < 5: return 0
        start, end = buf[0], buf[-1]
        diff = end - start
        threshold = max(0.01, abs(start) * 0.002)
        
        if diff > threshold: return 1
        if diff < -threshold: return -1
        return 0

    def reset(self):
        print("[GraphEngine] RESET")
        self.graph_buffers.clear()
        self._trend_buffers.clear()
        self._last_smoothed_values.clear()
        self.global_trends.clear()
        self._update_counters.clear()
        self._graph_refresh_counters.clear()

    def rebuild_buffers(self):
        self.window = config.get_tile_graph_window()
        for key in list(self.graph_buffers.keys()):
            old_buf = list(self.graph_buffers[key])[-self.window:]
            self.graph_buffers[key] = deque(old_buf, maxlen=self.window)
        for key in list(self._trend_buffers.keys()):
            old_buf = list(self._trend_buffers[key])[-self.window:]
            self._trend_buffers[key] = deque(old_buf, maxlen=self.window)

    def refresh_config(
        self,
        graph_refresh_interval=None,
        base_refresh_interval=None,
    ):
        self.rebuild_buffers()

        self.smoothing_factor = float(
            config.get_graph_smoothing_factor()
        )

        raw_resolution = float(config.get_graph_resolution())

        if raw_resolution <= 1.0:
            self.graph_resolution = max(
                1.0,
                raw_resolution * 100.0,
            )
        else:
            self.graph_resolution = raw_resolution

        self.graph_resolution = max(
            1.0,
            min(100.0, self.graph_resolution),
        )

        self._resolution_skip_interval = max(
            1,
            int(100.0 / self.graph_resolution),
        )

        if graph_refresh_interval is None:
            graph_refresh_interval = config.get_graph_refresh_interval()

        if base_refresh_interval is None:
            base_refresh_interval = config.get_refresh_interval()

        self.graph_refresh_interval = max(
            0.1,
            float(graph_refresh_interval),
        )

        self.base_refresh_interval = max(
            0.001,
            float(base_refresh_interval),
        )

        self._graph_refresh_tick_interval = max(
            1,
            round(
                self.graph_refresh_interval
                / self.base_refresh_interval
            ),
        )

        # Den tatsächlich erreichbaren Zeitabstand festhalten.
        self.graph_refresh_interval = (
            self._graph_refresh_tick_interval
            * self.base_refresh_interval
        )

        self._graph_refresh_counters.clear()

        if config.is_developer_mode():
            print(
                "[GraphEngine] Config refreshed: "
                f"graph_interval={self.graph_refresh_interval:.3f}s, "
                f"base_interval={self.base_refresh_interval:.3f}s, "
                f"ticks={self._graph_refresh_tick_interval}"
            )
