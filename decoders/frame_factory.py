# -*- coding: utf-8 -*-
import time
import config
import calculator
from dashboard_gui.circulation_fan_registry import add_normalized_fans
from decoders.binary_parser import load_profile, decode_with_profile

def offline_channel_frame(raw_hex=None):
    unit = f"°{config.get_temperature_unit().upper()}"
    return {
        "alive": False,
        "status": "offline",
        "packet_counter": None,
        "raw": raw_hex,
        "rssi": None,
        "internal": {
            "temperature": {"value": None, "unit": unit},
            "humidity": {"value": None, "unit": "%"}
        },
        "external": {
            "present": False,
            "temperature": {"value": None, "unit": unit},
            "humidity": {"value": None, "unit": "%"}
        },
        "external2": {
            "present": False,
            "leaf_temp": {"value": None, "unit": unit},
            "vpd_leaf": {"value": None, "unit": "kPa"}
        },
        "vpd_internal": {"value": None, "unit": "kPa"},
        "vpd_external": {"value": None, "unit": "kPa"},
        "battery_voltage": None,
        "dew_point_internal": {"value": None, "unit": unit},
        "dew_point_external": {"value": None, "unit": unit},
        "coord": {
            "internal": {"x": None, "y": None},
            "external": {"x": None, "y": None}
        }
    }
def build_active_ble_frame(decoded, entry, unit):
    T_i, H_i, T_e, H_e = calculator.apply_offsets(
        decoded["T_i"], decoded["H_i"], decoded["T_e"], decoded["H_e"]
    )
    xi, yi = calculator.vpd_coord_internal(T_i, H_i)
    xe, ye = calculator.vpd_coord_external(T_e, H_e)
    dpi = calculator.dew_point_internal(T_i, H_i)
    dpe = calculator.dew_point_external(T_e, H_e)
    
    T_l = decoded.get("T_l")
    vpd_l_val = None
    if T_l is not None and decoded["T_e"] is not None and decoded["H_e"] is not None:
        svp_l = 0.61078 * (10**((7.5 * T_l) / (237.3 + T_l)))
        svp_e = 0.61078 * (10**((7.5 * decoded["T_e"]) / (237.3 + decoded["T_e"])))
        avp_e = svp_e * (decoded["H_e"] / 100.0)
        vpd_l_val = round(svp_l - avp_e, 3)

    return {
        "alive": True, "status": "active", "packet_counter": entry.get("packet_counter"), "raw": decoded["raw"],
        "internal": {"temperature": {"value": calculator.to_unit(T_i), "unit": unit}, "humidity": {"value": H_i, "unit": "%"}},
        "external": {"present": decoded["T_e"] is not None, "temperature": {"value": calculator.to_unit(T_e), "unit": unit}, "humidity": {"value": H_e, "unit": "%"}},
        "external2": {"present": T_l is not None, "leaf_temp": {"value": calculator.to_unit(T_l), "unit": unit}, "vpd_leaf": {"value": vpd_l_val, "unit": "kPa"}},
        "vpd_internal": {"value": calculator.vpd_internal(T_i, H_i), "unit": "kPa"},
        "vpd_external": {"value": calculator.vpd_external(T_e, H_e), "unit": "kPa"},
        "battery_voltage": decoded.get("V_b"),
        "dew_point_internal": {"value": calculator.to_unit(dpi), "unit": unit},
        "dew_point_external": {"value": calculator.to_unit(dpe), "unit": unit},
        "coord": {"internal": {"x": xi, "y": yi}, "external": {"x": xe, "y": ye}}
    }

