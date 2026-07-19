# dashboard_gui/ui/plant_planner_content/plant_card.py

import os
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.plant_planner_content import plant_logic
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.grow_overview_content.segmented_progress_bar import SegmentedProgressBar
ASSET_ROOT = os.path.join("dashboard_gui", "assets", "plant_pics")


class PlantCard(BoxLayout):

    @staticmethod
    def _normalize_picture(plant):
        try:
            picture = int(plant.get("picture", 1))
        except (TypeError, ValueError):
            picture = 1
        return max(1, min(10, picture))

    @classmethod
    def _picture_asset(cls, plant):
        picture = cls._normalize_picture(plant)
        return os.path.join(ASSET_ROOT, f"plant{picture:02d}.png")

    def __init__(
        self,
        plant,
        on_edit=None,
        on_duplicate=None,
        on_delete=None,
        on_water=None,
        on_fertilize=None,
        on_reset=None,
        **kwargs,
    ):
        # Hauptlayout bleibt vertikal, Padding leicht erhöht für edleren Look
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=dp_scaled(16),
            spacing=dp_scaled(16),
            **kwargs,
        )
        # Gesamthöhe leicht angehoben, um dem Inhalt Raum zu geben
        self.height = dp_scaled(360)

        with self.canvas.before:
            Color(0.0, 0.0, 0.0, 0.7)
            rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(
            pos=lambda *_: setattr(rect, "pos", self.pos),
            size=lambda *_: setattr(rect, "size", self.size),
        )


        progress = plant_logic.calc_grow_progress(plant)

        self.progress_bar = SegmentedProgressBar(
            size_hint_y=None,
            height=dp_scaled(10),
            value=progress,
            max=100
        )

        self.add_widget(self.progress_bar)
        
        phase = plant_logic.get_current_phase(plant)

        if phase == "flowering":
            self.progress_bar.active_color = (0.9, 0.3, 0.9, 1)
        elif phase == "vegetative":
            self.progress_bar.active_color = (0.2, 1, 0.4, 1)        
        # =====================================================================
        # OBERER BEREICH: Nimmt den restlichen flexiblen Platz ein
        # =====================================================================
        upper_box = BoxLayout(orientation="horizontal", spacing=dp_scaled(18), size_hint_y=1)

        # ================= IMAGE COLUMN =================
        self.image_column = BoxLayout(
            orientation="vertical",
            size_hint=(0.5, 1)
        )

        self.plant_image = Image(
            source=self._picture_asset(plant),
            size_hint=(1, 1),
            fit_mode="contain",
            keep_ratio=False
        )

        self.image_column.add_widget(self.plant_image)
        upper_box.add_widget(self.image_column)

        # --- 2. RECHTS: Der komplette Text-Inhalt (Verteilt Platz gleichmäßig) ---
        text_content = BoxLayout(orientation="vertical", spacing=dp_scaled(2))

        # Top Bar (Titel & Phase) - Feste Höhe ist okay, da Text einzeilig
        top = BoxLayout(size_hint_y=None, height=dp_scaled(35))
        
        title = Label(
            text=f"[b]{plant.get('name', 'Unnamed')}[/b]",
            markup=True,
            font_size=sp_scaled(22),
            halign="left",
            valign="middle",
            color=(1, 1, 1, 1),
        )
        title.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        
        phase = plant_logic.get_current_phase(plant)
        phase_lbl = Label(
            text=f"[b]{phase.upper()}[/b]",
            markup=True,
            size_hint_x=None,
            width=dp_scaled(120),
            font_size=sp_scaled(18),
            color=plant_logic.phase_color(phase),
            halign="right",
            valign="middle",
        )
        phase_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        
        top.add_widget(title)
        top.add_widget(phase_lbl)
        text_content.add_widget(top)

        # Info Grid (Bekommt ein size_hint_y statt einer fixen Höhe)
        info_grid = GridLayout(
            cols=2,
            size_hint_y=None,
            height=dp_scaled(90),
            spacing=[dp_scaled(12), dp_scaled(4)]
        )
        items = [
            ("STRAIN", plant.get("strain", "---")),
            ("BREEDER", plant.get("breeder", "---")),
            ("MEDIUM", plant.get("medium", "---")),
            ("LIGHT", plant.get("light", "---")),
        ]
        for k, v in items:
            box = BoxLayout(orientation="vertical", spacing=dp_scaled(1))
            
            k_lbl = Label(
                text=k, 
                font_size=sp_scaled(16), 
                color=(0.5, 0.5, 0.6, 1), 
                halign="left", 
                valign="middle"
            )
            k_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            
            v_lbl = Label(
                text=str(v), 
                font_size=sp_scaled(18), 
                color=(1, 1, 1, 1), 
                halign="left", 
                valign="middle"
            )
            v_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            
            box.add_widget(k_lbl)
            box.add_widget(v_lbl)
            info_grid.add_widget(box)
            
        text_content.add_widget(info_grid)

        # Zeiten / Tage (Ebenfalls flexibel via size_hint_y)
        germination_days = plant_logic.calc_phase_days(plant, "germination")
        seedling_days = plant_logic.calc_phase_days(plant, "seedling")
        veg_days = plant_logic.calc_phase_days(plant, "vegetative")
        flower_days = plant_logic.calc_phase_days(plant, "flowering")
        total_days = plant_logic.calc_total_days(plant)
        combined_veg_days = germination_days + seedling_days + veg_days

        metrics_box = BoxLayout(orientation="horizontal", size_hint_y=0.8, spacing=dp_scaled(8))
        
        metrics_data = [
            ("VEG DAYS", f"{combined_veg_days} Days"),
            ("FLOWER DAYS", f"{flower_days} Days"),
            ("TOTAL DAYS", f"{total_days} Days")
        ]

        for label_text, value_text in metrics_data:
            m_col = BoxLayout(orientation="vertical", spacing=dp_scaled(2))
            
            m_lbl = Label(
                text=label_text, 
                font_size=sp_scaled(16), 
                color=(0.5, 0.5, 0.5, 1), 
                halign="center", 
                valign="middle"
            )
            m_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            
            m_val = Label(
                text=f"[b]{value_text}[/b]", 
                markup=True, 
                font_size=sp_scaled(18), 
                color=(0.2, 1, 0.4, 1), 
                halign="center", 
                valign="middle"
            )
            m_val.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            
            m_col.add_widget(m_lbl)
            m_col.add_widget(m_val)
            metrics_box.add_widget(m_col)

        text_content.add_widget(metrics_box)

        # Quick Actions (Baut sich sauber auf, Höhe leicht erhöht für Touch-Targets)
        quick_actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp_scaled(65),
            spacing=dp_scaled(8),
        )

        for icon, label_text, field_key, callback in [
            ("\uf043", "WATER", "last_watered", on_water),
            ("\uf4d8", "FERTILIZE", "last_fertilized", on_fertilize),
        ]:
            action_col = BoxLayout(
                orientation="vertical",
                spacing=dp_scaled(3),
            )

            action_btn = GlassButton(
                text=f"[font=FA]{icon}[/font]  {label_text}"
            )

            if callback:
                action_btn.bind(
                    on_release=lambda *_,
                    cb=callback,
                    plant_ref=plant: cb(plant_ref)
                )

            status_lbl = Label(
                text=plant_logic.format_relative_timestamp(
                    plant.get(field_key, 0)
                ),
                markup=True,
                font_size=sp_scaled(15),
                bold=True,
                color=(0.7, 0.8, 0.8, 1),
                halign="center",
                valign="middle",
            )
            status_lbl.bind(
                size=lambda inst, val: setattr(inst, "text_size", val)
            )

            action_col.add_widget(action_btn)
            action_col.add_widget(status_lbl)
            quick_actions.add_widget(action_col)

        # Reset Button Spalte
        reset_col = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=dp_scaled(55),
            spacing=dp_scaled(3)
        )
        
        reset_btn = GlassButton(
            text="[font=FA]\uf2f1[/font]"
        )
        reset_btn.color = (0.9, 0.4, 0.4, 1)
        
        if on_reset:
            reset_btn.bind(on_release=lambda *_: on_reset(plant))
            
        reset_lbl = Label(
            text="RESET",
            font_size=sp_scaled(14),
            color=(0.5, 0.5, 0.5, 1),
            halign="center",
            valign="middle"
        )
        reset_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        
        reset_col.add_widget(reset_btn)
        reset_col.add_widget(reset_lbl)
        quick_actions.add_widget(reset_col)

        text_content.add_widget(quick_actions)
        upper_box.add_widget(text_content)
        self.add_widget(upper_box)

        # =====================================================================
        # UNTERER BEREICH: Die globalen Buttons (Bleiben unten fixiert)
        # =====================================================================
        btn_box = BoxLayout(
            size_hint_y=None, height=dp_scaled(40), spacing=dp_scaled(8)
        )

        edit_btn = GlassButton(text="EDIT")
        dup_btn = GlassButton(text="DUPLICATE")
        del_btn = GlassButton(text="DELETE")
        del_btn.color = (1, 0.3, 0.3, 1)

        if on_edit:
            edit_btn.bind(on_release=lambda *_: on_edit(plant))
        if on_duplicate:
            dup_btn.bind(on_release=lambda *_: on_duplicate(plant))
        if on_delete:
            del_btn.bind(on_release=lambda *_: on_delete(plant))

        btn_box.add_widget(edit_btn)
        btn_box.add_widget(dup_btn)
        btn_box.add_widget(del_btn)

        self.add_widget(btn_box)
