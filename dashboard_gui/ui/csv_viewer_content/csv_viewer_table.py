# csv_viewer_table.py — SIMPLE CLEAN TERMINAL VIEWER
import os
import csv
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from dashboard_gui.ui.scaling_utils import dp_scaled


class CSVTableView(BoxLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"

        scroll = ScrollView(size_hint=(1, 1))
        self.add_widget(scroll)

        self.text_area = TextInput(
            readonly=True,
            size_hint=(1, None),
            height=dp_scaled(4000),
            font_size=14,
            background_color=(0.07, 0.07, 0.1, 1),
            foreground_color=(0.95, 0.95, 0.95, 1),
            cursor_blink=False,
        )
        scroll.add_widget(self.text_area)

        self.csv_path = None


    # ----------------------------------------------------
    # EXTERN SETZEN
    # ----------------------------------------------------
    def set_csv_path(self, p):
        self.csv_path = p
        self._reload()


    # ----------------------------------------------------
    # CSV → einfacher eingerückter Text
    # ----------------------------------------------------
    def _reload(self):
        if not self.csv_path or not os.path.exists(self.csv_path):
            self.text_area.text = f"File not found:\n{self.csv_path}"
            return

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        except Exception as e:
            self.text_area.text = f"Fehler beim Lesen:\n{e}"
            return

        if not rows:
            self.text_area.text = "CSV ist leer."
            return

        # Spaltennamen
        headers = list(rows[0].keys())

        # Output buffer
        lines = []

        # Kopfzeile
        header_line = " | ".join(headers)
        lines.append(header_line)
        lines.append("-" * len(header_line))

        # Zeilen
        for row in rows:
            parts = []
            for h in headers:
                # Wert holen, None → ""
                v = row.get(h, "") or ""
                parts.append(v)

            # Spalten durch Abstände trennen (einfach, sauber)
            line = " | ".join(parts)
            lines.append(line)

        # Ausgabe
        self.text_area.text = "\n".join(lines)
