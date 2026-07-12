# dashboard_gui/engines/tile_engine.py



class TileEngine:
    def __init__(self, gsm):
        self.gsm = gsm
        # REIHENFOLGE DER WAHRHEIT
        self.available_tiles = [
            "temp_in", "hum_in", "vpd_in",
            "temp_ex", "hum_ex", "vpd_ex",

            "ble_temp_outside",
            "ble_hum_outside",
            "ble_vpd_outside",
            "ble_temp_inside",
            "ble_hum_inside",
            "ble_vpd_inside",
            "leaf_temp", "vpd_leaf", 
            "circulation_fan_rpm",  # NEU
            "exhaust_fan_rpm",      # NEU
            "v_bat",
            "rssi",  # NEU: RSSI direkt im Kanal
                                    ]
        self.active_tiles = []
        self.active_tiles_by_context = {}

    def _context_key(self, device_id=None, channel=None):
        if device_id is None:
            device_id = self.gsm.get_active_device_id()
        if channel is None:
            channel = self.gsm.get_active_channel()
        if not device_id or not channel:
            return None
        return (device_id, channel)

    def _sort_tiles(self, tile_ids):
        valid = set(tile_ids or [])
        return [tile for tile in self.available_tiles if tile in valid]

    def parse_full_key(self, full_key):
        parts = str(full_key or "").split("_", 2)
        if len(parts) != 3 or not all(parts):
            return None, None, None
        return parts[0], parts[1], parts[2]

    def is_tile_active(self, device_id, channel, tile_id):
        return tile_id in self.get_active_tiles(device_id, channel)



# ---------------------------------------------------------
    # UI REGISTRATION
    # ---------------------------------------------------------

    def register_tiles(self, tile_ids, device_id=None, channel=None):
        """
        MetricsEngine meldet, was an Sensoren im aktuellen Frame da ist.
        Sortiert die Keys nach der 'Reihenfolge der Wahrheit' und verhindert 
        Key-Verluste durch unvollständige, asynchrone Datenströme.
        """
        if not tile_ids:
            return
        ctx = self._context_key(device_id, channel)
        if not ctx:
            return

        # 1. Akkumulation: Bestehende aktive Tiles behalten + neue Tiles hinzufügen
        # (Verhindert, dass langsame BLE-Sensoren nach dem ersten Frame wieder rausfliegen)
        current_set = set(self.active_tiles_by_context.get(ctx, []))
        for t_id in tile_ids:
            if t_id in self.available_tiles:
                current_set.add(t_id)

        # 2. Sortierung anhand der Master-Liste (Reihenfolge der Wahrheit) zwingend einhalten
        sorted_tiles = self._sort_tiles(current_set)

        # 3. Zustand atomar wegschreiben
        self.active_tiles_by_context[ctx] = sorted_tiles
        if ctx == self._context_key():
            self.active_tiles = sorted_tiles

    def reset_active_tiles(self, device_id=None, channel=None):
        """
        Muss aufgerufen werden, wenn ein Gerät gelöscht oder gewechselt wird,
        damit die Akkumulation für das neue Gerät von vorne beginnen kann.
        """
        ctx = self._context_key(device_id, channel)
        if ctx:
            print(f"[TileEngine] Resetting active tiles for context: {ctx}")
            self.active_tiles_by_context.pop(ctx, None)
        else:
            print("[TileEngine] Resetting all active tile contexts.")
            self.active_tiles_by_context.clear()
        self.active_tiles = self.get_active_tiles()

    def activate_tile(self, full_key):
        print(f"[FS] Aktiviere: {full_key}")

        dev_id, channel, tile_id = self.parse_full_key(full_key)
        if not dev_id or not channel or not tile_id:
            print("[FS] INVALID KEY FORMAT")
            return False

        allowed = self.get_active_tiles(dev_id, channel)

        if tile_id not in allowed:
            print(f"[FS] BLOCKED INVALID TILE: {tile_id}")

            fallback = self.get_first_tile_key(dev_id, channel)
            if fallback:
                print(f"[FS] FALLBACK -> {fallback}")
                return self.activate_tile(fallback)
            return False

        # ERST HIER state setzen!
        self.current_key = full_key
        self.tile_id = tile_id
        return True
    # ---------------------------------------------------------
    # FULL KEY BUILDER
    # ---------------------------------------------------------

    def build_full_key(self, device_id, channel, tile_id):
        return f"{device_id}_{channel}_{tile_id}"

    # ---------------------------------------------------------
    # TILE NAVIGATION
    # ---------------------------------------------------------

    def get_next_tile(self, current_tile, direction):
        active_tiles = self.get_active_tiles()

        if not active_tiles:
            return current_tile

        try:
            idx = active_tiles.index(current_tile)
        except ValueError:
            return current_tile

        new_idx = (idx + direction) % len(active_tiles)

        return active_tiles[new_idx]

    # ---------------------------------------------------------
    # FULL KEY NAVIGATION
    # ---------------------------------------------------------

