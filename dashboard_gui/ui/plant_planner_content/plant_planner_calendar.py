# =============================================================================
# DATE PICKER
# =============================================================================
import calendar
from datetime import date
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.buttons.glass_button import GlassButton

class DatePickerPopup(Popup):
    selected_date = StringProperty("")

    def __init__(self, callback=None, **kwargs):
        super().__init__(
            title="SELECT DATE",
            size_hint=(0.92, 0.85),
            auto_dismiss=False,
            background="",  # Entfernt Kivy-Standardtextur
            background_color=(0, 0, 0, 0.7),  # 0.7 durchscheinend schwarz
            title_align="center",
            title_size=dp_scaled(16),
            **kwargs
        )
        self.callback = callback
        
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.active_btn = None  # Tracker für den aktuell gedrückten Button

        # 1. Root-Layout
        self.root_layout = BoxLayout(
            orientation="vertical",
            padding=dp_scaled(12),
            spacing=dp_scaled(8)
        )

        # 2. Header
        self.header_box = BoxLayout(size_hint_y=None, height=dp_scaled(46), spacing=dp_scaled(10))
        self.prev_btn = GlassButton(text="<", size_hint_x=0.2)
        self.prev_btn.bind(on_release=self._prev_month)
        self.month_label = Label(text="", font_size=sp_scaled(16), bold=True, size_hint_x=0.6)
        self.next_btn = GlassButton(text=">", size_hint_x=0.2)
        self.next_btn.bind(on_release=self._next_month)
        
        self.header_box.add_widget(self.prev_btn)
        self.header_box.add_widget(self.month_label)
        self.header_box.add_widget(self.next_btn)
        self.root_layout.add_widget(self.header_box)

        # 3. ScrollView mit dem Grid
        self.scroll = ScrollView()
        self.days_grid = GridLayout(cols=7, spacing=dp_scaled(4), size_hint_y=None)
        self.days_grid.bind(minimum_height=self.days_grid.setter('height'))
        self.scroll.add_widget(self.days_grid)
        self.root_layout.add_widget(self.scroll)

        # 4. Footer (mit CLEAR-Option via SAVE ohne Auswahl)
        btn_box = BoxLayout(size_hint_y=None, height=dp_scaled(46), spacing=dp_scaled(10))
        cancel_btn = GlassButton(text="CANCEL")
        save_btn = GlassButton(text="SAVE")
        
        cancel_btn.bind(on_release=lambda *_: self.dismiss())
        save_btn.bind(on_release=self._save)
        
        btn_box.add_widget(cancel_btn)
        btn_box.add_widget(save_btn)
        self.root_layout.add_widget(btn_box)

        self.content = self.root_layout
        self._update_calendar_view()

    def _update_calendar_view(self):
        """Generiert das Tage-Grid basierend auf current_month & current_year neu."""
        self.days_grid.clear_widgets()
        self.active_btn = None

        month_name = calendar.month_name[self.current_month].upper()
        self.month_label.text = f"{month_name} {self.current_year}"

        # Wochentage
        for day_name in ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]:
            self.days_grid.add_widget(Label(
                text=day_name, 
                size_hint_y=None, 
                height=dp_scaled(24),
                font_size=sp_scaled(12),
                color=(0.5, 0.8, 0.5, 1)  # Akzentgrün für Wochentage, passt zum Pflanzendesign
            ))

        first_weekday, num_days = calendar.monthrange(self.current_year, self.current_month)
        
        total_cells = first_weekday + num_days
        rows = (total_cells // 7) + (1 if total_cells % 7 != 0 else 0) + 1
        self.days_grid.height = rows * dp_scaled(42)

        # Leere Plätze vor dem Ersten des Monats
        for _ in range(first_weekday):
            self.days_grid.add_widget(Label(size_hint_y=None, height=dp_scaled(38)))

        # Buttons für die echten Tage generieren
        for d in range(1, num_days + 1):
            btn = ToggleButton(
                text=str(d),
                group="date_picker",
                size_hint_y=None,
                height=dp_scaled(38),
                background_normal="",  # Flaches Design ohne Standard-Kivy-Grau
                background_down="",  # Flaches Design im gedrückten Zustand
                background_color=(1, 1, 1, 0.05),  # Leicht durchscheinend im Normalzustand
                color=(1, 1, 1, 1),
                font_size=sp_scaled(14)
            )
            
            # Falls das aktuell ausgewählte Datum auf diesen Tag fällt, visuell selektieren
            current_check = f"{self.current_year}-{self.current_month:02d}-{d:02d}"
            if self.selected_date == current_check:
                btn.state = "down"
                btn.background_color = (0.18, 0.49, 0.28, 0.8) # Sanftes Aktiv-Grün
                self.active_btn = btn

            btn.bind(on_release=self._select_day)
            self.days_grid.add_widget(btn)

    def _prev_month(self, *_):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._update_calendar_view()

    def _next_month(self, *_):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._update_calendar_view()

    def _select_day(self, btn):
        # Wenn der Button im "normal"-Zustand ist, wurde er ABGEWÄHLT
        if btn.state == "normal":
            self.selected_date = ""
            btn.background_color = (1, 1, 1, 0.05)  # Zurück auf Standard-Transluzent
            self.active_btn = None
        else:
            # Falls ein anderer Button aktiv war, dessen Farbe zurücksetzen (Kivy Group-Workaround)
            if self.active_btn and self.active_btn != btn:
                self.active_btn.background_color = (1, 1, 1, 0.05)
            
            self.selected_date = f"{self.current_year}-{self.current_month:02d}-{int(btn.text):02d}"
            btn.background_color = (0.18, 0.49, 0.28, 0.8)  # Schickes Dashboard-Grün für Selektion
            self.active_btn = btn

    def _save(self, *_):
        # Übergibt entweder das Datum oder einen leeren String zum Abwählen im Editor
        if self.callback is not None:
            # Falls kein Datum gewählt ist, übergeben wir "SET DATE" für den Button-Text
            self.callback(self.selected_date if self.selected_date else "SET DATE")
        self.dismiss()