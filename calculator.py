# calculator.py – universal & minimal
# © 2025 Dominik Rosenthal

import math
import config

# ------------------------------------------------------------
# Überprüfen ob externer Sensor vorhanden ist
# (Decoder benötigt diese Funktion → NICHT entfernen!)
# ------------------------------------------------------------
def external_present(humidity_external):
    if humidity_external is None:
        return False
    # ThermoBeacon-Logik
    return not (humidity_external <= 0.1 or humidity_external > 110.0)


# ------------------------------------------------------------
# Offsets korrekt anwenden – GLOBAL (intern + extern)
# None bleibt None → KEINE Logik
# ------------------------------------------------------------
def apply_offsets(T_i, H_i, T_e, H_e):

    temp_off = config.get_temperature_offset()
    hum_off  = config.get_humidity_offset()

    if T_i is not None:
        T_i = T_i + temp_off
    if H_i is not None:
        H_i = H_i + hum_off

    if T_e is not None:
        T_e = T_e + temp_off
    if H_e is not None:
        H_e = H_e + hum_off

    return T_i, H_i, T_e, H_e


# ------------------------------------------------------------
# Einheit anwenden (C/F)
# ------------------------------------------------------------
def to_unit(temp_c):
    if temp_c is None:
        return None
    unit = config.get_temperature_unit().upper()
    if unit == "F":
        return temp_c * 9/5 + 32
    return temp_c


# ------------------------------------------------------------
# VPD (kPa)
# ------------------------------------------------------------
def _vpd(temp_c, rh):
    # Falls rh fehlt, erzwingen wir deine 40.0
    val_rh = rh if rh is not None else 40.0
    val_t = temp_c if temp_c is not None else 0.0
    
    # Die Formel frisst jetzt alles
    try:
        svp = 610.78 * math.exp((17.269 * val_t) / (val_t + 237.3))
        avp = svp * (val_rh / 100.0)
        return round((svp - avp) / 1000.0, 3)
    except:
        return 999.99 # Falls math.exp explodiert (Overflow)


def vpd_internal(T_i, H_i):
    if T_i is None or H_i is None:
        return None
    leaf_off = config.get_leaf_offset()
    return _vpd(T_i + leaf_off, H_i)


def vpd_external(T_e, H_e):
    if T_e is None or H_e is None:
        return None
    leaf_off = config.get_leaf_offset()
    return _vpd(T_e + leaf_off, H_e)

# ------------------------------------------------------------
# Scatter-Koordinaten (einheitenfrei)
# x = humidity (%)
# y = temperature (°C, inkl. leaf offset!)
# ------------------------------------------------------------
def vpd_coord_internal(T_i, H_i):
    if T_i is None or H_i is None:
        return None, None
    leaf_off = config.get_leaf_offset()
    return H_i, T_i + leaf_off


def vpd_coord_external(T_e, H_e):
    if T_e is None or H_e is None:
        return None, None
    leaf_off = config.get_leaf_offset()
    return H_e, T_e + leaf_off

# ------------------------------------------------------------
# VPD LEAF (kPa)
# Blatt gegen Luft (External bevorzugt, sonst Internal)
# ------------------------------------------------------------
def vpd_leaf(T_leaf, T_air, H_air):
    if T_leaf is None or T_air is None or H_air is None:
        return None

    try:
        # SVP Blatt
        svp_leaf = 610.78 * math.exp((17.269 * T_leaf) / (T_leaf + 237.3))
        
        # SVP Luft
        svp_air = 610.78 * math.exp((17.269 * T_air) / (T_air + 237.3))
        avp_air = svp_air * (H_air / 100.0)

        return round((svp_leaf - avp_air) / 1000.0, 3)
    except:
        return None
# ------------------------------------------------------------
# Dew Point / Taupunkt (°C)
# ------------------------------------------------------------
def _dew_point(temp_c, rh):
    if temp_c is None or rh is None:
        return None
    if rh <= 0.0 or rh > 100.0:
        return None

    a = 17.62
    b = 243.12
    gamma = math.log(rh / 100.0) + (a * temp_c) / (b + temp_c)
    return round((b * gamma) / (a - gamma), 2)


def dew_point_internal(T_i, H_i):
    if T_i is None or H_i is None:
        return None
    return _dew_point(T_i, H_i)


def dew_point_external(T_e, H_e):
    if T_e is None or H_e is None:
        return None
    return _dew_point(T_e, H_e)
