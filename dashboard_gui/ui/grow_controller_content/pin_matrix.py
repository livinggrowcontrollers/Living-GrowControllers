# dashboard_gui/ui/grow_controller_content/pin_matrix.py

"""
Pin matrix and validator for grow controller GPIO assignments.
EXCLUSIVELY DESIGNED FOR: Diymore / Espressif ESP32-S3 DevKitC-1 N16R8 (Octal Flash/PSRAM)
"""
from typing import Tuple, Dict, Any

# Roles
ROLE_DIGITAL_IN = "INPUT"
ROLE_DIGITAL_OUT = "OUTPUT"
ROLE_PWM = "PWM"
ROLE_I2C = "I2C"
ROLE_ANALOG = "ANALOG"

# Die absolute Wahrheit für das N16R8 Board (0 bis 48)
PIN_WHITELIST = {}

# -1 ist der "Deaktiviert"-Joker für alle Rollen
PIN_WHITELIST[-1] = ([ROLE_DIGITAL_IN, ROLE_DIGITAL_OUT, ROLE_PWM, ROLE_I2C, ROLE_ANALOG], "Deaktiviert")

# 1. Erstmal alle Pins grundlegend als Universal-Pins freigeben (S3-Matrix)
for p in range(0, 49):
    PIN_WHITELIST[p] = ([ROLE_DIGITAL_IN, ROLE_DIGITAL_OUT, ROLE_PWM, ROLE_I2C], f"GPIO {p}")

# 2. Analog-Eingänge (ADC1 & ADC2 Kanäle des ESP32-S3) definieren
for p in range(1, 21):
    PIN_WHITELIST[p][0].append(ROLE_ANALOG)

# =========================================================================
# 3. BOARDSPEZIFISCHE HARDWARE-SPERREN (N16R8 SCHUTZSCHILD)
# =========================================================================

# CRITICAL: Da es sich um ein N16R8 Board handelt (Octal SPI), 
# belegen Flash und PSRAM intern zwingend die Pins 35, 36 und 37! 
# Jede Benutzung führt zum SOFORTIGEN Crash des ESP32-S3.
for p in (35, 36, 37):
    PIN_WHITELIST[p] = ([], "GESPERRT: Interner Octal-Flash/PSRAM Speicherbus!")

# Native USB-Pins (USB-C Port für Programmierung/JTAG) schützen
PIN_WHITELIST[19] = ([], "GESPERRT: Nativer USB-C Port (D-)")
PIN_WHITELIST[20] = ([], "GESPERRT: Nativer USB-C Port (D+)")

# Serieller Monitor Pins (TX0 / RX0) sperren, damit du Logs lesen kannst
PIN_WHITELIST[43] = ([], "GESPERRT: System UART0 TX (Serial Debug)")
PIN_WHITELIST[44] = ([], "GESPERRT: System UART0 RX (Serial Debug)")

# Boot-Strapping Pins absichern (Dürfen beim Booten nicht falsch gezogen werden)
PIN_WHITELIST[0]  = ([ROLE_DIGITAL_IN], "Vorsicht: Boot-Modus Pin (Nur Input sicher)")
PIN_WHITELIST[45] = ([ROLE_DIGITAL_OUT, ROLE_PWM], "Vorsicht: VDD_SPI Spannungs-Pin (Nur Output sicher)")
PIN_WHITELIST[46] = ([ROLE_DIGITAL_IN], "Vorsicht: Strapping Pin (Nur Input sicher)")

# Onboard RGB-LED (je nach Board-Revision auf Pin 38 oder 48) kennzeichnen
PIN_WHITELIST[38] = ([ROLE_DIGITAL_OUT, ROLE_PWM], "GPIO 38 (Eventuell Onboard RGB-LED)")
PIN_WHITELIST[48] = ([ROLE_DIGITAL_OUT, ROLE_PWM], "GPIO 48 (Eventuell Onboard RGB-LED)")


# Mapping: Welches JSON-Feld benötigt welche Hardware-Rolle
REQUIRED_ROLES = {
    "p_reset":   ROLE_DIGITAL_IN,
    "p_c_fan":   ROLE_PWM,
    "p_c_tac":   ROLE_DIGITAL_IN,
    "p_e_fan":   ROLE_PWM,
    "p_e_tac":   ROLE_DIGITAL_IN,
    "p_light":   ROLE_PWM,
    "p_i2c_sda": ROLE_I2C,
    "p_i2c_scl": ROLE_I2C,
    "p_rtc_sda": ROLE_I2C,
    "p_rtc_scl": ROLE_I2C,
    "p_bat":     ROLE_ANALOG
}

def validate_and_build_pins(current_device_data: Dict[str, Any], new_kwargs: Dict[str, Any]) -> Tuple[bool, Any]:
    current_gpios = current_device_data.get("gpios", {}) if current_device_data else {}

    merged_gpios = {}
    for key in REQUIRED_ROLES.keys():
        if key in new_kwargs:
            try:
                merged_gpios[key] = int(new_kwargs[key])
            except Exception:
                return False, f"Ungültiger Pin-Wert für {key}: {new_kwargs.get(key)}"
        else:
            merged_gpios[key] = int(current_gpios.get(key, -1))

    used_pins = {}
    for key, target_pin in merged_gpios.items():
        if target_pin == -1:
            continue

        # Jetzt voll kompatibel bis GPIO 48
        if target_pin not in PIN_WHITELIST:
            return False, f"GPIO {target_pin} existiert nicht auf dem ESP32-S3 DevKitC-1!"

        required_role = REQUIRED_ROLES.get(key)
        allowed_roles, info_text = PIN_WHITELIST[target_pin]

        # Wenn die Liste der erlaubten Rollen leer ist (z.B. bei Pin 35, 36, 37), knallt es hier korrekterweise
        if required_role not in allowed_roles:
            return False, f"Fehler bei {key}: {info_text} erlaubt keine '{required_role}'-Funktion!"

        if target_pin in used_pins:
            return False, f"Doppelbelegung! GPIO {target_pin} wird gleichzeitig von '{used_pins[target_pin]}' und '{key}' verwendet!"

        used_pins[target_pin] = key

    return True, merged_gpios

def get_pin_info(pin: int):
    return PIN_WHITELIST.get(pin, (None, "Unbekannter Pin"))