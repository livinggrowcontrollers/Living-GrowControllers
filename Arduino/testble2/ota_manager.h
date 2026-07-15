#ifndef OTA_MANAGER_H
#define OTA_MANAGER_H

#include <Arduino.h>
#include <ArduinoJson.h>

enum OtaState {
    OTA_STATE_IDLE = 0,
    OTA_STATE_UPDATING = 1,
    OTA_STATE_SUCCESS = 2,
    OTA_STATE_ERROR = 3
};

void ota_manager_init();
void ota_manager_get_status(JsonObject doc);
void ota_manager_process_json(JsonObject doc);

// Diese Funktionen werden direkt vom synchronen Webserver-Upload-Handler gefüttert
bool ota_manager_start(size_t total_size);
bool ota_manager_write(uint8_t* data, size_t len);
bool ota_manager_end();

#endif // OTA_MANAGER_H