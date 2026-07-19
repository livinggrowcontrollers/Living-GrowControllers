#ifndef CLIMATE_HUB_H
#define CLIMATE_HUB_H

#include <ArduinoJson.h>

void climate_hub_init();
void climate_hub_update();
void climate_hub_process_json(JsonObject doc);
void climate_hub_get_status(JsonObject doc);

#endif
