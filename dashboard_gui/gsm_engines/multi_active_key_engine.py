# dashboard_gui/engines/multi_active_key_engine.py
from typing import List, Dict, Set
import config # Falls du hier direkt speichern willst

class MultiActiveKeyEngine:
    """
    Verantwortlich für die Berechnung der aktiven Keys pro Gerät,
    Multi-Channel (adv + gatt + webserver) und Mixed-Mode.
    """

    def __init__(self, gsm):
        self.gsm = gsm

    # ---------------------------------------------------------
    # Multi-Channel Active Keys
    # ---------------------------------------------------------
    def extract_active_keys(self, frame: Dict) -> List[str]:
        """
        Ermittelt alle aktiven Keys für adv, gatt und webserver Kanäle.
        """
        active: Set[str] = set()

        for ch_name in ("adv", "gatt", "webserver"):
            ch = frame.get(ch_name)
            if not isinstance(ch, dict):
                continue

            internal = ch.get("internal", {})
            external = ch.get("external", {})
            vpd_int = ch.get("vpd_internal", {})
            vpd_ext = ch.get("vpd_external", {})
            dew_int = ch.get("dew_point_internal", {})
            dew_ext = ch.get("dew_point_external", {})

            # Interne Werte prüfen
            if internal.get("temperature", {}).get("value") is not None:
                active.add("temp_in")
            if internal.get("humidity", {}).get("value") is not None:
                active.add("hum_in")
            if vpd_int.get("value") is not None:
                active.add("vpd_in")
            if dew_int.get("value") is not None:
                active.add("dew_in")

            # Externe Werte prüfen (via present flag oder Werte-Check)
            if external.get("present") or external.get("temperature", {}).get("value") is not None:
                if external.get("temperature", {}).get("value") is not None:
                    active.add("temp_ex")
                if external.get("humidity", {}).get("value") is not None:
                    active.add("hum_ex")
                if vpd_ext.get("value") is not None:
                    active.add("vpd_ex")
                if dew_ext.get("value") is not None:
                    active.add("dew_ex")

        return list(active)

    # ---------------------------------------------------------
    # Mixed Mode Device Selection Helpers
    # ---------------------------------------------------------
    def toggle_device_selection(self, dev_id: str):
        """Aktiviert/Deaktiviert ein Gerät für den Mixed-Mode inkl. Config-Sync"""
        selected = self.gsm.mixed_selected_buffers
        if dev_id in selected:
            selected.remove(dev_id)
            config.set_mixed_enabled(dev_id, False)
        else:
            selected.add(dev_id)
            config.set_mixed_enabled(dev_id, True)

    def toggle_device_mode(self, dev_id: str, mode: str):
        """
        Internal / External Mode Toggle pro Device.
        Stellt sicher, dass mindestens ein Modus aktiv bleibt.
        """
        # Wir holen uns das aktuelle Set (Standard: internal)
        modes = self.gsm.mixed_device_modes.get(dev_id, {"internal"}).copy()
        
        if mode in modes:
            if len(modes) > 1:
                modes.remove(mode)
        else:
            modes.add(mode)
            
        self.gsm.mixed_device_modes[dev_id] = modes
        
        # Sync zur Config für permanenten Save
        is_external = "external" in modes
        config.set_mixed_external(dev_id, is_external)