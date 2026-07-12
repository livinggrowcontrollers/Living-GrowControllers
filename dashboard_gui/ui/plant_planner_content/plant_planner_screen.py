# dashboard_gui/ui/plant_planner_content/plant_planner_screen.py
# TARGET-REVISION v2.0 READY - CLEANED (NO INIT HANDSHAKE)
# ESP AUTHORITATIVE VERSION
# © 2026 Dominik Rosenthal

import copy
import os
import time
from datetime import date

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.plant_planner_content.plant_card import PlantCard
from dashboard_gui.ui.plant_planner_content.plant_editor import PlantEditorPopup
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.base_revision_system import BaseRevisionSystem
from dashboard_gui.ui.grow_controller_content.controller_command_status_popup import GrowCommandStatusPopup
ASSET_ROOT = os.path.join("dashboard_gui", "assets")


# =============================================================================
# SCREEN
# =============================================================================

class PlantPlannerScreen(Screen):

    name = "plant_planner"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GLOBAL_STATE.ui_handler.attach_screen(
            "plant_planner",
            self
        )
        self.plants = []
        self.search_text = ""

        self.engine = BaseRevisionSystem()
        self._last_sent_rev = 0               # NEU: Trackt die letzte gesendete PP-Revision
        self._pending_popup = None    
        
        self._user_active = False
        self._last_user_action = 0
        # Init-Revisions-Variablen entfernt, nur noch Tracking für normales Rev

        self._last_day = date.today()
        
        Clock.schedule_interval(
            self._check_day_rollover,
            30
        )        
        # =========================================================
        # ROOT
        # =========================================================

        self.root = BoxLayout(orientation="vertical")

        with self.root.canvas.before:
            Color(1, 1, 1, 1)
        
            self.bg_img = Rectangle(
                source=os.path.join(
                    ASSET_ROOT,
                    "background_about.png"
                ),
                pos=self.root.pos,
                size=self.root.size
            )
        
        self.root.bind(
            pos=lambda *_: setattr(self.bg_img, "pos", self.root.pos),
            size=lambda *_: setattr(self.bg_img, "size", self.root.size)
        )

        # =========================================================
        # HEADER
        # =========================================================

        self.header = HeaderBar()
        self.root.add_widget(self.header)

        # =========================================================
        # SEARCH
        # =========================================================

        topbar = BoxLayout(
            size_hint_y=None,
            height=dp_scaled(60),
            padding=[dp_scaled(15), dp_scaled(10)],
            spacing=dp_scaled(10)
        )

        self.search_input = TextInput(
            hint_text="SEARCH PLANTS...",
            multiline=False,
            background_color=(0.0, 0.0, 0.0, 0.7),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0.2, 1, 0.4, 1),
            font_size=sp_scaled(18)
        )

        self.search_input.bind(text=self._on_search)

        add_btn = GlassButton(
            text="+ NEW",
            size_hint_x=None,
            width=dp_scaled(110)
        )

        add_btn.bind(on_release=lambda *_: self.open_edit_popup())

        topbar.add_widget(self.search_input)
        topbar.add_widget(add_btn)

        self.root.add_widget(topbar)

        # =========================================================
        # SCROLL
        # =========================================================

        self.scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(4)
        )

        # HIER DIE ÄNDERUNG: cols=2 für die zweispaltige Übersicht
        self.body = GridLayout(
            cols=2,
            spacing=dp_scaled(10),
            padding=dp_scaled(12),
            size_hint_y=None
        )

        self.body.bind(
            minimum_height=self.body.setter("height")
        )

        self.scroll.add_widget(self.body)
        self.root.add_widget(self.scroll)
        self.add_widget(self.root)

        Clock.schedule_interval(
            self._check_sync_status,
            1.0
        )

    # =============================================================================
    # ENTER
    # =============================================================================
    def on_enter(self):
        """Wird aufgerufen, sobald der Screen sichtbar wird. Direktes Laden statt Handshake."""
        Clock.schedule_once(lambda *_: self._force_reload_plants(), 0.1)

    # =============================================================================
    # PUSH
    # =============================================================================

    def _push_plants_to_esp(self, plant_updates=None):
        kwargs = {"plants": self.plants}
        if plant_updates is not None:
            kwargs = {"plant_updates": plant_updates}

        new_rev = GLOBAL_STATE.send_overlay_command(
            "plant_planner",
            **kwargs
        )

        if new_rev:
            self.engine.mark_sent(new_rev)
            self._last_sent_rev = new_rev  # NEU: Speichern für den reaktiven Sync-Check
            print(f"[PlantPlanner] PUSH -> REV {new_rev}")

    def _force_reload_plants(self):
        mac = GLOBAL_STATE.get_active_device_id()
        if mac:
            data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac)
            self.update_from_global(data)

        if data:
            web_ch = data.get("webserver", {})
            server_rev = int(web_ch.get("rev_plant_planner", 0))
            self.engine.mark_confirmed_snapshot(server_rev)

    # =============================================================================
    # SEARCH
    # =============================================================================

    def _on_search(self, instance, value):
        self.search_text = value.lower().strip()
        self.build_ui()

    def _filtered_plants(self):
        """Filtert nur belegte Slots (used=True) nach Suchtext."""
        if not self.search_text:
            # Nur belegte Slots zurückgeben
            return [p for p in self.plants if p.get("used", False)]

        result = []
        for p in self.plants:
            # Ignoriere leere Slots
            if not p.get("used", False):
                continue
                
            blob = (
                str(p.get("name", "")) +
                str(p.get("strain", "")) +
                str(p.get("breeder", ""))
            ).lower()

            if self.search_text in blob:
                result.append(p)

        return result

    # =============================================================================
    # UI (OPTIMIERT: ASYNCHRONES / PROGRESSIVES LADEN)
    # =============================================================================

    def build_ui(self):
        self.body.clear_widgets()
        Clock.unschedule(self._load_cards_progressive)

        filtered = self._filtered_plants()

        if not filtered:
            empty = Label(
                text="NO PLANTS FOUND",
                size_hint_y=None,
                height=dp_scaled(120),
                font_size=sp_scaled(20),
                color=(0.7, 0.7, 0.7, 1)
            )
            self.body.add_widget(empty)
            return

        self._load_cards_progressive(filtered, 0)

    def _load_cards_progressive(self, plant_list, index, *args):
        if index >= len(plant_list):
            return

        if self.manager and self.manager.current != self.name:
            return

        plant = plant_list[index]
        card = PlantCard(
            plant=plant,
            on_edit=self.open_edit_popup,
            on_duplicate=self.duplicate_plant,
            on_delete=self.delete_plant,
            on_water=self.mark_plant_watered,
            on_fertilize=self.mark_plant_fertilized,
            on_reset=self.reset_plant_actions,  # <-- NEU hinzugefügt!
            
        )
        self.body.add_widget(card)

        Clock.schedule_once(lambda dt: self._load_cards_progressive(plant_list, index + 1), 0)

    # =============================================================================
    # EDIT
    # =============================================================================

    def open_edit_popup(self, plant=None):
        popup = PlantEditorPopup(
            plant=plant,
            on_save=self._on_popup_save
        )
        popup.open()

    def _on_popup_save(self, updated_plant, is_new, original_plant):
        """Speichert Pflanze in den entsprechenden Slot (Slot-basiert)."""
        if is_new:
            # Finde freien Slot
            slot = self._find_free_slot()
            if slot == -1:
                print("[PlantPlanner] ERROR: No free slots available!")
                return
            
            new_plant = copy.deepcopy(updated_plant)
            new_plant["slot"] = slot
            new_plant["used"] = True
            
            # Stelle sicher, dass das Array groß genug ist
            while len(self.plants) <= slot:
                self.plants.append({"used": False})
            
            self.plants[slot] = new_plant
        else:
            # Hole den Slot aus der Original-Pflanze
            original_slot = original_plant.get("slot", -1)
            if original_slot >= 0 and original_slot < len(self.plants):
                updated_copy = copy.deepcopy(updated_plant)
                updated_copy["slot"] = original_slot
                updated_copy["used"] = True
                self.plants[original_slot] = updated_copy

        if is_new:
            self._pending_popup = {
                "title": "Pflanze erstellt",
                "reset_sent": False,
            }
        else:
            self._pending_popup = {
                "title": "Pflanze gespeichert",
                "reset_sent": False,
            }

        self._push_plants_to_esp()
        self.build_ui()

    # =============================================================================
    # SAVE / DUPLICATE / DELETE
    # =============================================================================

    def _mark_plant_action(self, plant, field_name):
        """Aktualisiert einzelnes Feld (über Slot, nicht über Namen)."""
        timestamp = int(time.time())
        slot = plant.get("slot", -1)
        
        if slot >= 0 and slot < len(self.plants):
            self.plants[slot][field_name] = timestamp
        
        # Sende nur den Slot + das Feld als Update
        self._push_plants_to_esp(
            plant_updates=[{
                "slot": slot,
                field_name: timestamp,
            }]
        )
        self.build_ui()

    def mark_plant_watered(self, plant):
        self._mark_plant_action(plant, "last_watered")

    def mark_plant_fertilized(self, plant):
        self._mark_plant_action(plant, "last_fertilized")

    # =====================================================================
    # NEU: RESET ACTION LOGIK (Target-Revision v2.0 konform)
    # =====================================================================
    def reset_plant_actions(self, plant):
        """Setzt last_watered und last_fertilized für den Slot auf 0 zurück."""
        slot = plant.get("slot", -1)
        
        if slot >= 0 and slot < len(self.plants):
            self.plants[slot]["last_watered"] = 0
            self.plants[slot]["last_fertilized"] = 0
            
        self._status_popup_after_ack = True  # NEU: Zeige Popup, sobald der ESP32 die Rev spiegelt!


        self._pending_popup = {
            "title": "Werte zurückgesetzt",
            "reset_sent": False,
        }
        self._push_plants_to_esp(
            plant_updates=[{
                "slot": slot,
                "last_watered": 0,
                "last_fertilized": 0,
            }]
        )
        self.build_ui()

    def duplicate_plant(self, plant):
        """Dupliziert eine Pflanze in einen freien Slot."""
        slot = self._find_free_slot()
        if slot == -1:
            print("[PlantPlanner] ERROR: No free slots for duplication!")
            return
        
        new_plant = copy.deepcopy(plant)
        new_plant["slot"] = slot
        new_plant["used"] = True
        new_plant["name"] += " COPY"
        
        # Stelle sicher, dass das Array groß genug ist
        while len(self.plants) <= slot:
            self.plants.append({"used": False})
        
        self.plants[slot] = new_plant

        self._pending_popup = {
            "title": "Pflanze kopiert",
            "reset_sent": False,
        }

        self._push_plants_to_esp()
        self.build_ui()

    def delete_plant(self, plant):
        """Löscht eine Pflanze (setzt used=False, keine Verschiebung)."""
        slot = plant.get("slot", -1)
        if slot >= 0 and slot < len(self.plants):
            self.plants[slot]["used"] = False
            self.plants[slot]["slot"] = slot

        self._pending_popup = {
            "title": "Pflanze gelöscht",
            "reset_sent": False,
        }


        self._push_plants_to_esp()
        self.build_ui()

    # =============================================================================
    # SYNC & ROLLOVER
    # =============================================================================
    def _check_sync_status(self, dt):
        data = GLOBAL_STATE.overlay_engine.get_buffer_data(
            GLOBAL_STATE.get_active_device_id()
        )
        if not data:
            return

        web_ch = data.get("webserver", {})
        server_rev = int(web_ch.get("rev_plant_planner", 0))

        # 🔴 HARD REV GATE (WICHTIG!)
        # Wenn Server hinter uns ist → NICHTS tun, kein Retry-Spam
        if server_rev < self._last_sent_rev:
            return

        # 🔥 retry handling (jetzt sauber kontrolliert)
        if self.engine.is_pending(server_rev):
            if self.engine.should_retry():
                if self.engine.retry_allowed():
                    self.engine.register_retry()
                    self._push_plants_to_esp()
                    return

        # optional: status holen (für später UI)
        status = self.engine.get_status(
            server_rev,
            self._user_active,
            self._last_user_action
        )

    def _check_day_rollover(self, dt):
        today = date.today()
        if today != self._last_day:
            self._last_day = today
            print("[PlantPlanner] DAY CHANGED -> REFRESH UI")
            self.build_ui()

    # =============================================================================
    # HILFSFUNKTIONEN
    # =============================================================================
    
    def _find_free_slot(self):
        """Sucht den ersten freien Slot (0-9)."""
        for i in range(10):  # MAX 10 SLOTS
            if i >= len(self.plants):
                return i
            if not self.plants[i].get("used", False):
                return i
        return -1  # Alle Slots belegt
    
    # =============================================================================
    # UPDATE
    # =============================================================================

    def update_from_global(self, data):
        """Synchronisiert alle 10 Slots vom ESP32 mit Schutz gegen Pseudo-Daten."""
        if not data:
            self._clear_ui_to_empty()
            return
    
        self.header.update_from_global(data)
        web_ch = data.get("webserver", {})
        
        # 1. SCHUTZWAL: Prüfen, ob der Webserver überhaupt alive/online ist
        if not web_ch.get("alive", False) or web_ch.get("status") == "offline":
            # Wenn das Gerät offline ist oder wechselt, keine Pseudo-Daten rendern
            self._clear_ui_to_empty()
            return

        pp = web_ch.get("plant_planner", {})
        server_rev = int(web_ch.get("rev_plant_planner", 0))

        # ❗ BLOCKIERE ALTE DATEN
        if server_rev < self._last_sent_rev:
            return    
        # 2. SCHUTZWAL: Existiert der Key überhaupt und ist er valide befüllt?
        if not pp or "plants" not in pp:
            # Das Gerät hat gar keinen Plant Planner aktiv oder eingerichtet
            self._clear_ui_to_empty()
            return

        server_rev = int(web_ch.get("rev_plant_planner", 0))

        # ❗ NEU: Nur akzeptieren wenn >= letzter gesendeter Rev
        if server_rev < self._last_sent_rev:
            return  # IGNORE OLD DATA (Ghost Protection)

        new_plants = pp["plants"]
        if len(new_plants) != 10:
            return        
        # 3. SCHUTZWAL: Ist die Liste leer oder fehlerhaft strukturiert?
        if not isinstance(new_plants, list):
            return

        # Nur wenn echte, valide Daten da sind, updaten wir das RAM-Array
        if new_plants != self.plants:
            self.plants = copy.deepcopy(new_plants)
            self.build_ui()

        # =====================================================================
        # TARGET-REVISION ACKNOWLEDGEMENT FOR POPUP
        # =====================================================================
        server_rev = int(web_ch.get("rev_plant_planner", 0))
        if (
            self._pending_popup
            and self._last_sent_rev > 0
            and server_rev >= self._last_sent_rev
        ):
            GrowCommandStatusPopup.show(
                reset_sent=self._pending_popup["reset_sent"],
                title=self._pending_popup["title"],
                duration=1.2
            )
            self._pending_popup = None

    def _clear_ui_to_empty(self):
        """Setzt den lokalen Pflanzen-State sauber zurück, wenn das Gerät keine Daten hat."""
        if self.plants != []:
            self.plants = []
            self.build_ui()