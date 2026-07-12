//ble_bridge.h - BLE-Bridge für LGS Sensoren
#ifndef BLE_BRIDGE_H
#define BLE_BRIDGE_H

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>
#include <WiFi.h> // Wichtig: Wird benötigt, um die MAC-Adresse für den Namen auszulesen!

// --- KONFIGURATION ---
#define NEW_VENDOR_ID      0x02D3       
#define ENV_SERVICE_UUID   0x181A       

class BLEBridge {
private:
    BLEAdvertising *pAdvertising;
    uint8_t packetCounter = 0;
    uint8_t sendChannel = 17;
    bool enabled = false;
    String ble_name = ""; // Hier speichern wir den dynamischen Namen

    // Hilfsfunktion: Generiert exakt den gleichen Namen wie dein mDNS-Setup
    void ensure_ble_name_generated() {
        if (ble_name.length() > 0) return;

        String macStr = WiFi.macAddress();
        macStr.replace(":", "");
        String suffix = macStr.substring(macStr.length() - 4);
        ble_name = "growmaster-" + suffix;
        ble_name.toLowerCase();
    }

public:
    void begin() {
        // Sicherstellen, dass der Name anhand der MAC-Adresse generiert wurde
        ensure_ble_name_generated();
        Serial.printf("[BLEBridge] Initialisiere mit Name: %s\n", ble_name.c_str());
        
        // BLE-Device initialisieren (falls noch nicht geschehen)
        // Hinweis: BLEDevice::init() erwartet den Namen. Wir nutzen direkt den generierten Namen.
        BLEDevice::init(ble_name.c_str());
        
        // Maximale Sendeleistung einstellen (+9dBm für S3)
        esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_DEFAULT, ESP_PWR_LVL_P9); // <--- Hier stand der Fehler!
        esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);
        esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_SCAN, ESP_PWR_LVL_P9);
    
        pAdvertising = BLEDevice::getAdvertising();
        
        // Intervalle für schnelles Erscheinen im Dashboard
        pAdvertising->setMinInterval(100); // 100 * 0.625ms = 62.5ms
        pAdvertising->setMaxInterval(200); // Schnelleres Advertising während des Sendefensters
        
        pAdvertising->setScanResponse(true);
        pAdvertising->start();
        enabled = true;
    }

    void enable() {
        if (!pAdvertising) pAdvertising = BLEDevice::getAdvertising();
        if (pAdvertising && !enabled) {
            pAdvertising->start();
            enabled = true;
            Serial.println("[BLEBridge] Enabled advertising");
        }
    }

    void disable() {
        if (pAdvertising && enabled) {
            pAdvertising->stop();
            enabled = false;
            Serial.println("[BLEBridge] Disabled advertising");
        }
    }

    bool isEnabled() {
        return enabled;
    }

    void updateBroadcast(float t_ext, float h_ext, float t_int, float h_int, float t_leaf, float v_bat, int rpm) {
        uint8_t payload[17]; // 17 Bytes (A2, Ch, Te, He, Ti, Hi, Tl, Vb, RPM, Counter)
        
        payload[0] = 0xA2; 
        payload[1] = sendChannel;
        
        // Bestehende Sensor-Logik (unverändert)
        int16_t te = (t_ext < -250.0f) ? -25600 : (int16_t)(t_ext * 100);
        int16_t he = (h_ext < -250.0f) ? -25600 : (int16_t)(h_ext * 100);
        int16_t tl = (t_leaf < -250.0f) ? -25600 : (int16_t)(t_leaf * 100);
        int16_t ti = (t_int < -250.0f) ? -25600 : (int16_t)(t_int * 100);
        int16_t hi = (h_int < -250.0f) ? -25600 : (int16_t)(h_int * 100); 

        uint16_t vb = (v_bat < 0.1f) ? 0 : (uint16_t)(v_bat * 100);
    
        payload[2] = (te >> 8) & 0xFF; payload[3] = te & 0xFF;
        payload[4] = (he >> 8) & 0xFF; payload[5] = he & 0xFF;
        payload[6] = (ti >> 8) & 0xFF; payload[7] = ti & 0xFF;
        payload[8] = (hi >> 8) & 0xFF; payload[9] = hi & 0xFF;
        payload[10] = (tl >> 8) & 0xFF; payload[11] = tl & 0xFF;
        payload[12] = (vb >> 8) & 0xFF; payload[13] = vb & 0xFF;
    
        // RPM verpacken auf Pos 14 & 15
        uint16_t r = (uint16_t)constrain(rpm, 0, 30000);
        payload[14] = (r >> 8) & 0xFF; 
        payload[15] = r & 0xFF;
        
        // PacketCounter
        payload[16] = packetCounter++;
    
        // --- SENDEN ---
        BLEAdvertisementData oAdvertisementData;
        BLEAdvertisementData oScanResponseData;
        oAdvertisementData.setFlags(0x04); 
    
        String mData = "";
        uint16_t v_id = NEW_VENDOR_ID;
        mData += (char)(v_id & 0xFF);
        mData += (char)((v_id >> 8) & 0xFF);
        
        for(int i = 0; i < 17; i++) { 
            mData += (char)payload[i];
        }
        oAdvertisementData.setManufacturerData(mData);
        
        // HIER DIE ÄNDERUNG: Wir nutzen den dynamischen ble_name statt BRIDGE_NAME
        oScanResponseData.setName(ble_name.c_str());
    
        pAdvertising->setAdvertisementData(oAdvertisementData);
        pAdvertising->setScanResponseData(oScanResponseData);
    }
};

extern BLEBridge bleBridge;

#endif