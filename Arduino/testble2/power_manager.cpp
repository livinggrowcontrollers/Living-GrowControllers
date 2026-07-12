//power_manager.h

#include "power_manager.h"
#include "sys_config.h"
#include "hardware_init.h"
void power_manager_init()
{
    if (sysConfig.pin_bat == -1) {
        Serial.println("power_manager: PIN_BAT disabled (sysConfig). Skipping init.");
        return;
    }
    pinMode(sysConfig.pin_bat, INPUT);
}

// --- BATTERY VOLTAGE (BLE / WEB / LOGIC) ---
// --- BATTERY VOLTAGE (BLE / WEB / LOGIC) ---
float get_battery_voltage_now()
{
    if (sysConfig.pin_bat == -1) {
        return -256.0f; // ⚡ FIX: Liefert jetzt -256.0f statt 0.0f
    }
    uint16_t analogVolts = analogReadMilliVolts(sysConfig.pin_bat);
    return (analogVolts * 3.0f) / 1000.0f;
}

// --- OPTIONAL: PERIODIC POWER MGMT ---
void power_manager_update()
{
    // Headless: aktuell keine dynamische CPU / Sleep Logik
    // Kann später für Low-Power erweitert werden
}