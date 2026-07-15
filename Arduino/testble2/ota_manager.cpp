#include "ota_manager.h"
#include <Update.h>
#include <Preferences.h>

static Preferences otaPrefs;
static OtaState _ota_state = OTA_STATE_IDLE;
static uint32_t _ota_rev = 0;
static size_t _ota_bytes_written = 0;
static size_t _ota_total_bytes = 0;
static String _ota_error_msg = "";

void ota_manager_init() {
    otaPrefs.begin("ota_system", false);
    _ota_rev = otaPrefs.getUInt("ota_rev", 0);
    otaPrefs.end();
    
    Serial.print("[OTA] Initialisiert. Aktuelle ota_rev: ");
    Serial.println(_ota_rev);
}

void ota_manager_get_status(JsonObject doc) {
    JsonObject otaNode = doc.createNestedObject("ota");
    otaNode["ota_rev"] = _ota_rev;
    
    switch (_ota_state) {
        case OTA_STATE_IDLE:     otaNode["status"] = "IDLE"; break;
        case OTA_STATE_UPDATING: otaNode["status"] = "UPDATING"; break;
        case OTA_STATE_SUCCESS:  otaNode["status"] = "SUCCESS"; break;
        case OTA_STATE_ERROR:    otaNode["status"] = "ERROR"; break;
    }
    
    float progress = 0.0f;
    if (_ota_total_bytes > 0) {
        progress = ((float)_ota_bytes_written / (float)_ota_total_bytes) * 100.0f;
    }
    otaNode["progress"] = (int)progress;
    otaNode["error_msg"] = _ota_error_msg;
}

void ota_manager_process_json(JsonObject doc) {
    if (doc.containsKey("ota_rev")) {
        _ota_rev = doc["ota_rev"].as<uint32_t>();
        
        otaPrefs.begin("ota_system", false);
        otaPrefs.putUInt("ota_rev", _ota_rev);
        otaPrefs.end();
        
        Serial.print("[OTA] Neue ota_rev übernommen: ");
        Serial.println(_ota_rev);
    }
}

bool ota_manager_start(size_t total_size) {
    _ota_state = OTA_STATE_UPDATING;
    _ota_bytes_written = 0;
    _ota_total_bytes = total_size;
    _ota_error_msg = "";
    
    Serial.printf("[OTA] Starte Flash-Vorgang. Erwartete Größe: %d Bytes\n", total_size);
    
    if (!Update.begin(total_size, U_FLASH)) {
        _ota_state = OTA_STATE_ERROR;
        _ota_error_msg = "Nicht genug Platz auf der OTA Partition!";
        Update.printError(Serial);
        return false;
    }
    return true;
}

bool ota_manager_write(uint8_t* data, size_t len) {
    if (_ota_state != OTA_STATE_UPDATING) return false;
    
    size_t written = Update.write(data, len);
    if (written != len) {
        _ota_state = OTA_STATE_ERROR;
        _ota_error_msg = "Schreibfehler im Flash";
        return false;
    }
    
    _ota_bytes_written += written;
    return true;
}

bool ota_manager_end() {
    if (_ota_state != OTA_STATE_UPDATING) return false;
    
    if (Update.end(true)) {
        _ota_state = OTA_STATE_SUCCESS;
        Serial.println("[OTA] Update erfolgreich! ESP32 startet in 2 Sekunden neu...");
        delay(2000);
        ESP.restart();
        return true;
    } else {
        _ota_state = OTA_STATE_ERROR;
        _ota_error_msg = "Integritaetspruefung fehlgeschlagen";
        Update.printError(Serial);
        return false;
    }
}