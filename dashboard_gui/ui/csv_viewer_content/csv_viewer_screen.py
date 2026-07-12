from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.metrics import dp

from kivy.uix.scrollview import ScrollView
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.csv_viewer_content.csv_viewer_filebrowser import CSVViewerFileBrowser
from dashboard_gui.ui.csv_viewer_content.csv_viewer_table import CSVTableView
from dashboard_gui.ui.csv_viewer_content.csv_viewer_graphs import CSVGraphView
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE

class CSVViewerScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        GLOBAL_STATE.ui_handler.attach_screen("csv_viewer", self)
        self.file_browser = None  # Referenz initialisieren
        self.current_csv = None
        self.active_tab = "Table"
        self.active_filters = ["T_i", "H_i", "vpd_i"]
        self.active_devices = []
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)

        self.header = HeaderBar()
        root.add_widget(self.header)

        self.area = BoxLayout(orientation="vertical")
        root.add_widget(self.area)

        self.device_menu = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(5))
        self.area.add_widget(self.device_menu)
        
        self.filter_menu = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(35), spacing=dp_scaled(2))
        self.area.add_widget(self.filter_menu)

        self.table = CSVTableView()
        self.graph = CSVGraphView()

        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(52), spacing=dp_scaled(8), padding=[dp_scaled(8), dp_scaled(6)])
        
        btn_open = Button(text="📁 Datei", size_hint=(None, 1), width=dp_scaled(100), background_color=(0.2, 0.25, 0.35, 1))
        btn_open.bind(on_release=self._open_file)
        bottom.add_widget(btn_open)

        self.btn_tab_table = Button(text="Tabelle", background_color=(0.2, 0.3, 0.7, 1))
        self.btn_tab_table.bind(on_release=lambda *_: self._switch_tab("Table"))
        bottom.add_widget(self.btn_tab_table)

        self.btn_tab_graph = Button(text="Graph", background_color=(0.12, 0.12, 0.18, 1))
        self.btn_tab_graph.bind(on_release=lambda *_: self._switch_tab("Graph"))
        bottom.add_widget(self.btn_tab_graph)

        self.btn_reset = Button(text="Reset", size_hint=(None, 1), width=dp_scaled(80), background_color=(0.35, 0.2, 0.2, 1), opacity=0, disabled=True)
        self.btn_reset.bind(on_release=lambda *_: self.graph._reset_view())
        bottom.add_widget(self.btn_reset)

        root.add_widget(bottom)
        self._build_filter_buttons()
        self._switch_tab("Table")

    def _open_file(self, *_):
        # Nur öffnen, wenn nicht bereits ein Browser angezeigt wird
        if self.file_browser and self.file_browser.parent:
            return
            
        self.file_browser = CSVViewerFileBrowser(on_select=self._file_selected)
        self.add_widget(self.file_browser)

    def _file_selected(self, path):
        self.current_csv = path
        device_names = self.graph.set_csv_path(path)
        
        self.device_menu.clear_widgets()
        self.active_devices = [] # Liste für Multi-Auswahl zurücksetzen
        self.file_browser = None # Referenz nach Auswahl optional zurücksetzen
        if device_names:
            # Wir starten standardmäßig mit dem ersten Gerät
            self.active_devices = [device_names[0]]
            
            for name in device_names:
                is_active = name in self.active_devices
                btn = Button(
                    text=name, 
                    background_normal="", 
                    # Blau wenn aktiv, Dunkel wenn inaktiv
                    background_color=(0.2, 0.4, 0.8, 1) if is_active else (0.15, 0.18, 0.25, 1)
                )
                # WICHTIG: Wir binden jetzt an die neue _toggle_device Funktion
                btn.bind(on_release=self._toggle_device)
                self.device_menu.add_widget(btn)

        self._build_filter_buttons()
        
        # Dem Graphen sagen, was er zeigen soll
        if self.active_devices:
            self.graph.select_multiple_devices(self.active_devices)
            
        self._switch_tab(self.active_tab)

    def _build_filter_buttons(self):
        self.filter_menu.clear_widgets()
        for col in self.graph.colors.keys():
            is_active = col in self.active_filters
            # Wir holen uns die Farbe direkt aus der Farbtabelle des Graphen
            c = self.graph.colors.get(col, (0.5, 0.5, 0.5, 1))
            
            btn = Button(
                text=col,
                background_normal="",
                # Wenn aktiv: Kurvenfarbe | Wenn inaktiv: Dunkelgrau
                background_color=(c[0], c[1], c[2], 1) if is_active else (0.15, 0.15, 0.15, 1),
                color=(1, 1, 1, 1) if is_active else (0.6, 0.6, 0.6, 1),
                font_size=sp_scaled(16),
                bold=is_active
            )
            btn.bind(on_release=lambda b, c=col: self._toggle_filter(c))
            self.filter_menu.add_widget(btn)

    def _toggle_device(self, btn):
        name = btn.text
        if name in self.active_devices:
            # Nur entfernen, wenn es nicht das letzte aktive Gerät ist
            if len(self.active_devices) > 1:
                self.active_devices.remove(name)
                btn.background_color = (0.15, 0.18, 0.25, 1) # Dunkel
        else:
            self.active_devices.append(name)
            btn.background_color = (0.2, 0.4, 0.8, 1) # Blau
        
        # Graph mit der kompletten Liste aktualisieren
        self.graph.select_multiple_devices(self.active_devices)

    def _switch_tab(self, name):
        self.active_tab = name
        for child in list(self.area.children):
            if child not in [self.device_menu, self.filter_menu]:
                self.area.remove_widget(child)

        if name == "Table":
            self.btn_tab_table.background_color = (0.2, 0.3, 0.7, 1)
            self.btn_tab_graph.background_color = (0.12, 0.12, 0.18, 1)
            self.btn_reset.opacity = 0
            self.btn_reset.disabled = True
            self.area.add_widget(self.table)
            if self.current_csv: self.table.set_csv_path(self.current_csv)
        else:
            self.btn_tab_graph.background_color = (0.2, 0.3, 0.7, 1)
            self.btn_tab_table.background_color = (0.12, 0.12, 0.18, 1)
            self.btn_reset.opacity = 1
            self.btn_reset.disabled = False
            self.area.add_widget(self.graph)
            
            # WICHTIG: Wir nutzen jetzt NUR NOCH select_multiple_devices
            if self.current_csv and self.graph.all_data_by_device:
                if not self.active_devices:
                    names = sorted(list(self.graph.all_data_by_device.keys()))
                    if names: self.active_devices = [names[0]]
                
                if self.active_devices:
                    self.graph.select_multiple_devices(self.active_devices)

    def _toggle_filter(self, col):
        if col in self.active_filters:
            # Verhindern, dass man alle Filter abwählt (mind. einer bleibt aktiv)
            if len(self.active_filters) > 1:
                self.active_filters.remove(col)
        else:
            self.active_filters.append(col)
        
        # UI der Filter-Buttons aktualisieren
        self._build_filter_buttons()
        # Dem Graphen sagen, welche Spalten er jetzt zeichnen soll
        self.graph.set_active_plots(self.active_filters)
    def _toggle_device(self, btn):
        name = btn.text
        if name in self.active_devices:
            if len(self.active_devices) > 1:
                self.active_devices.remove(name)
                btn.background_color = (0.15, 0.18, 0.25, 1)
        else:
            self.active_devices.append(name)
            btn.background_color = (0.2, 0.4, 0.8, 1)
        
        # Jetzt sagen wir dem Graphen: Zeichne diese Liste von Geräten!
        self.graph.select_multiple_devices(self.active_devices)
    def _on_device_press(self, name):
        for btn in self.device_menu.children:
            btn.background_color = (0.2, 0.4, 0.8, 1) if btn.text == name else (0.15, 0.18, 0.25, 1)
        self.graph.select_device(name)

    def update_from_global(self, d):
        self.header.update_from_global(d)
