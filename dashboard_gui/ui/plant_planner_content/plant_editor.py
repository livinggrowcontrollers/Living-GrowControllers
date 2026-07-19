import copy
import os
import re

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.plant_planner_content.plant_planner_calendar import DatePickerPopup
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


ESTIMATED_DAY_DEFAULTS = {
    "estimated_veg_days": 30,
    "estimated_flower_days": 60,
}
MAX_ESTIMATED_DAYS = 3650
ASSET_ROOT = os.path.join("dashboard_gui", "assets")


class _EditorCard(BoxLayout):
    """Touchfreundliche, optisch eigenstaendige Editor-Kachel."""

    def __init__(self, accent=(0.18, 0.95, 0.45, 1), **kwargs):
        kwargs.setdefault("padding", [dp_scaled(14), dp_scaled(10)])
        kwargs.setdefault("spacing", dp_scaled(8))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.035, 0.045, 0.065, 0.96)
            self._bg = RoundedRectangle(radius=[dp_scaled(14)])
            Color(accent[0], accent[1], accent[2], 0.48)
            self._border = Line(
                rounded_rectangle=(0, 0, 0, 0, dp_scaled(14)),
                width=dp_scaled(1.1),
            )
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

    def _sync_canvas(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp_scaled(14),
        )


class PlantEditorPopup(Popup):
    def __init__(self, plant=None, on_save=None, **kwargs):
        super().__init__(
            title="PLANT EDITOR",
            size_hint=(0.97, 0.97),
            auto_dismiss=False,
            background="",
            background_color=(0.005, 0.008, 0.015, 0.97),
            title_align="center",
            title_size=sp_scaled(20),
            separator_color=(0.15, 0.95, 0.42, 0.75),
            **kwargs,
        )
        self.on_save = on_save
        self.is_new = plant is None
        self.original_plant = plant
        self._measurement_inputs = {}

        if self.is_new:
            plant = {
                "name": "",
                "strain": "",
                "breeder": "",
                "phenotype": "",
                "pot_size": "",
                "medium": "",
                "light": "",
                "location": "",
                "notes": "",
                "tags": "",
                "harvest_weight": "",
                "dry_weight": "",
                "favorite": False,
                "picture": 1,
                "harvest_date": "",
                "estimated_veg_days": 30,
                "estimated_flower_days": 60,
            }
            for phase in (
                "germination",
                "seedling",
                "vegetative",
                "flowering",
                "drying",
                "curing",
            ):
                plant[f"{phase}_start"] = ""

        self.current_plant = copy.deepcopy(plant)
        self._normalize_picture()

        root = BoxLayout(
            orientation="vertical",
            spacing=dp_scaled(10),
            padding=[dp_scaled(12), dp_scaled(8), dp_scaled(12), dp_scaled(12)],
        )

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp_scaled(5),
            scroll_type=["bars", "content"],
        )
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp_scaled(10),
            padding=[dp_scaled(3), dp_scaled(4), dp_scaled(3), dp_scaled(14)],
        )
        content.bind(minimum_height=content.setter("height"))

        self._add_section_title(content, "PLANT IMAGE", "Choose a visual")
        self._add_picture_selector(content)

        self._add_section_title(content, "PLANT PROFILE", "Basic information")
        self.profile_grid = GridLayout(
            cols=4,
            size_hint_y=None,
            spacing=dp_scaled(10),
        )
        self.profile_grid.bind(
            minimum_height=self.profile_grid.setter("height")
        )
        for label, key, hint in (
            ("NAME", "name", "Plant name"),
            ("STRAIN", "strain", "Strain or cultivar"),
            ("BREEDER", "breeder", "Breeder"),
            ("PHENOTYPE", "phenotype", "Phenotype"),
            ("MEDIUM", "medium", "Soil, coco, hydro ..."),
            ("LIGHT", "light", "Light or position"),
            ("LOCATION", "location", "Tent, room or zone"),
            ("TAGS", "tags", "Tags"),
        ):
            self._add_text_card(self.profile_grid, label, key, hint)
        content.add_widget(self.profile_grid)

        self._add_section_title(content, "VALUES", "Tap arrows or enter a value")
        self._add_stepper_card(content, "POT VOLUME", "pot_size", 0.1, "L", decimals=1)
        self._add_stepper_card(content, "HARVEST WEIGHT", "harvest_weight", 0.1, "g", decimals=1)
        self._add_stepper_card(content, "DRY WEIGHT", "dry_weight", 0.1, "g", decimals=1)
        self._add_stepper_card(
            content,
            "ESTIMATED VEGETATION",
            "estimated_veg_days",
            1,
            "days",
            decimals=0,
            minimum=1,
            maximum=MAX_ESTIMATED_DAYS,
        )
        self._add_stepper_card(
            content,
            "ESTIMATED FLOWERING",
            "estimated_flower_days",
            1,
            "days",
            decimals=0,
            minimum=1,
            maximum=MAX_ESTIMATED_DAYS,
        )

        self._add_section_title(content, "GROW PHASES", "Tap a tile to set the date")
        self._add_phase_tiles(content)

        self._add_section_title(content, "NOTES", "Everything worth remembering")
        self._add_notes_card(content)

        scroll.add_widget(content)
        root.add_widget(scroll)
        root.add_widget(self._build_actions())
        self.content = root

    # ------------------------------------------------------------------
    # TILE BUILDERS
    # ------------------------------------------------------------------

    def _add_section_title(self, target, title, subtitle):
        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(50),
            padding=[dp_scaled(6), dp_scaled(5)],
        )
        title_label = Label(
            text=f"[b]{title}[/b]",
            markup=True,
            halign="left",
            valign="bottom",
            color=(0.2, 1, 0.48, 1),
            font_size=sp_scaled(18),
        )
        subtitle_label = Label(
            text=subtitle,
            halign="left",
            valign="top",
            color=(0.55, 0.62, 0.68, 1),
            font_size=sp_scaled(12),
        )
        for label in (title_label, subtitle_label):
            label.bind(size=lambda inst, value: setattr(inst, "text_size", value))
            header.add_widget(label)
        target.add_widget(header)

    @staticmethod
    def _style_input(widget):
        widget.background_normal = ""
        widget.background_active = ""
        widget.background_color = (0.08, 0.1, 0.14, 1)
        widget.foreground_color = (1, 1, 1, 1)
        widget.cursor_color = (0.2, 1, 0.48, 1)
        widget.hint_text_color = (0.42, 0.48, 0.54, 1)
        widget.padding = [dp_scaled(12), dp_scaled(11)]

    def _add_text_card(self, target, label, key, hint):
        card = _EditorCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(107),
        )
        field_label = Label(
            text=label,
            size_hint_y=None,
            height=dp_scaled(20),
            halign="left",
            valign="middle",
            color=(0.62, 0.7, 0.76, 1),
            font_size=sp_scaled(11),
        )
        field_label.bind(
            size=lambda instance, value: setattr(instance, "text_size", value)
        )
        card.add_widget(field_label)
        field = TextInput(
            text=str(self.current_plant.get(key, "")),
            hint_text=hint,
            multiline=False,
            font_size=sp_scaled(14),
        )
        self._style_input(field)
        field.bind(text=lambda _inst, value, field_key=key: self.current_plant.update({field_key: value}))
        card.add_widget(field)
        target.add_widget(card)

    def _add_stepper_card(
        self,
        target,
        label,
        key,
        step,
        unit,
        decimals,
        minimum=0,
        maximum=65535,
    ):
        card = _EditorCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(112),
            accent=(0.15, 0.75, 1, 1),
        )
        card.add_widget(Label(
            text=label,
            size_hint_y=None,
            height=dp_scaled(22),
            halign="left",
            valign="middle",
            color=(0.62, 0.76, 0.84, 1),
            font_size=sp_scaled(13),
            text_size=(dp_scaled(1000), None),
        ))

        row = BoxLayout(spacing=dp_scaled(10))
        minus = GlassButton(
            text="[b]−[/b]",
            size_hint_x=None,
            width=dp_scaled(70),
            font_size=sp_scaled(28),
        )
        plus = GlassButton(
            text="[b]+[/b]",
            size_hint_x=None,
            width=dp_scaled(70),
            font_size=sp_scaled(28),
        )
        value_box = BoxLayout(spacing=dp_scaled(6))
        value_input = TextInput(
            text=self._display_numeric_value(key, decimals),
            multiline=False,
            input_filter="int" if decimals == 0 else "float",
            halign="center",
            font_size=sp_scaled(24),
        )
        self._style_input(value_input)
        unit_label = Label(
            text=unit,
            size_hint_x=None,
            width=dp_scaled(56),
            color=(0.55, 0.72, 0.8, 1),
            font_size=sp_scaled(15),
        )
        value_box.add_widget(value_input)
        value_box.add_widget(unit_label)

        def store_value(_instance, value):
            self.current_plant[key] = value

        def change_value(delta):
            current = self._parse_number(value_input.text, minimum)
            value = max(minimum, min(maximum, current + delta))
            value_input.text = self._format_number(value, decimals)

        value_input.bind(text=store_value)
        minus.bind(on_release=lambda *_: change_value(-step))
        plus.bind(on_release=lambda *_: change_value(step))
        self._measurement_inputs[key] = (value_input, decimals, minimum, maximum)

        row.add_widget(minus)
        row.add_widget(value_box)
        row.add_widget(plus)
        card.add_widget(row)
        target.add_widget(card)

    def _add_picture_selector(self, target):
        card = _EditorCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(150),
            accent=(0.85, 0.4, 1, 1),
        )
        previous = GlassButton(
            text="[b]‹[/b]",
            size_hint_x=None,
            width=dp_scaled(76),
            font_size=sp_scaled(34),
        )
        next_button = GlassButton(
            text="[b]›[/b]",
            size_hint_x=None,
            width=dp_scaled(76),
            font_size=sp_scaled(34),
        )
        preview = BoxLayout(orientation="vertical", spacing=dp_scaled(3))
        self.preview_image = Image(
            source=self._get_picture_asset(self._normalize_picture()),
            fit_mode="contain",
        )
        self.preview_label = Label(
            text=f"PLANT {self._normalize_picture():02d}",
            size_hint_y=None,
            height=dp_scaled(24),
            color=(0.9, 0.75, 1, 1),
            font_size=sp_scaled(15),
        )
        preview.add_widget(self.preview_image)
        preview.add_widget(self.preview_label)

        previous.bind(on_release=lambda *_: self._change_picture(-1))
        next_button.bind(on_release=lambda *_: self._change_picture(1))
        card.add_widget(previous)
        card.add_widget(preview)
        card.add_widget(next_button)
        target.add_widget(card)

    def _add_phase_tiles(self, target):
        grid = GridLayout(
            cols=4,
            size_hint_y=None,
            spacing=dp_scaled(10),
        )
        grid.bind(minimum_height=grid.setter("height"))

        for phase in (
            "germination",
            "seedling",
            "vegetative",
            "flowering",
            "drying",
            "curing",
        ):
            card = _EditorCard(
                orientation="vertical",
                size_hint_y=None,
                height=dp_scaled(100),
                accent=(1, 0.62, 0.18, 1),
            )
            card.add_widget(Label(
                text=phase.upper(),
                size_hint_y=None,
                height=dp_scaled(24),
                color=(0.82, 0.7, 0.5, 1),
                font_size=sp_scaled(12),
            ))
            date_key = f"{phase}_start"
            current_date = self.current_plant.get(date_key, "")
            button = GlassButton(
                text=current_date or "SET DATE",
                font_size=sp_scaled(16),
            )

            def open_picker(_button, phase_key=date_key, target_button=button):
                def set_date(date_string):
                    self.current_plant[phase_key] = date_string
                    target_button.text = date_string or "SET DATE"

                DatePickerPopup(callback=set_date).open()

            button.bind(on_release=open_picker)
            card.add_widget(button)
            grid.add_widget(card)
        target.add_widget(grid)

    def _add_notes_card(self, target):
        card = _EditorCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp_scaled(190),
        )
        self.notes_input = TextInput(
            text=str(self.current_plant.get("notes", "")),
            hint_text="Notes, observations, reminders ...",
            multiline=True,
            font_size=sp_scaled(16),
        )
        self._style_input(self.notes_input)
        card.add_widget(self.notes_input)
        target.add_widget(card)

    def _build_actions(self):
        actions = BoxLayout(
            size_hint_y=None,
            height=dp_scaled(45),
            spacing=dp_scaled(12),
        )
        cancel = GlassButton(text="CANCEL", font_size=sp_scaled(17))
        save = GlassButton(text="[b]SAVE PLANT[/b]", font_size=sp_scaled(18))
        save.background_color = (0.06, 0.42, 0.2, 0.82)
        cancel.bind(on_release=lambda *_: self.dismiss())
        save.bind(on_release=lambda *_: self._internal_save())
        actions.add_widget(cancel)
        actions.add_widget(save)
        return actions

    # ------------------------------------------------------------------
    # VALUE NORMALIZATION
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_number(value, fallback=0):
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
        if not match:
            return float(fallback)
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return float(fallback)

    @staticmethod
    def _format_number(value, decimals):
        if decimals == 0:
            return str(int(round(value)))
        return f"{value:.{decimals}f}"

    def _display_numeric_value(self, key, decimals):
        raw = self.current_plant.get(key, "")
        if raw in (None, ""):
            return ""
        return self._format_number(self._parse_number(raw), decimals)

    def _normalize_measurements(self):
        for key in ("pot_size", "harvest_weight", "dry_weight"):
            field, decimals, minimum, maximum = self._measurement_inputs[key]
            if not field.text.strip():
                self.current_plant[key] = ""
                continue
            value = max(minimum, min(maximum, self._parse_number(field.text)))
            self.current_plant[key] = self._format_number(value, decimals)

    def _normalize_estimated_days(self):
        for key, default in ESTIMATED_DAY_DEFAULTS.items():
            fallback = default
            if isinstance(self.original_plant, dict):
                try:
                    fallback = int(self.original_plant.get(key, default))
                except (TypeError, ValueError):
                    fallback = default

            field = self._measurement_inputs.get(key)
            raw = field[0].text if field else self.current_plant.get(key, fallback)
            try:
                value = int(round(self._parse_number(raw, fallback)))
            except (TypeError, ValueError):
                value = fallback
            self.current_plant[key] = max(1, min(MAX_ESTIMATED_DAYS, value))

    def _normalize_picture(self):
        try:
            picture = int(self.current_plant.get("picture", 1))
        except (TypeError, ValueError):
            picture = 1
        picture = max(1, min(10, picture))
        self.current_plant["picture"] = picture
        return picture

    def _get_picture_asset(self, picture):
        return os.path.join(
            ASSET_ROOT,
            "plant_pics",
            f"plant{int(picture):02d}.png",
        )

    def _change_picture(self, delta):
        picture = max(1, min(10, self._normalize_picture() + delta))
        self.current_plant["picture"] = picture
        self.preview_image.source = self._get_picture_asset(picture)
        self.preview_label.text = f"PLANT {picture:02d}"

    def _internal_save(self):
        self.current_plant["notes"] = self.notes_input.text.strip()
        self._normalize_picture()
        self._normalize_measurements()
        self._normalize_estimated_days()

        if self.on_save:
            self.on_save(self.current_plant, self.is_new, self.original_plant)
        self.dismiss()