# ---------------------------------------------------------
    # FULL KEY NAVIGATION (Waterproof Version)
    # ---------------------------------------------------------

    def get_next_full_key(self, current_full_key, direction):
        dev_id, channel, found_tile = self.parse_full_key(current_full_key)
        if not dev_id or not channel or not found_tile:
            return current_full_key

        active_tiles = self.get_active_tiles(dev_id, channel)
        
        # Wenn gar keine Kacheln aktiv sind, gibt es auch nichts zum Blättern
        if not active_tiles:
            return current_full_key

        try:
            prefix = f"{dev_id}_{channel}"

            # 3. Sicherheits-Check: Befinden wir uns in einem inaktiven Tile?
            # Wenn der User irgendwie in ein inaktives Tile geraten ist, 
            # holen wir ihn sofort zurück ins System.
            if found_tile not in active_tiles:
                return self.get_first_tile_key(dev_id, channel) or current_full_key

            # 4. Index in den AKTIVEN Kacheln bestimmen
            idx = active_tiles.index(found_tile)
            
            # 5. Den Loop berechnen (Modulo springt am Ende wieder an den Anfang)
            new_idx = (idx + direction) % len(active_tiles)
            next_tile_id = active_tiles[new_idx]
            
            # 6. Kontrollierter, sicherer neuer Key
            return f"{prefix}_{next_tile_id}"

        except Exception as e:
            print(f"[TileEngine] Critical Navigation Error: {e}")
            return current_full_key
        
    def get_first_tile_key(self, dev_id, channel):
        """Gibt den vollständigen Key für das allererste gültige AKTIVE Tile zurück."""
        active_tiles = self.get_active_tiles(dev_id, channel)
        if not active_tiles:
            return None
        return f"{dev_id}_{channel}_{active_tiles[0]}"
    
    def get_safe_neighbor(self, current_key, direction):
        """Sicherheits-Fallback: Findet den Nachbarn AUSSCHLIESSLICH innerhalb aktiver Tiles."""
        dev_id, channel, tile_id = self.parse_full_key(current_key)
        if not dev_id or not channel or not tile_id:
            return current_key

        active_tiles = self.get_active_tiles(dev_id, channel)
        
        if not active_tiles:
            return current_key
            
        if tile_id not in active_tiles:
            return self.get_first_tile_key(dev_id, channel) or current_key
            
        idx = active_tiles.index(tile_id)
        new_idx = (idx + direction) % len(active_tiles)
        return f"{dev_id}_{channel}_{active_tiles[new_idx]}"
    
    def get_active_tiles(self, device_id=None, channel=None):
        ctx = self._context_key(device_id, channel)
        if not ctx:
            self.active_tiles = []
            return []
        self.active_tiles = list(self.active_tiles_by_context.get(ctx, []))
        return self.active_tiles
    
