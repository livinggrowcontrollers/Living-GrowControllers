#!/usr/bin/env python3
# -*- coding: utf-8 -*-
###############################################################################
# !!! ABSOLUTES GESETZ v2.0: HYBRIDE STABILITÄT & RAM-DOMINANZ !!!
# -----------------------------------------------------------------------------
# 0. SINGLE SOURCE OF TRUTH (DIE QUELLE)
#    Der Decoder ist der alleinige Herrscher über den Systemstatus. 
#    UI und Engines lesen NUR die 'decoded.json'. Der Decoder liest für WEB
#    direkt aus dem RAM (_LIVE_WEB_DATA) – die Festplatte ist für WEB-Validierung tot.
#
# -----------------------------------------------------------------------------
# 1. RAM-INJEKTION VOR DISK-I/O
#    Web-Daten fließen per Direkt-Injektion in den Arbeitsspeicher. 
#    Ein langsames Dateisystem (SD-Karte/Android-I/O) darf niemals die 
#    Aktualität der Daten bremsen oder Flackern verursachen.
#
# -----------------------------------------------------------------------------
# 2. AUTONOME TIMEOUT-HOHEIT (DAS ENDE DES FLACKERNS)
#    Der Decoder berechnet den Offline-Status für WEB-Geräte SELBSTSTÄNDIG:
#    (Aktuelle_Zeit - Paket_Zeitstempel) > config.stale_timeout.
#    Der externe Watchdog-Status wird für WEB ignoriert, um Fehlalarme 
#    durch Netzwerk-Latenz zu eliminieren.
#
# -----------------------------------------------------------------------------
# 3. KANAL-ISOLATION & GNADENFRIST
#    Ein stockender Web-Request darf weder die BLE-Daten (ADV/GATT) stören, 
#    noch das Gerät sofort auf "offline" reißen. Solange der Cache innerhalb 
#    der Config-Zeit liegt, bleibt der Status "active".
#
# -----------------------------------------------------------------------------
# 4. LAST-GOOD-DATA (KEIN DATENVAKUUM)
#    Bei einem misslungenen Request oder korrupten Paket wird zwingend der 
#    letzte gültige Stand aus dem RAM-Cache serviert. "Leere" Frames 
#    zwischen zwei erfolgreichen Updates sind streng verboten.
#
# -----------------------------------------------------------------------------
# 5. ATOMARE KONSISTENZ
#    Die 'decoded.json' wird nur geschrieben, wenn der Frame in sich logisch ist.
#    Mischmasch aus uralten Web-Daten und frischen BLE-Daten wird durch 
#    individuelle Zeitstempel pro Kanal innerhalb des Objekts verhindert.
#
# -----------------------------------------------------------------------------
# 6. VERBOTENE MUSTER (TODSÜNDEN)
#    ❌ Watchdog sagt "offline" -> sofortiges Ausgrauen in der UI (WEB-Kanal)
#    ❌ config.stale_timeout ignorieren oder hartcodieren
#    ❌ Direktes Lesen der web_dump.json für die Status-Logik
#
# -----------------------------------------------------------------------------
# 7. ERLAUBTE MUSTER (GOLD STANDARD)
#    ✅ RAM-Cache (_LAST_WEB) als primäre Validierung
#    ✅ 'now - timestamp' gegen Config-Wert prüfen
#    ✅ Den Watchdog nur noch für passive Kanäle (BLE) als Berater nutzen
#
###############################################################################

import os
import json
import time
import threading

from platform_utils import is_android
import config
from ble_watchdog_manager import BleDumpWatchdog
import csv
# Submodule importieren
from decoders import binary_parser
from decoders.channel_decoder import decode_channel
from decoders.frame_factory import offline_channel_frame, offline_frame
import calculator 

# --- PFAD-LOGIK ---
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

if is_android():
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ctx = PythonActivity.mActivity
    DATA = os.path.join(ctx.getFilesDir().getAbsolutePath(), "app", "data")

RAW_FILE = os.path.join(DATA, "ble_dump.json")
DEC_FILE = os.path.join(DATA, "decoded.json")
PROFILES = os.path.join(DATA, "decoder_profiles")
CSV_FILE = os.path.join(DATA, "log.csv")

os.makedirs(DATA, exist_ok=True)
os.makedirs(PROFILES, exist_ok=True)

# Parser über Pfade informieren
binary_parser.set_profiles_path(PROFILES)

