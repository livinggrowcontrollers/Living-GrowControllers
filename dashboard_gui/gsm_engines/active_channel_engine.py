# dashboard_gui/engines/active_channel_engine.py
# RICHTIG:
import decoder
import config
import core

class ActiveChannelEngine:
    def __init__(self, gatt_config_engine):
        self.active_index = 0
        self.active_channel = "webserver"
        self._last_counter = None
        self.gatt_config_engine = gatt_config_engine

    # ---------------------------------------------------------
    # Channel Management
    # ---------------------------------------------------------
    def set_active_channel(self, channel):
        if channel not in ("adv", "gatt", "webserver"):
            return
        if channel == self.active_channel:
            return

        prev = self.active_channel
        self.active_channel = channel
        self._last_counter = None

        print(f"[ACE] Channel -> {channel}")

        try:
            # 1. Aktuelle Geräte-ID ermitteln (ROBUST GEGEN LEERE LISTEN / FALSCHE INDIZES)
            lst = self.get_device_list()
            if not lst:
                print("[ACE] No devices available. Skipping channel actions.")
                return
                
            # Sicherstellen, dass der Index nicht out-of-bounds ist
            if self.active_index >= len(lst):
                self.active_index = max(0, len(lst) - 1)

            item = lst[self.active_index]
            device_id = item.get("device_id") if isinstance(item, dict) else item

            if not device_id:
                print("[ACE] Device ID is empty. Skipping.")
                return

            # 2. Kanal-spezifische Hardware-Aktionen
            cfg = config._init()
            dev = cfg.get("devices", {}).get(device_id, {}) if cfg else {}
            bridge_profile = dev.get("bridge_profile", "")

            if prev in ("adv", "webserver") and channel == "gatt":
                if bridge_profile:
                    self.gatt_config_engine.write(device_id)
            elif prev == "gatt" and channel == "adv":
                try:
                    core.stop_gatt_bridge()
                    print("[ACE] GATT Bridge stopped")
                except Exception as e:
                    print("[ACE] stop_gatt_bridge failed:", e)

            # ---------------------------------------------------------
            # ROBUSTER FULLSCREEN-RESET (Sichert Key-Verluste ab)
            # ---------------------------------------------------------
            if hasattr(self.gatt_config_engine, "gsm") and self.gatt_config_engine.gsm:
                gsm = self.gatt_config_engine.gsm
                
                if hasattr(gsm, "tile_engine") and gsm.tile_engine:
                    allowed = gsm.tile_engine.get_active_tiles(device_id, channel)
                    if allowed and len(allowed) > 0:
                        new_key = f"{device_id}_{channel}_{allowed[0]}"
                        
                        if hasattr(gsm, "ui_handler") and gsm.ui_handler:
                            fs_screen = gsm.ui_handler.get_screen("fullscreen")
                            # Hier prüfen wir, ob die UI-Methode existiert und fangen Fehler ab
                            if fs_screen and hasattr(fs_screen, "activate_tile"):
                                try:
                                    fs_screen.activate_tile(new_key)
                                except Exception as tile_err:
                                    print(f"[ACE] Soft-fail activating tile '{new_key}':", tile_err)

        except Exception as e:
            print("[ACE] channel switch failed:", e)

    def get_active_channel(self):
        return self.active_channel

    # ---------------------------------------------------------
    # Device Management
    # ---------------------------------------------------------
    def next_device(self):
        lst = self.get_device_list()
        if not lst:
            return
        self.set_active_index((self.active_index + 1) % len(lst))

    def previous_device(self):
        lst = self.get_device_list()
        if not lst:
            return
        self.set_active_index((self.active_index - 1) % len(lst))

    def set_active_index(self, idx):
        lst = self.get_device_list()
        if not lst:
            self.active_index = 0
            return

        # Absicherung gegen ungültige Indizes
        idx = max(0, int(idx))
        if idx >= len(lst):
            idx = len(lst) - 1

        if idx == self.active_index:
            # Auch wenn der Index gleich bleibt, prüfen wir, ob die Hardware getriggert werden muss
            # (wichtig, falls das Gerät gelöscht und neu angelegt wurde)
            pass 

        self.active_index = idx
        self._last_counter = None
        print(f"[ACE] Active device -> {idx}")

        try:
            item = lst[self.active_index]
            device_id = item.get("device_id") if isinstance(item, dict) else item

            # Der PlantPlanner darf niemals den State des vorherigen ESP bis
            # zum naechsten globalen Tick sichtbar oder bedienbar halten.
            if hasattr(self.gatt_config_engine, "gsm") and self.gatt_config_engine.gsm:
                planner = self.gatt_config_engine.gsm.ui_handler.get_screen("plant_planner")
                if planner and hasattr(planner, "on_device_changed"):
                    planner.on_device_changed(device_id)

            if hasattr(self.gatt_config_engine, "gsm") and self.gatt_config_engine.gsm:
                gsm = self.gatt_config_engine.gsm
                allowed = gsm.tile_engine.get_active_tiles(device_id, self.active_channel)
                fs_screen = gsm.ui_handler.get_screen("fullscreen") if hasattr(gsm, "ui_handler") else None
                if fs_screen and getattr(fs_screen, "current_key", None):
                    fallback = gsm.tile_engine.get_first_tile_key(device_id, self.active_channel)
                    if fallback:
                        fs_screen.activate_tile(fallback)
                    elif hasattr(fs_screen, "_clear_active_tile"):
                        fs_screen._clear_active_tile()

            if self.active_channel == "gatt" and device_id:
                cfg = config._init()
                dev = cfg.get("devices", {}).get(device_id, {}) if cfg else {}
                bridge_profile = dev.get("bridge_profile", "")
                if bridge_profile:
                    self.gatt_config_engine.write(device_id)
                    
        except Exception as e:
            print("[ACE] device switch failed:", e)

    def _rebuild_device_list(self):
        """Wird nach Config-Änderungen (Delete/Move/Copy) aufgerufen"""
        lst = self.get_device_list()
        
        # SZenario: Das LETZTE Gerät wurde gelöscht (Liste ist jetzt komplett leer)
        if not lst:
            self.active_index = 0
            print("[ACE] All devices deleted. State cleared.")
            print(decoder.get_decoded_ram())
            # OPTIONAL: Hier einen UI-Clear triggern, damit kein alter Datenmüll angezeigt wird
            try:
                if hasattr(self.gatt_config_engine, "gsm") and self.gatt_config_engine.gsm:
                    fs_screen = self.gatt_config_engine.gsm.ui_handler.get_screen("fullscreen")
                    if fs_screen and hasattr(fs_screen, "clear_display"):
                        fs_screen.clear_display() # Oder ähnliche Aufräum-Funktion deiner GUI
            except Exception as clear_err:
                print("[ACE] Failed to clear UI after total delete:", clear_err)
            return
            
        # Falls der Index durch das Löschen außerhalb der neuen Liste liegt, korrigieren
        if self.active_index >= len(lst):
            self.active_index = max(0, len(lst) - 1)
            print(f"[ACE] Active index adjusted to {self.active_index}")
        
        # WICHTIG: Den globalen Zustand zwingen, sich auf das aktuelle (neue) Gerät zu synchronisieren
        try:
            device_id = lst[self.active_index]
            print(f"[ACE] Syncing after rebuild to new active device: {device_id}")
            
            # Trigger den UI-Reset für das verbleibende Gerät, damit der Fullscreen nicht einfriert
            if hasattr(self.gatt_config_engine, "gsm") and self.gatt_config_engine.gsm:
                allowed = self.gatt_config_engine.gsm.tile_engine.get_active_tiles(device_id, self.active_channel)
                if allowed:
                    new_key = f"{device_id}_{self.active_channel}_{allowed[0]}"
                    fs_screen = self.gatt_config_engine.gsm.ui_handler.get_screen("fullscreen")
                    if fs_screen and hasattr(fs_screen, "activate_tile"):
                        fs_screen.activate_tile(new_key)
                        
        except Exception as e:
            print("[ACE] Rebuild sync failed:", e)

    def get_active_index(self):
        return self.active_index

    def get_device_list(self):
        cfg = config._init()
        if not cfg:
            return []
        devs = cfg.get("devices", {})
        if not isinstance(devs, dict):
            return []
        return list(devs.keys())

    def get_device_label(self, device_id):
        cfg = config._init()
        if not cfg:
            return device_id
        d = cfg.get("devices", {}).get(device_id, {}) if cfg else {}
        return d.get("name", device_id)
