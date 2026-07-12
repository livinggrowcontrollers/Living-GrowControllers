// ble_scanner.cpp
#include "ble_scanner.h"
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <string>          
#include <Preferences.h>

portMUX_TYPE ble_mux = portMUX_INITIALIZER_UNLOCKED;

// Globale Variablen für BLE
Preferences blePrefs;
static BLEAddress outside_ADDR("00:00:00:00:00:00"); // Globale Adresse für außen
static BLEAddress inside_ADDR("00:00:00:00:00:00"); // Globale Adresse für innen
static char OUTSIDE_MAC_CSTR[18] = "00:00:00:00:00:00"; // C-String für outside MAC
static char INSIDE_MAC_CSTR[18] = "00:00:00:00:00:00"; // C-String für inside MAC
// no force-disabled flag
struct DiscoveredDevice {
    String address;
    String name;
};
#define MAX_DISCOVERED 10
static DiscoveredDevice _discovered_list[MAX_DISCOVERED];
static int _discovered_count = 0;

const uint32_t SCAN_TIME_MS      = 5000;   
const uint32_t SCAN_INTERVAL_MS  = 6000;   
const uint32_t SENSOR_WATCHDOG_MS = 60000;

struct SensorData {
    float temp = -256.0f;
    float humid = -256.0f;
    int packet = -1;
    unsigned long lastSeen = 0;
    bool is_online = false;
    String name = ""; // <-- NEU: Speichert den Namen dauerhaft für diesen Slot
};

static SensorData outside;
static SensorData inside;

BLEScan* pBLEScan = nullptr;
static bool ble_enabled = false;

// Hilfsfunktion zum Parsen der Rohdaten
float parseValue(const uint8_t* data, int offset, float scale) {
    int16_t raw = data[offset] | (data[offset + 1] << 8);
    return (float)raw / scale;
}

// Callback – Erkennt Geräte am NAMEN, ordnet sie nach MAC zu
class MyScannerCallbacks : public BLEAdvertisedDeviceCallbacks {
void onResult(BLEAdvertisedDevice device) {

    // ==========================================
    // FRÜHER FILTER
    // ==========================================
    if (!device.haveName()) {
        return;
    }

    String devName = device.getName().c_str();

    if (!devName.equalsIgnoreCase("sps") &&
        !devName.equalsIgnoreCase("Thermobeacon2")) {
        return;
    }

    // Erst jetzt weitere Arbeit
    const BLEAddress& addr = device.getAddress();
    String macStr = String(addr.toString().c_str());

    // JEDES relevante Gerät wandert in die Liste für Kivy
    bool exists = false;

    portENTER_CRITICAL(&ble_mux);

    for (int i = 0; i < _discovered_count; i++) {
        if (_discovered_list[i].address == macStr) {
            exists = true;
            break;
        }
    }

    if (!exists && _discovered_count < MAX_DISCOVERED) {
        _discovered_list[_discovered_count].address = macStr;
        _discovered_list[_discovered_count].name = devName;
        _discovered_count++;
    }

    portEXIT_CRITICAL(&ble_mux);

    // ==========================================
    // MESSWERTEXTRAKTION
    // ==========================================
    if (device.haveManufacturerData()) {

        float temp = -256.0f;
        float humid = -256.0f;
        bool decoded = false;

        String mData = device.getManufacturerData();

        if (devName.equalsIgnoreCase("sps") &&
            mData.length() >= 7) {

            temp = parseValue(
                (uint8_t*)mData.c_str(),
                0,
                100.0f
            );

            humid = parseValue(
                (uint8_t*)mData.c_str(),
                2,
                100.0f
            );

            decoded = true;
        }
        else if (devName.equalsIgnoreCase("Thermobeacon2") &&
                 mData.length() >= 19) {

            const uint8_t* sensorBase =
                (uint8_t*)mData.c_str() + 10;

            temp = parseValue(sensorBase, 0, 16.0f);
            humid = parseValue(sensorBase, 2, 16.0f);

            decoded = true;
        }

        if (decoded) {

            uint32_t now = millis();

            portENTER_CRITICAL(&ble_mux);

            if (addr.equals(outside_ADDR)) {
                outside.temp = temp;
                outside.humid = humid;
                outside.lastSeen = now;
                outside.is_online = true;
                outside.name = devName; // <-- NEU
            }

            if (addr.equals(inside_ADDR)) {
                inside.temp = temp;
                inside.humid = humid;
                inside.lastSeen = now;
                inside.is_online = true;
                inside.name = devName; // <-- NEU
            }

                // (names are copied into snapshot in get_snapshot under lock)

            portEXIT_CRITICAL(&ble_mux);
        }
    }
}
};
// ================= ZENTRALER NAMESPACE =================
namespace BLEScanner {

