# dashboard_gui/engines/unit_engine.py

class UnitEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        self.unit_map = {}  # { "MAC_adv_temp_in": "°F" }
        self.temp_unit = "°C"

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def get_unit(self, key):
        """Einheit für einen Graph-/Tile-Key."""
        return self.unit_map.get(key, "")

    def set_unit(self, key, unit):
        self.unit_map[key] = unit

    def toggle_temp_unit(self):
        """Globale Temperatur-Einheit wechseln."""
        self.temp_unit = "°F" if self.temp_unit == "°C" else "°C"
        print(f"[UnitEngine] Temp unit -> {self.temp_unit}")

        # Optional: Graph Reset damit keine Drift-Artefakte entstehen
        if hasattr(self.gsm, "graph_engine"):
            self.gsm.graph_engine.reset()

    def get_temp_unit(self):
        return self.temp_unit

    # ---------------------------------------------------------
    # Optional: Komplett-Reset
    # ---------------------------------------------------------

    def reset(self):
        self.unit_map.clear()