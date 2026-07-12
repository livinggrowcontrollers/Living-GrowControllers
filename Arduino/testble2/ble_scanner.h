

// ble_scanner.h
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

namespace BLEScanner {
    void init();
    void update();

    void restart();
    bool isScanning();
    // Enable / disable scanning at runtime
    void enable();
    void disable();
    bool isEnabled();
// NEU: Dem Compiler die Pairing-Funktion zeigen (wichtig für grow_controller.cpp!)
    void set_paired_mac(String type, String mac_address);
    void clear_saved_macs();
    void get_status(JsonObject& obj);
    
    // Snapshot API: copy minimal BLE state under lock for fast HTTP handlers
#define BLE_MAX_DISCOVERED 10
    struct DiscoveredSnapshot {
        char name[32];
        char mac[18];
    };
    struct BLESnapshot {
        float outside_temp;
        float outside_hum;
        bool outside_online;
        char outside_mac[18];
        char outside_name[32];

        float inside_temp;
        float inside_hum;
        bool inside_online;
        char inside_mac[18];
        char inside_name[32];

        DiscoveredSnapshot discovered[BLE_MAX_DISCOVERED];
        int discovered_count;
    };

    void get_snapshot(BLESnapshot& s);
    // ✅ HINZUFÜGEN:
    float get_outside_temp();
    float get_outside_hum();
    bool  is_outside_online();
}