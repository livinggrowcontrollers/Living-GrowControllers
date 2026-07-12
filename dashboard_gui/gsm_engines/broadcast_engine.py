import core
import os

class BroadcastEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        # Status-Variablen (aus dem GSM hierher verschoben)
        self.active = False
        self.data_available = False
        self.user_disabled = False

    def set_active(self, state: bool):
        """Schaltet die Bridge physisch an/aus und aktualisiert die UI."""
        if state == self.active:
            return
            
        self.active = state
        
        if state:
            try:
                core.start_broadcast_bridge()
                print("[BROADCAST] Bridge gestartet")
            except Exception as e:
                print(f"[BROADCAST] Start fehlgeschlagen: {e}")
        else:
            try:
                core.stop_broadcast_bridge()
                print("[BROADCAST] Bridge gestoppt")
            except Exception as e:
                print(f"[BROADCAST] Stop fehlgeschlagen: {e}")
        
        # UI informieren
        self.gsm.ui_handler.refresh_broadcast_buttons()

    def set_available(self, state: bool):
        """Wird von der MixedEngine gerufen, wenn Daten in der JSON liegen."""
        self.data_available = state
        # Falls Daten verschwinden, Bridge sofort aus
        if not state and self.active:
            self.set_active(False)

    def set_user_disabled(self, state: bool):
        """User hat manuell im Header auf den Button geklickt."""
        self.user_disabled = state
        if state:
            self.set_active(False)
        elif self.data_available:
            # Wenn wieder erlaubt und Daten da -> anmachen
            self.set_active(True)
        
        self.gsm.ui_handler.refresh_broadcast_buttons()

    def get_status(self):
        """Gibt alles für den Button-Refresh zurück."""
        return {
            "active": self.active,
            "available": self.data_available,
            "disabled": self.user_disabled
        }