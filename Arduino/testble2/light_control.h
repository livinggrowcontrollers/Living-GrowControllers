#ifndef LIGHT_CONTROL_H
#define LIGHT_CONTROL_H

#include <Arduino.h>
#include <ArduinoJson.h>

enum LightPhase {
    LIGHT_PHASE_NIGHT = 0,
    LIGHT_PHASE_SUNRISE,
    LIGHT_PHASE_DAY,
    LIGHT_PHASE_SUNSET,
};

enum LightMode {
    LIGHT_MODE_OFF_LOCKED = 0,
    LIGHT_MODE_MANUAL = 1,
    LIGHT_MODE_TIMER = 2,
};

void light_init();
void light_reconfigure();
void light_update();

void light_set_brightness(int percent);
void light_set_mode(LightMode mode);
void light_set_timer(int hour, int minute, int duration_minutes);

void light_apply_climate_factor(float factor);
bool light_climate_override_enabled();

int light_get_start_h();
int light_get_start_m();
int light_get_duration_min();
int light_get_sunrise_min();
int light_get_sunset_min();
int light_get_minutes_to_next_change();
int light_get_effective_brightness();
bool light_is_on();
float light_get_phase_progress();
LightPhase light_get_current_phase();

void light_control_process_json(JsonObject& doc);
void light_control_get_status(JsonObject& doc);

#endif
