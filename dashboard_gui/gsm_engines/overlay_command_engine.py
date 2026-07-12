###############################################################################
##### !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP (v2.0) !!! ############
###############################################################################
##### 1. HARDWARE FOLGT TARGET: Loop reagiert nur auf target vs effective.
#####    Direktes Pin-Schreiben durch UI-Input ist streng verboten!
#####

##### 3. REVISION-CONFIRMATION (rev): Der ESP bestätigt ECHTE Änderungen,
#####    indem er die rev spiegelt. Erst dann wird der Flash (Save) aktiv.
#####
##### 4. KEINE LÜGEN: Das UI zeigt "Synced" (Grün) NUR, wenn keine lokale
#####    Revision mehr auf Bestätigung wartet.
#####
##### 5. ATOMARE UPDATES: Neue Revisionen werden sofort übernommen, die
#####    Hardware (effective) zieht asynchron (z.B. über Rampen) nach.
#####
##### JEDE KI-ÄNDERUNG MUSS DIESE TRENNUNG VON RAM-PING (INIT) UND FLASH-DATA
##### (REV) WAHREN. WERTE OHNE REVISIONS-SPIEGELUNG SIND REINE LÜGEN!
###################################################################################################################################
import time
from web_client import WEB_CLIENT
try:
    from dashboard_gui.ui.grow_controller_content.pin_matrix import validate_and_build_pins
except Exception:
    # Fallback: if import fails (tests, CLI), define a noop validator that always succeeds
    def validate_and_build_pins(current, new_kwargs):
        # return True and merged view that prefers new_kwargs over current gpios
        current_gpios = current.get("gpios", {}) if current else {}
        merged = {}
        keys = [
            "p_reset",

            "p_c_fan",
            "p_c_tac",
            "p_c_tac_pull",

            "p_e_fan",
            "p_e_tac",
            "p_e_tac_pull",

            "p_light",

            "p_i2c_sda",
            "p_i2c_scl",

            "p_rtc_sda",
            "p_rtc_scl",

            "p_bat",
            "p_bat_pull",
        ]
        for k in keys:
            if k in new_kwargs:
                merged[k] = int(new_kwargs[k])
            else:
                merged[k] = current_gpios.get(k, -1)
        return True, merged

