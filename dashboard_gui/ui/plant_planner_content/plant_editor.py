# dashboard_gui/ui/plant_planner_content/plant_editor.py

import copy
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.plant_planner_content.plant_planner_calendar import DatePickerPopup
from dashboard_gui.ui.scaling_utils import dp_scaled

ASSET_ROOT = os.path.join("dashboard_gui", "assets")

class PlantEditorPopup(Popup):
    def __init__(self, plant=None, on_save=None, **kwargs):
        super().__init__(
            title="PLANT EDITOR", 
            size_hint=(0.95, 0.95), 
            auto_dismiss=False,
            background="",  
            background_color=(0, 0, 0, 0.7),  
            title_align="center",
            title_size=dp_scaled(16),
            **kwargs
        )
        self.on_save = on_save
        self.is_new = plant is None
        self.original_plant = plant

        if self.is_new:
            plant = {
                "name": "", "strain": "", "breeder": "", "phenotype": "",
                "pot_size": "", "medium": "", "light": "", "location": "",
                "notes": "", "tags": "", "harvest_weight": "", "dry_weight": "",
                "favorite": False, "picture": 1, "harvest_date": "", "estimated_veg_days": "", "estimated_flower_days": ""
            }
            for phase in ["germination", "seedling", "vegetative", "flowering", "drying", "curing"]:
                plant[f"{phase}_start"] = ""

        self.current_plant = copy.deepcopy(plant)
        self._normalize_picture()

        # Haupt-Container (Vertikal für Inhalt + untere Buttons)
        root = BoxLayout(orientation="vertical", spacing=dp_scaled(8), padding=dp_scaled(12))
        
        # Das zweispaltige Haupt-Layout (BoxLayout statt GridLayout, da ScrollViews die Spalten bilden)
        horizontal_layout = BoxLayout(orientation="horizontal", spacing=dp_scaled(14))

        # --- LINKE SPALTE (Unabhängiger ScrollView) ---
        scroll_left = ScrollView(size_hint_x=0.5)
        left_column = BoxLayout(orientation="vertical", spacing=dp_scaled(6), size_hint_y=None)
        left_column.bind(minimum_height=left_column.setter("height"))

        # Alle Textfelder (Stammdaten) links rendern
        fields = [
            ("NAME", "name"), ("STRAIN", "strain"), ("BREEDER", "breeder"),
            ("PHENOTYPE", "phenotype"), ("POT SIZE", "pot_size"), ("MEDIUM", "medium"),
            ("LIGHT", "light"), ("LOCATION", "location"), ("HARVEST WEIGHT", "harvest_weight"),
            ("DRY WEIGHT", "dry_weight"), ("TAGS", "tags"), ("ESTIMATED VEG DAYS", "estimated_veg_days"), ("ESTIMATED FLOWER DAYS", "estimated_flower_days")
        ]

        for label, key in fields:
            box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(58))
            box.add_widget(Label(text=label, size_hint_y=None, height=dp_scaled(18), color=(0.7, 0.7, 0.7, 1), font_size=dp_scaled(11)))

            ti = TextInput(
                text=str(self.current_plant.get(key, "")),
                multiline=False,
                background_color=(1, 1, 1, 0.05),
                foreground_color=(1, 1, 1, 1),
                padding=[dp_scaled(6), dp_scaled(6)],
                font_size=dp_scaled(13)
            )
            ti.bind(text=lambda inst, val, k=key: self.current_plant.update({k: val}))
            box.add_widget(ti)
            left_column.add_widget(box)

        scroll_left.add_widget(left_column)
        horizontal_layout.add_widget(scroll_left)


        # --- RECHTE SPALTE (Unabhängiger ScrollView) ---
        scroll_right = ScrollView(size_hint_x=0.5)
        right_column = BoxLayout(orientation="vertical", spacing=dp_scaled(8), size_hint_y=None)
        right_column.bind(minimum_height=right_column.setter("height"))

        # 1. Bild-Auswahl
        self._add_picture_selector(right_column)

        # 2. Wachstumsphasen
        phases_container = BoxLayout(orientation="vertical", spacing=dp_scaled(4), size_hint_y=None)
        phases_container.bind(minimum_height=phases_container.setter("height"))
        phases_container.add_widget(Label(text="GROW PHASES", size_hint_y=None, height=dp_scaled(20), color=(0.5, 0.8, 0.5, 1), font_size=dp_scaled(13)))

        phases_grid = GridLayout(cols=2, spacing=dp_scaled(6), size_hint_y=None)
        phases_grid.bind(minimum_height=phases_grid.setter("height"))

        for phase in ["germination", "seedling", "vegetative", "flowering", "drying", "curing"]:
            phase_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(46), spacing=dp_scaled(2))
            phase_box.add_widget(Label(text=phase.upper(), size_hint_y=None, height=dp_scaled(14), font_size=dp_scaled(10), color=(0.6, 0.6, 0.6, 1)))
            
            btn = GlassButton(text=self.current_plant.get(f"{phase}_start", "SET DATE"), font_size=dp_scaled(11))

            def set_date(date_str, ph=phase, b=btn):
                self.current_plant[f"{ph}_start"] = date_str
                b.text = date_str

            btn.bind(on_release=lambda *_, cb=set_date: DatePickerPopup(callback=cb).open())
            phase_box.add_widget(btn)
            phases_grid.add_widget(phase_box)

        phases_container.add_widget(phases_grid)
        right_column.add_widget(phases_container)

        # 3. Notizfeld
        notes_box = BoxLayout(orientation="vertical", spacing=dp_scaled(2), size_hint_y=None, height=dp_scaled(110))
        notes_box.add_widget(Label(text="NOTES", size_hint_y=None, height=dp_scaled(16), color=(0.7, 0.7, 0.7, 1), font_size=dp_scaled(11)))
        
        self.notes_input = TextInput(
            text=self.current_plant.get("notes", ""),
            multiline=True,
            background_color=(1, 1, 1, 0.05),
            foreground_color=(1, 1, 1, 1),
            padding=[dp_scaled(6), dp_scaled(6)],
            font_size=dp_scaled(12)
        )
        notes_box.add_widget(self.notes_input)
        right_column.add_widget(notes_box)

        scroll_right.add_widget(right_column)
        horizontal_layout.add_widget(scroll_right)

        # Das zweispaltige Layout dem Haupt-Container hinzufügen
        root.add_widget(horizontal_layout)

        # Action Buttons (unten fixiert)
        actions = BoxLayout(size_hint_y=None, height=dp_scaled(44), spacing=dp_scaled(10))
        cancel_btn = GlassButton(text="CANCEL")
        save_btn = GlassButton(text="SAVE")

        cancel_btn.bind(on_release=lambda *_: self.dismiss())
        save_btn.bind(on_release=lambda *_: self._internal_save())

        actions.add_widget(cancel_btn)
        actions.add_widget(save_btn)
        root.add_widget(actions)

        self.content = root

    def _normalize_picture(self):
        try:
            picture = int(self.current_plant.get("picture", 1))
        except (TypeError, ValueError):
            picture = 1

        picture = max(1, min(10, picture))
        self.current_plant["picture"] = picture
        return picture

    def _get_picture_asset(self, picture):
        return os.path.join("dashboard_gui", "assets", "plant_pics", f"plant{int(picture):02d}.png")

    def _update_preview(self):
        picture = self._normalize_picture()
        self.preview_image.source = self._get_picture_asset(picture)
        self.preview_label.text = f"Plant {picture:02d}"

    def _add_picture_selector(self, target_container):
        # Extrem komprimierter Bildwähler für die rechte Spalte
        image_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(110), spacing=dp_scaled(2))
        image_box.add_widget(Label(text="IMAGE", size_hint_y=None, height=dp_scaled(16), color=(0.7, 0.7, 0.7, 1), font_size=dp_scaled(11)))

        row = BoxLayout(size_hint_y=None, height=dp_scaled(76), spacing=dp_scaled(8))
        prev_btn = GlassButton(text="<", size_hint_x=0.15)
        self.preview_image = Image(
            source=self._get_picture_asset(self._normalize_picture()),
            size_hint_x=0.7,
            allow_stretch=True,
            keep_ratio=True,
        )
        next_btn = GlassButton(text=">", size_hint_x=0.15)
        row.add_widget(prev_btn)
        row.add_widget(self.preview_image)
        row.add_widget(next_btn)

        self.preview_label = Label(text="Plant 01", size_hint_y=None, height=dp_scaled(14), color=(1, 1, 1, 1), font_size=dp_scaled(10))

        def change_picture(delta):
            picture = self._normalize_picture() + delta
            picture = max(1, min(10, picture))
            self.current_plant["picture"] = picture
            self._update_preview()

        prev_btn.bind(on_release=lambda *_: change_picture(-1))
        next_btn.bind(on_release=lambda *_: change_picture(1))

        image_box.add_widget(row)
        image_box.add_widget(self.preview_label)
        target_container.add_widget(image_box)

    def _internal_save(self):
        self.notes_input.text = self.notes_input.text.strip()
        self.current_plant["notes"] = self.notes_input.text
        self._normalize_picture()

        if self.on_save:
            self.on_save(self.current_plant, self.is_new, self.original_plant)

        self.dismiss()