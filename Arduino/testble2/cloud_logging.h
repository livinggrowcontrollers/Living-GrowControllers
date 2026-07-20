#ifndef CLOUD_LOGGING_H
#define CLOUD_LOGGING_H

#include <ArduinoJson.h>

void cloud_logging_init();
void cloud_logging_update();
void cloud_logging_process_config(JsonObject config);
void cloud_logging_factory_reset();

#endif