class OverlayCommandEngine:
    def __init__(self, gsm):
        self.gsm = gsm

    def _is_valid_overlay_snapshot(self, frame, webserver):
        if not isinstance(frame, dict) or not isinstance(webserver, dict):
            return False

        if not webserver.get("alive", False):
            return False

        if webserver.get("status") == "offline":
            return False

        return True

    def process_command(self, mac, cmd_type, **kwargs):
        if cmd_type == "circulation_fan":
            return self.send_fan_command(mac, **kwargs)
        elif cmd_type == "circulation_fan_range":
            return self.send_fan_range(mac, **kwargs)
            
        # --- EXHAUST FAN LOGIK ---
        elif cmd_type == "exhaust_fan":
            return self.send_exhaust_command(mac, **kwargs)
        elif cmd_type == "exhaust_fan_range":
            return self.send_exhaust_range(mac, **kwargs)
            
        elif cmd_type == "light":
            return self.send_light_command(mac, **kwargs)
        elif cmd_type == "grow_controller":
            return self.send_grow_controller_command(mac, **kwargs)
        elif cmd_type == "plant_planner":
            return self.send_plant_planner_command(mac, **kwargs)
        elif cmd_type == "climate_hub":
            return self.send_climate_hub_command(mac, **kwargs)
        
        return None

    # =========================================================================
    # PLANT PLANNER COMMANDS (Target-Revision v2.0 - Ohne Init-Handshake)
    # =========================================================================
    
    def send_plant_planner_command(self, mac, **kwargs):
        """
        Inkrementiert die echte Revisionsnummer für Pflanzendaten.
        Triggert atomares Schreiben auf dem ESP erst bei Revision-Match.
        """
        current = self.get_latest_device_data(mac)
        pp = current.get("plant_planner", {})
    
        last_rev = int(pp.get("rev_plant_planner", 0))
        new_rev = last_rev + 1
    
        payload = {"rev_plant_planner": new_rev}
        plant_payload = {}

        if "plant_updates" in kwargs:
            plant_payload["plant_updates"] = kwargs.get("plant_updates", [])
        else:
            plant_payload["plants"] = kwargs.get("plants", pp.get("plants", []))

        if plant_payload:
            payload["plant_planner"] = plant_payload
    
        WEB_CLIENT.send_control(mac, payload)
        print(f"[PlantPlanner] TARGET-REV -> {new_rev}")
        return new_rev    

    # =========================================================================
    # CLIMATE HUB COMMANDS (Interims-Brücke auf rev_exhaust)
    # =========================================================================
    
    def send_climate_hub_command(self, mac, **kwargs):
        """ 
        Übergangslösung: Schreibt direkt auf rev_exhaust, da der ESP 
        die Klima-Sollwerte bereits im Exhaust-Kontext verwaltet.
        """
        current = self.get_latest_device_data(mac)
        
        # Wir nutzen die echte, vorhandene Exhaust-Revision!
        last_rev = int(current.get("rev_exhaust", 0))
        new_rev = last_rev + 1
        
        payload = {
            # Beibehalten der bestehenden Lüfter-Sollwerte aus dem Buffer

            
            # Die primären Klima-Sollwerte vom Climate Hub Overlay
            "target_temp_min": round(float(kwargs.get("t_min", current.get("target_temp_min", 22.0))), 1),
            "target_temp_max": round(float(kwargs.get("t_max", current.get("target_temp_max", 28.0))), 1),
            "target_humidity_min": int(kwargs.get("h_min", current.get("target_humidity_min", 45))),
            "target_humidity_max": int(kwargs.get("h_max", current.get("target_humidity_max", 70))),
            "target_vpd_min": round(float(kwargs.get("vpd_min", current.get("target_vpd_min", 0.8))), 1),
            "target_vpd_max": round(float(kwargs.get("vpd_max", current.get("target_vpd_max", 1.5))), 1),
            
            # Kennzeichnung für das Zielsystem auf dem ESP
            "rev_exhaust": new_rev
        }
        
        WEB_CLIENT.send_control(mac, payload)
        print(f"[ClimateHub -> Exhaust-Bridge] TARGET-REV: {new_rev} (Sollwerte synchronisiert)")
        return new_rev
   
   
   
   
    # =========================================================================
    # EXHAUST FAN COMMANDS (Target-Revision v2.0)
    # =========================================================================
    


    def send_exhaust_command(self, mac, **kwargs):
        """ Erhöht rev_exhaust -> ESP schreibt erst bei Match in den Flash. """
        current = self.get_latest_device_data(mac)
        
        last_rev = int(current.get("rev_exhaust", 0))
        new_rev = last_rev + 1
        
        payload = {
            "exhaust_fan_min": int(kwargs.get("min", current.get("exhaust_fan_min", 20))),
            "exhaust_fan_pct": int(kwargs.get("max", current.get("exhaust_fan_pct", 65))),
            "exhaust_fan_mode": kwargs.get("mode", current.get("exhaust_fan_mode", "auto")),
            "exhaust_fan_chaos": bool(kwargs.get("chaos", current.get("exhaust_fan_chaos_active", False))),
            "exhaust_fan_night_reduction":
                bool(
                    kwargs.get(
                        "night_reduction",
                        current.get(
                            "exhaust_fan_night_reduction",
                            True
                        )
                    )
                ),
            "target_temp_min": round(float(kwargs.get("t_min", current.get("target_temp_min", 22.0))), 1),
            "target_temp_max": round(float(kwargs.get("t_max", current.get("target_temp_max", 28.0))), 1),
            "target_humidity_min": int(kwargs.get("h_min", current.get("target_humidity_min", 40))),
            "target_humidity_max": int(kwargs.get("h_max", current.get("target_humidity_max", 70))),
            "target_vpd_min": round(float(kwargs.get("vpd_min", current.get("target_vpd_min", 0.8))), 1),
            "target_vpd_max": round(float(kwargs.get("vpd_max", current.get("target_vpd_max", 1.5))), 1),
            
            "rev_exhaust": new_rev
        }
        
        WEB_CLIENT.send_control(mac, payload)
        print(f"[Exhaust] TARGET-REV: {new_rev} | Mode: {payload['exhaust_fan_mode']}")
        return new_rev

    # =========================================================================
    # CIRCULATION FAN COMMANDS
    # =========================================================================

        
    def send_fan_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac)
        last = int(current.get("rev_circfan", 0))
        new_rev = last + 1
        
        payload = {
            "circulation_fan_min": int(kwargs.get("min", 20)),
            "circulation_fan_pct": int(kwargs.get("max", 65)),
            "circulation_fan_mode": kwargs.get("mode", "nat"),
            "rev_circfan": new_rev
        }
        
        WEB_CLIENT.send_control(mac, payload)
        return new_rev 

