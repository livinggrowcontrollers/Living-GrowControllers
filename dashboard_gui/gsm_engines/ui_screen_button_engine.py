# dashboard_gui/ui_screen_button_engine.py
# dashboard_gui/ui_screen_button_engine.py
class UIManager:
    def __init__(self, gsm):
        self.gsm = gsm  # Rückreferenz auf den Boss (GSM)
        self.broadcast_buttons = [] # Alle Screen-Referenzen zentral hier
        self.active_inspector = None
        self.active_light_overlay = None
        self.active_circulation_fan_overlay = None
        self.active_exhaust_fan_overlay = None
        # -------------------------------------------------
        # Navigation History
        # -------------------------------------------------
        self.back_stack = []
        self.forward_stack = []   
        self.screens = {
            "dashboard": None, "fullscreen": None, "setup": None,
            "about": None, "settings": None, "vpd_scatter": None,
            "debug": None, "csv_viewer": None, "cam_viewer": None,
            "device_picker": None, "sensor_mixed_mode": None,
            "grow_controller": None, "plant_planner": None,
            "grow_overview": None
        }

    def attach_screen(self, name, ref):
        """Registriert einen Screen im Manager."""
        if name in self.screens:
            self.screens[name] = ref

    def get_screen(self, name):
        """Gibt eine registrierte Screen-Referenz zurück, ohne den Kivy ScreenManager zu bemühen."""
        return self.screens.get(name)

    # ---------------------------------------------------------
    # Navigation Engine (Testlauf: Max 3 Screens + Loop-Schutz)
    # ---------------------------------------------------------

    def go_forward(self):
        from kivy.app import App

        app = App.get_running_app()
        sm = app.root

        if not self.forward_stack:
            return

        current = sm.current

        self.back_stack.append(current)

        sm.current = self.forward_stack.pop()

        self._refresh_navigation_buttons()


    # ---------------------------------------------------------
    # Navigation Engine (Optimiert: Max 4 Screens + Loop-Schutz)
    # ---------------------------------------------------------
    def goto(self, screen_name):
        from kivy.app import App

        sm = App.get_running_app().root
        current = sm.current

        # 🔥 WICHTIG: Kein Hard-Return mehr für Dashboard!
        if current == screen_name:
            return

        # Aktuellen Screen speichern
        self.back_stack.append(current)

        if not self.back_stack or self.back_stack[-1] != current:
            self.back_stack.append(current)
        # Max 4 History

        if len(self.back_stack) > 4:
            self.back_stack.pop(0)

        # Forward löschen (wie Browser)
        self.forward_stack.clear()

        # Wechsel
        sm.current = screen_name

        self._refresh_navigation_buttons()

    def go_back(self):
        from kivy.app import App
        sm = App.get_running_app().root

        if not self.back_stack:
            # NOTFALL-Sicherung: Wenn der Stack leer ist, wir aber nicht im Dashboard sind,
            # erzwinge den Sprung ins Dashboard!
            if sm.current != "dashboard":
                sm.current = "dashboard"
                self._refresh_navigation_buttons()
            return

        current = sm.current
        self.forward_stack.append(current)
        
        # Nächsten Screen holen
        next_screen = self.back_stack.pop()
        
        # Zusätzliche Absicherung für die "Max 4x Zurück"-Garantie:
        # Wenn der Stack jetzt leer ist, wir aber NICHT im Dashboard landen würden,
        # biegen wir das Ziel hart auf das Dashboard um.
        if not self.back_stack and next_screen != "dashboard" and "dashboard" in self.screens:
            next_screen = "dashboard"

        sm.current = next_screen
        self._refresh_navigation_buttons()

    def can_go_back(self):
        return len(self.back_stack) > 0

    def can_go_forward(self):
        return len(self.forward_stack) > 0

    def _refresh_navigation_buttons(self):
        for screen in self.screens.values():
            if screen and hasattr(screen, "header"):
                screen.header.update_navigation_buttons()

    def update_leds(self, led_state):
        """Pusht den LED-Status an ALLE registrierten Screens."""
        for name, scr in self.screens.items():
            if scr and hasattr(scr, 'header'):
                scr.header.set_led(led_state)

    # ---------------------------------------------------------
    # Button Sync
    # ---------------------------------------------------------

    def _refresh_all_buttons(self):
        """Geht alle registrierten Screens durch und aktualisiert die Controls."""
        for name, scr in self.screens.items():
            if scr:
                if hasattr(scr, "controls") and scr.controls:
                    scr.controls.refresh_state()

    def refresh_broadcast_buttons(self):
        """Aktualisiert die Broadcast-Buttons in allen Headern."""
        for btn in self.broadcast_buttons:
            btn.refresh()

    def update_active_screen(self, screen_manager, data_packet):
        """Sendet Daten nur an den aktuell sichtbaren Screen."""
        if screen_manager is None:
            return

        current_name = screen_manager.current
        current_scr = screen_manager.get_screen(current_name)

        if current_scr and hasattr(current_scr, 'update_from_global'):
            current_scr.update_from_global(data_packet)

    def register_broadcast_button(self, btn):
        if btn not in self.broadcast_buttons:
            self.broadcast_buttons.append(btn)
            btn.refresh()

    def unregister_broadcast_button(self, btn):
        if btn in self.broadcast_buttons:
            self.broadcast_buttons.remove(btn)

    def get_device_label(self, dev_id):
        return self.gsm.active_channel_engine.get_device_label(dev_id)

    def reset_all_screens(self):
        """Ruft auf JEDEM registrierten Screen die Reset-Logik auf."""
        for name, screen in self.screens.items():
            if hasattr(screen, 'reset_from_global'):
                print(f"[UIManager] Sende Reset an Screen: {name}")
                screen.reset_from_global()
   
    def open_signal_inspector(self, parent_header):
        if self.active_inspector:
            self.active_inspector.close()
        
        from dashboard_gui.ui.common.signal_inspector.signal_inspector import SignalInspector
        self.active_inspector = SignalInspector(parent_header=parent_header)
        
        from kivy.core.window import Window
        Window.add_widget(self.active_inspector)
        
    def close_signal_inspector(self):
        if self.active_inspector:
            self.active_inspector.close()
            self.active_inspector = None
