#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.global_state_manager import GLOBAL_STATE
import core 

class DebugScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        # Root Layout
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)

        # Header
        self.header = HeaderBar()
        root.add_widget(self.header)
        GLOBAL_STATE.ui_handler.attach_screen("debug", self)

        # --- Zwei-Spalten Layout Container ---
        content_layout = BoxLayout(orientation="horizontal", spacing=dp_scaled(15), padding=dp_scaled(12))
        root.add_widget(content_layout)

        # --- LINKE SPALTE (Kills / Stops) ---
        scroll_left = ScrollView(size_hint=(0.5, 1))
        self.container_left = GridLayout(cols=1, spacing=dp_scaled(10), size_hint_y=None)
        self.container_left.bind(minimum_height=self.container_left.setter("height"))
        scroll_left.add_widget(self.container_left)

        # --- RECHTE SPALTE (Restarts / Starts) ---
        scroll_right = ScrollView(size_hint=(0.5, 1))
        self.container_right = GridLayout(cols=1, spacing=dp_scaled(10), size_hint_y=None)
        self.container_right.bind(minimum_height=self.container_right.setter("height"))
        scroll_right.add_widget(self.container_right)

        content_layout.add_widget(scroll_left)
        content_layout.add_widget(scroll_right)

        # --- Helper: Überschrift ---
        def add_hdr(text, target):
            target.add_widget(Label(
                text=f"[b]{text}[/b]", 
                markup=True, 
                size_hint_y=None, 
                height=dp_scaled(40),
                color=(0.8, 0.3, 0.3, 1) if target == self.container_left else (0.3, 0.8, 0.3, 1)
            ))

        add_hdr("KILL / STOP", self.container_left)
        add_hdr("RESTART / START", self.container_right)

        # --- Debug Buttons hinzufügen ---
        # ADV
        self._add_debug_pair("ADV", core.stop_adv_bridge, core.restart_adv_bridge)
        # GATT
        self._add_debug_pair("GATT", core.stop_gatt_bridge, core.restart_gatt_bridge)
        # LOG
        self._add_debug_pair("LOG", core.stop_log_bridge, core.restart_log_bridge)
        # MESH
        self._add_debug_pair("MESH", core.stop_broadcast_bridge, core.restart_broadcast_bridge)
        # Links erscheint "WEB STOP", rechts erscheint "WEB RESTART" (bzw. hier als Start-Funktion genutzt)
        self._add_debug_pair("WEB", core.stop_web_client_bridge, core.start_web_client_bridge)
        
        self._add_debug_pair("DECODER", core.stop_decoder_bridge, core.start_decoder_bridge)
        # SYSTEM (Ganz unten als Abgrenzung)
        self.container_left.add_widget(Label(size_hint_y=None, height=dp_scaled(20))) # Spacer
        self.container_right.add_widget(Label(size_hint_y=None, height=dp_scaled(20)))
        
        btn_stop = self.mk_btn("SYSTEM STOP", core.stop, (0.6, 0.1, 0.1, 1))
        btn_start = self.mk_btn("SYSTEM START", core.start, (0.1, 0.5, 0.2, 1))
        self.container_left.add_widget(btn_stop)
        self.container_right.add_widget(btn_start)

        btn_reboot = self.mk_btn("APP REBOOT", core.restart_app, (0.5, 0.1, 0.5, 1))
        self.container_right.add_widget(btn_reboot)

    def _add_debug_pair(self, name, stop_fn, restart_fn):
        """Fügt ein Paar aus Stop (links) und Restart (rechts) hinzu"""
        btn_l = self.mk_btn(f"{name} STOP", stop_fn, (0.4, 0.1, 0.1, 1))
        btn_r = self.mk_btn(f"{name} RESTART", restart_fn, (0.12, 0.2, 0.45, 1))
        self.container_left.add_widget(btn_l)
        self.container_right.add_widget(btn_r)

    def mk_btn(self, label, cb, base_color):
        btn = Button(
            text=label,
            background_normal="",
            background_color=(*base_color[:3], 0.6),
            font_size=sp_scaled(18),
            size_hint_y=None,
            height=dp_scaled(50),
        )
        btn.bind(on_release=lambda b: self._flash_and_run(b, base_color, cb))
        return btn

    def _flash_and_run(self, btn, base_color, callback):
        r, g, b, _ = base_color
        btn.background_color = (min(r+0.3, 1), min(g+0.3, 1), min(b+0.3, 1), 1)
        def _restore(dt):
            btn.background_color = (*base_color[:3], 0.6)
            if callback: callback()
        Clock.schedule_once(_restore, 0.1)

    def update_from_global(self, d):
        self.header.update_from_global(d)