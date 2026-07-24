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

# overlay_command
import time
import uuid

import config
import web_client
from dashboard_gui.circulation_fan_registry import fan_prefix, fan_revision_key, fan_gpio_keys, MAX_CIRCULATION_FANS
from dashboard_gui.gsm_engines.graph_engine import HistorySelectionResult


CLIMATE_HUB_REVISION_KEY = "rev_exhaust"


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

            "p_humidifier",

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
        self._pending_plant_revs = {}
        self._pending_overlay_commands = {}
        self._pending_history_commands = {}

    @staticmethod
    def _channel_key(mac, command_type, instance_id=None):
        if command_type in ("exhaust_fan", "climate_hub"):
            return (mac, "climate_hub", None)
        if command_type == "circulation_fan":
            return (mac, "circulation_fan", int(instance_id or 1))
        return (mac, command_type, None)

    def _next_overlay_revision(self, mac, command_type, snapshot_revision, instance_id=None):
        key = self._channel_key(mac, command_type, instance_id)
        pending = self._pending_overlay_commands.get(key)
        pending_revision = int(pending["revision"]) if pending else 0
        return max(int(snapshot_revision), pending_revision) + 1

    def _send_revisioned_payload(self, mac, command_type, revision, payload, instance_id=None):
        key = self._channel_key(mac, command_type, instance_id)
        envelope = {"revision": int(revision), "payload": dict(payload)}
        self._pending_overlay_commands[key] = envelope
        web_client.WEB_CLIENT.send_control(mac, envelope["payload"])
        return envelope["revision"]

    def retry_command(self, mac, command_type, instance_id=None):
        """Retry the latest envelope without allocating another revision."""
        key = self._channel_key(mac, command_type, instance_id)
        envelope = self._pending_overlay_commands.get(key)
        if not envelope:
            return None
        web_client.WEB_CLIENT.send_control(mac, dict(envelope["payload"]))
        return int(envelope["revision"])

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
            
        # --- EXHAUST FAN LOGIK ---
        elif cmd_type == "exhaust_fan":
            return self.send_exhaust_command(mac, **kwargs)
        elif cmd_type == "humidifier":
            return self.send_humidifier_command(mac, **kwargs)
            
        elif cmd_type == "light":
            return self.send_light_command(mac, **kwargs)
        elif cmd_type == "grow_controller":
            return self.send_grow_controller_command(mac, **kwargs)
        elif cmd_type == "plant_planner":
            return self.send_plant_planner_command(mac, **kwargs)
        elif cmd_type == "climate_hub":
            return self.send_climate_hub_command(mac, **kwargs)
        elif cmd_type == "ota_update":
            return self.send_ota_command(mac, **kwargs)
        return None

    # =========================================================================
    # VIRTUAL HUB HISTORY COMMANDS
    # =========================================================================

    @staticmethod
    def _history_source_device_id(mac):
        try:
            cfg = config._init()
            device = cfg.get("devices", {}).get(str(mac), {})
            source_device_id = str(
                device.get("device_id") or ""
            ).strip()
        except (AttributeError, TypeError):
            source_device_id = ""
        return source_device_id

    @staticmethod
    def _history_error_result(
        mac,
        mode,
        message,
        selection_id=None,
        target_revision=None,
    ):
        return HistorySelectionResult(
            key=(str(mac), str(mode)),
            status="failed",
            error=str(message),
            selection_id=selection_id,
            target_revision=target_revision,
        )

    def send_history_command(
        self,
        mac,
        mode,
        history_window=None,
        target_points=None,
        on_complete=None,
        force=False,
    ):
        """Send one Hub target through the sole project command path."""
        normalized_mode = str(mode or "").strip().casefold()
        if normalized_mode not in ("history", "live"):
            return self._history_error_result(
                mac,
                normalized_mode,
                "Ungültiger History-Modus.",
            )

        graph_engine = self.gsm.graph_engine
        base_state = graph_engine.get_history_control_state()
        if not isinstance(base_state, dict):
            return self._history_error_result(
                mac,
                normalized_mode,
                "Noch keine History-Basisrevision vom Hub empfangen.",
            )

        base_session = str(
            base_state.get("history_session") or ""
        ).strip()
        try:
            base_revision = int(base_state["rev_history"])
        except (KeyError, TypeError, ValueError):
            return self._history_error_result(
                mac,
                normalized_mode,
                "Ungültige History-Basisrevision vom Hub.",
            )

        selection_id = str(uuid.uuid4())
        source_device_id = self._history_source_device_id(mac)
        if not source_device_id:
            return self._history_error_result(
                mac,
                normalized_mode,
                "Stabile device_id für den Virtual Hub fehlt.",
                selection_id,
                base_revision + 1,
            )
        points = (
            graph_engine.HISTORY_TARGET_POINTS
            if target_points is None
            else int(target_points)
        )

        if normalized_mode == "history":
            if history_window is None:
                return self._history_error_result(
                    mac,
                    normalized_mode,
                    "History-Zeitfenster fehlt.",
                    selection_id,
                    base_revision + 1,
                )
            result = graph_engine.select_history_window(
                device_id=mac,
                history_window=history_window,
                selection_id=selection_id,
                base_revision=base_revision,
                base_session=base_session,
                force=force,
                target_points=points,
            )
            params = {
                "mode": "history",
                "from": history_window.start_timestamp,
                "to": history_window.end_timestamp,
                "points": points,
                "range_key": history_window.range_key,
            }
        else:
            result = graph_engine.select_live_mode(
                device_id=mac,
                selection_id=selection_id,
                base_revision=base_revision,
                base_session=base_session,
            )
            params = {"mode": "live"}

        if result.status != "loading":
            return result

        params.update(
            {
                "device_id": source_device_id,
                "selection_id": selection_id,
                "base_revision": base_revision,
                "base_session": base_session,
            }
        )
        command_key = self._channel_key(mac, "history")
        envelope = {
            "selection_id": selection_id,
            "mode": normalized_mode,
            "source_device_id": source_device_id,
            "base_revision": base_revision,
            "base_session": base_session,
            "result": result,
        }
        self._pending_history_commands[command_key] = envelope

        def finish(acknowledgement, transport_error):
            current = self._pending_history_commands.get(command_key)
            if (
                not current
                or current["selection_id"] != selection_id
            ):
                return

            error = transport_error
            if not error:
                error = self._validate_history_acknowledgement(
                    acknowledgement,
                    envelope,
                )
            graph_engine.complete_history_command(
                selection_id,
                error=error,
            )
            self._pending_history_commands.pop(command_key, None)
            if callable(on_complete):
                on_complete(result.key, error)

        web_client.WEB_CLIENT.send_history_command(
            mac,
            params,
            finish,
        )
        return result

    @staticmethod
    def _validate_history_acknowledgement(
        acknowledgement,
        envelope,
    ):
        if not isinstance(acknowledgement, dict):
            return "Ungültige History-Bestätigung vom Hub."
        if acknowledgement.get("status") != "selected":
            return str(
                acknowledgement.get("error")
                or "History-Auswahl wurde vom Hub nicht bestätigt."
            )
        if (
            str(acknowledgement.get("selection_id") or "")
            != envelope["selection_id"]
        ):
            return "History-Auswahlkennung der Bestätigung stimmt nicht."
        if (
            str(acknowledgement.get("device_id") or "")
            != envelope["source_device_id"]
        ):
            return "History-Gerätekennung der Bestätigung stimmt nicht."
        if acknowledgement.get("mode") != envelope["mode"]:
            return "History-Modus der Bestätigung stimmt nicht."
        if (
            str(acknowledgement.get("history_session") or "")
            != envelope["base_session"]
        ):
            return "History-Session der Bestätigung stimmt nicht."
        try:
            confirmed_revision = int(
                acknowledgement["rev_history"]
            )
        except (KeyError, TypeError, ValueError):
            return "History-Revision der Bestätigung fehlt."
        if confirmed_revision != envelope["base_revision"] + 1:
            return "History-Zielrevision der Bestätigung stimmt nicht."
        return None


    # =========================================================================
    # OTA UPDATE COMMANDS
    # =========================================================================

    def send_ota_command(self, mac, **kwargs):
        file_path = kwargs.get("file_path")
        new_ota_rev = int(kwargs.get("new_ota_rev", 1))
        on_progress = kwargs.get("on_progress")
        on_done = kwargs.get("on_done")

        if not file_path:
            if on_done: on_done(False, "Keine Bin-Datei ausgewaehlt!")
            return None

        payload = {
            "ota_rev": new_ota_rev
        }
        web_client.WEB_CLIENT.send_control(mac, payload)

        # 🔥 Hier stand vorher 'start_ota_upload'. Jetzt greift es fehlerfrei:
        web_client.WEB_CLIENT.start_ota_update(
            mac=mac, 
            file_path=file_path, 
            on_progress_callback=on_progress, 
            on_done_callback=on_done
        )
        
        return new_ota_rev

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
    
        snapshot_rev = int(
            current.get(
                "rev_plant_planner",
                pp.get("rev_plant_planner", 0),
            )
        )
        # Mehrere UI-Aktionen koennen vor dem naechsten Poll eintreffen.
        # Jede davon braucht trotzdem eine eigene, strikt steigende Revision.
        last_rev = max(snapshot_rev, self._pending_plant_revs.get(mac, 0))
        new_rev = last_rev + 1
        self._pending_plant_revs[mac] = new_rev
    
        payload = {"rev_plant_planner": new_rev}
        plant_payload = {}

        if "plant_updates" in kwargs:
            plant_payload["plant_updates"] = kwargs.get("plant_updates", [])
        else:
            plant_payload["plants"] = kwargs.get("plants", pp.get("plants", []))

        if plant_payload:
            payload["plant_planner"] = plant_payload
    
        web_client.WEB_CLIENT.send_control(mac, payload)
        print(f"[PlantPlanner] TARGET-REV -> {new_rev}")
        return new_rev    

    # =========================================================================
    # CLIMATE HUB COMMANDS
    # =========================================================================

    def _send_climate_hub_patch(self, mac, patch):
        """Send one module patch through the Climate Hub revision channel.

        ``rev_exhaust`` is retained only as the deployed WebDoc field name.
        The latest unconfirmed patch is accumulated so asynchronously sent
        requests cannot lose a lower revision when they arrive out of order.
        """
        current = self.get_latest_device_data(mac)
        snapshot_revision = int(current.get(CLIMATE_HUB_REVISION_KEY, 0))
        channel_key = self._channel_key(mac, "climate_hub")
        pending = self._pending_overlay_commands.get(channel_key)

        payload = {}
        if pending and int(pending["revision"]) > snapshot_revision:
            payload.update(pending["payload"])
        payload.pop(CLIMATE_HUB_REVISION_KEY, None)
        payload.update(patch)

        new_revision = self._next_overlay_revision(
            mac,
            "climate_hub",
            snapshot_revision,
        )
        payload[CLIMATE_HUB_REVISION_KEY] = new_revision
        self._send_revisioned_payload(
            mac,
            "climate_hub",
            new_revision,
            payload,
        )
        return new_revision

    def send_climate_hub_command(self, mac, **kwargs):
        """Update only Climate Hub targets and its Night Reduction policy."""
        current = self.get_latest_device_data(mac)
        patch = {
            "target_temp_min": round(float(kwargs.get("t_min", current.get("target_temp_min", 22.0))), 1),
            "target_temp_max": round(float(kwargs.get("t_max", current.get("target_temp_max", 28.0))), 1),
            "target_humidity_min": int(kwargs.get("h_min", current.get("target_humidity_min", 45))),
            "target_humidity_max": int(kwargs.get("h_max", current.get("target_humidity_max", 70))),
            "target_vpd_min": round(float(kwargs.get("vpd_min", current.get("target_vpd_min", 0.8))), 1),
            "target_vpd_max": round(float(kwargs.get("vpd_max", current.get("target_vpd_max", 1.5))), 1),
            "exhaust_fan_night_reduction": bool(
                kwargs.get(
                    "night_reduction",
                    current.get("exhaust_fan_night_reduction", True),
                )
            ),
        }
        new_revision = self._send_climate_hub_patch(mac, patch)
        print(f"[ClimateHub] TARGET-REV: {new_revision}")
        return new_revision

    # =========================================================================
    # EXHAUST FAN COMMANDS
    # =========================================================================

    def send_exhaust_command(self, mac, **kwargs):
        """Update only the Exhaust actuator configuration."""
        current = self.get_latest_device_data(mac)
        patch = {
            "exhaust_fan_min": int(kwargs.get("min", current.get("exhaust_fan_min", 20))),
            "exhaust_fan_pct": int(kwargs.get("max", current.get("exhaust_fan_pct", 65))),
            "exhaust_fan_mode": kwargs.get("mode", current.get("exhaust_fan_mode", "auto")),
            "exhaust_fan_chaos": bool(kwargs.get("chaos", current.get("exhaust_fan_chaos_active", False))),
        }
        new_revision = self._send_climate_hub_patch(mac, patch)
        print(f"[Exhaust] TARGET-REV: {new_revision} | Mode: {patch['exhaust_fan_mode']}")
        return new_revision

    # =========================================================================
    # CIRCULATION FAN COMMANDS
    # =========================================================================

        
    def send_fan_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac)
        fan_id = int(kwargs.get("fan_id", 1))
        prefix = fan_prefix(fan_id)
        revision_key = fan_revision_key(fan_id)
        last = int(current.get(revision_key, 0))
        new_rev = self._next_overlay_revision(mac, "circulation_fan", last, instance_id=fan_id)
        
        payload = {
            f"{prefix}_min": int(kwargs.get("min", 20)),
            f"{prefix}_pct": int(kwargs.get("max", 65)),
            f"{prefix}_mode": kwargs.get("mode", "nat"),
            revision_key: new_rev
        }
        
        self._send_revisioned_payload(mac, "circulation_fan", new_rev, payload, instance_id=fan_id)
        return new_rev 

    # =========================================================================
    # HUMIDIFIER COMMANDS
    # =========================================================================

    def send_humidifier_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac) or {}
        snapshot_revision = int(current.get("rev_humidifier", 0) or 0)
        current_target = current.get("humidifier_pct")
        if current_target is None:
            current_target = 60
        target_pct = max(0, min(100, int(kwargs.get("pct", current_target))))
        new_revision = self._next_overlay_revision(
            mac,
            "humidifier",
            snapshot_revision,
        )
        payload = {
            "humidifier_pct": target_pct,
            "rev_humidifier": new_revision,
        }
        self._send_revisioned_payload(
            mac,
            "humidifier",
            new_revision,
            payload,
        )
        return new_revision

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
            "p_e_fan",
            "p_e_tac",

            "p_humidifier",

            "p_light",

            "p_i2c_sda",
            "p_i2c_scl",

            "p_rtc_sda",
            "p_rtc_scl",

            "p_bat",
        ]
        for fan_id in range(1, MAX_CIRCULATION_FANS + 1):
            pwm, tacho, _ = fan_gpio_keys(fan_id)
            gpio_keys.extend((pwm, tacho))


        for key in gpio_keys:
            if key in merged_gpios:
                payload[key] = int(merged_gpios.get(key, -1))

        pull_keys = [
            "p_e_tac_pull",
            "p_bat_pull",
        ]
        pull_keys.extend(fan_gpio_keys(fan_id)[2] for fan_id in range(1, MAX_CIRCULATION_FANS + 1))

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
        # BLE-Zustände sind unabhängige Patches. Unbeteiligte Grow-Befehle dürfen
        # keinen möglicherweise veralteten Zustand zurück an den ESP schreiben.
        if "ble_bridge" in kwargs:
            payload["ble_bridge"] = bool(kwargs["ble_bridge"])

        if "ble_scan" in kwargs:
            payload["ble_scan"] = bool(kwargs["ble_scan"])

        # Abfahrt an den Web-Client
        web_client.WEB_CLIENT.send_control(mac, payload)
        return new_rev



    def send_light_command(self, mac, **kwargs):
        current = self.get_latest_device_data(mac)
        last = int(current.get("rev_light", 0))
        new_rev = self._next_overlay_revision(mac, "light", last)
        
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
        
        self._send_revisioned_payload(mac, "light", new_rev, payload)
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
