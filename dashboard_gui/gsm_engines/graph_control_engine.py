# dashboard_gui/gsm_engines/graph_control_engine.py

class GraphControlEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self.is_running = True

    def start(self):
        print("[GraphControl] GLOBAL START")
        self.is_running = True
        # WICHTIG: Das Flag im Arbeiter setzen!
        self.gsm.graph_engine.running = True 

    def stop(self):
        print("[GraphControl] GLOBAL STOP")
        self.is_running = False
        # WICHTIG: Das Flag im Arbeiter setzen!
        self.gsm.graph_engine.running = False

    def reset(self):
        """Löscht alle Daten und bereinigt alle angemeldeten Screens."""
        print("[GraphControl] GLOBAL RESET TRIGGERED")
        
        # 1. Daten in der GraphEngine löschen
        self.gsm.graph_engine.reset()
        self.gsm.graph_history_engine.reset()
        
        # 2. Alle UIs informieren (Dashboard, Fullscreen, etc.)
        # Wir nutzen den UIManager, um alle Screens zu erreichen
        self.gsm.ui_handler.reset_all_screens()
