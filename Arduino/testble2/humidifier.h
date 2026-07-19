#ifndef HUMIDIFIER_H
#define HUMIDIFIER_H

#include <ArduinoJson.h>

void humidifier_init(int pin);
void humidifier_reconfigure();
void humidifier_update();

// Climate Hub supplies the runtime demand; the Humidifier remains the sole
// owner of its configured maximum, PWM output, persistence and revision.
void humidifier_apply_climate_factor(float factor, const char* reason);

void humidifier_process_json(JsonObject doc);
void humidifier_get_status(JsonObject doc);

#endif
