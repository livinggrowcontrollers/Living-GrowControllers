import csv, math, time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy_garden.graph import Graph, LinePlot
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

class CSVGraphView(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.spacing = dp_scaled(6)
        self.padding = dp_scaled(6)

        self.colors = {
            # INTERNAL
            "T_i": (0.3, 0.9, 1.0, 1),
            "H_i": (0.3, 1.0, 0.3, 1),
        
            # EXTERNAL
            "T_e": (1.0, 0.8, 0.3, 1),
            "H_e": (0.8, 0.6, 1.0, 1),
        
            # BLE outside
            "ble_outside_T": (0.2, 0.7, 1.0, 1),
            "ble_outside_H": (0.2, 1.0, 0.7, 1),
        
            # BLE inside
            "ble_inside_T": (1.0, 0.5, 0.2, 1),
            "ble_inside_H": (1.0, 0.8, 0.4, 1),
        
            # ACTUATORS
            "light": (1.0, 1.0, 0.3, 1),
            "exhaust": (1.0, 0.3, 0.3, 1),
            "circulation": (0.3, 0.6, 1.0, 1),
        }
        self.active_plots = ["T_i", "H_i", "light"]
        self._zoom, self._view_offset, self._last_tap_time = 1.0, 0, 0
        self.all_data_by_device, self.smoothed, self.smoothing = {}, {}, 0.25

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(30))
        self.lbl_title = Label(text="Graph", font_size=sp_scaled(16), bold=True)
        header.add_widget(self.lbl_title)
        self.add_widget(header)

        self.graph = Graph(xmin=0, xmax=100, ymin=0, ymax=100, background_color=(0,0,0,0.1), draw_border=False)
        self.graph.bind(on_touch_down=self._handle_touch_down, on_touch_move=self._handle_touch_move)
        
        self.plots_main, self.plots_glow = {}, {}
        for col, c in self.colors.items():
            self.plots_glow[col] = LinePlot(color=[c[0], c[1], c[2], 0.2], line_width=dp_scaled(4))
            self.graph.add_plot(self.plots_glow[col])
            self.plots_main[col] = LinePlot(color=c, line_width=dp_scaled(2))
            self.graph.add_plot(self.plots_main[col])

        self.add_widget(self.graph)
        self.lbl_stats = Label(text="Keine Daten geladen", size_hint_y=None, height=dp_scaled(20), font_size=sp_scaled(16))
        self.add_widget(self.lbl_stats)

    def set_csv_path(self, p):
        self.all_data_by_device = {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # FALLBACK: Wenn 'name' nicht existiert, nimm 'device_id'
                    display_name = row.get("name", row.get("device_id", "")).strip()
                    if not display_name: 
                        continue  # Wenn gar nichts da ist, überspringen

                    if display_name not in self.all_data_by_device:
                        self.all_data_by_device[display_name] = {k: [] for k in self.colors.keys()}
                    
                    for col in self.colors.keys():
                        val = row.get(col)
                        try:
                            v = float(val)
                            self.all_data_by_device[display_name][col].append(v)
                        except:
                            self.all_data_by_device[display_name][col].append(None)
            return sorted(list(self.all_data_by_device.keys()))
        except Exception as e:
            print(f"Fehler beim CSV-Laden: {e}")
            return []
    def select_device(self, name):
        # Wir leiten einfach auf die neue Multi-Logik um
        self.select_multiple_devices([name])

    def set_active_plots(self, plots):
        self.active_plots = plots
        self._redraw()
    def select_multiple_devices(self, names):
        self.smoothed = {} # Reset
        self.lbl_title.text = "Vergleich: " + ", ".join(names)        
        for name in names:
            if name in self.all_data_by_device:
                for col, arr in self.all_data_by_device[name].items():
                    # Wir erstellen einen eindeutigen Key: "Name|Spalte"
                    key = f"{name}|{col}"
                    self.smoothed[key] = []
                    last = None
                    for v in arr:
                        if v is None:
                            sm = last if last is not None else 0.0
                        else:
                            sm = v if last is None else last * (1 - self.smoothing) + v * self.smoothing
                        self.smoothed[key].append(sm)
                        last = sm
        
        # WICHTIG: Wir müssen die Plots jetzt dynamisch erstellen, 
        # da wir vorher nur feste Plots für ein Gerät hatten!
        self._sync_multi_plots()
        self._reset_view()

    def _sync_multi_plots(self):
        # 1. Alle alten Plots entfernen
        for p in list(self.plots_main.values()) + list(self.plots_glow.values()):
            try: self.graph.remove_plot(p)
            except: pass
        self.plots_main = {}
        self.plots_glow = {}

        # 2. Neue Plots für jede Kombination aus Gerät und Spalte erstellen
        # Wir nutzen die Keys aus self.smoothed (Format: "GeräteName|Spalte")
        for full_key in self.smoothed.keys():
            device_name, col = full_key.split("|")
            
            # Basis-Farbe aus unserer Tabelle holen
            base_c = self.colors.get(col, (0.5, 0.5, 0.5, 1))
            
            # Glow-Effekt (breite, transparente Linie)
            gp = LinePlot(color=[base_c[0], base_c[1], base_c[2], 0.15], line_width=dp_scaled(4))
            self.plots_glow[full_key] = gp
            self.graph.add_plot(gp)
            
            # Haupt-Linie
            mp = LinePlot(color=base_c, line_width=dp_scaled(1.8))
            self.plots_main[full_key] = mp
            self.graph.add_plot(mp)
    def _reset_view(self, *_):
        # FIX: max_len darf nicht 0 sein!
        max_len = max((len(v) for v in self.smoothed.values()), default=1)
        if max_len < 1: max_len = 1 
        
        self._zoom = 300.0 / max_len
        self._view_offset = 0
        self._redraw()

    def _redraw(self):
        if not self.smoothed: return
        max_total = max((len(v) for v in self.smoothed.values()), default=0)
        view_size = max(10, int(300 / self._zoom))
        self._view_offset = max(0, min(self._view_offset, max_total - view_size))
        start, end = max(0, max_total - view_size - self._view_offset), max_total - self._view_offset
        
        vals = []
        for full_key, arr in self.smoothed.items():
            # Wir prüfen nur den Spalten-Teil des Keys (z.B. "T_i" aus "Zelt1|T_i")
            col_part = full_key.split("|")[-1]
            
            if col_part not in self.active_plots:
                self.plots_main[full_key].points = self.plots_glow[full_key].points = []
                continue
            
            view = arr[start:end]
            pts = []
            for i, v in enumerate(view):
                if v is None:
                    continue
                pts.append((i, v))
                vals.append(v)
            
            self.plots_main[full_key].points = pts
            self.plots_glow[full_key].points = pts

        if vals:
            mi, ma = min(vals), max(vals)
            diff = (ma - mi) if (ma - mi) > 0.5 else 1.0
            self.graph.ymin, self.graph.ymax = mi - diff*0.1, ma + diff*0.1
        self.graph.xmax = view_size
        self._update_status(end)

    def _update_status(self, idx):
        if not self.smoothed:
            return
            
        # Wir gruppieren die Werte nach Gerätenamen
        # device_data = { "Zelt 1": ["T_i: 22°C", "H_i: 50%"], "Zelt 2": [...] }
        device_data = {}
        
        labels = {
            "T_i": "Ti", "H_i": "Hi",
            "T_e": "Te", "H_e": "He",
        
            "ble_outside_T": "outside_T",
            "ble_outside_H": "outside_H",
        
            "ble_inside_T": "inside_T",
            "ble_inside_H": "inside_H",
        
            "light": "Light",
            "exhaust": "Exh",
            "circulation": "Circ",
        }

        # Wir gehen durch alle Kurven, die wir im Speicher haben
        for full_key, arr in self.smoothed.items():
            if "|" not in full_key: continue
            
            device_name, col = full_key.split("|")
            
            # Nur anzeigen, wenn der Filter für diese Spalte aktiv ist
            if col in self.active_plots and arr and idx-1 < len(arr):
                lbl = labels.get(col, col)
                if "T" in col:
                    unit = "°C"
                elif "H" in col:
                    unit = "%"
                else:
                    unit = "%"
                v = arr[idx-1]
                
                if v is None:
                    continue
                
                val_str = f"{lbl}:{v:.1f}{unit}"                
                if device_name not in device_data:
                    device_data[device_name] = []
                device_data[device_name].append(val_str)

        # Jetzt bauen wir den finalen Text für das Label
        final_parts = []
        for dev, values in device_data.items():
            # Pro Gerät: "Zelt1 (Ti:22°C | Hi:50%)"
            dev_str = f"{dev}: " + " ".join(values)
            final_parts.append(dev_str)

        if final_parts:
            # Wir trennen die Geräte durch einen fetten Balken
            self.lbl_stats.text = "  ||  ".join(final_parts)
            # Kleiner Trick: Textgröße anpassen, falls es zu viele Daten werden
            self.lbl_stats.font_size = sp_scaled(18) if len(final_parts) > 1 else sp_scaled(18)

    def _handle_touch_down(self, inst, touch):
        if not self.graph.collide_point(*touch.pos): return False
        if (time.time() - self._last_tap_time) < 0.3: self._reset_view()
        self._last_tap_time = time.time()
        return True

    def _handle_touch_move(self, inst, touch):
        if not self.graph.collide_point(*touch.pos): return False
        if abs(touch.dy) > abs(touch.dx):
            self._zoom = max(0.1, min(20.0, self._zoom * (1.0 + touch.dy/500.0)))
        else:
            self._view_offset += int(touch.dx / (5 / self._zoom))
        self._redraw()
        return True