# Geteilte Zustände
BRIDGE_ALIVE = True
BRIDGE_STATUS = "OK"
BRIDGE_LAST_SEEN = None
UPTIME_START = None

_LAST_ADV_RAW, _LAST_ADV_TS = {}, {}
_LAST_GATT_RAW, _LAST_GATT_TS = {}, {}
_LAST_WEB = {}
_LAST_CHANNEL_RSSI = {"adv": {}, "gatt": {}, "webserver": {}}
_LAST_WRITE_TS = 0


_DECODED_RAM = []
_DECODED_TS = 0
_LAST_LOG_TS = 0.0
_LOG_INTERVAL = 5
_LIVE_WEB_DATA = {} 
LIVE_WEB_LOCK = threading.Lock()
def _valid_rssi(val):
    return val is not None and val > -250 and val != -256


def _normalize_channel_rssi(mac, channel_name, channel_frame):
    """Keep the last valid RSSI while its decoded channel remains alive.

    Bluetooth producers are allowed to omit RSSI from individual packets.
    That omission is not a signal loss and must not change dashboard tile
    visibility.  A real channel timeout still clears the cached value.
    """
    cache = _LAST_CHANNEL_RSSI[channel_name]
    if not channel_frame.get("alive"):
        cache.pop(mac, None)
        channel_frame["rssi"] = None
        return None

    value = channel_frame.get("rssi")
    if _valid_rssi(value):
        cache[mac] = value
    else:
        value = cache.get(mac)
    channel_frame["rssi"] = value
    return value
watchdog = BleDumpWatchdog(timeout=config.get_stale_timeout(), interval=1.0, callback=lambda x: x)


ERR256 = -256

def valid_value(value):
    """
    Liefert True sobald ein Wert technisch vorhanden ist.
    Nur -256 gilt als 'nicht vorhanden'.
    0 ist gültig.
    False ist gültig.
    """
    return value is not None and value != ERR256

def inject_web_data(mac, payload):
    global _LIVE_WEB_DATA
    with LIVE_WEB_LOCK:
        _LIVE_WEB_DATA[mac] = payload

def update_bridge_state(alive, status, last_seen):
    global BRIDGE_ALIVE, BRIDGE_STATUS, BRIDGE_LAST_SEEN
    BRIDGE_ALIVE = alive
    BRIDGE_STATUS = status
    BRIDGE_LAST_SEEN = last_seen


