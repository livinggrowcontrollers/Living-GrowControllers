# broadcast_button.py - Ein Button, um die Broadcast-Bridge zu steuern und ihren Status anzuzeigen.
from kivy.uix.button import Button
from dashboard_gui.ui.scaling_utils import sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE

class BroadcastButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.font_name = "FA"
        self.font_size = sp_scaled(22)
        self.size_hint = (None, 1)

        self.background_color = (0, 0, 0, 0)
        self.color = (0.7, 0.7, 0.7, 1)

        self.bind(on_release=self._toggle)
        
        # Initialer Refresh
        self.refresh()

    def _toggle(self, *_):
        """User klickt auf den Button"""
        be = GLOBAL_STATE.broadcast_engine
        
        # Wenn aktiv -> ausschalten und manuell deaktivieren
        if be.active:
            be.set_user_disabled(True)
        else:
            # Wenn inaktiv -> wieder erlauben
            be.set_user_disabled(False)
            # Falls Daten da sind, wird set_user_disabled(False) die Bridge automatisch starten

    def refresh(self, *_):
        """Wird vom GSM/UI-Handler gerufen, wenn sich was ändert"""
        be = GLOBAL_STATE.broadcast_engine
        status = be.get_status() # Holen uns das kompakte Status-Paket

        # 1. Sind überhaupt Daten da? (mixed.json)
        if not status["available"]:
            self.disabled = True
            self.color = (0.4, 0.4, 0.4, 1) # Dunkelgrau
            self.text = "\uf071" # Warn-Icon (Keine Daten)
            return

        # 2. Daten sind da -> Button freigeben
        self.disabled = False

        # 3. Ist die Bridge gerade aktiv?
        if status["active"]:
            self.text = "\uf09e" # RSSI/Sende-Icon
            self.color = (0.2, 1, 0.2, 1) # Leuchtend Grün
        else:
            # Daten da, aber Bridge aus (entweder durch User oder Fehler)
            self.text = "\uf05e" # Verbots-Schild / Aus-Icon
            self.color = (1, 0.3, 0.3, 1) if status["disabled"] else (0.7, 0.7, 0.7, 1)

    def on_parent(self, widget, parent):
        """Registriert sich beim UI-Handler, wenn der Button erscheint"""
        if parent:
            GLOBAL_STATE.ui_handler.register_broadcast_button(self)
        else:
            GLOBAL_STATE.ui_handler.unregister_broadcast_button(self)