    float get_outside_temp() { return outside.is_online ? outside.temp : -256.0f; }
    float get_outside_hum() { return outside.is_online ? outside.humid : -256.0f; }
    bool is_outside_online() { return outside.is_online; }

    void init() {
        // Load saved macs into both BLEAddress and C-string buffers
        {
            Preferences prefs;
            prefs.begin("blescan", false);
            String mo = prefs.getString("mac_outside", "00:00:00:00:00:00");
            String mi = prefs.getString("mac_inside", "00:00:00:00:00:00");
            prefs.end();
            outside_ADDR = BLEAddress(mo.c_str());
            inside_ADDR = BLEAddress(mi.c_str());
            strncpy(OUTSIDE_MAC_CSTR, mo.c_str(), sizeof(OUTSIDE_MAC_CSTR));
            OUTSIDE_MAC_CSTR[17] = '\0';
            strncpy(INSIDE_MAC_CSTR, mi.c_str(), sizeof(INSIDE_MAC_CSTR));
            INSIDE_MAC_CSTR[17] = '\0';
        }

        pBLEScan = BLEDevice::getScan();
        pBLEScan->setAdvertisedDeviceCallbacks(new MyScannerCallbacks(), true);
        pBLEScan->setActiveScan(true); // Passive Scan (nur Werbung, keine Verbindungsversuche)
        pBLEScan->setInterval(500);
        pBLEScan->setWindow(250);
    }

    void restart() {
        if (!ble_enabled) return;
        if (pBLEScan) {
            pBLEScan->stop();
            pBLEScan->clearResults();
            Serial.println("[BLEScanner] Restarted BLE Scan");
        }
    }

    bool isScanning() {
        return (ble_enabled && pBLEScan) ? pBLEScan->isScanning() : false;
    }

    void update() {
        static uint32_t lastScanTime = 0;
        unsigned long currentMillis = millis();
        if (!ble_enabled) {
            return;
        }
        if (currentMillis - outside.lastSeen > SENSOR_WATCHDOG_MS) outside.is_online = false;
        if (currentMillis - inside.lastSeen > SENSOR_WATCHDOG_MS) inside.is_online = false;

        if (!ble_enabled) return;

        if (currentMillis - lastScanTime >= SCAN_INTERVAL_MS || lastScanTime == 0) {
            lastScanTime = currentMillis;

            if (pBLEScan) {
                pBLEScan->stop();          
                pBLEScan->clearResults();  
                
                portENTER_CRITICAL(&ble_mux);
                _discovered_count = 0;
                portEXIT_CRITICAL(&ble_mux);

                pBLEScan->start(SCAN_TIME_MS / 1000, nullptr, false);
                Serial.println("[BLEScanner] Scan-Intervall erzwungen neu gestartet...");
            }
        }
    }

    void enable() {
        ble_enabled = true;
        Serial.println("[BLEScanner] Scanning enabled");
        // ensure pBLEScan exists
        if (!pBLEScan) init();
    }

