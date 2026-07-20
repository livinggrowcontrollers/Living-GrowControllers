# dashboard_gui/dashboard.py – SESSION 17 READY

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
import config
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.common.buttons.control_buttons import ControlButtons
from dashboard_gui.ui.dashboard_content.dashboard_main_panel import DashboardMainPanel
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.common.header_online import HeaderBar
ASSET_ROOT = os.path.join("dashboard_gui", "assets")

class DashboardScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.root_layout = BoxLayout(orientation="vertical")

        # Hintergrund-Optimierung für das gesamte Screen-Layout
        with self.root_layout.canvas.before:
            from kivy.graphics import Rectangle, Color
            # Grundebene auf satten, dunklen OLED-Ton setzen
            Color(0.05, 0.05, 0.06, 1)
            self.base_bg = Rectangle(pos=self.pos, size=self.size)
            
            # Jetzt die Grafik-Ebene darüberlegen
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(
                source=os.path.join(ASSET_ROOT, "background.png"),
                pos=self.pos,
                size=self.size
            )
        
        self.root_layout.bind(
            pos=lambda *_: [
                setattr(self.base_bg, "pos", self.root_layout.pos),
                setattr(self.bg_rect, "pos", self.root_layout.pos)
            ],
            size=lambda *_: [
                setattr(self.base_bg, "size", self.root_layout.size),
                setattr(self.bg_rect, "size", self.root_layout.size)
            ]
        )
        self.add_widget(self.root_layout)
        # IDIOTENSICHERER PFAD-CACHE
        self._bg_path_1 = os.path.join(ASSET_ROOT, "background.png")
        self._bg_path_2 = os.path.join(ASSET_ROOT, "background2.png")
        # Global State registrieren
        GLOBAL_STATE.ui_handler.attach_screen("dashboard", self) # Geht direkt zum Spezialisten

        # HEADER
        self.header = HeaderBar()
        self.root_layout.add_widget(self.header)

        # SCROLLVIEW CONTAINER
        self.scroll_container = ScrollView(
            size_hint=(1, 1), # WICHTIG: Nimmt den Platz zwischen Header und Controls ein
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp_scaled(2),
            scroll_type=['bars', 'content']
        )

        # MAIN PANEL (Das GridLayout)
        self.content = DashboardMainPanel()
        self.scroll_container.add_widget(self.content)
        
        self.root_layout.add_widget(self.scroll_container)

        # CONTROLS
        self.controls = ControlButtons(on_reset=self.reset_from_global)
        self.controls.size_hint = (1,None)
        self.controls.height = dp_scaled(40)
        self.controls.pos_hint = {'y':0}
        self.root_layout.add_widget(self.controls)

        # Tile-Reihenfolge
        self.tile_temp_in = self.content.tile_temp_in
        self.tile_hum_in  = self.content.tile_hum_in
        self.tile_vpd_in  = self.content.tile_vpd_in

        self.tile_temp_ex = self.content.tile_temp_ex
        self.tile_hum_ex  = self.content.tile_hum_ex
        self.tile_vpd_ex  = self.content.tile_vpd_ex

        # Bind each tile's release to open fullscreen (keeps tile IDs intact)
        def _bind_tile(tile):
            def _on_release(*_args):
                idx = GLOBAL_STATE.get_active_index()
                dev_list = GLOBAL_STATE.get_device_list()
                if not dev_list or idx >= len(dev_list):
                    return
                item = dev_list[idx]
                dev_id = item.get("device_id") if isinstance(item, dict) else item
                channel = GLOBAL_STATE.get_active_channel()
                full_key = f"{dev_id}_{channel}_{tile.tile_id}"
                if tile.tile_id not in GLOBAL_STATE.get_active_tiles(dev_id, channel):
                    print(f"[DASHBOARD] Blocked inactive tile: {full_key}")
                    return
                self.open_fullscreen(full_key)
            tile.bind(on_release=_on_release)

        for _k, _tile in self.content.tile_map.items():
            _bind_tile(_tile)



    # -----------------------------------------------------
    # Navigation
    # -----------------------------------------------------
    def goto_setup(self, *_):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
    
        GLOBAL_STATE.ui_handler.goto("setup")

    def goto_debug(self, *_):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
    
        GLOBAL_STATE.ui_handler.goto("debug")

    # -----------------------------------------------------
    # OPEN DEVICE PICKER
    # -----------------------------------------------------
    def open_device_picker(self, *_):
        """
        Wird von HeaderBar aufgerufen, wenn der User ⇅ klickt.
        """
        picker = self.manager.get_screen("device_picker")
        picker.open()
        
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.goto("device_picker")


    # -----------------------------------------------------
    # GLOBAL TICK → Dashboard Update
    # -----------------------------------------------------
    def update_from_global(self, d):
        # 1. Header immer updaten (macht die sauberer Arbeit)
        self.header.update_from_global(d)

        # 🔥 2. PRÜFUNG: Gibt es überhaupt echte konfigurierte Geräte?
        lst = []
        if hasattr(GLOBAL_STATE, "active_channel_engine") and GLOBAL_STATE.active_channel_engine:
            lst = GLOBAL_STATE.active_channel_engine.get_device_list()

        if not lst:
            # Wenn keine Geräte da sind, das Main-Panel komplett leeren und abbrechen!
            # Keine Updates an Kacheln schicken, keine Sichtbarkeiten berechnen.
            if hasattr(self, "content") and self.content:
                self.content.clear_widgets()
            
            # Hintergrund auf Standard (background.png) zwingen
            if self.bg_rect.source != self._bg_path_1:
                self.bg_rect.source = self._bg_path_1
            return # <-- HIER ABBRECHEN! Weitergehen verboten.

        # 3. Nur wenn Geräte da sind, wird das Content-Panel befeuert
        self.content.update_from_data(d)

        # --- ACTIVE TILE CHECK ---
        active_tiles = [k for k, v in self.content.tile_map.items() if v.parent is self.content]
        dev_id = GLOBAL_STATE.get_active_device_id()
        channel = GLOBAL_STATE.get_active_channel()
        GLOBAL_STATE.register_tiles(active_tiles, dev_id, channel)
        is_active = len(active_tiles) > 0

        # --- BACKGROUND SWITCH ---
        target_bg = self._bg_path_2 if is_active else self._bg_path_1
        if self.bg_rect.source != target_bg:
            self.bg_rect.source = target_bg
            
    # -----------------------------------------------------
    # GLOBAL RESET
    # -----------------------------------------------------
    def reset_from_global(self):
        print("[DASHBOARD] Suche Tiles zum Resetten...")

        # Zuerst alle Widgets resetten
        for widget in self.walk():
            if hasattr(widget, 'reset') and callable(widget.reset):
                widget.reset()

        # 🔥 NEU: Content-Panel hart leeren, um Geister-Kacheln zu eliminieren
        if hasattr(self, 'content') and self.content:
            self.content.clear_widgets()

        if hasattr(self, 'header'):
            self.header.set_clock("--:--")
            self.header.set_rssi(None)

    # -----------------------------------------------------
    # TILE → FULLSCREEN
    # -----------------------------------------------------
    def open_fullscreen(self, tile_id):
        fs = self.manager.get_screen("fullscreen")
        if not fs.activate_tile(tile_id):
            return
    
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.goto("fullscreen")