# =========================================================================
    # GROW CONTROLLER & LIGHTS
    # =========================================================================



    def send_grow_controller_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac)
        last_rev = int(current.get("rev_grow", 0))
        new_rev = last_rev + 1
    
        # Gesetz Punkt 4: Revision muss zwingend mitgesendet werden
        payload = {"rev_grow": new_rev}
    
        # ================= SYSTEM COMMANDS =================
        if "command" in kwargs: 
            payload["command"] = kwargs["command"]

        # ================= WIFI SETTINGS =================
        if "wifi_ssid" in kwargs: payload["wifi_ssid"] = kwargs["wifi_ssid"]
        if "wifi_pw" in kwargs: payload["wifi_pw"] = kwargs["wifi_pw"]
        # Wenn eine SSID gesetzt wird, setzen wir standardmässig den Station/Router-Mode (1),
        # sofern kein expliziter wifi_mode angegeben wurde.
        if "wifi_mode" in kwargs:
            payload["wifi_mode"] = int(kwargs["wifi_mode"])
        elif "wifi_ssid" in kwargs:
            payload["wifi_mode"] = 1
        
        # ================= SECURITY SETTINGS =================
        if "sec_user" in kwargs: payload["sec_user"] = kwargs["sec_user"]
        if "sec_pw" in kwargs: payload["sec_pw"] = kwargs["sec_pw"]

        # ================= BLUETOOTH PAIRING =================
        if "pair_outside" in kwargs: payload["pair_outside"] = kwargs["pair_outside"]
        if "pair_inside" in kwargs: payload["pair_inside"] = kwargs["pair_inside"]    

        # ================= GPIO / HAL CONFIG (NEU) =================
        # Validate requested GPIO changes first (role support & collisions).
        try:
            valid, result = validate_and_build_pins(current, kwargs)
        except Exception as e:
            print(f"[OverlayCommandEngine] GPIO validator error: {e}")
            valid, result = True, {}

        if not valid:
            # Validator returns (False, "error message") on failure.
            print(f"[OverlayCommandEngine] GPIO validation failed: {result}")
            return None

        merged_gpios = result if isinstance(result, dict) else {}

        gpio_keys = [
            "p_reset",

            "p_c_fan",
            "p_c_tac",

            "p_e_fan",
            "p_e_tac",

            "p_light",

            "p_i2c_sda",
            "p_i2c_scl",

            "p_rtc_sda",
            "p_rtc_scl",

            "p_bat",
        ]


        for key in gpio_keys:
            if key in merged_gpios:
                payload[key] = int(merged_gpios.get(key, -1))

        pull_keys = [
            "p_c_tac_pull",
            "p_e_tac_pull",
            "p_bat_pull",
        ]

        for key in pull_keys:
            if key in kwargs:
                try:
                    val = int(kwargs[key])
                except Exception:
                    val = 0

                if val not in (0, 1, 2):
                    val = 0

                payload[key] = val
        # ================= BLUETOOTH TOGGLING (Bridge vs Scanner) =================
        # Integrate BLE bridge/scan flags into the target-revision payload.
        # Always include explicit target values (use kwargs if provided, otherwise current device state).
        try:
            current_bridge = bool(current.get("ble_bridge_enabled", True))
        except Exception:
            current_bridge = True
        try:
            current_scan = bool(current.get("ble_scan_enabled", True))
        except Exception:
            current_scan = True

        if "ble_bridge" in kwargs:
            payload["ble_bridge"] = bool(kwargs.get("ble_bridge", current.get("ble_bridge_enabled", True)))
        else:
            payload["ble_bridge"] = current_bridge

        if "ble_scan" in kwargs:
            payload["ble_scan"] = bool(kwargs.get("ble_scan"))
        else:
            payload["ble_scan"] = current_scan
        # Debug: show BLE flags being sent so we can trace UI -> engine -> device
        try:
            print(f"[Overlay] Sending to {mac}: ble_bridge={payload.get('ble_bridge')} ble_scan={payload.get('ble_scan')} rev_grow={payload.get('rev_grow')}")
        except Exception:
            pass

        # Abfahrt an den Web-Client
        WEB_CLIENT.send_control(mac, payload)
        return new_rev



    def send_light_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac)
        last = int(current.get("rev_light", 0))
        new_rev = last + 1
        
        payload = {
            "light_pct": int(kwargs.get("pct", current.get("light_pct", 0))),
            "light_mode": kwargs.get("mode", current.get("light_mode", "manual")),
            "l_start_h": int(kwargs.get("h", current.get("l_start_h", 8))),
            "l_start_m": int(kwargs.get("m", current.get("l_start_m", 0))),
            "l_dur": int(kwargs.get("dur", current.get("l_dur", 720))),
            "l_sunrise": int(kwargs.get("sunrise", current.get("l_sunrise", 60))),
            "l_sunset": int(kwargs.get("sunset", current.get("l_sunset", 60))),
            "light_climate_override": bool(kwargs.get("climate_override", current.get("light_climate_override", False))),
            "rev_light": new_rev
        }
        
        WEB_CLIENT.send_control(mac, payload)
        return new_rev

    # =========================================================================
    # UTILS (OPTIMIERT: PIPELINE-BREMSE ENTFERNT)
    # =========================================================================

    def get_latest_device_data(self, mac, require_online=False):
        """ 
        Single Source of Truth aus dem BUFFER. 
        OPTIMIERT: Holt den Frame rückwärts (aktuellster zuerst) ohne tiefen Overhead.
        """
        try:
            from dashboard_gui.data_buffer import BUFFER
            # Umgekehrtes Suchen spart das komplette Iterieren durch alte Frames
            for frame in reversed(BUFFER.get()):
                if frame.get("device_id") == mac:
                    webserver = frame.get("webserver", {})
                    if require_online and not self._is_valid_overlay_snapshot(frame, webserver):
                        return None
                    return webserver if isinstance(webserver, dict) else {}
        except Exception as e:
            print(f"[Engine] Buffer Read Error: {e}")
        return None if require_online else {}

    def get_buffer_data(self, mac):
        return self.get_latest_device_data(mac, require_online=True)