def _write(frames):
    global _DECODED_RAM
    global _DECODED_TS
    global _LAST_WRITE_TS
    global _LAST_LOG_TS

    now = time.time()

    # RAM immer sofort
    _DECODED_RAM = frames
    _DECODED_TS = now

    # Disk nur alle 60 Sekunden
    if (now - _LAST_WRITE_TS) >= 60.0:
        try:
            with open(DEC_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    frames,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            _LAST_WRITE_TS = now

        except Exception as e:
            print("[Decoder] Write Error:", e)

    if _dev_enabled():
        if (now - _LAST_LOG_TS) >= _LOG_INTERVAL:
            _write_csv(frames)
            globals()["_LAST_LOG_TS"] = now
    else:
        _cleanup_csv()

def offline_all(cfg):
    now = time.time()
    frames = [offline_frame(mac, now, BRIDGE_ALIVE, BRIDGE_STATUS, BRIDGE_LAST_SEEN) for mac in cfg.get("devices", {}).keys()]
    _write(frames)

def step_decode():
    global UPTIME_START, _LAST_ADV_RAW, _LAST_GATT_RAW, _LAST_WEB, _LIVE_WEB_DATA, _LAST_LOG_TS
    
    cfg = config._init()
    devs = cfg.get("devices", {})
    
    # --- HARD RESET GATE (VERHINDERT GHOST REGENERATION) ---
    if not devs:
        _LIVE_WEB_DATA.clear()
        _LAST_WEB.clear()
        for channel_cache in _LAST_CHANNEL_RSSI.values():
            channel_cache.clear()
        _LAST_GATT_RAW.clear()
        _LAST_GATT_TS.clear()
        _LAST_ADV_RAW.clear()
        _LAST_ADV_TS.clear()
        print("[Decoder] CONFIG EMPTY → FULL RUNTIME RESET")    
        return

    now = time.time()
    if UPTIME_START is None: UPTIME_START = now

    # --- 0. CACHE BEREINIGUNG (GEISTER-DEVICES LÖSCHEN) ---
    active_macs = set(devs.keys())
    for cached_mac in list(_LAST_WEB.keys()):
        if cached_mac not in active_macs:
            _LAST_WEB.pop(cached_mac, None)
            _LAST_GATT_RAW.pop(cached_mac, None)
            _LAST_GATT_TS.pop(cached_mac, None)
            _LAST_ADV_RAW.pop(cached_mac, None)
            _LAST_ADV_TS.pop(cached_mac, None)
            for channel_cache in _LAST_CHANNEL_RSSI.values():
                channel_cache.pop(cached_mac, None)
            with LIVE_WEB_LOCK:
                _LIVE_WEB_DATA.pop(cached_mac, None)
            print(f"[Decoder] Cleaned stale device cache for deleted MAC: {cached_mac}")

    for channel_cache in _LAST_CHANNEL_RSSI.values():
        for cached_mac in list(channel_cache):
            if cached_mac not in active_macs:
                channel_cache.pop(cached_mac, None)
    
    # --- DIAGNOSE HEARTBEAT ---
    if now - _LAST_LOG_TS >= 60.0: 
        _LAST_LOG_TS = now
        devs_in_cfg = list(devs.keys()) if devs else []
        print(f"[HEARTBEAT DECODER] Ticking! Active Config Devices: {devs_in_cfg} | Live Web RAM Keys: {list(_LIVE_WEB_DATA.keys())}")

    # 1. WATCHDOG LADEN
    w_res = watchdog.check_status()
    w_devs = w_res.get("devices", {})

    # BLE Daten laden
    ble_list = []
    if os.path.exists(RAW_FILE):
        try:
            with open(RAW_FILE, "r") as f: 
                ble_list = json.load(f)
        except: pass
    
    # 2. WEB DATEN LADEN (RAM + DISK BACKUP)
    with LIVE_WEB_LOCK:
        web_data = _LIVE_WEB_DATA.copy()
    if not web_data:
        web_dump_path = os.path.join(DATA, "web_dump.json")
        if os.path.exists(web_dump_path):
            try:
                with open(web_dump_path, "r") as f: 
                    web_data = json.load(f)
            except: pass

    by_mac = {e.get("address"): e for e in ble_list if isinstance(e, dict) and e.get("address")}
    timeout = float(config.get_stale_timeout())
    frames = []

    for mac, dev_cfg in devs.items():
        entry = by_mac.get(mac)
        w_status = w_devs.get(mac, {})
        unit = f"°{config.get_temperature_unit().upper()}"

        # --- KANAL 1: ADV ---
        adv_w = w_status.get("adv", {"alive": False})
        adv_dec = offline_channel_frame(entry.get("adv_raw") if entry else None)
        if adv_w["alive"]:
            res = decode_channel(entry, "adv_raw", dev_cfg.get("adv_decoder"), _LAST_ADV_RAW, _LAST_ADV_TS, timeout) if entry else None
            if res and res["alive"]:
                adv_dec = res
                _LAST_ADV_RAW[mac] = entry.get("adv_raw")
            elif mac in _LAST_ADV_RAW:
                adv_dec = decode_channel({"address": mac, "adv_raw": _LAST_ADV_RAW[mac]}, "adv_raw", dev_cfg.get("adv_decoder"), _LAST_ADV_RAW, _LAST_ADV_TS, timeout)

        # --- KANAL 2: GATT (REPARIERT & KUGELSICHER) ---
        raw_from_entry = entry.get("gatt_raw") if entry else None
        gatt_dec = offline_channel_frame(raw_from_entry)

        # GATT validity is established by its own packet/raw timeout in
        # decode_channel.  A watchdog status is metadata only and must never
        # discard a freshly received gatt_raw payload.
        if entry and raw_from_entry:
            res = decode_channel(entry, "gatt_raw", dev_cfg.get("gatt_decoder"), _LAST_GATT_RAW, _LAST_GATT_TS, timeout, is_gatt=True)
            if res and res["alive"]:
                gatt_dec = res
                _LAST_GATT_RAW[mac] = raw_from_entry

        # Wenn der Kanal gerade tot ist, zieh den JOKER aus dem RAM
        if not gatt_dec["alive"] and mac in _LAST_GATT_RAW:
            gold_data = _LAST_GATT_RAW[mac]
            res_cache = decode_channel({"address": mac, "gatt_raw": gold_data}, "gatt_raw", dev_cfg.get("gatt_decoder"), _LAST_GATT_RAW, _LAST_GATT_TS, timeout, is_gatt=True)
            if res_cache and res_cache["alive"]:
                gatt_dec = res_cache

        # --- KANAL 3: WEBSERVER (REPARIERT & STRUKTURIERT) ---
        web_raw = web_data.get(mac)
        if web_raw: 
            _LAST_WEB[mac] = web_raw 

        current_web = _LAST_WEB.get(mac)
        web_alive = False
        if current_web:
            web_ts = current_web.get("timestamp")
            if web_ts and (now - web_ts) < timeout:
                web_alive = True

        # Basisdaten aufbauen
        web_dec = {
            "alive": web_alive,
            "status": "active" if web_alive else "offline",
            "timestamp": current_web.get("timestamp") if current_web else None,
            "dev_name": current_web.get("dev_name", dev_cfg.get("name", mac)) if current_web else dev_cfg.get("name", mac),
            "fw_ver": current_web.get("fw_ver", "unknown") if current_web else "unknown",
            "ip": current_web.get("ip", "0.0.0.0") if current_web else "0.0.0.0",
            "ssid": current_web.get("ssid", "unknown") if current_web else "unknown"
        }

        if current_web:
            web_dec.update({
                "target_temp_min": current_web.get("target_temp_min"),
                "target_temp_max": current_web.get("target_temp_max"),
                "target_humidity_min": current_web.get("target_humidity_min"),
                "target_humidity_max": current_web.get("target_humidity_max"),
                "target_vpd_min": current_web.get("target_vpd_min"),
                "target_vpd_max": current_web.get("target_vpd_max"),
                "exhaust_fan_mode": current_web.get("exhaust_fan_mode", "auto"),
                "circulation_fan_mode": current_web.get("circulation_fan_mode", "nat"),
                "plant_phase": current_web.get("plant_phase", 0),
                "plant_planner": current_web.get("plant_planner", {}),
                "gpios": current_web.get("gpios", {})
            })

        # Nur wenn der Webserver ECHT online ist, Telemetrie berechnen
        if web_alive and current_web:
            raw_t_in = current_web.get("temp_in")
            raw_h_in = current_web.get("humid_in")
            raw_t_e  = current_web.get("temp_ext")
            raw_h_e  = current_web.get("humid_ext")
            raw_t_l  = current_web.get("leaf_temp")

            internal_exists = valid_value(raw_t_in)
            sensor_exists   = valid_value(raw_t_e)
            leaf_exists     = valid_value(raw_t_l)

            t_i_final = raw_t_in if internal_exists else None
            h_i_final = raw_h_in if internal_exists else None
            t_e_final = raw_t_e if sensor_exists else None
            h_e_final = raw_h_e if sensor_exists else None

            # Offsets anwenden & berechnen
            T_i, H_i, T_e, H_e = calculator.apply_offsets(t_i_final, h_i_final, t_e_final, h_e_final)
            
            vpdi = calculator.vpd_internal(T_i, H_i)
            vpde = calculator.vpd_external(T_e, H_e)
            dpi  = calculator.dew_point_internal(T_i, H_i)
            dpe  = calculator.dew_point_external(T_e, H_e)
            xi, yi = calculator.vpd_coord_internal(T_i, H_i)
            xe, ye = calculator.vpd_coord_external(T_e, H_e)

            # Strukturierte Telemetrie-Injektion
            web_dec.update({
                "internal": {
                    "temperature": {"value": calculator.to_unit(T_i), "unit": unit}, 
                    "humidity": {"value": H_i, "unit": "%"},
                },
                "external": {
                    "present": sensor_exists,
                    "temperature": {"value": calculator.to_unit(T_e), "unit": unit}, 
                    "humidity": {"value": H_e, "unit": "%"},
                },
                "vpd_internal": {"value": vpdi, "unit": "kPa"},
                "vpd_external": {"value": vpde, "unit": "kPa"},
                "dew_point_internal": {"value": calculator.to_unit(dpi), "unit": unit},
                "dew_point_external": {"value": calculator.to_unit(dpe), "unit": unit},
                "coord": {
                    "internal": {"x": xi, "y": yi}, 
                    "external": {"x": xe if sensor_exists else None, "y": ye if sensor_exists else None}
                },
                "battery_voltage": current_web.get("vbat"),
                "circulation_fan": {
                    "circulation_fan_rpm": current_web.get("circulation_fan_rpm", 0),
                    "unit": "RPM"
                },
                "exhaust_fan": {
                    "exhaust_fan_rpm": current_web.get("exhaust_fan_rpm", 0),
                    "unit": "RPM"
                },
                "exhaust_fan_pct": current_web.get("exhaust_fan_pct", 0),
                "circulation_fan_pct": current_web.get("circulation_fan_pct", 0),
                "humidifier_pct": current_web.get("humidifier_pct"),
                "humidifier_speed_now": current_web.get("humidifier_speed_now"),
                "humidifier_status": current_web.get("humidifier_status"),
                "rev_humidifier": current_web.get("rev_humidifier", 0),
                "light_pct": current_web.get("light_pct", 0),
                "light_mode": current_web.get("light_mode", "off"),
                "uptime_esp_s": current_web.get("uptime_esp_s", 0),
                "free_heap": current_web.get("free_heap", 0),
                "rssi": current_web.get("rssi", None)
            })

            # Blatt-Logik
            if leaf_exists:
                ref_t = T_e if sensor_exists else T_i
                ref_h = H_e if sensor_exists else H_i
                vpd_l = calculator.vpd_leaf(raw_t_l, ref_t, ref_h)
                web_dec["external2"] = {
                    "present": True,
                    "leaf_temp": {"value": calculator.to_unit(raw_t_l), "unit": unit},
                    "vpd_leaf": {"value": vpd_l, "unit": "kPa"}
                }
            else:
                web_dec["external2"] = {"present": False, "leaf_temp": {"value": None, "unit": unit}, "vpd_leaf": {"value": None, "unit": "kPa"}}

            # BLE-Sensoren
            ble_block = current_web.get("ble_sensors", {})
            ble_out = {"discovered_devices": ble_block.get("discovered_devices", [])}
            
            for side in ["outside", "inside"]:
                side_data = ble_block.get(side, {})
                if side_data.get("online"):
                    t = side_data.get("ble_temp_" + side) or (side_data["temperature"].get("value") if isinstance(side_data.get("temperature"), dict) else None)
                    h = side_data.get("ble_humid_" + side) or (side_data["humidity"].get("value") if isinstance(side_data.get("humidity"), dict) else None)
                    
                    if t is not None and h is not None:
                        T_ble, H_ble, _, _ = calculator.apply_offsets(t, h, None, None)
                        ble_out[side] = {
                            "online": True,
                            "temperature": {"value": calculator.to_unit(T_ble), "unit": unit},
                            "humidity": {"value": H_ble, "unit": "%"},
                            "vpd": {"value": calculator._vpd(T_ble, H_ble), "unit": "kPa"},
                            "coord": {"x": calculator.vpd_coord_internal(T_ble, H_ble)[0], "y": calculator.vpd_coord_internal(T_ble, H_ble)[1]},
                            "mac": side_data.get("mac", "00:00:00:00:00:00"),
                            "name": side_data.get("name", "")
                        }
                    else:
                        ble_out[side] = {"online": False}
                else:
                    ble_out[side] = {"online": False}
            
            web_dec["ble_sensors"] = ble_out

            # ================================================
            # FAULHEITS-FILTER (Zukunftssicherungs-Loop)
            # ================================================
            BLACKLIST = {
                "temp_in", "humid_in", "temp_ext", "humid_ext", "leaf_temp", 
                "vbat", "rssi", "uptime_esp_s", "free_heap", "ble_sensors",
                "circulation_fan_rpm", "exhaust_fan_rpm", "rssi", "circulation_fan_pct", "exhaust_fan_pct",
                "humidifier_pct", "humidifier_speed_now", "humidifier_status", "rev_humidifier", "light_pct", "light_mode",
                "target_temp_min", "target_temp_max", "target_humidity_min", "target_humidity_max", "target_vpd_min", "target_vpd_max", "exhaust_fan_mode", "circulation_fan_mode", "plant_phase", "plant_planner"
                
            }

            for key, value in current_web.items():
                if key not in BLACKLIST and key not in web_dec:
                    web_dec[key] = value
        else:
            # FALLBACK Struktur bei Offline-Webserver
            web_dec.update({
                "internal": {"temperature": {"value": None, "unit": unit}, "humidity": {"value": None, "unit": "%"}},
                "external": {"present": False, "temperature": {"value": None, "unit": unit}, "humidity": {"value": None, "unit": "%"}},
                "external2": {"present": False, "leaf_temp": {"value": None, "unit": unit}, "vpd_leaf": {"value": None, "unit": "kPa"}},
                "ble_sensors": {"discovered_devices": [], "outside": {"online": False}, "inside": {"online": False}},
                "vpd_internal": {"value": None, "unit": "kPa"},
            })

        # --- FINAL MERGE (KOMPLETTE ORIGINAL-STRUKTUR) ---
        adv_rssi = _normalize_channel_rssi(mac, "adv", adv_dec)
        gatt_rssi = _normalize_channel_rssi(mac, "gatt", gatt_dec)
        web_rssi = _normalize_channel_rssi(mac, "webserver", web_dec)
        final_rssi = web_rssi if web_rssi is not None else gatt_rssi if gatt_rssi is not None else adv_rssi

        is_alive = any([adv_dec["alive"], gatt_dec["alive"], web_dec["alive"]])

        def scrub_256(obj):
            if isinstance(obj, dict):
                return {k: scrub_256(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [scrub_256(v) for v in obj]
            if obj == -256:
                return None
            return obj

        web_dec = scrub_256(web_dec)


        frames.append({
            "timestamp": now,
            "device_id": mac,
            "name": web_dec["dev_name"],
            "adv": adv_dec,
            "gatt": gatt_dec,
            "webserver": web_dec,
            "bridge_alive": BRIDGE_ALIVE,
            "bridge_status": BRIDGE_STATUS,
            "bridge_last_seen": BRIDGE_LAST_SEEN,
            "alive": is_alive,
            "status": "active" if is_alive else "offline",
            "health": {
                "uptime": {"value": now - UPTIME_START, "unit": "s"},
                "battery": {"value": None, "unit": "V", "voltage": web_dec.get("battery_voltage") or adv_dec.get("battery_voltage") or gatt_dec.get("battery_voltage")},
                "signal": {"rssi": final_rssi, "unit": "dBm"}
            },
            "device_online": is_alive and web_alive,
            "web_alive": web_alive,
        })
    _write(frames)
    
def get_decoded_ram():
    return _DECODED_RAM


def _dev_enabled():
    try:
        return config.is_developer_mode()
    except Exception:
        return False
    
def _cleanup_csv():
    if os.path.exists(CSV_FILE):
        try:
            os.remove(CSV_FILE)
        except Exception:
            pass

def _write_csv(frames):
    file_exists = os.path.exists(CSV_FILE)
    
    # Hier holen wir die aktuelle Config, um die Namen zu parsen
    try:
        cfg = config._init()
        devs = cfg.get("devices", {})
    except Exception:
        devs = {}

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            # Der Header mit den von der UI erwarteten Keys
            writer.writerow([
                "timestamp",
                "device_id",
                "name",         # Die UI sucht nach 'name'
                "T_i",          # Passend zu self.colors
                "H_i",
                "T_e",
                "H_e",
                "light",
                "exhaust",
                "circulation"
            ])

        for frame in frames:
            web = frame.get("webserver", {})
            mac = frame.get("device_id")
            
            # PARSING des Namens aus der Config anhand der MAC/device_id
            device_name = devs.get(mac, {}).get("name", mac)

            writer.writerow([
                frame.get("timestamp"),
                mac,
                device_name,    # Name wird jetzt hier fest eingetragen

                web.get("internal", {}).get("temperature", {}).get("value"),
                web.get("internal", {}).get("humidity", {}).get("value"),

                web.get("external", {}).get("temperature", {}).get("value"),
                web.get("external", {}).get("humidity", {}).get("value"),

                web.get("light_pct"),
                web.get("exhaust_fan_pct"),
                web.get("circulation_fan_pct"),
            ])

# --- THREAD CONTROL FOR ASYNC RUNTIME ---
_DECODER_THREAD = None
_DECODER_RUNNING = False

def _decoder_loop(interval=1.0):
    global _DECODER_RUNNING
    print("[Decoder] Background Thread STARTED.")
    while _DECODER_RUNNING:
        try:
            step_decode()
        except Exception as e:
            print(f"[Decoder Exception in Loop]: {e}")
        time.sleep(interval)
    print("[Decoder] Background Thread STOPPED.")

def start_decoder_thread(interval=1.0):
    global _DECODER_THREAD, _DECODER_RUNNING
    if _DECODER_RUNNING:
        print("[Decoder] Thread läuft bereits.")
        return
    _DECODER_RUNNING = True
    _DECODER_THREAD = threading.Thread(target=_decoder_loop, args=(interval,), daemon=True)
    _DECODER_THREAD.start()

def stop_decoder_thread():
    global _DECODER_RUNNING
    _DECODER_RUNNING = False