    void disable() {
        ble_enabled = false;
        Serial.println("[BLEScanner] Scanning disabled");
        if (pBLEScan) {
            pBLEScan->stop();
            pBLEScan->clearResults();
        }
        // Clear any cached sensor snapshots to avoid pseudo-values after disable
        portENTER_CRITICAL(&ble_mux);
        outside = SensorData();
        inside = SensorData();
        _discovered_count = 0;
        for (int i = 0; i < MAX_DISCOVERED; i++) {
            _discovered_list[i].address = "";
            _discovered_list[i].name = "";
        }
        portEXIT_CRITICAL(&ble_mux);
    }

    bool isEnabled() { return ble_enabled; }

    void set_paired_mac(String type, String mac_address) {
        if (mac_address.length() != 17) return;

        // 1. Update in-RAM immediately (fast, non-blocking)
        if (type == "outside") {
            outside_ADDR = BLEAddress(mac_address.c_str());
            strncpy(OUTSIDE_MAC_CSTR, mac_address.c_str(), sizeof(OUTSIDE_MAC_CSTR));
            OUTSIDE_MAC_CSTR[17] = '\0';

            // Watchdog direkt umgehen: Wenn entkoppelt wird, Daten sofort zurücksetzen
            if (mac_address == "00:00:00:00:00:00") {
                portENTER_CRITICAL(&ble_mux);
                outside = SensorData(); // Setzt temp/humid auf -256 und is_online = false
                portEXIT_CRITICAL(&ble_mux);
                Serial.println("[BLEScanner] Slot 'outside' erfolgreich im RAM zurückgesetzt.");
            }
        } else if (type == "inside") {
            inside_ADDR = BLEAddress(mac_address.c_str());
            strncpy(INSIDE_MAC_CSTR, mac_address.c_str(), sizeof(INSIDE_MAC_CSTR));
            INSIDE_MAC_CSTR[17] = '\0';

            // Watchdog direkt umgehen: Wenn entkoppelt wird, Daten sofort zurücksetzen
            if (mac_address == "00:00:00:00:00:00") {
                portENTER_CRITICAL(&ble_mux);
                inside = SensorData(); // Setzt temp/humid auf -256 und is_online = false
                portEXIT_CRITICAL(&ble_mux);
                Serial.println("[BLEScanner] Slot 'inside' erfolgreich im RAM zurückgesetzt.");
            }
        }

        // 2. Persist asynchronously to avoid blocking the HTTP handler
        struct NVSWriteRequest {
            bool is_outside;
            char mac[18];
        };

        NVSWriteRequest* req = new NVSWriteRequest();
        req->is_outside = (type == "outside");
        strncpy(req->mac, mac_address.c_str(), sizeof(req->mac));
        req->mac[17] = '\0';

        // Background task that performs the slow Preferences write
        auto nvs_write_task = [](void* pv) {
            NVSWriteRequest* r = (NVSWriteRequest*)pv;
            Preferences prefs;
            prefs.begin("blescan", false);
            if (r->is_outside) prefs.putString("mac_outside", String(r->mac));
            else prefs.putString("mac_inside", String(r->mac));
            prefs.end();
            
            Serial.printf("[BLEScanner] NVS-Write Erfolg für %s: %s\n", 
                          r->is_outside ? "outside" : "inside", r->mac);
            
            delete r;
            vTaskDelete(NULL);
        };

        BaseType_t ok = xTaskCreate(
            (TaskFunction_t)nvs_write_task,
            "nvs_write",
            3072,
            req,
            1,
            NULL
        );
        
        if (ok != pdPASS) {
            Serial.println("[BLEScanner] Warning: failed to create nvs_write task");
            // fallback: write synchronously (last resort)
            Preferences prefs;
            prefs.begin("blescan", false);
            if (req->is_outside) prefs.putString("mac_outside", String(req->mac));
            else prefs.putString("mac_inside", String(req->mac));
            prefs.end();
            delete req;
        }
    }
    void clear_saved_macs() {
        blePrefs.begin("blescan", false);
        blePrefs.clear();
        outside_ADDR = BLEAddress("00:00:00:00:00:00");
        inside_ADDR = BLEAddress("00:00:00:00:00:00");

        portENTER_CRITICAL(&ble_mux);
        _discovered_count = 0;
        for (int i = 0; i < MAX_DISCOVERED; i++) {
            _discovered_list[i].address = "";
            _discovered_list[i].name = "";
        }
        portEXIT_CRITICAL(&ble_mux);

        portENTER_CRITICAL(&ble_mux);
        outside = SensorData();
        inside = SensorData();
        portEXIT_CRITICAL(&ble_mux);

        Serial.println("[BLEScanner] Gespeicherte MACs gelöscht (blescan cleared)");
    }