def build_web_telemetry(web_dec, current_web, unit):
    ERR_VAL = -250.0
    raw_t_in = current_web.get("temp_in")
    raw_h_in = current_web.get("humid_in")
    raw_t_e  = current_web.get("temp_ext")
    raw_h_e  = current_web.get("humid_ext")
    raw_t_l  = current_web.get("leaf_temp")
    raw_rssi = current_web.get("rssi")


    internal_exists = (raw_t_in is not None and raw_t_in > ERR_VAL)
    sensor_exists   = (raw_t_e is not None and raw_t_e > ERR_VAL)
    leaf_exists     = (raw_t_l is not None and raw_t_l > ERR_VAL)

    t_i_final = raw_t_in if internal_exists else None
    h_i_final = raw_h_in if internal_exists else None
    t_e_final = raw_t_e if sensor_exists else None
    h_e_final = raw_h_e if sensor_exists else None

    T_i, H_i, T_e, H_e = calculator.apply_offsets(t_i_final, h_i_final, t_e_final, h_e_final)
    
    vpdi = calculator.vpd_internal(T_i, H_i)
    vpde = calculator.vpd_external(T_e, H_e)
    dpi  = calculator.dew_point_internal(T_i, H_i)
    dpe  = calculator.dew_point_external(T_e, H_e)
    xi, yi = calculator.vpd_coord_internal(T_i, H_i)
    xe, ye = calculator.vpd_coord_external(T_e, H_e)

    web_dec.update({
        "internal": {"temperature": {"value": calculator.to_unit(T_i), "unit": unit}, "humidity": {"value": H_i, "unit": "%"}},
        "external": {"present": sensor_exists, "temperature": {"value": calculator.to_unit(T_e), "unit": unit}, "humidity": {"value": H_e, "unit": "%"}},
        "vpd_internal": {"value": vpdi, "unit": "kPa"}, "vpd_external": {"value": vpde, "unit": "kPa"},
        "dew_point_internal": {"value": calculator.to_unit(dpi), "unit": unit}, "dew_point_external": {"value": calculator.to_unit(dpe), "unit": unit},
        "coord": {"internal": {"x": xi, "y": yi}, "external": {"x": xe if sensor_exists else None, "y": ye if sensor_exists else None}},
        "battery_voltage": current_web.get("vbat"),
        "circulation_fan": {"circulation_fan_rpm": current_web.get("circulation_fan_rpm", 0), "unit": "RPM"},
        "exhaust_fan": {"exhaust_fan_rpm": current_web.get("exhaust_fan_rpm", 0), "unit": "RPM"},
        "exhaust_fan_pct": current_web.get("exhaust_fan_pct", 0), "circulation_fan_pct": current_web.get("circulation_fan_pct", 0),
        "humidifier_pct": current_web.get("humidifier_pct"),
        "humidifier_speed_now": current_web.get("humidifier_speed_now"),
        "humidifier_status": current_web.get("humidifier_status"),
        "rev_humidifier": current_web.get("rev_humidifier", 0),
        "light_pct": current_web.get("light_pct", 0), "light_mode": current_web.get("light_mode", "off"),
        "uptime_esp_s": current_web.get("uptime_esp_s", 0), "free_heap": current_web.get("free_heap", 0),
        
        "rssi": {
            "value": raw_rssi if _valid_rssi(raw_rssi) else None,
            "unit": "dBm"
        } if _valid_rssi(raw_rssi) else None,
        "signal_quality": {"value": current_web.get("signal_quality"), "unit": "%"}
    })

    if leaf_exists:
        ref_t = T_e if sensor_exists else T_i
        ref_h = H_e if sensor_exists else H_i
        vpd_l = calculator.vpd_leaf(raw_t_l, ref_t, ref_h)
        web_dec["external2"] = {"present": True, "leaf_temp": {"value": calculator.to_unit(raw_t_l), "unit": unit}, "vpd_leaf": {"value": vpd_l, "unit": "kPa"}}
    else:
        web_dec["external2"] = {"present": False, "leaf_temp": {"value": None, "unit": unit}, "vpd_leaf": {"value": None, "unit": "kPa"}}

    # BLE Sensoren Verzweigung innerhalb des Web-Pakets
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
                    "online": True, "temperature": {"value": calculator.to_unit(T_ble), "unit": unit}, "humidity": {"value": H_ble, "unit": "%"},
                    "vpd": {"value": calculator._vpd(T_ble, H_ble), "unit": "kPa"},
                    "coord": {"x": calculator.vpd_coord_internal(T_ble, H_ble)[0], "y": calculator.vpd_coord_internal(T_ble, H_ble)[1]},
                    "mac": side_data.get("mac", "00:00:00:00:00:00"), "name": side_data.get("name", "")
                }
            else:
                ble_out[side] = {"online": False}
        else:
            ble_out[side] = {"online": False}
    web_dec["ble_sensors"] = ble_out

    # Dynamische Durchreichung restlicher Felder via Blacklist
    BLACKLIST = {
        "temp_in", "humid_in", "temp_ext", "humid_ext", "leaf_temp", "vbat", "rssi",
        "uptime_esp_s", "free_heap", "ble_sensors", "circulation_fan_rpm", "exhaust_fan_rpm",
        "humidifier_pct", "humidifier_speed_now", "humidifier_status", "rev_humidifier",
    }
    for key, value in current_web.items():
        if key not in BLACKLIST and key not in web_dec:
            web_dec[key] = value
    add_normalized_fans(current_web, web_dec)

def offline_frame(mac, now, bridge_alive, bridge_status, bridge_last_seen):
    unit = f"°{config.get_temperature_unit().upper()}"
    off_channel = offline_channel_frame(None)
    
    return {
        "timestamp": now,
        "device_id": mac,
        "name": config.get_device_name(mac) or mac,
        "adv": off_channel,
        "gatt": off_channel,
        "webserver": {
            "alive": False,
            "status": "offline",
            "timestamp": None,
            "dev_name": config.get_device_name(mac) or "growmaster-unknown",
            "fw_ver": "unknown",
            "ip": "0.0.0.0",
            "ssid": "unknown",
            "internal": {
                "temperature": {"value": None, "unit": unit},
                "humidity": {"value": None, "unit": "%"}
            },
            "external": {
                "present": False,
                "temperature": {"value": None, "unit": unit},
                "humidity": {"value": None, "unit": "%"}
            },
            "external2": {
                "present": False,
                "leaf_temp": {"value": None, "unit": unit},
                "vpd_leaf": {"value": None, "unit": "kPa"}
            },
            "ble_sensors": {
                "discovered_devices": [],
                "outside": {"online": False},
                "inside": {"online": False}
            },
            "rssi": None
        },
        "bridge_alive": bridge_alive,
        "bridge_status": bridge_status,
        "bridge_last_seen": bridge_last_seen,
        "alive": False,
        "status": "offline",
        "health": {
            "uptime": {"value": None, "unit": "s"},
            "battery": {"value": None, "unit": "V", "voltage": None},
            "signal": {"rssi": None, "quality": None}
        },
        "device_online": False,
        "web_alive": False
    }
