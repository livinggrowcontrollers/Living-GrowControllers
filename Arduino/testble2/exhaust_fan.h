#ifndef EXHAUST_FAN_H
#define EXHAUST_FAN_H

#include <Arduino.h>
#include <ArduinoJson.h>

enum exhaust_fanMode {
    exhaust_fan_MODE_MANUAL,
    exhaust_fan_MODE_AUTOMATIC
};

struct ExhaustFanConfig {
    bool enabled;
    exhaust_fanMode mode;
    bool chaos_active;
    int min_pct;
    int max_pct;
};

void exhaust_fan_init(int pin, int tacho_pin);
void exhaust_fan_reconfigure();
void exhaust_fan_update();

ExhaustFanConfig exhaust_fan_get_config();
void exhaust_fan_apply_config(const ExhaustFanConfig& config);
void exhaust_fan_apply_climate_target(
    float target_pct,
    const char* primary_reason,
    const char* secondary_reason
);

int exhaust_fan_get_rpm();
void exhaust_fan_get_status(JsonObject doc);

#endif
