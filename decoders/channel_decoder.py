# -*- coding: utf-8 -*-
import time
import config
from decoders.binary_parser import load_profile, decode_with_profile
from decoders.frame_factory import offline_channel_frame, build_active_ble_frame

def decode_channel(entry, raw_key, profile_name, last_signal_dict, last_ts_dict, timeout, is_gatt=False):
    now = time.time()
    mac = entry.get("address")

    if mac is None:
        return offline_channel_frame(entry.get(raw_key))

    if is_gatt:
        signal = entry.get("packet_counter")
    else:
        signal = entry.get(raw_key)

    # Timeout-Logik
    if signal is None:
        last_ts = last_ts_dict.get(mac)
        if not (last_ts and (time.time() - last_ts) < float(timeout)):
            return offline_channel_frame(entry.get(raw_key))

    # Update last seen
    last_signal = last_signal_dict.get(mac)
    last_ts = last_ts_dict.get(mac)

    if last_signal is None or signal != last_signal:
        last_signal_dict[mac] = signal
        last_ts_dict[mac] = now
    elif last_ts and (now - last_ts) >= float(timeout):
        return offline_channel_frame(entry.get(raw_key))

    # Eigentliche Dekodierung
    raw_hex = entry.get(raw_key)
    if not raw_hex:
        return offline_channel_frame(None)

    prof = load_profile(profile_name)
    if not prof:
        return offline_channel_frame(raw_hex)

    decoded = decode_with_profile(raw_hex, prof)
    if not decoded:
        return offline_channel_frame(raw_hex)

    unit = f"°{config.get_temperature_unit().upper()}"
    frame = build_active_ble_frame(decoded, entry, unit)
    
    # RSSI immer setzen (auch bei aktivem Frame)
#    RSSI immer setzen (Filtert -256 händisch raus)
    raw_rssi = entry.get("rssi", -256)
    frame["rssi"] = raw_rssi if (raw_rssi is not None and raw_rssi != -256 and raw_rssi > -250) else None
    
    return frame