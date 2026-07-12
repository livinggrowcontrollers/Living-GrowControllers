#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sim_tile_tester_pro_v2.py
RAW-MATRIX Simulator für Session 45+
Erzeugt ble_dump.json mit 3 RAW-Strängen pro Gerät:

- adv_raw   → simuliertes ADV (TB2-kompatibel)
- gatt_raw   → simuliertes GATT-Vendor-RAW (optional)
- log_raw   → Logging-RAW (frei)
"""

import os
import json
import random
import time
from datetime import datetime, timezone


BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")
OUT = os.path.join(DATA, "ble_dump.json")
os.makedirs(DATA, exist_ok=True)


# -------------------------------------------------------------------
# Timestamp
# -------------------------------------------------------------------
def ts():
    return (
        datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "+0000"
    )


# -------------------------------------------------------------------
# TB2 RAW Encoder (gleich gelassen)
# -------------------------------------------------------------------
def tb2_raw(temp_i, hum_i, temp_e, hum_e, pkt):
    def enc(v):
        if v is None:
            return [0xFF, 0x0F]  # TB2-Nullwert

        x = int(round(v * 16.0))
        if x < 0:
            x = (1 << 16) + x
        return [x & 0xFF, (x >> 8) & 0xFF]

    b = []
    b += [0x19, 0x00]                       # Company ID
    b += [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
    b += [0x02, 0x00]                       # Flags

    b += enc(temp_i)
    b += enc(hum_i)
    b += enc(temp_e)
    b += enc(hum_e)
    b += [pkt & 0xFF]

    return "".join(f"{x:02X}" for x in b)


# -------------------------------------------------------------------
# DEVICE SETUP
# -------------------------------------------------------------------
DEVICES = []

# 5 temp_only
for i in range(1, 6):
    DEVICES.append((f"TempOnly-{i:02d}", f"AA:BB:CC:00:10:{i:02d}", "temp_only"))

# 5 temp_hum
for i in range(1, 6):
    DEVICES.append((f"TempHum-{i:02d}", f"AA:BB:CC:00:20:{i:02d}", "temp_hum"))

# 5 temp_hum_ext
for i in range(1, 6):
    DEVICES.append((f"TempHumExt-{i:02d}", f"AA:BB:CC:00:30:{i:02d}", "temp_hum_ext"))

# 3 ultra_stable
for i in range(1, 4):
    DEVICES.append((f"Stable-{i:02d}", f"AA:BB:CC:00:40:{i:02d}", "ultra_stable"))

# 2 chaos
for i in range(1, 3):
    DEVICES.append((f"Chaos-{i:02d}", f"AA:BB:CC:00:50:{i:02d}", "chaos"))

# 1 external_only
DEVICES.append(("ExternalOnly-01", "AA:BB:CC:00:60:01", "external_only"))

# 1 humidity_only
DEVICES.append(("HumidityOnly-01", "AA:BB:CC:00:70:01", "humidity_only"))


pkt = 0
print("[TileSim PRO v2] schreibt RAW-Matrix →", OUT)


# Helper
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# -------------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------------
while True:
    pkt = (pkt + 1) % 255
    out = {}

    for name, mac, mode in DEVICES:

        # === Werte generieren ==========================================
        if mode == "temp_only":
            t_i = 20 + random.uniform(-0.7, 0.7)
            h_i = None
            t_e = None
            h_e = None

        elif mode == "temp_hum":
            t_i = 21 + random.uniform(-1, 1)
            h_i = 45 + random.uniform(-3, 3)
            t_e = None
            h_e = None

        elif mode == "temp_hum_ext":
            t_i = 23 + random.uniform(-1, 1)
            h_i = 55 + random.uniform(-4, 4)
            t_e = t_i - 1.2 + random.uniform(-0.3, 0.3)
            h_e = h_i - 7 + random.uniform(-2, 2)

        elif mode == "ultra_stable":
            t_i = 24 + random.uniform(-0.05, 0.05)
            h_i = 50 + random.uniform(-0.2, 0.2)
            t_e = None
            h_e = None

        elif mode == "chaos":
            t_i = clamp(20 + random.uniform(-8, 8), 10, 35)
            h_i = clamp(50 + random.uniform(-30, 30), 10, 90)
            if random.random() < 0.5:
                t_e = clamp(t_i - random.uniform(1, 5), 5, 35)
                h_e = clamp(h_i - random.uniform(5, 20), 5, 95)
            else:
                t_e = None
                h_e = None

        elif mode == "external_only":
            t_i = None
            h_i = None
            t_e = 18 + random.uniform(-1, 1)
            h_e = 40 + random.uniform(-4, 4)

        elif mode == "humidity_only":
            t_i = None
            h_i = 60 + random.uniform(-5, 5)
            t_e = None
            h_e = None

        else:
            t_i = 22
            h_i = 50
            t_e = None
            h_e = None

        # === generate RAWs ==============================================
        adv_raw = tb2_raw(t_i, h_i, t_e, h_e, pkt)

        # Vendor-GATT RAW (statisch/dummy → später kompatibel)
        gatt_raw = f"VENDOR{pkt:02X}{mac.replace(':','')}"

        # log_raw → default identisch wie ADV
        log_raw = adv_raw

        # === Gerät eintragen ============================================
        out[mac] = {
            "timestamp": ts(),
            "name": name,
            "address": mac,
            "rssi": random.randint(-85, -40),

            "adv_raw": adv_raw,
            "gatt_raw": gatt_raw,
            "log_raw": log_raw
        }

    # atomar write
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, OUT)

    time.sleep(1.2)
