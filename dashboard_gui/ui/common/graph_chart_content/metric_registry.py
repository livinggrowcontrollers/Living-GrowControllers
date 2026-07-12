# dashboard_gui/ui/dashboard_content/metric_registry.py

class MetricRegistry:

    DEFAULT_STYLE = {
        "sz_val": 26,
        "sz_name": 16,
        "sz_unit": 16,
        "sz_trend": 20,
        "color_sub": "#bbbbbb",
        "decimals": 2
    }

    METRICS = {
        "temp_in": {
            "name": "Temperature Internal",
            "unit": "°C",
            "color": "temp_internal",
            "style": {
                "decimals": 1
            }
        },
        "hum_in": {
            "name": "Humidity Internal",
            "unit": "%",
            "color": "hum_internal",
        },
    }
    
    
    # ZENTRALE FARBDEFINITION: Technisch-seriös mit Geräte-Nuancen 🛠️
    COLORS = {
        # --- TEMPERATUREN (Orange-Palette) ---
        "temp_internal": [0.90, 0.40, 0.15, 1],  # Sattes Tech-Orange (Hauptwert)
        "temp_external": [0.70, 0.30, 0.10, 1],  # Dunkleres Rost-Orange (Dezent im Hintergrund)
        "temp_ble":      [1.00, 0.55, 0.25, 1],  # Helles Amber-Orange (Signalisiert Funk/BLE)

        # --- FEUCHTIGKEIT (Blau-Palette) ---
        "hum_internal":  [0.12, 0.53, 0.90, 1],  # Hydro-Blau (Hauptwert)
        "hum_external":  [0.08, 0.38, 0.68, 1],  # Tiefsee-Blau (Dezent im Hintergrund)
        "hum_ble":       [0.30, 0.68, 1.00, 1],  # Eis-Blau / Sky Blue (Signalisiert Funk/BLE)

        # --- VPD (Indigo/Lila-Palette) ---
        "vpd_internal":  [0.44, 0.30, 0.82, 1],  # Slate-Purple (Hauptwert)
        "vpd_external":  [0.32, 0.20, 0.62, 1],  # Deep Indigo
        "vpd_ble":       [0.58, 0.45, 0.95, 1],  # Helles Lavendel-Standard

        # --- SONSTIGE ---
        "green":         [0.18, 0.65, 0.43, 1],  # Mint-Grün (Lüfter & Pflanze)
        "bat":           [0.82, 0.65, 0.12, 1],  # Signal-Gelb (Batterie)
        "white":         [0.44, 0.30, 0.82, 1],  # Reines Weiß (Neutral)
    }

    METRICS = {
        # Intern
        "temp_in":  {"name": "Temperature Internal", "unit": "—", "color": "temp_internal"},
        "hum_in":   {"name": "Humidity Internal", "unit": "%", "color": "hum_internal"},
        "vpd_in":   {"name": "VPD Internal", "unit": "kPa", "color": "vpd_internal"},

        # Extern
        "temp_ex":  {"name": "Temperature External", "unit": "—", "color": "temp_external"},
        "hum_ex":   {"name": "Humidity External", "unit": "%", "color": "hum_external"},
        "vpd_ex":   {"name": "VPD External", "unit": "kPa", "color": "vpd_external"},

        # BLE Outside
        "ble_temp_outside": {"name": "BLE Outside Temperature", "unit": "—", "color": "temp_ble"},
        "ble_hum_outside":  {"name": "BLE Outside Humidity", "unit": "%", "color": "hum_ble"},
        "ble_vpd_outside":  {"name": "BLE Outside VPD", "unit": "kPa", "color": "vpd_ble"},

        # BLE Inside
        "ble_temp_inside": {"name": "BLE Inside Temperature", "unit": "—", "color": "temp_ble"},
        "ble_hum_inside":  {"name": "BLE Inside Humidity", "unit": "%", "color": "hum_ble"},
        "ble_vpd_inside":  {"name": "BLE Inside VPD", "unit": "kPa", "color": "vpd_ble"},

        # Specials
        "leaf_temp":           {"name": "Leaf Temperature", "unit": "—", "color": "green"},
        "vpd_leaf":            {"name": "VPD Leaf", "unit": "kPa", "color": "vpd_internal"},
        "circulation_fan_rpm": {"name": "Circulation Fan", "unit": "RPM", "color": "green"},
        "exhaust_fan_rpm":     {"name": "Exhaust Fan", "unit": "RPM", "color": "green"},
        "v_bat":               {"name": "Battery", "unit": "V", "color": "bat"},

        "rssi":                {"name": "RSSI", "unit": "dBm", "color": "white"},
        "signal_quality":      {"name": "Signal Quality", "unit": "%", "color": "white"},
    }



    @classmethod
    def get(cls, key):
        cfg = cls.METRICS.get(key, {})

        base_color = cls.COLORS.get(cfg.get("color"), [1, 1, 1, 1])

        style = {**cls.DEFAULT_STYLE, **cfg.get("style", {})}

        return {
            "name": cfg.get("name", key.upper()),
            "unit": cfg.get("unit", ""),
            "color": base_color,
            "glow": [*base_color[:3], 0.28],
            "style": style
        }