    void get_status(JsonObject& obj) {
        // Backwards-compatible fast path: copy under lock then serialize outside
        BLESnapshot s;
        get_snapshot(s);

        JsonObject ble = obj.createNestedObject("ble_sensors");

        JsonObject j_outside = ble.createNestedObject("outside");
        j_outside["ble_temp_outside"] = s.outside_online ? s.outside_temp : -256.0;
        j_outside["ble_humid_outside"] = s.outside_online ? s.outside_hum : -256.0;
        j_outside["online"] = s.outside_online;
        j_outside["mac"] = s.outside_mac;
        j_outside["name"] = s.outside_name; // safe: from snapshot

        JsonObject j_inside = ble.createNestedObject("inside");
        j_inside["ble_temp_inside"] = s.inside_online ? s.inside_temp : -256.0;
        j_inside["ble_humid_inside"] = s.inside_online ? s.inside_hum : -256.0;
        j_inside["online"] = s.inside_online;
        j_inside["mac"] = s.inside_mac;
        j_inside["name"] = s.inside_name; // safe: from snapshot

        // HIER KORRIGIERT: Kommentar-Striche entfernt!
        JsonArray devArray = ble.createNestedArray("discovered_devices");
        for (int i = 0; i < s.discovered_count; i++) {
            JsonObject d = devArray.createNestedObject();
            d["name"] = s.discovered[i].name;
            d["mac"] = s.discovered[i].mac;
        }
    }

    void get_snapshot(BLESnapshot& s) {
        // copy minimal state under lock
        portENTER_CRITICAL(&ble_mux);
        s.outside_temp = outside.temp;
        s.outside_hum = outside.humid;
        s.outside_online = outside.is_online;
        strncpy(s.outside_mac, OUTSIDE_MAC_CSTR, sizeof(s.outside_mac));
        s.outside_mac[17] = '\0';

        s.inside_temp = inside.temp;
        s.inside_hum = inside.humid;
        s.inside_online = inside.is_online;
        strncpy(s.inside_mac, INSIDE_MAC_CSTR, sizeof(s.inside_mac));
        s.inside_mac[17] = '\0';

        int n = _discovered_count;
        if (n > BLE_MAX_DISCOVERED) n = BLE_MAX_DISCOVERED;
        s.discovered_count = n;
        for (int i = 0; i < n; i++) {
            // copy into fixed buffers
            memset(s.discovered[i].name, 0, sizeof(s.discovered[i].name));
            strncpy(s.discovered[i].name, _discovered_list[i].name.c_str(), sizeof(s.discovered[i].name)-1);
            memset(s.discovered[i].mac, 0, sizeof(s.discovered[i].mac));
            strncpy(s.discovered[i].mac, _discovered_list[i].address.c_str(), sizeof(s.discovered[i].mac)-1);
        }
        // safe copy of persistent names into snapshot
        memset(s.outside_name, 0, sizeof(s.outside_name));
        if (outside.name.length() > 0) {
            strncpy(s.outside_name, outside.name.c_str(), sizeof(s.outside_name)-1);
        }
        memset(s.inside_name, 0, sizeof(s.inside_name));
        if (inside.name.length() > 0) {
            strncpy(s.inside_name, inside.name.c_str(), sizeof(s.inside_name)-1);
        }
        portEXIT_CRITICAL(&ble_mux);
    }

} // namespace BLEScanner