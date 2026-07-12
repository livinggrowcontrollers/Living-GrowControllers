// exhaust_fan.h
#ifndef exhaust_fan_H
#define exhaust_fan_H

#include <ArduinoJson.h> 
#include <Arduino.h>

enum exhaust_fanMode {
    exhaust_fan_MODE_MANUAL,
    exhaust_fan_MODE_AUTOMATIC,
    exhaust_fan_MODE_CHAOTIC
};

// --- SYSTEM-REVISION (Wichtig für das Sync-Gesetz) ---
extern uint32_t device_confirmed_rev; // Die Bestätigung für die UI
// --- FUNKTIONEN ---
void exhaust_fan_init(uint8_t pin, uint8_t tacho_pin);
void exhaust_fan_update();
void exhaust_fan_set_speed(int percent);
void exhaust_fan_set_mode(exhaust_fanMode mode);
void exhaust_fan_set_min_speed(int percent);
void exhaust_fan_save_state();
int exhaust_fan_get_rpm();
void exhaust_fan_process_json(JsonObject doc);
void exhaust_fan_get_status(JsonObject doc);
void exhaust_fan_reconfigure();
// --- EXTERNE VARIABLEN ---
extern int current_exhaust_fan_speed;
extern exhaust_fanMode current_exhaust_fan_mode;
extern int current_exhaust_fan_min_speed;

// TARGETS
extern float target_temp;
extern float target_humidity;
extern int target_exhaust_fan_pct;
extern float target_vpd_min;
extern float target_vpd_max;
extern float target_temp_min;
extern float target_temp_max;

extern int target_humidity_min;
extern int target_humidity_max;
#endif